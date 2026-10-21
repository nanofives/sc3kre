#!/usr/bin/env python3
r"""bvx.py - boulevard junctions with avenues and with other boulevards (task bvx, 2026-10-17): the rule's wide
junction spans, the box pieces, art and lanes, offline checks. Offline twin of sc3netmod_bvx.c; the rule itself runs
inside the boulevard's (boulevard.py runs(), sc3netmod_bv.c bv_run1()), which calls the two hooks below.

A boulevard is three parallel straight roads (boulevard.py). Along a boulevard run, a JUNCTION SPAN is a group of
consecutive columns with road beside the run. One column wide = a single road (the boulevard's own junction pieces,
unchanged). Two or three columns wide with each side either road over the whole span or empty = a WIDE span:
  2 wide   an avenue (two parallel roads) crossing the boulevard (arms on both sides) or ending on it (one side)
  3 wide   another boulevard crossing it or ending on it
  end      a wide span at the very end of the run, nothing beyond it, arms on both sides: the boulevard ends on that
           avenue / boulevard (a T); one side only (a corner) is refused
  arm      every arm straight and clean for ARM_LEN cells: the side's cells go on that far, nothing beside them
The box = the span's columns x the boulevard's three rows, one paved box. Each box cell gets the piece of its edge
pattern N E S W (I another box cell, A an arm, C closed: the far side of a T), computed in REAL directions, so the two
runs of a boulevard x boulevard box (one along x, one along z) choose the same piece and state. Each avenue arm's
first cell (beside the box) becomes 11204 with the median ending in a nose (ARM, as avenue_junctions' 20810 / 20811);
a boulevard arm's first column gets the boulevard's own NOSE / OUTER pieces from its own run. Pieces 20900..20949.

Shape ownership (CHILD_PROTOCOL section 5 / 11): 2x2 blocks (RBT), an exactly-3x3 block (bigrbt: a boulevard x
boulevard box has 3-cell sides, a run shorter than 4 columns is refused by BV anyway), avenue x avenue (avx: no three
parallel roads), diagonals (no straight clean arm).

  py -3.12 bvx.py build PACK_DIR            art/<id>/ (+ anchors.json), box_<id>.lanes.json, manifest.json
  py -3.12 bvx.py check [--tiler]           every kind x rotation through boulevard.runs(); AVX / RBT on the stock tiles
  py -3.12 bvx.py mockup OUT.png PACK_DIR   owner sheet: stock vs bvx per kind, zoom 4 and 3, views 0 and 1
  py -3.12 bvx.py plan SAVE                 the junctions of a save and the pieces the rule wants
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

ARM_LEN = 2
# canonical box cells (edges N E S W at state 0) -> piece. Closed edges sit on S at state 0 (as avenue_junctions).
BOX = {"AIIA": 20900,       # corner between two arms
       "IACI": 20901,       # corner between an arm (E) and the closed side (S)
       "IICA": 20902,       # corner between the closed side (S) and an arm (W)
       "IIAI": 20903,       # one outside edge, an arm (S)
       "IICI": 20904,       # one outside edge, closed (S)
       "IIII": 20905}       # the middle of a 3 x 3 box
ARM = {1: 20910, 3: 20911}  # 11204 (state 0: median N, outer sidewalk S) with the median nose at its E / W end
LANES_OF = {"IACI": (39, 1), "IICA": (39, 1), "IICI": (39, 1)}     # closed side: T 39's lanes; the rest copy 43's
OWN = set(BOX.values()) | set(ARM.values())
# task bvlanes: with one-way lanes the box cells are chosen by (real box w, h, sides N E S W, cell i j) from the table
# bvlanes.py build writes into the package (bvlanes_boxes.json); None = choose by edge pattern (bvlanes builds the
# table from those placements, so it calls box_want with TABLE None)
TABLE = None
TABLE_PATH = os.path.join(HERE, "examples", "boulevard_junctions", "bvlanes_boxes.json")


def load_table(path=TABLE_PATH):
    """-> {(w, h, sides, i, j): (piece, state)} and the box pieces [{"piece", "edges"}], or (None, []) without a table"""
    global TABLE
    if not os.path.isfile(path):
        return None, []
    d = json.load(open(path))
    TABLE = {}
    for ln in d["lines"]:
        t = ln.split()
        TABLE[(int(t[1]), int(t[2]), t[3], int(t[4]), int(t[5]))] = (int(t[6]), int(t[7]))
    return TABLE, d["pieces"]
EDGES = "NESW"
# axis-space direction -> real edge: axis 0 real (s, w), axis 1 real (-w, s) (boulevard.py _to_real)
REAL_EDGE = {0: {"-w": 0, "+s": 1, "+w": 2, "-s": 3}, 1: {"-s": 0, "-w": 1, "+s": 2, "+w": 3}}


def rot(desc, k):
    """edge pattern turned k states (N -> E per state), as avx.rot"""
    out = [None] * 4
    for e in range(4):
        out[(e + k) % 4] = desc[e]
    return "".join(out)


def box_piece(desc):
    for k in range(4):
        for canon, pid in BOX.items():
            if rot(canon, k) == desc:
                return pid, k
    return None


# ------------------------------------------------------------------------------------------------ hooks for runs()
def spans(R, sa, sb, w0):
    """wide junction spans of the run columns sa..sb (axis space road set R, rows w0..w0+2) -> ({column: span}, why).
    span = {"kind": "W" + "N"? + "S"?, "ja", "jb", "n": arm N, "s": arm S, "nc" / "sc": the arm's columns}. One-column
    groups and groups whose sides are partly road are left to the boulevard's own per-column rule (single roads, as
    before), except (task avx32) a 3-column span with a 2-column avenue arm at one end of a side: the crossing road is
    a boulevard on one side and an avenue on the other (owner img7), or an avenue crossing one column offset."""
    out, why, s = {}, "", sa
    while s <= sb:
        if (s, w0 - 1) not in R and (s, w0 + 3) not in R:
            s += 1
            continue
        ja = s
        while s + 1 <= sb and ((s + 1, w0 - 1) in R or (s + 1, w0 + 3) in R):
            s += 1
        jb, s = s, s + 1
        m = jb - ja + 1
        if m < 2:
            continue
        side = {}
        for key, w, d in (("n", w0 - 1, -1), ("s", w0 + 3, 1)):
            cols = [c for c in range(ja, jb + 1) if (c, w) in R]
            if len(cols) not in (0, m) and not (m == 3 and len(cols) == 2 and cols in ([ja, ja + 1], [jb - 1, jb])):
                side = None                                     # task avx32: partial arms at one end of a 3-span
                break
            side[key] = (bool(cols), w, d, cols)
        if side is None:
            continue                                            # staggered single roads: the per-column rule
        if m > 3:
            why = why or "road %d wide beside the boulevard at columns %d..%d" % (m, ja, jb)
            continue
        for key, (arm, w, d, cols) in side.items():
            if not arm:
                continue
            c0, c1 = cols[0], cols[-1]
            for k in range(ARM_LEN):
                if not all((c, w + d * k) in R for c in cols):
                    why = why or "arm at columns %d..%d shorter than %d" % (c0, c1, ARM_LEN)
                if (c0 - 1, w + d * k) in R or (c1 + 1, w + d * k) in R:
                    why = why or "arm at columns %d..%d has road beside it" % (c0, c1)
        sp = {"kind": "W" + ("N" if side["n"][0] else "") + ("S" if side["s"][0] else ""), "ja": ja, "jb": jb,
              "n": side["n"][0], "s": side["s"][0], "nc": side["n"][3], "sc": side["s"][3]}
        for c in range(ja, jb + 1):
            out[c] = sp
    return out, why


def partial_letter(cells, arm, e):
    """task avx32: the letter of a box side (real edge e, N E S W) from the real cells beyond it and the ones an arm
    holds: 'A' all, 'C' none, 'L' the arm holds the low end of the side (smaller x on N / S, smaller z on E / W),
    'H' the high end (a 2-column avenue at one end of a 3-cell side)."""
    if not arm:
        return "C"
    if len(arm) == len(cells):
        return "A"
    k = 0 if e in (0, 2) else 1
    free = [c for c in cells if c not in arm]
    return "L" if min(c[k] for c in free) > min(c[k] for c in arm) else "H"


def box_want(axis, w0, sp, lo_closed, hi_closed, to_real, lo_arm=None, hi_arm=None):
    """the box of span sp (+ the avenue arms' nose cells) -> {real cell: (piece, state)}, or None if a pattern has no
    piece. lo_closed / hi_closed: the -s / +s side is the far side of a T (the run ends on the crossing road).
    lo_arm / hi_arm (task avx32): the rows w of an avenue going on past the run's -s / +s end, the box being that
    end (the crossing road is this boulevard on one side of the box and an avenue on the other)."""
    from netmod import avx
    ja, jb = sp["ja"], sp["jb"]
    E = REAL_EDGE[axis]
    beyond = {"-s": [(ja - 1, w) for w in range(w0, w0 + 3)], "+s": [(jb + 1, w) for w in range(w0, w0 + 3)],
              "-w": [(c, w0 - 1) for c in range(ja, jb + 1)], "+w": [(c, w0 + 3) for c in range(ja, jb + 1)]}
    arm = {"-s": [] if lo_closed else [(ja - 1, w) for w in (lo_arm or range(w0, w0 + 3))],
           "+s": [] if hi_closed else [(jb + 1, w) for w in (hi_arm or range(w0, w0 + 3))],
           "-w": [(c, w0 - 1) for c in sp.get("nc", range(ja, jb + 1) if sp["n"] else [])],
           "+w": [(c, w0 + 3) for c in sp.get("sc", range(ja, jb + 1) if sp["s"] else [])]}
    side = {k: partial_letter([to_real(axis, *c) for c in beyond[k]], [to_real(axis, *c) for c in arm[k]], E[k])
            for k in beyond}
    want = {}
    if TABLE is not None:                                       # task bvlanes: by box kind and position
        re_ = [None] * 4
        for key in ("-s", "+s", "-w", "+w"):
            re_[E[key]] = side[key]
        cells = [to_real(axis, s, w) for s in range(ja, jb + 1) for w in range(w0, w0 + 3)]
        x0, z0 = min(c[0] for c in cells), min(c[1] for c in cells)
        bw, bh = max(c[0] for c in cells) - x0 + 1, max(c[1] for c in cells) - z0 + 1
        for c in cells:
            v = TABLE.get((bw, bh, "".join(re_), c[0] - x0, c[1] - z0))
            if not v:
                return None
            want[c] = v
    for s in range(ja, jb + 1) if TABLE is None else ():
        for w in range(w0, w0 + 3):
            d = [None] * 4
            for key, (ns, nw) in (("-s", (s - 1, w)), ("+s", (s + 1, w)), ("-w", (s, w - 1)), ("+w", (s, w + 1))):
                inside = ja <= ns <= jb and w0 <= nw <= w0 + 2
                d[E[key]] = "I" if inside else "A" if (ns, nw) in arm[key] else "C"     # task avx32: per cell
            bp = box_piece("".join(d))
            if not bp:
                return None
            want[to_real(axis, s, w)] = bp
    for key in ("-w", "+w"):                                    # avenue arms (2 columns): the nose cells
        if len(arm[key]) != 2:
            continue
        e = E[key]
        cells = sorted((to_real(axis, *c) for c in arm[key]), key=lambda c: (c[0], c[1]) if e in (0, 2)
                       else (c[1], c[0]))
        for i, c in enumerate(cells):
            st = avx.half_state(e, i == 0)
            want[c] = (ARM[((e + 2) % 4 - st) % 4], st)
    return want


# ------------------------------------------------------------------------------------------------ pieces, build
NAMES = {"*": "Boulevard crossing", "ENGLISH": "Cruce de bulevar"}


class Box:
    """A box cell at state 0, edges `desc` (N E S W): avenue_junctions' box art (avx.Box: 29's curb on a closed side,
    43's corner where two arms meet, 43's own crosswalk lines across an arm) with one change: the plain asphalt is a
    palette of stock 43's plain asphalt picked per pixel instead of 43 mirrored about the cell middle. The mirror repeats a dark
    ring per cell, which reads as a quilt on a 2 x 3 or 3 x 3 box (mockup 2026-10-17). The palette is 43's own
    (asphalt43), so the tone stays the stock crossing's."""

    def __init__(self, desc):
        self.d = desc

    def colour(self, z, r, wx, wz):
        from netmod import avx
        from netmod import diagave_paint as P
        S = P.STOCK
        x, zl = (wx % 1.0) * 256.0, (wz % 1.0) * 256.0
        dist = (zl, 256.0 - x, 256.0 - zl, x)
        for e in range(4):
            if self.d[e] == "C" and dist[e] < avx.CURB_BAND:
                return S(29, e % 2, z, r, x, zl)
        for e in range(4):
            f = (e + 1) % 4
            if self.d[e] == "A" and self.d[f] == "A" and dist[e] < avx.CORNER and dist[f] < avx.CORNER:
                return S(43, 0, z, r, x, zl)
        for e in range(4):
            if self.d[e] == "A" and dist[e] < avx.LINE_BAND:
                px, pz = (min(avx.LINE_HI, max(avx.LINE_LO, x)), zl) if e % 2 == 0 else \
                    (x, min(avx.LINE_HI, max(avx.LINE_LO, zl)))
                c = S(43, 0, z, r, px, pz)
                if P.light(c):
                    return c
        pal = asphalt43(z)
        h = (int(wx * 512) * 73856093) ^ (int(wz * 512) * 19349663) ^ (z * 83492791)
        return pal[h % len(pal)]


_PAL = {}


def asphalt43(z):
    """the plain asphalt of stock 43 at zoom z: its pixels in the marking-free middle (lane units 72..184 both ways), all
    four views. Same tone as the stock crossing (mean luma 93 at zoom 3 and 4; diagave_paint's road palette is 107)"""
    if z not in _PAL:
        from netmod import diagave_paint as P
        out = []
        for r in range(4):
            for i in range(57):
                for j in range(57):
                    c = P.STOCK(43, 0, z, r, 72.0 + 2.0 * i, 72.0 + 2.0 * j)
                    if c[3] and not P.light(c):
                        out.append((c[0], c[1], c[2], 255))
        _PAL[z] = out
    return _PAL[z]


def cmd_build(a):
    from netmod import netart as NA
    from netmod import diagave_paint as P
    from netmod import diagave as D
    from netmod import avx
    art = lambda vid: os.path.join(a.pack, "art", str(vid))                       # noqa: E731
    only = set(int(v) for v in a.only.split(",")) if a.only else None
    _tab, groups = load_table(os.path.join(a.pack, "bvlanes_boxes.json"))     # task bvlanes
    boxes = sorted(BOX.items(), key=lambda t: t[1]) if not groups else [(g["edges"], g["piece"]) for g in groups]
    for desc, vid in boxes:
        if only and vid not in only:
            continue
        d = art(vid)
        anc = P.paint_cell(Box(desc), (0, 0), d)
        D._write_anchors(d, anc, "bvx.py build: box cell %s" % desc)
        if desc in LANES_OF and not groups:
            pid, st = LANES_OF[desc]
            spec = D.parts_spec([(pid, st)], vid, "bvx box cell %s: lanes of %d state %d" % (desc, pid, st))
            json.dump(spec, open(os.path.join(a.pack, "box_%d.lanes.json" % vid), "w", newline="\n"), indent=1)
        print("built %d (box %s)" % (vid, desc))
    for d0, vid in sorted(ARM.items(), key=lambda t: t[1]):
        if only and vid not in only:
            continue
        d = art(vid)
        os.makedirs(d, exist_ok=True)
        anc = {}
        for z in range(NA.ZOOMS):
            for r in range(NA.ROTS):
                im, LT = avx.arm_frame(d0, z, r)
                im.save(os.path.join(d, NA.frame_name(z, r)))
                anc[NA.frame_name(z, r)] = list(LT)
        D._write_anchors(d, anc, "bvx.py build: 11204 with the median nose at the %s end (avx.arm_frame)" % EDGES[d0])
        print("built %d (avenue arm, nose %s)" % (vid, EDGES[d0]))
    write_manifest(a.pack)


def write_manifest(pack):
    variants = []
    _tab, groups = load_table(os.path.join(pack, "bvlanes_boxes.json"))        # task bvlanes: one-way lanes
    bvl = lambda vid: os.path.isfile(os.path.join(pack, "bvl_%d.lanes.json" % vid))   # noqa: E731
    boxes = sorted(BOX.items(), key=lambda t: t[1]) if not groups else [(g["edges"], g["piece"]) for g in groups]
    for desc, vid in boxes:
        variants.append({"id": vid, "base": 43, "network": "ROAD", "name": NAMES,
                         "art": {"from": 43, "png_dir": "art/%d" % vid},
                         "trblkatt": "none" if desc in LANES_OF or bvl(vid) else "copy_base"})
    for d0, vid in sorted(ARM.items(), key=lambda t: t[1]):
        variants.append({"id": vid, "base": 11204, "network": "ROAD", "name": {"*": "Avenue", "ENGLISH": "Avenida"},
                         "art": {"from": 11204, "png_dir": "art/%d" % vid},
                         "trblkatt": "none" if bvl(vid) else "copy_base"})
    man = {"netpack": 1, "name": "boulevard_junctions", "version": "0.1.0", "author": "netmod (task bvx)",
           "description": "Boulevard junctions with avenues and with other boulevards: where an avenue (two parallel "
                          "roads) or another boulevard (three) crosses a boulevard, ends on it, or the boulevard ends on "
                          "it, sc3netmod's BV block makes the crossing one paved box: crosswalks across every arm at the "
                          "box edge, curbs round the outer corners and along the far side of a T, every median ending "
                          "in a concrete nose with its trees. Needs the boulevard package (its pieces next to the box). "
                          "Box cells 20900..20905 (one per edge pattern, base 43), avenue nose cells 20910 / 20911 "
                          "(base 11204). Built by `bvx.py build .` in this folder before install (art/ is made from "
                          "the game's frames and is not shipped).",
           "game": {"Apps/SIMNTWRK.DLL": "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"},
           "variants": variants,
           "lanes": [{"piece": v["id"], "spec": "bvl_%d.lanes.json" % v["id"]} for v in variants if bvl(v["id"])]
           if groups else
                    [{"piece": vid, "spec": "box_%d.lanes.json" % vid} for desc, vid in sorted(BOX.items(),
                                                                                           key=lambda t: t[1])
                     if desc in LANES_OF],
           "auto_boulevard_junctions": [{"box": [{"piece": vid, "edges": desc} for desc, vid in
                                                 sorted(BOX.items(), key=lambda t: t[1])],
                                         "arm": [{"piece": ARM[1], "nose": "E"}, {"piece": ARM[3], "nose": "W"}],
                                         "cells": json.load(open(os.path.join(pack, "bvlanes_boxes.json")))["lines"]
                                         if groups else []}]}
    if groups:                                                  # task bvlanes: the noses end one-way avenue bands
        man["version"] = "0.2.0"
        man["avenue_lines"] = ["avlj %d ...O" % ARM[1], "avlj %d .I.." % ARM[3]]
    json.dump(man, open(os.path.join(pack, "manifest.json"), "w", newline="\n"), indent=1)
    print("manifest: %d variants, %d lane specs" % (len(variants), len(man["lanes"])))


# ------------------------------------------------------------------------------------------------ shapes, checks
def shapes():
    """canonical drawings: boulevard A along x on rows 0..2 -> road cells"""
    A = {(x, z) for x in range(-9, 11) for z in range(3)}
    S = {
        "BxA": A | {(x, z) for x in (0, 1) for z in range(-8, 11)},                   # avenue crossing
        "AvT": A | {(x, z) for x in (0, 1) for z in range(-8, 0)},                    # avenue ends on the boulevard
        "BvT": {(x, z) for x in range(-9, 2) for z in range(3)} |                     # boulevard ends on an avenue
               {(x, z) for x in (0, 1) for z in range(-8, 11)},
        "BxB": A | {(x, z) for x in (0, 1, 2) for z in range(-9, 12)},                # boulevard crossing
        "BbT": A | {(x, z) for x in (0, 1, 2) for z in range(-9, 0)},                 # boulevard T
        # task avx32: the crossing road is a boulevard on one side and an avenue on the other (owner img7), the
        # avenue at the high / low end of the box; an avenue crossing one column offset (N low S high / N high S low)
        "BxBAh": A | {(x, z) for x in (0, 1, 2) for z in range(-9, 0)} | {(x, z) for x in (1, 2) for z in range(3, 11)},
        "BxBAl": A | {(x, z) for x in (0, 1, 2) for z in range(-9, 0)} | {(x, z) for x in (0, 1) for z in range(3, 11)},
        "BxAlh": A | {(x, z) for x in (0, 1) for z in range(-8, 0)} | {(x, z) for x in (1, 2) for z in range(3, 11)},
        "BxAhl": A | {(x, z) for x in (1, 2) for z in range(-8, 0)} | {(x, z) for x in (0, 1) for z in range(3, 11)},
    }
    return S


def _rot_cells(cells, k):
    out = set()
    for (x, z) in cells:
        for _ in range(k % 4):
            x, z = -z - 1, x
        out.add((x, z))
    return out


def junction_wants(road):
    """runs() over a road set -> (wanted pieces merged over the accepted runs, accepted runs, refused runs, clashes)"""
    from netmod import boulevard as B
    want, ok, bad, clash = {}, [], [], []
    for r in B.runs(road):
        if not r["ok"]:
            bad.append(r)
            continue
        ok.append(r)
        for c, v in r["want"].items():
            if c in want and want[c] != v:
                clash.append((c, want[c], v))
            want[c] = v
    return want, ok, bad, clash


SYM = {20701: 2, 20703: 2, 20905: 1}     # boulevard MIDDLE / NOSE2 look the same turned half a circle, IIII any turn


def norm(want):
    return {c: (p, st % SYM.get(p, 4)) for c, (p, st) in want.items()}


def cmd_check(a):
    from netmod import avx
    fails = 0
    S = shapes()
    expect_runs = {"BxA": 1, "AvT": 1, "BvT": 1, "BxB": 2, "BbT": 2, "BxBAh": 2, "BxBAl": 2, "BxAlh": 1, "BxAhl": 1}
    ref = {}
    for name, cells in sorted(S.items()):
        for k in range(4):
            R = _rot_cells(cells, k)
            want, ok, bad, clash = junction_wants(R)
            boxes = {c: v for c, v in want.items() if v[0] in OWN}
            good = len(ok) == expect_runs[name] and not clash and boxes and \
                not [r for r in bad if r["sb"] - r["sa"] + 1 >= 4]
            # rotation invariance: the rotated canonical wants
            if k == 0:
                ref[name] = want
            else:
                exp = {}
                for c, (p, st) in ref[name].items():
                    exp[next(iter(_rot_cells({c}, k)))] = (p, (st + k) & 3)
                if norm(exp) != norm(want):
                    good = False
                    print("  rotation %d differs from rotation 0 turned: %d cell(s)" %
                          (k, sum(1 for c in set(exp) | set(want) if exp.get(c) != want.get(c))))
            fails += not good
            print("%-4s rot %d: %s  runs ok %d, refused (4+ columns) %s, box/nose cells %d, clashes %d" % (
                name, k, "OK  " if good else "FAIL", len(ok),
                [r["why"] for r in bad if r["why"] and r["sb"] - r["sa"] + 1 >= 4] or "-",
                len(boxes), len(clash)))
            if a.verbose and k == 0:
                print(grid(want, -4, -4, 5, 6))
            # AVX on the same road: no junction may be found there
            js, _ = avx.find(R)
            if js:
                fails += 1
                print("  FAIL avx would convert: %s" % [j["kind"] for j in js])
    # the boulevard's own layouts must be unchanged (no wide span there)
    from netmod import boulevard as B
    road = {(x, z) for x in range(0, 13) for z in range(3)} | {(x, z) for x in range(-3, 0) for z in (0, 1)} | \
        {(x, z) for x in range(13, 16) for z in (1, 2)} | {(6, z) for z in range(-2, 5)}
    n = sum(len(r["want"]) for r in B.runs(road) if r["ok"])
    print("boulevard 'avenue' layout: %d cell(s) wanted (round 2: 39)" % n)
    fails += n != 39
    if a.tiler:
        from netmod import rb_auto
        for name, cells in sorted(S.items()):
            g = avx.stock_grid(cells)
            road = lambda x, z: g.get((x, z))                                     # noqa: E731
            hits = [(x, z) for (x, z) in cells if rb_auto.check(road, x, z)[0]]
            js, _ = avx.find(set(cells), {c: v[0] for c, v in g.items()})
            fails += bool(hits) + bool(js)
            print("stock %-4s: RBT %s, AVX %s" % (name, "none" if not hits else "FAIL %s" % hits,
                                                  "none" if not js else "FAIL %s" % [j["kind"] for j in js]))
            if a.verbose:
                print(avx.grid_text(g, -4, -4, 4, 5))
    print("%d failure(s)" % fails)
    return 1 if fails else 0


def grid(want, x0, z0, x1, z1):
    rows = ["%4d " % z + " ".join("%8s" % ("%d.%d" % want[(x, z)] if (x, z) in want else ".")
                                  for x in range(x0, x1 + 1)) for z in range(z0, z1 + 1)]
    return "\n".join(rows + ["     " + " ".join("%8d" % x for x in range(x0, x1 + 1))])


# ------------------------------------------------------------------------------------------------ mockup
def layout(cells, packs, use_mod, window=None):
    """cells for boulevard.render (both layers: the median trees): the stock tiler's pieces, with the rule's pieces over
    them when use_mod"""
    from netmod import avx
    g = avx.stock_grid(cells)
    want = junction_wants(set(cells))[0] if use_mod else {}
    out = []
    for c, (pid, s) in g.items():
        if window and c not in window:
            continue
        if c in want:
            p, st = want[c]
            d = os.path.join(packs[0] if p in OWN else packs[1], "art", str(p))
            out.append({"x": c[0], "z": c[1], "dir": d, "state": st})
        else:
            out.append({"x": c[0], "z": c[1], "piece": pid, "state": s})
    return out


def cmd_mockup(a):
    from PIL import Image, ImageDraw
    from netmod import boulevard as B
    S = shapes()
    packs = (os.path.abspath(a.pack), os.path.abspath(a.boulevard))
    cols = [("stock", False, 3, 0), ("bvx", True, 4, 0), ("bvx", True, 4, 1), ("bvx", True, 3, 0), ("bvx", True, 3, 1)]
    names = a.only.split(",") if a.only else ["BxA", "AvT", "BvT", "BxB", "BbT"]
    rows = []
    for name in names:
        win = {c for c in S[name] if -5 <= c[0] <= 6 and -5 <= c[1] <= 7}
        shots = []
        for label, mod, z, r in cols:
            lay = layout(S[name], packs, mod, win)
            sh = B.render(lay, z, r)
            shots.append(("%s %s zoom %d view %d" % (name, label, z, r), sh))
        rows.append(shots)
    cw = max(im.width for row in rows for _, im in row)
    ch = max(im.height for row in rows for _, im in row) + 18
    sheet = Image.new("RGB", (cw * len(cols), ch * len(rows)), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for i, row in enumerate(rows):
        for j, (lab, im) in enumerate(row):
            sheet.paste(im.convert("RGB"), (j * cw + (cw - im.width) // 2, i * ch + 18 + (ch - 18 - im.height) // 2))
            dr.text((j * cw + 6, i * ch + 3), lab, fill=(230, 230, 230))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(a.out, sheet.size)


def cmd_plan(a):
    """the boulevard runs of a save with wide junctions, and the pieces they want (read-only)"""
    from netmod import boulevard as B
    road = B.road_of_save(a.save)
    for r in B.runs(road):
        if r["sb"] - r["sa"] + 1 < 4:
            continue
        print("run axis %d row %d columns %d..%d: %s" % (r["axis"], r["w0"], r["sa"], r["sb"],
                                                       "converts" if r["ok"] else r["why"]))
        for c in sorted(r["want"], key=lambda c: (c[1], c[0])):
            print("  (%d,%d) %d.%d" % (c[0], c[1], *r["want"][c]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("build")
    s.add_argument("pack")
    s.add_argument("--only")
    s = sub.add_parser("check")
    s.add_argument("--tiler", action="store_true")
    s.add_argument("-v", "--verbose", action="store_true")
    s = sub.add_parser("mockup")
    s.add_argument("out")
    s.add_argument("pack")
    s.add_argument("--boulevard", default=os.path.join(HERE, "examples", "boulevard"))
    s.add_argument("--only")
    s = sub.add_parser("plan")
    s.add_argument("save")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "check": cmd_check, "mockup": cmd_mockup, "plan": cmd_plan}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
