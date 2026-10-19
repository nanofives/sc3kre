#!/usr/bin/env python3
r"""hwdd.py - diagonal highway x diagonal highway: the cloverleaf turned 45 degrees (task hwdd, 2026-10-18).

Stock (measured in game 2026-10-18, verify/hwdd/PLAN.md): the two diagonal families (A = x-z band 11223.2 / 11224.0 /
11223.0, B = x+z band 15052.2 / 15106.0 / 15052.0) meet at 90 degrees in the world. Where the two centrelines meet on
a cell centre stock leaves a 3x3 stub around ONE 15149 "Highway Construction" cell; where they meet on a cell corner a
4x4 stub around a 2x2 15149. Neither resolves.

This file is the geometry of the replacement, defined once and used by the plan picture, the mockup and the rule.

Frame. Continuous world coordinates: cell (x, z) spans [x, x+1] x [z, z+1]. The centrelines run through the middle
band cells' centres (A: x - z = cA, B: x + z = cB, both measured on the stock bands). O = their meeting point: a cell
centre ("c" parity, cA + cB odd in cell-index terms) or a cell corner ("h" parity). The plan frame is the game's
rotation-0 screen turned top-down: P = ((z - z0) - (x - x0)) / sqrt2 (screen right), Q = ((x - x0) + (z - z0)) / sqrt2
(screen down), true cell lengths. A runs along Q (screen vertical), B along P (screen horizontal).

Traffic (measured on the stock lanes): right-hand. A heading +Q (x+, z+) keeps P < 0, heading -Q keeps P > 0; B heading
-P (x+, z-) keeps Q < 0, heading +P keeps Q > 0. Lanes sit at |offset| 0.17 and 0.40 true cells, the band edge at
0.707 (= the 3-cell row band). Names below use screen compass words: N = up (-Q), E = right (+P).

Cloverleaf: in each quadrant one 270-degree loop (the left turn) and one outer ramp (the right turn) wrapped around
it: stream hwx's ramps (hwx.py ramps_q0, same W / R_LOOP / GAP / RHO / TAPER) turned 45 degrees in the world, so
every loop in the highway program looks the same. Seen from above the loops sit on the grid axes through O. A bridges
over B (deck), B passes under (painter's job).

  py -3.12 hwdd.py plan OUT.png           the owner's plan picture (both parities, fallback, stock aftermath)
  py -3.12 hwdd.py cells c|h              per-cell roles and ids (text)
  py -3.12 hwdd.py ctab OUT.h              the block's tables (re/harness/src/sc3netmod_hwdd_tab.h)
  py -3.12 hwdd.py flows c|h              router flows: clashes between carriageways, the 12 movements
  py -3.12 hwdd.py check                  offline twin of sc3netmod_hwdd.c on the measured stock aftermath
"""
import math
import os
import sys

try:
    from . import hwcap                  # tasks hwcap / hwcap2: stock end caps, where an arm ends
except ImportError:
    import hwcap

SQ2 = math.sqrt(2.0)
LANE_IN, LANE_OUT = 0.17, 0.40       # stock diagonal highway lanes, |offset| from the centreline, true cells
LANE_MID = (LANE_IN + LANE_OUT) / 2  # where the carriageway arrows are drawn
BAND_HALF = 1.0 / SQ2                # the 3-cell row band = |x - z - cA| <= 1 (cells)
DECK_HALF = 0.63                     # the diagonal deck's edge from the median: hwpaint W_DIAG (hwcore, measured on the
                                     # stock 11223 / 11224 bands at zoom 4, deck height); the band cells reach 0.707
# Ramp geometry shared with hwx / hwt (hwx.py W, R_LOOP, GAP, RHO, TAPER; orchestrator 2026-10-18): one look for
# every loop in the highway program. Only the band offsets differ: the diagonal band edge is 0.707 (hwx: 1.0) and its
# outer lane 0.40 (hwx: 0.57), so the ramp lines sit 0.25 outside 0.707.
RAMP_HALF = 0.31                     # hwx W: half width of a one-lane ramp deck (hwpaint RAMP_W 0.62, program call)
R_LOOP = 1.25                        # hwx R_LOOP: loop centreline radius (deck 1.03..1.47)
GAP = 0.19                           # hwx GAP: ground between the loop deck and the outer ramp deck
RHO = 0.75                           # hwx RHO: the outer ramp's two right-turn arcs (refit for the 0.62 deck)
TAPER = 0.62                         # hwx TAPER: the outer ramp's S tapers
LOOP_TAPER = 0.5                     # hwx: the loop's S tapers (2.0 -> 2.5 and -2.5 -> -2.01)
EDGE = DECK_HALF + 0.25              # the ramp line: 0.25 outside the deck edge (hwx: 1.25 = 1.0 + 0.25)
SLAB_HALF = 0.8                      # A's deck is a slab over B for |along| <= this (B's deck half width 0.63 + walls)
SLOPE_END = 1.6                      # A's rise to H_HIGH and B's dip to H_LOW end this far from O along the band; the
                                     # loops leave / join at 1.63..2.13 (hwcore: no minimum slope length)
FLY = SLOPE_END                      # a band cell reaching closer than this (along its band) to O shows the crossing or
                                     # a slope: a crossing cell (painted in both the cloverleaf and the flyover)
ARM_ROWS = 2                         # band rows past the outer ramps' joins the rule wants on each arm
ID0 = 21360
FLY_IDS = (0, 0)


def to_pq(x, z, o):
    dx, dz = x - o[0], z - o[1]
    return (dz - dx) / SQ2, (dx + dz) / SQ2


def to_xz(p, q, o):
    return o[0] + (q - p) / SQ2, o[1] + (q + p) / SQ2


def rot_pq(pt, k):
    """k quarter turns clockwise on screen: (P, Q) -> (-Q, P)."""
    p, q = pt
    for _ in range(k % 4):
        p, q = -q, p
    return p, q


def rot_cell(c, k, par):
    """the same quarter turns on a cell index, about O (cell centre in 'c', cell corner in 'h')."""
    i, j = c
    for _ in range(k % 4):
        if par == "c":
            i, j = j, -i
        else:
            i, j = j, -1 - i
    return i, j


def rot_cell_R(c, k, par):
    """k quarter turns of a cell about O by the game's state rotation R: (x, z) -> (-z, x) (hwy_rot)"""
    i, j = c
    for _ in range(k % 4):
        i, j = (-j, i) if par == "c" else (-j - 1, i)
    return i, j


# the stock stub after the two drags (measured in game 2026-10-18, verify/hwdd/RESULTS_plan.md), cells relative to the
# frame of Geo: 'c' = O at the centre of cell (0, 0), 'h' = O at the corner (0, 0)
STUB = {
    "c": {(0, 0): (15149, 0), (-1, 0): (73, 2), (1, 0): (73, 0), (0, -1): (15051, 2), (0, 1): (15051, 0),
          (-1, -1): (11224, 0), (1, -1): (15106, 0), (-1, 1): (15106, 0), (1, 1): (11224, 0)},
    "h": {(-1, -1): (15149, 0), (0, -1): (15149, 0), (-1, 0): (15149, 0), (0, 0): (15149, 0),
          (-2, -1): (73, 2), (-2, 0): (73, 2), (1, -1): (73, 0), (1, 0): (73, 0),
          (-1, -2): (15051, 2), (0, -2): (15051, 2), (-1, 1): (15051, 0), (0, 1): (15051, 0),
          (-2, -2): (11224, 0), (1, 1): (11224, 0), (1, -2): (15106, 0), (-2, 1): (15106, 0)},
}


def band_piece(o, c):
    """the stock piece (id, state) of a plain band cell, from its place across the band (measured 2026-10-18):
    A (x - z): 11223.2 / 11224.0 / 11223.0, B (x + z): 15052.2 / 15106.0 / 15052.0 (low x first); None off the bands"""
    cA = o[0] - o[1]
    cB = o[0] + o[1] - 1.0
    dA = (c[0] - c[1]) - cA
    dB = (c[0] + c[1]) - cB
    if abs(dA) <= 1 and dA == int(dA):
        return {-1: (11223, 2), 0: (11224, 0), 1: (11223, 0)}[int(dA)]
    if abs(dB) <= 1 and dB == int(dB):
        return {-1: (15052, 2), 0: (15106, 0), 1: (15052, 0)}[int(dB)]
    return None


def arc(c, r, a0, a1, n=None):
    n = n or max(8, int(abs(a1 - a0) * r * 12))
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * t / n), c[1] + r * math.sin(a0 + (a1 - a0) * t / n))
            for t in range(n + 1)]


def fillet_path(verts, r, step=0.05):
    """polyline through verts with every interior vertex rounded by radius r -> dense point list."""
    out = [verts[0]]
    for k in range(1, len(verts) - 1):
        a, v, b = verts[k - 1], verts[k], verts[k + 1]
        d1 = norm((v[0] - a[0], v[1] - a[1]))
        d2 = norm((b[0] - v[0], b[1] - v[1]))
        turn = math.acos(max(-1.0, min(1.0, d1[0] * d2[0] + d1[1] * d2[1])))
        t = r * math.tan(turn / 2)
        s, e = (v[0] - d1[0] * t, v[1] - d1[1] * t), (v[0] + d2[0] * t, v[1] + d2[1] * t)
        line(out, out[-1], s, step)
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        nrm = (-d1[1], d1[0]) if cross > 0 else (d1[1], -d1[0])
        c = (s[0] + nrm[0] * r, s[1] + nrm[1] * r)
        a0 = math.atan2(s[1] - c[1], s[0] - c[0])
        a1 = math.atan2(e[1] - c[1], e[0] - c[0])
        if cross > 0 and a1 < a0:
            a1 += 2 * math.pi
        if cross < 0 and a1 > a0:
            a1 -= 2 * math.pi
        out += arc(c, r, a0, a1)[1:]
    line(out, out[-1], verts[-1], step)
    return out


def norm(v):
    m = math.hypot(*v)
    return v[0] / m, v[1] / m


def line(out, a, b, step=0.05):
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
    out += [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(1, n + 1)]


def _bez(p0, p1, p2, p3, n=12):
    out = []
    for k in range(n + 1):
        t = k / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def _s(p0, p3, axis):
    m = (p0[axis] + p3[axis]) / 2
    if axis == 0:
        return _bez(p0, (m, p0[1]), (m, p3[1]), p3)
    return _bez(p0, (p0[0], m), (p3[0], m), p3)


def _arcd(c, r, a0, a1, n=24):
    return [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def ramps_q0_segs(bez_n=5):
    """the same ramps as ramps_q0 as primitives in the plan frame (P, Q): ("line", p0, p1) and ("arc", c, R, a0, a1)
    (degrees in the (u, w) build frame, see _pq_arc), the S tapers as bez_n lines each. -> {"loop": [...], "outer": [...]}"""
    c = (EDGE + R_LOOP, -EDGE - R_LOOP)
    r_out = R_LOOP + 2 * RAMP_HALF + GAP
    top, left = (c[0], c[1] + R_LOOP), (c[0] - R_LOOP, c[1])
    turn = lambda p: (-p[1], -p[0])       # noqa: E731

    def bez(p0, p3, axis):
        pts = [turn(q) for q in _s(p0, p3, axis)]
        k = max(1, (len(pts) - 1) // bez_n)
        sel = pts[::k] if (len(pts) - 1) % k == 0 else pts[::k] + [pts[-1]]
        return [("line", u, v) for u, v in zip(sel, sel[1:])]

    def arcp(cc, r, a0, a1):
        return [("arc", turn(cc), r, a0, a1)]

    def lin(p0, p1):
        return [("line", turn(p0), turn(p1))]
    loop = bez((top[0] - LOOP_TAPER, -LANE_OUT), top, 0) + arcp(c, R_LOOP, 90, -180) +         bez(left, (LANE_OUT, left[1] + LOOP_TAPER), 1)
    b = (c[0], c[1] - r_out)
    rt = (c[0] + r_out, c[1])
    s0 = (EDGE, b[1] - RHO)
    out = bez((LANE_OUT, s0[1] - TAPER), s0, 1) + arcp((s0[0] + RHO, s0[1]), RHO, 180, 90)
    if s0[0] + RHO < b[0]:
        out += lin((s0[0] + RHO, b[1]), b)
    out += arcp(c, r_out, -90, 0)
    e0 = (rt[0], -EDGE - RHO)
    if e0[1] > rt[1]:
        out += lin(rt, e0)
    out += arcp((e0[0] + RHO, e0[1]), RHO, 180, 90)
    out += bez((e0[0] + RHO, -EDGE), (e0[0] + RHO + TAPER, -LANE_OUT), 0)
    return {"loop": loop, "outer": out}


def ramps_q0():
    """hwx.ramps_q0 with the diagonal's offsets, then turned into the plan frame. Built in hwx's local frame (u, w):
    carriageway '+u' (traffic +u, outer lane w = -LANE_OUT) and carriageway '+w' (traffic +w, outer lane u = +LANE_OUT),
    ramp lines u = EDGE and w = -EDGE. (u, w) -> (P, Q) = (-w, -u) is a 45-degree WORLD rotation (the plan frame is
    itself a mirror of (x, z)), so '+u' becomes NB, '+w' becomes WB and right turns stay right turns.
    -> {"loop": NB -> WB, "outer": WB -> NB} in (P, Q)."""
    c = (EDGE + R_LOOP, -EDGE - R_LOOP)
    r_out = R_LOOP + 2 * RAMP_HALF + GAP
    top, left = (c[0], c[1] + R_LOOP), (c[0] - R_LOOP, c[1])
    loop = _s((top[0] - LOOP_TAPER, -LANE_OUT), top, 0)[:-1]
    loop += _arcd(c, R_LOOP, 90, -180, 54)[:-1]
    loop += _s(left, (LANE_OUT, left[1] + LOOP_TAPER), 1)
    b = (c[0], c[1] - r_out)
    rt = (c[0] + r_out, c[1])
    s0 = (EDGE, b[1] - RHO)
    out = _s((LANE_OUT, s0[1] - TAPER), s0, 1)[:-1]
    out += _arcd((s0[0] + RHO, s0[1]), RHO, 180, 90, 12)[:-1]
    out += [(s0[0] + RHO, b[1])] if s0[0] + RHO < b[0] else []
    out += _arcd(c, r_out, -90, 0, 24)[:-1]
    e0 = (rt[0], -EDGE - RHO)
    out += [rt] if e0[1] > rt[1] else []
    out += _arcd((e0[0] + RHO, e0[1]), RHO, 180, 90, 12)[:-1]
    out += _s((e0[0] + RHO, -EDGE), (e0[0] + RHO + TAPER, -LANE_OUT), 0)
    turn = lambda pts: [(-w, -u) for (u, w) in pts]       # noqa: E731
    # hwx's outer ramp runs '+w' -> '+u'; in the plan frame that is WB -> NB, as wanted
    return {"loop": turn(loop), "outer": turn(out)}


class Geo:
    """One cloverleaf: parity 'c' (O on a cell centre) or 'h' (O on a cell corner); cells are relative to O's cell."""

    def __init__(self, par):
        self.par = par
        self.o = (0.5, 0.5) if par == "c" else (0.0, 0.0)
        self.q0 = ramps_q0()
        self.join = max(max(abs(p), abs(q)) for pts in self.q0.values() for (p, q) in pts)   # farthest join, along
        self.ext = self.join + 2.4                     # how far the arms are drawn / required
        self.elems = self._elements()
        self.cells = self._cover()

    # ------------------------------------------------------------------------------------------ elements
    def _elements(self):
        E = []
        L = self.ext
        E.append(dict(kind="hwA", name="A", pts=[(0.0, -L), (0.0, L)], half=BAND_HALF))
        E.append(dict(kind="hwB", name="B", pts=[(-L, 0.0), (L, 0.0)], half=BAND_HALF))
        # carriageway arrows (lane mid line) per direction, canonical NB then rotated
        quad = ["NE", "SE", "SW", "NW"]
        for k in range(4):
            q = quad[k]
            # NE canonical: loop NB -> WB, outer WB -> NB (hwx Q0 turned 45 degrees, see ramps_q0)
            for kind, nm in (("loop", "L"), ("outer", "O")):
                E.append(dict(kind=kind, name=nm + q, pts=[rot_pq(p, k) for p in self.q0[kind]], half=RAMP_HALF))
        return E

    def lanes(self):
        """carriageway mid lines with direction (for arrows): (name, pts in travel order)."""
        L = self.ext
        out = []
        for k, nm in enumerate(["NB", "EB", "SB", "WB"]):
            pts = [(LANE_MID, L), (LANE_MID, -L)]
            out.append((nm, [rot_pq(p, k) for p in pts]))
        return out

    # ------------------------------------------------------------------------------------------ cells
    def _cover(self):
        cells = {}
        for e in self.elems:
            pts = e["pts"]
            dense = []
            for a, b in zip(pts, pts[1:]):
                line(dense, a, b, 0.04)
            for (p, q) in dense:
                if e["kind"] in ("loop", "outer") and min(abs(p), abs(q)) + e["half"] <= DECK_HALF + 0.02:
                    continue                    # ramp deck inside the band: the ramp lane IS the outer lane there
                x, z = to_xz(p, q, self.o)
                h = e["half"] * 0.999
                for i in range(math.floor(x - h), math.floor(x + h) + 1):
                    for j in range(math.floor(z - h), math.floor(z + h) + 1):
                        dx = max(i - x, 0, x - (i + 1))
                        dz = max(j - z, 0, z - (j + 1))
                        if dx * dx + dz * dz < h * h:
                            cells.setdefault((i, j), set()).add(e["name"])
        return cells

    def box(self):
        """bounding box of the written cells -> (width, height) in cells"""
        W = self.written()
        return (max(c[0] for c in W) - min(c[0] for c in W) + 1, max(c[1] for c in W) - min(c[1] for c in W) + 1)

    def centre_pq(self, c):
        return to_pq(c[0] + 0.5, c[1] + 0.5, self.o)

    def along_min(self, c):
        """-> (min |P|, min |Q|) over the cell square: how close the cell reaches to O along B and along A"""
        cs = [to_pq(c[0] + a, c[1] + b, self.o) for a in (0, 1) for b in (0, 1)]
        ps, qs = [v[0] for v in cs], [v[1] for v in cs]
        mp = 0.0 if min(ps) <= 0 <= max(ps) else min(abs(v) for v in ps)
        mq = 0.0 if min(qs) <= 0 <= max(qs) else min(abs(v) for v in qs)
        return mp, mq

    def role(self, c):
        s = self.cells.get(c, set())
        mp, mq = self.along_min(c)
        ramps = sorted(n for n in s if n[0] in "LO")
        if ("A" in s and "B" in s) or ("A" in s and mq < FLY) or ("B" in s and mp < FLY):
            return "XM" if ramps else "X"   # crossing / slope; XM = a loop's deck runs into it too
        if ramps and ("A" in s or "B" in s):
            return "M"                      # merge / diverge: highway + ramp
        if ramps:
            return "R"
        if s:
            return "S"                      # plain band: stays stock
        return ""

    def written(self):
        return {c for c in self.cells if self.role(c) in ("X", "XM", "M", "R")}

    def stock_piece(self, c):
        """the stock piece (id, state) the cell holds after the two drags (measured 2026-10-18): the stub around O or a
        plain band cell; None for land"""
        st = STUB[self.par].get(tuple(c))
        if st:
            return st
        return band_piece(self.o, c)

    def _assign(self, cells, start, c4):
        """{cell: (id, state)} with the game's state convention (state s = the content turned s times by R, (x, z) ->
        (-z, x), sc3netmod_hwy.c hwy_rot): C4 orbits for ramp-only cells, C2 for cells on the highway, whose piece
        state must be the stock state of the cell (it saves as its base at that state); the representative is the
        member whose stock state is 0, so every piece's art and lanes are painted / cut at state 0 in world frame."""
        out, rep, nxt = {}, {}, start
        for c in sorted(cells, key=lambda c: (c[1], c[0])):
            if c in out:
                continue
            land = self.role(c) == "R" if c4 else False
            turns = (0, 1, 2, 3) if land else (0, 2)
            orbit = [rot_cell_R(c, k, self.par) for k in turns]
            if not land:
                sp = [self.stock_piece(m) for m in orbit]
                if sp[0] is None or sp[1] is None or sp[0][0] != sp[1][0]:
                    raise SystemExit("cell %s: half-turn twin holds another stock piece: %s" % (c, sp))
                if sp[0][1] != 0 and sp[1][1] == 0:
                    orbit = orbit[::-1]
                    sp = sp[::-1]
                if sp[0][1] != 0 or sp[1][1] not in (0, 2):
                    raise SystemExit("cell %s: stock states %s cannot share a piece" % (c, sp))
            for k, m in zip(turns, orbit):
                if m in cells and m not in out:
                    out[m] = (nxt, k)
            rep[nxt] = orbit[0]
            nxt += 1
        return out, rep, nxt

    def ids(self, start):
        """cloverleaf pieces -> ({cell: (id, state)}, next id)"""
        out, _, nxt = self._assign(self.written(), start, True)
        return out, nxt

    def flyover_ids(self, ids, start):
        """the fallback (no ramps): every crossing cell (X and XM) gets its own flyover piece (C2) -> ({cell: (id,
        state)}, next id). `ids` is unused (kept for the callers)."""
        out, _, nxt = self._assign({c for c in self.written() if self.role(c) in ("X", "XM")}, start, False)
        return out, nxt

    def reps(self, start, flyover=False):
        """{id: representative cell} (state 0) of the cloverleaf or the flyover set"""
        cells = {c for c in self.written() if self.role(c) in ("X", "XM")} if flyover else self.written()
        return self._assign(cells, start, not flyover)[1]

    def lane_steps(self):
        """per ramp lane: number of steps between cells that are diagonal (the lane passes a cell corner)."""
        res = {}
        for e in self.elems:
            if e["kind"] not in ("loop", "outer"):
                continue
            seq = []
            dense = []
            for a, b in zip(e["pts"], e["pts"][1:]):
                line(dense, a, b, 0.01)
            for (p, q) in dense:
                x, z = to_xz(p, q, self.o)
                c = (math.floor(x), math.floor(z))
                if not seq or seq[-1] != c:
                    seq.append(c)
            diag = sum(1 for a, b in zip(seq, seq[1:]) if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1)
            res[e["name"]] = (len(seq), diag)
        return res


STOCK_HALF = """\
  26  11223.2 11224.0 15051.2 15051.2 15106.0 15052.0
  27     .    73.2    15149.0 15149.0    73.0     .
  28     .    73.2    15149.0 15149.0    73.0     .
  29  15052.2 15106.0 15051.0 15051.0 11224.0 11223.0
         55     56      57      58      59      60"""
STOCK_CENTRE = """\
  14  11223.2 11224.0 15051.2 15106.0 15052.0
  15     .    73.2    15149.0    73.0     .
  16  15052.2 15106.0 15051.0 11224.0 11223.0
        131     132     133     134     135"""


# ---------------------------------------------------------------------------------------------- plan picture
def plan_png(out):
    from PIL import Image, ImageDraw, ImageFont
    F = lambda s, b=False: ImageFont.truetype("arialbd.ttf" if b else "arial.ttf", s)   # noqa: E731
    FM = ImageFont.truetype("consola.ttf", 13)
    S = 31                                    # px per true cell
    geos = [Geo("c"), Geo("h")]
    global FLY_IDS
    i0, n0 = geos[0].ids(ID0)
    i1, n1 = geos[1].ids(n0)
    _, n2 = geos[0].flyover_ids(i0, n1)
    _, n3 = geos[1].flyover_ids(i1, n2)
    FLY_IDS = (n1, n3 - 1)
    span = max(g.ext for g in geos) + 0.6
    PW = int(2 * span * S)
    W = max(2 * PW + 60, 1600)
    H = PW + 420
    im = Image.new("RGB", (W, H), (250, 250, 247))
    d = ImageDraw.Draw(im)
    d.text((20, 10), "hwdd plan: diagonal highway x diagonal highway = a cloverleaf turned 45 degrees "
           "(top-down, oriented like the game at rotation 0)", font=F(20, True), fill=(20, 20, 20))
    d.text((20, 38), "Grey band = stock diagonal highway (A: x-z family, vertical here; B: x+z family, horizontal). "
           "A crosses OVER B on a deck. Blue = loops (left turns), green = outer ramps (right turns): hwx's ramps "
           "turned 45 degrees. Arrows = travel, right-hand.",
           font=F(13), fill=(40, 40, 40))
    COL = {"X": (240, 170, 170), "XM": (215, 160, 215), "M": (250, 205, 140), "R": (250, 240, 170), "S": (222, 222, 222)}
    nxt = ID0
    for gi, g in enumerate(geos):
        ox, oy = 30 + gi * (PW + 10) + PW / 2, 70 + PW / 2

        def sp(p, q):
            return ox + p * S, oy + q * S

        def cell_poly(c):
            return [sp(*to_pq(x, z, g.o)) for (x, z) in ((c[0], c[1]), (c[0] + 1, c[1]), (c[0] + 1, c[1] + 1),
                                                          (c[0], c[1] + 1))]
        n = int(span * SQ2) + 2
        ids, nxt = g.ids(nxt if gi else ID0)
        # cells
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                c = (i, j)
                pts = cell_poly(c)
                if not all(30 + gi * (PW + 10) <= x <= 30 + gi * (PW + 10) + PW and 70 <= y <= 70 + PW
                           for x, y in pts):
                    continue
                r = g.role(c)
                d.polygon(pts, fill=COL.get(r, (236, 244, 230)), outline=(200, 205, 200))
        # elements: B (under) first, then ramps, then A deck on top
        def stroke(pts, w, col):
            d.line([sp(*p) for p in pts], fill=col, width=w, joint="curve")

        for e in g.elems:
            if e["kind"] == "hwB":
                stroke(e["pts"], int(2 * DECK_HALF * S), (120, 120, 125))
        for e in g.elems:
            if e["kind"] in ("loop", "outer"):
                stroke(e["pts"], int(2 * RAMP_HALF * S), (60, 110, 200) if e["kind"] == "loop" else (50, 150, 70))
        for e in g.elems:
            if e["kind"] == "hwA":
                p0, p1 = e["pts"]
                stroke([p0, (0, -FLY - 0.3)], int(2 * DECK_HALF * S), (120, 120, 125))
                stroke([(0, FLY + 0.3), p1], int(2 * DECK_HALF * S), (120, 120, 125))
                # the deck over B
                x0, y0 = sp(-DECK_HALF, -FLY - 0.3)
                x1, y1 = sp(DECK_HALF, FLY + 0.3)
                d.rectangle([x0, y0, x1, y1], fill=(95, 95, 100), outline=(20, 20, 20), width=3)
        # lane arrows on carriageways
        for nm, (a, b) in g.lanes():
            v = norm((b[0] - a[0], b[1] - a[1]))
            for t in [-g.ext + 1.0 + 2.2 * k for k in range(int(2 * g.ext / 2.2))]:
                p = (a[0] + (b[0] - a[0]) * (t + g.ext) / (2 * g.ext), a[1] + (b[1] - a[1]) * (t + g.ext) / (2 * g.ext))
                arrow(d, sp(*p), v, (255, 255, 255), 9)
        for e in g.elems:
            if e["kind"] in ("loop", "outer"):
                pts = e["pts"]
                for f in (0.3, 0.7) if e["kind"] == "outer" else (0.2, 0.5, 0.8):
                    k = int(f * (len(pts) - 2))
                    v = norm((pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]))
                    arrow(d, sp(*pts[k]), v, (255, 255, 255), 7)
        # ids
        for c, (pid, st) in ids.items():
            x, y = sp(*g.centre_pq(c))
            t = "%d" % (pid - ID0)
            d.text((x - d.textlength(t, font=F(10, True)) / 2, y - 9), t, font=F(10, True), fill=(10, 10, 10))
            d.text((x - 3, y + 1), str(st), font=F(9), fill=(90, 30, 30))
        # O
        x, y = sp(0, 0)
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(200, 0, 0))
        # grid axes hint
        ax, ay = 30 + gi * (PW + 10) + 40, 70 + PW - 40
        arrow(d, (ax, ay), norm((-1, 1)), (40, 40, 40), 22, label="x+", font=F(12))
        arrow(d, (ax, ay), norm((1, 1)), (40, 40, 40), 22, label="z+", font=F(12))
        W_ = g.written()
        title = ("O on a cell CENTRE (stock: 3x3 stub, 1 cell 15149)" if g.par == "c"
                 else "O on a cell CORNER (stock: 4x4 stub, 2x2 15149)")
        d.rectangle([30 + gi * (PW + 10), 70, 30 + gi * (PW + 10) + PW, 70 + PW], outline=(80, 80, 80), width=1)
        d.text((36 + gi * (PW + 10), 74), title, font=F(15, True), fill=(20, 20, 20))
        steps = g.lane_steps()
        nd = sum(v[1] for v in steps.values())
        d.text((36 + gi * (PW + 10), 94),
               "%dx%d, %d cells (%d crossing, %d hw+ramp, %d ramp), ids %d..%d"
               % (g.box()[0], g.box()[1],
                  len(W_), sum(1 for c in W_ if g.role(c) in ("X", "XM")), sum(1 for c in W_ if g.role(c) == "M"),
                  sum(1 for c in W_ if g.role(c) == "R"), min(v[0] for v in ids.values()),
                  max(v[0] for v in ids.values())), font=F(12), fill=(40, 40, 40))
    # legend + rule text
    y = 70 + PW + 14
    x = 30
    for k, lab in (("X", "crossing: A deck over B (one id per half-turn pair); also the fallback flyover's piece"),
                   ("XM", "crossing + a loop's join: the fallback flyover uses a ramp-free twin id"),
                   ("M", "highway + ramp (merge / diverge)"), ("R", "ramp only"),
                   ("S", "plain diagonal highway: stays stock")):
        d.rectangle([x, y, x + 18, y + 14], fill=COL[k], outline=(120, 120, 120))
        d.text((x + 24, y), lab, font=F(13), fill=(30, 30, 30))
        y += 20
    d.text((x, y + 2), "Cell label: id - 21360 (top), state (bottom). Ramp-only cells repeat in the 4 quadrants as one "
           "id in 4 states;", font=F(13), fill=(30, 30, 30))
    d.text((x, y + 19), "highway + ramp and crossing cells only by a half turn (stock A turned a quarter is not stock B "
           "in every view frame).", font=F(13), fill=(30, 30, 30))
    y += 44
    rule = [
        "RULE (after every highway retile and city load, net 4):",
        "  an A band (rows 11223/11224/11223) and a B band (15052/15106/15052) whose centrelines meet at O, with the stock",
        "  stub between them (15149 + 73/15051, either parity). Each of the 4 arms runs as a clean band at least %d rows past"
        % ARM_ROWS,
        "  the outer ramps' joins. Every cell the cloverleaf writes is free (no building, zone or other network; trees are",
        "  cleared) and flat at the bands' height. Then: write the cloverleaf (cells above).",
        "FALLBACK: arms long enough for the stub but quadrants not free -> FLYOVER only (the crossing cells: A goes on over",
        "  a deck, B under it, no ramps; red cells keep their id, purple ones take a ramp-free twin %d..%d)." % FLY_IDS,
        "REFUSED (stock left as is): arms too short, slope, a third highway / road / avenue in the footprint, a T (one",
        "  diagonal ends on the other), two crossings whose footprints overlap, a diagonal x straight (stream hwdx).",
        "REVERT: a later edit that breaks the pattern (bulldozed ramp, zone, new road) takes the ramps out and restores",
        "  what still qualifies (cloverleaf -> flyover -> stock). Saves store stock ids (rb_save_id): no mod = stock stub.",
    ]
    for ln in rule:
        d.text((x, y), ln, font=FM, fill=(20, 20, 20))
        y += 17
    # stock aftermath (right side of the bottom area)
    sx = W - 440
    yy = 70 + PW + 14
    d.text((sx, yy), "STOCK aftermath, measured in game 2026-10-18 (lab, cells id.state):", font=F(13, True),
           fill=(20, 20, 20))
    yy += 20
    for ttl, txt in (("O on a corner (x-z = 30, x+z = 86):", STOCK_HALF), ("O on a centre (x-z = 118, x+z = 149):",
                                                                          STOCK_CENTRE)):
        d.text((sx, yy), ttl, font=F(12), fill=(40, 40, 40))
        yy += 16
        for ln in txt.splitlines():
            d.text((sx, yy), ln, font=FM, fill=(20, 20, 20))
            yy += 15
        yy += 6
    im.save(out)
    return out


def arrow(d, p, v, col, size, label=None, font=None):
    x, y = p
    tip = (x + v[0] * size * 0.6, y + v[1] * size * 0.6)
    back = (x - v[0] * size * 0.4, y - v[1] * size * 0.4)
    nx, ny = -v[1], v[0]
    if label is None:
        d.polygon([tip, (back[0] + nx * size * 0.35, back[1] + ny * size * 0.35),
                   (back[0] - nx * size * 0.35, back[1] - ny * size * 0.35)], fill=col, outline=(30, 30, 30))
    else:
        tip = (x + v[0] * size * 2, y + v[1] * size * 2)
        d.line([p, tip], fill=col, width=2)
        d.polygon([tip, (tip[0] - v[0] * 8 + nx * 4, tip[1] - v[1] * 8 + ny * 4),
                   (tip[0] - v[0] * 8 - nx * 4, tip[1] - v[1] * 8 - ny * 4)], fill=col)
        d.text((tip[0] + v[0] * 4 - 6, tip[1] + v[1] * 4 - 6), label, font=font, fill=col)


# ------------------------------------------------------------------------------------------------ router flows
# The SimTransit router reads each highway piece's turn matrix (prop 310: side entered -> side left), sides only. A
# flow = one carriageway or ramp as the chain of cells it crosses with (entry side, exit side) per cell; sides as
# lanekit: 0 x-, 1 z-, 2 x+, 3 z+.
SIDE_D = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}
OPP = {0: 2, 1: 3, 2: 0, 3: 1}
CARRIAGEWAYS = {"NB": (0, (LANE_IN + LANE_OUT) / 2, -1), "SB": (0, -(LANE_IN + LANE_OUT) / 2, 1),
                "EB": (1, (LANE_IN + LANE_OUT) / 2, 1), "WB": (1, -(LANE_IN + LANE_OUT) / 2, -1)}


def _chain(o, pts):
    """dense (P, Q) points -> [[cell, entry side, exit side]] (None at an end inside a cell)"""
    seq = []
    dense = []
    for a, b in zip(pts, pts[1:]):
        line(dense, a, b, 0.005)
    prev = None
    for (p, q) in dense:
        x, z = to_xz(p, q, o)
        c = (math.floor(x), math.floor(z))
        if c != prev:
            if prev is not None:
                d = (c[0] - prev[0], c[1] - prev[1])
                if abs(d[0]) + abs(d[1]) != 1:
                    raise SystemExit("flow passes a cell corner at %s -> %s" % (prev, c))
                side = [k for k, v in SIDE_D.items() if v == d][0]
                seq[-1][2] = side
                seq.append([c, OPP[side], None])
            else:
                seq.append([c, None, None])
            prev = c
    return seq


# Corner parity: in the 2x2 under O the true staircases of A and B enter cells by the same sides (NB with WB, SB with
# EB: the router would turn between the highways there without a ramp). B's two directions take other staircases
# through the 4x4 crossing zone instead (sides only; the drawn lanes keep the true geometry). Found by search over
# every monotone staircase of the four carriageways in the zone: no shared entry, A unchanged, no U-turn cell.
CORE_H = {"EB": [((1, -2), 2, 3), ((1, -1), 1, 3), ((1, 0), 1, 0), ((0, 0), 2, 3), ((0, 1), 1, 0), ((-1, 1), 2, 0),
                 ((-2, 1), 2, 3)],
          "WB": [((-2, 1), 0, 1), ((-2, 0), 3, 1), ((-2, -1), 3, 2), ((-1, -1), 0, 1), ((-1, -2), 3, 2),
                 ((0, -2), 0, 2), ((1, -2), 0, 1)]}


def _override(ch, seq):
    """replace the run of chain `ch` from seq's first cell to its last cell by seq"""
    cells = [f[0] for f in ch]
    a, b = cells.index(seq[0][0]), cells.index(seq[-1][0])
    if ch[a][1] != seq[0][1] or ch[b][2] != seq[-1][2]:
        raise SystemExit("core override does not meet the chain at %s / %s" % (seq[0][0], seq[-1][0]))
    return ch[:a] + [list(f) for f in seq] + ch[b + 1:]


def flows(g, reach):
    """-> {name: [[cell, e, l], ...]}: the 4 carriageways (lane mid line, `reach` cells along each band either side
    of O) and the 8 ramps. A ramp's first cell enters by the side its carriageway enters that cell, its last cell
    leaves by the side its carriageway leaves (it splits off / merges into it there)."""
    out = {}
    for nm, (ax, off, sgn) in CARRIAGEWAYS.items():
        pts = [(off, -sgn * reach), (off, sgn * reach)] if ax == 0 else [(-sgn * reach, off), (sgn * reach, off)]
        # NB: A (P = const), travel -Q; SB: +Q; EB: B (Q = const), travel +P; WB: -P
        if nm in ("NB", "SB"):
            pts = [(off, -sgn * reach), (off, sgn * reach)]
        else:
            pts = [(-sgn * reach, off), (sgn * reach, off)]
        out[nm] = _chain(g.o, pts)
        if g.par == "h" and nm in CORE_H:
            out[nm] = _override(out[nm], CORE_H[nm])
    q0 = ramps_q0()
    quad = ["NE", "SE", "SW", "NW"]
    start_cw = {"loop": ["NB", "EB", "SB", "WB"], "outer": ["WB", "NB", "EB", "SB"]}
    end_cw = {"loop": ["WB", "NB", "EB", "SB"], "outer": ["NB", "EB", "SB", "WB"]}
    for k in range(4):
        for kind in ("loop", "outer"):
            nm = ("L" if kind == "loop" else "O") + quad[k]
            ch = _chain(g.o, [rot_pq(p, k) for p in q0[kind]])
            cs, ce = out[start_cw[kind][k]], out[end_cw[kind][k]]
            e0 = [f for f in cs if f[0] == ch[0][0]]
            e1 = [f for f in ce if f[0] == ch[-1][0]]
            if not e0 or not e1:
                raise SystemExit("ramp %s starts / ends in a cell its carriageway does not cross: %s %s"
                                 % (nm, ch[0][0], ch[-1][0]))
            ch[0][1] = e0[0][1]
            ch[-1][2] = e1[0][2]
            out[nm] = ch
    return out


def cell_flows(g, fl):
    """{cell: [(flow name, e, l)]}"""
    out = {}
    for nm, ch in fl.items():
        for c, e, l in ch:
            if e is not None and l is not None:
                out.setdefault(c, []).append((nm, e, l))
    return out


RAMP_FROM = {"LNE": "NB", "LSE": "EB", "LSW": "SB", "LNW": "WB", "ONE": "WB", "OSE": "NB", "OSW": "EB", "ONW": "SB"}
RAMP_TO = {"LNE": "WB", "LSE": "NB", "LSW": "EB", "LNW": "SB", "ONE": "NB", "OSE": "EB", "OSW": "SB", "ONW": "WB"}


def clashes(cf, fl):
    """cells where flows share an entry side but leave by different sides and are not one carriageway with its own
    ramps (the router would let a car switch between them there) -> [(cell, [flows])]"""
    bad = []
    for c, fs in sorted(cf.items()):
        by = {}
        for nm, e, l in fs:
            by.setdefault(e, []).append(nm)
        for e, nms in by.items():
            if len(nms) < 2:
                continue
            roads = [n for n in nms if n not in RAMP_FROM]
            ramps = [n for n in nms if n in RAMP_FROM]
            if len({l for _, e2, l in fs if e2 == e}) == 1:
                continue                                  # same exit: no turn the flows do not already make
            if len(roads) <= 1 and all(roads[0] in (RAMP_FROM[r], RAMP_TO[r]) for r in ramps) if roads else False:
                continue                                  # a carriageway and its own ramps: the split / the merge
            bad.append((c, nms))
    return bad


def movements(g, cf, reach):
    """every (from, to) carriageway pair the router can reach over the turn sides, starting far out on each inbound
    carriageway and arriving far out on each outbound one"""
    from collections import deque
    fl = flows(g, reach)
    ends = {nm: (ch[1][0], ch[-2][0]) for nm, ch in fl.items() if nm in CARRIAGEWAYS}
    pairs = {}
    for c, fs in cf.items():
        for nm, e, l in fs:
            pairs.setdefault(c, set()).add((e, l))
    res = {}
    for a, (cin, _) in ends.items():
        e_in = [f[1] for f in fl[a] if f[0] == cin][0]
        seen, dq = set(), deque([(cin, e_in)])
        while dq:
            w, e = dq.popleft()
            if (w, e) in seen:
                continue
            seen.add((w, e))
            for e2, l2 in pairs.get(w, ()):
                if e2 == e:
                    d = SIDE_D[l2]
                    dq.append(((w[0] + d[0], w[1] + d[1]), OPP[l2]))
        cells = {w for w, e in seen}
        for b, (_, cout) in ends.items():
            res[(a, b)] = cout in cells
    return res


def matrices(g, fly):
    """{cell: sorted [(entry, exit)]} for the written cells of a mode (flyover: carriageways only)"""
    fl = flows(g, g.ext + 2)
    if fly:
        fl = {k: v for k, v in fl.items() if k in CARRIAGEWAYS}
    out = {}
    for c, fs in cell_flows(g, fl).items():
        out[c] = sorted({(e, l) for _, e, l in fs})
    return out


def cmd_flows(par):
    g = Geo(par)
    reach = g.ext + 2
    fl = flows(g, reach)
    cf = cell_flows(g, fl)
    bad = clashes(cf, fl)
    print("parity %s: %d flows, %d cells; clashes: %d" % (par, len(fl), len(cf), len(bad)))
    for c, nms in bad:
        print("  clash at %s (%s): %s" % (c, g.role(c) or "-", nms))
    mv = movements(g, cf, reach)
    print("  movements:", " ".join("%s->%s:%s" % (a, b, "Y" if v else ".") for (a, b), v in sorted(mv.items())))


LAND_BASE = 15099            # Protected HWAY base for pieces written into free cells (hwcore's choice, as hwdx)
CHECK_MARGIN = ARM_ROWS      # cells around the written box whose band cells must be plain stock (the arms go on)


def plan_all():
    """-> {"c": {...}, "h": {...}}: per parity the cloverleaf and flyover tables, ids assigned in one sequence
    (cloverleaf c, cloverleaf h, flyover c, flyover h). Table row: (dx, dz, role, id, state, base, base state, land);
    role 1 crossing, 2 highway + ramp, 3 ramp (land), 4 plain band to check, 5 no highway allowed."""
    gs = {par: Geo(par) for par in "ch"}
    nxt = ID0
    cl, fl, reps = {}, {}, {}
    for par in "ch":
        cl[par], nxt = gs[par].ids(nxt)
    for par in "ch":
        fl[par], nxt = gs[par].flyover_ids(None, nxt)
    if nxt - 1 > 21459:
        raise SystemExit("ids run past 21459: %d" % (nxt - 1))
    out = {}
    for par in "ch":
        g = gs[par]
        W = g.written()

        def table(ids, cells):
            x0 = min(c[0] for c in cells) - CHECK_MARGIN
            x1 = max(c[0] for c in cells) + CHECK_MARGIN
            z0 = min(c[1] for c in cells) - CHECK_MARGIN
            z1 = max(c[1] for c in cells) + CHECK_MARGIN
            rows = []
            for z in range(z0, z1 + 1):
                for x in range(x0, x1 + 1):
                    c = (x, z)
                    if c in cells:
                        pid, st = ids[c]
                        r = g.role(c)
                        role = {"X": 1, "XM": 1, "M": 2, "R": 3}[r]
                        if r == "R":
                            rows.append((x, z, 3, pid, st, LAND_BASE, 0, 1))
                        else:
                            b, bs = g.stock_piece(c)
                            rows.append((x, z, role, pid, st, b, bs, 0))
                    else:
                        sp = g.stock_piece(c)
                        if sp:
                            rows.append((x, z, 4, 0, 0, sp[0], sp[1], 0))
                        elif c not in g.cells:
                            rows.append((x, z, 5, 0, 0, 0, 0, 0))
            return rows
        Wx = {c for c in W if g.role(c) in ("X", "XM")}
        out[par] = {"clover": table(cl[par], W), "fly": table(fl[par], Wx),
                    "stub": sorted((c[0], c[1], v[0], v[1]) for c, v in STUB[par].items()),
                    "geo": g, "cl": cl[par], "fl": fl[par]}
    out["next"] = nxt
    return out


def ctab(path):
    T = plan_all()
    L = ["/* sc3netmod_hwdd_tab.h - generated by re/tools/netmod/hwdd.py ctab (task hwdd). Do not edit: regenerate. */",
         "/* Frames: 'c' = O at the centre of cell (0,0), 'h' = O at the corner of cell (0,0) (its low x, low z corner). */",
         "/* row: dx, dz, role (1 crossing, 2 highway+ramp, 3 ramp on land, 4 plain band to check, 5 no highway), */",
         "/*      piece id, piece state, base id, base state (the stock piece the cell holds), land */",
         "#define HWDD_ID0 %d" % ID0, "#define HWDD_ID1 %d" % (T["next"] - 1), ""]
    for par in "ch":
        for kind in ("clover", "fly"):
            rows = T[par][kind]
            L.append("#define HWDD_N_%s_%s %d" % (kind.upper(), par.upper(), len(rows)))
            L.append("static const HwddRow g_hwdd_%s_%s[] = {" % (kind, par))
            for r in rows:
                L.append("    {%d, %d, %d, %d, %d, %d, %d, %d}," % r)
            L.append("};")
        st = T[par]["stub"]
        L.append("#define HWDD_N_STUB_%s %d" % (par.upper(), len(st)))
        L.append("static const HwddStub g_hwdd_stub_%s[] = {" % par)
        for r in st:
            L.append("    {%d, %d, %d, %d}," % r)
        L.append("};")
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print(path, "ids %d..%d" % (ID0, T["next"] - 1), {par: {k: len(T[par][k]) for k in ("clover", "fly")} for par in "ch"})


# ------------------------------------------------------------------------------------------------ offline twin
CAPS = (14999, 15059, 15053, 15054, 11235, 11237)   # highway end caps (sc3netmod_hwdd.c hwdd_cap)


class Lab:
    """a map for the twin: {cell: (id, state)} highway occupants, a set of blocked land cells (buildings)"""

    def __init__(self, lay, blocked=()):
        self.lay, self.blocked = dict(lay), set(blocked)

    def at(self, c):
        return self.lay.get(c)


def _is(v, id_, st):
    if not v or v[0] != id_:
        return False
    return v[1] == st or (id_ in (11224, 15106, 15149) and (v[1] - st) % 2 == 0)


def aftermath(par, O, reach=12, cut=None):
    """the stock map after the two drags (measured): both bands `reach` cells out from O along the band, the stub
    around O. O = frame origin (world cell). cut = (arm, d): that arm (N = A toward -Q) stops d cells past O"""
    g = Geo(par)
    lay = {}
    for i in range(-reach - 2, reach + 3):
        for j in range(-reach - 2, reach + 3):
            sp = band_piece(g.o, (i, j))
            if not sp:
                continue
            p_, q_ = to_pq(i + 0.5, j + 0.5, g.o)
            if max(abs(p_), abs(q_)) > reach:
                continue
            if cut and cut[0] == "N" and q_ < -cut[1] and abs(p_) < 1:
                continue
            lay[(O[0] + i, O[1] + j)] = sp
    for c, v in STUB[par].items():
        lay[(O[0] + c[0], O[1] + c[1])] = v
    return lay


def twin_pass(lab, box, T):
    """hwdd_run on the twin -> (results, writes {cell: (id, st)}, kept cells)"""
    x0, z0, x1, z1 = box

    def inbox(c):
        return x0 < c[0] < x1 and z0 < c[1] < z1
    ids = set()
    for par in "ch":
        for kind in ("clover", "fly"):
            ids |= {r[3] for r in T[par][kind] if r[3]}
    lo, hi = min(ids), max(ids)

    def mine(v):
        return bool(v) and lo <= v[0] <= hi
    cands = []
    for z in range(z0, z1 + 1):
        for x in range(x0, x1 + 1):
            v = lab.at((x, z))
            if not v:
                continue
            if v[0] == 15149:
                for par, offs in (("c", [(0, 0)]), ("h", [(1, 1), (0, 1), (1, 0), (0, 0)])):
                    for dx, dz in offs:
                        o = (x + dx, z + dz)
                        if all(_is(lab.at((o[0] + r[0], o[1] + r[1])), r[2], r[3]) for r in T[par]["stub"]):
                            if (o, par) not in cands:
                                cands.append((o, par))
            elif mine(v):
                for par in "ch":
                    for kind in ("clover", "fly"):
                        for r in T[par][kind]:
                            if r[3] == v[0] and r[4] == v[1]:
                                o = (x - r[0], z - r[1])
                                if (o, par) not in cands:
                                    cands.append((o, par))

    def test(o, par, kind):
        rows = T[par][kind]
        nland = have = free = 0
        allin = True
        for (dx, dz, role, pid, st, base, bst, land) in rows:
            c = (o[0] + dx, o[1] + dz)
            v = lab.at(c)
            m = bool(v) and v == (pid, st)
            if role == 4 and (not v or v[0] in CAPS):      # task hwcap2: the arm ends on this band row or before it
                if base in (11223, 11224):
                    step = (1, 1) if dx + dz > 0 else (-1, -1)
                else:
                    step = (1, -1) if dx - dz > 0 else (-1, 1)
                if not hwcap.end(lab.lay, c, step):
                    return 0
                continue
            if role == 2 and not m and (not v or v[0] in CAPS):         # task hwcap2: it ends inside the joining rows
                return 0
            if role in (1, 2):
                if not v:                             # any highway: a stock retile may have re-placed the cell
                    return 0
                allin = allin and inbox(c)
                have += m
            elif role == 3:
                nland += 1
                if m:
                    have += 1
                    continue
                if v:
                    return 0
                if not inbox(c):
                    allin = False
                    continue
                if c not in lab.blocked:
                    free += 1
            elif role == 4:
                if not v or v[0] in CAPS:             # the arm goes on (any highway piece but an end cap)
                    return 0
            elif v and not mine(v):
                return 0
        if nland:
            hl = sum(1 for r in rows if r[2] == 3 and lab.at((o[0] + r[0], o[1] + r[1])) == (r[3], r[4]))
            if hl == nland:
                return 1
            if hl or free != nland or not allin:
                return 0
            return 2
        if have:
            return 1
        return 2 if allin else 0

    res, writes, kept = [], {}, set()
    for o, par in cands:
        r, kind = test(o, par, "clover"), "clover"
        if not r:                                           # hwdd_unbuild: clover cells outside the box go back
            for (dx, dz, role, pid, st, base, bst, land) in T[par]["clover"]:
                c = (o[0] + dx, o[1] + dz)
                if role <= 3 and not inbox(c) and lab.at(c) == (pid, st):
                    writes[c] = None if role == 3 else (base, bst)
            r, kind = test(o, par, "fly"), "fly"
        if not r:
            res.append((o, par, "none"))
            continue
        res.append((o, par, ("built " if r == 2 else "kept ") + kind))
        for (dx, dz, role, pid, st, base, bst, land) in T[par][kind]:
            if role <= 3:
                c = (o[0] + dx, o[1] + dz)
                if lab.at(c) != (pid, st):
                    writes[c] = (pid, st)
                kept.add(c)
    return res, writes, kept


def twin_end(lab, box, writes, kept, T, before):
    """apply the writes, then hwy_end's revert inside the box: unkept HWDD pieces go back (land: removed,
    on-highway: the stock piece the cell held before, as the in-place retile would put it)"""
    x0, z0, x1, z1 = box
    land = {r[3] for par in "ch" for k in ("clover", "fly") for r in T[par][k] if r[7]}
    allids = {r[3] for par in "ch" for k in ("clover", "fly") for r in T[par][k] if r[3]}
    for c, v in writes.items():
        if v is None:
            lab.lay.pop(c, None)
        else:
            lab.lay[c] = v
    for c, v in list(lab.lay.items()):
        if v[0] in allids and c not in kept and x0 < c[0] < x1 and z0 < c[1] < z1:
            if v[0] in land:
                del lab.lay[c]
            else:
                lab.lay[c] = before[c]


def saves_ok(lab, before, T):
    """every HWDD piece saves as its base at its state: that must be what the cell held after the drags"""
    base = {}
    for par in "ch":
        for k in ("clover", "fly"):
            for r in T[par][k]:
                if r[3]:
                    base[r[3]] = r[5]
    bad = []
    for c, (pid, st) in lab.lay.items():
        if pid in base:
            b = base[pid]
            if b == LAND_BASE:
                if c in before:
                    bad.append((c, "land piece on a highway cell"))
            elif not _is(before.get(c), b, st):
                bad.append((c, (pid, st), "saves as", (b, st), "held", before.get(c)))
    return bad


def cmd_check():
    T = plan_all()
    fails = 0
    for par, O in (("c", (133, 15)), ("h", (58, 28))):
        before = aftermath(par, O)
        box = (O[0] - 20, O[1] - 20, O[0] + 20, O[1] + 20)
        lab = Lab(before)
        res, w, kept = twin_pass(lab, box, T)
        twin_end(lab, box, w, kept, T, before)
        r1 = [r[2] for r in res]
        n1 = len(w)
        res2, w2, kept2 = twin_pass(lab, box, T)
        r2 = [r[2] for r in res2]
        bad = saves_ok(lab, before, T)
        print("%s O %s: fresh -> %s (%d cells written); again -> %s (%d writes); saves %s" % (
            par, O, r1, n1, r2, len(w2), "ok" if not bad else bad[:3]))
        fails += (r1 != ["built clover"]) + (r2 != ["kept clover"] or bool(w2)) + bool(bad)
        land = [(O[0] + r[0], O[1] + r[1]) for r in T[par]["clover"] if r[2] == 3]
        dead = land[len(land) // 3]
        del lab.lay[dead]
        b3 = (dead[0] - 8, dead[1] - 8, dead[0] + 8, dead[1] + 8)
        res3, w3, k3 = twin_pass(lab, b3, T)
        twin_end(lab, b3, w3, k3, T, before)
        left = [c for c in land if c in lab.lay]
        r3 = [r[2] for r in res3]
        print("   ramp cell %s bulldozed (pass box = cell + 8) -> %s; ramp pieces left: %d" % (dead, r3, len(left)))
        fails += r3 not in (["kept fly"], ["built fly"]) or bool(left)
        badb = saves_ok(lab, before, T)
        fails += bool(badb)
        if badb:
            print("   after the fallback, saves: %s" % badb[:3])
        blk = Lab(before, blocked=[land[0]])
        r4 = [r[2] for r in twin_pass(blk, box, T)[0]]
        print("   building on ramp cell %s before the build -> %s" % (land[0], r4))
        fails += r4 != ["built fly"]
        capped = Lab(lab.lay)
        arm = [c for c, v in capped.lay.items() if v[0] in (11223, 11224) and to_pq(c[0] - O[0] + 0.5, c[1] - O[1] + 0.5,
               Geo(par).o)[1] < -7.0]
        far = min(arm, key=lambda c: abs(to_pq(c[0] - O[0] + 0.5, c[1] - O[1] + 0.5, Geo(par).o)[1] + 8.0))
        capped.lay[far] = (14999, 0)
        r6 = [r[2] for r in twin_pass(capped, box, T)[0]]
        print("   end cap on a plain-band arm cell %s (the arm ends there for the block) -> %s" % (far, r6))
        fails += r6 not in (["built clover"], ["kept clover"])            # task hwcap2: a band row may hold the cap
        short = Lab(aftermath(par, O, cut=("N", 4)))
        r5 = [r[2] for r in twin_pass(short, box, T)[0]]
        print("   north arm only 4 cells past O (no stock cap) -> %s" % r5)
        fails += r5 not in (["none"], ["built fly"])
        # task hwcap2 ("never extend"): the north arm ends n cells past O with its stock end cap (hwcap.stock_ends).
        # A cap in the plain-band rows (or the arm past them) -> the cloverleaf; in the joining rows -> the flyover (or
        # nothing). Never a highway piece written into a cell the drag left empty.
        got = {}
        for n in range(3, 10):
            lay = aftermath(par, O, cut=("N", n))
            band = [c for c, v in lay.items() if v[0] in (11223, 11224)]
            ends = hwcap.stock_ends(lay, band, lambda i, s_, c: (i, s_))
            capc, step = min(ends, key=lambda e: to_pq(e[0][0] - O[0] + 0.5, e[0][1] - O[1] + 0.5, Geo(par).o)[1])
            before = set(lay)
            res7, w7, _ = twin_pass(Lab(lay), box, T)
            r7 = [r[2] for r in res7]
            onhw = {(o_[0] + r_[0], o_[1] + r_[1]) for o_, p_, _k in res7 for r_ in T[p_]["clover"] + T[p_]["fly"]
                    if r_[2] in (1, 2)}
            grown = sorted(c for c, v in w7.items() if v and c not in before and c in onhw)
            got[n] = r7
            print("   north arm ends %d cells past O (stock cap %s at %s) -> %s%s" % (
                n, lay[capc], capc, r7, " WROTE INTO EMPTY ARM CELLS %s" % grown if grown else ""))
            fails += bool(grown) or r7 not in (["built clover"], ["built fly"], ["none"], [])   # []: the stub itself cut
        fails += not any(v == ["built clover"] for v in got.values())       # a long enough arm still gets the clover
        fails += any(got[k] == ["built clover"] and got[k + 1] != ["built clover"] for k in range(3, 9))
    print("FAIL %d" % fails if fails else "all checks pass")
    return fails


def main(argv):
    if len(argv) > 1 and argv[1] == "check":
        return 1 if cmd_check() else 0
    if len(argv) > 2 and argv[1] == "flows":
        cmd_flows(argv[2])
        return 0
    if len(argv) > 2 and argv[1] == "ctab":
        ctab(argv[2])
        return 0
    if len(argv) > 2 and argv[1] == "plan":
        print(plan_png(argv[2]))
        return 0
    if len(argv) > 2 and argv[1] == "cells":
        g = Geo(argv[2])
        ids, nxt = g.ids(ID0 if argv[2] == "c" else Geo("c").ids(ID0)[1])
        for c in sorted(g.written(), key=lambda c: (c[1], c[0])):
            print(c, g.role(c), sorted(g.cells[c]), ids[c])
        gc, gh = Geo("c"), Geo("h")
        ic, n0 = gc.ids(ID0)
        ih, n1 = gh.ids(n0)
        fc, n2 = gc.flyover_ids(ic, n1)
        fl = fc if argv[2] == "c" else gh.flyover_ids(ih, n2)[0]
        print("flyover", sorted((c, v) for c, v in fl.items()))
        print("box", g.box(), "written", len(g.written()), "ids up to", nxt - 1, "lane steps (cells, diagonal steps)", g.lane_steps())
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
