#!/usr/bin/env python3
"""ixf_parse.py - parse/extract SimCity 3000 Unlimited .IXF GZ database segments.

FORMAT (CONFIRMED against Apps\\Res\\Text\\*\\*.IXF and Apps\\Res\\*.IXF; round-trip validated).
Mirrors the style of re/tools/syspak_parse.py. This is the container the GZCOM resource
manager reads for every localized string (see re/analysis/formats/IXF_segment.md).

  .IXF
    +0x00  u32  magic = 0x80C381D7            ; verified by GZResourceD 0x1000ca78
    +0x04  index: N x 20-byte records, contiguous:
              u32 group        ; the "group id" seen in SC3U.exe call sites
              u32 instance     ; the small index seen in SC3U.exe call sites
              u32 type         ; 0x2026960B for localized strings
              u32 offset       ; ABS file offset of the payload
              u32 size         ; payload length in bytes
           an all-zero record terminates the index; the remaining slots are zero padding
           (files reserve far more slots than they use)
    payload (at each record's offset):
              u32 length       ; byte length of the text that follows
              char[length]     ; the bytes; NOT NUL-terminated

  The key SC3U.exe builds -- {type=0x2026960B, group, instance} (re/analysis/RESOURCE_KEYS.md)
  -- is exactly an index lookup here: match type+group+instance, seek offset, read size.

NOTE ON LANGUAGES (observed, not inferred): the directory named ENGLISH contains SPANISH text;
the actual English strings are in English-UK. Verified on BAMBEStringsMain.IXF across
ENGLISH / English-UK / GERMAN / FRENCH.

Usage:
  py -3.12 re/tools/ixf_parse.py <file.IXF>                # list records + validation
  py -3.12 re/tools/ixf_parse.py <file.IXF> --dump         # print every string
  py -3.12 re/tools/ixf_parse.py <dir> --csv <out.csv>     # walk a tree -> one CSV
  py -3.12 re/tools/ixf_parse.py <dir> --find <group>:<instance>   # resolve one key
"""
import csv
import os
import struct
import sys

MAGIC = 0x80C381D7
REC = 20
TYPE_STRING = 0x2026960B


class IxfError(Exception):
    pass


def parse(path):
    """-> (records, data). Each record is a dict; raises IxfError on a bad container."""
    with open(path, "rb") as fh:
        d = fh.read()
    if len(d) < 4:
        raise IxfError("%s: too short (%d bytes)" % (path, len(d)))
    magic, = struct.unpack_from("<I", d, 0)
    if magic != MAGIC:
        raise IxfError("%s: bad magic 0x%08X (expected 0x%08X)" % (path, magic, MAGIC))

    records, n = [], 0
    while 4 + (n + 1) * REC <= len(d):
        group, instance, rtype, off, size = struct.unpack_from("<5I", d, 4 + n * REC)
        # End of index = the KEY TRIPLE is zero (first 12 bytes), not the whole 20-byte record.
        # Confirmed from the writer in SIMBABLD.DLL (0x1204f38e) which terminates on
        # local_b4==0 && local_b0==0 && local_ac==0, i.e. group/instance/type only.
        if (group, instance, rtype) == (0, 0, 0):
            break
        if off == 0xFFFFFFFF or size == 0xFFFFFFFF:
            # Deleted/free slot. GZResourceD skips these explicitly (0x1000ca78) rather than
            # treating them as end-of-index, so the walk must continue past them.
            n += 1
            continue
        if off + size > len(d):
            raise IxfError("%s: record %d payload [%d,%d) past EOF %d"
                           % (path, n, off, off + size, len(d)))
        records.append({
            "group": group, "instance": instance, "type": rtype,
            "offset": off, "size": size,
        })
        n += 1
    return records, d


def payload_text(rec, d):
    """Decode a record payload: u32 length + bytes. Returns (text, note)."""
    off, size = rec["offset"], rec["size"]
    raw = d[off:off + size]
    if size < 4:
        return raw.decode("cp1252", "replace"), "no length prefix (size<4)"
    length, = struct.unpack_from("<I", raw, 0)
    body = raw[4:]
    note = ""
    if length != len(body):
        note = "length %d != payload %d" % (length, len(body))
    return body.decode("cp1252", "replace"), note


def iter_files(target):
    if os.path.isfile(target):
        yield target
        return
    for root, _dirs, files in os.walk(target):
        for f in sorted(files):
            if f.lower().endswith(".ixf"):
                yield os.path.join(root, f)


def cmd_list(path, dump=False):
    records, d = parse(path)
    used = sum(r["size"] for r in records)
    first_data = min((r["offset"] for r in records), default=len(d))
    slots = (first_data - 4) // REC
    print("%s: %d records, magic OK, index %d/%d slots used, payload %d bytes, file %d bytes"
          % (path, len(records), len(records), slots, used, len(d)))
    if dump:
        for r in records:
            text, note = payload_text(r, d)
            print("  %08x:%-6d %s%s" % (r["group"], r["instance"], text,
                                        ("   [" + note + "]") if note else ""))


def cmd_csv(target, out):
    rows = n_files = n_bad = 0
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "language", "group", "instance", "type", "offset", "size", "text", "note"])
        for path in iter_files(target):
            try:
                records, d = parse(path)
            except IxfError as e:
                print("SKIP %s" % e, file=sys.stderr)
                n_bad += 1
                continue
            n_files += 1
            lang = os.path.basename(os.path.dirname(path))
            for r in records:
                text, note = payload_text(r, d)
                w.writerow([os.path.basename(path), lang,
                            "0x%08x" % r["group"], r["instance"], "0x%08x" % r["type"],
                            r["offset"], r["size"], text, note])
                rows += 1
    print("%d files, %d records -> %s (%d unreadable)" % (n_files, rows, out, n_bad))


def cmd_find(target, group, instance):
    hits = 0
    for path in iter_files(target):
        try:
            records, d = parse(path)
        except IxfError:
            continue
        for r in records:
            if r["group"] == group and (instance is None or r["instance"] == instance):
                text, note = payload_text(r, d)
                print("%-52s %08x:%-6d %s%s"
                      % (os.path.relpath(path), r["group"], r["instance"], text,
                         ("   [" + note + "]") if note else ""))
                hits += 1
    if not hits:
        print("no record with group 0x%08x%s"
              % (group, "" if instance is None else " instance %d" % instance))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = argv[1]
    args = argv[2:]

    if "--csv" in args:
        return cmd_csv(target, args[args.index("--csv") + 1])
    if "--find" in args:
        spec = args[args.index("--find") + 1]
        g, _, i = spec.partition(":")
        return cmd_find(target, int(g, 0), int(i, 0) if i else None)

    dump = "--dump" in args
    if os.path.isdir(target):
        for path in iter_files(target):
            try:
                cmd_list(path, dump)
            except IxfError as e:
                print("SKIP %s" % e, file=sys.stderr)
    else:
        cmd_list(target, dump)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
