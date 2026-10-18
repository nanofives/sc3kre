#!/usr/bin/env python3
r"""hwt_layout.py - the connecting highway T (stream hwt, 2026-10-18): layout generator + rule twin (pure Python).

  py -3.12 hwt_layout.py show [--loop 3|2] [--rio]      print the layout grid (stem frame) and the cell list
  py -3.12 hwt_layout.py match CITY.sc3 [--loop N]      run the rule on a save's surface layer, print every T found
  py -3.12 hwt_layout.py selftest                        layouts + the rule on the stock grids measured in game

Plan and the stock measurements: verify/hwt/README.md. Stem frame (state 0): stem arrives from -z, SB column x 0 (runs -z),
NB column x 1 (runs +z), through highway rows z 0 (EB, runs +x) and z 1 (WB, runs -x). Rotation r maps a frame cell to
world  A + R^r(x, z)  with  R(x, z) = (-z, x),  and a state s to (s + r) % 4 (NET_LANES.md 1.1: at state s, local side c is
world side (c + s) % 4; sides 0 x-, 1 z-, 2 x+, 3 z+). Checked against the stock grids: r 0 = stem from -z, r 2 = from +z.

Layouts
  full, loop L (2 or 3): the trumpet. The ring of the loop is columns 1..L, rows 2..L+1 (the cell where NB comes down off
  the bridge is its first cell); the outer ramp runs in column L+1 and row L+2. Box x -1..L+1, z -2..L+2.
  rio: right-in / right-out only (NB -> EB, EB -> SB); the stem keeps its stock caps at z -1. Box x -1..2, z -2..1.

Rule (both gestures, every rotation, every anchor):
  gesture 1  frame (0,-1) = cap 11235, (1,-1) = cap 11237; stem straight at z -2 and -3; through highway straight in rows
             0 and 1 from x -2 to the box's right edge + 1.
  gesture 2  the stub X: stock X centre 15113/15114 at (0..1, 0..1); arms 15150/15153 at (0..1, -1) and (0..1, 2),
             15107/15108 at (-1, 0..1) and (2, 0..1); stem straight at z -2 and -3; NO highway at (0..1, 3); through
             highway straight at x -2 and x 3..(right edge + 1). (hwx takes an X only when all four arms continue.)
  then       every new cell is free (no surface occupant, no building) and flat when a height map is given; no other
             highway touches a new cell from outside the box. Full layout first, rio when only the far side fails
             (gesture 1 only: gesture 2's stub stays stock). Overlapping finds: the first in scan order wins.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Ramp geometry shared with the cloverleaf X (stream hwx): deck half width, outer lane offset, loop centreline radius,
# gap between ramp decks. Read from hwx.py when it is importable (on main after the merge); else the values hwx sent on
# 2026-10-18 (Simcity_wt_hwx/re/tools/netmod/hwx.py lines 27-34). S tapers there are 0.5..0.6 cell long.
try:
    import hwx as _hwx
    GEOM = {"W": _hwx.W, "LANE_OUT": _hwx.LANE_OUT, "R_LOOP": _hwx.R_LOOP, "GAP": _hwx.GAP, "from": "hwx.py"}
except (ImportError, AttributeError):
    GEOM = {"W": 0.31, "LANE_OUT": 0.57, "R_LOOP": 1.25, "GAP": 0.19, "from": "hwx 2026-10-18 values (W 0.31 = hwpaint.RAMP_W / 2)"}

# ids (verify/hwt/README.md 2)
EXIT, UNDER_A, UNDER_B, ENTRY = 21200, 21201, 21202, 21203
STEM_DOWN, STEM_UP, FAR_DOWN, FAR_UP = 21204, 21205, 21206, 21207
STEM_ENTRY, STEM_EXIT = 21208, 21209
RAMP, CURVE_R, CURVE_L = 21210, 21211, 21212
STEM_ENTRY_END, STEM_EXIT_END = 21213, 21214          # rio: stem entry / exit whose through arm is closed (cap beyond)
IDS = range(21200, 21215)

# ramp heading <-> state: 0 N (+z), 1 W (-x), 2 S (-z), 3 E (+x)
N, Wd, S, Ed = 0, 1, 2, 3

# turn matrix per piece at state 0: {(enter side, leave side)}, sides 0 x-, 1 z-, 2 x+, 3 z+ (NET_LANES.md 1.1).
# "enter by side f, may leave by side t". The build writes these as props 310 (both halves, high = transpose).
CONNECTS = {
    EXIT: {(0, 2), (0, 1)},            # EB through + exit to z- (the ramp)
    UNDER_A: {(0, 2), (3, 1)},         # EB through, SB passing over (other level)
    UNDER_B: {(0, 2), (1, 3)},         # EB through, NB passing over
    ENTRY: {(0, 2), (1, 2)},           # EB through + ramp joining from z-
    STEM_DOWN: {(3, 1)}, STEM_UP: {(1, 3)}, FAR_DOWN: {(1, 3)}, FAR_UP: {(3, 1)},
    STEM_ENTRY: {(3, 1), (0, 1)},      # SB through + ramp joining from x-
    STEM_EXIT: {(1, 3), (1, 2)},       # NB through + exit to x+
    RAMP: {(1, 3)}, CURVE_R: {(1, 2)}, CURVE_L: {(1, 0)},
    STEM_ENTRY_END: {(0, 1)}, STEM_EXIT_END: {(1, 2)},
}
SIDE = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}


def connects(pid, st):
    return {((f + st) % 4, (t + st) % 4) for f, t in CONNECTS[pid]}


def reach(loop=3, rio=False):
    """Route every movement through the frame layout (plain straight highway around it). -> {source: set of sinks}."""
    lay, _ = layout(loop, rio)
    x0, z0, x1, z1 = box(lay)
    cells = {k: connects(p, st) for k, (p, st, _) in lay.items()}
    for x in range(x0 - 2, x1 + 3):
        cells.setdefault((x, 0), {(0, 2)})
        cells.setdefault((x, 1), {(2, 0)})
    for z in range(z0 - 2, 0):
        if rio and z == -1:
            continue                               # the stock caps: dead ends
        cells.setdefault((0, z), {(3, 1)})
        cells.setdefault((1, z), {(1, 3)})
    srcs = {"NB": ((1, z0 - 2), 1), "EB": ((x0 - 2, 0), 0), "WB": ((x1 + 2, 1), 2)}
    out = {}
    for name, start in srcs.items():
        seen, todo, sinks = set(), [start], set()
        while todo:
            cell, f = todo.pop()
            if (cell, f) in seen:
                continue
            seen.add((cell, f))
            for ff, t in cells.get(cell, ()):
                if ff != f:
                    continue
                d = SIDE[t]
                n = (cell[0] + d[0], cell[1] + d[1])
                if n not in cells:
                    sinks.add("EB" if t == 2 and cell[1] == 0 else "WB" if t == 0 and cell[1] == 1
                              else "SB" if t == 1 and cell[0] == 0 else "?%s,%d" % (cell, t))
                    continue
                todo.append((n, (t + 2) % 4))
        out[name] = sinks
    return out


CAPS = (11235, 11237)
X_CENTRE = (15113, 15114)
X_ARM_Z = (15150, 15153)
X_ARM_X = (15107, 15108)


def layout(loop=3, rio=False):
    """{(x, z): (id, state, role)} in the stem frame, and the set of NEW cells (not highway before)."""
    c = {}
    new = set()

    def put(x, z, pid, st, role="", fresh=False):
        c[(x, z)] = (pid, st % 4, role)
        if fresh:
            new.add((x, z))

    # stem side, both layouts
    put(-1, 0, EXIT, 0, "EB exit")
    put(2, 0, ENTRY, 0, "EB entry")
    put(-1, -1, RAMP, S, "EB->SB", True)
    put(-1, -2, CURVE_L, 2, "EB->SB", True)              # heading S, turns E
    put(2, -2, CURVE_L, 3, "NB->EB", True)               # heading E, turns N
    put(2, -1, RAMP, N, "NB->EB", True)
    if rio:
        put(0, -2, STEM_ENTRY_END, 0, "SB entry (end)")
        put(1, -2, STEM_EXIT_END, 0, "NB exit (end)")
        return c, new
    put(0, -2, STEM_ENTRY, 0, "SB entry")
    put(1, -2, STEM_EXIT, 0, "NB exit")
    put(0, -1, STEM_DOWN, 0, "SB down")
    put(1, -1, STEM_UP, 0, "NB up")
    put(0, 0, UNDER_A, 0, "EB under SB")
    put(1, 1, UNDER_A, 2, "WB under NB")
    put(1, 0, UNDER_B, 0, "EB under NB")
    put(0, 1, UNDER_B, 2, "WB under SB")
    L = loop
    # loop: up column 1, across row L+1, down column L, into WB at (L, 1)
    put(1, 2, FAR_DOWN, 0, "down to loop", True)
    for z in range(3, L + 1):
        put(1, z, RAMP, N, "loop", True)
    put(1, L + 1, CURVE_R, 0, "loop", True)              # N -> E
    for x in range(2, L):
        put(x, L + 1, RAMP, Ed, "loop", True)
    put(L, L + 1, CURVE_R, 3, "loop", True)              # E -> S
    for z in range(L, 1, -1):
        put(L, z, RAMP, S, "loop", True)
    put(L, 1, ENTRY, 2, "WB entry")
    # outer ramp: WB exit at (L+1, 1), up column L+1, west along row L+2, down column 0, up onto the bridge at (0, 2)
    put(L + 1, 1, EXIT, 2, "WB exit")
    for z in range(2, L + 2):
        put(L + 1, z, RAMP, N, "outer", True)
    put(L + 1, L + 2, CURVE_L, 0, "outer", True)         # N -> W
    for x in range(L, 0, -1):
        put(x, L + 2, RAMP, Wd, "outer", True)
    put(0, L + 2, CURVE_L, 1, "outer", True)             # W -> S
    for z in range(L + 1, 2, -1):
        put(0, z, RAMP, S, "outer", True)
    put(0, 2, FAR_UP, 0, "up to bridge", True)
    return c, new


def box(cells):
    xs = [x for x, _ in cells]
    zs = [z for _, z in cells]
    return min(xs), min(zs), max(xs), max(zs)


def rot(x, z, r):
    for _ in range(r % 4):
        x, z = -z, x
    return x, z


def world(a, r, cell):
    dx, dz = rot(cell[0], cell[1], r)
    return a[0] + dx, a[1] + dz


# straight stock highway: id/state -> heading vector
def heading(p):
    if p is None:
        return None
    pid, st = p
    if pid == 15051:
        return {2: (1, 0), 0: (-1, 0)}.get(st)
    if pid == 73:
        return {0: (0, 1), 2: (0, -1)}.get(st)
    return None


def want(r, v):
    return rot(v[0], v[1], r)


EB, WB, NB, SB = (1, 0), (-1, 0), (0, 1), (0, -1)


class Grid:
    """surface layer {(x, z): (id, state)} + optional buildings [(x0, z0, w, h)] + optional flat(x, z)."""

    def __init__(self, cells, buildings=(), flat=None):
        self.c = dict(cells)
        self.b = set()
        for (x0, z0, w, h) in buildings:
            for x in range(x0, x0 + w):
                for z in range(z0, z0 + h):
                    self.b.add((x, z))
        self.flat = flat

    def get(self, xz):
        return self.c.get(xz)

    def free(self, xz):
        return xz not in self.c and xz not in self.b and (self.flat is None or self.flat(*xz))

    def is_hwy(self, xz):
        p = self.c.get(xz)
        return p is not None and (heading(p) is not None or p[0] in CAPS + X_CENTRE + X_ARM_Z + X_ARM_X
                                  or 11223 <= p[0] <= 21459 and p[0] in HWY_IDS)


HWY_IDS = {73, 11223, 11224, 11235, 11237, 14094, 14999, 15051, 15052, 15053, 15054, 15059, 15106, 15149}
HWY_IDS |= set(range(15099, 15154)) | set(range(21100, 21460))


def _straight(g, a, r, cells_dirs, why, tag):
    for cell, d in cells_dirs:
        w = world(a, r, cell)
        if heading(g.get(w)) != want(r, d):
            why.append("%s %s=%s not straight %s" % (tag, w, g.get(w), want(r, d)))
            return False
    return True


def check(g, a, r, gesture, loop):
    """-> (layout name, frame cells, new cells) or (None, reasons)."""
    why = []
    # stem behind the end
    if not _straight(g, a, r, [((0, -2), SB), ((1, -2), NB), ((0, -3), SB), ((1, -3), NB)], why, "stem"):
        return None, why
    if gesture == 1:
        if g.get(world(a, r, (0, -1))) is None or g.get(world(a, r, (0, -1)))[0] != 11235 \
                or g.get(world(a, r, (1, -1))) is None or g.get(world(a, r, (1, -1)))[0] != 11237:
            return None, ["no cap pair"]
        core = [(x, z) for x in range(-1, 2 + 1) for z in (0, 1)]
    else:
        pat = {(0, 0): X_CENTRE, (1, 0): X_CENTRE, (0, 1): X_CENTRE, (1, 1): X_CENTRE,
               (0, -1): X_ARM_Z, (1, -1): X_ARM_Z, (0, 2): X_ARM_Z, (1, 2): X_ARM_Z,
               (-1, 0): X_ARM_X, (-1, 1): X_ARM_X, (2, 0): X_ARM_X, (2, 1): X_ARM_X}
        for cell, ids in pat.items():
            p = g.get(world(a, r, cell))
            if p is None or p[0] not in ids:
                return None, ["not a stock X"]
        for cell in ((0, 3), (1, 3)):
            if g.is_hwy(world(a, r, cell)):
                return None, ["far arm continues: a full X (hwx)"]
        core = []
    for name, lay, nw in (("full", *layout(loop)), ("rio", *layout(loop, rio=True))):
        if name == "rio" and gesture == 2:
            break
        bx0, bz0, bx1, bz1 = box(lay)
        lane = [((x, 0), EB) for x in range(-2, bx1 + 2) if (x, 0) not in core and not (gesture == 2 and -1 <= x <= 2)]
        lane += [((x, 1), WB) for x in range(-2, bx1 + 2) if (x, 1) not in core and not (gesture == 2 and -1 <= x <= 2)]
        w2 = []
        if not _straight(g, a, r, lane, w2, "through"):
            why += [name + ": " + s for s in w2]
            continue
        if gesture == 1 and not _straight(g, a, r, [((x, z), EB if z == 0 else WB) for (x, z) in core],
                                          w2, "through"):
            why += [name + ": " + s for s in w2]
            continue
        if gesture == 2:                           # the stub arm cells hold the X arm: they are rewritten, not claimed
            nw = set(nw) - {(0, 2), (1, 2)}
        bad = [world(a, r, c) for c in nw if not g.free(world(a, r, c))]
        if bad:
            why.append("%s: cells not free %s" % (name, bad[:4]))
            continue
        touch = []
        for c in nw:
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c[0] + d[0], c[1] + d[1])
                if n not in lay and not (n[1] in (0, 1) or n[0] in (0, 1) and n[1] < 0) and g.is_hwy(world(a, r, n)):
                    touch.append(world(a, r, n))
        if touch:
            why.append("%s: other highway touches %s" % (name, touch[:4]))
            continue
        return (name, lay, nw), why
    return None, why


def find(g, loop=3):
    """Every T in the grid: [(gesture, anchor, r, layout name, {world cell: (id, state, role)})]."""
    out, taken = [], set()
    seen = set()
    for (x, z), p in sorted(g.c.items()):
        if p[0] == 11235:
            cands = [(1, r) for r in range(4)]
        elif p[0] in X_CENTRE:
            cands = [(2, r) for r in range(4)]
        else:
            continue
        for gesture, r in cands:
            a = (x, z) if gesture == 2 else None
            if gesture == 1:                       # the cap 11235 is frame (0, -1)
                d = rot(0, -1, r)
                a = (x - d[0], z - d[1])
            key = (gesture, a, r)
            if key in seen:
                continue
            seen.add(key)
            res, why = check(g, a, r, gesture, loop)
            if res is None:
                continue
            name, lay, nw = res
            cells = {world(a, r, c): (pid, (st + r) % 4, role) for c, (pid, st, role) in lay.items()}
            if set(cells) & taken:
                continue
            taken |= set(cells)
            out.append((gesture, a, r, name, cells))
    return out


def show(loop, rio):
    lay, nw = layout(loop, rio)
    x0, z0, x1, z1 = box(lay)
    for z in range(z1, z0 - 1, -1):
        print("%3d " % z + " ".join(("%5d.%d%s" % (lay[(x, z)][0], lay[(x, z)][1], "*" if (x, z) in nw else " "))
                                    if (x, z) in lay else "   .    " for x in range(x0, x1 + 1)))
    print("    " + " ".join("%7d " % x for x in range(x0, x1 + 1)))
    print("box x %d..%d z %d..%d, %d cells, %d new (*)" % (x0, x1, z0, z1, len(lay), len(nw)))


# stock grids measured in game 2026-10-18 (verify/hwt/README.md 1), rebuilt from the drag results
def stock_cap_from_minus_z():
    c = {}
    for x in range(45, 71):
        c[(x, 27)], c[(x, 28)] = (15051, 2), (15051, 0)
    c[(45, 27)], c[(45, 28)], c[(70, 27)], c[(70, 28)] = (15053, 0), (15054, 0), (15054, 2), (15053, 2)
    for z in range(16, 26):
        c[(49, z)], c[(50, z)] = (73, 2), (73, 0)
    c[(49, 15)], c[(50, 15)], c[(49, 26)], c[(50, 26)] = (11237, 2), (11235, 2), (11235, 0), (11237, 0)
    return c


def stock_cap_from_plus_z():
    c = {}
    for x in range(45, 71):
        c[(x, 27)], c[(x, 28)] = (15051, 2), (15051, 0)
    for z in range(30, 38):
        c[(66, z)], c[(67, z)] = (73, 2), (73, 0)
    c[(66, 29)], c[(67, 29)], c[(66, 38)], c[(67, 38)] = (11237, 2), (11235, 2), (11235, 0), (11237, 0)
    return c


def stock_stub_x():
    c = {}
    for x in range(95, 115):
        c[(x, 87)], c[(x, 88)] = (15051, 2), (15051, 0)
    c.update({(100, 87): (15113, 2), (101, 87): (15114, 0), (100, 88): (15114, 2), (101, 88): (15113, 0),
              (99, 87): (15107, 0), (99, 88): (15108, 0), (102, 87): (15108, 2), (102, 88): (15107, 2),
              (100, 86): (15150, 2), (101, 86): (15153, 2), (100, 89): (15153, 0), (101, 89): (15150, 0)})
    for z in range(90, 98):
        c[(100, z)], c[(101, z)] = (73, 2), (73, 0)
    c[(100, 98)], c[(101, 98)] = (11235, 0), (11237, 0)
    return c


PIECE_OF = {(1, 0): (15051, 2), (-1, 0): (15051, 0), (0, 1): (73, 0), (0, -1): (73, 2)}


def synth_cap(a, r):
    """The gesture-1 scene built in the frame and rotated: through highway x -8..10, stem z -10..-2, caps at z -1."""
    c = {}
    for x in range(-8, 11):
        c[world(a, r, (x, 0))] = PIECE_OF[want(r, EB)]
        c[world(a, r, (x, 1))] = PIECE_OF[want(r, WB)]
    for z in range(-10, -1):
        c[world(a, r, (0, z))] = PIECE_OF[want(r, SB)]
        c[world(a, r, (1, z))] = PIECE_OF[want(r, NB)]
    c[world(a, r, (0, -1))], c[world(a, r, (1, -1))] = (11235, 0), (11237, 0)
    return c


def selftest():
    ok = True

    def t(cond, msg):
        nonlocal ok
        print(("ok   " if cond else "FAIL ") + msg)
        ok &= bool(cond)

    for L in (2, 3):
        lay, nw = layout(L)
        t(box(lay) == (-1, -2, L + 1, L + 2), "loop %d box %s" % (L, box(lay)))
        t(set(p for p, _, _ in lay.values()) <= set(IDS), "loop %d ids in range" % L)
    lay2, nw2 = layout(2)
    t(len(nw2) == 16, "loop 2: 16 new cells (verify/hwt/README.md)")
    lay3, nw3 = layout(3)
    t(len(nw3) == 22, "loop 3: 22 new cells")
    for L in (2, 3):
        rr = reach(L)
        t(rr == {"NB": {"EB", "WB"}, "EB": {"EB", "SB"}, "WB": {"WB", "SB"}}, "loop %d: every movement routes %s" % (L, rr))
    rr = reach(2, rio=True)
    t(rr == {"NB": {"EB"}, "EB": {"EB", "SB"}, "WB": {"WB"}}, "rio: right-in/right-out routes %s" % rr)
    g = Grid(stock_cap_from_minus_z())
    f = find(g)
    t(len(f) == 1 and f[0][:4] == (1, (49, 27), 0, "full"), "gesture 1 stem from -z: %s" % [x[:4] for x in f])
    if f:
        cells = f[0][4]
        t(cells[(49, 26)][0] == STEM_DOWN and cells[(50, 26)][0] == STEM_UP, "caps become the stem level change")
        t(cells[(48, 27)][:2] == (EXIT, 0), "EB exit at (48,27) state 0")
    g = Grid(stock_cap_from_plus_z())
    f = find(g)
    t(len(f) == 1 and f[0][:4] == (1, (67, 28), 2, "full"), "gesture 1 stem from +z: %s" % [x[:4] for x in f])
    if f:
        t(f[0][4][(68, 28)][:2] == (EXIT, 2), "EB-frame exit lands on the -x row z 28 at x 68, state 2")
    g = Grid(stock_stub_x())
    f = find(g)
    t(len(f) == 1 and f[0][:4] == (2, (101, 88), 2, "full"), "gesture 2 stub X: %s" % [x[:4] for x in f])
    for r in range(4):
        f = find(Grid(synth_cap((60, 60), r)))
        t(len(f) == 1 and f[0][:4] == (1, (60, 60), r, "full"), "synthetic cap scene rot %d: %s" % (r, [x[:4] for x in f]))
    # full X -> refused
    c = stock_stub_x()
    for z in range(83, 86):
        c[(100, z)], c[(101, z)] = (73, 2), (73, 0)
    t(find(Grid(c)) == [], "full X refused (hwx)")
    # far side blocked -> rio
    g = Grid(stock_cap_from_minus_z(), buildings=[(50, 31, 1, 1)])     # frame (1, 4): on the loop ring
    f = find(g)
    t(len(f) == 1 and f[0][3] == "rio", "far side blocked by a building -> rio: %s" % [x[:4] for x in f])
    # stem side blocked -> refused
    g = Grid(stock_cap_from_minus_z(), buildings=[(48, 25, 1, 1)])
    t(find(g) == [], "stem side blocked -> refused")
    # far side blocked on a stub X -> refused (stub stays stock)
    g = Grid(stock_stub_x(), buildings=[(99, 84, 1, 1)])
    t(find(g) == [], "stub X with far side blocked -> refused")
    # loop 3 on the cap case
    f = find(Grid(stock_cap_from_minus_z()), loop=2)
    t(len(f) == 1 and f[0][3] == "full", "loop 2 (switch) fits the cap case")
    # stem too short
    c = stock_cap_from_minus_z()
    for z in range(15, 24):
        del c[(49, z)], c[(50, z)]
    c[(49, 24)], c[(50, 24)] = (11237, 2), (11235, 2)
    t(find(Grid(c)) == [], "stem shorter than 3 refused")
    print("selftest", "PASSED" if ok else "FAILED")
    return 0 if ok else 1


def match_save(path, loop):
    sys.path.insert(0, os.path.dirname(HERE))
    from netmod import tiler
    city = tiler.City.load(path)
    cells = {xy: (p.id, p.state) for xy, p in city.layers["surface"].items()}
    bl = []
    for t, recs in getattr(city, "buildings", {}).items():
        for (a, b, sa, sb, key) in recs:
            bl.append((a, b, sa, sb))
    g = Grid(cells, bl, flat=lambda x, z: len({city.h(x, z), city.h(x + 1, z), city.h(x, z + 1),
                                                city.h(x + 1, z + 1)}) == 1)
    for gesture, a, r, name, cs in find(g, loop):
        print("T gesture %d anchor %s rot %d layout %s, %d cells" % (gesture, a, r, name, len(cs)))
        for xy in sorted(cs):
            print("   %s %s -> %d.%d %s" % (xy, cells.get(xy), *cs[xy]))


def main(argv):
    loop = int(argv[argv.index("--loop") + 1]) if "--loop" in argv else 3
    if len(argv) > 1 and argv[1] == "show":
        show(loop, "--rio" in argv)
    elif len(argv) > 2 and argv[1] == "match":
        match_save(argv[2], loop)
    elif len(argv) > 1 and argv[1] == "selftest":
        return selftest()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
