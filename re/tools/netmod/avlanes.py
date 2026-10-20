#!/usr/bin/env python3
r"""avlanes.py - one-way avenue halves: conventions, avcore's lane specs, edge checks (task avcore, 2026-10-19).

The contract is re/analysis/AVENUE_LANES.md. This module is its code form for every stream:

  half_dir(state)                 travel side (0 N, 1 E, 2 S, 3 W) of a one-way half whose 11204 state is `state`
  edge_nodes(state, side)         the two lane nodes a one-way half at `state` puts on `side` of its cell, as
                                  [(x, z, "in"|"out"), ...] (inner lane first); [] when that side is not along the half
  build(out_dir)                  write avcore's lane specs (avl_<id>.lanes.json) into a package folder
  check(a, sa, b, sb, side)       pieces a (state sa) and b (state sb, the cell beyond a's `side`): every lane of a that
                                  leaves across `side` meets a lane of b that enters there (same point within 8 units,
                                  same class), and the other way round; returns a list of problems ([] = clean).
                                  a / b = a piece id (its lane records as installed in the game) or a lanes.json path.

CLI (run from re/tools):
  py -3.12 -m netmod.avlanes build <package dir>
  py -3.12 -m netmod.avlanes check <piece|spec> <state> <piece|spec> <state> <side N|E|S|W>
  py -3.12 -m netmod.avlanes selftest               the avcore pieces against each other and a straight band
  py -3.12 -m netmod.avlanes corner-letters          the letters an avlj piece on a corner's outer cell must show
  py -3.12 -m netmod.avlanes tightleft <package dir> [...]
                                                    REPORT (not a gate): every car lane (ENGLISH and English-UK) whose
                                                    curve, as driven, has a left bend of radius <= 80 (by geometry)
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from netmod import lanekit as LK  # noqa: E402

TILE = 255
SIDES = "NESW"
# lanekit side codes: exit code = 8 * side index in lanekit's order x- 0, z- 1, x+ 2, z+ 3
LK_SIDE = {"W": 0, "N": 1, "E": 2, "S": 3}

PIECE_STRAIGHT = 21700        # base 11204: one-way half
PIECE_UTURN = 21701           # base 11203: avenue end quarter; also a corner's OUTER bend (the same left turn)
PIECE_CORNER = 21726          # base 11203: a corner's INNER bend (a right turn, the median lane on the wide arc)
SHAPE_INNER = 23600           # (255, 80) -> (0, 80), y 0
SHAPE_UTURN_INNER = 23602     # (0, 175) -> (80, 255) radius 80 about (0, 255)
# English-UK holds every curve reversed under the same key (lanekit MIRROR_LANGS). With right-hand lanes in every
# language, a UK lane needs a curve that runs forward in the UK file: a new shape whose ENGLISH geometry is the
# reverse gets exactly that UK copy. Lanes carry no path key: each language's library is searched by end points.
SHAPE_UTURN_OUTER_UK = 23601  # English geometry (175, 255) -> (0, 80): its UK copy is the U-turn outer lane
SHAPE_OUTER_UK = 23603        # English geometry (0, 175) -> (255, 175): its UK copy is the straight outer lane
KEY_OUTER_STRAIGHT = 256      # stock (255, 175) -> (0, 175)
KEY_UTURN_OUTER = 1024        # stock 11203 (0, 80) -> (175, 255) radius 175 about (0, 255)
TIGHT_LEFT = 80               # the report radius of tightleft
MATRIX_STRAIGHT = {"low": [["x+", "x-"]], "high": [["x-", "x+"]]}
MATRIX_UTURN = {"low": [["x-", "z+"]], "high": [["z+", "x-"]]}
MATRIX_CORNER = {"low": [["z+", "x-"]], "high": [["x-", "z+"]]}
# the 8 stock corner patterns (avcorner_scan, 169 corner ends over the 15 shipped cities): (axis 0 along z / 1 along x,
# end -1 back / +1 forward, inner bend on B) -> 11203 / 11204 states of A, B (end row) and A2, B2 (next row); the
# inner and the outer bend always share one 11203 state. Same table as sc3netmod_avl.c AVL_CST.
CORNER_PATTERNS = {(0, -1, 0): (0, 3, 2, 0), (0, -1, 1): (1, 3, 3, 2), (0, 1, 0): (1, 3, 0, 1), (0, 1, 1): (1, 2, 2, 0),
                   (1, -1, 0): (2, 0, 1, 2), (1, -1, 1): (2, 3, 3, 1), (1, 1, 0): (1, 0, 3, 1), (1, 1, 1): (2, 0, 0, 3)}


def half_dir(state):
    """AVENUE_LANES.md 1: the half's median lies on world side `state`; traffic runs toward side (state + 3) % 4."""
    return (state + 3) % 4


def _rot(x, z, k):
    for _ in range(k % 4):
        x, z = TILE - z, x
    return x, z


def edge_nodes(state, side):
    """Nodes of the one-way straight half (21700) at `state` on cell side `side` ('N', 'E', 'S', 'W'), inner first."""
    pts = [((255, 80), (0, 80)), ((255, 175), (0, 175))]          # state 0: inner, outer; entry -> exit
    out = []
    for a, b in pts:
        for p, kind in ((a, "in"), (b, "out")):
            x, z = _rot(p[0], p[1], state)
            s = "W" if x == 0 else "E" if x == TILE else "N" if z == 0 else "S" if z == TILE else None
            if s == side:
                out.append((x, z, kind))
    return out


def _line(a, b, n=9):
    return [[round(a[0] + (b[0] - a[0]) * t / (n - 1)), 0, round(a[1] + (b[1] - a[1]) * t / (n - 1))] for t in range(n)]


def _arc(cx, cz, r, a0, a1, n=9):
    out = []
    for t in range(n):
        a = math.radians(a0 + (a1 - a0) * t / (n - 1))
        out.append([round(cx + r * math.cos(a)), 0, round(cz + r * math.sin(a))])
    return out


def _stock_ped(game, piece):
    rec = LK.decode(game.trblkatt("ENGLISH")[piece * 256])
    d, _probs = LK.describe(rec, game.paths("ENGLISH"), piece=piece, exact=False)
    return d.get("pedestrian")


def specs(game=None):
    """avcore's lane specs (state-0 frame, all four states by lanekit's rotation, right-hand in every language)."""
    game = game or LK.Game()
    straight = {
        "piece": PIECE_STRAIGHT, "states": [0, 1, 2, 3], "flag": 0, "mirror_uk": False,
        "_comment": "AVENUE_LANES.md 2: one-way half, median on the N edge at state 0, traffic -x; inner lane z 80, "
                    "outer lane z 175. No path keys: each language's curve library is searched by end points "
                    "(English-UK stores every curve reversed under the same key; new curve 23600 serves the other "
                    "languages' inner lane).",
        "vehicle": {"class": "car", "speed": 64000, "lanes": [
            {"from": [255, 80], "to": [0, 80]},
            {"from": [255, 175], "to": [0, 175]}]},
        "pedestrian": _stock_ped(game, 11204),
        "connects": {"road": MATRIX_STRAIGHT},
        "curves": [{"shape": SHAPE_INNER, "pts": _line((255, 80), (0, 80))},
                   {"shape": SHAPE_OUTER_UK, "pts": _line((0, 175), (255, 175))}],
    }
    # quarter circles about (0, 255): angle measured from +x toward +z, (0, 255 - r) is angle -90
    uturn = {
        "piece": PIECE_UTURN, "states": [0, 1, 2, 3], "flag": 0, "mirror_uk": False,
        "_comment": "AVENUE_LANES.md 3: avenue end quarter, traffic enters across x- and leaves across z+ at state 0; "
                    "outer lane (0,80) -> (175,255) = stock 11203's curve 1024, inner (0,175) -> (80,255) new 23602.",
        "vehicle": {"class": "car", "speed": 48000, "lanes": [
            {"from": [0, 80], "to": [175, 255]},
            {"from": [0, 175], "to": [80, 255]}]},
        "pedestrian": _stock_ped(game, 11203),
        "connects": {"road": MATRIX_UTURN},
        "curves": [{"shape": SHAPE_UTURN_INNER, "pts": _arc(0, 255, 80, -90, 0)},
                   {"shape": SHAPE_UTURN_OUTER_UK, "pts": _arc(0, 255, 175, -90, 0)[::-1]}],
    }
    corner = {
        "piece": PIECE_CORNER, "states": [0, 1, 2, 3], "flag": 0, "mirror_uk": False,
        "_comment": "AVENUE_LANES.md 3: avenue corner, inner bend (2 x 2 block: inner and outer 11203 at one state, two "
                    "11204 halves); traffic enters across z+ and leaves across x- at state 0, a right turn: median lane "
                    "(175,255) -> (0,80) on r 175 (23601 in English, stock 1024's copy in English-UK), curb lane "
                    "(80,255) -> (0,175) on r 80 (stock 768 in English, 23602's copy in English-UK). The outer bend is 21701.",
        "vehicle": {"class": "car", "speed": 48000, "lanes": [
            {"from": [175, 255], "to": [0, 80]},
            {"from": [80, 255], "to": [0, 175]}]},
        "pedestrian": _stock_ped(game, 11203),
        "connects": {"road": MATRIX_CORNER},
        "curves": [],
    }
    return {PIECE_STRAIGHT: straight, PIECE_UTURN: uturn, PIECE_CORNER: corner}


# ----------------------------------------------------------------- crossings / slopes on a half (AVENUE_LANES.md 3)
CROSS_BASES = [69, 67, 11258, 15098, 31, 32, 11201, 11202]     # ids 21710 + 2k (toward x+ / z+), + 1 (the other way)
CROSS_ID0 = 21710
SHAPE_CROSS0 = 23604                                          # new curves for these pieces, allocated in order


def _road_lanes(d):
    """the stock road car lanes of a described spec: class car, never at the highway deck height 1024"""
    out = []
    for i, ln in enumerate(d["vehicle"]["lanes"]):
        if ln.get("class", d["vehicle"].get("class", "car")) != "car":
            continue
        a, b = LK._pty(ln["from"]), LK._pty(ln["to"])
        if a[1] == 1024 or b[1] == 1024:
            continue
        out.append(i)
    return out


def _curve_pts(P, key):
    return [list(p) for p in P.veh[key]["pts"]]


def cross_specs(game=None):
    """-> {piece: spec}, [(piece, base, side)] for every one-way crossing / slope variant, plus the new curves used"""
    game = game or LK.Game()
    from netmod import hwlanes as HL
    for sp0 in specs(game).values():                          # avcore's own curves first: reuse them
        if id(sp0) not in _CUR:
            HL.inject(game, sp0)
    P = game.paths("ENGLISH")
    specs_out, lines, shape = {}, [], SHAPE_CROSS0
    for k, base in enumerate(CROSS_BASES):
        rec = LK.decode(game.trblkatt("ENGLISH")[base * 256])
        d, _ = LK.describe(rec, P, piece=base, exact=False)
        ri = _road_lanes(d)
        road = [d["vehicle"]["lanes"][i] for i in ri]
        if len(road) != 2:
            raise SystemExit("base %d: %d road lanes, expected 2" % (base, len(road)))
        pts = [(LK._pty(ln["from"]), LK._pty(ln["to"])) for ln in road]
        axis_x = pts[0][0][0] != pts[0][1][0]                       # the lane moves along x
        pos = lambda p: p[2] if axis_x else p[0]
        # the height at each end of the road, from either stock lane: along-coordinate 0 / 255 -> y
        yat = {}
        for a, b in pts:
            for q in (a, b):
                yat[q[0] if axis_x else q[2]] = q[1]
        curves = []
        new_lanes = {}
        for fwd in (1, 0):
            lanes = []
            for slot in (80, 175):
                s0, s1 = (0, 255) if fwd else (255, 0)
                a = (s0, yat[s0], slot) if axis_x else (slot, yat[s0], s0)
                b = (s1, yat[s1], slot) if axis_x else (slot, yat[s1], s1)
                lanes.append({"from": list(a), "to": list(b), "uk_keep": True})
            new_lanes[fwd] = lanes
        # every geometry the four lanes need, in both orientations (English finds L, English-UK the reverse of L):
        need = []
        for fwd in (1, 0):
            for ln in new_lanes[fwd]:
                a, b = tuple(ln["from"]), tuple(ln["to"])
                need += [(a, b), (b, a)]
        for a, b in need:
            if P.find("veh", (a[0], a[2]), (b[0], b[2])):
                hits = [kk for kk in P.find("veh", (a[0], a[2]), (b[0], b[2]))
                        if P.veh[kk]["pts"][0][1] == a[1] and P.veh[kk]["pts"][-1][1] == b[1]]
                if hits:
                    continue
            # make it from the stock road curve at the same slot (reversed, or the other slot's moved over)
            src, skey = None, None
            for ln, (sa, sb) in zip(road, pts):
                if pos(sa) == pos(a) and ln.get("path") is not None:
                    src, skey = _curve_pts(P, ln["path"]), ln["path"]
                    if (src[0][0], src[0][2]) != (a[0], a[2]):
                        src = src[::-1]
            if src is None:
                for ln, (sa, sb) in zip(road, pts):
                    if ln.get("path") is None:
                        continue
                    c = _curve_pts(P, ln["path"])
                    dz = pos(a) - pos(sa)
                    c = [[q[0], q[1], q[2] + dz] if axis_x else [q[0] + dz, q[1], q[2]] for q in c]
                    if (c[0][0], c[0][2]) != (a[0], a[2]):
                        c = c[::-1]
                    src, skey = c, ln["path"]
                    break
            # the source stock curve's own sort id (stock slopes: 31 / 32 carry 2, 11201 / 11202 carry 0)
            curves.append({"shape": shape, "pts": [list(q) for q in src], "sort_id": P.veh[skey]["extra"]})
            HL.inject(game, {"curves": [curves[-1]]})          # findable for the next lanes, in every language
            shape += 1
        keep = [ln for i, ln in enumerate(d["vehicle"]["lanes"]) if i not in ri]
        drop = {tuple(LK._pty(road[j][e])[i] for i in (0, 2)) for j in range(2) for e in ("from", "to")}
        exits = [x for x in d["vehicle"].get("exits", []) if tuple(x["at"][:1] + x["at"][-1:]) not in drop]
        m = (game.masks(base) or {}).get("road", 0)             # the stock matrix, as lanekit describe reads it
        lo = [[LK.SIDES[a], LK.SIDES[b]] for a, b in LK.mask_turns(m & 0xFFFF)]
        hi = [[LK.SIDES[a], LK.SIDES[b]] for a, b in LK.mask_turns(m >> 16)]
        ax = ("x-", "x+") if axis_x else ("z-", "z+")
        strip = lambda m: [t for t in m if not (t[0] in ax and t[1] in ax)]
        for fwd in (1, 0):
            pid = CROSS_ID0 + 2 * k + (0 if fwd else 1)
            turn = [ax[0], ax[1]] if fwd else [ax[1], ax[0]]
            sp = {"piece": pid, "states": [0, 1, 2, 3], "flag": d["flag"], "alt": d.get("alt", [0, 0, 0, 0]),
                  "_comment": "AVENUE_LANES.md 3: base %d on a one-way half, road lanes toward %s at state 0 (both in "
                              "every language: uk_keep), the other network's lanes as stock" % (base, ax[1] if fwd else ax[0]),
                  "vehicle": {"class": d["vehicle"].get("class", "car"), "speed": d["vehicle"].get("speed", 64000),
                              "lanes": keep + new_lanes[fwd], "exits": exits},
                  "pedestrian": d.get("pedestrian"),
                  "connects": {"road": {"low": strip(lo) + [turn], "high": strip(hi) + [[turn[1], turn[0]]]}},
                  "curves": curves}
            if not exits:
                sp["vehicle"].pop("exits")
            specs_out[pid] = sp
            side = (1 if fwd else 3) if axis_x else (2 if fwd else 0)
            lines.append((pid, base, side))
    return specs_out, lines


def build(out_dir):
    out = []
    game = LK.Game()
    allspecs = dict(specs(game))
    cs, lines = cross_specs(game)
    allspecs.update(cs)
    for pid, sp in allspecs.items():
        p = os.path.join(out_dir, "avl_%d.lanes.json" % pid)
        with open(p, "w", newline="\n") as f:
            json.dump(sp, f, indent=1)
        out.append(p)
    return out


# ----------------------------------------------------------------- checks
_CUR = {}


def _records(spec_or_piece, state, game, lang="ENGLISH"):
    """-> lanekit record (dict) of a piece at a state: a spec dict / path compiled here (new curves registered in a
    private copy of the curve library), or an installed piece id's TrBlkAtt record."""
    if isinstance(spec_or_piece, int):
        blob = game.trblkatt(lang).get(spec_or_piece * 256 + state)
        if blob is None:
            raise SystemExit("piece %d has no TrBlkAtt record at state %d in %s" % (spec_or_piece, state, game.root))
        return LK.decode(blob)
    spec = spec_or_piece
    if isinstance(spec, str):
        spec = json.load(open(spec))
    sp = dict(spec, states=[0])
    if spec.get("curves") and id(spec) not in _CUR:          # make the new shapes findable (every language)
        from netmod import hwlanes as HL
        HL.inject(game, spec)
        _CUR[id(spec)] = 1
    rec0 = LK.decode(LK.compile_spec(sp, game, lang)["records"][0])
    return LK.rotate(rec0, state)


def _ends(rec, side):
    """(x, z, 'out'|'in') of every car node on `side` that exits (has an exit edge) or is entered from outside (has no
    in-edge from another node and an out-edge)."""
    s = LK_SIDE[side]
    targets = {e["to"] for n in rec["veh"] for e in n["edges"] if e["to"] is not None}
    out = []
    for i, n in enumerate(rec["veh"]):
        on = {0: n["x"] == 0, 1: n["z"] == 0, 2: n["x"] == TILE, 3: n["z"] == TILE}[s]
        if not on:
            continue
        if any(e["to"] is None and e["code"] == 8 * s for e in n["edges"]):
            out.append((n["x"], n["z"], "out"))
        elif i not in targets and any(e["to"] is not None for e in n["edges"]):
            out.append((n["x"], n["z"], "in"))
    return out


def _name(v):
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return os.path.basename(v)
    return "spec %s" % v.get("piece")


def check(a, sa, b, sb, side, game=None, lang="ENGLISH"):
    game = game or LK.Game()
    na, nb = _name(a), _name(b)
    opp = {"N": "S", "S": "N", "E": "W", "W": "E"}[side]
    ea, eb = _ends(_records(a, sa, game, lang), side), _ends(_records(b, sb, game, lang), opp)

    def across(x, z):                          # a point on a's `side` as b sees it
        return {"N": (x, TILE), "S": (x, 0), "E": (0, z), "W": (TILE, z)}[side]
    probs = []
    for x, z, k in ea:
        px, pz = across(x, z)
        want = "in" if k == "out" else "out"
        if not any(abs(px - x2) <= 8 and abs(pz - z2) <= 8 and k2 == want for x2, z2, k2 in eb):
            probs.append("%s(%d) %s at (%d,%d) on %s has no %s lane of %s(%d) at (%d,%d)" %
                         (na, sa, k, x, z, side, want, nb, sb, px, pz))
    for x, z, k in eb:
        back = {"N": (x, 0), "S": (x, TILE), "E": (TILE, z), "W": (0, z)}[side]
        want = "in" if k == "out" else "out"
        if not any(abs(back[0] - x2) <= 8 and abs(back[1] - z2) <= 8 and k2 == want for x2, z2, k2 in ea):
            probs.append("%s(%d) %s at (%d,%d) on %s has no %s lane of %s(%d)" % (nb, sb, k, x, z, opp, want, na, sa))
    return probs


def selftest():
    game = LK.Game()
    sp = specs(game)
    S, U = sp[PIECE_STRAIGHT], sp[PIECE_UTURN]
    bad = []
    cs, lines = cross_specs(game)
    for lang in ("ENGLISH", "English-UK"):
        bad += _selftest_lang(game, S, U, lang)
        bad += ["%s: %s" % (lang, b) for b in _selftest_corners(game, {"S": S, "U": U, "K": sp[PIECE_CORNER]}, lang)]
        for pid, base, side in lines:                    # each crossing between two one-way halves, every state
            for st in range(4):
                t = (side + st) % 4
                s_half = (t + 1) % 4                     # the half state whose traffic runs toward t
                back = SIDES[(t + 2) % 4]
                bad += ["%s: %s" % (lang, b) for b in check(cs[pid], st, S, s_half, SIDES[t], game, lang)]
                bad += ["%s: %s" % (lang, b) for b in check(S, s_half, cs[pid], st, SIDES[t], game, lang)]
    for s in range(4):
        assert len(edge_nodes(s, SIDES[half_dir(s)])) == 2
    bad += _selftest_outer_avlj()
    from netmod import hwlanes as HL
    bad += ["hwlanes curve sort id: %s" % b for b in HL.selftest_extra()]   # flat curve 0, deck curve 2
    print("selftest:", "PASSED" if not bad else "FAILED")
    for b in bad:
        print("  ", b)
    return not bad


def corner_grid(axis, end, ib):
    """{(x, z): (role, state)} of one corner pattern: the band's last row, the 2 x 2 block, the other band's first row"""
    a, b, a2, b2 = CORNER_PATTERNS[(axis, end, ib)]
    g = {}
    if axis == 0:
        g[(0, -end)], g[(1, -end)] = ("S", 1), ("S", 3)
        A, B, A2, B2 = (0, 0), (1, 0), (0, end), (1, end)
        cx = 2 if ib else -1
        zs = sorted((0, end))
        g[(cx, zs[0])], g[(cx, zs[1])] = ("S", 2), ("S", 0)
    else:
        g[(-end, 0)], g[(-end, 1)] = ("S", 2), ("S", 0)
        A, B, A2, B2 = (0, 0), (0, 1), (end, 0), (end, 1)
        cz = 2 if ib else -1
        xs = sorted((0, end))
        g[(xs[0], cz)], g[(xs[1], cz)] = ("S", 1), ("S", 3)
    g[A] = ("K", a) if not ib else ("S", a)
    g[B] = ("K", b) if ib else ("S", b)
    g[A2] = ("S", a2) if not ib else ("U", a2)
    g[B2] = ("U", b2) if not ib else ("S", b2)
    return g


AVL_D = [(0, -1), (1, 0), (0, 1), (-1, 0)]                    # N E S W, as sc3netmod_avl.c


def corner_outer_requirement(axis, end, ib):
    """The letters a declared avlj piece on a corner's OUTER cell must show, by WORLD side: {side index: 'I' | 'O'} for
    the two sides facing the block's halves (I = that half's traffic flows into the piece). Mirrors avl_outer_join."""
    g = corner_grid(axis, end, ib)
    (ox, oz), = [c for c, (r, _st) in g.items() if r == "U"]
    need = {}
    for w, (dx, dz) in enumerate(AVL_D):
        n = g.get((ox + dx, oz + dz))
        if n is None or n[0] != "S":
            continue
        t = half_dir(n[1])
        into = (ox + dx + AVL_D[t][0], oz + dz + AVL_D[t][1]) == (ox, oz)
        need[w] = "I" if into else "O"
    return need


def outer_fits(axis, end, ib, letters, state):
    """avl_outer_join's test on one pattern: a piece with avlj `letters` (N E S W at its state 0) at `state` on the
    outer cell; letter on world side w = letters[(w - state) & 3]"""
    return all(letters[(w - state) & 3] == want for w, want in corner_outer_requirement(axis, end, ib).items())


def _selftest_outer_avlj():
    """a fake avlj-declared outer cell: 21701's own turn declared as letters (enters x- = W, leaves z+ = S at state 0:
    "..OI") must fit every pattern at the pattern's outer state; the swapped letters ("..IO") must fit none"""
    bad = []
    for key, sts in sorted(CORNER_PATTERNS.items()):
        st = sts[2] if key[2] else sts[3]
        if not outer_fits(*key, letters="..OI", state=st):
            bad.append("outer avlj: pattern %s: the U-turn's letters ..OI at state %d do not fit %s"
                       % (key, st, corner_outer_requirement(*key)))
        if outer_fits(*key, letters="..IO", state=st):
            bad.append("outer avlj: pattern %s: swapped letters ..IO fit" % (key,))
    return bad


def _selftest_corners(game, pieces, lang):
    bad = []
    for (axis, end, ib) in sorted(CORNER_PATTERNS):
        g = corner_grid(axis, end, ib)
        for (x, z), (ra, sa) in g.items():
            for side, (dx, dz) in (("E", (1, 0)), ("S", (0, 1))):
                o = g.get((x + dx, z + dz))
                if o is None:
                    continue
                for pr in check(pieces[ra], sa, pieces[o[0]], o[1], side, game, lang):
                    bad.append("corner pattern %s: (%d,%d)-(%d,%d): %s" % ((axis, end, ib), x, z, x + dx, z + dz, pr))
    return bad


def _selftest_lang(game, S, U, lang):
    bad = []
    # a straight run: state s next to state s along the travel axis (both directions of travel)
    for s in range(4):
        d = SIDES[half_dir(s)]
        bad += check(S, s, S, s, d, game, lang)
    # the four end patterns (AVENUE_LANES.md 3): (band along, end side, cell A state, cell B state, A->B side)
    # band along z ending N: x- cell 11203.3, x+ cell 11203.0; the straight halves below them: x- 11204.1, x+ 11204.3
    ends = [("N", 3, 0, 1, 3, "E"), ("S", 2, 1, 1, 3, "E"), ("E", 0, 1, 2, 0, "S"), ("W", 3, 2, 2, 0, "S")]
    for end, ua, ub, ha, hb, across in ends:
        opp = {"N": "S", "S": "N", "E": "W", "W": "E"}[end]
        bad += check(S, ha, U, ua, end, game, lang)     # straight half A runs into its end cell
        bad += check(U, ua, U, ub, across, game, lang)   # end cell A -> end cell B
        bad += check(U, ub, S, hb, opp, game, lang)      # end cell B -> straight half B
    return ["%s: %s" % (lang, b) for b in bad]


# ----------------------------------------------------------------- tight left turns (by geometry)
def curve_left_radius(pts, min_chord=80):
    """Smallest radius of a LEFT bend along a curve as driven (points in order), or None. Left as avjunc counts it:
    (0,175) -> (80,255), heading +x then +z, is a left turn (cross product of the headings > 0); stock 769 (0,80) ->
    (80,0) is a right turn. Radius = circumradius of point triples p[i], p[m], p[j] whose chord p[i]p[j] is at least
    `min_chord` (shorter chords are dominated by the curve files' integer rounding)."""
    xz = [(float(p[0]), float(p[-1])) for p in pts]
    best = None
    for i in range(len(xz)):
        for j in range(i + 2, len(xz)):
            (x1, z1), (x3, z3) = xz[i], xz[j]
            if math.hypot(x3 - x1, z3 - z1) < min_chord:
                continue
            m = (i + j) // 2
            x2, z2 = xz[m]
            cross = (x2 - x1) * (z3 - z2) - (z2 - z1) * (x3 - x2)
            if cross <= 0:
                continue
            a, b, c = math.hypot(x2 - x1, z2 - z1), math.hypot(x3 - x2, z3 - z2), math.hypot(x3 - x1, z3 - z1)
            r = a * b * c / (2.0 * abs(cross))
            best = r if best is None else min(best, r)
    return best


def _lane_hits(rec, P, limit):
    out = []
    for n in rec["veh"]:
        for e in n["edges"]:
            if e["to"] is None or not e.get("path") or e["path"] not in P.veh:
                continue
            c = P.veh[e["path"]]
            r = curve_left_radius(c["pts"])
            if r is not None and r <= limit:
                t = rec["veh"][e["to"]]
                out.append({"from": (n["x"], n["z"]), "to": (t["x"], t["z"]), "key": e["path"], "radius": r,
                            "y": max(p[1] for p in c["pts"]), "new": e["path"] >= 20003 * 256})
    return out


def tight_lefts(spec, game, lang, limit=TIGHT_LEFT * 1.1):
    """-> [{"from", "to", "key", "radius", "y", "new"}] for every car lane of a spec (compiled for `lang`, curves found
    as the game would) whose curve has a left bend of radius <= limit (default 88: 80 plus the rounding margin)."""
    from netmod import hwlanes as HL
    if spec.get("curves") and id(spec) not in _CUR:
        HL.inject(game, spec)
        _CUR[id(spec)] = 1
    rec = LK.compile_spec(dict(spec, states=[0]), game, lang)["rec0"]
    return _lane_hits(rec, game.paths(lang), limit)


def scan_packages(dirs, game=None, langs=("ENGLISH", "English-UK")):
    """every lanes entry of every package dir; the curves of ALL the packages are injected first (as netpack merges)"""
    from netmod import hwlanes as HL
    from netmod import netpack_lanes as NL
    game = game or LK.Game()
    packs = []
    for d in dirs:
        mp = os.path.join(d, "manifest.json")
        if not os.path.isfile(mp):
            continue
        man = json.load(open(mp, encoding="utf-8"))
        specs_ = []
        for n, e in enumerate(man.get("lanes", [])):
            try:
                sp = NL._spec_of(d, e, "%s lanes %d" % (man.get("name"), n + 1))
            except NL.LanesError as ex:
                specs_.append((e.get("piece"), None, str(ex)))
                continue
            sp["piece"] = e["piece"]
            specs_.append((e["piece"], sp, None))
        packs.append((man.get("name", os.path.basename(d)), specs_))
    clash = []
    for name, specs_ in packs:
        for pid, sp, _err in specs_:
            if sp and sp.get("curves"):
                try:
                    HL.inject(game, sp)
                except LK.LaneError as ex:
                    clash.append((name, pid, "*", "curve inject: %s" % ex))
    hits, errors = [], clash
    for name, specs_ in packs:
        for pid, sp, err in specs_:
            if sp is None:
                errors.append((name, pid, "*", err))
                continue
            for lang in langs:
                try:
                    rec = LK.compile_spec(dict(sp, states=[0]), game, lang)["rec0"]
                except (LK.LaneError, KeyError, ValueError, TypeError) as ex:
                    errors.append((name, pid, lang, str(ex)))
                    continue
                for h in _lane_hits(rec, game.paths(lang), TIGHT_LEFT * 1.1):
                    hits.append(dict(h, pack=name, piece=pid, lang=lang, radius=round(h["radius"])))
    return hits, errors


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    if argv[1] == "build":
        for p in build(argv[2]):
            print("wrote", p)
        return 0
    if argv[1] == "check":
        conv = lambda v: int(v) if v.isdigit() else v
        probs = check(conv(argv[2]), int(argv[3]), conv(argv[4]), int(argv[5]), argv[6])
        print("clean" if not probs else "\n".join(probs))
        return 0 if not probs else 1
    if argv[1] == "selftest":
        return 0 if selftest() else 1
    if argv[1] == "corner-letters":
        for key in sorted(CORNER_PATTERNS):
            sts = CORNER_PATTERNS[key]
            req = corner_outer_requirement(*key)
            print("pattern axis %d end %+d inner on %s: outer cell stock state %d, needs %s" %
                  (key[0], key[1], "B" if key[2] else "A", sts[2] if key[2] else sts[3],
                   ", ".join("%s=%s" % (SIDES[w], l) for w, l in sorted(req.items()))))
        return 0
    if argv[1] == "tightleft":
        hits, errors = scan_packages(argv[2:])
        for h in hits:
            print("HIT %s piece %s %s lane %s -> %s curve %d (shape %d rot %d) left radius %d y %d %s" %
                  (h["pack"], h["piece"], h["lang"], h["from"], h["to"], h["key"], h["key"] >> 8, h["key"] & 255,
                   h["radius"], h["y"], "new curve" if h["new"] else "stock curve"))
        for name, pid, lang, err in errors:
            print("NOT COMPILED %s piece %s %s: %s" % (name, pid, lang, err))
        print("tightleft: %d hit(s), %d spec(s) not compiled" % (len(hits), len(errors)))
        return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
