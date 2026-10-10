#!/usr/bin/env python3
r"""neighbor_layer.py - read/write the neighbor-deals section of a saved city (2026-10-09).

Section {type 0xc2910e7d, group 0x82937b60, inst 0}, no DEADBEEF frame. Owner: SIMMISC neighbor-deals manager
(citySim+0xf4); save SIMMISC 0x10015378, load 0x10014ae3 (worker read 2026-10-09, parser consumed all 849 bytes
of Europolis). Strings are u32 length + bytes.

  4 x neighbor (index = map side: 0 x=0, 1 y=0, 2 x=w-1, 3 y=h-1, SIMMISC FUN_10016f13):
      str name; str mayor; u32 population; u32 (4000000); u8 land_neighbor;
      u32 road, rail, power, water, highway, subway   (connection counts per side, loaded as stored)
      6 x u8
  u32 nActive; deal x nActive;  u32 nPending; deal x nPending
  deal = str city; str description; i32 amount, cost; u8 neighbor; u8 type (0/1 power, 2/3 water, 4/5 garbage);
         i32 length, termination_cost, minimum_cost, rate; u32 start_year
  6 x { u32 n; n x u32 cell }  in the order rail, road, water, power, highway, subway; cell = x << 16 | y

Deals are checked against the connection counts and edge cells (validator SIMMISC 0x10018cd5): a deal whose side
has no connection of its kind is cancelled with a penalty.
"""
import struct

GROUP, TYPE = 0x82937b60, 0xc2910e7d
EDGE_ORDER = ("rail", "road", "water", "power", "highway", "subway")
COUNT_ORDER = ("road", "rail", "power", "water", "highway", "subway")


class _R:
    def __init__(self, b):
        self.b, self.p = b, 0

    def u8(self):
        v = self.b[self.p]; self.p += 1; return v

    def u32(self):
        v = struct.unpack_from("<I", self.b, self.p)[0]; self.p += 4; return v

    def st(self):
        n = self.u32(); v = bytes(self.b[self.p:self.p + n]); self.p += n; return v


def parse(b):
    """-> dict with neighbors (each with 'counts_at' byte offset), raw deal bytes, edge cell lists."""
    r = _R(b)
    out = {"neighbors": []}
    for _ in range(4):
        n = {"name": r.st(), "mayor": r.st()}
        r.p += 4 + 4 + 1
        n["counts_at"] = r.p
        n["counts"] = dict(zip(COUNT_ORDER, (r.u32() for _ in range(6))))
        r.p += 6
        out["neighbors"].append(n)
    deals_from = r.p
    out["deals"] = []
    for key in ("active", "pending"):
        for _ in range(r.u32()):
            d = {"list": key, "city": r.st(), "desc": r.st()}
            d["amount"], d["cost"] = struct.unpack_from("<ii", b, r.p); r.p += 8
            d["neighbor"], d["type"] = r.u8(), r.u8()
            d["length"], d["termination_cost"], d["minimum_cost"], d["rate"] = struct.unpack_from("<4i", b, r.p); r.p += 16
            d["start_year"] = r.u32()
            out["deals"].append(d)
    out["head"] = bytes(b[:r.p])               # neighbors + deals, verbatim
    out["deals_from"] = deals_from
    out["edges"] = {}
    for name in EDGE_ORDER:
        out["edges"][name] = [((v >> 16), v & 0xffff) for v in (r.u32() for _ in range(r.u32()))]
    if r.p != len(b):
        raise ValueError("neighbor section: parsed %d of %d bytes" % (r.p, len(b)))
    return out


def side_of(x, y, w, h):
    """Map side of an edge cell, as SIMMISC FUN_10016f13 numbers them (corner cells: first match)."""
    if x == 0:
        return 0
    if y == 0:
        return 1
    if x == w - 1:
        return 2
    if y == h - 1:
        return 3
    return None


def build(parsed, edges, w, h):
    """Section bytes with the given edge cell lists and per-side counts recounted from them."""
    head = bytearray(parsed["head"])
    for side, n in enumerate(parsed["neighbors"]):
        counts = {k: 0 for k in COUNT_ORDER}
        for kind, cells in edges.items():
            counts[kind] += sum(1 for (x, y) in cells if side_of(x, y, w, h) == side)
        struct.pack_into("<6I", head, n["counts_at"], *(counts[k] for k in COUNT_ORDER))
    out = bytes(head)
    for name in EDGE_ORDER:
        cells = edges.get(name, [])
        out += struct.pack("<I", len(cells)) + b"".join(struct.pack("<I", (x << 16) | y) for x, y in cells)
    return out
