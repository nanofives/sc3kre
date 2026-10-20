#!/usr/bin/env python3
r"""dbvlanes.py - diagonal boulevard lanes for the avenue lane rework (task bvlanes, 2026-10-19): 3 lanes each way.

The straight boulevard's rule (bvlanes.py, verify/bvlanes/PLAN.md) on the diagonal band of diagbv.py. Canonical frame
of a band (diagbv: axis 0, the down-right diagonal): rows z hold cells a..a+3 (a = z + P0), p = x - z across, q = x + z
along. Strip A (p P0 .. P0 + 1) runs -q, strip C (P0 + 2 .. P0 + 3) +q: the median on the driver's left (right-hand).
Lane offsets across a strip: 80 / 175 / 270 (/256) from the outer edge, as the straight boulevard's; a lane at offset
f is the 45 degree chord through the stock 35 slots of every cell it crosses. The diagonal single road of a taper
keeps stock 35's lanes: -q at k + 80/256, +q at k + 175/256 of its strip k.

Each band's lanes are drawn per END in the end's own bottom frame (diagbv.classify_end: the band's last full row at
row 0, a = z there), from the band's middle row to the end and on into what follows (avenue, road, U-turn cap,
straight boulevard), then put in place (the top end turned half a circle). Junctions (diagbv JUNCTIONS: a row road
along x on one band row, a column road along z through four rows) add their road lanes and every turn, with arcs
fitted between any two directions (45 / 135 degree turns).

  py -3.12 dbvlanes.py check            every DBV case (diagbv.check_cases), pieces whose placements disagree
"""
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from netmod import bvlanes as BL          # noqa: E402

S2 = math.sqrt(2.0)
OFF = (80 / 256.0, 175 / 256.0, 270 / 256.0)        # A side lanes, outer -> inner (p from the band's p0)
STEP = 1.0 / 64.0
QH = (-1 / S2, -1 / S2)                              # A heading (-q)
QC = (1 / S2, 1 / S2)                                # C heading (+q)


def _w(q, p):
    return ((q + p) / 2.0, (q - p) / 2.0)


def line_q(p_of, q0, q1, sign):
    """a lane along the band: p = p_of(q) for q from q0 to q1, driven toward +q (sign 1) or -q (-1)"""
    n = max(2, int(abs(q1 - q0) / STEP))
    pts = [_w(q0 + (q1 - q0) * k / n, p_of(q0 + (q1 - q0) * k / n)) for k in range(n + 1)]
    return pts if sign > 0 else pts[::-1]


def _smooth_line(pts, win=24, passes=3):
    """moving average along a lane (window `win` points of STEP, ends kept): rounds the corners the curb clamp leaves"""
    for _ in range(passes):
        out = list(pts)
        for i in range(win, len(pts) - win):
            xs = pts[i - win:i + win + 1]
            out[i] = (sum(p[0] for p in xs) / len(xs), sum(p[1] for p in xs) / len(xs))
        pts = out
    return pts


def _s2arc(t, L=0.6, D=(175.0 - 80.0) / 256.0):
    """0..1 profile of an S made of two tangent circular arcs (length L, lateral shift D, true cells), t in 0..1"""
    t = min(1.0, max(0.0, t))
    Dt = D / S2                                          # the p shift between two lanes, as a true distance
    R = (L * L + Dt * Dt) / (4.0 * Dt)
    s = t * L
    if s <= L / 2:
        y = R - math.sqrt(max(0.0, R * R - s * s))
    else:
        y = Dt - (R - math.sqrt(max(0.0, R * R - (L - s) ** 2)))
    return y / Dt


def smooth(t):
    return BL.smooth(t)


def clamp(v, lo, hi):
    return min(hi, max(lo, v))


# ------------------------------------------------------------------------------------------------ general turns
def _unit(v):
    L = math.hypot(*v)
    return (v[0] / L, v[1] / L)


def fillet(pin, h, pout, g):
    """lane from pin heading h to pout heading g: straight, an arc tangent to both lines, straight (any angle between
    them). Falls back to a cubic when the lines meet behind either point."""
    h, g = _unit(h), _unit(g)
    det = h[0] * (-g[1]) - h[1] * (-g[0])
    if abs(det) < 1e-9:
        return BL.seg(pin, pout)
    dx, dz = pout[0] - pin[0], pout[1] - pin[1]
    la = (dx * (-g[1]) - dz * (-g[0])) / det        # pin + la h = pout - lb g
    lb = (h[0] * dz - h[1] * dx) / det
    if la < -1e-6 or lb < -1e-6:
        return _cubic(pin, h, pout, g)
    I = (pin[0] + la * h[0], pin[1] + la * h[1])
    t = min(la, lb)
    cosang = max(-1.0, min(1.0, h[0] * g[0] + h[1] * g[1]))
    phi = math.acos(cosang)                          # turn angle
    if phi < 1e-3:
        return BL.seg(pin, pout)
    r = t / math.tan(phi / 2.0)
    A = (I[0] - t * h[0], I[1] - t * h[1])
    B = (I[0] + t * g[0], I[1] + t * g[1])
    cross = h[0] * g[1] - h[1] * g[0]
    n = (-h[1], h[0]) if cross > 0 else (h[1], -h[0])     # toward the centre
    C = (A[0] + r * n[0], A[1] + r * n[1])
    a0 = math.atan2(A[1] - C[1], A[0] - C[0])
    a1 = math.atan2(B[1] - C[1], B[0] - C[0])
    if cross > 0 and a1 < a0:
        a1 += 2 * math.pi
    if cross < 0 and a1 > a0:
        a1 -= 2 * math.pi
    return BL.join(BL.seg(pin, A), BL.arc(C, r, a0, a1), BL.seg(B, pout))


def _cubic(a, h, b, g, n=48):
    L = math.hypot(b[0] - a[0], b[1] - a[1]) / 2.0
    p1 = (a[0] + h[0] * L, a[1] + h[1] * L)
    p2 = (b[0] - g[0] * L, b[1] - g[1] * L)
    out = []
    for k in range(n + 1):
        t = k / n
        u = 1 - t
        out.append((u ** 3 * a[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * b[0],
                    u ** 3 * a[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * b[1]))
    return out


def junction_turns(arms, inside):
    """arms: [{"name", "in": [(pt, h)] outer -> inner, "out": [(pt, g)] outer -> inner, "straight": arm name fed
    straight from (or None)}]. Every turn: right from the outer lane(s), left from the inner lane(s), 2 from a 3-lane
    arm, 1 otherwise, as many as fit where the target has no straight feeder; merges aim at a virtual lane one slot
    further in (inside(pt) must hold) and bend onto the real one at the edge. -> [Lane]"""
    out = []
    fed = {a["name"]: False for a in arms}
    for a in arms:
        if a.get("straight"):
            fed[a["straight"]] = True
    # an arm no straight feeds (the band's side past a stem, a T's road) must get every one of its lanes from the
    # turns: count its right / left turning lanes, and let the last right (or left) one fan out over the rest
    fan = {}
    used = set()
    for b in arms:
        if fed[b["name"]] or not b["out"]:
            continue
        g = b["out"][0][1]
        nr = nl = 0
        for a in arms:
            if a is b or not a["in"]:
                continue
            h = a["in"][0][1]
            cross = h[0] * g[1] - h[1] * g[0]
            if abs(cross) < 0.2:
                continue
            m = min(len(a["in"]), len(b["out"]))
            if cross < 0:
                nr += m
            else:
                nl += m
        fan[b["name"]] = (nr, nl, len(b["out"]))
    for a in arms:
        if not a["in"]:
            continue
        h = a["in"][0][1]
        n = len(a["in"])
        for b in arms:
            if b is a or not b["out"]:
                continue
            g = b["out"][0][1]
            cross = h[0] * g[1] - h[1] * g[0]
            if abs(cross) < 0.2:
                continue                              # straight on (the band / road lanes themselves) or a U-turn
            which = "l" if cross > 0 else "r"
            m = 2 if n >= 3 else 1
            if not fed[b["name"]]:
                m = min(n, len(b["out"]))
            srcs = a["in"][:m] if which == "r" else a["in"][::-1][:m]
            tg = b["out"] if which == "r" else b["out"][::-1]
            pairs = [(k, k) for k in range(len(srcs))]
            if b["name"] in fan:
                nr, nl, T = fan[b["name"]]
                if nr + nl < T:                          # fan out: the right turners take the outer lanes,
                    if which == "r" and nr:              # the left turners the inner ones
                        pairs += [(len(srcs) - 1, j) for j in range(len(srcs), T - nl)]
                    elif which == "l" and not nr:
                        pairs += [(len(srcs) - 1, j) for j in range(len(srcs), T)]
            for k, j in pairs:
                p = srcs[k][0]
                q, _g = tg[min(j, len(tg) - 1)]
                lane = fillet(p, h, q, g)                # merges too: tangent onto the real lane, no kink
                out.append(BL.Lane(lane, "t" + a["name"][0] + which))
                used.add((a["name"], k if which == "r" else n - 1 - k))
    # an in lane with no move left (no straight on past a stem, its only left a dropped 135 degree one) turns right
    # too, onto the right arm's outer lane
    goes_on = {b["straight"] for b in arms if b.get("straight")}
    for a in arms:
        if not a["in"] or a["name"] in goes_on:
            continue
        h = a["in"][0][1]
        rights = [b for b in arms if b is not a and b["out"] and h[0] * b["out"][0][1][1] - h[1] * b["out"][0][1][0] < -0.2]
        if not rights:
            continue
        b = rights[0]
        for i, (p, _h) in enumerate(a["in"]):
            if (a["name"], i) not in used:
                q, g = b["out"][0]
                out.append(BL.Lane(fillet(p, h, q, g), "t" + a["name"][0] + "r"))
    return out


# ------------------------------------------------------------------------------------------------ the ends
def _half(t0, w):
    """lane p's of a north-type half (frame at T t0, extra lane width w): outer, middle, inner (T / 256)"""
    return [(t0 + 80.0) / 256.0, (t0 + 175.0) / 256.0, (t0 + 175.0 + 95.0 * w / 104.0) / 256.0]


def _band_p(side, k):
    return OFF[k] if side == "A" else 3.0 - OFF[k]


def end_lanes(kind, wz_from):
    """the lanes of one end in its bottom frame (band rows z <= 0, a = z; the end past row 0), starting at the band
    point where wz = wz_from (< 0). -> [Lane]"""
    from netmod import diagbv as DB
    from netmod import diagbv_paint as P
    from netmod import boulevard_paint as BP
    out = []
    q_far = 20.0

    def qa(p):                                      # the q where a lane at p crosses wz = wz_from
        return 2.0 * wz_from + p

    if kind in ("narrow-C", "narrow-A"):
        sc = DB.ENDS[kind][2](P)
        av = BP.AvenueNarrow((0, 1) if kind == "narrow-C" else (1, 2))

        def ps(q):
            t = sc.t(q)
            t0n, wn, t0s, ws, mid = av.params(t)
            return _half(t0n, wn), [3.0 - v for v in _half(512.0 - t0s, ws)]
        for k in range(3):
            out.append(BL.Lane(line_q(lambda q, k=k: ps(q)[0][k], qa(OFF[k]), q_far, -1), "A"))
            out.append(BL.Lane(line_q(lambda q, k=k: ps(q)[1][k], qa(3 - OFF[k]), q_far, 1), "C"))
        return out
    if kind.startswith("taper"):
        sc = DB.ENDS[kind][2](P)
        keep = sc.keep
        road = {"A": keep + 80 / 256.0, "C": keep + 175 / 256.0}
        g = 95 / 256.0
        K = DB.ENDS[kind][1]                           # claimed rows: the merge must be done before the stock road
        q0, q1 = sc.q_nose, min(sc.q_close, 2.0 * K + 2.0 + keep - 0.4)

        def tt(q):
            return clamp((q - q0) / max(1e-6, q1 - q0), 0.0, 1.0)
        for side, sign, outward in (("A", -1, -1.0), ("C", 1, 1.0)):
            inner0 = _band_p(side, 2)
            g1 = lambda q: g * (1 - smooth(tt(q)))                        # noqa: E731
            g0 = lambda q: g1(q) + g * (1 - smooth(2 * tt(q)))            # noqa: E731
            for rank, off in ((0, g0), (1, g1), (2, lambda q: 0.0)):
                def pf(q, off=off, side=side, inner0=inner0, outward=outward):
                    base = inner0 + (road[side] - inner0) * smooth(tt(q))
                    v = base + outward * off(q)
                    return clamp(v, sc.lo(q) + 80 / 256.0, sc.hi(q) - 80 / 256.0)
                out.append(BL.Lane(_smooth_line(line_q(pf, qa(_band_p(side, rank)), q_far, sign)), side))
        return out
    if kind.startswith("cap"):
        sc = DB.ENDS[kind][2](P)
        return _cap_lanes(sc, wz_from)
    if kind == "bend-x":                            # the straight boulevard along +x from x 1 (rows -2..0)
        for k in range(3):
            for side, sign in (("A", -1), ("C", 1)):
                p = _band_p(side, k)
                zj = 1.0 - p
                pts = BL.join(BL.seg((wz_from + p, wz_from), (1.0, zj)), BL.seg((1.0, zj), (q_far, zj)))
                out.append(BL.Lane(pts if sign > 0 else pts[::-1], side))
        return out
    if kind == "bend-z":                            # the straight boulevard along +z from z 1 (columns 1..3)
        for k in range(3):
            for side, sign in (("A", -1), ("C", 1)):
                p = _band_p(side, k)
                xj = 1.0 + p
                pts = BL.join(BL.seg((wz_from + p, wz_from), (xj, 1.0)), BL.seg((xj, 1.0), (xj, q_far)))
                out.append(BL.Lane(pts if sign > 0 else pts[::-1], side))
        return out
    if kind == "stem":                              # the band ends on a row road at row 0: lanes stop at its edge
        for k in range(3):
            for side, sign in (("A", -1), ("C", 1)):
                p = _band_p(side, k)
                pts = BL.seg((wz_from + p, wz_from), (p, 0.0))
                out.append(BL.Lane(pts if sign > 0 else pts[::-1], side))
        return out
    raise ValueError("end kind %s" % kind)


def _left_radius(pts, min_chord=80.0 / 255.0):
    """smallest LEFT bend radius (cells) of a world polyline as driven, as avlanes.curve_left_radius (screen +z up:
    world (x, z) left = counter-clockwise in x / z)"""
    best = None
    n = len(pts)
    stride = max(1, n // 40)
    xs = pts[::stride]
    for i in range(len(xs)):
        for j in range(i + 2, len(xs)):
            (x1, z1), (x3, z3) = xs[i], xs[j]
            if math.hypot(x3 - x1, z3 - z1) < min_chord:
                continue
            x2, z2 = xs[(i + j) // 2]
            cross = (x2 - x1) * (z3 - z2) - (z2 - z1) * (x3 - x2)
            if cross <= 0:
                continue
            A, B, C = math.hypot(x2 - x1, z2 - z1), math.hypot(x3 - x2, z3 - z2), math.hypot(x3 - x1, z3 - z1)
            r = A * B * C / (2.0 * abs(cross))
            best = r if best is None else min(best, r)
            break
    return best


R_MIN = 100.0 / 255.0                                # cells: no left bend tighter (AVENUE_LANES.md 6, rule <= 80)


CAP_DEPTH = (0.62, 0.50, 0.38)                       # cells along +q of the outer / middle / inner U-turn


def _cap_lanes(sc, wz_from):
    """U-turns round the median nose, outer to outer, middle to middle, inner to inner: three concentric half
    ellipses square to the band (across: half the true distance between the two lanes, 0.84 / 0.58 / 0.31 cells;
    along +q: CAP_DEPTH), centred on the median line and pushed as far along +q as the closure lets the outer one stay
    on the pavement (Cap.dist >= 0.06). The inner U is tight (the lanes are 0.63 cells apart across the diagonal):
    allowed since the radius rule was lifted (the 2026-10-20 hang was a Frida test trap)."""
    up = (1 / S2, -1 / S2)                               # world direction of increasing p
    uq = (1 / S2, 1 / S2)                                # increasing q
    pm = 1.5

    def lane_pts(k, qc):
        pc, pa = 3.0 - OFF[k], OFF[k]
        R = (pc - pa) / 2.0 / S2
        a = CAP_DEPTH[k]                                 # half ellipses, shallower than circles (a < R): the
        C = _w(qc, pm)                                   # tightest bend is a^2 / R at the sides (117 / 110 units)
        u = [(C[0] + R * math.cos(t) * up[0] + a * math.sin(t) * uq[0], C[1] + R * math.cos(t) * up[1] + a * math.sin(t) * uq[1])
             for t in [math.pi * i / 96 for i in range(97)]]
        cin = BL.seg((wz_from + pc, wz_from), u[0])
        aout = BL.seg(u[-1], (wz_from + pa, wz_from))
        return cin, u, aout
    q_hi = 2.0 * sc.wz0 + 10.0                           # past any closure; walk back to the first centre that
    qc = q_hi                                            # keeps the outer U paved (independent of the band length)
    for i in range(800):
        qc = q_hi - 0.025 * i
        cin, u, aout = lane_pts(0, qc)
        if min(sc.dist(x, z) for (x, z) in u) >= 0.06:
            break
    out = []
    for k in (0, 1, 2):                                  # outer to outer, middle to middle, inner to inner
        cin, u, aout = lane_pts(k, qc)
        out.append(BL.Lane(BL.join(cin, u, aout), "C"))
    return out


def place(lanes, axis_e, a_e, z_e):
    """end frame -> canonical band frame (bottom: shift; top: the half turn)"""
    out = []
    for ln in lanes:
        if axis_e == 1:
            pts = [(x + a_e, z + z_e) for (x, z) in ln.pts]
        else:
            pts = [(a_e + 4 - x, z_e + 1 - z) for (x, z) in ln.pts]
        out.append(BL.Lane(pts, ln.kind))
    return out


# ------------------------------------------------------------------------------------------------ junctions
def road_lanes_x(z, x0, x1, both=True, side=None):
    """a row road along x on row z: +x at z + 80/255, -x at z + 175/255 (stock 29)"""
    return [BL.Lane(BL.seg((x0, z + 80 / 255.0), (x1, z + 80 / 255.0)), "r"),
            BL.Lane(BL.seg((x1, z + 175 / 255.0), (x0, z + 175 / 255.0)), "r")]


def road_lanes_z(x, z0, z1):
    """a column road along z on column x: +z at x + 175/255, -z at x + 80/255 (stock 29 state 1)"""
    return [BL.Lane(BL.seg((x + 175 / 255.0, z0), (x + 175 / 255.0, z1)), "r"),
            BL.Lane(BL.seg((x + 80 / 255.0, z1), (x + 80 / 255.0, z0)), "r")]


def junction_lanes(kind, ref, turned, P0):
    """road lanes + turns of a junction use (diagbv uses: kind, canonical ref cell, turned) on a band whose strip A
    starts at p = P0"""
    from netmod import diagbv as DB
    fam = DB.JUNCTIONS[kind][0]
    x0, z0 = ref
    pa = [P0 + v for v in OFF]                         # A lanes outer -> inner
    pc = [P0 + 3.0 - v for v in OFF]                   # C lanes outer -> inner
    lanes = []
    if fam == "row":
        z = z0
        W = kind in ("jrow-both", "jrow-stem") or (kind == "jrow-A" and not turned)
        E = kind in ("jrow-both", "jrow-stem") or (kind == "jrow-A" and turned)
        bottom = kind != "jrow-stem" or turned        # stem-after: no band past the road (+q) unless turned
        top = kind != "jrow-stem" or not turned
        zp, zm = z + 80 / 255.0, z + 175 / 255.0
        xl = xl2 = float(x0)                           # the road meets the junction row's cells at their edges
        xr = xr2 = float(x0 + 4)
        if W and E:
            lanes += road_lanes_x(z, xl - 8, xr + 8)
        else:
            if W:
                lanes += [BL.Lane(BL.seg((xl - 8, zp), (xl, zp)), "r"), BL.Lane(BL.seg((xl2, zm), (xl2 - 8, zm)), "r")]
            if E:
                lanes += [BL.Lane(BL.seg((xr2 + 8, zm), (xr2, zm)), "r"), BL.Lane(BL.seg((xr, zp), (xr + 8, zp)), "r")]
        arms = []
        if top:
            arms.append({"name": "top", "in": [((p + z, z), QC) for p in pc], "out": [((p + z, z), QH) for p in pa],
                         "straight": "bottom" if bottom else None})
        if bottom:
            arms.append({"name": "bottom", "in": [((p + z + 1, z + 1), QH) for p in pa],
                         "out": [((p + z + 1, z + 1), QC) for p in pc], "straight": "top" if top else None})
        if W:
            arms.append({"name": "W", "in": [((xl, zp), (1, 0))], "out": [((xl2, zm), (-1, 0))],
                         "straight": "E" if E else None})
        if E:
            arms.append({"name": "E", "in": [((xr2, zm), (-1, 0))], "out": [((xr, zp), (1, 0))],
                         "straight": "W" if W else None})

        def inside(pt):
            return z < pt[1] < z + 1 and P0 < pt[0] - pt[1] < P0 + 3
    else:
        x = x0
        N = kind == "jcol-both" or (kind == "jcol-A" and turned)
        S = kind == "jcol-both" or (kind == "jcol-A" and not turned)
        xp, xm = x + 175 / 255.0, x + 80 / 255.0       # +z / -z lanes
        zN_p = zN_m = float(z0 - 3)                    # the column's junction cells: rows z0 - 3 .. z0
        zS_p = zS_m = float(z0 + 1)
        if N and S:
            lanes += road_lanes_z(x, zN_p - 8, zS_p + 8)
        else:
            if N:
                lanes += [BL.Lane(BL.seg((xp, zN_p - 8), (xp, zN_p)), "r"), BL.Lane(BL.seg((xm, zN_m), (xm, zN_m - 8)), "r")]
            if S:
                lanes += [BL.Lane(BL.seg((xm, zS_m + 8), (xm, zS_m)), "r"), BL.Lane(BL.seg((xp, zS_p), (xp, zS_p + 8)), "r")]
        arms = [{"name": "top", "in": [((x, x - p), QC) for p in pc], "out": [((x, x - p), QH) for p in pa],
                 "straight": "bottom"},
                {"name": "bottom", "in": [((x + 1, x + 1 - p), QH) for p in pa],
                 "out": [((x + 1, x + 1 - p), QC) for p in pc], "straight": "top"}]
        if N:
            arms.append({"name": "N", "in": [((xp, zN_p), (0, 1))], "out": [((xm, zN_m), (0, -1))],
                         "straight": "S" if S else None})
        if S:
            arms.append({"name": "S", "in": [((xm, zS_m), (0, -1))], "out": [((xp, zS_p), (0, 1))],
                         "straight": "N" if N else None})

        def inside(pt):
            return x < pt[0] < x + 1 and P0 < pt[0] - pt[1] < P0 + 3
    return lanes + junction_turns(arms, inside)


# ------------------------------------------------------------------------------------------------ a band
def band_lanes(b):
    """every lane of one accepted band (diagbv.bands entry) in its canonical frame"""
    rows = b["rows"]                                  # [(z, a)]
    P0 = rows[0][1] - rows[0][0]
    mid = rows[len(rows) // 2][0]
    lanes = []
    for e in (1, 0):
        z_e, a_e = rows[-1] if e else rows[0]
        kind = b["ends"][e]
        if e:
            wz_from = mid - z_e
        else:
            wz_from = -(mid - z_e) + 1                 # the turned frame: wz' = z_e + 1 - wz
        lanes += place(end_lanes(kind, wz_from), e, a_e, z_e)
    from netmod import diagbv as DB
    for kind, ref, turned in b["uses"]:
        if kind in DB.JUNCTIONS:                       # (uses also list the ends' stamps)
            lanes += junction_lanes(kind, ref, turned, P0)
    return lanes


def avoid_corners(pts, near=6.0 / 255.0, push=8.0 / 255.0):
    """a lane may not pass through a cell corner (a car leaves a cell across one of its four sides only): points
    closer than `near` to a corner move `push` cells to the driver's left, faded over the neighbouring points (the
    same move however the scene is turned)"""
    pts = list(pts)
    n = len(pts)
    bump = [0.0] * n
    for i, (x, z) in enumerate(pts):
        d = math.hypot(x - round(x), z - round(z))
        if d < near:
            for j in range(max(0, i - 4), min(n, i + 5)):
                bump[j] = max(bump[j], push * (1 - abs(j - i) / 5.0))
    if not any(bump):
        return pts
    out = []
    for i, (x, z) in enumerate(pts):
        a, b = pts[max(0, i - 1)], pts[min(n - 1, i + 1)]
        h = _unit((b[0] - a[0], b[1] - a[1])) if (a != b) else (1.0, 0.0)
        out.append((x - h[1] * bump[i], z + h[0] * bump[i]))
    return out


def to_real_pts(axis, pts):
    """canonical -> real: diagbv.rot1 maps cell (x, z) -> (-z - 1, x); a point (x, z) -> (-z, x)"""
    if not axis:
        return pts
    return [(-z, x) for (x, z) in pts]


def _ctx(b, stamps):
    """real cell -> (kind, dx, dz, stamp state) of the stamp entry that writes it, for every use of band b; band cells
    -> ("band", ...) with the nearest use (a lane change of that use reaching into them)"""
    from netmod import diagbv as DB
    out, refs = {}, []
    for kind, ref, turned in b["uses"]:
        fam = DB.JUNCTIONS[kind][0] if kind in DB.JUNCTIONS else "row"
        refs.append((kind, ref, turned, fam))
        for (dx, dz, pc, st) in stamps.get(kind, []):
            ddx, ddz = DB.turn_rel(fam, dx, dz) if turned else (dx, dz)
            c = DB.to_real(b["axis"], (ref[0] + ddx, ref[1] + ddz))
            out[c] = (kind, dx, dz, st)
    return out, refs


def _band_ctx(b, refs, c, st_real):
    """a band cell's position relative to its nearest use, as a new stamp entry (kind, dx, dz, stamp state)"""
    from netmod import diagbv as DB
    cc = DB.to_canon(b["axis"], c)
    best = None
    for kind, ref, turned, fam in refs:
        d = max(abs(cc[0] - ref[0]), abs(cc[1] - ref[1]))
        if best is None or d < best[0]:
            best = (d, kind, ref, turned, fam)
    _d, kind, ref, turned, fam = best
    dx, dz = cc[0] - ref[0], cc[1] - ref[1]
    if turned:                                         # turn_rel is its own inverse
        dx, dz = DB.turn_rel(fam, dx, dz)
    st = (st_real - b["axis"] - (2 if turned else 0)) % 4
    return (kind, dx, dz, st)


def placements_dbv(stamps=None, with_ctx=False):
    """[(case, real cell, piece, state, [cuts])] over every accepted band of diagbv.check_cases()"""
    from netmod import diagbv as DB
    stamps = stamps or DB.load_stamps(DB.PACK)
    out = []
    cases = [(n, r) for (n, r, ok, _d, _e) in DB.check_cases() if ok]
    for kind in DB.ENDS:                               # every end shape on its own (some no drag case makes)
        F = DB.end_footprint(kind) | DB._band_rows(-12, 0)
        T = {(2 - x, -1 - z) for (x, z) in F}           # the same end at the top
        for nm, R in (("end " + kind, F), ("end " + kind + " (top)", T)):
            cases.append((nm, R))
            cases.append((nm + " axis 1", {DB.rot1(c) for c in R}))
    for name, road in cases:
        for b in DB.bands(road, stamps):
            if not b["ok"]:
                continue
            lanes = [BL.Lane(avoid_corners(to_real_pts(b["axis"], ln.pts)), ln.kind) for ln in band_lanes(b)]
            ctx, refs = _ctx(b, stamps) if with_ctx else ({}, [])
            for c, (pid, st) in b["want"].items():
                if pid in (29, 35):
                    continue
                cuts = []
                for ln in lanes:
                    for lu in BL.clip_cell(ln.pts, *c):
                        cuts.append({"pts": lu, "a": BL.side_of_pt(lu[0]), "b": BL.side_of_pt(lu[-1]), "kind": ln.kind})
                if with_ctx:
                    cx = ctx.get(c) or (("band",) + _band_ctx(b, refs, c, st))
                    out.append((name, c, pid, st, cuts, cx))
                else:
                    out.append((name, c, pid, st, cuts))
    return out


SPLIT0, SPLIT1 = 21900, 21949
SPLIT_IDS = list(range(21900, 21950)) + list(range(20933, 20950)) + [20709] + list(range(20713, 20720))   # + free BVX / BV


def local_set(cuts, st):
    loc = []
    for ct in cuts:
        if len(ct["a"]) == 1 and len(ct["b"]) == 1:
            loc.append(tuple(tuple(v) for v in BL._int_cut([BL.to_local(p, st) for p in ct["pts"]])))
    return set(loc)


def cmd_rebuild(a):
    """give every extra lane set of a DBV piece its own id (21900..21949) in the package's stamps; the art of a new id
    is a copy of the piece it splits from. Repeats until every id has one lane set."""
    import json
    import shutil
    from netmod import diagbv as DB
    pack = a.pack
    man = json.load(open(os.path.join(pack, "manifest.json")))
    A = man["auto_diagonal_boulevards"][0]
    var = {v["id"]: v for v in man["variants"]}
    free = [v for v in SPLIT_IDS if v not in var]
    for rnd in range(6):
        stamps = {k: [tuple(c) for c in v] for k, v in A["stamps"].items()}
        stamps["band"] = tuple(A["band"])
        sets = defaultdict(list)                       # pid -> [(set, [ctx...])]
        for name, c, pid, st, cuts, cx in placements_dbv(stamps, with_ctx=True):
            loc = local_set(cuts, st)
            for s0, ctxs in sets[pid]:
                if BL.same_set(s0, loc):
                    ctxs.append(cx)
                    break
            else:
                sets[pid].append((loc, [cx]))
        todo = {pid: v for pid, v in sets.items() if len(v) > 1}
        print("round %d: %d piece(s) with more than one lane set" % (rnd, len(todo)))
        if not todo:
            break
        for pid, groups in sorted(todo.items()):
            for loc, ctxs in groups[1:]:
                if not free:
                    raise SystemExit("out of DBV split ids")
                new = free.pop(0)
                v = json.loads(json.dumps(var[pid]))
                v["id"] = new
                v["art"]["png_dir"] = "art/%d" % new
                src, dst = os.path.join(pack, "art", str(pid)), os.path.join(pack, "art", str(new))
                if os.path.isdir(src) and not os.path.isdir(dst):
                    shutil.copytree(src, dst)
                var[new] = v
                for cx in {tuple(x) for x in ctxs}:
                    if cx[0] == "band":
                        kind, dx, dz, st = cx[1:]
                        A["stamps"][kind] = [e for e in A["stamps"][kind] if (e[0], e[1]) != (dx, dz)] + \
                            [[dx, dz, new, st]]
                    else:
                        kind, dx, dz, st = cx
                        A["stamps"][kind] = [[e[0], e[1], new, e[3]] if (e[0], e[1]) == (dx, dz) else e
                                             for e in A["stamps"][kind]]
                print("  %d -> new %d (%d placement(s), %s)" % (pid, new, len(ctxs), sorted({x[0] if x[0] != "band"
                      else "band near " + x[1] for x in ctxs})))
    man["variants"] = [var[k] for k in sorted(var)]
    json.dump(man, open(os.path.join(pack, "manifest.json"), "w", newline="\n"), indent=1)
    print("manifest: %d variants" % len(man["variants"]))


def cmd_check(a):
    seen = {}
    sets = defaultdict(list)
    bad_end = 0
    for name, c, pid, st, cuts in placements_dbv():
        loc = []
        for ct in cuts:
            if len(ct["a"]) != 1 or len(ct["b"]) != 1:
                bad_end += 1
                if bad_end <= 10:
                    print("inside end:", name, c, pid, [round(v) for v in ct["pts"][0]], [round(v) for v in ct["pts"][-1]])
                continue
            loc.append(tuple(tuple(v) for v in BL._int_cut([BL.to_local(p, st) for p in ct["pts"]])))
        loc = set(loc)
        for i, (s0, where) in enumerate(sets[pid]):
            if BL.same_set(s0, loc):
                where.append((name, c, st))
                break
        else:
            sets[pid].append((loc, [(name, c, st)]))
    extra = 0
    for pid in sorted(sets):
        n = len(sets[pid])
        extra += n - 1
        tag = "" if n == 1 else "   <-- %d lane sets" % n
        print("%d: %d placement(s)%s" % (pid, sum(len(w) for _, w in sets[pid]), tag))
        if n > 1 or a.verbose:
            for s0, where in sets[pid]:
                print("    %d lanes, e.g. %s %s state %d (%d placements)" % (len(s0), where[0][0], where[0][1],
                                                                          where[0][2], len(where)))
    print("pieces %d, extra ids needed %d, lanes ending inside a cell %d" % (len(sets), extra, bad_end))


def cmd_manifest(a):
    """the package's lanes: every variant with a bvl_<id>.lanes.json (bvlanes.py build) carries it (trblkatt none)"""
    import json
    pack = a.pack
    man = json.load(open(os.path.join(pack, "manifest.json")))
    lanes = []
    for v in man["variants"]:
        f = "bvl_%d.lanes.json" % v["id"]
        if os.path.isfile(os.path.join(pack, f)):
            v["trblkatt"] = "none"
            lanes.append({"piece": v["id"], "spec": f})
    man["lanes"] = lanes
    man["version"] = "0.2.0"
    if "task bvlanes" not in man["description"]:
        man["description"] += (" Traffic (task bvlanes): 3 lanes each way, right-hand, one way per side, every turn at "
                               "the junctions; own lane specs (bvl_*.lanes.json, dbvlanes.py / bvlanes.py).")
    json.dump(man, open(os.path.join(pack, "manifest.json"), "w", newline="\n"), indent=1)
    print("manifest: %d variants, %d lane specs" % (len(man["variants"]), len(lanes)))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("check")
    s.add_argument("-v", "--verbose", action="store_true")
    s = sub.add_parser("rebuild")
    s.add_argument("pack")
    s = sub.add_parser("manifest")
    s.add_argument("pack")
    a = ap.parse_args(argv)
    return {"check": cmd_check, "rebuild": cmd_rebuild, "manifest": cmd_manifest}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
