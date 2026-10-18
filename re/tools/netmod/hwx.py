#!/usr/bin/env python3
r"""hwx.py - straight highway x straight highway (task hwx, highway program 2026-10-18): the cloverleaf and the
cleaned-up flyover fallback. Design note: verify/hwx/README.md.

    py -3.12 re/tools/netmod/hwx.py cells                 # the cell table: piece, base, quadrant, turns (from the geometry)
    py -3.12 re/tools/netmod/hwx.py plan OUT.png          # top-down plan picture for the owner
    py -3.12 re/tools/netmod/hwx.py mockup OUT.png --work DIR [--support slab|wall] [--fallback] [--resume]
    py -3.12 re/tools/netmod/hwx.py sheet OUT.png --work DIR   # owner sheet from the painted cells

Frame. Cells (x, z) relative to the X: the highway along z holds x = -1 (traffic -z) and x = 0 (traffic +z), the
highway along x holds z = -1 (traffic +x) and z = 0 (traffic -x) (stock 73.2 / 73.0 and 15051.2 / 15051.0, lanes from
lanekit describe). Cell (i, j) covers [i, i+1] x [j, j+1] in cell units. The stock X is the 12-cell plus shape in
x, z = -2..1 (STOCK.md); the highway along z always goes over (deck up to 1792), the one along x under (down to 256),
whatever the drag order (offline tiler, both orders).

Right turns leave a carriageway toward its outer side, left turns would cross the opposite carriageway, so: one
outer ramp per quadrant for a right turn, one 270-degree loop per quadrant for a left turn. Quadrant Q0 = (+x, -z)
holds the loop "+x -> +z" and the outer ramp "+z -> +x"; Q1..Q3 are Q0 turned 90, 180, 270 degrees about the X
centre, (i, j) -> (-j - 1, i) per step, which maps every carriageway onto the next with its direction (the traffic
pattern is symmetric under quarter turns). Every ramp is one lane at the highway deck height (1024); no ramp crosses
another ramp or a carriageway, so the only bridge is the X itself.
"""
import argparse
import math
import os
import sys

# ---------------------------------------------------------------- geometry (cell units, quadrant Q0)
# W, LANE_OUT, R_LOOP and GAP are imported by stream hwt (hwt_layout.GEOM) so the T and X loops match: keep the names.
W = 0.31            # half width of a one-lane ramp deck = hwpaint.RAMP_W / 2 (0.62: stock parapet, edge line,
                    # one lane, inner curb)
LANE_OUT = 0.57     # outer lane of a carriageway, distance from the median (lanes at 61 / 145 of 256 per cell)
R_LOOP = 1.25       # loop centreline radius, the size parameter (--loop-r): 1.25 = deck 1.03..1.47 around the
                    # centre, a 3x3 block (12x12 box); 1.75 = a 4x4 block (14x14 box). Minimum 1.25: the loop is
                    # tangent to the lines 0.25 outside both carriageways, so its ends sit at x = z = 1.25 + R, and
                    # each S taper needs about 0.5 cell outside the stock 4x4 arm cells (x >= 2, z <= -3), so a
                    # 2x2 loop (R 0.75, ends at 2.0) cannot be built at the X
GAP = 0.19          # ground between the loop deck and the outer ramp deck
RHO = 0.75          # the outer ramp's two right-turn arcs (0.75 keeps the 12x12 box at the 0.62 deck)


def configure(r_loop):
    global R_LOOP
    if r_loop < 1.25:
        raise SystemExit("loop radius %.2f < 1.25: the loop's ends would sit on the stock X arm cells" % r_loop)
    R_LOOP = r_loop


def c_loop():
    """loop centre, tangent to the ramp lines z = -1.25 (beside +x) and x = 1.25 (beside +z)"""
    return (1.25 + R_LOOP, -1.25 - R_LOOP)


def r_out():
    """outer ramp centreline radius about the loop centre (2.06 at R_LOOP 1.25)"""
    return R_LOOP + 2 * W + GAP


def _arc(c, r, a0, a1, n=24):
    """points of a circle arc, angles in degrees in the (x, z) plane, a = 0 along +x, 90 along +z"""
    return [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def _bez(p0, p1, p2, p3, n=12):
    out = []
    for k in range(n + 1):
        t = k / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def _s(p0, p3, axis):
    """S taper between two parallel lines, both ends heading along `axis` (0 = x, 1 = z)"""
    m = (p0[axis] + p3[axis]) / 2
    if axis == 0:
        return _bez(p0, (m, p0[1]), (m, p3[1]), p3)
    return _bez(p0, (p0[0], m), (p3[0], m), p3)


def ramps_q0():
    """{name: polyline} for Q0, in driving order"""
    C_LOOP, R_OUT = c_loop(), r_out()
    cx, cz = C_LOOP
    top, left = (cx, cz + R_LOOP), (cx - R_LOOP, cz)
    # loop: leave the +x carriageway's outer lane in cell (2,-1), 270 degrees clockwise seen from above with z up
    # (in the (x, z) plane: +x -> -z -> -x -> +z), join the +z carriageway's outer lane in cell (0,-3)
    loop = _s((2.0, -LANE_OUT), top, 0)[:-1]
    loop += _arc(C_LOOP, R_LOOP, 90, -180, 54)[:-1]
    loop += _s(left, (LANE_OUT, -2.0), 1)                 # ends ON the border z = -2 (hwlanes cuts lanes there)
    # outer ramp: leave the +z carriageway in cell (0,-6), right turn, around the loop (left turn), right turn,
    # join the +x carriageway in cell (5,-1)
    b = (cx, cz - R_OUT)                       # bottom of the arc around the loop
    rt = (cx + R_OUT, cz)                      # right end of it
    s0 = (1.25, b[1] - RHO)
    out = _s((LANE_OUT, math.floor(s0[1] - 0.5)), s0, 1)[:-1]     # starts ON a cell border
    out += _arc((s0[0] + RHO, s0[1]), RHO, 180, 90, 12)[:-1]
    out += [(s0[0] + RHO, b[1])] if s0[0] + RHO < b[0] else []
    out += _arc(C_LOOP, R_OUT, -90, 0, 24)[:-1]
    e0 = (rt[0], -1.25 - RHO)
    out += [rt] if e0[1] > rt[1] else []
    out += _arc((e0[0] + RHO, e0[1]), RHO, 180, 90, 12)[:-1]
    out += _s((e0[0] + RHO, -1.25), (math.ceil(e0[0] + RHO + 0.5), -LANE_OUT), 0)   # ends ON a cell border
    return {"loop": loop, "outer": out}


def rot(p, k):
    """quarter turns about the X centre (0, 0): (x, z) -> (-z, x)"""
    x, z = p
    for _ in range(k % 4):
        x, z = -z, x
    return (x, z)


def rot_cell(c, k):
    i, j = c
    for _ in range(k % 4):
        i, j = -j - 1, i
    return (i, j)


SIDES = {(-1, 0): "x-", (0, -1): "z-", (1, 0): "x+", (0, 1): "z+"}


def cell_path(poly):
    """cells a centreline passes, in order, with (enter side, leave side)"""
    seq = []
    for k in range(len(poly) - 1):
        a, b = poly[k], poly[k + 1]
        for t in [(i + 0.5) / 8 for i in range(8)]:      # sub-segment midpoints: an end exactly on a border stays in its cell
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            c = (math.floor(p[0]), math.floor(p[1]))
            if not seq or seq[-1] != c:
                seq.append(c)
    out = []
    for n, c in enumerate(seq):
        ent = SIDES[(seq[n - 1][0] - c[0], seq[n - 1][1] - c[1])] if n else None
        lv = SIDES[(seq[n + 1][0] - c[0], seq[n + 1][1] - c[1])] if n + 1 < len(seq) else None
        out.append((c, ent, lv))
    return out


# ---------------------------------------------------------------- the X core (stock) and the piece table
STOCK_CORE = {(-2, -1): (15107, 0), (-1, -1): (15113, 2), (0, -1): (15114, 0), (1, -1): (15108, 2),
              (-2, 0): (15108, 0), (-1, 0): (15114, 2), (0, 0): (15113, 0), (1, 0): (15107, 2),
              (-1, -2): (15150, 2), (0, -2): (15153, 2), (-1, 1): (15153, 0), (0, 1): (15150, 0)}
CLEAN_CORE = {15113: 21160, 15114: 21161, 15107: 21162, 15108: 21163, 15150: 21164, 15153: 21165}


def carriageway(c):
    """'x' / 'z' highway cell of the plain arms, with the stock straight piece and state"""
    i, j = c
    if j in (-1, 0) and i not in (-1, 0):
        return "x", (15051, 2 if j == -1 else 0)
    if i in (-1, 0) and j not in (-1, 0):
        return "z", (73, 2 if i == -1 else 0)
    return None, None


# Ramp ids are used in all four quadrants (state = quadrant, nominal: the engine's state turn direction is checked
# at build time); mainline ids sit on one highway, so they come in an x and a z flavour.
RAMP_ID0 = 21120
RAMP_ID_END = 21149   # ramp ids 21120..21149: 15 used at loop radius 1.25, 21 at 1.75
MAIN_IDS = {("x", "loop diverge"): 21150, ("x", "outer merge"): 21151, ("x", "loop merge"): 21152,
            ("x", "outer diverge"): 21153, ("z", "loop diverge"): 21154, ("z", "outer merge"): 21155,
            ("z", "loop merge"): 21156, ("z", "outer diverge"): 21157}


def deck_cells(poly, ramp_cells):
    """cells a ramp deck (centreline +- W) touches outside the carriageways and the core"""
    out = set()
    for k in range(len(poly) - 1):
        a, b = poly[k], poly[k + 1]
        for t in range(10):
            x, z = a[0] + (b[0] - a[0]) * t / 10, a[1] + (b[1] - a[1]) * t / 10
            for i in range(-6, 7):
                for j in range(-6, 7):
                    dx, dz = i / 6 * W, j / 6 * W
                    if dx * dx + dz * dz <= W * W:
                        c = (math.floor(x + dx), math.floor(z + dz))
                        if carriageway(c)[0] is None and c not in STOCK_CORE:
                            out.add(c)
    return out


def _inside(p, poly):
    n, x, z, ins = len(poly), p[0], p[1], False
    for k in range(n):
        (x1, z1), (x2, z2) = poly[k], poly[(k + 1) % n]
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
            ins = not ins
    return ins


def q0_cells():
    """-> (ramp ids {cell: id}, mainline kinds {cell: kind}, enclosed ground cells), all from the geometry"""
    rq = ramps_q0()
    ids, main = {}, {}
    for name, poly in rq.items():
        path = cell_path(poly)
        main[path[0][0]] = name + " diverge"
        main[path[-1][0]] = name + " merge"
        for c, _, _ in path[1:-1]:
            ids.setdefault(c, RAMP_ID0 + len(ids))
    for name, poly in rq.items():
        for c in sorted(deck_cells(poly, ids), key=lambda c: (-c[1], c[0])):
            ids.setdefault(c, RAMP_ID0 + len(ids))
    if RAMP_ID0 + len(ids) - 1 > RAMP_ID_END:
        raise SystemExit("%d ramp cells: past the ramp id block" % len(ids))
    ring = rq["outer"] + [(1.0, -1.0)]
    ground = [(i, j) for i in range(1, 12) for j in range(-12, -1)
              if (i, j) not in ids and _inside((i + 0.5, j + 0.5), ring)]
    return ids, main, ground


def box():
    xs = [v for c in table() for v in c]
    return (min(xs), max(xs))


def table():
    """{cell: dict(id, base, state, quadrant, turns, kind)} for the whole cloverleaf"""
    rq = ramps_q0()
    RAMP_IDS, MAIN_KIND, GROUND_Q0 = q0_cells()
    turns0 = {c: [] for c in RAMP_IDS}
    for name, poly in rq.items():
        for c, e, l in cell_path(poly):
            turns0.setdefault(c, []).append((name, e, l))
    out = {}
    for q in range(4):
        for c0, tl in turns0.items():
            c = rot_cell(c0, q)
            tr = [(n, _rot_side(e, q), _rot_side(l, q)) for n, e, l in tl]
            if c0 in MAIN_KIND and tl and len({n for n, _, _ in tl}) > 1:
                raise SystemExit("two ramps on one mainline cell %s" % (c0,))
            if c0 in MAIN_KIND:
                hw, base = carriageway(c)
                kind = MAIN_KIND[c0]
                pid = MAIN_IDS[(hw, kind)]
                # through lanes of the carriageway are kept
                out[c] = dict(id=pid, base=base, quadrant=q, turns=tr, kind=kind + " (" + hw + " highway)")
            else:
                out[c] = dict(id=RAMP_IDS[c0], base=None, state=q, quadrant=q, turns=tr,
                              kind=("ramp " + "+".join(sorted({n for n, _, _ in tl}))) if tl else "ramp deck edge")
        for g in GROUND_Q0:
            out[rot_cell(g, q)] = dict(id=0, quadrant=q, turns=[], kind="ground (left to the player)")
    for c, (pid, st) in STOCK_CORE.items():
        out[c] = dict(id=CLEAN_CORE[pid], base=(pid, st), quadrant=None, turns=[], kind="X core (clean flyover)")
    # placement: cls (land = written into an empty cell, main = a carriageway cell rewritten, core = an X core cell),
    # put = the state the block writes, ref = the cell whose art and lanes the id carries at state 0 (art and lanes
    # are painted / cut there; another cell of the id is that cell turned `put` quarter turns about the X centre)
    first = {}
    for q in range(4):
        for c in sorted(out):
            v = out[c]
            if v["id"] and v["quadrant"] == q and v["base"] is not None:
                first.setdefault(v["id"], q)
    for c, v in out.items():
        if not v["id"]:
            continue
        if v["quadrant"] is None:
            v.update(cls="core", put=v["base"][1])
            v["ref"] = next(k for k, (p, st) in STOCK_CORE.items() if CLEAN_CORE[p] == v["id"] and st == 0)
        elif v["base"] is None:
            v.update(cls="land", put=v["quadrant"], ref=rot_cell(c, -v["quadrant"]))
        else:
            k = (v["quadrant"] - first[v["id"]]) % 4
            v.update(cls="main", put=k, ref=rot_cell(c, -k))
    for c, v in out.items():                         # every placement is its ref cell turned `put` times
        if v["id"] and rot_cell(v["ref"], v["put"]) != c:
            raise SystemExit("cell %s: id %d is not its ref %s turned %d" % (c, v["id"], v["ref"], v["put"]))
        if v["id"] and v["cls"] != "land" and v["put"] not in (0, 2):
            raise SystemExit("cell %s: highway piece %d in state %d" % (c, v["id"], v["put"]))
    return out


def _rot_side(s, k):
    if s is None:
        return None
    order = ["x-", "z-", "x+", "z+"]        # (x, z) -> (-z, x) sends x+ to z+, z+ to x-, ...
    return order[(order.index(s) + k) % 4]


def cmd_cells(a):
    t = table()
    for c in sorted(t, key=lambda c: (t[c]["quadrant"] is None, t[c]["quadrant"] or 0, c[1], c[0])):
        d = t[c]
        if a.q is not None and d["quadrant"] != a.q:
            continue
        tr = ", ".join("%s %s->%s" % (n, e or "start", l or "end") for n, e, l in d["turns"])
        base = "%d.%d" % d["base"] if d.get("base") else ("empty cell, state %d" % d["state"] if "state" in d else "")
        print("%-9s q%s  %5s  %-38s %-22s %s" % (c, d["quadrant"], d["id"] or "-", d["kind"], base, tr))
    xs = [c[0] for c in t] + [c[1] for c in t]
    print("loop radius %.2f: cells %d, box %d..%d" % (R_LOOP, len(t), min(xs), max(xs)))


# ---------------------------------------------------------------- mockup (hwpaint scene)
class Polyline:
    """a hwpaint path segment through sampled points (the S tapers are Bezier curves, hwpaint has lines and arcs)"""

    def __init__(self, pts):
        import numpy as np
        self.P = np.asarray(pts, dtype=float)
        d = np.diff(self.P, axis=0)
        self.seglen = np.hypot(d[:, 0], d[:, 1])
        keep = self.seglen > 1e-9
        self.P = np.vstack([self.P[:1], self.P[1:][keep]])
        d = np.diff(self.P, axis=0)
        self.seglen = np.hypot(d[:, 0], d[:, 1])
        self.u = d / self.seglen[:, None]
        self.cum = np.concatenate([[0.0], np.cumsum(self.seglen)])
        self.length = float(self.cum[-1])

    def project(self, wx, wz):
        import numpy as np
        wx, wz = np.asarray(wx, dtype=float), np.asarray(wz, dtype=float)
        shp = wx.shape
        X, Z = wx.reshape(-1), wz.reshape(-1)
        s_out, t_out = np.empty(X.shape), np.empty(X.shape)
        if X.size == 0:
            return s_out.reshape(shp), t_out.reshape(shp)
        n = len(self.seglen)
        # only the segments near the queried points (a cell's column): a point farther than 1.5 cells from every
        # segment is off the deck anyway, so it gets s = -10 (before the start, outside every deck)
        m = 1.5
        P0, P1 = self.P[:-1], self.P[1:]
        near = ((np.minimum(P0[:, 0], P1[:, 0]) <= X.max() + m) & (np.maximum(P0[:, 0], P1[:, 0]) >= X.min() - m) &
                (np.minimum(P0[:, 1], P1[:, 1]) <= Z.max() + m) & (np.maximum(P0[:, 1], P1[:, 1]) >= Z.min() - m))
        idx = np.nonzero(near)[0]
        if idx.size == 0:
            s_out[:] = -10.0
            t_out[:] = 10.0
            return s_out.reshape(shp), t_out.reshape(shp)
        lo = np.zeros(n)
        lo[0] = -np.inf
        hi = self.seglen.copy()
        hi[-1] = np.inf
        lo, hi, Pk, uk = lo[idx], hi[idx], self.P[idx], self.u[idx]
        step = max(1, 2000000 // idx.size)
        for i in range(0, len(X), step):
            rx = X[i:i + step, None] - Pk[None, :, 0]
            rz = Z[i:i + step, None] - Pk[None, :, 1]
            a = rx * uk[None, :, 0] + rz * uk[None, :, 1]
            t = -rx * uk[None, :, 1] + rz * uk[None, :, 0]
            ac = np.clip(a, lo[None, :], hi[None, :])
            k = np.argmin((a - ac) ** 2 + t * t, axis=1)
            j = np.arange(len(k))
            s_out[i:i + step] = self.cum[idx[k]] + a[j, k]
            t_out[i:i + step] = t[j, k]
        return s_out.reshape(shp), t_out.reshape(shp)

    def at(self, s):
        import numpy as np
        s = min(max(float(s), 0.0), self.length)
        k = int(min(np.searchsorted(self.cum, s, side="right") - 1, len(self.seglen) - 1))
        p = self.P[k] + self.u[k] * (s - self.cum[k])
        return (float(p[0]), float(p[1])), (float(self.u[k, 0]), float(self.u[k, 1]))

    def offset(self, o):
        raise NotImplementedError


def _hump(e0, e1, e2):
    """height over |c| (cells from the X centre): e0 at the centre, e1 at the core edge 1, e2 at the arm end 2, the
    stock lane heights there (1792 / 1536 / 1024 up, 256 / 512 / 1024 down). One smooth curve, level at 0 and 2: a
    parabola to 1, then a cubic Hermite to 2 with the same slope at 1 (two straight rises would draw two kinks)"""
    import numpy as np
    a = e1 - e0                                   # e0 + a u^2 on [0, 1]
    m = 2.0 * a                                   # its slope at 1

    def f(c):
        u = np.minimum(np.abs(np.asarray(c, dtype=float)), 2.0)
        t = u - 1.0
        h00, h10, h01 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t, -2 * t ** 3 + 3 * t ** 2
        return np.where(u <= 1.0, e0 + a * u * u, h00 * e1 + h10 * m + h01 * e2)
    return f


E_TOP = 1792 * 31.75 / 1024     # the stock X's upper deck at the centre (lanes 1792), zoom-3 px
E_BOT = 256 * 31.75 / 1024      # the lower deck at the centre (lanes 256)


def scene(support="slab", ext=9, ramps=True):
    """the cloverleaf as one hwpaint Scene. The X core keeps the stock lane heights at the cell edges (z highway 1024 ->
    1536 -> 1792, x highway 1024 -> 512 -> 256) on one smooth hump each, with straight full-width decks: the clean
    flyover (stock narrows the lower highway into an arched tunnel)."""
    import hwpaint as HP
    hx, hz = _hump(E_BOT, HP.H_LOW, HP.H), _hump(E_TOP, HP.H_HIGH, HP.H)
    xh = HP.highway(HP.Path.line((-ext, 0.0), (ext, 0.0)), height=lambda s: hx(s - ext))
    zh = HP.highway(HP.Path.line((0.0, -ext), (0.0, ext)), height=lambda s: hz(s - ext), slab=[(ext - 1.0, ext + 1.0)])
    decks = xh + zh
    rq = ramps_q0()
    for q in range(4 if ramps else 0):
        for name, poly in rq.items():
            pts = [rot(p, q) for p in poly]
            path = HP.Path([Polyline(pts)])
            kw = {}
            if support == "slab":
                n = 3 if name == "loop" else 4
                kw = dict(support="slab", thick=10.25,
                          pillars=[path.at(path.length * (k + 1) / (n + 1))[0] for k in range(n)])
            decks.append(HP.ramp_deck(path, outer="right", width=2 * W, height=HP.H, name="%s%d" % (name, q), **kw))
    _open_parapets(decks[:4], decks[4:])
    return HP.Scene(decks)


def _open_parapets(roads, ramps):
    """parapet gaps (hwpaint Deck.gaps) on each carriageway where a ramp deck crosses its outer edge"""
    import numpy as np
    for dk in roads:
        n = int(dk.path.length * 32) + 1
        ss = np.linspace(0.0, dk.path.length, n)
        edge = []
        for s_ in ss:
            p, d, nrm = dk.frame_at(s_)
            edge.append((p[0] + nrm[0] * dk.w / 2.0, p[1] + nrm[1] * dk.w / 2.0))
        ex, ez = np.array([e[0] for e in edge]), np.array([e[1] for e in edge])
        gaps = []
        for rd in ramps:
            _, _, ins = rd.footprint(ex, ez)
            if ins.any():
                # clamped to the join cell (cell borders are whole s values: the decks start on a cell border), so
                # the X core and the plain cells beside a join keep their parapet and the core art is the same with
                # and without ramps
                g0, g1 = float(ss[ins].min()) - 0.05, float(ss[ins].max()) + 0.05
                k = math.floor((g0 + g1) / 2.0)
                gaps.append((max(g0, k), min(g1, k + 1.0), "outer"))
        dk.gaps = list(dk.gaps) + gaps


def _deck_box(dk):
    """world bounding box of a deck (sampled along it, plus its half width and pillars)"""
    pts = [dk.path.at(dk.path.length * k / 64.0)[0] for k in range(65)] + list(dk.pillars)
    m = dk.w / 2.0 + 0.05
    return (min(p[0] for p in pts) - m, min(p[1] for p in pts) - m, max(p[0] for p in pts) + m,
            max(p[1] for p in pts) + m)


def cmd_mockup(a):
    import time
    import hwpaint as HP
    from PIL import Image, ImageDraw, ImageFont
    sc = scene(a.support, ramps=not a.fallback)
    b0, b1 = box() if not a.fallback else (-4, 3)
    cells = [(i, j) for i in range(b0, b1 + 1) for j in range(b0, b1 + 1)]
    cells = [c for c in cells if (c in table() and not a.fallback) or c in STOCK_CORE or carriageway(c)[0]]
    extra = []
    for k in list(range(b0 - 3, b0)) + list(range(b1 + 1, b1 + 4)):
        for c in ((k, -1), (k, 0), (-1, k), (0, k)):
            hw, (pid, st) = carriageway(c)
            extra.append({"at": [-c[0], c[1]], "piece": pid, "slot": st})
    root = os.path.join(a.work, "cells_fallback" if a.fallback else "cells_%s_r%g" % (a.support, R_LOOP))
    boxes = [_deck_box(dk) for dk in sc.decks]
    import netart as NA
    shots = {}
    for z in a.zooms:
        t0 = time.time()
        layout = []
        for c in cells:
            dd = os.path.join(root, "z%d" % z, "%d_%d" % c)
            if not a.reuse and not (a.resume and os.path.exists(os.path.join(dd, "z%d_r3.png" % z))):
                near = [dk for dk, bb in zip(sc.decks, boxes)
                        if bb[0] < c[0] + 1.5 and bb[2] > c[0] - 0.5 and bb[1] < c[1] + 1.5 and bb[3] > c[1] - 0.5]
                HP.paint_cell(HP.Scene(near), c, dd, zooms=[z])
            layout.append({"at": [-c[0], c[1]], "dir": dd, "slot": 0})
        pv = NA.preview({"cells": layout + extra}, None, zooms=[z], rots=[0, 1])
        shots[(z, 0)], shots[(z, 1)] = pv[(z, 0)], pv[(z, 1)]
        print("zoom %d: %d cells, %.0f s" % (z, len(cells), time.time() - t0))
    try:
        fb = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        fb = ImageFont.load_default()
    rows = []
    for z in a.zooms:
        row = [shots[(z, r)] for r in (0, 1)]
        rows.append((z, row))
    Wd = max(sum(i.width for i in row) for _, row in rows)
    Hd = sum(max(i.height for i in row) + 30 for _, row in rows)
    sheet = Image.new("RGB", (Wd, Hd), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    y = 0
    for z, row in rows:
        x = 0
        for r, im in zip((0, 1), row):
            d.text((x + 8, y + 6), ("zoom %d, view %d  (clean flyover)" % (z, r)) if a.fallback else
                   "zoom %d, view %d  (loop radius %.2f, ramps: %s)" % (z, r, R_LOOP, a.support),
                   fill=(230, 230, 230), font=fb)
            sheet.paste(im.convert("RGB"), (x, y + 30))
            x += im.width
        y += max(i.height for i in row) + 30
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(a.out, sheet.size)


def _assemble(work, fallback, z, rots=(0, 1), support="slab"):
    """previews of cells painted by `mockup` (no painting)"""
    import netart as NA
    b0, b1 = box() if not fallback else (-4, 3)
    root = os.path.join(work, "cells_fallback" if fallback else "cells_%s_r%g" % (support, R_LOOP), "z%d" % z)
    lay = []
    for i in range(b0, b1 + 1):
        for j in range(b0, b1 + 1):
            c = (i, j)
            if (c in table() and not fallback) or c in STOCK_CORE or carriageway(c)[0]:
                lay.append({"at": [-i, j], "dir": os.path.join(root, "%d_%d" % c), "slot": 0})
    for k in list(range(b0 - 3, b0)) + list(range(b1 + 1, b1 + 4)):
        for c in ((k, -1), (k, 0), (-1, k), (0, k)):
            pid, st = carriageway(c)[1]
            lay.append({"at": [-c[0], c[1]], "piece": pid, "slot": st})
    pv = NA.preview({"cells": lay}, None, zooms=[z], rots=list(rots))
    return [pv[(z, r)] for r in rots]


def _stock_x(z, rots=(0, 1)):
    import netart as NA
    lay = []
    for i in range(-7, 7):
        for j in range(-7, 7):
            c = (i, j)
            p = STOCK_CORE.get(c) or (carriageway(c)[1] if carriageway(c)[0] else None)
            if p:
                lay.append({"at": [-i, j], "piece": p[0], "slot": p[1]})
    pv = NA.preview({"cells": lay}, None, zooms=[z], rots=list(rots))
    return [pv[(z, r)] for r in rots]


def _centre_crop(im, w, h, dy=0):
    cx, cy = im.width // 2, im.height // 2 + dy
    return im.crop((max(0, cx - w // 2), max(0, cy - h // 2), min(im.width, cx + w // 2), min(im.height, cy + h // 2)))


def cmd_sheet(a):
    """the owner sheet: cloverleaf at zoom 3 (views 0, 1), zoom 4 close-ups of the centre, stock X vs clean flyover"""
    from PIL import Image, ImageDraw, ImageFont
    try:
        fh = ImageFont.truetype("arialbd.ttf", 26)
        fb = ImageFont.truetype("arialbd.ttf", 19)
        fs = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        fh = fb = fs = ImageFont.load_default()
    z3 = _assemble(a.work, False, 3)
    z4 = [_centre_crop(im, 1300, 820) for im in _assemble(a.work, False, 4)]
    st4 = [_centre_crop(im, 900, 560) for im in _stock_x(4, (0,))]
    fb4 = [_centre_crop(im, 900, 560) for im in _assemble(a.work, True, 4, (0,))]
    blocks = [
        ("Cloverleaf, zoom 3, views 0 and 1 (whole 12x12)", z3),
        ("Cloverleaf, zoom 4, views 0 and 1 (centre: the X and the four loops' joins)", z4),
        ("Fallback when a quadrant is built up, zoom 4 view 0:  stock X (left)  vs  clean flyover (right)", st4 + fb4),
    ]
    W = max(sum(i.width for i in ims) + 20 * (len(ims) - 1) for _, ims in blocks) + 40
    notes = [
        "hwx mockup (painted with hwcore's hwpaint.py from the plan geometry; offline, not in game yet).",
        "Ramps: one lane, 0.62 cell wide (stock ramp width), slabs on pillars at highway deck height. Loop radius 1.25.",
        "The X: z highway over, x highway under, same lane heights as stock at every cell edge, drawn as one smooth",
        "hump each with straight full-width decks (stock squeezes the lower highway into an arched tunnel).",
    ]
    Hh = 70 + 24 * len(notes) + sum(max(i.height for i in ims) + 50 for _, ims in blocks)
    sheet = Image.new("RGB", (W, Hh), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    d.text((20, 16), "hwx: cloverleaf at a straight highway X (mockup)", fill=(240, 240, 240), font=fh)
    y = 60
    for t in notes:
        d.text((20, y), t, fill=(200, 200, 200), font=fs)
        y += 24
    y += 10
    for title, ims in blocks:
        d.text((20, y), title, fill=(240, 220, 150), font=fb)
        y += 30
        x = 20
        for im in ims:
            sheet.paste(im.convert("RGB"), (x, y))
            x += im.width + 20
        y += max(i.height for i in ims) + 20
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(a.out, sheet.size)


# ---------------------------------------------------------------- plan picture
def cmd_plan(a):
    from PIL import Image, ImageDraw, ImageFont
    S = 46                                   # px per cell
    ext = box()[1] + 3                       # cells shown each side of the X centre
    PAD = 60
    side = 2 * ext * S
    LEG_W = 560
    img = Image.new("RGB", (PAD * 2 + side + LEG_W, PAD * 2 + side + 520), (247, 246, 241))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("arial.ttf", 11)
        fb = ImageFont.truetype("arialbd.ttf", 15)
        fh = ImageFont.truetype("arialbd.ttf", 20)
        fs = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        f = fb = fh = fs = ImageFont.load_default()

    # z grows UP the page (so the plan is the (x, z) plane seen from above, x to the right)
    def P(x, z):
        return (PAD + (x + ext) * S, PAD + (ext - z) * S)

    t = table()
    ids0, _m, gr0 = q0_cells()
    nr, ng, bw = len(ids0), len(gr0), box()[1] - box()[0] + 1
    # ground, footprint box, grid
    bx0, bx1 = box()
    d.rectangle([P(bx0, bx1 + 1), P(bx1 + 1, bx0)], fill=(226, 234, 214))
    for c, v in t.items():
        if v["id"] == 0:
            d.rectangle([P(c[0], c[1] + 1), P(c[0] + 1, c[1])], fill=(200, 222, 180))
    for k in range(-ext, ext + 1):
        d.line([P(k, -ext), P(k, ext)], fill=(205, 205, 200))
        d.line([P(-ext, k), P(ext, k)], fill=(205, 205, 200))
    d.rectangle([P(bx0, bx1 + 1), P(bx1 + 1, bx0)], outline=(90, 140, 70), width=2)

    deck = (150, 150, 155)
    over = (120, 120, 200)
    # carriageways
    for (x0, z0, x1, z1) in [(-ext, -1, ext, 1), (-1, -ext, 1, ext)]:
        d.rectangle([P(x0, z1), P(x1, z0)], fill=deck)
    # the X core: the z highway over (blue deck), the x highway under it
    d.rectangle([P(-1, 2), P(1, -2)], fill=over)
    d.line([P(0, -ext), P(0, ext)], fill=(250, 250, 250), width=2)          # median of the z highway
    d.line([P(-ext, 0), P(-1, 0)], fill=(250, 250, 250), width=2)
    d.line([P(1, 0), P(ext, 0)], fill=(250, 250, 250), width=2)
    d.line([P(-1, 0), P(1, 0)], fill=(70, 70, 140), width=1)

    def arrow(p, q, col, wid=3):
        d.line([P(*p), P(*q)], fill=col, width=wid)
        ax, az = q[0] - p[0], q[1] - p[1]
        L = math.hypot(ax, az) or 1
        ux, uz = ax / L, az / L
        h = 0.22
        a1 = (q[0] - h * ux + 0.5 * h * uz, q[1] - h * uz - 0.5 * h * ux)
        a2 = (q[0] - h * ux - 0.5 * h * uz, q[1] - h * uz + 0.5 * h * ux)
        d.polygon([P(*q), P(*a1), P(*a2)], fill=col)

    # carriageway direction arrows
    for x in (-7, -4, 3, 6):
        arrow((x, -0.5), (x + 0.9, -0.5), (255, 255, 255), 2)
        arrow((x + 0.9, 0.5), (x, 0.5), (255, 255, 255), 2)
    for z in (-7, -4, 3, 6):
        arrow((0.5, z), (0.5, z + 0.9), (255, 255, 255), 2)
        arrow((-0.5, z + 0.9), (-0.5, z), (255, 255, 255), 2)

    cols = {"loop": (205, 70, 40), "outer": (40, 120, 200)}
    rq = ramps_q0()
    for q in range(4):
        for name, poly in rq.items():
            pts = [rot(p, q) for p in poly]
            d.line([P(*p) for p in pts], fill=(125, 125, 130), width=int(2 * W * S) + 1, joint="curve")
        for name, poly in rq.items():
            pts = [rot(p, q) for p in poly]
            d.line([P(*p) for p in pts], fill=cols[name], width=3, joint="curve")
            for frac in (0.3, 0.62, 0.9):
                k = int(len(pts) * frac)
                arrow(pts[k - 1], pts[k], cols[name], 3)

    # ids per cell
    for c, v in t.items():
        if v["id"]:
            st = v.get("state")
            if st is None and v.get("base"):
                st = v["base"][1]
            txt = "%d" % (v["id"] - 21100)
            px, pz = P(c[0] + 0.5, c[1] + 0.5)
            tw = d.textlength(txt, font=f)
            d.rectangle([px - tw / 2 - 2, pz - 7, px + tw / 2 + 2, pz + 7], fill=(255, 255, 255))
            d.text((px - tw / 2, pz - 6), txt, fill=(0, 0, 0), font=f)
            d.text((px - tw / 2 + tw + 3, pz - 2), ".%d" % st, fill=(90, 90, 90), font=f)
    # axes
    for k in range(-ext, ext, 2):
        d.text((P(k, -ext)[0] + 3, P(k, -ext)[1] + 4), str(k), fill=(110, 110, 110), font=f)
        d.text((P(-ext, k)[0] - 22, P(-ext, k + 1)[1] + 16), str(k), fill=(110, 110, 110), font=f)
    d.text((P(ext, -ext)[0] + 6, P(ext, -ext)[1] - 10), "x ->", fill=(0, 0, 0), font=fb)
    d.text((P(-ext, ext)[0] - 50, P(-ext, ext)[1] - 4), "z ^", fill=(0, 0, 0), font=fb)
    qn = {0: "Q0", 1: "Q1", 2: "Q2", 3: "Q3"}
    for q in range(4):
        p = rot((5.0, -6.6), q)
        d.text(P(*p), qn[q], fill=(60, 110, 50), font=fb)

    # legend / notes
    L = PAD + side + 30
    y = PAD
    d.text((L, y), "hwx plan: cloverleaf at a straight highway X", fill=(0, 0, 0), font=fh); y += 34
    notes = [
        "Top-down, cell grid (1 square = 1 game cell), X centre at (0,0).",
        "Numbers = piece id - 21100 (so 20 = 21120), .s = state.",
        "Grey bands = highway decks, all at deck height 1024 on walls.",
        "Blue square = the X core: the z highway goes OVER (to 1792),",
        "the x highway goes UNDER (to 256), as stock does whatever the",
        "drag order. No ramp crosses anything: the X is the only bridge.",
        "White arrows = traffic on each carriageway (one cell per direction).",
        "Red = loop ramp (left turn, 270 deg), blue = outer ramp (right turn).",
        "Ramps: one lane, deck %.2f cell. Loop: radius %.2f cells (%dx%d block)." % (
            2 * W, R_LOOP, round(2 * R_LOOP + 0.5), round(2 * R_LOOP + 0.5)),
        "Light green = %dx%d footprint (cells %d..%d). Darker green = enclosed" % (
            box()[1] - box()[0] + 1, box()[1] - box()[0] + 1, box()[0], box()[1]),
        "ground (loop hole, corner): left to the player, no piece.",
        "In game view 0, +x runs to the screen's lower left, +z to its",
        "lower right (netart: u = -x, v = z).",
        "",
        "Movements (all 12 connected):",
        "  through: 4, on the stock X (cleaned-up art)",
        "  right turns: 4 outer ramps, e.g. Q0: +z -> +x",
        "  left turns: 4 loops, e.g. Q0: +x -> +z (pass the X, exit right,",
        "     loop, join before the X)",
        "Each carriageway, in driving order: outer exit, loop entry, X,",
        "  loop exit, outer entry (the classic cloverleaf weave over the X).",
        "",
        "Pieces (Q1..Q3 = Q0 turned 90/180/270 deg):",
        "  21120..%d  %d ramp cells (empty cells), states 0..3" % (21119 + nr, nr),
        "  21150..21157  8 mainline cells with a diverge / merge,",
        "                x-highway (base 15051) and z-highway (base 73) kinds",
        "  21160..21165  6 clean X core cells (bases 15113/14, 15107/08,",
        "                15150/53), states 0/2: also the fallback",
        "  21170..21189  reserved: X on a slope;  21190..21199 spare",
        "Per X: %d ramp cells + 16 mainline + 12 core; %d ground cells." % (4 * nr, 4 * ng),
    ]
    for s in notes:
        d.text((L, y), s, fill=(30, 30, 30), font=fs)
        y += 18

    # bottom: stock vs fallback, the rule
    y0 = PAD + side + 30
    d.text((PAD, y0), "Stock after the two drags (offline tiler, = STOCK.md):", fill=(0, 0, 0), font=fb)
    d.text((PAD + 470, y0), "Fallback (a quadrant built up): clean flyover, same 4x4", fill=(0, 0, 0), font=fb)

    def mini(ox, oy, ids):
        s = 54
        for (i, j), (pid, st) in ids.items():
            x0, z0 = ox + (i + 3) * s, oy + (2 - j) * s
            d.rectangle([x0, z0, x0 + s, z0 + s], fill=(180, 180, 200) if i in (-1, 0) and j in (-1, 0) else deck,
                        outline=(255, 255, 255))
            d.text((x0 + 4, z0 + 12), "%d" % pid, fill=(0, 0, 0), font=f)
            d.text((x0 + 4, z0 + 28), "state %d" % st, fill=(60, 60, 60), font=f)
    arm = {}
    for i in (-3, 2):
        arm[(i, -1)] = (15051, 2)
        arm[(i, 0)] = (15051, 0)
    for j in (-3, 2):
        arm[(-1, j)] = (73, 2)
        arm[(0, j)] = (73, 0)
    mini(PAD, y0 + 26, {**arm, **STOCK_CORE})
    mini(PAD + 470, y0 + 26, {**arm, **{c: (CLEAN_CORE[p], s) for c, (p, s) in STOCK_CORE.items()}})
    rule = [
        "Rule (net 4 pass on RBT's hooks, after a retile):",
        "  trigger: an edit pass that builds or touches the stock 12-cell X (ids above) on flat dry ground,",
        "    all 4 arms continuing past the 4x4; a city load only restores existing ones, never takes land",
        "    (an arm that is a 1-cell stub with nothing beyond is a T: refused, stream hwt owns it);",
        "  cloverleaf if: the %dx%d box is flat, dry and inside the map; the arms are plain straight" % (bw, bw),
        "    highway (15051 / 73 pairs) on cells 2..%d and %d..-3 of every arm; all %d ramp cells are" % (
            box()[1], box()[0], 4 * nr),
        "    empty or trees (no building, zone, network); no other highway piece,",
        "    on-ramp or interchange in the box (another X closer than %d cells, a T, a diagonal);" % bw,
        "  else the clean flyover on the 12 core cells. All four quadrants or none.",
        "  refused (left stock): X on a slope (15149, later), Berlin-style rings 15115..15128 in the 6x6.",
    ]
    yy = y0 + 26 + 6 * 54 + 14
    for s in rule:
        d.text((PAD, yy), s, fill=(30, 30, 30), font=fs)
        yy += 18
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    img.save(a.out)
    print(a.out, img.size)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ap.add_argument("--loop-r", type=float, default=R_LOOP, help="loop centreline radius in cells (>= 1.25)")
    c = sub.add_parser("cells")
    c.add_argument("--q", type=int)
    p = sub.add_parser("plan")
    p.add_argument("out")
    m = sub.add_parser("mockup")
    m.add_argument("out")
    m.add_argument("--work", required=True, help="gitignored folder for the painted cells")
    m.add_argument("--support", default="slab", choices=["slab", "wall"])
    m.add_argument("--zooms", type=int, nargs="+", default=[4, 3])
    m.add_argument("--reuse", action="store_true", help="assemble cells painted by an earlier run")
    m.add_argument("--resume", action="store_true", help="paint only cells whose frames for the zoom are missing")
    m.add_argument("--fallback", action="store_true", help="the clean flyover alone (no ramps)")
    sh = sub.add_parser("sheet")
    sh.add_argument("out")
    sh.add_argument("--work", required=True)
    a = ap.parse_args(argv)
    configure(a.loop_r)
    return {"cells": cmd_cells, "plan": cmd_plan, "mockup": cmd_mockup, "sheet": cmd_sheet}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
