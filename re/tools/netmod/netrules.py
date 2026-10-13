"""netrules.py -- tiling-rule explorer on top of the offline retiler (tiler.py).

  py -3 -m netmod.netrules validate <save...> [--net ROAD] [--opt k=v ...] [--csv out.csv]
  py -3 -m netmod.netrules explain <save> <x> <y> [--net ROAD] [--rules DIR]
  py -3 -m netmod.netrules preview <rules dir> <save> [--net ROAD] [--out map.png|map.txt]
  py -3 -m netmod.netrules apply-edits <manifest.json> [--base DIR] [--out DIR] [--save <city>]
  py -3 -m netmod.netrules lint [--rules DIR]

Run from re/tools (or with re/tools on sys.path). Read-only on the game install: edits are
applied to a copy (--out, default re/netcat_out/rules_<manifest name>).
"""
import argparse
import os
import sys
from collections import Counter

from . import paths, tiler

NETS = ["ROAD", "RAIL", "POWR", "HWAY", "PIPE", "SUBW"]


def _opts(kv, trace=False):
    d = dict(a.split("=", 1) for a in (kv or []))
    return tiler.Options(trace=trace, **d)


def _nets(arg):
    if not arg:
        return [tiler.TAG_NET[t] for t in NETS]
    return [tiler.TAG_NET[t.upper()] for t in arg.split(",")]


_EX = {}


def exemplars(game):
    if game.occupant not in _EX:
        _EX[game.occupant] = tiler.Exemplars(game.occupant)
    return _EX[game.occupant]


def retile_all(rules, city, net, opts, pe, ex=None):
    """Re-tile every cell of `net` from scratch, as one FUN_1001547b call whose node list is
    every occupied cell of that network (sorted (x, y), like FUN_1001b7cc)."""
    c2 = city.copy()
    if opts.stations == "subway":
        c2.add_stations({12360: ("subway", 0x40100), 12361: ("subway", 0x40100)})
    T = tiler.Tiler(rules, c2, opts, pe, ex)
    lay = T.layer(net)
    nodes = sorted(p for p, o in lay.items() if o.flags is None and T.predA(net, o))
    T.retile(net, nodes)
    return T, nodes


def compare(city, T, net, nodes):
    """-> list of (cell, (id,state) saved, (id,state)|None simulated)."""
    L0 = city.layers[tiler.LAYER_OF[net]]
    lay = T.layer(net)
    out = []
    for p in nodes:
        o = L0[p]
        s = lay.get(p)
        out.append((p, (o.id, o.state), (s.id, s.state) if s else None))
    return out


# ---------------------------------------------------------------------------- classify
CLASSES = [
    ("water", "water tile: commit refuses water (FUN_10016d69 -> SIMDIRT 0x100065f0); built by the bridge path"),
    ("slope", "slope tile: slope tables / illegal slope (FUN_1001a2c0, FUN_10016d00)"),
    ("edge", "map edge row/column: neighbour-connection input (+0x48 vt+0x58) [UNCERTAIN]"),
    ("stale", "saved piece's arm set (rule geometry) disagrees with its 4 neighbours: the occupancy changed "
              "after the tile was last re-tiled (history, not reproducible from the save)"),
    ("pole", "power pole phase: same 4-tile spacing, start set by the drag that built the line"),
    ("diag", "diagonal piece in the 3x3: diagonal drag path (FUN_1001da5f / FUN_1000abde), not modelled"),
    ("gap", "unmodelled occupant in the layer within 2 cells (empty cell inside a run)"),
    ("near-slope", "within 2 cells of a sloped tile"),
    ("interior", "flat interior, no class above"),
]


def classify(city, T0, net, cell, saved, sim, rules):
    """First applicable class wins (order of CLASSES)."""
    x, y = cell
    if city.is_water(x, y):
        return "water"
    if not T0.flat(x, y):
        return "slope"
    n = city.n
    if x in (0, n - 1) or y in (0, n - 1):
        return "edge"
    lay = city.layers[tiler.LAYER_OF[net]]
    if net == 3 and saved[0] in (14, 15, 92) and sim and sim[0] in (14, 15, 92):
        return "pole"
    arms = rules.arms(*saved)
    if arms is not None and not (net == 3 and saved[0] in (14, 15)):
        occ = 0
        for d in range(4):
            dx, dy = tiler.DIRS[d]
            o = lay.get((x + dx, y + dy))
            if o is not None and T0.predA(net, o):
                occ |= 1 << d
        if arms != occ and saved[0] != 43:
            return "stale"
    diag = rules.sets["DIAG"]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            o = lay.get((x + dx, y + dy))
            if o is not None and o.id in diag:
                return "diag"
    if sim and sim[0] in diag:
        return "diag"
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            q = (x + dx, y + dy)
            if q in lay:
                continue
            # an empty cell with the network on two opposite sides
            for ax, ay in ((1, 0), (0, 1)):
                a_, b_ = lay.get((q[0] - ax, q[1] - ay)), lay.get((q[0] + ax, q[1] + ay))
                if a_ is not None and b_ is not None and T0.predA(net, a_) and T0.predA(net, b_):
                    return "gap"
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if not T0.flat(x + dx, y + dy):
                return "near-slope"
    return "interior"


def cmd_validate(a):
    g = paths.Game()
    rules = tiler.Rules(a.rules or g.tiling)
    pe = tiler.load_pe(g)
    opts = _opts(a.opt)
    rows = []
    total = Counter()
    for path in a.saves:
        city = tiler.City.load(path)
        T0 = tiler.Tiler(rules, city, opts, pe)
        for net in _nets(a.net):
            T, nodes = retile_all(rules, city, net, opts, pe, exemplars(g))
            cmp_ = compare(city, T, net, nodes)
            same = sum(1 for _, s, m in cmp_ if s == m)
            ids = sum(1 for _, s, m in cmp_ if m and s[0] == m[0])
            cls = Counter()
            for cell, s, m in cmp_:
                if s != m:
                    k = classify(city, T0, net, cell, s, m, rules)
                    cls[k] += 1
                    rows.append((city.name, tiler.NET_TAG[net], cell[0], cell[1], s, m, k))
            total[(tiler.NET_TAG[net], "n")] += len(nodes)
            total[(tiler.NET_TAG[net], "same")] += same
            if nodes:
                print("%-28s %s %6d tiles  id+state %6.2f%%  id %6.2f%%  %s" % (
                    city.name[:28], tiler.NET_TAG[net], len(nodes), 100.0 * same / len(nodes),
                    100.0 * ids / len(nodes), dict(cls.most_common(6))))
    print("--- total")
    for t in NETS:
        n = total[(t, "n")]
        if n:
            print("%s %7d tiles  %6.2f%%" % (t, n, 100.0 * total[(t, "same")] / n))
    if a.csv:
        with open(a.csv, "w", newline="") as fh:
            fh.write("city,net,x,y,saved,sim,class\n")
            for r in rows:
                fh.write("%s,%s,%d,%d,%s,%s,%s\n" % (r[0].replace(",", ";"), r[1], r[2], r[3],
                                                     "%d/%d" % r[4], "%d/%d" % r[5] if r[5] else "-", r[6]))
        print("wrote", a.csv)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="netrules")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("saves", nargs="+")
    v.add_argument("--net")
    v.add_argument("--rules")
    v.add_argument("--opt", action="append")
    v.add_argument("--csv")
    a = ap.parse_args(argv)
    {"validate": cmd_validate}[a.cmd](a)


if __name__ == "__main__":
    main()
