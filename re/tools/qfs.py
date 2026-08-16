#!/usr/bin/env python3
"""qfs.py - QFS/RefPack decompressor for SimCity 3000 Unlimited sprite pixel data.

Transcribed byte-for-byte from the shipped decompressor, NOT from public RefPack docs:
  sc3_qfs_get_uncompressed_size  SIMSPR.DLL 0x10050cdf  [CONFIRMED]
  sc3_qfs_decompress             SIMSPR.DLL 0x10050d09  (441 bytes)  [CONFIRMED]
See re/analysis/formats/QFS.md. The four control forms below cite the exact decomp lines.

HEADER  [CONFIRMED @0x10050d09 lines 21-26]
    if (byte0 & 1) header is 5 bytes else 2 bytes
    then 3 bytes BIG-endian = uncompressed size
  (0x10050cdf tests `u16be == 0x10FB` instead; both agree, since 0x10 & 1 == 0.)

CONTROL FORMS  [CONFIRMED @0x10050d09]
  NOTE the copy loops are `do { ... } while (n-- != 0)`, which runs n+1 times. Every
  back-reference length below is therefore ONE MORE than the naive read of the source,
  and every offset is +1 because the source pointer is `out + (-X) - 1`.

  b0 & 0x80 == 0            2 bytes  lit = b0 & 3
    (lines 31-53)                    off = ((b0 & 0x60) << 3) + b1 + 1
                                     len = ((b0 >> 2) & 7) + 3
  b0 & 0xC0 == 0x80         3 bytes  lit = b1 >> 6
    (lines 56-72)                    off = ((b1 & 0x3F) << 8) + b2 + 1
                                     len = (b0 & 0x3F) + 4
  b0 & 0xE0 == 0xC0         4 bytes  lit = b0 & 3
    (lines 75-97)                    off = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
                                     len = ((b0 & 0x0C) << 6) + b3 + 5
  b0 >= 0xE0                1 byte   n = (b0 & 0x1F) * 4 + 4
    (lines 99-116)                   n <= 0x70 -> literal run of n, continue
                                     n >  0x70 -> TERMINATOR, copy (b0 & 3) literals, stop

Back-references copy byte-by-byte from the output already written; overlapping copies are
legal and intentional (len > off repeats a run).

SPRITE RECORD  [CONFIRMED @0x1001de49, and against shipped bytes]
    +0x00 dword0   (dword0 >> 8) & 0xFF = FORMAT CODE; dword0 & 0xFF -> pixel decoder arg
    +0x04 dword1   flags; also the pixel-format selector at 0x1001e086
    +0x08 dword2
    +0x0c dword3
    +0x10 dword4   length of the stream that follows
    +0x14 stream   QFS (magic 0x10FB) when format code == 1

    format 0                                    -> raw,  FUN_1001e086 dispatcher
    format 1 && (dword1 & 0x8000)==0
             && (dword1 & 0x80000)!=0           -> QFS,  FUN_1001ddb8

Usage:
  py -3.12 re/tools/qfs.py <file.DAT>                  # decode + validate every type-0 record
  py -3.12 re/tools/qfs.py <dir>                       # walk a tree of .DAT archives
  py -3.12 re/tools/qfs.py <file.DAT> --record <n>     # one record, verbose + hex head
  py -3.12 re/tools/qfs.py <dir> --extract <outdir>    # write decompressed streams to disk
  py -3.12 re/tools/qfs.py <dir> --csv <out.csv>       # per-record table for analysis
"""
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ixf_parse

QFS_MAGIC = 0x10FB
HDR_SIZE = 0x14          # dword0..dword4, then the stream
TYPE_PIXELS = 0
TYPE_ANCHOR = 1


class QfsError(Exception):
    pass


def uncompressed_size(buf, pos=0):
    """Declared output size. Transcribed from sc3_qfs_get_uncompressed_size 0x10050cdf."""
    if pos + 5 > len(buf):
        raise QfsError("stream too short for a header")
    p = pos + (5 if buf[pos] & 1 else 2)
    if p + 3 > len(buf):
        raise QfsError("stream too short for the size field")
    return (buf[p] << 16) | (buf[p + 1] << 8) | buf[p + 2]


def decompress(buf, pos=0, limit=None):
    """-> (out, consumed, declared_size). Transcribed from sc3_qfs_decompress 0x10050d09."""
    start = pos
    end = len(buf) if limit is None else min(len(buf), start + limit)
    p = pos + (5 if buf[pos] & 1 else 2)
    declared = (buf[p] << 16) | (buf[p + 1] << 8) | buf[p + 2]
    p += 3

    out = bytearray()

    def literals(n, p):
        if p + n > end:
            raise QfsError("literal run of %d overruns the stream at +%d" % (n, p - start))
        out.extend(buf[p:p + n])
        return p + n

    def backref(off, ln):
        # Byte-by-byte on purpose: off < ln is legal and repeats the tail.
        if off > len(out):
            raise QfsError("back-reference offset %d exceeds %d bytes of output" % (off, len(out)))
        src = len(out) - off
        for _ in range(ln):
            out.append(out[src])
            src += 1

    while True:
        if p >= end:
            raise QfsError("stream ended without a terminator control byte")
        b0 = buf[p]

        if b0 & 0x80 == 0:                                    # 2-byte form
            b1 = buf[p + 1]
            p = literals(b0 & 3, p + 2)
            backref(((b0 & 0x60) << 3) + b1 + 1, ((b0 >> 2) & 7) + 3)

        elif b0 & 0x40 == 0:                                  # 3-byte form
            b1, b2 = buf[p + 1], buf[p + 2]
            p = literals(b1 >> 6, p + 3)
            backref(((b1 & 0x3F) << 8) + b2 + 1, (b0 & 0x3F) + 4)

        elif b0 & 0x20 == 0:                                  # 4-byte form
            b1, b2, b3 = buf[p + 1], buf[p + 2], buf[p + 3]
            p = literals(b0 & 3, p + 4)
            backref(((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1, ((b0 & 0x0C) << 6) + b3 + 5)

        else:                                                 # literal run / terminator
            n = (b0 & 0x1F) * 4 + 4
            if n > 0x70:
                p = literals(b0 & 3, p + 1)
                break
            p = literals(n, p + 1)

    return bytes(out), p - start, declared


# --- sprite records -------------------------------------------------------------------

def record_header(payload):
    """-> dict of the 5 header dwords + the derived format code."""
    if len(payload) < HDR_SIZE:
        raise QfsError("payload %d bytes, shorter than the 0x14-byte header" % len(payload))
    d0, d1, d2, d3, d4 = struct.unpack_from("<5I", payload, 0)
    return {"d0": d0, "d1": d1, "d2": d2, "d3": d3, "d4": d4,
            "format": (d0 >> 8) & 0xFF, "fmt_arg": d0 & 0xFF}


def qfs_stream_start(h):
    """-> byte offset of the QFS stream in the payload, or None if this record is not QFS.

    TWO paths reach FUN_1001ddb8 (the decompressor), and they differ in where the stream
    begins. Both are [CONFIRMED]; the second was found empirically (1,139 shipped records)
    and then traced back through the call graph.

    BOTH callers pass `payload + 0x10`, and the wrapper FUN_1001ddb8 adds 4 before
    calling the decompressor:  FUN_10050d09((byte *)(param_1 + 4), ...)
    [CONFIRMED @0x1001ddb8:17], mirrored by FUN_1001de0c -> FUN_10050cdf(param_1 + 4)
    [CONFIRMED @0x1001de0c:16]. So the stream is at payload + 0x14 in EVERY case, and
    the dword at +0x10 is a length field the wrapper skips.

    (A guess that path (b) started at +0x10 was tested against the shipped archives and
    FALSIFIED: 00000010_Smoke.DAT rec 25 gives magic 0x4E05, not 0x10FB.)

    (a) 0x1001de49 line 60: format code == 1 && (d1 & 0x8000)==0 && (d1 & 0x80000)!=0
        -> FUN_1001ddb8 directly.
        The decompressed block is self-describing (its own size, w, h, a row table).

    (b) 0x1001de49 line 58: format code == 0 -> FUN_1001e086(payload + 0x10, ..., d1),
        and at 0x1001e086 the case (d1 & 0x10000000)!=0 && (d1 & 0x8000)==0
        && (d1 & 0x80000)!=0 -> FUN_1001e869 -> FUN_1001ddb8 on the same pointer.
        0x1001e869 then memcpy's the result row by row (height = vt+0x3c rows of
        vt+0x38 bytes, into a surface of stride vt+0x1ac) [CONFIRMED @0x1001e869:56-60],
        so THIS output is a plain row-major bitmap with no inner header.
    """
    if h["format"] == 1 and (h["d1"] & 0x8000) == 0 and (h["d1"] & 0x80000) != 0:
        return 0x14
    if (h["format"] == 0 and (h["d1"] & 0x10000000) != 0
            and (h["d1"] & 0x8000) == 0 and (h["d1"] & 0x80000) != 0):
        return 0x14
    return None


def decode_record(payload):
    """-> (kind, data|None, info). kind in {'qfs','raw','error'}."""
    h = record_header(payload)
    info = dict(h)
    start = qfs_stream_start(h)
    info["stream_at"] = start
    if start is None:
        info["note"] = "format %d, d1 0x%08x (neither QFS branch)" % (h["format"], h["d1"])
        return ("raw", None, info)
    stream = payload[start:]
    if len(stream) < 2:
        info["note"] = "no stream after the header"
        return ("error", None, info)
    magic = (stream[0] << 8) | stream[1]
    info["magic"] = magic
    if magic != QFS_MAGIC:
        info["note"] = "magic 0x%04X, expected 0x%04X" % (magic, QFS_MAGIC)
        return ("error", None, info)
    out, consumed, declared = decompress(stream)
    info["declared"] = declared
    info["actual"] = len(out)
    info["consumed"] = consumed
    info["stream_len"] = len(stream)
    info["d4_matches_stream"] = (h["d4"] == len(stream))
    if len(out) != declared:
        info["note"] = "SIZE MISMATCH: declared %d, produced %d" % (declared, len(out))
        return ("error", out, info)
    info["note"] = ""
    return ("qfs", out, info)


def archives(target):
    if os.path.isfile(target):
        yield target
        return
    for root, _dirs, files in os.walk(target):
        for f in sorted(files):
            if f.lower().endswith((".dat", ".ixf")):
                yield os.path.join(root, f)


def scan(target, extract=None, csv_out=None, verbose_record=None):
    tot = {"files": 0, "recs": 0, "type0": 0, "type1": 0, "qfs": 0, "raw": 0,
           "err": 0, "bytes_in": 0, "bytes_out": 0}
    failures = []
    writer = fh_csv = None
    if csv_out:
        fh_csv = open(csv_out, "w", newline="", encoding="utf-8")
        writer = csv.writer(fh_csv)
        writer.writerow(["file", "idx", "group", "instance", "type", "size",
                         "d0", "d1", "d2", "d3", "d4", "format", "stream_at",
                         "declared", "actual", "consumed", "status", "note"])

    for path in archives(target):
        try:
            records, d = ixf_parse.parse(path)
        except ixf_parse.IxfError as e:
            print("SKIP %s" % e, file=sys.stderr)
            continue
        tot["files"] += 1
        f_ok = f_err = 0
        for idx, r in enumerate(records):
            tot["recs"] += 1
            if r["type"] == TYPE_ANCHOR:
                tot["type1"] += 1
                continue
            if r["type"] != TYPE_PIXELS:
                continue
            tot["type0"] += 1
            if verbose_record is not None and idx != verbose_record:
                continue
            payload = d[r["offset"]:r["offset"] + r["size"]]
            try:
                kind, out, info = decode_record(payload)
            except QfsError as e:
                kind, out, info = "error", None, dict(record_header(payload) if r["size"] >= HDR_SIZE else {}, note=str(e))
            except Exception as e:                              # noqa: BLE001 - report, never mask
                kind, out, info = "error", None, {"note": "%s: %s" % (type(e).__name__, e)}

            if kind == "qfs":
                tot["qfs"] += 1
                f_ok += 1
                tot["bytes_in"] += r["size"]
                tot["bytes_out"] += len(out)
            elif kind == "raw":
                tot["raw"] += 1
            else:
                tot["err"] += 1
                f_err += 1
                if len(failures) < 20:
                    failures.append("%s rec %d (grp %08x inst %08x): %s"
                                    % (os.path.basename(path), idx, r["group"], r["instance"],
                                       info.get("note", "?")))

            if writer:
                writer.writerow([os.path.basename(path), idx,
                                 "0x%08x" % r["group"], "0x%08x" % r["instance"],
                                 r["type"], r["size"],
                                 "0x%08x" % info.get("d0", 0), "0x%08x" % info.get("d1", 0),
                                 info.get("d2", ""), info.get("d3", ""), info.get("d4", ""),
                                 info.get("format", ""), info.get("stream_at", ""),
                                 info.get("declared", ""), info.get("actual", ""),
                                 info.get("consumed", ""), kind, info.get("note", "")])

            if extract and out is not None:
                sub = os.path.join(extract, os.path.splitext(os.path.basename(path))[0])
                os.makedirs(sub, exist_ok=True)
                name = "%08x_%08x_%05d.bin" % (r["group"], r["instance"], idx)
                with open(os.path.join(sub, name), "wb") as fh:
                    fh.write(out)

            if verbose_record is not None:
                print("%s record %d" % (path, idx))
                print("  key      group=0x%08x instance=0x%08x type=%d size=%d"
                      % (r["group"], r["instance"], r["type"], r["size"]))
                for k in ("d0", "d1", "d2", "d3", "d4"):
                    if k in info:
                        print("  %-8s 0x%08x  (%d)" % (k, info[k], info[k]))
                print("  format   %s   fmt_arg 0x%02x" % (info.get("format"), info.get("fmt_arg", 0)))
                print("  status   %s  %s" % (kind, info.get("note", "")))
                if out is not None:
                    print("  declared %s  actual %d  consumed %s of %s stream bytes"
                          % (info.get("declared"), len(out), info.get("consumed"), info.get("stream_len")))
                    print("  head     %s" % out[:64].hex(" "))

        if verbose_record is None:
            print("%-58s %5d type-0  %5d ok  %4d fail"
                  % (os.path.relpath(path), f_ok + f_err, f_ok, f_err))

    if fh_csv:
        fh_csv.close()
        print("\n-> %s" % csv_out)

    if verbose_record is None:
        print("\n%d archives, %d index records: %d type-0, %d type-1"
              % (tot["files"], tot["recs"], tot["type0"], tot["type1"]))
        print("type-0: %d QFS decoded, %d non-QFS format, %d FAILED"
              % (tot["qfs"], tot["raw"], tot["err"]))
        if tot["bytes_in"]:
            print("%s compressed -> %s decompressed (%.2fx)"
                  % ("{:,}".format(tot["bytes_in"]), "{:,}".format(tot["bytes_out"]),
                     tot["bytes_out"] / tot["bytes_in"]))
        if failures:
            print("\nfirst failures:")
            for f in failures:
                print("  " + f)
    return 1 if tot["err"] else 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target, args = argv[1], argv[2:]
    extract = args[args.index("--extract") + 1] if "--extract" in args else None
    csv_out = args[args.index("--csv") + 1] if "--csv" in args else None
    rec = int(args[args.index("--record") + 1], 0) if "--record" in args else None
    if extract:
        os.makedirs(extract, exist_ok=True)
    return scan(target, extract, csv_out, rec)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
