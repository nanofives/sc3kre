#!/usr/bin/env python3
r"""city_flatten.py - level a saved city's terrain to one height (test-city tooling, 2026-10-08).

Terrain section (DirtBag, group 0x21737de5, instance 0), measured on Moscow (N=256) and a game-written 1024 map:
  8-byte SIMCITY frame | 4 bytes (25 06 51 40 in both) | grid A: (N+1)^2 bytes | grid B: (N+1)^2 bytes | N^2/8+1 bytes
  - grid A varies (21..35 on the 1024 map, mostly 32 in Moscow): ground height per tile corner. Road z equals the
    corner height on uniform ground in the shipped cities. `[UNCERTAIN]` exact corner alignment on slopes
    (no row/column shift or transpose matched better than 77%).
  - grid B is a single value in both files (19 / 30): the water level; corners with A < B are water.
  - the tail is all zero bar a handful of bytes, left untouched.
Layout read from data only, not from the SIMDIRT save function (0x10004d90) - treat as a working hypothesis.

Usage: python city_flatten.py <in.sc3> <out.sc3> [height]   (default: the most common grid-A value)
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_write

TERRAIN_GROUP = 0x21737DE5


def flatten(src, dst, height=None):
    c = city_write.City.load(src)
    n = c.n
    sec = [s for s in c.sections if s.group == TERRAIN_GROUP and s.instance == 0][0]
    m = (n + 1) ** 2
    if len(sec.data) != 2 * m + n * n // 8 + 13:
        raise SystemExit("terrain section is %d bytes, layout expects %d" % (len(sec.data), 2 * m + n * n // 8 + 13))
    a = sec.data[12:12 + m]
    water = sec.data[12 + m]
    if height is None:
        height = collections.Counter(a).most_common(1)[0][0]
    if height <= water:
        raise SystemExit("height %d is at or below the water level %d" % (height, water))
    sec.data[12:12 + m] = bytes([height]) * m
    c.save(dst)
    return n, height, water


if __name__ == "__main__":
    h = int(sys.argv[3]) if len(sys.argv) > 3 else None
    n, h, w = flatten(sys.argv[1], sys.argv[2], h)
    print("N %d: every corner set to %d (water level %d) -> %s" % (n, h, w, sys.argv[2]))
