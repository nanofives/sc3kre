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


def prepared(city, opts):
    """A copy of the city with the non-network occupants the engine sees in its layers: stations / utilities
    (tiler.STATIONS) and, with Options.buildings == "surface", every saved building in the surface layer, which
    is the city's occupant manager (vt+0x11c -> manager +0x3c, FUN_10012609)."""
    c2 = city.copy()
    if opts.stations in tiler.STATIONS:
        c2.add_stations(tiler.STATIONS[opts.stations])
    if opts.buildings == "surface":
        c2.add_stations({t: ("surface", 0) for t in getattr(city, "buildings", {})})
    return c2


def retile_all(rules, city, net, opts, pe, ex=None):
    """Re-tile every cell of `net` from scratch, as one FUN_1001547b call whose node list is
    every occupied cell of that network (sorted (x, y), like FUN_1001b7cc)."""
    c2 = prepared(city, opts)
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
    ("water", "water tile: commit refuses a water centre (FUN_100165d8 -> FUN_10016d69 -> SIMDIRT 0x100065f0); "
              "these tiles come from the bridge path (FUN_10014a23), not from this retile"),
    ("slope", "sloped tile: slope tables / illegal slope (FUN_1001a2c0, FUN_10016d00)"),
    ("seam", "within 1 cell of a --seam multiple: the 1024 test city is a 4x4 copy of a 256 city, so a piece cut at "
             "a seam keeps the arm that pointed into its old neighbour (an artifact of how the save was assembled)"),
    ("pole-phase", "POWR pole 14/15 positions differ inside a straight pole run: Complex rules #34/#58 make a pole "
                   "where the line runs straight 2 cells each way, #20-33/#35-36 and #44-57/#59-60 place the next "
                   "one 4 cells from any pole or non-straight piece, in work-list order, so the poles record the "
                   "order and extent of past retiles, which a save does not keep"),
    ("edge", "map edge row/column: neighbour-connection input (+0x48 vt+0x58) [UNCERTAIN]"),
    ("arm-to-building", "the saved piece has an arm into a cell that holds a building and no network piece"),
    ("arm-to-empty", "the saved piece has an arm into an empty cell"),
    ("arm-missing", "the saved piece lacks an arm toward a network neighbour that the simulator connects"),
    ("diag", "diagonal piece in the 3x3: diagonal drag path (FUN_1001da5f / FUN_1000abde), not modelled"),
    ("gap", "an empty cell within 2 cells with the network on two opposite sides of it"),
    ("near-slope", "within 2 cells of a sloped tile"),
    ("interior", "flat interior, no class above"),
]

POLES = {3: {(14, 0): 0, (92, 0): 0, (15, 0): 1, (92, 1): 1}}     # piece -> axis (0 = x run, 1 = y run)


def _building_cells(city):
    b = getattr(city, "_bcells", None)
    if b is None:
        b = {}
        for t, lst in getattr(city, "buildings", {}).items():
            for (a, b_, sa, sb, key) in lst:
                for x in range(a, a + sa):
                    for y in range(b_, b_ + sb):
                        b[(x, y)] = (t, key[2] & 0xFFFF)
        city._bcells = b
    return b


def _pole_phase(city, T, net, cell, saved, sim):
    """Both layouts put poles every 4 cells along the run through `cell`, at a different phase."""
    fam = POLES.get(net)
    if not fam or saved not in fam or sim not in fam or fam[saved] != fam[sim]:
        return False
    ax = fam[saved]
    L0, L1 = city.layers[tiler.LAYER_OF[net]], T.layer(net)
    step = (1, 0) if ax == 0 else (0, 1)
    pole = (14, 0) if ax == 0 else (15, 0)

    def run(lay):
        out, c = [], cell
        while True:                                      # walk back to the run start
            p = (c[0] - step[0], c[1] - step[1])
            o = lay.get(p)
            if o is None or (o.id, o.state) not in fam or fam[(o.id, o.state)] != ax:
                break
            c = p
        k = 0
        while True:
            o = lay.get(c)
            if o is None or (o.id, o.state) not in fam or fam[(o.id, o.state)] != ax:
                break
            if (o.id, o.state) == pole:
                out.append(k)
            c = (c[0] + step[0], c[1] + step[1])
            k += 1
        return out

    a, b = run(L0), run(L1)
    return bool(a) and bool(b) and a != b


def classify(city, T0, net, cell, saved, sim, rules, T=None, seam=None):
    """First applicable class wins (order of CLASSES). T = the Tiler after the retile, for pole-phase."""
    x, y = cell
    if city.is_water(x, y):
        return "water"
    if not T0.flat(x, y):
        return "slope"
    if seam and (x % seam in (seam - 1, 0) or y % seam in (seam - 1, 0)):
        return "seam"
    if T is not None and sim and _pole_phase(city, T, net, cell, saved, sim):
        return "pole-phase"
    n = city.n
    if x in (0, n - 1) or y in (0, n - 1):
        return "edge"
    lay = city.layers[tiler.LAYER_OF[net]]
    arms = rules.arms(*saved)
    if arms is not None:
        bcell = _building_cells(city)
        occ = 0
        for d in range(4):
            dx, dy = tiler.DIRS[d]
            o = lay.get((x + dx, y + dy))
            if o is not None and T0.predA(net, o):
                occ |= 1 << d
        extra = arms & ~occ
        if extra:
            for d in range(4):
                if extra >> d & 1:
                    dx, dy = tiler.DIRS[d]
                    if (x + dx, y + dy) in bcell:
                        return "arm-to-building"
            return "arm-to-empty"
        sim_arms = rules.arms(*sim) if sim else None
        if sim_arms is not None and sim_arms & ~arms & occ:
            return "arm-missing"
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
                    k = classify(city, T0, net, cell, s, m, rules, T, a.seam)
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


# ---------------------------------------------------------------------------- explain
# dir -> label by grid offset. The engine has no compass (NETWORK_RULE_ENGINE.md 13), so offsets, not N/E/S/W.
def dlabel(d):
    if d == tiler.SELF:
        return "self"
    dx, dy = tiler.DIRS[d]
    return "%s%s" % ("" if not dx else ("x%+d" % dx), "" if not dy else ("z%+d" % dy))


def mask_label(m):
    if m == 0x100:
        return "any"
    bits = [dlabel(d) for d in range(24) if m >> d & 1]
    return "0x%x (%s)" % (m, " ".join(bits) if bits else "none")


def rec_label(dir_, pid, st):
    if pid == 0:
        return "%s:%s" % (dlabel(dir_), {5: "empty", 1: "pending", 0: "empty-or-foreign"}.get(st, "0/%d" % st))
    return "%s:%d/%d" % (dlabel(dir_), pid, st)


def rule_label(rule):
    return "%s #%d (line %d): selector %s, if [%s] then [%s]" % (
        rule.file, rule.index, rule.line, mask_label(rule.selector),
        ", ".join(rec_label(c.dir, c.id, c.state) for c in rule.conds) or "-",
        ", ".join(rec_label(r.dir, r.id, r.state) for r in rule.results) or "-")


def piece_label(p):
    if p is None:
        return "empty"
    if p.flags is not None:
        return "building %d (type %d, flags 0x%x)" % (p.id, p.kind, p.flags)
    return "%d/%d" % (p.id, p.state)


def neighbourhood(city, lay, cell, r=2):
    bc = _building_cells(city)
    rows = ["       " + " ".join("%9s" % ("x%+d" % dx if dx else "x") for dx in range(-r, r + 1))]
    for dy in range(-r, r + 1):
        line = []
        for dx in range(-r, r + 1):
            q = (cell[0] + dx, cell[1] + dy)
            o = lay.get(q)
            if not (0 <= q[0] < city.n and 0 <= q[1] < city.n):
                t = "off-map"
            elif o is not None and o.flags is None:
                t = "%d/%d" % (o.id, o.state)
            elif o is not None or q in bc:
                t = "bldg"
            else:
                t = "."
            line.append("%9s" % (("[%s]" % t) if (dx, dy) == (0, 0) else t))
        rows.append("%6s " % ("z%+d" % dy if dy else "z") + " ".join(line))
    return "\n".join(rows)


def explain(rules, city, net, cell, opts, pe, ex, out=print):
    opts.trace = True
    opts.watch = {cell}
    T, nodes = retile_all(rules, city, net, opts, pe, ex)
    lay0 = city.layers[tiler.LAYER_OF[net]]
    saved, sim = lay0.get(cell), T.layer(net).get(cell)
    out("%s %s cell x=%d z=%d" % (city.name, tiler.NET_TAG[net], cell[0], cell[1]))
    out("saved: %s   simulated (from-scratch retile of all %d %s tiles): %s" % (
        piece_label(saved), len(nodes), tiler.NET_TAG[net], piece_label(sim)))
    out("saved neighbourhood (%s layer):" % tiler.LAYER_OF[net])
    out(neighbourhood(city, lay0, cell))
    if city.is_water(*cell):
        out("note: water tile (FUN_10016d69): FUN_100165d8 refuses to build on it")
    elif not T.flat(*cell):
        out("note: not flat, skipped by every rule stage (FUN_10016ccd); slope pass only (FUN_1001a2c0)")
    out("events (in engine order):")
    for ev in T.events:
        head = "  [%s%s]" % (ev.stage, "" if ev.stage == "slope" else " pass %d" % ev.passno)
        at = "here" if ev.cell == cell else "from x=%d z=%d" % ev.cell
        if ev.stage == "slope":
            out("%s %s: slope table row %d -> %s, %s" % (
                head, at, ev.mask, ", ".join(rec_label(r.dir, r.id, r.state) for r in ev.results),
                "built" if ev.committed else "not built"))
            continue
        if ev.rule is None or not ev.results:
            out("%s %s: mask %s, %s" % (head, at, mask_label(ev.mask), ev.why))
            if ev.cell == cell:
                seen = [rec_label(r[1], r[0], r[2]) for r in ev.obs if r[0] or r[1] != tiler.SELF]
                out("      observed: %s" % (", ".join(seen) or "-"))
            continue
        out("%s %s: mask %s" % (head, at, mask_label(ev.mask)))
        out("      first match %s" % rule_label(ev.rule))
        if ev.committed:
            got = ev.after.get(cell, "n/a") if ev.after else "n/a"
            out("      committed; this cell is now %s" % (piece_label(got) if got != "n/a" else "unchanged"))
        else:
            out("      refused: %s" % ev.why)
    if (saved and (saved.id, saved.state)) != (sim and (sim.id, sim.state)):
        T0 = tiler.Tiler(rules, city, opts, pe, ex)
        s = (saved.id, saved.state) if saved else (0, 0)
        m = (sim.id, sim.state) if sim else None
        k = classify(city, T0, net, cell, s, m, rules, T)
        out("verdict: DISAGREES, class '%s': %s" % (k, dict(CLASSES)[k]))
    else:
        out("verdict: agrees with the save")
    return T


def cmd_explain(a):
    g = paths.Game()
    rules = tiler.Rules(a.rules or g.tiling)
    pe = tiler.load_pe(g)
    city = tiler.City.load(a.save)
    cell = (a.x, a.z)
    if a.net:
        nets = _nets(a.net)
    else:
        T0 = tiler.Tiler(rules, city, _opts(a.opt), pe)
        nets = [n for n in (1, 4, 2, 3, 5, 6)
                if (lambda o: o is not None and o.flags is None and T0.predA(n, o))(T0.layer(n).get(cell))]
        if not nets:
            raise SystemExit("no network piece at x=%d z=%d (give --net to explain an empty cell)" % cell)
    for i, net in enumerate(nets):
        if i:
            print()
        explain(rules, city, net, cell, _opts(a.opt), pe, exemplars(g))


# ---------------------------------------------------------------------------- preview
def _diff(TA, TB, net):
    la, lb = TA.layer(net), TB.layer(net)
    out = {}
    for p in set(la) | set(lb):
        a_, b_ = la.get(p), lb.get(p)
        if a_ is not None and a_.flags is not None:
            continue
        ka = (a_.id, a_.state) if a_ else None
        kb = (b_.id, b_.state) if b_ else None
        if ka != kb:
            out[p] = (ka, kb)
    return out


def simulate(rules, city, net, opts, pe, ex, rect=None):
    """rect None: from-scratch retile of the whole net; else the in-game rectangle retile (message 0x637c0dab)."""
    if rect is None:
        return retile_all(rules, city, net, opts, pe, ex)[0]
    c2 = prepared(city, opts)
    T = tiler.Tiler(rules, c2, opts, pe, ex)
    bit ={1: 1, 4: 1, 2: 4, 3: 0x20, 5: 8, 6: 0x10}[net]
    T.retile_rect(bit, *rect)
    return T


PNG_COLOURS = {"same": (110, 110, 110), "changed": (230, 60, 40), "added": (40, 200, 70),
               "removed": (60, 110, 240), "empty": (16, 16, 20), "bldg": (45, 40, 34)}


def write_png(path, w, h, px):
    import struct as _s
    import zlib
    raw = b"".join(b"\x00" + bytes(c for rgb in row for c in rgb) for row in px)

    def chunk(t, d):
        return _s.pack(">I", len(d)) + t + d + _s.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", _s.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) +
                 chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def cmd_preview(a):
    g = paths.Game()
    new = tiler.Rules(a.rules_dir)
    stock = tiler.Rules(a.base or g.tiling)
    pe = tiler.load_pe(g)
    ex = exemplars(g)
    for i, d in enumerate(a.alias or []):
        k, v = (int(t) for t in d.split("="))
        ex.masks[k] = ex.masks.get(v, (0, 0, 0))
    city = tiler.City.load(a.save)
    rect = [int(v) for v in a.rect.split(",")] if a.rect else None
    lines = []
    for net in _nets(a.net):
        TA = simulate(stock, city, net, _opts(a.opt), pe, ex, rect)
        TB = simulate(new, city, net, _opts(a.opt), pe, ex, rect)
        d = _diff(TA, TB, net)
        lines.append("%s %s: %d tile(s) differ between %s and %s%s" % (
            city.name, tiler.NET_TAG[net], len(d), os.path.abspath(a.base or g.tiling), os.path.abspath(a.rules_dir),
            "" if rect is None else " (rectangle retile x=%d..%d z=%d..%d)" % (rect[0], rect[2], rect[1], rect[3])))
        for p in sorted(d):
            ka, kb = d[p]
            lines.append("  x=%-4d z=%-4d %-10s -> %s" % (p[0], p[1], "%d/%d" % ka if ka else "empty",
                                                         "%d/%d" % kb if kb else "empty"))
        if not a.out or not d:
            continue
        xs, ys = [p[0] for p in d], [p[1] for p in d]
        m = 4
        x0, x1 = max(min(xs) - m, 0), min(max(xs) + m, city.n - 1)
        y0, y1 = max(min(ys) - m, 0), min(max(ys) + m, city.n - 1)
        lb, bc = TB.layer(net), _building_cells(city)
        if a.out.lower().endswith(".png"):
            s = max(1, int(a.scale))
            full = a.full
            X0, X1, Y0, Y1 = (0, city.n - 1, 0, city.n - 1) if full else (x0, x1, y0, y1)
            px = []
            for y in range(Y0, Y1 + 1):
                row = []
                for x in range(X0, X1 + 1):
                    p = (x, y)
                    if p in d:
                        ka, kb = d[p]
                        k = "added" if ka is None else "removed" if kb is None else "changed"
                    elif p in lb and lb[p].flags is None:
                        k = "same"
                    elif p in bc:
                        k = "bldg"
                    else:
                        k = "empty"
                    row.extend([PNG_COLOURS[k]] * s)
                for _ in range(s):
                    px.append(row)
            out = a.out if len(_nets(a.net)) == 1 else a.out[:-4] + "_" + tiler.NET_TAG[net] + ".png"
            write_png(out, (X1 - X0 + 1) * s, (Y1 - Y0 + 1) * s, px)
            lines.append("  wrote %s (x %d..%d right, z %d..%d down; grey same, red changed, green added, "
                         "blue removed)" % (out, X0, X1, Y0, Y1))
        else:
            lines.append("  map x=%d..%d (columns) z=%d..%d (rows): # piece, * changed, + added, - removed, "
                         "b building, . empty" % (x0, x1, y0, y1))
            for y in range(y0, y1 + 1):
                row = ""
                for x in range(x0, x1 + 1):
                    p = (x, y)
                    if p in d:
                        ka, kb = d[p]
                        row += "+" if ka is None else "-" if kb is None else "*"
                    elif p in lb and lb[p].flags is None:
                        row += "#"
                    elif p in bc:
                        row += "b"
                    else:
                        row += "."
                lines.append("  %4d %s" % (y, row))
    text = "\n".join(lines)
    print(text)
    if a.out and not a.out.lower().endswith(".png"):
        with open(a.out, "w") as fh:
            fh.write(text + "\n")


# ---------------------------------------------------------------------------- apply-edits
def load_edits(manifests):
    """-> {file name: [edits]} merged over all manifests in order, like netpack's install: the variants' Set
    membership first (netpack.py "TilingRules: Set membership for every variant"), then each package's
    rule_edits. Also -> {variant id: base id} for the simulator's connectivity masks."""
    import json
    edits, alias = {}, {}
    for mp in manifests:
        with open(mp, encoding="utf-8") as fh:
            man = json.load(fh)
        name = man.get("name") or os.path.basename(os.path.dirname(os.path.abspath(mp)))
        by_net = {}
        for v in man.get("variants", []):
            by_net.setdefault(v["network"], []).append(v["id"])
            alias[v["id"]] = v["base"]
        for net, ids in sorted(by_net.items()):
            edits.setdefault("%s_GRND_Set.txt" % net, []).append({"op": "list_add", "ids": ids, "_pack": "(variants)"})
        for e in man.get("rule_edits", []):
            edits.setdefault(e["file"], []).append(dict(e, _pack=name))
    return edits, alias


def apply_edits(base, out_dir, edits):
    """Copy `base` (a TilingRules directory) to `out_dir` with every edited file rebuilt by netpack_rules.apply,
    the one implementation of the rule_edits format. -> [(file, stock bytes, new bytes)]."""
    from . import netpack_rules as NR
    import shutil
    real = {n.lower(): n for n in os.listdir(base)}
    os.makedirs(out_dir, exist_ok=True)
    for n in real.values():
        shutil.copyfile(os.path.join(base, n), os.path.join(out_dir, n))
    done = []
    for fname, el in sorted(edits.items(), key=lambda kv: kv[0].lower()):
        n = real.get(fname.lower())
        if n is None:
            raise SystemExit("rule edit names %s, which is not in %s" % (fname, base))
        with open(os.path.join(base, n), "rb") as fh:
            old = fh.read()
        try:
            new = NR.apply(n, old, el)
        except NR.RuleEditError as e:
            raise SystemExit("refused: %s" % e)
        with open(os.path.join(out_dir, n), "wb") as fh:
            fh.write(new)
        done.append((n, old, new, len(el)))
    return done


def cmd_apply_edits(a):
    g = paths.Game()
    base = a.base or g.tiling
    edits, alias = load_edits(a.manifests)
    stem = "_".join(os.path.splitext(os.path.basename(os.path.dirname(os.path.abspath(m)) if
                                                      os.path.basename(m) == "manifest.json" else m))[0]
                    for m in a.manifests)
    out_dir = a.out or os.path.join(paths.default_out(), "rules_" + stem)
    done = apply_edits(base, out_dir, edits)
    print("rules copied from %s to %s" % (base, out_dir))
    for n, old, new, k in done:
        print("  %-34s %d edit(s), %d -> %d bytes" % (n, k, len(old), len(new)))
    print("findings the edits add (lint against %s):" % base)
    print_lint(lint_dir(out_dir, base), True)
    if a.save:
        args = argparse.Namespace(rules_dir=out_dir, base=base, save=a.save, net=a.net, rect=a.rect, out=a.png,
                                  opt=a.opt, scale=a.scale, full=False,
                                  alias=["%d=%d" % kv for kv in alias.items()])
        print()
        cmd_preview(args)


# ---------------------------------------------------------------------------- lint
def _implied(ci, cj):
    """A condition of rule i is met whenever rule j's condition cj is (same dir and id; state equal, or ci.state
    0 which also accepts an observed 5, FUN_100220c5)."""
    return ci.dir == cj.dir and ci.id == cj.id and (ci.state == cj.state or (ci.state == 0 and cj.state in (0, 5)))


def lint_rules(rules):
    """Findings the engine semantics make certain (each cites the code that makes it so)."""
    out = []
    for stage_name, mode in (("Simple", 8), ("Complex", 0x18), ("final", 4)):
        for net in tiler.NET_TAG:
            rl, _ = rules.stage(stage_name, net)
            for j, rj in enumerate(rl):
                w = rj.where()
                sel = rj.selector
                if mode == 0x18 and sel not in (0, 0x100):
                    out.append(("never-matches", "%s: selector %s in a Complex file can never match: FUN_10019768 "
                                                 "builds no mask in mode 0x18, so the observed mask is always 0"
                                % (w, mask_label(sel))))
                elif sel != 0x100 and sel >> (4 if mode == 4 else 8):
                    out.append(("never-matches", "%s: selector %s sets bits the %s stage never sets (FUN_10019768 "
                                                 "sets bit d only for d < mode %d)" % (w, mask_label(sel), stage_name, mode)))
                lim = 24 if mode == 0x18 else 8
                for c in rj.conds:
                    if c.dir != tiler.SELF and c.dir >= lim:
                        out.append(("never-matches", "%s: condition %s is outside the %s window (3x3 in modes 4/8, "
                                                     "5x5 in 0x18, FUN_10019768)" % (w, rec_label(c.dir, c.id, c.state), stage_name)))
                    if mode != 0x18 and c.id == 0 and c.dir != tiler.SELF:
                        out.append(("never-matches", "%s: condition %s can never be observed in the %s stage: modes "
                                                     "4/8 report neighbours only for occupied cells, and a sentinel "
                                                     "record keeps dir self (FUN_1001a056 / FUN_100220b7)"
                                    % (w, rec_label(c.dir, c.id, c.state), stage_name)))
                dirs = {}
                for c in rj.conds:
                    if c.dir != tiler.SELF:
                        dirs.setdefault(c.dir, set()).add((c.id, c.state if c.state not in (0, 5) or c.id else 0))
                for d, s in dirs.items():
                    if len(s) > 1:
                        out.append(("never-matches", "%s: two different conditions at %s; one cell yields one "
                                                     "record, so the rule never matches" % (w, dlabel(d))))
                if not rj.results:
                    out.append(("no-results", "%s: no results: the parser (FUN_10022676) only stores a rule when its "
                                              "result count is reached, so its conditions merge into the next rule" % w))
                for i in range(j):
                    ri = rl[i]
                    if ri.selector not in (0x100, sel) or not ri.results:
                        continue
                    if all(any(_implied(ci, cj) for cj in rj.conds) for ci in ri.conds):
                        if (ri.selector == sel and set(ri.conds) == set(rj.conds)
                                and list(ri.results) == list(rj.results)):
                            out.append(("duplicate", "%s: duplicate of rule #%d (line %d), conditions in another "
                                                     "order; never reached, harmless" % (w, ri.index, ri.line)))
                        else:
                            out.append(("shadowed", "%s: never reached, rule #%d (line %d) matches first whenever "
                                                    "it would (same or wildcard selector, conditions a subset; first "
                                                    "match wins, FUN_100228ff)" % (w, ri.index, ri.line)))
                        break
                for r in rj.results:
                    if r.id and not any(r.id in s for s in rules.sets.values()):
                        out.append(("unknown-id", "%s: result %s places id %d, which is in no *_GRND_Set.txt nor "
                                                  "DIAG_Set.txt" % (w, rec_label(r.dir, r.id, r.state), r.id)))
    return out


def lint_dir(d, base=None):
    """-> [(kind, text)]; with `base`, only findings absent from that directory (an edit's new problems)."""
    probs = lint_rules(tiler.Rules(d))
    if base:
        have = set(lint_rules(tiler.Rules(base)))
        probs = [p for p in probs if p not in have]
    return probs


def print_lint(probs, show_all=False, out=print):
    from collections import Counter as _C
    c = _C(k for k, _ in probs)
    out("lint: %s" % (", ".join("%d %s" % (v, k) for k, v in sorted(c.items())) or "clean"))
    for k, t in probs:
        if show_all or k != "duplicate":
            out("  [%s] %s" % (k, t))
    if c.get("duplicate") and not show_all:
        out("  (%d duplicate rules not listed: --all)" % c["duplicate"])


def cmd_lint(a):
    g = paths.Game()
    d = a.rules or g.tiling
    probs = lint_dir(d, a.base)
    print("%s%s" % (d, " (findings not in %s)" % a.base if a.base else ""))
    print_lint(probs, a.all)
    return 1 if any(k != "duplicate" for k, _ in probs) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="netrules")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("saves", nargs="+")
    v.add_argument("--net")
    v.add_argument("--rules")
    v.add_argument("--opt", action="append")
    v.add_argument("--csv")
    v.add_argument("--seam", type=int, help="classify cells next to multiples of N as 'seam' (tiled test cities)")
    e = sub.add_parser("explain", help="why the simulator builds what it builds on one cell")
    e.add_argument("save")
    e.add_argument("x", type=int)
    e.add_argument("z", type=int)
    e.add_argument("--net")
    e.add_argument("--rules")
    e.add_argument("--opt", action="append")
    p = sub.add_parser("preview", help="tiles a rules directory changes against the stock rules, on one save")
    p.add_argument("rules_dir")
    p.add_argument("save")
    p.add_argument("--net")
    p.add_argument("--base", help="reference rules (default: the game's)")
    p.add_argument("--rect", help="x0,z0,x1,z1: simulate the in-game rectangle retile (message 0x637c0dab) "
                                  "instead of a from-scratch retile of the whole network")
    p.add_argument("--out", help="map.png or map.txt")
    p.add_argument("--scale", type=int, default=4)
    p.add_argument("--full", action="store_true", help="PNG of the whole map, not just the changed area")
    p.add_argument("--alias", action="append", help="ID=BASE: a new piece id uses BASE's connectivity masks")
    p.add_argument("--opt", action="append")
    m = sub.add_parser("apply-edits", help="apply netpack rule_edits (one or more manifests, one pass) to a copy")
    m.add_argument("manifests", nargs="+")
    m.add_argument("--base", help="stock TilingRules directory (default: the game's)")
    m.add_argument("--out", help="output directory (default re/netcat_out/rules_<name>)")
    m.add_argument("--save", help="then preview the result on this city")
    m.add_argument("--net")
    m.add_argument("--rect")
    m.add_argument("--png", help="preview map output (.png or .txt)")
    m.add_argument("--scale", type=int, default=4)
    m.add_argument("--opt", action="append")
    li = sub.add_parser("lint", help="rules that can never fire, or place ids outside the network's Set")
    li.add_argument("--rules")
    li.add_argument("--base", help="only report findings not already present in this directory")
    li.add_argument("--all", action="store_true", help="list duplicate rules too")
    a = ap.parse_args(argv)
    return {"validate": cmd_validate, "explain": cmd_explain, "preview": cmd_preview,
            "apply-edits": cmd_apply_edits, "lint": cmd_lint}[a.cmd](a)


if __name__ == "__main__":
    main()
