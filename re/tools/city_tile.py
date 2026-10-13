#!/usr/bin/env python3
r"""city_tile.py - tile a real 256 city's roads and zones KxK across a bigger flat map (test-city tooling, 2026-10-09).

Owner's idea: a developed 1024 test city that looks like a real one, by repeating a shipped city's layout.
Copies, per copy at offset (ox, oy) = (i*256, j*256):
  - every ROAD tile of the source at x, y in 1..255, verbatim (piece, flg, state), z forced to the target level.
    Europolis is flat (all 9,464 road tiles at z 75), so its pieces, diagonals included, are valid on level ground.
  - every zone slot of the source at x, y in 1..255 except 22 (plopped building - the building itself is not
    copied: the occupant section is not decoded for writing).
  - a SEAM road along x = ox and y = oy (replacing the source's row/column 0), so the copies connect: source
    roads that reached the west/north edge now meet the seam at ox/oy, and those that reached the east/south
    edge (x or y = 255) land on ox+255, next to the following copy's seam at ox+256.
  Seam tiles and the tiles touching them get their piece recomputed from the 4-neighbour mask (city_grid table).
Then lists 4x4 empty squares (no road, no zone) spread over the map, for power plants (place_direct.py).

Not copied: terrain heights and water (target stays flat and dry), rail, highways, power lines, pipes, buildings.

Usage: python city_tile.py <source 256.sc3> <flat target.sc3> <out.sc3> [--z 27] [--plants-per-copy 3]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import network_layer as nl
from city_grid import PIECE, STATE

SRC_N = 256


def plant_spots(road, zone, n, per_copy, copies):
    """4x4 squares with no road and no zone, touching a zone (zones carry power), spread inside each copy."""
    spots = []
    for j in range(copies):
        for i in range(copies):
            ox, oy = i * SRC_N, j * SRC_N
            got = []
            for y in range(oy + 8, oy + SRC_N - 8, 2):
                for x in range(ox + 8, ox + SRC_N - 8, 2):
                    if any(abs(x - gx) < 64 and abs(y - gy) < 64 for gx, gy in got):
                        continue
                    sq = [(x + a, y + b) for a in range(4) for b in range(4)]
                    if any(p in road or zone[p[1] * n + p[0]] for p in sq):
                        continue
                    ring = [(x - 1, y + b) for b in range(4)] + [(x + 4, y + b) for b in range(4)] + \
                           [(x + a, y - 1) for a in range(4)] + [(x + a, y + 4) for a in range(4)]
                    if any(zone[q[1] * n + q[0]] for q in ring):
                        got.append((x, y))
                        if len(got) >= per_copy:
                            break
                if len(got) >= per_copy:
                    break
            spots += got
    return spots


def build(src, dst_in, out, z, per_copy):
    s = nl.NetworkEditor.load(src)
    if s.city.n != SRC_N:
        raise SystemExit("source must be a 256 city (got %d)" % s.city.n)
    e = nl.NetworkEditor.load(dst_in)
    c = e.city
    n = c.n
    if n % SRC_N:
        raise SystemExit("target size %d is not a multiple of 256" % n)
    k = n // SRC_N
    if e.tiles("road"):
        raise SystemExit("target already has roads - use an empty flat map (city_flatten.py)")
    src_tiles = {(t.x, t.y): t for t in s.tiles("road") if 1 <= t.x < SRC_N and 1 <= t.y < SRC_N}
    szone, _ = s.city._zone()
    szone = szone.data
    declared = c.declared_slots()

    road = {}                                     # (x, y) -> (piece, flg, state)
    seam = set()
    for j in range(k):
        for i in range(k):
            ox, oy = i * SRC_N, j * SRC_N
            for (x, y), t in src_tiles.items():
                road[(ox + x, oy + y)] = (t.piece, t.state, t.props)
            for t in range(SRC_N):
                seam.add((ox, oy + t)); seam.add((ox + t, oy))
    for p in seam:
        road[p] = None                            # piece decided below
    fix = set(seam)
    for (x, y) in seam:
        for dx, dy in nl._DIRS:
            if (x + dx, y + dy) in road:
                fix.add((x + dx, y + dy))
    recomputed = 0
    for (x, y) in fix:
        m = 0
        for b, (dx, dy) in enumerate(nl._DIRS):
            if (x + dx, y + dy) in road:
                m |= 1 << b
        if m == 0:
            del road[(x, y)]
            continue
        piece, flg = PIECE[m]
        road[(x, y)] = (piece, flg, STATE)
        recomputed += 1

    if not 0 <= z <= nl.Z_MAX:
        raise SystemExit("z %d outside 0..%d" % (z, nl.Z_MAX))
    bulk = e.tiles("road")                        # bulk append, as city_grid does (add_tile is O(n) per call)
    for (x, y), (piece, flg, state) in sorted(road.items()):
        bulk.append(nl.Tile(x, y, z, flg, piece, state))

    zdata, _ = c._zone()
    zdata = zdata.data
    zoned = skipped = 0
    for j in range(k):
        for i in range(k):
            ox, oy = i * SRC_N, j * SRC_N
            for y in range(1, SRC_N):
                for x in range(1, SRC_N):
                    sl = szone[y * SRC_N + x]
                    if not sl:
                        continue
                    if sl == 22 or sl not in declared or (ox + x, oy + y) in road:
                        skipped += 1
                        continue
                    zdata[(oy + y) * n + ox + x] = sl
                    zoned += 1
    spots = plant_spots(set(road), zdata, n, per_copy, k)
    e.save(out)
    return len(road), recomputed, zoned, skipped, spots


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("target"); ap.add_argument("out")
    ap.add_argument("--z", type=int, default=27)
    ap.add_argument("--plants-per-copy", type=int, default=3)
    a = ap.parse_args()
    r, rc, zn, sk, spots = build(a.src, a.target, a.out, a.z, a.plants_per_copy)
    print("roads %d tiles (%d recomputed at seams), zoned %d tiles (%d skipped: plopped/undeclared/under road)"
          % (r, rc, zn, sk))
    print("plant spots (%d):" % len(spots), " ".join("%d,%d" % p for p in spots))
