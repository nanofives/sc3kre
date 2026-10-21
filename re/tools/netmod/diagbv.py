#!/usr/bin/env python3
r"""diagbv.py - diagonal boulevards (task diagbv, 2026-10-17): three diagonal road drags joined side by side become one
3-wide diagonal boulevard. The rule's offline twin, the pieces' art and lanes, offline checks.

Three diagonal drags, each one cell over from the last, make a band of four cells per row: d0 (staircase A), d1
(A + B), d2 (B + C), d3 (C). Stock tiles it as a ladder of 11203 / 43 / 43 / 11203. Here A and C are the carriageways
and B gives each an extra lane and holds a grass median with avenue 11204's trees: the straight boulevard's
cross-section turned 45 degrees (diagbv_paint.py).

Note: the footprint of A + C alone (two diagonals drawn TWO cells apart) is the same four cells per row; its ends
leave a gap (d0 and d2 only), which no end here accepts, so that gesture stays the stock ladder unless its ends are
square. The expected gesture: each drag one cell over along x (down-right diagonal) / one cell up (the other one), as
DAV's; the other offset gives staggered ends, of which the oblique caps (cap-x4z3, cap-x4z4) are covered.

Canonical frame: axis 0 (the down-right diagonal), band offset 0 (row z = cells z..z+3), an end at the BOTTOM with the
band's last full row at row 0. A top end is the bottom end turned half a circle (diagbv_paint.turn); axis 1 is axis 0
turned one state.

  py -3 diagbv.py fit                       every end scene against the cells its footprint leaves and its neighbours
  py -3 diagbv.py pieces                    the pieces the stamps need (art compared per cell, duplicates shared)
  py -3 diagbv.py check                     the rule on drag footprints, then DAV's and BV's twins with its claims
  py -3 diagbv.py build PACK_DIR            art/<id>/, the inner piece's lanes, manifest.json
  py -3 diagbv.py plan SAVE                 bands of a save and the pieces the rule wants (read-only)
  py -3 diagbv.py mockup OUT.png [--cache DIR]   the owner mockup (scenes painted per road cell, zoom 4 / 3, views 0 / 1)
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

SQ2 = math.sqrt(2.0)
L = 3.0 * SQ2                     # boulevard_paint.TAPER_LEN (3 cells along) in q units (q = x + z)


def clamp01(v):
    return min(1.0, max(0.0, v))


# ------------------------------------------------------------------------------------------------ the ends
# Each bottom-end case: the continuation below the band's last full row (row 0) as d offsets of each row's cells,
# the rows of it the boulevard still writes (claims) and the scene. Fitted with `fit`: every road cell holds road,
# no road is drawn in a cell the drags leave empty, and where the claim ends the scene equals the neighbour's art
# (the diagonal avenue's pieces, the stock single road).
#
# Why the numbers: past the last full row the strip p 2..3 (C) only has cells in teeth (the d2 cells' corners), so C
# must be gone where the d3 cells stop (the row edge z = 1) unless a d2 cell of the next row carries it; the strip
# p 0..1 (A) likewise where the d0 cells stop. Measured limits (q along, p across):
#   C side, next rows hold d2 (narrowing to A+B, taper to B):  outer edge <= 8 - q, so 3 -> 2 linearly by q 6
#   C side, next rows hold only d0, d1 (taper to A):           gone by q 4 at p 2: holds p 3 to q 3.5, then closes
#                                                             (a 1999-like end) and follows the cell edge x = 3 to q 5
#   A side, next rows hold d1 (narrowing to B+C, taper to B):  outer edge >= q - 2, so 0 -> 1 linearly by q 3
#   A side, next rows hold only d2, d3 (taper to C):           0 -> 2 by q 4 along the same bound (slope 1/2)


def _hi_taper_a(q):
    """the C side's outer curb when the band tapers to A: full width to q 3.5, closes to p 2 at q 4 (cubic, arriving
    along the cell edge), then the cell edge x = 3 (p = 6 - q) to the single road's far curb at q 5"""
    if q <= 3.5:
        return 3.0
    if q <= 4.0:
        t = (q - 3.5) / 0.5
        return 3.0 - 2.5 * t * t + 1.5 * t ** 3
    if q <= 5.0:
        return 6.0 - q
    return 1.0


ENDS = {
    # name: (continuation d's (one tuple: every claimed row; caps list each row), claimed rows, scene factory)
    "narrow-C": ((0, 1, 2), 2, lambda P: P.Narrow("C", 6.0 - L, 6.0)),
    "narrow-A": ((1, 2, 3), 0, lambda P: P.Narrow("A", 3.0 - L, 3.0)),
    "taper-0": ((0, 1), 2, lambda P: P.Taper(0, 3.5, lambda q: 0.0, _hi_taper_a, 5.0)),
    "taper-1": ((1, 2), 2, lambda P: P.Taper(1, 3.0 - L, lambda q: clamp01((q - (3.0 - L)) / L),
                                             lambda q: 3.0 - clamp01((q - (6.0 - L)) / L), 6.0)),
    "taper-2": ((2, 3), 1, lambda P: P.Taper(2, 0.0, lambda q: 2.0 * clamp01(q / 4.0), lambda q: 3.0, 4.0)),
    # all three end: the band's last row is full (square end) or followed by one row of d0..d2 (drags whose last
    # step is along x: each one's last cell is alone in its row)
    # the ending drags' single last cells past the last full row (drags whose last step is along x): one row more
    # for the closing carriageways, so a gentler curb
    "taper-0s": (((0, 1, 2), (0, 1)), 2, lambda P: P.Taper(0, 2.5, lambda q: 0.0,
                                                           lambda q: 3.0 - 2.0 * clamp01((q - 2.5) / 4.5), 7.0)),
    "taper-1s": (((0, 1, 2), (1, 2)), 2, lambda P: P.Taper(1, 5.0 - L, lambda q: clamp01((q - (5.0 - L)) / L),
                                                           lambda q: 3.0 - clamp01((q - (6.0 - L)) / L), 6.0)),
    "taper-2s": (((1, 2, 3), (2, 3)), 1, lambda P: P.Taper(2, 0.0, lambda q: 2.0 * clamp01(q / 6.0),
                                                           lambda q: 3.0, 6.0)),
    # all three end: the band's last row is full (square end), or followed by rows of the drags' last cells. Each
    # is the band closed by a straight curb along the cell edges the drags leave (z = Zm, x = Xm), corners rounded
    "cap-square": ((), 0, lambda P: P.Cap(0.0, [("z", 1.0)])),
    "cap-part": (((0, 1, 2),), 1, lambda P: P.Cap(0.5, [("z", 2.0), ("x", 4.0)])),
    "cap-x4z3": (((0, 1, 2), (0, 1)), 2, lambda P: P.Cap(0.5, [("z", 3.0), ("x", 4.0)])),
    "cap-x4z4": (((0, 1, 2), (0, 1), (0,)), 3, lambda P: P.Cap(0.5, [("z", 4.0), ("x", 4.0)])),
}


def cont_row(name, j):
    """the d offsets of continuation row j (1-based) of end `name`: one tuple for every row, or a tuple per row"""
    cont = ENDS[name][0]
    if cont and isinstance(cont[0], tuple):
        return cont[j - 1] if j <= len(cont) else (cont[-1] if not name.startswith("cap") else ())
    return cont


# ------------------------------------------------------------------------------------------------ scene helpers

class Shift:
    """a scene moved by whole cells (the 35 lattice: same art)"""

    def __init__(self, scene, dx, dz):
        self.scene, self.dx, self.dz = scene, dx, dz

    def colour(self, z, r, wx, wz):
        return self.scene.colour(z, r, wx - self.dx, wz - self.dz)

    def tree_points(self, cell):
        return [(wx + self.dx, wz + self.dz) for (wx, wz) in
                self.scene.tree_points((cell[0] - self.dx, cell[1] - self.dz))]


def end_scene(name, top=False, at=0):
    """the scene of end `name`; bottom end with its last full row at row `at`, or (top) the turned end whose first
    full row is row `at` (continuation above)"""
    from netmod import diagbv_paint as P
    sc = ENDS[name][2](P)
    if top:
        return Shift(P.Turned(sc), at + 1, at + 1)
    return Shift(sc, at, at)


def band_trees(scene_pm, q0, q1):
    from netmod import diagbv_paint as P
    return P.tree_points(scene_pm, q0, q1)


# ------------------------------------------------------------------------------------------------ fit

def footprint(cont, rows=6, top=-6):
    cells = set()
    for z in range(top, 1):
        cells |= {(z + d, z) for d in range(4)}
    for z in range(1, rows + 1):
        cells |= {(z + d, z) for d in cont}
    return cells


def coverage(scene, c, n=16, z=3, r=0):
    k = 0
    for i in range(n):
        for j in range(n):
            if scene.colour(z, r, c[0] + (i + 0.5) / n, c[1] + (j + 0.5) / n)[3]:
                k += 1
    return k / float(n * n)


def end_reference(name):
    """the art the cells past an end's claim show (their own pieces): a function (z, r, wx, wz) or None"""
    from netmod import diagave_paint as DP
    if name == "narrow-C":
        return lambda z, r, wx, wz: DP.StraightAvenue().colour(z, r, wx, wz)
    if name == "narrow-A":
        return lambda z, r, wx, wz: DP.StraightAvenue().colour(z, r, wx - 1.0, wz)
    if name.startswith("taper"):
        k = int(name[6])
        return lambda z, r, wx, wz: DP.diag(k, wx, wz, z, r)
    return None


def mismatch(scene, ref, c, n=16, z=3, r=0):
    """share of samples whose colour differs (the strip-edge pixel row of a single road counts ~0.06)"""
    from netmod import diagbv_paint as P
    k = 0
    with P.diagonal():
        for i in range(n):
            for j in range(n):
                wx, wz = c[0] + (i + 0.5) / n, c[1] + (j + 0.5) / n
                a, b = scene.colour(z, r, wx, wz), ref(z, r, wx, wz)
                if bool(a[3]) != bool(b[3]) or (a[3] and sum(abs(a[t] - b[t]) for t in range(3)) > 60):
                    k += 1
    return k / float(n * n)


def cmd_fit(a):
    from netmod import diagbv_paint as P
    for name, (cont, K, mk) in ENDS.items():
        sc = mk(P)
        F = end_footprint(name)
        bad = []
        with P.diagonal():
            for zz in range(-3, K + 1):
                for x in range(zz - 3, zz + 7):
                    c = (x, zz)
                    v = coverage(sc, c)
                    if c in F and v < 0.03:
                        bad.append("cell %s holds %.2f road" % (c, v))
                    if c not in F and v > 0.0:
                        bad.append("cell %s is not road but gets %.2f" % (c, v))
            ref = end_reference(name)
            for zz in range(K + 1, K + 3):                  # past the claim: the neighbour's own art
                for x in range(zz - 2, zz + 6):
                    if ref and (x, zz) in F:
                        m = mismatch(sc, ref, (x, zz))
                        if m > 0.08:
                            bad.append("cell %s past the claim differs from its own piece by %.2f" % ((x, zz), m))
        print("%-10s continuation d %s, claims %d row(s): %s" % (name, cont, K, "; ".join(bad) or "fits"))


# ------------------------------------------------------------------------------------------------ mockup

def paint_layout(cells, cache, zooms=(3, 4)):
    """cells: {(x, z): scene | ('piece', id, state) | ('dir', path, state)} -> render cells for boulevard.render; scenes
    are painted per cell into cache/<x>_<z>/ on the full tile (trees from scene.trees if given)"""
    from netmod import diagbv_paint as P
    from netmod import boulevard_paint as BP
    from netmod import netart
    out = []
    for (x, z), v in sorted(cells.items()):
        if isinstance(v, tuple):
            if v[0] == "piece":
                out.append({"x": x, "z": z, "piece": v[1], "state": v[2]})
            else:
                out.append({"x": x, "z": z, "dir": v[1], "state": v[2]})
            continue
        scene = v[0] if isinstance(v, list) else v
        d = os.path.join(cache, "%d_%d" % (x, z))
        anc = P.paint_cell(scene, (x, z), d, zooms=list(zooms))
        spots = list(trees_of(scene, (x, z), is_full(scene, (x, z)))) if hasattr(scene, "tree_points") else []
        if spots:
            for zz in zooms:
                for s in range(netart.ROTS):
                    im, ac = P.tree_layer(zz, s, spots)
                    im.save(os.path.join(d, netart.frame_name(zz, s, 1)))
                    anc[netart.frame_name(zz, s, 1)] = list(ac)
        json.dump(anc, open(os.path.join(d, "anchors.json"), "w"))
        out.append({"x": x, "z": z, "dir": d, "state": 0})
    return out


def lone_cells(road, cells):
    """stock pieces of lone staircases / straight roads for the plain road cells of a layout"""
    from netmod.diagave import LONE, _mask
    out = {}
    for c in road:
        if c in cells:
            continue
        m = _mask(c, road)
        if m in LONE:
            out[c] = ("piece",) + LONE[m]
        else:
            horiz = (c[0] - 1, c[1]) in road or (c[0] + 1, c[1]) in road
            out[c] = ("piece", 29, 0 if horiz else 1)
    return out


def layout_long():
    """single road A | taper (top end, keep A) | band | row road crossing | band | column road crossing | band |
    narrowing to the diagonal avenue (C ends) | diagonal avenue"""
    from netmod import diagbv_paint as P
    from netmod import diagave as DV
    band = P.Band()
    cells, road = {}, set()
    top, bot = -7, 11
    for z in range(top, bot + 1):
        road |= {(z + d, z) for d in range(4)}
    for z in range(top - 5, top):                       # the single road (strip A) above the top end
        road |= {(z, z), (z + 1, z)}
    for z in range(bot + 1, bot + 8):                   # the diagonal avenue below
        road |= {(z + d, z) for d in range(3)}
    jr, jc = -2, 6                                      # row road on row jr, column road on column jc
    road |= {(x, jr) for x in range(jr - 7, jr + 7)}
    road |= {(jc, z) for z in range(jc - 9, jc + 5)}
    tsc = end_scene("taper-2", top=True, at=top)
    bsc = end_scene("narrow-C", at=bot)
    rj = Shift(P.Junction(0, "both"), jr, jr)
    cj = Shift(P.Junction(1, "both"), jc, jc)
    ptrees = []
    for (x, z) in road:
        p = x - z
        if (z == jr and x < jr + 7) or (abs(z - jr) == 1 and 0 <= p <= 3):
            sc = rj
        elif x == jc or (abs(x - jc) == 1 and 0 <= p <= 3 and jc - 4 <= z <= jc + 1):
            sc = cj
        elif z <= top + 3:
            sc = tsc
        elif z >= bot - 2:
            sc = bsc
        elif 0 <= p <= 3:
            sc = band
        else:
            continue
        cells[(x, z)] = sc
    for c in cells:
        cells[c] = [cells[c], ptrees]
    dav = os.path.join(HERE, "examples", "diagonal_avenue", "art")
    for z in range(bot + 3, bot + 8):                   # past the claim: the diagonal avenue's own pieces
        cells[(z, z)] = ("dir", os.path.join(dav, "20505"), 2)
        cells[(z + 1, z)] = ("dir", os.path.join(dav, "20500"), 0)
        cells[(z + 2, z)] = ("dir", os.path.join(dav, "20505"), 0)
    cells.update(lone_cells(road, cells))
    return cells, road


def layout_bend():
    """taper to the middle road (top end) | band | T from the C side (row road) | band | bend into the straight
    boulevard (bottom end, along x)"""
    from netmod import diagbv_paint as P
    from netmod import boulevard as BV
    band = P.Band()
    cells, road = {}, set()
    top, M = -6, 6                                      # the straight rows are M, M + 1, M + 2; joint at x = M + 3
    for z in range(top, M):
        road |= {(z + d, z) for d in range(4)}
    road |= {(M, M), (M + 1, M), (M + 2, M), (M + 1, M + 1), (M + 2, M + 1), (M + 2, M + 2)}
    for z in range(top - 5, top):
        road |= {(z + 1, z), (z + 2, z)}                # the middle road above the top end
    jr = 0
    road |= {(x, jr) for x in range(jr + 4, jr + 9)}    # a T from the C side (east)
    tsc = end_scene("taper-1", top=True, at=top)
    rj = Shift(P.Junction(0, "C"), jr, jr)
    ptrees = []
    for (x, z) in road:
        p = x - z
        if z == jr or (abs(z - jr) == 1 and 0 <= p <= 3):
            sc = rj
        elif z <= top + 3:
            sc = tsc
        elif 0 <= p <= 3:
            sc = band
        else:
            continue
        cells[(x, z)] = sc
    for c in cells:
        cells[c] = [cells[c], ptrees]
    pack = os.path.join(HERE, "examples", "boulevard")
    for x in range(M + 3, M + 9):                       # the straight boulevard (task boulevard's pieces)
        cells[(x, M)] = ("dir", BV.art(pack, BV.OUTER), 2)
        cells[(x, M + 1)] = ("dir", BV.art(pack, BV.MIDDLE), 0)
        cells[(x, M + 2)] = ("dir", BV.art(pack, BV.OUTER), 0)
        road |= {(x, M), (x, M + 1), (x, M + 2)}
    cells.update(lone_cells(road, cells))
    return cells, road


def layout_stock():
    """three joined diagonals as the stock tiler places them (tiler.py, 2026-10-17): 11203 / 43 / 43 / 11203"""
    cells = {}
    for z in range(0, 7):
        for d, (pid, st) in enumerate(((11203, 2), (43, 0), (43, 0), (11203, 0))):
            cells[(z + d, z)] = ("piece", pid, st)
    return cells


def cmd_plan_pieces(a):
    pieces, stamps = plan_pieces()
    for p in pieces:
        print("  %d  base %d  %s%s%s" % (p["id"], p["base"], p["note"], "" if p["full"] else "  (partial tile)",
                                        "  trees %d" % len(p["trees"]) if p["trees"] else ""))
    print("%d pieces" % len(pieces))


def cmd_mockup(a):
    from PIL import Image, ImageDraw
    from netmod import boulevard as BV
    cache = a.cache or os.path.join(os.path.dirname(os.path.abspath(a.out)), "diagbv_mockup_cache")
    shots = []
    for name, fn, note in (("long", layout_long, "taper to road A (top) | row road crossing | column road crossing | "
                                                  "narrowing to the diagonal avenue (bottom)"),
                           ("bend", layout_bend, "taper to the middle road (top) | T from the east | bend into the "
                                                 "straight boulevard (bottom)")):
        cells, _road = fn()
        rc = paint_layout(cells, os.path.join(cache, name))
        for z, r in ((4, 0), (3, 1)):
            shots.append(("%s, zoom %d, view %d" % (note, z, r), BV.render(rc, z, r)))
    st = [{"x": x, "z": z, "piece": v[1], "state": v[2]} for (x, z), v in layout_stock().items()]
    shots.append(("stock today: three joined diagonal drags, zoom 3, view 0", BV.render(st, 3, 0)))
    W = max(im.width for _, im in shots)
    H = sum(im.height + 24 for _, im in shots)
    sheet = Image.new("RGB", (W, H), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    y = 0
    for title, im in shots:
        d.text((6, y + 5), title, fill=(230, 230, 230))
        sheet.paste(im.convert("RGB"), (0, y + 24))
        y += im.height + 24
    sheet.save(a.out)
    print(a.out, sheet.size)

# ------------------------------------------------------------------------------------------------ the rule (twin)
# Axis 1 is axis 0 turned one state: a real cell is rot1(canonical cell), its piece state + 1. Stamps (the cells a
# junction or an end writes) are kept in a frame relative to a reference cell: 'row' = (x - a, z - zr) from a band
# row's left cell (junction rows, ends: the band's last full row), 'col' = (x - x0, z - zr) from the cell where a
# column road is that row's d0. The turned stamp (the other side of a T, the top end) is the stamp turned half a
# circle: row (dx, dz) -> (3 - dx, -dz), col -> (-dx, -3 - dz), state + 2.

MIN_CLEAN = 3                     # clean band rows (nothing beside them) a band needs, as DAV's MIN_ROWS
PIECE_BASE = 20950


def rot1(c):
    return (-c[1] - 1, c[0])


def unrot1(c):
    return (c[1], -c[0] - 1)


def to_real(axis, c):
    return rot1(c) if axis else c


def to_canon(axis, c):
    return unrot1(c) if axis else c


def turn_rel(fam, dx, dz):
    return (3 - dx, -dz) if fam == "row" else (-dx, -3 - dz)


def _band_rows(z0, z1):
    return {(z + d, z) for z in range(z0, z1 + 1) for d in range(4)}


JUNCTIONS = {
    # kind: (family, scene factory, canonical footprint)
    "jrow-both": ("row", lambda P: P.Junction(0, "both"),
                  lambda: _band_rows(-6, 6) | {(x, 0) for x in range(-6, 10)}),
    "jrow-A": ("row", lambda P: P.Junction(0, "A"), lambda: _band_rows(-6, 6) | {(x, 0) for x in range(-6, 4)}),
    "jrow-stem": ("row", lambda P: P.Junction(0, "stem-after"),
                  lambda: _band_rows(-6, 0) | {(x, 0) for x in range(-6, 10)}),
    "jcol-both": ("col", lambda P: P.Junction(1, "both"), lambda: _band_rows(-9, 6) | {(0, z) for z in range(-9, 7)}),
    "jcol-A": ("col", lambda P: P.Junction(1, "A"), lambda: _band_rows(-9, 6) | {(0, z) for z in range(-3, 7)}),
}
WINDOW = {"row": (-3, 3), "col": (-7, 4)}       # rows of a junction stamp that may differ from the band


def end_footprint(name):
    cells = _band_rows(-6, 0)
    for z in range(1, 7):
        cells |= {(z + d, z) for d in cont_row(name, z)}
    return cells


def junction_arms(kind):
    """canonical arm cells of a junction kind (straight road 29 the rule writes beside the band) -> {cell: o}"""
    fam = JUNCTIONS[kind][0]
    if fam == "row":
        out = {(-1, 0): 0, (-2, 0): 0}
        if kind != "jrow-A":
            out.update({(4, 0): 0, (5, 0): 0})
        return out
    out = {(0, 1): 1, (0, 2): 1}
    if kind == "jcol-both":
        out.update({(0, -4): 1, (0, -5): 1})
    return out


def _arms_at(kind, ref, turned):
    fam = JUNCTIONS[kind][0]
    out = {}
    for (dx, dz), o in junction_arms(kind).items():
        if turned:
            dx, dz = turn_rel(fam, dx, dz)
        out[(ref[0] + dx, ref[1] + dz)] = o
    return out


def bands(road, stamps=None):
    """road: set of real ROAD cells -> [{axis, rows, ok, why, want: {real cell: (piece, state)}, claims: set}].
    stamps: the package's table {kind: [(dx, dz, piece, state)], 'band': (outer, inner)}; None = cells only (pieces
    0.0), for footprint checks before a build."""
    out = []
    for axis in (0, 1):
        R = {to_canon(axis, c) for c in road}
        full = lambda a, z: all((a + d, z) in R for d in range(4))       # noqa: E731
        seen = set()
        for (x0, z0) in sorted(R, key=lambda c: (c[1], c[0])):
            if (x0, z0) in seen or not full(x0, z0) or full(x0 - 1, z0 - 1):
                continue
            chain = [(z0, x0)]
            while full(chain[-1][1] + 1, chain[-1][0] + 1):
                chain.append((chain[-1][0] + 1, chain[-1][1] + 1))
            seen.update((a, z) for (z, a) in chain)
            clean = [(a - 1, z) not in R and (a + 4, z) not in R for (z, a) in chain]
            if sum(clean) < MIN_CLEAN:
                continue
            b = _one_band(R, chain, stamps)
            b["axis"] = axis
            b["rows"] = list(chain)
            b["want"] = {to_real(axis, c): (pc, (st + axis) % 4) for c, (pc, st) in b["want"].items()}
            b["claims"] = {to_real(axis, c) for c in b["claims"]}
            out.append(b)
    return out


DAV_BAND_OK = None      # task bvlanes: twin of sc3netmod's dav_band_ok(canonical cell) -> bool; None = assume it converts


def _dav_ok(c):
    return DAV_BAND_OK is None or bool(DAV_BAND_OK(c))


def classify_end(R, z_e, a_e, e, nrows):
    """end e (1 bottom = the chain's last row, 0 top = its first row, turned) -> (kind or None, cell function)"""
    def cell(dx, dz):                     # bottom-oriented coordinates of this end -> canonical cell
        return (a_e + dx, z_e + dz) if e else (a_e + 3 - dx, z_e - dz)

    rd = lambda dx, dz: cell(dx, dz) in R                           # noqa: E731
    if nrows >= 3 + MIN_CLEAN and all(rd(4, dz) and rd(5, dz) for dz in (-2, -1, 0)) and \
            not any(rd(dz - 1, dz) for dz in (-2, -1, 0)) and not rd(1, -3) and \
            not any(rd(dx, 1) for dx in range(-1, 7)):
        return "bend-x", cell
    rr = [tuple(d for d in range(-2, 7) if rd(j + d, j)) for j in range(1, 7)]
    r1, r2, r3, r4 = rr[:4]
    if r1 == (0, 1, 2) and r2 == (-1, 0, 1):
        return "bend-z", cell
    if all(r == (0, 1, 2) for r in rr[:5]):                         # DAV gets at least 3 rows past the claim
        return ("narrow-C" if _dav_ok(cell(3, 3)) else None), cell   # task bvlanes: the avenue must convert
    if all(r == (1, 2, 3) for r in rr[:3]):
        return ("narrow-A" if _dav_ok(cell(2, 1)) else None), cell
    if r1 == r2 and r1 in ((0, 1), (1, 2), (2, 3)):
        return "taper-%d" % r1[0], cell
    if (r1, r2) == ((0, 1, 2), (0, 1)) and r3 == (0, 1):
        return "taper-0s", cell
    if (r1, r2, r3) == ((0, 1, 2), (1, 2), (1, 2)):
        return "taper-1s", cell
    if (r1, r2) == ((1, 2, 3), (2, 3)) and r3 == (2, 3):
        return "taper-2s", cell
    if r1 == () and rd(-1, 0) and rd(4, 0):
        return "stem", cell
    if rd(-1, 0) or rd(4, 0):
        return None, cell
    for name in ("cap-square", "cap-part", "cap-x4z3", "cap-x4z4"):    # task avrbtfix: stamp rows + 1 empty row
        if all(r == cont_row(name, j + 1) for j, r in enumerate(rr[:len(ENDS[name][0]) + 1])):
            return name, cell
    return "ragged", cell                 # task avrbtfix: the band converts, this end's rows stay stock (was None)


def _one_band(R, chain, stamps):
    """the rule on one anchored chain in canonical coordinates"""
    n = len(chain)
    why = ""
    band, dcell = set(), {}               # band cells (default pieces by d)
    for (z, a) in chain:
        for d in range(4):
            band.add((a + d, z))
            dcell[(a + d, z)] = d
    rowleft = {z: a for (z, a) in chain}
    outside = lambda c: c in R and c not in band                    # noqa: E731
    uses, arms, path = [], {}, set()      # (kind, ref, turned); canonical arm cell -> o; road owned elsewhere
    ends, endrows = {}, set()
    for e in (1, 0):
        z_e, a_e = chain[-1] if e else chain[0]
        kind, cell = classify_end(R, z_e, a_e, e, n)
        ends[e] = kind
        if kind is None:
            why = why or "%s end: the roads past the band are not an end this package knows" % ("bottom" if e else "top")
            continue
        sgn = 1 if e else -1
        if kind == "bend-x":
            for dz in (-2, -1, 0):
                endrows.add(z_e + sgn * dz)
                for dx in range(dz, dz + 4):
                    if dx >= 1:                                       # the straight cells: the straight boulevard's
                        band.discard(cell(dx, dz))
                        dcell.pop(cell(dx, dz), None)
                for dx in range(1, 128):
                    if not (cell(dx, dz) in R):
                        break
                    path.add(cell(dx, dz))
        elif kind == "bend-z":
            for j in range(1, 128):
                cs = [cell(dx, j) for dx in (1, 2, 3) if cell(dx, j) in R]
                if not cs:
                    break
                path |= set(cs)
        elif kind == "ragged":                                          # task avrbtfix: rows past it stay stock
            endrows.add(z_e)
            for j in (1, 2):
                for dx in range(-2, j + 6):
                    if cell(dx, j) in R:
                        path.add(cell(dx, j))
        elif kind == "stem":
            endrows.add(z_e)
            uses.append(("jrow-stem", (a_e, z_e), not e))
            arms.update(_arms_at("jrow-stem", (a_e, z_e), not e))
        else:
            uses.append((kind, (a_e, z_e), not e))
            depth = 1 - min([dz for (_dx, dz, _p, _s) in (stamps or {}).get(kind, [])] or [-2])
            endrows |= {z_e - sgn * k for k in range(0, max(1, depth))}
            _cont, K, _mk = ENDS[kind]
            for j in range(1, K + 1):
                for d in cont_row(kind, j):
                    if cell(j + d, j) in R:
                        path.add(cell(j + d, j))                     # written by the end's stamp
            for j in range(K + 1, K + 3):                             # the avenue / single road going on
                for d in range(-1, 5):
                    if cell(j + d, j) in R:
                        path.add(cell(j + d, j))
    # ---- junctions inside the chain: row roads (W / E arms), then column roads (N arm at a row's d3, S at its d0)
    for (z, a) in chain:
        if z in endrows:
            continue
        w, east = (a - 1, z) in R, (a + 4, z) in R
        rw = w and (a - 2, z) in R and not any(outside(c) for c in ((a - 1, z + 1), (a - 2, z + 1), (a - 2, z - 1)))
        re_ = east and (a + 5, z) in R and not any(outside(c) for c in ((a + 4, z - 1), (a + 5, z - 1), (a + 5, z + 1)))
        if (w and not rw) or (east and not re_) or not (w or east):
            continue                                                  # none, or a column road's arm (below)
        kind, turned = ("jrow-both", False) if (w and east) else ("jrow-A", bool(east))
        uses.append((kind, (a, z), turned))
        arms.update(_arms_at(kind, (a, z), turned))
    for (z, a) in chain:
        x0 = a + 3
        if z in endrows or (x0, z - 1) not in R or (x0, z - 1) in arms or (x0, z - 1) in path:
            continue
        straight = (x0, z - 2) in R and not any(outside(c) for c in ((x0 + 1, z - 1), (x0 + 1, z - 2), (x0 - 1, z - 2)))
        if not straight:
            why = why or "road above the band at canonical (%d,%d) is not a straight single road" % (x0, z - 1)
            continue
        zl = z + 3
        south = rowleft.get(zl) == x0 and (x0, zl + 1) in R and (x0, zl + 2) in R and \
            not any(outside(c) for c in ((x0 - 1, zl + 1), (x0 - 1, zl + 2), (x0 + 1, zl + 2)))
        if any(zz in endrows or zz not in rowleft for zz in range(z, z + 4)):
            why = why or "a column road inside an end"
            continue
        kind, turned = ("jcol-both", False) if south else ("jcol-A", True)    # N only: the turned (south) T
        uses.append((kind, (x0, zl), turned))
        arms.update(_arms_at(kind, (x0, zl), turned))
    for (z, a) in chain:
        x0 = a
        if z in endrows or (x0, z + 1) not in R or (x0, z + 1) in arms or (x0, z + 1) in path or                 any(u[1] == (x0, z) for u in uses):
            continue
        if not ((x0, z + 2) in R and not any(outside(c) for c in ((x0 - 1, z + 1), (x0 - 1, z + 2), (x0 + 1, z + 2)))):
            why = why or "road below the band at canonical (%d,%d) is not a straight single road" % (x0, z + 1)
            continue
        if any(zz in endrows or zz not in rowleft for zz in range(z - 3, z + 1)):
            why = why or "a column road inside an end"
            continue
        uses.append(("jcol-A", (x0, z), False))
        arms.update(_arms_at("jcol-A", (x0, z), False))
    # ---- clean rows (anchor) besides junction and end rows
    jrows = set()
    for kind, ref, turned in uses:
        if kind.startswith("jrow"):
            jrows.add(ref[1])
        elif kind.startswith("jcol"):
            jrows |= {ref[1] - 3 + i for i in range(4)}
    nclean = sum(1 for (z, a) in chain if z not in jrows and z not in endrows and
                 (a - 1, z) not in R and (a + 4, z) not in R)
    if not why and nclean < MIN_CLEAN:
        why = "fewer than %d clean rows" % MIN_CLEAN
    # ---- pieces: the band by d, then each use's stamp (overlaps refused), then the arms
    want, owner = {}, {}
    o_, i_ = (stamps or {}).get("band", (0, 0))
    for c in band:
        want[c] = ((o_, 2), (i_, 2), (i_, 0), (o_, 0))[dcell[c]]
    for kind, ref, turned in uses:
        fam = JUNCTIONS[kind][0] if kind in JUNCTIONS else "row"
        if stamps is None:
            continue
        if kind not in stamps:
            why = why or "no %s pieces declared" % kind
            continue
        for (dx, dz, pc, st) in stamps[kind]:
            if turned:
                dx, dz = turn_rel(fam, dx, dz)
                st = (st + 2) % 4
            c = (ref[0] + dx, ref[1] + dz)
            if c in owner and owner[c] != (kind, ref):
                why = why or "junctions or ends too close together at canonical %s" % (c,)
            owner[c] = (kind, ref)
            if c not in R:
                why = why or "a %s cell, canonical %s, is not road" % (kind, c)
            want[c] = (pc, st)
    for c, o in arms.items():
        if c in band or c in owner:
            why = why or "an arm cell, canonical %s, inside the band" % (c,)
        want[c] = (29, o)
    # ---- isolated: nothing else touches the band or the cells it writes
    mine = set(want) | band
    for c in list(mine):
        if c in arms:
            continue
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                q = (c[0] + dx, c[1] + dz)
                if q in R and q not in mine and q not in path and q not in arms:
                    why = why or "touches road at canonical %s" % (q,)
    if why:
        return {"ok": False, "why": why, "want": {}, "claims": set(), "uses": uses, "ends": ends}
    return {"ok": True, "why": "", "want": want, "claims": set(want), "uses": uses, "ends": ends}


# ------------------------------------------------------------------------------------------------ pieces
# Every piece is one cell of a scene. A stamp cell whose art equals the band's at that place keeps the band piece;
# one whose art equals an existing piece (also turned half a circle) reuses it; else it is a new piece. Art is
# compared on a sample of each cell (zoom 3 and 4, views 0 and 1) plus its trees and its base.

KIND_NO = {"jrow-both": 1, "jrow-A": 2, "jrow-stem": 3, "jcol-both": 4, "jcol-A": 5, "narrow-C": 6, "narrow-A": 7,
           "taper-0": 8, "taper-1": 9, "taper-2": 10, "cap-square": 11, "cap-part": 12, "taper-0s": 13,
           "taper-1s": 14, "taper-2s": 15, "cap-x4z3": 16, "cap-x4z4": 17}
GRID = 10


def kind_scene(kind):
    from netmod import diagbv_paint as P
    if kind in JUNCTIONS:
        return JUNCTIONS[kind][1](P)
    return ENDS[kind][2](P)


def candidates(kind):
    """canonical cells a use of this kind may write: (cell, base, in a band row with d / None)"""
    out = []
    if kind in JUNCTIONS:
        fam, _mk, foot = JUNCTIONS[kind]
        F = foot()
        lo, hi = WINDOW[fam]
        if kind == "jrow-stem":
            hi = 0
        arms = junction_arms(kind)
        for (x, z) in sorted(F, key=lambda c: (c[1], c[0])):
            if not (lo <= z <= hi) or (x, z) in arms:
                continue
            d = x - z
            if not 0 <= d <= 3:
                continue                                    # road strip beyond the band: arms / stock 29
            road_cell = (z == 0) if fam == "row" else (x == 0)
            out.append(((x, z), 43 if road_cell or d in (1, 2) else 35, d))
        return out
    _cont, K, _mk = ENDS[kind]
    F = end_footprint(kind)
    for (x, z) in sorted(F, key=lambda c: (c[1], c[0])):
        if not -6 <= z <= K:
            continue
        d = x - z
        if z <= 0:
            out.append(((x, z), 43 if d in (1, 2) else 35, d))
        else:
            row = cont_row(kind, z)
            out.append(((x, z), 35 if len(row) <= 2 or d in (row[0], row[-1]) else 43, None))
    return out


def cell_sig(scene, cell, turned=False):
    from netmod import diagbv_paint as P
    X, Z = cell
    out = []
    with P.diagonal():
        for z in (3, 4):
            for r in (0, 1):
                for i in range(GRID):
                    for j in range(GRID):
                        lx, lz = (i + 0.5) / GRID, (j + 0.5) / GRID
                        if turned:
                            c = scene.colour(z, (r + 2) % 4, X + 1.0 - lx, Z + 1.0 - lz)
                        else:
                            c = scene.colour(z, r, X + lx, Z + lz)
                        out.append(tuple(c))
    return tuple(out)


def is_full(scene, cell, n=16):
    from netmod import diagbv_paint as P
    X, Z = cell
    with P.diagonal():
        for i in range(n):
            for j in range(n):
                if not scene.colour(4, 0, X + (i + 0.5) / n, Z + (j + 0.5) / n)[3]:
                    return False
    return True


def trees_of(scene, cell, full):
    """tree spots of a cell as lane points (x, zl, which tree) when its frames cover the tile"""
    if not full:
        return ()
    X, Z = cell
    return tuple(sorted((round((wx - X) * 256.0, 1), round((wz - Z) * 256.0, 1), int(round(2 * (wx + wz))) % 4 // 2)
                        for (wx, wz) in scene.tree_points(cell)))


def turn_trees(trees):
    return tuple(sorted((round(256.0 - x, 1), round(256.0 - zl, 1), k) for (x, zl, k) in trees))


def plan_pieces(log=print):
    """-> (pieces [dict], stamps {kind: [(dx, dz, piece, state)], 'band': (outer, inner)})"""
    from netmod import diagbv_paint as P
    pieces = []
    band = P.Band()

    def new(scene, cell, base, note, canvas=None, kind=None):
        full = is_full(scene, cell)
        trees = trees_of(scene, cell, full)
        p = {"id": PIECE_BASE + len(pieces), "scene": scene, "cell": cell, "base": base, "note": note,
             "canvas": canvas, "full": full, "trees": trees, "kind": kind,
             "sig0": cell_sig(scene, cell) + (trees, base), "sig2": cell_sig(scene, cell, True) + (turn_trees(trees), base)}
        pieces.append(p)
        return p

    out_p = new(band, (3, 0), 35, "band, outer cell (d3; d0 = turned)", canvas=(35, 0), kind="band")
    inn_p = new(band, (2, 0), 43, "band, inner cell (d2; d1 = turned)", kind="band")
    stamps = {"band": (out_p["id"], inn_p["id"])}
    for kind in KIND_NO:
        sc = kind_scene(kind)
        rows = []
        for cell, base, d in candidates(kind):
            full = is_full(sc, cell)
            s0 = cell_sig(sc, cell) + (trees_of(sc, cell, full), base)
            if d is not None and cell[1] <= (0 if kind in ENDS else 99):
                bfull = is_full(band, cell)
                b0 = cell_sig(band, cell) + (trees_of(band, cell, bfull), 43 if d in (1, 2) else 35)
                if s0 == b0:
                    continue                                    # the band piece already there
            hit = None
            for p in pieces:
                if s0 == p["sig0"]:
                    hit = (p["id"], 0)
                    break
                if s0 == p["sig2"]:
                    hit = (p["id"], 2)
                    break
            if hit is None:
                p = new(sc, cell, base, "%s cell %s" % (kind, cell), kind=kind)
                hit = (p["id"], 0)
            rows.append((cell[0], cell[1]) + hit)
        stamps[kind] = rows
        log("%-10s %2d cell(s), pieces so far %d" % (kind, len(rows), len(pieces)))
    return pieces, stamps



# ------------------------------------------------------------------------------------------------ offline checks

def three_drags(n_a, n_b, n_c, sx=1, first="x", offs=((0, 0), (1, 0), (2, 0)), firsts=None, z0=0):
    """three diagonal drags of n_a / n_b / n_c steps from the offset cells (x by sx per step)"""
    from netmod.diagave import drag
    firsts = firsts or (first, first, first)
    cells = set()
    for (ox, oz), n, f in zip(offs, (n_a, n_b, n_c), firsts):
        if n:
            cells |= set(drag(ox * sx, oz + z0, n, sx, f))
    return cells


def check_cases():
    """(name, road, expect DBV ok, expect DAV ok, end kinds wanted {bottom, top} or None)"""
    cases = []
    for sx in (1, -1):
        ax = 0 if sx > 0 else 1
        # the gesture both diagonal rules expect: each drag one cell over along x (axis 0) / one cell up (axis 1)
        offs = ((0, 0), (1, 0), (2, 0)) if ax == 0 else ((0, 0), (0, -1), (0, -2))

        def three(n_a, n_b, n_c, sx, f, offs=offs):
            return three_drags(n_a, n_b, n_c, sx, f, offs)
        for f in "xz":
            cases.append(("staggered gesture (other offset), first %s, axis %d" % (f, ax),
                          three_drags(9, 9, 9, sx, f, ((0, 0), (0, -1), (0, -2)) if ax == 0 else ((0, 0), (1, 0), (2, 0))),
                          None, False, None))
            cases.append(("three equal, first %s, axis %d" % (f, ax), three(8, 8, 8, sx, f), True, False, None))
            cases.append(("C shorter by 7, first %s, axis %d" % (f, ax), three(16, 16, 9, sx, f), True, True, None))
            cases.append(("A shorter by 7, first %s, axis %d" % (f, ax), three(9, 16, 16, sx, f), True, True, None))
            cases.append(("B and C shorter, first %s, axis %d" % (f, ax), three(13, 9, 9, sx, f), True, False, None))
            cases.append(("A and B shorter, first %s, axis %d" % (f, ax), three(9, 9, 13, sx, f), True, False, None))
            cases.append(("A and C shorter, first %s, axis %d" % (f, ax), three(9, 13, 9, sx, f), True, False, None))
            cases.append(("two drags joined (DAV), first %s, axis %d" % (f, ax),
                          three(8, 8, 0, sx, f), False, True, None))
            cases.append(("two drags two apart, first %s, axis %d" % (f, ax),
                          three(8, 0, 8, sx, f), None, False, None))
            base = three(13, 13, 13, sx, f)
            zs = sorted({z for _, z in base})
            zm = zs[len(zs) // 2]
            xs = sorted(x for x, z in base if z == zm)
            cases.append(("row road crossing, first %s, axis %d" % (f, ax),
                          base | {(x, zm) for x in range(xs[0] - 5, xs[-1] + 6)}, True, False, None))
            cases.append(("row road T from the left, first %s, axis %d" % (f, ax),
                          base | {(x, zm) for x in range(xs[0] - 5, xs[0])}, True, False, None))
            cases.append(("row road T from the right, first %s, axis %d" % (f, ax),
                          base | {(x, zm) for x in range(xs[-1] + 1, xs[-1] + 6)}, True, False, None))
            xm = xs[1]
            colz = sorted(z for x, z in base if x == xm)
            cases.append(("column road crossing, first %s, axis %d" % (f, ax),
                          base | {(xm, z) for z in range(colz[0] - 5, colz[-1] + 6)}, True, False, None))
            cases.append(("column road T from above, first %s, axis %d" % (f, ax),
                          base | {(xm, z) for z in range(colz[0] - 5, colz[0])}, True, False, None))
            cases.append(("column road T from below, first %s, axis %d" % (f, ax),
                          base | {(xm, z) for z in range(colz[-1] + 1, colz[-1] + 6)}, True, False, None))
            zl = zs[-1]
            xl = sorted(x for x, z in base if z == zl)
            cases.append(("band ending on a row road, first %s, axis %d" % (f, ax),
                          base | {(x, zl) for x in range(xl[0] - 6, xl[-1] + 7)}, ax == 0, False, None))
    # three parallel straight roads (BV), an avenue (11204), a 3x3 block: never DBV
    cases.append(("three straight roads", {(x, z) for x in range(10) for z in range(3)}, False, False, None))
    cases.append(("four straight roads", {(x, z) for x in range(10) for z in range(4)}, False, False, None))
    cases.append(("4x4 block", {(x, z) for x in range(4) for z in range(4)}, False, False, None))
    # bends into the straight boulevard (bottom end along x / along z; top ends turned)
    bx = _band_rows(-8, 5) | {(6, 6), (7, 6), (8, 6), (7, 7), (8, 7), (8, 8)} | \
        {(x, z) for x in range(9, 16) for z in (6, 7, 8)}
    cases.append(("bend along x (bottom)", bx, True, False, None))
    bz = _band_rows(-8, 5) | {(x, z) for x in (6, 7, 8) for z in range(6, 13)}
    cases.append(("bend along z (bottom)", bz, True, False, None))
    tb = {(2 - x, -1 - z) for (x, z) in bx}
    cases.append(("bend along x (top, turned)", tb, True, False, None))
    return cases


def cmd_check(a):
    """the twin on drag footprints, run as in the game: DBV first, then DAV's and BV's twins with DBV's claims. Does
    each convert as expected, and does no cell belong to two blocks"""
    from netmod import diagave as DV
    from netmod import boulevard as BV
    _pieces, stamps = plan_pieces(log=lambda *x: None) if not a.no_stamps else (None, None)
    bad = 0
    for name, road, exp, exp_dav, _ends in check_cases():
        bs = bands(road, stamps)
        ok = [b for b in bs if b["ok"]]
        dbv_cells = set().union(*[b["claims"] for b in ok]) if ok else set()
        dav = [b for b in DV.bands(road, dbv_cells) if DV.wanted(b)]
        dav_cells = set().union(*[set(DV.wanted(b)) for b in dav]) if dav else set()
        bvr = [r for r in BV.runs(road, claimed=dbv_cells) if r["ok"]]
        bv_cells = set().union(*[set(r["want"]) for r in bvr]) if bvr else set()
        both = (dbv_cells & (dav_cells | bv_cells)) | (dav_cells & bv_cells)
        flag = (exp is not None and bool(ok) != exp) or (exp_dav is not None and bool(dav) != exp_dav) or both
        bad += bool(flag)
        print("%-4s %-46s DBV %s%s | DAV %s | BV %s%s" % ("BAD" if flag else "ok", name,
              "converts %s" % [(b["axis"], b["ends"]) for b in ok] if ok else
              "no (%s)" % "; ".join(b["why"] for b in bs) if bs else "no band",
              "" if not ok else " %d cells" % len(dbv_cells),
              "converts" if dav else "no", "converts" if bvr else "no", " OVERLAP %d" % len(both) if both else ""))
    print("%d case(s) off" % bad)


# ------------------------------------------------------------------------------------------------ build

VERSION = "0.1.0"


def art_table(pc):
    """the stock piece whose frame table a piece takes: the band's outer cell = 35 (stock frame size, ground under, as
    DAV's 20505); a cell whose frames cover the tile = 11204 with trees (two layers), 43 without; else 35 (ground is
    drawn under it: no cyan at zoom 3)"""
    if pc["canvas"] == (35, 0):
        return 35
    if pc["full"]:
        return 11204 if pc["trees"] else 43
    return 35


def cmd_build(a):
    """art/<id>/ for every piece, the inner piece's lane spec, manifest.json"""
    from netmod import diagbv_paint as P
    from netmod import netart
    from netmod.diagave import parts_spec
    pieces, stamps = plan_pieces()
    zooms = [int(v) for v in a.zooms.split(",")] if a.zooms else list(range(netart.ZOOMS))
    only = set(int(v) for v in a.only.split(",")) if a.only else None
    for pc in pieces:
        if only and pc["id"] not in only:
            continue
        d = os.path.join(a.pack, "art", str(pc["id"]))
        anc = P.paint_cell(pc["scene"], pc["cell"], d, canvas=pc["canvas"], zooms=zooms)
        for z in zooms:
            for st in range(netart.ROTS):
                fn = os.path.join(d, netart.frame_name(z, st, 1))
                if pc["trees"] and art_table(pc) == 11204:
                    im, ac = P.tree_layer(z, st, list(pc["trees"]))
                    im.save(fn)
                    anc[netart.frame_name(z, st, 1)] = list(ac)
                elif os.path.exists(fn):
                    os.remove(fn)
        anc["_"] = "diagbv.py build: %s" % pc["note"]
        json.dump(anc, open(os.path.join(d, "anchors.json"), "w"), indent=1)
        print("built %d (%s)" % (pc["id"], pc["note"]))
    write_manifest(a.pack, pieces, stamps)


def write_manifest(pack, pieces, stamps):
    from netmod.diagave import parts_spec
    variants, lanes = [], []
    inner = stamps["band"][1]
    for pc in pieces:
        variants.append({"id": pc["id"], "base": pc["base"], "network": "ROAD",
                         "name": {"*": "Diagonal boulevard", "ENGLISH": "Diagonal boulevard"},
                         "art": {"from": art_table(pc), "png_dir": "art/%d" % pc["id"]},
                         "trblkatt": "copy_base"})
    # the inner band cell holds one carriageway (C's half of the d2 cell: 35 at state 2) and the median: own lanes
    spec = parts_spec([(35, 2)], inner, "inner band cell: the carriageway half of 35 (state 2); the rest is median")
    json.dump(spec, open(os.path.join(pack, "dbv_%d.lanes.json" % inner), "w", newline="\n"), indent=1)
    for v in variants:
        if v["id"] == inner:
            v["trblkatt"] = "none"
    lanes.append({"piece": inner, "spec": "dbv_%d.lanes.json" % inner})
    man = {"netpack": 1, "name": "diagonal_boulevard", "version": VERSION, "author": "netmod (task diagbv)",
           "description": "Diagonal boulevards: draw three diagonal roads joined side by side (each one cell over: "
                          "along x on the down-right diagonal, one cell up on the other) and sc3netmod's DBV block makes "
                          "them one 3-wide boulevard, the straight boulevard's cross-section turned 45 degrees: the "
                          "outer roads are the carriageways, the middle one gives each an extra lane and holds a grass "
                          "median with avenue 11204's trees. Straight single roads crossing it, meeting it from one side "
                          "or closing its end get junctions with crosswalks; it narrows into the diagonal avenue or "
                          "tapers into one of its three roads, closes with a round curb where all three stop, and turns "
                          "into the straight boulevard where its drags go on straight. Lane lines are white dashes. "
                          "Built by `diagbv.py build .` in this folder before install (art/ is made from the game's "
                          "frames and is not shipped). Needs sc3netmod.dll with the DBV block.",
           "game": {"Apps/SIMNTWRK.DLL": "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"},
           "variants": variants, "lanes": lanes,
           "auto_diagonal_boulevards": [{"band": list(stamps["band"]),
                                         "stamps": {k: [list(c) for c in v] for k, v in stamps.items() if k != "band"}}]}
    json.dump(man, open(os.path.join(pack, "manifest.json"), "w", newline="\n"), indent=1)
    print("manifest: %d variants (%d..%d), %d lane spec(s)" % (len(variants), pieces[0]["id"], pieces[-1]["id"], len(lanes)))


def load_stamps(pack):
    """the package's DBV table from its manifest -> stamps for bands()"""
    man = json.load(open(os.path.join(pack, "manifest.json")))
    a = man["auto_diagonal_boulevards"][0]
    out = {k: [tuple(c) for c in v] for k, v in a["stamps"].items()}
    out["band"] = tuple(a["band"])
    return out


PACK = os.path.join(HERE, "examples", "diagonal_boulevard")


def road_of_save(save):
    """ROAD cells of a save (stock road pieces and the netpack ids every installed package uses; saves hold bases)"""
    from netmod.diagave import road_cells
    _lay, road = road_cells(save)
    return road


def cmd_plan(a):
    """bands of a save and the pieces the rule wants (read-only), then DAV and BV with its claims"""
    from netmod.diagave import road_cells
    from netmod import diagave as DV
    lay, road = road_cells(a.save)
    st = load_stamps(a.pack)
    claims = set()
    for b in bands(road, st):
        print("band axis %d rows %d from %s: %s %s" % (b["axis"], len(b["rows"]), b["rows"][0],
                                                     "converts" if b["ok"] else b["why"], b.get("ends")))
        if b["ok"]:
            claims |= b["claims"]
            for c in sorted(b["want"], key=lambda c: (c[1], c[0])):
                p = lay.get(c)
                print("  (%d,%d) now %-8s want %d.%d" % (c[0], c[1], "%d.%d" % (p.id, p.state) if p else "-",
                                                        *b["want"][c]))
    for b in DV.bands(road, claims):
        w = DV.wanted(b)
        print("DAV band axis %d rows %d from %s: %s" % (b["axis"], len(b["rows"]), b["rows"][0],
                                                      "converts, %d cells" % len(w) if w else b["why"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fit")
    sub.add_parser("pieces")
    s = sub.add_parser("build")
    s.add_argument("pack")
    s.add_argument("--zooms")
    s.add_argument("--only")
    s = sub.add_parser("plan")
    s.add_argument("save")
    s.add_argument("--pack", default=PACK)
    s = sub.add_parser("check")
    s.add_argument("--no-stamps", action="store_true")
    s = sub.add_parser("mockup")
    s.add_argument("out")
    s.add_argument("--cache")
    a = ap.parse_args(argv)
    {"fit": cmd_fit, "mockup": cmd_mockup, "pieces": cmd_plan_pieces, "check": cmd_check, "build": cmd_build, "plan": cmd_plan}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
