#!/usr/bin/env python3
r"""fbf.py - sc3ui2 (round 2026-11-18g): read SimCity 3000 Unlimited .FBF bitmap fonts.

FORMAT (all 8 FBF files under Apps\Res\Text\<lang>\ parse to EOF with this layout; the ENGLISH and English-UK
copies are byte-identical):

    +0x00  u32  1            [UNCERTAIN] version / kind, 1 in every file
    +0x04  u32  sheet width  640 in every file
    +0x08  u32  sheet height (MAIN9 42, MAIN10 48, SYSTEM9 28, SERIF17 145, TITLE9 54, TITLE12 92, systemloadsave 51)
    +0x0c  u32  1            [UNCERTAIN] 1 in every file
    +0x10  u8[w*h]           8-bit sheet, row-major, top row first. Index 16 is the key (transparent), as the
                             game reads it from sheet pixel (0,0) (GZServiceD FUN_10007ce5). Indices 1..15 are
                             coverage levels: SetColor writes palette entries 1..15 as a ramp from the text
                             colour (entry 1) to entry 16 (GZServiceD FUN_100070aa), so 1 = full ink, 15 = least.
    +0x10+w*h   u16[256]     RGB565 palette (the game replaces entries 1..16 at draw time)
    then        256 x 5 u32  glyph table, one per byte value: left, top, right, bottom (sheet rect, right/bottom
                             exclusive) and advance in px (GZServiceD FUN_10006e54 reads the same 0x14-byte cells)

Never commit the files or anything rendered from them (EA data). This reader writes to a gitignored folder only.

    py -3.12 re/tools/sc3ui/fbf.py <file.fbf>                 # header + glyph stats
    py -3.12 re/tools/sc3ui/fbf.py <file.fbf> --png out.png   # coverage sheet as greyscale (local only)
"""
import struct, sys
import numpy as np

KEY = 16


class Font:
    def __init__(self, path):
        b = open(path, 'rb').read()
        self.path = path
        self.kind, self.w, self.h, self.flag = struct.unpack_from('<4I', b, 0)
        n = self.w * self.h
        self.sheet = np.frombuffer(b, np.uint8, n, 16).reshape(self.h, self.w)
        self.pal = np.frombuffer(b, '<u2', 256, 16 + n)
        tab = np.frombuffer(b, '<u4', 256 * 5, 16 + n + 512).reshape(256, 5).astype(int)
        if 16 + n + 512 + 256 * 20 != len(b):
            raise ValueError('size mismatch: %d bytes, layout says %d' % (len(b), 16 + n + 512 + 5120))
        self.tab = tab
        levels = sorted(set(np.unique(self.sheet).tolist()) - {KEY, 17})
        self.levels = levels
        # line height = the tallest glyph cell
        self.line = int((tab[:, 3] - tab[:, 1]).max())

    def cell(self, ch):
        """(coverage float array 0..1, advance). Coverage: index 1 -> 1.0, 15 -> 1/15, key -> 0."""
        l, t, r, bt, adv = self.tab[ord(ch) if isinstance(ch, str) else ch]
        s = self.sheet[t:bt, l:r].astype(int)
        cov = np.where((s >= 1) & (s <= 15), (16 - s) / 15.0, 0.0)
        if self.levels == [1]:
            cov = (s == 1).astype(float)
        return cov, adv

    def render(self, text):
        """Coverage image of a string laid out with the font's own advances (no kerning, as the game)."""
        cells = [self.cell(c.encode('latin1')[0]) for c in text]
        width = sum(a for _, a in cells) + max((c.shape[1] for c, _ in cells), default=0)
        img = np.zeros((self.line, max(width, 1)))
        x = 0
        for cov, adv in cells:
            h, w = cov.shape
            img[:h, x:x + w] = np.maximum(img[:h, x:x + w], cov)
            x += adv
        return img[:, :max(x, 1)]


def main():
    f = Font(sys.argv[1])
    glyphs = [(i, *f.tab[i]) for i in range(256) if f.tab[i][2] > f.tab[i][0]]
    print('%s: kind %d sheet %dx%d flag %d, %d glyphs, line %d px, coverage levels %s' % (
        f.path, f.kind, f.w, f.h, f.flag, len(glyphs), f.line, f.levels))
    for ch in 'Hxgd ':
        l, t, r, b, a = f.tab[ord(ch)]
        print('  %r cell %dx%d adv %d' % (ch, r - l, b - t, a))
    if '--png' in sys.argv:
        from PIL import Image
        out = sys.argv[sys.argv.index('--png') + 1]
        s = f.sheet.astype(int)
        g = np.where((s >= 1) & (s <= 15), 255 - (16 - s) * 17, 255)
        Image.fromarray(g.astype(np.uint8)).save(out)


if __name__ == '__main__':
    main()
