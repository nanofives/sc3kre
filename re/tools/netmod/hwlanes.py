#!/usr/bin/env python3
r"""hwlanes.py - highway lanes and turn matrices for the highway program's pieces (task hwcore, 2026-10-18).

Shared by every highway-program stream: copy it verbatim, ask hwcore for changes. Lane facts: NET_LANES.md.

What a highway piece needs (NET_LANES.md 1-3):
  * the TURN MATRIX (exemplar prop 310, low half = ENGLISH lanes, high half = its transpose): the SimTransit router
    reads it for every highway node; a highway piece whose matrix lacks a turn blocks highway trips that way
    (NET_LANES.md 8, arm H). lanekit's "connects": "auto" derives it from the lanes.
  * LANES (TrBlkAtt, one record per state, every language): the animated cars. A lane is one edge from an entry node
    on one side to an exit node on another side, following a CURVE (VPATHATT record, by key). The street sim links a
    piece only if every curve key exists, and finds the next cell's entry node by POSITION (72-unit buckets), so lanes
    of neighbouring pieces must meet at the same border point (x or z exactly 0 / 255) and height.

Measured on the stock highway records (`hwlanes.py stock`):
  * lane units: x = (world x - X) * 255, z = (world z - Z) * 255 (the art's lane frame, hwpaint, scaled so a border is
    exactly 0 / 255 and a mirrored lane lands at 255 - x as in the stock records: 73.0 at 61 / 145, 73.2 at 194 / 110);
  * node height y = 32 x hwpaint height e (y_of snaps to the stock multiples of 256): stock deck 1024 (H 31.75), X
    lower deck 512 (H_LOW 16), upper 1536 / 1792 (H_HIGH 47.5 / 55.5), ramps 512 / 768 on the slope pieces;
  * a carriageway cell (73.0) drives +z on two lanes at x 61 and 145 (0.761 and 0.431 of the width from the outer
    parapet), speed 110,000; the one-lane ramps (15123..15141) speed 74,999 / 65,000;
  * curves: "BIN\r", u32 n, n x (s32 x, y, z), u8 entry heading, u8 exit heading, u32 extra (2 on 508 of 556
    elevated curves); headings = the direction of travel at each end as a side code (-x 0, -z 8, +x 16, +z 24); key =
    shape * 256 + rotation, rotation r = the points turned r times ((x, z) -> (255 - z, x), headings + 8);
    English-UK ships its own VPathAtt.IXF where each curve has the SAME key, points reversed, both headings + 16.
    The stock set has fixed shapes only (908 curves, shapes up to 20002), so arcs of new radii need NEW curves.

New curves: a lane spec may carry "curves": [{"shape": S, "pts": [[x, y, z], ...]}] (state-0 frame); hwlanes writes
the four rotations (keys S*256 + r) into every language folder's VPathAtt.IXF (English-UK: the reversed copies)
(netpack_lanes calls inject() / curve_records()). Shape numbers: your stream's range in the protocol's section 5 table
(CHILD_PROTOCOL_2026-10-18_highways.md, "Lane curve shape numbers": hwcore 21100..21119 + 23300..23399, hwdx
22000..22499, hwx 22500..22799, hwt 22800..22999, hwdd 23000..23299), all clear of the stock shapes (up to 20002).

API:
    deck_lanes(deck) -> [(t, speed)]                  lane offsets of a hwpaint Deck (left of travel, cells)
    cell_runs(path, cell, t=0.0, height=H) -> [[[x, y, z], ...], ...]   a lane through one cell, lane units
    build_cells(decks, cells, shape0, piece_of) -> ({cell: spec}, next_shape)   lanekit specs for each cell's piece:
        every lane of every deck, cut per cell, one new curve per cut, "connects": {"road": "auto"}
    y_of(e)                                           node height of a hwpaint height
CLI:
    py -3.12 hwlanes.py stock                         the stock highway / ramp lanes and curves this note quotes
    py -3.12 hwlanes.py demo <out_dir>                specs for hwpaint's loop / bridge demo scenes, compiled with lanekit
    py -3.12 hwlanes.py core <package_dir>            lane specs of the proof pieces 21100 / 21101 (examples/highway_core)
"""
import argparse
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", ".."))

from netmod import lanekit as LK  # noqa: E402

Y_PER_E = 32.0                      # node y per hwpaint height unit (1024 / 32 = the stock deck)
EXTRA = 2                           # the curve record's trailing u32 (the path SORT ID) on the deck; see extra_for
HW_SPEED = 110000                   # stock 73 / 15051 lanes
RAMP_SPEED = 74999                  # stock one-lane ramp corners 15123..15133
HW_LANES = (1 - 145 / 255.0, 1 - 61 / 255.0)   # 73.0's lanes (x 145, 61) as shares of the width from its outer parapet
DIAG_LANES = (0.396, 0.170)         # stock diagonal band lanes (11224 / 11223, 15106 / 15052), cells from the median
MAX_PTS = 9                         # stock curves carry 2..9 points


def y_of(e):
    """node height of a hwpaint height: 32 per unit, snapped to the stock levels (multiples of 256) within 24, so a
    deck at H (31.75) meets stock 73's nodes at 1024"""
    y = float(e) * Y_PER_E
    k = round(y / 256.0) * 256.0
    return int(k if abs(y - k) <= 24 else round(y))


# ------------------------------------------------------------------------------------------------ curves

def heading(dx, dz):
    """direction of travel -> side code (-x 0, -z 8, +x 16, +z 24)"""
    if abs(dx) >= abs(dz):
        return 0 if dx < 0 else 16
    return 8 if dz < 0 else 24


def _rot(pts, r):
    out = []
    for x, y, z in pts:
        for _ in range(r % 4):
            x, z = 255 - z, x
        out.append([x, y, z])
    return out


def extra_for(pts):
    """The curve record's trailing u32, by height as stock (task avcore 2026-10-19): 0 when every point is at y 0, else
    EXTRA (2). It is the path's sort id [UNCERTAIN as a hang cause]: STRTSIM SerialReadBinary 0x1001e673 stores it at
    +0x34 (file value + 1; Linux accessor SortId), and a car whose sort id changes sends it to the anim occupant manager
    (0x1001b030 / 0x10018820 / 0x1001bc70, property 0x80). Stock: all 192 flat ground curves 0, all 408 deck curves 2.
    Ramps and mixed heights stay 2 until measured (stock mixes 0 / 1 / 2 there)."""
    return 0 if all(int(p[1]) == 0 for p in pts) else EXTRA


def _payload(pts, hin, hout, extra=None):
    if extra is None:
        extra = extra_for(pts)
    return (b"BIN\r" + struct.pack("<I", len(pts)) + b"".join(struct.pack("<iii", *p) for p in pts) +
            bytes([hin & 0xff, hout & 0xff]) + struct.pack("<I", extra))


def curve_set(shape, pts):
    """-> {"en": {key: (pts, in, out)}, "uk": {...}}: the four rotations of a state-0 curve, and English-UK's copy"""
    en, uk = {}, {}
    for r in range(4):
        p = _rot(pts, r)
        hin = heading(p[1][0] - p[0][0], p[1][2] - p[0][2])
        hout = heading(p[-1][0] - p[-2][0], p[-1][2] - p[-2][2])
        key = shape * 256 + r
        en[key] = (p, hin, hout)
        uk[key] = (p[::-1], (hin + 16) % 32, (hout + 16) % 32)
    return {"en": en, "uk": uk}


def _uk(lang):
    return lang in LK.MIRROR_LANGS


def spec_curves(spec):
    out = {}
    for c in spec.get("curves", []):
        s = int(c["shape"])
        if not 20003 <= s <= 0xFFFFFF:
            raise LK.LaneError("curve shape %d: use your stream's shape range (protocol section 5; stock reaches 20002)" % s)
        out[s] = [[int(v) for v in p] for p in c["pts"]]
    return out


def inject(game, spec):
    """make a spec's new curves visible to lanekit (every language's curve library of `game`) -> {shape: pts}"""
    cs = spec_curves(spec)
    for lang in game.langs():
        P = game.paths(lang)
        for s, pts in cs.items():
            for key, (p, hin, hout) in curve_set(s, pts)["uk" if _uk(lang) else "en"].items():
                old = P.veh.get(key)
                new = {"pts": [tuple(v) for v in p], "in": hin, "out": hout, "extra": extra_for(p)}
                if old is not None and (old["pts"], old["in"], old["out"]) != (new["pts"], hin, hout):
                    raise LK.LaneError("curve key %d is already taken by another curve" % key)
                P.veh[key] = new
    return cs


def curve_records(shapes):
    """{shape: pts} -> {"en": [(group, key, type, payload)], "uk": [...]} for VPATHATT.IXF / English-UK VPathAtt.IXF"""
    out = {"en": [], "uk": []}
    for s, pts in sorted(shapes.items()):
        for kind, d in curve_set(s, pts).items():
            for key, (p, hin, hout) in sorted(d.items()):
                out[kind].append((LK.VPA_GROUP, key, LK.VPA_TYPE, _payload(p, hin, hout)))
    return out


def vpath_rels(stock):
    """-> {rel: "en" | "uk"}: every language folder's VPathAtt.IXF (each folder carries one; English-UK's runs the
    curves backwards), case as on disk. `stock` = netpack's Stock (root + listdir)."""
    out = {}
    base = os.path.join(stock.root, "Apps", "Res", "SSimData")
    for lang in sorted(os.listdir(base)):
        if not os.path.isdir(os.path.join(base, lang)):
            continue
        for n in stock.listdir("Apps/Res/SSimData/" + lang):
            if n.lower() == "vpathatt.ixf":
                out["Apps/Res/SSimData/%s/%s" % (lang, n)] = "uk" if _uk(lang) else "en"
    return out


# ------------------------------------------------------------------------------------------------ lanes from hwpaint decks

def driven(deck):
    """-> (path, height function) in the direction cars drive on a deck: traffic keeps right, so the outer parapet is
    on the driver's right (stock 73.0 drives +z with its parapet on +x): along the path for outer "right", against
    it for outer "left". Draw a ramp's path in its direction of travel with outer "right"."""
    if deck.outer == "right":
        return deck.path, deck.h
    L = deck.path.length
    return deck.path.reversed(), (lambda s, h=deck.h: h(L - __import__("numpy").asarray(s, dtype=float)))


def deck_lanes(deck):
    """-> [(t, speed)]: lane offsets (cells, left of the direction of travel of driven(deck)) of a hwpaint Deck: a "hw"
    carriageway has 73's two lanes (a W_DIAG-wide one, from highway_diag, the stock diagonal band's: 0.396 and 0.170
    from the median, so its border points meet stock 11223 / 11224 / 15052 / 15106 cells), a "ramp" one lane in the
    middle of its width"""
    from netmod import hwpaint as HP
    if deck.profile == "hw" and abs(deck.w - HP.W_DIAG) < 1e-6:     # a highway_diag carriageway: the stock band's lanes
        tos, sp = [deck.w - m for m in DIAG_LANES], HW_SPEED
    elif deck.profile == "hw":
        tos, sp = [f * deck.w for f in HW_LANES], HW_SPEED
    else:
        tos, sp = [deck.w / 2.0], RAMP_SPEED
    return [(to - deck.w / 2.0, sp) for to in tos]


def _lane_pt(path, s, t):
    p, d = path.at(s)
    return p[0] - d[1] * t, p[1] + d[0] * t


def _inside(p, X, Z):
    return X <= p[0] <= X + 1 and Z <= p[1] <= Z + 1


def _to_lane(p, X, Z):
    def q(v):                                            # 255 per cell: stock lanes mirror as 255 - x (61 / 194)
        return int(min(255, max(0, round(v * 255.0))))
    return q(p[0] - X), q(p[1] - Z)


def cell_runs(path, cell, t=0.0, height=None, step=1.0 / 256.0):
    """the lane `t` cells left of `path` inside `cell`: each pass through the cell as [[x, y, z], ...] (lane units, the
    end points exactly on the border, at most MAX_PTS points); y from `height` (hwpaint height function of s or a
    number, default the stock deck)"""
    import numpy as np
    from netmod import hwpaint as HP
    X, Z = cell
    h = HP._hfun(HP.H if height is None else height)
    n = max(2, int(path.length / step) + 1)
    ss = [path.length * k / (n - 1) for k in range(n)]
    ins = [_inside(_lane_pt(path, s, t), X, Z) for s in ss]
    runs = []
    k = 0
    while k < n:
        if not ins[k]:
            k += 1
            continue
        a = k
        while k < n and ins[k]:
            k += 1
        b = k - 1

        def edge(s_in, s_out):
            for _ in range(30):
                m = (s_in + s_out) / 2.0
                if _inside(_lane_pt(path, m, t), X, Z):
                    s_in = m
                else:
                    s_out = m
            return s_in
        s0 = edge(ss[a], ss[a - 1]) if a > 0 else ss[a]
        s1 = edge(ss[b], ss[b + 1]) if b < n - 1 else ss[b]
        if s1 - s0 < 1e-3:
            continue
        m = min(MAX_PTS, max(2, int((s1 - s0) * 8) + 2))
        pts = []
        for j in range(m):
            s = s0 + (s1 - s0) * j / (m - 1)
            x, z = _to_lane(_lane_pt(path, s, t), X, Z)
            y = y_of(float(np.asarray(h(np.array([s])))[0]))
            pts.append([x, y, z])
        for end in (0, -1):                              # a border end point exactly on one side (not a corner)
            x, y, z = pts[end]
            if x in (0, 255) and z in (0, 255):
                pts[end][2] = min(254, max(1, z))
        pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
        if len(pts) >= 2:
            runs.append(pts)
    return runs


def build_cells(decks, cells, shape0, piece_of, states=(0,)):
    """lanekit specs (state-0 frame) for the pieces of `cells`: every lane of every deck cut per cell, one new curve
    per cut (shapes from shape0 up), connects auto. piece_of: {cell: piece id}. -> ({cell: spec}, next free shape)"""
    specs = {}
    shape = shape0
    for c in cells:
        lanes, curves = [], []
        for d in decks:
            dpath, dh = driven(d)
            for t, sp in deck_lanes(d):
                for run in cell_runs(dpath, c, t, dh):
                    a, b = run[0], run[-1]
                    if len(LK.boundary_sides(a[0], a[2])) != 1 or len(LK.boundary_sides(b[0], b[2])) != 1:
                        continue                         # starts or ends inside the cell: no lane (cars would strand)
                    curves.append({"shape": shape, "pts": run})
                    lanes.append({"from": a, "to": b, "path": shape * 256, "speed": sp})
                    shape += 1
        if lanes:
            specs[tuple(c)] = {"piece": piece_of[tuple(c)], "states": list(states), "flag": 0,
                               "vehicle": {"class": "car", "speed": HW_SPEED, "lanes": lanes},
                               "connects": {"road": "auto"}, "curves": curves}
    return specs, shape


def compile_check(spec, root=None):
    """compile a spec with lanekit in every language (new curves injected) -> (masks, warnings)"""
    g = LK.Game(root)
    inject(g, spec)
    warns, masks = [], None
    for lang in g.langs():
        c = LK.compile_spec(spec, g, lang)
        warns += ["%s: %s" % (lang, w) for w in c["warnings"]]
        masks = masks or c["masks"]
    return masks, warns


# ------------------------------------------------------------------------------------------------ CLI

def cmd_stock(a):
    g = LK.Game(a.root)
    P = g.paths()
    trb = g.trblkatt()
    for pid in (73, 15051, 15099, 15107, 15113, 15150, 15119, 15120, 15123, 15127, 15130, 15134, 15138, 11224, 15106):
        m = (g.masks(pid) or {}).get("road", 0)
        sts = sorted(k & 0xff for k in trb if k >> 8 == pid)
        spec, _ = LK.describe(LK.decode(trb[pid * 256 + sts[0]]), P, pid, exact=False)
        print("%d states %s matrix low %s" % (pid, sts, [(LK.SIDES[x], LK.SIDES[y]) for x, y in LK.mask_turns(m & 0xffff)]))
        for ln in spec.get("vehicle", {}).get("lanes", []):
            p = P.veh.get(ln.get("path"), {})
            print("    %s -> %s curve %s (%d pts, in %s out %s) speed %s" % (
                ln["from"], ln["to"], ln.get("path"), len(p.get("pts", [])), p.get("in"), p.get("out"),
                spec["vehicle"].get("speed")))


def cmd_core(a):
    """lane specs of hwcore's proof pieces 21100 / 21101 (examples/highway_core), curve shapes 21100.."""
    from netmod import hwpaint as HP
    shape = 21100
    for pid, sc in HP.core_scenes().items():
        specs, shape = build_cells(sc.decks, [(0, 0)], shape, {(0, 0): pid}, states=(0, 1, 2, 3))
        spec = specs[(0, 0)]
        masks, warns = compile_check(spec, a.root)
        f = os.path.join(a.pkg, "hwcore_%d.lanes.json" % pid)
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(spec, fh, indent=1)
        print(pid, f, [(LK.SIDES[x], LK.SIDES[y]) for x, y in LK.mask_turns(masks["road"] & 0xffff)], warns[:3])


def cmd_demo(a):
    from netmod import hwpaint as HP
    os.makedirs(a.out, exist_ok=True)
    shape = 23300                                        # hwcore's second shape range (protocol section 5)
    for name, sc in HP.demo_scenes().items():
        cells = HP.scene_cells(sc)
        piece_of = {c: 21100 + i for i, c in enumerate(cells)}
        specs, shape = build_cells(sc.decks, cells, shape, piece_of)
        n_ok = 0
        for c, spec in sorted(specs.items()):
            masks, warns = compile_check(spec, a.root)
            n_ok += 1
            with open(os.path.join(a.out, "%s_%d_%d.lanes.json" % (name, c[0], c[1])), "w", encoding="utf-8") as f:
                json.dump(spec, f, indent=1)
            turns = [(LK.SIDES[x], LK.SIDES[y]) for x, y in LK.mask_turns(masks.get("road", 0) & 0xffff)]
            print("%s cell %s: %d lane(s), matrix %s%s" % (name, c, len(spec["vehicle"]["lanes"]), turns,
                                                           "; " + "; ".join(warns[:2]) if warns else ""))
        print("%s: %d cell specs compiled in every language, shapes up to %d" % (name, n_ok, shape - 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=None, help="stock game root (default $SC3_GAME_ROOT / the main checkout)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stock")
    p = sub.add_parser("demo")
    p.add_argument("out")
    p = sub.add_parser("core")
    p.add_argument("pkg")
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    {"stock": cmd_stock, "demo": cmd_demo, "core": cmd_core, "selftest": cmd_selftest}[a.cmd](a)


def selftest_extra():
    """task avcore: curve_set / curve_records / inject agree on the trailing u32: a flat curve 0, a deck curve 2, both
    languages. -> list of problems"""
    bad = []
    flat = [[255, 0, 80], [128, 0, 80], [0, 0, 80]]
    deck = [[255, 1024, 80], [128, 1024, 80], [0, 1024, 80]]
    for shape, pts, want in ((0xFFFF00, flat, 0), (0xFFFF01, deck, EXTRA)):
        for kind, recs in curve_records({shape: pts}).items():
            for _g, key, _t, b in recs:
                n = struct.unpack_from("<I", b, 4)[0]
                got = struct.unpack_from("<I", b, 8 + 12 * n + 2)[0]
                if got != want:
                    bad.append("curve_records %s key %d: extra %d, want %d" % (kind, key, got, want))
        for kind, d in curve_set(shape, pts).items():
            for key, (p, _hi, _ho) in d.items():
                if extra_for(p) != want:
                    bad.append("curve_set %s key %d: extra %d, want %d" % (kind, key, extra_for(p), want))

    class _P:
        def __init__(self):
            self.veh = {}

    class _G:
        def __init__(self):
            self.p = {"ENGLISH": _P(), "English-UK": _P()}

        def langs(self):
            return list(self.p)

        def paths(self, lang):
            return self.p[lang]
    g = _G()
    inject(g, {"curves": [{"shape": 0xFFFF00, "pts": flat}, {"shape": 0xFFFF01, "pts": deck}]})
    for lang, P in g.p.items():
        for key, c in P.veh.items():
            want = 0 if key >> 8 == 0xFFFF00 else EXTRA
            if c["extra"] != want:
                bad.append("inject %s key %d: extra %d, want %d" % (lang, key, c["extra"], want))
    return bad


def cmd_selftest(a):
    bad = selftest_extra()
    print("hwlanes selftest:", "PASSED" if not bad else "FAILED")
    for b in bad:
        print("  ", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
