#!/usr/bin/env python3
"""city_parse.py - open SimCity 3000 city / terrain / scenario files.

  .sc3  saved cities      .sct  terrains      .snr  scenarios      .st3  starter towns

All four are `.IXF` containers (see re/analysis/formats/CITY_SAVE.md). Their bulk payload is
a single large record whose body is a 24-byte header followed by a **QFS-compressed** stream --
the same QFS used for sprites, so re/tools/qfs.py decodes it unchanged.

PAYLOAD RECORD LAYOUT [CONFIRMED against all 59 shipped city-family files]

    +0x00  u32   0x67 (103)          constant in every shipped file
    +0x04  u32   4                   constant in every shipped file
    +0x08  char4 "0.90"              ASCII version; "0.90" in every shipped file
    +0x0c  u32   compressedLength    == len(record) - 20
    +0x10  u32   uncompressedLength  == the QFS stream's own declared size
    +0x14  u32   compressedLength    (repeated)
    +0x18        QFS stream (magic 0x10FB)

The QFS stream's 3-byte big-endian declared size agrees with the u32 at +0x10 in all 59 files,
which is what pins the header layout.

DECOMPRESSED BODY [CONFIRMED against all 59 shipped files]

    +0x00  u32   sectionCount
    +0x04  u32   sectionTableOffset      == len(body) - sectionCount*16, in all 59 files
    +0x08  ...   section payloads (the FIRST section starts here, at offset 8, in all 59)
    @tableOffset  sectionCount x 16-byte SECTION ENTRIES:
                    +0  u32 type
                    +4  u32 group      <- a GZCOM CLASS id: SC3ZoneLayer 0x409ff3ba and
                                          SC3WorldLayer 0xe11bddf6 appear here EXACTLY
                    +8  u32 instance   (small ints, 0..18)
                    +12 u32 offset     (strictly increasing when sorted; all < tableOffset)

    So the table is the city's SAVED-LAYER DIRECTORY: a GZCOM {type, group, instance} key
    per section plus its offset. 3,451 sections across the 59 files.

    SECTION OFFSET BASE = 0 [CONFIRMED, 59/59 -- an earlier "+0x0C" reading is FALSIFIED]
    The `offset` field is absolute in the body. The body header is 8 bytes, not 20: what used
    to be read as header fields at +0x08 / +0x0c / +0x10 is the FIRST SECTION's own content.

    Proof: many savers wrap their section in an 8-byte object frame written by SIMCITY's frame
    class (ctor 0x10010315 read / 0x10010531 write):

        u16 version ; u8 flags ; u8 extra (read iff flags & 2) ; u32 0xDEADBEEF

    With base 0 that frame sits exactly at a section start for 2,330 of the 3,451 sections --
    and 2,330 is ALSO the total number of 0xDEADBEEF occurrences in all 59 decompressed
    bodies. Every marker in every file is accounted for, none is left over, and no marker
    lands anywhere but a section start. With base 12 only 319 sections line up. The remaining
    1,121 sections belong to classes that serialise without the frame.

    Section SIZES are the delta to the next sorted offset (the table has no size field); the
    last section runs to tableOffset.

    [UNCERTAIN] group `0x029ca804` occurs once per file and sits 2 below the pinned
    TrafficLayer id `0x029ca806`. Near-miss ids are NOT treated as matches here.

Usage:
  py -3.12 re/tools/city_parse.py <file.sc3>                  # index + payload summary
  py -3.12 re/tools/city_parse.py <file.sc3> --sections       # + the full section table
  py -3.12 re/tools/city_parse.py <dir>                       # walk a tree, validate all
  py -3.12 re/tools/city_parse.py <file.sc3> --extract out/   # write decompressed payloads
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ixf_parse
import qfs

HDR = 0x18
QFS_MAGIC = 0x10FB
DEADBEEF = 0xDEADBEEF
OFFSET_BASE = 0    # [CONFIRMED 59/59] section offsets are absolute; body header is 8 bytes


class CityError(Exception):
    pass


def is_compressed_payload(body):
    """True if this record body is the 24-byte header + QFS form."""
    return len(body) >= HDR + 2 and ((body[HDR] << 8) | body[HDR + 1]) == QFS_MAGIC


def parse_payload(body):
    """-> (decompressed, info). Raises CityError if the header does not check out."""
    if not is_compressed_payload(body):
        raise CityError("not a QFS payload (no 0x10FB at +0x18)")
    a, b = struct.unpack_from("<2I", body, 0)
    version = body[8:12].decode("ascii", "replace")
    clen, ulen, clen2 = struct.unpack_from("<3I", body, 12)
    out, consumed, declared = qfs.decompress(body, HDR)
    if declared != ulen:
        raise CityError("header says %d uncompressed, QFS stream says %d" % (ulen, declared))
    if len(out) != declared:
        raise CityError("produced %d bytes, declared %d" % (len(out), declared))
    info = {"a": a, "b": b, "version": version, "clen": clen, "ulen": ulen,
            "clen2": clen2, "consumed": consumed,
            "deadbeef": len(out) >= 16 and struct.unpack_from("<I", out, 12)[0] == DEADBEEF}
    return out, info


# GZCOM class ids pinned elsewhere in the project (re/analysis/MODULE_MAP.md, HANDOFF.md).
# Only EXACT matches are labelled -- a near-miss id is a different class, not a typo.
KNOWN_CLASS = {
    0x20AFDF44: "SC3PowerLayer", 0x82BF0042: "SC3WaterLayer", 0x60A42F32: "SC3ValveLayer",
    0x409FF3BA: "SC3ZoneLayer", 0x029CA806: "TrafficLayer", 0xE150E7BB: "SC3BuildingLayer",
    0xC11BCC75: "SC3BudgetLayer", 0xE11BDDF6: "SC3WorldLayer", 0xA411112F: "SpriteManager",
}


def read_frame(body, pos):
    """The SIMCITY object frame, if one starts at `pos`.

    From SIMCITY.DLL FUN_10010315 (read ctor) / FUN_10010531 (write ctor):
        u16 version           [CONFIRMED @0x10010315]
        u8  flags
        u8  extra   -- read only if flags & 2
        u32 0xDEADBEEF        -- the ctor rejects the object if this does not match
    Returns {"len", "version", "flags", "extra"} or None.
    """
    if pos + 7 > len(body):
        return None
    version, flags = struct.unpack_from("<HB", body, pos)
    p = pos + 3
    extra = None
    if flags & 2:
        if p >= len(body):
            return None
        extra = body[p]
        p += 1
    if p + 4 > len(body) or struct.unpack_from("<I", body, p)[0] != DEADBEEF:
        return None
    return {"len": p + 4 - pos, "version": version, "flags": flags, "extra": extra}


def parse_sections(body):
    """-> (info, [entries]). Each entry: {type, group, instance, offset, size, cls, frame}."""
    count, table = struct.unpack_from("<2I", body, 0)
    if table + count * 16 != len(body):
        raise CityError("count*16 + tableOffset (%d) != body length (%d)"
                        % (table + count * 16, len(body)))
    ents = []
    for i in range(count):
        t, g, inst, off = struct.unpack_from("<4I", body, table + i * 16)
        ents.append({"type": t, "group": g, "instance": inst,
                     "offset": off,               # as stored
                     "abs": OFFSET_BASE + off,    # absolute in the body
                     "cls": KNOWN_CLASS.get(g),
                     "frame": read_frame(body, OFFSET_BASE + off)})
    # No size field exists; derive it from the next section in offset order.
    order = sorted(ents, key=lambda e: e["offset"])
    for a, b in zip(order, order[1:]):
        a["size"] = b["offset"] - a["offset"]
    if order:
        order[-1]["size"] = table - order[-1]["abs"]
    return {"count": count, "table": table,
            "framed": sum(1 for e in ents if e["frame"])}, ents


def walk(target):
    if os.path.isfile(target):
        yield target
        return
    for root, _dirs, files in os.walk(target):
        for f in sorted(files):
            if f.lower().endswith((".sc3", ".sct", ".snr", ".st3")):
                yield os.path.join(root, f)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = argv[1]
    extract = argv[argv.index("--extract") + 1] if "--extract" in argv else None
    if extract:
        os.makedirs(extract, exist_ok=True)

    n_files = n_pay = n_bad = 0
    tot_in = tot_out = 0
    for path in walk(target):
        try:
            records, d = ixf_parse.parse(path)
        except ixf_parse.IxfError as e:
            print("SKIP %s" % e, file=sys.stderr)
            continue
        n_files += 1
        payloads = []
        for idx, r in enumerate(records):
            body = d[r["offset"]:r["offset"] + r["size"]]
            if not is_compressed_payload(body):
                continue
            try:
                out, info = parse_payload(body)
            except (CityError, qfs.QfsError) as e:
                n_bad += 1
                print("  FAIL %s rec %d: %s" % (os.path.basename(path), idx, e), file=sys.stderr)
                continue
            n_pay += 1
            tot_in += len(body)
            tot_out += len(out)
            payloads.append((idx, r, info, out))

        print("%-34s %2d records, %d payload(s)%s"
              % (os.path.basename(path), len(records), len(payloads),
                 "" if payloads else "  (no compressed payload)"))
        for idx, r, info, out in payloads:
            print("    rec %-3d type 0x%08x  v%s  %s -> %s bytes  DEADBEEF=%s"
                  % (idx, r["type"], info["version"], "{:,}".format(info["clen"]),
                     "{:,}".format(len(out)), info["deadbeef"]))
            try:
                sinfo, ents = parse_sections(out)
                named = [e for e in ents if e["cls"]]
                print("      %d sections, %d framed%s"
                      % (sinfo["count"], sinfo["framed"],
                         "" if not named else "; named classes: "
                         + ", ".join(sorted({"%s x%d" % (c, sum(1 for e in named if e["cls"] == c))
                                             for c in {e["cls"] for e in named}}))))
                if "--sections" in argv:
                    for e in sorted(ents, key=lambda x: x["offset"]):
                        f = e["frame"]
                        print("        %08x:%08x:%-3d  off %-9d size %-9d %-13s %s"
                              % (e["type"], e["group"], e["instance"], e["offset"],
                                 e.get("size", 0), e["cls"] or "",
                                 "" if not f else "frame v%d f%d" % (f["version"], f["flags"])))
            except (CityError, struct.error) as e:
                print("      section table: %s" % e)
            if extract:
                name = "%s_%d_%08x.bin" % (os.path.splitext(os.path.basename(path))[0],
                                           idx, r["type"])
                with open(os.path.join(extract, name), "wb") as fh:
                    fh.write(out)

    print("\n%d files, %d payloads decoded, %d failed" % (n_files, n_pay, n_bad))
    if tot_in:
        print("%s compressed -> %s decompressed (%.2fx)"
              % ("{:,}".format(tot_in), "{:,}".format(tot_out), tot_out / tot_in))
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
