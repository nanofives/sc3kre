#!/usr/bin/env python3
r"""hwcars_map.py - top-down map of a saved city for picking test sites (task hwcars 2026-10-19). Read-only.

  py -3.12 hwcars_map.py CITY.sc3 OUT.png [X0,Z0,X1,Z1] [--px 4]          (run from re/tools)

Colours: water blue, highway red, ramp (HWAY+ROAD) orange, road grey, avenue (ids 11203/11204-family not split:
any ROAD id) grey, rail brown, building tan, other occupant purple, free land green shaded by height. Grid every 10.
"""
import os, sys
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "netmod"))
from netmod import tiler, paths
from PIL import Image, ImageDraw


def main(a):
    px = int(a[a.index("--px") + 1]) if "--px" in a else 4
    a = [v for i, v in enumerate(a) if v != "--px" and (i == 0 or a[i - 1] != "--px")]
    city = tiler.City.load(a[1])
    R = tiler.Rules(os.path.join(paths.game_root(), "Apps", "Res", "TilingRules"))
    n = city.n
    box = tuple(map(int, a[3].split(","))) if len(a) > 3 else (0, 0, n - 1, n - 1)
    x0, z0, x1, z1 = box
    W, H = (x1 - x0 + 1) * px, (z1 - z0 + 1) * px
    im = Image.new("RGB", (W + 30, H + 14), (255, 255, 255))
    d = ImageDraw.Draw(im)
    blk = set()
    for t, recs in getattr(city, "buildings", {}).items():
        for (bx, bz, sa, sb, key) in recs:
            for x in range(bx, bx + sa):
                for z in range(bz, bz + sb):
                    blk.add((x, z))
    surf = city.layers["surface"]
    hs = [city.h(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    hmin, hmax = min(hs), max(hs) + 1
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            p = surf.get((x, z))
            if p is not None:
                hw, rd = p.id in R.sets["HWAY"], p.id in R.sets["ROAD"]
                rl = p.id in R.sets["RAIL"]
                col = (255, 140, 0) if hw and rd else (210, 30, 30) if hw else (110, 110, 110) if rd else \
                      (140, 90, 40) if rl else (150, 60, 200) if p.flags is None else (215, 190, 140)
                if p.flags is None and not (hw or rd or rl):
                    col = (150, 60, 200)
            elif (x, z) in blk:
                col = (215, 190, 140)
            elif city.is_water(x, z):
                col = (60, 110, 220)
            else:
                f = (city.h(x, z) - hmin) / (hmax - hmin)
                col = (int(90 + 100 * f), int(170 + 60 * f), int(90 + 100 * f))
            X, Z = (x - x0) * px, (z - z0) * px
            d.rectangle([X, Z, X + px - 1, Z + px - 1], fill=col)
    for x in range(x0, x1 + 1):
        if x % 10 == 0:
            X = (x - x0) * px
            d.line([X, 0, X, H], fill=(0, 0, 0) if x % 50 == 0 else (200, 200, 200))
            d.text((X + 1, H + 1), str(x), fill=(0, 0, 0))
    for z in range(z0, z1 + 1):
        if z % 10 == 0:
            Z = (z - z0) * px
            d.line([0, Z, W, Z], fill=(0, 0, 0) if z % 50 == 0 else (200, 200, 200))
            d.text((W + 2, Z), str(z), fill=(0, 0, 0))
    im.save(a[2])
    print("saved", a[2], im.size, "box", box)


if __name__ == "__main__":
    main(sys.argv)
