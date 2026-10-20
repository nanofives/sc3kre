#!/usr/bin/env python3
r"""avdiag.py - the diagonal avenue family on one-way halves (task avdiag, avenue lane rework 2026-10-19).

Plan: verify/avdiag/PLAN.md. This file draws lane scenes of the diagonal avenue pieces (the DAV block's offline twin,
diagave.py, places the pieces; the lanes come from the package specs and the stock records) and holds the one-way
lane rule for the family.

Coordinates: diagave cells are game cells (x, z). Lane points are tile units 0..255 in the piece's state-0 frame,
rotated per state by (x, z) -> (255 - z, x) (lanekit.rot_pt). The drawings put game x to the LEFT and z down, which is
how netart's view 0 lays the cells out (u = -x), so right-hand traffic looks right-hand.

  py -3.12 avdiag.py scene OUT.png KIND [--proposed]     one scene (end, end_z, tail, merge, bend, cross-x, T-W,
                                                        stem-top, ..., XX0, XSX, TSX, TX0, ...)
  py -3.12 avdiag.py sheet OUT.png [--kinds a,b] [--hwave]   owner sheet: today | plan per kind
  py -3.12 avdiag.py joins [--kinds ...]                 avlj letters of the pieces a straight band ends on, and
                                                        sc3netmod_avl.c's end test with them, every scene at 4 turns
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from netmod import diagave as DA          # noqa: E402
from netmod import lanekit as LK          # noqa: E402

PACK = os.path.join(HERE, "examples", "diagonal_avenue")
# the package's lane specs before the one-way rework (git d5dddf1): "today's lanes" in the drawings, and the end caps
# the planner reads to tell the kinds of band end apart
PACK_BEFORE = os.path.join(HERE, "..", "..", "..", "verify", "avdiag", "data", "dav_specs_before")
T = 256.0


# ------------------------------------------------------------------------------------------------ lanes per piece
class Lanes:
    """(piece, state) -> [lane] with lane = {"pts": [(x, z) world tile units relative to the cell], "exit": bool}"""

    def __init__(self, root=None, pack=None):
        pack = pack or PACK_BEFORE
        self.g = LK.Game(root)
        self.P = self.g.paths("ENGLISH")
        self.specs = {}
        for f in os.listdir(pack):
            if f.endswith(".lanes.json"):
                s = json.load(open(os.path.join(pack, f)))
                self.specs[s["piece"]] = s
        self.base = {v["id"]: v["base"] for v in json.load(open(os.path.join(pack, "manifest.json")))["variants"]
                     if v.get("trblkatt") == "copy_base"}

    def _curve(self, key, a, b):
        c = self.P.veh.get(key)
        if c and (c["pts"][0][0], c["pts"][0][2]) == tuple(a) and (c["pts"][-1][0], c["pts"][-1][2]) == tuple(b):
            return [(p[0], p[2]) for p in c["pts"]]
        return [tuple(a), tuple(b)]

    def lanes(self, pid, st):
        out = []
        if pid in self.specs:
            for ln in self.specs[pid]["vehicle"]["lanes"]:
                a, b = LK.rot_pt(*ln["from"], k=st), LK.rot_pt(*ln["to"], k=st)
                key = LK.rot_key(ln["path"], st) if ln.get("path") else None
                out.append({"pts": self._curve(key, a, b) if key else [a, b]})
            return out
        blob = self.g.trblkatt().get(self.base.get(pid, pid) * 256 + st)
        if blob is None:
            return out
        rec = LK.decode(blob)
        for n in rec["veh"]:
            for e in n["edges"]:
                if e["to"] is None:
                    continue
                m = rec["veh"][e["to"]]
                out.append({"pts": self._curve(e["path"], (n["x"], n["z"]), (m["x"], m["z"]))})
        return out


# ------------------------------------------------------------------------------------------------ scenes
def scene(kind, rows=7):
    """-> ({cell: (piece, state)}, set of road cells, note) for one canonical drawing"""
    road = set(DA.drag(0, 0, rows, 1, "x")) | set(DA.drag(1, 0, rows, 1, "x"))
    stock = {}
    if kind == "end_z":
        road = set(DA.drag(0, 0, rows, 1, "x")) | set(DA.drag(0, -1, rows, 1, "x"))
    elif kind == "tail":
        road = set(DA.drag(0, 0, rows + 1, 1, "x")) | set(DA.drag(1, 0, rows, 1, "x"))
    elif kind == "merge":
        road = set(DA.drag(0, 0, rows + 3, 1, "x")) | set(DA.drag(1, 0, rows, 1, "x"))
    elif kind == "bend":                                   # bottom end turns down z as a straight avenue (bend kind 2)
        ch = DA.bands(road)[0]["rows"]
        z0, a0 = ch[-1]
        road = {c for c in road if c[1] <= z0}
        for z in range(z0 + 1, z0 + 6):
            road |= {(a0 + 1, z), (a0 + 2, z)}
            stock[(a0 + 1, z)], stock[(a0 + 2, z)] = (11204, 1), (11204, 3)
    elif kind == "bend_x":                                 # bottom end goes on along +x as a straight avenue (kind 1)
        ch = DA.bands(road)[0]["rows"]
        z0, a0 = ch[-1]
        road = {c for c in road if c[1] <= z0}
        for x in range(a0 + 2, a0 + 8):
            road.add((x, z0 - 1))
        for x in range(a0 + 3, a0 + 8):
            road.add((x, z0))
        for x in range(a0, a0 + 8):                        # cells DAV leaves alone are the straight avenue's
            stock[(x, z0 - 1)], stock[(x, z0)] = (11204, 2), (11204, 0)
    elif kind in DA.JUNCTION_KINDS:
        road |= DA.junction_road(kind, 1, rows, 1, 0)
    elif kind in DA.XKINDS:
        road = DA.x_layout(kind, 0, box=(-9, -9, 11, 11))
        sc = DA.x_scene(kind)
        F = DA.x_footprint(sc, (-9, -9, 11, 11))
        for c, els in F.items():
            for i in els:
                e = sc.els[i]
                if e.el.kind == "straight":
                    cz2 = math.floor(e.canon(c[0] + .5, c[1] + .5)[1])
                    stock[c] = (11204, ((2 if cz2 == e.el.m else 0) + e.k) % 4)
    want, notes = {}, []
    bs = DA.bands(road)
    for b in bs:
        w = DA.wanted(b)
        notes.append("band axis %d rows %d: %s" % (b["axis"], len(b["rows"]), "converts" if w else b["why"]))
        want.update(w or {})
    for c in road:
        if c in want:
            continue
        if c in stock:
            want[c] = stock[c]
        else:
            want[c] = (29, 0 if ((c[0] - 1, c[1]) in road or (c[0] + 1, c[1]) in road) else 1)
    cors = [Cor.band(b, road) for b in bs if b["ok"]]
    cors += Cor.avenues({c: v for c, v in stock.items() if want.get(c) == v})
    if kind in DA.JUNCTION_KINDS:
        cors.append(Cor.road(DA.junction_road(kind, 1, rows, 1, 0)))
    return want, road, notes, cors


# ------------------------------------------------------------------------------------------------ corridors
R2 = math.sqrt(2.0)
LANE_R = {"band": (80 / 255.0 / R2, 175 / 255.0 / R2),        # 35's lane lines z - x = 80 / 175 (lane units: a border
          "avenue": (80 / 255.0, 175 / 255.0),                 # is 0 / 255), from the median line; 11204 halves: lanes
          "road": (47.5 / 255.0,)}                             # 80 / 175 from the median; 29: lanes 80 / 175, centre 127.5


class Cor:
    """A straight corridor in world cell units: origin o (on the median / centre line), unit along t, lane offsets r
    (along left(t) = (-tz, tx)), present for s in [s0, s1]. Right-hand rule: r > 0 travels -t, r < 0 travels +t."""

    def __init__(self, kind, o, t, s0, s1, cells=()):
        self.kind, self.o, self.t, self.s0, self.s1, self.cells = kind, o, t, s0, s1, set(cells)
        self.n = (-t[1], t[0])
        self.lanes = [(sg * r, -sg) for r in LANE_R[kind] for sg in (1, -1)]      # (r, travel sign)

    def sr(self, p):
        d = (p[0] - self.o[0], p[1] - self.o[1])
        return d[0] * self.t[0] + d[1] * self.t[1], d[0] * self.n[0] + d[1] * self.n[1]

    def at(self, s, r):
        return (self.o[0] + s * self.t[0] + r * self.n[0], self.o[1] + s * self.t[1] + r * self.n[1])

    def _span(self, cells):
        ss = [self.sr((c[0] + .5, c[1] + .5))[0] for c in cells]
        self.s0, self.s1 = min(ss), max(ss)
        return self

    @staticmethod
    def band(b, road=None):
        t = (1 / R2, 1 / R2) if b["axis"] == 0 else (-1 / R2, 1 / R2)
        M = sorted(b["A"] & b["B"], key=lambda c: c[1])
        o = (M[0][0] + .5, M[0][1] + .5)
        c = Cor("band", o, t, 0, 0, b["A"] | b["B"])._span({m for m in b["A"] & b["B"] if road is None or m in road})
        c.b = b
        return c

    @staticmethod
    def avenues(stock):
        out = []
        for along in (0, 1):
            cells = {c: st for c, (p, st) in stock.items() if p == 11204 and st % 2 == along}
            if not cells:
                continue
            hi = [c for c, st in cells.items() if st == (0 if along == 0 else 3)]      # the +z / +x half
            if along == 0:
                o, t = (0.0, float(min(c[1] for c in hi))), (1.0, 0.0)
            else:
                o, t = (float(min(c[0] for c in hi)), 0.0), (0.0, 1.0)
            out.append(Cor("avenue", o, t, 0, 0, cells)._span(cells))
        return out

    @staticmethod
    def road(cells):
        xs, zs = {c[0] for c in cells}, {c[1] for c in cells}
        if len(zs) == 1:
            return Cor("road", (0.0, list(zs)[0] + .5), (1.0, 0.0), 0, 0, cells)._span(cells)
        return Cor("road", (list(xs)[0] + .5, 0.0), (0.0, 1.0), 0, 0, cells)._span(cells)


def world_lanes(want, L):
    """today's lanes as world polylines: [(cell, pid, [(x, z)])]"""
    out = []
    for (cx, cz), (pid, st) in want.items():
        for ln in L.lanes(pid, st):
            out.append(((cx, cz), pid, [(cx + x / T, cz + z / T) for (x, z) in ln["pts"]]))
    return out


def _on_edge(p):
    fx, fz = p[0] - math.floor(p[0] + 1e-6), p[1] - math.floor(p[1] + 1e-6)
    return min(fx, 1 - fx) < 0.01 or min(fz, 1 - fz) < 0.01


def _beyond(cell, p):
    """the cell a border point leads to, or None when p is not on the cell's border"""
    x, z = cell
    lx, lz = p[0] - x, p[1] - z
    if lx < 0.01:
        return (x - 1, z)
    if lx > 0.99:
        return (x + 1, z)
    if lz < 0.01:
        return (x, z - 1)
    if lz > 0.99:
        return (x, z + 1)
    return None


def bez(a, c, b, n=16):
    return [((1 - u) ** 2 * a[0] + 2 * (1 - u) * u * c[0] + u * u * b[0],
             (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * c[1] + u * u * b[1]) for u in (k / float(n) for k in range(n + 1))]


def smooth(cor, s0, r0, s1, r1, n=16):
    return [cor.at(s0 + (s1 - s0) * u, r0 + (r1 - r0) * u * u * (3 - 2 * u)) for u in (k / float(n) for k in range(n + 1))]


def _isect(c1, r1, c2, r2):
    """world point where lane line (c1, r1) meets (c2, r2), or None for parallel corridors"""
    p, q = c1.at(0, r1), c2.at(0, r2)
    d1, d2 = c1.t, c2.t
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-6:
        return None
    u = ((q[0] - p[0]) * d2[1] - (q[1] - p[1]) * d2[0]) / den
    return (p[0] + u * d1[0], p[1] + u * d1[1])


RED, BLUE, GREEN, GREY = (205, 45, 40), (35, 90, 215), (20, 150, 60), (90, 90, 90)


def proposed(want, road, cors, L):
    """-> (polylines [(pts, colour, width)], notes): the planned lanes as corridor lines (one direction per
    carriageway, right-hand), the new lanes at the band ends (two-lane U-turn, merge taper, bend joint) and the turns
    where two corridors cross (right turn outer lane to outer lane, left turn inner to inner)."""
    out, notes = [], []
    bands = [c for c in cors if c.kind == "band"]
    ri, ro = LANE_R["band"]
    lanes = world_lanes(want, L)

    def is_cap(a, b):
        return any(abs(a[k] - b[k]) < 1e-3 and _on_edge((a[k], a[k])) for k in (0, 1))

    def mid(pts):
        return pts[len(pts) // 2]

    def col(c, sign):
        d = (sign * c.t[0], sign * c.t[1])
        return RED if d[1] > 1e-6 or (abs(d[1]) < 1e-6 and d[0] < 0) else BLUE
    dead = 0
    for cell, pid, pts in lanes:
        if 20500 <= pid <= 20599 and any(cell in c.cells for c in bands) and any(
                _beyond(cell, p) is not None and _beyond(cell, p) not in road for p in (pts[0], pts[-1])):
            dead += 1
    if dead:
        notes.append("today: %d avenue lane(s) run on through the road into a cell with no road" % dead)
    # each band end: U-turn, merge, bend into a straight avenue, or open (a junction / crossing)
    ends = {}
    for c in bands:
        b = c.b
        caps = [pts for cell, pid, pts in lanes if cell in c.cells and is_cap(pts[0], pts[-1])]
        for e in (-1, 1):
            se = c.s0 if e < 0 else c.s1
            capped = [p for p in caps if (c.sr(mid(p))[0] - (c.s0 + c.s1) / 2) * e > 0]
            near = [o for o in cors if o is not c and o.s0 - 0.6 <= o.sr(c.at(se, 0))[0] <= o.s1 + 0.6 and
                    abs(o.sr(c.at(se, 0))[1]) < 1.6]
            info = {"kind": "open", "stop": se}
            for o in near:
                if abs(o.t[0] * c.t[0] + o.t[1] * c.t[1]) > 0.9 or o.kind == "band" and False:
                    continue
                f0, f1 = o.sr(c.at(0, 0))[1], o.sr(c.at(1, 0))[1]
                W = {"road": 0.5, "avenue": 1.0, "band": 0.75}[o.kind]
                cand = [(w - f0) / (f1 - f0) for w in (W, -W)]
                mids = (c.s0 + c.s1) / 2
                inner = min(cand, key=lambda v: (v - mids) * e)
                outer = max(cand, key=lambda v: (v - mids) * e)
                if (se - outer) * e < 0.3:           # the band does not go on past the other corridor: a T
                    info["stop"] = inner
            if capped and b.get("merge"):
                ms = [c.sr((m[0] + .5, m[1] + .5))[0] for m in b["merge"]]
                if (sum(ms) / len(ms) - (c.s0 + c.s1) / 2) * e > 0:
                    gone = 1 if sum(c.sr(mid(p))[1] for p in capped) > 0 else -1
                    sn = max(c.sr(mid(p))[0] * e for p in capped) * e
                    path = [c.sr((m[0] + .5, m[1] + .5))[0] for m in b["path"]] or [sn + e * 3]
                    info = {"kind": "merge", "gone": gone, "nose": sn, "stop": sn, "L": 2.2,
                            "far": max(s * e for s in path) * e + e * 0.5}
            elif capped and not near and len({1 if c.sr(mid(p))[1] > 0 else -1 for p in capped}) == 2 and abs(
                    max(c.sr(mid(p))[0] * e for p in capped if c.sr(mid(p))[1] > 0) -
                    max(c.sr(mid(p))[0] * e for p in capped if c.sr(mid(p))[1] < 0)) > 1.0:
                # one drag a step longer: the shorter carriageway ends there, the longer one goes on as a short
                # two-way stub with its stock cap (a merge without the taper art)
                side_s = {g: max(c.sr(mid(p))[0] * e for p in capped if c.sr(mid(p))[1] * g > 0) * e for g in (1, -1)}
                gone = min((1, -1), key=lambda g: side_s[g] * e)
                info = {"kind": "merge", "gone": gone, "nose": side_s[gone], "stop": side_s[gone], "L": 1.3,
                        "far": side_s[-gone], "tail": [p for p in capped if c.sr(mid(p))[1] * gone < 0]}
            elif capped and not near:
                scap = max(max(c.sr(q)[0] * e for q in p) for p in capped) * e
                info = {"kind": "uturn", "stop": scap - e * ro}
            elif any(o.kind == "avenue" and abs(abs(o.t[0] * c.t[0] + o.t[1] * c.t[1]) - 1 / R2) < 0.01 and
                     min(abs(o.sr(c.at(se, 0))[0] - o.s0), abs(o.sr(c.at(se, 0))[0] - o.s1)) < 1.2 for o in near):
                notes.append("bend into the straight avenue: each lane meets the straight avenue's lane of the same "
                             "side and rank on the joint line (no new lanes)")
                info = {"kind": "bend", "stop": se + e * 0.5,
                        "to": [o for o in near if o.kind == "avenue"][0]}
            ends[(id(c), e)] = info
        c.ends = {e: ends[(id(c), e)] for e in (-1, 1)}
    # corridor lines
    for c in cors:
        if c.kind == "band":
            lo, hi = ends[(id(c), -1)], ends[(id(c), 1)]
            for r, sg in c.lanes:
                s0, s1 = lo["stop"], hi["stop"]
                for e, en in ((-1, lo), (1, hi)):
                    if en["kind"] == "bend":                 # end on the straight avenue's first cell line
                        o = en["to"]
                        sa = o.s0 - 0.5 if abs(o.sr(c.at(en["stop"], 0))[0] - o.s0) < abs(
                            o.sr(c.at(en["stop"], 0))[0] - o.s1) else o.s1 + 0.5
                        f0, f1 = o.sr(c.at(0, r))[0], o.sr(c.at(1, r))[0]
                        sb = (sa - f0) / (f1 - f0)
                        s0, s1 = (sb, s1) if e < 0 else (s0, sb)
                for e, en in ((-1, lo), (1, hi)):
                    if en["kind"] == "merge" and r * en["gone"] > 0:
                        if e < 0:
                            s0 = en["nose"] + en["L"]
                        else:
                            s1 = en["nose"] - en["L"]
                    if en["kind"] == "merge" and r * en["gone"] < 0 and abs(r) < ri + 1e-6:
                        if e < 0:                            # the continuing side's inner lane starts after the split
                            s0 = en["nose"] + 0.9
                        else:
                            s1 = en["nose"] - 0.9
                a, bb = c.at(s0, r), c.at(s1, r)
                out.append(([a, bb] if sg > 0 else [bb, a], col(c, sg), 3))
            for e, en in ((-1, lo), (1, hi)):
                if en["kind"] != "merge":
                    continue
                for p in en.get("tail", ()):
                    out.append((p, GREY, 3))                 # the stub's stock cap
                g = en["gone"]
                for r in (-g * ri, -g * ro):              # the single road: the continuing staircase, two-way
                    sg = -1 if r > 0 else 1
                    if abs(r) < ri + 1e-6:
                        sg = -sg                             # its inner lane runs the ending side's way
                    s0, s1 = sorted((en["nose"] + e * (0.5 if abs(r) < ri + 1e-6 else 0.0), en["far"]))
                    a, bb = c.at(s0, r), c.at(s1, r)
                    out.append(([a, bb] if sg > 0 else [bb, a], GREY, 3))
        else:
            for r, sg in c.lanes:
                a, bb = c.at(c.s0 - 0.5, r), c.at(c.s1 + 0.5, r)
                out.append(([a, bb] if sg > 0 else [bb, a], GREY if c.kind == "road" else col(c, sg), 3))
    # the new lanes at the band ends
    for c in bands:
        for e in (-1, 1):
            en = ends[(id(c), e)]
            if en["kind"] == "merge":
                g, sn, TL = en["gone"], en["nose"], en["L"]
                rci, rco = -g * ri, -g * ro
                if -g == e:                                  # the ending side arrives at the end: into the road
                    for r in (g * ri, g * ro):
                        out.append((smooth(c, sn - e * TL, r, sn + e * 0.5, rci), GREEN, 3))
                    out.append((smooth(c, sn + e * 0.5, rco, sn - e * 0.9, rci), GREEN, 3))
                else:
                    for r in (g * ri, g * ro):
                        out.append((smooth(c, sn + e * 0.5, rci, sn - e * TL, r), GREEN, 3))
                    out.append((smooth(c, sn - e * 0.9, rci, sn + e * 0.5, rco), GREEN, 3))
                notes.append(("one drag a step longer: the shorter side ends, the longer goes on as a two-way stub "
                              "(lanes as a merge)") if en.get("tail") else
                             "merge: the ending carriageway's two lanes join the single road's lane, the single "
                             "road's other lane widens to two")
            elif en["kind"] == "uturn":
                se = en["stop"]
                for r in (ri, ro):
                    out.append(([c.at(se + e * r * math.sin(math.pi * k / 16.0), -e * r * math.cos(math.pi * k / 16.0))
                                 for k in range(17)], GREEN, 3))
                notes.append("free end: two-lane U-turn around the median nose, outer lane to outer lane")
            elif en["kind"] == "bend" and False:
                o = en["to"]
                so = o.s0 - 0.5 if abs(o.sr(c.at(en["stop"], 0))[0] - o.s0) < abs(o.sr(c.at(en["stop"], 0))[0] - o.s1) \
                    else o.s1 + 0.5
                for r, sg in c.lanes:
                    p = c.at(en["stop"], r)
                    # the avenue lane on the same side, same rank (outer / inner)
                    side = 1 if o.sr(p)[1] > 0 else -1
                    rank = 0 if abs(r) < ri + 1e-6 else 1
                    q = o.at(so, side * LANE_R["avenue"][rank])
                    X = _isect(c, r, o, side * LANE_R["avenue"][rank]) or q
                    pts = bez(p, X, q)
                    out.append((pts if sg * e > 0 else pts[::-1], GREEN, 3))
                notes.append("bend into the straight avenue: lanes keep their side and order (outer to outer)")
    # turns where two corridors cross
    nt = 0
    HALF = {"road": 0.5, "avenue": 1.0, "band": 0.75}

    def rng(c):
        if c.kind == "band":
            return ends[(id(c), -1)]["stop"], ends[(id(c), 1)]["stop"]
        return c.s0 - 0.5, c.s1 + 0.5
    for c1 in cors:
        for c2 in cors:
            cosang = c1.t[0] * c2.t[0] + c1.t[1] * c2.t[1]
            if c2 is c1 or abs(cosang) > 0.9:
                continue
            if any(ends.get((id(c), e), {}).get("to") in (c1, c2) for c in (c1, c2) for e in (-1, 1)):
                continue                             # a band and the straight avenue it bends into
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
                    X = _isect(c1, r1, c2, r2)
                    if X is None:
                        continue
                    phi = math.acos(max(-1.0, min(1.0, h1[0] * h2[0] + h1[1] * h2[1])))
                    lead = (0.45 if left else 0.3) * math.tan(phi / 2)
                    s1x, s2x = c1.sr(X)[0], c2.sr(X)[0]
                    w1, w2 = 3.0 * HALF[c2.kind], 3.0 * HALF[c1.kind]   # X may lie across the other corridor
                    if not (lo1 - w1 <= s1x <= hi1 + w1 and lo2 - w2 <= s2x <= hi2 + w2):
                        continue
                    a = min(max(s1x - sgn1 * lead, lo1), hi1)
                    b = min(max(s2x + sgn2 * lead, lo2), hi2)
                    if (s1x - a) * sgn1 < 0.05 or (b - s2x) * sgn2 < 0.05:
                        continue                     # no road behind the turn's start or past its end
                    out.append((bez(c1.at(a, r1), X, c2.at(b, r2)), GREEN, 2))
                    nt += 1
    if nt:
        notes.append("%d turning lanes (green, thin): right turn from the outer lane, left turn from the inner lane "
                     "through the median opening" % nt)
    return out, notes


def draw_world(want, polys, out, title="", lines=(), scale=0.42):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("arial.ttf", 13)
    xs = [c[0] for c in want]
    zs = [c[1] for c in want]
    X0, X1, Z0, Z1 = min(xs), max(xs), min(zs), max(zs)
    S = T * scale
    pad = 30
    W = int((X1 - X0 + 1) * S) + 2 * pad
    H = int((Z1 - Z0 + 1) * S) + 2 * pad + 18 * (1 + len(lines))
    im = Image.new("RGB", (W, H), (250, 250, 247))
    d = ImageDraw.Draw(im)

    def px(x, z):                           # game x to the LEFT
        return pad + (X1 + 1 - x) * S, pad + (z - Z0) * S
    for (cx, cz), (pid, st) in sorted(want.items()):
        a, b = px(cx, cz), px(cx + 1, cz + 1)
        d.rectangle([b[0], a[1], a[0], b[1]], outline=(185, 185, 185), fill=(228, 228, 224))
        d.text((b[0] + 3, a[1] + 2), "%s.%d" % (pid, st) if pid != "" else "", fill=(120, 120, 120), font=font)
    for pts, col, w in polys:
        q = [px(*p) for p in pts]
        d.line(q, fill=col, width=w)
        (ax, ay), (bx, by) = q[-2], q[-1]
        ang = math.atan2(by - ay, bx - ax)
        for da in (2.6, -2.6):
            d.line([(bx, by), (bx + 9 * math.cos(ang + da), by + 9 * math.sin(ang + da))], fill=col, width=w)
    y = H - 18 * (1 + len(lines)) + 4
    for t in ([title] if title else []) + list(lines):
        d.text((pad, y), t, fill=(20, 20, 20), font=font)
        y += 18
    if out:
        im.save(out)
    return im


# ------------------------------------------------------------------------------------------------ drawing
def draw(want, L, out, title="", lines=(), scale=0.42, lanes_of=None, colour_of=None):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("arial.ttf", 13)
    xs = [c[0] for c in want]
    zs = [c[1] for c in want]
    X0, X1, Z0, Z1 = min(xs), max(xs), min(zs), max(zs)
    S = T * scale
    pad = 30
    W = int((X1 - X0 + 1) * S) + 2 * pad
    H = int((Z1 - Z0 + 1) * S) + 2 * pad + 18 * (1 + len(lines))
    im = Image.new("RGB", (W, H), (250, 250, 247))
    d = ImageDraw.Draw(im)

    def px(cx, cz, lx, lz):                 # game x to the LEFT
        return pad + (X1 + 1 - (cx + lx / T)) * S, pad + (cz - Z0 + lz / T) * S
    for (cx, cz), (pid, st) in sorted(want.items()):
        a, b = px(cx, cz, 0, 0), px(cx, cz, 256, 256)
        d.rectangle([b[0], a[1], a[0], b[1]], outline=(185, 185, 185), fill=(228, 228, 224))
        d.text((b[0] + 3, a[1] + 2), "%d.%d" % (pid, st), fill=(110, 110, 110), font=font)
    for (cx, cz), (pid, st) in sorted(want.items()):
        lanes = lanes_of(cx, cz, pid, st) if lanes_of else L.lanes(pid, st)
        for ln in lanes:
            col = colour_of(cx, cz, ln) if colour_of else (40, 40, 40)
            pts = [px(cx, cz, x, z) for (x, z) in ln["pts"]]
            d.line(pts, fill=col, width=3)
            (ax, ay), (bx, by) = pts[-2], pts[-1]
            ang = math.atan2(by - ay, bx - ax)
            for da in (2.6, -2.6):
                d.line([(bx, by), (bx + 9 * math.cos(ang + da), by + 9 * math.sin(ang + da))], fill=col, width=3)
    y = H - 18 * (1 + len(lines)) + 4
    for t in ([title] if title else []) + list(lines):
        d.text((pad, y), t, fill=(20, 20, 20), font=font)
        y += 18
    if out:
        im.save(out)
    return im


# ------------------------------------------------------------------------------------------------ hwave diagonal transition
# hwave_build.py's diagonal frame (state 0): band middle line p = x - z = 0, q = x + z along, the highway at low q, the
# deck lands at q 23 (hwave_paint D_LAND), the avenue beyond. p > 0 = the x+ side.
HW_EX = (0.396 * R2, 0.170 * R2)          # highway exit carriageway (p > 0, drives +q): outer, inner (hwlanes DIAG_LANES)
DAV_HI = (12.0 - (11.0 + 80 / 255.0), 12.0 - (11.0 + 175 / 255.0))     # the avenue's p > 0 strip: outer, inner


def _pq(p, q):
    return ((q + p) / 2.0, (q - p) / 2.0)


def hwave_lines(today):
    """-> [(pts, colour, width)] of the transition's four lanes from q 12 to q 30 (world x, z), today's (hwave_build
    d_lane_decks: the exit's inner lane and the avenue's outgoing lanes cross the median) or the one-way plan (each lane
    keeps its side and rank)"""
    def across(p0, p1, q0, q1, n=12):
        return [_pq(p0 + (p1 - p0) * u * u * (3 - 2 * u), q0 + (q1 - q0) * u) for u in (k / float(n) for k in range(n + 1))]
    out = []
    (eo, ei), (ho, hi) = HW_EX, DAV_HI
    if today:
        out.append(([_pq(eo, 12)] + across(eo, ho, 20.5, 22.99) + [_pq(ho, 30)], RED, 3))
        out.append(([_pq(ei, 12)] + across(ei, -hi, 19.8, 22.0) + [_pq(-hi, 30)], RED, 3))
        out.append(([_pq(-ho, 30)] + across(-ho, -eo, 22.99, 20.5) + [_pq(-eo, 12)], BLUE, 3))
        out.append(([_pq(hi, 30)] + across(hi, -ei, 21.4, 20.1) + [_pq(-ei, 12)], BLUE, 3))
    else:
        for e, h in ((eo, ho), (ei, hi)):
            out.append(([_pq(e, 12)] + across(e, h, 20.0, 23.0) + [_pq(h, 30)], RED, 3))
            out.append(([_pq(-h, 30)] + across(-h, -e, 23.0, 20.0) + [_pq(-e, 12)], BLUE, 3))
    return out


def hwave_cells():
    cells = {}
    for X in range(4, 17):
        for Z in range(4, 17):
            q, p = X + Z + 1, X - Z
            if 12 <= q <= 30 and abs(p) <= (1 if q < 22 else 1):
                cells[(X, Z)] = ("hw" if q < 20 else "DAV" if q > 23 else "")
    for c, pid in {(10, 9): 21604, (9, 10): 21605, (10, 10): 21606, (11, 10): 21607, (10, 11): 21608,
                   (11, 11): 21609}.items():
        cells[c] = str(pid)
    return {c: (v, 0) for c, v in cells.items()}


# ------------------------------------------------------------------------------------------------ owner sheet
SHEET_ROWS = [
    ("end", "Band and free ends", "each drag a two-way road; each end a one-road cap",
     "one carriageway per direction, 2 lanes; the end is a two-lane U-turn around the median nose"),
    ("tail", "One drag a step longer", "the longer road's cap sticks out",
     "the shorter side ends; the longer goes on as a short two-way stub, lanes joined as at a merge"),
    ("merge", "Merge into a single road", "the ending road caps (U-turn inside its own carriageway)",
     "its 2 lanes join the single road's lane; the single road's other lane widens to 2"),
    ("bend", "Bend into the straight avenue", "two-way halves meet two-way halves",
     "same lane positions, one direction per side: no new lanes, only directions"),
    ("cross-x", "Road crossing the avenue", "turns only where lanes happen to share a node",
     "median opening: every turn (right from the outer lane, left from the inner lane)"),
    ("T-W", "Road meeting the avenue from one side", "as above", "4 movements, all connected"),
    ("stem-top", "Avenue ending on a road", "the avenue's lanes run on through the road into empty land",
     "arriving side turns left / right, the road feeds the leaving side"),
    ("XSX", "Diagonal x straight avenue", "straight through only (both two-way)",
     "through + 8 turns, both avenues one-way"),
    ("TSX", "Diagonal ending on the straight avenue", "the diagonal caps at the avenue", "4 turns"),
    ("XX0", "Diagonal x diagonal", "straight through only", "through + 8 turns"),
    ("TX0", "Diagonal ending on a diagonal", "caps", "4 turns"),
]


def _panel(im, maxw):
    if im.width > maxw:
        im = im.resize((maxw, int(im.height * maxw / im.width)))
    return im


def cmd_sheet(a):
    from PIL import Image, ImageDraw, ImageFont
    L = Lanes()
    FT, FB, F = (ImageFont.truetype(n, s) for n, s in (("arialbd.ttf", 26), ("arialbd.ttf", 19), ("arial.ttf", 16)))
    rows = [r for r in SHEET_ROWS if not a.kinds or r[0] in a.kinds.split(",")]
    PW = 560
    panels = []
    for kind, title, t_today, t_new in rows:
        want, road, notes, cors = scene(kind)
        today = draw(want, L, None, scale=0.3)
        polys, n2 = proposed(want, road, cors, L)
        new = draw_world(want, polys, None, scale=0.3)
        special = [c for c, (p, st) in want.items() if isinstance(p, int) and 20510 <= p <= 20599 and not
                   20520 <= p <= 20534]
        if special and len(want) > 60:                 # a crossing: the plan zoomed on its special cells
            cx = sum(c[0] for c in special) / float(len(special))
            cz = sum(c[1] for c in special) / float(len(special))
            box = {c: v for c, v in want.items() if abs(c[0] + .5 - cx) <= 3.6 and abs(c[1] + .5 - cz) <= 3.6}

            def inside(p):
                return abs(p[0] - cx) <= 3.6 and abs(p[1] - cz) <= 3.6
            clipped = []
            for pts, cl, w in polys:
                dense = [pts[0]]
                for p0, p1 in zip(pts, pts[1:]):
                    n = max(1, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 0.05))
                    dense += [(p0[0] + (p1[0] - p0[0]) * k / n, p0[1] + (p1[1] - p0[1]) * k / n) for k in range(1, n + 1)]
                run = []
                for p in dense + [None]:
                    if p is not None and inside(p):
                        run.append(p)
                    else:
                        if len(run) > 1:
                            clipped.append((run, cl, w + 1))
                        run = []
            new = draw_world(box, clipped, None, scale=0.62)
            t_new += "  (zoomed on the crossing)"
        panels.append((title, t_today, t_new, _panel(today, PW), _panel(new, PW)))
        print(kind, notes + n2)
    if a.hwave:
        cells = hwave_cells()
        panels.append(("hwave diagonal transition (highway <-> diagonal avenue), 21604..21609",
                       "the exit's inner lane and the avenue's leaving lanes cross the median",
                       "no crossing: each highway lane drops onto the carriageway lane of its side and rank",
                       _panel(draw_world(cells, hwave_lines(True), None, scale=0.3), PW),
                       _panel(draw_world(cells, hwave_lines(False), None, scale=0.3), PW)))
    BW = 2 * PW + 30                                  # one pair (today | plan)
    NC = 2                                            # pairs per row
    rowsH = []
    for k in range(0, len(panels), NC):
        rowsH.append(max(max(p[3].height, p[4].height) for p in panels[k:k + NC]) + 74)
    W = NC * BW + (NC + 1) * 30
    H = 120 + sum(rowsH) + 30 * len(a.foot) + 20
    sh = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(sh)
    d.text((20, 14), a.title, font=FT, fill=(0, 0, 0))
    d.text((20, 50), "In each pair, left: today's lanes (from the package and stock records), right: the plan. Red / blue = "
           "the two directions, green = new lanes (U-turns, merges, turns). Game x to the left, z down (as view 0).",
           font=F, fill=(40, 40, 40))
    d.text((20, 74), "Right-hand traffic: every carriageway drives with the median on its left (as the highways). On a "
           "diagonal the curb-side lane already runs that way, the median-side lane is reversed.",
           font=F, fill=(40, 40, 40))
    y = 112
    for k in range(0, len(panels), NC):
        for m, (title, t_today, t_new, im1, im2) in enumerate(panels[k:k + NC]):
            x = 30 + m * (BW + 30)
            d.text((x, y), title, font=FB, fill=(0, 0, 0))
            d.text((x, y + 24), "today: " + t_today, font=F, fill=(90, 90, 90))
            d.text((x, y + 44), "plan: " + t_new, font=F, fill=(20, 110, 40))
            sh.paste(im1, (x, y + 68))
            sh.paste(im2, (x + PW + 30, y + 68))
            d.line([(x + PW + 15, y + 68), (x + PW + 15, y + 68 + max(im1.height, im2.height))], fill=(200, 200, 200), width=2)
        y += rowsH[k // NC]
    for t in a.foot:
        d.text((20, y), t, font=F, fill=(0, 0, 0))
        y += 30
    sh.save(a.out)
    print(a.out, sh.size)


# ------------------------------------------------------------------------------------------------ joins with AVL
# AVENUE_LANES.md 5: a straight band (sc3netmod_avl.c) may END on a sibling's piece declared `avlj <piece> <NESW>`
# (per side at the piece's state 0: I = a one-way half's traffic enters across it, O = leaves, . = none). The diagonal
# pieces that a straight band can end on (bends, XS / TS crossings) get their letters from the planned lanes: every
# one-way through lane (band carriageways, straight avenue halves) that crosses a side of the cell.
SIDE_N = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}         # N E S W outward normals (N = -z)


def scene_turned(kind, k, rows=7):
    """scene() turned k states: (x, z) -> (-z - 1, x) per state (diagave._xrot), stock states + k"""
    want, road, notes, cors = scene(kind, rows)
    if k % 4 == 0:
        return want, road, notes, cors
    stock = {DA._xrot(c, k): (p, (s + k) % 4) for c, (p, s) in want.items() if p == 11204}
    road2 = {DA._xrot(c, k) for c in road}
    want2, notes2 = {}, []
    bs = DA.bands(road2)
    for b in bs:
        w = DA.wanted(b)
        notes2.append("band axis %d rows %d: %s" % (b["axis"], len(b["rows"]), "converts" if w else b["why"]))
        want2.update(w or {})
    for c in road2:
        if c not in want2:
            want2[c] = stock.get(c) or (29, 0 if ((c[0] - 1, c[1]) in road2 or (c[0] + 1, c[1]) in road2) else 1)
    cors2 = [Cor.band(b, road2) for b in bs if b["ok"]] + Cor.avenues(stock)
    return want2, road2, notes2, cors2


def cell_letters(want, road, cors, L):
    """-> {cell: [N, E, S, W] world letters} for the cells crossed by one-way through lanes ('X' = both ways)"""
    proposed(want, road, cors, L)                      # sets c.ends on the bands
    out = {}
    for c in cors:
        if c.kind not in ("band", "avenue"):
            continue
        lo, hi = (c.ends[-1]["stop"], c.ends[1]["stop"]) if c.kind == "band" else (c.s0 - 0.5, c.s1 + 0.5)
        for r, sg in c.lanes:
            p0, p1 = c.at(lo, r), c.at(hi, r)
            d = (sg * c.t[0], sg * c.t[1])
            for cell in want:
                if c.kind == "band" and cell not in c.cells:
                    continue
                cx, cz = cell
                for side, (nx, nz) in SIDE_N.items():
                    # the side's line: x = cx (W) / cx + 1 (E), z = cz (N) / cz + 1 (S)
                    axis = 0 if nx else 1
                    val = (cx + (1 if nx > 0 else 0)) if nx else (cz + (1 if nz > 0 else 0))
                    a, b = (p0[axis], p1[axis])
                    if abs(b - a) < 1e-9 or not min(a, b) - 1e-9 <= val <= max(a, b) + 1e-9:
                        continue
                    u = (val - a) / (b - a)
                    q = p0[1 - axis] + u * (p1[1 - axis] - p0[1 - axis])
                    base = cz if axis == 0 else cx
                    if not base + 0.02 < q < base + 0.98:
                        continue
                    let = "O" if d[0] * nx + d[1] * nz > 0 else "I"
                    cur = out.setdefault(cell, [".", ".", ".", "."])
                    cur[side] = let if cur[side] in (".", let) else "X"
    return out


def piece_letters(want, letters):
    """world letters -> {piece: set of state-0 letter strings} (avl_letter reads e[(w - st) & 3])"""
    out = {}
    for cell, lw in letters.items():
        pid, st = want[cell]
        if not (isinstance(pid, int) and 20500 <= pid <= 20599):
            continue
        e = "".join(lw[(k + st) % 4] for k in range(4))
        out.setdefault(pid, set()).add(e)
    return out


def avl_ends(want, letters_of):
    """sc3netmod_avl.c's band walk and end test on stock 11204 cells: -> [(axis, row cells, end, verdict)]"""
    def st_at(c, sid):
        v = want.get(c)
        return v is not None and v[0] == 11204 and v[1] == sid
    res, seen = [], set()
    for (x, z), (p, s) in sorted(want.items()):
        for axis in (0, 1):                                      # 0 = along z (A x, B x+1), 1 = along x (A z, B z+1)
            sa, sb = (1, 3) if axis == 0 else (2, 0)
            dx, dz = (0, 1) if axis == 0 else (1, 0)
            ox, oz = (1, 0) if axis == 0 else (0, 1)

            def row(k):
                a = (x + dx * k, z + dz * k)
                return st_at(a, sa) and st_at((a[0] + ox, a[1] + oz), sb)
            if (axis, x, z) in seen or not row(0):
                continue
            k0 = k1 = 0
            while row(k0 - 1):
                k0 -= 1
            while row(k1 + 1):
                k1 += 1
            for k in range(k0, k1 + 1):
                seen.add((axis, x + dx * k, z + dz * k))
            for end, k in ((-1, k0 - 1), (1, k1 + 1)):
                a = (x + dx * k, z + dz * k)
                b = (a[0] + ox, a[1] + oz)
                if a not in want and b not in want:
                    res.append((axis, a, end, "scene edge"))
                    continue
                fwd = end > 0
                face = (3 if fwd else 1) if axis else (0 if fwd else 2)
                toward = (1 if fwd else 3) if axis else (2 if fwd else 0)
                da, db = (1, 3) if axis else (0, 2)
                la, lb = letters_of(a, face), letters_of(b, face)
                need = ("I" if da == toward else "O", "I" if db == toward else "O")
                ok = (la, lb) == need
                res.append((axis, a, end, "%s (%s %s: letters %s %s, need %s %s)" % (
                    "ACCEPTED" if ok else "refused", want.get(a), want.get(b), la, lb, need[0], need[1])))
    return res


def cmd_joins(a):
    """every scene where a straight avenue meets the diagonal (bends, XS / TS crossings) at 4 turns: the letters each
    diagonal piece would declare, their consistency, and sc3netmod_avl.c's end test with them"""
    L = Lanes()
    allp = {}
    runs = []
    for kind in a.kinds.split(","):
        for k in range(4):
            want, road, notes, cors = scene_turned(kind, k)
            lt = cell_letters(want, road, cors, L)
            for pid, es in piece_letters(want, lt).items():
                allp.setdefault(pid, set()).update(es)
            runs.append((kind, k, want, lt))
    decl = {}
    bad = 0
    for pid in sorted(allp):
        es = allp[pid]
        merged = ["".join(sorted(set(e[i] for e in es) - {"."})) or "." for i in range(4)]
        ok = all(len(m) == 1 for m in merged)
        bad += not ok
        decl[pid] = "".join(m if len(m) == 1 else "?" for m in merged)
        if a.verbose or not ok:
            print("letters %d %s%s" % (pid, decl[pid], "" if ok else "   CONFLICT %s" % sorted(es)))
    used = set()
    for kind, k, want, lt in runs:
        def letter(c, w):
            v = want.get(c)
            if not v or v[0] not in decl:
                return None
            return decl[v[0]][(w - v[1]) % 4]
        for axis, cell, end, verdict in avl_ends(want, letter):
            if a.verbose or not verdict.startswith(("ACCEPTED", "scene")):
                print("%s turn %d: straight band along %s, %s end at %s: %s" % (
                    kind, k, "z" if axis == 0 else "x", "back" if end < 0 else "forward", cell, verdict))
            bad += verdict.startswith("refused")
            if verdict.startswith("ACCEPTED"):
                ox, oz = (1, 0) if axis == 0 else (0, 1)
                used |= {want[cell][0], want[(cell[0] + ox, cell[1] + oz)][0]}
    print("pieces a straight band ends on (declare these, a side with both directions as '.'):")
    for pid in sorted(used):
        print("  avlj %d %s" % (pid, decl[pid].replace("?", ".")))
    print("problems: %d" % bad)
    return 1 if bad else 0


def cmd_scene(a):
    L = Lanes()
    want, road, notes, cors = scene(a.kind)
    if a.proposed:
        polys, n2 = proposed(want, road, cors, L)
        notes += n2
        draw_world(want, polys, a.out, title="%s (proposed: one-way halves, right-hand)" % a.kind, lines=notes)
    else:
        draw(want, L, a.out, title="%s (today's lanes)" % a.kind, lines=notes)
    print(a.out, notes)
    for c, v in sorted(want.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        print(c, v)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scene")
    s.add_argument("out")
    s.add_argument("kind")
    s.add_argument("--proposed", action="store_true")
    s = sub.add_parser("joins")
    s.add_argument("--kinds", default="bend,bend_x,XSX,XSZ,TSX,TSZ")
    s.add_argument("--verbose", action="store_true")
    s = sub.add_parser("sheet")
    s.add_argument("out")
    s.add_argument("--kinds", default="")
    s.add_argument("--hwave", action="store_true")
    s.add_argument("--title", default="Diagonal avenues on one-way halves (avdiag plan)")
    s.add_argument("--foot", action="append", default=[])
    a = ap.parse_args(argv)
    return {"scene": cmd_scene, "sheet": cmd_sheet, "joins": cmd_joins}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
