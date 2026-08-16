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

Usage:
  py -3.12 re/tools/syspak_parse.py <SYS.PAK>            # list files + validation
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

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
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
