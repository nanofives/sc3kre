#!/usr/bin/env python3
"""Make SIMDIRT's terrain vertex buffer work for maps larger than 256 tiles.

THE BUFFER. SIMDIRT keeps a lazily-created singleton (`DAT_10025bac`, built by FUN_1001214d ->
FUN_1001665c) whose field `+0x2c` is a ushort-per-vertex terrain buffer. On a map of N tiles the
vertex grid is (N+1) x (N+1), so the buffer needs 2*(N+1)^2 bytes and a row stride of (N+1).
The shipped binary hardcodes BOTH for N=256.

THREE GROUPS OF SITES, all length-preserving (imm32 / disp32), all verified by disassembly:

  A. SIZE  -- `push 0x20402` (= 257*257*2 = 132098)                    4 sites
       0x100166e0  operator_new -> obj+0x2c        (ctor FUN_1001665c)
       0x100132c3  memset(obj+0x2c, 0, size)       (FUN_10013241)
       0x10014159  memset(obj+0x2c, 0, size)       (FUN_100140d8)
       0x1001469f  memset(obj+0x2c, 0, size)       (FUN_1001461d)

  B. STRIDE -- `imul reg, reg, 0x101` (= 257)                          7 sites
       0x10012d0f 0x10012d2d 0x10012d4e 0x10012d6c  (FUN_10012cf3, four cell corners)
       0x100130b0                                    (FUN_1001309e)
       0x10013fc0                                    (FUN_10013fab)
       0x10014512                                    (FUN_100144ff)
     The buffer is addressed as buf[(X * stride + Z) * 2].

  C. CORNER DISPLACEMENT -- `mov word [edx+ecx*2+0x204], ax`           1 site
       0x10012d3e  disp32 at file offset 0x012d42
     The value is DERIVED, not fitted. From base index (X*stride + Z):

         index(X+1, Z+1) = (X+1)*stride + (Z+1) = base + stride + 1
         byte offset     = 2*(base + stride + 1) = base*2 + 2*(stride + 1)
         => disp         = 2*(stride + 1) = 2*((N+1) + 1) = 2*(N+2)

     At N=256 that yields 2*258 = 516 = 0x204, which is exactly what the shipped binary
     contains -- the formula reproduces the shipped constant, which is the check that it is
     right. Verified as the only 0x204 memory displacement in the whole module.
     (The sibling `+2` displacement is the (X, Z+1) corner, i.e. base + 1, which carries no
     stride term and is therefore stride-INDEPENDENT. It is deliberately left alone.)

     Cross-check: with size, stride and disp all set from N, the highest byte touched by the
     four corner writes at the maximum CELL (X = Z = N-1) is exactly the last byte of the
     buffer -- zero spare -- at N=256 AND N=512. Two independent exact fits from one formula.
     Beware two off-by-ones that both produce wrong answers here: using the maximum VERTEX (N)
     instead of the maximum CELL (N-1), and reading "buffer is S bytes" as permitting index S.

WHY BOTH A AND B MATTER, and why patching A alone was not enough:
  * shipped (size 132098, stride 257): at N=512 the max byte index is
    2*(512*257 + 511) = 264190 into a 132098-byte block -- a 132 KB HEAP OVERRUN. That is the
    confirmed corruptor; it shreds neighbouring allocations including the CellMap row-pointer
    table that SIMDIRT FUN_10012e44 later reads, which is where the observed crash surfaced.
  * size-only patch (size 526338, stride 257): 264190 < 526338, so no overrun -- but rows ALIAS,
    row X's cells 257..511 landing on row X+1. Wrong terrain data, not memory corruption. This
    matches the measured result: N=512 went from 0/6 surviving to 4/6, not to 6/6.
  * both (size 526338, stride 513): correct.

Usage:
    py -3.12 patch_dirtbuf.py --n 512
    py -3.12 patch_dirtbuf.py --restore
    py -3.12 patch_dirtbuf.py --check
"""
import argparse
import hashlib
import os
import shutil
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TARGET = os.path.join(ROOT, "Apps", "SIMDIRT.DLL")
# The pristine backup deliberately lives under verify/, NOT next to this script. re/tools/ is
# whitelisted by .gitignore, and these are game-derived binaries that must never be published
# (sc3kre is public: tools and notes only). Deriving it from __file__ would both publish them and,
# after this script moved from verify/ to re/tools/, silently break --restore and strand a
# patched install.
BACKUP = os.path.join(ROOT, "verify", "citysize_mod_test", "SIMDIRT.DLL.shipped")
# Pristine oracle: the untouched module shipped in the repo. Used to refuse capturing another
# session's live patch as our "shipped" backup (the single-slot-backup poisoning bug).
REFERENCE = os.path.join(ROOT, "original", "modules", "SIMDIRT.DLL")

SHIPPED_N = 256

# (file offset of the 4-byte field, expected prefix bytes before it, label)
SIZE_SITES = [
    (0x0166E0, b"\x68", "operator_new -> obj+0x2c"),
    (0x0132C3, b"\x68", "memset (FUN_10013241)"),
    (0x014159, b"\x68", "memset (FUN_100140d8)"),
    (0x01469F, b"\x68", "memset (FUN_1001461d)"),
]
STRIDE_SITES = [
    (0x012D0F, b"\x69\xc9", "imul ecx (FUN_10012cf3 corner 1)"),
    (0x012D2D, b"\x69\xc9", "imul ecx (FUN_10012cf3 corner 2)"),
    (0x012D4E, b"\x69\xc9", "imul ecx (FUN_10012cf3 corner 3)"),
    (0x012D6C, b"\x69\xc9", "imul ecx (FUN_10012cf3 corner 4)"),
    (0x0130B0, b"\x69\xd2", "imul edx (FUN_1001309e)"),
    (0x013FC0, b"\x69\xc9", "imul ecx (FUN_10013fab)"),
    (0x014512, b"\x69\xd2", "imul edx (FUN_100144ff)"),
]
CORNER_SITES = [
    (0x012D3E, b"\x66\x89\x84\x4a", "disp (X+1,Z+1) corner (FUN_10012cf3)"),
]


def size_for(n):    return 2 * (n + 1) * (n + 1)
def stride_for(n):  return n + 1
def corner_for(n):  return 2 * (n + 2)


GROUPS = [
    ("SIZE  ", SIZE_SITES, size_for, 1),      # imm32 sits 1 byte after `push`
    ("STRIDE", STRIDE_SITES, stride_for, 2),  # imm32 sits 2 bytes after `imul r,r,`
    ("CORNER", CORNER_SITES, corner_for, 4),  # disp32 sits 4 bytes after the modrm
]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def report(data):
    for label, sites, fn, delta in GROUPS:
        for off, prefix, role in sites:
            got = bytes(data[off:off + len(prefix)])
            cur = struct.unpack_from("<I", data, off + delta)[0]
            ok = "OK" if got == prefix else "PREFIX MISMATCH"
            print("  %s @0x%06x %-6s val=%-8d (0x%-6x)  %s  %s"
                  % (label, off, got.hex(), cur, cur, ok, role))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, help="max map size in tiles")
    ap.add_argument("--restore", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--groups", default="all",
                    help="comma list of SIZE,STRIDE,CORNER (default all). Groups NOT listed are "
                         "reset to their SHIPPED values, so switching between configurations is "
                         "idempotent and cannot leave a stale half-patch behind. Needed to build "
                         "the SIZE-only configuration for the A/B, which is what measured 4/6.")
    a = ap.parse_args()

    sel = {g.strip().upper() for g in a.groups.split(",") if g.strip()}
    if "ALL" in sel:
        sel = {"SIZE", "STRIDE", "CORNER"}
    unknown = sel - {"SIZE", "STRIDE", "CORNER"}
    if unknown:
        sys.exit("unknown group(s): %s" % ", ".join(sorted(unknown)))

    if a.restore:
        if not os.path.exists(BACKUP):
            sys.exit("no backup at %s" % BACKUP)
        shutil.copy2(BACKUP, TARGET)
        got = sha256(TARGET)
        print("restored %s\nsha256 %s" % (TARGET, got))
        if os.path.exists(REFERENCE) and got != sha256(REFERENCE):
            print("WARNING: restored bytes != original/modules/SIMDIRT.DLL -- the .shipped backup "
                  "may be poisoned; consider copying from original/modules/ instead.")
        return 0

    data = bytearray(open(TARGET, "rb").read())
    print("target %s\nsha256 %s" % (TARGET, sha256(TARGET)))
    report(data)
    if a.check:
        return 0
    if a.n is None:
        sys.exit("give --n <tiles> / --restore / --check")

    # validate every site before writing anything
    for label, sites, fn, delta in GROUPS:
        want, shipped = fn(a.n), fn(SHIPPED_N)
        for off, prefix, role in sites:
            if bytes(data[off:off + len(prefix)]) != prefix:
                sys.exit("prefix mismatch at 0x%06x (%s) -- refusing" % (off, role))
            cur = struct.unpack_from("<I", data, off + delta)[0]
            if cur not in (shipped, want):
                sys.exit("unexpected value %d at 0x%06x (%s) -- refusing" % (cur, off, role))
    if not (0 < size_for(a.n) <= 0x4000000):
        sys.exit("refusing implausible n=%d" % a.n)

    if not os.path.exists(BACKUP):
        if os.path.exists(REFERENCE) and sha256(TARGET) != sha256(REFERENCE):
            sys.exit("no backup yet AND Apps/SIMDIRT.DLL != original/modules/SIMDIRT.DLL -- "
                     "another session's patch may be live; refusing to capture it as 'shipped'. "
                     "Restore the install first (game_lock.ps1 -Status shows who patched it).")
        shutil.copy2(TARGET, BACKUP)
        print("backup written: %s" % BACKUP)
    touched = 0
    for label, sites, fn, delta in GROUPS:
        # A group NOT selected is written back to its SHIPPED value rather than left alone, so
        # e.g. `--groups SIZE` after a full patch really does produce the SIZE-only build.
        val = fn(a.n) if label.strip() in sel else fn(SHIPPED_N)
        for off, _prefix, _role in sites:
            struct.pack_into("<I", data, off + delta, val)
            touched += 1
    open(TARGET, "wb").write(bytes(data))
    print("\npatched for N=%d, groups=%s: size=%d stride=%d corner=0x%x  (%d sites written)"
          % (a.n, ",".join(sorted(sel)) if sel else "(none)",
             size_for(a.n) if "SIZE" in sel else size_for(SHIPPED_N),
             stride_for(a.n) if "STRIDE" in sel else stride_for(SHIPPED_N),
             corner_for(a.n) if "CORNER" in sel else corner_for(SHIPPED_N),
             touched))
    report(bytearray(open(TARGET, "rb").read()))
    print("sha256 %s" % sha256(TARGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())

