#!/usr/bin/env python3
r"""hwt_paint.py - the connecting highway T as an hwpaint scene (stream hwt, 2026-10-18).

  py -3.12 hwt_paint.py mockup OUT_DIR [--loop-r 1.25]   previews zoom 4 and 3, views 0 and 1 + sheet hwt_mockup.png
  py -3.12 hwt_paint.py paint OUT_DIR --zoom Z --shard I/N   paint one shard of the mockup cells (run N in parallel)
  py -3.12 hwt_paint.py mockup OUT_DIR --reuse              assemble previews from painted shards
  py -3.12 hwt_paint.py routes | export OUT.json            turn matrices from the centrelines / the footprint table
  py -3.12 hwt_paint.py cells [--loop-r 1.25]            cells the decks touch (the art footprint), in the stem frame

Stem frame = world here (verify/hwt/README.md 2): through highway along x, rows z 0 (EB, +x) and z 1 (WB, -x), median z = 1; stem
along z from -z, SB column x 0..1, NB column x 1..2. Geometry (cells):
  * the through highway stays stock: level at H, straight; ramps leave and join it at its outer edges.
  * the stem's two carriageways end at z -3 and split into one-lane ramp decks (hwx's width 2 W = 0.62 = hwpaint.RAMP_W): NB into the
    exit to EB and the straight ramp to the bridge; SB is fed by the bridge ramp and the ramp from EB.
  * the two straight ramps rise to H_TOP = H + (H_HIGH - H_LOW) (the stock X's clearance over a deck) and cross both
    carriageways side by side on slab bridges, 0.81 apart (deck 0.62 + gap 0.19), at x = 1 -+ 0.405.
  * far side: NB's ramp loops clockwise (radius R_LOOP about C = (1.405 + R, 2.25 + R)), coming down along its whole length,
    and joins WB from outside after an S taper. The outer ramp (WB -> SB) leaves WB east of the loop, turns north and
    runs concentric with the loop at R + 0.81, so its west leg is exactly the SB bridge ramp at x 0.595.
  * stem side: NB -> EB and EB -> SB leave / join the stem and EB through S tapers 0.25 outside their edges, with
    quarter turns of radius 1.0 between.
Ramp constants come from hwt_layout.GEOM (hwx.py when importable).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import hwpaint as HP  # noqa: E402
import hwlanes as HL  # noqa: E402
import hwt_layout  # noqa: E402

G = hwt_layout.GEOM
RW = 2 * G["W"]                       # one-lane ramp deck width (0.44)
SEP = RW + G["GAP"]                   # centreline spacing of two parallel ramp decks (0.63)
H, H_TOP = HP.H, HP.H + (HP.H_HIGH - HP.H_LOW)
EDGE_OUT = 0.25                       # ramp line 0.25 outside a carriageway edge (hwx)
RAMP_SLAB = 10.25                     # ramp slab thickness: the fitted stock 15127 (hwpaint proof), as hwx
Z_SPLIT = -3.0                        # the stem's carriageways end here and split into the ramps (a cell edge)


def s_taper(path, offset, length):
    """append an S of two equal arcs moving the path `offset` cells to its LEFT (negative = right) over `length`"""
    th = 2.0 * math.atan(abs(offset) / length)
    rho = length / (2.0 * math.sin(th))
    sg = 1.0 if offset > 0 else -1.0
    return path.then_arc(rho, sg * math.degrees(th)).then_arc(rho, -sg * math.degrees(th))


def line_to(path, pt):
    """append a straight to `pt` (skipped when the path already ends there)"""
    a, _ = path.at(path.length)
    if math.hypot(pt[0] - a[0], pt[1] - a[1]) < 1e-6:
        return path
    return HP.Path(path.segs + [HP.Line(a, pt)])


def s_at(path, pred, n=2000):
    """first arc length where pred(point) holds"""
    for k in range(n + 1):
        s = path.length * k / n
        p, _ = path.at(s)
        if pred(p):
            return s
    return path.length


def pillars(path, s0, s1, step=1.25, avoid=()):
    out = []
    k = s0 + step / 2.0
    while k < s1:
        p, _ = path.at(k)
        if not any(f(p) for f in avoid):
            out.append(p)
        k += step
    return out


SCENE_PATHS = {}            # filled by scene(): every lane's centreline in travel direction
LANE_DECKS = []             # filled by scene(): the decks hwlanes cuts lanes from (the NB ramp as ONE deck: its two
                            # painted decks meet inside a cell, and hwlanes drops a lane cut that starts or ends there)


def cell_seq(path, step=0.004):
    """cells a centreline passes, in order (a diagonal step through a corner is split at the midpoint's cell)"""
    out = []
    n = int(path.length / step) + 1
    for k in range(n + 1):
        p, _ = path.at(path.length * k / n)
        c = (int(math.floor(p[0])), int(math.floor(p[1])))
        if out and c != out[-1] and abs(c[0] - out[-1][0]) + abs(c[1] - out[-1][1]) == 2:
            q, _ = path.at(path.length * (k - 0.5) / n)
            m = (int(math.floor(q[0])), int(math.floor(q[1])))
            if m in (out[-1], c):
                m = (out[-1][0], c[1])
            out.append(m)
        if not out or c != out[-1]:
            out.append(c)
    return out


def side(a, b):
    """side of cell a facing neighbour b: 0 x-, 1 z-, 2 x+, 3 z+ (NET_LANES.md 1.1)"""
    return {(-1, 0): 0, (0, -1): 1, (1, 0): 2, (0, 1): 3}[(b[0] - a[0], b[1] - a[1])]


def routes(paths=None):
    """{cell: {(enter side, leave side)}} from every lane centreline (a path starting / ending inside a cell enters
    / leaves it along its own heading there)"""
    paths = paths or SCENE_PATHS
    def toward(d):                       # side a heading points at (dominant axis)
        return (2 if d[0] > 0 else 0) if abs(d[0]) >= abs(d[1]) else (3 if d[1] > 0 else 1)

    out = {}
    for name, P in paths.items():
        cs = cell_seq(P)
        d0, d1 = P.at(0.0)[1], P.at(P.length)[1]
        for i, c in enumerate(cs):
            lv = side(c, cs[i + 1]) if i + 1 < len(cs) else toward(d1)
            en = side(c, cs[i - 1]) if i > 0 else (toward(d0) + 2) % 4
            out.setdefault(c, set()).add((en, lv))
    return out


def reach_routes(rt, window):
    """route NB, EB, WB entries through `rt` to where they leave the window -> {source: sinks}"""
    x0, x1, z0, z1 = window
    srcs = {"NB": ((1, z0), 1), "EB": ((x0, 0), 0), "WB": ((x1, 1), 2)}
    step = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}
    out = {}
    for name, start in srcs.items():
        seen, todo, sinks = set(), [start], set()
        while todo:
            cell, f = todo.pop()
            if (cell, f) in seen:
                continue
            seen.add((cell, f))
            for ff, t in rt.get(cell, ()):
                if ff != f:
                    continue
                n = (cell[0] + step[t][0], cell[1] + step[t][1])
                if not (x0 <= n[0] <= x1 and z0 <= n[1] <= z1):
                    sinks.add("EB" if t == 2 and cell[1] == 0 else "WB" if t == 0 and cell[1] == 1
                              else "SB" if t == 1 and cell[0] == 0 else "?%s,%d" % (cell, t))
                    continue
                todo.append((n, (t + 2) % 4))
        out[name] = sinks
    return out


def deck_cells(deck, inset=0.02):
    """cells one deck covers (sampled every 1/32 cell along it, across its width less `inset` each side)"""
    cells = set()
    n = max(2, int(deck.path.length * 32) + 1)
    for k in range(n):
        p, dd = deck.path.at(deck.path.length * k / (n - 1))
        left = (-dd[1], dd[0])
        for j in range(9):
            o = (j / 8.0 - 0.5) * (deck.w - 2 * inset)
            cells.add((int(math.floor(p[0] + o * left[0])), int(math.floor(p[1] + o * left[1]))))
    return cells


STOCK_DECKS = ("hw_left", "hw_right")      # the through highway and the stem carriageways (stock art)


def footprint(sc, window=(-4, 7, -5, 7)):
    """-> {cell: {"decks": [...], "connects": [[enter, leave], ...], "kind": "new" | "highway"}} for every cell whose
    art or lanes differ from the plain stock highway. "highway" = a cell the through highway or the stem already holds
    (rewritten), "new" = a cell the T claims."""
    x0, x1, z0, z1 = window
    rt = routes()
    by = {}
    for d in sc.decks:
        for c in deck_cells(d):
            if x0 <= c[0] <= x1 and z0 <= c[1] <= z1:
                by.setdefault(c, set()).add(d.name)
    out = {}
    for c in sorted(set(by) | set(rt)):
        if not (x0 <= c[0] <= x1 and z0 <= c[1] <= z1):
            continue
        names = by.get(c, set())
        if names <= set(STOCK_DECKS):
            continue                                    # plain stock highway: stays stock
        hw = c[1] in (0, 1) or (c[0] in (0, 1) and c[1] < 0)
        out[c] = {"decks": sorted(names), "connects": sorted([list(e) for e in rt.get(c, ())]),
                  "kind": "highway" if hw else "new"}
    return out


def under_through(p):
    return -0.15 <= p[1] <= 2.15


def auto_gaps(decks, tol_h=1.5, step=0.02, pad=0.06):
    """open the parapet of every deck where another deck at the same height, driven the same way, touches or overlaps
    it (ramp joins and the stem's split): the side the other deck lies on ("outer" = the deck's right, its parapet
    side, or "inner"). Decks driven opposite ways (the stem's two ramps at the median) keep their parapets."""
    for A in decks:
        marks = []
        for B in decks:
            if B is A:
                continue
            n = max(2, int(B.path.length / step))
            for k in range(n + 1):
                sb = B.path.length * k / n
                p, db = B.path.at(sb)
                sa, ta = A.path.project(np.array([p[0]]), np.array([p[1]]))
                sa, ta = float(sa[0]), float(ta[0])
                if not (0.0 <= sa <= A.path.length) or abs(ta) > A.w / 2.0 + B.w / 2.0 - 0.02:
                    continue
                da = A.path.at(sa)[1]
                if da[0] * db[0] + da[1] * db[1] < 0.0:
                    continue                              # opposite directions (the median): keep the parapets
                if abs(float(A.h(np.array([sa]))[0]) - float(B.h(np.array([sb]))[0])) > tol_h:
                    continue
                marks.append((sa, "outer" if ta < 0 else "inner"))
        gaps = []
        for side in ("outer", "inner"):
            ss = sorted(m[0] for m in marks if m[1] == side)
            for v in ss:
                if gaps and gaps[-1][2] == side and v - gaps[-1][1] <= 0.15:
                    gaps[-1][1] = v
                else:
                    gaps.append([v, v, side])
        A.gaps = [(max(0.0, g0 - pad), min(A.path.length, g1 + pad), sd) for g0, g1, sd in gaps if g1 - g0 > 0.02]
    return decks


def scene(R=None, extent=(-5.0, 8.0, -6.0, 8.0), rio=False):
    """Every ramp starts and ends ON a carriageway lane at a cell border (hwlanes links lanes of neighbouring cells by
    border position): the stem's two carriageways end at Z_SPLIT (a cell edge) and each lane goes on as one ramp; the
    through highway's outer lane feeds the exits and takes the entries at cell borders."""
    R = R or G["R_LOOP"]
    x0, x1, z0, z1 = extent
    lo, li = HL.HW_LANES                                  # outer / inner lane, share of the width from the outer parapet
    xs, xn = 1.0 - SEP / 2.0, 1.0 + SEP / 2.0          # SB / NB bridge ramp centrelines (0.595 / 1.405)
    C = (xn + R, 2.0 + EDGE_OUT + R)                      # loop centre: loop bottom tangent to z = 2 + EDGE_OUT
    Ro = R + SEP
    decks = []
    # through highway: stock, level, straight
    decks += HP.highway(HP.Path.line((x0, 1.0), (x1, 1.0)))
    # stem: two carriageways up to Z_SPLIT (no end face there: the ramps carry on from the same edge)
    decks += HP.highway(HP.Path.line((1.0, z0), (1.0, Z_SPLIT)))
    decks[-2].ends = (True, False)                        # hw_right (NB) runs along the path: its end is at Z_SPLIT
    decks[-1].ends = (False, True)                        # hw_left (SB) runs against it: its start is at Z_SPLIT
    rise = (-1.8, -0.15)                                  # z span of the near-side climb
    # NB straight ramp from NB's inner lane: S over to x 1.405, up over the bridge, down the far side, the loop,
    # the S taper into WB's outer lane, to the cell border x 1
    nb = HP.Path.line((2.0 - li, Z_SPLIT), (2.0 - li, Z_SPLIT + 0.01))
    nb = s_taper(nb, -(xn - (2.0 - li)), 0.6)             # heading +z: right = +x
    nb = line_to(nb, (xn, C[1]))
    nb = nb.then_arc(R, -270.0)                           # right turn (clockwise), ends heading -x at z = 2.25
    s_loop1 = nb.length
    nb = s_taper(nb, (2.0 + EDGE_OUT) - (2.0 - lo), 0.65)  # heading -x: left = -z, into WB's outer lane
    nb = line_to(nb, (1.0, 2.0 - lo))
    s_br0, s_br1 = rise[1] - Z_SPLIT, 2.15 - Z_SPLIT     # bridge span (s along the straight part, ~ z - Z_SPLIT)
    h_nb = (lambda f0, f1: (lambda s: np.minimum(f0(s), f1(s))))(
        HP.ramp(H, H_TOP, rise[0] - Z_SPLIT, rise[1] - Z_SPLIT, ease=True),
        HP.ramp(H_TOP, H, s_br1, s_loop1 - 0.2, ease=True))
    # two decks: the tail (taper into WB) passes under the ramp's own bridge, and hwpaint gives a point the height of
    # the NEAREST segment of a path, so one path that crosses itself would cut a notch out of the bridge
    k_loop = [i for i, g in enumerate(nb.segs) if isinstance(g, HP.Arc) and abs(g.R - R) < 1e-9][0]
    nb_main, nb_tail = HP.Path(nb.segs[:k_loop + 1]), HP.Path(nb.segs[k_loop + 1:])
    decks.append(HP.ramp_deck(nb_main, outer="right", width=RW, height=h_nb, slab=[(s_br0, nb_main.length)],
                              thick=RAMP_SLAB, pillars=pillars(nb_main, s_br1, s_loop1, 1.3), ends=(False, False),
                              name="NB->WB"))
    decks.append(HP.ramp_deck(nb_tail, outer="right", width=RW, height=H, ends=(False, False), name="NB->WB"))
    nb_lane = HP.ramp_deck(nb, outer="right", width=RW, height=h_nb, name="NB->WB")
    # outer ramp WB -> SB, in travel direction: from WB's outer lane at the border x 7, taper out to z 2.25, right
    # turn north, concentric left half-turn over the loop, south along x 0.595 over the bridge, S into SB's inner lane
    xe = C[0] + Ro                                        # east leg x
    rho1 = 0.75
    start_x = xe + rho1 + 0.65
    ob = HP.Path.line((float(int(start_x) + 1), 2.0 - lo), (start_x, 2.0 - lo))
    ob = s_taper(ob, -((2.0 + EDGE_OUT) - (2.0 - lo)), 0.65)   # heading -x: right = +z, out to z 2.25
    ob = line_to(ob, (xe + rho1, 2.0 + EDGE_OUT))
    ob = ob.then_arc(rho1, -90.0)                          # right turn: heading +z at x = xe
    ob = line_to(ob, (xe, C[1]))
    ob = ob.then_arc(Ro, 180.0)                            # left half-turn round the loop: heading -z at x = xs
    s_w = ob.length
    ob = line_to(ob, (xs, Z_SPLIT + 0.6))
    ob = s_taper(ob, li - xs, 0.6)                         # heading -z: left = +x, into SB's inner lane at Z_SPLIT
    sb_br0 = s_w + (C[1] - 2.15)
    sb_br1 = s_w + (C[1] - rise[1])
    h_ob = (lambda f0, f1: (lambda s: np.minimum(f0(s), f1(s))))(
        HP.ramp(H, H_TOP, 1.4, sb_br0, ease=True),
        HP.ramp(H_TOP, H, sb_br1, s_w + C[1] - rise[0], ease=True))
    decks.append(HP.ramp_deck(ob, outer="right", width=RW, height=h_ob, slab=[(0.9, sb_br1)], thick=RAMP_SLAB,
                              pillars=pillars(ob, 1.6, sb_br0, 1.3), ends=(False, False), name="WB->SB"))
    # NB -> EB: from NB's outer lane at the split, S taper out to 0.25 outside the stem's edge, quarter turn right,
    # S taper into EB's outer lane, to the border x 5
    r2 = 1.0
    xo = 2.0 + EDGE_OUT
    ne = HP.Path.line((2.0 - lo, Z_SPLIT), (2.0 - lo, Z_SPLIT + 0.01))
    ne = s_taper(ne, -(xo - (2.0 - lo)), 0.65)                     # heading +z: right = +x
    ne = line_to(ne, (xo, -EDGE_OUT - r2)).then_arc(r2, -90.0)
    ne = s_taper(ne, EDGE_OUT + lo, 0.65)                          # heading +x: left = +z, into EB's outer lane
    ne = line_to(ne, (float(int(ne.at(ne.length)[0][0]) + 1), lo))
    decks.append(HP.ramp_deck(ne, outer="right", width=RW, height=H, ends=(False, False), name="NB->EB"))
    # EB -> SB: from EB's outer lane at the border x -3, S taper out to z -0.25, quarter turn right, south 0.25 outside
    # SB's edge, S taper into SB's outer lane at the split
    xw = -EDGE_OUT
    xt = xw - r2
    es = HP.Path.line((float(int(xt - 0.65) - 1), lo), (xt - 0.65, lo))
    es = s_taper(es, -(EDGE_OUT + lo), 0.65)                       # heading +x: right = -z
    es = line_to(es, (xt, -EDGE_OUT))
    es = es.then_arc(r2, -90.0)
    es = line_to(es, (xw, Z_SPLIT + 0.65))
    es = s_taper(es, lo - xw, 0.65)                                # heading -z: left = +x, into SB's outer lane
    decks.append(HP.ramp_deck(es, outer="right", width=RW, height=H, ends=(False, False), name="EB->SB"))
    auto_gaps(decks)
    lanes = {"EB": HP.Path.line((x0, 0.5), (x1, 0.5)), "WB": HP.Path.line((x1, 1.5), (x0, 1.5)),
             "NB": HP.Path.line((1.5, z0), (1.5, Z_SPLIT)), "SB": HP.Path.line((0.5, Z_SPLIT), (0.5, z0)),
             "NB->WB": nb, "WB->SB": ob, "NB->EB": ne, "EB->SB": es}
    if rio:     # right-in / right-out fallback: no bridge, no far side; the stem runs to its stock caps at z -1
        decks = [d for d in decks if d.name not in ("NB->WB", "WB->SB") and d not in decks[2:4]]
        stem = HP.highway(HP.Path.line((1.0, z0), (1.0, -1.0)))
        stem[0].ends, stem[1].ends = (True, False), (False, True)
        decks[2:2] = stem
        auto_gaps(decks)
        for k in ("NB->WB", "WB->SB"):
            del lanes[k]
        lanes["NB"] = HP.Path.line((1.5, z0), (1.5, -1.0))
        lanes["SB"] = HP.Path.line((0.5, -1.0), (0.5, z0))
    SCENE_PATHS.clear()
    SCENE_PATHS.update(lanes)
    LANE_DECKS[:] = [d for d in decks if d.name != "NB->WB"] + ([] if rio else [nb_lane])
    return HP.Scene(decks), C


def font(sz, bold=False):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/%s.ttf" % ("arialbd" if bold else "arial"), sz)
    except OSError:
        return ImageFont.load_default()


def mock_cells(sc):
    return [c for c in HP.scene_cells(sc) if -4 <= c[0] <= 7 and -5 <= c[1] <= 7]


def paint_shard(out, R, zoom, i, n):
    """paint every n-th cell (offset i) of the mockup at one zoom (run n of these in parallel, then mockup --reuse)"""
    sc, C = scene(R)
    cells = mock_cells(sc)[i::n]
    for c in cells:
        HP.paint_cell(sc, c, os.path.join(out, "cells_z%d" % zoom, "%d_%d" % c), zooms=[zoom])
    print("shard %d/%d zoom %d: %d cells" % (i, n, zoom, len(cells)))


def mockup(out, R, reuse=False):
    sc, C = scene(R)
    cells = mock_cells(sc)
    print(len(cells), "cells")
    shots = []
    painted = set()
    for z, r in ((4, 0), (4, 1), (3, 0), (3, 1)):
        im = HP.preview_cells(sc, cells, z, r, os.path.join(out, "cells_z%d" % z), paint=not reuse and z not in painted)
        painted.add(z)
        f = os.path.join(out, "hwt_mock_z%d_r%d.png" % (z, r))
        im.save(f)
        shots.append(((z, r), im))
        print(f, im.size)
    return shots


COLS = {"NB->WB": (230, 120, 20), "WB->SB": (150, 60, 200), "NB->EB": (40, 120, 220), "EB->SB": (40, 160, 70)}


def topdown(sc, cell=34, window=(-3, 7, -3, 6)):
    """top-down plan from the scene itself: claimed / rewritten cells, every deck's outline, lane arrows (x right,
    z up: the game's handedness)"""
    x0, x1, z0, z1 = window
    W, Hh = (x1 - x0 + 1) * cell + 40, (z1 - z0 + 1) * cell + 40
    im = Image.new("RGBA", (W, Hh), (245, 245, 238, 255))
    d = ImageDraw.Draw(im, "RGBA")
    P = lambda x, z: (20 + (x - x0) * cell, 20 + (z1 + 1 - z) * cell)   # noqa: E731
    fp = footprint(sc)
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            k = fp.get((x, z), {}).get("kind")
            fill = {"new": (250, 232, 180, 255), "highway": (205, 205, 225, 255)}.get(k, (236, 236, 228, 255))
            d.rectangle([P(x, z + 1), P(x + 1, z)], fill=fill, outline=(170, 170, 170))
    f = font(10)
    for x in range(x0, x1 + 1):
        d.text((P(x + 0.4, z0)[0], P(x, z0)[1] + 3), str(x), fill=(0, 0, 0), font=f)
    for z in range(z0, z1 + 1):
        d.text((4, P(x0, z + 0.6)[1]), str(z), fill=(0, 0, 0), font=f)
    for dk in sc.decks:
        n = max(2, int(dk.path.length * 12))
        L, R_ = [], []
        hs = []
        for k in range(n + 1):
            pt, dd = dk.path.at(dk.path.length * k / n)
            lf = (-dd[1], dd[0])
            L.append(P(pt[0] + lf[0] * dk.w / 2, pt[1] + lf[1] * dk.w / 2))
            R_.append(P(pt[0] - lf[0] * dk.w / 2, pt[1] - lf[1] * dk.w / 2))
            hs.append(float(dk.h(np.array([dk.path.length * k / n]))[0]))
        col = COLS.get(dk.name, (110, 110, 110))
        top = max(hs) > H + 1
        d.polygon(L + R_[::-1], fill=col + (70 if dk.name in COLS else 90,), outline=col + (255,))
    for name, Pth in SCENE_PATHS.items():
        col = COLS.get(name, (60, 60, 60))
        n = max(2, int(Pth.length * 2))
        for k in range(1, n):
            a, _ = Pth.at(Pth.length * (k - 0.15) / n)
            b, _ = Pth.at(Pth.length * k / n)
            pa, pb = P(*a), P(*b)
            ang = math.atan2(pb[1] - pa[1], pb[0] - pa[0])
            d.polygon([pb, (pb[0] - 8 * math.cos(ang - 0.5), pb[1] - 8 * math.sin(ang - 0.5)),
                       (pb[0] - 8 * math.cos(ang + 0.5), pb[1] - 8 * math.sin(ang + 0.5))], fill=col + (255,))
    return im


def sheet(shots, out, sc=None):
    bg = (54, 88, 54, 255)
    pad = 10
    row1 = [im for (z, r), im in shots if z == 4]
    row2 = [im for (z, r), im in shots if z == 3]
    W = max(sum(i.width for i in row1), sum(i.width for i in row2)) + pad * 3
    Hh = max(i.height for i in row1) + max(i.height for i in row2) + 120
    s = Image.new("RGBA", (W, Hh), bg)
    d = ImageDraw.Draw(s)
    d.text((pad, 6), "hwt mockup: highway T that connects (trumpet, loop R %.2f like hwx, ramps 0.44 wide)"
           % G["R_LOOP"], fill=(255, 255, 255), font=font(18, True))
    y = 36
    for row, zz in ((row1, 4), (row2, 3)):
        x = pad
        for i, im in enumerate(row):
            d.text((x, y), "zoom %d, view %d" % (zz, i), fill=(255, 255, 255), font=font(13))
            s.alpha_composite(im, (x, y + 18))
            x += im.width + pad
        y += max(i.height for i in row) + 40
    if sc is not None:
        td = topdown(sc)
        s2 = Image.new("RGBA", (s.width + td.width + pad, max(s.height, td.height + 60)), bg)
        s2.alpha_composite(s, (0, 0))
        dd = ImageDraw.Draw(s2)
        dd.text((s.width + 2, 36), "top-down, x right z up: yellow = cells the T claims, blue = highway cells it "
                "rewrites", fill=(255, 255, 255), font=font(12))
        dd.text((s.width + 2, 52), "orange NB->WB (loop), purple WB->SB (outer), blue NB->EB, green EB->SB",
                fill=(255, 255, 255), font=font(12))
        s2.alpha_composite(td, (s.width + 2, 72))
        s = s2
    s.save(out)
    print("sheet", out, s.size)


def main(argv):
    R = float(argv[argv.index("--loop-r") + 1]) if "--loop-r" in argv else None
    if argv[1] == "routes":
        sc, C = scene(R)
        rt = routes()
        win = (-4, 7, -5, 7)
        rt = {c: v for c, v in rt.items() if win[0] <= c[0] <= win[1] and win[2] <= c[1] <= win[3]}
        print("reach", reach_routes(rt, win))
        art = set(c for c in HP.scene_cells(sc) if win[0] <= c[0] <= win[1] and win[2] <= c[1] <= win[3])
        plain = {(0, 2): 0}
        for z in range(win[3], win[2] - 1, -1):
            row = []
            for x in range(win[0], win[1] + 1):
                v = rt.get((x, z))
                row.append(("".join("%d%d" % e for e in sorted(v)) if v else ("art" if (x, z) in art else ".")).ljust(9))
            print("%3d " % z + "".join(row))
        print("    " + "".join(("%d" % x).ljust(9) for x in range(win[0], win[1] + 1)))
        print("art-only cells (deck, no lane):", sorted(art - set(rt)))
    elif argv[1] == "paint":
        i, n = map(int, argv[argv.index("--shard") + 1].split("/"))
        paint_shard(argv[2], R, int(argv[argv.index("--zoom") + 1]), i, n)
    elif argv[1] == "export":
        import json
        sc, C = scene(R)
        fp = footprint(sc)
        rows = [{"cell": list(c), **v} for c, v in fp.items()]
        xs = [c[0] for c in fp]
        zs = [c[1] for c in fp]
        meta = {"loop_r": R or G["R_LOOP"], "geom": G, "box": [min(xs), min(zs), max(xs), max(zs)],
                "cells": len(rows), "new": sum(r["kind"] == "new" for r in rows)}
        json.dump({"meta": meta, "cells": rows}, open(argv[2], "w"), indent=1)
        print(meta)
        for z in range(max(zs), min(zs) - 1, -1):
            print("%3d " % z + " ".join(("N" if fp[(x, z)]["kind"] == "new" else "H") if (x, z) in fp else "."
                                        for x in range(min(xs), max(xs) + 1)))
        print("    " + " ".join(str(x % 10) for x in range(min(xs), max(xs) + 1)))
    elif argv[1] == "topdown":
        sc, C = scene(R)
        topdown(sc).save(argv[2])
    elif argv[1] == "cells":
        sc, C = scene(R)
        cs = HP.scene_cells(sc)
        print("loop centre", C, "cells", len(cs))
        print([c for c in cs if -4 <= c[0] <= 7 and -5 <= c[1] <= 7])
    elif argv[1] == "mockup":
        out = argv[2]
        os.makedirs(out, exist_ok=True)
        shots = mockup(out, R, reuse="--reuse" in argv)
        sheet(shots, os.path.join(out, "hwt_mockup.png"), scene(R)[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
