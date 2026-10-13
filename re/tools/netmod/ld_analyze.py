#!/usr/bin/env python3
r"""ld_analyze.py - compare ld_probe.py arms (verify/lanedensity/PRE.md).

  py -3.12 ld_analyze.py --save <city.sc3> --arm N1=<probe.npz> --arm N2=... [--pair N1,N2 --pair N1,A1 ...]
                         [--cells x0,z0,x1,z1 ...] [--months 3:14] [--json out.json]

Road tiles = surface tiles of --save whose piece id is in ROAD_GRND_Set.txt (SC3_GAME_ROOT) or a variant listed
with --road-id. Per arm: mean of the published grid +0x60 over the month range (1-based, inclusive) per tile.
Per pair: mean |diff| over road tiles, 99th percentile of |diff|, total of each arm; per --cells rect: sum of the
per-tile means in each arm.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import network_layer as nl  # noqa: E402
import netpack_rules as NR  # noqa: E402


def road_mask(save, n, extra):
    root = os.environ.get("SC3_GAME_ROOT", r"C:\Users\maria\Desktop\Proyectos\Simcity_stock")
    with open(os.path.join(root, "Apps", "Res", "TilingRules", "ROAD_GRND_Set.txt"), "rb") as f:
        ids = set(NR.braced_ids(f.read())) | set(extra)
    nets, _ = nl.read_networks(save)
    m = np.zeros((n, n), dtype=bool)
    for r in nets[1]:
        if r[4] in ids:
            m[r[0], r[1]] = True
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", required=True)
    ap.add_argument("--arm", action="append", default=[])
    ap.add_argument("--pair", action="append", default=[])
    ap.add_argument("--cells", action="append", default=[])
    ap.add_argument("--months", default="3:14")
    ap.add_argument("--road-id", type=int, action="append", default=[])
    ap.add_argument("--json")
    a = ap.parse_args()
    m0, m1 = (int(v) for v in a.months.split(":"))
    arms = {}
    for spec in a.arm:
        k, p = spec.split("=", 1)
        z = np.load(p)
        g = z["grids"].astype(np.float64)
        if g.shape[0] < m1:
            print("%s: only %d months, using %d..%d" % (k, g.shape[0], m0, g.shape[0]))
        arms[k] = g[m0 - 1:m1].mean(axis=0)
    n = next(iter(arms.values())).shape[0]
    road = road_mask(a.save, n, a.road_id)
    out = {"road_tiles": int(road.sum()), "months": [m0, m1], "arms": {}, "pairs": {}, "cells": {}}
    print("road tiles %d, months %d..%d" % (road.sum(), m0, m1))
    for k, g in arms.items():
        out["arms"][k] = {"road_total": float(g[road].sum()), "map_total": float(g.sum())}
        print("  %-6s road total %10.1f   map total %10.1f" % (k, g[road].sum(), g.sum()))
    for spec in a.pair:
        x, y = spec.split(",")
        d = np.abs(arms[x] - arms[y])[road]
        r = {"mean_abs": float(d.mean()), "p99_abs": float(np.percentile(d, 99)), "max_abs": float(d.max()),
             "rel_total": float((arms[y][road].sum() - arms[x][road].sum()) / max(arms[x][road].sum(), 1))}
        out["pairs"][spec] = r
        print("  %-12s mean|d| %.3f  p99|d| %.2f  max|d| %.1f  total %+.2f%%"
              % (spec, r["mean_abs"], r["p99_abs"], r["max_abs"], 100 * r["rel_total"]))
    for spec in a.cells:
        x0, z0, x1, z1 = (int(v) for v in spec.split(","))
        row = {k: float(g[x0:x1 + 1, z0:z1 + 1].sum()) for k, g in arms.items()}
        out["cells"][spec] = row
        print("  cells %-18s " % spec + "  ".join("%s %.1f" % (k, v) for k, v in row.items()))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
