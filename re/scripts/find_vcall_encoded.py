#!/usr/bin/env python3
"""find_vcall_encoded.py - find `call dword ptr [reg+disp8]` in 100% of .text, by ENCODING.

RESULT THIS PRODUCED (2026-08-19), and it retired a proposed re-carve: across all 30 shipped
modules only **12** such dispatches sit in uncarved code, **8 of them one byte-identical
statically-linked FPU helper duplicated into 4 DLLs**, and **SIMRCI has ZERO**. So the U-065
coverage hole does not hide the zone rect writer's caller, and re-carving SIMRCI would not have
found it. Requires `capstone` (5.0.7 used).

WHY, and why this beats a re-carve. U-065 measured that the decompiled export covers only
96-98% of .text, so every sweep over it is a negative about 97% of the code. The obvious fix is to
re-carve the gaps in Ghidra -- but a re-carve mutates a project two other live sessions depend on,
the headless driver hardcodes -readOnly, and it invalidates every export. Unnecessary here: a
virtual call through a vtable slot has ONE fixed encoding family, so it can be found in the raw
bytes with no disassembly of the surrounding function and no notion of where functions begin.

    call dword ptr [eax+disp8]   FF 50 <disp8>
                   [ecx+disp8]   FF 51 <disp8>
                   [edx+disp8]   FF 52 <disp8>
                   [ebx+disp8]   FF 53 <disp8>
                   [esp+disp8]   FF 54 24 <disp8>     (SIB, handled separately)
                   [ebp+disp8]   FF 55 <disp8>
                   [esi+disp8]   FF 56 <disp8>
                   [edi+disp8]   FF 57 <disp8>

FALSE POSITIVES ARE REAL and are filtered, not ignored: those three bytes also occur inside other
instructions' operands and inside data. Every candidate is verified by disassembling a window that
ENDS at the candidate with capstone and requiring that the instruction stream lands exactly on it
(a byte sequence that is only an operand of a longer instruction will not be reachable that way).
Candidates that survive are reported with their decode; candidates that fail are counted, so the
filter's own effect is visible rather than silent.

POSITIVE CONTROL, checked by --selftest against facts established by hand earlier: PlaceZone's two
cell-map writes at 0x10035c1f and 0x10035f17 are `ff 50 3c` and MUST be found.
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "re", "scripts"))
from read_vtables import PE  # noqa: E402

import capstone  # noqa: E402

REGS = {0x50: "eax", 0x51: "ecx", 0x52: "edx", 0x53: "ebx",
        0x55: "ebp", 0x56: "esi", 0x57: "edi"}


def carved_intervals(mod):
    """Union of exported function extents for a module, from the export filenames+headers."""
    d = os.path.join(ROOT, "re", "ghidra_export_" + mod, "functions")
    if not os.path.isdir(d):
        return []
    iv = []
    for fn in os.listdir(d):
        m = re.match(r"([0-9a-f]{8})_", fn)
        if not m or not fn.endswith(".c"):
            continue
        a = int(m.group(1), 16)
        with open(os.path.join(d, fn), encoding="utf-8", errors="replace") as fh:
            h = fh.readline()
        ms = re.search(r"\((\d+) bytes\)", h)
        iv.append((a, a + (int(ms.group(1)) if ms else 0)))
    iv.sort()
    un = []
    for s, e in iv:
        if un and s <= un[-1][1]:
            un[-1] = (un[-1][0], max(un[-1][1], e))
        else:
            un.append((s, e))
    return un


def in_carved(un, va):
    lo, hi = 0, len(un) - 1
    while lo <= hi:
        m = (lo + hi) // 2
        if va < un[m][0]:
            hi = m - 1
        elif va >= un[m][1]:
            lo = m + 1
        else:
            return True
    return False


def verify(md, data, rp, idx, want_len):
    """Is a real instruction boundary at raw offset idx? Disassemble a window ending there."""
    for back in (16, 24, 32, 48):
        start = max(0, idx - back)
        for insn in md.disasm(data[start:idx + want_len + 8], start):
            if insn.address == idx:
                return insn
            if insn.address > idx:
                break
    return None


def scan(dllpath, mod, disps):
    pe = PE(dllpath)
    sec = pe.section(".text")
    if not sec:
        return []
    n, sva, vsize, rp, rs = sec
    base = pe.imagebase + sva
    d = pe.data
    un = carved_intervals(mod)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out, rejected = [], 0
    for i in range(rp, rp + rs - 3):
        if d[i] != 0xFF:
            continue
        modrm = d[i + 1]
        if modrm in REGS and d[i + 2] in disps:
            ln = 3
        elif modrm == 0x54 and d[i + 2] == 0x24 and d[i + 3] in disps:
            ln = 4
        else:
            continue
        insn = verify(md, d, rp, i, ln)
        if insn is None or insn.mnemonic != "call":
            rejected += 1
            continue
        va = base + (i - rp)
        out.append((va, insn.mnemonic + " " + insn.op_str, d[i + 2] if ln == 3 else d[i + 3],
                    in_carved(un, va)))
    return out, rejected


def selftest():
    ok = True

    def chk(l, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print("  [%s] %s = %r (want %r)" % ("OK" if good else "FAIL", l, got, want))

    hits, rej = scan(os.path.join(ROOT, "original", "modules", "SIMRCI.DLL"), "simrci", {0x3C})
    vas = {h[0] for h in hits}
    # positive control: PlaceZone's two writes, established by hand from the bytes earlier
    chk("PlaceZone write @0x10035c1f found", 0x10035C1F in vas, True)
    chk("PlaceZone write @0x10035f17 found", 0x10035F17 in vas, True)
    both = [h for h in hits if h[0] in (0x10035C1F, 0x10035F17)]
    chk("both decode as call [eax+0x38..0x40] family",
        all(h[1].startswith("call dword ptr [eax + 0x3c]") for h in both), True)
    chk("both are inside CARVED code (they are in PlaceZone)", all(h[3] for h in both), True)
    # NEGATIVE CONTROL for verify(). The first version of this selftest asserted `rej > 0`, which
    # FAILED -- not because the filter is broken but because no candidate in SIMRCI at disp 0x3c
    # happened to be a false positive. That was a wrong test, not a wrong tool. The honest check is
    # a crafted case: `b8 ff 50 3c 00` is `mov eax, 0x3c50ff`, which CONTAINS the bytes ff 50 3c at
    # offset 1 without there being an instruction boundary there.
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    blob = b"\x90" * 16 + b"\xb8\xff\x50\x3c\x00" + b"\x90" * 8
    fake = 16 + 1                                   # the ff inside the mov's immediate
    chk("verify() rejects ff 50 3c inside a mov immediate",
        verify(md, blob, 0, fake, 3), None)
    real = len(b"\x90" * 16 + b"\xb8\xff\x50\x3c\x00") + 8
    blob2 = b"\x90" * 16 + b"\xff\x50\x3c" + b"\x90" * 8
    chk("verify() accepts a genuine call at a boundary",
        (verify(md, blob2, 0, 16, 3) or type("x", (), {"mnemonic": None})).mnemonic, "call")
    print("  [%s] selftest overall  (%d verified hits, %d rejected candidates)"
          % ("OK" if ok else "FAIL", len(hits), rej))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    disps = {0x38, 0x3C, 0x40}
    moddir = os.path.join(ROOT, "original", "modules")
    print("call dword ptr [reg+0x38/0x3c/0x40] across 100%% of .text, by encoding.\n")
    gap_total = 0
    for f in sorted(os.listdir(moddir)):
        if not f.upper().endswith(".DLL"):
            continue
        mod = f[:-4].lower()
        hits, rej = scan(os.path.join(moddir, f), mod, disps)
        gaps = [h for h in hits if not h[3]]
        if hits:
            print("  %-14s %5d verified (%4d rejected) | %d IN UNCARVED GAPS"
                  % (mod, len(hits), rej, len(gaps)))
        for va, txt, disp, carved in gaps:
            print("        GAP 0x%08x  %s" % (va, txt))
            gap_total += 1
    print("\nTOTAL hits in uncarved gaps, all modules: %d" % gap_total)
