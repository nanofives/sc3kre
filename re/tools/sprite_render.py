#!/usr/bin/env python3
"""sprite_render.py - render SimCity 3000 sprite records to PNG.

Currently handles ONLY the "plain bitmap" record class, which is fully decoded:

    format code 0  &&  dword1 == 0x10080000        (1,139 records in 12 archives)

Chain [CONFIRMED]: 0x1001de49 -> FUN_1001e086 -> FUN_1001e869 -> FUN_1001ddb8 (QFS).
0x1001e869 decompresses into a linear buffer and memcpy's it row by row into the target
surface: `iVar4` = vt+0x3c rows of `_Size` = vt+0x38 bytes, destination stride vt+0x1ac
[CONFIRMED @0x1001e869:56-60]. So the decompressed buffer is plain row-major with no inner
header.

GEOMETRY [CONFIRMED against all 1,139 shipped records]
    width  = record dword2
    height = record dword3
    declared uncompressed size == width * height, EXACTLY, for 1139/1139 records
    => bytes_per_row == width  => 8 bits per pixel, one byte per pixel.

PIXEL VALUES [CONFIRMED against all 1,139 shipped records]
    Every byte of every record is in 0..31 inclusive (global min 0, max 31, 32 distinct
    values, contiguous). Value 0 accounts for ~71% of bytes. The range never reaches 32,
    so the stored quantity is 5-bit, not a full 8-bit palette index.

    [UNCERTAIN] whether that 5-bit value is an ALPHA/coverage mask or an index into a
    32-entry palette. Evidence for alpha: the range is exactly 5-bit (matching one RGB565
    channel), 0 dominates and behaves as background, and every archive using this record
    class is an effect layer (Smoke, EffectSprites, disaster_*, GAME_UI). Evidence NOT yet
    obtained: no palette load and no blend call has been read; FUN_1001e869 itself only
    memcpy's, so it does not constrain the interpretation. Do not state this as fact until
    the surface's consumer is read.

    --mode alpha (default) renders it AS IF it were coverage: white RGBA, alpha = v*255/31.
    --mode gray renders the raw value scaled to 0..255, which asserts nothing about meaning.
    --mode raw  writes the undecorated 0..31 bytes as an 8-bit PNG (lossless, for analysis).

Usage:
  py -3.12 re/tools/sprite_render.py <dir-or-file> --out <outdir> [--mode alpha|gray|raw]
  py -3.12 re/tools/sprite_render.py <dir-or-file> --out <outdir> --sheet   # + contact sheets
  py -3.12 re/tools/sprite_render.py <file.DAT> --record <n> --out <outdir>
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ixf_parse
import qfs

from PIL import Image

PLAIN_D1 = 0x10080000
VMAX = 31          # confirmed maximum over all 1,139 records
SPAN_HDR = 16      # size of the inner header of a format-1 block


def is_plain_bitmap(h):
    return h["format"] == 0 and h["d1"] == PLAIN_D1


def is_span_sprite(h):
    return h["format"] == 1


def parse_anchor(payload):
    """Decode a type-1 ('anchor') record -> dict.

    [CONFIRMED, C4] 8 bytes = 4 x SIGNED i16. The shipped .SII text mirrors document the
    schema in their own header comment:
        [ImageGroup], [ImageInst], [Span L (reg pt x)], [Span T (reg pt y)], [Span R], [Span B]
    and joining the two on (group, instance) gives 8,132 matches with ZERO mismatches.
    The fields must be read SIGNED: 138 records have a negative spanT, 30 a negative spanB,
    10 a negative spanL and 8 a negative spanR.

    spanL / spanT are the registration point (the sprite's origin relative to its tile
    anchor), which is why they go negative.
    """
    if len(payload) < 8:
        raise qfs.QfsError("anchor record is %d bytes, expected 8" % len(payload))
    l, t, r, b = struct.unpack_from("<4h", payload, 0)
    return {"spanL": l, "spanT": t, "spanR": r, "spanB": b}


def parse_span_block(block):
    """Parse the self-describing format-1 block.

    LAYOUT [CONFIRMED against all 62,552 shipped format-1 records]
        +0x00 u32  total size            == len(block)
        +0x04 u16  width                 == record dword2
        +0x06 u16  height                == record dword3
        +0x08 u16  a                     (4 in every shipped record)
        +0x0a u16  b                     (7 in every shipped record)
        +0x0c u16  colour key            (0xF81F in every shipped record)
        +0x0e u16  pad                   (0 in every shipped record)
        +0x10      height x { u32 pixelOffset, u16 x, u16 flags }
                   span length n = flags & 0x7FFF
        then       pixel data, ONE u16 PER PIXEL

    The spans chain exactly: row[i].off + n(i) == row[i+1].off, and the last span ends
    precisely at the end of the data section. Pixels outside a row's span are not stored
    at all -- that is the compression, on top of QFS.

    [UNCERTAIN] the meaning of `a`/`b` (constant 4 and 7 everywhere, so no variation to
    learn from) and of the flags bit 0x8000.
    """
    tot, w, h, a, b, key, pad = struct.unpack_from("<IHHHHHH", block, 0)
    data_start = SPAN_HDR + h * 8
    rows = []
    for i in range(h):
        off, x, fl = struct.unpack_from("<IHH", block, SPAN_HDR + i * 8)
        rows.append((off, x, fl & 0x7FFF, fl >> 15))
    return {"total": tot, "w": w, "h": h, "a": a, "b": b, "key": key, "pad": pad,
            "rows": rows, "data_start": data_start}


def rgb565(v):
    return (((v >> 11) & 0x1F) * 255 // 31, ((v >> 5) & 0x3F) * 255 // 63, (v & 0x1F) * 255 // 31)


def rgb555(v):
    return (((v >> 10) & 0x1F) * 255 // 31, ((v >> 5) & 0x1F) * 255 // 31, (v & 0x1F) * 255 // 31)


# TWO pixel layouts ship, and the colour key identifies which [CONFIRMED over 62,552 records]:
#   key 0xF81F, header b == 7  -> RGB565.  0xF81F is magenta in 565.  62,462 records.
#   key 0x7C1F, header b == 5  -> RGB555.  0x7C1F is magenta in 555.     90 records.
# Both keys are the SAME COLOUR (magenta) once decoded with their own layout, which is what
# ties the layout to the key rather than to a guess. The header field b at +0x0a correlates
# perfectly with the key across all records; keying off the colour value is the directly
# evidenced choice, so that is what is used here.
KEY_555 = 0x7C1F


def span_to_image(block):
    """Render a format-1 block to RGBA. Unstored pixels and colour-key pixels are alpha 0."""
    m = parse_span_block(block)
    w, h, key, ds = m["w"], m["h"], m["key"], m["data_start"]
    conv = rgb555 if key == KEY_555 else rgb565
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y, (off, x, n, _top) in enumerate(m["rows"]):
        base = ds + off * 2
        for i in range(n):
            v, = struct.unpack_from("<H", block, base + i * 2)
            if v == key:
                continue
            px[x + i, y] = conv(v) + (255,)
    return img


def to_image(data, w, h, mode="alpha"):
    if len(data) != w * h:
        raise qfs.QfsError("expected %d bytes for %dx%d, got %d" % (w * h, w, h, len(data)))
    if mode == "raw":
        return Image.frombytes("L", (w, h), bytes(data))
    scaled = bytes(min(255, v * 255 // VMAX) for v in data)
    if mode == "gray":
        return Image.frombytes("L", (w, h), scaled)
    img = Image.new("RGBA", (w, h))
    img.putdata([(255, 255, 255, a) for a in scaled])
    return img


def contact_sheet(images, cols=16, pad=2, bg=(24, 24, 32, 255)):
    if not images:
        return None
    cw = max(i.width for i in images) + pad
    ch = max(i.height for i in images) + pad
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw + pad, rows * ch + pad), bg)
    for n, im in enumerate(images):
        x = pad + (n % cols) * cw
        y = pad + (n // cols) * ch
        sheet.paste(im.convert("RGBA"), (x, y), im.convert("RGBA"))
    return sheet


def run(target, outdir, mode="alpha", sheet=False, only=None):
    os.makedirs(outdir, exist_ok=True)
    total = skipped = 0
    for path in qfs.archives(target):
        try:
            records, d = ixf_parse.parse(path)
        except ixf_parse.IxfError as e:
            print("SKIP %s" % e, file=sys.stderr)
            continue
        name = os.path.splitext(os.path.basename(path))[0]
        imgs, n = [], 0
        for idx, r in enumerate(records):
            if r["type"] != qfs.TYPE_PIXELS:
                continue
            if only is not None and idx != only:
                continue
            payload = d[r["offset"]:r["offset"] + r["size"]]
            try:
                hdr = qfs.record_header(payload)
            except qfs.QfsError:
                continue
            if not (is_plain_bitmap(hdr) or is_span_sprite(hdr)):
                skipped += 1
                continue
            kind, out, info = qfs.decode_record(payload)
            if out is None:
                print("  FAIL %s rec %d: %s" % (name, idx, info.get("note")), file=sys.stderr)
                continue
            try:
                if is_span_sprite(hdr):
                    img = span_to_image(out)
                else:
                    img = to_image(out, hdr["d2"], hdr["d3"], mode)
            except (qfs.QfsError, struct.error, IndexError) as e:
                print("  FAIL %s rec %d: %s" % (name, idx, e), file=sys.stderr)
                continue
            sub = os.path.join(outdir, name)
            os.makedirs(sub, exist_ok=True)
            img.save(os.path.join(sub, "%05d_%08x_%08x.png" % (idx, r["group"], r["instance"])))
            imgs.append(img)
            n += 1
            total += 1
        if n:
            print("%-32s %4d rendered  (%dx%d .. %dx%d)"
                  % (name, n, imgs[0].width, imgs[0].height, imgs[-1].width, imgs[-1].height))
        if sheet and imgs:
            s = contact_sheet(imgs)
            if s:
                s.save(os.path.join(outdir, "_sheet_%s.png" % name))
    print("\n%d images written to %s (%d records skipped: not the plain-bitmap class)"
          % (total, outdir, skipped))
    return 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    target, args = argv[1], argv[2:]
    outdir = args[args.index("--out") + 1] if "--out" in args else "sprites_png"
    mode = args[args.index("--mode") + 1] if "--mode" in args else "alpha"
    only = int(args[args.index("--record") + 1], 0) if "--record" in args else None
    return run(target, outdir, mode, "--sheet" in args, only)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
