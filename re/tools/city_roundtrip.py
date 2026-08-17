#!/usr/bin/env python3
"""city_roundtrip.py - LAYERED byte-identity probe for the city-save writer.

Answers one question per layer, with the layers BELOW it held verbatim, so a failure
names exactly one layer instead of one file:

  L0 container : rebuild the .IXF (magic + index slots + payloads, payload bytes verbatim)
  L1 record    : rebuild the 24-byte payload header + the QFS stream verbatim
  L2 archive   : rebuild the decompressed body from the parsed section table, section
                 payload bytes verbatim
  L3 qfs       : recompress the body with the transcribed GZResourceD encoder
                 (qfs_encode.compress) and compare to the shipped QFS stream
  L4 whole file: sections -> body -> QFS -> 24-byte header -> record -> container, with
                 the two length fields RECOMPUTED, compared to the original file bytes

Nothing here is allowed to copy the original file through: every layer is re-emitted from
parsed structure. A layer that copies its own input is marked SKIP, not PASS.

Usage:
  py -3.12 re/tools/city_roundtrip.py <file-or-dir>
  py -3.12 re/tools/city_roundtrip.py <dir> --verbose
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_parse
import ixf_parse
import qfs_encode

MAGIC = ixf_parse.MAGIC
REC = ixf_parse.REC


# --- L0: the container ----------------------------------------------------------------

def read_index_slots(d):
    """Every 20-byte slot up to (and including) the terminator, as raw tuples.

    The writer must reproduce the index EXACTLY, including deleted slots (offset/size
    0xFFFFFFFF) and the reserved zero slots after the terminator, so they are read here as
    data rather than filtered like ixf_parse.parse does.
    """
    slots = []
    n = 0
    while 4 + (n + 1) * REC <= len(d):
        g, i, t, off, size = struct.unpack_from("<5I", d, 4 + n * REC)
        slots.append((g, i, t, off, size))
        n += 1
        if (g, i, t) == (0, 0, 0):
            break
    return slots


TYPE_STRING = 0x2026960B


def payload_extent(rtype, size):
    """On-disk byte length of a record payload, which is NOT always the index `size`.

    [CONFIRMED, 59/59] For type 0x2026960B (localized string) the index `size` is the
    STRING length and the payload is `u32 length + chars`, so it occupies `4 + size`
    bytes. Measured on 110 such records across the 13 .SNR files: in every one the u32 at
    the payload start equals `size` exactly, and `offset + 4 + size` is exactly the next
    record's offset. Reading only `size` bytes truncates the last four characters of every
    string ("Maxis" -> "M", "Blazej Stompel" -> "Blazej Stom").

    Every other type in the 59 files stores its payload at exactly `size` bytes.
    """
    return size + 4 if rtype == TYPE_STRING else size


def container_layout(d):
    """-> (slots, pad_len, payloads, free, tail_len). Measures, never assumes.

    `free` is [(offset, length)] for regions covered by neither the index nor a payload.
    One per .SNR file (20,200 bytes after the 0x23dfae5f record) and all-zero in all 59
    files, so it is container slack rather than data -- but it is emitted explicitly, so a
    writer that reuses the layout does not have to guess.
    """
    slots = read_index_slots(d)
    index_end = 4 + len(slots) * REC
    live = [s for s in slots if s[3] != 0xFFFFFFFF and s[4] != 0xFFFFFFFF and s[:3] != (0, 0, 0)]
    first_data = min((s[3] for s in live), default=len(d))
    pad_len = first_data - index_end
    payloads = [(s[3], d[s[3]:s[3] + payload_extent(s[2], s[4])]) for s in live]

    free, cursor = [], first_data
    for off, data in sorted(payloads):
        if off > cursor:
            free.append((cursor, off - cursor))
        cursor = max(cursor, off + len(data))
    return slots, pad_len, payloads, free, len(d) - cursor


def build_container(slots, pad, payloads, tail):
    """Re-emit the .IXF from structure. `payloads` is [(abs_offset, bytes)]."""
    out = bytearray()
    out += struct.pack("<I", MAGIC)
    for s in slots:
        out += struct.pack("<5I", *s)
    out += pad
    for off, data in sorted(payloads):
        if off < len(out):
            raise ValueError("payload at %d overlaps emitted %d bytes" % (off, len(out)))
        out += b"\x00" * (off - len(out))
        out += data
    out += tail
    return bytes(out)


# --- L1: the payload record (24-byte header + QFS stream) -----------------------------

def build_record_body(info, qfs_stream, plain_len=None):
    """Re-emit the 24-byte header from parsed fields + a QFS stream. [CITY_SAVE.md]

    When `plain_len` is given the two length fields are RECOMPUTED from the emitted stream
    rather than copied from the parsed header -- which is what a real writer must do, and
    what makes the L4 check meaningful:
        clen == len(record) - 20 == len(stream) + 4,  and clen is stored twice.
    """
    clen = len(qfs_stream) + 4 if plain_len is not None else info["clen"]
    ulen = plain_len if plain_len is not None else info["ulen"]
    return (struct.pack("<2I", info["a"], info["b"])
            + info["version"].encode("ascii")
            + struct.pack("<3I", clen, ulen, clen)
            + qfs_stream)


# --- L2: the section archive ----------------------------------------------------------

def build_body(ents, body):
    """Re-emit the decompressed body from the section table; section bytes verbatim.

    Layout [CITY_SAVE.md, CONFIRMED 59/59]:
      u32 sectionCount ; u32 sectionTableOffset ; payloads from offset 8 ; table at the end.
    The table is emitted in the ORIGINAL entry order (not sorted) because that order is
    itself file data; payloads are emitted in offset order.
    """
    count = len(ents)
    table_off = max((e["abs"] + e["size"] for e in ents), default=8)
    out = bytearray(struct.pack("<2I", count, table_off))
    for e in sorted(ents, key=lambda x: x["abs"]):
        if e["abs"] < len(out):
            raise ValueError("section at %d overlaps emitted %d" % (e["abs"], len(out)))
        out += b"\x00" * (e["abs"] - len(out))
        out += body[e["abs"]:e["abs"] + e["size"]]
    if len(out) != table_off:
        raise ValueError("payload region ends at %d, table says %d" % (len(out), table_off))
    for e in ents:
        out += struct.pack("<4I", e["type"], e["group"], e["instance"], e["offset"])
    return bytes(out)


# --- driver ---------------------------------------------------------------------------

def first_diff(a, b):
    if a == b:
        return None
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i
    return min(len(a), len(b))


def check(path, verbose=False):
    """-> dict of per-layer verdicts for one file."""
    r = {"file": os.path.basename(path), "L0": "?", "L1": "?", "L2": "?", "L3": "?", "L4": "?"}
    with open(path, "rb") as fh:
        d = fh.read()

    # L0
    try:
        slots, pad_len, payloads, free, tail_len = container_layout(d)
        index_end = 4 + len(slots) * REC
        pad = d[index_end:index_end + pad_len]
        tail = d[len(d) - tail_len:] if tail_len else b""
        nonzero = [(o, n) for o, n in free if any(d[o:o + n])]
        if nonzero:
            raise ValueError("free region carries data: %r" % nonzero[:3])
        rebuilt = build_container(slots, pad, payloads, tail)
        off = first_diff(rebuilt, d)
        r["L0"] = "PASS" if off is None else "FAIL @%d (len %d vs %d)" % (off, len(rebuilt), len(d))
        r["slots"] = len(slots)
        r["pad"] = pad_len
        r["free"] = sum(n for _o, n in free)
        r["tail"] = tail_len
    except Exception as e:                                        # noqa: BLE001
        r["L0"] = "ERROR %s: %s" % (type(e).__name__, e)
        return r

    # find the compressed payload
    recs, _ = ixf_parse.parse(path)
    target = None
    for rec in recs:
        body = d[rec["offset"]:rec["offset"] + rec["size"]]
        if city_parse.is_compressed_payload(body):
            target = (rec, body)
            break
    if target is None:
        r["L1"] = r["L2"] = r["L3"] = r["L4"] = "no compressed payload"
        return r
    rec, rbody = target

    try:
        plain, info = city_parse.parse_payload(rbody)
    except Exception as e:                                        # noqa: BLE001
        r["L1"] = r["L2"] = r["L3"] = r["L4"] = "ERROR %s: %s" % (type(e).__name__, e)
        return r

    # L1 -- header rebuilt from fields, stream verbatim
    stream = rbody[city_parse.HDR:]
    rebuilt = build_record_body(info, stream)
    off = first_diff(rebuilt, rbody)
    r["L1"] = "PASS" if off is None else "FAIL @%d" % off

    # L2 -- body rebuilt from the section table
    try:
        _sinfo, ents = city_parse.parse_sections(plain)
        rebuilt = build_body(ents, plain)
        off = first_diff(rebuilt, plain)
        r["L2"] = "PASS" if off is None else "FAIL @%d (len %d vs %d)" % (off, len(rebuilt), len(plain))
        r["sections"] = len(ents)
        r["body"] = len(plain)
    except Exception as e:                                        # noqa: BLE001
        r["L2"] = "ERROR %s: %s" % (type(e).__name__, e)

    # L3 -- the QFS stream, re-encoded by the transcribed compressor
    try:
        restream = qfs_encode.compress_stream(plain)
        off = first_diff(restream, stream)
        r["L3"] = "PASS" if off is None else "FAIL @%d (%d vs %d bytes)" % (off, len(restream), len(stream))
    except Exception as e:                                        # noqa: BLE001
        r["L3"] = "ERROR %s: %s" % (type(e).__name__, e)
        restream = None

    # L4 -- the WHOLE file, rebuilt from parsed structure with nothing copied through:
    # sections -> body -> QFS -> 24-byte header -> record -> container.
    if restream is not None and r["L2"] == "PASS":
        try:
            rebody = build_body(ents, plain)
            rerec = build_record_body(info, qfs_encode.compress_stream(rebody), len(rebody))
            payloads2 = [(o, rerec if o == rec["offset"] else b) for o, b in payloads]
            rebuilt = build_container(slots, pad, payloads2, tail)
            off = first_diff(rebuilt, d)
            r["L4"] = "PASS" if off is None else "FAIL @%d (%d vs %d bytes)" % (off, len(rebuilt), len(d))
        except Exception as e:                                    # noqa: BLE001
            r["L4"] = "ERROR %s: %s" % (type(e).__name__, e)

    if verbose:
        print("  %s: %d slots, %d pad, %d tail, %d sections, body %d"
              % (r["file"], r.get("slots", 0), r.get("pad", 0), r.get("tail", 0),
                 r.get("sections", 0), r.get("body", 0)))
    return r


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = argv[1]
    verbose = "--verbose" in argv
    rows = [check(p, verbose) for p in city_parse.walk(target)]
    if not rows:
        print("no city-family files under %s" % target)
        return 2

    # Never truncate a verdict: a clipped "FAIL @941" reads as "FAIL @94" and sends you
    # looking at the wrong offset. Only the file name is allowed to clip.
    print("%-30s %-14s %-10s %-14s %-14s %-14s"
          % ("file", "L0 container", "L1 rec", "L2 archive", "L3 qfs", "L4 whole file"))
    for r in rows:
        print("%-30s %-14s %-10s %-14s %-14s %-14s"
              % (r["file"][:30], r["L0"], r["L1"], r["L2"], r["L3"], r["L4"]))

    bad = 0
    print()
    for layer in ("L0", "L1", "L2", "L3", "L4"):
        ok = sum(1 for r in rows if r[layer] == "PASS")
        bad += len(rows) - ok
        print("%s  %d/%d byte-identical" % (layer, ok, len(rows)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
