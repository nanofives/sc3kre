#!/usr/bin/env python3
r"""diagave.py - diagonal avenues (task diagave, 2026-10-17): the band rule, its pieces, art and lanes, offline checks.

A diagonal avenue is two diagonal road drags JOINED side by side: the second drag one cell over, so the two
staircases share their middle diagonal. The stock tiler turns that into a ladder of 3 pieces per row (curve, 4-way,
curve: verify/diagave/RESULTS_phase1.md); sc3netmod's DAV block applies the rule below after every road retile
instead, and this file is its offline twin plus the builder of the pieces it places.

Why it works: stock diagonal 35 draws only HALF its diamond, the road strip (verify/diagave/RESULTS.md). In a band of
three cells per row the middle cell holds the inner half of BOTH roads, so it is road all over; the outer cells keep
the stock pieces. The middle cell becomes a variant whose art is the two stock halves on one tile and whose lanes are
both halves' lanes.

The rule (down-right axis; the other axis is the same with x mirrored):
  band row  z, left a: ROAD cells (a..a+2, z), no ROAD at (a-1, z) and (a+3, z)
  band      a chain of band rows, each the next row's left - 1, at least MIN_ROWS rows, plus the rows above
            (z_top-k, left a_top-k) and below (z_bot+k, left a_bot+k) while they hold ROAD at d 0..2 (the drags' ends)
  d         x - (row left). Staircase A = d 0,1 and staircase B = d 1,2 in band rows; in end rows d 0 is A, d 2 is B and
            d 1 is A, B or both, whichever keeps every cell of both staircases a lone-staircase mask (fewest "both")
  isolated  no ROAD cell outside the band touches a band cell (8 neighbours); else the band is left to the stock tiler
  piece     a cell of one staircase gets the piece the stock tiler gives a LONE staircase of 3+ steps, by its mask
            inside that staircase (LONE); a cell of both gets the MID variant of (A's piece, B's piece, state offset)

  py -3 diagave.py combos                     the MID combinations every drag footprint needs (ids are assigned here)
  py -3 diagave.py build PACK_DIR             art/<id>/ (z*_r*.png + anchors.json) and mid_<id>.lanes.json per MID variant
  py -3 diagave.py scan [SAVE ...]            bands per save (default: the shipped Cities) and whether they convert
  py -3 diagave.py plan SAVE                  bands + wanted pieces on a save (read-only)
  py -3 diagave.py preview OUT.png PACK_DIR [--rows 6] [--zoom 4] [--axis 0|1] [--rot 0..3] [--offset x|z]
"""
import argparse
import glob
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

MIN_ROWS = 3
DIRS = [(-1, 0), (0, -1), (1, 0), (0, 1), (-1, -1), (1, -1), (1, 1), (-1, 1)]   # mask bit k (tiler.py:41)
# lone staircase (3+ steps): own-footprint mask -> (piece, state); tiler.py on the stock rules, both axes, both phases
LONE = {17: (18004, 2), 18: (1999, 2), 22: (35, 2), 25: (35, 0), 34: (18004, 3), 35: (35, 1), 36: (1999, 3),
        44: (35, 3), 68: (18004, 0), 70: (35, 2), 72: (1999, 0), 73: (35, 0), 86: (35, 2), 89: (35, 0),
        129: (1999, 1), 131: (35, 1), 136: (18004, 1), 140: (35, 3), 163: (35, 1), 172: (35, 3)}
# MID variants: (A's piece, B's piece, (B state - A state) mod 4) -> id; the cell's state is A's. Filled from `combos`.
MID = {(35, 35, 2): 20500, (35, 18004, 0): 20501, (18004, 35, 0): 20502, (35, 1999, 2): 20503, (1999, 35, 2): 20504}
# OUTER: a cell of one staircase holding 35 with the other road beside it in its row: its median-side sidewalk tip
# becomes grass too (the median strip runs past the middle cell's corners into the outer cells). Key (35, 0, 0).
OUTER = {(35, 0, 0): 20505}
# JUNC: canonical junction descriptor (35 half states, road 29 orientation 0 x / 1 z, far curb edge N0 E1 S2 W3 or -1)
# -> variant id. Filled from `combos` (junction footprints).
JUNC = {((0,), 0, -1): 20510, ((0,), 1, -1): 20511, ((0, 2), 0, -1): 20512, ((0, 2), 1, -1): 20513,
        ((0,), 0, 0): 20514, ((0,), 0, 2): 20515, ((0,), 1, 1): 20516, ((0,), 1, 3): 20517,
        ((0, 2), 0, 0): 20518, ((0, 2), 1, 1): 20519}


# ------------------------------------------------------------------------------------------------ the rule
def _mask(c, cells):
    return sum(1 << k for k, (dx, dz) in enumerate(DIRS) if (c[0] + dx, c[1] + dz) in cells)


def bands(road):
    """road: set of (x, z) ROAD cells. -> list of {axis, rows: [(z, a)], A, B, junc: {cell: key}, arms: {cell: state},
    ok, why} in real coordinates. junc keys are junction descriptors (JKEY); arms are straight road cells next to the
    avenue that become road 29 in that state."""
    out = []
    for axis in (0, 1):
        R = road if axis == 0 else {(-x, z) for (x, z) in road}
        full = {}
        for (x, z) in R:
            if (x, z) in R and (x + 1, z) in R and (x + 2, z) in R:
                full.setdefault(z, set()).add(x)
        clean = lambda a, z: (a - 1, z) not in R and (a + 3, z) not in R      # noqa: E731
        seen = set()
        for z in sorted(full):
            for a in sorted(full[z]):
                if (z, a) in seen or a - 1 in full.get(z - 1, ()):
                    continue
                chain = [(z, a)]
                while chain[-1][1] + 1 in full.get(chain[-1][0] + 1, ()):
                    chain.append((chain[-1][0] + 1, chain[-1][1] + 1))
                seen.update(chain)
                if sum(1 for (zz, aa) in chain if clean(aa, zz)) < MIN_ROWS:   # anchored by MIN_ROWS clean rows
                    continue
                band = {(aa + d, zz) for (zz, aa) in chain for d in range(3)}
                A, B, amb = set(), set(), []
                for (zz, aa) in chain:
                    A |= {(aa, zz), (aa + 1, zz)}
                    B |= {(aa + 1, zz), (aa + 2, zz)}
                # side cells of each row: straight road arms along the row (W / E) or along a column (N / S)
                why, junc, arms = "", {}, {}
                colN, colS = {}, {}                      # column x -> row where its arm touches the band
                rowarm = {}
                outside = lambda c: c in R and c not in band     # noqa: E731
                for (zz, aa) in chain:
                    w, e = (aa - 1, zz), (aa + 3, zz)
                    sides = []
                    if w in R:
                        if (aa - 2, zz) in R and not any(outside(c) for c in ((aa - 1, zz + 1), (aa - 2, zz + 1), (aa - 2, zz - 1))):
                            sides.append("W")
                            arms[w], arms[(aa - 2, zz)] = 0, 0
                        elif (aa - 1, zz + 1) in R and not any(outside(c) for c in ((aa - 2, zz), (aa, zz + 1), (aa - 2, zz + 1))):
                            colS[aa - 1] = zz
                            arms[w], arms[(aa - 1, zz + 1)] = 1, 1
                        else:
                            why = why or "road beside the avenue at (%d,%d) is not a straight arm" % ((-w[0] if axis else w[0]), w[1])
                    if e in R:
                        if (aa + 4, zz) in R and not any(outside(c) for c in ((aa + 3, zz - 1), (aa + 4, zz + 1), (aa + 4, zz - 1))):
                            sides.append("E")
                            arms[e], arms[(aa + 4, zz)] = 0, 0
                        elif (aa + 3, zz - 1) in R and not any(outside(c) for c in ((aa + 4, zz), (aa + 2, zz - 1), (aa + 4, zz - 1))):
                            colN[aa + 3] = zz
                            arms[e], arms[(aa + 3, zz - 1)] = 1, 1
                        else:
                            why = why or "road beside the avenue at (%d,%d) is not a straight arm" % ((-e[0] if axis else e[0]), e[1])
                    rowarm[zz] = (aa, sides)
                first, last = chain[0][0], chain[-1][0]
                for zz, (aa, sides) in rowarm.items():
                    if not sides:
                        continue
                    stem = -1
                    if sides == ["W", "E"] and zz in (first, last):
                        stem = 0 if zz == first else 2            # the far curb: N above the first row, S below the last
                    ds = [0, 1, 2] if sides == ["W", "E"] else [0] if sides == ["W"] else [2]
                    for d in ds:
                        junc[(aa + d, zz)] = ("x", d, stem)
                for x0, zz in colN.items():                       # enters the band at (x0, zz+1), its d2 cell
                    cells = [(x0, zz + 1)]
                    if colS.get(x0) == zz + 4:                    # and leaves it at (x0, zz+3): a crossing
                        cells = [(x0, zz + 1), (x0, zz + 2), (x0, zz + 3)]
                    for c in cells:
                        if c not in band:
                            why = why or "column road at x=%d leaves the avenue's rows" % x0
                        junc[c] = ("z", c[0] - [aa for (zr, aa) in chain if zr == c[1]][0] if c in band else 0, -1)
                for x0, zz in colS.items():                       # leaves the band from (x0, zz-1), its d0 cell
                    if colN.get(x0) == zz - 4:
                        continue
                    c = (x0, zz - 1)
                    if c not in band:
                        why = why or "column road at x=%d leaves the avenue's rows" % x0
                    else:
                        junc[c] = ("z", 0, -1)
                # the drags' ends beyond the full rows (as before)
                for (z0, a0), step, pref in ((chain[0], -1, "A"), (chain[-1], 1, "B")):
                    if rowarm[z0][1]:                             # a junction row ends the chain: no drag stub beyond
                        continue
                    k = 1
                    while True:
                        zr, ar = z0 + step * k, a0 + step * k
                        got = [d for d in range(3) if (ar + d, zr) in R and (ar + d, zr) not in arms]
                        if not got:
                            break
                        for d in got:
                            c = (ar + d, zr)
                            band.add(c)
                            if d == 0:
                                A.add(c)
                            elif d == 2:
                                B.add(c)
                            else:
                                amb.append((c, pref))
                        k += 1
                if not why:
                    for c in band:
                        for dx, dz in DIRS:
                            q = (c[0] + dx, c[1] + dz)
                            if q in R and q not in band and q not in arms:
                                why = "touches road at (%d,%d)" % ((-q[0] if axis else q[0]), q[1])
                                break
                        if why:
                            break
                pick = None
                if not why:
                    best = None                      # same order as sc3netmod_dav.c: cost 100 per both + 1 per other,
                    for combo in range(3 ** len(amb)):  # first lowest-cost combination (cell 0 = least digit)
                        choice = [("pref", "other", "both")[(combo // 3 ** i) % 3] for i in range(len(amb))]
                        cost = 100 * choice.count("both") + choice.count("other")
                        if best is not None and cost >= best[0]:
                            continue
                        a2, b2 = set(A), set(B)
                        for (c, pref), ch in zip(amb, choice):
                            side = pref if ch == "pref" else ("B" if pref == "A" else "A") if ch == "other" else "AB"
                            if "A" in side:
                                a2.add(c)
                            if "B" in side:
                                b2.add(c)
                        if all(_mask(c, a2) in LONE for c in a2) and all(_mask(c, b2) in LONE for c in b2):
                            best = (cost, a2, b2)
                    pick = best[1:] if best else None
                    if pick is None:
                        why = "no split into two lone staircases"
                A2, B2 = pick if pick else (A, B)
                st = AXIS_STATES[axis]
                jk = {}
                for c, (o, d, stem) in junc.items():
                    halves = tuple(sorted({0: (st["A0"],), 1: (st["A1"], st["B1"]), 2: (st["B2"],)}[d]))
                    jk[c] = (halves, 0 if o == "x" else 1, stem)
                if axis == 1:
                    m = lambda c: (-c[0], c[1])                   # noqa: E731
                    A2, B2 = {m(c) for c in A2}, {m(c) for c in B2}
                    jk = {m(c): v for c, v in jk.items()}
                    arms = {m(c): v for c, v in arms.items()}
                    chain = [(zz, -aa) for (zz, aa) in chain]
                out.append({"axis": axis, "rows": chain, "A": A2, "B": B2, "junc": jk, "arms": arms,
                            "ok": not why, "why": why})
    return out


# 35's state in each band position (real coordinates): staircase A at d 0 / 1, B at d 1 / 2 (measured in game, axis 1
# in its mirrored frame: d 0 is the real rightmost cell)
AXIS_STATES = {0: {"A0": 2, "A1": 0, "B1": 2, "B2": 0}, 1: {"A0": 1, "A1": 3, "B1": 1, "B2": 3}}


def jrot(key, k):
    """a junction descriptor turned by k states: 35 states + k, road 29 orientation + k (mod 2), far curb + k"""
    halves, o, edge = key
    return (tuple(sorted((s + k) % 4 for s in halves)), (o + k) % 2, edge if edge < 0 else (edge + k) % 4)


def jcanon(key):
    """-> (canonical descriptor, state k with jrot(canonical, k) == key)"""
    best = min((jrot(key, -k % 4), k) for k in range(4))
    return best


def wanted(band, mids=None):
    """-> {(x, z): (piece id, state)} for one band, or None (not isolated / no valid split / a piece has no id)."""
    mids = MID if mids is None else mids
    if not band["ok"]:
        return None
    A, B = band["A"], band["B"]
    out = {}
    for c in A | B:
        if c in band["junc"]:
            canon, k = jcanon(band["junc"][c])
            if canon not in JUNC:
                band["why"] = "no junction piece for %s at %s" % (canon, c)
                return None
            out[c] = (JUNC[canon], k)
            continue
        pa = LONE.get(_mask(c, A)) if c in A else None
        pb = LONE.get(_mask(c, B)) if c in B else None
        if pa and pb:
            key = (pa[0], pb[0], (pb[1] - pa[1]) % 4)
            if key not in mids:
                band["why"] = "no MID piece for %s at %s" % (key, c)
                return None
            out[c] = (mids[key], pa[1])
        else:
            p = pa or pb
            other = B if c in A else A
            beside = any((c[0] + dx, c[1]) in other for dx in (-2, -1, 1, 2))
            out[c] = (OUTER[(35, 0, 0)], p[1]) if p[0] == 35 and beside and (35, 0, 0) in OUTER else p
    for c, o in band["arms"].items():
        out[c] = (29, o)
    return out


def mid_combos(band):
    A, B = band["A"], band["B"]
    for c in A & B:
        if c in band["junc"]:
            continue
        pa, pb = LONE[_mask(c, A)], LONE[_mask(c, B)]
        yield (pa[0], pb[0], (pb[1] - pa[1]) % 4)


# ------------------------------------------------------------------------------------------------ footprints
def drag(x0, z0, n, sx, first):
    """The cells of a diagonal drag of n steps from (x0, z0): x by sx and z by +1, alternating, `first` first."""
    cells = [(x0, z0)]
    x, z = x0, z0
    for i in range(2 * n):
        if (i % 2 == 0) == (first == "x"):
            x += sx
        else:
            z += 1
        cells.append((x, z))
    return cells


def footprints():
    """Two joined drags in every way a player makes them: both axes, both step phases of each drag, the second drag
    one cell along x or one cell up, the same length or one step shorter / longer."""
    for sx in (1, -1):
        for fa, fb in itertools.product("xz", repeat=2):
            for ox, oz in ((sx, 0), (0, -1)):
                for m in (4, 5, 6):
                    yield (sx, fa, fb, ox, oz, m), set(drag(0, 0, 5, sx, fa)) | set(drag(ox, oz, m, sx, fb))


JUNCTION_KINDS = ("cross-x", "T-W", "T-E", "stem-top", "stem-bottom", "cross-z", "T-N", "T-S")


def junction_road(kind, sx, n, ox, oz):
    """A straight road for one junction kind, drawn against the avenue drag(0,0,n) + drag(ox,oz,n) (sx = x step):
    a row road (z fixed) through / into the avenue, or a column road (x fixed). Axis 1 is the x mirror of axis 0."""
    m = n // 2
    av = set(drag(0, 0, n, sx, "x")) | set(drag(ox, oz, n, sx, "x"))
    zs = [z for _, z in av]
    row_cells = lambda z: sorted(x for x, zz in av if zz == z)                       # noqa: E731
    if kind in ("cross-x", "T-W", "T-E"):
        xs = row_cells(m)
        lo, hi = min(xs), max(xs)
        span = {"cross-x": (lo - 5, hi + 5), "T-W": (lo - 5, lo), "T-E": (hi, hi + 5)}[kind]
        if sx < 0:                                         # mirrored: west is +x in real space
            span = {"cross-x": (lo - 5, hi + 5), "T-W": (hi, hi + 5), "T-E": (lo - 5, lo)}[kind]
        return {(x, m) for x in range(span[0], span[1] + 1)}
    if kind in ("stem-top", "stem-bottom"):                # the drags run up to the road: its row holds their ends
        z = max(min(z for x, z in drag(0, 0, n, sx, "x")), min(z for x, z in drag(ox, oz, n, sx, "x")))             if kind == "stem-top" else min(max(z for x, z in drag(0, 0, n, sx, "x")), max(z for x, z in drag(ox, oz, n, sx, "x")))
        xs = [x for x, _ in av]
        return {(x, z) for x in range(min(xs) - 5, max(xs) + 6)}
    xs = row_cells(m)
    x0 = max(xs) if sx > 0 else min(xs)                    # the column through the row's d2 cell (axis space)
    span = {"cross-z": (min(zs) - 5, max(zs) + 5), "T-N": (min(zs) - 5, m), "T-S": (m, max(zs) + 5)}[kind]
    return {(x0, z) for z in range(span[0], span[1] + 1)}


def jfootprints():
    for sx in (1, -1):
        for ox, oz in ((sx, 0), (0, -1)):
            for kind in JUNCTION_KINDS:
                av = set(drag(0, 0, 9, sx, "x")) | set(drag(ox, oz, 9, sx, "x"))
                yield (kind, sx, ox, oz), av | junction_road(kind, sx, 9, ox, oz)


def cmd_combos(a):
    need, fails = {}, []
    for key, road in footprints():
        bs = bands(road)
        if not bs:
            fails.append((key, "no band"))
            continue
        for b in bs:
            if not b["ok"]:
                fails.append((key, b["why"]))
                continue
            for c in mid_combos(b):
                need[c] = need.get(c, 0) + 1
    for c, n in sorted(need.items(), key=lambda t: -t[1]):
        print("  %-22s %3d footprint(s)  id %s" % (c, n, MID.get(c, "MISSING")))
    print("footprints without a converting band: %d of %d" % (len(fails), len(list(footprints()))))
    for k, w in fails[:16]:
        print("  ", k, w)
    jneed, jfails = {}, []
    for key, road in jfootprints():
        bs = [b for b in bands(road) if b["ok"]]
        if not bs:
            jfails.append((key, [b["why"] for b in bands(road)]))
            continue
        for b in bs:
            for c, k in b["junc"].items():
                canon, st = jcanon(k)
                jneed.setdefault(canon, set()).add(key[0])
            for c in mid_combos(b):
                if c not in MID:
                    jfails.append((key, "middle %s" % (c,)))
    print("junction pieces (canonical descriptor: 35 half states, road 29 orientation, far curb):")
    for c, kinds in sorted(jneed.items()):
        print("  %-28s id %-8s %s" % (c, JUNC.get(c, "MISSING"), sorted(kinds)))
    print("junction footprints without a converting band: %d of %d" % (len(jfails), len(list(jfootprints()))))
    for k, w in jfails[:16]:
        print("  ", k, w)


# ------------------------------------------------------------------------------------------------ art + lanes
def mid_frame(pa, pb, delta, z, slot):
    """A's piece frame (slot) + B's piece frame (slot + delta) on one full tile. -> (RGBA, (L, T))"""
    from PIL import Image
    from netmod import netart
    W = netart.TILE_W[z]
    H = W // 2
    T = H // 2 - 1
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for pid, s in ((pa, slot), (pb, (slot + delta) % 4)):
        im, (L, Tt) = netart.stock_frames(pid)[(z, s)]
        canvas.alpha_composite(im, (0 - L, T - Tt))
    return canvas, (0, T)


TREE_PIECE = 20500           # the middle piece that gets the avenue median: art from 11204's two-layer table


def _light(c):
    """a sidewalk pixel of stock 35: light and grey (the measured seam is 156..205 per channel, curbs 115..131)"""
    return c[3] and min(c[:3]) >= 140 and max(c[:3]) - min(c[:3]) <= 40


def grass_palette(z):
    """Grass pixels of avenue 11204's median (layer 0, slot 0: the strip between the trees and the road)."""
    from netmod import netart
    im, (L, T) = netart.stock_frames(11204, 0)[(z, 0)]
    W = netart.TILE_W[z]
    px = im.load()
    out = []
    for y in range(im.height):
        for x in range(im.width):
            gx = x - (0 - L)
            if gx < 0 or gx > W or y < T - (gx / 2.0 if gx <= W / 2 else (W - gx) / 2.0):
                continue                                    # outside the ground diamond: tree crowns
            r, g, b, a = px[x, y]
            if a and g > r + 12 and g > b + 8 and g < 150:
                out.append((r, g, b, 255))
    return out or [(74, 105, 57, 255)]


def tree_sprites(z):
    """The two trees of 11204's tree layer (layer 1, slot 1), each as (RGBA image, base point in the image)."""
    from PIL import Image
    from netmod import netart
    im = netart.stock_frames(11204, 1)[(z, 1)][0]
    px = im.load()
    seen, comps = set(), []
    for y in range(im.height):
        for x in range(im.width):
            if not px[x, y][3] or (x, y) in seen:
                continue
            stack, comp = [(x, y)], []
            seen.add((x, y))
            while stack:
                p = stack.pop()
                comp.append(p)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        q = (p[0] + dx, p[1] + dy)
                        if 0 <= q[0] < im.width and 0 <= q[1] < im.height and q not in seen and px[q][3]:
                            seen.add(q)
                            stack.append(q)
            comps.append(comp)
    comps = [c for c in comps if len(c) >= max(2, len(max(comps, key=len)) // 5)]
    if len(comps) == 1:                  # the two trees overlap: cut at the emptiest column of the middle half
        comp = comps[0]
        xs = [p[0] for p in comp]
        x0, x1 = min(xs), max(xs)
        if x1 - x0 >= 3:
            count = {x: 0 for x in range(x0, x1 + 1)}
            for p in comp:
                count[p[0]] += 1
            mid = range(x0 + (x1 - x0) // 4, x1 - (x1 - x0) // 4 + 1)
            cut = min(mid, key=lambda x: (count[x], abs(x - (x0 + x1) / 2.0)))
            comps = [[p for p in comp if p[0] < cut], [p for p in comp if p[0] >= cut]]
    out = []
    for comp in sorted(comps, key=lambda c: min(p[0] for p in c)):
        xs, ys = [p[0] for p in comp], [p[1] for p in comp]
        spr = Image.new("RGBA", (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1), (0, 0, 0, 0))
        for (x, y) in comp:
            spr.putpixel((x - min(xs), y - min(ys)), px[x, y])
        base = max(comp, key=lambda p: p[1])
        out.append((spr, (base[0] - min(xs), base[1] - min(ys))))
    if len(out) == 1:                    # tiny zooms: one blob for both trees
        out = out * 2
    return out


def median_frames(z, slot):
    """20500 with the avenue median: layer 0 = the two 35 halves with the sidewalk seam along the cell's diagonal
    repainted as 11204's median grass (the curb pixel on each side kept); layer 1 = two trees from 11204's tree layer
    on the diagonal. -> ((ground, anchor), (trees, anchor))"""
    from PIL import Image
    from netmod import netart
    ground, (L, T) = mid_frame(35, 35, 2, z, slot)
    W, H = ground.size
    px = ground.load()
    pal = grass_palette(z)
    vertical = slot % 2 == 0                           # the diagonal is x = W/2 (slots 0, 2) or y = T (slots 1, 3)
    hw, off = seam_halfwidth(z, vertical)              # light pixels nearer the diagonal than the curb -> grass
    for y in range(H):
        for x in range(W):
            d = abs(x - (W // 2 + off)) if vertical else abs(y - (T + 1 + off))
            if d < hw and _light(px[x, y]):
                h = (x * 73856093) ^ (y * 19349663) ^ (z * 83492791)
                px[x, y] = pal[h % len(pal)]
    trees = tree_sprites(z)
    up = max(t.height for t, _ in trees) + 2
    Tc = up + T
    layer = Image.new("RGBA", (W, up + H), (0, 0, 0, 0))
    spots = [(W // 2, Tc - H // 4), (W // 2, Tc + H // 4)] if vertical else [(W // 4, Tc), (3 * W // 4, Tc)]
    for k, (bx, by) in enumerate(sorted(spots, key=lambda p: p[1])):   # back to front
        spr, (tx, ty) = trees[k % len(trees)]
        tmp = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        tmp.paste(spr, (bx - tx, by - ty))
        layer.alpha_composite(tmp)
    return (ground, (L, T)), (layer, (0, Tc))


def seam_halfwidth(z, vertical):
    """(half width, centre offset) of the light sidewalk run on the middle cell's diagonal (centre row / column of
    35 + 35); the offset is the run's centre minus the diagonal's pixel (W/2, or T + 1)."""
    from netmod import netart
    im, (L, T) = mid_frame(35, 35, 2, z, 0 if vertical else 1)
    W, H = im.size
    px = im.load()
    c = W // 2 if vertical else T + 1
    at = (lambda t: (t, T)) if vertical else (lambda t: (W // 2, t))
    lim = W if vertical else H
    if not _light(px[at(c)]):
        return 0, 0
    lo, hi = c, c
    while lo - 1 >= 0 and _light(px[at(lo - 1)]):
        lo -= 1
    while hi + 1 < lim and _light(px[at(hi + 1)]):
        hi += 1
    return (hi - lo) / 2.0, (lo + hi) / 2.0 - c


def outer_frame(z, slot):
    """OUTER: stock 35's frame (its own size and anchor, so the ground-under bit behaves as stock) with the light
    pixels within the median's half-width of its tip repainted as median grass: the tip is the corner where the
    median line runs (x = 0 / W on a vertical strip, y = top / bottom on a horizontal one)."""
    from netmod import netart
    im, (L, T) = netart.stock_frames(35)[(z, slot)]
    im = im.copy()
    W = netart.TILE_W[z]
    H = W // 2
    Tt = H // 2 - 1
    ox, oy = 0 - L, Tt - T                       # frame top-left in tile coordinates (left vertex at (0, Tt))
    px = im.load()
    pal = grass_palette(z)
    vertical = slot % 2 == 0
    hw, off = seam_halfwidth(z, vertical)
    xs = [x for y in range(im.height) for x in range(im.width) if px[x, y][3]]
    ys = [y for y in range(im.height) for x in range(im.width) if px[x, y][3]]
    if vertical:
        line = (W if (sum(xs) / len(xs) + ox) > W / 2 else 0) + off   # the road half's outer corner = its tip
    else:
        line = (Tt + 1 - H // 2 if (sum(ys) / len(ys) + oy) < Tt else Tt + 1 + H // 2) + off
    for y in range(im.height):
        for x in range(im.width):
            d = abs((x + ox) - line) if vertical else abs((y + oy) - line)
            if d < hw and _light(px[x, y]):
                h = ((x + ox) * 73856093) ^ ((y + oy) * 19349663) ^ (z * 83492791)
                px[x, y] = pal[h % len(pal)]
    return im, (L, T)


FAR_KEEP = 0.22             # tile units: a stem keeps road 29's sidewalk pixels this close to its far curb


def _asphalt(c):
    return c[3] and max(c[:3]) < 135 and max(c[:3]) - min(c[:3]) < 22


def asphalt_palette(z):
    """Asphalt pixels of road 29 (dark, grey, not the yellow line)."""
    from netmod import netart
    out = []
    for s in range(4):
        im, _ = netart.stock_frames(29)[(z, s)]
        for (r, g, b, a) in im.getdata():
            if a and max(r, g, b) < 135 and max(r, g, b) - min(r, g, b) < 22:
                out.append((r, g, b, 255))
    return out or [(90, 93, 98, 255)]


def tile_uv(px, py, W, H, T):
    """pixel of a full-tile frame (left vertex at (0, T)) -> view-0 cell coordinates (U along x, V along z), 0..1"""
    dx = px + 0.5 - W / 2.0
    dy = py + 0.5 - (T + 1 - H / 2.0)
    return dy / H - dx / W, dy / H + dx / W


def junction_frame(canon, z, slot):
    """A junction cell: road 29 (orientation o) with the avenue's road halves (35 at the listed states) over it as plain
    asphalt; a stem keeps 29's sidewalk along its far curb. Art at slot k = the canonical descriptor turned by k."""
    from PIL import Image
    from netmod import netart
    halves, o, edge = canon
    W = netart.TILE_W[z]
    H = W // 2
    T = H // 2 - 1
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    im29, (L, Tt) = netart.stock_frames(29)[(z, (o + slot) % 4)]
    canvas.alpha_composite(im29, (0 - L, T - Tt))
    mask = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for s in halves:
        im, (L, Tt) = netart.stock_frames(35)[(z, (s + slot) % 4)]
        mask.alpha_composite(im, (0 - L, T - Tt))
    px, mk = canvas.load(), mask.load()
    pal = asphalt_palette(z)
    e = -1 if edge < 0 else (edge + slot) % 4
    for y in range(H):
        for x in range(W):
            if not mk[x, y][3] or not px[x, y][3]:
                continue
            if e >= 0:
                U, V = tile_uv(x, y, W, H, T)
                dist = (V, 1 - U, 1 - V, U)[e]
                if dist < FAR_KEEP and _light(px[x, y]):
                    continue                                # the far curb stays
            if _asphalt(px[x, y]):
                continue                                    # road 29's own asphalt stays
            if _asphalt(mk[x, y]):
                px[x, y] = mk[x, y]                         # else the diagonal's asphalt at this pixel
                continue
            h = (x * 73856093) ^ (y * 19349663) ^ (z * 83492791)
            px[x, y] = pal[h % len(pal)]                    # sidewalk / lane line of both: plain asphalt
    return canvas, (0, T)


def junction_spec(canon, vid):
    """Lanes of a junction piece: road 29's (orientation o) plus each avenue half's (35 at its state)."""
    halves, o, edge = canon
    parts = [_describe(29, o)] + [_describe(35, s) for s in halves]
    spec = {"_": "diagave.py: junction %s: lanes of 29 (state %d) + 35 at %s" % (canon, o, list(halves)),
            "piece": vid, "states": [0, 1, 2, 3], "flag": parts[0].get("flag", 0), "alt": parts[0].get("alt", [0, 0, 0, 0])}
    veh = {"class": parts[0]["vehicle"]["class"], "speed": parts[0]["vehicle"]["speed"], "lanes": [], "exits": []}
    ped = {"walks": [], "exits": []}
    for s in parts:
        veh["lanes"] += s.get("vehicle", {}).get("lanes", [])
        veh["exits"] += [e for e in s.get("vehicle", {}).get("exits", []) if e not in veh["exits"]]
        ped["walks"] += s.get("pedestrian", {}).get("walks", [])
        ped["exits"] += [e for e in s.get("pedestrian", {}).get("exits", []) if e not in ped["exits"]]
    spec["vehicle"], spec["pedestrian"] = veh, ped
    pairs = []
    for ln in veh["lanes"]:
        p = [_side(ln["from"]), _side(ln["to"])]
        if p not in pairs:
            pairs.append(p)
    spec["connects"] = {"road": pairs}
    return spec


def _side(p):
    return "x-" if p[0] == 0 else "x+" if p[0] == 255 else "z-" if p[1] == 0 else "z+"


def _describe(pid, state):
    import subprocess
    out = subprocess.run([sys.executable, "-m", "netmod.lanekit", "describe", str(pid), "--state", str(state)],
                         capture_output=True, text=True, cwd=os.path.dirname(HERE), check=True).stdout
    return json.loads(out)


def mid_spec(pa, pb, delta, vid):
    """Lane spec (lanekit authoring format) of a MID variant: A's piece at state 0 + B's piece at state delta, the
    state-0 record; lanekit makes states 1..3 by rotation."""
    sa, sb = _describe(pa, 0), _describe(pb, delta)
    spec = {"_": "diagave.py: lanes of %d (state 0) + %d (state %d), the two roads that share this cell" % (pa, pb, delta),
            "piece": vid, "states": [0, 1, 2, 3], "flag": sa.get("flag", 0), "alt": sa.get("alt", [0, 0, 0, 0])}
    veh = {"class": sa["vehicle"]["class"], "speed": sa["vehicle"]["speed"], "lanes": [], "exits": []}
    ped = {"walks": [], "exits": []}
    for s in (sa, sb):
        veh["lanes"] += s.get("vehicle", {}).get("lanes", [])
        veh["exits"] += [e for e in s.get("vehicle", {}).get("exits", []) if e not in veh["exits"]]
        ped["walks"] += s.get("pedestrian", {}).get("walks", [])
        ped["exits"] += [e for e in s.get("pedestrian", {}).get("exits", []) if e not in ped["exits"]]
    spec["vehicle"], spec["pedestrian"] = veh, ped
    pairs = []
    for ln in veh["lanes"]:
        p = [_side(ln["from"]), _side(ln["to"])]
        if p not in pairs:
            pairs.append(p)
    spec["connects"] = {"road": pairs}
    return spec


def cmd_build(a):
    from netmod import netart
    for (pa, pb, delta), vid in sorted(MID.items(), key=lambda t: t[1]):
        d = os.path.join(a.pack, "art", str(vid))
        os.makedirs(d, exist_ok=True)
        anchors = {"_": "diagave.py build: %d (slot) + %d (slot + %d) on one tile" % (pa, pb, delta)}
        for z in range(netart.ZOOMS):
            for s in range(netart.ROTS):
                if vid == TREE_PIECE:                  # two layers (art from 11204): grass median, trees
                    (im, anc), (im1, anc1) = median_frames(z, s)
                    im1.save(os.path.join(d, netart.frame_name(z, s, 1)))
                    anchors[netart.frame_name(z, s, 1)] = list(anc1)
                else:
                    im, anc = mid_frame(pa, pb, delta, z, s)
                im.save(os.path.join(d, netart.frame_name(z, s)))
                anchors[netart.frame_name(z, s)] = list(anc)
        json.dump(anchors, open(os.path.join(d, "anchors.json"), "w"), indent=1)
        spec = mid_spec(pa, pb, delta, vid)
        with open(os.path.join(a.pack, "mid_%d.lanes.json" % vid), "w", newline="\n") as fh:
            json.dump(spec, fh, indent=1)
        print("built %d: art %s, lanes mid_%d.lanes.json (%d vehicle lane(s), connects %s)"
              % (vid, d, vid, len(spec["vehicle"]["lanes"]), spec["connects"]["road"]))
    for canon, vid in sorted(JUNC.items(), key=lambda t: t[1]):      # junction cells: road 29 + the avenue as asphalt
        d = os.path.join(a.pack, "art", str(vid))
        os.makedirs(d, exist_ok=True)
        anchors = {"_": "diagave.py build: junction %s" % (canon,)}
        for z in range(netart.ZOOMS):
            for s in range(netart.ROTS):
                im, anc = junction_frame(canon, z, s)
                im.save(os.path.join(d, netart.frame_name(z, s)))
                anchors[netart.frame_name(z, s)] = list(anc)
        json.dump(anchors, open(os.path.join(d, "anchors.json"), "w"), indent=1)
        spec = junction_spec(canon, vid)
        with open(os.path.join(a.pack, "junc_%d.lanes.json" % vid), "w", newline="\n") as fh:
            json.dump(spec, fh, indent=1)
        print("built %d (junction %s): %d vehicle lane(s)" % (vid, canon, len(spec["vehicle"]["lanes"])))
    for key, vid in OUTER.items():                    # outer cells: 35's frame with the median tip; 35's own lanes
        d = os.path.join(a.pack, "art", str(vid))
        os.makedirs(d, exist_ok=True)
        anchors = {"_": "diagave.py build: stock 35 with the median-side sidewalk tip as grass"}
        for z in range(netart.ZOOMS):
            for s in range(netart.ROTS):
                im, anc = outer_frame(z, s)
                im.save(os.path.join(d, netart.frame_name(z, s)))
                anchors[netart.frame_name(z, s)] = list(anc)
        json.dump(anchors, open(os.path.join(d, "anchors.json"), "w"), indent=1)
        print("built %d (outer): art %s" % (vid, d))


# ------------------------------------------------------------------------------------------------ checks
def road_cells(save):
    import re
    from netmod import tiler, paths
    g = paths.game_root()
    ids = {int(v) for v in re.findall(r"\d+", open(os.path.join(g, "Apps", "Res", "TilingRules",
                                                                "ROAD_GRND_Set.txt")).read())} | set(MID.values()) | set(OUTER.values())
    lay = tiler.City.load(save).layers["surface"]
    return lay, {c for c, p in lay.items() if p.id in ids and p.flags is None}


def cmd_scan(a):
    from netmod import paths
    saves = a.saves or sorted(glob.glob(os.path.join(paths.game_root(), "Cities", "*.sc3")))
    for s in saves:
        _lay, road = road_cells(s)
        b = bands(road)
        print("%-26s bands %d %s" % (os.path.basename(s), len(b), [(x["axis"], x["rows"][0], len(x["rows"]),
                                                                       "converts" if wanted(x) else x["why"]) for x in b]))


def cmd_plan(a):
    lay, road = road_cells(a.save)
    for b in bands(road):
        w = wanted(b)
        print("band axis %d rows %d from %s: %s" % (b["axis"], len(b["rows"]), b["rows"][0], "converts" if w else b["why"]))
        for c in sorted(b["A"] | b["B"], key=lambda c: (c[1], c[0])):
            p = lay.get(c)
            print("  (%d,%d) %-2s now %-8s want %s" % (c[0], c[1], ("A" if c in b["A"] else "") + ("B" if c in b["B"] else ""),
                                                      "%d.%d" % (p.id, p.state) if p else "-",
                                                      "%d.%d" % w[c] if w else "-"))


def cmd_preview(a):
    from netmod import netart
    sx = 1 if a.axis == 0 else -1
    ox, oz = (sx, 0) if a.offset == "x" else (0, -1)
    road = set(drag(0, 0, a.rows, sx, "x")) | set(drag(ox, oz, a.rows, sx, "x"))
    if a.junction:
        road |= junction_road(a.junction, sx, a.rows, ox, oz)
    cells = []
    for b in bands(road):
        w = wanted(b) or {}
        for c, (pid, s) in w.items():
            cell = {"at": [-c[0], c[1]], "slot": s}
            if pid in MID.values() or pid in OUTER.values() or pid in JUNC.values():
                cell["dir"] = os.path.join(a.pack, "art", str(pid))
            else:
                cell["piece"] = pid
            cells.append(cell)
        print("band axis %d rows %d: %s" % (b["axis"], len(b["rows"]), "converts" if w else b["why"]))
    done = {tuple(c["at"]) for c in cells}
    for (x, z) in road:                                 # the rest of a test road: straight 29 along its run
        if (-x, z) not in done:
            cells.append({"at": [-x, z], "piece": 29, "slot": 0 if ((x - 1, z) in road or (x + 1, z) in road) else 1})
    shot = netart.preview({"cells": cells}, None, zooms=[a.zoom], rots=[a.rot])[(a.zoom, a.rot)]
    shot.convert("RGB").save(a.out)
    print(a.out, shot.size)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("combos")
    s = sub.add_parser("build")
    s.add_argument("pack")
    s = sub.add_parser("scan")
    s.add_argument("saves", nargs="*")
    s = sub.add_parser("plan")
    s.add_argument("save")
    s = sub.add_parser("preview")
    s.add_argument("out")
    s.add_argument("pack")
    s.add_argument("--rows", type=int, default=6)
    s.add_argument("--zoom", type=int, default=4)
    s.add_argument("--axis", type=int, default=0)
    s.add_argument("--rot", type=int, default=0)
    s.add_argument("--offset", default="x", choices=("x", "z"))
    s.add_argument("--junction", choices=JUNCTION_KINDS)
    a = ap.parse_args(argv)
    {"combos": cmd_combos, "build": cmd_build, "scan": cmd_scan, "plan": cmd_plan, "preview": cmd_preview}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
