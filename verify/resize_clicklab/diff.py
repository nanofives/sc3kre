#!/usr/bin/env python3
"""diff.py - per-region changed-pixel counts between the clicklab screenshots.

Regions are in CLIENT coordinates; the shots are WINDOW captures, so a border offset is
subtracted (auto-detected from the size difference, assumed symmetric horizontally).

Usage: diff.py <dir> [--base s0_noise_a] [--client 2048x1081]
"""
import argparse
import os
import sys

from PIL import Image, ImageChops

REGIONS = {
    "HUD":  (1248, 1025, 1847, 1081),
    "SIDE": (1952, 481, 2048, 923),
    "MINI": (1888, 917, 2048, 1081),
}
THRESH = 24  # per-channel difference that counts as a changed pixel


def load(path):
    return Image.open(path).convert("RGB")


def changed(a, b, box, off):
    x0, y0, x1, y1 = box
    ox, oy = off
    box = (x0 + ox, y0 + oy, x1 + ox, y1 + oy)
    box = (max(0, box[0]), max(0, box[1]), min(a.width, box[2]), min(a.height, box[3]))
    if box[2] <= box[0] or box[3] <= box[1]:
        return None, 0
    ca, cb = a.crop(box), b.crop(box)
    d = ImageChops.difference(ca, cb).convert("L")
    px = d.load()
    n = 0
    for y in range(d.height):
        for x in range(d.width):
            if px[x, y] >= THRESH:
                n += 1
    return (d.width * d.height), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--base", default="s0_noise_a")
    ap.add_argument("--client", default="2048x1081")
    a = ap.parse_args()

    cw, chh = (int(v) for v in a.client.split("x"))
    base = load(os.path.join(a.dir, a.base + ".png"))
    ox = (base.width - cw) // 2
    oy = base.height - chh - ox   # title bar above, symmetric border below
    print(f"# capture {base.width}x{base.height}  client {cw}x{chh}  offset ({ox},{oy})")

    shots = sorted(f[:-4] for f in os.listdir(a.dir)
                   if f.endswith(".png") and f[:-4] != a.base)
    hdr = "shot".ljust(16) + "".join(r.ljust(22) for r in REGIONS)
    print(hdr)
    for s in shots:
        img = load(os.path.join(a.dir, s + ".png"))
        if img.size != base.size:
            print(s.ljust(16) + f"SIZE MISMATCH {img.size} vs {base.size}")
            continue
        row = s.ljust(16)
        for name, box in REGIONS.items():
            tot, n = changed(base, img, box, (ox, oy))
            pct = (100.0 * n / tot) if tot else 0.0
            row += f"{n}/{tot} ({pct:.2f}%)".ljust(22)
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
