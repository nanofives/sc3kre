#!/usr/bin/env python3
r"""ctm_lanes.py - M2 of re/analysis/CAR_TRIPS.md: turn a captured router path into a drivable lane route (offline).

Lane graph per cell, as STRTSIM's cars use it (NET_LANES 2, decoded again for this task):
  - nodes: (class, x, z) in tile units 0..255; edges: internal (target node) or exit (code: side * 8)
  - crossing (FUN_1001c750): exit edge code -> next cell = cell + EXIT_STEP[code >> 2]; the next cell must hold a
    class-0 occupant passing the road predicate (0x1001ac90: occupant flags & 0x8000 or & 0x10000) with a graph; the
    arrival node is FUN_10020108(graph, pos.x - next.x * 256, pos.z - next.z * 256, class): bucket
    ((x + 16) / 72, (z + 16) / 72) of 4 x 4 (unsigned: below -16 or from 272 up there is none), one node -> it if
    its class matches, several -> the nearest of the class (squared distance, first minimum); pos = the car's
    position = the exit node's position (exit edges carry no curve, FUN_100201d8 zeroes it); then the arrival
    node's chosen edge must be internal (`[edge+4] != 0` at 0x1001c87e)
  - sim rect: a car never enters a cell outside it (0x1001c7bc)

Graph sources:
  save   the city save's surface network (network_layer) + TrBlkAtt records id*0x100+state (missing -> road 29 state 0,
         STRTSIM DAT_10033064); every tile with class-0 lane nodes counts as drivable (approximation of the occupant
         predicate, checked against the in-game dump)
  dump   the graphs sc3cartrips.dll read from game memory (cartrips_graphs.bin)

Route (PRE M2): the in-view window of a dumped trip in travel order; each maximal run of road nodes (types 1, 2, 3)
clipped to the sim rect is one route r0..rk.

Checks per route:
  literal   every middle step a -> b -> c: b's lanes take the car from the side facing a to the side facing c
  corridor  a lane path (search below) from any class-0 node of r0 to any node of rk (and, when the route leaves
            the rect after rk, an exit edge of rk toward r(k+1)), through cells of the corridor, visiting the route in
            order: state = (cell, node, j), j = last route index matched; entering route cell r(i), j < i <= j + SKIP
            sets j = i; every cell entered lies within distance 1 (4-neighbourhood) of r(j) or r(j+1), inside the
            rect. Cost: 1 per lane edge, +OFFROUTE per entry into a cell that is not a route cell. Dijkstra.
"""
import argparse
import collections
import heapq
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network_layer  # noqa: E402
from netmod import lanekit  # noqa: E402
import ctm_read  # noqa: E402

ROAD = (1, 2, 3)
STEP = {0: (-1, 0), 2: (0, -1), 4: (1, 0), 6: (0, 1)}          # code >> 2 for vehicle exits (side * 8)
SIDE_OF = {(-1, 0): 0, (0, -1): 1, (1, 0): 2, (0, 1): 3}
SKIPC = 3          # cost per skipped route cell
OFFC = 1           # cost per entry into a corridor cell that is not a route cell
BACK = 2           # how far behind the reached route index a cell may lie
WIDE_START = True  # w >= 1: start on any corridor cell around r0 too (the spawn lane is the mod's choice)


class Graph:
    __slots__ = ("key", "cls", "x", "z", "edges", "buckets", "incoming")

    def __init__(self, key, nodes):
        """nodes: [(cls, x, z, [(to | None, code), ...]), ...] in record order."""
        self.key = key
        self.cls = [n[0] for n in nodes]
        self.x = [n[1] for n in nodes]
        self.z = [n[2] for n in nodes]
        self.edges = [n[3] for n in nodes]
        self.buckets = collections.defaultdict(list)
        for i in range(len(nodes)):
            bx, bz = (self.x[i] + 16) // 72, (self.z[i] + 16) // 72
            self.buckets[(bx, bz)].append(i)
        self.incoming = set(t for es in self.edges for t, c in es if t is not None)

    def lookup(self, rx, rz, cls=0):
        if rx + 16 < 0 or rz + 16 < 0:
            return None
        bx, bz = (rx + 16) // 72, (rz + 16) // 72
        if bx >= 4 or bz >= 4:
            return None
        lst = self.buckets.get((bx, bz), [])
        if len(lst) == 1:
            return lst[0] if self.cls[lst[0]] == cls else None
        best, bd = None, 10000000
        for i in lst:
            if self.cls[i] != cls:
                continue
            d = (rz - self.z[i]) ** 2 + (rx - self.x[i]) ** 2
            if d < bd:
                best, bd = i, d
        return best

    def has_internal(self, i):
        return any(t is not None for t, c in self.edges[i])

    def turns(self, cls=0):
        """(entry side, exit side) pairs, lanekit.lane_turns rule on this graph."""
        out = set()
        for i in range(len(self.cls)):
            if i in self.incoming or self.cls[i] != cls:
                continue
            for s_in in lanekit.boundary_sides(self.x[i], self.z[i]):
                seen, st = set(), [i]
                while st:
                    j = st.pop()
                    if j in seen:
                        continue
                    seen.add(j)
                    for t, c in self.edges[j]:
                        if t is None:
                            if c % 8 == 0:
                                out.add((s_in, c // 8))
                        else:
                            st.append(t)
        return out


class SaveGraphs:
    """cell (x, z) -> (Graph or None, piece, state, has_record)"""

    def __init__(self, city, lang="ENGLISH"):
        self.tiles = {}
        for x, y, z, state, piece, props in network_layer.read_networks(city)[0][1]:
            self.tiles[(x, y)] = (piece, state)
        g = lanekit.Game()
        self.trb = g.trblkatt(lang)
        self.cache = {}
        self.default_key = 29 * 0x100

    def record(self, key):
        if key not in self.cache:
            blob = self.trb.get(key)
            if blob is None:
                self.cache[key] = None
            else:
                rec = lanekit.decode(blob)
                self.cache[key] = Graph(key, [(n["cls"], n["x"], n["z"], [(e["to"], e["code"]) for e in n["edges"]])
                                              for n in rec["veh"]])
        return self.cache[key]

    def at(self, cell):
        t = self.tiles.get(cell)
        if t is None:
            return None, None, None, False
        piece, state = t
        key = piece * 0x100 + state
        g = self.record(key)
        has = g is not None
        if g is None:
            g = self.record(self.default_key)
        if not any(c == 0 for c in g.cls):
            return None, piece, state, has
        return g, piece, state, has


class DumpGraphs:
    """the graphs sc3cartrips.dll read from game memory (cartrips_graphs.bin, 'TCG1'): cell (x, z) -> (Graph or None,
    None, None, True); status per cell as the DLL's graph_at returned it (0 ok, 1 off map, 2 no layer, 3 no occupant,
    4 not a road, 5 no QI, 6 no graph, 7 fault)"""
    STATUS = ["ok", "off-map", "no-layer", "no-occupant", "not-road", "no-qi", "no-graph", "fault"]

    def __init__(self, path):
        b = open(path, "rb").read()
        magic, ver = struct.unpack_from("<II", b, 0)
        if magic != 0x31474354:
            raise SystemExit("not a TCG1 dump: %s" % path)
        o, self.graphs, self.cells = 8, {}, {}
        while o < len(b):
            t = b[o]
            if t == 1:
                ptr, n = struct.unpack_from("<IH", b, o + 1)
                o += 7
                nodes = []
                for _ in range(n):
                    cls, x, z, ne = struct.unpack_from("<biiB", b, o)
                    o += 10
                    es = []
                    for _ in range(ne):
                        to, code = struct.unpack_from("<hB", b, o)
                        o += 3
                        es.append((None if to < 0 else to, code))
                    nodes.append((cls, x, z, es))
                self.graphs[ptr] = Graph(ptr, nodes)
            elif t == 2:
                x, z, st, ptr = struct.unpack_from("<hhBI", b, o + 1)
                o += 10
                self.cells[(x, z)] = (st, ptr)
            else:
                raise SystemExit("bad record type %d at %d" % (t, o))

    def at(self, cell):
        st, ptr = self.cells.get(cell, (None, 0))
        g = self.graphs.get(ptr) if st == 0 else None
        return g, None, None, True


def read_routes(path):
    """cartrips_routes.bin ('TCR1'): per solved route: seq, ridx, cells, rect, us, then the width-1 result with its
    lane path and the width-0 result"""
    b = open(path, "rb").read()
    magic, ver = struct.unpack_from("<II", b, 0)
    if magic != 0x31524354:
        raise SystemExit("not a TCR1 dump: %s" % path)
    o, out = 8, []
    while o + 20 <= len(b):
        seq, ridx, n, rx0, rz0, rx1, rz1, us = struct.unpack_from("<IHH4hI", b, o)
        o += 20
        cells = [struct.unpack_from("<hh", b, o + 4 * i) for i in range(n)]
        o += 4 * n
        res = []
        for w in (1, 0):
            ok, reason, jmax, cost, skipped, off, exp, npath = struct.unpack_from("<BBHIHHIH", b, o)
            o += 18
            path = [struct.unpack_from("<hhB", b, o + 5 * i) for i in range(npath)]
            o += 5 * npath
            res.append({"ok": ok, "reason": reason, "jmax": jmax, "cost": cost, "skipped": skipped, "offroute": off,
                        "expanded": exp, "path": path})
        out.append({"seq": seq, "ridx": ridx, "cells": cells, "rect": [rx0, rz0, rx1, rz1], "us": us,
                    "w1": res[0], "w0": res[1]})
    return out


def match(graphs_path, routes_path, limit=None):
    """C solver (routes dump) against solve() on the same dumped graphs"""
    G = DumpGraphs(graphs_path)
    rs = read_routes(routes_path)
    st = collections.Counter()
    bad = []
    for r in rs[:limit] if limit else rs:
        route = {"cells": [tuple(c) for c in r["cells"]]}
        for w in (1, 0):
            py = solve(G, route, r["rect"], width=w)
            c = r["w%d" % w]
            st["w%d_routes" % w] += 1
            same = bool(py["ok"]) == bool(c["ok"])
            if same and py["ok"]:
                same = py["cost"] == c["cost"] and py["skipped"] == c["skipped"] and py["offroute_cells"] == c["offroute"]
                if w == 1:
                    same = same and [tuple(x) for x in py["path"]] == [tuple(x) for x in c["path"]]
            elif same:
                same = py["jmax"] == c["jmax"]
            st["w%d_same" % w] += same
            st["w%d_ok_c" % w] += bool(c["ok"])
            if not same and len(bad) < 10:
                bad.append({"seq": r["seq"], "w": w, "c": {k: v for k, v in c.items() if k != "path"},
                            "py": {k: v for k, v in py.items() if k not in ("path", "moves")}})
    return {"counts": dict(st), "mismatches": bad}


def compare_sources(graphs_path, city, lang="ENGLISH"):
    """per cell the DLL read: does the save + TrBlkAtt graph equal the in-memory one (same nodes, edges)?"""
    D = DumpGraphs(graphs_path)
    S = SaveGraphs(city, lang)
    st = collections.Counter()
    diff = collections.Counter()
    for cell, (status, ptr) in D.cells.items():
        gs = S.at(cell)
        gd = D.graphs.get(ptr) if status == 0 else None
        st["cells"] += 1
        st["dll_" + DumpGraphs.STATUS[status]] += 1
        if gd is None and gs[0] is None:
            st["both_none"] += 1
        elif gd is None or gs[0] is None:
            st["one_none"] += 1
            diff[("dll " + DumpGraphs.STATUS[status], "save piece %s/%s" % (gs[1], gs[2]))] += 1
        else:
            # internal edges: memory +0x16 holds the curve's exit heading, the record stores 0; only exit codes matter
            norm = lambda g: (g.cls, g.x, g.z, [[(t, c if t is None else 0) for t, c in es] for es in g.edges])
            a, b = norm(gd), norm(gs[0])
            st["same" if a == b else "different"] += 1
            if a != b:
                diff[("graph differs", "save piece %s/%s" % (gs[1], gs[2]))] += 1
    return {"counts": dict(st), "diffs": [[a, b, n] for (a, b), n in diff.most_common(20)]}


def routes_of(trip):
    """-> list of routes: dict(cells=[(x, z)...], types, lead, tail) in travel order, clipped to the trip's rect."""
    rx0, rz0, rx1, rz1 = trip["rect"]
    nodes = list(reversed(trip["nodes"]))          # travel order
    out, cur = [], []

    def inrect(n):
        return rx0 <= n[0] <= rx1 and rz0 <= n[1] <= rz1

    for k, n in enumerate(nodes):
        x0, z0, x1, z1, ty = n[:5]
        ok = ty in ROAD and x0 == x1 and z0 == z1 and inrect(n)
        if ok:
            cur.append(k)
        if not ok or k == len(nodes) - 1:
            if cur:
                a, b = cur[0], cur[-1]
                cl, ty = [], []
                for i in cur:
                    c = (nodes[i][0], nodes[i][1])
                    if not cl or cl[-1] != c:                 # a lot-entered road cell is popped twice (LANE_DENSITY 1)
                        cl.append(c)
                        ty.append(nodes[i][4])
                out.append({"cells": cl, "types": ty,
                            "before": nodes[a - 1] if a > 0 else None, "after": nodes[b + 1] if b + 1 < len(nodes) else None})
            cur = []
    return out


def neighbours(c):
    x, z = c
    return [(x - 1, z), (x, z - 1), (x + 1, z), (x, z + 1)]


def literal(G, r):
    """phase-1 rule: every middle step drivable on b's lane turns -> (ok, first failing index, reason)"""
    cells = r["cells"]
    for i in range(1, len(cells) - 1):
        a, b, c = cells[i - 1], cells[i], cells[i + 1]
        if a == b or b == c:
            continue
        s_in, s_out = SIDE_OF.get((a[0] - b[0], a[1] - b[1])), SIDE_OF.get((c[0] - b[0], c[1] - b[1]))
        if s_in is None or s_out is None:
            return False, i, "not-adjacent"
        g = G.at(b)[0]
        if g is None:
            return False, i, "no-graph"
        if (s_in, s_out) not in g.turns():
            return False, i, "no-turn"
    return True, None, None


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def solve(G, r, rect, skipc=SKIPC, offc=OFFC, back=BACK, width=1, limit=200000, wide_start=WIDE_START):
    free = 2 if width >= 1 else 1
    """corridor search (PRE addendum 1) -> dict(ok, path=[(x, z, node)], skipped, jmax, expanded, reason...)

    state (cell, node, j), j = route index reached. Corridor = cells within Chebyshev distance `width` of a route cell,
    inside the rect. Entering cell n: M(n) = route indices i with cheb(n, r_i) <= width; j becomes the largest i of
    M(n) in (j, j + 2], else the smallest i > j of M(n) (the i - j - 2 route cells in between are skipped, cost skipc
    each), else stays; n must be within
    distance `width` of some r_i with i >= j - back. Cost 1 per lane edge, + offc when n is not a route cell.
    Start: every class-0 node of r0. Goal: j = k."""
    cells = r["cells"]
    k = len(cells) - 1
    rx0, rz0, rx1, rz1 = rect
    route = set(cells)
    M = collections.defaultdict(list)
    for i, c in enumerate(cells):
        for dx in range(-width, width + 1):
            for dz in range(-width, width + 1):
                n = (c[0] + dx, c[1] + dz)
                if rx0 <= n[0] <= rx1 and rz0 <= n[1] <= rz1 and (not M[n] or M[n][-1] != i):
                    M[n].append(i)
    gcache = {}

    def gat(c):
        if c not in gcache:
            gcache[c] = G.at(c)[0]
        return gcache[c]

    # start cells: r0, then (wide_start, w >= 1) the corridor cells around r0 in dx, dz order, cost offc each
    scells = [cells[0]]
    if wide_start and width >= 1:
        for dx in range(-width, width + 1):
            for dz in range(-width, width + 1):
                c = (cells[0][0] + dx, cells[0][1] + dz)
                if c != cells[0] and c in M:
                    scells.append(c)
    pq, best, prev, seq = [], {}, {}, 0
    nstart = 0
    for c in scells:
        g0 = gat(c)
        if g0 is None:
            continue
        for n in range(len(g0.cls)):
            if g0.cls[n] != 0:
                continue
            s = (c, n, 0)
            d0 = 0 if c == cells[0] else offc
            if d0 < best.get(s, 1e18):
                best[s] = d0
                heapq.heappush(pq, (d0, seq, s))
                seq += 1
                nstart += 1
    if gat(cells[0]) is None and not nstart:
        return {"ok": False, "reason": "start-no-graph", "jmax": 0, "expanded": 0}
    if not nstart:
        return {"ok": False, "reason": "start-no-node", "jmax": 0, "expanded": 0}
    jmax, expanded, goal = 0, 0, None
    fail_moves = collections.Counter()
    while pq:
        d, _q, s = heapq.heappop(pq)
        if best.get(s, 1e18) < d:
            continue
        expanded += 1
        if expanded > limit:
            break
        cell, n, j = s
        jmax = max(jmax, j)
        if j == k:
            goal = s
            break
        g = gat(cell)
        for t, code in g.edges[n]:
            if t is not None:
                ns, nd = (cell, t, j), d + 1
            else:
                st = STEP.get(code >> 2)
                if st is None:
                    continue
                nc = (cell[0] + st[0], cell[1] + st[1])
                m = M.get(nc)
                if not m:
                    fail_moves["off-corridor" if rx0 <= nc[0] <= rx1 and rz0 <= nc[1] <= rz1 else "out-of-rect"] += 1
                    continue
                if m[-1] < j - back:
                    fail_moves["backwards"] += 1
                    continue
                near = [i for i in m if j < i <= j + free]
                if near:
                    nj = max(near)
                elif width == 0:
                    nj = j
                    if nc not in route or m[-1] > j:
                        fail_moves["skip"] += 1
                        continue
                else:
                    nj = next((i for i in m if i > j), j)
                g2 = gat(nc)
                if g2 is None:
                    fail_moves["next-no-graph"] += 1
                    continue
                an = g2.lookup(g.x[n] - 256 * st[0], g.z[n] - 256 * st[1], 0)
                if an is None:
                    fail_moves["no-arrival-node"] += 1
                    continue
                if not g2.has_internal(an):
                    fail_moves["arrival-no-internal"] += 1
                    continue
                ns = (nc, an, nj)
                nd = d + 1 + (0 if nc in route else offc) + skipc * max(0, nj - j - free)
            if nd < best.get(ns, 1e18):
                best[ns] = nd
                prev[ns] = s
                heapq.heappush(pq, (nd, seq, ns))
                seq += 1
    if goal is None:
        return {"ok": False, "reason": "no-lane-path", "jmax": jmax, "expanded": expanded, "moves": dict(fail_moves)}
    path, s = [], goal
    while s is not None:
        path.append(s)
        s = prev.get(s)
    path.reverse()
    cseq, skipped, lastj = [], 0, 0
    for c, n, j in path:
        if not cseq or cseq[-1] != c:
            cseq.append(c)
        skipped += max(0, j - lastj - free)
        lastj = j
    off = sum(1 for c in cseq if c not in route)
    return {"ok": True, "jmax": k, "expanded": expanded, "lanes": len(path), "cells": len(cseq), "offroute_cells": off,
            "cost": best[goal],
            "skipped": skipped, "path": [(c[0], c[1], n) for c, n, j in path]}


def link(G, a, b):
    """lane link a -> b: some class-0 node of a has an exit edge toward b whose arrival node in b exists and has an
    internal edge (the FUN_1001c750 conditions, sim rect aside)"""
    ga, gb = G.at(a)[0], G.at(b)[0]
    st = (b[0] - a[0], b[1] - a[1])
    if ga is None or gb is None or st not in SIDE_OF:
        return False
    for n in range(len(ga.cls)):
        if ga.cls[n] != 0:
            continue
        for t, code in ga.edges[n]:
            if t is None and STEP.get(code >> 2) == st:
                an = gb.lookup(ga.x[n] - 256 * st[0], ga.z[n] - 256 * st[1], 0)
                if an is not None and gb.has_internal(an):
                    return True
    return False


def step_status(G, a, b):
    if a == b:
        return "same-cell"
    if cheb(a, b) != 1 or (a[0] != b[0] and a[1] != b[1]):
        return "not-adjacent"
    if G.at(b)[0] is None:
        return "no-lanes"
    if link(G, a, b):
        return "linked"
    return "against-lanes" if link(G, b, a) else "unconnected"


def classify(G, r, jmax):
    """why a route has no lane path: the first step from route index jmax - 1 on that is not lane-linked, else a
    reversal (U-turn) after it, else 'turn'"""
    cells = r["cells"]
    lo = max(0, jmax - 3)
    for i in range(lo, len(cells) - 1):
        stt = step_status(G, cells[i], cells[i + 1])
        if stt not in ("linked", "same-cell"):
            return stt, i
    d = [(cells[i + 1][0] - cells[i][0], cells[i + 1][1] - cells[i][1]) for i in range(len(cells) - 1)]
    for i in range(lo, len(d)):
        for q in range(i + 1, min(len(d), i + 4)):           # a step, then its opposite after <= 2 sideways steps
            if d[q] == (-d[i][0], -d[i][1]) and all(d[m][0] * d[i][0] + d[m][1] * d[i][1] == 0 for m in range(i + 1, q)):
                return "u-turn", i
    return "turn", jmax


def piece_name(G, cell):
    g, piece, state, has = G.at(cell)
    if piece is None:
        return "none"
    return "%d/%d%s" % (piece, state, "" if has else " (no lane record)")


def analyse(G, trips, out_json=None, sample=None, widths=(1, 0, 2)):
    st = collections.Counter()
    reasons = collections.Counter()
    places = collections.Counter()
    pieces = collections.Counter()
    times = []
    per = []
    for t in trips[:sample] if sample else trips:
        for r in routes_of(t):
            if len(r["cells"]) < 2:
                st["routes_1cell"] += 1
                continue
            st["routes"] += 1
            lit, li, lreason = literal(G, r)
            st["literal_ok"] += lit
            steps = [step_status(G, r["cells"][i], r["cells"][i + 1]) for i in range(len(r["cells"]) - 1)]
            for x in set(steps):
                st["routes_with_step_" + x] += 1
            row = {"seq": t["seq"], "n": len(r["cells"]), "literal": lit, "cells": r["cells"]}
            for w in widths:
                t0 = time.perf_counter()
                res = solve(G, r, t["rect"], width=w)
                dt = time.perf_counter() - t0
                tag = "w%d_" % w
                if w == widths[0]:
                    times.append(dt)
                st[tag + "solved"] += res["ok"]
                if res["ok"]:
                    cov = 1 - res["skipped"] / len(r["cells"])
                    st[tag + "full"] += res["skipped"] == 0
                    st[tag + "cov90"] += cov >= 0.9
                    st[tag + "offroute_cells"] += res["offroute_cells"]
                    row[tag + "skipped"] = res["skipped"]
                    if w == widths[0]:
                        row["lane_path"] = res["path"]
                elif w == widths[0]:
                    why, i = classify(G, r, res["jmax"])
                    a = r["cells"][i]
                    b = r["cells"][i + 1] if i + 1 < len(r["cells"]) else None
                    reasons[why] += 1
                    places[(a, b, why)] += 1
                    pieces[(piece_name(G, a), piece_name(G, b) if b else "-", why)] += 1
                    row["reason"] = why
                    row["at"] = [a, b]
                row[tag + "ok"] = res["ok"]
                row[tag + "jmax"] = res["jmax"]
            per.append(row)
    times.sort()
    out = {"counts": dict(st), "fail_reasons_w%d" % widths[0]: dict(reasons),
           "fail_places": [[list(a), list(b) if b else None, w, n] for (a, b, w), n in places.most_common(20)],
           "fail_pieces": [[a, b, w, n] for (a, b, w), n in pieces.most_common(25)],
           "solve_ms": {"median": 1000 * times[len(times) // 2] if times else None,
                        "p90": 1000 * times[int(len(times) * 0.9)] if times else None,
                        "max": 1000 * times[-1] if times else None}}
    if st["routes"]:
        R = st["routes"]
        out["pct"] = {"literal": 100.0 * st["literal_ok"] / R}
        for w in widths:
            for key in ("solved", "full", "cov90"):
                out["pct"]["w%d_%s" % (w, key)] = 100.0 * st["w%d_%s" % (w, key)] / R
        for key in [k for k in st if k.startswith("routes_with_step_")]:
            out["pct"][key[7:]] = 100.0 * st[key] / R
    if out_json:
        json.dump({**out, "routes": per}, open(out_json, "w"), indent=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("analyse", help="routes of a trip dump, graphs from a save (or --graphs, the DLL's dump)")
    p.add_argument("trips"); p.add_argument("--city"); p.add_argument("--graphs"); p.add_argument("--lang", default="ENGLISH")
    p.add_argument("--json"); p.add_argument("--sample", type=int)
    p = sp.add_parser("match", help="the DLL's solver results against solve() on the DLL's graphs")
    p.add_argument("graphs"); p.add_argument("routes"); p.add_argument("--limit", type=int); p.add_argument("--json")
    p = sp.add_parser("sources", help="save + TrBlkAtt graphs against the DLL's in-memory graphs, per cell")
    p.add_argument("graphs"); p.add_argument("city"); p.add_argument("--lang", default="ENGLISH"); p.add_argument("--json")
    a = ap.parse_args()
    if a.cmd == "analyse":
        G = DumpGraphs(a.graphs) if a.graphs else SaveGraphs(a.city, a.lang)
        out = analyse(G, ctm_read.read_trips(a.trips), a.json, a.sample)
    elif a.cmd == "match":
        out = match(a.graphs, a.routes, a.limit)
    else:
        out = compare_sources(a.graphs, a.city, a.lang)
    if getattr(a, "json", None) and a.cmd != "analyse":
        json.dump(out, open(a.json, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
