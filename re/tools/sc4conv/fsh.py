#!/usr/bin/env python3
r"""fsh.py - task sc4conv (2026-11-18h): SimCity 4 FSH texture reader (type 0x7AB50E44, 'SHPI').

Layout (re/analysis/SC4_FORMATS.md 5):
  +0x00 'SHPI'  +0x04 u32 file size  +0x08 u32 entry count  +0x0C 4-char directory id ('G264' in the pack)
  +0x10 count x {4-char name, u32 offset}
  bitmap at offset: u8 code, u24 offset to the next block (0 = none), u16 width, u16 height,
                    u16 centre x, u16 centre y, u16 position x, u16 position y (high 4 bits = mipmap count),
                    then the main image, then the mipmaps (each half size, at least 1 x 1 pixel / one 4 x 4 block)
  codes read here: 0x60 DXT1, 0x61 DXT3, 0x62 DXT5, 0x7D A8R8G8B8, 0x7F R8G8B8, 0x78 R5G6B5, 0x7E A1R5G5B5,
                   0x6D A4R4G4B4, 0x7B 8-bit indexed (palette in a following 0x2A/0x22 block; not in the pack)
Returns numpy RGBA uint8 arrays (h, w, 4).
"""
import struct

import numpy as np


def _565(c):
    r = (c >> 11) & 31
    g = (c >> 5) & 63
    b = c & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.int32)


def _dxt_colour_block(blocks, alpha1bit):
    """blocks: (n, 8) uint8 -> (n, 16, 4) RGBA."""
    c0 = blocks[:, 0].astype(np.uint32) | (blocks[:, 1].astype(np.uint32) << 8)
    c1 = blocks[:, 2].astype(np.uint32) | (blocks[:, 3].astype(np.uint32) << 8)
    bits = (blocks[:, 4].astype(np.uint32) | (blocks[:, 5].astype(np.uint32) << 8) |
            (blocks[:, 6].astype(np.uint32) << 16) | (blocks[:, 7].astype(np.uint32) << 24))
    a = _565(c0)
    b = _565(c1)
    n = len(blocks)
    pal = np.zeros((n, 4, 4), np.int32)
    pal[:, 0, :3] = a
    pal[:, 1, :3] = b
    pal[:, :, 3] = 255
    four = (c0 > c1) | (not alpha1bit)
    p2 = np.where(four[:, None], (2 * a + b) // 3, (a + b) // 2)
    p3 = np.where(four[:, None], (a + 2 * b) // 3, 0)
    pal[:, 2, :3] = p2
    pal[:, 3, :3] = p3
    if alpha1bit:
        pal[:, 3, 3] = np.where(four, 255, 0)
    idx = (bits[:, None] >> (2 * np.arange(16, dtype=np.uint32))[None, :]) & 3
    return np.take_along_axis(pal, idx[:, :, None].astype(np.int64).repeat(4, 2), 1)


def _unblock(px, w, h):
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    img = px.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    return img[:h, :w].astype(np.uint8)


def decode(code, b, p, w, h):
    """One image of the given code at b[p:]; returns (rgba, bytes used)."""
    if code in (0x60, 0x61, 0x62):
        bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
        n = bw * bh
        bs = 8 if code == 0x60 else 16
        raw = np.frombuffer(b, np.uint8, n * bs, p).reshape(n, bs)
        if code == 0x60:
            px = _dxt_colour_block(raw, True)
        else:
            px = _dxt_colour_block(raw[:, 8:], False)
            if code == 0x61:
                ab = raw[:, :8]
                nib = np.stack([ab & 15, ab >> 4], -1).reshape(n, 16).astype(np.int32)
                px[:, :, 3] = nib * 17
            else:
                a0 = raw[:, 0].astype(np.int32)
                a1 = raw[:, 1].astype(np.int32)
                bits = np.zeros(n, np.uint64)
                for k in range(6):
                    bits |= raw[:, 2 + k].astype(np.uint64) << np.uint64(8 * k)
                idx = ((bits[:, None] >> (3 * np.arange(16, dtype=np.uint64))[None, :]) & np.uint64(7)).astype(np.int64)
                tab = np.zeros((n, 8), np.int32)
                tab[:, 0], tab[:, 1] = a0, a1
                big = a0 > a1
                for k in range(1, 7):              # 8-value ramp: a0 > a1
                    tab[big, k + 1] = ((7 - k) * a0[big] + k * a1[big]) // 7
                sm = ~big
                for k in range(1, 5):              # 6-value ramp + 0 and 255: a0 <= a1
                    tab[sm, k + 1] = ((5 - k) * a0[sm] + k * a1[sm]) // 5
                tab[sm, 6] = 0
                tab[sm, 7] = 255
                px[:, :, 3] = np.take_along_axis(tab, idx, 1)
        return _unblock(px, w, h), n * bs
    if code == 0x7D:
        a = np.frombuffer(b, np.uint8, w * h * 4, p).reshape(h, w, 4)
        return a[:, :, [2, 1, 0, 3]].copy(), w * h * 4
    if code == 0x7F:
        a = np.frombuffer(b, np.uint8, w * h * 3, p).reshape(h, w, 3)
        out = np.full((h, w, 4), 255, np.uint8)
        out[:, :, :3] = a[:, :, ::-1]
        return out, w * h * 3
    if code in (0x78, 0x7E, 0x6D):
        c = np.frombuffer(b, '<u2', w * h, p).reshape(h, w).astype(np.int32)
        out = np.full((h, w, 4), 255, np.int32)
        if code == 0x78:
            out[:, :, :3] = _565(c)
        elif code == 0x7E:
            for k, s in enumerate((10, 5, 0)):
                v = (c >> s) & 31
                out[:, :, k] = (v << 3) | (v >> 2)
            out[:, :, 3] = np.where(c & 0x8000, 255, 0)
        else:
            for k, s in enumerate((8, 4, 0)):
                out[:, :, k] = ((c >> s) & 15) * 17
            out[:, :, 3] = ((c >> 12) & 15) * 17
        return out.astype(np.uint8), w * h * 2
    raise ValueError('FSH code 0x%02X not read' % code)


def read_fsh(b, mips=False):
    """-> list of {name, code, w, h, centre, pos, mipmaps, image, [mip images]}"""
    if b[:4] != b'SHPI':
        raise ValueError('not SHPI')
    size, count = struct.unpack_from('<II', b, 4)
    dirid = b[12:16].decode('latin-1')
    out = []
    for k in range(count):
        name = b[16 + 8 * k:20 + 8 * k].decode('latin-1')
        off = struct.unpack_from('<I', b, 20 + 8 * k)[0]
        hdr = struct.unpack_from('<I', b, off)[0]
        code = hdr & 0xFF
        nxt = hdr >> 8
        w, h, cx, cy, px_, py_ = struct.unpack_from('<6H', b, off + 4)
        nmip = py_ >> 12
        img, used = decode(code, b, off + 16, w, h)
        e = {'name': name, 'dir': dirid, 'code': code, 'w': w, 'h': h, 'centre': (cx, cy),
             'pos': (px_, py_ & 0x0FFF), 'mipmaps': nmip, 'next': nxt, 'image': img, 'main_bytes': used}
        if mips:
            q = off + 16 + used
            ims = []
            mw, mh = w, h
            for _ in range(nmip):
                mw, mh = max(1, mw // 2), max(1, mh // 2)
                im, u = decode(code, b, q, mw, mh)
                ims.append(im)
                q += u
            e['mips'] = ims
            e['end'] = q
        out.append(e)
    return out
