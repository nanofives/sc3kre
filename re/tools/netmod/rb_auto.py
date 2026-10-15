#!/usr/bin/env python3
r"""rb_auto.py - the automatic 2x2 roundabout rule (task roundabout3, verify/roundabout3/PRE.md), offline.

The same rule sc3netmod.dll's RBT block applies in game, run on a save, so a city's conversions can be predicted
before it is loaded. Read-only.

A block is the 2x2 of ROAD cells with origin (X, Z): (X,Z) (X+1,Z) (X,Z+1) (X+1,Z+1). It is the pinwheel the stock
tiler builds when, per cell, the expected state holds and the piece is T 39 where the cell's exit holds road and curve
11203 where it does not (20400 counts as either: it is the converted block). Exit / closed / corner cells:

    exit    W (X-1,Z)    N (X+1,Z-1)  E (X+2,Z+1)  S (X,Z+2)      state of the block cell it serves: 3, 0, 1, 2
    closed    (X-1,Z+1)    (X,Z-1)      (X+2,Z)      (X+1,Z+2)
    corner    (X-1,Z-1)    (X+2,Z-1)    (X+2,Z+2)    (X-1,Z+2)    (the corner beside each exit)

Qualifies when ALL hold: (a) the four block cells are that pinwheel, (b) no closed cell holds road, (c) no exit that
holds road is part of a 2x2 of road cells outside the block (the exit, the corner beside it and the two cells beyond
them, away from the block: a 2-wide road or another 2x2 block), (d) at least MIN (3) exits hold road.
"Road" = a ROAD network piece (the tiler's predicate A for ROAD).

  py -3.12 rb_auto.py scan SAVE [SAVE ...] [--min 3] [--list]     qualifying blocks per city (+ why the others fail)
  py -3.12 rb_auto.py at SAVE X,Z                                  one block, every check
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

ROUNDABOUT = 20400
CLOSED_Q = 20401          # task roundabout4: the quarter whose exit holds no road (counts as either stock tile too)
T, CURVE = 39, 11203
CELLS = [((0, 0), 3), ((1, 0), 0), ((1, 1), 1), ((0, 1), 2)]       # block cell, its state (= the 20400 state)
EXIT = {3: (-1, 0), 0: (1, -1), 1: (2, 1), 2: (0, 2)}                 # by the state of the block cell it serves
CORNER = {3: (-1, -1), 0: (2, -1), 1: (2, 2), 2: (-1, 2)}
OUT = {3: (-1, 0), 0: (0, -1), 1: (1, 0), 2: (0, 1)}                  # the arm's direction away from the block
CLOSED = [(-1, 1), (0, -1), (2, 0), (1, 2)]


def check(road, X, Z, min_arms=3):
    """road(x, z) -> None | (id, state). -> (ok, arms, reason)"""
    cells = []
    for (dx, dz), st in CELLS:                          # (a) the four block cells first
        c = road(X + dx, Z + dz)
        if c is None:
            return False, 0, "block cell (%d,%d) not road" % (X + dx, Z + dz)
        pid, s = c
        if s != st or pid not in (T, CURVE, ROUNDABOUT, CLOSED_Q):
            return False, 0, "block cell (%d,%d) is %d.%d, not the pinwheel (%d.%d / %d.%d)" % (
                X + dx, Z + dz, pid, s, T, st, CURVE, st)
        cells.append((dx, dz, st, pid))
    arms = 0
    for dx, dz, st, pid in cells:
        ex, ez = EXIT[st]
        has = road(X + ex, Z + ez) is not None
        if pid == T and not has:
            return False, 0, "block cell (%d,%d) is T %d.%d but its exit (%d,%d) holds no road" % (
                X + dx, Z + dz, pid, st, X + ex, Z + ez)
        if pid == CURVE and has:
            return False, 0, "block cell (%d,%d) is curve %d.%d but its exit (%d,%d) holds road" % (
                X + dx, Z + dz, pid, st, X + ex, Z + ez)
        if has:
            cx, cz = CORNER[st]
            ox, oz = OUT[st]
            sq = [(X + ex, Z + ez), (X + cx, Z + cz), (X + ex + ox, Z + ez + oz), (X + cx + ox, Z + cz + oz)]
            if all(road(*c) is not None for c in sq):
                return False, 0, "exit (%d,%d) is part of a 2x2 of road %s (2-wide road / another block)" % (
                    X + ex, Z + ez, " ".join("(%d,%d)" % c for c in sq))
            arms += 1
    for dx, dz in CLOSED:
        if road(X + dx, Z + dz) is not None:
            return False, arms, "closed cell (%d,%d) holds road (avenue / another block / road into a closed side)" % (
                X + dx, Z + dz)
    if arms < min_arms:
        return False, arms, "%d arm(s) < %d" % (arms, min_arms)
    return True, arms, "qualifies, %d arms" % arms


_RULES = None


def road_of(city):
    """road(x, z) -> (id, state) of a ROAD piece (the tiler's predicate A for ROAD), else None"""
    global _RULES
    from netmod import tiler, paths
    if _RULES is None:
        _RULES = tiler.Rules(os.path.join(paths.Game().root, "Apps", "Res", "TilingRules"))
    flags = tiler.NETCFG[1]["predA"]
    lay = city.layers.get("surface", {})

    def road(x, z):
        p = lay.get((x, z))
        if p is None:
            return None
        f = _RULES.flags(T if p.id in (ROUNDABOUT, CLOSED_Q) else p.id)
        return (p.id, p.state) if (f & flags) == flags else None
    return road


def pieces(road, X, Z):
    """task roundabout4: the piece RBT writes per block cell, rows "(X,Z) (X+1,Z) / (X,Z+1) (X+1,Z+1)" as id.state:
    20400 where the cell's exit holds road, 20401 where it does not"""
    out = {}
    for (dx, dz), st in CELLS:
        ex, ez = EXIT[st]
        out[(dx, dz)] = "%d.%d" % (ROUNDABOUT if road(X + ex, Z + ez) is not None else CLOSED_Q, st)
    return "%s %s / %s %s" % (out[(0, 0)], out[(1, 0)], out[(0, 1)], out[(1, 1)])


def blocks(city, min_arms=3):
    """every pinwheel-shaped block (check (a) passes on its first cell) -> [(X, Z, ok, arms, reason)]"""
    road = road_of(city)
    out = []
    for (x, z), p in sorted(city.layers.get("surface", {}).items()):
        if p.state == 3 and p.id in (T, CURVE, ROUNDABOUT, CLOSED_Q):
            ok, arms, why = check(road, x, z, min_arms)
            if ok or not why.startswith("block cell"):
                out.append((x, z, ok, arms, why))
    return out


def main(argv):
    from netmod import tiler
    if len(argv) >= 3 and argv[1] == "scan":
        mn = int(argv[argv.index("--min") + 1]) if "--min" in argv else 3
        saves = [a for a in argv[2:] if a.lower().endswith(".sc3")]
        tot = 0
        for s in saves:
            c = tiler.City.load(s)
            bs = blocks(c, mn)
            q = [b for b in bs if b[2]]
            tot += len(q)
            reasons = {}
            for b in bs:
                if not b[2]:
                    k = b[4].split(" (")[0].split(" holds")[0]
                    k = "arms < %d" % mn if "arm(s) <" in b[4] else ("exit in a 2x2 of road" if "2x2 of road" in b[4] else
                         ("closed cell holds road" if "closed cell" in b[4] else k))
                    reasons[k] = reasons.get(k, 0) + 1
            print("%-28s pinwheel blocks %3d, qualify %3d   not: %s" % (os.path.basename(s)[:28], len(bs), len(q),
                  ", ".join("%s %d" % kv for kv in sorted(reasons.items())) or "-"))
            road = road_of(c)
            for b in q:
                print("    (%d,%d) %d arms -> %s" % (b[0], b[1], b[3], pieces(road, b[0], b[1])))
            if "--list" in argv:
                for b in bs:
                    print("    (%d,%d) %s" % (b[0], b[1], b[4]))
        print("total qualifying: %d" % tot)
        return 0
    if len(argv) == 4 and argv[1] == "at":
        c = tiler.City.load(argv[2])
        X, Z = (int(t) for t in argv[3].split(","))
        road = road_of(c)
        print(check(road, X, Z))
        for z in range(Z - 2, Z + 4):
            print("%4d " % z + " ".join(("%5d.%d" % road(x, z)) if road(x, z) else "      ." for x in range(X - 2, X + 4)))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
