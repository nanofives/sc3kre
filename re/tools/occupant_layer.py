#!/usr/bin/env python3
"""occupant_layer.py - walk of the SIMGEOM occupant collection {group 0xa0ab89f0} (2026-10-09; writer: city_clone.py).

Layout (read of SIMGEOM saver FUN_100032ca / loader FUN_10002cc2, validated on all 15 shipped .sc3 and two
game-written 1024 saves, every byte consumed): instance 0 (type 0x20631788) = 8-byte frame + u32 count + u32 1;
instance 1 (type 0xe0faadc7) = 8-byte frame + records back to back, no count, size or id per record.
Record +0 u32 position: x bits 0-10, y bits 11-21, height bits 22-29 (recomputed from the terrain on load,
0x100035fd), rotation bits 30-31; +4 flags (footprint x bits 0-5, y bits 6-11; bits 21-28 enable optional
fields). No per-record ids or cross-section handles, so a record can be copied with a shifted position.

Grammar from SIMGEOM FUN_1001e226 (writer) / FUN_1001e516 (reader), stream primitives from
GZResourceD vtable 0x1001cb34 (0x88/0x98 = u32, 0x90 = 4 bytes, 0x84 = u32[n], 0xa4 = u32 len + bytes,
0xa8 = 3 x u32 key, 0xb0 = variant).
"""
import collections
import struct
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from city_write import City

GROUP = 0xa0ab89f0


class R:
    def __init__(self, d, o=0):
        self.d, self.o = d, o

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.o)[0]
        self.o += 4
        return v

    def raw(self, n):
        v = self.d[self.o:self.o + n]
        if len(v) != n:
            raise ValueError("short read")
        self.o += n
        return v

    def string(self):
        return self.raw(self.u32())


def variant(r):
    t = r.u32()
    raise NotImplementedError("variant type 0x%x at 0x%x" % (t, r.o - 4))


def record(r):
    o0 = r.o
    rec = {"off": o0}
    pos = r.u32()
    fl = r.u32()
    rec["pos"] = pos
    rec["a"] = pos & 0x7ff
    rec["b"] = (pos >> 11) & 0x7ff
    rec["alt"] = (pos >> 22) & 0xff
    rec["rot"] = pos >> 30
    rec["flags"] = fl
    rec["sa"] = fl & 0x3f
    rec["sb"] = (fl >> 6) & 0x3f
    rec["t18"] = r.u32()
    rec["key"] = (r.u32(), r.u32(), r.u32())
    if fl & (1 << 21):
        rec["str24"] = r.string()
    if fl & (1 << 22):
        rec["p1c"] = (r.u32(), r.u32())
    if fl & (1 << 27):
        rec["v38"] = r.u32()
    if fl & (1 << 28):
        rec["v3c"] = r.u32()
    if fl & (1 << 23):
        n = r.u32()
        rec["m40"] = [struct.unpack_from("<II", r.raw(8)) for _ in range(n)]
    if fl & (1 << 24):
        n = r.u32()
        rec["m4c"] = [(r.u32(), r.string()) for _ in range(n)]
    if fl & (1 << 25):
        n = r.u32()
        rec["m58"] = [(r.u32(), r.u32()) for _ in range(n)]
    if fl & (1 << 26):
        n = r.u32()
        rec["v64"] = [(r.u32(), variant(r)) for _ in range(n)]
    rec["len"] = r.o - o0
    return rec


def parse(path):
    c = City.load(path)
    s0 = c.section(GROUP, 0, 0x20631788).data
    s1 = c.section(GROUP, 1, 0xe0faadc7).data
    hdr0 = s0[:8]
    cnt, ver = struct.unpack_from("<II", s0, 8)
    r = R(s1, 8)
    recs = []
    while r.o < len(s1):
        recs.append(record(r))
    return c, s0, s1, cnt, ver, recs


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: occupant_layer.py <city.sc3>")
    path = sys.argv[1]
    c, s0, s1, cnt, ver, recs = parse(path)
    print("instance0:", s0.hex(), " count=%d second=%d" % (cnt, ver))
    print("instance1 header:", s1[:8].hex(), " bytes=%d" % len(s1))
    print("records parsed=%d  consumed to end=%s" % (len(recs), recs[-1]["off"] + recs[-1]["len"] == len(s1)))
    print("record lengths:", collections.Counter(x["len"] for x in recs).most_common())
    print("flags:", [(hex(k), v) for k, v in collections.Counter(x["flags"] for x in recs).most_common(30)])
    print("t18:", [(hex(k), v) for k, v in collections.Counter(x["t18"] for x in recs).most_common(30)])
    print("key type/group:", [("%08x/%08x" % k, v) for k, v in
                              collections.Counter(x["key"][:2] for x in recs).most_common(30)])
    print("a range", min(x["a"] for x in recs), max(x["a"] for x in recs),
          " b range", min(x["b"] for x in recs), max(x["b"] for x in recs),
          " alt", collections.Counter(x["alt"] for x in recs).most_common(5),
          " rot", collections.Counter(x["rot"] for x in recs).most_common())
    print("footprints:", collections.Counter((x["sa"], x["sb"]) for x in recs).most_common(15))
    for k in ("str24", "p1c", "v38", "v3c", "m40", "m4c", "m58", "v64"):
        xs = [x for x in recs if k in x]
        if xs:
            vals = collections.Counter(repr(x[k])[:60] for x in xs).most_common(8)
            print("field %s: present in %d; top %s" % (k, len(xs), vals))
    print()
    for x in recs[:20]:
        print("@%06x len=%d a=%d b=%d alt=%d rot=%d fl=%08x size=%dx%d t18=0x%x key=%08x/%08x/%08x %s" % (
            x["off"], x["len"], x["a"], x["b"], x["alt"], x["rot"], x["flags"], x["sa"], x["sb"], x["t18"],
            *x["key"], {k: x[k] for k in ("str24", "p1c", "v38", "v3c", "m40", "m4c", "m58") if k in x}))


if __name__ == "__main__":
    main()
