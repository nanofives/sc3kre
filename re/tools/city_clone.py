#!/usr/bin/env python3
r"""city_clone.py - repeat a whole 256 city KxK on a bigger map (test-city tooling, 2026-10-09).

Successor of city_tile.py (roads + zones only, flat and dry, z forced, buildings placed live as plopped).
Copies, per copy at offset (ox, oy) = (i*256, j*256), from the source save:
  - TERRAIN: the corner height grid A and water-level grid B of the DirtBag section (group 0x21737de5, layout
    in city_flatten.py) and the tail's leading water-level byte. A corner is water when A <= B (SIMDIRT
    0x100065f0); Europolis's water-pump rings surround corners with A == B == 75, so its pump water comes along.
  - ALL THREE NETWORK SECTIONS of group 0x2147c2dd, z/flg/piece/state verbatim. Measured 2026-10-09 against
    Apps\Res\TilingRules\*_Set.txt on five shipped cities: instance 1 = every surface network (road, rail,
    highway, power line), instance 2 = water PIPES, instance 3 = SUBWAY (network_layer.py's 'rail'/'net2'
    labels are older names).
  - a SEAM road on instance 1 along x = ox and y = oy so the copies connect, except where the source has a
    building or a non-road piece (an edge power line) on row/column 0: those stay. Pieces at and next to the
    seam come from the 4-neighbour mask (city_grid table).
  - BUILDINGS: every record of the occupant section (occupant_layer.py), position shifted, rest verbatim, so
    grown buildings stay grown and plopped ones plopped. Build dates (optional field, flag bit 22) are reset to
    the new start date. --extra-plants N adds up to N more copies of the source's power plant per plant row,
    continuing the row on free land (no road, zone or building) in both directions.
  - ZONES: the whole zone raster, slot 22 (plopped) included where its building came along.
  - CITY-WIDE SECTIONS, verbatim from the source: ordinances (group 0xe1193c2a: u32 count, then {u32 id,
    u8 enacted, u8 available}), budget/taxes (SIMMISC budget layer 0xa11bcc54), and the neighbor deals
    (0x82937b60, neighbor_layer.py) with their edge connection cells moved to the big map's edges and the
    per-side connection counts recounted, keeping only cells where the network really reaches the edge.
  - DATE: the city header record {0xfa1, 0x617e198d} (outside the compressed body: day of year, year,
    founding year) and the load-dialog preview {0xe2f42628, 0x62f42635} (+0x1c day, +0x20 year) are set to
    --year (default 2100) day 1. Year-gated buildings unlock from that on load (SIMADV 0x1001a3ec etc.).
  - PONDS (optional, --ponds JSON [[x, y, w, h], ...] in source coordinates): corners strictly inside each
    rectangle lowered below the water level; buildings and zones inside it are dropped.

Usage: python city_clone.py <source 256.sc3> <empty target.sc3> <out.sc3> [--year 2100] [--extra-plants 4]
"""
import argparse
import collections
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_write
import ixf_parse
import neighbor_layer
import network_layer as nl
import occupant_layer
from city_grid import PIECE, STATE

SRC_N = 256
TERRAIN_GROUP = 0x21737DE5
ORDINANCE_GROUP = 0xE1193C2A
BUDGET_GROUP = 0xA11BCC54
POWER_PLANT_TYPES = range(12101, 12119)          # [AgentTypes] 12101 PowerPlant .. 12118 (SYSPAK.md)
HEADER_KEY = (0xFA1, 0x617E198D)
PREVIEW_KEY = (0xE2F42628, 0x62F42635)
TILING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Apps", "Res", "TilingRules")


def road_pieces():
    """Piece ids the road tiler can produce (ROAD and DIAG sets)."""
    out = set()
    for f in ("ROAD_GRND_Set.txt", "DIAG_Set.txt"):
        out |= {int(v) for v in re.findall(r"\b\d+\b", open(os.path.join(TILING, f), errors="ignore").read())}
    return out


def terrain(city):
    n = city.n
    sec = [s for s in city.sections if s.group == TERRAIN_GROUP and s.instance == 0][0]
    m = (n + 1) ** 2
    if len(sec.data) != 2 * m + n * n // 8 + 13:
        raise SystemExit("terrain section is %d bytes, layout expects %d" % (len(sec.data), 2 * m + n * n // 8 + 13))
    return sec, m


def copy_section(src_city, dst_city, group):
    """Replace every section of `group` in dst with the source's, verbatim."""
    got = [s for s in src_city.sections if s.group == group]
    if not got:
        return 0
    order = {(s.type, s.instance): s.order for s in dst_city.sections if s.group == group}
    dst_city.sections = [s for s in dst_city.sections if s.group != group]
    nxt = max((s.order for s in dst_city.sections), default=-1) + 1
    for s in got:
        o = order.get((s.type, s.instance))
        if o is None:
            o, nxt = nxt, nxt + 1
        dst_city.sections.append(city_write.Section(s.type, s.group, s.instance, bytearray(s.data), o))
    return len(got)


def date_field_at(rec):
    """Offset of the optional (year, day) pair inside a record, or None."""
    if not rec["flags"] & (1 << 22):
        return None
    off = 24
    if rec["flags"] & (1 << 21):
        off += 4 + len(rec["str24"])
    return off


def parse_header(b):
    """City header record (SIMCITY saver 0x1000429d / loader 0x1000351e): offsets of the date fields."""
    p = 3
    flags = b[2]
    extra = None
    if flags & 2:
        extra = b[p]; p += 1
    if struct.unpack_from("<I", b, p)[0] != 0xDEADBEEF:
        raise ValueError("city header: no frame marker")
    p += 4

    def st():
        nonlocal p
        n = struct.unpack_from("<I", b, p)[0]
        p += 4 + n
    if extra:
        st()
    p += 4 * 4 + 4
    st()                                         # user name
    p += 3 * 4                                   # map dimensions
    st(); st()                                   # city, mayor
    return {"day": p, "year": p + 4, "speed": p + 8, "founding": p + 12}


def patch_date(path, year, day=1):
    data = bytearray(open(path, "rb").read())
    recs, _ = ixf_parse.parse(path)
    done = []
    for r in recs:
        key = (r["type"], r["group"])
        if key == HEADER_KEY:
            at = parse_header(data[r["offset"]:r["offset"] + r["size"]])
            for f, v in (("day", day), ("year", year), ("founding", year)):
                struct.pack_into("<I", data, r["offset"] + at[f], v)
            done.append("header")
        elif key == PREVIEW_KEY:
            struct.pack_into("<II", data, r["offset"] + 0x1C, day, year)
            done.append("preview")
    open(path, "wb").write(data)
    return done


def build(src, dst_in, out, ponds=(), year=2100, extra_plants=4):
    s = nl.NetworkEditor.load(src)
    if s.city.n != SRC_N:
        raise SystemExit("source must be a 256 city (got %d)" % s.city.n)
    e = nl.NetworkEditor.load(dst_in)
    c = e.city
    n = c.n
    if n % SRC_N:
        raise SystemExit("target size %d is not a multiple of 256" % n)
    k = n // SRC_N
    if any(e.tiles(i) for i in (1, 2, 3)):
        raise SystemExit("target already has network tiles - use an empty map")
    copies = [(i * SRC_N, j * SRC_N) for j in range(k) for i in range(k)]
    blocked = set()
    for (px, py, w, h) in ponds:
        blocked |= {(x, y) for x in range(px, px + w) for y in range(py, py + h)}

    # terrain
    ssec, sm = terrain(s.city)
    tsec, tm = terrain(c)
    sa, sb = bytearray(ssec.data[12:12 + sm]), ssec.data[12 + sm:12 + 2 * sm]
    water_level = ssec.data[12 + 2 * sm]
    ta, tb = bytearray(tsec.data[12:12 + tm]), bytearray(tsec.data[12 + tm:12 + 2 * tm])
    for (px, py, w, h) in ponds:
        low = max(0, min(sb[py * (SRC_N + 1) + px], water_level) - 4)
        for y in range(py + 1, py + h):
            for x in range(px + 1, px + w):
                sa[y * (SRC_N + 1) + x] = low
    for ox, oy in copies:
        for y in range(SRC_N + 1):
            srow, trow = y * (SRC_N + 1), (oy + y) * (n + 1) + ox
            ta[trow:trow + SRC_N + 1] = sa[srow:srow + SRC_N + 1]
            tb[trow:trow + SRC_N + 1] = sb[srow:srow + SRC_N + 1]
    tsec.data[12:12 + tm] = ta
    tsec.data[12 + tm:12 + 2 * tm] = tb
    tsec.data[12 + 2 * tm] = water_level

    # source buildings
    _, s0, s1, cnt, ver, recs = occupant_layer.parse(src)

    def cells_of(r, ax=None, by=None):
        a = r["a"] if ax is None else ax
        b = r["b"] if by is None else by
        return {(a + dx, b + dy) for dx in range(max(1, r["sa"])) for dy in range(max(1, r["sb"]))}
    keep = [r for r in recs if not cells_of(r) & blocked]
    dropped = len(recs) - len(keep)
    src_bcells = set()
    for r in recs:
        src_bcells |= cells_of(r)

    # extra power plants: continue each straight row of the source's plants on free land
    szone = s.city._zone()[0].data
    used = src_bcells | {(t.x, t.y) for t in s.tiles(1)} | blocked
    def free(cells):
        return all(0 <= x < SRC_N and 0 <= y < SRC_N and (x, y) not in used and not szone[y * SRC_N + x]
                   for x, y in cells)
    plants = [r for r in keep if r["t18"] in POWER_PLANT_TYPES]
    extra = []                                   # (template record, a, b)
    rows = collections.defaultdict(list)
    for p in plants:
        rows[("x", p["a"], p["key"])].append(p)
        rows[("y", p["b"], p["key"])].append(p)
    for (axis, fixed, key), ps in rows.items():
        if len(ps) < 2:
            continue
        t = ps[0]
        step = t["sb"] if axis == "x" else t["sa"]
        along = sorted(p["b"] if axis == "x" else p["a"] for p in ps)
        if any(b - a != step for a, b in zip(along, along[1:])):
            continue                             # not one straight, touching row
        for direction in (-1, 1):
            pos = along[0] if direction < 0 else along[-1]
            for _ in range(extra_plants):
                pos += direction * step
                a, b = (fixed, pos) if axis == "x" else (pos, fixed)
                cells = cells_of(t, a, b)
                if not free(cells):
                    break
                used |= cells
                extra.append((t, a, b))
    for t, a, b in extra:
        for x, y in cells_of(t, a, b):
            src_bcells.add((x, y))

    # networks: pipes and subway verbatim
    counts = {}
    for inst in (2, 3):
        dst = e.tiles(inst)
        for ox, oy in copies:
            for t in s.tiles(inst):
                dst.append(nl.Tile(ox + t.x, oy + t.y, t.z, t.flg, t.piece, t.state))
        counts[inst] = len(dst)

    # surface network + seam
    road_z = collections.Counter(t.z for t in s.tiles(1)).most_common(1)[0][0]
    roadp = road_pieces()
    keep0 = src_bcells | {(t.x, t.y) for t in s.tiles(1) if (t.x == 0 or t.y == 0) and t.piece not in roadp}
    src1 = [t for t in s.tiles(1) if (t.x >= 1 and t.y >= 1) or (t.x, t.y) in keep0]
    road, seam = {}, set()
    for ox, oy in copies:
        for t in src1:
            road[(ox + t.x, oy + t.y)] = (t.z, t.flg, t.piece, t.state)
        for q in range(SRC_N):
            if (0, q) not in keep0:
                seam.add((ox, oy + q))
            if (q, 0) not in keep0:
                seam.add((ox + q, oy))
    for p in seam:
        road[p] = None
    fix = set(seam)
    for (x, y) in seam:
        for dx, dy in nl._DIRS:
            q = (x + dx, y + dy)
            if q in road and (road[q] is None or road[q][2] in roadp):
                fix.add(q)
    recomputed = 0
    for (x, y) in fix:
        m = 0
        for b, (dx, dy) in enumerate(nl._DIRS):
            q = (x + dx, y + dy)
            if q in road and (road[q] is None or road[q][2] in roadp):
                m |= 1 << b
        if m == 0:
            del road[(x, y)]
            continue
        piece, flg = PIECE[m]
        old = road[(x, y)]
        road[(x, y)] = (old[0] if old else road_z, flg, piece, STATE)
        recomputed += 1
    bulk = e.tiles(1)
    for (x, y), (z, flg, piece, state) in sorted(road.items()):
        bulk.append(nl.Tile(x, y, z, flg, piece, state))
    counts[1] = len(bulk)

    # buildings, build dates reset to the start date
    def emit(r, a, b):
        raw = bytearray(s1[r["off"]:r["off"] + r["len"]])
        struct.pack_into("<I", raw, 0, (r["pos"] & ~0x3fffff) | (a & 0x7ff) | ((b & 0x7ff) << 11))
        at = date_field_at(r)
        if at is not None:
            struct.pack_into("<II", raw, at, year, 1)
        return raw
    t0 = c.section(occupant_layer.GROUP, 0, 0x20631788)
    t1 = c.section(occupant_layer.GROUP, 1, 0xe0faadc7)
    body = bytearray(t1.data[:8])
    nrec = 0
    for ox, oy in copies:
        for r in keep:
            body += emit(r, r["a"] + ox, r["b"] + oy)
        for t, a, b in extra:
            body += emit(t, a + ox, b + oy)
        nrec += len(keep) + len(extra)
    t1.data = body
    t0.data = bytearray(t0.data[:8]) + struct.pack("<II", nrec, ver)
    bcells = set()
    for r in keep:
        bcells |= cells_of(r)

    # zones: the whole raster, 22 where its plopped building came along; extra plants get 22 too
    declared = c.declared_slots() | {22}
    zdata = c._zone()[0].data
    zoned = skipped = 0
    for ox, oy in copies:
        for y in range(SRC_N):
            for x in range(SRC_N):
                sl = szone[y * SRC_N + x]
                if not sl:
                    continue
                if sl not in declared or (ox + x, oy + y) in seam or (x, y) in blocked or \
                        (sl == 22 and (x, y) not in bcells):
                    skipped += 1
                    continue
                zdata[(oy + y) * n + ox + x] = sl
                zoned += 1
        for t, a, b in extra:
            for x, y in cells_of(t, a, b):
                zdata[(oy + y) * n + ox + x] = 22

    # city-wide sections
    copied = {name: copy_section(s.city, c, g) for name, g in (("ordinances", ORDINANCE_GROUP), ("budget", BUDGET_GROUP))}
    nsec = s.city.section(neighbor_layer.GROUP, 0, neighbor_layer.TYPE)
    deals = None
    if nsec is not None:
        nb = neighbor_layer.parse(nsec.data)
        net_at = {"road": {(t.x, t.y) for t in bulk}, "rail": {(t.x, t.y) for t in bulk},
                  "highway": {(t.x, t.y) for t in bulk}, "power": {(t.x, t.y) for t in bulk},
                  "water": {(t.x, t.y) for t in e.tiles(2)}, "subway": {(t.x, t.y) for t in e.tiles(3)}}
        edges = {}
        for kind, cells in nb["edges"].items():
            out_cells = []
            for (x, y) in cells:
                side = neighbor_layer.side_of(x, y, SRC_N, SRC_N)
                if side == 0:
                    cand = [(0, j * SRC_N + y) for j in range(k)]
                elif side == 1:
                    cand = [(i * SRC_N + x, 0) for i in range(k)]
                elif side == 2:
                    cand = [(n - 1, j * SRC_N + y) for j in range(k)]
                elif side == 3:
                    cand = [(i * SRC_N + x, n - 1) for i in range(k)]
                else:
                    cand = []
                out_cells += [p for p in cand if p in net_at[kind] and p not in out_cells]
            edges[kind] = out_cells
        data = neighbor_layer.build(nb, edges, n, n)
        tsec = c.section(neighbor_layer.GROUP, 0, neighbor_layer.TYPE)
        if tsec is not None:
            tsec.data = bytearray(data)
        else:
            c.sections.append(city_write.Section(neighbor_layer.TYPE, neighbor_layer.GROUP, 0, bytearray(data),
                                                 max(x.order for x in c.sections) + 1))
        deals = {"deals": [(d["city"].decode("latin-1"), d["type"], d["neighbor"]) for d in nb["deals"]],
                 "edge_cells": {kk: len(v) for kk, v in edges.items()}}
    e.save(out)
    dated = patch_date(out, year)
    return {"copies": len(copies), "surface": counts[1], "pipes": counts[2], "subway": counts[3],
            "seam_recomputed": recomputed, "zoned": zoned, "zone_skipped": skipped, "water_level": water_level,
            "buildings": nrec, "buildings_dropped_per_copy": dropped, "extra_plants_per_copy": len(extra),
            "copied": copied, "neighbors": deals, "date": (year, 1, dated)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("target"); ap.add_argument("out")
    ap.add_argument("--ponds", help="JSON list of [x, y, w, h] rectangles in source coordinates")
    ap.add_argument("--year", type=int, default=2100)
    ap.add_argument("--extra-plants", type=int, default=4, help="max extra power plants per row end")
    a = ap.parse_args()
    ponds = json.load(open(a.ponds)) if a.ponds else []
    print(build(a.src, a.target, a.out, ponds, a.year, a.extra_plants))
