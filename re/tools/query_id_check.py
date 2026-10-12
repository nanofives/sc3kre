#!/usr/bin/env python3
r"""query_id_check.py - check a "Copiar ID" clipboard block (sc3resize QUERYID) against a saved city.

The block is what the query (?) dialog's "Copiar ID" button puts on the clipboard (spec: re/analysis/QUERY_ID.md).
This reads the same tile/object back from a .sc3 save and prints one verdict per comparable field:

  cell + zone          -> the zone raster at row N-1-x, column z           (see zone_at)
  object.packed        -> occupant_layer record whose position word matches (SIMGEOM occupant section)
  object.type_id/key/size/rotation/cell -> that record's +8 type id, +12 key, footprint, position bits
  network.words        -> network_layer tile(s) at network.tile x, y: word0 and the piece id

Only objects that exist in the save can be compared: query a city loaded from the file (or save right after the
query) and pass that file.

Usage:
  py -3.12 re/tools/query_id_check.py <city.sc3> --clip            # read the block from the Windows clipboard
  py -3.12 re/tools/query_id_check.py <city.sc3> <block.txt> [...]  # or from saved text files
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import city_write  # noqa: E402
import network_layer  # noqa: E402
import occupant_layer  # noqa: E402


def read_clipboard():
    import ctypes
    from ctypes import wintypes
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    u.GetClipboardData.restype = wintypes.HANDLE
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = [wintypes.HANDLE]
    k.GlobalUnlock.argtypes = [wintypes.HANDLE]
    if not u.OpenClipboard(None):
        raise SystemExit("cannot open the clipboard")
    try:
        h = u.GetClipboardData(13)  # CF_UNICODETEXT
        if not h:
            raise SystemExit("no text on the clipboard")
        p = k.GlobalLock(h)
        try:
            return ctypes.wstring_at(p)
        finally:
            k.GlobalUnlock(h)
    finally:
        u.CloseClipboard()


def parse_block(text):
    f = {}
    for line in text.splitlines():
        m = re.match(r"^([a-z_.]+)\??:\s*(.*)$", line.strip())
        if m:
            f[m.group(1)] = m.group(2)
    return f


def hexes(s):
    return [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]+)", s)]


def kv(s, key):
    m = re.search(r"\b%s=(-?\d+)" % key, s)
    return int(m.group(1)) if m else None


def zone_at(c, x, z):
    """Zone byte at the game's cell (x, z). The raster row is N-1-x and the column z: 12 of 12 query readings in
    Berlin matched this and no other of the 8 axis orders (verify/queryid/RESULTS.md). city_write.zone_get(X, Y) reads
    data[Y*N + X], so the game cell (x, z) is zone_get(z, N-1-x)."""
    return c.zone_get(z, c.n - 1 - x)


def check(city_path, f, cache):
    out = []

    def verdict(name, ok, got, want):
        out.append("%-20s %s  clipboard=%s  save=%s" % (name, "PASS" if ok else "FAIL", got, want))

    if "city" not in cache:
        cache["city"] = city_write.City.load(city_path)
        _, _, _, _, _, recs = occupant_layer.parse(city_path)
        cache["occ_full"] = {r["pos"]: r for r in recs}
        cache["net"], _ = network_layer.read_networks(city_path)
    c = cache["city"]
    cell = f.get("cell", "")
    x, z = kv(cell, "x"), kv(cell, "z")
    if x is not None and "zone" in f:
        zb = int(f["zone"].split()[0])
        verdict("zone", zone_at(c, x, z) == zb, zb, zone_at(c, x, z))
    if "object.packed" in f and "network.piece_id" not in f:
        w = hexes(f["object.packed"])[0]
        r = cache["occ_full"].get(w)
        if r is None:
            out.append("%-20s n/a   no record with position word 0x%08X in the SIMGEOM occupant section (flora, "
                       "network pieces and some other classes are saved elsewhere)" % ("object.packed", w))
        else:
            verdict("object.packed", True, "0x%08X" % w, "record @%06x" % r["off"])
            if "object.type_id" in f:
                tid = int(f["object.type_id"].split()[0])
                verdict("object.type_id", r["t18"] == tid, tid, r["t18"])
            if "object.key" in f:
                k = tuple(hexes(f["object.key"]))
                verdict("object.key", k == tuple(r["key"]), "%08X/%08X/%08X" % k, "%08X/%08X/%08X" % tuple(r["key"]))
            if "object.size" in f:
                m = re.match(r"(\d+)x(\d+)", f["object.size"])
                got = (int(m.group(1)), int(m.group(2)))
                verdict("object.size", got == (r["sa"], r["sb"]), "%dx%d" % got, "%dx%d" % (r["sa"], r["sb"]))
            if "object.rotation" in f:
                rot = int(f["object.rotation"].split()[0])
                verdict("object.rotation", rot == r["rot"], rot, r["rot"])
            if "object.cell" in f:
                oc = f["object.cell"]
                got = (kv(oc, "x"), kv(oc, "z"), kv(oc, "alt"))
                verdict("object.cell", got == (r["a"], r["b"], r["alt"]), got, (r["a"], r["b"], r["alt"]))
    if "network.words" in f and "network.tile" in f:
        w0, w1 = hexes(f["network.words"])[:2]
        t = f["network.tile"]
        tx, ty = kv(t, "x"), kv(t, "y")
        hits = [(inst, tile) for inst, tiles in cache["net"].items() for tile in tiles if tile[0] == tx and tile[1] == ty]
        if not hits:
            out.append("%-20s n/a   no network tile at %d,%d in the save" % ("network", tx, ty))
        for inst, (xx, yy, zz, flg, piece, state) in hits:
            s0 = struct.unpack("<I", network_layer.Tile(xx, yy, zz, flg, piece, state).pack()[:4])[0]
            name = {1: "surface", 2: "pipe", 3: "subway"}.get(inst, str(inst))
            out.append("%-20s %s  save[%s] word0=0x%08X piece=%d  clipboard word0=0x%08X piece=%d" % (
                "network", "MATCH" if (s0, piece) == (w0, w1 & 0xffff) else "other", name, s0, piece, w0, w1 & 0xffff))
    return out


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    city = argv[0]
    blocks = [read_clipboard()] if argv[1] == "--clip" else [open(p, encoding="utf-8", errors="replace").read() for p in argv[1:]]
    cache = {}
    for b in blocks:
        f = parse_block(b)
        print("--- %s | %s" % (f.get("cell", "?"), f.get("object.name", f.get("object.class", "no object"))))
        for line in check(city, f, cache):
            print("  " + line)


if __name__ == "__main__":
    main(sys.argv[1:])
