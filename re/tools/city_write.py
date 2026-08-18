#!/usr/bin/env python3
"""city_write.py - EDIT a SimCity 3000 city file and write it back.

The layer above `city_roundtrip.py`. That tool proved the pipeline is reversible
(container -> 24-byte header -> QFS -> section archive, 59/59 byte-identical). This one turns
that into an editing API: load a city, change something decoded, write a valid file.

    from city_write import City
    c = City.load("Cities/Berlin, Germany.sc3")
    c.n                              # 256 -- the map dimension
    c.zone_get(10, 20)               # the tile's zone-developer SLOT INDEX
    c.zone_set(10, 20, 0)            # 0 = unzoned
    c.save("out.sc3")

WHAT IS SAFE TO CHANGE, and it is deliberately narrow. Only the zone raster is decoded to a
per-tile meaning `[CONFIRMED, 59/59]`: the first `N*N` bytes of section
`{0x206c6e7c, 0x409ff3ba, instance 0}` are one byte per tile, and that byte indexes the
23-slot zone-developer table (Residential / Commercial / Industrial / Landfill named from
their `SC3Tune.INI` sections). Everything else is exposed as raw section bytes, because
nothing else has a decoded per-field meaning yet -- see `formats/CITY_SAVE.md`.

THE HONEST LIMITS. Read these before believing a modified file will work:

  1. **A modified file has NEVER been loaded by the game.** Byte-identical round-trip of an
     UNMODIFIED file is proven for all 59 shipped files; that is a statement about the
     container, not about whether the sim accepts edited contents. `--selftest` proves the
     former and nothing more.
  2. **No checksum is known, and that is not the same as there being none.** The 24-byte
     header carries two length fields and no checksum `[CONFIRMED @formats/CITY_SAVE.md]`, and
     the section archive has none either. If a validity check lives inside a section, this tool
     does not know about it.
  3. **The `u16` permutation is left alone.** The zone section's tail holds `N*N` distinct
     `u16`s -- a traversal order, not map content -- and the loader reads it back. Changing the
     raster does NOT update it, and whether the two must agree is `[UNCERTAIN]` (`U-029`).
  4. **Derived state is not recomputed.** The loader rebuilds a 23-entry slot histogram at
     `this+0x3c` when a read fails, so it can regenerate that itself; but RCI demand, land
     value and anything else downstream of zoning are NOT touched by editing the raster.

Usage:
  py -3.12 re/tools/city_write.py <file> --info
  py -3.12 re/tools/city_write.py <dir-or-file> --selftest        # round-trip identity
  py -3.12 re/tools/city_write.py <file> --set-zone X,Y=SLOT [...] -o <out>
  py -3.12 re/tools/city_write.py <file> --fill-zone SLOT -o <out>    # every zoned tile
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_parse
import city_roundtrip as RT
import ixf_parse
import qfs
import qfs_encode

ZONE_GROUP = 0x409FF3BA          # SC3ZoneLayer, SIMRCI
GRID_GROUP = 0x80AB8AB0          # SIMGEOM tile grid: frame(8) + N*N + 8 -> N = isqrt(size-16)
SECTION_TYPE = 0x206C6E7C

# The zone types. R/C/I/Landfill are named from the SC3Tune.INI section each constructor loads
# [CONFIRMED @0x10036382 and the four ctors]. The REST are named from the query tool's own
# zone-name switch, SIMRCI 0x10034716, which dispatches the raster byte either to a localized
# string in LTEXT group 0x82e0074c or to a hardcoded `*BUG*` string for a type the game refuses
# [CONFIRMED @0x10034716]. Corroborated at ten order-preserving points by the SimCity 2000
# importer's nibble table [CONFIRMED @0x10031bcc]. See formats/CITY_SAVE.md.
SLOT_NAMES = {
    0: "unzoned",
    1: "Residential", 2: "Residential", 3: "Residential",
    5: "Commercial", 6: "Commercial", 7: "Commercial",
    9: "Industrial", 10: "Industrial", 11: "Industrial",
    13: "Military -- REFUSED by the game (`*BUG* No military zones allowed!` @0x100581dc)",
    14: "Airport",                        # case 0xe -> LTEXT 25 `Aeropuerto`
    15: "Seaport",                        # case 0xf -> LTEXT 24 `Puerto`
    16: "Spaceport -- REFUSED by the game (`*BUG* No spaceport zones allowed` @0x100581b8)",
    17: "Landfill",                       # case 0x11 -> LTEXT 26 `Vertedero`
    22: "kPloppedBuilding -- a tile owned by a directly-placed building, NOT a zone developer. "
        "No case in the name switch, so the query tool reports it as `Unzoned` (LTEXT 405). "
        "No shipped x86 code writes it; the iOS sibling's PlaceBuilding stamps it over the "
        "footprint rect [iOS-HINT @0x001fe2a8]",
}


class CityError(Exception):
    pass


class Section:
    """One archive section: its 16-byte key plus its payload bytes."""

    __slots__ = ("type", "group", "instance", "data", "order")

    def __init__(self, stype, group, instance, data, order):
        self.type, self.group, self.instance = stype, group, instance
        self.data = bytearray(data)
        self.order = order            # position in the ORIGINAL table, which is file data

    def __repr__(self):
        return "<Section %08x:%08x:%d %d bytes>" % (self.type, self.group, self.instance,
                                                    len(self.data))


class City:
    """A loaded city file, editable, re-emittable."""

    def __init__(self, path, raw, slots, pad, tail, rec_offset, info, sections):
        self.path = path
        self._raw = raw                  # the original file bytes, for comparison only
        self._slots = slots              # .IXF index slots, verbatim
        self._pad = pad                  # reserved index slots (all zero in all 59 files)
        self._tail = tail                # unreferenced trailing bytes (7 .SNR files have some)
        self._rec_offset = rec_offset    # which payload record holds the city blob
        self._info = info                # parsed 24-byte header fields
        self.sections = sections

    # --- loading ---------------------------------------------------------------------

    @classmethod
    def load(cls, path):
        with open(path, "rb") as fh:
            raw = fh.read()
        slots, pad_len, payloads, free, tail_len = RT.container_layout(raw)
        index_end = 4 + len(slots) * RT.REC
        nonzero = [(o, n) for o, n in free if any(raw[o:o + n])]
        if nonzero:
            raise CityError("container free space carries data at %r; refusing to guess" % nonzero[:2])

        target = None
        for off, data in payloads:
            if city_parse.is_compressed_payload(data):
                target = (off, data)
                break
        if target is None:
            raise CityError("%s: no QFS city payload" % path)
        rec_offset, body = target
        plain, info = city_parse.parse_payload(body)
        _si, ents = city_parse.parse_sections(plain)

        sections = []
        for i, e in enumerate(sorted(ents, key=lambda x: x["abs"])):
            sections.append(Section(e["type"], e["group"], e["instance"],
                                    plain[e["abs"]:e["abs"] + e["size"]],
                                    next(j for j, x in enumerate(ents) if x is e)))
        return cls(path, raw, slots, raw[index_end:index_end + pad_len],
                   raw[len(raw) - tail_len:] if tail_len else b"", rec_offset, info, sections)

    # --- section access --------------------------------------------------------------

    def section(self, group, instance=0, stype=SECTION_TYPE):
        for s in self.sections:
            if s.group == group and s.instance == instance and s.type == stype:
                return s
        return None

    def declared_slots(self):
        """The zone-developer slots this city declares.

        Each non-NULL slot of the 23-slot table gets its own 4-byte section with
        `instance == slot + 1` `[CONFIRMED @0x100320e7:120-148]`, so the file states its own
        occupied set. Editing to an undeclared slot would put a value in the raster that this
        city has no developer for.
        """
        return {s.instance - 1 for s in self.sections
                if s.group == ZONE_GROUP and s.instance != 0}

    @property
    def n(self):
        """Map dimension, from the SIMGEOM tile-grid section: frame(8) + N*N + 8 bytes."""
        g = self.section(GRID_GROUP, 0, 0x406B1196)
        if g is None:
            raise CityError("no tile-grid section {0x406b1196, 0x80ab8ab0}")
        side = len(g.data) - 16
        n = int(round(side ** 0.5))
        if n * n != side:
            raise CityError("tile-grid section is %d bytes; %d-16 is not a square"
                            % (len(g.data), len(g.data)))
        return n

    # --- the zone raster -------------------------------------------------------------

    def _zone(self):
        z = self.section(ZONE_GROUP, 0)
        if z is None:
            raise CityError("no SC3ZoneLayer instance-0 section")
        n = self.n
        if len(z.data) < n * n:
            raise CityError("zone section %d bytes, shorter than N*N = %d" % (len(z.data), n * n))
        return z, n

    def zone_get(self, x, y):
        """The zone-developer slot index at (x, y). Row-major, stride N."""
        z, n = self._zone()
        if not (0 <= x < n and 0 <= y < n):
            raise CityError("(%d,%d) outside 0..%d" % (x, y, n - 1))
        return z.data[y * n + x]

    def zone_set(self, x, y, slot):
        """Set the tile's slot index. Refuses a slot this city does not declare.

        The bound is the loader's own: it accepts tile values `< 0x17` (23)
        `[CONFIRMED @0x10031c85:144-163]`. On top of that, this refuses values the file has no
        developer section for, because a raster byte is an index into that table and every one
        of the 59 shipped files keeps its non-zero values inside its own declared set.
        """
        z, n = self._zone()
        if not (0 <= x < n and 0 <= y < n):
            raise CityError("(%d,%d) outside 0..%d" % (x, y, n - 1))
        if not 0 <= slot < 0x17:
            raise CityError("slot %d outside the loader's own bound 0..22" % slot)
        if slot == 22:
            raise CityError(
                "22 (0x16) is kPloppedBuilding: the mark for a tile owned by a directly-placed "
                "BUILDING, not a zone developer [CONFIRMED @0x10034716, formats/CITY_SAVE.md]. "
                "Writing it would claim a building footprint with no occupant behind it, and the "
                "game's own path CLEARS it when an occupant's rect is processed "
                "[CONFIRMED @0x10032ca9]. Refused deliberately, not for lack of knowledge.")
        if slot and slot not in self.declared_slots():
            raise CityError("slot %d is not declared by this city (declared: %s); a raster byte "
                            "indexes the developer table, so an undeclared slot has no developer"
                            % (slot, sorted(self.declared_slots())))
        z.data[y * n + x] = slot

    def zone_histogram(self):
        z, n = self._zone()
        h = {}
        for b in z.data[:n * n]:
            h[b] = h.get(b, 0) + 1
        return dict(sorted(h.items()))

    # --- emitting --------------------------------------------------------------------

    def body_bytes(self):
        """Re-emit the decompressed body: header, payloads laid out contiguously, table.

        Offsets are RECOMPUTED rather than reused, which is what makes editing possible at all
        (a section that changes length shifts every later one). For an unmodified city this
        reproduces the original body exactly, because the shipped sections tile contiguously
        from offset 8 with no gaps `[CONFIRMED, 59/59]` -- `--selftest` is the check on that,
        not an assumption.
        """
        out = bytearray(8)
        offsets = {}
        for s in self.sections:
            offsets[id(s)] = len(out)
            out += s.data
        table_off = len(out)
        struct.pack_into("<2I", out, 0, len(self.sections), table_off)
        for s in sorted(self.sections, key=lambda x: x.order):
            out += struct.pack("<4I", s.type, s.group, s.instance, offsets[id(s)])
        return bytes(out)

    def to_bytes(self):
        """The whole file: body -> QFS -> 24-byte header -> .IXF container."""
        body = self.body_bytes()
        stream = qfs_encode.compress_stream(body)
        rec = RT.build_record_body(self._info, stream, len(body))
        slots = []
        delta = len(rec) - self._orig_record_len()
        for (g, i, t, off, size) in self._slots:
            if off == self._rec_offset and size != 0xFFFFFFFF:
                size = len(rec)
            elif size != 0xFFFFFFFF and off != 0xFFFFFFFF and off > self._rec_offset:
                off += delta          # records after the blob move when it changes length
            slots.append((g, i, t, off, size))
        payloads = []
        for off, data in RT.container_layout(self._raw)[2]:
            if off == self._rec_offset:
                payloads.append((off, rec))
            elif off > self._rec_offset:
                payloads.append((off + delta, data))
            else:
                payloads.append((off, data))
        return RT.build_container(slots, self._pad, payloads, self._tail)

    def _orig_record_len(self):
        for off, data in RT.container_layout(self._raw)[2]:
            if off == self._rec_offset:
                return len(data)
        raise CityError("lost track of the city record")

    def save(self, path):
        data = self.to_bytes()
        with open(path, "wb") as fh:
            fh.write(data)
        return len(data)

    def is_unchanged_roundtrip(self):
        """True if re-emitting reproduces the original file byte for byte."""
        return self.to_bytes() == self._raw


# --- CLI -------------------------------------------------------------------------------

def cmd_info(path):
    c = City.load(path)
    print("%s" % os.path.basename(path))
    print("  map dimension N   : %d" % c.n)
    print("  sections          : %d" % len(c.sections))
    print("  declared zone slots: %s" % sorted(c.declared_slots()))
    print("  zone raster histogram (slot: tiles):")
    for slot, cnt in c.zone_histogram().items():
        print("     %3d  %-8d %s" % (slot, cnt, SLOT_NAMES.get(slot, "")))
    print("  unmodified re-emit is byte-identical: %s" % c.is_unchanged_roundtrip())
    return 0


def cmd_selftest(target):
    ok = bad = 0
    for p in city_parse.walk(target):
        try:
            c = City.load(p)
            same = c.is_unchanged_roundtrip()
        except Exception as e:                                    # noqa: BLE001
            print("%-36s ERROR %s: %s" % (os.path.basename(p)[:36], type(e).__name__, e))
            bad += 1
            continue
        ok += same
        bad += not same
        print("%-36s %s" % (os.path.basename(p)[:36], "identical" if same else "DIFFERS"))
    print()
    print("load -> save with NO edits: %d/%d byte-identical" % (ok, ok + bad))
    print("This proves the container survives a rewrite. It does NOT prove the game accepts an")
    print("EDITED file -- that has never been tested. See the module docstring.")
    return 1 if bad else 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = argv[1]
    if "--selftest" in argv:
        return cmd_selftest(target)
    if "--info" in argv:
        return cmd_info(target)

    out = argv[argv.index("-o") + 1] if "-o" in argv else None
    edits = [a for a in argv if "," in a and "=" in a]
    fill = argv[argv.index("--fill-zone") + 1] if "--fill-zone" in argv else None
    if not out or (not edits and fill is None):
        print(__doc__)
        return 2

    c = City.load(target)
    n_edit = 0
    for e in edits:
        xy, _, slot = e.partition("=")
        x, _, y = xy.partition(",")
        c.zone_set(int(x), int(y), int(slot))
        n_edit += 1
    if fill is not None:
        slot = int(fill)
        for y in range(c.n):
            for x in range(c.n):
                if c.zone_get(x, y):
                    c.zone_set(x, y, slot)
                    n_edit += 1

    size = c.save(out)
    print("%d tile(s) changed -> %s (%d bytes)" % (n_edit, out, size))
    print("UNTESTED: no modified city file has ever been loaded by the game.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
