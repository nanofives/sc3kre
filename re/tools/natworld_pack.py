#!/usr/bin/env python3
"""natworld_pack.py - pack the Classic Natural World colours into sc3natworld.bin for sc3resize NATWORLD.

Classic Natural World v1.0 (thronevintagetech, used with the author's permission, re/analysis/COMMUNITY_MODS.md)
ships four replaced game files under Apps\\Res\\Dirt\\Palette. We do not ship those files: they are EA's files with
new colours. This tool keeps only the pixel colours of each palette image, which is the author's work, in our own
container. sc3resize reads it at run time and writes the colours over the game's palette tables after the stock
load (SIMDIRT sc3_dirt_load_palette 0x10016cce), so the player's own files are never touched.

Container (little endian):
  "SC3NW1\\0\\0"                       8 bytes
  u32 count
  count x { u32 slot, u32 w, u32 h, w*h*3 bytes RGB, rows top-down }
slot: 1..5 = land palette instance 1..5 of 455A72B1_LandPalettes.IXF (game palette id 4), 6 = palWater.bmp,
      7 = palEdgeL.bmp, 8 = palEdgeD.bmp (game palette ids 6..8, SIMDIRT 0x10016cce).

usage: py -3.12 re/tools/natworld_pack.py <Natural World package dir or its Apps\\Res\\Dirt\\Palette> <out.bin>
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ixf_parse  # noqa: E402

LAND_GROUP = 0x455A72B1


def bmp_rgb(b):
    """24-bit uncompressed BMP -> (w, h, RGB bytes top-down)."""
    if b[:2] != b"BM":
        raise ValueError("not a BMP")
    off = struct.unpack_from("<I", b, 10)[0]
    w, h, _planes, bpp, comp = struct.unpack_from("<iiHHI", b, 18)
    if bpp != 24 or comp != 0:
        raise ValueError(f"bpp {bpp} comp {comp}: only 24-bit uncompressed")
    flip = h > 0
    h = abs(h)
    stride = (w * 3 + 3) & ~3
    out = bytearray()
    for y in range(h):
        sy = h - 1 - y if flip else y
        row = b[off + sy * stride: off + sy * stride + w * 3]
        for x in range(w):
            bl, g, r = row[x * 3], row[x * 3 + 1], row[x * 3 + 2]
            out += bytes((r, g, bl))
    return w, h, bytes(out)


def find_palette_dir(p):
    for cand in (p, os.path.join(p, "Apps", "Res", "Dirt", "Palette")):
        if os.path.exists(os.path.join(cand, "455A72B1_LandPalettes.IXF")):
            return cand
    for root, _dirs, files in os.walk(p):
        if "455A72B1_LandPalettes.IXF" in files:
            return root
    raise SystemExit(f"455A72B1_LandPalettes.IXF not found under {p}")


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    pal = find_palette_dir(argv[1])
    entries = []
    ixf = os.path.join(pal, "455A72B1_LandPalettes.IXF")
    recs, _ = ixf_parse.parse(ixf)
    data = open(ixf, "rb").read()
    for r in recs:
        if r["group"] == LAND_GROUP and 1 <= r["instance"] <= 5:
            entries.append((r["instance"],) + bmp_rgb(data[r["offset"]: r["offset"] + r["size"]]))
    for slot, name in ((6, "PALWATER.BMP"), (7, "PALEDGEL.BMP"), (8, "PALEDGED.BMP")):
        entries.append((slot,) + bmp_rgb(open(os.path.join(pal, name), "rb").read()))
    entries.sort()
    with open(argv[2], "wb") as f:
        f.write(b"SC3NW1\0\0" + struct.pack("<I", len(entries)))
        for slot, w, h, rgb in entries:
            f.write(struct.pack("<III", slot, w, h) + rgb)
    for slot, w, h, _ in entries:
        print(f"slot {slot}: {w}x{h}")
    print(f"wrote {argv[2]} ({os.path.getsize(argv[2])} bytes, {len(entries)} palettes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
