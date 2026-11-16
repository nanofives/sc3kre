#!/usr/bin/env python3
r"""xnet_build.py - build the diagonal_xnet package (task diagxnet, round 2026-11-15b, xsect 68 69 72 73): the diagonal
level crossing and the diagonal underpass as variants of the stock crossing pieces, art from xnet_paint.py.

  py -3.12 -m netmod.xnet_build examples/diagonal_xnet [--only rail|hwy] [--keep]     (run from re/tools)

Pieces (ids from 30000, grant 30000..30199), one per band cell role:
  rail   variant of 69, written at state 1 (rail along x); the same piece at state 0 = the scene turned one state back
         (rail along z, the band on the other axis). DA axis 0 / 1: 3 + 3, DB: 4 + 4.
  hwy    variant of 15098 (highway along x: rows m state 2, m + 1 state 0) and of 11258 (highway along z: columns
         m state 2, m + 1 state 0), written at the stock crossing's own state, one piece per cell (no odd states, so
         no lit twins). DA 6 + 6 per base, DB 8 + 8 per base.
Lanes: the band cell's own car lanes and pedestrians (the lone 35 staircases that hold it, as the band pieces) + the
base's train lanes (69) or deck lanes (15098 / 11258) at the written state; no `connects`, so the base's turn matrix
(prop 310 / 311: highway trips, rail) stays as copied with the exemplar.
Table: `crossing_lines` = `davxn <base> <base state> <band piece> <band state> <variant>` (sc3netmod_davxn.c). The DA
middle 20500 is drawn the same at s and s + 2 (DAV writes 20500.0 on axis 0 and 20500.3 on axis 1), so its lines carry
both parities.
"""
import hashlib
import json
import os
import shutil
import sys

from netmod import netart as NA
from netmod import diagave as D
from netmod import diagave_paint as P
from netmod import xnet_paint as X

IDS = (30000, 30199)
# canonical band pieces per cell offset d = x - z - c (axis 0), from the xsect grids (68 / 69 / 72 / 73)
WANT = {"da": [(20505, 2), (20500, 0), (20505, 0)],
        "db": [(20950, 2), (20951, 2), (20951, 0), (20950, 0)]}
# axis 1 as DAV / DBV write it, low x first (xsect 46 / 49 grids)
WANT1 = {"da": [(20505, 3), (20500, 3), (20505, 1)],
         "db": [(20950, 3), (20951, 3), (20951, 1), (20950, 1)]}
LONE = {"da": [[(35, 2)], [(35, 0), (35, 2)], [(35, 0)]],
        "db": [[(35, 2)], [(35, 0), (35, 2)], [(35, 0), (35, 2)], [(35, 0)]]}
NAME = {("rail", "da"): ("Diagonal avenue level crossing", "Paso a nivel de avenida diagonal"),
        ("rail", "db"): ("Diagonal boulevard level crossing", "Paso a nivel de bulevar diagonal"),
        ("hwy", "da"): ("Diagonal avenue underpass", "Paso inferior de avenida diagonal"),
        ("hwy", "db"): ("Diagonal boulevard underpass", "Paso inferior de bulevar diagonal")}
_DESC = {}


def describe(pid, st):
    if (pid, st) not in _DESC:
        _DESC[(pid, st)] = D._describe(pid, st)
    return _DESC[(pid, st)]


def element(kind, k):
    return P.Placed(P.DiagEl(0) if kind == "da" else X.DiagBEl(0), k)


def offset(el, X0, Z0):
    """the band cell offset d of world cell (X0, Z0) in the element's canonical frame"""
    import math
    cx, cz = el.canon(X0 + .5, Z0 + .5)
    return math.floor(cx) - math.floor(cz) - el.el.c


def axis1_turn(kind):
    """k (1 or 3) whose turned band gives DAV / DBV's own axis-1 pieces in a row, low x first"""
    for k in (1, 3):
        el = element(kind, k)
        cells = sorted(x for x in range(-8, 9) if el.has_cell(x, 0))
        got = [(WANT[kind][offset(el, x, 0)][0], (WANT[kind][offset(el, x, 0)][1] + k) % 4) for x in cells]
        norm = lambda w: [(p, s % 2 if p == 20500 else s) for p, s in w]          # noqa: E731
        if norm(got) == norm(WANT1[kind]):
            return k
    raise SystemExit("no turn gives the axis-1 pieces of %s" % kind)


def spec_of(vid, band_parts, extra, note):
    """band_parts / extra: [(piece, state relative to the written state)]; extra = the base, train / deck lanes only"""
    specs = [describe(p, s) for p, s in band_parts]
    sp = D.parts_spec(band_parts, vid, note)
    for p, s in extra:
        e = describe(p, s)
        lanes = [ln for ln in e["vehicle"]["lanes"] if len(ln["from"]) == 3 or ln.get("class") == "train"]
        exits = [x for x in e["vehicle"]["exits"] if len(x["at"]) == 3]
        sp["vehicle"]["lanes"] += lanes
        sp["vehicle"]["exits"] += [x for x in exits if x not in sp["vehicle"]["exits"]]
    sp.pop("connects", None)                       # the base's turn matrix stays (highway trips, rail)
    assert specs
    return sp


def relabel(src, dst, s, note):
    """world-view frames (z{z}_r{r}, l1_...) -> the piece's frames at written state s: frame (r + s) % 4"""
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    anc = json.load(open(os.path.join(src, "anchors.json")))
    out = {"_": note}
    for layer in (0, 1):
        for z in range(NA.ZOOMS):
            for r in range(NA.ROTS):
                n = NA.frame_name(z, r, layer)
                if not os.path.exists(os.path.join(src, n)):
                    continue
                m = NA.frame_name(z, (r + s) % 4, layer)
                shutil.copyfile(os.path.join(src, n), os.path.join(dst, m))
                out[m] = anc[n]
    json.dump(out, open(os.path.join(dst, "anchors.json"), "w"), indent=1)


def pieces_plan(only):
    """[(look, kind, axis k, base, cell, written state, band want (world), band parts (world))]"""
    plan = []
    for kind in ("da", "db"):
        k1 = axis1_turn(kind)
        for k in (0, k1):
            el = element(kind, k)
            if only in (None, "rail"):
                for x in sorted(x for x in range(-8, 9) if el.has_cell(x, 0)):
                    d = offset(el, x, 0)
                    w = (WANT[kind][d][0], (WANT[kind][d][1] + k) % 4)
                    parts = [(p, (s + k) % 4) for p, s in LONE[kind][d]]
                    plan.append(("rail", kind, k, 69, (x, 0), X.RAIL_STATE, w, parts))
            if only in (None, "hwy"):
                for base in (15098, 11258):
                    for i, st in enumerate((2, 0)):
                        cells = [(x, i) for x in range(-8, 9) if el.has_cell(x, i)] if base == 15098 else \
                                [(i, zz) for zz in range(-8, 9) if el.has_cell(i, zz)]
                        for c in sorted(cells):
                            d = offset(el, *c)
                            w = (WANT[kind][d][0], (WANT[kind][d][1] + k) % 4)
                            parts = [(p, (s + k) % 4) for p, s in LONE[kind][d]]
                            plan.append(("hwy", kind, k, base, c, st, w, parts))
    return plan


def main(argv):
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    pack = os.path.abspath([a for i, a in enumerate(argv[1:], 1) if not a.startswith("--") and argv[i - 1] != "--only"][0])
    work = os.path.join(pack, "_work")
    os.makedirs(os.path.join(pack, "art"), exist_ok=True)
    plan = pieces_plan(only)
    print("%d pieces" % len(plan))
    variants, lanes, lines = [], [], []
    keyseen = {}
    for n, (look, kind, k, base, cell, st, w, parts) in enumerate(plan):
        vid = IDS[0] + n
        if vid > IDS[1]:
            raise SystemExit("out of ids")
        tag = "%s_%s_k%d_%d_%d_%d" % (look, kind, k, base, cell[0], cell[1])
        wd = os.path.join(work, tag)
        if not os.path.exists(os.path.join(wd, "anchors.json")) or "--keep" not in argv:
            if os.path.isdir(wd):
                shutil.rmtree(wd)
            if look == "rail":
                anc = X.paint_rail_cell(X.RailX(element(kind, k), 0), cell, wd, kind)
            else:
                anc = X.paint_under_cell(X.Underpass(element(kind, k), 0, base, (2, 0)), cell, st, wd, kind)
            json.dump(anc, open(os.path.join(wd, "anchors.json"), "w"))
        relabel(wd, os.path.join(pack, "art", str(vid)), st,
                "xnet_build.py: %s %s band turned %d, cell %s, base %d written at state %d" % (look, kind, k, cell, base, st))
        rel = [(p, (s - st) % 4) for p, s in parts]
        sp = spec_of(vid, rel, [(base, 0)], "%s %s cell %s: band lanes of %s + %d's %s lanes" %
                     (look, kind, cell, rel, base, "train" if base == 69 else "deck"))
        fn = "xn_%d.lanes.json" % vid
        json.dump(sp, open(os.path.join(pack, fn), "w", newline="\n"), indent=1)
        en, es = NAME[(look, kind)]
        variants.append({"id": vid, "base": base, "network": "ROAD", "name": {"*": en, "ENGLISH": es},
                         "art": {"from": base, "png_dir": "art/%d" % vid}, "trblkatt": "copy_base"})
        lanes.append({"piece": vid, "spec": fn})
        keys = [(st, w[0], w[1])]
        if look == "rail":                         # the same piece at state 0: the scene turned one state back
            keys.append(((st + 3) % 4, w[0], (w[1] + 3) % 4))
        for bs, p, s in list(keys):
            if p == 20500:
                keys.append((bs, p, (s + 2) % 4))
        for bs, p, s in keys:
            key = (base, bs, p, s)
            if key in keyseen and keyseen[key] != vid:
                raise SystemExit("key %s for both %d and %d" % (key, keyseen[key], vid))
            if key not in keyseen:
                keyseen[key] = vid
                lines.append("davxn %d %d %d %d %d" % (base, bs, p, s, vid))
        print("%d %-34s band %s -> %d lines" % (vid, tag, w, len(keys)))
    man = {"netpack": 1, "name": "diagonal_xnet", "version": "0.1.0", "author": "netmod (task diagxnet)",
           "description": "Diagonal avenues and boulevards across a rail line or under a highway. Stock keeps its "
                          "straight road x rail crossing (69) and highway-over-road pieces (15098 / 11258) on those "
                          "cells, drawn as a 2-lane road. These are variants of those pieces (so the rail and the "
                          "highway keep working and saves load as stock without the mod) with the band's own lanes: "
                          "a level crossing that follows the diagonal lanes, and one underpass the shape of the "
                          "band. sc3netmod's DAVXN block writes them (SC3NETMOD_DAVXNRAIL / SC3NETMOD_DAVXNHWY = 0: "
                          "off). Built by `py -3.12 -m netmod.xnet_build <this folder>` from re/tools before install "
                          "(art/ is made from the game's frames and is not shipped).",
           "game": {"Apps/SIMNTWRK.DLL": "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"},
           "variants": variants, "lanes": lanes, "crossing_lines": lines}
    json.dump(man, open(os.path.join(pack, "manifest.json"), "w", encoding="utf-8", newline="\n"), indent=1,
              ensure_ascii=False)
    print("manifest: %d variants, %d davxn lines" % (len(variants), len(lines)))


if __name__ == "__main__":
    main(sys.argv)
