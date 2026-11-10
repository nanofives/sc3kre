#!/usr/bin/env python3
r"""avends_fbuild.py - task avends F3 (2026-11-09): the boulevard narrowing with an avenue T on its last two columns,
pieces 22002..22013 of the avenue_ends package (sc3netmod_bv.c `bvn` lines, block SC3NETMOD_BVNT).

Canonical frame = bvlanes.py's (boulevard along +x on rows z 0 / 1 / 2, row 0's side runs +x, the narrowing over
x 0..3 at the +x end, the avenue beyond on rows `keep`). The narrowing's column 0 keeps boulevard's own bva pieces.
Columns 1..2 (x 1..3) are one junction box (bvlanes.box_lanes, avjunc's movement rule: every lane straight on, right
turns from the outer lanes, left turns from the inner ones, no U-turn) with four arms:
  W (x = 1)   the narrowing's lanes where its column 0 ends (bvlanes.narrow_end sampled at x = 1): 3 in, 3 out
  E (x = 3)   the avenue on rows `keep`: 2 out (+x side), 2 in (-x side)
  N / S       the avenue arm on the kept side's outer edge over x 1..3 (bvlanes.arm_z, width 2): N for keep (0, 1),
              S for keep (1, 2)
plus one lane that opens the -x side's third lane (the avenue's inner in-lane -> the narrowing's third out-lane), as
the plain narrowing does. Lanes cut per cell into each piece's state-0 frame, curves as bvlanes (own shapes from
26520). Art: bvx.Box per cell (the box look of the boulevard junctions: crosswalk lines where an arm meets the box,
curb on a closed side, plain asphalt).

  py -3.12 -m netmod.avends_fbuild build PACK [--root TREE_OVERLAY] [--no-art]   specs + art into PACK
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from netmod import bvlanes as BL      # noqa: E402

U = BL.U
IDS = {(0, 1): list(range(22002, 22008)), (1, 2): list(range(22008, 22014))}   # col 1 rows 0..2, col 2 rows 0..2
SHAPE0, SHAPE1 = 26520, 26999
# box-cell edges N E S W per cell (col, row) for the art: A an arm meets the box, I inside the box, C curb
EDGES = {(0, 1): {(1, 0): "AIIA", (1, 1): "IIIA", (1, 2): "IICA", (2, 0): "AAII", (2, 1): "IAII", (2, 2): "ICCI"},
         (1, 2): {(1, 0): "CIIA", (1, 1): "IIIA", (1, 2): "IIAA", (2, 0): "CCII", (2, 1): "IAII", (2, 2): "IAAI"}}


def z_at(pts, x):
    for a, b in zip(pts, pts[1:]):
        if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
            f = (x - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * f
    raise ValueError("lane does not reach x = %s" % x)


def scene(keep):
    nar = BL.narrow_end(0, keep)
    plus = [ln for ln in nar if ln.kind == "+"]           # outer -> inner, as narrow_end builds them
    minus = [ln for ln in nar if ln.kind == "-"]
    W = {"in": [(1.0, z_at(ln.pts, 1.0)) for ln in plus], "out": [(1.0, z_at(ln.pts, 1.0)) for ln in minus]}
    if keep == (0, 1):
        E = {"in": [(3.0, 1 + 175 / U), (3.0, 1 + 80 / U)], "out": [(3.0, BL.PX[0]), (3.0, BL.PX[1])]}
        arms = {0: W, 2: E, 1: BL.arm_z(1, 0, 1, 2)}
    else:
        E = {"in": [(3.0, BL.MX[0]), (3.0, BL.MX[1])], "out": [(3.0, 1 + 80 / U), (3.0, 1 + 175 / U)]}
        arms = {0: W, 2: E, 3: BL.arm_z(3, 3, 1, 2)}
    lanes = BL.box_lanes(1, 3, 0, 3, arms)
    p, q = E["in"][-1], W["out"][2]                       # the -x side's third lane opens from its inner one
    mid = (p[0] + q[0]) / 2.0
    lanes.append(BL.Lane(BL.join(BL.seg(p, (mid, p[1])), BL.seg((mid, p[1]), q)), "-o"))
    return lanes, arms


def cell_cuts(lanes, c):
    out = []
    for ln in lanes:
        for lu in BL.clip_cell(ln.pts, *c):
            if len(lu) >= 2:
                out.append(BL._int_cut([BL.to_local(pt, 0) for pt in lu]))
    return out


def specs(root):
    from netmod import lanekit as LK
    from netmod import avlanes as AL
    BL.SHAPE0, BL.SHAPE1 = SHAPE0, SHAPE1
    cv = BL.Curves(root)
    game = LK.Game(root)
    ped43 = AL._stock_ped(game, 43)
    out = {}
    for keep, ids in IDS.items():
        lanes, _arms = scene(keep)
        for k, pid in enumerate(ids):
            c = (1 + k // 3, k % 3)
            cuts = cell_cuts(lanes, c)
            plan = []
            for cut in cuts:
                pts = [list(v) for v in cut]
                plan.append((pts, (pts[0][0], pts[0][2]), (pts[-1][0], pts[-1][2])))
            own = set()
            for _round in range(4):
                bad = 0
                for pts, a, b in plan:
                    for lang in ("en", "uk"):
                        h = cv.pick(lang, a, b, own)
                        if h and h[2] != "other" and BL.same_geom(h[1], pts):
                            continue
                        bad += 1
                        own.add(cv.shape_for(pts if lang == "en" else pts[::-1]))
                if not bad:
                    break
            else:
                raise ValueError("piece %d: curve picks do not settle" % pid)
            vl, exits = [], set()
            for pts, a, b in plan:
                ln = {"from": [a[0], a[1]], "to": [b[0], b[1]]}
                if b in exits:
                    ln["exit"] = False
                exits.add(b)
                vl.append(ln)
            out[pid] = {"piece": pid, "states": [0, 1, 2, 3], "flag": 1, "mirror_uk": False,
                        "vehicle": {"class": "car", "speed": 64000, "lanes": vl},
                        "pedestrian": json.loads(json.dumps(ped43)), "connects": {"road": BL._turns(plan)},
                        "curves": [{"shape": s, "pts": cv.new[s]} for s in sorted(own)],
                        "_": "avends_fbuild.py: boulevard narrowing to the avenue on rows %s with an avenue T, cell "
                             "(col %d, row %d) of the narrowing (canonical, +x end), saved as 43" % (keep, c[0], c[1])}
            if not vl:                                    # the closed corner no lane crosses (as bvlanes' taper corners)
                out[pid]["connects"] = {"road": {"low": [], "high": []}}
    return out


def cmd_build(a):
    sp = specs(a.root)
    for pid, s in sp.items():
        json.dump(s, open(os.path.join(a.pack, "bvn_%d.lanes.json" % pid), "w", newline="\n"), indent=1)
        print("%d: %d lanes, %d own curve(s), turns %s" % (pid, len(s["vehicle"]["lanes"]), len(s["curves"]),
                                                       s["connects"]["road"]))
    if a.no_art:
        return
    from netmod import bvx as BX
    from netmod import diagave_paint as P
    from netmod import diagave as D
    for keep, ids in IDS.items():
        for k, pid in enumerate(ids):
            c = (1 + k // 3, k % 3)
            d = os.path.join(a.pack, "art", str(pid))
            desc = EDGES[keep][c]
            anc = P.paint_cell(BX.Box(desc), (0, 0), d)
            D._write_anchors(d, anc, "avends_fbuild.py: narrowing + T box cell %s (bvx.Box)" % desc)
            print("art %d: box %s" % (pid, desc))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("pack")
    ap.add_argument("--root", help="the tree's netmod overlay (curve library with the installed shapes)")
    ap.add_argument("--no-art", action="store_true")
    a = ap.parse_args(argv)
    return {"build": cmd_build}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
