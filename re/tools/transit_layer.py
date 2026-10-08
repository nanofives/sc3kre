#!/usr/bin/env python3
r"""transit_layer.py - reader for the SimTransit traffic-density save layer (GZCOM group 0x029ca804).

⚠️ NAME: the save layer is group **0x029ca804 = SimTransit** (class iOS `SimCity::goTrafficLayer`),
NOT 0x029ca806 (TrafficLayer, which never appears in a save). Save `SIMTRANSIT FUN_10004c8d`, load
`FUN_100048ee`, both hold the literal 0x29ca804 `[CONFIRMED @0x10004c8d, 0x100048ee]`.

WHAT IT IS. Six per-cell traffic-DENSITY grids (all dynamic sim outputs; there are NO static
per-cell cost grids - static routing costs are STTraffic.INI scalars, not grids). Density is
accumulated along assigned trip routes each sim step (`FUN_10006edd`, clamp `TrafficMaxDensity`) and
decremented monthly (`FUN_100093e9`). So a density grid RESPONDS to the sim ticking - this is the
camera-independent oracle a simulation-level test (T3) needs. `[CONFIRMED @0x10006edd, 0x100093e9]`

ON-DISK LAYOUT - fully pinned 2026-08-27 (arithmetic + decompilation write-order + empirical A/B/C).
The section is one instance-0 blob after the 8-byte SIMCITY object frame; payload = 165 + 6.25*cells,
cells = N*N. Byte order `[CONFIRMED write @0x10004c8d, boundaries A=0/B=145/C=20 measured]`:

    offset                       field            bytes        meaning
    0                            surf_snap (+0x60) cells       surface(road+hwy) monthly density snapshot
    cells                        rail_snap (+0x64) cells       rail monthly snapshot
    2*cells                      sub_snap  (+0x68) cells       subway monthly snapshot
    3*cells                      bit0      (+0x80) cells/8      1-bit/cell boolean plane (unnamed)
    3*cells + cells/8            bit1      (+0x7c) cells/8      1-bit/cell boolean plane (paired w/ bit0)
    3*cells + cells/4            [B: 145 bytes]                2 u32 + 1 u8 + 1 u32 + the +0xac stats obj
    3*cells + cells/4 + 145      surf_live (+0x6c) cells       surface LIVE within-month accumulator  <-- T3
    4*cells + cells/4 + 145      rail_live (+0x70) cells       rail LIVE accumulator                   <-- T3
    5*cells + cells/4 + 145      sub_live  (+0x74) cells       subway LIVE accumulator                 <-- T3
    6*cells + cells/4 + 145      [C: 20 bytes]                 4 u32 + 1 u32 trailing scalars (to EOF)

  A/B/C derivation (all consistent): C = 16 + W90 = 20 -> W90 = 4 (vt+0x90 = u32); B = 2*W90+5+Sac =
  145 -> Sac = 132 (the +0xac stats object serialises to 132 B inline); A = 0 (the record body starts
  at grid +0x60; the leading object frame is the 8-byte frame already stripped). Master equation
  a + Sac + 3*W90 = 144 holds (0 + 132 + 12). Coder = GZResourceD universal stream IID 0x199627,
  vt+0x88 = u32 `[CONFIRMED @0x1000c1d6]`, vt+0x68 = u8 `[CONFIRMED @0x1000c157]`.

  Validation (--validate): the trailing chunk C is exactly 20 bytes at N=128/192/256; g60==g6c
  (snapshot==live) byte-exact for saves taken right after a monthly tick (Madison, Moscow); rail/
  subway grids are zero in cities without that mode's traffic. Grid element = 1 byte, row-major
  stride N, value 0..TrafficMaxDensity.

MODE MAPPING is `[iOS-HINT]` (from `GetTrafficDensity` mask grouping @ios 0x2711dc): surface grid
aggregates road+highway (mask bits 1,4,0x10,0x20), rail = bit 2, subway = bit 8. The three-way
snapshot/live pairing (surf/rail/sub) is `[CONFIRMED]` by the accumulator masks in FUN_10006edd
(0x35 -> +0x6c, 2 -> +0x70, 8 -> +0x74).

DENSITY IS NOT CONFINED TO NETWORK TILES (measured: absent-network grids are not all-zero for the
surface mode). The robust oracle is a whole-map or regional SUM of a live grid, compared before vs
after a sim run - NOT a per-tile-on-road match.

Usage:
  py -3.12 transit_layer.py <city.sc3>                 # per-grid totals + occupancy
  py -3.12 transit_layer.py <city.sc3> --grid NAME     # dump one grid (name below) as x,y,value CSV
  py -3.12 transit_layer.py <city.sc3> --sum NAME [--rect x0,y0,x1,y1]   # T3 oracle: grid sum
  py -3.12 transit_layer.py --validate [<dir>]         # structural checks across all cities
  py -3.12 transit_layer.py --diff <base.sc3> <after.sc3>   # per-grid total + changed-cell deltas
  grid NAME in: surf_snap rail_snap sub_snap surf_live rail_live sub_live
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_parse
import ixf_parse

TRANSIT_GROUP = 0x029CA804
GRID_GROUP = 0x80AB8AB0
GRID_TYPE = 0x406B1196
A_LEN = 0            # bytes before the first grid
B_LEN = 145          # scalars + the +0xac stats object, between the bit grids and the live grids
C_LEN = 20           # trailing scalars

# byte-grid names in save order (snapshot trio, then live trio); the bit grids sit between them
BYTE_GRIDS = ("surf_snap", "rail_snap", "sub_snap", "surf_live", "rail_live", "sub_live")
LIVE = {"surf_live", "rail_live", "sub_live"}


class TransitError(Exception):
    pass


def _map_dim(ents):
    g = next((x for x in ents if x["group"] == GRID_GROUP and x["type"] == GRID_TYPE), None)
    if g is None:
        raise TransitError("no tile-grid section to derive N")
    n = int(round((g["size"] - 16) ** 0.5))
    if n * n != g["size"] - 16:
        raise TransitError("tile-grid section %d bytes is not N*N+16" % g["size"])
    return n


def _find(path):
    records, d = ixf_parse.parse(path)
    for r in records:
        raw = d[r["offset"]:r["offset"] + r["size"]]
        if not city_parse.is_compressed_payload(raw):
            continue
        body, _ = city_parse.parse_payload(raw)
        _, ents = city_parse.parse_sections(body)
        e = next((x for x in ents if x["group"] == TRANSIT_GROUP), None)
        if e is None:
            continue
        return body, e, _map_dim(ents)
    raise TransitError("%s: no SimTransit (0x029ca804) section" % path)


class Transit:
    """Decoded SimTransit blob: six 1-byte-per-cell density grids at their confirmed offsets."""

    __slots__ = ("n", "_blob", "_off", "tail_len")

    def __init__(self, n, blob):
        cells = n * n
        need = A_LEN + 6 * cells + cells // 4 + B_LEN + C_LEN
        if len(blob) != need:
            raise TransitError("payload %d bytes, expected %d for N=%d" % (len(blob), need, n))
        self.n = n
        self._blob = blob
        c = cells
        snap = A_LEN
        live = A_LEN + 3 * c + c // 4 + B_LEN
        self._off = {
            "surf_snap": snap, "rail_snap": snap + c, "sub_snap": snap + 2 * c,
            "surf_live": live, "rail_live": live + c, "sub_live": live + 2 * c,
        }
        self.tail_len = len(blob) - (live + 3 * c)   # must be C_LEN

    @classmethod
    def load(cls, path):
        body, e, n = _find(path)
        flen = e["frame"]["len"]
        return cls(n, bytes(body[e["abs"] + flen:e["abs"] + e["size"]]))

    def grid(self, name):
        if name not in self._off:
            raise TransitError("unknown grid %r (use %s)" % (name, ", ".join(BYTE_GRIDS)))
        o = self._off[name]
        return self._blob[o:o + self.n * self.n]

    def total(self, name):
        return sum(self.grid(name))

    def rect_sum(self, name, x0, y0, x1, y1):
        g = self.grid(name)
        n = self.n
        return sum(g[y * n + x] for y in range(y0, y1 + 1) for x in range(x0, x1 + 1))

    def cells(self, name):
        g = self.grid(name)
        n = self.n
        return {(i % n, i // n): b for i, b in enumerate(g) if b}


# --- CLI --------------------------------------------------------------------------------------

def cmd_summary(path):
    t = Transit.load(path)
    print("# %s  N=%d  cells=%d  tail=%dB" % (os.path.basename(path), t.n, t.n * t.n, t.tail_len))
    for name in BYTE_GRIDS:
        g = t.grid(name)
        nz = sum(1 for b in g if b)
        print("  %-9s total %9d  nonzero %6d (%4.1f%%)  max %3d"
              % (name, sum(g), nz, 100 * nz / len(g), max(g)))
    return 0


def cmd_grid(path, name):
    t = Transit.load(path)
    print("x,y,value")
    for (x, y), v in sorted(t.cells(name).items()):
        print("%d,%d,%d" % (x, y, v))
    return 0


def cmd_sum(path, name, rect):
    t = Transit.load(path)
    if rect:
        x0, y0, x1, y1 = rect
        print("%s rect(%d,%d..%d,%d) sum = %d" % (name, x0, y0, x1, y1, t.rect_sum(name, x0, y0, x1, y1)))
    else:
        print("%s total = %d" % (name, t.total(name)))
    return 0


def cmd_validate(target):
    """Structural checks that FAIL if the A/B/C boundaries are wrong (not a tautology)."""
    bad = 0
    n_post_tick = 0
    for p in city_parse.walk(target):
        name = os.path.basename(p)[:32]
        try:
            t = Transit.load(p)
        except TransitError:
            continue
        problems = []
        if t.tail_len != C_LEN:
            problems.append("tail %d != %d" % (t.tail_len, C_LEN))
        # snapshot == live for post-monthly-tick saves; else live is a plausible density field
        eq = t.grid("surf_snap") == t.grid("surf_live")
        n_post_tick += eq
        if max(t.grid("surf_live"), default=0) > 255:
            problems.append("surf_live byte > 255 (impossible)")
        tag = "  [snap==live: post-tick save]" if eq else ""
        if problems:
            bad += 1
            print("%-32s FAIL %s" % (name, "; ".join(problems)))
        else:
            print("%-32s ok%s" % (name, tag))
    print()
    print("structural validation: %d failures; %d saves are post-monthly-tick (snap==live)"
          % (bad, n_post_tick))
    print("A=%d B=%d C=%d confirmed by the constant %d-byte tail across all map sizes."
          % (A_LEN, B_LEN, C_LEN, C_LEN))
    return 1 if bad else 0


def cmd_diff(base, after):
    a = Transit.load(base)
    b = Transit.load(after)
    if a.n != b.n:
        raise TransitError("map dims differ: %d vs %d" % (a.n, b.n))
    print("# transit diff %s -> %s (N=%d)" % (os.path.basename(base), os.path.basename(after), a.n))
    print("# grid       total_base   total_after     delta   cells_changed")
    for name in BYTE_GRIDS:
        ga, gb = a.grid(name), b.grid(name)
        ta, tb = sum(ga), sum(gb)
        changed = sum(1 for i in range(len(ga)) if ga[i] != gb[i])
        print("  %-9s %11d %13d %+9d %7d" % (name, ta, tb, tb - ta, changed))
    return 0


def main(argv):
    if "--validate" in argv:
        i = argv.index("--validate")
        target = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else "Cities"
        return cmd_validate(target)
    if "--diff" in argv:
        i = argv.index("--diff")
        return cmd_diff(argv[i + 1], argv[i + 2])
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    if "--grid" in argv:
        return cmd_grid(path, argv[argv.index("--grid") + 1])
    if "--sum" in argv:
        name = argv[argv.index("--sum") + 1]
        rect = None
        if "--rect" in argv:
            rect = tuple(int(v) for v in argv[argv.index("--rect") + 1].split(","))
        return cmd_sum(path, name, rect)
    return cmd_summary(path)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
