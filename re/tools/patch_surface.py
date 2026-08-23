#!/usr/bin/env python3
"""Widen the fixed 256x256 SIMUI surface that a city-sized raster is written into.

THE SITE [CONFIRMED @ 0x10053114], inside SIMUI FUN_10052ed2 (+0x242):

    0x10053114  b8 00 01 00 00   mov eax, 0x100
    0x10053119  50               push eax
    0x1005311a  50               push eax
    0x1005311b  ff 56 0c         call dword ptr [esi+0xc]    ; surface SetSize(256, 256)

`vt+0xc` on a GZGraphicD surface is the size setter (0x10009efb: width -> this+0x24,
height -> this+0x28). ONE immediate feeds both axes, so a single dword patch resizes the
surface squarely. The surface is created in the same window-factory path (class 0x5a9,
IID 0x5df) as the map view built by FUN_10050de2.

WHY WE THINK THIS IS THE CORRUPTOR. At N=512 the process dies with a SIMGEOM red-black-tree
iterator holding 0x5baa5baa -- a value whose two 16-bit halves are IDENTICAL. That is the
signature of a 16-bit pixel fill (RGB565, the format this install runs in) written over heap
memory that holds tree nodes. A city-sized raster written into a 256-wide surface overruns it.

This is a HYPOTHESIS UNDER TEST, not an established fix. It is falsified if N=512 still
crashes with this applied.

Usage:
    py -3.12 patch_surface.py --n 512
    py -3.12 patch_surface.py --restore
    py -3.12 patch_surface.py --check
"""
import argparse
import hashlib
import os
import shutil
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TARGET = os.path.join(ROOT, "Apps", "SIMUI.DLL")
# The pristine backup deliberately lives under verify/, NOT next to this script. re/tools/ is
# whitelisted by .gitignore, and these are game-derived binaries that must never be published
# (sc3kre is public: tools and notes only). Deriving it from __file__ would both publish them and,
# after this script moved from verify/ to re/tools/, silently break --restore and strand a
# patched install.
BACKUP = os.path.join(ROOT, "verify", "citysize_mod_test", "SIMUI.DLL.shipped")
# Pristine oracle: the untouched module shipped in the repo. Used to refuse capturing another
# session's live patch as our "shipped" backup (the single-slot-backup poisoning bug). Note
# patch_citysize.py shares THIS same SIMUI.DLL.shipped slot, so the guard matters doubly here.
REFERENCE = os.path.join(ROOT, "original", "modules", "SIMUI.DLL")

OPCODE_OFF = 0x053114
OPCODE = bytes.fromhex("b8")           # mov eax, imm32
IMM_OFF = OPCODE_OFF + 1
SHIPPED = 0x100
# the two pushes and the call must be intact, or we are not on this instruction
TAIL_OFF = 0x053119
TAIL = bytes.fromhex("5050ff560c")     # push eax; push eax; call [esi+0xc]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int)
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if a.restore:
        if not os.path.exists(BACKUP):
            sys.exit("no backup at %s" % BACKUP)
        shutil.copy2(BACKUP, TARGET)
        got = sha256(TARGET)
        print("restored %s\nsha256 %s" % (TARGET, got))
        if os.path.exists(REFERENCE) and got != sha256(REFERENCE):
            print("WARNING: restored bytes != original/modules/SIMUI.DLL -- the .shipped backup "
                  "may be poisoned; consider copying from original/modules/ instead.")
        return 0

    data = bytearray(open(TARGET, "rb").read())
    cur = struct.unpack_from("<I", data, IMM_OFF)[0]
    print("target %s" % TARGET)
    print("sha256 %s" % sha256(TARGET))
    print("opcode @0x%06x : %s" % (OPCODE_OFF, bytes(data[OPCODE_OFF:OPCODE_OFF + 1]).hex()))
    print("surface size     : %d (0x%x)" % (cur, cur))
    print("tail  @0x%06x : %s %s" % (TAIL_OFF, bytes(data[TAIL_OFF:TAIL_OFF + 5]).hex(),
                                     "OK" if bytes(data[TAIL_OFF:TAIL_OFF + 5]) == TAIL
                                     else "MISMATCH"))
    if a.check:
        return 0
    if a.n is None:
        sys.exit("give --n <pixels> / --restore / --check")
    if bytes(data[OPCODE_OFF:OPCODE_OFF + 1]) != OPCODE:
        sys.exit("not a `mov eax, imm32` at 0x%06x -- refusing" % OPCODE_OFF)
    if bytes(data[TAIL_OFF:TAIL_OFF + 5]) != TAIL:
        sys.exit("tail mismatch -- refusing")
    if not (0 < a.n <= 0xFFFF):
        sys.exit("refusing implausible n=%d" % a.n)

    if not os.path.exists(BACKUP):
        if os.path.exists(REFERENCE) and sha256(TARGET) != sha256(REFERENCE):
            sys.exit("no backup yet AND Apps/SIMUI.DLL != original/modules/SIMUI.DLL -- "
                     "another session's patch may be live; refusing to capture it as 'shipped'. "
                     "Restore the install first (game_lock.ps1 -Status shows who patched it).")
        shutil.copy2(TARGET, BACKUP)
        print("backup written: %s" % BACKUP)
    struct.pack_into("<I", data, IMM_OFF, a.n)
    open(TARGET, "wb").write(bytes(data))
    print("\npatched: surface %d -> %d (4 bytes at 0x%06x)" % (cur, a.n, IMM_OFF))
    print("sha256 %s" % sha256(TARGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())

