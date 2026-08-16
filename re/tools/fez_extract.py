#!/usr/bin/env python3
"""fez_extract.py — parse/extract the iOS 'FEZC' container (SimCity Deluxe data.fez).

FORMAT (confirmed against data.fez, 4949 entries, extraction validated on raw PNG/CAF):
  Header (LE):
    0x00  "FEZC"
    0x04  u32 version (0x00010000)
    0x08  u32 fileCount
    0x0C  u32 pathTableOffset   (= 0x28)
    0x10  u32 metaTableOffset   (= end of path table)
    0x14  u32 dataStartOffset
    0x18  16-byte archive hash/guid
  Path table @ pathTableOffset: fileCount * [u32 len][len bytes incl trailing NUL]
  Meta table @ metaTableOffset: fileCount * 32-byte records, SAME order as path table:
    +0x00  u32  field0 (per-entry; NOT the size — role [UNCERTAIN], see notes)
    +0x04  u32  dataOffset (absolute; entries tile the data region contiguously)
    +0x08  16   per-entry hash
  File size = next entry's dataOffset - this dataOffset (last = EOF - dataOffset).

  Payloads: raw for already-compressed formats (PNG 89504e47, CAF/RIFF 52494646);
  other entries (.gvf/.spr/.vpt/.vis/.pvr/.trb …) are a single zlib stream (78 da). Inflate
  with zlib.decompressobj().decompress(blob) — NOT zlib.decompress() (which is intolerant and
  raises -5/-3 on these). Verified: 4321/4321 zlib entries inflate cleanly, 628 stored raw.
  Decompressed .gvf files carry magic "FE_GVF_BIN_0001" (FusionEngine keyed string/data table;
  keys like QI_LABEL_TRAFFIC / QI_CRIME_HIGH / LC_CITY_SIZE_HISTORY).

Usage:  py -3.12 re/tools/fez_extract.py <data.fez> [outdir] [--inflate]
"""
import sys, os, struct, zlib

def u32(b, o): return struct.unpack_from('<I', b, o)[0]

def maybe_inflate(blob):
    """Return (bytes, inflated?). Single zlib stream via decompressobj; else raw."""
    if blob[:2] == b'\x78\xda':
        try:
            return zlib.decompressobj().decompress(blob), True
        except Exception:
            return blob, False
    return blob, False

def parse(data):
    assert data[:4] == b'FEZC', "not a FEZC file"
    count = u32(data, 8); paths = u32(data, 0x0c); meta = u32(data, 0x10); dstart = u32(data, 0x14)
    off = paths; names = []
    for _ in range(count):
        ln = u32(data, off); off += 4
        names.append(data[off:off+ln].split(b'\x00', 1)[0].decode('latin1')); off += ln
    assert off == meta, f"path table end 0x{off:x} != metaTableOffset 0x{meta:x}"
    offs = [u32(data, meta + i*32 + 4) for i in range(count)]
    sizes = [(offs[i+1] if i < count-1 else len(data)) - offs[i] for i in range(count)]
    assert offs[0] == dstart and offs[-1]+sizes[-1] == len(data), "offset table failed validation"
    return names, offs, sizes

def main():
    data = open(sys.argv[1], 'rb').read()
    names, offs, sizes = parse(data)
    print(f"FEZC: {len(names)} files, data region 0x{offs[0]:x}..0x{len(data):x} (validated contiguous)")
    args = sys.argv[2:]
    inflate = '--inflate' in args
    outs = [a for a in args if not a.startswith('--')]
    if outs:
        out = outs[0]; n = infl = 0
        for nm, o, s in zip(names, offs, sizes):
            blob = data[o:o+s]
            if inflate:
                blob, did = maybe_inflate(blob); infl += did
            dst = os.path.join(out, nm)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(blob); n += 1
        print(f"extracted {n} files -> {out}" + (f"  (inflated {infl})" if inflate else ""))
    else:
        print("pass an outdir to extract (add --inflate to decompress). Sample:", names[:3])

if __name__ == '__main__':
    main()
