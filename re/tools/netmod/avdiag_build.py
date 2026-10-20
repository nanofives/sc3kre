#!/usr/bin/env python3
r"""avdiag_build.py - lane specs of the diagonal avenue family on one-way halves (task avdiag, 2026-10-19).

Plan: verify/avdiag/PLAN.md. avdiag.py draws the planned lanes of a scene as WORLD polylines (corridor lines, U-turns,
merge tapers, turns); this file cuts them per cell, maps each cut into its piece's state-0 frame, and checks that a
piece gets the same lanes in every scene it appears in (a piece has one TrBlkAtt record per state). Then it finds or
makes the curves (AVENUE_LANES.md 2: no path keys, a curve per language by end points; where English lacks the lane's
geometry or its reverse, a new shape) and writes the specs.

Lane units: local x, z = (world - cell) * 255, rounded, so a border point is exactly 0 / 255 and both cells sharing
it agree. A piece at state s shows rot^s of its state-0 frame (lanekit.rot_pt: (x, z) -> (255 - z, x)).

  py -3.12 avdiag_build.py cuts [--scenes ends,junctions,merges,crossings]   per-piece lane sets + consistency report
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from netmod import avdiag as AV           # noqa: E402
from netmod import diagave as DA          # noqa: E402
from netmod import diagave_paint as DP    # noqa: E402
from netmod import lanekit as LK          # noqa: E402

U = 255.0
OURS = range(20500, 20600)


# ------------------------------------------------------------------------------------------------ scenes
def _finish(road, stock, roads=()):
    """road cells (+ stock straight-avenue cells, + straight road runs) -> (want, road, cors)"""
    want = {}
    bs = DA.bands(road)
    for b in bs:
        want.update(DA.wanted(b) or {})
    for c in road:
        if c not in want:
            want[c] = stock.get(c) or (29, 0 if ((c[0] - 1, c[1]) in road or (c[0] + 1, c[1]) in road) else 1)
    cors = [AV.Cor.band(b, road) for b in bs if b["ok"]]
    cors += AV.Cor.avenues({c: v for c, v in stock.items() if want.get(c) == v})
    for r in roads:                                     # a road runs through plain road and junction cells only
        rc = {q for q in r if want.get(q, (0,))[0] == 29 or 20510 <= want.get(q, (0,))[0] <= 20519}
        if rc:
            cors.append(AV.Cor.road(rc))
    return want, road, cors, bs


def scenes(which):
    """-> [(name, want, road, cors)]"""
    out = []
    if "ends" in which:
        for key, road in DA.footprints():
            w, r, c, bs = _finish(road, {})
            if all(b["ok"] for b in bs):
                out.append(("end %s" % (key,), w, r, c))
    if "junctions" in which:
        for sx in (1, -1):
            for ox, oz in ((sx, 0), (0, -1)):
                for kind in DA.JUNCTION_KINDS:
                    av = set(DA.drag(0, 0, 9, sx, "x")) | set(DA.drag(ox, oz, 9, sx, "x"))
                    jr = DA.junction_road(kind, sx, 9, ox, oz)
                    w, r, c, bs = _finish(av | jr, {}, [jr])
                    if all(b["ok"] for b in bs):
                        out.append(("junction %s %d %d,%d" % (kind, sx, ox, oz), w, r, c))
    if "merges" in which:
        for axis in (0, 1):
            for end in (0, 1):
                for cont in "AB":
                    road = DP.merge_case_footprint(axis, end, cont, rows=7)
                    w, r, c, bs = _finish(road, {})
                    if all(b["ok"] for b in bs):
                        out.append(("merge %d %d %s" % (axis, end, cont), w, r, c))
    if "crossings" in which:
        for kind in DA.XKINDS:
            for k in range(4):
                w, r, n, c = AV.scene_turned(kind, k)
                out.append(("crossing %s %d" % (kind, k), w, r, c))
    if "bends" in which:
        for kind in ("bend", "bend_x"):
            for k in range(4):
                w, r, n, c = AV.scene_turned(kind, k)
                out.append(("%s %d" % (kind, k), w, r, c))
    return out


# ------------------------------------------------------------------------------------------------ the planned lanes
RI, RO = AV.LANE_R["band"]


def _sq_hits(c, r, cell):
    """band-frame s values where lane line r of corridor c crosses cell's border (sorted)"""
    out = []
    x0, z0 = cell
    for ax, v in ((0, x0), (0, x0 + 1), (1, z0), (1, z0 + 1)):
        p0, p1 = c.at(0, r), c.at(1, r)
        d = p1[ax] - p0[ax]
        if abs(d) < 1e-12:
            continue
        s = (v - p0[ax]) / d
        q = c.at(s, r)
        o = q[1 - ax] - (z0 if ax == 0 else x0)
        if -1e-9 <= o <= 1 + 1e-9:
            out.append(s)
    return sorted(out)


def band_ends(c, want, road, cors, L):
    """-> {e: info} per band end. kinds: uturn (M = the last middle cell), merge (M, gone, cont), open (a junction /
    crossing / T: stop s), bend (the straight avenue), through"""
    AV.proposed(want, road, cors, L)                   # c.ends: open / bend / merge / tail / uturn by today's caps
    b = c.b
    mids = [m for m in b["A"] & b["B"] if m in road]
    out = {}
    for e in (-1, 1):
        en = dict(c.ends[e])
        M = max(mids, key=lambda m: c.sr((m[0] + .5, m[1] + .5))[0] * e)
        sM = c.sr((M[0] + .5, M[1] + .5))[0]
        if en["kind"] == "merge" and not en.get("tail"):
            # the continuing side = where the single road lies past M (the path cells and merge cells beyond M)
            past = [q for q in list(b.get("path", ())) + list(b.get("merge", {})) if
                    (c.sr((q[0] + .5, q[1] + .5))[0] - sM) * e > 0.3]
            rs = sum(c.sr((q[0] + .5, q[1] + .5))[1] for q in past)
            en["gone"] = -1 if rs > 0 else 1
            en["M"], en["sM"] = M, sM
            en["mk"] = "L" if any(20520 <= want[q][0] <= 20524 for q in b.get("merge", {})) else "R"
        elif en["kind"] in ("uturn", "merge"):          # a tail is an even end plus a dead stub
            en = {"kind": "uturn", "M": M, "sM": sM}
        elif en["kind"] == "open":
            se = c.s0 if e < 0 else c.s1
            near = [o for o in cors if o is not c and abs(o.t[0] * c.t[0] + o.t[1] * c.t[1]) < 0.9 and
                    o.s0 - 0.6 <= o.sr(c.at(se, 0))[0] <= o.s1 + 0.6 and abs(o.sr(c.at(se, 0))[1]) < 1.6]
            if not near:                                 # a free end without today's caps in view: still a U-turn
                en = {"kind": "uturn", "M": M, "sM": sM}
            else:                                        # a T: each lane stops on the other corridor's near edge
                for o in near:
                    W = {"road": 0.5, "avenue": 1.0, "band": 0.75}[o.kind]
                    f0, f1 = o.sr(c.at(0, 0))[1], o.sr(c.at(1, 0))[1]
                    cand = [(w - f0) / (f1 - f0) for w in (W, -W)]
                    mids_ = (c.s0 + c.s1) / 2
                    k = min(range(2), key=lambda i: (cand[i] - mids_) * e)
                    if abs(cand[k] - en["stop"]) < 1e-6:
                        en["edge"] = (o, (W, -W)[k])
        out[e] = en
    return out


def plan_lanes(want, road, cors, L, special=None):
    """-> [poly] world polylines in travel order (one-way, right-hand), for cutting into cells. special: the cells a turn
    may use (default: our junction / crossing pieces)"""
    if special is None:
        special = {c for c, (p, s) in want.items() if isinstance(p, int) and
                   (20510 <= p <= 20519 or 20540 <= p <= 20599 or 21806 <= p <= 21849)}
    polys = []
    straight = []                                        # (corridor, r, s lo, s hi, travel sign): split at turn nodes
    nodes = []                                           # (corridor, r, s) where a turn starts or ends
    lane_rng = {}                                        # (band, r) -> (s lo, s hi) of that lane's line
    made = []                                            # the turns: (c1, r1, sign1, a, c2, r2, sign2, b, left, h1, h2)
    tend = {}                                            # (corridor, r) -> s values where the lane stops at a T
    bands = [c for c in cors if c.kind == "band"]
    E = {}
    for c in bands:
        E[id(c)] = band_ends(c, want, road, cors, L)
    # ---- band carriageways
    for c in bands:
        ends = E[id(c)]
        for r, sg in c.lanes:
            lo, hi = None, None
            cut_at = {}
            for e, en in ends.items():
                if en["kind"] == "uturn":
                    hs = _sq_hits(c, r, en["M"])
                    s = max(hs, key=lambda v: -v * e)        # where the lane meets M on its band side
                elif en["kind"] == "merge":
                    sM = en["sM"]
                    g = en["gone"]
                    if r * g > 0:                            # the ending carriageway: into / out of the taper
                        s = sM + e * MERGE_P[en["mk"]][0]
                    elif abs(r) < RI + 1e-9:                 # the continuing side's one-way inner lane
                        s = sM + e * MERGE_P[en["mk"]][3]
                    else:                                    # the continuing outer lane: on into the single road
                        s = None
                elif en["kind"] == "bend":
                    o = en["to"]
                    sa = o.s0 - 0.5 if abs(o.sr(c.at(en["stop"], 0))[0] - o.s0) < abs(o.sr(c.at(en["stop"], 0))[0] - o.s1) \
                        else o.s1 + 0.5
                    f0, f1 = o.sr(c.at(0, r))[0], o.sr(c.at(1, r))[0]
                    s = (sa - f0) / (f1 - f0)
                elif en.get("edge"):
                    o, wv = en["edge"]
                    f0, f1 = o.sr(c.at(0, r))[1], o.sr(c.at(1, r))[1]
                    s = _snap(c, r, (wv - f0) / (f1 - f0), -1e9, 1e9, tol=0.04)   # no sliver past a border
                    tend.setdefault((id(c), round(r, 9)), set()).add(round(s, 9))
                else:
                    s = en["stop"]
                cut_at[e] = s
            lo, hi = cut_at[-1], cut_at[1]
            for e in (-1, 1):                                # the continuing outer lane: on past the split node
                if cut_at[e] is None:
                    en = ends[e]
                    sc, far = en["sM"] + e * MERGE_P[en["mk"]][2], en["far"]
                    part = [c.at(sc, r), c.at(far, r)]
                    polys.append(part if sg * e > 0 else part[::-1])
                    if e < 0:
                        lo = sc
                    else:
                        hi = sc
            straight.append((c, r, lo, hi, sg))
            lane_rng[(id(c), round(r, 9))] = (lo, hi)
        # ---- ends
        for e, en in ends.items():
            if en["kind"] == "uturn":
                for r in (RI, RO):
                    rin = -e * r                                    # arriving side (travels toward e): r * e < 0
                    hs = _sq_hits(c, rin, en["M"])
                    s0 = max(hs, key=lambda v: -v * e)
                    if r == RO:                                     # outer: a semicircle on the median line, r 124
                        polys.append([c.at(s0 + e * r * math.sin(math.pi * k / 48.0),
                                           -e * r * math.cos(math.pi * k / 48.0)) for k in range(49)])
                    else:                                           # inner: a reverse curve, left arc r 84 > 80
                        polys.append([c.at(s0 - e * ds, -e * rr) for ds, rr in _bulb(RI, UTURN_RHO, 30)])
            elif en["kind"] == "merge":
                g, sM = en["gone"], en["sM"]
                rci, rco = -g * RI, -g * RO
                kind = "L" if any(20520 <= want[q][0] <= 20524 for q in c.b.get("merge", {})) else "R"
                pa, pb, pc, pd = MERGE_P[kind]
                sa, sb, sc, sd = sM + e * pa, sM + e * pb, sM + e * pc, sM + e * pd
                far = en["far"]
                if -g == e:                                  # the ending side arrives: both lanes into the single road
                    for r in (g * RI, g * RO):
                        polys.append(AV.smooth(c, sa, r, sb, rci, n=24))
                    polys.append([c.at(sb, rci), c.at(far, rci)])
                    polys.append(AV.smooth(c, sc, rco, sd, rci, n=24))   # the continuing inner lane starts
                else:
                    polys.append([c.at(far, rci), c.at(sb, rci)])
                    for r in (g * RI, g * RO):
                        polys.append(AV.smooth(c, sb, rci, sa, r, n=24))
                    polys.append(AV.smooth(c, sd, rci, sc, rco, n=24))   # the continuing inner lane ends
    # ---- straight avenues and roads
    def road_span(c):
        """a road that ENDS in a junction cell (a T) stops at that cell's border, its turns start there"""
        lo, hi = c.s0 - 0.5, c.s1 + 0.5
        if c.kind == "road":
            for q in c.cells:
                sq = c.sr((q[0] + .5, q[1] + .5))[0]
                if not 20510 <= want.get(q, (0,))[0] <= 20519:
                    continue
                if abs(sq - c.s0) < 1e-6:
                    lo = sq + 0.5
                if abs(sq - c.s1) < 1e-6:
                    hi = sq - 0.5
            for v in (lo, hi):
                if v not in (c.s0 - 0.5, c.s1 + 0.5):
                    for rr, _ in c.lanes:
                        tend.setdefault((id(c), round(rr, 9)), set()).add(round(v, 9))
        return lo, hi
    for c in cors:
        if c.kind in ("avenue", "road"):
            lo, hi = road_span(c)
            for r, sg in c.lanes:
                straight.append((c, r, lo, hi, sg))

    # ---- turns where two corridors cross, inside the special cells
    def rng(c):
        if c.kind == "band":
            en = E[id(c)]
            return (en[-1].get("stop", c.s0) if en[-1]["kind"] != "uturn" else c.s0,
                    en[1].get("stop", c.s1) if en[1]["kind"] != "uturn" else c.s1)
        return road_span(c)

    def in_special(p):
        return (int(math.floor(p[0])), int(math.floor(p[1]))) in special

    near_sp = set(special)                              # where a turn may look for its lanes (one cell round)
    for q in list(special):
        near_sp |= {(q[0] + dx, q[1] + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (q[0] + dx, q[1] + dz) in want}

    def in_near(p):
        return (int(math.floor(p[0])), int(math.floor(p[1]))) in near_sp

    def _intervals(c, r, lo, hi, step=0.005, wide=False):
        """[(s_in, s_out)] stretches of lane line (c, r) within [lo, hi] that lie in special cells (borders snapped)"""
        out, cur = [], None
        n = int((hi - lo) / step) + 1
        for k in range(n + 1):
            sv = min(hi, lo + k * step)
            if (in_near if wide else in_special)(c.at(sv, r)):
                if cur is None:
                    cur = sv
            elif cur is not None:
                out.append((_snap(c, r, cur, lo, hi, step * 2), _snap(c, r, sv, lo, hi, step * 2)))
                cur = None
        if cur is not None:
            out.append((_snap(c, r, cur, lo, hi, step * 2), hi))
        return out

    def _region_end(c, r, sv, d, step=0.005):
        """walking lane line (c, r) from s = sv in direction d: the s where it leaves the special cells (a border)"""
        k = 0
        while in_special(c.at(sv + d * step * (k + 1), r)) and k < 4000:
            k += 1
        s_in = sv + d * step * k
        return _snap(c, r, s_in, -1e9, 1e9, tol=step * 2)


    for c1 in cors:
        for c2 in cors:
            if c2 is c1 or abs(c1.t[0] * c2.t[0] + c1.t[1] * c2.t[1]) > 0.9:
                continue
            if any(E.get(id(c), {}).get(e, {}).get("to") in (c1, c2) for c in (c1, c2) for e in (-1, 1)):
                continue
            lo1, hi1 = rng(c1)
            lo2, hi2 = rng(c2)
            for sgn1 in (1, -1):
                l1 = sorted([r for r, d in c1.lanes if d == sgn1], key=abs)
                for sgn2 in (1, -1):
                    l2 = sorted([r for r, d in c2.lanes if d == sgn2], key=abs)
                    h1 = (c1.t[0] * sgn1, c1.t[1] * sgn1)
                    h2 = (c2.t[0] * sgn2, c2.t[1] * sgn2)
                    left = h1[0] * h2[1] - h1[1] * h2[0] > 0
                    r1, r2 = (l1[0], l2[0]) if left else (l1[-1], l2[-1])
                    X = AV._isect(c1, r1, c2, r2)
                    if X is None:
                        continue
                    s1x, s2x = c1.sr(X)[0], c2.sr(X)[0]
                    lo1, hi1 = lane_rng.get((id(c1), round(r1, 9)), rng(c1))
                    lo2, hi2 = lane_rng.get((id(c2), round(r2, 9)), rng(c2))
                    I1 = _intervals(c1, r1, lo1 - 1.5, hi1 + 1.5)         # past a T end too: the turn may run on
                    I2 = _intervals(c2, r2, lo2 - 1.5, hi2 + 1.5)         # into the cells the lane stops at
                    if not I1:
                        I1 = _intervals(c1, r1, lo1 - 1.5, hi1 + 1.5, wide=True)
                    if not I2:
                        I2 = _intervals(c2, r2, lo2 - 1.5, hi2 + 1.5, wide=True)
                    if not I1 or not I2:
                        continue
                    # the special stretch of each lane nearest the crossing point (travel order u = s * sign)
                    i1 = min(I1, key=lambda iv: 0 if iv[0] <= s1x <= iv[1] else min(abs(s1x - iv[0]), abs(s1x - iv[1])))
                    i2 = min(I2, key=lambda iv: 0 if iv[0] <= s2x <= iv[1] else min(abs(s2x - iv[0]), abs(s2x - iv[1])))
                    if min(abs(s1x - v) for v in i1) > 1.6 and not i1[0] <= s1x <= i1[1]:
                        continue
                    if min(abs(s2x - v) for v in i2) > 1.6 and not i2[0] <= s2x <= i2[1]:
                        continue
                    # no turn out of a lane before it begins, none into a lane after it ends (at a T: the leaving
                    # carriageway starts at the crossing, the arriving one stops there)
                    if s1x * sgn1 < min(lo1 * sgn1, hi1 * sgn1) - 0.05 or s2x * sgn2 > max(lo2 * sgn2, hi2 * sgn2) + 0.05:
                        continue
                    phi = math.acos(max(-1.0, min(1.0, h1[0] * h2[0] + h1[1] * h2[1])))
                    u_in1, u_out1 = sorted((i1[0] * sgn1, i1[1] * sgn1))
                    u_in2, u_out2 = sorted((i2[0] * sgn2, i2[1] * sgn2))
                    found = None
                    if left:                                       # first: a circular fillet of radius > 80 at X
                        Rf = 92.0 / U
                        tl = Rf * math.tan(phi / 2)
                        ua_, ub_ = s1x * sgn1 - tl, s2x * sgn2 + tl
                        if min(lo1 * sgn1, hi1 * sgn1) - 1e-6 <= ua_ <= max(lo1 * sgn1, hi1 * sgn1) + 1e-6 and                                 min(lo2 * sgn2, hi2 * sgn2) - 1e-6 <= ub_ <= max(lo2 * sgn2, hi2 * sgn2) + 1e-6:
                            P0, P3 = c1.at(ua_ * sgn1, r1), c2.at(ub_ * sgn2, r2)
                            cen = (P0[0] - h1[1] * Rf, P0[1] + h1[0] * Rf)   # left of h1: (-hz, hx)
                            a0 = math.atan2(P0[1] - cen[1], P0[0] - cen[0])
                            a1 = math.atan2(P3[1] - cen[1], P3[0] - cen[0])
                            if a1 <= a0:
                                a1 += 2 * math.pi
                            tc = [(cen[0] + Rf * math.cos(a0 + (a1 - a0) * k / 24.0),
                                   cen[1] + Rf * math.sin(a0 + (a1 - a0) * k / 24.0)) for k in range(25)]
                            if all(math.hypot(sg[-1][0] - sg[0][0], sg[-1][1] - sg[0][1]) * U >= 6 for _, sg in cut(tc))                                     and not any(not in_special(p) for p in _dense(tc, 0.02)[1:-1])                                     and math.dist(tc[-1], P3) < 0.01:
                                found = (tc, ua_ * sgn1, ub_ * sgn2)
                    for mul in (1.0, 1.25, 1.5, 1.8, 2.2, 0.8):     # a longer run-in when a left turn is too tight
                        if found:
                            break
                        lead = (0.45 if left else 0.3) * math.tan(phi / 2) * mul
                        ua = max(u_in1, min(u_out1 - 0.15, s1x * sgn1 - lead))
                        ub = min(u_out2, max(u_in2 + 0.15, s2x * sgn2 + lead))
                        ua = min(max(ua, min(lo1 * sgn1, hi1 * sgn1)), max(lo1 * sgn1, hi1 * sgn1))   # on the lane
                        ub = min(max(ub, min(lo2 * sgn2, hi2 * sgn2)), max(lo2 * sgn2, hi2 * sgn2))
                        # a lane that stops at a T is met at its very end / start (no dead stub beside the turn)
                        e1 = max(lo1 * sgn1, hi1 * sgn1)
                        if round(e1 * sgn1, 9) in tend.get((id(c1), round(r1, 9)), ()):
                            ua = e1
                        b0 = min(lo2 * sgn2, hi2 * sgn2)
                        if round(b0 * sgn2, 9) in tend.get((id(c2), round(r2, 9)), ()):
                            ub = b0
                        a, b2 = _snap(c1, r1, ua * sgn1, lo1, hi1), _snap(c2, r2, ub * sgn2, lo2, hi2)
                        P0, P3 = c1.at(a, r1), c2.at(b2, r2)
                        d = math.hypot(P3[0] - P0[0], P3[1] - P0[1])
                        if d < 0.1:
                            continue
                        for f in (0.45, 0.40, 0.50, 0.35, 0.55, 0.30, 0.60, 0.65, 0.70):
                            L_ = f * d                     # the tangent length
                            P1 = (P0[0] + h1[0] * L_, P0[1] + h1[1] * L_)
                            P2 = (P3[0] - h2[0] * L_, P3[1] - h2[1] * L_)
                            tc = [_cubic(P0, P1, P2, P3, k / 24.0) for k in range(25)]
                            if not all(math.hypot(sg[-1][0] - sg[0][0], sg[-1][1] - sg[0][1]) * U >= 6 for _, sg in cut(tc)):
                                continue                   # a cell would get a sliver
                            if any(not in_special(p) for p in _dense(tc, 0.02)[1:-1]):
                                continue                   # a turn must stay inside the junction / crossing cells
                            lr = left_radius([(p[0] * U, p[1] * U) for p in tc]) if left else None
                            if lr is not None and lr < LEFT_MIN:
                                continue                   # owner rule: no left turn of radius <= 80
                            found = (tc, a, b2)
                            break
                        if found:
                            break
                    if DEBUG:
                        print("turn %s->%s %s: %s" % (c1.kind, c2.kind, "L" if left else "R", "ok" if found else "none"))
                    if found:
                        tc, a, b2 = found
                        polys.append(tc)
                        TURNS.append((c1.kind, c2.kind, "left" if left else "right"))
                        nodes.append((c1, r1, a))
                        nodes.append((c2, r2, b2))
                        made.append((c1, r1, sgn1, a, c2, r2, sgn2, b2, left, h1, h2))
                    else:
                        DROPPED.append((c1.kind, c2.kind, "left" if left else "right"))
    # ---- a lane that stops at a T and lost its left turn (too tight, owner rule) shares the right turn of the lane
    #      beside it; a lane that starts at a T without a feed takes one from the lane feeding its neighbour
    for c in bands:
        for r, sg in c.lanes:
            T = tend.get((id(c), round(r, 9)), ())
            if not T:
                continue
            lo, hi = lane_rng[(id(c), round(r, 9))]
            end_s, start_s = (hi, lo) if sg > 0 else (lo, hi)
            if round(end_s, 9) in T and not any(m[0] is c and abs(m[1] - r) < 1e-9 for m in made):
                mate = [m for m in made if m[0] is c and m[2] == sg and not m[8]]
                if mate:
                    m = mate[0]
                    P0, P3 = c.at(end_s, r), m[4].at(m[7], m[5])
                    d = math.dist(P0, P3)
                    hh1, hh2 = (c.t[0] * sg, c.t[1] * sg), m[10]
                    tc = [_cubic(P0, (P0[0] + hh1[0] * .45 * d, P0[1] + hh1[1] * .45 * d),
                                 (P3[0] - hh2[0] * .45 * d, P3[1] - hh2[1] * .45 * d), P3, k / 24.0) for k in range(25)]
                    polys.append(tc)
                    TURNS.append((c.kind, m[4].kind, "right (shared)"))
            if round(start_s, 9) in T and not any(m[4] is c and abs(m[5] - r) < 1e-9 for m in made):
                mate = [m for m in made if m[4] is c and m[6] == sg and not m[8]]
                if mate:
                    m = mate[0]
                    P0, P3 = m[0].at(m[3], m[1]), c.at(start_s, r)
                    d = math.dist(P0, P3)
                    hh1, hh2 = m[9], (c.t[0] * sg, c.t[1] * sg)
                    tc = [_cubic(P0, (P0[0] + hh1[0] * .45 * d, P0[1] + hh1[1] * .45 * d),
                                 (P3[0] - hh2[0] * .45 * d, P3[1] - hh2[1] * .45 * d), P3, k / 24.0) for k in range(25)]
                    polys.append(tc)
                    TURNS.append((m[0].kind, c.kind, "right (shared)"))
    # ---- through lanes, split at every turn node on them
    for c, r, lo, hi, sg in straight:
        cuts = sorted({round(sv, 9) for (cc, rr, sv) in nodes if cc is c and abs(rr - r) < 1e-9 and lo + 1e-6 < sv < hi - 1e-6})
        pts = [lo] + cuts + [hi]
        for s0, s1 in zip(pts, pts[1:]):
            seg = [c.at(s0, r), c.at(s1, r)]
            polys.append(seg if sg > 0 else seg[::-1])
    return polys


def _snap(c, r, sv, lo, hi, tol=0.12):
    """a turn node near a cell border goes onto it (the through lane has a node there anyway); never past lo / hi"""
    p = c.at(sv, r)
    best = None
    for ax in (0, 1):
        if abs(c.t[ax]) < 1e-9:
            continue
        for v in (math.floor(p[ax]), math.ceil(p[ax])):
            sb = sv + (v - p[ax]) / c.t[ax]
            if abs(sb - sv) <= tol and lo - 1e-9 <= sb <= hi + 1e-9 and (best is None or abs(sb - sv) < abs(best - sv)):
                best = sb
    return sv if best is None else best


# 2026-10-19: a "left turn of radius <= 80 hangs the game" rule was set and then retracted (avjunc's hang was its own
# Frida probe). LEFT_MIN keeps the check available.
LEFT_MIN = 0.0       # lane units; 88 while the rule stood. RETRACTED 2026-10-19 (the hang was a Frida probe): left
                     # turns follow the geometry again; fillets of radius 92 are still tried first where they fit
UTURN_RHO = 0.33     # inner U-turn left arc, cells (84.2 lane units): the widest whose apex stays inside the outer
                     # semicircle (r 0.485 = 124 units, fixed by the cell) with a 14-unit gap


def _bulb(a, rho, n=10):
    """the inner U-turn as a reverse curve: right arc (radius rho) away from the median, a left arc of radius rho
    centred on the median line round the end, right arc back. Canonical frame: (ds, r) with ds <= 0 measured from
    the entry point toward the end, the arriving lane at r = +a heading toward the end. -> [(ds, r)]"""
    h = math.sqrt(4 * rho * rho - (a + rho) ** 2)        # entry to the left arc's centre, along the band
    c1, c2, c3 = (0.0, a + rho), (-h, 0.0), (0.0, -(a + rho))
    t1 = ((c1[0] + c2[0]) / 2, (c1[1] + c2[1]) / 2)      # tangency points of the reverse curves
    t2 = ((c3[0] + c2[0]) / 2, (c3[1] + c2[1]) / 2)

    def arc(cen, p, q, ccw, m):
        a0 = math.atan2(p[1] - cen[1], p[0] - cen[0])
        a1 = math.atan2(q[1] - cen[1], q[0] - cen[0])
        if ccw and a1 <= a0:
            a1 += 2 * math.pi
        if not ccw and a1 >= a0:
            a1 -= 2 * math.pi
        return [(cen[0] + rho * math.cos(a0 + (a1 - a0) * k / m), cen[1] + rho * math.sin(a0 + (a1 - a0) * k / m))
                for k in range(m + 1)]
    p = arc(c1, (0.0, a), t1, False, n)                 # right: clockwise in (ds, r), a left turn is counter-clockwise
    p += arc(c2, t1, t2, True, 3 * n)[1:]
    p += arc(c3, t2, (0.0, -a), False, n)[1:]
    return p


def left_radius(pts, step=4.0, span=16.0):
    """smallest radius (lane units) of the left-turning stretches of a polyline in lane units, None if it has none.
    Left = toward left(h) = (-hz, hx), the side the median is on for right-hand traffic."""
    d = [0.0]
    for p, q in zip(pts, pts[1:]):
        d.append(d[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
    if d[-1] < 2 * span:
        return None
    rs = _resample(pts, max(4, int(d[-1] / step)))
    k = max(1, int(span / step))
    best = None
    for i in range(k, len(rs) - k):
        a, b, c = rs[i - k], rs[i], rs[i + k]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if cr <= 1e-6:
            continue
        R = math.dist(a, b) * math.dist(b, c) * math.dist(c, a) / (2 * cr)
        best = R if best is None else min(best, R)
    return best


AV_HALF = {"road": 0.5, "avenue": 1.0, "band": 0.75}
TURNS = []                                                # the turns plan_lanes made (for reports)
DROPPED = []                                              # the turns it could not fit (cells, slivers, radius)
DEBUG = False


def _cubic(p0, p1, p2, p3, u):
    v = 1 - u
    return (v ** 3 * p0[0] + 3 * v * v * u * p1[0] + 3 * v * u * u * p2[0] + u ** 3 * p3[0],
            v ** 3 * p0[1] + 3 * v * v * u * p1[1] + 3 * v * u * u * p2[1] + u ** 3 * p3[1])
# merge tapers, offsets from the last middle cell's centre toward the end (s units, a row is 1.41): the ending side
# leaves its line at a, joins the single road's inner lane at b; the continuing side's inner lane splits off the outer
# lane at c and runs on its own line from d. Found by `avdiag_build.py mergefit` (every cut inside the merge cells).
MERGE_P = {"L": (-0.1, 2.2, 2.5, -0.4), "R": (-1.5, 0.8, 1.1, -1.8)}


# ------------------------------------------------------------------------------------------------ cutting
def _dense(pts, step=0.01):
    out = [pts[0]]
    for p0, p1 in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / step))
        out += [(p0[0] + (p1[0] - p0[0]) * k / n, p0[1] + (p1[1] - p0[1]) * k / n) for k in range(1, n + 1)]
    return out


def _border_hit(p, q):
    """the first point on a cell border after p, up to and including q (None when there is none)"""
    best = None
    for ax in (0, 1):
        a, b = p[ax], q[ax]
        if a == b:
            continue
        lo, hi = min(a, b), max(a, b)
        for v in range(int(math.floor(lo)), int(math.floor(hi)) + 1):
            if v == a or not lo <= v <= hi:
                continue
            u = (v - a) / (b - a)
            if 0 < u <= 1 and (best is None or u < best[0]):
                best = (u, ax, v)
    if best is None:
        return None
    u, ax, v = best
    pt = [p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u]
    pt[ax] = float(v)
    return tuple(pt)


def cut(poly):
    """world polyline -> [(cell, [world points])] pieces split exactly on cell borders"""
    pts = _dense(poly)
    out, cur = [], [pts[0]]
    for q in pts[1:]:
        p = cur[-1]
        while True:
            h = _border_hit(p, q)
            if h is None:
                break
            cur.append(h)
            out.append(cur)
            cur = [h]
            p = h
        cur.append(q)
    out.append(cur)
    res = []
    for seg in out:
        if len(seg) < 2 or math.hypot(seg[-1][0] - seg[0][0], seg[-1][1] - seg[0][1]) < 1e-6:
            continue
        m = seg[len(seg) // 2] if len(seg) > 2 else ((seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2)
        res.append(((int(math.floor(m[0])), int(math.floor(m[1]))), seg))
    return res


def to_local(cell, p):
    return (int(round((p[0] - cell[0]) * U)), int(round((p[1] - cell[1]) * U)))


def to_state0(p, st):
    return LK.rot_pt(p[0], p[1], k=(4 - st) % 4)


def _simplify(lpts):
    """local integer points: drop repeats and collinear runs"""
    out = []
    for p in lpts:
        if out and out[-1] == p:
            continue
        out.append(p)
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 0.5 * math.hypot(c[0] - a[0], c[1] - a[1]):
            out.pop(i)
        else:
            i += 1
    # no two points closer than 6 lane units (integer rounding on close points makes the heading jitter)
    kept = [out[0]]
    for p in out[1:-1]:
        if math.dist(p, kept[-1]) >= 6:
            kept.append(p)
    if len(out) > 1:
        if len(kept) > 1 and math.dist(kept[-1], out[-1]) < 6:
            kept.pop()
        kept.append(out[-1])
    return kept


def cell_lanes(want, polys):
    """-> {cell: set of (a, b, pts)} in the PIECE's state-0 frame (a, b end points, pts the local polyline)"""
    out = {}
    probs = []
    for poly, col, w in polys:
        for cell, seg in cut(poly):
            if cell not in want:
                probs.append("lane leaves the road at %s" % (cell,))
                continue
            pid, st = want[cell]
            lp = [to_state0(to_local(cell, p), st) for p in seg]
            lp = _simplify(lp)
            if len(lp) < 2:
                continue
            out.setdefault(cell, set()).add((lp[0], lp[-1], tuple(lp)))
    return out, probs


def collect(which, L=None, verbose=False):
    L = L or AV.Lanes()
    per = {}          # pid -> {frozenset of (a, b)} -> [scene names]
    geo = {}          # (pid, a, b) -> pts
    probs = []
    for name, want, road, cors in scenes(which):
        polys = [(p, None, 0) for p in plan_lanes(want, road, cors, L)]
        cl, pr = cell_lanes(want, polys)
        probs += ["%s: %s" % (name, p) for p in pr]
        for cell, (pid, st) in want.items():
            if not (isinstance(pid, int) and (pid in OURS or pid in (35, 18004, 1999))):
                continue
            if pid in (35, 18004, 1999) and not any(cell in c.cells for c in cors if c.kind == "band"):
                continue
            ls = cl.get(cell, set())
            key = frozenset((a, b) for a, b, _ in ls)
            per.setdefault(pid, {}).setdefault(key, []).append("%s @%s.%d" % (name, cell, st))
            for a, b, pts in ls:
                geo.setdefault((pid, a, b), pts)
    return per, geo, probs


# ------------------------------------------------------------------------------------------------ roles, authoring, check
# New ids (PLAN.md 3): the last middle cell of a free end carries the two-lane U-turn; cells past it carry no lanes.
ID_U = {-1: 21800, 1: 21801}              # 20500 as the last middle cell at the end toward -t / +t (art 20500)
ID_NONE = {20505: 21802, 18004: 21803, 1999: 21804, 35: 21805}       # past a U-turn: no lanes (art of the base piece)
ID_T = {20510: 21806, 20511: 21807}      # 20510 / 20511 where the road ends in the cell (a T touching one carriageway)
# crossing pieces whose art the X and the T of the same pair share, but whose lanes differ (the T's diagonal ends):
# the T templates of recipe_crossings.json write these instead (art of the X piece)
ID_XT = {"TSX": {20553: 21810, 20554: 21811}, "TSZ": {20565: 21812, 20568: 21813},
         "TX0": {20541: 21814, 20543: 21815}, "TX1": {20549: 21816}}


def t_templates():
    """diagave's crossing templates with ID_XT applied to the T kinds (in memory; `avdiag_build.py build` writes them)"""
    ts = DA.x_tables()
    for t in ts:
        m = ID_XT.get(t["kind"], {})
        t["writes"] = [[dx, dz, m.get(p, p), st] for dx, dz, p, st in t["writes"]]
    return ts


t_templates()
NEW_ART = {21810: 20553, 21811: 20554, 21812: 20565, 21813: 20568, 21814: 20541, 21815: 20543, 21816: 20549,
           21806: 20510, 21807: 20511, 21800: 20500, 21801: 20500, 21802: 20505, 21803: 18004, 21804: 1999, 21805: 35}


def roles(want, road, cors, L):
    """the DAV writer's rule on top of diagave.wanted: -> {cell: piece id} for every band cell (others unchanged)"""
    out = {c: p for c, (p, s) in want.items()}
    probs = []
    for c, (p, s) in want.items():                     # a single-half junction cell whose road arrives from one side only
        if p in ID_T:
            vert = p == 20511
            nb = [(c[0], c[1] - 1), (c[0], c[1] + 1)] if (vert ^ (s % 2 == 1)) else [(c[0] - 1, c[1]), (c[0] + 1, c[1])]
            arms = [q for q in nb if want.get(q, (0,))[0] in (29,) or 20510 <= want.get(q, (0,))[0] <= 20519]
            if len(arms) == 1:
                out[c] = ID_T[p]
    for c in cors:
        if c.kind != "band":
            continue
        for e, en in band_ends(c, want, road, cors, L).items():
            if en["kind"] != "uturn":
                continue
            M, sM = en["M"], en["sM"]
            if want[M][0] == 20500:
                out[M] = ID_U[e if c.b["axis"] == 0 else -e]     # the corner the U-turn wraps, in 20500's own frame
            elif not 20501 <= want[M][0] <= 20504:
                probs.append("end cell %s holds %s" % (M, want[M]))
            for q in c.cells:
                if q not in road or q == M:
                    continue
                if (c.sr((q[0] + .5, q[1] + .5))[0] - sM) * e > 0.1:
                    p = want[q][0]
                    if p in ID_NONE:
                        out[q] = ID_NONE[p]
                    else:
                        probs.append("cell %s past a U-turn holds %s" % (q, want[q]))
    return out, probs


FAMILIES = {"ends": "ends", "merges": "merges_canon", "junctions": "junctions", "crossings": "crossings"}


def scenes_for(fam):
    if fam == "merges_canon":
        out = []
        for kind in "LR":
            w, r, c, bs = _finish(DP.merge_footprint(kind), {})
            out.append(("merge canon %s" % kind, w, r, c))
        return out
    return scenes([fam])


def author(L=None, fams=("ends", "merges", "junctions", "crossings")):
    """-> ({piece id: (lane set, pts by (a, b))}, report lines). A lane set = frozenset of (a, b) in the piece's state-0
    frame; the set used most often wins, the others are reported."""
    L = L or AV.Lanes()
    per, geo, rep = {}, {}, []
    for fam in fams:
        for name, want, road, cors in scenes_for(FAMILIES[fam]):
            ro, pr = roles(want, road, cors, L)
            rep += ["%s: %s" % (name, p) for p in pr]
            cl, pr = cell_lanes(want, [(p, None, 0) for p in plan_lanes(want, road, cors, L)])
            rep += ["%s: %s" % (name, p) for p in pr]
            for cell, pid in ro.items():
                if not (20500 <= pid <= 20599 or 21800 <= pid <= 21849):
                    continue
                if fam != "merges" and 20520 <= pid <= 20534:
                    continue                                  # merge pieces: from the canonical scenes only
                ls = cl.get(cell, set())
                key = frozenset((a, b) for a, b, _ in ls)
                per.setdefault(pid, {}).setdefault(key, []).append("%s @%s.%d" % (name, cell, want[cell][1]))
                for a, b, pts in ls:
                    geo.setdefault((pid, a, b), pts)
    out = {}
    for pid, sets in sorted(per.items()):
        best = max(sets.items(), key=lambda kv: (len(kv[1]), len(kv[0])))
        out[pid] = (best[0], {ab: geo[(pid,) + ab] for ab in best[0]})
        if len(sets) > 1:
            rep.append("%d: %d lane sets; kept %d use(s), others %s" % (
                pid, len(sets), len(best[1]), [(len(v), v[0]) for k, v in sets.items() if k != best[0]]))
    return out, rep


def _spec_lanes(path):
    s = json.load(open(path))
    return [(tuple(l["from"]), tuple(l["to"])) for l in s["vehicle"]["lanes"]]


def verify(authored, L=None, fams=("ends", "merges", "junctions", "crossings", "bends")):
    """place the authored lanes (and the stock / avcore lanes around them) in every scene and check that every lane end
    on a border meets a lane of the cell beyond at the same point, in the same direction"""
    L = L or AV.Lanes()
    avl = os.path.join(HERE, "examples", "avenue_lanes", "avl_21700.lanes.json")
    straight = _spec_lanes(avl)
    stock_cache = {}
    probs, n_ok = [], 0
    allsc = []
    for fam in fams:
        allsc += scenes(["merges" if fam == "merges" else fam])
    for name, want, road, cors in allsc:
        ro, pr = roles(want, road, cors, L)
        probs += ["%s: %s" % (name, p) for p in pr]
        lanes = {}                                       # cell -> [(a_world, b_world)]
        for cell, (pid0, st) in want.items():
            pid = ro[cell]
            if pid in authored:
                ls = authored[pid][0]
            elif pid == 11204:
                ls = straight
            elif pid >= 20000:
                probs.append("%s: no authored lanes for %d at %s" % (name, pid, cell))
                continue
            else:
                if (pid, 0) not in stock_cache:
                    stock_cache[(pid, 0)] = [(ln["pts"][0], ln["pts"][-1]) for ln in L.lanes(pid, 0)]
                ls = stock_cache[(pid, 0)]
            w = []
            for a, b in ls:
                aw = LK.rot_pt(a[0], a[1], k=st)
                bw = LK.rot_pt(b[0], b[1], k=st)
                w.append(((cell[0] + aw[0] / U, cell[1] + aw[1] / U), (cell[0] + bw[0] / U, cell[1] + bw[1] / U)))
            lanes[cell] = w

        def key(p):
            return (int(round(p[0] * U)), int(round(p[1] * U)))
        starts = {cell: {key(a) for a, b in ls} for cell, ls in lanes.items()}
        ends_ = {cell: {key(b) for a, b in ls} for cell, ls in lanes.items()}
        ours = lambda c: c in ro and (20500 <= ro[c] <= 20599 or 21800 <= ro[c] <= 21849)   # noqa: E731
        for cell, ls in lanes.items():
            for a, b in ls:
                for p, is_exit in ((b, True), (a, False)):
                    nb = _beyond(cell, p)
                    if nb is None:
                        continue
                    if not (ours(cell) or ours(nb)):
                        continue
                    if nb not in lanes:
                        if nb not in road:
                            probs.append("%s: %s %s at %s leads into a cell with no road %s" % (
                                name, ro[cell], "exit" if is_exit else "entry", key(p), nb))
                        continue
                    pool = starts[nb] if is_exit else ends_[nb]
                    if key(p) in pool:
                        n_ok += 1
                    else:
                        probs.append("%s: %s.%d %s at %s: %s.%d has no %s there" % (
                            name, ro[cell], want[cell][1], "exit" if is_exit else "entry", key(p), ro[nb],
                            want[nb][1], "entry" if is_exit else "exit"))
    return n_ok, probs


def _beyond(cell, p):
    x, z = cell
    lx, lz = (p[0] - x) * U, (p[1] - z) * U
    if lx < 0.5:
        return (x - 1, z)
    if lx > U - 0.5:
        return (x + 1, z)
    if lz < 0.5:
        return (x, z - 1)
    if lz > U - 0.5:
        return (x, z + 1)
    return None


def cmd_author(a):
    authored, rep = author(fams=a.fams.split(","))
    for pid in sorted(authored):
        print(pid, sorted(authored[pid][0]))
    for r in rep:
        print("NOTE", r)
    n, probs = verify(authored, fams=a.check.split(","))
    for p in probs[:a.max]:
        print("PROBLEM", p)
    print("joins checked %d, problems %d" % (n, len(probs)))



# ------------------------------------------------------------------------------------------------ curves + specs
SHAPES = list(range(23800, 23900)) + list(range(25000, 25500))     # this stream's grants (protocol)
SIDE_NAME = {0: "x-", 1: "z-", 2: "x+", 3: "z+"}                    # lanekit side index


def _resample(pts, n=16):
    """polyline -> n + 1 points evenly spaced by arc length"""
    d = [0.0]
    for p, q in zip(pts, pts[1:]):
        d.append(d[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
    out, j = [], 0
    for k in range(n + 1):
        t = d[-1] * k / n
        while j < len(d) - 2 and d[j + 1] < t:
            j += 1
        seg = d[j + 1] - d[j] or 1.0
        u = (t - d[j]) / seg
        out.append((pts[j][0] + (pts[j + 1][0] - pts[j][0]) * u, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * u))
    return out


def _dev(p, q):
    a, b = _resample(p), _resample(q)
    return max(math.hypot(x[0] - y[0], x[1] - y[1]) for x, y in zip(a, b))


class Curves:
    """English curve library (stock + this stream's new shapes) searched by end points, as lanekit does"""

    def __init__(self, game):
        from netmod import hwlanes as HL
        self.HL = HL
        self.P = game.paths("ENGLISH")
        self.new = {}                    # shape -> pts (state-0 frame, [x, 0, z])
        self.free = list(SHAPES)
        self.reused, self.conflicts = 0, []

    def need(self, a, b, pts, who):
        """an English curve from a to b along pts; -> new shape number or None (an existing curve serves)"""
        hits = self.P.find("veh", a, b)
        if hits:
            c = self.P.veh[hits[0]]
            dv = _dev([(p[0], p[2]) for p in c["pts"]], pts)
            if dv > 12:
                self.conflicts.append("%s: lane %s -> %s: curve %d has these end points but runs %.0f units off" %
                                      (who, a, b, hits[0], dv))
            else:
                self.reused += 1
            return (hits[0] >> 8) if (hits[0] >> 8) in self.new else None   # ours: the spec carries it as well
        return self._add(pts)

    def _add(self, pts):
        s = self.free.pop(0)
        p3 = [[int(p[0]), 0, int(p[1])] for p in pts]
        self.new[s] = p3
        for key, (p, hin, hout) in self.HL.curve_set(s, p3)["en"].items():
            self.P.veh[key] = {"pts": [tuple(v) for v in p], "in": hin, "out": hout, "extra": self.HL.EXTRA}
        return s


def lane_curves(C, a, b, pts, who, depth=0):
    """-> (via points, new shapes): split the lane at interior nodes until every segment has a curve of its own path in
    both directions (English forward, and its reverse for English-UK's copy), where a stock curve with the same end
    points runs elsewhere (lanekit takes the lowest key among the curves whose end points fit)"""
    def fits(p, q, seg):
        hits = C.P.find("veh", p, q)
        if not hits:
            return True                                   # a new shape will be made
        c = C.P.veh[hits[0]]
        return _dev([(v[0], v[2]) for v in c["pts"]], seg) <= 12
    if (fits(a, b, pts) and fits(b, a, pts[::-1])) or len(pts) < 2 or depth > 3:
        n0 = len(C.conflicts)
        s1 = C.need(a, b, pts, who)
        s2 = C.need(b, a, pts[::-1], who)
        return [], [s for s in (s1, s2) if s is not None]
    # split at the point of the polyline nearest the middle of its length (integer lane units)
    dense = _resample(pts, 32)
    m = tuple(int(round(v)) for v in dense[16])
    k = min(range(1, len(pts) - 1), key=lambda i: math.hypot(pts[i][0] - m[0], pts[i][1] - m[1])) if len(pts) > 2 else None
    if k is not None and math.hypot(pts[k][0] - m[0], pts[k][1] - m[1]) < 3:
        m = tuple(pts[k])
        first, second = pts[:k + 1], pts[k:]
    else:
        # insert m: the segment of pts that holds it
        best = None
        for i in range(len(pts) - 1):
            p, q = pts[i], pts[i + 1]
            dx, dz = q[0] - p[0], q[1] - p[1]
            L2 = dx * dx + dz * dz or 1
            u = max(0.0, min(1.0, ((m[0] - p[0]) * dx + (m[1] - p[1]) * dz) / L2))
            d = math.hypot(p[0] + u * dx - m[0], p[1] + u * dz - m[1])
            if best is None or d < best[0]:
                best = (d, i)
        i = best[1]
        first, second = pts[:i + 1] + [m], [m] + pts[i + 1:]
    v1, s1 = lane_curves(C, a, m, first, who, depth + 1)
    v2, s2 = lane_curves(C, m, b, second, who, depth + 1)
    return v1 + [list(m)] + v2, s1 + s2


def _side(p):
    x, z = p
    out = []
    if x == 0:
        out.append(0)
    if x == 255:
        out.append(2)
    if z == 0:
        out.append(1)
    if z == 255:
        out.append(3)
    return out


def connects_of(lanes):
    """turn matrix low half from the lanes: entry side -> every exit side reachable through the lane graph"""
    nxt = {}
    for a, b in lanes:
        nxt.setdefault(a, []).append(b)
    turns = set()
    for a, b in lanes:
        sa = _side(a)
        if len(sa) != 1:
            continue
        seen, stack = set(), [b]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            sb = _side(n)
            if len(sb) == 1:
                turns.add((sa[0], sb[0]))
                continue
            stack += nxt.get(n, [])
    return sorted([SIDE_NAME[f], SIDE_NAME[t]] for f, t in turns)


def graph_problems(pid, lanes):
    """interior nodes need a way in and a way on; every entry must reach an exit"""
    out = []
    ins, outs = {}, {}
    for a, b in lanes:
        outs.setdefault(a, []).append(b)
        ins.setdefault(b, []).append(a)
    for n in set(ins) | set(outs):
        if _side(n):
            continue
        if n not in ins or n not in outs:
            out.append("%d: interior node %s has %s" % (pid, n, "no way in" if n not in ins else "no way on"))
    return out


def _ped_of(pid, L, specs):
    if pid in specs:
        return specs[pid].get("pedestrian"), specs[pid].get("flag", 0)
    base = {21802: 35, 21803: 18004, 21804: 1999, 21805: 35, 20505: 35}.get(pid, pid)
    blob = L.g.trblkatt().get(base * 256)
    sp, _ = LK.describe(LK.decode(blob), L.P, base, exact=False)
    return sp.get("pedestrian"), sp.get("flag", 0)


def cmd_build(a):
    L = AV.Lanes()
    authored, rep = author(L)
    n, probs = verify(authored, L)
    if probs:
        for p in probs[:20]:
            print("PROBLEM", p)
        raise SystemExit("verify: %d problems, nothing written" % len(probs))
    print("verify: %d joins, 0 problems" % n)
    old = {}
    for f in os.listdir(a.pack):
        if f.endswith(".lanes.json"):
            s = json.load(open(os.path.join(a.pack, f)))
            old[s["piece"]] = (f, s)
    specs_old = {p: s for p, (f, s) in old.items()}
    C = Curves(L.g)
    out, gprobs = {}, []
    for pid in sorted(authored):
        ls, geo = authored[pid]
        art = NEW_ART.get(pid, pid)
        ped, flag = _ped_of(art, L, specs_old)
        lanes, seen_exit, shapes = [], set(), []
        for ab in sorted(ls):
            ga, gb = ab
            pts = [tuple(p) for p in geo[ab]]
            via, ss = lane_curves(C, ga, gb, pts, pid)          # English-UK's copy of each reverse runs forward
            shapes += [x for x in ss if x not in shapes]
            ex = bool(_side(gb)) and gb not in seen_exit
            if _side(gb):
                seen_exit.add(gb)
            ln = {"from": list(ga), "to": list(gb), "exit": ex}
            if via:
                ln["via"] = via
            lanes.append(ln)
        gprobs += graph_problems(pid, ls)
        spec = {"_": "avdiag_build.py: one-way diagonal avenue lanes (right-hand, verify/avdiag/PLAN.md), no path keys",
                "piece": pid, "states": [0, 1, 2, 3], "flag": flag, "alt": [0, 0, 0, 0], "mirror_uk": False,
                "vehicle": {"class": "car", "speed": 64000, "lanes": lanes},
                "pedestrian": ped or {"walks": [], "exits": []},
                "connects": {"road": connects_of(ls)}}
        if shapes:
            spec["curves"] = [{"shape": s, "pts": C.new[s]} for s in shapes]
        fname = old[pid][0] if pid in old else ("mid_20505.lanes.json" if pid == 20505 else "avd_%d.lanes.json" % pid)
        out[pid] = (fname, spec)
    for g in gprobs:
        print("GRAPH", g)
    for c in C.conflicts:
        print("CURVE", c)
    print("pieces %d, curves reused %d, new shapes %d (%d..%d), conflicts %d" % (
        len(out), C.reused, len(C.new), min(C.new) if C.new else 0, max(C.new) if C.new else 0, len(C.conflicts)))
    if not a.write:
        print("dry run: --write to write the specs")
        return 0
    for pid, (fname, spec) in out.items():
        json.dump(spec, open(os.path.join(a.pack, fname), "w", newline="\n"), indent=1)
    print("wrote %d specs into %s" % (len(out), a.pack))
    write_manifest(a.pack, out)
    return 0


def write_manifest(pack, out):
    """manifest.json: variants for the new ids (art of the piece they stand for), lanes entries in build order (a spec
    uses the curves of the specs before it), save_43 for new ids whose art piece saves as 43, the T crossing ids in the
    crossing templates (recipe_crossings.json too), and the writer's role table for sc3netmod's DAV block"""
    mp = os.path.join(pack, "manifest.json")
    m = json.load(open(mp))
    byid = {v["id"]: v for v in m["variants"]}
    for nid, art in sorted(NEW_ART.items()):
        if art in byid:
            v = json.loads(json.dumps(byid[art]))
        else:                                            # a stock cap / diagonal: its own frames
            v = {"base": art, "network": "ROAD", "name": {"*": "Diagonal avenue", "ENGLISH": "Avenida diagonal"},
                 "art": {"from": art}, "trblkatt": "copy_base"}
        v["id"] = nid
        byid[nid] = v
    m["variants"] = [byid[k] for k in sorted(byid)]
    m["lanes"] = [{"piece": pid, "spec": fname} for pid, (fname, spec) in out.items()]
    a = m["auto_diagonal_avenues"][0]
    s43 = set(a["save_43"]) | {nid for nid, art in NEW_ART.items() if art in a["save_43"]}
    s43 -= {ID_U[-1], ID_U[1]}                           # the U-turn 20500s save as 43 through their davu line
    a["save_43"] = sorted(s43)
    rp = os.path.join(pack, "recipe_crossings.json")
    rec = json.load(open(rp))
    for t in rec["templates"]:
        mm = ID_XT.get(t["kind"], {})
        t["writes"] = [[dx, dz, mm.get(p, p), st] for dx, dz, p, st in t["writes"]]
    kinds = {t["id"]: t["kind"] for t in rec["templates"]}
    for t in a["crossing"]:
        mm = ID_XT.get(kinds[t["id"]], {})
        t["writes"] = [[dx, dz, mm.get(p, p), st] for dx, dz, p, st in t["writes"]]
    a["oneway"] = {"uturn": [ID_U[-1], ID_U[1]], "none": {str(k): v for k, v in sorted(ID_NONE.items())},
                   "junction_t": {str(k): v for k, v in sorted(ID_T.items())}}
    m["avenue_lines"] = ["avlj %d %s" % (p, e) for p, e in sorted(AVLJ.items())]
    json.dump(rec, open(rp, "w", newline="\n"), indent=1)
    json.dump(m, open(mp, "w", newline="\n"), indent=1)
    stale = os.path.join(pack, "oneway_roles.json")
    if os.path.exists(stale):
        os.remove(stale)
    print("manifest: %d variants, %d lanes entries, save_43 %d, %d avlj lines; crossing templates updated" % (
        len(m["variants"]), len(m["lanes"]), len(a["save_43"]), len(m["avenue_lines"])))


# the pieces a straight avenue band ends on (bends, XS / TS crossings): `avdiag.py joins` (40 / 40 ends accepted with
# these letters; a side the lanes cross both ways, never a face, is '.')
AVLJ = {20500: "IOIO", 20505: "..OI", 20555: "O..I", 20558: ".I.O", 20559: ".I.O", 20562: ".IO.", 20566: "O..I",
        20567: ".I.O", 20574: ".I.O", 20575: ".IO.", 20577: "OO.I", 20582: ".I.O", 20583: "O.II", 20588: "I.O."}



# ------------------------------------------------------------------------------------------------ hwave diagonal
def hwave_decks():
    """the four lanes of the highway <-> diagonal avenue transition with one-way avenue halves: each highway lane drops
    onto the avenue lane of its side and rank (hwave_build.py's frame: p = x - z, the exit carriageway at p > 0 drives
    +x +z; the avenue's p > 0 strip now drives +x +z on both lanes, the p < 0 strip -x -z), no crossing"""
    import hwave_build as HW
    r2 = 2 ** 0.5
    ex_o, ex_i, en_o, en_i = 0.396 * r2, 0.170 * r2, -0.396 * r2, -0.170 * r2
    hi_o, hi_i = (12.0, 11.0 + 80 / 255.0), (12.0, 11.0 + 175 / 255.0)     # p 0.686 / 0.314 on (12, 11)'s x- side
    lo_o, lo_i = (11.0 + 80 / 255.0, 12.0), (11.0 + 175 / 255.0, 12.0)     # p -0.686 / -0.314 on (11, 12)'s z- side

    def p_of(pt):
        return pt[0] - pt[1]

    def q_of(pt):
        return pt[0] + pt[1]

    def beyond(pt, k):
        return (pt[0] + k * 0.3, pt[1] + k * 0.3)
    q0 = 14.0
    out = []
    for e, h in ((ex_o, hi_o), (ex_i, hi_i)):            # highway exit -> the avenue's +x +z strip
        out.append(HW.d_lane([HW._pq(e, q0)] + HW._across(e, p_of(h), 20.0, q_of(h)) + [beyond(h, 1)]))
    for e, l in ((en_o, lo_o), (en_i, lo_i)):            # the avenue's -x -z strip -> highway entry
        out.append(HW.d_lane([beyond(l, 1), l] + HW._across(p_of(l), e, q_of(l), 20.0) + [HW._pq(e, q0)]))
    return out


def _dev3(p, q):
    def rs(pts, n=16):
        d = [0.0]
        for a, b in zip(pts, pts[1:]):
            d.append(d[-1] + math.dist(a, b))
        out, j = [], 0
        for k in range(n + 1):
            t = d[-1] * k / n
            while j < len(d) - 2 and d[j + 1] < t:
                j += 1
            u = (t - d[j]) / ((d[j + 1] - d[j]) or 1.0)
            out.append(tuple(pts[j][i] + (pts[j + 1][i] - pts[j][i]) * u for i in range(3)))
        return out
    return max(math.dist(x, y) for x, y in zip(rs(p), rs(q)))


def cmd_hwave(a):
    """lanes of 21604..21609 (package examples/highway_avenue): hwave_decks cut by hwlanes.build_cells, then no path
    keys, "mirror_uk": false, and for every cut its curve and the reverse (English-UK's copy) found or made"""
    import hwave_paint as WP
    from netmod import hwlanes as HL
    g = LK.Game()
    P = g.paths("ENGLISH")
    specs, _ = HL.build_cells(hwave_decks(), list(WP.DCELLS), 1, WP.DCELLS, states=(0, 1, 2, 3))
    shape = a.shape0
    made, probs = {}, []
    for cell, sp in sorted(specs.items(), key=lambda kv: kv[1]["piece"]):
        cv = {c["shape"]: c["pts"] for c in sp.pop("curves")}
        new_curves = []
        for ln in sp["vehicle"]["lanes"]:
            pts = cv[ln.pop("path") // 256]
            for seq in (pts, pts[::-1]):
                A, B = (seq[0][0], seq[0][2]), (seq[-1][0], seq[-1][2])
                hits = P.find("veh", A, B)
                if hits:
                    dv = _dev3([tuple(v) for v in P.veh[hits[0]]["pts"]], [tuple(v) for v in seq])
                    if dv > 12:
                        probs.append("%d: %s -> %s: curve %d fits the end points but runs %.0f off" % (sp["piece"], A, B, hits[0], dv))
                    elif (hits[0] >> 8) in made:
                        new_curves.append({"shape": hits[0] >> 8, "pts": made[hits[0] >> 8]})
                    continue
                made[shape] = [list(v) for v in seq]
                for key, (p, hin, hout) in HL.curve_set(shape, made[shape])["en"].items():
                    P.veh[key] = {"pts": [tuple(v) for v in p], "in": hin, "out": hout, "extra": HL.EXTRA}
                new_curves.append({"shape": shape, "pts": made[shape]})
                shape += 1
        sp["mirror_uk"] = False
        sp["_"] = ("avdiag_build.py hwave: highway <-> diagonal avenue on one-way halves, each lane keeps its side "
                   "(no crossing), no path keys")
        sp["curves"] = new_curves
        old = os.path.join(a.pkg, "hwave_%d.lanes.json" % sp["piece"])
        if os.path.exists(old):
            o = json.load(open(old))
            sp["pedestrian"] = o.get("pedestrian", sp.get("pedestrian"))
        if a.write:
            json.dump(sp, open(old, "w", newline="\n"), indent=1)
        print(sp["piece"], cell, len(sp["vehicle"]["lanes"]), "lanes", [(l["from"], l["to"]) for l in sp["vehicle"]["lanes"]])
    for p in probs:
        print("CURVE", p)
    print("new shapes %d (%d..%d), problems %d%s" % (len(made), a.shape0, shape - 1, len(probs), "" if a.write else "; dry run"))


# ------------------------------------------------------------------------------------------------ owner sheet (built)
BUILT_ROWS = [
    ("end", "Band and free ends", "two-lane U-turn inside the last middle cell; the caps past it carry no lanes"),
    ("tail", "One drag a step longer", "U-turn at the shorter drag's end; the extra step carries no lanes (a dead stub)"),
    ("merge", "Merge into a single road", "the ending side's 2 lanes join the single road's lane; its other lane widens to 2"),
    ("bend", "Bend into the straight avenue", "no new lanes: each lane meets avcore's one-way half on the joint line"),
    ("cross-x", "Road crossing the avenue", "median opening: 8 turns (right from the outer lane, left from the inner)"),
    ("T-W", "Road meeting one side", "right in, right out (the median has no opening there)"),
    ("stem-top", "Avenue ending on a road", "4 turns: the arriving side turns left / right, the road feeds the leaving side"),
    ("XSX", "Diagonal x straight avenue", "through on both + 8 turns"),
    ("TSX", "Diagonal ending on the straight avenue", "4 turns"),
    ("XX0", "Diagonal x diagonal", "through on both + 8 turns"),
    ("TX0", "Diagonal ending on a diagonal", "4 turns"),
]


def _fit(im, w):
    if im.width <= w:
        return im
    return im.resize((w, int(im.height * w / float(im.width))))


def cmd_sheet(a):
    """owner sheet: today's lanes | the lanes as built, per kind (pieces labelled with the ids the writer places)"""
    from PIL import Image, ImageDraw, ImageFont
    L = AV.Lanes()
    FT, FB, F = (ImageFont.truetype(n, s) for n, s in (("arialbd.ttf", 26), ("arialbd.ttf", 19), ("arial.ttf", 16)))
    rows = [r for r in BUILT_ROWS if not a.kinds or r[0] in a.kinds.split(",")]
    PW = 560
    panels = []
    for kind, title, text in rows:
        want, road, notes, cors = AV.scene(kind)
        jr = [DA.junction_road(kind, 1, 7, 1, 0)] if kind in DA.JUNCTION_KINDS else []
        want2, road2, cors2, bs = _finish(road, {c: v for c, v in want.items() if v[0] == 11204}, jr)
        ro, _ = roles(want2, road2, cors2, L)
        today = AV.draw(want, L, None, scale=0.3)
        del TURNS[:]
        polys = plan_lanes(want2, road2, cors2, L)
        out = []
        for p in polys:
            d = (p[-1][0] - p[0][0], p[-1][1] - p[0][1])
            turn = len(p) == 25
            col = AV.GREEN if turn else (AV.RED if d[1] > 1e-6 or (abs(d[1]) < 1e-6 and d[0] < 0) else AV.BLUE)
            out.append((p, col, 2 if turn else 3))
        lab = {c: (ro[c], v[1]) for c, v in want2.items()}
        new = AV.draw_world(lab, out, None, scale=0.3)
        panels.append((title, text, _fit(today, PW), _fit(new, PW)))
        print(kind, len(TURNS), "turns")
    BW, NC = 2 * PW + 30, 2
    rowsH = [max(max(p[2].height, p[3].height) for p in panels[k:k + NC]) + 74 for k in range(0, len(panels), NC)]
    W, H = NC * BW + (NC + 1) * 30, 120 + sum(rowsH) + 20
    sh = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(sh)
    d.text((20, 14), a.title, font=FT, fill=(0, 0, 0))
    d.text((20, 50), "In each pair, left: today's lanes. Right: the lanes as BUILT, drawn from the world lines the "
           "package's specs were cut from. Red / blue = the two directions, green = turns, U-turns, tapers. "
           "Game x to the left, z down.", font=F, fill=(40, 40, 40))
    d.text((20, 74), "Offline check: every lane end on a border meets a lane of the next cell at the same point and "
           "direction, every drag shape, junction and crossing kind, 4 turns each (19,336 joins, 0 problems).",
           font=F, fill=(40, 40, 40))
    y = 112
    for k in range(0, len(panels), NC):
        for m, (title, text, im1, im2) in enumerate(panels[k:k + NC]):
            x = 30 + m * (BW + 30)
            d.text((x, y), title, font=FB, fill=(0, 0, 0))
            d.text((x, y + 26), "built: " + text, font=F, fill=(20, 110, 40))
            sh.paste(im1, (x, y + 68))
            sh.paste(im2, (x + PW + 30, y + 68))
        y += rowsH[k // NC]
    sh.save(a.out)
    print(a.out, sh.size)



def cmd_mergefit(a):
    """grid search of MERGE_P per canonical merge (L: B ends, R: A ends): every taper / split point and curve inside the
    merge cells, nodes at least 12 lane units from a cell border; longest tapers win"""
    L = AV.Lanes()
    steps = [k * 0.1 for k in range(-35, 36)]
    for kind in "LR":
        want, road, cors, bs = _finish(DP.merge_footprint(kind), {})
        c = [x for x in cors if x.kind == "band"][0]
        ends = band_ends(c, want, road, cors, L)
        e, en = [(e, en) for e, en in ends.items() if en["kind"] == "merge"][0]
        g, sM = en["gone"], en["sM"]
        mcells = {q for q, (p, st) in want.items() if 20520 <= p <= 20534}

        def inside(p, margin=12 / U):
            q = (int(math.floor(p[0])), int(math.floor(p[1])))
            fx, fz = p[0] - q[0], p[1] - q[1]
            return q in mcells and min(fx, 1 - fx, fz, 1 - fz) >= margin

        def curve_ok(pts):
            return all(((int(math.floor(p[0])), int(math.floor(p[1]))) in mcells) for p in _dense(pts, 0.02))
        rci, rco = -g * RI, -g * RO
        best1 = None
        for pa in steps:
            for pb in steps:
                if pb < pa + 0.8:
                    continue
                sa, sb = sM + e * pa, sM + e * pb
                pts = [c.at(sa, g * RI), c.at(sa, g * RO), c.at(sb, rci)]
                if not all(inside(p) for p in pts):
                    continue
                if not all(curve_ok(AV.smooth(c, sa, r, sb, rci, n=24)) for r in (g * RI, g * RO)):
                    continue
                sc = pb - pa
                if best1 is None or sc > best1[0]:
                    best1 = (sc, pa, pb)
        best2 = None
        for pc in steps:
            for pd in steps:
                if pc < pd + 0.6 or best1 is None or best1[2] < pd + 0.3:
                    continue
                sc_, sd = sM + e * pc, sM + e * pd
                if not (inside(c.at(sc_, rco)) and inside(c.at(sd, rci))):
                    continue
                if not curve_ok(AV.smooth(c, sc_, rco, sd, rci, n=24)):
                    continue
                sc = pc - pd
                if best2 is None or sc > best2[0]:
                    best2 = (sc, pc, pd)
        print(kind, "gone", g, "end", e, "taper", best1, "split", best2)
        if best1 and best2:
            print('    "%s": (%.1f, %.1f, %.1f, %.1f),' % (kind, best1[1], best1[2], best2[1], best2[2]))


def cmd_cuts(a):
    per, geo, probs = collect(a.scenes.split(","))
    for pid in sorted(per):
        sets = per[pid]
        print("%d: %d lane set(s)%s" % (pid, len(sets), "" if len(sets) == 1 else "  <-- differs by scene"))
        for k, (ls, where) in enumerate(sorted(sets.items(), key=lambda kv: -len(kv[1]))):
            print("   set %d (%d use(s), e.g. %s): %s" % (k, len(where), where[0], sorted(ls)))
    for p in sorted(set(probs))[:40]:
        print("PROBLEM", p)
    print("problems: %d" % len(set(probs)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("cuts")
    s.add_argument("--scenes", default="ends")
    s = sub.add_parser("author")
    s.add_argument("--fams", default="ends,merges,junctions,crossings")
    s.add_argument("--check", default="ends,merges,junctions,crossings,bends")
    s.add_argument("--max", type=int, default=60)
    sub.add_parser("mergefit")
    s = sub.add_parser("sheet")
    s.add_argument("out")
    s.add_argument("--kinds", default="")
    s.add_argument("--title", default="Diagonal avenues on one-way halves: the lanes as built (avdiag)")
    s = sub.add_parser("hwave")
    s.add_argument("pkg")
    s.add_argument("--shape0", type=int, default=25400)
    s.add_argument("--write", action="store_true")
    s = sub.add_parser("build")
    s.add_argument("pack")
    s.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    return {"cuts": cmd_cuts, "author": cmd_author, "mergefit": cmd_mergefit, "build": cmd_build, "hwave": cmd_hwave, "sheet": cmd_sheet}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
