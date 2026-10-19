#!/usr/bin/env python3
r"""hwdx.py - stream hwdx (diagonal highway x straight highway, 45 degrees): cell tables, rule and offline twin.

The geometry is hwdx_plan.py (plan 'clover', the default the orchestrator picked 2026-10-18). This file turns it into
what the block and the package need, and checks the rule against the stock tiler offline.

  py -3.12 -m netmod.hwdx table [--case A|B]     cell table: piece class, id, state, base, flows (enter -> leave)
  py -3.12 -m netmod.hwdx ids                    id allocation (classes x flavours)
  py -3.12 -m netmod.hwdx check                  offline twin: the four drags on Roadless Paradise -> stock
                                                 aftermath -> detect -> place -> claim / plain checks -> movements;
                                                 then the end-cap cases (tasks hwcap / hwcap2): each arm ending on
                                                 its last joining cell, stock caps placed as the game does -> capped
                                                 joins; ending earlier -> that quadrant refused; never extended
Run from re/tools.

Frames. A crossing is found in the world as (O, case, r): O = the cell corner where the medians cross, case A or B,
r = quarter turns. The case frame is hwdx_plan's: S along x (row j = -1 runs +x, row 0 runs -x), D in band
i - j in {-1,0,1} (case A, x-z family) or i + j in {-2,-1,0} (case B, x+z family). World cell = case cell turned r
times about O with (i, j) -> (-j - 1, i) per step (hwx.rot_cell), sides x- -> z- -> x+ -> z+ per step, piece state
+ r. Which way the engine turns a state is checked at build time (as hwx does); `STATE_DIR` flips it.

Flavours. A mainline piece sits on stock highway, and the stock uses different ids per axis / family (straight along
x 15051, along z 73; x-z diagonal 11223 / 11224, x+z diagonal 15052 / 15106). So every class that touches highway
comes in two flavours: r even (S along x) and r odd (S along z). Ramp-only classes have one flavour.
"""
import argparse
import math
import os
import sys
from collections import deque

from . import hwdx_plan as G
from . import hwcap

PLAN = "clover"
STATE_DIR = 1                     # +1: a world state is case state + r; -1 if the engine turns the other way
SIDES = ["x-", "z-", "x+", "z+"]  # (x, z) -> (-z, x) sends each to the next
SIDE_D = {"x-": (-1, 0), "z-": (0, -1), "x+": (1, 0), "z+": (0, 1)}
OPP = {"x-": "x+", "x+": "x-", "z-": "z+", "z+": "z-"}
ID_RANGES = [(21260, 21359), (21460, 21559)]


def rot_side(s, k):
    return SIDES[(SIDES.index(s) + k) % 4]


def rot_cell(c, k):
    i, j = c
    for _ in range(k % 4):
        i, j = -j - 1, i
    return (i, j)


def mz(s):
    return {"z+": "z-", "z-": "z+"}.get(s, s)


# ------------------------------------------------------------------------------------------------ case-frame flows
def in_band(c, case):
    i, j = c
    return (i - j) in (-1, 0, 1) if case == "A" else (i + j) in (-2, -1, 0)


# Core turn sides of D (case A). The stock staircase takes one x step per row; inside the S rows an x step in the same
# direction as that row's traffic shares an entry side with S, and the turn matrix (sides only) then merges the two
# carriageways: the router would turn between S and D in the core without a ramp (measured offline: 4 of the 8
# turns). So in the core D takes its x steps only where they run against S's traffic: D+ (+x) goes straight up
# through row -1 (S runs +x there) and steps twice in row 0; D- (-x) goes straight down through row 0 and steps twice
# in row -1. Turn sides only: the drawn diagonal and its lanes keep the true geometry.
CORE_D_A = {(-2, -1): [("D-", "x+", "z-")],
            (-1, -1): [("D+", "z-", "z+"), ("D-", "x+", "x-")],
            (0, -1): [("D-", "z+", "x-")],
            (-1, 0): [("D+", "z-", "x+")],
            (0, 0): [("D+", "x-", "x+"), ("D-", "z+", "z-")],
            (1, 0): [("D+", "x-", "z+")]}


def mainline_flows(c, case, core=False):
    """flows through a mainline cell of the case frame: [(name, enter, leave)]; stock unless `core` (then D takes
    CORE_D_A's sides)"""
    i, j = c
    out = []
    if core and case == "A" and c in CORE_D_A:
        return [f for f in mainline_flows(c, "A") if f[0].startswith("S")] + CORE_D_A[c]
    if j == -1:
        out.append(("S+x", "x-", "x+"))
    elif j == 0:
        out.append(("S-x", "x+", "x-"))
    if case == "A":
        k = i - j
        if k == 1:
            out.append(("D+", "x-", "z+"))
        elif k == 0:
            out += [("D+", "z-", "x+"), ("D-", "z+", "x-")]
        elif k == -1:
            out.append(("D-", "x+", "z-"))
    else:                                     # case A mirrored z -> -z, directions reversed
        for name, e, l in mainline_flows((i, -1 - j), "A", core):
            if name.startswith("D"):
                out.append((name, mz(l), mz(e)))
    return out


def cell_path(pts):
    """cells a ramp centreline passes, in order, with (enter side, leave side); None at the two ends"""
    seq = []
    for x, z, h, e in pts:
        c = (math.floor(x), math.floor(z))
        if seq and c != seq[-1]:
            dx, dz = c[0] - seq[-1][0], c[1] - seq[-1][1]
            if abs(dx) + abs(dz) == 2:                       # through a corner: step via the x neighbour
                seq.append((seq[-1][0] + dx, seq[-1][1]))
        if not seq or c != seq[-1]:
            seq.append(c)
    inv = {v: k for k, v in SIDE_D.items()}
    out = []
    for n, c in enumerate(seq):
        ent = inv[(seq[n - 1][0] - c[0], seq[n - 1][1] - c[1])] if n else None
        lv = inv[(seq[n + 1][0] - c[0], seq[n + 1][1] - c[1])] if n + 1 < len(seq) else None
        out.append((c, ent, lv))
    return out


def case_table(case):
    """{cell: dict(kind, flows, quadrant, cls, cstate)} in the case frame. cls / cstate = piece class and the state
    that turns the class's state-0 content onto this cell."""
    g, core, att, ramp = G.classify(PLAN, case)
    R = G.ramp_samples(PLAN, case)
    quad = {"L6": "A1", "R4": "A1", "L3": "O1", "R7": "O1", "L8": "A2", "R2": "A2", "L1": "O2", "R5": "O2"}
    if case == "B":                                          # mirror swaps the quadrants' sides of S
        quad = {k: {"A1": "A1'", "A2": "A2'", "O1": "O1'", "O2": "O2'"}[v] for k, v in quad.items()}
    out = {}
    for c in g:
        kind = "core" if c in core else "att" if c in att else "ramp"
        out[c] = dict(kind=kind, flows=list(mainline_flows(c, case, kind == "core")) if kind != "ramp" else [],
                      quadrant=set())
    for name, pts in R.items():
        path = cell_path(pts)
        for n, (c, e, l) in enumerate(path):
            if c not in out:                                  # centreline cell the deck test missed (cannot happen)
                raise SystemExit("ramp %s centreline in unclassified cell %s" % (name, c))
            ml = out[c]["flows"]
            if e is None:                                    # the ramp splits off the carriageway it starts on
                e = next((f[1] for f in ml if f[2] == l or True), None) if ml else None
                e = _entry_of(ml, pts, c) or e
            if l is None:
                l = _exit_of(ml, pts, c) or (ml[0][2] if ml else None)
            out[c]["flows"].append((name, e, l))
            out[c]["quadrant"].add(quad[name])
    for name in R:
        for c in G.raster(PLAN, case) if False else ():
            pass
    for c, d in out.items():
        if not d["quadrant"]:
            near = [quad[n] for n, pts in R.items() for x, z, h, e in pts[::5]
                    if abs(x - c[0] - .5) < 1.2 and abs(z - c[1] - .5) < 1.2]
            d["quadrant"] = {near[0]} if near and d["kind"] != "core" else set()
    return out


def _entry_of(ml, pts, c):
    """the carriageway entry side for a ramp that starts inside cell c (it was on that carriageway)"""
    h = pts[0][2]
    best = None
    for name, e, l in ml:
        dx, dz = SIDE_D[l][0] - SIDE_D[e][0], SIDE_D[l][1] - SIDE_D[e][1]
        a = math.degrees(math.atan2(dz, dx))
        dd = abs((a - h + 180) % 360 - 180)
        if best is None or dd < best[0]:
            best = (dd, e)
    return best[1] if best else None


def _exit_of(ml, pts, c):
    h = pts[-1][2]
    best = None
    for name, e, l in ml:
        dx, dz = SIDE_D[l][0] - SIDE_D[e][0], SIDE_D[l][1] - SIDE_D[e][1]
        a = math.degrees(math.atan2(dz, dx))
        dd = abs((a - h + 180) % 360 - 180)
        if best is None or dd < best[0]:
            best = (dd, l)
    return best[1] if best else None


# ------------------------------------------------------------------------------------------------ classes and ids
def stock_base(case, c):
    """what the stock puts in a plain mainline cell of the case frame: (kind, family, state, symmetric).
    kind 'S' straight, 'Do' diagonal outer cell, 'Dm' diagonal middle cell (both halves: state 0 == state 2).
    Case frame = world at r = 0: S along x (15051.2 runs +x, 15051.0 -x); case A band 11223.0 / 11224.0 / 11223.2,
    case B band 15052.0 / 15106.0 / 15052.2 (measured in game 2026-10-18)."""
    i, j = c
    if j in (-1, 0):
        return ("S", None, 2 if j == -1 else 0, False)
    k = i - j if case == "A" else i + j + 1
    fam = "xz" if case == "A" else "xpz"
    return {1: ("Do", fam, 0, False), 0: ("Dm", fam, 0, True), -1: ("Do", fam, 2, False)}[k]


def classes():
    """piece classes over both cases: {(case, cell): (cls, cstate)}, {cls: dict(kind, base, rep)}.
    A cell on highway takes the stock state of its base there (so the piece saves as the right stock piece); a cell
    off the highway (ramp alone) shares a piece with any cell whose content is the same up to a turn."""
    sig_of, info, out = {}, {}, {}
    for case in ("A", "B"):
        g, core, att, ramp = G.classify(PLAN, case)
        for c in sorted(g, key=lambda c: (c[1], c[0])):
            if c in core:
                m = (-1 - c[0], -1 - c[1])
                rep = min(c, m)
                kb, fam, st, sym = stock_base(case, c)
                if sym:
                    st = 0 if c == rep else 2
                key = ("core", case, rep)
                base = (kb, fam)
            elif c in att:
                kb, fam, st0, sym = stock_base(case, c)
                cand = [0, 2] if sym else [st0]
                st, sig = min(((k, G.rot_sig(g[c], (-k) % 4)) for k in cand), key=lambda t: t[1])
                key = ("m", kb, fam, sig)
                base = (kb, fam)
            else:
                sigs = [G.rot_sig(g[c], k) for k in range(4)]
                best = min(sigs)
                st = (-sigs.index(best)) % 4                  # canonical = rot(content, -st)
                key = ("r", best)
                base = ("land", None)
            if key not in sig_of:
                sig_of[key] = len(sig_of)
                kind = "core" if c in core else "att" if c in att else "ramp"
                info[sig_of[key]] = dict(kind=kind, base=base, rep=(case, c), flavoured=kind != "ramp")
            out[(case, c)] = (sig_of[key], st)
    return out, info


FLIP = {"xz": "xpz", "xpz": "xz"}
BASE_ID = {("S", 0): 15051, ("S", 1): 73, ("Do", "xz"): 11223, ("Do", "xpz"): 15052, ("Dm", "xz"): 11224,
           ("Dm", "xpz"): 15106}
LAND_BASE = 15099          # Protected HWAY base for pieces written into free cells (hwcore's choice)


def base_of(info_c, flavour):
    """-> (base id, state offset) of a class in a flavour. Flavour 1 = the crossing turned an odd number of quarter
    turns (S along z): the stock uses 73 for a straight along z (15051.2 turned = 73.0: offset +1) and the other
    family's diagonal pieces (11223.0 turned = 15052.0: offset -1; 15052.0 turned = 11223.2: offset +1)."""
    kb, fam = info_c["base"]
    if kb == "land":
        return LAND_BASE, 0
    if kb == "S":
        return BASE_ID[("S", flavour)], (1 if flavour else 0)
    # 11223.0 turned once = 15052.0 (offset -1); 15052.0 turned once = 11223.2 (offset +1)
    return BASE_ID[(kb, FLIP[fam] if flavour else fam)], ((3 if fam == "xz" else 1) if flavour else 0)


def ids():
    """{(cls, flavour): id}; flavour 0 = S along x (r even), 1 = S along z (r odd); ramp classes flavour 0 only"""
    cmap, info = classes()
    pool = [i for a, b in ID_RANGES for i in range(a, b + 1)]
    out, k = {}, 0
    order = sorted(info, key=lambda c: ({"core": 0, "att": 1, "ramp": 2}[info[c]["kind"]], c))
    for fl in (0, 1):
        for cls in order:
            if info[cls]["flavoured"] or fl == 0:
                if k >= len(pool):
                    raise SystemExit("ids: %d pieces, %d ids" % (k + 1, len(pool)))
                out[(cls, fl)] = pool[k]
                k += 1
    return out, k, len(pool)


# ------------------------------------------------------------------------------------------------ the stock twin
_E = {}


def env():
    if not _E:
        from netmod import tiler, netrules, paths
        g = paths.game_root()
        game = paths.Game()
        _E.update(g=g, game=game, tiler=tiler, netrules=netrules)
    return _E


def new_tiler():
    E = env()
    tiler, netrules = E["tiler"], E["netrules"]
    opts = tiler.Options()
    city = netrules.prepared(tiler.City.load(os.path.join(E["g"], "Cities", "Roadless Paradise.sc3")), opts)
    T = tiler.Tiler(tiler.Rules(os.path.join(E["g"], "Apps", "Res", "TilingRules")), city, opts,
                    tiler.load_pe(E["game"]), E["netrules"].exemplars(E["game"]))
    return T, city


def drag(T, city, cells):
    lay = T.layer(4)
    for c in cells:
        if c not in lay:
            lay[c] = env()["tiler"].Piece(15051, 0, city.h(*c))
    T.retile(4, cells)


def world_drags(O, case, r, n=14, s=None, d=None):
    """the cells of the two highway drags of a crossing (O, case, r): S rows and the D band, n cells each way, or the
    S columns i in s = (lo, hi) and the band middles k in d = (lo, hi) (case frame)"""
    s = s or (-n, n)
    d = d or (-n, n)
    S = [(i, j) for i in range(s[0], s[1] + 1) for j in (-1, 0)]
    D = [(k + e, k) for k in range(d[0], d[1] + 1) for e in (-1, 0, 1)] if case == "A" else \
        [(k + e, -1 - k) for k in range(d[0], d[1] + 1) for e in (-1, 0, 1)]
    f = lambda c: (O[0] + rot_cell(c, r)[0], O[1] + rot_cell(c, r)[1])      # noqa: E731
    return [f(c) for c in S], [f(c) for c in D]


def cap_ends(T, city, cells):
    """the stock end caps the game puts on a drag (the offline tiler places none): hwcap.stock_ends"""
    Pc = env()["tiler"].Piece
    lay = T.layer(4)
    return hwcap.stock_ends(lay, [c for c in cells if c in lay], lambda i, s, c: Pc(i, s, city.h(*c)))


def arm_step(c, case, r):
    """outward step (world) of the arm a case-frame cell lies on (sc3netmod_hwdx.c hwdx_arm_step)"""
    i, j = c
    if j in (-1, 0):
        v = (1 if i >= 0 else -1, 0)
    elif case == "A":
        v = (1, 1) if j > 0 else (-1, -1)
    else:
        v = (1, -1) if j < 0 else (-1, 1)
    for _ in range(r % 4):
        v = (-v[1], v[0])
    return v


# ------------------------------------------------------------------------------------------------ the rule
STRAIGHT = {15051, 73}
BAND = {11223, 11224, 15052, 15106}
MID = {11224, 15106}
CONSTR = 15149
# the stock aftermath in the case frame (case A; case B = rows mirrored), measured in game 2026-10-18 and reproduced
# by the offline tiler: role per cell
AFTER_A = {(-3, -1): "c", (-2, -1): "c", (1, 0): "c", (2, 0): "c",      # 15149
           (-1, -1): "m", (0, 0): "m",                                  # band middle cells inside the S rows
           (0, -1): "s", (-1, 0): "s",                                  # the band's outer cells left straight
           (-3, -2): "s", (2, 1): "s"}                                  # band cells beside S turned straight (73)


def after(case):
    return AFTER_A if case == "A" else {(i, -1 - j): v for (i, j), v in AFTER_A.items()}


def detect(lay):
    """crossings in a highway layer {cell: Piece}: [(O, case, r)], r in {0, 1} (r and r + 2 are the same placement:
    the design is point-symmetric about O)"""
    cons = {c for c, p in lay.items() if p.id == CONSTR}
    found = set()
    for w in cons:
        for case in ("A", "B"):
            pat = after(case)
            for r in range(4):
                for p, role in pat.items():
                    if role != "c":
                        continue
                    q = rot_cell(p, r)
                    O = (w[0] - q[0], w[1] - q[1])
                    ok = True
                    for p2, role2 in pat.items():
                        q2 = rot_cell(p2, r)
                        piece = lay.get((O[0] + q2[0], O[1] + q2[1]))
                        want = {"c": {CONSTR}, "m": MID, "s": STRAIGHT}[role2]
                        if piece is None or piece.id not in want:
                            ok = False
                            break
                    if ok:
                        found.add((O, case, r % 2))
    return sorted(found)


def to_world(O, r, c):
    q = rot_cell(c, r)
    return (O[0] + q[0], O[1] + q[1])


def place(lay, city, O, case, r, cut=None):
    """-> dict(placements {world cell: (id, state, cls, kind, base)}, quadrants built, refused {quadrant: why}, core_ok,
    carried [] and ext set() (kept for callers; task hwcap2 never carries an arm on). A joining cell that holds the
    arm's own stock end cap gets its class's capped join (kind 'capjoin', at the cap's state); a joining cell that holds
    nothing (the arm ended before it) refuses its quadrant."""
    tab = case_table(case)
    cmap, info = classes()
    idm, _, _ = ids()
    fl = r % 2
    quads = sorted({q for d in tab.values() for q in d["quadrant"]})
    why = {}
    # core: must be the stock aftermath (16 cells) and flat dry ground
    core_ok = True
    for c, d in tab.items():
        if d["kind"] != "core":
            continue
        w = to_world(O, r, c)
        p = lay.get(w)
        if p is None or p.id not in STRAIGHT | BAND | {CONSTR}:
            core_ok = False
            why["core"] = "core cell %s holds %s" % (w, p)
    if not core_ok:
        return dict(placements={}, built=[], refused=why, core_ok=False, carried=[], ext=set())
    capm = {(cp["cls"], cp["flavour"]): cp for cp in capped_list()}
    capped = {}
    for q in quads:
        for c, d in tab.items():
            if q not in d["quadrant"] or d["kind"] == "core":
                continue
            w = to_world(O, r, c)
            p = lay.get(w)
            if d["kind"] == "att":
                if p is None or p.id in hwcap.CAP_IDS:              # the arm ends here or before (hwcap / hwcap2)
                    cp = capm.get((cmap[(case, c)][0], fl))
                    if cp and p is not None and hwcap.cap_dir(p) == arm_step(c, case, r) and p.id == cp["base"]:
                        capped[w] = (cp["id"], p.state, cp["base"])     # the arm ends on it: the capped join
                        continue
                    why[q] = "joining cell %s: %s" % (w, "the arm ends before it" if p is None else
                                                      "end cap %s with no capped join" % (p,))
                    break
                if p.id not in STRAIGHT | BAND:
                    why[q] = "joining cell %s holds %s, wants plain highway" % (w, p)
                    break
            else:
                if p is not None or (cut and w in cut):
                    why[q] = "ramp cell %s is taken (%s)" % (w, p if p is not None else "claimed")
                    break
                if not flat(city, w):
                    why[q] = "ramp cell %s is not flat" % (w,)
                    break
    built = [q for q in quads if q not in why]
    out = {}
    for c, d in tab.items():
        if d["kind"] != "core" and not (d["quadrant"] & set(built)):
            continue
        cls, cs = cmap[(case, c)]
        f = fl if info[cls]["flavoured"] else 0
        pid = idm[(cls, f)]
        bid, off = base_of(info[cls], f)
        w = to_world(O, r, c)
        if w in capped:
            out[w] = (capped[w][0], capped[w][1], cls, "capjoin", capped[w][2])
            continue
        out[w] = (pid, (cs + STATE_DIR * r + off) % 4, cls, d["kind"], bid)
    return dict(placements=out, built=built, refused=why, core_ok=True, carried=[], ext=set())


def flat(city, c):
    x, z = c
    hs = {city.h(x, z), city.h(x + 1, z), city.h(x, z + 1), city.h(x + 1, z + 1)}
    return len(hs) == 1 and not city.is_water(x, z)


# ------------------------------------------------------------------------------------------------ movements
def world_flows(lay, placed, O, case, r, tabs):
    """{world cell: [(enter, leave)]}: placed cells from the case table (turned), other highway cells from stock"""
    tab = tabs[case]
    inv = {}
    for c, d in tab.items():
        w = to_world(O, r, c)
        if w in placed:
            inv[w] = [(rot_side(e, r), rot_side(l, r)) for n, e, l in d["flows"] if e and l]
    return inv


def stock_flows(c, O, case, r):
    """flows of a plain stock highway cell, from the case frame (the arms are the canonical S rows and band)"""
    # back to the case frame
    for k in range(4):
        if to_world(O, r, rot_cell((0, 0), 0)) is None:
            pass
    rel = (c[0] - O[0], c[1] - O[1])
    q = rel
    for _ in range((-r) % 4):
        q = rot_cell(q, 1)
    return [(rot_side(e, r), rot_side(l, r)) for n, e, l in mainline_flows(q, case)]


def movements(placed, O, case, r, tabs, reach=16):
    """every (from arm, to arm) pair reachable over the turn sides; arms = S rows / band cells `reach` out"""
    flows = world_flows(None, placed, O, case, r, tabs)

    def cell_flows(w):
        if w in flows:
            return flows[w]
        return stock_flows(w, O, case, r)

    # entry points: case-frame cells far out on each carriageway, inbound direction
    n = reach
    ends = {"-x": ((-n, -1), (-n, 0)), "+x": ((n, 0), (n, -1)),     # (inbound entry cell, outbound exit cell)
            "-d": ((-n + 1, -n), (-n - 1, -n)), "+d": ((n - 1, n), (n + 1, n))}
    if case == "B":            # D: mirrored rows, and mirror + reverse turns A's inbound cell into B's outbound one
        ends = {k: ((v[1][0], -1 - v[1][1]), (v[0][0], -1 - v[0][1])) if k in ("-d", "+d") else v
                for k, v in ends.items()}
    res = {}
    for a, (cin, _) in ends.items():
        start = to_world(O, r, cin)
        seen = set()
        dq = deque()
        for e, l in cell_flows(start):
            dq.append((start, e))
        while dq:
            w, e = dq.popleft()
            if (w, e) in seen:
                continue
            seen.add((w, e))
            for e2, l2 in cell_flows(w):
                if e2 == e:
                    d = SIDE_D[l2]
                    nb = (w[0] + d[0], w[1] + d[1])
                    if abs(nb[0] - O[0]) > n + 2 or abs(nb[1] - O[1]) > n + 2:
                        continue
                    dq.append((nb, OPP[l2]))
        cells = {w for w, e in seen}
        for b, (_, cout) in ends.items():
            res[(a, b)] = to_world(O, r, cout) in cells
    return res


# ------------------------------------------------------------------------------------------------ commands
def cmd_table(a):
    tab = case_table(a.case)
    cmap, info = classes()
    idm, _, _ = ids()
    for c in sorted(tab, key=lambda c: (c[1], c[0])):
        d = tab[c]
        cls, cs = cmap[(a.case, c)]
        pid = idm[(cls, 0)]
        fl = ", ".join("%s %s->%s" % f for f in d["flows"])
        print("%-9s %-4s %-12s cls %3d id %d.%d  %s" % (c, d["kind"], "/".join(sorted(d["quadrant"])) or "-",
                                                         cls, pid, cs, fl))


def cmd_ids(a):
    idm, n, pool = ids()
    cmap, info = classes()
    by = {}
    for cls, d in info.items():
        by[d["kind"]] = by.get(d["kind"], 0) + 1
    print("classes %d (%s); with flavours %d ids of %d" % (len(info), ", ".join("%s %d" % kv for kv in
                                                                               sorted(by.items())), n, pool))
    print("first / last id: %d / %d" % (min(idm.values()), max(idm.values())))


def cmd_check(a):
    tabs = {"A": case_table("A"), "B": case_table("B")}
    bad = 0
    drags = [((58, 28), "A", 0), ((58, 28), "B", 0), ((58, 28), "A", 1), ((58, 28), "B", 1)]
    for O, case, r in drags:
        for order in ("SD", "DS"):
            T, city = new_tiler()
            S, D = world_drags(O, case, r)
            first, second = (S, D) if order == "SD" else (D, S)
            drag(T, city, first)
            drag(T, city, second)
            lay = T.layer(4)
            found = detect(lay)
            tag = "case %s r%d (%s, %s first)" % (case, r, "S along x" if r % 2 == 0 else "S along z",
                                                  "S" if order == "SD" else "D")
            want = (O, case, r % 2)
            if found != [want]:
                print("FAIL %s: detect -> %s, wanted %s" % (tag, found, want))
                bad += 1
                continue
            res = place(lay, city, O, case, r)
            pl = res["placements"]
            # a joining piece saves as its base at its state: that must be the stock piece the cell held
            badb = []
            for w, (pid, st, cls, kind, bid) in pl.items():
                if kind != "att":
                    continue
                p = lay[w]
                sym = bid in (11224, 15106)
                if p.id != bid or (p.state != st and not (sym and (p.state - st) % 2 == 0)):
                    badb.append((w, (p.id, p.state), (bid, st)))
            if badb:
                print("  base mismatch at %d joining cells, e.g. %s" % (len(badb), badb[:3]))
                bad += 1
            mv = movements(pl, O, case, r, tabs)
            need = [(x, y) for x in ("-x", "+x", "-d", "+d") for y in ("-x", "+x", "-d", "+d") if x != y]
            miss = [k for k in need if not mv[k]]
            print("%-34s found O %s; quadrants %s refused %s; %d cells placed; movements %d/12%s" % (
                tag, O, ",".join(res["built"]), res["refused"] or "-", len(pl), 12 - len(miss),
                (" MISSING " + ", ".join("%s->%s" % k for k in miss)) if miss else ""))
            if miss or res["refused"]:
                bad += 1
            if not mv and a.verbose:
                pass
    # cells sharing a piece must share its turn sides, turned by their state
    cmap, info = classes()
    mism = 0
    for (case, c), (cls, cs) in cmap.items():
        rcase, rc = info[cls]["rep"]
        k = (cs - cmap[(rcase, rc)][1]) % 4                  # cell = rep turned k times
        rep = {(rot_side(e, k), rot_side(l, k)) for n, e, l in tabs[rcase][rc]["flows"] if e and l}
        got = {(e, l) for n, e, l in tabs[case][c]["flows"] if e and l}
        if rep != got:
            mism += 1
            if a.verbose:
                print("  turn sides differ: case %s %s (class %d, state %d): %s vs rep %s %s" % (
                    case, c, cls, cs, sorted(got), rc, sorted(rep)))
    print("pieces whose cells disagree on turn sides: %d of %d cells" % (mism, len(cmap)))
    bad += 1 if mism else 0
    # no ramps (core only): the turn matrices must give the four through movements and nothing else, else the
    # router turns between S and D inside the core (see CORE_D_A)
    for case in ("A", "B"):
        core = {to_world((0, 0), 0, c): None for c, d in tabs[case].items() if d["kind"] == "core"}
        mv = movements(core, (0, 0), case, 0, tabs)
        got = sorted("%s>%s" % k for k, v in mv.items() if v and k[0] != k[1])
        okc = got == ["+d>-d", "+x>-x", "-d>+d", "-x>+x"]
        print("core only, case %s: %s%s" % (case, " ".join(got), "" if okc else "  <- LEAK"))
        bad += 0 if okc else 1
    # a refusal case: a claimed cell inside quadrant A1's ramp cells
    T, city = new_tiler()
    S, D = world_drags((58, 28), "A", 0)
    drag(T, city, S)
    drag(T, city, D)
    lay = T.layer(4)
    cut = {(58 + 7, 28 + 3)}
    res = place(lay, city, (58, 28), "A", 0, cut=cut)
    print("claimed cell %s in A1 -> built %s, refused %s" % (sorted(cut), ",".join(res["built"]), res["refused"]))
    bad += check_caps(tabs)
    print("FAILURES: %d" % bad)
    return 1 if bad else 0


# Arm lengths that put the stock end cap on each arm's last joining cell (case frame: S columns i, band middles k).
# The game caps a drag ON its last cell at one end and one cell PAST it at the other (sc3netmod_hwcap.c), so a drag
# that reaches exactly the last joining row works from one side and not from the other.
CAP_ARMS = {"+x": dict(s=(-14, 9)), "-x": dict(s=(-10, 14)), "+d": dict(d=(-14, 6)), "-d": dict(d=(-7, 14))}


def check_caps(tabs):
    """tasks hwcap / hwcap2: the end-cap cases (stock caps placed on the footprint ends, as the game does). Owner
    2026-10-18: never extend. An arm ending ON its last joining cell -> that cell's capped join, every quadrant built;
    an arm ending a row earlier -> that quadrant refused; the straight arm ending on O2's / O1's last joining column
    (i 6 / -7) -> O2 / O1 with a capped join, A1 / A2 refused. Never a highway piece in a cell the drags left empty.
    -> failures"""
    bad = 0
    print("--- end caps (tasks hwcap / hwcap2)")
    need = [(x, y) for x in ("-x", "+x", "-d", "+d") for y in ("-x", "+x", "-d", "+d") if x != y]
    runs = [(O, case, r, arms, None, 4) for O, case, r in [((58, 28), "A", 0), ((58, 28), "B", 0), ((58, 28), "A", 1),
                                                         ((58, 28), "B", 1)]
            for arms in (["+x"], ["-x"], ["+d"], ["-d"], ["+x", "-x", "+d", "-d"])]
    for case, r in (("A", 0), ("B", 0), ("A", 1), ("B", 1)):
        runs.append(((58, 28), case, r, ["+d"], "short", 2))      # the arm ends a row earlier: A1 refused, and O1
                                                                   # (its joining outer cell lies past the new cap)
        runs.append(((58, 28), case, r, ["+x"], "short", 3))
        runs.append(((58, 28), case, r, ["+x"], "O2", 3))         # S ends on column 6: O2 capped, A1 refused
        runs.append(((58, 28), case, r, ["-x"], "O1", 3))         # S ends on column -7: O1 capped, A2 refused
    for O, case, r, arms, mode, want in runs:
        T, city = new_tiler()
        lim = {}
        for a in arms:                                            # +x and -x (+d and -d) together: both ends short
            for key, (lo, hi) in CAP_ARMS[a].items():
                plo, phi = lim.get(key, (-14, 14))
                lim[key] = (max(lo, plo), min(hi, phi))
        if mode == "short":                                       # one row short of the last joining cell
            if arms[0] == "+d":
                lim["d"] = (-14, 5)
            else:
                lim["s"] = (-14, 8)
        if mode == "O2":
            lim["s"] = (-14, 6)
        if mode == "O1":
            lim["s"] = (-7, 14)
        S, D = world_drags(O, case, r, s=lim.get("s"), d=lim.get("d"))
        drag(T, city, S)
        drag(T, city, D)
        cap_ends(T, city, S)
        cap_ends(T, city, D)
        lay = T.layer(4)
        found = detect(lay)
        tag = "case %s r%d, cap on the last joining cell of %s%s" % (case, r, "/".join(arms),
                                                                    " (%s)" % mode if mode else "")
        if found != [(O, case, r % 2)]:
            print("FAIL %s: detect -> %s" % (tag, found))
            bad += 1
            continue
        res = place(lay, city, O, case, r)
        pl = res["placements"]
        mv = movements(pl, O, case, r, tabs)
        miss = [k for k in need if not mv[k]]
        caps_in = [w for w, v in pl.items() if v[3] != "capjoin" and lay.get(w) is not None and
                   lay[w].id in hwcap.CAP_IDS]
        grown = [w for w, v in pl.items() if v[3] in ("att", "capjoin", "core") and lay.get(w) is None]
        capj = [(w, v[0], v[1]) for w, v in pl.items() if v[3] == "capjoin"]
        want_cap = len(arms) if mode is None else 0 if mode == "short" else 1
        qs = {"O2": "O2", "O1": "O1"}.get(mode)
        ok = len(res["built"]) == want and (want < 4 or not miss) and not caps_in and not grown and \
            len(capj) == want_cap and (qs is None or any(b.startswith(qs) for b in res["built"]))
        print("%s %-58s built %s refused %s; capped joins %s; %d cells%s%s" % (
            "ok  " if ok else "FAIL", tag, ",".join(res["built"]), sorted(res["refused"]) or "-", capj or "-",
            len(pl), (" MISSING " + ", ".join("%s->%s" % k for k in miss)) if miss and want == 4 else "",
            " WROTE INTO EMPTY CELLS %s" % grown if grown else ""))
        if res["refused"]:
            print("       why: %s" % res["refused"])
        bad += 0 if ok else 1
    return bad


# ------------------------------------------------------------------------------------------------ capped joins (hwcap)
# When a diagonal arm's stock end cap sits ON its last joining cell (the middle (6, 6) / (-7, -7) of case A, (6, -7) /
# (-7, 6) of case B) and the arm cannot be carried on (the land past the end takes no highway: Seoul's lake), that
# cell gets a CAPPED JOIN: the join piece's content with the diagonal ending at the cap line (the cell's anti-diagonal,
# where the stock cap 14999 / 15059 ends it) and hwpaint's stock end face there. The ramp that joins there (R4 / R2)
# has merged before that line (R4 centreline ends at x + z = 12.80, the line is 13). Base = the stock cap, and the piece
# sits at the cap's own state (painted at the turn where that cap is state 0), so saves and the stock tiler see the
# stock end. Straight arms get none: their cap is a two-lane row whose stock art is not decoded (frame 0 of 15053 is a
# flat 60 x 31 tile), so a straight arm that cannot be carried on still drops the quadrant.
CAP_CELLS = {"A": (6, 6), "B": (6, -7)}        # (-7, -7) / (-7, 6): the same class turned twice
CAP_ID0 = 21532
# task hwcap2: the straight arms' last joining cells (the +x side; the -x side is the same class turned twice): case A
# A1's (9, 0) and O2's (6, -1), case B A1''s (9, -1) and O2''s (6, 0). The cap row there is both lanes; only the joining
# lane's cell gets a capped join (the other lane's cell is plain highway and keeps the stock cap).
CAP_CELLS_S = {"A": ((9, 0), (6, -1)), "B": ((9, -1), (6, 0))}


def _lane_lower(c, case, r):
    """is the straight-arm cell c (case frame, row -1 / 0) the lower lane in the world at rotation r"""
    w = to_world((0, 0), r, c)
    p = to_world((0, 0), r, (c[0], -1 - c[1]))
    st = arm_step(c, case, r)
    return w[1] < p[1] if st[1] == 0 else w[0] < p[0]


def capped_list():
    """[dict(id, cls, flavour, case, cell, r, base, scap)] - one capped join per class and flavour whose cell can hold
    an arm's end: the diagonal families' (task hwcap, ids 21532..21535) and the straight arms' (task hwcap2, from
    21536). r = the crossing rotation (parity = flavour) at which the stock cap on the rep cell has state 0 (paint and
    cut lanes there). scap = how the painted scene ends that arm: True = the diagonal on its cap line, ("S", e) = the
    straight's +x end at x = e"""
    cmap, info = classes()
    idm, n, pool = ids()
    out = []
    k = 0
    cells = [(fl, case, c, True) for fl in (0, 1) for case in ("A", "B") for c in (CAP_CELLS[case],)] + \
        [(fl, case, c, ("S", c[0] + 1)) for case in ("A", "B") for c in CAP_CELLS_S[case] for fl in (0, 1)]
    for fl, case, c, scap in cells:
        cls = cmap[(case, c)][0]
        for r in (fl, fl + 2):
            step = arm_step(c, case, r)
            cap = hwcap.cap_of(step, True if scap is True else _lane_lower(c, case, r))
            if cap[1] == 0:
                break
        pid = CAP_ID0 + k
        if pid > ID_RANGES[-1][1] or pid in idm.values():
            raise SystemExit("capped join id %d is not free" % pid)
        out.append(dict(id=pid, cls=cls, flavour=fl, case=case, cell=c, r=r, base=cap[0], scap=scap))
        k += 1
    return out


def capped_flows(cp, tabs=None):
    """task hwcap2: a straight capped join's turns at state 0 (the rep cell at rotation r): the join's turns with the
    outward side replaced by the side toward the row's other lane (the stock cap's U-turn)"""
    tabs = tabs or {"A": case_table("A"), "B": case_table("B")}
    c, case, r = cp["cell"], cp["case"], cp["r"]
    out_side = {v: k_ for k_, v in SIDE_D.items()}[arm_step(c, case, r)]
    w, p = to_world((0, 0), r, c), to_world((0, 0), r, (c[0], -1 - c[1]))
    part = {v: k_ for k_, v in SIDE_D.items()}[(p[0] - w[0], p[1] - w[1])]
    fl = set()
    for n_, e, l_ in tabs[case][c]["flows"]:
        if not (e and l_):
            continue
        e, l_ = rot_side(e, r), rot_side(l_, r)
        e, l_ = (part if e == out_side else e), (part if l_ == out_side else l_)
        if e != l_:
            fl.add((e, l_))
    return sorted(fl)


QUAD_IX = {"A1": 0, "A2": 1, "O1": 2, "O2": 3, "A1'": 0, "A2'": 1, "O1'": 2, "O2'": 3}


def pieces_list():
    """[dict(id, cls, flavour, base, land, rep=(case, cell), r, state0_rot, flows)] - one per id. `r` is a crossing
    rotation at which the rep cell's piece sits at state 0 (paint the art there); `flows` = the rep's turn sides
    turned to the piece's state 0."""
    cmap, info = classes()
    idm, _, _ = ids()
    tabs = {"A": case_table("A"), "B": case_table("B")}
    out = []
    for (cls, f), pid in sorted(idm.items(), key=lambda t: t[1]):
        case, c = info[cls]["rep"]
        cs = cmap[(case, c)][1]
        bid, off = base_of(info[cls], f)
        k = (-(cs + off)) % 4                               # state-0 content = rep content turned k times
        r = k if info[cls]["flavoured"] else k              # crossing rotation that puts the rep at state 0
        if info[cls]["flavoured"] and r % 2 != f:
            raise SystemExit("piece %d: flavour %d but state-0 rotation %d" % (pid, f, r))
        fl = [(rot_side(e, k), rot_side(l, k)) for n, e, l in tabs[case][c]["flows"] if e and l]
        out.append(dict(id=pid, cls=cls, flavour=f, base=bid, land=info[cls]["kind"] == "ramp", rep=(case, c), r=r,
                        flows=sorted(set(fl)), kind=info[cls]["kind"]))
    for cp in capped_list():                                 # tasks hwcap / hwcap2: capped joins, painted at their own turn
        fl = list(CAP_MATRIX[cp["base"]]) if cp["scap"] is True else capped_flows(cp, tabs)
        out.append(dict(id=cp["id"], cls=cp["cls"], flavour=cp["flavour"], base=cp["base"], land=False,
                        rep=(cp["case"], cp["cell"]), r=cp["r"], flows=fl, kind="capjoin", capped=cp["scap"]))
    return out


# the stock caps' turn matrix at state 0 (`lanekit show`, low half; the high half is it reversed): a U-turn between
# the cap's two open sides. The capped join keeps it: the joining ramp enters from the same side as its carriageway.
CAP_MATRIX = {14999: [("z+", "x+")], 15059: [("x-", "z+")]}


# Stock one-lane ramp pieces a land piece saves as in a game without the mod (hwcore's `hwys` lines): state-0 turn
# (lanekit show, low half). Curves first (15127 / 15128 are the arcs), then the corners, then the straight strips.
SAVE_STOCK = [(15127, ("x+", "z+")), (15128, ("z+", "x-")), (15123, ("z-", "x-")), (15124, ("x-", "z+")),
              (15125, ("x+", "z-")), (15126, ("z-", "x-")), (15134, ("x+", "x-")), (15135, ("x-", "x+")),
              (15136, ("z+", "z-")),
              (15137, ("z-", "z+"))]


def save_as(flows):
    """-> [(stock id, state)] for states 0..3 of a land piece whose state-0 turn sides are `flows`: the stock ramp
    piece and state whose turn matches the most of the piece's turns (directed, then by sides), curves preferred"""
    out = []
    for st in range(4):
        mine = {(rot_side(e, st), rot_side(l, st)) for e, l in flows}
        sides = {x for f in mine for x in f}
        best = None
        for rank, (pid, (e0, l0)) in enumerate(SAVE_STOCK):
            for k in (0, 2):         # the shipped cities place 15123..15141 at states 0 and 2 only (hwcore, 16 cities)
                t = (rot_side(e0, k), rot_side(l0, k))
                score = (2 * (t in mine) + len(sides & set(t)), -rank)
                if best is None or score > best[0]:
                    best = (score, pid, k)
        out.append((best[1], best[2]) if mine else ((15134, 0) if st % 2 == 0 else (15136, 0)))   # deck edge only
    return out


def cmd_package(a):
    """write examples/<package>/manifest.json (art and lane specs come from hwdx_paint.py art / lanes)"""
    import json
    P = pieces_list()
    variants, connects, lines = [], [], []
    for p in P:
        what = {"core": "crossing", "att": "ramp join", "ramp": "ramp", "capjoin": "ramp join, highway end"}[p["kind"]]
        variants.append({"id": p["id"], "base": p["base"], "network": "HWAY",
                         "name": {"*": "Highway interchange (%s)" % what},
                         # the program's ground rule (HWY_BASE.md): frame table from stock 15127, ground_under, frames
                         # padded to the full cell diamond (hwdx_paint.py pad)
                         "art": {"from": 15127, "png_dir": "art/%d" % p["id"], "ground_under": True},
                         "trblkatt": "copy_base"})
        connects.append({"piece": p["id"], "spec": "lanes/%d.json" % p["id"]})   # lanes + turn matrix (hwdx_paint lanes)
        lines.append("hwyp %d %d" % (p["id"], 1 if p["land"] else 0))
        if p["land"]:                                   # saved as a stock one-lane ramp piece in a game without the mod
            lines.append("hwys %d %s" % (p["id"], " ".join("%d %d" % t for t in save_as(p["flows"]))))
    man = {"netpack": 1, "name": "highway_diagonal_cloverleaf", "version": "0.1.0", "author": "sc3kre",
           "description": "Task hwdx: a diagonal highway crossing a straight highway at 45 degrees becomes a skewed "
                          "cloverleaf (the straight bridges over the diagonal; four loops for the left turns, four "
                          "outer ramps for the right turns), per quadrant where the land is free. Rule in "
                          "sc3netmod_hwdx.c, tables from re/tools/netmod/hwdx.py, art from hwdx_paint.py.",
           "game": {"Apps/SIMNTWRK.DLL": "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"},
           "variants": variants, "lanes": connects, "highway_lines": lines}
    os.makedirs(a.dir, exist_ok=True)
    out = os.path.join(a.dir, "manifest.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(man, fh, indent=1)
        fh.write("\n")
    print("wrote", out, "(%d variants)" % len(variants))


def cmd_ctab(a):
    """write the block's tables (re/harness/src/sc3netmod_hwdx_tab.h)"""
    cmap, info = classes()
    idm, n, pool = ids()
    L = ["/* sc3netmod_hwdx_tab.h - generated by re/tools/netmod/hwdx.py ctab (task hwdx). Do not edit: regenerate. */",
         "/* classes: id / base / state offset per flavour (0 = straight along x, 1 = along z; id 0 = none) */",
         "#define HWDX_NCLS %d" % len(info),
         "static const WORD g_hwdx_id[HWDX_NCLS][2] = {"]
    for cls in range(len(info)):
        L.append("    {%d, %d}," % (idm[(cls, 0)], idm.get((cls, 1), 0)))
    L.append("};")
    L.append("static const WORD g_hwdx_base[HWDX_NCLS][2] = {")
    for cls in range(len(info)):
        b0 = base_of(info[cls], 0)[0]
        b1 = base_of(info[cls], 1)[0] if info[cls]["flavoured"] else 0
        L.append("    {%d, %d}," % (b0, b1))
    L.append("};")
    L.append("static const BYTE g_hwdx_soff[HWDX_NCLS][2] = {")
    for cls in range(len(info)):
        L.append("    {%d, %d}," % (base_of(info[cls], 0)[1], base_of(info[cls], 1)[1] if info[cls]["flavoured"] else 0))
    L.append("};")
    capm = {(cp["cls"], cp["flavour"]): cp for cp in capped_list()}
    L.append("/* task hwcap: capped join per class and flavour (0 = none) and the stock cap it stands for (its base) */")
    L.append("static const WORD g_hwdx_cap[HWDX_NCLS][2][2] = {")
    for cls in range(len(info)):
        L.append("    {%s}," % ", ".join("{%d, %d}" % ((capm[(cls, f)]["id"], capm[(cls, f)]["base"]) if (cls, f) in capm
                                                      else (0, 0)) for f in (0, 1)))
    L.append("};")
    L.append("/* cells of a case frame: i, j, kind (0 core, 1 joins a highway, 2 ramp alone), quadrant (0 A1, 1 A2, 2 O1,"
             " 3 O2; 255 core), class, state in the case frame */")
    L.append("typedef struct { signed char i, j; BYTE kind, quad; WORD cls; BYTE cs; } HwdxCell;")
    for case in ("A", "B"):
        tab = case_table(case)
        cells = sorted(tab, key=lambda c: (tab[c]["kind"] != "core", c[1], c[0]))
        L.append("#define HWDX_N%s %d" % (case, len(cells)))
        L.append("static const HwdxCell g_hwdx_%s[HWDX_N%s] = {" % (case, case))
        for c in cells:
            d = tab[c]
            cls, cs = cmap[(case, c)]
            q = 255 if d["kind"] == "core" else QUAD_IX[next(iter(d["quadrant"]))]
            L.append("    {%d, %d, %d, %d, %d, %d}," % (c[0], c[1], {"core": 0, "att": 1, "ramp": 2}[d["kind"]], q,
                                                    cls, cs))
        L.append("};")
    L.append("/* the stock aftermath, case A frame (case B: j -> -1 - j): i, j, role (0 = 15149, 1 = band middle, "
             "2 = straight) */")
    L.append("static const signed char g_hwdx_after[%d][3] = {" % len(AFTER_A))
    L.append("    " + ", ".join("{%d, %d, %d}" % (i, j, {"c": 0, "m": 1, "s": 2}[r]) for (i, j), r in
                                sorted(AFTER_A.items())) + "};")
    out = a.out
    open(out, "w", newline="\n").write("\n".join(L) + "\n")
    print("wrote", out, "(%d classes, %d ids)" % (len(info), n))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("table")
    p.add_argument("--case", default="A")
    p.set_defaults(fn=cmd_table)
    p = sub.add_parser("ids")
    p.set_defaults(fn=cmd_ids)
    p = sub.add_parser("package")
    p.add_argument("dir")
    p.set_defaults(fn=cmd_package)
    p = sub.add_parser("ctab")
    p.add_argument("out")
    p.set_defaults(fn=cmd_ctab)
    p = sub.add_parser("check")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(fn=cmd_check)
    a = ap.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
