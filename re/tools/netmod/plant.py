#!/usr/bin/env python3
r"""plant.py -- write network cells into a COPY of a city save (artkit, 2026-10-13): put a new piece in a test city
without a tiling rule or a tool. Uses network_layer.py's editor (add_tile / set_piece, never guesses z).

    py -3.12 plant.py find <city.sc3> [--size 8] [--near-road 6]     # flat, dry, empty boxes (top candidates)
    py -3.12 plant.py plant <city.sc3> <out.sc3> <cells.json> --at X,Y

cells.json = {"cells": [{"dx": 0, "dy": 0, "piece": 20400, "state": 3}, ...]} relative to --at, in SAVE coordinates
(x, y) = the engine's cell (x, z) (network_layer.py, tiler.py). z of every cell = the terrain height of its corners,
which must all be equal (flat), or the cell is refused. Cells that already hold a network tile are refused.
A save holding an id that no installed package defines loses those cells on load (NEW_PIECE.md 4).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import network_layer as nl  # noqa: E402
from netmod import tiler  # noqa: E402


def corners(city, x, y):
    return [city.h(x + a, y + b) for a in (0, 1) for b in (0, 1)]


def flat_z(city, x, y):
    c = corners(city, x, y)
    return c[0] if len(set(c)) == 1 else None


def occupied(city, x, y):
    if any((x, y) in city.layers[k] for k in city.layers):
        return True
    for lst in getattr(city, "buildings", {}).values():
        for (a, b, sa, sb, _k) in lst:
            if a <= x < a + sa and b <= y < b + sb:
                return True
    return False


def find(city, size=8, near_road=6, top=10):
    n = city.n
    road = [(x, y) for (x, y), p in city.layers["surface"].items()]
    out = []
    for x0 in range(2, n - size - 2, 2):
        for y0 in range(2, n - size - 2, 2):
            z0 = flat_z(city, x0, y0)
            if z0 is None:
                continue
            ok = True
            for x in range(x0, x0 + size):
                for y in range(y0, y0 + size):
                    if flat_z(city, x, y) != z0 or city.is_water(x, y) or occupied(city, x, y):
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                continue
            d = min((max(abs(rx - (x0 + size // 2)), abs(ry - (y0 + size // 2))) for rx, ry in road), default=999)
            if d <= near_road + size // 2:
                out.append((d, x0, y0, z0))
    out.sort()
    return out[:top]


def plant(src, dst, cells, at):
    city = tiler.City.load(src)
    ed = nl.NetworkEditor.load(src)
    X, Y = at
    done = []
    for c in cells:
        x, y = X + c["dx"], Y + c["dy"]
        z = flat_z(city, x, y)
        if z is None:
            raise SystemExit("cell (%d,%d) is not flat: corners %s" % (x, y, corners(city, x, y)))
        if occupied(city, x, y):
            raise SystemExit("cell (%d,%d) is occupied" % (x, y))
        ed.add_tile("surface", x, y, c["piece"], c["state"], z)
        done.append((x, y, z, c["piece"], c["state"]))
    ed.save(dst)
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find")
    f.add_argument("city")
    f.add_argument("--size", type=int, default=8)
    f.add_argument("--near-road", type=int, default=6)
    p = sub.add_parser("plant")
    p.add_argument("city")
    p.add_argument("out")
    p.add_argument("cells")
    p.add_argument("--at", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "find":
        c = tiler.City.load(a.city)
        for d, x, y, z in find(c, a.size, a.near_road):
            print("box at %d,%d (size %d), z %d, nearest network cell %d" % (x, y, a.size, z, d))
        return 0
    cells = json.load(open(a.cells, encoding="utf-8"))["cells"]
    at = tuple(int(v) for v in a.at.split(","))
    for x, y, z, pid, st in plant(a.city, a.out, cells, at):
        print("planted %d.%d at (%d,%d) z %d" % (pid, st, x, y, z))
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
