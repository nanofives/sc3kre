#!/usr/bin/env python3
r"""hwdx_plan.py - milestone-1 plans of the hwdx stream (diagonal highway x straight highway, 45 degrees), 2026-10-18.

Geometry only (no art): the footprint, which highway bridges, every ramp as a centreline, the cells each one touches,
and the piece count. Writes the owner's top-down plan pictures.

  py -3.12 hwdx_plan.py cells [--plan clover|direct]        cell classes and piece counts (both diagonal families)
  py -3.12 hwdx_plan.py png OUT.png [--plan clover|direct]  the plan sheet (with the other plan's numbers beside)

Plans:
  clover  skewed cloverleaf: four loops (left turns), four outer ramps (right turns), one bridge (the crossing)
  direct  the acute quadrants as in clover; in the obtuse quadrants the 45-degree left turns are direct flyovers and
          the 45-degree right turns hug the corner

Canonical frame (case A, measured in game, STATUS_hwdx.md): O = the cell corner where the two medians cross; cell
(i, j) covers [i, i+1] x [j, j+1] (game cell = (58 + i, 28 + j) in the lab). Straight S: row j = -1 runs +x (15051.2),
row j = 0 runs -x (15051.0). Diagonal D (x-z family): band cells with i - j in {-1, 0, 1}; the +x+z carriageway is the
half x - z in (0, 1), the -x-z one x - z in (-1, 0). Right-hand traffic: right(d) = (dz, -dx); a right turn lowers the
heading angle atan2(dz, dx).
Case B (x+z family) = case A mirrored z -> -z with every direction reversed (still right-hand); a straight along z is
case A or B turned 90 degrees (game states), so A and B cover the four drags.

Ramp geometry follows stream hwx (re/tools/netmod/hwx.py in its worktree, program decision 2026-10-18): deck 0.62
(W 0.31), ramp lines 0.25 outside a carriageway edge, loop radius 1.25, 0.19 of ground between neighbouring decks,
turn arcs 0.75, S tapers 0.62 into the outer lane (0.57 of the carriageway width from the median), every taper
outside the cells where a deck changes height. D's edge is the stock band's (hwpaint W_DIAG 0.63 off the median).
"""
import math
import sys

R2 = math.sqrt(2.0)
S22 = math.sin(math.radians(22.5))
C22 = math.cos(math.radians(22.5))


def right(h):
    r = math.radians(h)
    return (math.sin(r), -math.cos(r))


def left(h):
    r = math.radians(h)
    return (-math.sin(r), math.cos(r))


class Turtle:
    """A ramp centreline: straight lines, circular arcs and cubic S tapers. `up()` / `down()` mark the stretch that
    flies over a carriageway (a one-lane bridge above the 1024 decks)."""

    def __init__(self, x, z, h=0.0):
        self.x, self.z, self.h = x, z, h
        self.segs = []
        self.elev = False

    def up(self):
        self.elev = True
        return self

    def down(self):
        self.elev = False
        return self

    def to(self, x, z):                       # straight line to a point (sets the heading)
        self.segs.append(("line", (self.x, self.z), (x, z), self.elev))
        self.h = math.degrees(math.atan2(z - self.z, x - self.x))
        self.x, self.z = x, z
        return self

    def fwd(self, d):
        r = math.radians(self.h)
        h = self.h
        self.to(self.x + d * math.cos(r), self.z + d * math.sin(r))
        self.h = h
        return self

    def arc(self, rad, dh):                   # dh < 0 = right turn
        n = right(self.h) if dh < 0 else left(self.h)
        cx, cz = self.x + rad * n[0], self.z + rad * n[1]
        a0 = math.degrees(math.atan2(self.z - cz, self.x - cx))
        self.segs.append(("arc", (cx, cz), rad, a0, dh, self.elev))
        a1 = math.radians(a0 + dh)
        self.x, self.z = cx + rad * math.cos(a1), cz + rad * math.sin(a1)
        self.h += dh
        return self

    def taper(self, x, z):
        """S taper to (x, z), keeping the heading (between two parallel lines)."""
        r = math.radians(self.h)
        ux, uz = math.cos(r), math.sin(r)
        along = (x - self.x) * ux + (z - self.z) * uz
        p0, p3 = (self.x, self.z), (x, z)
        p1 = (p0[0] + ux * along / 2, p0[1] + uz * along / 2)
        p2 = (p3[0] - ux * along / 2, p3[1] - uz * along / 2)
        self.segs.append(("bez", p0, p1, p2, p3, self.elev))
        self.x, self.z = x, z
        return self

    def samples(self, step=0.04):
        """[(x, z, heading, elevated)]"""
        out = []
        for s in self.segs:
            if s[0] == "line":
                (x0, z0), (x1, z1) = s[1], s[2]
                n = max(2, int(math.hypot(x1 - x0, z1 - z0) / step))
                h = math.degrees(math.atan2(z1 - z0, x1 - x0))
                out += [(x0 + (x1 - x0) * k / n, z0 + (z1 - z0) * k / n, h, s[3]) for k in range(n + 1)]
            elif s[0] == "arc":
                (cx, cz), rad, a0, dh = s[1], s[2], s[3], s[4]
                n = max(2, int(abs(math.radians(dh)) * rad / step))
                for k in range(n + 1):
                    a = math.radians(a0 + dh * k / n)
                    out.append((cx + rad * math.cos(a), cz + rad * math.sin(a),
                                math.degrees(a) + (90 if dh > 0 else -90), s[5]))
            else:
                p0, p1, p2, p3 = s[1], s[2], s[3], s[4]
                L = math.hypot(p3[0] - p0[0], p3[1] - p0[1])
                n = max(4, int(L / step) * 2)
                for k in range(n + 1):
                    t = k / n
                    a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
                    x = a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0]
                    z = a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]
                    da, db, dc = 3 * (1 - t) ** 2, 6 * t * (1 - t), 3 * t * t
                    dx = da * (p1[0] - p0[0]) + db * (p2[0] - p1[0]) + dc * (p3[0] - p2[0])
                    dz = da * (p1[1] - p0[1]) + db * (p2[1] - p1[1]) + dc * (p3[1] - p2[1])
                    out.append((x, z, math.degrees(math.atan2(dz, dx)), s[5]))
        return out


def xform(pts, f):
    """Samples through a map f in {rot180, mirror_rev}."""
    if f == "rot180":
        return [(-x, -z, h + 180, e) for x, z, h, e in pts]
    if f == "mirror_rev":                     # z -> -z, direction reversed (case B)
        return [(x, -z, (-h) + 180, e) for x, z, h, e in reversed(pts)]
    return pts


# ------------------------------------------------------------------------------------------------ the design
W = 0.31              # half width of a one-lane ramp deck: 0.62 = the stock ramp (program decision 2026-10-18, hwx)
LINE = 0.25           # ramp line beyond a carriageway edge (hwx: loops tangent 0.25 outside)
GAP = 0.19            # ground between neighbouring decks (hwx)
R_LOOP = 1.25         # loop radius (hwx: a 3x3 block)
RHO = 0.75            # small turning arcs of the outer ramps (hwx at the 0.62 deck)
TAPER = 0.62          # S taper length (hwx)
LANE_OUT = 0.57       # a carriageway's outer lane, from the median (hwx)
OFFS = 2 * W + GAP    # centreline spacing of two neighbouring ramps (0.63)

S_LINE = 1.0 + LINE                   # ramp line beside S: z = +-1.25
D_EDGE = 0.63                         # D carriageway width across = its edge off the median (hwpaint W_DIAG, stock band)
D_LINE = (D_EDGE + LINE) * R2         # ramp line beside D: x - z = +-1.245
S_OUT = LANE_OUT                      # S outer lane: z = +-0.57
D_OUT = LANE_OUT * D_EDGE * R2        # D outer lane: x - z = +-0.508 (the same fraction of its width as S's)
S_FREE_W = -2.0                       # row 0: tapers stay west of the S arm cell (-2, 0) ...
S_FREE_E = 3.0                        # ... and east of (2, 0)
D_FREE = 2.0                          # D: tapers stay off the dip arm row j = 1


def _diag_pt(k, z):
    """the point of the line x - z = k at height z"""
    return (z + k, z)


def _to_d_out(x, z, side):
    """(x, z) on the D ramp line on `side` (+1 / -1) moved across onto that carriageway's outer lane"""
    sh = (D_LINE - D_OUT) / 2
    return (x - side * sh, z + side * sh)


def acute_A1():
    """Quadrant A1 (between the +x arm and the +d arm, 45 degrees): loop L6 at the corner, R4 around it."""
    corner = (D_LINE + S_LINE, S_LINE)                         # where the two ramp lines meet
    d = R_LOOP / S22
    C = (corner[0] + d * C22, corner[1] + d * S22)             # loop centre, tangent to both lines
    t1 = (C[0] - R_LOOP / R2, C[1] + R_LOOP / R2)              # tangent point on the D line
    t2 = (C[0], S_LINE)                                        # tangent point on the S line
    out = {}
    # L6: +d-bound (leaving O) -> 225 degrees right -> -x-bound (towards O)
    a = _to_d_out(t1[0] - TAPER / R2, t1[1] - TAPER / R2, 1)
    s = Turtle(a[0], a[1], 45)
    s.taper(*t1).arc(R_LOOP, -225).taper(t2[0] - TAPER, S_OUT)
    out["L6"] = s
    # R4: -x-bound (towards O) -> right 90 -> round the loop (left) -> right -> +d-bound (leaving O)
    ro = R_LOOP + OFFS
    xs = C[0] + ro + RHO                                       # where R4 leaves the S line

    def build(th, s):
        s.arc(RHO, -90)
        if C[1] > s.z:
            s.fwd(C[1] - s.z)
        return s.arc(ro, th).arc(RHO, -(th + 45))

    best = min((abs((lambda t: (t.x - t.z) - D_LINE)(build(k * 0.05, Turtle(xs, S_LINE, 180)))), k * 0.05)
               for k in range(1, 3000))
    th = best[1]
    s = Turtle(xs + TAPER, S_OUT, 180)
    s.taper(xs, S_LINE)
    build(th, s)
    s.taper(*_to_d_out(s.x + TAPER / R2, s.z + TAPER / R2, 1))
    out["R4"] = s
    return out


def obtuse_O1_clover():
    """Quadrant O1 (between the +d arm and the -x arm, 135 degrees), cloverleaf: loop L3 (315 degrees: right 180,
    straight, right 135) and the outer ramp R7 one spacing outside it (right 45, straight, left 90, right 90)."""
    out = {}
    A = (S_FREE_W - TAPER, S_LINE)
    bz = D_FREE + TAPER / R2 + (D_LINE - D_OUT) / 2 + 0.05     # where L3 lands on the D line (taper ends in row 2)
    B = _diag_pt(-D_LINE, bz)
    C2 = (B[0] - R_LOOP / R2, B[1] + R_LOOP / R2)
    top = C2[1] + R_LOOP
    r1 = (top - S_LINE) / 2
    C1 = (A[0], S_LINE + r1)
    s = Turtle(S_FREE_W, S_OUT, 180)
    s.taper(*A).arc(r1, -180).fwd(C2[0] - A[0]).arc(R_LOOP, -135)
    s.taper(*_to_d_out(s.x - TAPER / R2, s.z - TAPER / R2, -1))
    out["L3"] = s
    # R7
    ztop = top + OFFS
    ro1 = r1 + OFFS
    cz = ztop + RHO                                            # first right arc (heading 225 -> 180), centre
    cx = cz - D_LINE - RHO * R2                                # its start (centre + RHO (1, -1)/sqrt2) is on the D line
    st = (cx + RHO / R2, cz - RHO / R2)
    a = _to_d_out(st[0] + TAPER / R2, st[1] + TAPER / R2, -1)
    s = Turtle(a[0], a[1], 225)
    s.taper(*st).arc(RHO, -45).fwd(cx - C1[0]).arc(ro1, 90)
    s.fwd(C1[1] - (S_LINE + RHO))
    s.arc(RHO, -90).taper(s.x - TAPER, S_OUT)
    out["R7"] = s
    return out


def obtuse_O1_direct():
    """Quadrant O1, direct: R7 hugs the corner (right 45 on the ramp lines); L1 (-x -> +d, left 45) leaves the -x
    arm's +x-bound carriageway outside quadrant A2's ramps, flies over S, runs up the quadrant, flies over D past
    quadrant A1's ramps and joins the +d-bound carriageway from its outer side."""
    out = {}
    corner = (S_LINE - D_LINE, S_LINE)
    tdist = RHO * math.tan(math.radians(22.5))
    p = (corner[0] + tdist / R2, corner[1] + tdist / R2)       # fillet start on the D line
    st = _diag_pt(-D_LINE, D_FREE + TAPER / R2 + 0.12)
    a = _to_d_out(st[0] + TAPER / R2, st[1] + TAPER / R2, -1)
    s = Turtle(a[0], a[1], 225)
    s.taper(*st).to(*p).arc(RHO, -45).to(S_FREE_W - TAPER, S_LINE)
    s.h = 180
    s.taper(S_FREE_W - 2 * TAPER, S_OUT)
    out["R7"] = s
    # L1: starts on the +x-bound carriageway (row -1) west of quadrant A2's ramps (A2 = A1 turned 180 degrees)
    x_r2 = -acute_A1()["R4"].segs[0][1][0]                     # R2 leaves the +x-bound carriageway here
    x0 = x_r2 - 2.4                                           # L1 is over S before R2's taper starts
    s = Turtle(x0 - TAPER, -S_OUT, 0)
    s.taper(x0, -S_LINE).up().arc(R_LOOP, 45)                  # climb, turn towards S
    s.fwd(4.2)                                                 # over S (two rows), into O1
    zc = 7.4                                                   # crosses D above quadrant A1's ramps
    zr = zc - R_LOOP * (1 - 1 / R2)                            # the right arc to heading 0 starts here
    s.fwd((zr - s.z) * R2).arc(R_LOOP, -45)
    xe = zc + D_LINE + 1.0                                     # past D, plus room to come down
    s.fwd(xe - s.x).down().arc(R_LOOP, 45)
    k = s.x - s.z
    e = (s.x + 1.0, s.z + 1.0)
    s.taper(*_to_d_out(e[0] - (k - D_LINE) / 2, e[1] + (k - D_LINE) / 2, 1))
    out["L1"] = s
    return out


def ramps_north(plan):
    out = dict(acute_A1())
    out.update(obtuse_O1_clover() if plan == "clover" else obtuse_O1_direct())
    return out


def twin_names(plan):
    return {"L6": "L8", "R4": "R2", "L3": "L1", "R7": "R5"} if plan == "clover" else \
        {"L6": "L8", "R4": "R2", "L1": "L3", "R7": "R5"}


def ramp_samples(plan, case="A"):
    """{name: samples} for all eight ramps of one case."""
    n = {k: t.samples() for k, t in ramps_north(plan).items()}
    out = dict(n)
    for k, v in twin_names(plan).items():
        out[v] = xform(n[k], "rot180")
    if case == "B":
        out = {k: xform(v, "mirror_rev") for k, v in out.items()}
    return out


# Movement names: arms +x / -x (S) and +d / -d (D; +d = the +x+z end in case A). Quadrants A1/A2 acute, O1/O2 obtuse.
MOVES = {
    "clover": {
        "L1": ("-x", "+d", "left 45: loop 315 (O2)"),
        "L3": ("+x", "-d", "left 45: loop 315 (O1)"),
        "L6": ("-d", "-x", "left 135: loop 225 (A1)"),
        "L8": ("+d", "+x", "left 135: loop 225 (A2)"),
        "R2": ("-x", "-d", "right 135: round the loop (A2)"),
        "R4": ("+x", "+d", "right 135: round the loop (A1)"),
        "R5": ("-d", "+x", "right 45: round the loop (O2)"),
        "R7": ("+d", "-x", "right 45: round the loop (O1)"),
    },
    "direct": {
        "L1": ("-x", "+d", "left 45: flyover over S and D (O1)"),
        "L3": ("+x", "-d", "left 45: flyover over S and D (O2)"),
        "L6": ("-d", "-x", "left 135: loop 225 (A1)"),
        "L8": ("+d", "+x", "left 135: loop 225 (A2)"),
        "R2": ("-x", "-d", "right 135: round the loop (A2)"),
        "R4": ("+x", "+d", "right 135: round the loop (A1)"),
        "R5": ("-d", "+x", "right 45: hugs the corner (O2)"),
        "R7": ("+d", "-x", "right 45: hugs the corner (O1)"),
    },
}

# Core, case A: S bridges over D. S rises 1024 -> 1536 -> 1792 (as the stock X's z arms 15150 / 15153); D dips
# 1024 -> 512 -> 256 (as its x arms 15107 / 15108).
S_BRIDGE = [(-1, 0), (0, 0), (1, 0), (-2, -1), (-1, -1), (0, -1)]
S_ARM = [(-2, 0), (2, 0), (-3, -1), (1, -1)]
D_DIP = [(0, 1), (1, 1), (2, 1), (-3, -2), (-2, -2), (-1, -2)]


def mainline_label(x, z, case):
    """What the stock highways put at a point (case-local): heading 0 / 180 (S) or 45 / 225 (D), 'M' on D's median
    line, or None."""
    if case == "B":
        z = -z
    lab = None
    if -1 <= z < 0:
        lab = 0
    elif 0 <= z < 1:
        lab = 180
    else:
        k = x - z
        if abs(k) < 1e-9:
            return "M"
        if 0 < k < 1 - 1e-9:
            lab = 45
        elif -1 + 1e-9 < k < 0:
            lab = 225
    if lab is None:
        return None
    if case == "B":
        lab = (180 - lab) % 360            # mirrored then reversed: -h + 180
    return lab


def core_cells(case):
    c = set(S_BRIDGE + S_ARM + D_DIP)
    if case == "B":
        c = {(i, -1 - j) for i, j in c}
    return c


N = 12                 # sub-cell grid per cell for the "same content" test


def raster(plan, case):
    """{cell: {(u, v): label}} - each cell's content sampled at N x N sub-cell centres: within W of a ramp centreline
    -> 'r<heading/45>' (+ 'e' on a flyover); mainline cells in the footprint add 'm<heading/45>'. Sub-cell centres
    are symmetric under a quarter turn, so turned copies compare exactly."""
    R = ramp_samples(plan, case)
    pts = [p for v in R.values() for p in v]
    hsh = {}
    for p in pts:
        hsh.setdefault((math.floor(p[0]), math.floor(p[1])), []).append(p)
    cells = set()
    for x, z, h, e in pts:
        for dx in (-W, 0, W):
            for dz in (-W, 0, W):
                cells.add((math.floor(x + dx), math.floor(z + dz)))
    grid = {}
    lim = W * W
    for c in cells:
        near = [p for di in (-1, 0, 1) for dj in (-1, 0, 1) for p in hsh.get((c[0] + di, c[1] + dj), ())]
        g = {}
        for u in range(N):
            for v in range(N):
                px, pz = c[0] + (u + .5) / N, c[1] + (v + .5) / N
                best = None
                for x, z, h, e in near:
                    dd = (x - px) ** 2 + (z - pz) ** 2
                    if dd < lim and (best is None or dd < best[0]):
                        best = (dd, h, e)
                if best:
                    g[(u, v)] = "r%d%s" % (round(best[1] / 45) % 8, "e" if best[2] else "")
        if g:
            grid[c] = g
    for c in set(grid) | core_cells(case):
        g = grid.setdefault(c, {})
        for u in range(N):
            for v in range(N):
                lab = mainline_label(c[0] + (u + .5) / N, c[1] + (v + .5) / N, case)
                if lab is not None and (u, v) not in g:
                    g[(u, v)] = "mM" if lab == "M" else "m%d" % (lab // 45)
    return grid


def rot_sig(g, k):
    """Content turned by k quarter turns (a game state), headings turned with it."""
    out = []
    for (u, v), lab in g.items():
        for _ in range(k):
            u, v = N - 1 - v, u                # (x, z) -> (-z, x) on the cell grid: heading + 90
        if lab[1] == "M":
            out.append(((u, v), lab))
            continue
        out.append(((u, v), lab[0] + str((int(lab[1]) + 2 * k) % 8) + lab[2:]))
    return tuple(sorted(out))


def classify(plan, case):
    g = raster(plan, case)
    core = core_cells(case)
    ml = {c for c in g if any(lab[0] == "m" for lab in g[c].values())}
    att = {c for c in g if c in ml and c not in core}
    ramp = {c for c in g if c not in ml and c not in core}
    return g, core, att, ramp


def pieces(plan, cases=("A", "B")):
    """Distinct pieces over the given cases: two cells share a piece when their content is the same up to a quarter
    turn (a state); core cells are unique per 180-degree pair. Returns ({(case, cell): piece}, count, {piece: kind})."""
    canon, out, kind = {}, {}, {}
    for case in cases:
        g, core, att, ramp = classify(plan, case)
        for c in sorted(g, key=lambda c: (c[1], c[0])):
            if c in core:
                m = (-1 - c[0], -1 - c[1])
                sig = ("core", case, min(c, m))
            else:
                sig = min(rot_sig(g[c], k) for k in range(4))
            if sig not in canon:
                canon[sig] = len(canon)
                kind[canon[sig]] = "core" if c in core else "att" if c in att else "ramp"
            out[(case, c)] = canon[sig]
    return out, len(canon), kind


def summary(plan):
    g, core, att, ramp = classify(plan, "A")
    xs = [c[0] for c in g]
    zs = [c[1] for c in g]
    pa = pieces(plan, ("A",))[1]
    pid, n, kind = pieces(plan)
    by = {}
    for k in kind.values():
        by[k] = by.get(k, 0) + 1
    R = ramp_samples(plan)
    seglen = [(math.hypot(b[0] - a[0], b[1] - a[1]), a[3] and b[3]) for v in R.values() for a, b in zip(v, v[1:])]
    return {"cells": len(g), "core": len(core), "att": len(att), "ramp": len(ramp),
            "box": (min(xs), max(xs), min(zs), max(zs)), "w": max(xs) - min(xs) + 1, "h": max(zs) - min(zs) + 1,
            "pA": pa, "pAB": n, "by": by, "len": sum(L for L, e in seglen), "elev": sum(L for L, e in seglen if e)}


def cmd_cells(plan):
    for n, t in sorted(ramps_north(plan).items()):
        ends = []
        for s in t.segs:
            if s[0] == "line":
                ends.append("(%.2f,%.2f)" % s[2])
            elif s[0] == "arc":
                a = math.radians(s[3] + s[4])
                ends.append("arc->(%.2f,%.2f)" % (s[1][0] + s[2] * math.cos(a), s[1][1] + s[2] * math.sin(a)))
            else:
                ends.append("S->(%.2f,%.2f)" % s[4])
        print("%s: %s" % (n, " ".join(ends)))
    s = summary(plan)
    print("plan %s, case A: core %d, ramp-on-highway %d, ramp-only %d = %d cells; box i %d..%d, j %d..%d (%d x %d)"
          % ((plan, s["core"], s["att"], s["ramp"], s["cells"]) + s["box"] + (s["w"], s["h"])))
    print("ramp centreline %.1f cells, of which flyover %.1f" % (s["len"], s["elev"]))
    print("distinct pieces: case A %d, A+B %d (%s)" % (s["pA"], s["pAB"],
                                                       ", ".join("%s %d" % kv for kv in sorted(s["by"].items()))))


# ------------------------------------------------------------------------------------------------ the picture
COL = {
    "L1": (200, 40, 40), "L3": (40, 90, 200), "L6": (0, 150, 150), "L8": (190, 60, 170),
    "R2": (230, 120, 0), "R4": (120, 80, 20), "R5": (60, 150, 40), "R7": (110, 60, 190),
}


def cmd_png(out, plan):
    from PIL import Image, ImageDraw, ImageFont
    case = "A"
    other = "direct" if plan == "clover" else "clover"
    g, core, att, ramp = classify(plan, case)
    pid, npieces, kind = pieces(plan)
    me, oth = summary(plan), summary(other)
    R = ramp_samples(plan, case)
    S = 30                                   # px per cell
    X0, X1, Z0, Z1 = -14, 14, -11, 11
    W_, H_ = (X1 - X0) * S, (Z1 - Z0) * S
    ML, MT = 34, 78
    LEG = 470
    img = Image.new("RGB", (ML + W_ + 18 + LEG, MT + H_ + 30), (250, 250, 248))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("arial.ttf", 9)
        fb = ImageFont.truetype("arialbd.ttf", 16)
        fm = ImageFont.truetype("arial.ttf", 12)
        fmb = ImageFont.truetype("arialbd.ttf", 12)
    except OSError:
        f = fb = fm = fmb = ImageFont.load_default()

    def P(x, z):                              # z grows downward, like the game's cell dumps
        return ML + (x - X0) * S, MT + (z - Z0) * S

    def box(i, j, inset=0):
        a, b = P(i, j)
        return [a + inset, b + inset, a + S - inset, b + S - inset]

    d.rectangle([ML, MT, ML + W_, MT + H_], fill=(214, 232, 200))
    for c in core:
        d.rectangle(box(*c), fill=(236, 226, 200))
    for c in att:
        d.rectangle(box(*c), fill=(225, 215, 235))
    GREY = (165, 165, 165)
    for i in range(X0, X1):
        for j in range(Z0, Z1):
            a, b = P(i, j)
            if j in (-1, 0):
                d.rectangle(box(i, j), fill=GREY)
            elif i - j == 0:
                d.rectangle(box(i, j), fill=GREY)
            elif i - j == 1:
                d.polygon([(a, b), (a, b + S), (a + S, b + S)], fill=GREY)
            elif i - j == -1:
                d.polygon([(a, b), (a + S, b), (a + S, b + S)], fill=GREY)
    for c in D_DIP:
        d.rectangle(box(*c, 1), outline=(130, 70, 20), width=3)
    for c in S_ARM:
        d.rectangle(box(*c, 1), outline=(30, 60, 170), width=2)
    for c in S_BRIDGE:
        d.rectangle(box(*c, 1), outline=(30, 60, 170), width=4)
    d.line([P(X0, 0), P(X1, 0)], fill=(245, 215, 60), width=2)
    lo, hi = max(X0, Z0), min(X1, Z1)
    d.line([P(lo, lo), P(hi, hi)], fill=(245, 215, 60), width=2)

    def arrow(x, z, h, col, size=0.35, w=2):
        r = math.radians(h)
        ux, uz = math.cos(r), math.sin(r)
        tip = P(x + ux * size, z + uz * size)
        d.line([P(x - ux * size, z - uz * size), tip], fill=col, width=w)
        for s_ in (1, -1):
            a = r + math.pi - s_ * 0.5
            d.line([tip, P(x + ux * size + 0.3 * math.cos(a), z + uz * size + 0.3 * math.sin(a))], fill=col, width=w)

    for x in (-13, -11, 10, 12):
        arrow(x + 0.5, -0.5, 0, (55, 55, 55))
        arrow(x + 0.5, 0.5, 180, (55, 55, 55))
    for k in (-10, -8, 8, 10):
        arrow(k + 0.5 + 0.3, k + 0.5 - 0.3, 45, (55, 55, 55))
        arrow(k + 0.5 - 0.3, k + 0.5 + 0.3, 225, (55, 55, 55))
    wpx = max(3, int(S * 2 * W * 0.75))
    labels = {}
    for name, pts in R.items():
        seg = [P(x, z) for x, z, h, e in pts[::2]]
        el = [e for x, z, h, e in pts[::2]]
        d.line(seg, fill=COL[name], width=wpx, joint="curve")
        for k in range(len(seg) - 1):                # flyover stretch: black edges
            if el[k] and el[k + 1]:
                d.line([seg[k], seg[k + 1]], fill=(0, 0, 0), width=wpx + 5)
        for k in range(len(seg) - 1):
            if el[k] and el[k + 1]:
                d.line([seg[k], seg[k + 1]], fill=COL[name], width=wpx)
        n = len(pts)
        for frac in (0.2, 0.5, 0.8):
            x, z, h, e = pts[int(n * frac)]
            arrow(x, z, h, (255, 255, 255), 0.2, 2)
    north = {"clover": {"L6": (5.3, 2.0), "R4": (8.3, 3.6), "L3": (-1.6, 3.0), "R7": (-6.6, 3.3)},
             "direct": {"L6": (5.3, 2.0), "R4": (8.3, 3.6), "R7": (-1.8, 2.2), "L1": (-6.4, 4.6)}}[plan]
    for k, (x, z) in north.items():
        labels[k] = (x, z)
        labels[twin_names(plan)[k]] = (-x - 0.6, -z - 0.4)
    for i in range(X0, X1 + 1):
        d.line([P(i, Z0), P(i, Z1)], fill=(150, 160, 150), width=1)
    for j in range(Z0, Z1 + 1):
        d.line([P(X0, j), P(X1, j)], fill=(150, 160, 150), width=1)
    for (cs, c), n in pid.items():
        if cs == case and X0 <= c[0] < X1 and Z0 <= c[1] < Z1:
            a, b = P(*c)
            d.text((a + 2, b + 1), str(n), fill=(0, 0, 0), font=f)
    for name, (x, z) in labels.items():
        a, b = P(x, z)
        d.rectangle([a - 1, b, a + 19, b + 13], fill=(250, 250, 248))
        d.text((a, b), name, fill=COL[name], font=fmb)
    for i in range(X0, X1 + 1, 2):
        a, b = P(i, Z0)
        d.text((a - 4, b - 12), "%+d" % i if i else "0", fill=(80, 80, 80), font=f)
    for j in range(Z0, Z1 + 1, 2):
        a, b = P(X0, j)
        d.text((a - 24, b - 5), "%+d" % j if j else "0", fill=(80, 80, 80), font=f)
    title = {"clover": "skewed cloverleaf, loops for every left turn, one bridge",
             "direct": "direct flyovers for the 45-degree left turns"}[plan]
    d.text((ML, 6), "hwdx plan (%s): diagonal x straight highway, %s" % (plan, title), fill=(0, 0, 0), font=fb)
    d.text((ML, 28), "Top-down cell grid, x to the right, z down (as the game's cell dumps). Case A (x-z diagonal): "
           "lab cell = (58 + i, 28 + j). Number in a cell = piece index.", fill=(40, 40, 40), font=fm)
    d.text((ML, 44), "Grey = highway decks at 1024. Thick blue = S bridge deck (1792), thin blue = S rising arm "
           "(1536). Brown = D underpass (256) and its dip arms (512).", fill=(40, 40, 40), font=fm)
    d.text((ML, 60), "Tint: beige = core, lilac = ramp joins a highway cell, green = ramp alone. Black-edged ramp = "
           "one-lane flyover above the decks. Arrows = driving direction.", fill=(40, 40, 40), font=fm)

    lx, y = ML + W_ + 18, MT - 4
    lines = [
        ("STOCK TODAY (measured in game)", "b"),
        ("Two 2-cell 'Highway Construction' 15149 blocks that never", None),
        ("resolve; the diagonal's outer cells beside S turn straight.", None),
        ("", None),
        ("BRIDGE", "b"),
        ("S (straight) over, D (diagonal) under, the stock X's split:", None),
        ("one deck rises to 1792, the other dips to 256. Ramps join", None),
        ("only where both are back at 1024 (outside the outlined cells).", None),
        ("", None),
        ("MOVEMENTS (all 8 turns connect)", "b"),
    ]
    for k in ("L1", "L3", "L6", "L8", "R2", "R4", "R5", "R7"):
        a, b, why = MOVES[plan][k]
        lines.append(("%s  %s arm -> %s arm, %s" % (k, a, b, why), COL[k]))
    if plan == "clover":
        lines += [
            ("", None),
            ("Acute A1/A2 (45): 225-degree loop at the corner, the 135-", None),
            ("degree ramp runs round it. Obtuse O1/O2 (135): 315-degree", None),
            ("loop, the 45-degree ramp runs round it. No ramp crosses a", None),
            ("road: the S/D crossing is the only bridge.", None),
        ]
    else:
        lines += [
            ("", None),
            ("Acute A1/A2 as in the cloverleaf. Obtuse O1/O2: the right", None),
            ("turn hugs the corner, the left turn is a flyover. The two", None),
            ("halves of S (and of D) touch, with no median gap, so a left", None),
            ("exit cannot climb over the other half. L1/L3 leave from the", None),
            ("outer side outside the acute ramps on that arm, fly over all", None),
            ("of S, then over all of D, and join from the outer side past", None),
            ("the other acute quadrant: 2 one-lane bridges each, 4 in all.", None),
        ]
    lines += [
        ("", None),
        ("Each quadrant uses its own two carriageways only: a built-up", None),
        ("quadrant drops its ramps, the rest still builds (core alone", None),
        ("if none fits)." + (" Here L1/L3 also cross A2/A1." if plan == "direct" else ""), None),
        ("", None),
        ("COMPARISON (case A; pieces for both diagonal families)", "b"),
    ]
    for nm, sm in ((plan, me), (other, oth)):
        lines.append(("%s: %d x %d cells, %d cells touched, ramps %.0f cells" % (nm, sm["w"], sm["h"], sm["cells"],
                                                                               sm["len"]), None))
        lines.append(("    (flyover %.0f), pieces A %d, A + B %d" % (sm["elev"], sm["pA"], sm["pAB"]), None))
    lines += [
        ("Ids: 200 (21260..21359 + 21460..21559). hwx's X: 12 x 12.", None),
        ("Case B (x+z diagonal) = this drawing mirrored, directions", None),
        ("reversed (own pieces: its loops are mirror images).", None),
    ]
    for text, col in lines:
        if col == "b":
            d.text((lx, y), text, fill=(0, 0, 0), font=fmb)
        elif col:
            d.rectangle([lx, y + 3, lx + 14, y + 11], fill=col)
            d.text((lx + 20, y), text, fill=(0, 0, 0), font=fm)
        else:
            d.text((lx, y), text, fill=(0, 0, 0), font=fm)
        y += 16
    for name, (x, z) in {"A1": (9.0, 4.0), "O1": (-4.5, 7.0), "A2": (-10.0, -5.0), "O2": (3.5, -8.0)}.items():
        d.text(P(x, z), name, fill=(80, 80, 80), font=fb)
    for name, (x, z) in {"+x arm": (12.0, 1.3), "-x arm": (-13.9, -2.0), "+d arm": (10.6, 10.2),
                         "-d arm": (-10.4, -10.8)}.items():
        d.text(P(x, z), name, fill=(50, 50, 50), font=fmb)
    img.save(out)
    print("wrote", out, img.size)


if __name__ == "__main__":
    a = sys.argv[1:]
    plan = "clover"
    if "--plan" in a:
        plan = a[a.index("--plan") + 1]
        a = [x for x in a if x not in ("--plan", plan)]
    if a and a[0] == "png":
        cmd_png(a[1], plan)
    else:
        cmd_cells(plan)
