#!/usr/bin/env python3
"""Shared PE + vtable helper, and a search for a class by its vtable-slot GETTER FINGERPRINT.

Imported by `find_dim_consts.py` for its `PE` reader and path constants; runnable on its own to
find every class whose chosen slots are all trivial field accessors.

THE SEARCH, mechanical and guess-free:
  1. Locate vtable STARTS the only reliable way (as `re/scripts/read_vtables.py --starts` does):
     an address in a read-only section that `.text` loads as an IMMEDIATE is a
     `mov [reg+N], <vtable>` store in a constructor. Adjacent vtables sit back-to-back with no
     separator, so scanning for "a run of code pointers" merges them and every slot number derived
     that way is wrong. Only the constructor knows where a vtable begins.
  2. For each start, read the dwords at the requested slots (default `+0xcc` / `+0xd0`).
  3. Accept only when ALL targets are trivial accessors -- `mov eax,[ecx+N] ; ret` -- and report
     the field offsets, flagging whether they are adjacent.

⚠️ A MATCHING SLOT NUMBER IS NOT EVIDENCE. Unrelated classes collide on slot numbers freely. This
script's `+0x54`/`+0x5c` search returned a SIMINIT graphics-device descriptor that looked exactly
like the city-parameters class being hunted, and the wrong identification survived several hours
before a tracker note contradicted it. Always corroborate with a second, independent witness --
the constructor's defaults, an arity fingerprint, a string or CLSID xref, or the call topology.

Usage:
  py -3.12 re/tools/pe_vtable.py                      # default: slots 0xcc / 0xd0
  py -3.12 re/tools/pe_vtable.py --slots=0x54,0x5c    # any slot set
  py -3.12 re/tools/pe_vtable.py --slots=0xc SIMSPR.DLL
"""
import os
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

MD = Cs(CS_ARCH_X86, CS_MODE_32)
# Derived, never hardcoded: this file lives in <repo>/re/tools/, so the repo root is three
# dirname() levels up. A machine-specific absolute path would work only on the machine it was
# written on, and would leak a local layout into a public repo.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODDIR = os.path.join(ROOT, "original", "modules")


class PE:
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        d = self.data
        e, = struct.unpack_from("<I", d, 0x3C)
        assert d[e:e + 4] == b"PE\0\0", path
        coff = e + 4
        nsec, = struct.unpack_from("<H", d, coff + 2)
        sizeopt, = struct.unpack_from("<H", d, coff + 16)
        opt = coff + 20
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
        s = self.sec_of_va(va)
        if not s:
            return None
        _n, sva, _vs, rp, rs = s
        delta = (va - self.imagebase) - sva
        return None if delta >= rs else rp + delta

    def dword(self, va):
        o = self.off(va)
        return None if o is None or o + 4 > len(self.data) else struct.unpack_from("<I", self.data, o)[0]

    def section(self, name):
        for s in self.sections:
            if s[0] == name:
                return s
        return None

    def is_text(self, va):
        s = self.sec_of_va(va)
        return bool(s) and s[0] == ".text"


def vtable_starts(pe):
    """Addresses in any non-.text raw section that .text loads as an immediate."""
    txt = pe.section(".text")
    if not txt:
        return []
    _n, sva, _vs, rp, rs = txt
    ro = []
    for name, s2, vs2, rp2, rs2 in pe.sections:
        if name != ".text" and rs2:
            ro.append((pe.imagebase + s2, pe.imagebase + s2 + rs2))
    if not ro:
        return []
    d = pe.data
    hits = set()
    for i in range(rs - 3):
        v, = struct.unpack_from("<I", d, rp + i)
        if any(lo <= v < hi for lo, hi in ro):
            hits.add(v)
    return sorted(hits)


def trivial_getter(pe, va):
    """(field_offset, kind) when `va` is `mov eax,[ecx+N] ; ret[ imm]`, else None."""
    o = pe.off(va)
    if o is None:
        return None
    ins = list(MD.disasm(pe.data[o:o + 16], va))
    if len(ins) < 2:
        return None
    a, b = ins[0], ins[1]
    if b.mnemonic != "ret":
        return None
    if a.mnemonic != "mov" or not a.op_str.startswith("eax, dword ptr [ecx"):
        return None
    inner = a.op_str.split("[", 1)[1].rstrip("]")
    if inner == "ecx":
        n = 0
    elif "+" in inner:
        n = int(inner.split("+")[1].strip(), 0)
    else:
        return None
    imm = int(b.op_str, 0) if b.op_str else 0
    return n, imm


def scan(pe, slots):
    starts = vtable_starts(pe)
    out = []
    for vt in starts:
        vals = []
        for s in slots:
            v = pe.dword(vt + s)
            if v is None or not pe.is_text(v):
                vals = None
                break
            g = trivial_getter(pe, v)
            if g is None:
                vals = None
                break
            vals.append((s, v, g))
        if vals:
            out.append((vt, vals))
    return len(starts), out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pes = args or ([os.path.join(ROOT, "original", "SC3U.exe")] +
                   [os.path.join(MODDIR, f) for f in sorted(os.listdir(MODDIR))
                    if f.lower().endswith((".dll", ".exe"))])
    sl = [a for a in sys.argv[1:] if a.startswith("--slots=")]
    slots = tuple(int(x, 0) for x in sl[0].split("=", 1)[1].split(",")) if sl else (0xcc, 0xd0)
    print("looking for vtables whose +0x%x and +0x%x are BOTH trivial getters\n" % slots)
    for p in pes:
        try:
            pe = PE(p)
        except AssertionError:
            continue
        n, hits = scan(pe, slots)
        tag = os.path.basename(p)
        if not hits:
            print("%-18s %4d vtable starts, 0 candidate(s)" % (tag, n))
            continue
        print("%-18s %4d vtable starts, %d CANDIDATE(S)" % (tag, n, len(hits)))
        for vt, vals in hits:
            desc = "  ".join("+0x%x -> 0x%08x (reads this+0x%x, ret %d)"
                             % (s, v, g[0], g[1]) for s, v, g in vals)
            offs = [g[0] for _s, _v, g in vals]
            adj = "ADJACENT" if len(offs) == 2 and offs[1] - offs[0] == 4 else "not adjacent"
            print("   vtable 0x%08x : %s   [%s]" % (vt, desc, adj))
        print()


if __name__ == "__main__":
    main()
