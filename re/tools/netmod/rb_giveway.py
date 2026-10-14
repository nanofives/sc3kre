#!/usr/bin/env python3
r"""rb_giveway.py - metric G of verify/roundabout3/PRE.md addendum 1: give-way paint runs round the ring, in-game frames.

  py -3.12 rb_giveway.py DIR PFX X,Z ALT [--n 192] [--r 214.5] [--band] [--step 0.25]
DIR holds PFX_z{z}_r{r}.png dumped with the camera of rb_outline.CAMS. X,Z = block origin, ALT = its terrain altitude.
The circle of radius --r units (256 per cell) round the block centre, world corner (X+1, Z+1), is sampled every --step
degrees and projected with the SIMSPR draw point (NET_ART.md 2). A sample is paint when its pixel equals, in 5/6/5,
the marking colour of that zoom (netpaint RoadSampler.paint_white of road 29). Prints paint fraction and runs.
--band (metric G', PRE addendum 2): an angle is paint when ANY of the radii 211.5 .. 217.5 (step 1) hits the colour.
"""
import math
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import rb_outline  # noqa: E402


def q565(c):
    return (c[0] >> 3, c[1] >> 2, c[2] >> 3)


def fview(wx, wz, rot, n):
    """continuous world (cell units, corner based) -> continuous view coords (fx, fz) of the draw formula"""
    return [(wx - 1, wz), (n - 1 - wz, wx), (n - 1 - wx, n - wz), (wz - 1, n - wx)][rot]


def main(argv):
    from netmod import netpaint as NPT
    d, pfx, at, alt = argv[1], argv[2], argv[3], int(argv[4])
    X, Z = (int(t) for t in at.split(","))
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 192
    rad = float(argv[argv.index("--r") + 1]) if "--r" in argv else 214.5
    step = float(argv[argv.index("--step") + 1]) if "--step" in argv else 0.25
    S = NPT.RoadSampler(29)
    paint = {z: q565(S.paint_white(z)[:3]) for z in (2, 3, 4)}
    for (z, r), (ox, oy) in sorted(rb_outline.CAMS.items()):
        f = os.path.join(d, "%s_z%d_r%d.png" % (pfx, z, r))
        if not os.path.exists(f):
            continue
        px = Image.open(f).convert("RGB").load()
        A, B = 4 << z, 2 << z
        on = []
        k = 0
        while k * step < 360.0:
            a = math.radians(k * step)
            hit = False
            for rr in ([211.5 + i for i in range(7)] if "--band" in argv else [rad]):
                wx, wz = X + 1 + rr * math.cos(a) / 256.0, Z + 1 + rr * math.sin(a) / 256.0
                fx, fz = fview(wx, wz, r, n)
                sx = (fz - fx) * A - ox
                sy = (fx + fz) * B - alt * (1 << z) - oy
                hit = hit or q565(px[int(math.floor(sx)), int(math.floor(sy))]) == paint[z]
            on.append(hit)
            k += 1
        runs = sum(1 for i in range(len(on)) if on[i] and not on[i - 1])
        print("z%d r%d: paint %.3f of %d samples, runs %d" % (z, r, sum(on) / len(on), len(on), runs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
