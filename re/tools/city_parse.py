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

DECOMPRESSED BODY (first bytes; layout NOT yet fully decoded)
    +0x00  u32   e.g. 0x3d
    +0x04  u32   e.g. 0x20d7f7      (slightly less than the total -- a section length?)
    +0x08  u32   e.g. 0x00020003
    +0x0c  u32   0xDEADBEEF          [CONFIRMED] a literal marker in every file
    +0x10  u32   e.g. 0x40510625
    +0x14  ...   byte data in the 0x16..0x20 range -- consistent with a terrain height map,
                 but [UNCERTAIN]: no code has been read that consumes this yet.

Usage:
  py -3.12 re/tools/city_parse.py <file.sc3>                 # index + payload summary
  py -3.12 re/tools/city_parse.py <dir>                      # walk a tree, validate all
  py -3.12 re/tools/city_parse.py <file.sc3> --extract out\  # write decompressed payloads
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
