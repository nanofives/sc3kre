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
PIECE_UTURN = 21701           # base 11203: avenue end quarter
SHAPE_INNER = 23600           # (255, 80) -> (0, 80), y 0
SHAPE_UTURN_INNER = 23602     # (0, 175) -> (80, 255) radius 80 about (0, 255)
# English-UK holds every curve reversed under the same key (lanekit MIRROR_LANGS). With right-hand lanes in every
# language, a UK lane needs a curve that runs forward in the UK file: a new shape whose ENGLISH geometry is the
# reverse gets exactly that UK copy. Lanes carry no path key: each language's library is searched by end points.
SHAPE_UTURN_OUTER_UK = 23601  # English geometry (175, 255) -> (0, 80): its UK copy is the U-turn outer lane
SHAPE_OUTER_UK = 23603        # English geometry (0, 175) -> (255, 175): its UK copy is the straight outer lane
KEY_OUTER_STRAIGHT = 256      # stock (255, 175) -> (0, 175)
KEY_UTURN_OUTER = 1024        # stock 11203 (0, 80) -> (175, 255) radius 175 about (0, 255)
MATRIX_STRAIGHT = {"low": [["x+", "x-"]], "high": [["x-", "x+"]]}
MATRIX_UTURN = {"low": [["x-", "z+"]], "high": [["z+", "x-"]]}


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
    return {PIECE_STRAIGHT: straight, PIECE_UTURN: uturn}


def build(out_dir):
    out = []
    for pid, sp in specs().items():
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
    for lang in ("ENGLISH", "English-UK"):
        bad += _selftest_lang(game, S, U, lang)
    for s in range(4):
        assert len(edge_nodes(s, SIDES[half_dir(s)])) == 2
    print("selftest:", "PASSED" if not bad else "FAILED")
    for b in bad:
        print("  ", b)
    return not bad


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
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
