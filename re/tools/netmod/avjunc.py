#!/usr/bin/env python3
r"""avjunc.py - junctions on one-way avenues (task avjunc, 2026-10-19): the box-cell lane model, its turn matrices and
curves, and the plan sheet. Plan: verify/avjunc/PLAN.md. Rework of the AVX block (avx.py, sc3netmod_avx.c).

The model. A junction box is a set of paved cells across both halves of an avenue (and of a crossing avenue). Every box
cell is a small crossroads whose four edges each carry one MODE (state-0 frame of the piece, sides in the SIMNTWRK dir
order 0 x-, 1 z-, 2 x+, 3 z+, which is also the rotation order):
  N  two lanes in       (an edge where a one-way flow enters: an avenue half running into the box, or the box cell
                        upstream on the same one-way row / column)
  O  two lanes out      (the same, leaving)
  T  two-way            (a road arm, a two-way avenue half, or an edge across a median opening: the stock road slots,
                        one lane in and one out)
  C  closed
Lane slots are the stock ones: 80 and 175 along each edge (NET_LANES.md 2.4). Right-hand traffic (ENGLISH lanes; the
owner's decision, English-UK included): a car heading h has its right side on h - 1 (mod 4), so at an edge the
right-hand slot is the one nearer that side. A T edge's in-lane is the right-hand slot of the inbound heading (= the
stock road lane), its out-lane the right-hand slot of the outbound heading.

Inside a cell every in-lane joins the exits on the other three edges:
  straight  2 -> 2 lane by lane, 2 -> 1 both merge, 1 -> 2 the lane feeds both, 1 -> 1
  right     the right-hand in-lane to the right-hand out-lane
  left      the left-hand in-lane to the left-hand out-lane
  fallback  an in-lane left with no exit takes the nearest one (straight first, then the turn on its own side), to
            the out-lane on its own side (a dual turn keeps the lane order)
No U-turn inside one cell; U-turns happen across two cells (left, left) through a median opening.
Turn matrix (props 310) = the (entry side, exit side) pairs that carry a lane, low half; high half its transpose
(the stock rule, NET_LANES.md 1.2).

Box cells get their modes from two flows: the ROW flow (the one-way half the cell lies on, or none = two-way) and the
COLUMN flow (the crossing avenue's one-way half, or none). An internal edge along x takes the row flow, along z the
column flow (none -> T); an outside edge takes the neighbour: a one-way half -> N / O by its direction, a road or a
two-way half -> T, nothing -> C. With both flows set (avenue x avenue) the four box cells form a one-way ring.

CLI:
  py -3.12 avjunc.py plan OUT.png            the milestone-1 plan sheet (top-down, as seen in game)
  py -3.12 avjunc.py cell NOTC               one cell's lanes and matrix (modes for sides x- z- x+ z+)
  py -3.12 avjunc.py curves                  the distinct lane curves the model needs, modulo rotation
"""
import argparse
import itertools
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

SIDES = ("x-", "z-", "x+", "z+")
DV = ((-1, 0), (0, -1), (1, 0), (0, 1))
SLOTS = (80, 175)
SPEED = 64000


def opp(d):
    return (d + 2) % 4


def right_of(h):
    return (h - 1) % 4


def left_of(h):
    return (h + 1) % 4


def slots_rl(h):
    """lane slots for heading h, right-hand lane first"""
    return [80, 175] if right_of(h) in (0, 1) else [175, 80]


def edge_pt(e, t):
    return [(0, t), (t, 0), (255, t), (t, 255)][e]


def in_lanes(modes, e):
    h = opp(e)
    if modes[e] == "N":
        return [edge_pt(e, t) for t in slots_rl(h)]
    if modes[e] == "T":
        return [edge_pt(e, slots_rl(h)[0])]
    return []


def out_lanes(modes, f):
    if modes[f] == "O":
        return [edge_pt(f, t) for t in slots_rl(f)]
    if modes[f] == "T":
        return [edge_pt(f, slots_rl(f)[0])]
    return []


def turn(e, f):
    h = opp(e)
    if f == h:
        return "straight"
    if f == right_of(h):
        return "right"
    if f == left_of(h):
        return "left"
    return "u"


def cell_lanes(modes):
    """modes: 4 chars (sides x- z- x+ z+) -> [(e, p_in, f, p_out, kind)], state-0 frame"""
    out = []
    for e in range(4):
        ins = in_lanes(modes, e)
        if not ins:
            continue
        got = {tuple(p): 0 for p in ins}
        moves = {}
        for f in range(4):
            if f == e:
                continue
            outs = out_lanes(modes, f)
            if outs:
                moves[turn(e, f)] = (f, outs)
        for kind, (f, outs) in moves.items():
            if kind == "straight":
                if len(ins) == len(outs):
                    pairs = list(zip(ins, outs))
                elif len(ins) == 2:
                    pairs = [(ins[0], outs[0]), (ins[1], outs[0])]
                else:
                    pairs = [(ins[0], outs[0]), (ins[0], outs[1])]
            elif kind == "right":
                pairs = [(ins[0], outs[0])]
            else:
                pairs = [(ins[-1], outs[-1])]
            for a, b in pairs:
                out.append((e, a, f, b, kind))
                got[tuple(a)] += 1
        for a in ins:                                   # fallback: no in-lane without an exit
            if got[tuple(a)]:
                continue
            side = "right" if a == ins[0] else "left"
            for kind in ("straight", side, "left" if side == "right" else "right"):
                if kind in moves:
                    f, outs = moves[kind]
                    b = outs[0] if a == ins[0] else outs[-1]          # a dual turn keeps the lane order
                    out.append((e, a, f, b, kind + "*"))
                    break
    return out


def matrix(modes):
    """-> sorted [(entry side, exit side)] that carry a lane (props 310 low half)"""
    return sorted({(e, f) for e, _, f, _, _ in cell_lanes(modes)})


def mask(modes):
    low = 0
    for e, f in matrix(modes):
        low |= 1 << (4 * e + f)
    high = 0
    for e, f in matrix(modes):
        high |= 1 << (4 * f + e)
    return (high << 16) | low


# ------------------------------------------------------------------------------------------------ curves

def heading_vec(h):
    return DV[h]


def bezier(p0, h0, p1, h1, n=9):
    """a lane from p0 (travelling h0) to p1 (arriving travelling h1): cubic Bezier, end tangents along the headings"""
    (x0, z0), (x1, z1) = p0, p1
    d0, d1 = heading_vec(h0), heading_vec(h1)
    if h0 == h1 and (x0 == x1 or z0 == z1) and (x1 - x0) * d0[0] + (z1 - z0) * d0[1] > 0 and \
            ((d0[0] and z0 == z1) or (d0[1] and x0 == x1)):
        return [[x0, 0, z0], [x1, 0, z1]]                # a straight lane: two points, as the stock straights
    if h0 == h1:
        L = abs((x1 - x0) * d0[0] + (z1 - z0) * d0[1]) * 0.5
        c0 = (x0 + d0[0] * L, z0 + d0[1] * L)
        c1 = (x1 - d1[0] * L, z1 - d1[1] * L)
    else:                                                # a turn: corner point = the two lane lines' intersection
        if d0[0]:
            cx, cz = x1, z0
        else:
            cx, cz = x0, z1
        k = 0.5523
        c0 = (x0 + (cx - x0) * k, z0 + (cz - z0) * k)
        c1 = (x1 + (cx - x1) * k, z1 + (cz - z1) * k)
    pts = []
    for i in range(n):
        t = i / (n - 1.0)
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
        pts.append([int(round(a * x0 + b * c0[0] + c * c1[0] + d * x1)), 0,
                    int(round(a * z0 + b * c0[1] + c * c1[1] + d * z1))])
    return pts


def rot_pt(p, k):
    x, z = p
    for _ in range(k % 4):
        x, z = 255 - z, x
    return (x, z)


def curve_key(e, a, f, b):
    """canonical geometry of a lane (rotated so it enters by x-) and the rotation back -> ((t_in, f', t_out), r)"""
    k = (-e) % 4
    a2, b2 = rot_pt(a, k), rot_pt(b, k)
    f2 = (f + k) % 4
    return (a2[1], f2, b2), (4 - k) % 4


def all_curves(patterns):
    seen = {}
    for m in patterns:
        for e, a, f, b, kind in cell_lanes(m):
            g, r = curve_key(e, a, f, b)
            seen.setdefault(g, kind)
    return seen


# ------------------------------------------------------------------------------------------------ scenes

class Scene:
    """a small top-down grid for the plan sheet. Cell kinds:
       ('half', d)        one-way avenue half running toward side d (2 lanes)
       ('twhalf', axis)   stock two-way avenue half along axis 'x' / 'z'
       ('road', axis)     two-way road straight along axis
       ('nose', d, ends)  one-way half with the median nose at `ends` (sides)
       ('box', row, col)  junction box cell; row / col = one-way flow direction or None"""

    def __init__(self, w, h, title, sub):
        self.w, self.h, self.title, self.sub = w, h, title, sub
        self.c = {}
        self.median = []            # (x, z, side): a median strip along that side of the cell
        self.labels = {}

    def art(self, x, z):
        """edge outline per side: I another box cell, A an arm (any neighbour), C closed"""
        out = []
        for e in range(4):
            q = self.c.get((x + DV[e][0], z + DV[e][1]))
            out.append("C" if q is None else ("I" if q[0] == "box" else "A"))
        return "".join(out)

    def modes(self, x, z):
        k = self.c[(x, z)]
        if k[0] in ("half", "nose"):
            d = k[1]
            m = ["C"] * 4
            m[d], m[opp(d)] = "O", "N"
            return "".join(m)
        if k[0] in ("road", "twhalf"):
            m = ["C"] * 4
            if k[1] == "x":
                m[0] = m[2] = "T"
            else:
                m[1] = m[3] = "T"
            return "".join(m)
        _, row, col = k
        m = []
        for e in range(4):
            nb = (x + DV[e][0], z + DV[e][1])
            q = self.c.get(nb)
            if q is not None and q[0] == "box":
                flow = row if e in (0, 2) else col
                m.append("T" if flow is None else ("O" if e == flow else "N"))
            elif q is None:
                m.append("C")
            elif q[0] in ("half", "nose"):
                d = q[1]
                m.append("O" if d == e else ("N" if d == opp(e) else "C"))
            elif q[0] in ("road", "twhalf"):
                along = q[1] == "x"
                m.append("T" if (e in (0, 2)) == along else "C")
            else:
                m.append("C")
        return "".join(m)


def scene_avenue_x(S, rows, x0, x1, oneway=True):
    """an avenue along x on rows (z, z+1): the z- row runs +x, the z+ row -x (11204 states 2 / 0)"""
    for x in range(x0, x1 + 1):
        if oneway:
            S.c[(x, rows)] = ("half", 2)
            S.c[(x, rows + 1)] = ("half", 0)
        else:
            S.c[(x, rows)] = ("twhalf", "x")
            S.c[(x, rows + 1)] = ("twhalf", "x")
        S.median.append((x, rows, 3))


def scene_avenue_z(S, cols, z0, z1, oneway=True):
    """an avenue along z on columns (x, x+1): the x- column runs -z, the x+ column +z (11204 states 1 / 3)"""
    for z in range(z0, z1 + 1):
        if oneway:
            S.c[(cols, z)] = ("half", 1)
            S.c[(cols + 1, z)] = ("half", 3)
        else:
            S.c[(cols, z)] = ("twhalf", "z")
            S.c[(cols + 1, z)] = ("twhalf", "z")
        S.median.append((cols, z, 2))


def drop_median(S, cells):
    S.median = [m for m in S.median if (m[0], m[1]) not in cells]


def box(S, cells, row=None, col=None):
    for c in cells:
        r = row(c) if callable(row) else row
        k = col(c) if callable(col) else col
        S.c[c] = ("box", r, k)
    drop_median(S, set(cells))


def scenes():
    out = []
    # 1 road x avenue
    S = Scene(7, 6, "ROAD x AVENUE", "box across both halves, every turn")
    scene_avenue_x(S, 2, 0, 6)
    for z in range(0, 6):
        if z not in (2, 3):
            S.c[(3, z)] = ("road", "z")
    box(S, [(3, 2), (3, 3)], row=lambda c: 2 if c[1] == 2 else 0)
    out.append(S)
    # 2 road T
    S = Scene(7, 6, "ROAD MEETS ONE SIDE (T)", "the box still spans both halves")
    scene_avenue_x(S, 2, 0, 6)
    for z in range(0, 2):
        S.c[(3, z)] = ("road", "z")
    box(S, [(3, 2), (3, 3)], row=lambda c: 2 if c[1] == 2 else 0)
    out.append(S)
    # 3 staggered T's
    S = Scene(8, 6, "TWO T's OFFSET BY ONE CELL", "two boxes, a short median between")
    scene_avenue_x(S, 2, 0, 7)
    for z in range(0, 2):
        S.c[(2, z)] = ("road", "z")
    for z in range(4, 6):
        S.c[(5, z)] = ("road", "z")
    box(S, [(2, 2), (2, 3)], row=lambda c: 2 if c[1] == 2 else 0)
    box(S, [(5, 2), (5, 3)], row=lambda c: 2 if c[1] == 2 else 0)
    out.append(S)
    # 4 avenue x avenue
    S = Scene(6, 6, "AVENUE x AVENUE", "the four box cells form a one-way ring")
    scene_avenue_x(S, 2, 0, 5)
    scene_avenue_z(S, 2, 0, 5)
    S.median = [m for m in S.median if not ((m[0], m[1]) in {(2, 2), (2, 3), (3, 2), (3, 3)})]
    box(S, [(2, 2), (3, 2), (2, 3), (3, 3)], row=lambda c: 2 if c[1] == 2 else 0, col=lambda c: 1 if c[0] == 2 else 3)
    out.append(S)
    # 5 avenue T
    S = Scene(6, 6, "AVENUE ENDS ON AVENUE (T)", "ring with one side closed")
    scene_avenue_x(S, 2, 0, 5)
    scene_avenue_z(S, 2, 0, 1)
    box(S, [(2, 2), (3, 2), (2, 3), (3, 3)], row=lambda c: 2 if c[1] == 2 else 0, col=lambda c: 1 if c[0] == 2 else 3)
    out.append(S)
    # 6 avenue ends on a road
    S = Scene(6, 6, "AVENUE ENDS ON A ROAD", "the road row becomes the box")
    for x in range(0, 6):
        if x not in (2, 3):
            S.c[(x, 1)] = ("road", "x")
    scene_avenue_z(S, 2, 2, 5)
    box(S, [(2, 1), (3, 1)], col=lambda c: 1 if c[0] == 2 else 3)
    out.append(S)
    # 7 mixed: one-way avenue x two-way avenue
    S = Scene(6, 6, "ONE-WAY x TWO-WAY AVENUE", "an avenue the mod could not convert")
    scene_avenue_x(S, 2, 0, 5)
    scene_avenue_z(S, 2, 0, 5, oneway=False)
    box(S, [(2, 2), (3, 2), (2, 3), (3, 3)], row=lambda c: 2 if c[1] == 2 else 0)
    out.append(S)
    for S in out:                                    # noses on the one-way half cells beside each box
        for (x, z), k in list(S.c.items()):
            if k[0] != "half":
                continue
            ends = [e for e in (k[1], opp(k[1]))
                    if S.c.get((x + DV[e][0], z + DV[e][1]), ("",))[0] == "box"]
            if ends:
                S.c[(x, z)] = ("nose", k[1], ends)
    return out


# ------------------------------------------------------------------------------------------------ drawing

COL = {2: (214, 39, 40), 0: (31, 90, 220), 1: (148, 70, 178), 3: (240, 140, 0)}   # by heading entering the cell
ASPHALT, BOXC, GRASS, BG, NOSE = (150, 150, 150), (128, 128, 128), (62, 150, 62), (246, 246, 246), (200, 200, 190)


def _font(sz, bold=False):
    from PIL import ImageFont
    for f in (("arialbd.ttf" if bold else "arial.ttf"),):
        try:
            return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f), sz)
        except OSError:
            pass
    return ImageFont.load_default()


def canon(t):
    """the smallest rotation of a per-side tuple (rotation order = side order)"""
    return min(tuple(t[(i - k) % 4] for i in range(4)) for k in range(4))


def cell_type(S, c):
    return canon(tuple(a + m for a, m in zip(S.art(*c), S.modes(*c))))


def label_scenes(sc):
    names = {}
    for S in sc:
        S.labels = {}
        for c in sorted(S.c, key=lambda c: (c[1], c[0])):
            if S.c[c][0] != "box":
                continue
            t = cell_type(S, c)
            names.setdefault(t, "B%d" % (len(names) + 1))
            S.labels[c] = names[t]
    return names


MODE_WORD = {"N": "2 in", "O": "2 out", "T": "two-way", "C": "closed"}


def draw_scene(im, S, ox, oy, cs):
    """top-down, AS SEEN IN GAME: lane z runs up the screen (the lane frame is mirrored on screen: +x -> +z is
    counter-clockwise, NET_LANES.md 8), so screen y = oy + (h - z) * cs - (local z) * cs / 256"""
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    sc = cs / 256.0

    def P(x, z, lx, lz):
        return (ox + (x + lx / 256.0) * cs, oy + (S.h - z - lz / 256.0) * cs)

    for (x, z), k in S.c.items():
        x0, y0 = P(x, z, 0, 256)
        x1, y1 = P(x, z, 256, 0)
        d.rectangle([x0, y0, x1, y1], fill=BOXC if k[0] == "box" else ASPHALT)
    for (x, z, side) in S.median:
        if side == 3:
            a, b = P(x, z, 0, 256 - 10), P(x, z, 256, 256 + 10)
        else:
            a, b = P(x, z, 256 - 10, 0), P(x, z, 256 + 10, 256)
        d.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], fill=GRASS)
    for (x, z), k in S.c.items():                      # median noses: a short concrete tip at the box end
        if k[0] != "nose":
            continue
        for e in k[2]:
            side = 3 if k[1] in (0, 2) and (x, z) in {(m[0], m[1]) for m in S.median if m[2] == 3} else None
            for (mx, mz, ms) in S.median:
                if (mx, mz) == (x, z) or (ms == 3 and (mx, mz + 1) == (x, z)) or (ms == 2 and (mx + 1, mz) == (x, z)):
                    if ms == 3:
                        lx0, lx1 = (0, 40) if e == 0 else (216, 256)
                        a, b = P(mx, mz, lx0, 256 - 12), P(mx, mz, lx1, 256 + 12)
                    else:
                        lz0, lz1 = (0, 40) if e == 1 else (216, 256)
                        a, b = P(mx, mz, 256 - 12, lz0), P(mx, mz, 256 + 12, lz1)
                    d.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], fill=NOSE)
    for (x, z), k in S.c.items():                      # lane dashes between the two lanes of a one-way half
        if k[0] not in ("half", "nose"):
            continue
        for i in range(4):
            if k[1] in (0, 2):
                a, b = P(x, z, i * 64 + 16, 127), P(x, z, i * 64 + 48, 127)
            else:
                a, b = P(x, z, 127, i * 64 + 16), P(x, z, 127, i * 64 + 48)
            d.line([a, b], fill=(255, 255, 255), width=2)
    for (x, z), k in S.c.items():
        m = S.modes(x, z)
        for e, a, f, b, kind in cell_lanes(m):
            pts = bezier(a, opp(e), b, f, 13)
            xy = [P(x, z, p[0], p[2]) for p in pts]
            col = COL[opp(e)] if k[0] == "box" else COL[opp(e)]
            d.line(xy, fill=col, width=2)
            if k[0] == "box" or (S.c.get((x + DV[f][0], z + DV[f][1])) is None):
                (ax, ay), (bx, by) = xy[-2], xy[-1]
                L = math.hypot(bx - ax, by - ay) or 1
                ux, uy = (bx - ax) / L, (by - ay) / L
                s = 7
                d.polygon([(bx, by), (bx - ux * s - uy * s * 0.6, by - uy * s + ux * s * 0.6),
                           (bx - ux * s + uy * s * 0.6, by - uy * s - ux * s * 0.6)], fill=col)
    f = _font(13, True)
    for (x, z), lab in S.labels.items():
        cx, cy = P(x, z, 128, 128)
        tw = d.textlength(lab, font=f)
        d.rectangle([cx - tw / 2 - 3, cy - 9, cx + tw / 2 + 3, cy + 9], fill=(255, 255, 255))
        d.text((cx - tw / 2, cy - 8), lab, fill=(0, 0, 0), font=f)


PLAN_TEXT = [
    ("h", "What changes"),
    ("t", "- Every junction on a one-way avenue becomes one paved box across both halves (the AVX box, extended)."),
    ("t", "- Each box cell is a small crossroads: per edge 2 lanes in, 2 lanes out, two-way, or closed."),
    ("t", "  Inside a cell: straight lane by lane, right turn from the right lane, left turn from the left lane."),
    ("t", "- The median opening is the box itself: a left turn or a U-turn crosses to the other half inside it."),
    ("t", "- Avenue x avenue: the four box cells form a one-way ring (in, around, out), so every turn connects."),
    ("t", "- The halves next to a box keep the concrete median nose, now with the two one-way lanes."),
    ("t", "- Art stays the AVX look (paved box, crosswalks, curbs); 7 new box outlines for the new shapes."),
    ("h", "Shipped cities (15, offline scan)"),
    ("t", "- 3,040 junction or end segments on straight avenues; AVX boxes about 1,200 of them today."),
    ("t", "- The new rule boxes 3,063 junctions (9,058 box cells) with 52 distinct box cells (ids fit the grant)."),
    ("t", "- Left two-way (the whole avenue): rare diagonal-road pieces at the junction (26), runs over 4 cells (10)."),
    ("h", "Open"),
    ("t", "- Avenue CORNERS (an avenue turning 90 degrees, ~90 + ~150 with a road) have no owner yet."),
    ("t", "- English-UK: new lane curves must be written the same way round there (today's tools reverse them)."),
]


def draw_cell_zoom(im, modes, ox, oy, size):
    """one box cell, large, with what each edge carries (as seen in game: lane z up the screen)"""
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    P = lambda lx, lz: (ox + lx / 256.0 * size, oy + (1 - lz / 256.0) * size)        # noqa: E731
    d.rectangle([ox, oy, ox + size, oy + size], fill=BOXC)
    for e, a, f, b, kind in cell_lanes(modes):
        xy = [P(p[0], p[2]) for p in bezier(a, opp(e), b, f, 17)]
        col = COL[opp(e)]
        d.line(xy, fill=col, width=3)
        (ax, ay), (bx, by) = xy[-2], xy[-1]
        L = math.hypot(bx - ax, by - ay) or 1
        ux, uy = (bx - ax) / L, (by - ay) / L
        d.polygon([(bx, by), (bx - ux * 11 - uy * 7, by - uy * 11 + ux * 7),
                   (bx - ux * 11 + uy * 7, by - uy * 11 - ux * 7)], fill=col)
    f = _font(14, True)
    words = [MODE_WORD[m] for m in modes]
    cx, cy = ox + size / 2, oy + size / 2
    pos = [(ox - 8, cy, "r"), (cx, oy + size + 6, "t"), (ox + size + 8, cy, "l"), (cx, oy - 22, "t")]
    for e, (x, y, anc) in enumerate(pos):                  # side e: x- left, z- bottom (screen), x+ right, z+ top
        w = d.textlength(words[e], font=f)
        tx = x - w if anc == "r" else (x if anc == "l" else x - w / 2)
        d.text((tx, y - (8 if anc in "rl" else 0)), words[e], fill=(0, 0, 0), font=f)


def cmd_plan(a):
    from PIL import Image, ImageDraw
    sc = scenes()
    names = label_scenes(sc)
    cs = 54
    W = 1800
    im = Image.new("RGB", (W, 2400), BG)
    d = ImageDraw.Draw(im)
    d.text((16, 10), "Avenue junctions on one-way avenues (plan, stream avjunc)", fill=(0, 0, 0), font=_font(24, True))
    d.text((16, 44), "Drawn as seen in game, from above (right-hand traffic). Lane colour = where it heads entering the "
           "cell: red right, blue left, orange up, purple down.", fill=(40, 40, 40), font=_font(15))
    d.text((16, 64), "Green = median, light grey = median nose, darker grey = the junction box. B1.. = box cell types "
           "(one piece each, turned as needed).", fill=(40, 40, 40), font=_font(15))
    x0, y = 16, 100
    rowh = 6 * cs + 80
    for i, S in enumerate(sc):
        col = i % 3
        if col == 0 and i:
            y += rowh
        x = x0 + col * (8 * cs + 60)
        d.text((x, y), S.title, fill=(0, 0, 0), font=_font(17, True))
        d.text((x, y + 22), S.sub, fill=(60, 60, 60), font=_font(14))
        draw_scene(im, S, x, y + 46, cs)
    # zoom of B1 (road x avenue, near half) in the last row's free slot
    zx, zy = x0 + 1 * (8 * cs + 60) + 40, y + 60
    d.text((x0 + 1 * (8 * cs + 60), y), "INSIDE ONE BOX CELL (B1)", fill=(0, 0, 0), font=_font(17, True))
    d.text((x0 + 1 * (8 * cs + 60), y + 22), "straight lane by lane, right turn from the right lane, left from the left",
           fill=(60, 60, 60), font=_font(14))
    rxa = sc[0]
    draw_cell_zoom(im, rxa.modes(3, 2), zx + 60, zy + 30, 250)
    # cell type legend
    lx, ly = x0 + 2 * (8 * cs + 60), y
    d.text((lx, ly), "BOX CELL TYPES IN THESE DRAWINGS", fill=(0, 0, 0), font=_font(17, True))
    ly += 28
    for t, nm in sorted(names.items(), key=lambda kv: int(kv[1][1:])):
        txt = "%s  edges going round: %s" % (nm, ", ".join(
            "%s%s" % (MODE_WORD[m], "" if a == "I" else (" (arm)" if a == "A" else "")) for a, m in t))
        d.text((lx, ly), txt, fill=(30, 30, 30), font=_font(14))
        ly += 20
    ty = y + rowh + 10
    for kind, txt in PLAN_TEXT:
        if kind == "h":
            ty += 8
            d.text((16, ty), txt, fill=(0, 100, 0) if txt == "Open" else (0, 0, 0), font=_font(17, True))
            ty += 26
        else:
            d.text((16, ty), txt, fill=(30, 30, 30), font=_font(15))
            ty += 21
    im = im.crop((0, 0, W, ty + 16))
    im.save(a.out)
    print("wrote", a.out, im.size, "types", {v: "".join(a + m for a, m in k) for k, v in names.items()})


def cmd_cell(a):
    m = a.modes.upper()
    for e, p, f, q, kind in cell_lanes(m):
        print("  %s %s -> %s %s  %s" % (SIDES[e], p, SIDES[f], q, kind))
    print("matrix low:", ", ".join("%s=>%s" % (SIDES[e], SIDES[f]) for e, f in matrix(m)), " mask 0x%08x" % mask(m))


def cmd_curves(a):
    pats = ["".join(p) for p in itertools.product("NOTC", repeat=4)]
    cv = all_curves(pats)
    for g, kind in sorted(cv.items()):
        print("  x- %3d -> %s %s   (%s)" % (g[0], SIDES[g[1]], g[2], kind))
    print(len(cv), "curve geometries modulo rotation")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("plan")
    s.add_argument("out")
    s = sub.add_parser("cell")
    s.add_argument("modes")
    sub.add_parser("curves")
    a = ap.parse_args(argv)
    return {"plan": cmd_plan, "cell": cmd_cell, "curves": cmd_curves}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
