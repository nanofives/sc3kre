#!/usr/bin/env python3
r"""uiart.py - sc3ui3 (round 2026-11-19b): extract the few game UI bitmaps the pages are allowed to publish.

Owner call 2026-11-19: the play / stop buttons, the window close X, the slider (knob + track), the dropdown arrow
and the volume steps are published as the game's own bitmaps (docs/assets/sc3ui/). Nothing else from the game is.

Where they live (found by matching every UI record against a native 800x600 grab of Preferencias, verify/sc3ui3):

    file                     group      instance   size    frames                       piece
    Apps\Res\UI\Shared\SYS   82b9b75b   453ba1f4   92x23   4 x 23x23                    close X (title bar)
    Apps\Res\UI\Shared\SYS   82b9b75b   82fab6d2   96x25   4 x 24x25                    play
    Apps\Res\UI\Shared\SYS   82b9b75b   22fab6de   96x25   4 x 24x25                    stop
    Apps\Res\UI\Shared\SYS   82b9b75b   62b99d31   64x16   4 x 16x16, one file each     dropdown arrow button
    Apps\Res\UI\Shared\SYS   82b9b75b   c2b99e09   80x20   cols 0..59 track, 60..79 knob slider
    ...\22DEC92D_OtherCtrls  22dec92d   00000001   68x10   1                            volume steps
    Apps\Res\UI\Shared\SYS   82b9b75b   c2d6e93a   104x13  8 x 13x13                    check box
    Apps\Res\UI\Shared\SYS   82b9b75b   0000000a   96x12   8 x 12x12, magenta key       radio button
    Apps\Res\UI\Shared\SYS   82b9b75b   a2defd9a   168x32  4 x 42x32                    OK (tick) button
    Apps\Res\UI\Shared\SYS   82b9b75b   e2b99e01   192x16  12 x 16x16, one file each    scroll bar (both directions)

Check box / radio frames, observed the same way: 0 on, 1 off, 2 on + hover, 3 off + hover, 4 on + pressed,
5 off + pressed, 6 on + disabled (the music list's ticks with Musica unticked), 7 off + disabled (by the pairing).
Scroll bar frames: 0/1 left arrow normal/pressed, 2 horizontal thumb, 3 horizontal track, 4/5 right arrow, 6/7 up
arrow, 8 vertical thumb, 9 vertical track (16 identical rows), 10/11 down arrow. The arrows show no hover change.
OK: the 4-frame button order above (1 normal, 2 pressed, 3 hover observed).

Frame order of a 4-frame button strip, observed in the game with posted input (verify/sc3ui3/states.py,
disabled.py): 0 = disabled (Musica unticked greys play / stop), 1 = normal, 2 = pressed (mouse down), 3 = hover.
Each frame matched the grab with 0 differing pixels (close X: rows 2..22, see UI_STYLE.md).

Record layout (type 0x62b9da24): 0x18-byte header u32 (2, size, width, height, 7, size), then a QFS stream that
decodes to RGB565, top row first (re/tools/qfs.py). 565 is expanded by bit replication (r<<3|r>>2, g<<2|g>>4),
which gives the colours the game's 16-bit screen shows (#7b92ff for the title blue). The bitmaps carry no key
colour: their background is the blue the game draws them on.

    py -3.12 re/tools/sc3ui/uiart.py --game <install> --out docs/assets/sc3ui     # write the published PNGs
    py -3.12 re/tools/sc3ui/uiart.py --game <install> --check docs/assets/sc3ui   # exit 1 if a PNG differs
"""
import argparse, os, struct, sys, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import ixf_parse, qfs  # noqa: E402

TYPE_IMG = 0x62b9da24
# out name -> (IXF file under Apps\Res\UI\Shared, group, instance, crop (x0, x1) or None)
PIECES = {
    'close.png':        ('SYS.IXF', 0x82b9b75b, 0x453ba1f4, None),
    'play.png':         ('SYS.IXF', 0x82b9b75b, 0x82fab6d2, None),
    'stop.png':         ('SYS.IXF', 0x82b9b75b, 0x22fab6de, None),
    # the dropdown arrow is cut into one file per frame: a <select> is wider than the arrow, so a strip would show
    # the neighbouring frame beside it (UI_STYLE.md "Game bitmaps")
    'combo_arrow_disabled.png': ('SYS.IXF', 0x82b9b75b, 0x62b99d31, (0, 16)),
    'combo_arrow.png':          ('SYS.IXF', 0x82b9b75b, 0x62b99d31, (16, 32)),
    'combo_arrow_pressed.png':  ('SYS.IXF', 0x82b9b75b, 0x62b99d31, (32, 48)),
    'combo_arrow_hover.png':    ('SYS.IXF', 0x82b9b75b, 0x62b99d31, (48, 64)),
    'slider_track.png': ('SYS.IXF', 0x82b9b75b, 0xc2b99e09, (0, 60)),
    'slider_knob.png':  ('SYS.IXF', 0x82b9b75b, 0xc2b99e09, (60, 80)),
    'volume.png':       ('22DEC92D_OtherCtrls.ixf', 0x22dec92d, 0x00000001, None),
    # owner, 2026-11-19 (second list): check box, radio button, OK button, list scroll bar
    'checkbox.png':     ('SYS.IXF', 0x82b9b75b, 0xc2d6e93a, None),
    'radio.png':        ('SYS.IXF', 0x82b9b75b, 0x0000000a, None),     # magenta key -> transparent
    'ok.png':           ('SYS.IXF', 0x82b9b75b, 0xa2defd9a, None),
    # the scroll bar record holds 12 frames of 16x16. Browsers draw scroll bar parts from whole images (no sprite
    # cropping), so each frame is its own file
    'scroll_left.png':          ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (0, 16)),
    'scroll_left_pressed.png':  ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (16, 32)),
    'scroll_hthumb.png':        ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (32, 48)),
    'scroll_htrack.png':        ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (48, 64)),
    'scroll_right.png':         ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (64, 80)),
    'scroll_right_pressed.png': ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (80, 96)),
    'scroll_up.png':            ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (96, 112)),
    'scroll_up_pressed.png':    ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (112, 128)),
    'scroll_thumb.png':         ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (128, 144)),
    'scroll_track.png':         ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (144, 160)),
    'scroll_down.png':          ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (160, 176)),
    'scroll_down_pressed.png':  ('SYS.IXF', 0x82b9b75b, 0xe2b99e01, (176, 192)),
}
KEYED = {'radio.png'}          # the game draws these with RGB565 magenta (0xF81F) as the transparent key


def read_image(path, group, instance):
    """-> (width, height, rows of (r, g, b) bytes) for one UI bitmap record."""
    recs, d = ixf_parse.parse(path)
    for r in recs:
        if r['type'] == TYPE_IMG and r['group'] == group and r['instance'] == instance:
            p = d[r['offset']:r['offset'] + r['size']]
            _, _, w, h, fmt, _ = struct.unpack_from('<6I', p, 0)
            raw = qfs.decompress(p, 0x18)[0]
            if len(raw) < w * h * 2:
                raise ValueError('%s %08x:%08x decodes short' % (path, group, instance))
            rows = []
            for y in range(h):
                row = bytearray()
                for x in range(w):
                    v = raw[(y * w + x) * 2] | raw[(y * w + x) * 2 + 1] << 8
                    r5, g6, b5 = v >> 11 & 31, v >> 5 & 63, v & 31
                    row += bytes((r5 << 3 | r5 >> 2, g6 << 2 | g6 >> 4, b5 << 3 | b5 >> 2))
                rows.append(bytes(row))
            return w, h, rows
    raise KeyError('%08x:%08x not in %s' % (group, instance, path))


def png_bytes(w, h, rows, keyed=False):
    """Plain 8-bit RGB PNG (RGBA when keyed: the magenta key becomes alpha 0), no ancillary chunks, byte-stable."""
    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    if keyed:
        rows = [b''.join(r[k:k + 3] + (b'\0' if r[k:k + 3] == b'\xff\x00\xff' else b'\xff') for k in range(0, len(r), 3))
                for r in rows]
    body = b''.join(b'\0' + r for r in rows)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6 if keyed else 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(body, 9)) + chunk(b'IEND', b''))


def build(game):
    shared = os.path.join(game, 'Apps', 'Res', 'UI', 'Shared')
    out = {}
    for name, (f, g, i, crop) in PIECES.items():
        w, h, rows = read_image(os.path.join(shared, f), g, i)
        if crop:
            x0, x1 = crop
            rows = [r[x0 * 3:x1 * 3] for r in rows]
            w = x1 - x0
        out[name] = png_bytes(w, h, rows, name in KEYED)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--game', required=True, help='game install folder (holds Apps\\Res\\UI\\Shared)')
    ap.add_argument('--out', help='write the PNGs here')
    ap.add_argument('--check', help='compare against the PNGs in this folder')
    a = ap.parse_args()
    files = build(a.game)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        for n, b in files.items():
            open(os.path.join(a.out, n), 'wb').write(b)
            print('wrote', n, len(b), 'bytes')
    if a.check:
        bad = [n for n, b in files.items()
               if not os.path.exists(os.path.join(a.check, n)) or open(os.path.join(a.check, n), 'rb').read() != b]
        print('uiart check:', 'all %d identical' % len(files) if not bad else 'DIFFER: ' + ', '.join(bad))
        sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
