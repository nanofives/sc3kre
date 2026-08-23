#!/usr/bin/env python3
"""Stop the new-city size from being written into the VERTICAL extent (SIMINIT.DLL).

WHY. SIMINIT FUN_1000c09c is a single setter that writes one scalar into all three dimension
fields of the new-city descriptor [CONFIRMED @ 0x1000c09c]:

    0x1000c0a0  89 41 3c   mov [ecx+0x3c], eax     -> city+0x3c  = CellCountX (horizontal)
    0x1000c0a3  89 41 40   mov [ecx+0x40], eax     -> city+0x44  = VERTICAL extent
    0x1000c0a6  89 41 44   mov [ecx+0x44], eax     -> city+0x40  = CellCountZ (horizontal)

(the desc->city mapping is crossed: desc+0x40 -> city+0x44 via vt[0x58], desc+0x44 -> city+0x40
via vt[0x5c], both [CONFIRMED @ 0x10003b8b].)

Occupant positions are packed into ONE 32-bit word as 11 bits X | 11 bits Y | 8 bits Z |
2 bits orientation [CONFIRMED @ 0x1001dd49, 0x1001cd38, 0x1001d128]. So the horizontal axes
allow up to 2047, but the VERTICAL is capped at 255. The Z setter does not even mask
[CONFIRMED @ 0x1001d1bf: `shl eax, 0x16` with no `and`], so Z >= 256 silently corrupts the
orientation bits.

Raising the city size therefore also raised the vertical extent past what 8 bits can hold, which
is why 256 passes and 257 fails. NOP-ing the middle store leaves the descriptor's constructor
default of 0x80 in place [CONFIRMED @ 0x1000bdc3: param_1[0x10] = 0x80], pinning the vertical
extent at 128 while the horizontal size stays whatever the dialog selected.

Three bytes, no length change, no relocation.

SIDE EFFECT, stated plainly: maximum terrain elevation becomes 128 for every new city instead of
tracking the map size. Shipped behaviour tied it to N.

Usage:
    py -3.12 patch_vertical.py --apply
    py -3.12 patch_vertical.py --restore
    py -3.12 patch_vertical.py --check
"""
import argparse
import hashlib
import os
import shutil
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TARGET = os.path.join(ROOT, "Apps", "SIMINIT.DLL")
# The pristine backup deliberately lives under verify/, NOT next to this script. re/tools/ is
# whitelisted by .gitignore, and these are game-derived binaries that must never be published
# (sc3kre is public: tools and notes only). Deriving it from __file__ would both publish them and,
# after this script moved from verify/ to re/tools/, silently break --restore and strand a
# patched install.
BACKUP = os.path.join(ROOT, "verify", "citysize_mod_test", "SIMINIT.DLL.shipped")
# Pristine oracle: the untouched module shipped in the repo. Used to refuse capturing another
# session's live patch as our "shipped" backup (the single-slot-backup poisoning bug).
REFERENCE = os.path.join(ROOT, "original", "modules", "SIMINIT.DLL")

VA = 0x1000C0A3
ORIG = bytes.fromhex("894140")      # mov [ecx+0x40], eax
PATCH = bytes.fromhex("909090")     # nop nop nop
# neighbours that must be intact, so we know we are on the right instruction boundary
NEIGHBOURS = [(0x1000C0A0, bytes.fromhex("89413c")), (0x1000C0A6, bytes.fromhex("894144"))]


def pe_va_to_off(data, va):
    e = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e:e + 4] == b"PE\0\0"
    coff = e + 4
    nsec = struct.unpack_from("<H", data, coff + 2)[0]
    sizeopt = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    imagebase = struct.unpack_from("<I", data, opt + 28)[0]
    st = opt + sizeopt
    rel = va - imagebase
    for i in range(nsec):
        o = st + i * 40
        vsize, sva, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
        if sva <= rel < sva + max(vsize, rawsize):
            d = rel - sva
            if d < rawsize:
                return rawptr + d
    return None


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
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
            print("WARNING: restored bytes != original/modules/SIMINIT.DLL -- the .shipped backup "
                  "may be poisoned; consider copying from original/modules/ instead.")
        return 0

    data = bytearray(open(TARGET, "rb").read())
    off = pe_va_to_off(data, VA)
    if off is None:
        sys.exit("VA 0x%08x has no raw bytes" % VA)
    cur = bytes(data[off:off + 3])
    print("target %s" % TARGET)
    print("sha256 %s" % sha256(TARGET))
    print("VA 0x%08x -> file offset 0x%06x" % (VA, off))
    print("bytes  %s  (%s)" % (cur.hex(), "SHIPPED" if cur == ORIG
                               else "PATCHED" if cur == PATCH else "UNKNOWN"))
    for nva, nb in NEIGHBOURS:
        noff = pe_va_to_off(data, nva)
        got = bytes(data[noff:noff + 3])
        print("  neighbour 0x%08x: %s %s" % (nva, got.hex(), "OK" if got == nb else "MISMATCH"))

    if a.check:
        return 0
    if not a.apply:
        sys.exit("give --apply / --restore / --check")

    for nva, nb in NEIGHBOURS:
        if bytes(data[pe_va_to_off(data, nva):pe_va_to_off(data, nva) + 3]) != nb:
            sys.exit("neighbour mismatch at 0x%08x -- refusing to patch" % nva)
    if cur == PATCH:
        print("already patched, nothing to do")
        return 0
    if cur != ORIG:
        sys.exit("unexpected bytes %s at the patch site -- refusing" % cur.hex())

    if not os.path.exists(BACKUP):
        if os.path.exists(REFERENCE) and sha256(TARGET) != sha256(REFERENCE):
            sys.exit("no backup yet AND Apps/SIMINIT.DLL != original/modules/SIMINIT.DLL -- "
                     "another session's patch may be live; refusing to capture it as 'shipped'. "
                     "Restore the install first (game_lock.ps1 -Status shows who patched it).")
        shutil.copy2(TARGET, BACKUP)
        print("backup written: %s" % BACKUP)
    data[off:off + 3] = PATCH
    open(TARGET, "wb").write(bytes(data))
    print("\npatched: mov [ecx+0x40],eax -> nop x3   (vertical extent now stays at the ctor "
          "default 0x80 = 128)")
    print("sha256 %s" % sha256(TARGET))
    return 0


if __name__ == "__main__":
    sys.exit(main())

