#!/usr/bin/env python3
r"""netvariant.py - read and repair the variant data of a saved city, offline (netmod suite, 2026-10-13).

sc3netmod.dll saves every variant tile with its BASE id in the tile word (stock-loadable) and lists the variant ids
in one extra network section {0x206c6e7c, 0x2147c2dd, instance 0x4E56}: frame (version 1) + "NVR1" + count +
count x {u32 word0, u32 word1 as saved, u32 variant id}. re/analysis/NETVARIANT.md has the evidence.

  py -3.12 netvariant.py scan <city.sc3> [--table <netmod_variants.txt>]
        tiles whose id is a variant (raw, as an old save holds them) and the section's entries
  py -3.12 netvariant.py fallback <in.sc3> <out.sc3> --table <netmod_variants.txt>
        repair an OLD save written without sc3netmod: raw variant ids -> base in the tile words, and the section
        written so sc3netmod restores them. The result opens on a stock game (base pieces) and with the mod (variants).

Pass the variant table (the installed Apps\Res\netmod_variants.txt) with --table, or pairs with --map 20029:29.
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import city_write      # noqa: E402

NET_TYPE, NET_GROUP, NV_INST = 0x206c6e7c, 0x2147c2dd, 0x4E56
NV_MAGIC = 0x3152564E
# The frame sc3netmod's in-game save writes through SIMNTWRK FUN_10026129 (version 1): read back from
# verify/netvariant S1_after.sc3 as 01 00 02 00 ef be ad de.
NV_FRAME = bytes.fromhex("01000200efbeadde")
NET_FRAME_LEN = 8


def read_table(args):
    t = {}
    if args.table:
        for line in open(args.table, encoding="ascii"):
            line = line.strip()
            if not line or line[0] in "#;":
                continue
            v, b = (int(x) for x in line.split()[:2])
            t[v] = b
    for m in args.map or []:
        v, b = (int(x) for x in m.split(":"))
        t[v] = b
    return t


def section_entries(city):
    s = city.section(NET_GROUP, NV_INST, NET_TYPE)
    if s is None:
        return None
    d = bytes(s.data)
    if d[4:8] != NV_FRAME[4:8]:
        raise SystemExit("section 0x4E56 has no 0xDEADBEEF frame")
    magic, n = struct.unpack_from("<II", d, 8)
    if magic != NV_MAGIC:
        raise SystemExit("section 0x4E56 magic 0x%08X" % magic)
    return [struct.unpack_from("<III", d, 16 + 12 * i) for i in range(n)]


def surface_words(city):
    s = city.section(NET_GROUP, 1, NET_TYPE)
    d = s.data
    return s, [(i, struct.unpack_from("<II", d, NET_FRAME_LEN + 8 * i))
               for i in range((len(d) - NET_FRAME_LEN) // 8)]


def xy(w0):
    return w0 & 0x7ff, (w0 >> 11) & 0x7ff


def cmd_scan(a):
    table = read_table(a)
    c = city_write.City.load(a.city)
    raw = []
    for inst in (1, 2, 3):
        s = c.section(NET_GROUP, inst, NET_TYPE)
        if s is None:
            continue
        d = s.data
        for i in range((len(d) - NET_FRAME_LEN) // 8):
            w0, w1 = struct.unpack_from("<II", d, NET_FRAME_LEN + 8 * i)
            if (w1 & 0xffff) in table:
                raw.append((inst, xy(w0), w1 & 0xffff))
    print("raw variant tiles (stock drops these on load): %d" % len(raw))
    for r in raw:
        print("  net %d (%d,%d) id %d" % (r[0], r[1][0], r[1][1], r[2]))
    ents = section_entries(c)
    if ents is None:
        print("section 0x4E56: absent")
    else:
        print("section 0x4E56: %d entries" % len(ents))
        for w0, w1, vid in ents:
            print("  (%d,%d) saved id %d -> variant %d" % (xy(w0) + (w1 & 0xffff, vid)))
    return 0


def cmd_fallback(a):
    table = read_table(a)
    if not table:
        raise SystemExit("no variants: pass --table or --map")
    c = city_write.City.load(a.inp)
    ents = section_entries(c) or []
    n = 0
    for inst in (1, 2, 3):
        s = c.section(NET_GROUP, inst, NET_TYPE)
        if s is None:
            continue
        for i in range((len(s.data) - NET_FRAME_LEN) // 8):
            off = NET_FRAME_LEN + 8 * i
            w0, w1 = struct.unpack_from("<II", s.data, off)
            vid = w1 & 0xffff
            if vid in table:
                w1b = (w1 & 0xffff0000) | table[vid]
                struct.pack_into("<I", s.data, off + 4, w1b)
                ents.append((w0, w1b, vid))
                n += 1
    if not n:
        print("no raw variant tiles in %s; nothing to do" % a.inp)
        return 0
    body = NV_FRAME + struct.pack("<II", NV_MAGIC, len(ents)) + b"".join(struct.pack("<III", *e) for e in ents)
    s = c.section(NET_GROUP, NV_INST, NET_TYPE)
    if s is None:
        order = max(x.order for x in c.sections) + 1
        c.sections.append(city_write.Section(NET_TYPE, NET_GROUP, NV_INST, body, order))
    else:
        s.data = bytearray(body)
    size = c.save(a.out)
    print("%d raw variant tile(s) -> base; section 0x4E56 holds %d entries; wrote %s (%d bytes)"
          % (n, len(ents), a.out, size))
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("city")
    f = sub.add_parser("fallback")
    f.add_argument("inp")
    f.add_argument("out")
    for p in (s, f):
        p.add_argument("--table")
        p.add_argument("--map", action="append", help="variant:base, repeatable")
    a = ap.parse_args(argv[1:])
    return cmd_scan(a) if a.cmd == "scan" else cmd_fallback(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
