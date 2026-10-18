#!/usr/bin/env python3
r"""rb_hole.py - pixels of one cell that are neither terrain nor art, on in-game dumps (task roundabout4).

  py -3.12 rb_hole.py FRAME.png CAM.json CX,CZ ALT [--n 192] [--out crop.png]
Counts, inside cell CX,CZ's diamond (SIMSPR draw point, as rb_ground.py), the pixels whose blue exceeds green by
more than 8 and whose channels are all < 130 (no grass, sidewalk, asphalt or marking colour of the roundabout art
or the terrain has that: grass is green-dominant, art greys have b - g <= 8; measured on these dumps), and prints
them as JSON {"n": .., "bbox": ..}.
"""
import json
import sys

from PIL import Image


def view(x, z, rot, W, H):
    return [(x, z), (H - 1 - z, x), (W - 1 - x, H - 1 - z), (z, W - 1 - x)][rot]


def main(argv):
    im = Image.open(argv[1]).convert("RGB")
    cam = json.load(open(argv[2]))
    CX, CZ = (int(t) for t in argv[3].split(","))
    alt = int(argv[4])
    n = int(argv[argv.index("--n") + 1]) if "--n" in argv else 192
    zm, rot, (ox, oy) = cam["zoom"], cam["rot"], cam["origin"]
    A, B = 4 << zm, 2 << zm
    vx, vz = view(CX, CZ, rot, n, n)
    p = im.load()
    pts = []
    for py in range(im.height):
        for px in range(im.width):
            Xc, Yc = px + 0.5 + ox, py + 0.5 + oy + alt * (1 << zm)
            fz = (Xc / A + Yc / B) / 2.0
            fx = (Yc / B - Xc / A) / 2.0
            if not (vx - 1 <= fx <= vx and vz <= fz <= vz + 1):
                continue
            c = p[px, py]
            if c[2] > c[1] + 8 and max(c) < 130:
                pts.append((px, py))
    bb = [min(x for x, _ in pts), min(y for _, y in pts), max(x for x, _ in pts), max(y for _, y in pts)] if pts else None
    if "--out" in argv and bb:
        im.crop((bb[0] - 40, bb[1] - 30, bb[2] + 40, bb[3] + 30)).save(argv[argv.index("--out") + 1])
    print(json.dumps({"n": len(pts), "bbox": bb}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
