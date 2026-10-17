#!/usr/bin/env python3
r"""diag_probe.py - stock diagonal road facts for the diagonal-avenue work (verify/diagave, 2026-10-17). Read-only.

  py -3 diag_probe.py scan [SAVE ...]                    diagonal-family piece counts per save (default: shipped Cities)
  py -3 diag_probe.py sites SAVE ID [--n 2] [--r 3]       id.state grids around cells holding piece ID
  py -3 diag_probe.py render SAVE X,Z OUT.png [--r 4] [--zoom 3]
                                                          stock road sprites around a cell (netart.preview, view 0)
  py -3 diag_probe.py band OUT_DIR [--shift 2 3] [--len 8]
                                                          offline: one diagonal staircase, then a second one shifted
                                                          along x, retiled with the stock rules (tiler.py)

`band` seeds the staircase as the saves hold it (row z = k: (k, k) = 35.2, (k+1, k) = 35.0) and retiles; the in-game
diagonal drag code is not modelled (TILER_SIM.md class "diag"). The game run of 2026-10-17 matched its band interior
cell for cell; the drag's own end caps (18004 / 1999) differ.
"""
import argparse
import glob
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from netmod import tiler, netrules, netart, paths  # noqa: E402

# 35 = diagonal straight; 18004 / 1999 = ends; 11207-11210 diagonal Y-branch; 11211-11214, 14030/14031 straight road
# merging into a diagonal; 14010-14017 2x2 bend from straight to diagonal (two hands); 11204 = avenue (2 cells wide)
DIAG = {35, 1999, 18004, 11207, 11208, 11209, 11210, 11211, 11212, 11213, 11214, 14030, 14031} | set(range(14000, 14018))
AVENUE = 11204


def road_ids(g):
    txt = open(os.path.join(g, "Apps", "Res", "TilingRules", "ROAD_GRND_Set.txt")).read()
    return {int(v) for v in re.findall(r"\d+", txt)}


def cell(lay, c, ids):
    p = lay.get(c)
    return "%d.%d" % (p.id, p.state) if p is not None and p.id in ids else "."


def grid(lay, x0, z0, x1, z1, ids):
    rows = ["%4d " % z + " ".join("%8s" % cell(lay, (x, z), ids) for x in range(x0, x1 + 1)) for z in range(z0, z1 + 1)]
    rows.append("     " + " ".join("%8d" % x for x in range(x0, x1 + 1)))
    return "\n".join(rows)


def cmd_scan(a, g):
    saves = a.saves or sorted(glob.glob(os.path.join(g, "Cities", "*.sc3")))
    total = Counter()
    for s in saves:
        lay = tiler.City.load(s).layers["surface"]
        n = Counter(p.id for p in lay.values() if p.id in DIAG or p.id == AVENUE)
        total.update(n)
        print("%-26s %s" % (os.path.basename(s), dict(sorted(n.items()))))
    print("TOTAL", dict(sorted(total.items())))


def cmd_sites(a, g):
    ids = road_ids(g)
    lay = tiler.City.load(a.save).layers["surface"]
    k = 0
    for (x, z), p in sorted(lay.items()):
        if p.id != a.id:
            continue
        print("== %d.%d at (%d,%d)" % (p.id, p.state, x, z))
        print(grid(lay, x - a.r, z - a.r, x + a.r, z + a.r, ids))
        k += 1
        if k >= a.n:
            break


def render(lay, box, out, ids, zoom):
    x0, z0, x1, z1 = box
    cells = [{"at": [-x, z], "piece": p.id, "slot": p.state} for (x, z), p in lay.items()
             if x0 <= x <= x1 and z0 <= z <= z1 and p.id in ids and p.flags is None]
    shot = netart.preview({"cells": cells}, None, zooms=[zoom], rots=[0])[(zoom, 0)]
    shot.convert("RGB").save(out)
    print(out, len(cells), "cells", shot.size)


def cmd_render(a, g):
    x, z = (int(t) for t in a.at.split(","))
    lay = tiler.City.load(a.save).layers["surface"]
    render(lay, (x - a.r, z - a.r, x + a.r, z + a.r), a.out, road_ids(g), a.zoom)


def staircase(x0, z0, n, dx):
    out = {}
    for k in range(n):
        out[(x0 + dx + k, z0 + k)] = (35, 2)
        out[(x0 + dx + k + 1, z0 + k)] = (35, 0)
    return out


def flat_patch(city, w, h):
    lay = city.layers["surface"]
    for x0 in range(4, city.n - w - 4, 2):
        for z0 in range(4, city.n - h - 4, 2):
            alt = city.h(x0, z0)
            if all(city.h(x, z) == alt and (x, z) not in lay and not city.is_water(min(x, city.n - 1), min(z, city.n - 1))
                   for x in range(x0, x0 + w + 1) for z in range(z0, z0 + h + 1)):
                return x0, z0
    raise SystemExit("no flat empty patch")


def cmd_band(a, g):
    game = paths.Game()
    ids = road_ids(g)
    os.makedirs(a.out, exist_ok=True)
    for sh in a.shift:
        opts = tiler.Options()
        city = netrules.prepared(tiler.City.load(os.path.join(g, "Cities", "Roadless Paradise.sc3")), opts)
        T = tiler.Tiler(tiler.Rules(os.path.join(g, "Apps", "Res", "TilingRules")), city, opts, tiler.load_pe(game),
                        netrules.exemplars(game))
        X, Z = flat_patch(city, a.len + sh + 6, a.len + 4)
        X, Z = X + 2, Z + 2
        lay = T.layer(1)
        box = (X - 1, Z - 1, X + a.len + sh + 2, Z + a.len)
        for dx in (0, sh):
            cells = staircase(X, Z, a.len, dx)
            for c, (i, s) in cells.items():
                lay.setdefault(c, tiler.Piece(i, s, city.h(*c)))
            T.retile_rect(3, min(c[0] for c in cells), min(c[1] for c in cells),
                          max(c[0] for c in cells), max(c[1] for c in cells))
            print("== shift %d, staircase at dx %d, patch (%d,%d)\n%s" % (sh, dx, X, Z, grid(lay, *box, ids)))
        render(lay, box, os.path.join(a.out, "band_shift%d.png" % sh), ids, 3)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("saves", nargs="*")
    t = sub.add_parser("sites")
    t.add_argument("save")
    t.add_argument("id", type=int)
    t.add_argument("--n", type=int, default=2)
    t.add_argument("--r", type=int, default=3)
    r = sub.add_parser("render")
    r.add_argument("save")
    r.add_argument("at")
    r.add_argument("out")
    r.add_argument("--r", type=int, default=4)
    r.add_argument("--zoom", type=int, default=3)
    b = sub.add_parser("band")
    b.add_argument("out")
    b.add_argument("--shift", type=int, nargs="+", default=[2, 3])
    b.add_argument("--len", type=int, default=8)
    a = ap.parse_args(argv)
    g = paths.game_root()
    {"scan": cmd_scan, "sites": cmd_sites, "render": cmd_render, "band": cmd_band}[a.cmd](a, g)
    return 0


if __name__ == "__main__":
    sys.exit(main())
