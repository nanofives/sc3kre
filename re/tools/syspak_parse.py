#!/usr/bin/env python3
"""syspak_parse.py — parse/extract SimCity 3000 Unlimited SYS.PAK config archive.

FORMAT (CONFIRMED against Apps/Sys/SYS.PAK, 51 entries; round-trip validated to EOF).
Mirrors the style of re/tools/fez_extract.py. Uncompressed, plain ASCII.

  SYS.PAK
    TOC (from 0x0, no magic/count):
       51 × [u32 A_i][u32 nameLen][name bytes]            ; A_i is the record-offset table:
                                                              A_0 = 51 (== file count, [UNCERTAIN] role)
                                                              A_i (i>=1) = ABS start of record[i-1]
    @toc_end: [u32 A_51]                                   ; ABS start of record[50] (last), tail of A[]
    @toc_end+4 = A_1: 51 records, contiguous, SAME ORDER as TOC:
       record = [u32 lineCount][ lineCount × ([u32 lineLen][line ASCII]) ]
       => record[i] spans [A_{i+1}, A_{i+2}); record[50] spans [A_51, EOF)

  A "line" is one ini physical line without its trailing newline. Section headers "[X]"
  are their own line. Canonical parse walks records sequentially by lineCount, pairing with
  TOC names in order; the A[] offset table is redundant but validated (record[i].start==A[i+1]).

READ AND WRITE. `build()` rebuilds an archive from names + line lists, `replace_member()` swaps
one member's text, and `roundtrip()` checks a rebuild against the original byte for byte.

  py -3.12 re/tools/syspak_parse.py Apps/Sys/SYS.PAK --selftest
  SYS.PAK round-trip: byte-identical  (51 members, 272507 bytes)

WHY A WRITER EXISTS: the archive WINS over loose files. `FUN_004872e8` checks SYS.PAK exists,
opens it read-only, scans its directory for the member name, and falls back to a loose file only
when the archive is missing or lacks that entry [CONFIRMED @0x004872e8]. So modding a tunable
that already ships inside SYS.PAK means rewriting SYS.PAK.

Usage:
  py -3.12 re/tools/syspak_parse.py <SYS.PAK>            # list files + validation
  py -3.12 re/tools/syspak_parse.py <SYS.PAK> --selftest # rebuild and byte-compare
  py -3.12 re/tools/syspak_parse.py <SYS.PAK> <outdir>   # extract reconstructed .ini files
"""
import sys, os, struct

def u32(b, o): return struct.unpack_from('<I', b, o)[0]

def parse_toc(data):
    """Return (names, offsets, toc_end). TOC = 51× [u32 offset][u32 nameLen][name]."""
    names, offs, off = [], [], 0
    while off + 8 <= len(data):
        offset = u32(data, off); nl = u32(data, off + 4)
        if nl == 0 or nl > 128:
            break
        name = data[off + 8:off + 8 + nl]
        if not all(32 <= c < 127 for c in name):
            break
        names.append(name.decode('latin1')); offs.append(offset); off += 8 + nl
    return names, offs, off

def parse_records(data, toc_end, count):
    """Walk `count` line-framed records from the content region. Returns list of
    record dicts: {start, end, lines:[str,...]}. Order matches the TOC.
    The u32 at toc_end is A_51 = absolute start of the last record (not a length)."""
    a51 = u32(data, toc_end)     # == start of record[count-1]
    c0 = toc_end + 4             # == A_1 == start of record[0]
    off = c0; recs = []
    for _ in range(count):
        start = off
        lc = u32(data, off); off += 4
        lines = []
        for _ in range(lc):
            ln = u32(data, off); off += 4
            lines.append(data[off:off + ln].decode('latin1')); off += ln
        recs.append({'start': start, 'end': off, 'lines': lines})
    assert off == len(data), (
        f"record walk ended at 0x{off:x}; expected EOF 0x{len(data):x}")
    assert recs[-1]['start'] == a51, (
        f"last record start 0x{recs[-1]['start']:x} != A_51 0x{a51:x}")
    return recs

def parse(data):
    names, offs, toc_end = parse_toc(data)
    recs = parse_records(data, toc_end, len(names))
    return names, offs, toc_end, recs

def to_ini_text(lines):
    return '\n'.join(lines) + ('\n' if lines else '')

# --- WRITE SIDE ------------------------------------------------------------------------
#
# Added 2026-08-17 (roadmap gate T3, route A). Needed because the archive WINS over loose
# files: FUN_004872e8 checks SYS.PAK exists, opens it read-only, scans its directory for the
# member name, and only falls back to a loose file when the archive is missing or has no such
# entry [CONFIRMED @0x004872e8]. So changing a tunable that already lives in SYS.PAK means
# rewriting SYS.PAK.
#
# The bar is the one every other format in this project met: rebuild the shipped archive BYTE
# FOR BYTE, checked by --selftest, before anyone trusts it with a modified member.

def build(names, records):
    """Rebuild a SYS.PAK from `names` and `records` -> bytes.

    `records` is a list of line lists (the `lines` value from parse_records), one per name,
    in the same order as `names`.

    THE OFFSET TABLE IS SHIFTED BY ONE, which is the only subtle part of the format
    `[CONFIRMED against the shipped archive, 51/51 entries]`:

        entry[0].u32 = the member COUNT (51), not an offset
        entry[i].u32 = ABS start of record[i-1]      for i >= 1
        u32 at toc_end = ABS start of record[LAST]   -- the tail of the same table

    So the table holds N+1 numbers for N records, with the count occupying slot 0. Emitting
    `entry[i] = start[i]` instead of `start[i-1]` produces a file that looks structurally
    plausible and is wrong in every entry.
    """
    if len(names) != len(records):
        raise ValueError("%d names but %d records" % (len(names), len(records)))

    blobs = []
    for lines in records:
        b = bytearray(struct.pack('<I', len(lines)))
        for ln in lines:
            raw = ln.encode('latin1')
            b += struct.pack('<I', len(raw)) + raw
        blobs.append(bytes(b))

    toc_end = sum(8 + len(n.encode('latin1')) for n in names)
    starts, pos = [], toc_end + 4
    for b in blobs:
        starts.append(pos)
        pos += len(b)

    out = bytearray()
    for i, n in enumerate(names):
        raw = n.encode('latin1')
        out += struct.pack('<II', len(names) if i == 0 else starts[i - 1], len(raw)) + raw
    out += struct.pack('<I', starts[-1])
    for b in blobs:
        out += b
    return bytes(out)


def roundtrip(path):
    """-> (ok, detail). Parse a SYS.PAK, rebuild it from structure, compare byte for byte."""
    data = open(path, 'rb').read()
    try:
        names, offs, toc_end, recs = parse(data)
        rebuilt = build(names, [r['lines'] for r in recs])
    except Exception as e:                                        # noqa: BLE001 - report it
        return False, '%s: %s' % (type(e).__name__, e)
    if rebuilt == data:
        return True, '%d members, %d bytes' % (len(names), len(data))
    for i in range(min(len(rebuilt), len(data))):
        if rebuilt[i] != data[i]:
            return False, 'first difference at byte %d (rebuilt %d, original %d)' % (
                i, len(rebuilt), len(data))
    return False, 'length differs: rebuilt %d, original %d' % (len(rebuilt), len(data))


def replace_member(data, name, text):
    """-> bytes: the archive with one member's text replaced. Case-insensitive on the name.

    `text` is the whole file as a string; it is split on newlines into the line-framed form
    the archive stores. Trailing empty lines are dropped, because the shipped records carry
    no terminator line and adding one changes the record's line count.
    """
    names, offs, toc_end, recs = parse(data)
    lines = [r['lines'] for r in recs]
    hit = [i for i, n in enumerate(names) if n.lower() == name.lower()]
    if not hit:
        raise KeyError('%s is not in this archive (%d members)' % (name, len(names)))
    new = text.replace('\r\n', '\n').split('\n')
    while new and new[-1] == '':
        new.pop()
    lines[hit[0]] = new
    return build(names, lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    if '--selftest' in sys.argv:
        ok, detail = roundtrip(sys.argv[1])
        print('SYS.PAK round-trip: %s  (%s)' % ('byte-identical' if ok else 'FAILED', detail))
        return 0 if ok else 1
    data = open(sys.argv[1], 'rb').read()
    names, offs, toc_end, recs = parse(data)
    print(f"SYS.PAK: {len(names)} files, TOC 0x0..0x{toc_end:x}, "
          f"content 0x{toc_end+4:x}..0x{len(data):x} (validated, round-trips to EOF)")
    if len(sys.argv) >= 3:
        out = sys.argv[2]; n = 0
        for nm, r in zip(names, recs):
            dst = os.path.join(out, nm)
            os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
            open(dst, 'w', encoding='latin1', newline='\n').write(to_ini_text(r['lines']))
            n += 1
        print(f"extracted {n} files -> {out}")
    else:
        for nm, r in zip(names, recs):
            size = r['end'] - r['start']
            print(f"  {size:8d}B  {len(r['lines']):4d} lines  {nm}")

if __name__ == '__main__':
    main()
