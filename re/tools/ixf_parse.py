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


# --- WRITE SIDE -----------------------------------------------------------------------
#
# Promoted here 2026-08-17 (roadmap gate T2). This code proved itself inside
# re/tools/city_roundtrip.py, a TEST HARNESS, which meant the only .IXF writer in the project
# was not usable as a library. It is the same implementation, moved and documented; the
# harness now calls it rather than carrying its own copy.
#
# Everything below exists to reproduce a shipped container BYTE FOR BYTE, which is a stricter
# bar than "the game accepts it" and is the only bar testable offline.

TYPE_STRING_PAYLOAD = 0x2026960B


def payload_extent(rtype, size):
    """On-disk byte length of a record payload, which is NOT always the index `size`.

    [CONFIRMED, 59/59 city files] For type 0x2026960B (localized string) the index `size` is the
    STRING length and the payload is `u32 length + chars`, so it occupies `4 + size` bytes.
    Measured on 110 such records: the u32 at the payload start equals `size` in every one, and
    `offset + 4 + size` is exactly the next record's offset. Reading only `size` truncates the
    last four characters of every string ("Maxis" -> "M").

    Every other type observed stores exactly `size` bytes.
    """
    return size + 4 if rtype == TYPE_STRING_PAYLOAD else size


def read_index_slots(d):
    """Every 20-byte index slot up to AND INCLUDING the terminator, as raw 5-tuples.

    `parse()` filters deleted slots and stops at the terminator, which is right for reading.
    A writer must reproduce the index exactly -- deleted slots (offset/size 0xFFFFFFFF) and all
    -- so this returns them untouched.
    """
    slots, n = [], 0
    while 4 + (n + 1) * REC <= len(d):
        slot = struct.unpack_from("<5I", d, 4 + n * REC)
        slots.append(slot)
        n += 1
        if slot[:3] == (0, 0, 0):
            break
    return slots


def layout(d):
    """Describe a container completely enough to rebuild it: -> dict.

    Keys: `slots` (raw index slots), `pad` (reserved bytes between the index and the first
    payload), `payloads` [(offset, bytes)], `free` [(offset, length)] for regions covered by
    neither index nor payload, and `tail` (bytes after the last payload).

    `free` and `tail` are not padding to be assumed away. In the shipped corpus the free regions
    are all-zero container slack, but **7 of the 13 `.SNR` files carry 51-63,586 bytes of
    non-zero data past the last indexed payload** that no slot points at (`U-039`). A writer that
    drops it produces a file the game would probably still read, but not the same file.
    """
    slots = read_index_slots(d)
    index_end = 4 + len(slots) * REC
    live = [s for s in slots
            if s[3] != 0xFFFFFFFF and s[4] != 0xFFFFFFFF and s[:3] != (0, 0, 0)]
    first_data = min((s[3] for s in live), default=len(d))
    payloads = [(s[3], d[s[3]:s[3] + payload_extent(s[2], s[4])]) for s in live]

    free, cursor = [], first_data
    for off, data in sorted(payloads):
        if off > cursor:
            free.append((cursor, off - cursor))
        cursor = max(cursor, off + len(data))
    return {"slots": slots,
            "pad": d[index_end:first_data],
            "payloads": payloads,
            "free": free,
            "tail": d[cursor:]}


def build(lay):
    """Rebuild a container from a `layout()` dict -> bytes.

    Payloads are written at their recorded absolute offsets; any gap is zero-filled, which is
    correct for the shipped corpus (every `free` region there is all-zero) and is why `layout()`
    reports `free` separately -- so a caller can check rather than trust.
    """
    out = bytearray(struct.pack("<I", MAGIC))
    for s in lay["slots"]:
        out += struct.pack("<5I", *s)
    out += lay["pad"]
    for off, data in sorted(lay["payloads"]):
        if off < len(out):
            raise IxfError("payload at %d overlaps %d bytes already emitted" % (off, len(out)))
        out += b"\x00" * (off - len(out))
        out += data
    out += lay["tail"]
    return bytes(out)


def roundtrip(path):
    """-> (ok, detail). Read a container, rebuild it from structure, compare byte for byte."""
    with open(path, "rb") as fh:
        d = fh.read()
    if len(d) < 4 or struct.unpack_from("<I", d, 0)[0] != MAGIC:
        return None, "not an .IXF container"
    try:
        lay = layout(d)
        rebuilt = build(lay)
    except (IxfError, struct.error) as e:
        return False, "%s: %s" % (type(e).__name__, e)
    if rebuilt == d:
        return True, "%d slots, %d payloads, %d free region(s), %d tail bytes" % (
            len(lay["slots"]), len(lay["payloads"]), len(lay["free"]), len(lay["tail"]))
    for i in range(min(len(rebuilt), len(d))):
        if rebuilt[i] != d[i]:
            return False, "first difference at byte %d (rebuilt %d bytes, original %d)" % (
                i, len(rebuilt), len(d))
    return False, "length differs: rebuilt %d, original %d" % (len(rebuilt), len(d))


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
