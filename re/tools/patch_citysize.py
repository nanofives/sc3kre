#!/usr/bin/env python3
"""Retarget the New City dialog's largest city-size option in Apps/SIMUI.DLL.

THE SITE. SIMUI FUN_1005eb40 maps the four size radio buttons to a tile count and stores it
in the dialog at +0x174, which is then handed to the terrain generator as a square (N,N):

    VA 0x1005ecf8  c7 86 74 01 00 00 | 00 01 00 00   mov [esi+0x174], 0x100   <- the "else" arm
    VA 0x1005ed04  c7 86 74 01 00 00 | c0 00 00 00   mov [esi+0x174], 0xc0
    VA 0x1005ed10  c7 86 74 01 00 00 | 80 00 00 00   mov [esi+0x174], 0x80
    VA 0x1005ed1c  c7 86 74 01 00 00 | 40 00 00 00   mov [esi+0x174], 0x40

Only the 0x100 arm is touched, so the 64/128/192 options keep shipping behaviour and act as
controls: if the patched run breaks in a way the other three also show, the cause is not N.

WHY THIS IS THE RIGHT SITE. Downstream is size-agnostic. The generator's vt+0x0c
(SIMDIRT 0x1001742c) stores N+1 as the vertex count and heap-allocates four grids at
(N+1)x(N+1); the city's dimensions land in cSC3City +0x3c/+0x40 and every consumer reads
them through vtable slots +0xcc/+0xd0. No fixed-size buffer sits on that path -- the one
256-entry array in the generator (0x10017c2d local_42c) is a histogram indexed by a BYTE,
not by N.

Usage:
    py -3.12 patch_citysize.py --n 512          # apply, backing up first
    py -3.12 patch_citysize.py --restore        # put the shipped DLL back
    py -3.12 patch_citysize.py --check          # report current state only
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
REFERENCE = os.path.join(ROOT, "original", "modules", "SIMUI.DLL")

# Shipped SIMUI.DLL, verified equal to original/modules/SIMUI.DLL before any patch.
SHIPPED_SHA256 = "2efdf265d3ce3eec85920ead44e8bb9b7c0d08a1994fd29a3674817c692103fd"

OPCODE_OFF = 0x05ECF8          # file offset of the mov
IMM_OFF = OPCODE_OFF + 6       # file offset of its imm32
OPCODE = bytes.fromhex("c78674010000")   # mov dword ptr [esi+0x174], imm32
SHIPPED_N = 0x100

# The three arms we must NOT disturb, as (file offset, expected imm).
CONTROLS = [(0x05ED04 + 6, 0xc0), (0x05ED10 + 6, 0x80), (0x05ED1C + 6, 0x40)]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def read_imm(data, off):
    return struct.unpack_from("<I", data, off)[0]


def describe(data):
    print("  opcode @0x%06x : %s" % (OPCODE_OFF, data[OPCODE_OFF:OPCODE_OFF + 6].hex()))
    print("  largest option   : %d (0x%x)" % (read_imm(data, IMM_OFF),) * 1
          if False else "  largest option   : %d (0x%x)"
          % (read_imm(data, IMM_OFF), read_imm(data, IMM_OFF)))
    for off, want in CONTROLS:
        got = read_imm(data, off)
        flag = "OK" if got == want else "CHANGED"
        print("  control @0x%06x : %d (expected %d) %s" % (off, got, want, flag))


def load():
    if not os.path.exists(TARGET):
        sys.exit("target not found: %s" % TARGET)
    return bytearray(open(TARGET, "rb").read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, help="new tile count for the largest option")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    if a.restore:
        if not os.path.exists(BACKUP):
            sys.exit("no backup at %s -- nothing to restore" % BACKUP)
        shutil.copy2(BACKUP, TARGET)
        got = sha256(TARGET)
        print("restored from %s" % BACKUP)
        print("sha256 %s  %s" % (got, "MATCHES shipped" if got == SHIPPED_SHA256 else "MISMATCH"))
        return 0 if got == SHIPPED_SHA256 else 1

    data = load()
    print("target %s" % TARGET)
    print("sha256 %s" % sha256(TARGET))
    describe(data)

    if a.check:
        return 0

    if a.n is None:
        sys.exit("give --n <tiles>, or --check / --restore")
    if not (0 < a.n <= 0xFFFF):
        sys.exit("refusing implausible n=%d" % a.n)

    # Assert we are looking at the instruction we think we are, before writing anything.
    if bytes(data[OPCODE_OFF:OPCODE_OFF + 6]) != OPCODE:
        sys.exit("opcode mismatch at 0x%06x -- wrong binary or already relocated" % OPCODE_OFF)
    cur = read_imm(data, IMM_OFF)
    if cur != SHIPPED_N and cur != a.n:
        print("note: largest option is already %d, not the shipped %d" % (cur, SHIPPED_N))
    for off, want in CONTROLS:
        if read_imm(data, off) != want:
            sys.exit("control arm at 0x%06x is not %d -- refusing to patch" % (off, want))

    if not os.path.exists(BACKUP):
        if sha256(TARGET) != SHIPPED_SHA256:
            sys.exit("no backup yet AND target is not the shipped hash -- refusing to proceed")
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        shutil.copy2(TARGET, BACKUP)
        print("backup written: %s" % BACKUP)
    else:
        print("backup already present: %s" % BACKUP)

    struct.pack_into("<I", data, IMM_OFF, a.n)
    open(TARGET, "wb").write(bytes(data))
    print("\npatched: largest option %d -> %d (4 bytes at 0x%06x)" % (cur, a.n, IMM_OFF))
    after = bytearray(open(TARGET, "rb").read())
    describe(after)
    print("sha256 %s" % sha256(TARGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())

