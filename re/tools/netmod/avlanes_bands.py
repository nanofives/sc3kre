#!/usr/bin/env python3
r"""avlanes_bands.py - read-only (task avlanes 2026-10-19): walk every straight-avenue band (pairs of 11204 halves)
along its axis and count the pieces each half passes through until the band stops (not an avenue half any more),
so every piece that sits on an avenue half is counted once per cell, with its id.state.

A cell continues the band when both halves' cells hold a road-class piece (29, 31, 32, 39, 43, 67, 69, 11201, 11202,
11203, 11204, 11207..11216, 14030, 14031, 11258, 15098 or a mod variant >= 20000) and at least one of the two is
not a plain road straight across the band. Heuristic, for sizing only.

  py -3.12 avlanes_bands.py OUT.json CITY.sc3 ...        (run from re/tools)
"""
import collections, json, os, sys
sys.path.insert(0, os.getcwd())
from netmod import tiler
ROADISH = {29, 31, 32, 39, 43, 67, 69, 11201, 11202, 11203, 11204, 11258, 15098, 14030, 14031} | set(range(11207, 11217))
cnt = collections.Counter(); pairs = collections.Counter(); seen = set()
for path in sys.argv[2:]:
    s = tiler.City.load(path).layers["surface"]
    city = os.path.basename(path)
    for (x, z), p in s.items():
        if p.id != 11204 or (p.state & 3) not in (1, 2):      # start from the x- half (state 1) / z- half (state 2)
            continue
        st = p.state & 3
        other = (x + 1, z) if st == 1 else (x, z + 1)
        q = s.get(other)
        if q is None or q.id != 11204:
            continue
        step = (0, 1) if st == 1 else (1, 0)
        for sgn in (1, -1):
            k = 1
            while True:
                a = (x + sgn * step[0] * k, z + sgn * step[1] * k)
                b = (other[0] + sgn * step[0] * k, other[1] + sgn * step[1] * k)
                pa, pb = s.get(a), s.get(b)
                if pa is None or pb is None or (pa.id not in ROADISH and pa.id < 20000) or (pb.id not in ROADISH and pb.id < 20000):
                    break
                if pa.id == 11204 and pb.id == 11204:
                    break                                     # the next pair counts itself
                for c, pc in ((a, pa), (b, pb)):
                    if (city, c) not in seen:
                        seen.add((city, c)); cnt["%d" % pc.id] += 1
                pairs["%d|%d" % (pa.id, pb.id)] += 1
                if pa.id in (11203,) or pb.id in (11203,):
                    break
                k += 1
                if k > 3:
                    break
    for (x, z), p in s.items():
        if p.id == 11204 and (city, (x, z)) not in seen:
            seen.add((city, (x, z))); cnt["11204"] += 1
json.dump({"cells_by_piece": dict(cnt.most_common()), "pairs_across": dict(pairs.most_common(40))}, open(sys.argv[1], "w"), indent=1)
print("cells on avenue halves by piece:", cnt.most_common(30))
print("piece pairs across the band (x-/z- half | other half):", pairs.most_common(20))
