#!/usr/bin/env python3
r"""bvlanes.py - boulevard lanes for the avenue lane rework (task bvlanes, 2026-10-19): 3 lanes each way, right-hand.

Plan: verify/bvlanes/PLAN.md. Every lane of a boulevard scene is drawn once in WORLD coordinates (cells, floats),
cut per cell, and turned into each cell's piece frame (state 0). One piece id must carry one lane set wherever the
rule places it: `check` reports every piece whose placements disagree (those need their own id).

World frame of the canonical scenes: boulevard along x, rows z 0 / 1 / 2 (boulevard.py). Right-hand traffic (NET_LANES
2.4: road 29's lane at z 80 runs +x): row 0's side runs +x, row 2's side -x, the median in row 1. Lane positions across
(lane units, 255 per cell as hwlanes): +x at z 80, 175 (row 0) and 255 + 14 (row 1), -x at 255 + 241 (row 1), 510 + 80,
510 + 175 (row 2): the slots the pieces already use, 95 apart.

  py -3.12 bvlanes.py check                 placements of every scene (boulevard.runs), lane sets per piece, matrices
  py -3.12 bvlanes.py sheet OUT.png         the plan sheet (top-down, seen from above as in the game: +x right, +z up)
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

U = 255.0                                    # lane units per cell
SIDES = ["x-", "z-", "x+", "z+"]
PX = [80 / U, 175 / U, 1 + 14 / U]           # +x lanes, outer -> inner (z)
MX = [2 + 175 / U, 2 + 80 / U, 1 + 241 / U]  # -x lanes, outer -> inner (z)
STEP = 1.0 / 64.0                            # polyline sampling, cells


# ------------------------------------------------------------------------------------------------ geometry
def seg(a, b):
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / STEP))
    return [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]


def join(*parts):
    out = []
    for p in parts:
        if out and p and math.hypot(out[-1][0] - p[0][0], out[-1][1] - p[0][1]) < 1e-9:
            p = p[1:]
        out += p
    return out


def arc(c, r, a0, a1):
    n = max(2, int(abs(a1 - a0) * r / STEP))
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * k / n), c[1] + r * math.sin(a0 + (a1 - a0) * k / n))
            for k in range(n + 1)]


def turn(pin, hin, pout, hout):
    """lane from pin (heading hin) to pout (heading hout, perpendicular): straight, quarter arc tangent to both lines,
    straight. The arc radius is the shorter leg, so concentric lanes stay concentric."""
    # corner I: the in line through pin along hin meets the out line through pout along hout
    if hin[0] != 0:
        I = (pout[0], pin[1])
    else:
        I = (pin[0], pout[1])
    la = abs(I[0] - pin[0]) + abs(I[1] - pin[1])
    lb = abs(pout[0] - I[0]) + abs(pout[1] - I[1])
    r = min(la, lb)
    A = (I[0] - r * hin[0], I[1] - r * hin[1])
    B = (I[0] + r * hout[0], I[1] + r * hout[1])
    C = (A[0] + r * hout[0], A[1] + r * hout[1])
    a0 = math.atan2(A[1] - C[1], A[0] - C[0])
    a1 = math.atan2(B[1] - C[1], B[0] - C[0])
    cross = hin[0] * hout[1] - hin[1] * hout[0]           # +1: turning +x -> +z (counter-clockwise on screen)
    if cross > 0 and a1 < a0:
        a1 += 2 * math.pi
    if cross < 0 and a1 > a0:
        a1 -= 2 * math.pi
    return join(seg(pin, A), arc(C, r, a0, a1), seg(B, pout))


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def slide(x0, x1, z_of, sign):
    """a lane along x from x0 to x1 whose z follows z_of(t), t = 0 at x0 .. 1 at x1 (sign: travel +x / -x)"""
    n = max(2, int(abs(x1 - x0) / STEP))
    pts = [(x0 + (x1 - x0) * k / n, z_of(k / n)) for k in range(n + 1)]
    return pts if sign > 0 else pts[::-1]


def rot180(pts, cx, cz):
    return [(2 * cx - x, 2 * cz - z) for (x, z) in pts]


# ------------------------------------------------------------------------------------------------ lanes of a run
class Lane:
    def __init__(self, pts, kind):
        self.pts, self.kind = pts, kind          # kind: "+" (+x side), "-" (-x side), "a" (crossing arm)


def straights(x0, x1):
    out = [Lane(seg((x0, z), (x1, z)), "+") for z in PX]
    out += [Lane(seg((x1, z), (x0, z)), "-") for z in MX]
    return out


CAP_ALONG = (0.75, 0.6, 0.45)                # apex of the outer / middle / inner U-turn, cells past the cap's edge


def cap_end(xe):
    """the cap column xe..xe+1 at the +x end: 3-lane U-turn round the median nose (outer to outer, middle to middle,
    inner to inner), plus two routing branches in the middle cell (the router cannot use the inner U-turn: it would
    re-enter the middle-row cell it came from, LANE_DENSITY.md 1)"""
    zc = (PX[2] + MX[2]) / 2.0
    out = []
    for k in range(3):
        d = (MX[k] - PX[k]) / 2.0
        a = CAP_ALONG[k]
        n = 64
        pts = [(xe + a * math.sin(math.pi * i / n), zc - d * math.cos(math.pi * i / n)) for i in range(n + 1)]
        out.append(Lane([(xe - 1e-9, PX[k])] + pts, "+"))
    # branches: inner lane in -> middle lane out (via row 2); middle lane in (from row 0) -> inner lane out. Half
    # ellipses too (no left bend under radius 100: a car on a tight left turn deadlocks SC3, AVENUE_LANES.md 6)
    for zin, zout in ((PX[2], MX[1]), (PX[1], MX[2])):
        c, d, a = (zin + zout) / 2.0, (zout - zin) / 2.0, 0.53
        pts = [(xe + a * math.sin(math.pi * i / 64), c - d * math.cos(math.pi * i / 64)) for i in range(65)]
        out.append(Lane([(xe - 1e-9, zin)] + pts, "+b"))
    return out


def narrow_end(xe, keep):
    """narrowing to an avenue over xe..xe+3 (+x end, canonical placement state 0). keep (0, 1): rows 0, 1 go on as the
    avenue (row 0 the +x half, row 1 the -x half, avcore's one-way halves at their 80 / 175 slots): the +x side keeps
    its two outer lanes and merges its middle-row lane into them; the -x side's two lanes slide one row out with the
    carriageway (linear, as the paint: AvenueNarrow.params) and the boulevard's inner lane opens from the inner one.
    keep (1, 2): the same with the sides swapped (the +x carriageway slides one row in)."""
    g = 95 / U
    ext = lambda t: g * (1 - smooth(t / 0.8))                       # noqa: E731  the third lane's offset
    if keep == (0, 1):
        return [Lane(seg((xe, PX[0]), (xe + 3, PX[0])), "+"), Lane(seg((xe, PX[1]), (xe + 3, PX[1])), "+"),
                Lane(slide(xe, xe + 3, lambda t: PX[1] + ext(t) * (PX[2] - PX[1]) / g, +1), "+"),
                Lane(slide(xe, xe + 3, lambda t: MX[0] - t, -1), "-"),
                Lane(slide(xe, xe + 3, lambda t: MX[1] - t, -1), "-"),
                Lane(slide(xe, xe + 3, lambda t: MX[1] - t - ext(t), -1), "-")]
    return [Lane(slide(xe, xe + 3, lambda t: PX[0] + t, +1), "+"),
            Lane(slide(xe, xe + 3, lambda t: PX[1] + t, +1), "+"),
            Lane(slide(xe, xe + 3, lambda t: PX[1] + t + ext(t), +1), "+"),
            Lane(seg((xe + 3, MX[0]), (xe, MX[0])), "-"), Lane(seg((xe + 3, MX[1]), (xe, MX[1])), "-"),
            Lane(slide(xe, xe + 3, lambda t: MX[1] - ext(t), -1), "-")]


def taper_end(xe, keep):
    """taper to the single road on row `keep` over xe..xe+3: 3 -> 1 lanes each way. Per side the lanes keep their
    order: the outer lane closes onto the middle one by half way, the middle onto the inner one by the end, while the
    inner lane moves to the road's lane (the +x side merges, the -x side splits: the same lanes driven backwards)."""
    g = 95 / U
    out = []
    for lanes, road_z, outward, kind, sign in ((PX, keep + 80 / U, -1, "+", +1), (MX, keep + 175 / U, +1, "-", -1)):
        inner = lanes[2]
        base = lambda t, i=inner, r=road_z: i + (r - i) * smooth(t)              # noqa: E731
        g1 = lambda t: g * (1 - smooth(t))                                       # noqa: E731
        g0 = lambda t: g1(t) + g * (1 - smooth(2 * t))                           # noqa: E731
        for off in (lambda t: 0.0, g1, g0):
            out.append(Lane(slide(xe, xe + 3, lambda t, b=base, o=off, w=outward: b(t) + w * o(t), sign), kind))
    return out


def right_of(h):
    return (h[1], -h[0])                         # left(h) = (-hz, hx) (NET_LANES 8: +x -> +z counter-clockwise)


def left_of(h):
    return (-h[1], h[0])


def box_lanes(x0, x1, z0, z1, arms):
    """turning lanes of a junction box [x0, x1] x [z0, z1]. arms: {side: {"in": [(x, z) outer -> inner],
    "out": [...], "h": heading into the box}} for sides 0 x- (W), 1 z- (N), 2 x+ (E), 3 z+ (S). Straight: every in
    lane to the opposite arm's out lane of the same rank. Right: the outer lane(s), left: the inner lane(s), 2 of each
    on a 3-lane arm, 1 otherwise; targets outer-first (right) / inner-first (left), merging when the target has fewer."""
    out = []
    H = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}     # heading of traffic entering by side s
    side_of_h = {v: k for k, v in H.items()}
    for s, a in arms.items():
        h = H[s]
        n = len(a["in"])
        opp = (s + 2) % 4
        if opp in arms:
            for k, p in enumerate(a["in"]):
                q = arms[opp]["out"][min(k, len(arms[opp]["out"]) - 1)]
                out.append(Lane(seg(p, q) if (abs(p[0] - q[0]) < 1e-9 or abs(p[1] - q[1]) < 1e-9) else
                                join(seg(p, ((p[0] + q[0]) / 2, p[1]) if h[0] else (p[0], (p[1] + q[1]) / 2)),
                                     seg(((p[0] + q[0]) / 2, p[1]) if h[0] else (p[0], (p[1] + q[1]) / 2), q)),
                                "a" + str(s)))
        for which, hdir in (("r", right_of(h)), ("l", left_of(h))):
            ts = side_of_h[(-hdir[0], -hdir[1])]           # the side traffic leaves by (heading hdir)
            if ts not in arms:
                continue
            tgt = arms[ts]["out"]
            m = 2 if n >= 3 else 1
            if (ts + 2) % 4 not in arms:                   # no straight feeds that side (a T's stem / the run's end):
                m = min(n, len(tgt))                       # turn into as many of its lanes as fit
            srcs = a["in"][:m] if which == "r" else a["in"][::-1][:m]
            outs = tgt if which == "r" else tgt[::-1]
            for k, p in enumerate(srcs):
                q = outs[min(k, len(outs) - 1)]
                # a merge (more turning lanes than target lanes) runs onto the real lane too: an arc tangent to it,
                # no kink (no tight left bend, AVENUE_LANES.md 6)
                lane = turn(p, h, q, hdir)
                out.append(Lane(lane, "a" + str(s) + which))
    return out


def _merge_tail(lane, q, hdir):
    """bend the straight tail of a lane onto the real target q at the box edge"""
    # last arc point: where the polyline stops being along hdir
    k = len(lane) - 1
    while k > 0:
        dx, dz = lane[k][0] - lane[k - 1][0], lane[k][1] - lane[k - 1][1]
        L = math.hypot(dx, dz)
        if L < 1e-12 or abs(dx * hdir[0] + dz * hdir[1]) / L < 0.999:
            break
        k -= 1
    return lane[:k + 1] + seg(lane[k], q)[1:]


# ------------------------------------------------------------------------------------------------ arms
def arm_bv_x(side, x):
    """a boulevard arm along x entering a box edge at x (side 0 W / 2 E)"""
    if side == 0:
        return {"in": [(x, z) for z in PX], "out": [(x, z) for z in MX]}
    return {"in": [(x, z) for z in MX], "out": [(x, z) for z in PX]}


def arm_z(side, z, xa, width):
    """an arm along z (road 1, avenue 2, boulevard 3 columns from xa) entering at z (side 1 N / 3 S). Right-hand: the
    x+ part runs +z, the x- part -z; outer lanes farthest from the median."""
    if width == 1:
        pz, mz = [xa + 175 / U], [xa + 80 / U]                     # road 29 along z: +z at x 175, -z at x 80
    elif width == 2:
        pz, mz = [xa + 1 + 175 / U, xa + 1 + 80 / U], [xa + 80 / U, xa + 175 / U]
    else:
        pz = [xa + 3 - v for v in PX]
        mz = [xa + 3 - v for v in MX]
    if side == 1:
        return {"in": [(x, z) for x in pz], "out": [(x, z) for x in mz]}
    return {"in": [(x, z) for x in mz], "out": [(x, z) for x in pz]}


def arm_road_lanes(side, z_edge, xa, width, length, crossing):
    """the arm's own lanes outside the box (for drawing and for the arm cells)"""
    a = arm_z(side, z_edge, xa, width)
    far = z_edge - length if side == 1 else z_edge + length
    out = []
    for (x, z) in a["in"]:
        out.append(Lane(seg((x, far), (x, z_edge)), "a%d" % side))
    for (x, z) in a["out"]:
        out.append(Lane(seg((x, z_edge), (x, far)), "a%d" % ((side + 2) % 4)))
    return out


# ------------------------------------------------------------------------------------------------ scenes
def cap_lo(xa):
    """the cap at the -x end (column xa): the +x end turned half a circle"""
    return [Lane(rot180(l.pts, xa + 0.5, 1.5), l.kind.replace("+", "~").replace("-", "+").replace("~", "-"))
            for l in cap_end(xa)]


def scene_cap():
    road = {(x, z) for x in range(0, 8) for z in range(3)}
    lanes = straights(1, 7) + cap_end(7) + cap_lo(0)
    return {"name": "straight + caps", "road": road, "lanes": lanes, "view": (-0.5, -0.6, 8.5, 3.6)}


def junction_scene(kind):
    """single road crossing (X), T from z- (TN) or z+ (TS) at column 5 of a 12-column boulevard"""
    road = {(x, z) for x in range(0, 12) for z in range(3)}
    j = 5
    arms = {0: arm_bv_x(0, j), 2: arm_bv_x(2, j + 1)}
    lanes = straights(1, j) + straights(j + 1, 11) + cap_lo(0) + cap_end(11)
    if kind in ("X", "TN"):
        road |= {(j, z) for z in range(-3, 0)}
        arms[1] = arm_z(1, 0, j, 1)
        lanes += arm_road_lanes(1, 0, j, 1, 3, kind == "X")
    if kind in ("X", "TS"):
        road |= {(j, z) for z in range(3, 6)}
        arms[3] = arm_z(3, 3, j, 1)
        lanes += arm_road_lanes(3, 3, j, 1, 3, kind == "X")
    lanes += box_lanes(j, j + 1, 0, 3, arms)
    return {"name": {"X": "road crossing", "TN": "road T (from z-)", "TS": "road T (from z+)"}[kind], "road": road,
            "lanes": lanes, "view": (2.5, -2.6, 9.5, 5.6), "caps": True}


def scene_narrow():
    road = {(x, z) for x in range(0, 9) for z in range(3)} | {(x, z) for x in range(9, 13) for z in (0, 1)}
    lanes = straights(1, 6) + cap_lo(0) + narrow_end(6, (0, 1))
    lanes += [Lane(seg((9, PX[0]), (12, PX[0])), "+"), Lane(seg((9, PX[1]), (12, PX[1])), "+"),
              Lane(seg((12, 1 + 175 / U), (9, 1 + 175 / U)), "-"), Lane(seg((12, 1 + 80 / U), (9, 1 + 80 / U)), "-")]
    return {"name": "narrowing to an avenue on rows 0, 1 (3 -> 2)", "road": road, "lanes": lanes,
            "view": (3.5, -0.6, 11.5, 3.6), "medians": [narrow_median(6, (0, 1)), rect(9, 13, *AV_MED)]}


def scene_narrow12():
    road = {(x, z) for x in range(0, 9) for z in range(3)} | {(x, z) for x in range(9, 13) for z in (1, 2)}
    lanes = straights(1, 6) + cap_lo(0) + narrow_end(6, (1, 2))
    lanes += [Lane(seg((9, 1 + 80 / U), (12, 1 + 80 / U)), "+"), Lane(seg((9, 1 + 175 / U), (12, 1 + 175 / U)), "+"),
              Lane(seg((12, MX[0]), (9, MX[0])), "-"), Lane(seg((12, MX[1]), (9, MX[1])), "-")]
    return {"name": "narrowing to an avenue on rows 1, 2 (3 -> 2)", "road": road, "lanes": lanes,
            "view": (3.5, -0.6, 11.5, 3.6), "medians": [narrow_median(6, (1, 2)), rect(9, 13, AV_MED[0] + 1, AV_MED[1] + 1)]}


def scene_taper(keep):
    road = {(x, z) for x in range(0, 9) for z in range(3)} | {(x, keep) for x in range(9, 13)}
    lanes = straights(1, 6) + cap_lo(0) + taper_end(6, keep)
    lanes += [Lane(seg((9, keep + 80 / U), (12, keep + 80 / U)), "+"),
              Lane(seg((12, keep + 175 / U), (9, keep + 175 / U)), "-")]
    return {"name": "taper to row %d (3 -> 1)" % keep, "road": road, "lanes": lanes, "view": (3.5, -0.6, 11.5, 3.6),
            "caps": True}


def box_scene(kind):
    """bvx kinds (bvx.shapes): BxA avenue crossing, AvT avenue ends on it, BvT it ends on an avenue, BxB boulevard
    crossing, BbT a boulevard ends on it. Box columns 0..w-1."""
    from netmod import bvx as BX
    road = BX.shapes()[kind]
    w = 3 if kind in ("BxB", "BbT") else 2
    arms = {0: arm_bv_x(0, 0)}
    lanes = straights(-9, 0)
    if kind != "BvT":
        arms[2] = arm_bv_x(2, w)
        lanes += straights(w, 11)
    arms[1] = arm_z(1, 0, 0, w)
    lanes += arm_road_lanes(1, 0, 0, w, 8 if w == 2 else 9, True)
    if kind in ("BxA", "BvT", "BxB"):
        arms[3] = arm_z(3, 3, 0, w)
        lanes += arm_road_lanes(3, 3, 0, w, 8, True)
    lanes += box_lanes(0, w, 0, 3, arms)
    med = []
    if w == 2:                                          # the avenue arms' medians, ending in a nose at the box
        med.append(rect(AV_MED[0], AV_MED[1], -9, -0.12))
        if 3 in arms:
            med.append(rect(AV_MED[0], AV_MED[1], 3.12, 12))
    names = {"BxA": "boulevard x avenue", "AvT": "avenue ends on the boulevard", "BvT": "boulevard ends on an avenue",
             "BxB": "boulevard x boulevard", "BbT": "boulevard ends on a boulevard"}
    return {"name": names[kind], "road": road, "lanes": lanes, "view": (-3.5, -3.6, w + 3.5, 6.6), "medians": med,
            "box": True}


def scenes():
    out = [scene_cap(), junction_scene("X"), junction_scene("TN"), junction_scene("TS"), scene_narrow(),
           scene_narrow12()]
    out += [scene_taper(k) for k in (1, 0, 2)]
    out += [box_scene(k) for k in ("BxA", "AvT", "BvT", "BxB", "BbT")]
    return out


# ------------------------------------------------------------------------------------------------ cutting
def clip_cell(pts, X, Z):
    """runs of a polyline inside cell [X, X+1] x [Z, Z+1] -> [[(x, z), ...]] in lane units (0..255), end points
    exactly on the border where the polyline crosses it"""
    def inside(p):
        return X - 1e-9 <= p[0] <= X + 1 + 1e-9 and Z - 1e-9 <= p[1] <= Z + 1 + 1e-9

    def cross(a, b):                                     # a inside, b outside: the border point
        lo, hi = 0.0, 1.0
        for _ in range(40):
            m = (lo + hi) / 2
            p = (a[0] + (b[0] - a[0]) * m, a[1] + (b[1] - a[1]) * m)
            if inside(p):
                lo = m
            else:
                hi = m
        return (a[0] + (b[0] - a[0]) * lo, a[1] + (b[1] - a[1]) * lo)

    runs, cur = [], None
    for i, p in enumerate(pts):
        if inside(p):
            if cur is None:
                cur = [cross(p, pts[i - 1])] if i > 0 and not inside(pts[i - 1]) else []
            cur.append(p)
        elif cur is not None:
            cur.append(cross(pts[i - 1], p))
            runs.append(cur)
            cur = None
    if cur is not None:
        runs.append(cur)
    out = []
    for r in runs:
        lu = [(min(U, max(0.0, (x - X) * U)), min(U, max(0.0, (z - Z) * U))) for (x, z) in r]
        for k in (0, -1):                                # a border point near a corner: slide it along its border to
            x, z = lu[k]                                 # CORNER units off the corner (the neighbour cell computes
            ex, ez = min(x, U - x), min(z, U - z)        # the same point, so both sides keep one node)
            if ex <= ez and ez < CORNER:
                lu[k] = (x, CORNER if z < U / 2 else U - CORNER)
            elif ez < ex and ex < CORNER:
                lu[k] = (CORNER if x < U / 2 else U - CORNER, z)
        L = sum(math.hypot(lu[i + 1][0] - lu[i][0], lu[i + 1][1] - lu[i][1]) for i in range(len(lu) - 1))
        if L < 0.5:
            continue                                     # a point touch
        out.append(lu)
    return out


CORNER = 3.0


def side_of_pt(p):
    x, z = p
    s = []
    if x <= 0.5:
        s.append(0)
    if z <= 0.5:
        s.append(1)
    if x >= U - 0.5:
        s.append(2)
    if z >= U - 0.5:
        s.append(3)
    return s


def to_local(p, state):
    """world lane point inside a cell -> the piece's state-0 frame (inverse of lanekit's (x, z) -> (255 - z, x))"""
    x, z = p
    for _ in range(state % 4):
        x, z = z, U - x
    return (x, z)


def resample(lu, n=9):
    L = [0.0]
    for i in range(len(lu) - 1):
        L.append(L[-1] + math.hypot(lu[i + 1][0] - lu[i][0], lu[i + 1][1] - lu[i][1]))
    out = []
    for k in range(n):
        t = L[-1] * k / (n - 1)
        i = max(0, min(len(lu) - 2, next((j for j in range(len(L) - 1) if L[j + 1] >= t), len(lu) - 2)))
        f = (t - L[i]) / max(1e-12, L[i + 1] - L[i])
        out.append((lu[i][0] + (lu[i + 1][0] - lu[i][0]) * f, lu[i][1] + (lu[i + 1][1] - lu[i][1]) * f))
    return out


def cut_scene(sc):
    """-> {cell: [cut, ...]} for the cells the rule writes (boulevard.runs over the scene's road), cut = dict with
    world lane-unit points, sides, kind; and the rule's want {cell: (piece, state)}"""
    from netmod import bvx as BX
    want, ok, bad, clash = BX.junction_wants(sc["road"])
    x0, z0, x1, z1 = sc["view"]
    want = {c: v for c, v in want.items() if x0 <= c[0] + 0.5 <= x1 and z0 <= c[1] + 0.5 <= z1}
    cuts = defaultdict(list)
    for c in want:
        for ln in sc["lanes"]:
            for lu in clip_cell(ln.pts, *c):
                a, b = side_of_pt(lu[0]), side_of_pt(lu[-1])
                cuts[c].append({"pts": lu, "a": a, "b": b, "kind": ln.kind})
    return want, cuts, bad, clash


def sig_of(cuts, state):
    """a piece-frame signature of a cell's lanes: sorted (from, to) slot pairs + the mid point, rounded"""
    out = []
    for ct in cuts:
        pts = [to_local(p, state) for p in resample(ct["pts"], 5)]
        out.append(tuple((round(x / 8.0), round(z / 8.0)) for (x, z) in pts))
    return tuple(sorted(set(out)))


def turns_of(cuts, state):
    t = set()
    for ct in cuts:
        a = [(s - state) % 4 for s in ct["a"]]
        b = [(s - state) % 4 for s in ct["b"]]
        if len(a) == 1 and len(b) == 1:
            t.add((a[0], b[0]))
    return t


def cmd_check(a):
    per_piece = defaultdict(dict)                        # piece -> {sig: [(scene, cell, state)]}
    turns = defaultdict(set)
    bad_ends = []
    shapes = set()
    for sc in scenes():
        want, cuts, bad, clash = cut_scene(sc)
        if clash:
            print("CLASH", sc["name"], clash[:3])
        for c, (pid, st) in want.items():
            cs = cuts.get(c, [])
            for ct in cs:
                if len(ct["a"]) != 1 or len(ct["b"]) != 1:
                    bad_ends.append((sc["name"], c, pid, [round(v) for v in ct["pts"][0]],
                                     [round(v) for v in ct["pts"][-1]]))
                loc = tuple((round(x), round(z)) for (x, z) in (to_local(p, st) for p in resample(ct["pts"], 9)))
                shapes.add(min(_rots(loc)))
            s = sig_of(cs, st)
            per_piece[pid].setdefault(s, []).append((sc["name"], c, st))
            turns[(pid, s)] |= turns_of(cs, st)
    nsplit = 0
    for pid in sorted(per_piece):
        sigs = per_piece[pid]
        tag = "" if len(sigs) == 1 else "   <-- %d lane sets: needs %d more id(s)" % (len(sigs), len(sigs) - 1)
        nsplit += len(sigs) - 1
        print("%d: %d placement(s)%s" % (pid, sum(len(v) for v in sigs.values()), tag))
        for s, where in sigs.items():
            t = sorted(turns[(pid, s)])
            print("    lanes %2d, turns %s   e.g. %s cell %s state %d" % (
                len(s), " ".join("%s=>%s" % (SIDES[x], SIDES[y]) for x, y in t), where[0][0], where[0][1], where[0][2]))
    print("pieces %d, extra ids needed %d, distinct lane cuts (up to rotation) %d, lanes ending inside a cell %d" % (
        len(per_piece), nsplit, len(shapes), len(bad_ends)))
    for b in bad_ends[:20]:
        print("  inside end:", b)


def _rots(pts):
    out = []
    p = list(pts)
    for _ in range(4):
        out.append(tuple(p))
        p = [(round(U - z), x) for (x, z) in p]
    return out


# ------------------------------------------------------------------------------------------------ the sheet
COL = {"+": (210, 40, 40), "-": (30, 90, 220), "a": (130, 60, 170)}


def draw_scene(sc, px=64, label=True, fonts=None):
    from PIL import Image, ImageDraw
    x0, z0, x1, z1 = sc["view"]
    W, H = int((x1 - x0) * px), int((z1 - z0) * px)
    im = Image.new("RGB", (W, H), (236, 236, 230))
    d = ImageDraw.Draw(im)

    def P(x, z):                                         # seen from above as in the game: +x right, +z UP
        return ((x - x0) * px, (z1 - z) * px)

    want, cuts, bad, clash = cut_scene(sc)
    for (cx, cz) in sc["road"]:
        a, b = P(cx, cz + 1), P(cx + 1, cz)
        d.rectangle([a, b], fill=(150, 150, 150) if (cx, cz) in want else (178, 178, 178))
    for (cx, cz) in want:                                # the median (approximate: the middle row's grass band)
        pass
    _medians(sc, d, P, want)
    for gx in range(int(math.floor(x0)), int(math.ceil(x1)) + 1):
        d.line([P(gx, z0), P(gx, z1)], fill=(205, 205, 200), width=1)
    for gz in range(int(math.floor(z0)), int(math.ceil(z1)) + 1):
        d.line([P(x0, gz), P(x1, gz)], fill=(205, 205, 200), width=1)
    for ln in sc["lanes"]:
        col = COL.get(ln.kind[0], (130, 60, 170))
        if ln.kind.startswith("a") and len(ln.kind) > 1:
            s = int(ln.kind[1])
            col = {0: (210, 40, 40), 2: (30, 90, 220), 1: (150, 70, 190), 3: (230, 140, 20)}[s]
        w = 1 if ln.kind.endswith("b") else 2
        pts = [P(x, z) for (x, z) in ln.pts if x0 - 1 <= x <= x1 + 1 and z0 - 1 <= z <= z1 + 1]
        if len(pts) < 2:
            continue
        if ln.kind.endswith("b"):
            for i in range(0, len(pts) - 1, 2):
                d.line([pts[i], pts[i + 1]], fill=col, width=w)
        else:
            d.line(pts, fill=col, width=w)
        _arrow(d, pts, col)
    if label and fonts:
        for (cx, cz), (pid, st) in want.items():
            X, Y = P(cx + 0.04, cz + 0.97)
            d.text((X, Y), "%d.%d" % (pid, st), fill=(0, 0, 0), font=fonts["s"])
    return im


def _arrow(d, pts, col):
    # arrowheads at 45% and at the end of the visible part
    for f in (0.5, 1.0):
        i = max(1, min(len(pts) - 1, int((len(pts) - 1) * f)))
        (xa, ya), (xb, yb) = pts[i - 1], pts[i]
        if math.hypot(xb - xa, yb - ya) < 1e-6:
            continue
        a = math.atan2(yb - ya, xb - xa)
        for s in (2.6, -2.6):
            d.line([(xb, yb), (xb + 7 * math.cos(a + s), yb + 7 * math.sin(a + s))], fill=col, width=2)


def _to_world(c, st, lx, lz):
    x, z = lx, lz
    for _ in range(st % 4):
        x, z = U - z, x
    return (c[0] + x / U, c[1] + z / U)


MED = (72.0, 186.0)                      # the boulevard median across its middle cell, lane units (T 328..442)
AV_MED = (0.87, 1.13)                    # an avenue's median about its two halves' border, cells (approximate)
NOSE_L = 0.12 * U


def _medians(sc, d, P, want):
    """grass medians, for orientation (approximate): the middle pieces' band from the piece frame (any state), the
    narrowing's from AvenueNarrow.params, and the scene's own extra polygons (avenue arms)"""
    green = (80, 150, 80)
    for c, (pid, st) in want.items():
        if pid in (20701, 20702, 20703):
            xa = NOSE_L if pid == 20703 else 0.0
            xb = U - NOSE_L if pid in (20702, 20703) else U
            q = [_to_world(c, st, *v) for v in ((xa, MED[0]), (xb, MED[0]), (xb, MED[1]), (xa, MED[1]))]
            d.polygon([P(*v) for v in q], fill=green)
    for poly in sc.get("medians", []):
        d.polygon([P(*v) for v in poly], fill=green)


def narrow_median(xe, keep):
    from netmod import boulevard_paint as BP
    sc = BP.AvenueNarrow(keep)
    lo, hi = [], []
    for k in range(31):
        t = k / 30.0
        t0n, wn, t0s, ws, mid = sc.params(t)
        lo.append((xe + 3 * t, (t0n + wn + 224.0) / 256.0))
        hi.append((xe + 3 * t, (t0s + 34.0 - ws) / 256.0))
    return lo + hi[::-1]


def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def draw_dbv(px=40, fonts=None):
    """the diagonal boulevard (schematic, not cut): the straight cross-section turned 45 degrees (p = x - z across,
    q = x + z along, diagbv.py), 3 lanes each way. Strip A (p 0..1) runs -q, C (p 2..3) +q (the median on the
    driver's left, as everywhere). Top end: narrowing into the diagonal avenue on strips A + B (narrow-C), where
    avdiag's one-way halves start: A -q, B +q, at the stock 35 slots."""
    from PIL import Image, ImageDraw
    rows_band, rows_nar, rows_av = 5, 3, 3
    nz = rows_band + rows_nar + rows_av
    x0, z0, x1, z1 = -0.5, -0.5, nz + 4.5, nz + 0.5
    W, H = int((x1 - x0) * px), int((z1 - z0) * px)
    im = Image.new("RGB", (W, H), (236, 236, 230))
    d = ImageDraw.Draw(im)

    def P(x, z):
        return ((x - x0) * px, (z1 - z) * px)
    cells = {}
    for z in range(nz):
        n = 4 if z < rows_band + rows_nar else 3
        for k in range(n):
            cells[(z + k, z)] = "band" if z < rows_band else ("nar" if z < rows_band + rows_nar else "dav")
    for (cx, cz), kind in cells.items():
        d.rectangle([P(cx, cz + 1), P(cx + 1, cz)], fill=(178, 178, 178) if kind == "dav" else (150, 150, 150))
    for gx in range(int(x0), int(x1) + 1):
        d.line([P(gx, z0), P(gx, z1)], fill=(205, 205, 200), width=1)
    for gz in range(int(z0), int(z1) + 1):
        d.line([P(x0, gz), P(x1, gz)], fill=(205, 205, 200), width=1)
    q_a = 2.0 * rows_band + 1.0                     # narrowing from q_a over 3 * sqrt(2) along (diagbv L)
    L = 3 * math.sqrt(2.0)
    q_lo, q_hi = 3.0, 2.0 * nz - 1.0

    def W_(q, p):                                   # (q, p) -> world (x, z): band strips start at p 0 = cell x = z
        return ((q + p) / 2.0, (q - p) / 2.0)

    def tt(q):
        return min(1.0, max(0.0, (q - q_a) / L))
    g = 95 / U
    qs = [q_lo + (q_hi - q_lo) * i / 400.0 for i in range(401)]
    med_lo = [W_(q, 1.28 - 0.41 * tt(q)) for q in qs]
    med_hi = [W_(q, 1.72 - 0.59 * tt(q)) for q in qs]
    d.polygon([P(*v) for v in med_lo + med_hi[::-1]], fill=(80, 150, 80))
    ext = lambda q: g * (1 - smooth(tt(q) / 0.8))           # noqa: E731
    fA = [lambda q: PX[0], lambda q: PX[1], lambda q: PX[1] + ext(q) * (PX[2] - PX[1]) / g]
    fC = [lambda q: MX[0] - tt(q), lambda q: MX[1] - tt(q), lambda q: MX[1] - tt(q) - ext(q)]
    lanes = [([W_(q, f(q)) for q in qs][::-1], (210, 40, 40)) for f in fA]       # A runs -q
    lanes += [([W_(q, f(q)) for q in qs], (30, 90, 220)) for f in fC]           # C runs +q
    for pts, col in lanes:
        pp = [P(*v) for v in pts]
        d.line(pp, fill=col, width=2)
        for f in (0.2, 0.45, 0.7, 0.95):
            i = int((len(pp) - 1) * f)
            (xa, ya), (xb, yb) = pp[i - 1], pp[i]
            ang = math.atan2(yb - ya, xb - xa)
            for sg in (2.6, -2.6):
                d.line([(xb, yb), (xb + 7 * math.cos(ang + sg), yb + 7 * math.sin(ang + sg))], fill=col, width=2)
    if fonts:
        d.text(P(4.6, 2.0), "band 20950 / 20951 (4 cells a row)", fill=(0, 0, 0), font=fonts["m"])
        d.text(P(rows_band + 4.6, rows_band + 1.4), "narrowing 20972..20982", fill=(0, 0, 0), font=fonts["m"])
        d.text(P(rows_band + rows_nar + 3.6, rows_band + rows_nar + 1.0), "diagonal avenue (avdiag)", fill=(0, 0, 0),
               font=fonts["m"])
    return im


def _sheet(out, title, sub, panels, notes, fonts, cols):
    from PIL import Image, ImageDraw
    rows = [panels[i:i + cols] for i in range(0, len(panels), cols)]
    pad, head = 16, 70
    W = max(sum(im.width for _, im in r) + pad * (len(r) + 1) for r in rows)
    W = max(W, 1500)
    H = head + sum(max(im.height for _, im in r) + 34 for r in rows) + pad * 2 + 22 * len(notes) + 20
    sheet = Image.new("RGB", (W, H), (248, 248, 248))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 10), title, fill=(0, 0, 0), font=fonts["t"])
    d.text((pad, 40), sub, fill=(40, 40, 40), font=fonts["m"])
    y = head
    for r in rows:
        x = pad
        for name, im in r:
            d.text((x, y + 4), name, fill=(0, 0, 0), font=fonts["b"])
            sheet.paste(im, (x, y + 26))
            x += im.width + pad
        y += max(im.height for _, im in r) + 34
    for i, line in enumerate(notes):
        d.text((pad, y + 6 + 21 * i), line, fill=(20, 20, 20), font=fonts["m"])
    sheet = sheet.crop((0, 0, W, y + 20 + 21 * len(notes)))
    sheet.save(out)
    print(out, sheet.size)


def cmd_sheet(a):
    from PIL import ImageFont
    try:
        fonts = {"s": ImageFont.truetype("arial.ttf", 10), "m": ImageFont.truetype("arial.ttf", 14),
                 "b": ImageFont.truetype("arialbd.ttf", 16), "t": ImageFont.truetype("arialbd.ttf", 22)}
    except OSError:
        f = ImageFont.load_default()
        fonts = {"s": f, "m": f, "b": f, "t": f}
    sub = ("Seen from above as in the game (+x right, +z up). Red = one side's direction, blue = the other, purple / "
           "orange = the crossing road's two directions, thin dashes = routing branches. Grey = cells the mod writes "
           "(piece.state), light grey = neighbours.")
    sc = scenes()
    bv = [(s["name"], draw_scene(s, px=a.px, fonts=fonts)) for s in sc if not s.get("box")]
    bv.append(("diagonal boulevard into a diagonal avenue", draw_dbv(px=int(a.px * 0.62), fonts=fonts)))
    _sheet(a.out, "Boulevard lanes (bvlanes plan 1/2): 3 lanes each way, right-hand", sub, bv, NOTES, fonts, a.cols)
    bx = [(s["name"], draw_scene(s, px=a.px, fonts=fonts)) for s in sc if s.get("box")]
    root, ext_ = os.path.splitext(a.out)
    _sheet(root + "_boxes" + ext_, "Boulevard junction boxes (bvlanes plan 2/2): median openings, every turn", sub, bx,
           NOTES_BOX, fonts, a.cols)


NOTES = [
    "- Each side runs one way on 3 lanes: the outer cell's 2 lanes + the middle cell's lane beside it; the grass median stays in the middle cell.",
    "  The lane lines are already painted that way: only the car lanes and the turn matrices change, no art.",
    "- End (cap): outer to outer, middle to middle, inner to inner. Trips cannot use the inner U-turn (it would re-enter the cell they came from),",
    "  so the middle cap cell also lets the inner lane out by the far row and the middle lane in from the near row (thin dashes).",
    "- Single road crossing or T: straight on every lane, right from the outer 2 lanes, left from the inner 2 through the median opening;",
    "  the road turns right into the near side's outer lanes and left into the far side's inner lanes.",
    "- Into an avenue (3 -> 2): the side going in merges its middle-cell lane; the side coming out opens a third lane as it slides one row out.",
    "- Into a single road (3 -> 1): two merges on one side, two splits on the other. No lane changes on a plain stretch (as stock).",
    "- Diagonal boulevard: the same rule turned 45 degrees; its narrowing meets the diagonal avenue's one-way halves (avdiag) at the stock slots.",
    "- A game without the mod still loads stock pieces (every piece saves as its base, as today).",
]

NOTES_BOX = [
    "- Every box: straight on every lane, right turns from the outer lane(s), left turns from the inner lane(s) through the median opening",
    "  (2 of each from a 3-lane boulevard side, 1 from a 2-lane avenue side). No U-turns inside a box.",
    "- Avenue arms (one-way halves, 2 lanes each way) and boulevard arms (3 each way) meet the box at their own lane slots.",
    "- Today the 6 box pieces 20900..20905 are shared by edge pattern. With one-way lanes a corner of an avenue crossing and a corner of a",
    "  boulevard T need different lanes, so those box cells get their own ids (21 more). Same art as today.",
]


# ================================================================================================ build (milestone 2)
# Lane specs follow AVENUE_LANES.md 6: "mirror_uk": false, no path keys (each language's curve library is searched by
# end points; English-UK holds every curve reversed under the same key), connects auto (low = the lanes' turns, high =
# its transpose). A cut whose geometry no stock curve has gets a new shape; where English-UK has no forward copy, a
# TWIN shape whose English geometry is the cut reversed (hwlanes writes UK copies reversed, so the twin's UK copy is
# the cut). lanekit prefers a spec's own curves when several share end points (task bvlanes line in compile_spec).

SHAPE0, SHAPE1 = 24000, 24999            # bvlanes curve shapes: 24000..24199 (protocol) + 24200..24999 (granted 2026-10-20)
BV_JN_T, BV_JM_T = 20707, 20708          # T junction entry row / middle row (PLAN.md 2)
BOX_OLD = (20900, 20901, 20902, 20903, 20904, 20905)
BOX_NEW = tuple(range(20912, 20950))
ARM_IDS = (20910, 20911)
CAPS = (20704, 20705, 20706)
AVCORE_SHAPES = {23600: [[255, 0, 80], [223, 0, 80], [191, 0, 80], [159, 0, 80], [128, 0, 80], [96, 0, 80], [64, 0, 80],
                         [32, 0, 80], [0, 0, 80]],
                 23603: [[0, 0, 175], [32, 0, 175], [64, 0, 175], [96, 0, 175], [128, 0, 175], [159, 0, 175],
                         [191, 0, 175], [223, 0, 175], [255, 0, 175]]}
TOL = 8.0                                # lane units: a curve "matches" a cut when every resampled point is this close


def _rs(pts, n=9):
    return resample([(p[0], p[-1]) for p in pts], n)


def same_geom(a, b, tol=TOL):
    if (a[0][0], a[0][-1]) != (b[0][0], b[0][-1]) or (a[-1][0], a[-1][-1]) != (b[-1][0], b[-1][-1]):
        return False
    return max(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(_rs(a), _rs(b))) <= tol


def _int_cut(lu):
    pts = resample(lu, 9)
    out = [[int(round(x)), 0, int(round(z))] for (x, z) in pts]
    for p in (out[0], out[-1]):                            # end points exactly on a border, off the corners
        s = side_of_pt((p[0], p[2]))
        if len(s) != 1:
            raise ValueError("cut end %s is not on exactly one side" % p)
    ded = [out[0]] + [p for i, p in enumerate(out[1:], 1) if p != out[i - 1]]
    return ded


def placements():
    """every scene's cells with the NEW rule's pieces: [(scene, cell, piece, state, [world cuts])]. The BV T columns
    take 20707 / 20708 (the T from z+ at state 2), the BVX boxes their (box config, cell) pieces from box_table()."""
    table = box_table()
    out = []
    for sc in scenes():
        want, cuts, bad, clash = cut_scene(sc)
        want = dict(want)
        _new_rule(sc, want, table)
        for c, (pid, st) in want.items():
            out.append((sc["name"], c, pid, st, cuts.get(c, [])))
    return out


def _new_rule(sc, want, table):
    """rewrite the placements of today's rule (boulevard.runs) into the new one (twin of boulevard.py / bvx.py)"""
    if sc["name"].startswith("road T"):
        for c, (pid, st) in list(want.items()):
            if pid == 20710:
                want[c] = (BV_JN_T, st)
            elif pid == 20711:
                frm_hi = any(p == 20712 and s == 2 for (p, s) in want.values())       # far row at state 2: T from z+
                want[c] = (BV_JM_T, 2 if frm_hi else 0)
    boxes = [c for c, (pid, st) in want.items() if pid in BOX_OLD]
    if boxes:
        cfg = box_config(set(boxes), sc["road"])
        for c in boxes:
            want[c] = table[(cfg[0], cfg[1], cfg[2], None, c[0] - cfg[4], c[1] - cfg[5])]


def box_config(cells, road):
    """real box -> (wx, hz, sides NESW 'A'/'C', x0, z0)"""
    xs, zs = [c[0] for c in cells], [c[1] for c in cells]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    sides = ""
    for beyond in ([(x, z0 - 1) for x in range(x0, x1 + 1)], [(x1 + 1, z) for z in range(z0, z1 + 1)],
                   [(x, z1 + 1) for x in range(x0, x1 + 1)], [(x0 - 1, z) for z in range(z0, z1 + 1)]):
        sides += "A" if all(b in road for b in beyond) else "C"
    return (x1 - x0 + 1, z1 - z0 + 1, sides, None, x0, z0)


def _rot_cfg(wx, hz, sides, i, j, k):
    """the box configuration turned k states: cell (i, j) -> (hz - 1 - j, i), sides N -> E"""
    for _ in range(k % 4):
        i, j = hz - 1 - j, i
        wx, hz = hz, wx
        sides = sides[3] + sides[:3]
    return wx, hz, sides, i, j


def box_table():
    """{(wx, hz, sides, None, x0, z0, i, j) ... } is awkward: -> {(wx, hz, sides, None, i, j)... }"""
    if hasattr(box_table, "_t"):
        return box_table._t
    groups = []                                         # [(piece, sig at state 0, desc)]
    canon = {}                                          # (wx, hz, sides, i, j) -> (piece, state)
    pool = list(BOX_OLD) + list(BOX_NEW)
    for sc in scenes():
        if not sc.get("box"):
            continue
        want, cuts, bad, clash = cut_scene(sc)
        cells = {c for c, (pid, st) in want.items() if pid in BOX_OLD}
        wx, hz, sides, _n, x0, z0 = box_config(cells, sc["road"])
        for c in sorted(cells):
            sig0 = sig_of(cuts.get(c, []), 0)
            hit = None
            for (pid, gsig, gdesc) in groups:
                for k in range(4):
                    if sig_of(cuts.get(c, []), k) == gsig:
                        hit = (pid, k)
                        break
                if hit:
                    break
            if not hit:
                pid = pool[len(groups)]
                old_pid, old_st = want[c]
                groups.append((pid, sig0, _desc_at(old_pid, old_st)))
                hit = (pid, 0)
            canon[(wx, hz, sides, c[0] - x0, c[1] - z0)] = hit
    table = {}
    for (wx, hz, sides, i, j), (pid, st) in canon.items():
        for k in range(4):
            key = _rot_cfg(wx, hz, sides, i, j, k)
            table[(key[0], key[1], key[2], None, key[3], key[4])] = (pid, (st + k) % 4)
    box_table._t = table
    box_table.groups = groups
    return table


def _desc_at(pid, st):
    """the real edge pattern of an old box piece placed at state st, seen in a new piece's own state-0 frame (the new
    piece is placed at state 0 where it is first met): the old pattern turned by st"""
    from netmod import bvx as BX
    canon = {v: k for k, v in BX.BOX.items()}[pid]
    return BX.rot(canon, st)


# ------------------------------------------------------------------------------------------------ curves
class Curves:
    def __init__(self, root=None):
        from netmod import lanekit as LK
        self.LK = LK
        g = LK.Game(root)
        self.lib = {"en": g.paths("ENGLISH").veh, "uk": g.paths("English-UK").veh}
        self.new = {}                                   # shape -> English pts
        self.by_geom = {}                               # tuple(pts) of a rotation -> (shape, r)
        for s, pts in AVCORE_SHAPES.items():
            self._index(s, pts)
        self.next = SHAPE0

    def _index(self, s, pts):
        self.new[s] = pts
        p = [list(v) for v in pts]
        for r in range(4):
            self.by_geom.setdefault(tuple(tuple(v) for v in p), (s, r))
            p = [[255 - v[2], v[1], v[0]] for v in p]

    def shape_for(self, pts):
        """a new shape (or an existing one turned) carrying exactly these English points"""
        k = tuple(tuple(v) for v in pts)
        if k in self.by_geom:
            return self.by_geom[k][0]
        if self.next > SHAPE1:
            raise ValueError("bvlanes: out of curve shapes (%d..%d)" % (SHAPE0, SHAPE1))
        s = self.next
        self.next += 1
        self._index(s, pts)
        return s

    def lang_curves(self, lang, own):
        """{key: pts} of a language's library with this package's new shapes (all of them) in it"""
        out = {}
        for s, pts in self.new.items():
            p = [list(v) for v in pts]
            for r in range(4):
                out[s * 256 + r] = (p if lang == "en" else p[::-1], s in own)
                p = [[255 - v[2], v[1], v[0]] for v in p]
        return out

    def pick(self, lang, a, b, own):
        """the key lanekit takes for a lane a -> b in `lang` (own = the spec's shapes) -> (key, pts, kind)"""
        mine = self.lang_curves(lang, own)
        hits = []
        for k, c in self.lib[lang].items():
            if (c["pts"][0][0], c["pts"][0][2]) == a and (c["pts"][-1][0], c["pts"][-1][2]) == b and k not in mine:
                hits.append((k, [list(v) for v in c["pts"]], "stock"))
        for k, (p, is_own) in mine.items():
            if (p[0][0], p[0][2]) == a and (p[-1][0], p[-1][2]) == b:
                hits.append((k, p, "own" if is_own else "other"))
        ownk = {s * 256 + r for s in own for r in range(4)}
        hits.sort(key=lambda h: (h[0] not in ownk, h[0]))
        return hits[0] if hits else None


DBV_BASE = {}                                      # task bvlanes: DBV piece -> its base (pedestrians, flag)


def dbv_placements():
    """the diagonal boulevard's placements (dbvlanes.py) with the package's current stamps; fills DBV_BASE"""
    from netmod import dbvlanes as DL
    from netmod import diagbv as DB
    man = json.load(open(os.path.join(DB.PACK, "manifest.json")))
    for v in man["variants"]:
        DBV_BASE[v["id"]] = v["base"]
    return DL.placements_dbv()


def piece_specs(root=None, dbv=False):
    """-> ({piece: spec}, Curves, report lines). One lane set per piece is asserted on the placements."""
    seen, states = {}, {}
    allp = list(placements()) + (list(dbv_placements()) if dbv else [])
    for name, c, pid, st, cuts in allp:
        loc = set()
        for ct in cuts:
            loc.add(tuple(tuple(v) for v in _int_cut([to_local(p, st) for p in ct["pts"]])))
        states.setdefault(pid, set()).add(st)
        if pid not in seen:
            seen[pid] = (loc, name, c, st)
        elif not same_set(seen[pid][0], loc):
            raise ValueError("piece %d: two lane sets (%s %s state %d / %s %s state %d)" % (
                (pid,) + seen[pid][1:] + (name, c, st)))
    seen.setdefault(20703, seen[20701])                 # one cell between two junctions: the middle row's lanes
    states[20703] = {0, 2}
    cv = Curves(root)
    specs, rep = {}, []
    for pid in sorted(seen):
        cuts = sorted(seen[pid][0])
        own, lanes = set(), []
        plan = []
        for cut in cuts:
            pts = [list(v) for v in cut]
            a, b = (pts[0][0], pts[0][2]), (pts[-1][0], pts[-1][2])
            plan.append((pts, a, b))
        for _round in range(4):                         # add own shapes until every language picks the cut's geometry
            bad = 0
            for pts, a, b in plan:
                for lang in ("en", "uk"):
                    h = cv.pick(lang, a, b, own)
                    if h and h[2] != "other" and same_geom(h[1], pts):
                        continue
                    bad += 1
                    own.add(cv.shape_for(pts if lang == "en" else pts[::-1]))
            if not bad:
                break
        else:
            raise ValueError("piece %d: curve picks do not settle" % pid)
        exits = set()
        for pts, a, b in plan:
            ln = {"from": [a[0], a[1]], "to": [b[0], b[1]]}
            if b in exits:
                ln["exit"] = False
            exits.add(b)
            lanes.append(ln)
        sp = {"piece": pid, "states": [0, 1, 2, 3], "flag": int(DBV_BASE[pid] == 43) if pid in DBV_BASE else (1 if pid in JUNCTION_LIKE else 0),
              "mirror_uk": False, "vehicle": {"class": "car", "speed": 64000, "lanes": lanes},
              "pedestrian": peds_of(pid), "connects": {"road": _turns(plan)},
              "curves": [{"shape": s, "pts": cv.new[s]} for s in sorted(own)],
              "_": "bvlanes.py: 3 lanes each way, right-hand (verify/bvlanes/PLAN.md); no path keys"}
        if not lanes:
            sp["connects"] = {"road": {"low": [], "high": []}}
            sp["_"] += "; a taper corner the curb cuts off: no lane"
        specs[pid] = sp
        PLAN_CUTS[pid] = [pts for pts, _a, _b in plan]
        rep.append("%d: %d lanes, states %s, %d own curve(s)" % (pid, len(lanes), sp["states"], len(own)))
    return specs, cv, rep


def _turns(plan):
    """the low half of the turn matrix: every lane's (entry side, exit side), sides as lanekit names them (lanes that
    share an exit node carry exit: false, which lanekit's "auto" would skip); high half = its transpose"""
    t = set()
    for pts, a, b in plan:
        sa, sb = side_of_pt(a), side_of_pt(b)
        t.add((SIDES[sa[0]], SIDES[sb[0]]))
    return sorted([x, y] for x, y in t)


def same_set(A, B, tol=4.0):
    """two lane sets (int cuts) equal within `tol` lane units (rounding of the same lane in two placements)"""
    def near(a, b):
        if math.hypot(a[0][0] - b[0][0], a[0][2] - b[0][2]) > 2 or math.hypot(a[-1][0] - b[-1][0], a[-1][2] - b[-1][2]) > 2:
            return False
        return max(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(_rs(a), _rs(b))) <= tol
    A, B = [list(c) for c in A], [list(c) for c in B]
    return all(any(near(a, b) for b in B) for a in A) and all(any(near(b, a) for a in A) for b in B)


JUNCTION_LIKE = set((20710, 20711, 20712, BV_JN_T, BV_JM_T) + BOX_OLD + BOX_NEW)
_PEDS = {}


def peds_of(pid):
    """pedestrian walks: the outer row's outer sidewalk (as today), the junction and box pieces their stock source's
    (43, or T 39 turned so its closed side is the piece's), none elsewhere (today they had road 29's fallback, walks
    across the curb)."""
    from netmod.diagave import _describe
    if pid in DBV_BASE:                                # DBV: its base's walks (what copy_base gave it)
        src = (DBV_BASE[pid], 0)
        if src not in _PEDS:
            _PEDS[src] = _describe(*src)["pedestrian"]
        return json.loads(json.dumps(_PEDS[src]))
    if pid == 20700:
        sp = _describe(29, 0)
        return {"walks": [w for w in sp["pedestrian"]["walks"] if w["from"][1] > 128],
                "exits": [e for e in sp["pedestrian"]["exits"] if e["at"][1] > 128]}
    src = None
    if pid in (20710, 20711, BV_JN_T, BV_JM_T):
        src = (43, 0)
    elif pid == 20712:
        src = (39, 1)
    elif pid in BOX_OLD + BOX_NEW:
        desc = {p: d for (p, s, d) in getattr(box_table, "groups", [])}.get(pid)
        if desc is None:
            return {"walks": [], "exits": []}
        src = (43, 0) if "C" not in desc else (39, (1 + desc.index("C") - 2) % 4)
    if src is None:
        return {"walks": [], "exits": []}
    if src not in _PEDS:
        _PEDS[src] = _describe(*src)["pedestrian"]
    return json.loads(json.dumps(_PEDS[src]))


def cmd_build(a):
    """write the lane specs into the boulevard / boulevard_junctions packages, the box table, the manifests' lanes"""
    specs, cv, rep = piece_specs(a.root, dbv=bool(a.dbv))
    bv_dir, bx_dir = a.bv, a.bvx
    for pid, sp in specs.items():
        d = a.dbv if pid in DBV_BASE else bx_dir if pid in BOX_OLD + BOX_NEW + ARM_IDS else bv_dir
        with open(os.path.join(d, "bvl_%d.lanes.json" % pid), "w", newline="\n") as fh:
            json.dump(sp, fh, indent=1)
    tab = box_table()
    lines = sorted("bvxc %d %d %s %d %d %d %d" % (k[0], k[1], k[2], k[4], k[5], v[0], v[1]) for k, v in tab.items())
    groups = [{"piece": p, "edges": d} for (p, s, d) in box_table.groups]
    with open(os.path.join(bx_dir, "bvlanes_boxes.json"), "w", newline="\n") as fh:
        json.dump({"_": "bvlanes.py build: box cells by (box w, h, sides NESW, cell i j) -> piece, state; the piece "
                        "art = bvx Box(edges) at state 0", "pieces": groups, "lines": lines}, fh, indent=1)
    print("\n".join(rep))
    print("specs %d, new curve shapes %d (%d..%d), box table %d lines, box pieces %d" % (
        len(specs), cv.next - SHAPE0, SHAPE0, cv.next - 1, len(lines), len(groups)))


PLAN_CUTS = {}


def cmd_verify(a):
    """compile every package with netpack's own lanes compiler, decode the state-0 records of ENGLISH and English-UK
    and check, per lane edge: the curve lanekit picked starts and ends at the edge's nodes and has the planned
    geometry (bvlanes' cut) in BOTH languages (right-hand everywhere, no reversed UK lane)"""
    from netmod import lanekit as LK
    from netmod import netpack_lanes as NL
    from netmod import hwlanes as HL
    root = a.root or os.environ.get("SC3_GAME_ROOT")
    piece_specs(root, dbv=any("diagonal" in pk for pk in a.packs))     # fills PLAN_CUTS
    g = LK.Game(root)
    bad = total = 0
    for pack in a.packs:
        man = json.load(open(os.path.join(pack, "manifest.json")))
        comp = NL.compile_entries(root, pack, man)
        libs = {}
        for lang in ("ENGLISH", "English-UK"):
            lib = {k: [tuple(p) for p in v["pts"]] for k, v in g.paths(lang).veh.items()}
            for s, pts in comp["curves"].items():
                for key, (p, hin, hout) in HL.curve_set(s, pts)["uk" if lang == "English-UK" else "en"].items():
                    lib[key] = [tuple(v) for v in p]
            libs[lang] = lib
        for e in comp["lanes"]:
            pid = e["piece"]
            if pid not in PLAN_CUTS:
                continue
            for lang in ("ENGLISH", "English-UK"):
                rec = LK.decode(dict((k & 0xff, b) for (_g, k, _t, b) in e["records"][lang])[0])
                for n in rec["veh"]:
                    for ed in n["edges"]:
                        if ed["to"] is None:
                            continue
                        total += 1
                        m = rec["veh"][ed["to"]]
                        pts = libs[lang].get(ed["path"])
                        a_, b_ = (n["x"], n["z"]), (m["x"], m["z"])
                        ok = pts is not None and (pts[0][0], pts[0][2]) == a_ and (pts[-1][0], pts[-1][2]) == b_
                        plan = [c for c in PLAN_CUTS[pid] if (c[0][0], c[0][2]) == a_ and (c[-1][0], c[-1][2]) == b_]
                        ok = ok and any(same_geom([list(v) for v in pts], c) for c in plan)
                        if not ok:
                            bad += 1
                            if bad <= 20:
                                print("BAD %d %s lane %s -> %s key %s" % (pid, lang, a_, b_, ed["path"]))
    print("verify: %d lane edges in ENGLISH + English-UK, %d off the plan" % (total, bad))
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    s = sub.add_parser("build")
    s.add_argument("bv")
    s.add_argument("bvx")
    s.add_argument("dbv", nargs="?", help="task bvlanes: the diagonal_boulevard package (its stamps from dbvlanes rebuild)")
    s.add_argument("--root")
    s = sub.add_parser("verify")
    s.add_argument("packs", nargs="+")
    s.add_argument("--root")
    s = sub.add_parser("sheet")
    s.add_argument("out")
    s.add_argument("--px", type=int, default=56)
    s.add_argument("--cols", type=int, default=3)
    a = ap.parse_args(argv)
    return {"check": cmd_check, "sheet": cmd_sheet, "build": cmd_build, "verify": cmd_verify}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
