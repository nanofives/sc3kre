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
  py -3 diagave.py xbuild PACK_DIR [--fresh]  crossing pieces + templates (recipe_crossings.json, manifest.json) (task diagx)
  py -3 diagave.py xcheck                     every crossing kind, turned 0..3, through the rule
  py -3 diagave.py xpreview OUT.png PACK_DIR --kind XX0 [--turn k] [--zooms 3,4] [--rots 0,1]
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
OPENING = True       # task avdiag: a road meeting one carriageway goes on through a median opening to the far curb
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
# MERGE: one carriageway ends and the other goes on as a single road. Canonical cells (diagave_paint.MERGES, axis 0,
# bottom end at row 0) -> piece; MERGE_TABLE: (axis, end 0 bottom / 1 top, continuing 'A'/'B') -> [(dx, dz, piece,
# state)] relative to the end row's left cell in axis space (diagave_paint.merge_table, rotation search).
MERGE_PIECES = {"L": [((1, 0), 20520), ((1, 1), 20521), ((2, 0), 20522), ((2, 1), 20523), ((2, 2), 20524)],
                "R": [((0, -1), 20530), ((0, 0), 20531), ((1, -1), 20532), ((1, 0), 20533), ((2, 0), 20534)]}
MERGE_TABLE = {
    (0, 0, "A"): [(1, 0, 20520, 0), (1, 1, 20521, 0), (2, 0, 20522, 0), (2, 1, 20523, 0), (2, 2, 20524, 0)],
    (0, 0, "B"): [(0, -1, 20530, 0), (0, 0, 20531, 0), (1, -1, 20532, 0), (1, 0, 20533, 0), (2, 0, 20534, 0)],
    (0, 1, "A"): [(2, 1, 20530, 2), (2, 0, 20531, 2), (1, 1, 20532, 2), (1, 0, 20533, 2), (0, 0, 20534, 2)],
    (0, 1, "B"): [(1, 0, 20520, 2), (1, -1, 20521, 2), (0, 0, 20522, 2), (0, -1, 20523, 2), (0, -2, 20524, 2)],
    (1, 0, "A"): [(1, 0, 20530, 1), (2, 0, 20531, 1), (1, 1, 20532, 1), (2, 1, 20533, 1), (2, 2, 20534, 1)],
    (1, 0, "B"): [(0, -1, 20520, 1), (1, -1, 20521, 1), (0, 0, 20522, 1), (1, 0, 20523, 1), (2, 0, 20524, 1)],
    (1, 1, "A"): [(2, 1, 20520, 3), (1, 1, 20521, 3), (2, 0, 20522, 3), (1, 0, 20523, 3), (0, 0, 20524, 3)],
    (1, 1, "B"): [(1, 0, 20530, 3), (0, 0, 20531, 3), (1, -1, 20532, 3), (0, -1, 20533, 3), (0, -2, 20534, 3)]}
# JUNC: canonical junction descriptor (35 half states, road 29 orientation 0 x / 1 z, far curb edge N0 E1 S2 W3 or -1)
# -> variant id. Filled from `combos` (junction footprints).
JUNC = {((0,), 0, -1): 20510, ((0,), 1, -1): 20511, ((0, 2), 0, -1): 20512, ((0, 2), 1, -1): 20513,
        ((0,), 0, 0): 20514, ((0,), 0, 2): 20515, ((0,), 1, 1): 20516, ((0,), 1, 3): 20517,
        ((0, 2), 0, 0): 20518, ((0, 2), 1, 1): 20519,
        ((0,), 0, 1): 20506, ((0,), 1, 0): 20507}           # task avdiag: a median opening's far cell (road stops at the curb)
OPENING_PIECES = (20506, 20507)


# ------------------------------------------------------------------------------------------------ the rule
def _mask(c, cells):
    return sum(1 << k for k, (dx, dz) in enumerate(DIRS) if (c[0] + dx, c[1] + dz) in cells)


def bands(road, claimed=frozenset()):
    """road: set of (x, z) ROAD cells. -> list of {axis, rows: [(z, a)], A, B, junc: {cell: key}, arms: {cell: state},
    ok, why} in real coordinates. junc keys are junction descriptors (JKEY); arms are straight road cells next to the
    avenue that become road 29 in that state. claimed: cells a diagonal boulevard holds (task diagbv, diagbv.py), which
    are never avenue rows; an end that runs into them is a bend (kind 3: virtual rows past it, nothing written)."""
    out = []
    fulls = {}
    for axis in (0, 1):
        R = road if axis == 0 else {(-x, z) for (x, z) in road}
        C = claimed if axis == 0 else {(-x, z) for (x, z) in claimed}                  # task diagbv
        full = fulls[axis] = {}
        for (x, z) in R:
            if (x, z) in R and (x + 1, z) in R and (x + 2, z) in R and \
                    not all((x + k, z) in C for k in range(3)):                         # task diagbv
                full.setdefault(z, set()).add(x)
    for axis in (0, 1):
        R = road if axis == 0 else {(-x, z) for (x, z) in road}
        C = claimed if axis == 0 else {(-x, z) for (x, z) in claimed}                  # task diagbv (per axis)
        full = fulls[axis]
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
                start = chain[0]                             # (z, a) in axis space: the band's key
                if sum(1 for (zz, aa) in chain if clean(aa, zz)) < MIN_ROWS:   # anchored by MIN_ROWS clean rows
                    continue
                # task diagx: crossing templates, tried at every row with road beside it (anchor = that row)
                xm, xcov, xw, partners, why = [], set(), {}, [], ""
                for (zz, aa) in chain:
                    if not clean(aa, zz):
                        xm += [(t, aa, zz) for t in x_tables()
                               if t["axis"] == axis and x_match(t, lambda x, z: (x, z) in R, aa, zz)]
                for (t, aa, zz) in xm:
                    xcov |= x_window(t, aa, zz)
                    for (dx, dz, p, s) in t["writes"]:
                        c = (aa + dx, zz + dz)
                        if xw.get(c, (p, s)) != (p, s):
                            why = why or "two crossings claim (%d,%d)" % ((-c[0] if axis else c[0]), c[1])
                        xw[c] = (p, s)
                    if t["pax"] >= 0:                          # the other diagonal's chain: its start row
                        X = -(aa + t["pdx"]) if axis else aa + t["pdx"]
                        xp, zp = (-X if t["pax"] else X), zz + t["pdz"]
                        while xp - 1 in fulls[t["pax"]].get(zp - 1, ()):
                            xp, zp = xp - 1, zp - 1
                        partners.append((t["pax"], zp, xp))
                xend = [any((chain[i][1] + d, chain[i][0]) in xcov for d in range(3)) for i in (0, -1)]
                bend = [0 if xend[e] else bend_kind(R, chain, e, C) for e in (0, 1)]   # task diagbv: C
                n = len(chain)
                band = {(aa + d, zz) for k, (zz, aa) in enumerate(chain) for d in range(3)
                        if not (bend[0] == 1 and ((k == 0 and d < 2) or (k == 1 and d == 0)))
                        and not (bend[1] == 1 and ((k == n - 1 and d > 0) or (k == n - 2 and d == 2)))}
                A, B, amb = set(), set(), []
                for (zz, aa) in chain:
                    A |= {(aa, zz), (aa + 1, zz)}
                    B |= {(aa + 1, zz), (aa + 2, zz)}
                # side cells of each row: straight road arms along the row (W / E) or along a column (N / S)
                junc, arms = {}, {}
                colN, colS = {}, {}                      # column x -> row where its arm touches the band
                rowarm = {}
                outside = lambda c: c in R and c not in band and c not in C     # noqa: E731  (task diagbv: C)
                for k, (zz, aa) in enumerate(chain):
                    w, e = (aa - 1, zz), (aa + 3, zz)
                    sides = []
                    if bend[0] == 1 and k <= 1:
                        w = None                                  # the straight avenue, not an arm
                    if bend[1] == 1 and k >= n - 2:
                        e = None
                    if w in R and w not in xcov and w not in C:   # task diagx: crossing cells; diagbv: boulevard
                        if (aa - 2, zz) in R and not any(outside(c) for c in ((aa - 1, zz + 1), (aa - 2, zz + 1), (aa - 2, zz - 1))):
                            sides.append("W")
                            arms[w], arms[(aa - 2, zz)] = 0, 0
                        elif (aa - 1, zz + 1) in R and not any(outside(c) for c in ((aa - 2, zz), (aa, zz + 1), (aa - 2, zz + 1))):
                            colS[aa - 1] = zz
                            arms[w], arms[(aa - 1, zz + 1)] = 1, 1
                        else:
                            why = why or "road beside the avenue at (%d,%d) is not a straight arm" % ((-w[0] if axis else w[0]), w[1])
                    if e in R and e not in xcov and e not in C:
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
                    if OPENING and len(sides) == 1 and zz in (first, last):
                        why = why or "a road meets one carriageway in the avenue's end row"     # task avdiag
                        continue
                    if OPENING and len(sides) == 1:
                        # task avdiag: a median opening: the road goes on across the median and stops at the far
                        # carriageway's outer curb (axis-space edge E 1 / W 3 of the far cell)
                        far, end = (2, 1) if sides == ["W"] else (0, 3)
                        for d in (0, 1, 2):
                            junc[(aa + d, zz)] = ("x", d, end if d == far else -1)
                        continue
                    for d in ds:
                        junc[(aa + d, zz)] = ("x", d, stem)
                rows_z = {zr: aa for (zr, aa) in chain}
                for x0, zz in colN.items():                       # enters the band at (x0, zz+1), its d2 cell
                    cells = [(x0, zz + 1)]
                    endc = None
                    if colS.get(x0) == zz + 4:                    # and leaves it at (x0, zz+3): a crossing
                        cells = [(x0, zz + 1), (x0, zz + 2), (x0, zz + 3)]
                    elif OPENING and all((x0, zz + t) in band and zz + t in rows_z for t in (1, 2, 3)) and                             zz + 3 not in (first, last) and zz + 1 not in (first, last):
                        cells = [(x0, zz + 1), (x0, zz + 2), (x0, zz + 3)]   # task avdiag: a median opening, the
                        endc = (x0, zz + 3)                                   # road stops at the far curb (S)
                    elif OPENING:
                        why = why or "a column road meets one carriageway near the avenue's end"     # task avdiag
                    for c in cells:
                        if c not in band:
                            why = why or "column road at x=%d leaves the avenue's rows" % x0
                        junc[c] = ("z", c[0] - rows_z[c[1]] if c in band else 0, 2 if c == endc else -1)
                for x0, zz in colS.items():                       # leaves the band from (x0, zz-1), its d0 cell
                    if colN.get(x0) == zz - 4:
                        continue
                    c = (x0, zz - 1)
                    if c not in band:
                        why = why or "column road at x=%d leaves the avenue's rows" % x0
                    elif OPENING and all((x0, zz - t) in band and zz - t in rows_z for t in (1, 2, 3)) and                             zz - 3 not in (first, last) and zz - 1 not in (first, last):
                        for t in (1, 2, 3):                       # task avdiag: a median opening (far curb N)
                            cc = (x0, zz - t)
                            junc[cc] = ("z", cc[0] - rows_z[cc[1]], 0 if t == 3 else -1)
                    elif OPENING:
                        why = why or "a column road meets one carriageway near the avenue's end"     # task avdiag
                    else:
                        junc[c] = ("z", 0, -1)
                # the drags' ends beyond the full rows: a merge (one carriageway goes on as a single road) or stubs
                merges, path, real = [], set(), set()
                for (z0, a0), step, pref in ((chain[0], -1, "A"), (chain[-1], 1, "B")):
                    ee = 1 if step > 0 else 0
                    if bend[ee]:                                  # straight cells: path; two virtual rows beyond
                        for c, bits, is_real in bend_cells(a0, z0, ee, bend[ee]):
                            path.add(c)
                            if is_real:
                                real.add(c)
                            if bits & 1:
                                A.add(c)
                            if bits & 2:
                                B.add(c)
                        continue
                    if rowarm[z0][1] or xend[ee]:                 # a junction row / a crossing ends the chain: no stub
                        continue
                    cont = merge_cont(R, arms, z0, a0, step)
                    if cont:
                        S = A if cont == "A" else B
                        off = (0, 1) if cont == "A" else (1, 2)
                        for k in range(1, MERGE_ROWS + 2):
                            zr, ar = z0 + step * k, a0 + step * k
                            cs = [(ar + d, zr) for d in off if (ar + d, zr) in R]
                            for c in cs:
                                S.add(c)
                                if k <= MERGE_ROWS:
                                    band.add(c)
                                else:
                                    path.add(c)                   # the single road goes on: stock territory
                                real.add(c)
                        merges.append((0 if step > 0 else 1, cont, z0, a0))
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
                            if q in R and q not in band and q not in arms and q not in real and q not in xcov \
                                    and q not in C:
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
                        if all(_mask(c, a2) in LONE for c in a2 if c not in path and c not in xw) and \
                                all(_mask(c, b2) in LONE for c in b2 if c not in path and c not in xw):
                            best = (cost, a2, b2)
                    pick = best[1:] if best else None
                    if pick is None:
                        why = "no split into two lone staircases"
                A2, B2 = pick if pick else (A, B)
                st = AXIS_STATES[axis]
                jk = {}
                for c, (o, d, stem) in junc.items():
                    halves = tuple(sorted({0: (st["A0"],), 1: (st["A1"], st["B1"]), 2: (st["B2"],)}[d]))
                    if axis == 1 and stem in (1, 3):
                        stem = 4 - stem                           # task avdiag: axis 1 mirrors x: E <-> W
                    jk[c] = (halves, 0 if o == "x" else 1, stem)
                mk = {}
                for (end, cont, z0, a0) in merges:                # merge cells: (piece, state) from the case table
                    for (dx, dz, piece, state) in MERGE_TABLE.get((axis, end, cont), []):
                        c = (a0 + dx, z0 + dz)
                        if c not in band:
                            why = why or "merge cell (%d,%d) is not road" % ((-c[0] if axis else c[0]), c[1])
                        mk[c] = (piece, state)
                if axis == 1:
                    m = lambda c: (-c[0], c[1])                   # noqa: E731
                    A2, B2 = {m(c) for c in A2}, {m(c) for c in B2}
                    jk = {m(c): v for c, v in jk.items()}
                    arms = {m(c): v for c, v in arms.items()}
                    mk = {m(c): v for c, v in mk.items()}
                    path = {m(c) for c in path}
                    xw = {m(c): v for c, v in xw.items()}
                    chain = [(zz, -aa) for (zz, aa) in chain]
                out.append({"axis": axis, "rows": chain, "A": A2, "B": B2, "junc": jk, "arms": arms,
                            "merge": mk, "path": path, "bend": bend, "ok": not why, "why": why,
                            "xw": xw, "partners": partners, "start": (axis, start[0], start[1]),
                            "claimed": claimed})                     # task diagbv: written by DBV, not here
    # task diagx: a crossing of two diagonal avenues converts only when both bands do (sc3netmod_dav.c: dry rounds
    # until no band changes, then the write round)
    ok = {b["start"]: wanted(b) is not None for b in out}
    changed = True
    while changed:
        changed = False
        for b in out:
            if ok[b["start"]] and not all(ok.get(p, False) for p in b["partners"]):
                ok[b["start"]], b["ok"], changed = False, False, True
                b["why"] = "the crossing diagonal avenue does not convert"
    for b in out:
        b["ok"] = b["ok"] and ok[b["start"]]
        b["why"] = b["why"] if not b["ok"] else ""
    return out


MERGE_ROWS = 3              # rows of the single road past a merge that the avenue still writes (then stock)


def _bend_xz(a0, z0, e, u, v):
    """(u, v) at a chain end: u cells right of the end row's left cell, v rows past it; the top end (e 0) turned half
    a circle (u -> 2 - u, v up), so one rule serves both ends"""
    return (a0 + u, z0 + v) if e else (a0 + 2 - u, z0 - v)


def bend_kind(R, chain, e, C=frozenset()):
    """End e (0 top, 1 bottom) of a chain: 1 when the avenue goes on along x as two straight roads (rows v -1 and 0 run
    on past their d2), 2 when it goes on along z (columns u 1 and 2 below), else 0. The carriageways' edges meet the
    straight ones on one cell line, so the diagonal cells keep their middle-of-band pieces and the straight cells stay
    stock (11204)."""
    z0, a0 = chain[-1] if e else chain[0]
    rd = lambda u, v: _bend_xz(a0, z0, e, u, v) in R                               # noqa: E731
    if any(_bend_xz(a0, z0, e, u, 1) in C for u in range(4)):
        return 3                                     # task diagbv: the end runs into a diagonal boulevard
    if len(chain) >= 3 and rd(3, 0) and rd(2, -1) and rd(3, -1) and not any(rd(u, 1) for u in (1, 2, 3)):
        return 1
    if rd(1, 1) and rd(2, 1) and rd(1, 2) and rd(2, 2) and not rd(0, 1) and not rd(3, 1):
        return 2
    return 0


def bend_cells(a0, z0, e, kind):
    """-> [(cell, staircase bits 1 A / 2 B, real straight road)] at a bend end: the straight cells beside the band and
    two virtual rows of both staircases past the end (their masks make the end cells middle-of-band pieces)"""
    out = []
    for v in range(-1, 3):
        for u in range(v, v + 4):
            d, bits, real = u - v, 0, False
            if v >= 1 and d <= 2:
                bits = (1, 3, 2)[d]
            if kind == 1 and v in (-1, 0) and u in (1, 2):
                real = True
                bits = (2 if u == 1 else 0) if v == -1 else (3 if u == 1 else 2)
            if kind == 2 and v == 1 and u in (1, 2):
                real = True
            if not e:
                bits = ((bits & 1) << 1) | ((bits & 2) >> 1)        # turned: d 0 is B's side
            if bits or real:
                out.append((_bend_xz(a0, z0, e, u, v), bits, real))
    return out


def merge_cont(R, arms, z0, a0, step):
    """At a chain end row (z0, left a0), going `step`: 'A' / 'B' when only that staircase's two cells hold road in the
    next two rows (one carriageway ends, the other goes on as a single road), else None."""
    def row(k):
        zr, ar = z0 + step * k, a0 + step * k
        return [((ar + d, zr) in R and (ar + d, zr) not in arms) for d in range(3)]
    r1, r2 = row(1), row(2)
    if r1 == [True, True, False] and r2 == [True, True, False]:
        return "A"
    if r1 == [False, True, True] and r2 == [False, True, True]:
        return "B"
    return None


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
        if c in band.get("xw", {}):
            out[c] = band["xw"][c]                         # task diagx: a crossing's piece
            continue
        if c in band.get("path", ()) or c in band.get("claimed", ()):
            continue                                       # the single road past a merge: left to the stock tiler
        if c in band.get("merge", {}):
            out[c] = band["merge"][c]
            continue
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
    out.update(band.get("xw", {}))                         # task diagx: the crossing's other cells
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


def parts_spec(parts, vid, note):
    """Lanes of the stock pieces (piece, state) that share one cell, as the state-0 record of piece `vid`."""
    specs = [_describe(p, s) for p, s in parts]
    spec = {"_": "diagave.py: %s" % note, "piece": vid, "states": [0, 1, 2, 3], "flag": specs[0].get("flag", 0),
            "alt": specs[0].get("alt", [0, 0, 0, 0])}
    veh = {"class": specs[0]["vehicle"]["class"], "speed": specs[0]["vehicle"]["speed"], "lanes": [], "exits": []}
    ped = {"walks": [], "exits": []}
    for sp in specs:
        veh["lanes"] += sp.get("vehicle", {}).get("lanes", [])
        veh["exits"] += [e for e in sp.get("vehicle", {}).get("exits", []) if e not in veh["exits"]]
        ped["walks"] += sp.get("pedestrian", {}).get("walks", [])
        ped["exits"] += [e for e in sp.get("pedestrian", {}).get("exits", []) if e not in ped["exits"]]
    spec["vehicle"], spec["pedestrian"] = veh, ped
    pairs = []
    for ln in veh["lanes"]:
        pr = [_side(ln["from"]), _side(ln["to"])]
        if pr not in pairs:
            pairs.append(pr)
    spec["connects"] = {"road": pairs}
    return spec


def merge_parts(kind):
    """canonical merge cell -> [(piece, state)] of the lone staircases that hold it (lanes), and whether it holds both
    carriageways inside the band (it then saves as 4-way 43, as the middle pieces do)"""
    from netmod import diagave_paint as P
    F = P.merge_footprint(kind)
    ends = P.MERGES[kind][0]
    A = {c for c in F if c[0] - c[1] in (0, 1) and (ends == "B" or c[1] <= 0)}
    B = {c for c in F if c[0] - c[1] in (1, 2) and (ends == "A" or c[1] <= 0)}
    out = {}
    for c, vid in MERGE_PIECES[kind]:
        parts = []
        for S in (A, B):
            if c in S and _mask(c, S) in LONE:
                parts.append(LONE[_mask(c, S)])
        out[c] = (parts, c in A and c in B)
    return out


def _write_anchors(d, anchors, note):
    anchors = dict(anchors)
    anchors["_"] = note
    json.dump(anchors, open(os.path.join(d, "anchors.json"), "w"), indent=1)


def cmd_build(a):
    """All pieces' art (png_dir per id) and lane specs. Ground art comes from the world scenes of diagave_paint, so the
    middle, edge, junction and merge pieces meet exactly; the middle piece's tree layer is 11204's trees."""
    from netmod import netart
    from netmod import diagave_paint as P
    report = {"save_43": []}
    art = lambda vid: os.path.join(a.pack, "art", str(vid))                       # noqa: E731
    # the middle piece of the straight avenue: ground from the scene, trees on layer 1
    d = art(TREE_PIECE)
    anc = P.paint_cell(P.StraightAvenue(), (1, 0), d)
    for z in range(netart.ZOOMS):
        for s in range(netart.ROTS):
            _g, (im1, anc1) = median_frames(z, s)
            im1.save(os.path.join(d, netart.frame_name(z, s, 1)))
            anc[netart.frame_name(z, s, 1)] = list(anc1)
    _write_anchors(d, anc, "diagave.py build: straight avenue middle cell + 11204 trees")
    spec = mid_spec(35, 35, 2, TREE_PIECE)
    json.dump(spec, open(os.path.join(a.pack, "mid_%d.lanes.json" % TREE_PIECE), "w", newline="\n"), indent=1)
    report["save_43"].append(TREE_PIECE)
    print("built %d (middle, scene + trees)" % TREE_PIECE)
    # the cap combinations at the avenue's ends: the two stock pieces on one tile (concrete seam: the median's nose)
    for (pa, pb, delta), vid in sorted(MID.items(), key=lambda t: t[1]):
        if vid == TREE_PIECE:
            continue
        d = art(vid)
        anchors = P.paint_cell(P.CapCombo(pa, pb, delta), (1, 0), d)
        _write_anchors(d, anchors, "diagave.py build: %d (slot) + %d (slot + %d) on one tile, dashed lanes" % (pa, pb, delta))
        spec = mid_spec(pa, pb, delta, vid)
        json.dump(spec, open(os.path.join(a.pack, "mid_%d.lanes.json" % vid), "w", newline="\n"), indent=1)
        report["save_43"].append(vid)
        print("built %d (cap combination)" % vid)
    # the edge cells beside the median: stock 35's own frame size (ground-under as stock)
    for key, vid in OUTER.items():
        d = art(vid)
        anc = P.paint_cell(P.StraightAvenue(), (2, 0), d, canvas=(35, 0))
        _write_anchors(d, anc, "diagave.py build: straight avenue edge cell (35 state 0)")
        print("built %d (edge, scene)" % vid)
    # junctions: road 29 + the avenue as asphalt + crosswalks
    for canon, vid in sorted(JUNC.items(), key=lambda t: t[1]):
        d = art(vid)
        if vid in OPENING_PIECES:                         # task avdiag: on 35's frames (ground drawn under)
            anc = P.paint_cell(P.Opening(canon[0], canon[1], canon[2]), (0, 0), d, canvas=(35, canon[0][0]))
        else:
            anc = P.paint_cell(P.Junction(canon[0], canon[1], canon[2]), (0, 0), d)
        _write_anchors(d, anc, "diagave.py build: junction %s" % (canon,))
        spec = junction_spec(canon, vid)
        json.dump(spec, open(os.path.join(a.pack, "junc_%d.lanes.json" % vid), "w", newline="\n"), indent=1)
        print("built %d (junction %s)" % (vid, canon))
    # merges: one carriageway tapers into the other
    for kind, cells in MERGE_PIECES.items():
        ends, q_s, q_e = P.MERGES[kind]
        scene = P.Merge(ends, q_s, q_e)
        parts = merge_parts(kind)
        for c, vid in cells:
            d = art(vid)
            anc = P.paint_cell(scene, c, d)
            _write_anchors(d, anc, "diagave.py build: merge %s cell %s" % (kind, c))
            ps, both = parts[c]
            spec = parts_spec(ps, vid, "merge %s cell %s: lanes of %s" % (kind, c, ps))
            json.dump(spec, open(os.path.join(a.pack, "merge_%d.lanes.json" % vid), "w", newline="\n"), indent=1)
            if both:
                report["save_43"].append(vid)
            print("built %d (merge %s cell %s, lanes of %s)" % (vid, kind, c, ps))
    json.dump(report, open(os.path.join(a.pack, "art", "build.json"), "w"), indent=1)


# ------------------------------------------------------------------------------------------------ crossings (task diagx)
# A diagonal avenue crossing another diagonal avenue or the straight avenue 11204, or ending on one (a T). Each kind is
# one canonical layout of two ELEMENTS (diagave_paint: ("diag", c, k) = the axis-0 avenue on strips c..c+2 turned k
# states, ("straight", m, k) = 11204 along x on rows m, m+1 turned k states) and, for a T, the stem (element i ends at
# the other's edge e). Every other drawing of the kind is a turn by k states (cells and piece states turn together)
# moved by whole cells. The two diagonal kinds differ by where the bands meet: XX0 / TX0 share a plus of 5 cells, XX1 /
# TX1 a 2x2 block.
XKINDS = {
    "XX0": ([("diag", 0, 0), ("diag", 1, 1)], None),
    "XX1": ([("diag", 0, 0), ("diag", 2, 1)], None),
    "XSX": ([("diag", 0, 0), ("straight", 0, 0)], None),
    "XSZ": ([("diag", 0, 0), ("straight", -2, 1)], None),
    "TSX": ([("diag", 0, 0), ("straight", 0, 0)], (0, 1)),
    "TSZ": ([("diag", 0, 0), ("straight", -2, 1)], (0, 0)),
    "TX0": ([("diag", 0, 0), ("diag", 1, 1)], (0, 1)),
    "TX1": ([("diag", 0, 0), ("diag", 2, 1)], (0, 1)),
}
XIDS = (20540, 20599)              # this stream's netpack variant ids
XBOX = (-7, -7, 10, 9)             # canonical cells examined around the crossing
XWIN = 2                           # template window: the special cells grown by this many cells (8-neighbourhood)
XJSON = os.path.join(HERE, "examples", "diagonal_avenue", "recipe_crossings.json")   # recipe_*: tracked
_XT = None


def x_scene(kind):
    from netmod import diagave_paint as P
    els, stem = XKINDS[kind]
    return P.Crossing([P.Placed(P.DiagEl(e[1]) if e[0] == "diag" else P.StraightEl(e[1]), e[2]) for e in els], stem)


def x_footprint(sc, box=XBOX):
    """-> {cell: set of element indices} of the canonical layout: an element's cells (band rows / avenue rows), a
    stem's cells only where its road reaches (sampled)"""
    x0, z0, x1, z1 = box
    out = {}
    for X in range(x0, x1 + 1):
        for Z in range(z0, z1 + 1):
            for i in (0, 1):
                if sc.els[i].has_cell(X, Z) and any(sc.has(i, X + (a + .5) / 5, Z + (b + .5) / 5)
                                                    for a in range(5) for b in range(5)):
                    out.setdefault((X, Z), set()).add(i)
    return out


def x_special(sc, F, zooms=(3, 4), n=12):
    """cells whose art in the crossing scene differs from what the elements' own pieces draw there"""
    out = []
    for c in sorted(F, key=lambda c: (c[1], c[0])):
        if len(F[c]) > 1:
            out.append(c)
            continue
        i = next(iter(F[c]))
        diff = False
        for z in zooms:
            for r in range(4):
                for a in range(n):
                    for b in range(n):
                        wx, wz = c[0] + (a + .5) / n, c[1] + (b + .5) / n
                        if sc.colour(z, r, wx, wz) != sc.plain(z, r, wx, wz, i):
                            diff = True
                            break
                    if diff:
                        break
                if diff:
                    break
            if diff:
                break
        if diff:
            out.append(c)
    return out


def x_staircases(sc, F, i):
    """element i (a diagonal): (A, B) world cell sets inside the footprint"""
    import math
    e = sc.els[i]
    A, B = set(), set()
    for c, els in F.items():
        if i not in els:
            continue
        cx, cz = e.canon(c[0] + .5, c[1] + .5)
        d = math.floor(cx) - math.floor(cz) - e.el.c
        if d in (0, 1):
            A.add(c)
        if d in (1, 2):
            B.add(c)
    return A, B


def x_parts(sc, F, c):
    """[(stock piece, world state)] of the road parts in cell c: each diagonal staircase that holds it (its lone-
    staircase piece by mask, as the plain avenue has it), the straight avenue's 11204"""
    import math
    parts = []
    for i in sorted(F[c]):
        e = sc.els[i]
        if e.el.kind == "diag":
            for S in x_staircases(sc, F, i):
                if c in S and _mask(c, S) in LONE:
                    parts.append(LONE[_mask(c, S)])
        else:
            cz = math.floor(e.canon(c[0] + .5, c[1] + .5)[1])
            parts.append((11204, ((2 if cz == e.el.m else 0) + e.k) % 4))
    return parts


def _xrot(c, k):
    """world cell turned k states (one state: (x, z) -> (-z - 1, x))"""
    x, z = c
    for _ in range(k % 4):
        x, z = -z - 1, x
    return (x, z)


def _grow(cells, n):
    out = set(cells)
    for _ in range(n):
        out |= {(x + dx, z + dz) for (x, z) in out for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
    return out


def x_templates(kind, sc, F, special, place):
    """Templates of one kind, one per turn k and diagonal element of the turned layout. A template is anchored on a
    band row of its element (axis space: x mirrored for axis 1; the row's left cell), lists the window (the special
    cells grown by XWIN) as road 'r' / no road '.', and the cells to write: the special cells' pieces (place[cell] =
    (piece, state)) and the straight avenue's plain cells (11204). pax / pdx / pdz: the other diagonal's band, which
    must convert too (a row's left cell, relative to the anchor in this axis space)."""
    import math
    out = []
    W0 = _grow(special, XWIN)
    shapes = []
    for k in range(4):
        Fk = {_xrot(c, k): els for c, els in F.items()}
        Wk = {_xrot(c, k) for c in W0}
        mx, mz = min(c[0] for c in Wk), min(c[1] for c in Wk)
        shape = {((c[0] - mx, c[1] - mz), c in Fk) for c in Wk}
        if shape in shapes:
            continue           # a symmetric kind: this turn is an earlier one moved; its templates would match twice
        shapes.append(shape)
        writes = {}
        for c in W0:
            if c in place:
                p, s = place[c]
                writes[_xrot(c, k)] = (p, (s + k) % 4)
            elif c in F and any(sc.els[i].el.kind == "straight" for i in F[c]):
                i = next(i for i in F[c] if sc.els[i].el.kind == "straight")
                cz = math.floor(sc.els[i].canon(c[0] + .5, c[1] + .5)[1])
                writes[_xrot(c, k)] = (11204, ((2 if cz == sc.els[i].el.m else 0) + sc.els[i].k + k) % 4)
        for ie, e in enumerate(sc.els):
            if e.el.kind != "diag":
                continue
            axis = (e.k + k) % 2
            ax = (lambda X: -X) if axis else (lambda X: X)                      # noqa: E731
            mine = {(ax(c[0]), c[1]) for c, els in Fk.items() if ie in els}
            road = {(ax(c[0]), c[1]) for c in Fk}
            win = {(ax(c[0]), c[1]) for c in Wk}
            rows = sorted((z, a) for (a, z) in mine if (a + 1, z) in mine and (a + 2, z) in mine)
            anchor = next(((a, z) for (z, a) in rows if any((a + d, z) in win for d in range(3)) and
                           ((a - 1, z) in road or (a + 3, z) in road)), None)
            if anchor is None:
                raise SystemExit("%s turn %d element %d: no band row with a road beside it in the window" % (kind, k, ie))
            a0, z0 = anchor
            xs, zs = [c[0] for c in win], [c[1] for c in win]
            gx0, gz0, gx1, gz1 = min(xs), min(zs), max(xs), max(zs)
            grid = "".join("-" if (x, z) not in win else "r" if (x, z) in road else "."
                           for z in range(gz0, gz1 + 1) for x in range(gx0, gx1 + 1))
            wl = sorted((ax(c[0]) - a0, c[1] - z0, p, s) for c, (p, s) in writes.items())
            t = {"kind": kind, "turn": k, "element": ie, "axis": axis, "x0": gx0 - a0, "z0": gz0 - z0,
                 "w": gx1 - gx0 + 1, "h": gz1 - gz0 + 1, "grid": grid, "writes": [list(v) for v in wl], "pax": -1,
                 "pdx": 0, "pdz": 0}
            io = 1 - ie
            o = sc.els[io]
            if o.el.kind == "diag":
                pax = (o.k + k) % 2
                pa = (lambda X: -X) if pax else (lambda X: X)                  # noqa: E731
                theirs = {(pa(c[0]), c[1]) for c, els in Fk.items() if io in els}
                prow = next(((a, z) for (a, z) in sorted(theirs, key=lambda c: (c[1], c[0])) if
                             (a + 1, z) in theirs and (a + 2, z) in theirs and (pa(a), z) in Wk), None)
                if prow is None:
                    raise SystemExit("%s turn %d: no partner band row in the window" % (kind, k))
                t["pax"], t["pdx"], t["pdz"] = pax, ax(pa(prow[0])) - a0, prow[1] - z0
            out.append(t)
    return out


def x_tables():
    """the crossing templates (recipe_crossings.json, written by `xbuild`); [] when not built"""
    global _XT
    if _XT is None:
        _XT = json.load(open(XJSON))["templates"] if os.path.exists(XJSON) else []
    return _XT


def x_match(t, road_ax, a, z):
    """template t anchored at axis-space row (a, z)? road_ax(x, z) tests ROAD in that axis space"""
    w = t["w"]
    for j in range(t["h"]):
        for i in range(w):
            g = t["grid"][j * w + i]
            if g == "-":
                continue
            if (g == "r") != road_ax(a + t["x0"] + i, z + t["z0"] + j):
                return False
    return True


def x_window(t, a, z):
    """axis-space road cells of a matched template's window"""
    w = t["w"]
    return {(a + t["x0"] + i, z + t["z0"] + j) for j in range(t["h"]) for i in range(w) if t["grid"][j * w + i] == "r"}


def cmd_xbuild(a):
    """The crossing pieces: special cells per kind (cached in recipe_crossings.json unless --fresh), art (one painted cell
    per piece, deduplicated over turns), lanes (the road parts' stock lanes), templates; updates manifest.json."""
    from netmod import netart
    from netmod import diagave_paint as P
    import hashlib
    import shutil
    old = json.load(open(XJSON)) if os.path.exists(XJSON) and not a.fresh else {}
    cache = old.get("special", {})
    tmp = os.path.join(a.pack, "art", "x_cells")
    pieces, keys, place_all, templates, special_all = [], {}, {}, [], {}
    nid = XIDS[0]
    for kind in (a.kinds.split(",") if a.kinds else XKINDS):
        sc = x_scene(kind)
        F = x_footprint(sc)
        special = [tuple(c) for c in cache[kind]] if kind in cache else x_special(sc, F)
        special_all[kind] = [list(c) for c in special]
        place = {}
        for c in special:
            d = os.path.join(tmp, kind, "%d_%d" % c)
            if not os.path.exists(os.path.join(d, "anchors.json")) or a.fresh:
                anc = P.paint_cell(sc, c, d)
                _write_anchors(d, anc, "diagave.py xbuild: %s cell %s" % (kind, c))
            parts = x_parts(sc, F, c)
            frames = {}
            for z in range(netart.ZOOMS):
                for r in range(netart.ROTS):
                    frames[(z, r)] = open(os.path.join(d, netart.frame_name(z, r)), "rb").read()

            def key(s):
                return hashlib.sha1(b"".join(frames[(z, (sl - s) % 4)] for z in range(netart.ZOOMS)
                                             for sl in range(netart.ROTS))).hexdigest()
            if len(parts) == 1:
                states = [parts[0][1]]
                base = parts[0][0]
            else:
                states = [0, 1, 2, 3]
                base = 43
            hit = next(((keys[(base, key(s))], s) for s in states if (base, key(s)) in keys), None)
            if hit:
                place[c] = hit
                continue
            s = states[0]
            if nid > XIDS[1]:
                raise SystemExit("out of piece ids (%d..%d)" % XIDS)
            vid, nid = nid, nid + 1
            keys[(base, key(s))] = vid
            place[c] = (vid, s)
            out = os.path.join(a.pack, "art", str(vid))
            os.makedirs(out, exist_ok=True)
            src_anc = json.load(open(os.path.join(d, "anchors.json")))
            anc = {}
            for z in range(netart.ZOOMS):
                for r in range(netart.ROTS):
                    shutil.copyfile(os.path.join(d, netart.frame_name(z, r)),
                                    os.path.join(out, netart.frame_name(z, (r + s) % 4)))
                    anc[netart.frame_name(z, (r + s) % 4)] = src_anc[netart.frame_name(z, r)]
            _write_anchors(out, anc, "diagave.py xbuild: %s cell %s placed at state %d" % (kind, c, s))
            rel = [(p, (st - s) % 4) for p, st in parts]
            spec = parts_spec(rel, vid, "crossing %s cell %s: lanes of %s" % (kind, c, rel))
            json.dump(spec, open(os.path.join(a.pack, "xing_%d.lanes.json" % vid), "w", newline="\n"), indent=1)
            pieces.append({"id": vid, "base": base, "kind": kind, "cell": list(c), "parts": [list(p) for p in parts],
                           "save_43": len(parts) > 1})
            print("built %d (%s cell %s, base %d, parts %s)" % (vid, kind, c, base, parts))
        place_all[kind] = {"%d,%d" % c: list(v) for c, v in place.items()}
        templates += x_templates(kind, sc, F, special, place)
    seen, uniq = set(), []
    for t in templates:
        k = json.dumps({kk: v for kk, v in t.items() if kk not in ("kind", "turn", "element")}, sort_keys=True)
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    for n, t in enumerate(uniq):
        t["id"] = n
    json.dump({"_": "diagave.py xbuild (task diagx): crossing pieces, their placement per kind, templates",
               "special": special_all, "pieces": pieces, "place": place_all, "templates": uniq},
              open(XJSON, "w", newline="\n"), indent=1)
    print("%d crossing pieces (%d..%d), %d templates -> %s" % (len(pieces), XIDS[0], nid - 1, len(uniq), XJSON))
    if not a.no_manifest:
        x_manifest(a.pack, pieces, uniq)


def x_manifest(pack, pieces, templates):
    """crossing pieces into manifest.json: variants, lanes, auto_diagonal_avenues[0].crossing and save_43"""
    path = os.path.join(pack, "manifest.json")
    m = json.load(open(path, encoding="utf-8"))
    lo, hi = XIDS
    m["variants"] = [v for v in m["variants"] if not lo <= v["id"] <= hi]
    m["lanes"] = [v for v in m["lanes"] if not lo <= v["piece"] <= hi]
    for p in pieces:
        m["variants"].append({"id": p["id"], "base": p["base"], "network": "ROAD",
                              "name": {"*": "Diagonal avenue crossing", "ENGLISH": "Cruce de avenidas"},
                              "art": {"from": 35, "png_dir": "art/%d" % p["id"]}, "trblkatt": "copy_base"})
        m["lanes"].append({"piece": p["id"], "spec": "xing_%d.lanes.json" % p["id"]})
    dav = m["auto_diagonal_avenues"][0]
    dav["save_43"] = [v for v in dav.get("save_43", []) if not lo <= v <= hi] + [p["id"] for p in pieces if p["save_43"]]
    dav["crossing"] = [{"id": t["id"], "axis": t["axis"], "x0": t["x0"], "z0": t["z0"], "w": t["w"], "h": t["h"],
                        "grid": t["grid"], "partner": [t["pax"], t["pdx"], t["pdz"]], "writes": t["writes"]}
                       for t in templates]
    json.dump(m, open(path, "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
    print("manifest: %d crossing variants, %d templates" % (len(pieces), len(templates)))


# ------------------------------------------------------------------------------------------------ checks
def road_cells(save):
    import re
    from netmod import tiler, paths
    g = paths.game_root()
    ids = {int(v) for v in re.findall(r"\d+", open(os.path.join(g, "Apps", "Res", "TilingRules",
                                                                "ROAD_GRND_Set.txt")).read())} | set(MID.values()) | set(OUTER.values()) |         set(JUNC.values()) | {v for cs in MERGE_PIECES.values() for _, v in cs}
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
                                                      "%d.%d" % w[c] if w and c in w else
                                                      "(stock)" if c in b["path"] else "-"))


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
            if pid in MID.values() or pid in OUTER.values() or pid in JUNC.values() or                     pid in {v for cs in MERGE_PIECES.values() for _, v in cs}:
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


def x_layout(kind, k, box=(-14, -14, 16, 16)):
    """a drawing of the kind turned k states, long arms: the road cells"""
    return {_xrot(c, k) for c in x_footprint(x_scene(kind), box)}


def cmd_xcheck(a):
    """every kind turned 0..3: does the rule convert every band and give each special cell its art? A symmetric kind
    uses the templates of an earlier turn, so a cell may get another piece / state that draws the same frames: the
    check compares the frames each (piece, state) shows per view."""
    from netmod import netart
    data = json.load(open(XJSON))
    bad = 0
    art = os.path.join(os.path.dirname(XJSON), "art")
    cache = {}

    def look(v):
        if v is None or not XIDS[0] <= v[0] <= XIDS[1]:
            return v
        p, s = v
        if p not in cache:
            cache[p] = {(z, sl): open(os.path.join(art, str(p), netart.frame_name(z, sl)), "rb").read()
                        for z in range(netart.ZOOMS) for sl in range(netart.ROTS)}
        return tuple(cache[p][(z, (r + s) % 4)] for z in range(netart.ZOOMS) for r in range(netart.ROTS))
    for kind in (a.kinds.split(",") if a.kinds else XKINDS):
        place = {tuple(int(v) for v in c.split(",")): tuple(p) for c, p in data["place"][kind].items()}
        nb = 1 if kind in ("XSX", "XSZ", "TSX", "TSZ") else 2
        for k in range(4):
            bs = bands(x_layout(kind, k))
            w = {}
            for b in bs:
                w.update(wanted(b) or {})
            # the turn whose templates serve this one (a symmetric kind: an earlier turn, moved)
            W0 = _grow([tuple(c) for c in data["special"][kind]], XWIN)
            F0 = x_footprint(x_scene(kind))
            corner, shapes = [], []
            for kk in range(k + 1):
                Wk = {_xrot(c, kk) for c in W0}
                mx, mz = min(c[0] for c in Wk), min(c[1] for c in Wk)
                corner.append((mx, mz))
                shapes.append({((c[0] - mx, c[1] - mz), _xrot(c, -kk % 4) in F0) for c in Wk})
            k0 = shapes.index(shapes[k])
            dx, dz = corner[k][0] - corner[k0][0], corner[k][1] - corner[k0][1]
            exp = {(_xrot(c, k0)[0] + dx, _xrot(c, k0)[1] + dz): (p, (s + k0) % 4) for c, (p, s) in place.items()}
            miss = sorted(c for c, v in exp.items() if look(w.get(c)) != look(v))
            good = sum(1 for b in bs if b["ok"]) == nb == len(bs) and not miss
            bad += not good
            print("%s turn %d: %d band(s), %d convert, special cells placed %d/%d %s %s" % (
                kind, k, len(bs), sum(1 for b in bs if b["ok"]), len(exp) - len(miss), len(exp),
                "OK" if good else "FAIL", [b["why"] for b in bs if not b["ok"]][:2] + miss[:4]))
    print("failures: %d" % bad)


def cmd_xpreview(a):
    """one drawing of a kind with the built pieces (stock 11204 on the straight avenue outside the crossing), as
    netart.preview shows it, cropped to --crop W,H about the crossing's centre"""
    import math
    from netmod import netart
    sc = x_scene(a.kind)
    data = json.load(open(XJSON))
    sp = [tuple(c) for c in data["special"][a.kind]]
    cx = (min(c[0] for c in sp) + max(c[0] for c in sp) + 1) / 2.0     # canonical centre of the special cells
    cz = (min(c[1] for c in sp) + max(c[1] for c in sp) + 1) / 2.0
    for _ in range(a.turn % 4):
        cx, cz = -cz, cx
    r = a.r
    X0, X1 = int(math.ceil(cx - 0.5)) - r, int(math.floor(cx - 0.5)) + r
    Z0, Z1 = int(math.ceil(cz - 0.5)) - r, int(math.floor(cz - 0.5)) + r
    F = x_footprint(sc, (-r - 6, -r - 6, r + 8, r + 8))
    road, stock = set(), {}
    for c, els in F.items():
        w = _xrot(c, a.turn)
        if not (X0 <= w[0] <= X1 and Z0 <= w[1] <= Z1):
            continue
        road.add(w)
        for i in els:
            e = sc.els[i]
            if e.el.kind == "straight":
                cz2 = math.floor(e.canon(c[0] + .5, c[1] + .5)[1])
                stock[w] = (11204, ((2 if cz2 == e.el.m else 0) + e.k + a.turn) % 4)
    want = {}
    for b in bands(road):
        print("band axis %d rows %d: %s" % (b["axis"], len(b["rows"]), "converts" if b["ok"] else b["why"]))
        want.update(wanted(b) or {})
    ours = set(MID.values()) | set(OUTER.values()) | set(JUNC.values()) | \
        {v for cs in MERGE_PIECES.values() for _, v in cs} | set(range(XIDS[0], XIDS[1] + 1))
    cells = []
    for c in road:
        pid, st = want.get(c) or stock.get(c) or (35, 0)
        cell = {"at": [-c[0], c[1]], "slot": st}
        if pid in ours:
            cell["dir"] = os.path.join(a.pack, "art", str(pid))
        else:
            cell["piece"] = pid
        cells.append(cell)
    for (mx, mz) in ((X0 - 1, Z0 - 1), (X1 + 1, Z0 - 1), (X0 - 1, Z1 + 1), (X1 + 1, Z1 + 1)):
        cells.append({"at": [-mx, mz], "piece": 29, "slot": 0})     # markers: the crop box is symmetric about the centre
    shots = netart.preview({"cells": cells}, None, zooms=[int(z) for z in a.zooms.split(",")],
                           rots=[int(v) for v in a.rots.split(",")])
    for (z, rr), im in shots.items():
        if a.crop:
            cw, ch = [int(v) for v in a.crop.split(",")]
            cw, ch = cw >> (4 - z), ch >> (4 - z)
            im = im.crop((im.width // 2 - cw // 2, im.height // 2 - ch // 2, im.width // 2 + cw // 2,
                          im.height // 2 + ch // 2))
        out = a.out % {"z": z, "r": rr, "kind": a.kind, "turn": a.turn} if "%" in a.out else a.out
        im.convert("RGB").save(out)
        print(out, im.size)


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
    s = sub.add_parser("xbuild")                                   # task diagx
    s.add_argument("pack")
    s.add_argument("--kinds")
    s.add_argument("--fresh", action="store_true")
    s.add_argument("--no-manifest", action="store_true")
    s = sub.add_parser("xcheck")
    s.add_argument("--kinds")
    s = sub.add_parser("xpreview")
    s.add_argument("out")
    s.add_argument("pack")
    s.add_argument("--kind", default="XX0", choices=sorted(XKINDS))
    s.add_argument("--turn", type=int, default=0)
    s.add_argument("--r", type=int, default=7)
    s.add_argument("--zooms", default="4")
    s.add_argument("--rots", default="0")
    s.add_argument("--crop", help="W,H at zoom 4 (halved per zoom below)")
    a = ap.parse_args(argv)
    {"combos": cmd_combos, "build": cmd_build, "scan": cmd_scan, "plan": cmd_plan, "preview": cmd_preview,
     "xbuild": cmd_xbuild, "xcheck": cmd_xcheck, "xpreview": cmd_xpreview}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
