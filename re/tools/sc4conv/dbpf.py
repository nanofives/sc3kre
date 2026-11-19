#!/usr/bin/env python3
r"""dbpf.py - task sc4conv (2026-11-18h): read SimCity 4 DBPF 1.0 / 1.1 files and QFS-packed entries.

Layout (re/analysis/SC4_FORMATS.md 1-2, every offset checked on the JMyers Homes Pack files):

  header (96 bytes, little endian)
    +0x00 'DBPF'          +0x04 major (1)        +0x08 minor (0 or 1)
    +0x20 index major version (7)    +0x24 index entry count   +0x28 index offset   +0x2C index size
    +0x30 hole count                 +0x34 hole offset         +0x38 hole size      +0x3C index minor version
  index: count x {type, group, instance, offset, size} (u32 each, 20 bytes; 24 with a second instance when the
         index minor version is 2)
  directory entry (type 0xE86B1EEF): {type, group, instance, uncompressed size} per QFS-packed entry (16 bytes,
         20 with index minor 2)
  QFS entry: u32 compressed size (LE), 0x10 0xFB, u24 uncompressed size (BIG endian), then the command stream.

API:  f = DBPF(path);  for e in f.entries: ...;  f.read(e) -> bytes (unpacked when the directory lists it)
"""
import struct
import sys

T_DIR = 0xE86B1EEF
T_EXEMPLAR = 0x6534284A
T_COHORT = 0x05342861
T_S3D = 0x5AD0E817
T_FSH = 0x7AB50E44
T_LTEXT = 0x2026960B
TYPE_NAMES = {T_DIR: 'DIR', T_EXEMPLAR: 'EXMP', T_COHORT: 'COHT', T_S3D: 'S3D', T_FSH: 'FSH', T_LTEXT: 'LTEXT',
              0x856DDBAC: 'PNG', 0x6A386D26: 'KEYCFG', 0x88777601: 'T88777601'}


def qfs_decompress(data, off=0):
    """QFS / RefPack. data[off:] starts at the 4-byte compressed size of a DBPF entry, or at the 0x10FB magic."""
    if data[off + 4:off + 6] == b'\x10\xfb':
        off += 4
    if data[off:off + 2] != b'\x10\xfb' and data[off + 1] != 0xFB:
        raise ValueError('no QFS magic')
    flags = data[off]
    usize = (data[off + 2] << 16) | (data[off + 3] << 8) | data[off + 4]
    p = off + 5
    if flags & 0x01:          # a compressed-size field follows (not seen in SC4 files)
        p += 3
    out = bytearray(usize)
    o = 0
    n = len(data)
    while p < n:
        b0 = data[p]
        if b0 < 0x80:
            b1 = data[p + 1]
            p += 2
            plain = b0 & 3
            clen = ((b0 & 0x1C) >> 2) + 3
            coff = ((b0 & 0x60) << 3) + b1 + 1
        elif b0 < 0xC0:
            b1, b2 = data[p + 1], data[p + 2]
            p += 3
            plain = (b1 >> 6) & 3
            clen = (b0 & 0x3F) + 4
            coff = ((b1 & 0x3F) << 8) + b2 + 1
        elif b0 < 0xE0:
            b1, b2, b3 = data[p + 1], data[p + 2], data[p + 3]
            p += 4
            plain = b0 & 3
            clen = ((b0 & 0x0C) << 6) + b3 + 5
            coff = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
        elif b0 < 0xFC:
            p += 1
            plain = ((b0 & 0x1F) << 2) + 4
            clen = 0
            coff = 0
        else:
            p += 1
            plain = b0 & 3
            clen = 0
            coff = 0
            out[o:o + plain] = data[p:p + plain]
            o += plain
            break
        out[o:o + plain] = data[p:p + plain]
        o += plain
        p += plain
        if clen:
            s = o - coff
            if coff >= clen:
                out[o:o + clen] = out[s:s + clen]
            else:                       # overlapping copy, byte by byte
                for i in range(clen):
                    out[o + i] = out[s + i]
            o += clen
    if o != usize:
        raise ValueError('QFS size mismatch %d != %d' % (o, usize))
    return bytes(out)


class Entry:
    __slots__ = ('type', 'group', 'instance', 'offset', 'size', 'usize', 'packed')

    def __init__(self, t, g, i, off, size):
        self.type, self.group, self.instance, self.offset, self.size = t, g, i, off, size
        self.usize = size
        self.packed = False

    @property
    def tgi(self):
        return (self.type, self.group, self.instance)

    def __repr__(self):
        return '<%s %08X %08X %08X @%d %d%s>' % (TYPE_NAMES.get(self.type, '%08X' % self.type), self.type,
                                                 self.group, self.instance, self.offset, self.size,
                                                 ' qfs->%d' % self.usize if self.packed else '')


class DBPF:
    def __init__(self, path, data=None):
        self.path = path
        if data is None:
            with open(path, 'rb') as f:
                data = f.read()
        self.data = data                  # task sc4props: a file inflated from a zip / jar member
        d = self.data
        if d[:4] != b'DBPF':
            raise ValueError('%s: not a DBPF file' % path)
        self.major, self.minor = struct.unpack_from('<II', d, 4)
        (self.index_major, count, ioff, isize, self.hole_count, self.hole_off, self.hole_size,
         self.index_minor) = struct.unpack_from('<8I', d, 0x20)
        self.index_minor = self.index_minor if self.minor >= 1 else 0
        esz = 24 if self.index_minor == 2 else 20
        if count and isize != count * esz:
            raise ValueError('%s: index size %d != %d x %d' % (path, isize, count, esz))
        self.entries = []
        for k in range(count):
            p = ioff + k * esz
            t, g, i = struct.unpack_from('<III', d, p)
            off, size = struct.unpack_from('<II', d, p + esz - 8)
            self.entries.append(Entry(t, g, i, off, size))
        self.by_tgi = {e.tgi: e for e in self.entries}
        dsz = 20 if self.index_minor == 2 else 16
        for e in self.entries:
            if e.type == T_DIR:
                raw = d[e.offset:e.offset + e.size]
                for p in range(0, len(raw) - dsz + 1, dsz):
                    t, g, i = struct.unpack_from('<III', raw, p)
                    us = struct.unpack_from('<I', raw, p + dsz - 4)[0]
                    x = self.by_tgi.get((t, g, i))
                    if x is not None:
                        x.packed = True
                        x.usize = us

    def raw(self, e):
        return self.data[e.offset:e.offset + e.size]

    def read(self, e):
        if isinstance(e, tuple):
            e = self.by_tgi[e]
        raw = self.raw(e)
        if e.packed:
            return qfs_decompress(raw)
        return raw

    def of_type(self, t):
        return [e for e in self.entries if e.type == t]


def main(argv):
    from collections import Counter
    for path in argv[1:]:
        f = DBPF(path)
        c = Counter(e.type for e in f.entries)
        print('%s: DBPF %d.%d index %d.%d, %d entries' % (path, f.major, f.minor, f.index_major, f.index_minor,
                                                            len(f.entries)))
        for t, n in c.most_common():
            pk = sum(1 for e in f.entries if e.type == t and e.packed)
            print('  %-10s %08X %6d  (%d QFS)' % (TYPE_NAMES.get(t, '?'), t, n, pk))


if __name__ == '__main__':
    main(sys.argv)
