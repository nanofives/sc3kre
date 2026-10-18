#!/usr/bin/env python3
r"""hwtraffic_twin.py - the hwdx offline twin run over a real city (task hwtraffic 2026-10-18): drag one diagonal across
an existing straight highway with tiler.py, detect the stock aftermath, place the quadrants, write the probe's groups.

  env CLEAR="44,10;45,10;46,10" py -3.12 hwtraffic_twin.py CITY.sc3 48,13 A 0 3 10 groups.json      (run from re/tools)
args: city, O, case, r, north arm length, south arm length, groups out (+ <out>_placements.json). CLEAR = cells emptied
first (the power-line cells the edit demolishes). Taken cells for ramps = buildings and any non-highway occupant.
"""
import sys, os
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "netmod"))
from netmod import hwdx
E = hwdx.env(); tiler, netrules = E["tiler"], E["netrules"]
P = sys.argv[1]
O = tuple(map(int, sys.argv[2].split(","))); case = sys.argv[3]; r = int(sys.argv[4])
kn, ks = int(sys.argv[5]), int(sys.argv[6])     # diagonal arm lengths: north (k<0) / south (k>0)
opts = tiler.Options()
city = netrules.prepared(tiler.City.load(P), opts)
T = tiler.Tiler(tiler.Rules(os.path.join(E["g"], "Apps", "Res", "TilingRules")), city, opts,
                tiler.load_pe(E["game"]), netrules.exemplars(E["game"]))
lay = T.layer(4)
print("highway layer cells", len(lay))
for c in [tuple(map(int, v.split(","))) for v in os.environ.get("CLEAR", "").split(";") if v]:
    lay.pop(c, None); city.layers["surface"].pop(c, None)
    print("cleared", c)
S, D = hwdx.world_drags(O, case, r, n=max(kn, ks))
# keep only k in [-kn, ks]
D = [c for c in D]
def kof(c):
    q = (c[0] - O[0], c[1] - O[1])
    for rr in range(4):  # undo rotation
        pass
    return None
Dk = []
for k in range(-kn, ks + 1):
    for d in (-1, 0, 1):
        c = (k + d, k) if case == "A" else (k + d, -1 - k)
        w = hwdx.rot_cell(c, r); Dk.append((O[0] + w[0], O[1] + w[1]))
surf = city.layers["surface"]
blk = set()
for t, recs in getattr(city, "buildings", {}).items():
    for (a, b, sa, sb, key) in recs:
        for x in range(a, a + sa):
            for z in range(b, b + sb): blk.add((x, z))
bad = [c for c in Dk if c in blk or (c in surf and c not in lay)]
print("diagonal cells on buildings / other networks:", [(c, surf[c].id if c in surf else "bldg") for c in bad])
hwdx.drag(T, city, Dk)
lay = T.layer(4)
found = hwdx.detect(lay)
print("detect", found)
# taken = any surface occupant that is not highway, or a building
cut = {c for c in blk} | {c for c, p in surf.items() if c not in lay}
for (O2, cs, rr) in found:
    res = hwdx.place(lay, city, O2, cs, rr, cut=cut)
    print("built", res["built"], "refused", res["refused"], "cells", len(res["placements"]))
print("--- after drag, rows", O[1]-8, "..", O[1]+12)
for z in range(O[1] - 8, O[1] + 13):
    row = []
    for x in range(O[0] - 12, O[0] + 14):
        p = lay.get((x, z))
        row.append("%6s" % ("%d" % p.id if p else "."))
    print("%3d" % z, "".join(row))
import json
res = hwdx.place(lay, city, found[0][0], found[0][1], found[0][2], cut=cut)
pl = res["placements"]
ramps = sorted(w for w, v in pl.items() if v[3] == "ramp")
joins = sorted(w for w, v in pl.items() if v[3] == "att")
core = sorted(w for w, v in pl.items() if v[3] == "core")
print("ramps", len(ramps), "joins", len(joins), "core", len(core))
band_s = [c for c in Dk if c[1] >= O[1] + 2 and c not in pl]
band_n = [c for c in Dk if c[1] <= O[1] - 3 and c not in pl]
one = lambda cs: [[x, z, x, z] for x, z in cs]
groups = {"west": [[0, 11, 40, 16]], "core": [[45, 11, 50, 14]], "east": [[56, 11, 68, 14]],
          "diag_s": one(band_s), "diag_n": one(band_n), "ramps": one(ramps), "joins": one(joins)}
json.dump(groups, open(sys.argv[7], "w"))
json.dump({"%d,%d" % w: v for w, v in pl.items()}, open(sys.argv[7].replace(".json", "_placements.json"), "w"))
print({k: len(v) for k, v in groups.items()})
tabs = {"A": hwdx.case_table("A"), "B": hwdx.case_table("B")}
mv = hwdx.movements(pl, found[0][0], found[0][1], found[0][2], tabs)
print("movements", sorted("%s>%s" % k for k, v in mv.items() if v and k[0] != k[1]))
