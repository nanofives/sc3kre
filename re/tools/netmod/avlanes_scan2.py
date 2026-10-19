#!/usr/bin/env python3
r"""avlanes_scan2.py - read-only (task avlanes 2026-10-19): (1) 11204 cells with no 11204 partner across the band,
(2) 11203 corners: in an avenue end (its across partner along the bend is another 11203 forming a U, next to an 11204
pair) or a plain road corner, (3) road pieces that sit on an avenue half (along-axis neighbour of an 11204 band).

  py -3.12 avlanes_scan2.py OUT.json CITY.sc3 ...        (run from re/tools)
"""
import collections, json, os, sys
sys.path.insert(0, os.getcwd())
from netmod import tiler
AX = {1: "z", 3: "z", 0: "x", 2: "x"}
res = {"lone_11204": collections.Counter(), "lone_partner": collections.Counter(), "c11203": collections.Counter(), "n11204": 0}
for path in sys.argv[2:]:
    s = tiler.City.load(path).layers["surface"]
    for (x, z), p in s.items():
        if p.id == 11204:
            res["n11204"] += 1
            st = p.state & 3
            nb = [(x - 1, z), (x + 1, z)] if AX[st] == "z" else [(x, z - 1), (x, z + 1)]
            if not any(s.get(c) is not None and s[c].id == 11204 and AX[s[c].state & 3] == AX[st] for c in nb):
                res["lone_11204"][os.path.basename(path)] += 1
                for c in nb:
                    q = s.get(c); res["lone_partner"]["%d" % q.id if q else "empty"] += 1
        elif p.id == 11203:
            # an avenue U end: one of the 4 side neighbours is also 11203, and an 11204 continues from one of them
            pair = [c for c in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)) if s.get(c) is not None and s[c].id == 11203]
            near4 = any(s.get(c) is not None and s[c].id == 11204 for c in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)))
            res["c11203"]["pair+11204" if pair and near4 else "pair only" if pair else "next to 11204" if near4 else "plain corner"] += 1
out = {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in res.items()}
json.dump(out, open(sys.argv[1], "w"), indent=1); print(json.dumps(out, indent=1))
