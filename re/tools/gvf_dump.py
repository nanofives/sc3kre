#!/usr/bin/env python3
"""gvf_dump.py — parse FusionEngine 'FE_GVF_BIN_0001' keyed tables from data.fez and dump keys.

Record format (reverse-engineered from strings.gvf):
  16-byte magic "FE_GVF_BIN_0001\0", then a small header, then repeating entries:
    [u16 keyLen LE][key ASCII (keyLen bytes)][u32 value LE]
The entry start offset after the magic is auto-detected (the first offset from which the
[len][ascii][u32] chain parses cleanly to EOF).

Usage: py -3.12 re/tools/gvf_dump.py <data.fez> [out.csv]
"""
import sys, os, struct, zlib

def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]

def _parse_at(buf, start):
    entries, o = [], start
    while o + 6 <= len(buf):
        ln = u16(buf, o)
        if ln == 0 or ln > 96 or o + 2 + ln + 4 > len(buf):
            break
        key = buf[o+2:o+2+ln]
        if not all(32 <= c < 127 for c in key):
            break
        entries.append((key.decode('latin1'), u32(buf, o+2+ln)))
        o += 2 + ln + 4
    return entries

def parse_gvf(buf):
    if not buf.startswith(b'FE_GVF_BIN_'):
        return None
    # entry start = the offset (after the fixed header region) that yields the most entries
    best = max((_parse_at(buf, s) for s in range(16, 48)), key=len, default=[])
    return best if len(best) > 3 else None

def main():
    data = open(sys.argv[1], 'rb').read()
    out = sys.argv[2] if len(sys.argv) > 2 else None
    u = lambda o: struct.unpack_from('<I', data, o)[0]
    count = u(8); paths = u(0x0c); meta = u(0x10)
    off = paths; names = []
    for _ in range(count):
        ln = u(off); off += 4
        names.append(data[off:off+ln].split(b'\x00', 1)[0].decode('latin1')); off += ln
    offs = [u(meta + i*32 + 4) for i in range(count)]
    sizes = [(offs[i+1] if i < count-1 else len(data)) - offs[i] for i in range(count)]

    rows = []; files_ok = files_gvf = 0
    for nm, o, s in zip(names, offs, sizes):
        if not nm.endswith('.gvf'):
            continue
        files_gvf += 1
        blob = data[o:o+s]
        if blob[:2] == b'\x78\xda':
            try: blob = zlib.decompressobj().decompress(blob)
            except Exception: continue
        ents = parse_gvf(blob)
        if ents:
            files_ok += 1
            for k, v in ents:
                rows.append((nm, k, v))
    print(f".gvf files: {files_gvf}, parsed OK: {files_ok}, total keys: {len(rows)}")
    # sample
    for r in rows[:20]:
        print(f"  {r[0]:28} {r[1]:32} = {r[2]}")
    if out:
        with open(out, 'w', encoding='utf-8') as f:
            f.write("file,key,value\n")
            for nm, k, v in rows:
                f.write(f"{nm},{k},{v}\n")
        print(f"wrote {len(rows)} rows -> {out}")

if __name__ == '__main__':
    main()
