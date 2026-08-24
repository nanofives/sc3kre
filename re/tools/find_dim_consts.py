#!/usr/bin/env python3
"""Find allocation sizes derived from a 256-tile map -- siblings of the confirmed defect.

The confirmed one is SIMDIRT 0x100166e0 `push 0x20402` = 257*257*2, one ushort per vertex of a
256-tile map (N+1 vertices per axis). Anything else sized from 255/256/257/258 SQUARED is a
candidate for the same bug.

Matching is on the real immediate VALUE from capstone's operand detail. An earlier version of
this script compared the hex string as a substring, which matched "0x100" inside addresses like
"0x10038690" and produced hundreds of false hits -- do not reintroduce that.

Filter: the immediate must be followed by a `call` within 24 bytes, so it is plausibly being
passed as an allocation size rather than being a mask, colour or resource id. Single-axis values
(256, 512) are excluded as hopelessly ambiguous; only squared-area values are reported.
"""
import os
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32, x86_const

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pe_vtable import PE, MODDIR, ROOT  # noqa: E402

MD = Cs(CS_ARCH_X86, CS_MODE_32)
MD.detail = True

WANTED = {}
for base in (255, 256, 257, 258):
    for w, wn in ((1, "byte"), (2, "ushort"), (4, "dword")):
        WANTED[base * base * w] = "%d^2 x %d (%s per vertex)" % (base, w, wn)
        WANTED[base * base * w + 2] = "%d^2 x %d + 2" % (base, w)

EXPORT = {
    "SIMDIRT.DLL": "ghidra_export_simdirt", "SIMGEOM.DLL": "ghidra_export_simgeom",
    "SIMSPR.DLL": "ghidra_export_simspr", "SIMRCI.DLL": "ghidra_export_simrci",
    "SIMMISC.DLL": "ghidra_export_simmisc", "SIMNTWRK.DLL": "ghidra_export_simntwrk",
    "SIMUI.DLL": "ghidra_export_simui", "SIMECO.DLL": "ghidra_export_simeco",
    "SIMSERV.DLL": "ghidra_export_simserv", "SimTransit.dll": "ghidra_export_simtransit",
    "STRTSIM.DLL": "ghidra_export_strtsim", "SIMBABLD.DLL": "ghidra_export_simbabld",
    "SIMADV.DLL": "ghidra_export_simadv", "SIMUTIL.DLL": "ghidra_export_simutil",
    "SIMDSTR.DLL": "ghidra_export_simdstr", "SIMINIT.DLL": "ghidra_export_siminit",
}


def fn_starts(expdir):
    d = os.path.join(ROOT, "re", expdir, "functions")
    if not os.path.isdir(d):
        return []
    return sorted(int(f.split("_")[0], 16) for f in os.listdir(d) if f.endswith(".c"))


def imms(ins):
    return [o.imm for o in ins.operands if o.type == x86_const.X86_OP_IMM]


def main():
    print("area-sized allocation immediates derived from a 256-tile map")
    print("candidate values: %s\n" % ", ".join("0x%x" % v for v in sorted(WANTED)))
    total = 0
    for fname, expdir in sorted(EXPORT.items()):
        path = os.path.join(MODDIR, fname)
        if not os.path.exists(path):
            continue
        try:
            pe = PE(path)
        except AssertionError:
            continue
        sec = pe.section(".text")
        if not sec:
            continue
        _n, sva, _vs, rp, rs = sec
        starts = fn_starts(expdir)
        rows = []
        for ins in MD.disasm(pe.data[rp:rp + rs], pe.imagebase + sva):
            for v in imms(ins):
                if v not in WANTED:
                    continue
                o = pe.off(ins.address)
                if o is None:
                    continue
                if not any(i.mnemonic.startswith("call")
                           for i in MD.disasm(pe.data[o:o + 24], ins.address)):
                    continue
                owner = [s for s in starts if s <= ins.address]
                rows.append((ins.address, v, WANTED[v], owner[-1] if owner else 0,
                             "%s %s" % (ins.mnemonic, ins.op_str)))
        if rows:
            print("=== %s ===" % fname)
            for addr, v, desc, owner, txt in rows:
                print("  0x%08x  %-24s = %-8d %-28s  in FUN_%08x"
                      % (addr, txt, v, desc, owner))
            print()
            total += len(rows)
    print("total: %d candidate(s)" % total)


if __name__ == "__main__":
    main()

