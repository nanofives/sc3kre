#!/usr/bin/env python3
r"""city_grid.py - lay a road lattice and zone the blocks of a saved city (test-city tooling, 2026-10-08).

Writes ROAD tiles with network_layer.NetworkEditor and zone slots with city_write.City. Each road tile's
(piece, rotation) comes from its 4-neighbour mask, using the pieces the shipped cities use on level ground
(measured over all 59 stock cities: state is always 0x3000 and the save's `flg` bits are the rotation):

  straight 29 (W-E flg0, N-S flg1) | crossroads 43 | T 11204 | corner 35 | dead end 11225

The ground must be level at height `z` (see city_flatten.py): z is not read per tile.
Zones use the city's declared slots: 1,2,3 residential, 5,6,7 commercial, 9,10,11 industrial (light..dense).

Usage: python city_grid.py <in.sc3> <out.sc3> --x0 X --y0 Y --size S [--spacing 7] [--z 27] [--mix r1:..]
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import network_layer as nl

STATE = 0x3000
# mask bits follow network_layer._DIRS = W, N, E, S
PIECE = {
    15: (43, 0),
    5: (29, 0), 10: (29, 1),
    7: (11204, 0), 11: (11204, 3), 13: (11204, 2), 14: (11204, 1),
    3: (35, 1), 6: (35, 2), 9: (35, 0), 12: (35, 3),
    1: (11225, 1), 2: (11225, 2), 4: (11225, 3), 8: (11225, 0),
}


def build(src, dst, x0, y0, size, spacing, z, mix, seed=1, gaps=True, plant_holes=()):
    e = nl.NetworkEditor.load(src)
    c = e.city
    n = c.n
    if x0 < 0 or y0 < 0 or x0 + size > n or y0 + size > n:
        raise SystemExit("patch outside the %dx%d map" % (n, n))
    had_roads = bool(e.tiles("road"))
    road = set()
    for k in range(0, size, spacing):
        for t in range(size):
            road.add((x0 + k, y0 + t))      # N-S line
            road.add((x0 + t, y0 + k))      # W-E line
    last = x0 + ((size - 1) // spacing) * spacing   # trim the dangling tails past the last line
    road = {(x, y) for (x, y) in road if x <= last and y <= y0 + (last - x0)}
    # GAPS: drop the middle tile of every road segment between two crossings and zone it instead, so every
    # block touches its neighbours. Zones carry power and roads do not (owner's game knowledge, consistent with
    # the first patch: a plant beside a road powered nothing), so power can flood the whole grid with no lines.
    gap = set()
    if gaps:
        half = spacing // 2
        for k in range(0, last - x0 + 1, spacing):
            for j in range(0, last - x0, spacing):
                gap.add((x0 + k, y0 + j + half))      # N-S line, middle of the segment
                gap.add((x0 + j + half, y0 + k))      # W-E line
        road -= gap
    # BULK PATH: NetworkEditor.add_tile rebuilds its whole (x,y) index on every call (O(n^2) over ~300k tiles at
    # 1024). Validate once here, then append Tile objects directly; flush() still re-packs and re-counts.
    if not 0 <= z <= nl.Z_MAX:
        raise SystemExit("z %d outside 0..%d" % (z, nl.Z_MAX))
    existing = {t.key() for t in e.tiles("road")}
    bulk = e.tiles("road")
    for (x, y) in sorted(road):
        m = 0
        for i, (dx, dy) in enumerate(nl._DIRS):
            if (x + dx, y + dy) in road:
                m |= 1 << i
        if m == 0:
            continue
        piece, flg = PIECE[m]
        if (x, y) in existing:
            e.remove_tile("road", x, y); existing.discard((x, y))
        bulk.append(nl.Tile(x, y, z, flg, piece, STATE))
    rnd = random.Random(seed)
    slots, weights = zip(*mix)
    zoned = 0
    declared = c.declared_slots()
    for sl in slots:   # the same checks zone_set makes, once
        if sl == 22 or not 0 < sl < 0x17 or sl not in declared:
            raise SystemExit("zone slot %d not allowed (declared %s)" % (sl, sorted(declared)))
    zdata, _ = c._zone()
    zdata = zdata.data

    class _Z:
        @staticmethod
        def zone_set(x, y, slot):
            zdata[y * n + x] = slot
    c = _Z
    for (x, y) in gap:
        if x0 < x < last and y0 < y < y0 + (last - x0):     # interior gaps only; the outer ring stays road
            c.zone_set(x, y, slots[0]); zoned += 1
    for by in range(y0, y0 + (last - x0), spacing):
        for bx in range(x0, last, spacing):
            slot = rnd.choices(slots, weights)[0]
            for y in range(by + 1, by + spacing):
                for x in range(bx + 1, bx + spacing):
                    if any(hx <= x < hx + 4 and hy <= y < hy + 4 for (hx, hy) in plant_holes):
                        continue                              # left empty for a 4x4 power plant
                    c.zone_set(x, y, slot)
                    zoned += 1
    e.save(dst)
    return len(road), zoned


def parse_mix(s):
    out = []
    for part in s.split(","):
        k, v = part.split(":")
        out.append((int(k), float(v)))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--x0", type=int, required=True); ap.add_argument("--y0", type=int, required=True)
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--spacing", type=int, default=7)
    ap.add_argument("--z", type=int, default=27)
    ap.add_argument("--mix", default="1:30,2:20,3:10,5:12,6:8,9:12,10:8")
    ap.add_argument("--no-gaps", action="store_true")
    ap.add_argument("--plant", action="append", default=[], help="X,Y top-left of a 4x4 hole for a power plant")
    a = ap.parse_args()
    holes = [tuple(int(v) for v in p.split(",")) for p in a.plant]
    r, zn = build(a.src, a.dst, a.x0, a.y0, a.size, a.spacing, a.z, parse_mix(a.mix), gaps=not a.no_gaps,
                  plant_holes=holes)
    print("roads %d tiles, zoned %d tiles -> %s" % (r, zn, a.dst))
