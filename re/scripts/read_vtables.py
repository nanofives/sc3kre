#!/usr/bin/env python3
"""read_vtables.py - read vtable CONTENTS straight out of a PE's bytes. No Ghidra, no lock.

WHY THIS EXISTS. Four sessions on the zone subsystem were blocked by one recorded fact:
`re/ghidra_export_simrci/globals.csv` holds exactly ONE `vftable` line, so the text export carries
no vtable contents, "so it structurally cannot show who dispatches into a vtable slot" and only
live Ghidra can answer. That conclusion was about the EXPORT, and it was quietly generalised into
a claim about what is knowable. It is not: a vtable is a run of dwords in `.rdata`, and the shipped
DLL is right there in `original\\modules\\`. This script reads them.

WHAT IT ANSWERS, that the export cannot:
  * which vtable slot holds function F, and therefore F's dispatch offset  (`--find`)
  * what a vtable's slots are, in order                                    (`--vt`)
  * every dword in the image equal to an address                           (`--xref`)
  * where a vtable BEGINS -- by finding the addresses inside a pointer run
    that `.text` loads as an immediate, i.e. the `mov [reg+N], <vtable>`
    stores in the constructor                                              (`--starts`)

The `--starts` step is the load-bearing one. Adjacent vtables in `.rdata` are back-to-back with no
separator, so "scan until a non-.text pointer" merges them: on SIMRCI that gives one 180-pointer
run spanning ten vtables, and any slot number derived from it is wrong. Only the constructor knows
where a vtable starts.

TRAP THIS SCRIPT EXISTS TO KILL. Slot numbers had been inferred from the STRIDE of a block of
8-byte adjustor thunks: thunk at block index k was assumed to occupy vtable offset k*4. That
happened to be right for SIMRCI's zone layer, but it is an assumption about layout, not a
measurement, and it is circular when the offset it produces is then cited as the evidence for the
slot. Measure it here instead.

Usage:
  py -3.12 re/scripts/read_vtables.py --selftest
  py -3.12 re/scripts/read_vtables.py --find 10032afa 10032a96
  py -3.12 re/scripts/read_vtables.py --starts 1004d000 1004d400
  py -3.12 re/scripts/read_vtables.py --vt 1004d274 --slots 18
  py -3.12 re/scripts/read_vtables.py --pe original/modules/SIMUTIL.DLL --find 10010593
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT = os.path.join(ROOT, "original", "modules", "SIMRCI.DLL")


class PE:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as fh:
            self.data = fh.read()
        d = self.data
        e_lfanew, = struct.unpack_from("<I", d, 0x3C)
        assert d[e_lfanew:e_lfanew + 4] == b"PE\0\0", "not a PE: %s" % path
        coff = e_lfanew + 4
        nsec, = struct.unpack_from("<H", d, coff + 2)
        sizeopt, = struct.unpack_from("<H", d, coff + 16)
        opt = coff + 20
        magic, = struct.unpack_from("<H", d, opt)
        assert magic == 0x10B, "not PE32 (magic 0x%x)" % magic
        self.imagebase, = struct.unpack_from("<I", d, opt + 28)
        self.sections = []
        st = opt + sizeopt
        for i in range(nsec):
            o = st + i * 40
            name = d[o:o + 8].rstrip(b"\0").decode("latin1")
            vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", d, o + 8)
            self.sections.append((name, va, vsize, rawptr, rawsize))

    def sec_of_va(self, va):
        r = va - self.imagebase
        for name, sva, vsize, rp, rs in self.sections:
            if sva <= r < sva + max(vsize, rs):
                return name, sva, vsize, rp, rs
        return None

    def off(self, va):
        """Raw file offset of `va`, or None if it has no backing bytes."""
        s = self.sec_of_va(va)
        if not s:
            return None
        name, sva, vsize, rp, rs = s
        delta = (va - self.imagebase) - sva
        if delta >= rs:
            return None                      # virtual padding: no raw bytes
        return rp + delta

    def dword(self, va):
        o = self.off(va)
        if o is None or o + 4 > len(self.data):
            return None
        return struct.unpack_from("<I", self.data, o)[0]

    def section(self, name):
        for s in self.sections:
            if s[0] == name:
                return s
        return None

    def iter_dwords(self, aligned=True, only=None):
        """(section, va, value) for dwords with raw backing. aligned=False scans every byte
        offset, which is what finding an IMMEDIATE inside an instruction requires."""
        d = self.data
        for name, sva, vsize, rp, rs in self.sections:
            if only and name != only:
                continue
            base = self.imagebase + sva
            step = 4 if aligned else 1
            start = ((-base) % 4) if aligned else 0
            for delta in range(start, rs - 3, step):
                yield name, base + delta, struct.unpack_from("<I", d, rp + delta)[0]


def cmd_find(pe, addrs):
    want = {a: [] for a in addrs}
    for name, va, val in pe.iter_dwords(aligned=True):
        if val in want:
            want[val].append((name, va))
    for a in addrs:
        print("0x%08x : %d aligned dword slot(s) hold this value" % (a, len(want[a])))
        for name, va in want[a]:
            print("    at 0x%08x (%s)" % (va, name))
    return want


def cmd_starts(pe, lo, hi):
    """Addresses in [lo,hi) that .text loads as an immediate = vtable starts."""
    d = pe.data
    sec = pe.section(".text")
    name, sva, vsize, rp, rs = sec
    hits = {}
    for i in range(rs - 3):
        v, = struct.unpack_from("<I", d, rp + i)
        if lo <= v < hi:
            hits.setdefault(v, []).append(pe.imagebase + sva + i)
    print("vtable starts in [0x%08x, 0x%08x) -- addresses .text loads as an immediate:" % (lo, hi))
    for v in sorted(hits):
        print("  0x%08x   loaded from %d site(s): %s"
              % (v, len(hits[v]), ", ".join("0x%08x" % x for x in hits[v][:6])))
    return sorted(hits)


def cmd_vt(pe, addr, span):
    print("=== vtable at 0x%08x ===" % addr)
    print(" slot  offset    value      target")
    for i in range(span):
        va = addr + i * 4
        v = pe.dword(va)
        if v is None:
            print("  (no raw bytes at 0x%08x)" % va)
            return
        s = pe.sec_of_va(v)
        tag = s[0] if s else "<not in image>"
        note = "" if tag == ".text" else "   <-- NOT .text; run of code pointers ends here"
        print(" %4d  +0x%-5x 0x%08x  %s%s" % (i, i * 4, v, tag, note))
        if tag != ".text":
            return


def cmd_xref(pe, addr):
    hits = [(n, va) for n, va, val in pe.iter_dwords(aligned=True) if val == addr]
    print("0x%08x appears as an aligned dword in %d place(s)" % (addr, len(hits)))
    for n, va in hits:
        print("    0x%08x (%s)" % (va, n))
    return hits


# --- selftest: every check has an answer known by hand -----------------------------------------

def selftest(pe):
    """Facts checked here were established independently (functions.csv, the decompilation, or
    hand-decoded instruction bytes) BEFORE this script existed."""
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print("  [%s] %s = %r (want %r)" % ("OK" if good else "FAIL", label, got, want))

    chk("imagebase", pe.imagebase, 0x10000000)
    chk("has .text", pe.section(".text") is not None, True)
    chk("0x10032afa section", pe.sec_of_va(0x10032afa)[0], ".text")

    # The adjustor thunk 0x1003433a is 8 bytes: `sub ecx,0x10` then `jmp 0x10032afa`.
    # Hand-decoded: 83 e9 10 | e9 <rel32>, rel32 = target - (0x1003433a+3+5).
    o = pe.off(0x1003433a)
    raw = pe.data[o:o + 8]
    chk("thunk 0x1003433a bytes", raw.hex(), "83e910e9b8e7ffff")
    rel, = struct.unpack_from("<i", raw, 4)
    chk("thunk 0x1003433a jmp target", 0x1003433a + 3 + 5 + rel, 0x10032afa)

    # functions.csv already recorded: 0x10032a96 is reached through cSC3ZoneLayer vtable
    # 0x1004d1e0 slot 15 via the adjustor thunk 0x10034342. So 0x1004d1e0+15*4 must hold it.
    chk("0x1004d1e0 slot 15", pe.dword(0x1004d1e0 + 15 * 4), 0x10034342)
    # and functions.csv recorded 0x1003547c as slot 32 of that same vtable
    chk("0x1004d1e0 slot 32", pe.dword(0x1004d1e0 + 32 * 4), 0x1003547c)
    # a value that must NOT be in a vtable: the thunk block is code, so reading a thunk
    # ADDRESS as a dword must not yield a .text pointer
    v = pe.dword(0x1003433a)
    s = pe.sec_of_va(v)
    chk("dword AT a code address is not a .text ptr", s is None or s[0] != ".text", True)

    print("  [%s] selftest overall" % ("OK" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    a = sys.argv[1:]
    path = DEFAULT
    if "--pe" in a:
        p = a[a.index("--pe") + 1]
        path = p if os.path.isabs(p) else os.path.join(ROOT, p)
    pe = PE(path)
    print("PE %s   imagebase 0x%08x" % (path, pe.imagebase))
    for n, sva, vs, rp, rs in pe.sections:
        print("   %-8s va 0x%08x vsize %8d rawsize %8d" % (n, pe.imagebase + sva, vs, rs))
    print()
    if "--selftest" in a:
        return selftest(pe)
    did = False
    if "--find" in a:
        i = a.index("--find") + 1
        cmd_find(pe, [int(x, 16) for x in a[i:] if not x.startswith("--")])
        did = True
    if "--starts" in a:
        i = a.index("--starts") + 1
        cmd_starts(pe, int(a[i], 16), int(a[i + 1], 16))
        did = True
    if "--vt" in a:
        span = int(a[a.index("--slots") + 1]) if "--slots" in a else 64
        cmd_vt(pe, int(a[a.index("--vt") + 1], 16), span)
        did = True
    if "--xref" in a:
        cmd_xref(pe, int(a[a.index("--xref") + 1], 16))
        did = True
    if not did:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
