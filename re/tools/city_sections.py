#!/usr/bin/env python3
"""city_sections.py - decode the INSIDE of SimCity 3000 city-save sections.

`city_parse.py` gets you the container, the QFS payload, the section table and the per-section
frame. This goes one level in: it applies per-class decoders to the sections whose layout is
established in `re/analysis/formats/CITY_SAVE.md`, and reports everything else as raw.

It decodes only what there is evidence for. A section with no decoder is reported with its
size, frame and first bytes -- never guessed at.

THE MAP DIMENSION IS READABLE FROM THE FILE  [CONFIRMED, 59/59]
--------------------------------------------------------------
CITY_SAVE.md records that the zone blob is not self-describing (its reader takes rowCount and
rowBytes from the object, never from the stream) and that SC3WorldLayer was FALSIFIED as the
source of the dimensions. The source is the SIMGEOM tile-grid section instead:

    section {type 0x406b1196, group 0x80ab8ab0}  =  frame(8) + N*N bytes + 8-byte trailer

so `N = isqrt(size - 16)`. Two independent derivations agree in all 59 shipped files:

  * this section:      size - 16 == N*N
  * the zone blob:     size == 3*N*N + tail,  tail == 900 + 6k

N is 128, 192 or 256 -- the three map sizes. Neither derivation was used to build the other.

They agree on N, and therefore on the size DECOMPOSITION. They say nothing about what fills
it: the "3 planes of N*N" reading is FALSIFIED. Only the first N*N is a raster; the following
2*N*N has no spatial coherence at any stride and uses all 256 byte values. See CITY_SAVE.md,
"Attempt 8".

Usage:
  py -3.12 re/tools/city_sections.py <file.sc3>            # decode one file
  py -3.12 re/tools/city_sections.py <dir>                 # validate a whole tree
  py -3.12 re/tools/city_sections.py <file.sc3> --pgm out/ # dump byte grids as PGM images
"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_parse            # noqa: E402
import ixf_parse             # noqa: E402

GRID_GROUP = 0x80AB8AB0      # SIMGEOM tile grid, saver 0x1000beec
ZONE_GROUP = 0x409FF3BA      # SC3ZoneLayer, saver 0x100320e7 / loader 0x10031c85
WORLD_GROUP = 0xE11BDDF6     # SC3WorldLayer, save 0x1002776c / load 0x10027563
DIRT_GROUP = 0x21737DE5      # SIMDIRT terrain, saver 0x10004d90 ("DirtBag")

# Zone-raster value -> developer class. The three groups come from the reader FUN_1001deca,
# which partitions the value exactly this way; the class NAMES come from the SC3Tune.INI
# section each developer's constructor loads (ResidentialZoneDeveloper at 0x10028198,
# CommercialZoneDeveloper at 0x1000f022, IndustrialZoneDeveloper at 0x10016290,
# LandfillZoneDeveloper at 0x100194cf). Two independent lines of evidence, same grouping.
# [CONFIRMED @0x10036382, 0x1001deca] -- see CITY_SAVE.md.
ZONE_CLASS = {
    "residential": (1, 2, 3),
    "commercial": (5, 6, 7, 0x0E, 0x16),   # 0x16 is grouped here by the reader but is not a
                                           # declared developer slot in any file
    "industrial": (9, 10, 11, 0x0F),
    "landfill": (17,),
}


class SectionError(Exception):
    pass


def map_dimension(ents):
    """-> N from the tile-grid section, or None. [CONFIRMED 59/59]"""
    for e in ents:
        if e["group"] != GRID_GROUP:
            continue
        flen = e["frame"]["len"] if e["frame"] else 0
        payload = e["size"] - flen - 8          # 8-byte trailer
        n = math.isqrt(payload)
        if n * n == payload and n in (128, 192, 256):
            return n
    return None


def decode_tile_grid(body, e, n):
    """frame + N*N bytes + 8 trailer. Returns the raw grid."""
    flen = e["frame"]["len"] if e["frame"] else 0
    s = e["abs"] + flen
    grid = body[s:s + n * n]
    if len(grid) != n * n:
        raise SectionError("short grid")
    return {"kind": "tile_grid", "n": n, "grid": grid,
            "trailer": body[s + n * n:e["abs"] + e["size"]],
            "distinct": len(set(grid))}


def decode_zone_bulk(body, e, n):
    """The zone blob: plane 0 is a 1-byte-per-tile raster of N*N.

    Only plane 0 is a raster [CONFIRMED by stride coherence]. The remaining 2*N*N is NOT --
    it is high-entropy packed data, falsified as a plane. It and the 900+6k tail are undecoded --
    the grammar for them is confirmed from both the saver and the loader and still does not
    match the bytes after seven attempts (U-029). Reporting them raw is the honest option.
    """
    s = e["abs"]
    plane = body[s:s + n * n]
    if len(plane) != n * n:
        raise SectionError("short zone plane")
    rest = e["size"] - 3 * n * n
    # Each byte is a ZONE-DEVELOPER SLOT INDEX into the 23-slot table [CONFIRMED 59/59]:
    # 0 == unzoned (all 21 .sct terrains are 100% zero), and every other value is one of the
    # slots that file declares via its 4-byte id sections -- with the single exception of
    # 0x16, which is in range but never declared. See CITY_SAVE.md.
    hist = {}
    for b in plane:
        hist[b] = hist.get(b, 0) + 1
    return {"kind": "zone_bulk", "n": n, "grid": plane, "distinct": len(set(plane)),
            "unzoned": hist.get(0, 0), "slots": sorted(k for k in hist if k),
            "by_class": {c: sum(hist.get(v, 0) for v in vs)
                         for c, vs in ZONE_CLASS.items()},
            "undecoded_middle": 2 * n * n, "tail": rest}


def decode_zone_id(body, e):
    """The twelve 4-byte SC3ZoneLayer sections: one slot id each, byte-identical in all 59."""
    if e["size"] != 4:
        raise SectionError("not a 4-byte id section")
    return {"kind": "zone_slot_id",
            "slot": e["instance"] - 1,            # instance == slot index + 1
            "id": struct.unpack_from("<I", body, e["abs"])[0]}


def decode_framed_u32s(body, e):
    """Generic: a frame followed by whole u32s. Used for the small framed sections."""
    fr = e["frame"]
    if not fr:
        raise SectionError("no frame")
    s, end = e["abs"] + fr["len"], e["abs"] + e["size"]
    if (end - s) % 4:
        raise SectionError("payload not a whole number of u32s")
    return {"kind": "framed_u32", "version": fr["version"],
            "values": list(struct.unpack_from("<%dI" % ((end - s) // 4), body, s))}


def decode(body, e, n):
    g, sz = e["group"], e["size"]
    try:
        if g == GRID_GROUP:
            return decode_tile_grid(body, e, n) if n else None
        if g == ZONE_GROUP:
            if sz == 4:
                return decode_zone_id(body, e)
            if e["instance"] == 0 and n and sz > 3 * n * n:
                return decode_zone_bulk(body, e, n)
            return None
        if e["frame"] and sz - e["frame"]["len"] <= 64:
            return decode_framed_u32s(body, e)
    except (SectionError, struct.error):
        return None
    return None


def write_pgm(path, grid, n):
    with open(path, "wb") as fh:
        fh.write(b"P5\n%d %d\n255\n" % (n, n))
        fh.write(grid)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = argv[1]
    pgm = argv[argv.index("--pgm") + 1] if "--pgm" in argv else None
    if pgm:
        os.makedirs(pgm, exist_ok=True)

    files = n_grid = n_dec = n_sec = 0
    for path in city_parse.walk(target):
        records, d = ixf_parse.parse(path)
        for rec in records:
            raw = d[rec["offset"]:rec["offset"] + rec["size"]]
            if not city_parse.is_compressed_payload(raw):
                continue
            body, _ = city_parse.parse_payload(raw)
            info, ents = city_parse.parse_sections(body)
            n = map_dimension(ents)
            files += 1
            if n:
                n_grid += 1
            base = os.path.basename(path)
            decoded = []
            for e in sorted(ents, key=lambda x: x["offset"]):
                n_sec += 1
                dec = decode(body, e, n)
                if dec:
                    n_dec += 1
                    decoded.append((e, dec))
            print("%-34s N=%-4s %d sections, %d decoded"
                  % (base, n or "?", len(ents), len(decoded)))
            for e, dec in decoded:
                if dec["kind"] == "tile_grid":
                    print("    tile grid      %dx%d, %d distinct byte values, trailer %s"
                          % (dec["n"], dec["n"], dec["distinct"], dec["trailer"].hex(" ")))
                elif dec["kind"] == "zone_bulk":
                    print("    zone plane 0   %dx%d, %.1f%% unzoned, developer slots %s"
                          % (dec["n"], dec["n"],
                             100.0 * dec["unzoned"] / (dec["n"] * dec["n"]),
                             dec["slots"]))
                    print("                   by class: %s"
                          % ", ".join("%s %.1f%%" % (c, 100.0 * v / (dec["n"] * dec["n"]))
                                      for c, v in dec["by_class"].items() if v))
                    print("                   %d bytes undecoded + %d tail (U-029)"
                          % (dec["undecoded_middle"], dec["tail"]))
                elif dec["kind"] == "zone_slot_id" and dec["slot"] in (1, 5, 9):
                    print("    zone slot %-2d   id 0x%08x" % (dec["slot"], dec["id"]))
                if pgm and dec["kind"] in ("tile_grid", "zone_bulk"):
                    name = "%s_%08x_%s.pgm" % (os.path.splitext(base)[0], e["group"],
                                               dec["kind"])
                    write_pgm(os.path.join(pgm, name), dec["grid"], dec["n"])

    print("\n%d files, %d with a readable map dimension, %d of %d sections decoded"
          % (files, n_grid, n_dec, n_sec))
    return 0 if n_grid == files else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
