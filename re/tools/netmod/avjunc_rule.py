#!/usr/bin/env python3
r"""avjunc_rule.py - the junction rule on avenue bands (task avjunc, 2026-10-19): offline twin of the reworked AVX block
(re/harness/src/sc3netmod_avx.c). Plan verify/avjunc/PLAN.md section 3; lane model avjunc.py.

World sides here are N E S W = 0 1 2 3 (N = -z), as AVENUE_LANES.md and sc3netmod_avx.c; the rotation of a piece by
one state turns N -> E. Cells are (x, z); a layer is {(x, z): (id, state)}.

1. STRAIGHT PAIR = the two halves of a band side by side, each a straight-half piece (stock 11204, avcore's 21700, an
   avjunc nose or plain half) in its half state: band along x, (x, z) state 2 and (x, z + 1) state 0; band along z,
   (x, z) state 1 and (x + 1, z) state 3.
2. SEGMENT = the positions along the band, from a straight pair, until the next straight pair (at most MAXSEG
   positions); both cells of each position hold a road piece. A foreign variant (another block's) stops the walk and
   refuses the segment.
3. ARM POSITION = a position where a half connects (both cells' arms face each other) to a road cell on its outside.
   Runs of consecutive arm positions = BOXES (1..MAXRUN positions x 2 halves). Two outside arms at consecutive
   positions on one side whose cells, 1 or 2 cells out, are a straight pair of the crossing axis = a CROSSING AVENUE
   SPAN (its first half at the lower position).
4. Every other position of the segment whose cells are plain (29 / 39 / 43 / a straight half, no outside arm) and every
   straight pair next to a box becomes a one-way half cell with the median nose toward each box beside it.
5. Box cell edges: along the band, inside the box -> the row flow; outside the box -> the band's arm (one-way by the
   half's direction), a road (T) or nothing (C). Outside edge -> crossing span (one-way by the crossing half's
   direction), a road arm (T) or C. Median edge (between the halves) -> the column flow if a span covers the position,
   else T (the opening). Row flow = the half's direction when neither external along edge of that row is two-way;
   column flow the same for the crossing half.
6. Demotion: an avenue arm whose band avcore did not convert is two-way: its edges become T, the nose on it two-way
   (AVX's 20810 / 20811 art, stock lanes), and the flows of that row / column drop to none.
"""
import collections
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

DIRV = ((0, -1), (1, 0), (0, 1), (-1, 0))         # N E S W
MAXSEG = 6
MAXRUN = 4

# stock road pieces' turn matrices (props 310, SIMNTWRK dir order x- z- x+ z+): verify/avlanes/data/stock_lanes.txt
STOCK_MASK = {29: 0x01040104, 39: 0x309a309a, 43: 0x7bde7bde, 11203: 0x10081008, 11204: 0x01040104,
              69: 0x01040104, 67: 0x01040104, 11258: 0x21040184, 15098: 0x20842180, 31: 0x20802080,
              32: 0x01040104, 11201: 0x20802080, 11202: 0x01040104}
PLAIN = {29, 39, 43, 11204}                        # pieces a box or a nose may take
AVCORE_BAND = {69, 67, 11258, 15098, 31, 32, 11201, 11202}   # avcore's one-way crossing / slope bases (band cells)
AVL_STRAIGHT = 21700
TEE_ROADS = {29, 39, 43, 11203}                    # task avxroad: roads whose dangling arm into a half reads as a T


def opp(s):
    return (s + 2) % 4


def half_dir(state):
    return (state + 3) % 4


def mask_arms_nesw(mask):
    """props 310 -> local arm sides N E S W at state 0 (a side is an arm if its row has a bit in either half)"""
    out = set()
    for d in range(4):
        if (mask >> (4 * d)) & 0xF or (mask >> (16 + 4 * d)) & 0xF:
            out.add((d + 3) % 4)                    # SIMNTWRK d (x- z- x+ z+) -> N E S W
    return out


class Pieces:
    """what the rule knows about piece ids: stock arms, avcore's variants (by base), avjunc's own pieces."""

    def __init__(self, own=None, avl_base=None):
        self.own = own or {}                        # id -> {"outline": "NESW", "kind": "box" | "nose" | "half"}
        self.virt = {}                              # task avx32: cell -> arm sides (cap_links), set by find()
        self.avl_base = avl_base or {AVL_STRAIGHT: 11204, 21701: 11203}
        for k in range(21710, 21726):
            self.avl_base.setdefault(k, [69, 67, 11258, 15098, 31, 32, 11201, 11202][(k - 21710) // 2])

    def stock_of(self, pid):
        if pid in STOCK_MASK:
            return pid
        return self.avl_base.get(pid)

    def arms(self, pid, state):
        if pid in self.own:
            loc = {e for e, c in enumerate(self.own[pid]["outline"]) if c in "AI"}
        else:
            b = self.stock_of(pid)
            if b is None:
                return None                         # foreign
            loc = mask_arms_nesw(STOCK_MASK[b])
        return {(e + state) % 4 for e in loc}

    def is_row(self, pid):
        """a band row cell: stock 11204, avcore's straight, our nose on a straight pair (not a link nose)"""
        return pid in (11204, AVL_STRAIGHT) or (pid in self.own and self.own[pid]["kind"] in ("nose", "half"))

    def is_half(self, pid):
        return pid in (11204, AVL_STRAIGHT) or (pid in self.own and self.own[pid]["kind"] in ("nose", "half"))

    def foreign(self, pid):
        return pid >= 20000 and pid not in self.own and pid not in self.avl_base


def straight_pair(L, P, a, b, axis):
    """a band row: stock 11204 / avcore's straight half on both cells. NOT our noses: a reloaded layout (noses saved
    and restored) must segment exactly as the stock one did"""
    pa, pb = L.get(a), L.get(b)
    if not (pa and pb and P.is_row(pa[0]) and P.is_row(pb[0])):
        return False
    if a in P.virt or b in P.virt:                  # task avx32: a capped crossing avenue joins here (cap_links)
        return False
    return (pa[1] & 3, pb[1] & 3) == ((2, 0) if axis == "x" else (1, 3))


def conn(L, P, c, side):
    p = L.get(c)
    if p is None:
        return False
    A = P.virt.get(c) or P.arms(p[0], p[1] & 3)    # task avx32: cap_links' arms first
    if not A or side not in A:
        return False
    n = (c[0] + DIRV[side][0], c[1] + DIRV[side][1])
    q = L.get(n)
    if q is None:
        return False
    B = P.virt.get(n) or P.arms(q[0], q[1] & 3)
    return bool(B) and opp(side) in B


def plain(L, P, c):
    """a cell a box or a nose may take: a plain stock piece, or (task avx32) a cell cap_links re-reads"""
    return L[c][0] in PLAIN or c in P.virt


def cap_links(L, P):
    """task avx32 (owner hand test 2026-10-21, img8): an avenue that crosses an avenue but goes on past it as a single
    road on one column only. The stock tiler caps the other half of the avenue at the crossing (11203) and joins the
    going-on half with a T 39, so the avenue does not reach the box. Pattern: a straight pair of the crossing avenue,
    then a row {11203, 39} (the T joining back and forward), then two road cells. Those cells are re-read: the cap and
    the T as a plain link row (arms back and forward), the cell past the cap with an extra arm toward it (and it is no
    longer a straight pair of the through avenue). -> {cell: arm sides}"""
    P.virt = {}
    out = {}
    for (x, z), pc in L.items():
        if not P.is_half(pc[0]) or (pc[1] & 3) not in (1, 2):
            continue
        axis = "z" if (pc[1] & 3) == 1 else "x"
        B = Band(axis)
        a0, b0 = B.cells(x, z)
        if not straight_pair(L, P, a0, b0, axis):
            continue
        for sg in (1, -1):
            d = (sg * B.step[0], sg * B.step[1])
            fwd = DIRV.index(d)
            back = opp(fwd)
            a1, b1 = (a0[0] + d[0], a0[1] + d[1]), (b0[0] + d[0], b0[1] + d[1])
            p1, q1 = L.get(a1), L.get(b1)
            if not (p1 and q1) or {p1[0], q1[0]} != {11203, 39}:
                continue
            cap, tee = (a1, b1) if p1[0] == 11203 else (b1, a1)
            ta = P.arms(L[tee][0], L[tee][1] & 3) or set()
            if back not in ta or fwd not in ta:
                continue
            c2 = (cap[0] + d[0], cap[1] + d[1])
            t2 = (tee[0] + d[0], tee[1] + d[1])
            if c2 not in L or t2 not in L or not P.is_half(L[c2][0]):
                continue
            # past the through avenue (two rows) the road goes on in the T's column only (img8); both columns going
            # on, or none, is another shape (an avenue ending on an avenue with a road beside it, London (141,170))
            c3, c4 = (c2[0] + d[0], c2[1] + d[1]), (c2[0] + 2 * d[0], c2[1] + 2 * d[1])
            t3, t4 = (t2[0] + d[0], t2[1] + d[1]), (t2[0] + 2 * d[0], t2[1] + 2 * d[1])
            if c3 not in L or t3 not in L or t4 not in L or c4 in L:
                continue
            a2 = P.arms(L[c2][0], L[c2][1] & 3)
            if not a2:
                continue
            out[cap] = {back, fwd}
            out[tee] = {back, fwd}
            out[c2] = set(a2) | {back}
    return out


def dropped_tees(L, P, roads, virt):
    """task avxroad (owner hand test 2026-10-26, img1; C avx_drops): two roads meeting an avenue from opposite sides one
    position apart. The stock tiler drops BOTH T's (measured with no netmod loaded), leaving each road with an arm
    pointing into a straight half that has none back. Such a half (stock 11204 / avcore's straight) is re-read with
    that arm, so the two positions form one box with a road arm on each side. Only plain single-road neighbours
    (TEE_ROADS): another avenue's half, a rail crossing or a slope abutting the side is another shape (shipped cities:
    64 of 227 dangling arms). -> {cell: arm sides}, merged over virt"""
    out = dict(virt)
    P.tees = set()
    for c, pc in L.items():
        if pc[0] not in (11204, AVL_STRAIGHT):
            continue
        st = pc[1] & 3
        side = (st + 2) % 4
        n = (c[0] + DIRV[side][0], c[1] + DIRV[side][1])
        q = L.get(n)
        if q is None or n not in roads or q[0] not in TEE_ROADS:
            continue
        A = out.get(c) or P.arms(pc[0], st)
        B = P.arms(q[0], q[1] & 3)
        if not A or side in A or not B or st not in B:
            continue
        out[c] = set(A) | {side}
        P.tees.add(c)
    return out


class Band:
    """geometry of a band axis: positions along it, halves a (x- / z- side) and b"""

    def __init__(self, axis):
        self.axis = axis
        if axis == "x":
            self.step, self.across = (1, 0), (0, 1)
            self.out = (0, 2)                       # outside side of a (N), of b (S)
            self.dir = (1, 3)                       # a runs E, b runs W
            self.st = (2, 0)
            self.perp_dir = (0, 2)                  # the crossing (z) avenue: first column runs N, second S
        else:
            self.step, self.across = (0, 1), (1, 0)
            self.out = (3, 1)                       # a outside W, b outside E
            self.dir = (0, 2)                       # a runs N, b runs S
            self.st = (1, 3)
            self.perp_dir = (1, 3)                  # the crossing (x) avenue: first row runs E, second W
        self.along = (3, 1) if axis == "x" else (0, 2)  # side toward lower / higher positions: (W, E) or (N, S)

    def cells(self, x, z):
        return (x, z), (x + self.across[0], z + self.across[1])


def bv_box(roads, B, pos, r, bvcells):
    """task avx32: a run of 3 positions that BV's own rule (boulevard.runs, geometry only) takes as part of a boulevard;
    BV builds that junction (sc3netmod_avx.c avx_bv_box -> bv_takes). bvcells: the cells of the accepted runs"""
    return len(r) == 3 and pos[r[1]][0] in bvcells


def bv_cells(roads):
    """task avx32: every cell an accepted BV run writes (boulevard.runs, band checks taken as passed)"""
    from netmod import boulevard as BVR
    out = set()
    for run in BVR.runs(roads):
        if run["ok"]:
            out |= set(run["want"])
    return out


def find(L, P, roads, drop=frozenset(), bv=True, caps=True, tees=True):
    """L: layer {(x, z): (id, state)}; roads: the set of ROAD cells; drop: box cell sets to leave stock (the
    validation pass). -> dict with boxes, noses, refusals."""
    P.virt = cap_links(L, P) if caps else {}         # task avx32
    if tees:
        P.virt = dropped_tees(L, P, roads, P.virt)    # task avxroad
    bvc = bv_cells(roads) if bv else set()            # task avx32
    segs = {}
    for (x, z), p in L.items():
        if not P.is_half(p[0]) or (p[1] & 3) not in (1, 2):
            continue
        axis = "z" if (p[1] & 3) == 1 else "x"
        B = Band(axis)
        a0, b0 = B.cells(x, z)
        if not straight_pair(L, P, a0, b0, axis):
            continue
        for sg in (1, -1):
            pos, k, why, term = [], 1, None, "band"
            while True:
                a = (a0[0] + sg * B.step[0] * k, a0[1] + sg * B.step[1] * k)
                b = (b0[0] + sg * B.step[0] * k, b0[1] + sg * B.step[1] * k)
                if not (a in roads and b in roads):
                    term = "end"
                    break
                if straight_pair(L, P, a, b, axis):
                    break
                if P.foreign(L[a][0]) or P.foreign(L[b][0]):
                    why = "foreign piece"
                    break
                pos.append((a, b))
                k += 1
                if k > MAXSEG:
                    why = "segment longer than %d" % MAXSEG
                    break
            if not pos:
                continue
            if sg < 0:
                pos = pos[::-1]
            key = frozenset(c for pr in pos for c in pr)
            if key not in segs:
                segs[key] = dict(axis=axis, pos=pos, why=why, term=term, pairs=(sg, (a0, b0)))
    boxes, noses, links, refused = {}, {}, {}, collections.Counter()
    for sg in segs.values():
        if sg["why"]:
            refused[sg["why"]] += 1
            continue
        B = Band(sg["axis"])
        pos = sg["pos"]
        feat = []
        for a, b in pos:
            feat.append((conn(L, P, a, B.out[0]), conn(L, P, b, B.out[1])))
        runs, cur = [], []
        for i, f in enumerate(feat):
            if f[0] or f[1]:
                cur.append(i)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        if not runs:
            refused["no outside arm"] += 1
            continue
        if any(len(r) > MAXRUN for r in runs):
            refused["run longer than %d" % MAXRUN] += 1
            continue
        bad = [c for pr in pos for c in pr if not plain(L, P, c) and L[c][0] not in P.own and
               P.stock_of(L[c][0]) not in AVCORE_BAND]
        if bad:
            refused["piece %d in the segment" % L[bad[0]][0]] += 1
            continue
        inrun = {i for r in runs for i in r}
        for r in runs:
            cells = [pos[i][h] for i in r for h in (0, 1)]
            if any(not plain(L, P, c) and L[c][0] not in P.own for c in cells):
                refused["box over a crossing / slope piece"] += 1
                continue
            if bv and bv_box(roads, B, pos, r, bvc):       # task avx32: a boulevard's junction (BV / BVX)
                refused["boulevard junction (BV's)"] += 1
                continue
            bx = make_box(L, P, B, pos, r)
            key = frozenset(bx["cells"])
            if key in drop:
                refused["box dropped: edges do not meet"] += 1
                continue
            if key in boxes:                        # a crossing avenue's box, found from its other band too
                continue
            # a cell already in another box (AxA found from both axes, with a different extent) -> keep the bigger
            clash = [k for k in boxes if k & key]
            if clash:
                if all(len(k) >= len(key) for k in clash):
                    continue
                for k in clash:
                    del boxes[k]
            boxes[key] = bx
        # link noses: plain non-run positions of the segment (kept below only if they chain to a kept box)
        for i, (a, b) in enumerate(pos):
            if i in inrun:
                continue
            if all(plain(L, P, c) or L[c][0] in P.own for c in (a, b)):
                for c, h in ((a, 0), (b, 1)):
                    links.setdefault(c, {"axis": sg["axis"], "h": h})
    # straight pairs beside a box (along the band) become noses; record which sides face a box
    boxcell = {}
    for k, bx in boxes.items():
        for c in bx["cells"]:
            boxcell[c] = k
    def own_nose(n):                                    # a saved link chain reads back as our LINK nose pieces
        q = L.get(n)
        return bool(q and q[0] in P.own and P.own[q[0]]["kind"] == "link")
    for k, bx in boxes.items():
        for c, side in bx["along_out"]:
            n = (c[0] + DIRV[side][0], c[1] + DIRV[side][1])
            while n not in noses and n not in boxcell and (n in links or own_nose(n)):   # links / link noses
                noses[n] = dict(links[n] if n in links else {"axis": bx["axis_of"][c], "h": None}, link=True)
                n = (n[0] + DIRV[side][0], n[1] + DIRV[side][1])
            p = L.get(n)
            if p and P.is_row(p[0]) and n not in boxcell:
                noses.setdefault(n, {"axis": bx["axis_of"][c], "h": None})
        B = bx["band"]                                   # the crossing avenue's side: its links and first halves
        other = "z" if B.axis == "x" else "x"
        for (i, h) in bx["spans"]:
            c = bx["pos"][i][h]
            side = B.out[h]
            n = (c[0] + DIRV[side][0], c[1] + DIRV[side][1])
            while n not in noses and n not in boxcell and (n in links or own_nose(n)):
                noses[n] = dict(links[n] if n in links else {"axis": other, "h": None}, link=True)
                n = (n[0] + DIRV[side][0], n[1] + DIRV[side][1])
            p = L.get(n)
            if p and P.is_row(p[0]) and n not in boxcell:
                noses.setdefault(n, {"axis": other, "h": None})
    for n, d in list(noses.items()):
        p = L[n]
        ends = []
        along = (1, 3) if d["axis"] == "x" else (0, 2)
        for s in along:
            m = (n[0] + DIRV[s][0], n[1] + DIRV[s][1])
            if m in boxcell:
                ends.append(s)
        d["ends"] = ends
        if P.is_half(p[0]):
            d["state"] = p[1] & 3
        else:                                       # a plain link cell: its half state from the band geometry
            B = Band(d["axis"])
            d["state"] = B.st[d["h"]]
    return {"boxes": list(boxes.values()), "noses": noses, "refused": refused}


def make_box(L, P, B, pos, r):
    """box over run r of a segment: cells, outline and arm list; modes come from box_modes()"""
    cells = {}
    i0, i1 = r[0], r[-1]
    spans = {}                                      # (position, side) -> 0 first / 1 second half of a crossing span
    for h in (0, 1):
        side = B.out[h]
        i = i0
        while i < i1:
            ca, cb = pos[i][h], pos[i + 1][h]
            if conn(L, P, ca, side) and conn(L, P, cb, side):
                found = False
                for k in (1, 2, 3):
                    oa = (ca[0] + DIRV[side][0] * k, ca[1] + DIRV[side][1] * k)
                    ob = (cb[0] + DIRV[side][0] * k, cb[1] + DIRV[side][1] * k)
                    if straight_pair(L, P, oa, ob, "z" if B.axis == "x" else "x"):
                        found = True
                        break
                    qa, qb = L.get(oa), L.get(ob)       # links, avcore's crossings / slopes, noses: keep going
                    if not (qa and qb and all(q[0] in PLAIN or q[0] in P.own or P.stock_of(q[0]) in AVCORE_BAND
                                              or o in P.virt for q, o in ((qa, oa), (qb, ob)))):     # task avx32
                        break
                if found:
                    spans[(i, h)] = 0
                    spans[(i + 1, h)] = 1
                    i += 2
                    continue
            i += 1
    box = {"cells": [], "axis_of": {}, "along_out": [], "cell": {}}
    for i in r:
        for h in (0, 1):
            c = pos[i][h]
            box["cells"].append(c)
            box["axis_of"][c] = B.axis
            e_out, e_med = B.out[h], B.out[1 - h]
            info = {"pos": i, "h": h, "edges": {}}
            for e in range(4):
                n = (c[0] + DIRV[e][0], c[1] + DIRV[e][1])
                if e in B.along:
                    j = i - 1 if e == B.along[0] else i + 1
                    if i0 <= j <= i1:
                        info["edges"][e] = ("I", "row", h)
                    else:
                        box["along_out"].append((c, e))
                        q = L.get(n)
                        if q is None or not conn(L, P, c, e):
                            info["edges"][e] = ("C", None, None)
                        elif 0 <= j < len(pos) or P.is_half(q[0]) or P.stock_of(q[0]) in AVCORE_BAND:
                            info["edges"][e] = ("A", "band", h)
                        else:
                            info["edges"][e] = ("A", "road", None)
                elif e == e_out:
                    if (i, h) in spans:
                        info["edges"][e] = ("A", "span", (i, h))
                    elif conn(L, P, c, e):
                        info["edges"][e] = ("A", "road", None)
                    else:
                        info["edges"][e] = ("C", None, None)
                else:
                    sp = [(i, hh) for hh in (0, 1) if (i, hh) in spans]
                    info["edges"][e] = ("I", "col", sp[0] if sp else None)
            box["cell"][c] = info
    box["spans"] = spans
    box["band"] = B
    box["pos"] = pos
    box["run"] = r
    return box


def box_arms(bx):
    """the avenue arms of a box: ('band', h, side) for each external along edge facing the band, ('span', side_h,
    first_pos) for each crossing span side"""
    out = set()
    for c, info in bx["cell"].items():
        for e, (o, kind, ref) in info["edges"].items():
            if kind == "band":
                out.add(("band", ref, e))
            elif kind == "span":
                i, h = ref
                first = i if bx["spans"][ref] == 0 else i - 1
                out.add(("span", h, first))
    return sorted(out)


def box_modes(bx, demoted=frozenset()):
    """-> {cell: (outline NESW, modes NESW)}; modes I (2 in) O (2 out) T C. `demoted` = arms (box_arms) left two-way."""
    B = bx["band"]
    spans = bx["spans"]
    # crossing half direction of a span cell (i, h): its column is first (0) or second (1)
    def span_dir(key):
        return B.perp_dir[spans[key]]
    # which crossing columns are two-way: a span side demoted -> both its columns on that side
    span_tw = set()
    for kind, h, first in [a for a in demoted if a[0] == "span"]:
        span_tw |= {(first, h), (first + 1, h)}
    # a column's internal flow drops only when every outside arm of that column is two-way; a row's the same (a
    # two-way arm's opposite traffic has to turn at the box either way, so keeping the flow loses no movement)
    col_tw = set()
    for i in {i for (i, h) in spans}:
        sides = [(i, h) for h in (0, 1) if (i, h) in spans]
        if all(k in span_tw for k in sides):
            col_tw.add(i)
    band_arms = {}
    for c, info in bx["cell"].items():
        for e, (o, kind, ref) in info["edges"].items():
            if kind == "band":
                band_arms.setdefault(ref, set()).add(("band", ref, e))
    row_tw = {h for h, arms in band_arms.items() if arms <= set(demoted)}
    out = {}
    for c, info in bx["cell"].items():
        h, i = info["h"], info["pos"]
        outline, modes = [], []
        for e in range(4):
            o, kind, ref = info["edges"][e]
            outline.append(o)
            if o == "C":
                modes.append("C")
            elif kind == "road":
                modes.append("T")
            elif kind == "band":
                if ("band", ref, e) in demoted:
                    modes.append("T")
                else:
                    d = B.dir[h]
                    modes.append("O" if e == d else "I")
            elif kind == "span":
                if ref in span_tw:
                    modes.append("T")
                else:
                    d = span_dir(ref)
                    modes.append("O" if e == d else "I")
            elif kind == "row":
                if h in row_tw:
                    modes.append("T")
                else:
                    d = B.dir[h]
                    modes.append("O" if e == d else "I")
            else:                                   # median edge: the crossing column's flow, else an opening
                if ref is None or i in col_tw:
                    modes.append("T")
                else:
                    d = span_dir(ref)
                    modes.append("O" if e == d else "I")
        out[c] = ("".join(outline), "".join(modes))
    return out


def rot(t, k):
    """turn a per-side string by k states (N -> E per state)"""
    o = [None] * 4
    for e in range(4):
        o[(e + k) % 4] = t[e]
    return "".join(o)


def canonical(outline, modes):
    """the piece's own orientation (state 0) for an outline + modes, chosen so that its save base fits (see
    save_base): one closed edge on E (39), two adjacent closed on N and E (11203), two opposite on N and S (29), none:
    the smallest rotation. -> (outline0, modes0, k) with rot(outline0, k) == outline."""
    cands = []
    for k in range(4):
        o0, m0 = rot(outline, -k % 4), rot(modes, -k % 4)
        cands.append((o0, m0, k))
    nc = outline.count("C")
    def ok(o0):
        if nc == 0:
            return True
        if nc == 1:
            return o0[1] == "C"
        if nc == 2:
            return (o0[0] == o0[1] == "C") or (o0[0] == o0[2] == "C")
        return False
    good = [c for c in cands if ok(c[0])]
    if not good:
        return None
    return min(good, key=lambda c: (c[0], c[1], c[2]))


def save_base(outline0):
    nc = outline0.count("C")
    if nc == 0:
        return 43
    if nc == 1:
        return 39
    if nc == 2:
        return 11203 if outline0[0] == outline0[1] == "C" else 29
    return None


def nose_kind(d, P_noses=None):
    """a nose cell -> ('nose', ends at state 0 as a frozenset of local sides) for a one-way half at d['state']"""
    s = d["state"]
    return frozenset(((e - s) % 4) for e in d["ends"])


# ------------------------------------------------------------------------------------------------ avl twin (approx.)

UTURN_ENDS = {("z", 0): (3, 0), ("z", 2): (2, 1), ("x", 1): (0, 1), ("x", 3): (3, 2)}   # AVENUE_LANES.md 3


def avl_bands(L, P, roads, res):
    """APPROXIMATION of avcore's band rule (AVENUE_LANES.md 4, the C block is avcore's): a band = straight pairs and
    avcore's crossing / slope pairs along an axis; it converts when both ends are an avjunc nose / box, a clean U-turn
    end (the four 11203 patterns) or the map edge. -> {cell: True/False} for every band cell."""
    noses = res["noses"]
    boxcell = {c for b in res["boxes"] for c in b["cells"]}
    out = {}
    seen = set()
    # task avxroad: avcore never sees AVX's re-read halves (dropped_tees); a box written over them ends the band
    tees = getattr(P, "tees", set())
    full_virt = P.virt
    P.virt = {c: v for c, v in full_virt.items() if c not in tees}
    def bandpos(a, b, axis):
        if a in boxcell or b in boxcell:
            return False
        if straight_pair(L, P, a, b, axis) and a not in noses and b not in noses:
            return True
        pa, pb = L.get(a), L.get(b)
        return bool(pa and pb and P.stock_of(pa[0]) in AVCORE_BAND and P.stock_of(pb[0]) in AVCORE_BAND)
    for (x, z), p in L.items():
        if (x, z) in seen:
            continue
        a0 = None
        for axis in ("x", "z"):
            B = Band(axis)
            a, b = B.cells(x, z)
            if bandpos(a, b, axis) and (P.is_half(p[0]) and (p[1] & 3) == B.st[0] or
                                       P.stock_of(p[0]) in AVCORE_BAND and not P.is_half(p[0])):
                a0, b0 = a, b
                break
        if a0 is None:
            continue
        cells, ok = [], True
        for sg in (1, -1):
            k = 0 if sg == 1 else 1
            while True:
                a = (a0[0] + sg * B.step[0] * k, a0[1] + sg * B.step[1] * k)
                b = (b0[0] + sg * B.step[0] * k, b0[1] + sg * B.step[1] * k)
                if bandpos(a, b, axis):
                    cells += [a, b]
                    k += 1
                    continue
                endside = B.along[1] if sg == 1 else B.along[0]
                if a not in L and b not in L:
                    pass                                         # map edge or empty: [UNCERTAIN] treated as an end
                elif (a in noses and b in noses) or (a in boxcell and b in boxcell):
                    pass
                else:
                    pa, pb = L.get(a), L.get(b)
                    u = UTURN_ENDS.get((axis, endside))
                    if not (u and pa and pb and pa[0] in (11203, 21701) and pb[0] in (11203, 21701) and
                            (pa[1] & 3, pb[1] & 3) == u):
                        ok = False
                break
        for c in cells:
            out[c] = ok
            seen.add(c)
    P.virt = full_virt
    return out


def arm_status(L, P, res, bands):
    """-> {(box index, arm): one-way?} following each arm out of its box past avjunc's noses"""
    noses = res["noses"]
    boxcell = {c for b in res["boxes"] for c in b["cells"]}
    st = {}
    for bi, bx in enumerate(res["boxes"]):
        B = bx["band"]
        for arm in box_arms(bx):
            if arm[0] == "band":
                _, h, e = arm
                c = [c for c, inf in bx["cell"].items() if inf["h"] == h and inf["edges"][e][1] == "band"][0]
                side = e
            else:
                _, h, first = arm
                c = bx["pos"][first][h]
                side = B.out[h]
            n = (c[0] + DIRV[side][0], c[1] + DIRV[side][1])
            while n in noses:
                n = (n[0] + DIRV[side][0], n[1] + DIRV[side][1])
            if n in boxcell:
                st[(bi, arm)] = True
            else:
                st[(bi, arm)] = bool(bands.get(n))
    return st


# ------------------------------------------------------------------------------------------------ offline scan

def city_layer(path, ids):
    from netmod import tiler
    s = tiler.City.load(path).layers["surface"]
    L = {c: (p.id, p.state & 3) for c, p in s.items() if p.flags is None}
    roads = {c for c, p in s.items() if p.flags is None and (p.id in ids or p.id >= 20000)}
    return L, roads


REAL = collections.Counter()


def scan(paths_, ids, P=None, combos=True):
    """-> Counter of pieces {(outline0, modes0): cells}, per-city stats, nose kinds"""
    P = P or Pieces()
    need = collections.Counter()
    stats = {}
    nose_need = collections.Counter()
    for path in paths_:
        L, roads = city_layer(path, ids)
        r = find_valid(L, P, roads)
        nb = len(r["boxes"])
        ncell = sum(len(b["cells"]) for b in r["boxes"])
        miss = 0
        bands = avl_bands(L, P, roads, r)
        ast = arm_status(L, P, r, bands)
        conv = sum(1 for v in bands.values() if v)
        real = collections.Counter()
        for bi, bx in enumerate(r["boxes"]):
            dm = frozenset(a for a in box_arms(bx) if not ast[(bi, a)])
            for c, (o, m) in box_modes(bx, dm).items():
                cz = canonical(o, m)
                if cz:
                    real[(cz[0], cz[1])] += 1
        for k, n in real.items():
            REAL[k] += n
        for bx in r["boxes"]:
            arms = box_arms(bx)
            sets = [frozenset()]
            if combos:
                sets = [frozenset(c) for n in range(len(arms) + 1) for c in itertools.combinations(arms, n)]
            for dm in sets:
                for c, (o, m) in box_modes(bx, dm).items():
                    cz = canonical(o, m)
                    if cz is None:
                        miss += 1
                        continue
                    need[(cz[0], cz[1])] += 1 if not dm else 0
                    need.setdefault((cz[0], cz[1]), 0)
        for n, d in r["noses"].items():
            nose_need[nose_kind(d)] += 1
        stats[os.path.basename(path)] = {"boxes": nb, "cells": ncell, "noses": len(r["noses"]),
                                         "band cells": len(bands), "converted": conv,
                                         "refused": dict(r["refused"]), "no_canonical": miss}
    return need, stats, nose_need


# ------------------------------------------------------------------------------------------------ edge check

def cell_modes_world(L, P, res, bands, ast, extra=None, noses_oneway=False):
    """-> {cell: modes NESW} for every box cell (with its demotions), nose (one-way or two-way) and plain neighbour"""
    out = {}
    boxcell = {}
    for bi, bx in enumerate(res["boxes"]):
        dm = frozenset(a for a in box_arms(bx) if not ast[(bi, a)])
        for c, (o, m) in box_modes(bx, dm).items():
            out[c] = m
            boxcell[c] = bi
    noses = res["noses"]
    # a nose is one-way when the band past it converts or it sits between boxes only
    for n, d in noses.items():
        ow = True if noses_oneway else nose_oneway(L, P, res, bands, n, d)
        out[n] = half_modes(d["state"], ow)
    return out, boxcell


def half_modes(state, oneway):
    d = half_dir(state)
    m = ["C"] * 4
    if oneway:
        m[d], m[opp(d)] = "O", "I"
    else:
        m[d] = m[opp(d)] = "T"
    return "".join(m)


def nose_oneway(L, P, res, bands, n, d):
    boxcell = {c for b in res["boxes"] for c in b["cells"]}
    B = Band(d["axis"])
    for side in B.along:
        m = (n[0] + DIRV[side][0], n[1] + DIRV[side][1])
        while m in res["noses"]:
            m = (m[0] + DIRV[side][0], m[1] + DIRV[side][1])
        if m in boxcell:
            continue
        if not bands.get(m):
            return False
    return True


def other_modes(L, P, bands, c):
    """modes of a cell that is neither a box nor a nose: a converted band cell (one-way), a stock road piece (T on its
    arms), None if unknown"""
    p = L.get(c)
    if p is None:
        return "CCCC"
    if bands.get(c) and P.is_half(p[0]):
        return half_modes(p[1] & 3, True)
    if P.stock_of(p[0]) in AVCORE_BAND:                 # avcore's crossing / slope pieces: skipped
        return None
    A = P.arms(p[0], p[1] & 3)
    if A is None:
        return "XXXX"                                   # unknown connections (a diagonal road piece, ...): refuse
    return "".join("T" if e in A else "C" for e in range(4))


def edge_check(L, P, roads):
    res = find_c(L, P, roads)
    bands, ast, M = res["bands"], res["arm_status"], res["modes"]
    boxcell = {c for b in res["boxes"] for c in b["cells"]}
    bad = collections.Counter()
    ex = {}
    ok = 0
    for c, m in M.items():
        for e in range(4):
            n = (c[0] + DIRV[e][0], c[1] + DIRV[e][1])
            a = m[e]
            b = M[n][opp(e)] if n in M else (other_modes(L, P, bands, n) or "????")[opp(e)]
            if b == "?":
                continue
            good = (a, b) in (("I", "O"), ("O", "I"), ("T", "T"), ("C", "C")) or (a == "C" and n not in roads)
            if good:
                ok += 1
            else:
                k = "%s %s|%s %s" % ("box" if c in boxcell else "nose", a, b,
                                     "box" if n in boxcell else ("nose" if n in res["noses"] else str(L.get(n, ("-",))[0])))
                bad[k] += 1
                ex.setdefault(k, (c, e))
    return ok, bad, ex, res


def find_valid(L, P, roads, bands_fn=None, rounds=6):
    """find() + the validation pass: a box whose edges do not meet its neighbours' (after demotion) is left stock,
    and the rule runs again without it, until every box meets. bands_fn(L, P, roads, res) -> band map (avcore's
    decision; offline: avl_bands)."""
    bands_fn = bands_fn or avl_bands
    drop = set()
    for _ in range(rounds):
        res = find(L, P, roads, frozenset(drop))
        bands = bands_fn(L, P, roads, res)
        ast = arm_status(L, P, res, bands)
        allow = bands_fn is bands_all                # the C block validates with every arm and nose one-way
        if allow:
            ast = {k: True for k in ast}
        M, boxcell = cell_modes_world(L, P, res, bands, ast, noses_oneway=allow)
        bad = set()
        for bi, bx in enumerate(res["boxes"]):
            for c in bx["cells"]:
                for e in range(4):
                    n = (c[0] + DIRV[e][0], c[1] + DIRV[e][1])
                    a = M[c][e]
                    if n in M:
                        b = M[n][opp(e)]
                    else:
                        b = (other_modes(L, P, bands, n) or "????")[opp(e)]
                        if a == "C" and b == "T":                # a stub road that does not connect (stock too)
                            continue
                    if b == "?":
                        continue
                    if b == "X" or ((a, b) not in (("I", "O"), ("O", "I"), ("T", "T"), ("C", "C")) and
                                    not (a == "C" and n not in roads)):
                        bad.add(frozenset(bx["cells"]))
        if not bad:
            break
        drop |= bad
    res["bands"], res["arm_status"], res["modes"] = bands, ast, M
    return res


def bands_all(L, P, roads, res):
    """every band cell converted: what the C block assumes when it validates boxes before avcore decides"""
    return {c: True for c in avl_bands(L, P, roads, res)}


def find_c(L, P, roads):
    """the C block's order: validate assuming every band converts (avx_run), then demote by avcore's decision
    (avx_post) without dropping more boxes"""
    res = find_valid(L, P, roads, bands_fn=bands_all)
    bands = avl_bands(L, P, roads, res)
    ast = arm_status(L, P, res, bands)
    M, _ = cell_modes_world(L, P, res, bands, ast)
    res["bands"], res["arm_status"], res["modes"] = bands, ast, M
    return res


def cmd_check(saves, ids):
    tot_ok = 0
    tot = collections.Counter()
    for path in saves:
        L, roads = city_layer(path, ids)
        ok, bad, ex, res = edge_check(L, Pieces(), roads)
        tot_ok += ok
        tot.update(bad)
        print("%-28s boxes %4d, dropped %3d, edges ok %6d  mismatched %4d  %s" % (os.path.basename(path), len(res["boxes"]),
              res["refused"].get("box dropped: edges do not meet", 0), ok, sum(bad.values()),
                                                           {k: (n, ex[k]) for k, n in bad.most_common(4)}))
    print("total ok %d, mismatched %d: %s" % (tot_ok, sum(tot.values()), tot.most_common(12)))


def main(argv=None):
    import argparse
    import glob
    from netmod import avx
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan", "check"])
    ap.add_argument("saves", nargs="*")
    a = ap.parse_args(argv)
    E = avx._env()
    saves = a.saves or sorted(glob.glob(os.path.join(E["g"], "Cities", "*.sc3")))
    if a.cmd == "check":
        return cmd_check(saves, E["ids"])
    need, stats, nose_need = scan(saves, E["ids"])
    for k, v in stats.items():
        print("%-28s %s" % (k, v))
    used = [k for k, n in need.items() if n]
    print("\npieces needed: %d with every arm one-way, %d with any arm two-way too" % (len(used), len(need)))
    for (o, m), n in sorted(need.items(), key=lambda t: -t[1]):
        print("  %6d  %s %s  base %s" % (n, o, m, save_base(o)))
    print("noses:", {tuple(sorted(k)): n for k, n in nose_need.items()})
    print("\npieces with the avl twin's band decisions: %d" % len(REAL))
    for (o, m), n in sorted(REAL.items(), key=lambda t: -t[1]):
        print("  %6d  %s %s" % (n, o, m))


if __name__ == "__main__":
    sys.exit(main())


# ------------------------------------------------------------------------------------------------ corner junctions
# task avjunc corners (2026-10-19): an avenue corner (avcore: inner bend 21726, outer bend 21701, two halves 21700)
# whose OUTER cell is a T 39 / X 43 with plain roads (29) leaving its outside. The outer cell becomes a corner piece:
# the avenue's two lanes turn through it, the road keeps two-way lanes. Seen in the corner's own frame the avenue
# always enters across one side (e_in) and leaves across the next side anticlockwise (e_out = e_in - 1), a left turn.

CORNER_ROAD_IDS = {29}
INNER_BENDS = {11203, 21726}


def corner_at(L, P, roads, c):
    """-> dict (cell, e_in, e_out, outline, modes NESW, roads) or None"""
    p = L.get(c)
    if not p or not (p[0] in (39, 43) or (p[0] in P.own and P.own[p[0]]["kind"] == "corner")):
        return None
    for e_in in range(4):
        e_out = (e_in + 3) % 4
        hi = (c[0] + DIRV[e_in][0], c[1] + DIRV[e_in][1])
        ho = (c[0] + DIRV[e_out][0], c[1] + DIRV[e_out][1])
        inner = (hi[0] + DIRV[e_out][0], hi[1] + DIRV[e_out][1])
        qi, qo, qn = L.get(hi), L.get(ho), L.get(inner)
        if not (qi and qo and qn and qn[0] in INNER_BENDS):
            continue
        if not (qi[0] in (11204, AVL_STRAIGHT) and qo[0] in (11204, AVL_STRAIGHT)):
            continue
        si, so = qi[1] & 3, qo[1] & 3
        if half_dir(si) != opp(e_in) or half_dir(so) != e_out:
            continue
        if (hi[0] + DIRV[si][0], hi[1] + DIRV[si][1]) != inner or (ho[0] + DIRV[so][0], ho[1] + DIRV[so][1]) != inner:
            continue
        outline, modes, rds = [None] * 4, [None] * 4, []
        outline[e_in], modes[e_in] = "A", "I"
        outline[e_out], modes[e_out] = "A", "O"
        ok = True
        for e in (opp(e_in), opp(e_out)):
            n = (c[0] + DIRV[e][0], c[1] + DIRV[e][1])
            if conn(L, P, c, e):
                if L[n][0] not in CORNER_ROAD_IDS:
                    ok = False
                outline[e], modes[e] = "A", "T"
                rds.append(e)
            else:
                outline[e], modes[e] = "C", "C"
        if ok and rds:
            return {"cell": c, "e_in": e_in, "e_out": e_out, "outline": "".join(outline), "modes": "".join(modes),
                    "roads": rds}
    return None


def find_corners(L, P, roads):
    out = []
    for c, p in L.items():
        if p[0] in (39, 43) or p[0] in P.own:
            k = corner_at(L, P, roads, c)
            if k:
                out.append(k)
    return out
