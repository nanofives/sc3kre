#!/usr/bin/env python3
r"""rb_ground.py - terrain under the closed quarter (20401), on two pixel-aligned in-game dumps (task roundabout4, arm GR).

  py -3.12 rb_ground.py A.png B.png CAM.json X,Z CX,CZ ALT [--n 192] [--rmin 262] [--diff OUT.png]
A = the mod game's frame (block converted, CX,CZ = the closed quarter 20401), B = the stock game's frame (same save,
same camera calls: CAM.json = the camera state {"zoom", "rot", "origin"} printed by rb_lab.py cam, equal in both).
X,Z = block origin, ALT = terrain altitude of the block. Pixels are mapped to continuous view coordinates with the
SIMSPR draw point (NET_ART.md 2, as rb_outline.py). G = pixels inside the closed cell's diamond whose distance from
the block centre is > --rmin units: transparent in the 20401 frames (r > 258) AND in stock curve 11203's (opaque r max
259.3, measured), so in both games the only thing drawn there is whatever lies under the piece.
Prints |G|, the fraction of G equal in A and B (5/6/5), and the fraction of G that is black (all channels < 16).
"""
import json
import math
import sys

from PIL import Image


def view(x, z, rot, W, H):
    return [(x, z), (H - 1 - z, x), (W - 1 - x, H - 1 - z), (z, W - 1 - x)][rot]


def bounds(cells, rot, n):
    vs = [view(x, z, rot, n, n) for x, z in cells]
    return (min(v[0] for v in vs) - 1, max(v[0] for v in vs), min(v[1] for v in vs), max(v[1] for v in vs) + 1)


def q565(c):
    return (c[0] >> 3, c[1] >> 2, c[2] >> 3)


def main(argv):
    fa, fb, cam = argv[1], argv[2], json.load(open(argv[3]))
    X, Z = (int(t) for t in argv[4].split(","))
    CX, CZ = (int(t) for t in argv[5].split(","))
    alt = int(argv[6])
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 192
    rmin = float(argv[argv.index("--rmin") + 1]) if "--rmin" in argv else 262.0
    zm, rot, (ox, oy) = cam["zoom"], cam["rot"], cam["origin"]
    A, B = 4 << zm, 2 << zm
    a, b = Image.open(fa).convert("RGB"), Image.open(fb).convert("RGB")
    pa, pb = a.load(), b.load()
    bx0, bx1, bz0, bz1 = bounds([(X, Z), (X + 1, Z), (X, Z + 1), (X + 1, Z + 1)], rot, n)
    mx, mz = (bx0 + bx1) / 2.0, (bz0 + bz1) / 2.0                 # block centre, view coords
    cx0, cx1, cz0, cz1 = bounds([(CX, CZ)], rot, n)
    G = eq = black = 0
    diff = Image.new("RGB", a.size, (0, 0, 0)) if "--diff" in argv else None
    for py in range(a.height):
        for px in range(a.width):
            Xc, Yc = px + 0.5 + ox, py + 0.5 + oy + alt * (1 << zm)
            fz = (Xc / A + Yc / B) / 2.0
            fx = (Yc / B - Xc / A) / 2.0
            if not (cx0 <= fx <= cx1 and cz0 <= fz <= cz1):
                continue
            if 256.0 * math.hypot(fx - mx, fz - mz) <= rmin:
                continue
            G += 1
            e = q565(pa[px, py]) == q565(pb[px, py])
            eq += e
            black += max(pa[px, py]) < 16
            if diff is not None:
                diff.putpixel((px, py), (0, 255, 0) if e else (255, 0, 0))
    if diff is not None:
        diff.save(argv[argv.index("--diff") + 1])
    print(json.dumps({"G": G, "equal": eq, "equal_frac": round(eq / G, 4) if G else None,
                      "black_frac": round(black / G, 4) if G else None}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
