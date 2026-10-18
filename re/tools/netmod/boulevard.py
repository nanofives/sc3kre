#!/usr/bin/env python3
r"""boulevard.py - boulevards (task boulevard, 2026-10-17): three parallel straight roads drawn side by side become
one 3-wide avenue. The rule's offline twin, the pieces' art and lanes, offline checks.

Stock tiles three parallel roads as 11204 / 29 / 11204: two avenue medians facing a plain road
(re/sessions/CHILD_PROTOCOL_2026-10-17.md section 4). Here the outer roads are the carriageways (stock road look,
yellow centre line kept), the middle road gives each one an extra lane along its inner side and holds a grass median
with 11204's trees, about twice as wide as the stock avenue's (boulevard_paint.py has the cross-section).

  py -3 boulevard.py build PACK_DIR            art/<id>/ (z*_r*.png [+ l1_*] + anchors.json) and *.lanes.json
  py -3 boulevard.py preview OUT.png PACK_DIR --layout NAME [--zoom 4] [--rot 0]
  py -3 boulevard.py mockup OUT.png PACK_DIR   the owner mockup: zoom 4 and 3, views 0 and 1
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from netmod import bvx as BX                                     # noqa: E402  task bvx: wide junctions

# piece ids (20700..20749, CHILD_PROTOCOL section 6). Canonical frame: boulevard along x, rows z 0 / 1 / 2.
OUTER = 20700            # an outer row: painted as the SOUTH row in state 0 (= stock 11204.0's state there)
MIDDLE = 20701           # the middle row: lanes edges + median + trees
NOSE = 20702             # middle row, median ends in a nose at its +x edge (state 2: at -x)
NOSE2 = 20703            # middle row, nose at both ends (one cell between two junctions)
JUNC_N = 20710           # junction column, the outer row the crossing road enters by (state 0: north row)
JUNC_M = 20711           # junction column, middle row
JUNC_F = 20712           # junction column, the far outer row of a T (state 0: south row, closed side S)
TAPER = {1: 20720, 0: 20730, 2: 20740}   # + 3 * column + row: taper cells, canonical +x end, kept row 0 / 1 / 2
AVNARROW = {(0, 1): 20750, (1, 2): 20760}   # + 3 * column + row: narrowing to an avenue (two rows go on)

TREE_PIECES = (MIDDLE, NOSE, NOSE2)
CAP = (20704, 20705, 20706)   # end column where all three roads stop, rows 0 / 1 / 2 (canonical +x end)

MIN_COLS = 3             # boulevard columns (not junction, taper or cap columns) a run needs
TAPER_COLS = 3
MIN_RUN = 4              # columns of three parallel roads a run needs at all (orchestrator ruling 2026-10-17: an
                         # exactly-3x3 full road block belongs to bigrbt, whatever its arms)


# ------------------------------------------------------------------------------------------------ the rule
def _to_real(axis, s, w):
    """axis space (s along, w across) -> real cell. axis 1 turns the canonical frame one state: row w -> x = -w"""
    return (s, w) if axis == 0 else (-w, s)


def runs(road, have_cap=True, have_taper=True):
    """road: set of real ROAD cells -> [{axis, w0, sa, sb, ok, why, want: {cell: (piece, state)}}]

    column    s with ROAD at (s, w0..w0+2); clean: no ROAD at (s, w0-1) and (s, w0+3); junction: a straight single road
              arm at (s, w0-1) and / or (s, w0+3) (the arm's next cell is road, the cells beside the arm cell are not)
    run       maximal consecutive columns; its ends: nothing beyond the last column -> cap (that column closes), one
              row going on straight -> taper to that row over the last TAPER_COLS columns, else refused
    accepted  at least MIN_COLS columns besides junction / taper / cap columns, junctions not next to an end region,
              no ROAD 8-touching the run except junction arms and the road a taper goes on into
    """
    out = []
    for axis in (0, 1):
        R = {((x, z) if axis == 0 else (z, -x)) for (x, z) in road}
        full = lambda s, w: all((s, w + k) in R for k in range(3))     # noqa: E731
        starts = sorted((s, w) for (s, w) in R if full(s, w) and not full(s - 1, w))
        for (sa, w0) in starts:
            sb = sa
            while full(sb + 1, w0):
                sb += 1
            if sb - sa + 1 < MIN_COLS:
                continue                                        # (a crossing road's own cells, a stub)
            if sb - sa + 1 < MIN_RUN:                           # an exactly-3x3 block is bigrbt's, whatever its arms
                out.append({"axis": axis, "w0": w0, "sa": sa, "sb": sb, "ok": False, "want": {}, "ends": {},
                            "why": "3-column run: a 3x3 block (bigrbt's)"})
                continue
            wide, why = BX.spans(R, sa, sb, w0)                 # task bvx: avenue / boulevard arms (bvx.py)
            kind = {}
            for s in range(sa, sb + 1):
                if s in wide:                                   # task bvx
                    kind[s] = wide[s]["kind"]
                    continue
                n, so = (s, w0 - 1) in R, (s, w0 + 3) in R
                if not n and not so:
                    kind[s] = "C"
                    continue
                arm = lambda w, d: (s, w + d) in R and (s - 1, w) not in R and (s + 1, w) not in R  # noqa: E731
                if (n and not arm(w0 - 1, -1)) or (so and not arm(w0 + 3, 1)):
                    why = why or "road beside the boulevard at column %d is not a straight single road" % s
                kind[s] = "J" + ("N" if n else "") + ("S" if so else "")
            ends, extra = {}, set()
            for e, (se, step) in enumerate(((sb, 1), (sa, -1))):
                beyond = [k for k in range(3) if (se + step, w0 + k) in R]
                if not beyond and se in wide:                   # task bvx: the run ends on an avenue / boulevard
                    sp = wide[se]
                    if not (sp["n"] and sp["s"]):
                        why = why or "end at column %d: a corner (road on one side only)" % se
                        ends[e] = ("bad", None, [])
                    else:
                        ends[e] = ("tee", None, [se - step * i for i in range(sp["jb"] - sp["ja"] + 1)])
                elif not beyond:
                    ends[e] = ("cap", None, [se])
                elif len(beyond) == 1 and (se + 2 * step, w0 + beyond[0]) in R:
                    k = beyond[0]
                    ends[e] = ("taper", k, [se - step * i for i in range(TAPER_COLS)])
                    extra.add((se + step, w0 + k))
                elif len(beyond) == 2 and beyond[1] == beyond[0] + 1 and                         all((se + 2 * step, w0 + k) in R for k in beyond):
                    ends[e] = ("avenue", tuple(beyond), [se - step * i for i in range(TAPER_COLS)])
                    extra |= {(se + step, w0 + k) for k in beyond}
                else:
                    why = why or "end at column %d: roads %s go on (not one road, not an avenue)" % (se, beyond)
                    ends[e] = ("bad", None, [])
            endcols = {c for (_, _, cs) in ends.values() for c in cs}
            normal = [s for s in range(sa, sb + 1) if s not in endcols]
            if not why and len(set(ends[0][2]) & set(ends[1][2])):
                why = "run too short for its two ends"
            if not why and sum(1 for s in normal if kind[s] == "C") < MIN_COLS:
                why = "fewer than %d boulevard columns" % MIN_COLS
            tee = {c for (typ, _, cs) in ends.values() if typ == "tee" for c in cs}       # task bvx
            if not why and any(kind[s] != "C" for s in endcols - tee):
                why = "a junction inside an end region"
            if not why and normal and (kind[normal[0]] != "C" or kind[normal[-1]] != "C"):
                why = "a junction next to an end region"
            if not why and ((ends[0][0] == "cap" and not have_cap) or (ends[0][0] == "taper" and not have_taper) or
                            (ends[1][0] == "cap" and not have_cap) or (ends[1][0] == "taper" and not have_taper)):
                why = "end pieces not declared"
            cells = {(s, w0 + k) for s in range(sa, sb + 1) for k in range(3)}
            arms = {(s, w0 - 1) for s in kind if "N" in kind[s][1:]} | {(s, w0 + 3) for s in kind if "S" in kind[s][1:]}
            if not why:
                for (s, w) in cells:
                    for ds in (-1, 0, 1):
                        for dw in (-1, 0, 1):
                            q = (s + ds, w + dw)
                            if q in R and q not in cells and q not in arms and q not in extra:
                                why = why or "touches road at %s" % (_to_real(axis, *q),)
            want = {}
            if not why:
                def put(s, row, piece, st):
                    want[_to_real(axis, s, w0 + row)] = (piece, (st + axis) & 3)
                for e, (typ, k, cs) in ends.items():
                    if typ == "tee":                            # task bvx: its box comes with the spans below
                        continue
                    if typ == "cap":
                        for row in range(3):
                            put(cs[0], row if e == 0 else 2 - row, CAP[row], 0 if e == 0 else 2)
                    else:
                        if typ == "avenue":
                            base = AVNARROW[k if e == 0 else (2 - k[1], 2 - k[0])]
                        else:
                            base = TAPER[k if e == 0 else 2 - k]
                        for col in range(TAPER_COLS):
                            for row in range(3):
                                s = cs[-1] + col if e == 0 else cs[-1] - col
                                put(s, row if e == 0 else 2 - row, base + 3 * col + row, 0 if e == 0 else 2)
                for s in normal:
                    if kind[s] == "C":
                        put(s, 0, OUTER, 2)
                        put(s, 2, OUTER, 0)
                        nosed = {c for (typ, _, cs) in ends.values() if typ != "avenue" for c in cs}   # the median
                        hi = s + 1 in nosed or kind.get(s + 1, "C") != "C"           # goes on into an avenue end
                        lo = s - 1 in nosed or kind.get(s - 1, "C") != "C"
                        put(s, 1, NOSE2 if hi and lo else NOSE if hi or lo else MIDDLE, 2 if lo and not hi else 0)
                    elif s in wide:                             # task bvx: the box, below
                        continue
                    else:
                        j = kind[s][1:]
                        if j == "N":
                            put(s, 0, JUNC_N, 0); put(s, 1, JUNC_M, 0); put(s, 2, JUNC_F, 0)        # noqa: E702
                        elif j == "S":
                            put(s, 0, JUNC_F, 2); put(s, 1, JUNC_M, 0); put(s, 2, JUNC_N, 2)        # noqa: E702
                        else:
                            put(s, 0, JUNC_N, 0); put(s, 1, JUNC_M, 0); put(s, 2, JUNC_N, 2)        # noqa: E702
                for sp in {id(v): v for v in wide.values()}.values():          # task bvx: one paved box per span
                    want.update(BX.box_want(axis, w0, sp, ends[1][0] == "tee" and sp["ja"] == sa,
                                            ends[0][0] == "tee" and sp["jb"] == sb, _to_real))
            out.append({"axis": axis, "w0": w0, "sa": sa, "sb": sb, "ok": not why, "why": why, "want": want,
                        "ends": ends})
    return out


def pieces():
    """id -> (scene, cell, art 'from', trees, note)"""
    from netmod import boulevard_paint as P
    out = {
        OUTER: (P.Boulevard(), (0, 2), 29, False, "outer row (south row, state 0)"),
        MIDDLE: (P.Boulevard(), (0, 1), 11204, True, "middle row: extra lanes + median + trees"),
        NOSE: (P.Boulevard(nose_hi=1.0), (0, 1), 11204, True, "middle row, median nose at +x"),
        NOSE2: (P.Boulevard(nose_lo=0.0, nose_hi=1.0), (0, 1), 11204, True, "middle row, noses at both ends"),
        JUNC_N: (P.Junction("N"), (0, 0), 43, False, "junction, entry row (north row, state 0)"),
        JUNC_M: (P.Junction("M"), (0, 1), 43, False, "junction, middle row"),
        JUNC_F: (P.Junction("F"), (0, 2), 39, False, "junction, far row of a T (south row, state 0)"),
    }
    for row in range(3):
        out[CAP[row]] = (P.Cap(), (0, row), 11203, False, "end cap (all three stop), row %d" % row)
    for keep, base in AVNARROW.items():
        sc = P.AvenueNarrow(keep)
        for col in range(3):
            for row in range(3):
                spots = sc.tree_spots((col, row))
                out[base + 3 * col + row] = (sc, (col, row), 11204 if spots else 11203, spots or False,
                                             "narrowing to the avenue on rows %d, %d, column %d, row %d" % (keep + (col, row)))
    for keep, base in TAPER.items():
        sc = P.Taper(keep)
        for col in range(3):
            for row in range(3):
                out[base + 3 * col + row] = (sc, (col, row), 11203, False,
                                             "taper to row %d, column %d, row %d" % (keep, col, row))
    return out


def cmd_build(a):
    from netmod import netart
    from netmod import boulevard_paint as P
    only = set(int(v) for v in a.only.split(",")) if a.only else None
    zooms = [int(v) for v in a.zooms.split(",")] if a.zooms else list(range(netart.ZOOMS))
    for vid, (scene, cell, src, trees, note) in sorted(pieces().items()):
        if only and vid not in only:
            continue
        d = os.path.join(a.pack, "art", str(vid))
        anc = P.paint_cell(scene, cell, d, zooms=zooms)
        if trees:
            for z in zooms:
                for s in range(netart.ROTS):
                    spots = list(P.MEDIAN_TREES) if trees is True else list(trees)
                    im, ac = P.tree_layer(z, s, spots)
                    im.save(os.path.join(d, netart.frame_name(z, s, 1)))
                    anc[netart.frame_name(z, s, 1)] = list(ac)
        anc["_"] = "boulevard.py build: %s" % note
        json.dump(anc, open(os.path.join(d, "anchors.json"), "w"), indent=1)
        print("built %d (%s)" % (vid, note))
    write_manifest(a.pack)


BASE = {OUTER: 11204, MIDDLE: 29, NOSE: 29, NOSE2: 29}
FULL_LANES = os.environ.get("BV_FULL_LANES") == "1"          # junction, cap and taper pieces: 43


def lane_spec(vid):
    """lanekit authoring spec (state-0 record) of a piece: OUTER = 29's lanes and its outer (south) walk; the middle
    pieces = one lane along each carriageway (zl 14 going -x beside the north row's x+ -> x- lane, zl 241 going +x);
    cap and taper pieces = 29's lanes (cosmetic: traffic uses the road grid). Junction pieces keep 43's (copy_base)."""
    from netmod.diagave import _describe
    sp = _describe(29, 0)
    sp["piece"] = vid
    sp["states"] = [0, 1, 2, 3]
    sp["_"] = "boulevard.py: lanes of piece %d" % vid
    if vid == OUTER:
        sp["pedestrian"]["walks"] = [w for w in sp["pedestrian"]["walks"] if w["from"][1] > 128]
        sp["pedestrian"]["exits"] = [e for e in sp["pedestrian"]["exits"] if e["at"][1] > 128]
    elif vid in (MIDDLE, NOSE, NOSE2):
        for ln in sp["vehicle"]["lanes"]:
            zl = 14 if ln["from"][0] == 255 else 241
            ln["from"][1] = ln["to"][1] = zl
        for e in sp["vehicle"]["exits"]:
            e["at"][1] = 14 if e["at"][0] == 0 else 241
        sp["pedestrian"] = {"walks": [], "exits": []}
    sp["connects"] = {"road": [["x-", "x+"], ["x+", "x-"]]}
    return sp


def write_manifest(pack):
    """manifest.json + *.lanes.json of the package"""
    ps = pieces()
    variants, lanes = [], []
    for vid in sorted(ps):
        _scene, _cell, src, _trees, note = ps[vid]
        # TrBlkAtt's reserved index has 161 free slots per language for ALL installed packages (a lane spec costs
        # one per state, copy_base one per base record). A piece without a record for its state gets road 29's
        # straight lanes (NET_LANES.md section 3), which is what the outer, cap, taper and narrowing pieces carry
        # anyway: only the middle pieces (lanes beside the carriageways) and the outer piece (pedestrians on its outer
        # sidewalk only: the inner one is a lane) have specs; junctions copy 43's one record. FULL_LANES (env
        # BV_FULL_LANES=1) writes a spec for every non-junction piece: the index-growth test of 2026-10-17.
        own = vid in (OUTER, MIDDLE, NOSE, NOSE2) or FULL_LANES
        variants.append({"id": vid, "base": BASE.get(vid, 43), "network": "ROAD",
                         "name": {"*": "Boulevard", "ENGLISH": "Bulevar"},
                         "art": {"from": src, "png_dir": "art/%d" % vid},
                         "trblkatt": "copy_base" if vid in (JUNC_N, JUNC_M, JUNC_F) else "none"})
        if own and vid in (JUNC_N, JUNC_M, JUNC_F):
            own = False
        if own:
            fn = "bv_%d.lanes.json" % vid
            json.dump(lane_spec(vid), open(os.path.join(pack, fn), "w", newline="\n"), indent=1)
            lanes.append({"piece": vid, "spec": fn})
    man = {"netpack": 1, "name": "boulevard", "version": "0.2.0", "author": "netmod (task boulevard)",
           "description": "Boulevards: draw three parallel straight roads side by side (at least three columns) and "
                          "sc3netmod's BV block makes them one boulevard. The outer roads are the carriageways (stock "
                          "road look, yellow centre line), the middle road gives each one an extra lane and holds a "
                          "grass median with avenue 11204's trees, about twice as wide as the stock avenue's. Single "
                          "straight roads crossing it or meeting it from one side get junctions with crosswalks (the "
                          "median ends in a nose); where all three roads stop the end column closes it with a round "
                          "curb; where only one goes on, the boulevard tapers into it over its last three columns; where two "
                          "neighbouring roads go on, it narrows back into the stock avenue. Lane lines are white dashes. "
                          "Built by `boulevard.py build .` in this folder before install (art/ is made from the game's "
                          "frames and is not shipped).",
           "game": {"Apps/SIMNTWRK.DLL": "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"},
           "variants": variants, "lanes": lanes,
           "auto_boulevards": [{"pieces": {"outer": OUTER, "middle": MIDDLE, "nose": NOSE, "nose2": NOSE2,
                                           "junction_entry": JUNC_N, "junction_middle": JUNC_M,
                                           "junction_far": JUNC_F},
                                "cap": list(CAP),
                                "taper": {str(k): [TAPER[k] + i for i in range(9)] for k in (0, 1, 2)},
                                "avenue_narrow": {str(k[0]): [AVNARROW[k] + i for i in range(9)] for k in AVNARROW}}]}
    json.dump(man, open(os.path.join(pack, "manifest.json"), "w", newline="\n"), indent=1)
    print("manifest: %d variants, %d lane specs" % (len(variants), len(lanes)))


# ------------------------------------------------------------------------------------------------ preview

def load_layers(d):
    """png_dir -> {(layer, z, r): (image, anchor)}"""
    from PIL import Image
    from netmod import netart
    anc = {}
    p = os.path.join(d, "anchors.json")
    if os.path.isfile(p):
        anc = {k: tuple(v) for k, v in json.load(open(p)).items() if not k.startswith("_")}
    out = {}
    for layer in (0, 1):
        for z in range(netart.ZOOMS):
            for r in range(netart.ROTS):
                n = netart.frame_name(z, r, layer)
                f = os.path.join(d, n)
                if os.path.isfile(f):
                    out[(layer, z, r)] = (Image.open(f).convert("RGBA"), anc.get(n))
    return out


def render(cells, z, r, pad=8, bg=(54, 88, 54, 255)):
    """cells: [{"x", "z", "piece" | "dir", "state"}] in world cells -> image (layer 0 of every cell, then layer 1)"""
    from PIL import Image
    from netmod import netart
    srcs = {}

    def frames(c):
        k = c.get("dir") or c["piece"]
        if k not in srcs:
            if "dir" in c:
                srcs[k] = load_layers(c["dir"])
            else:
                srcs[k] = {(0, zz, rr): v for (zz, rr), v in netart.stock_frames(c["piece"]).items()}
                srcs[k].update({(1, zz, rr): v for (zz, rr), v in netart.stock_frames(c["piece"], 1).items()})
        return srcs[k]

    us = [-c["x"] for c in cells]
    vs = [c["z"] for c in cells]
    cu, cv = (min(us) + max(us) + 1) / 2.0, (min(vs) + max(vs) + 1) / 2.0
    W = netart.TILE_W[z]
    placed = []
    for c in cells:
        du, dv = netart._rot_vec(-c["x"] + 0.5 - cu, c["z"] + 0.5 - cv, r)
        placed.append((cu + du - 0.5, cv + dv - 0.5, c, (c.get("state", 0) + r) % 4))
    placed.sort(key=lambda p: (p[1] - p[0], p[0] + p[1]))
    n = max(max(us) - min(us), max(vs) - min(vs)) + 3
    w = h = int(n * W + 2 * pad)
    img = Image.new("RGBA", (w, h), bg)
    ox, oy = pad, h // 2
    for layer in (0, 1):
        for u2, v2, c, s in placed:
            fr = frames(c)
            if (layer, z, s) not in fr:
                continue
            im, a = fr[(layer, z, s)]
            X, Y = netart.project(z, u2 - min(us) + 1, v2 - min(vs) + 1)
            img.alpha_composite(im, (int(round(ox + X - a[0])), int(round(oy + Y - a[1] - W / 2))))
    bb = netart._content_box(img, bg)
    if bb:
        img = img.crop((max(0, bb[0] - pad), max(0, bb[1] - pad), min(w, bb[2] + pad), min(h, bb[3] + pad)))
    return img


def art(pack, vid):
    return os.path.join(pack, "art", str(vid))


def layout_mockup(pack):
    """single road (row 0) | taper to row 0 (-x end) | boulevard | crossing road | boulevard | T from the north |
    boulevard | taper to the middle row | single road (row 1)"""
    cells = []

    def put(x, z, vid, state):
        cells.append({"x": x, "z": z, "dir": art(pack, vid), "state": state})

    def stock(x, z, pid, state):
        cells.append({"x": x, "z": z, "piece": pid, "state": state})

    for x in range(-3, 0):
        stock(x, 0, 29, 0)
    for col in range(3):                         # taper at the -x end: canonical keep 2 turned half a circle
        for row in range(3):
            put(2 - col, 2 - row, TAPER[2] + 3 * col + row, 2)
    def straight(x, nose=None):
        put(x, 0, OUTER, 2)
        put(x, 2, OUTER, 0)
        if nose == "both":
            put(x, 1, NOSE2, 0)
        elif nose == "hi":
            put(x, 1, NOSE, 0)
        elif nose == "lo":
            put(x, 1, NOSE, 2)
        else:
            put(x, 1, MIDDLE, 0)
    straight(3, "lo")
    straight(4)
    straight(5, "hi")
    for z in range(-3, 0):                      # the crossing road along z at x 6
        stock(6, z, 29, 1)
    for z in range(3, 6):
        stock(6, z, 29, 1)
    put(6, 0, JUNC_N, 0)
    put(6, 1, JUNC_M, 0)
    put(6, 2, JUNC_N, 2)
    straight(7, "lo")
    straight(8, "hi")
    for z in range(-3, 0):                      # a T from the north at x 9
        stock(9, z, 29, 1)
    put(9, 0, JUNC_N, 0)
    put(9, 1, JUNC_M, 0)
    put(9, 2, JUNC_F, 0)
    straight(10, "lo")
    straight(11, "hi")
    for col in range(3):
        for row in range(3):
            put(12 + col, row, TAPER[1] + 3 * col + row, 0)
    for x in range(15, 18):
        stock(x, 1, 29, 0)
    return cells


def layout_from_roads(pack, road):
    """the rule's pieces on a road set; other road cells: an avenue pair as stock 11204 (2 north, 0 south), a lone
    road as 29 along its run"""
    cells, done = [], set()
    for r in runs(road):
        if r["ok"]:
            for (x, z), (pid, st) in r["want"].items():
                cells.append({"x": x, "z": z, "dir": art(pack, pid), "state": st})
                done.add((x, z))
    for (x, z) in road - done:
        if (x, z + 1) in road and (x, z + 1) not in done and ((x - 1, z) in road or (x + 1, z) in road):
            cells.append({"x": x, "z": z, "piece": 11204, "state": 2})
        elif (x, z - 1) in road and (x, z - 1) not in done and ((x - 1, z) in road or (x + 1, z) in road):
            cells.append({"x": x, "z": z, "piece": 11204, "state": 0})
        else:
            cells.append({"x": x, "z": z, "piece": 29, "state": 0 if ((x - 1, z) in road or (x + 1, z) in road) else 1})
    return cells


def layout_avenue(pack):
    """avenue (rows 0, 1) | narrowing | boulevard | crossing | boulevard | narrowing | avenue (rows 1, 2)"""
    road = {(x, z) for x in range(0, 13) for z in range(3)} | {(x, z) for x in range(-3, 0) for z in (0, 1)} |            {(x, z) for x in range(13, 16) for z in (1, 2)} | {(6, z) for z in range(-2, 5)}
    return layout_from_roads(pack, road)


LAYOUTS = {"mockup": layout_mockup, "avenue": layout_avenue}


def road_of_save(save):
    """ROAD cells of a save (stock road pieces and this package's ids; saves hold the base ids)"""
    from netmod.diagave import road_cells
    _lay, road = road_cells(save)
    return road


def cmd_plan(a):
    """runs of a save and the pieces the rule wants (read-only)"""
    for r in runs(road_of_save(a.save)):
        if not r["ok"] and r["sb"] - r["sa"] + 1 < 2 * MIN_COLS:
            continue
        print("run axis %d row %d columns %d..%d: %s %s" % (r["axis"], r["w0"], r["sa"], r["sb"],
                                                         "converts" if r["ok"] else r["why"],
                                                         {e: v[:2] for e, v in r["ends"].items()}))
        for c in sorted(r["want"], key=lambda c: (c[1], c[0])):
            print("  (%d,%d) %d.%d" % (c[0], c[1], *r["want"][c]))


def cmd_preview(a):
    cells = LAYOUTS[a.layout](a.pack)
    render(cells, a.zoom, a.rot).convert("RGB").save(a.out)
    print(a.out)


def layout_stock():
    """the same straight stretch and crossing as the stock tiler places it (tiler.py, 2026-10-17): 11204 / 29 / 11204,
    the crossing a patch of 39 / 43"""
    cells = []
    for x in range(3, 10):
        col = {5: ((39, 3), (43, 0), (39, 1)), 6: ((43, 0), (43, 0), (43, 0)), 7: ((39, 3), (43, 0), (39, 1))}.get(
            x, ((11204, 2), (29, 0), (11204, 0)))
        for z, (pid, st) in enumerate(col):
            cells.append({"x": x, "z": z, "piece": pid, "state": st})
    for z in (-2, -1, 3, 4):
        cells.append({"x": 6, "z": z, "piece": 29, "state": 1})
    return cells


def cmd_mockup(a):
    from PIL import Image, ImageDraw
    cells = LAYOUTS["mockup"](a.pack)
    shots = [("boulevard, zoom %d, view %d" % (z, r), render(cells, z, r)) for z in (4, 3) for r in (0, 1)]
    av = LAYOUTS["avenue"](a.pack)
    shots += [("narrowing to an avenue at both ends, zoom %d, view %d" % (z, r), render(av, z, r)) for z, r in ((4, 0), (3, 1))]
    shots.append(("stock today (three parallel roads + a crossing), zoom 3, view 0", render(layout_stock(), 3, 0)))
    W = max(im.width for _, im in shots)
    H = sum(im.height + 24 for _, im in shots)
    sheet = Image.new("RGB", (W, H), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    y = 0
    for title, im in shots:
        d.text((6, y + 5), title, fill=(230, 230, 230))
        sheet.paste(im.convert("RGB"), (0, y + 24))
        y += im.height + 24
    sheet.save(a.out)
    print(a.out, sheet.size)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("build")
    s.add_argument("pack")
    s.add_argument("--only")
    s.add_argument("--zooms")
    s = sub.add_parser("preview")
    s.add_argument("out")
    s.add_argument("pack")
    s.add_argument("--layout", default="mockup")
    s.add_argument("--zoom", type=int, default=4)
    s.add_argument("--rot", type=int, default=0)
    s = sub.add_parser("plan")
    s.add_argument("save")
    s = sub.add_parser("mockup")
    s.add_argument("out")
    s.add_argument("pack")
    a = ap.parse_args(argv)
    {"build": cmd_build, "preview": cmd_preview, "mockup": cmd_mockup, "plan": cmd_plan}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
