#!/usr/bin/env python3
"""sprite_encode.py - re-encode a span-sprite block, transcribed from the shipped encoder.

This exists to ROUND-TRIP the format: decode a shipped block to a full pixel surface, run the
encoder over that surface, and byte-compare the result against the original block. A
byte-identical result proves the layout is understood exactly -- not merely well enough to
produce a plausible image.

  py -3.12 re/tools/sprite_encode.py "Apps/Res" --selftest
  round-tripped 62552 format-1 records: 62552 byte-identical, 0 mismatched   [2026-08-17]

Transcribed from GZGraphicD.dll `sc3gfx_image_encode_span_block` FUN_100017de (1,280 bytes),
the 16bpp branch (`*(int *)(pixfmt + 4) == 0x10`). Line numbers below refer to
re/ghidra_export_gzgraphicd/functions/100017de_FUN_100017de.c.

  L90   allocate (width+1)*height*2 + 0x10        -> 16-byte header, 2 bytes per pixel
  L100  local_2c = 0x10                           -> row table starts at +0x10
  L157  local_2c += 8                             -> 8 bytes per row entry
  L115  count leading pixels equal to the key     -> local_20
  L123  count trailing pixels equal to the key    -> param_1
  L128  span length = width - leading - trailing  -> iVar5
  L130  scan the span; any key pixel clears bVar1
  L146  rec+0 = running pixel offset (u32)
  L147  rec+4 = leading count (u16)
  L148  rec+6 = (bVar1 ? 0x8000 : 0) | span length
  L164  hdr+6  = height
  L165  hdr+0  = total size
  L166  hdr+4  = width
  L167  hdr+8  = literal 4
  L169  hdr+10 = pixel-format id (from the surface descriptor at vt+0x50)
  L170  hdr+12 = colour key

Empty-row case (L109-113, reached when every pixel equals the key): span length 0, bVar1 = 1,
and the leading count has run to `width`, so the entry is {off, x = width, flags = 0x8000}.

Usage:
  py -3.12 re/tools/sprite_encode.py <dir-or-file>          # round-trip every format-1 record
  py -3.12 re/tools/sprite_encode.py <file.DAT> --record 0  # one record, verbose
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ixf_parse
import qfs
import sprite_render as sr

HDR = 16


def block_to_surface(block):
    """Decode a block to a flat list of width*height u16 pixels (key where nothing is stored)."""
    m = sr.parse_span_block(block)
    w, h, key, ds = m["w"], m["h"], m["key"], m["data_start"]
    surf = [key] * (w * h)
    for y, (off, x, n, _top) in enumerate(m["rows"]):
        base = ds + off * 2
        for i in range(n):
            surf[y * w + x + i], = struct.unpack_from("<H", block, base + i * 2)
    return surf, m


def encode(surf, w, h, key, fmt_id, tag=4):
    """Encode a full surface back into a span block. Mirrors FUN_100017de's 16bpp branch."""
    rows = bytearray()
    pix = bytearray()
    running = 0
    for y in range(h):
        row = surf[y * w:(y + 1) * w]
        lead = 0
        while lead < w and row[lead] == key:
            lead += 1
        if w == 0 or lead >= w:
            # every pixel is the key: L109-113 leaves span 0 and the opaque flag SET
            span, opaque, x = 0, 1, lead
        else:
            trail = 0
            i = w - 1
            while row[i] == key:              # L123: no lower bound; safe, a non-key exists
                trail += 1
                i -= 1
            span = w - lead - trail
            x = lead
            opaque = 1
            for j in range(lead, lead + span):
                if row[j] == key:
                    opaque = 0
                    break
        rows += struct.pack("<IHH", running, x, (0x8000 if opaque else 0) | span)
        for j in range(x, x + span):
            pix += struct.pack("<H", row[j])
        running += span

    total = HDR + len(rows) + len(pix)
    hdr = bytearray(HDR)
    struct.pack_into("<I", hdr, 0, total)
    struct.pack_into("<H", hdr, 4, w)
    struct.pack_into("<H", hdr, 6, h)
    struct.pack_into("<H", hdr, 8, tag)
    struct.pack_into("<H", hdr, 10, fmt_id)
    struct.pack_into("<H", hdr, 12, key)
    # +0x0e is left zero; it is 0 in all 62,552 shipped records.
    return bytes(hdr + rows + pix)


def roundtrip(block):
    """-> (ok, detail). Re-encode a shipped block and compare byte for byte."""
    surf, m = block_to_surface(block)
    out = encode(surf, m["w"], m["h"], m["key"], m["b"], m["a"])
    if out == block:
        return True, ""
    if len(out) != len(block):
        return False, "length %d != %d" % (len(out), len(block))
    for i, (a, b) in enumerate(zip(out, block)):
        if a != b:
            where = ("header +0x%x" % i if i < HDR
                     else "row %d +%d" % ((i - HDR) // 8, (i - HDR) % 8)
                     if i < HDR + m["h"] * 8 else "pixel data +%d" % (i - HDR - m["h"] * 8))
            return False, "first diff at %d (%s): got 0x%02x want 0x%02x" % (i, where, a, b)
    return False, "unknown"


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target = argv[1]
    # `--selftest` is accepted as an alias for "walk the whole corpus", which is what a bare
    # directory argument already does. Roadmap gate T2 asks every proven-write format for a
    # --selftest, so the flag exists here for a uniform surface rather than to add behaviour.
    only = int(argv[argv.index("--record") + 1], 0) if "--record" in argv else None

    n_ok = n_bad = n_tot = 0
    fails = []
    for path in qfs.archives(target):
        try:
            records, d = ixf_parse.parse(path)
        except ixf_parse.IxfError:
            continue
        f_ok = f_bad = 0
        for idx, r in enumerate(records):
            if r["type"] != qfs.TYPE_PIXELS:
                continue
            if only is not None and idx != only:
                continue
            pay = d[r["offset"]:r["offset"] + r["size"]]
            try:
                h = qfs.record_header(pay)
            except qfs.QfsError:
                continue
            if h["format"] != 1:
                continue
            block = qfs.decode_record(pay)[1]
            if block is None:
                continue
            n_tot += 1
            ok, detail = roundtrip(block)
            if ok:
                n_ok += 1
                f_ok += 1
            else:
                n_bad += 1
                f_bad += 1
                if len(fails) < 10:
                    fails.append("%s rec %d (%dx%d): %s"
                                 % (os.path.basename(path), idx, h["d2"], h["d3"], detail))
            if only is not None:
                print("%s record %d: %dx%d, %d bytes -> %s %s"
                      % (path, idx, h["d2"], h["d3"], len(block),
                         "BYTE-IDENTICAL" if ok else "MISMATCH", detail))
        if only is None and (f_ok or f_bad):
            print("%-34s %6d ok  %5d MISMATCH" % (os.path.basename(path), f_ok, f_bad))

    if only is None:
        print("\nround-tripped %d format-1 records: %d byte-identical, %d mismatched"
              % (n_tot, n_ok, n_bad))
        for f in fails:
            print("   " + f)
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
