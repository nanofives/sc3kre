#!/usr/bin/env python3
r"""bigrbt.py - automatic 3x3 roundabouts (task bigrbt, 2026-10-17): the block rule, its pieces, art, lanes, previews.

A 3x3 block of ROAD cells becomes one big roundabout (sc3netmod's RBT9 block, re/harness/src/sc3netmod_rbt9.c, applies
the same rule in game after every road retile and after a city load; this file is its offline twin and the builder
of the pieces it places). Block origin (X, Z) = its x-, z- cell; world sides 0 x-, 1 z-, 2 x+, 3 z+ (SIMNTWRK dir
index). Each side has three boundary cell edges, index 0..2 along +x (N/S sides) or +z (W/E sides).

The rule (all must hold):
  full      the 9 cells hold ROAD, each a flat stock road piece (29, 39, 43, 11203, 11204) or one of ours
  corners   the four diagonal cells (X-1, Z-1), (X+3, Z-1), (X-1, Z+3), (X+3, Z+3) hold no ROAD
  sides     on each side the three arm cells (one step out) hold road in one of the patterns
            000, 100, 010, 001 (one single road), 101 (two single roads), 110, 011 (an avenue); never 111
            (that is a three-road run, task boulevard, or a block bigger than 3x3)
  avenue    an avenue's two arm cells, the two cells beyond them (two steps out) hold ROAD as well, and the two arm
            cells are flat road pieces (29, 39, 43, 11203, 11204: the block writes 11204 there)
Not ours (refused by the rule above): a 2x2 block (RBT: a 2x2 is never full 3x3), avenue x avenue boxes (avx: a 2x2
box), three-row runs (boulevard: a side with three arm cells), diagonal avenues (no full 3x3 in a band).

Pieces (canonical state 0; the block's cells take states by position, see STATE): centre 20600; the side-middle cell
(state 0 = the E cell, outer side x+) by its arm: none 20601, road 20602, avenue half with the median toward z-
20603 / toward z+ 20604; the corner cell (state 0 = the NE cell, outer sides z- and x+) by the arm on z- (kN) and on
x+ (kE), each 0 none / 1 road / 2 avenue half: 20610 + 3 * kN + kE. Avenue arm cells (one step out) are written as
stock 11204 (median on the partner side) so the median runs up to the block edge.

  py -3.12 -m netmod.bigrbt mockup OUT.png [--arms SPEC]       every block cell painted straight from the scene
  py -3.12 -m netmod.bigrbt build PACK_DIR [--manifest]         art/<id>/ + <id>.lanes.json for every piece
  py -3.12 -m netmod.bigrbt preview OUT.png PACK_DIR [--arms SPEC]   the block from the built pieces
  (run from re/tools; SPEC like "W=av01;N=av12;E=r1;S=r0,r2": avenue on side cells 0,1 / a road on cell 1; zooms
  and views with --zooms 4,3 --rots 0,1)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

CENTRE = 20600
SIDE_IDS = {0: 20601, 1: 20602, 2: 20603, 3: 20604}          # side kind: none, road, avenue median z-, median z+
CORNER0 = 20610                                              # + 3 * kN + kE
FLAT = {29, 39, 43, 11203, 11204}

# block cells by world side, index 0..2 along the side; the arm cell is one step out
SIDE_CELLS = {0: [(0, 0), (0, 1), (0, 2)], 1: [(0, 0), (1, 0), (2, 0)],
              2: [(2, 0), (2, 1), (2, 2)], 3: [(0, 2), (1, 2), (2, 2)]}
OUT = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}
ALONG = {0: 3, 1: 2, 2: 3, 3: 2}                                # the side's index direction (+z or +x)


def rot_side(s, k):
    return (s + k) % 4


def cell_state(c):
    """-> (type, state): the canonical piece's state for block cell c (side state 0 = E, corner state 0 = NE)"""
    if c == (1, 1):
        return "centre", 0
    if c in ((2, 1), (1, 2), (0, 1), (1, 0)):
        return "side", {(2, 1): 0, (1, 2): 1, (0, 1): 2, (1, 0): 3}[c]
    return "corner", {(2, 0): 0, (2, 2): 1, (0, 2): 2, (0, 0): 3}[c]


def outer_sides(c):
    x, z = c
    return [s for s, (dx, dz) in OUT.items() if not (0 <= x + dx <= 2 and 0 <= z + dz <= 2)]


# ------------------------------------------------------------------------------------------------ the rule

def side_arms(road, X, Z):
    """-> {(cell, side): ('road' | 'avenue', partner side or None)} or (None, why). road = set of (x, z)."""
    arms = {}
    for s in range(4):
        dx, dz = OUT[s]
        pat = [(X + cx + dx, Z + cz + dz) in road for (cx, cz) in SIDE_CELLS[s]]
        if all(pat):
            return None, "side %d: three arm cells (three-road run or bigger block)" % s
        pairs = [(0, 1)] if pat[0] and pat[1] else [(1, 2)] if pat[1] and pat[2] else []
        for i, on in enumerate(pat):
            if not on:
                continue
            pr = [p for p in pairs if i in p]
            if pr:
                j = pr[0][0] if pr[0][1] == i else pr[0][1]
                cx, cz = SIDE_CELLS[s][i]
                ox, oz = SIDE_CELLS[s][j]
                partner = {(1, 0): 2, (-1, 0): 0, (0, 1): 3, (0, -1): 1}[(ox - cx, oz - cz)]
                arms[(SIDE_CELLS[s][i], s)] = ("avenue", partner)
            else:
                arms[(SIDE_CELLS[s][i], s)] = ("road", None)
        for (a, b) in pairs:
            for i in (a, b):
                cx, cz = SIDE_CELLS[s][i]
                if (X + cx + 2 * dx, Z + cz + 2 * dz) not in road:
                    return None, "side %d: a 2-wide arm that does not go on as an avenue" % s
    return arms, ""


def check(road, ids, X, Z):
    """ids: (x, z) -> piece id (for the flat test). -> (arms, '') or (None, why)"""
    for cx in range(3):
        for cz in range(3):
            c = (X + cx, Z + cz)
            if c not in road:
                return None, "not full"
            if ids.get(c) not in FLAT and not is_ours(ids.get(c)):
                return None, "block cell %s is piece %s" % (c, ids.get(c))
    for c in ((X - 1, Z - 1), (X + 3, Z - 1), (X - 1, Z + 3), (X + 3, Z + 3)):
        if c in road:
            return None, "diagonal cell %s holds road" % (c,)
    arms, why = side_arms(road, X, Z)
    if arms is None:
        return None, why
    for ((cx, cz), s), (kind, _p) in arms.items():
        dx, dz = OUT[s]
        if kind == "avenue" and ids.get((X + cx + dx, Z + cz + dz)) not in FLAT:
            return None, "avenue arm cell is piece %s" % ids.get((X + cx + dx, Z + cz + dz))
    return arms, ""


def is_ours(pid):
    return pid is not None and (pid == CENTRE or pid in SIDE_IDS.values() or CORNER0 <= pid < CORNER0 + 9)


def kind_code(kind, partner, state, cell_type):
    """local arm code of a block cell's outer edge"""
    if kind is None:
        return 0
    if kind == "road":
        return 1
    if cell_type == "corner":
        return 2
    lp = (partner - state) % 4                                     # partner side in the piece's own frame
    return 2 if lp == 1 else 3


def wanted(arms):
    """arms of one block -> {block cell: (piece, state)} and the avenue arm cells {offset cell: (11204, state)}"""
    out, extra = {}, {}
    for cx in range(3):
        for cz in range(3):
            t, st = cell_state((cx, cz))
            if t == "centre":
                out[(cx, cz)] = (CENTRE, 0)
                continue
            codes = {}
            for s in outer_sides((cx, cz)):
                kind, partner = arms.get(((cx, cz), s), (None, None))
                codes[(s - st) % 4] = kind_code(kind, partner, st, t)
                if kind == "avenue":
                    dx, dz = OUT[s]
                    extra[(cx + dx, cz + dz)] = (11204, {3: 2, 1: 0, 2: 1, 0: 3}[partner])
            if t == "side":
                out[(cx, cz)] = (SIDE_IDS[codes[2]], st)
            else:
                out[(cx, cz)] = (CORNER0 + 3 * codes[1] + codes[2], st)
    return out, extra


# ------------------------------------------------------------------------------------------------ scenes

def scene_arms(arms):
    from netmod import bigrbt_paint as BP
    return [BP.Arm(c, s, kind, partner) for (c, s), (kind, partner) in arms.items()]


def canon_arms(pid):
    """the canonical piece pid at state 0 -> (block cell, arms dict holding only its own edges)"""
    from netmod import bigrbt_paint as BP  # noqa: F401
    if pid == CENTRE:
        return (1, 1), {}
    for code, v in SIDE_IDS.items():
        if v == pid:
            c, arms = (2, 1), {}
            if code == 1:
                arms[((2, 1), 2)] = ("road", None)
            elif code in (2, 3):
                arms[((2, 1), 2)] = ("avenue", 1 if code == 2 else 3)
            return c, arms
    k = pid - CORNER0
    kN, kE = k // 3, k % 3
    c, arms = (2, 0), {}
    if kN:
        arms[((2, 0), 1)] = ("road", None) if kN == 1 else ("avenue", 0)     # N side: partner toward x- (cell (1,0))
    if kE:
        arms[((2, 0), 2)] = ("road", None) if kE == 1 else ("avenue", 3)     # E side: partner toward z+ (cell (2,1))
    return c, arms


ALL_PIECES = [CENTRE] + sorted(SIDE_IDS.values()) + list(range(CORNER0, CORNER0 + 9))

DEMO = {"W": "av01", "N": "av12", "E": "r1", "S": "r0,r2"}


def parse_arms(spec):
    """'W=av01;N=av12;E=r1;S=r0,r2' or the DEMO dict -> road cells of arms around a block at (0, 0), 3 cells long"""
    if isinstance(spec, str):
        spec = dict(p.split("=") for p in spec.split(";") if p)
    sid = {"W": 0, "N": 1, "E": 2, "S": 3}
    road = {(x, z) for x in range(3) for z in range(3)}
    for k, v in spec.items():
        s = sid[k]
        dx, dz = OUT[s]
        for item in v.split(","):
            idx = [int(ch) for ch in item[2:]] if item.startswith("av") else [int(item[1:])]
            for i in idx:
                cx, cz = SIDE_CELLS[s][i]
                for n in range(1, 4):
                    road.add((cx + dx * n, cz + dz * n))
    return road


def layout_for(road, cell_dir):
    """preview cells: the block from cell_dir(block cell, piece, state) -> (dir, slot), the arms as stock pieces"""
    arms, why = check(road, {c: 29 for c in road}, 0, 0)
    if arms is None:
        raise SystemExit("demo block does not qualify: " + why)
    want, extra = wanted(arms)
    cells = []
    for c, (pid, st) in want.items():
        d, slot = cell_dir(c, pid, st, arms)
        cells.append({"at": [-c[0], c[1]], "dir": d, "slot": slot, "like": 39})
    stock = {}
    for ((cx, cz), s), (kind, partner) in arms.items():       # the arms as the stock tiler draws them (avenue: 11204)
        dx, dz = OUT[s]
        for n in range(1, 4):
            c = (cx + dx * n, cz + dz * n)
            if c in road:
                stock[c] = (11204, {3: 2, 1: 0, 2: 1, 0: 3}[partner]) if kind == "avenue" else (29, 0 if s in (0, 2) else 1)
    for (x, z) in sorted(road):
        if 0 <= x <= 2 and 0 <= z <= 2:
            continue
        pid, st = stock.get((x, z), (29, 0))
        cells.append({"at": [-x, z], "piece": pid, "slot": st})
    return cells, arms, want


def _write_anchors(d, anchors, note):
    anchors = dict(anchors)
    anchors["_"] = note
    json.dump(anchors, open(os.path.join(d, "anchors.json"), "w"), indent=1)


# ------------------------------------------------------------------------------------------------ lanes

# Car lanes in the canonical frames (state 0). ENGLISH is right-hand traffic: road 29's lane at z 80 runs +x
# (NET_LANES.md 2.4), so the ring runs counter-clockwise seen from above (island on the left): +x along the N
# side, +z along the E side. Only stock curves: VPATHATT has no new shapes (NET_LANES.md 3), so the ring is the outer
# slot of each cell (x 175 in the E side cell, the r175 left turn 1024 round the centre cell's corner in the NE
# corner) and every entry / exit is a stock right turn (r80) or a straight where the arm is tangent to the ring.
RING = {"side": {"from": [175, 0], "to": [175, 255], "path": 259},
        "corner": {"from": [0, 80], "to": [175, 255], "path": 1024}}
ARM_LANES = {                       # (cell type, local side) -> (inbound lane, outbound lane)
    ("side", 2): ({"from": [255, 175], "to": [175, 255], "path": 771},
                  {"from": [175, 0], "to": [255, 80], "path": 770}),
    ("corner", 1): ({"from": [175, 0], "to": [175, 255], "path": 259},
                    {"from": [0, 80], "to": [80, 0], "path": 769}),
    ("corner", 2): ({"from": [255, 175], "to": [175, 255], "path": 771},
                    {"from": [0, 80], "to": [255, 80], "path": 512}),
}
SIDE_NAME = {0: "x-", 1: "z-", 2: "x+", 3: "z+"}
PED_EDGE = {1: ([15, 15], [240, 15], 256), 2: ([240, 15], [240, 240], 257)}     # walk along an outer edge (local side)


def lane_spec(pid):
    """lanekit authoring spec of a piece (state-0 frame)"""
    cell, arms = canon_arms(pid)
    t, _st = cell_state(cell)
    spec = {"_": "bigrbt.py: 3x3 roundabout piece %d (%s cell, arms %s)" % (
                pid, t, sorted("%s %s" % (SIDE_NAME[s], k[0]) for (c, s), k in arms.items())),
            "piece": pid, "states": [0, 1, 2, 3], "flag": 1}
    if t == "centre":                                # the island: nothing drives or walks here
        spec["vehicle"] = {"class": "car", "lanes": []}
        spec["pedestrian"] = {"walks": [], "exits": []}
        spec["connects"] = {"road": []}
        return spec
    lanes = [dict(RING[t])]
    ends = {tuple(lanes[0]["to"])}
    for (c, s), _k in sorted(arms.items()):
        for ln in ARM_LANES[(t, s)]:
            ln = dict(ln)
            if tuple(ln["to"]) in ends:
                ln["exit"] = False          # merges into the ring: the ring lane's own exit edge leaves that node
            ends.add(tuple(ln["to"]))
            lanes.append(ln)
    spec["vehicle"] = {"class": "car", "lanes": lanes}
    walks, exits = [], []
    for ls in ([2] if t == "side" else [1, 2]):     # the block's outer sidewalk; a crosswalk over an arm
        a, b, path = PED_EDGE[ls]
        armed = any(s == ls for (_c, s) in arms)
        walks.append({"from": a, "to": b, "path": path, "crosswalk": armed})
        if armed:
            exits += [{"at": a, "code": 8 * ls}, {"at": b, "code": 8 * ls}]
    if t == "side":                                  # on along the perimeter: z- to the NE corner, z+ to the SE one
        exits += [{"at": [240, 15], "code": 8}, {"at": [240, 240], "code": 24}]
    else:                                            # x- to the N side cell, z+ to the E side cell
        exits += [{"at": [15, 15], "code": 0}, {"at": [240, 240], "code": 24}]
    spec["pedestrian"] = {"walks": walks, "exits": exits}
    # the turns every lane drives (a lane that merges into the ring's exit node has no exit edge of its own, so
    # lanekit's "auto" would leave its turn out of the matrix)
    pairs = []
    for ln in lanes:
        pr = [_edge_side(ln["from"]), _edge_side(ln["to"])]
        if pr not in pairs:
            pairs.append(pr)
    spec["connects"] = {"road": pairs}
    return spec


def _edge_side(p):
    return "x-" if p[0] == 0 else "x+" if p[0] == 255 else "z-" if p[1] == 0 else "z+"


def base_of(pid):
    """the variant's base = the piece a game without the mod loads (SAVEBASE): 43 where the cell holds several
    roads, the stock T 39 / curve 11203 for an arm-less side / corner (their stock connections in that state)"""
    if pid == SIDE_IDS[0]:
        return 39
    if pid == CORNER0:
        return 11203
    return 43


NAMES = {"*": "Roundabout (3x3)", "ENGLISH": "Rotonda grande"}


def manifest():
    variants, lanes = [], []
    for pid in ALL_PIECES:
        variants.append({"id": pid, "base": base_of(pid), "network": "ROAD", "name": NAMES,
                         "art": {"from": 39, "png_dir": "art/%d" % pid}, "trblkatt": "copy_base"})
        lanes.append({"piece": pid, "spec": "%d.lanes.json" % pid})
    return {
        "netpack": 1, "name": "big_roundabout", "version": "0.1.0", "author": "netmod (task bigrbt)",
        "description": "Automatic 3x3 roundabouts: draw a 3x3 square of road cells with roads or avenues leaving it "
                       "(at most two per side: an avenue on two neighbouring cells, or two single roads on the outer "
                       "cells) and sc3netmod's RBT9 block turns it into one big roundabout: circular grass island, "
                       "one-lane ring running counter-clockwise, give-way lines at the entries, avenue medians ending "
                       "in a nose at the ring. 14 pieces (20600 centre, 20601..20604 side cells, 20610..20618 corner "
                       "cells by their arms), all painted from stock road 29's frames by `bigrbt.py build .` in this "
                       "folder before install (art/ is made from the game's frames and is not shipped). Lanes: stock "
                       "curves only. A game without the mod opens the block as stock 43 / 39 / 11203 road.",
        "game": {"Apps/SIMNTWRK.DLL": "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"},
        "variants": variants, "lanes": lanes,
        "auto_big_roundabouts": [{"centre": CENTRE, "side": [SIDE_IDS[k] for k in range(4)],
                                  "corner": list(range(CORNER0, CORNER0 + 9))}]}


def cmd_build(a):
    from netmod import bigrbt_paint as BP
    from netmod import diagave_paint as DP
    zooms = [int(v) for v in a.zooms.split(",")] if a.zooms else list(range(5))
    os.makedirs(a.pack, exist_ok=True)
    for pid in ALL_PIECES:
        if a.only and pid not in a.only:
            continue
        cell, arms = canon_arms(pid)
        d = os.path.join(a.pack, "art", str(pid))
        if not a.lanes_only:
            anc = DP.paint_cell(BP.Roundabout3(scene_arms(arms)), cell, d, zooms=zooms)
            _write_anchors(d, anc, "bigrbt.py build: piece %d = block cell %s of the scene with arms %s" % (
                pid, cell, sorted(arms.items())))
        json.dump(lane_spec(pid), open(os.path.join(a.pack, "%d.lanes.json" % pid), "w", newline="\n"),
                  indent=1)
        print("built %d (cell %s, arms %s)" % (pid, cell, sorted(arms.items())))
    if a.manifest:
        json.dump(manifest(), open(os.path.join(a.pack, "manifest.json"), "w", newline="\n"), indent=1)
        print("wrote manifest.json")


def sheet(shots, zooms, rots):
    from PIL import Image
    cw = max(i.width for i in shots.values())
    ch = sum(max(shots[(z, r)].height for r in rots) for z in zooms)
    out = Image.new("RGB", (cw * len(rots), ch), (20, 20, 20))
    y = 0
    for z in zooms:
        h = max(shots[(z, r)].height for r in rots)
        for i, r in enumerate(rots):
            out.paste(shots[(z, r)].convert("RGB"), (i * cw, y))
        y += h
    return out


def cmd_preview(a):
    """the block from the built pieces (each cell its canonical piece in its state)"""
    from netmod import netart
    road = parse_arms(a.arms or DEMO)

    def cell_dir(c, pid, st, arms):
        return os.path.join(a.pack, "art", str(pid)), st

    cells, arms, want = layout_for(road, cell_dir)
    zooms = [int(v) for v in a.zooms.split(",")]
    rots = [int(v) for v in a.rots.split(",")]
    sheet(netart.preview({"cells": cells}, None, zooms=zooms, rots=rots), zooms, rots).save(a.out)
    print(a.out, {c: v for c, v in sorted(want.items())})


def cmd_mockup(a):
    """Every block cell painted straight from the world scene of the demo block (slot 0), arms as stock pieces."""
    from PIL import Image
    from netmod import netart
    from netmod import bigrbt_paint as BP
    from netmod import diagave_paint as DP
    road = parse_arms(a.arms or DEMO)
    work = a.work or os.path.join(os.path.dirname(os.path.abspath(a.out)), "bigrbt_mockup_cells")
    zooms = [int(v) for v in a.zooms.split(",")]
    rots = [int(v) for v in a.rots.split(",")]
    scene = [None]

    def cell_dir(c, pid, st, arms):
        if scene[0] is None:
            scene[0] = BP.Roundabout3(scene_arms(arms))
        d = os.path.join(work, "c%d%d" % c)
        anc = DP.paint_cell(scene[0], c, d, zooms=zooms)
        _write_anchors(d, anc, "bigrbt mockup cell %s" % (c,))
        return d, 0

    cells, arms, want = layout_for(road, cell_dir)
    shots = netart.preview({"cells": cells}, None, zooms=zooms, rots=rots)
    cw = max(i.width for i in shots.values())
    ch = sum(max(shots[(z, r)].height for r in rots) for z in zooms)
    sheet = Image.new("RGB", (cw * len(rots), ch), (20, 20, 20))
    y = 0
    for z in zooms:
        h = max(shots[(z, r)].height for r in rots)
        for i, r in enumerate(rots):
            sheet.paste(shots[(z, r)].convert("RGB"), (i * cw, y))
        y += h
    sheet.save(a.out)
    print(a.out, sheet.size, "pieces:", {c: v for c, v in sorted(want.items())})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("mockup")
    s.add_argument("out")
    s.add_argument("--arms")
    s.add_argument("--work")
    s.add_argument("--zooms", default="4,3")
    s.add_argument("--rots", default="0,1")
    s = sub.add_parser("build")
    s.add_argument("pack")
    s.add_argument("--zooms")
    s.add_argument("--only", type=int, nargs="*")
    s.add_argument("--lanes-only", action="store_true")
    s.add_argument("--manifest", action="store_true")
    s = sub.add_parser("preview")
    s.add_argument("out")
    s.add_argument("pack")
    s.add_argument("--arms")
    s.add_argument("--zooms", default="4,3")
    s.add_argument("--rots", default="0,1")
    a = ap.parse_args(argv)
    {"mockup": cmd_mockup, "build": cmd_build, "preview": cmd_preview}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
