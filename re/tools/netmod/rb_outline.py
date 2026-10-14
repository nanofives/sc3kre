#!/usr/bin/env python3
r"""rb_outline.py - the outline-line metric of verify/roundabout3/PRE.md arm V, on two pixel-aligned in-game dumps.

  py -3.12 rb_outline.py DIR PFX_A PFX_B X,Z ALT [--dist 1.5] [--white 200] [--list N]
DIR holds PFX_A_z{z}_r{r}.png (roundabout) and PFX_B_z{z}_r{r}.png (stock block), dumped with the same camera calls
(nramp_cam.py, origins in CAMS below or --cams JSON). X,Z = block origin, ALT = terrain altitude of the block.
O = pixels whose centre lies within --dist screen px of the block's outer diamond edge (both sides), from the SIMSPR
draw point (NET_ART.md 2). White = R, G, B all >= --white (8-bit). W = |{p in O: white in A, not white in B}|.
Also prints, per W pixel, its edge (NW/NE/SE/SW on screen), side (in = inside the block, out) and distance.
"""
import json
import math
import os
import sys

from PIL import Image

CAMS = {  # zoom, rot -> origin, for the camera centred on (121,121) by nramp_cam (both runs gave the same values)
    (2, 0): (-336, 1336), (3, 0): (-320, 2944), (4, 0): (-288, 6160),
    (2, 1): (480, 928), (3, 1): (1312, 2128), (4, 1): (2976, 4528),
    (2, 2): (-336, 520), (3, 2): (-320, 1312), (4, 2): (-288, 2896),
    (2, 3): (-1152, 928), (3, 3): (-1952, 2128), (4, 3): (-3552, 4528),
}


def view(x, z, rot, W=256, H=256):
    return [(x, z), (H - 1 - z, x), (W - 1 - x, H - 1 - z), (z, W - 1 - x)][rot]


def outline(z, r, X, Z, alt, n, dist):
    """-> {(px, py): (edge, side, d)} for the block's outline pixels"""
    A, B = 4 << z, 2 << z
    ox, oy = CAMS[(z, r)]
    vs = [view(X + dx, Z + dz, r, n, n) for dx in (0, 1) for dz in (0, 1)]
    vx0, vx1 = min(v[0] for v in vs), max(v[0] for v in vs)
    vz0, vz1 = min(v[1] for v in vs), max(v[1] for v in vs)
    fx0, fx1, fz0, fz1 = vx0 - 1, vx1, vz0, vz1 + 1        # continuous view coords of the block (see docstring)
    k = 4.0 * B / math.sqrt(5.0)                            # screen px per unit of f across an edge
    out = {}
    cx = (fz0 + fz1) / 2 * A - (fx0 + fx1) / 2 * A - ox
    cy = (fx0 + fx1 + fz0 + fz1) / 2 * B - alt * (1 << z) - oy
    R = int((vz1 - vz0 + 2) * A + 8)
    for py in range(int(cy - R), int(cy + R)):
        for px in range(int(cx - R), int(cx + R)):
            Xc, Yc = px + 0.5 + ox, py + 0.5 + oy + alt * (1 << z)
            fz = (Xc / A + Yc / B) / 2.0
            fx = (Yc / B - Xc / A) / 2.0
            inside = fx0 <= fx <= fx1 and fz0 <= fz <= fz1
            # distance to each of the 4 edge lines, only where the foot lies on the edge segment
            best = None
            for name, val, lo, hi, f, g in (("fx0", fx0, fz0, fz1, fx, fz), ("fx1", fx1, fz0, fz1, fx, fz),
                                            ("fz0", fz0, fx0, fx1, fz, fx), ("fz1", fz1, fx0, fx1, fz, fx)):
                if lo - 0.05 <= g <= hi + 0.05:
                    d = abs(f - val) * k
                    if best is None or d < best[1]:
                        best = (name, d)
            if best and best[1] <= dist:
                # screen side of the edge: fx0 = upper right (NE), fx1 = lower left (SW), fz0 = upper left (NW),
                # fz1 = lower right (SE)
                scr = {"fx0": "NE", "fx1": "SW", "fz0": "NW", "fz1": "SE"}[best[0]]
                out[(px, py)] = (scr, "in" if inside else "out", round(best[1], 2))
    return out


def main(argv):
    d, pa, pb, at, alt = argv[1], argv[2], argv[3], argv[4], int(argv[5])
    X, Z = (int(t) for t in at.split(","))
    dist = float(argv[argv.index("--dist") + 1]) if "--dist" in argv else 1.5
    wt = int(argv[argv.index("--white") + 1]) if "--white" in argv else 200
    nl = int(argv[argv.index("--list") + 1]) if "--list" in argv else 0
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 192
    tot = 0
    rep = {}
    for (z, r) in sorted(CAMS):
        fa, fb = os.path.join(d, "%s_z%d_r%d.png" % (pa, z, r)), os.path.join(d, "%s_z%d_r%d.png" % (pb, z, r))
        if not (os.path.exists(fa) and os.path.exists(fb)):
            continue
        a, b = Image.open(fa).convert("RGB").load(), Image.open(fb).convert("RGB").load()
        o = outline(z, r, X, Z, alt, n, dist)
        white = lambda c: min(c) >= wt
        W = [(p, info, a[p], b[p]) for p, info in o.items() if white(a[p]) and not white(b[p])]
        wa = sum(1 for p in o if white(a[p]))
        wb = sum(1 for p in o if white(b[p]))
        by = {}
        for p, info, ca, cb in W:
            by[info[0] + "/" + info[1]] = by.get(info[0] + "/" + info[1], 0) + 1
        rep["z%d_r%d" % (z, r)] = {"O": len(o), "W": len(W), "white_A": wa, "white_B": wb, "by_edge": by}
        tot += len(W)
        print("z%d r%d: |O| %4d  W %3d  (white in A %3d, in B %3d)  %s" % (z, r, len(o), len(W), wa, wb,
              " ".join("%s:%d" % kv for kv in sorted(by.items()))))
        for p, info, ca, cb in W[:nl]:
            print("    %s %s A%s B%s" % (p, info, ca, cb))
    print("total W %d" % tot)
    if "--json" in argv:
        json.dump(rep, open(argv[argv.index("--json") + 1], "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
