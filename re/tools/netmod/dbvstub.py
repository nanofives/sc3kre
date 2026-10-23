#!/usr/bin/env python3
r"""dbvstub.py - diagonal boulevard STUB caps (task avrbtfix, 2026-10-21).

Owner img4 / img5: a hand-drawn third diagonal road rarely ends on the same row as the avenue's two. Past the band's last
full row one drag (or two) goes on for a row or two, an end shape none of diagbv.ENDS covers, so DBV used to refuse the
whole band (stock ladder = "a column of roundabouts"). sc3netmod_dbv.c now converts such a band with that end left stock
(RAGGED); this module paints real ends for the common shapes.

A stub cap is diagbv_paint.Cap generalised: past the band's last full row (canonical bottom frame, row 0 = cells 0..3)
the pavement is the band's two diagonal edges (p = x - z in 0..3) intersected with the UNION of the road cells the
drags hold, `rows` {j: d offsets of row j} (row j's cell d is (j + d, j)). The curb runs along the edges of the cells
the drags leave and along the band's edges, corners rounded by rho as Cap's. For a shape Cap already covers this is
Cap's own closure (cap-part: rows {1: (0, 1, 2)} = Cap(0.5, [z 2, x 4])). Lanes: dbvlanes._cap_lanes unchanged (the
three U-turns round the median nose, placed where the full-width closure leaves room); the stub tongue is paved, with
no other lane into it (the U-turns sit as far along as the closure lets the outer one stay paved, which uses the stub
when it widens the end on that side: 01, 012/0).

  py -3.12 dbvstub.py shapes                       the ragged end shapes of +-1-row staggered drags, by frequency
  py -3.12 dbvstub.py plan OUT.png [SHAPE ...]     top-down plan sheet (cells, curb, median nose, lanes with arrows)
SHAPE = rows as d lists, '/' between rows, e.g. 12 (row 1 = d 1, 2) or 012/0 (row 1 = d 0..2, row 2 = d 0).
"""
import itertools
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

SQ2 = math.sqrt(2.0)


def parse_shape(s):
    return {j + 1: tuple(int(c) for c in part) for j, part in enumerate(s.split("/")) if part}


def shape_name(rows):
    return "/".join("".join(str(d) for d in rows[j]) for j in sorted(rows))


def _sq_dist(px, pz, x0, z0):
    dx = max(x0 - px, 0.0, px - (x0 + 1.0))
    dz = max(z0 - pz, 0.0, pz - (z0 + 1.0))
    return math.hypot(dx, dz)


def _outside(c):
    """a cell wholly outside the band's strip p 0..3 (its p range is x - z - 1 .. x - z + 1)"""
    return c[0] - c[1] + 1 <= 0.0 or c[0] - c[1] - 1 >= 3.0


def make_scene(rows, wz0=None, rho=0.35, band_rows=8):
    """the stub cap scene (a diagbv_paint.Cap whose closure is the cell union)"""
    from netmod import diagbv_paint as P

    cells = {(z + d, z) for z in range(-band_rows, 1) for d in range(4)}
    for j, ds in rows.items():
        cells |= {(j + d, j) for d in ds}
    if wz0 is None:
        wz0 = 0.5 if rows else 0.0                       # as Cap: markings stop half a row in when a row goes on

    class StubCap(P.Cap):
        def dist(self, wx, wz):
            ci, cj = math.floor(wx), math.floor(wz)
            if (ci, cj) not in cells:
                return -1.0
            p = wx - wz
            s = [p / SQ2, (3.0 - p) / SQ2]
            for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (1, 1), (-1, 1)):
                n = (ci + di, cj + dj)
                if n in cells:
                    continue
                if _outside(n):
                    continue                                 # wholly outside the band's edges: the wall closes there
                if di and dj:
                    h, v = (ci + di, cj), (ci, cj + dj)      # the two edge neighbours beside the diagonal square
                    if h in cells and v in cells:
                        s.append(_sq_dist(wx, wz, n[0], n[1]))   # a concave corner
                    elif v in cells and h not in cells and _outside(h):
                        s.append(abs(wx - (ci + (1 if di > 0 else 0))))   # the closure line x between v and n
                    elif h in cells and v not in cells and _outside(v):
                        s.append(abs(wz - (cj + (1 if dj > 0 else 0))))   # the closure line z between h and n
                    continue                                 # (else an edge square already bounds this side)
                s.append(_sq_dist(wx, wz, n[0], n[1]))
            r = self.rho
            if min(s) >= r:
                return min(s)
            return r - math.sqrt(sum(max(0.0, r - v) ** 2 for v in s))

    sc = StubCap(wz0, [], rho)
    sc.cells = cells
    sc.rows = rows
    return sc


# ------------------------------------------------------------------------------------------------ shapes
def staggered_shapes(spread=1):
    """ragged end shapes (rows past the end, bottom frame) of three drags, each starting / ending up to `spread` rows
    off, both first-step directions -> Counter"""
    from netmod import diagbv as D
    from netmod.diagave import drag
    tally = Counter()
    rng = range(-spread, spread + 1)
    for f in "xz":
        for ss in itertools.product(rng, repeat=3):
            for ls in itertools.product(rng, repeat=3):
                cells = set()
                for k, (s, l) in enumerate(zip(ss, ls)):
                    cells |= set(drag(k + s, s, 10 - s + l, 1, f))
                R = {D.to_canon(0, c) for c in cells}
                for b in D.bands(cells):
                    if b["axis"] != 0:
                        continue
                    for e, (z_e, a_e) in ((1, b["rows"][-1]), (0, b["rows"][0])):
                        kind, cell = D.classify_end(R, z_e, a_e, e, len(b["rows"]))
                        if kind != "ragged":
                            tally[kind] += 1
                            continue
                        rows = {}
                        for j in range(1, 5):
                            ds = tuple(d for d in range(-2, 7) if cell(j + d, j) in R)
                            if ds:
                                rows[j] = ds
                        tally["ragged " + shape_name(rows)] += 1
    return tally


def cmd_shapes(argv):
    t = staggered_shapes()
    n = sum(t.values())
    for k, v in t.most_common():
        print("%5d  %5.1f%%  %s" % (v, 100.0 * v / n, k))


# ------------------------------------------------------------------------------------------------ plan sheet
def lanes_of(sc, wz_from=-5.0):
    from netmod import dbvlanes as DL
    from netmod import bvlanes as BL
    return [("u", ln.pts) for ln in DL._cap_lanes(sc, wz_from)]     # C side in (+q), U-turn, A side out (-q)


def plan_panel(rows, title, W=420, H=520, S=46.0):
    """one top-down panel, turned 45 degrees so the band runs down the page as in the game at rotation 0"""
    from PIL import Image, ImageDraw
    sc = make_scene(rows)
    im = Image.new("RGB", (W, H), (70, 98, 60))
    dr = ImageDraw.Draw(im)
    cx, cy = W / 2.0, H * 0.62

    def scr(wx, wz):                                    # screen x = -(p - 1.5), y = q (down), scale S per cell
        p, q = wx - wz, wx + wz
        return cx - (p - 1.5) * S / SQ2, cy + (q - 1.0) * S / SQ2

    # pavement (sampled), curb = dist band
    step = 2
    for py_ in range(0, H, step):
        for px_ in range(0, W, step):
            p = 1.5 - (px_ - cx) * SQ2 / S
            q = 1.0 + (py_ - cy) * SQ2 / S
            wx, wz = (q + p) / 2.0, (q - p) / 2.0
            if p < 0.0 or p >= 3.0:
                continue
            if wz < sc.wz0:
                col = (118, 118, 118)
                if abs(p - 1.5) < 0.18 and wz < sc.wz0 - 0.15:
                    col = (96, 140, 70)                     # median (grass + trees in the art)
            else:
                d = sc.dist(wx, wz)
                if d <= 0.0:
                    continue
                col = (205, 205, 200) if d < 0.07 else (118, 118, 118)
            dr.rectangle([px_, py_, px_ + step - 1, py_ + step - 1], fill=col)
    # cell grid + road cells past the end
    for z in range(-6, 5):
        for x in range(z - 3, z + 8):
            pts = [scr(x, z), scr(x + 1, z), scr(x + 1, z + 1), scr(x, z + 1)]
            if (x, z) in sc.cells and z >= 0:
                dr.polygon(pts, outline=(255, 210, 60))
                if z >= 1:
                    mx, my = scr(x + 0.5, z + 0.5)
                    dr.text((mx - 10, my - 6), "stub", fill=(255, 210, 60))
            else:
                dr.polygon(pts, outline=(52, 74, 46))
    # lanes with arrows
    cols = {"u": (255, 255, 255)}
    for kind, pts in lanes_of(sc):
        sp = [scr(x, z) for (x, z) in pts]
        sp = [p for p in sp if -10 < p[0] < W + 10 and -10 < p[1] < H + 10]
        if len(sp) < 2:
            continue
        dr.line(sp, fill=cols[kind], width=2)
        for i in range(len(sp) // 3, len(sp) - 1, max(8, len(sp) // 3)):
            (x1, y1), (x2, y2) = sp[i], sp[min(len(sp) - 1, i + 3)]
            a = math.atan2(y2 - y1, x2 - x1)
            for da in (2.6, -2.6):
                dr.line([(x2, y2), (x2 + 9 * math.cos(a + da), y2 + 9 * math.sin(a + da))], fill=cols[kind], width=2)
    dr.rectangle([0, 0, W - 1, 22], fill=(30, 30, 30))
    dr.text((6, 5), title, fill=(255, 255, 255))
    return im


def cmd_plan(argv):
    from PIL import Image, ImageDraw
    out = argv[0]
    shapes = argv[1:] or ["", "12", "123", "23", "01", "012/0"]
    panels = [plan_panel(parse_shape(s), "row past end: %s" % (s or "none (cap-square, today)")) for s in shapes]
    W, H = panels[0].size
    cols = 3
    sheet = Image.new("RGB", (W * cols, H * ((len(panels) + cols - 1) // cols) + 60), (20, 20, 20))
    for i, pn in enumerate(panels):
        sheet.paste(pn, ((i % cols) * W, (i // cols) * H))
    dr = ImageDraw.Draw(sheet)
    y = sheet.size[1] - 56
    dr.text((8, y), "Diagonal boulevard end, top-down, turned so the band runs down the page (game rotation 0). Yellow = the "
            "cells the end writes: the band's last full row and the 'stub' cells past it.", fill=(230, 230, 230))
    dr.text((8, y + 16), "Lanes (white, arrows): 3 lanes each way, right-hand, the left side runs down the page; the three "
            "U-turns go round the median nose, outer to outer, middle to middle, inner to inner.", fill=(230, 230, 230))
    dr.text((8, y + 32), "Stub cells are paved and curbed along the cell edges the drags leave (the existing caps' rule). The "
            "U-turns sit as far down as the pavement lets the outer one (01, 012/0: into the stub); no other lane.", fill=(230, 230, 230))
    sheet.save(out)
    print("plan ->", out)


def cmd_mockup(argv):
    """the shapes painted with the boulevard painter (diagbv.paint_layout, the game's projection via boulevard.render)"""
    from PIL import Image, ImageDraw
    from netmod import boulevard as BV
    from netmod import diagbv as D
    out = argv[0]
    shapes = argv[1:] or ["", "12", "123", "23", "01", "012/0"]
    cache = os.path.join(os.path.dirname(os.path.abspath(out)), "dbvstub_mockup_cache")
    shots = []
    for s in shapes:
        rows = parse_shape(s)
        sc = make_scene(rows)
        cells = {c: sc for c in sc.cells if c[1] >= -5}
        rc = D.paint_layout(cells, os.path.join(cache, s.replace("/", "_") or "square"), zooms=(3, 4))
        for z, r in ((4, 0), (3, 2)):
            shots.append(("row past end: %s, zoom %d, view %d" % (s or "none (cap-square, today)", z, r),
                          BV.render(rc, z, r)))
    W = max(im.width for _, im in shots)
    cols = 2
    rowsh = [max(shots[i][1].height, shots[i + 1][1].height) + 24 for i in range(0, len(shots), 2)]
    sheet = Image.new("RGB", (W * cols, sum(rowsh)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    y = 0
    for k, i in enumerate(range(0, len(shots), 2)):
        for c in range(cols):
            title, im = shots[i + c]
            d.text((c * W + 6, y + 5), title, fill=(230, 230, 230))
            sheet.paste(im.convert("RGB"), (c * W, y + 24))
        y += rowsh[k]
    sheet.save(out)
    print("mockup ->", out, sheet.size)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[1] == "shapes":
        cmd_shapes(argv[2:])
    elif argv[1] == "plan":
        cmd_plan(argv[2:])
    elif argv[1] == "mockup":
        cmd_mockup(argv[2:])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
