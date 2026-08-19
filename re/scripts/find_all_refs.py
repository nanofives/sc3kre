#!/usr/bin/env python3
"""find_all_refs.py - EVERY reference to an address, over 100% of a module, four ways.

BUILT TO RE-CHECK RECORDED ZEROS, and it changed one and confirmed another on its first outing
(2026-08-19):
  * `[FALSIFIED]` U-057's "`0x10032a96`, `0x10034342` and both thunks have ZERO references of any
    kind". All four have vtable-slot references. The tool that produced that zero could not see
    vtable contents -- which U-057's very next sentence says.
  * `[CONFIRMED, and upgraded]` CITY_SAVE.md's three INI-loader stubs `0x1000e837` / `0x1001599d`
    / `0x1002115d` really are unreferenced. That claim previously carried the caveat that a byte
    scan "cannot find call sites by construction" because `CALL rel32` encodes a displacement.
    This tool decodes displacements, so the negative now covers all four reference classes.

Requires `capstone`.

⚠️ **KNOWN LIMITATION, and it briefly fooled me.** The relative CALL/JMP classes are
capstone-verified to sit on an instruction boundary. The **aligned-dword and unaligned-immediate
classes are NOT** -- they are raw pattern matches, because an absolute address embedded in an
instruction has no self-evident boundary. So a reported `imm` hit tells you the bytes are there,
not that an instruction starts where you think.

To decode one correctly, do NOT just back up until something spans the hit -- that finds a decode,
not the right one. Disassemble from EVERY start offset in a ~24-byte window and take the reading
the surrounding stream agrees with. Worked example: `0x1006cdac` at `0x10011539` in GZGraphicD
backs up to a plausible-looking `cmp eax, 0x1006cdac`, and that is WRONG. The raw bytes are
`e8 1d1b0000 | 80 3d ac cd 06 10 00 | 8d 4d 94`: a `call` ending exactly at `0x10011537`, then
`cmp byte ptr [0x1006cdac], 0`, then `lea ecx,[ebp-0x6c]`. The true instruction starts at
`0x10011537` and it is a READ, not a compare-against-the-address.

Ghidra xrefs only see carved code, which is 96-98% of .text (U-065). This sees all of it:

  1. relative CALL   E8 <rel32>   target == VA
  2. relative JMP    E9 <rel32>   target == VA        (adjustor thunks land here)
  3. aligned dword   == VA                            (vtable slots, function tables)
  4. unaligned imm   == VA in .text                   (push/mov of a function pointer)

Each relative hit is capstone-verified to be a real instruction boundary, so bytes that merely
happen to encode the right rel32 inside another instruction are rejected rather than counted.

POSITIVE CONTROLS baked into --selftest, all established by hand earlier in this project:
  * 0x10032afa is referenced by exactly ONE aligned dword (vtable 0x1004d274 slot 14, = +0x38)
    and by exactly ONE relative JMP -- the adjustor thunk 0x1003433a's `e9 b8e7ffff`.
  * 0x1003591f (PlaceZone) is referenced by exactly ONE aligned dword (vtable 0x1004d1e0 +0x88)
    and by NO relative call -- it is dispatched, never called directly.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "re", "scripts"))
from read_vtables import PE  # noqa: E402
import capstone  # noqa: E402


def verify_at(md, data, idx, want):
    for back in (16, 24, 32, 48):
        s = max(0, idx - back)
        for insn in md.disasm(data[s:idx + want + 8], s):
            if insn.address == idx:
                return insn
            if insn.address > idx:
                break
    return None


def allrefs(pe, va):
    d = pe.data
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = {"call": [], "jmp": [], "dword": [], "imm": []}
    tsec = pe.section(".text")
    n, sva, vs, rp, rs = tsec
    base = pe.imagebase + sva
    for i in range(rp, rp + rs - 4):
        op = d[i]
        if op in (0xE8, 0xE9):
            rel, = struct.unpack_from("<i", d, i + 1)
            if i + 5 - rp + base + rel == va:
                insn = verify_at(md, d, i, 5)
                if insn and insn.mnemonic in ("call", "jmp"):
                    out["call" if op == 0xE8 else "jmp"].append(base + (i - rp))
    pat = struct.pack("<I", va)
    for name, sva2, vs2, rp2, rs2 in pe.sections:
        b2 = pe.imagebase + sva2
        for i in range(rp2, rp2 + rs2 - 3):
            if d[i:i + 4] == pat:
                a = b2 + (i - rp2)
                if a % 4 == 0:
                    out["dword"].append((name, a))
                elif name == ".text":
                    out["imm"].append(a)
    return out


def report(pe, va, label=""):
    r = allrefs(pe, va)
    tot = sum(len(v) for v in r.values())
    print("0x%08x %s-- %d reference(s) over 100%% of the module" % (va, label, tot))
    for k, lbl in (("call", "relative CALL"), ("jmp", "relative JMP"),
                   ("dword", "aligned dword"), ("imm", "unaligned imm in .text")):
        for x in r[k]:
            print("    %-22s %s" % (lbl, ("0x%08x (%s)" % (x[1], x[0])) if k == "dword"
                                     else "0x%08x" % x))
    if tot == 0:
        print("    (none)")
    return r


def selftest(pe):
    ok = True

    def chk(l, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print("  [%s] %s = %r (want %r)" % ("OK" if good else "FAIL", l, got, want))

    r = allrefs(pe, 0x10032AFA)
    chk("0x10032afa aligned dwords", [x[1] for x in r["dword"]], [0x1004D2AC])
    # NOTE the +3: the thunk BODY starts at 0x1003433a with `83 e9 10` (sub ecx,0x10), so its
    # `e9 <rel32>` sits at 0x1003433d. This tool reports the address of the JMP INSTRUCTION, not
    # of the enclosing thunk. The first version of this check expected 0x1003433a and failed --
    # a wrong expectation of mine, not a wrong tool. Same class of slip as confusing a function's
    # start with the slot that holds it.
    chk("0x10032afa relative JMPs (the adjustor thunk's e9, at thunk+3)", r["jmp"], [0x1003433D])
    chk("0x10032afa relative CALLs", r["call"], [])
    r = allrefs(pe, 0x1003591F)
    chk("PlaceZone aligned dwords (its vtable slot)", [x[1] for x in r["dword"]], [0x1004D268])
    chk("PlaceZone relative CALLs (dispatched, never called)", r["call"], [])
    print("  [%s] selftest overall" % ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    dll = os.path.join(ROOT, "original", "modules", "SIMRCI.DLL")
    if "--pe" in a:
        dll = a[a.index("--pe") + 1]
    pe = PE(dll)
    if "--selftest" in a:
        sys.exit(selftest(pe))
    skip = set()
    for i, x in enumerate(a):
        if x == "--pe":
            skip.add(i + 1)                 # the path is a value, not an address
    for i, x in enumerate(a):
        if x.startswith("--") or i in skip:
            continue
        report(pe, int(x, 16))
        print()
