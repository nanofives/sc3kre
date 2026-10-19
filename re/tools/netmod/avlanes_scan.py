#!/usr/bin/env python3
r"""avlanes_scan.py - read-only survey of the avenues in saved cities (task avlanes 2026-10-19).

For every cell holding stock straight avenue 11204: its axis (lanes along z at states 1 / 3, along x at 0 / 2, from
lanekit show 11204), the piece across the band on each side (the other half), and the pieces the band runs into along
its axis. Output: counts of (state, side of the band) pairs and of the pieces met along the axis / across.

  py -3.12 avlanes_scan.py OUT.json CITY.sc3 [CITY.sc3 ...]          (run from re/tools)
"""
import collections, json, os, sys
sys.path.insert(0, os.getcwd())
from netmod import tiler

out = {"pairs": collections.Counter(), "along": collections.Counter(), "across_other": collections.Counter(),
       "cells": 0, "cities": {}}
for path in sys.argv[2:]:
    c = tiler.City.load(path)
    s = c.layers["surface"]
    n = 0
    for (x, z), p in s.items():
        if p.id != 11204:
            continue
        n += 1
        st = p.state & 3
        if st in (1, 3):           # band along z: the other half is at x-1 or x+1
            across = [(-1, 0), (1, 0)]; along = [(0, -1), (0, 1)]
        else:
            across = [(0, -1), (0, 1)]; along = [(-1, 0), (1, 0)]
        for k, (dx, dz) in enumerate(across):
            q = s.get((x + dx, z + dz))
            if q is not None and q.id == 11204 and (q.state & 3) in ((1, 3) if st in (1, 3) else (0, 2)):
                side = "x-" if (dx, dz) == (-1, 0) else "x+" if (dx, dz) == (1, 0) else "z-" if (dx, dz) == (0, -1) else "z+"
                out["pairs"]["state %d has its other half (11204.%d) at %s" % (st, q.state & 3, side)] += 1
            elif q is not None and q.id != 11204:
                out["across_other"]["%d.%d" % (q.id, q.state & 3)] += 1
        for dx, dz in along:
            q = s.get((x + dx, z + dz))
            key = "%d.%d" % (q.id, q.state & 3) if q is not None else "empty"
            if q is None or q.id != 11204:
                out["along"][key] += 1
    out["cells"] += n
    out["cities"][os.path.basename(path)] = n
res = {k: (dict(v.most_common()) if isinstance(v, collections.Counter) else v) for k, v in out.items()}
json.dump(res, open(sys.argv[1], "w"), indent=1)
print("11204 cells", out["cells"], out["cities"])
print("pairs", dict(out["pairs"]))
print("along (pieces an avenue runs into)", out["along"].most_common(40))
print("across, not 11204", out["across_other"].most_common(25))
