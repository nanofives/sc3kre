#!/usr/bin/env python3
r"""s3d.py - task sc4conv (2026-11-18h): SimCity 4 S3D model reader (type 0x5AD0E817, '3DMD').

Layout read from the JMyers Homes Pack (re/analysis/SC4_FORMATS.md 4). The chunk length fields after the 4-byte
tag hold the right value only for HEAD, PROP and REGP in this pack (VERT, INDX, PRIM, MATS, ANIM give larger
numbers that run past the end of the file), so the reader walks the chunks by their contents, in the fixed order
HEAD VERT INDX PRIM MATS ANIM PROP REGP, and checks that it lands on the next tag and on the end of the file.

  '3DMD' u32 (value not used)
  HEAD  u32 len, u16 major (1), u16 minor (5)
  VERT  u32 len, u32 groups; group: u16 flags, u16 count, u32 format, count x vertex
        format 0x80004001 = 3 f32 position + 2 f32 uv (20 bytes, the only format in the pack)
  INDX  u32 len, u32 groups; group: u16 flags, u16 stride (2), u16 count, count x u16
  PRIM  u32 len, u32 groups; group: u16 count; prim: u32 type (0 = triangle list), u32 first, u32 count
  MATS  u32 len, u32 groups; group: u32 flags, u8 alpha func, u8 depth func, u8 src blend, u8 dst blend,
        u16 alpha threshold, u32 material class, u8 reserved, u8 texture count;
        texture: u32 FSH instance, u8 wrap s, u8 wrap t, u8 mag, u8 min, u16 anim rate, u16 anim mode,
                 u8 name length, name (with its NUL)
  ANIM  u32 len, u16 frames, u16 frame rate, u16 mode, u32 flags, f32 displacement, u16 meshes;
        mesh: u8 name length, u8 flags, name, frames x {u16 vert group, u16 index group, u16 prim group,
        u16 mat group}
  PROP  u32 len, u32 count (0 in the pack)     REGP  u32 len, u32 count (0 in the pack)
"""
import struct


class S3D:
    def __init__(self, b):
        if b[:4] != b'3DMD':
            raise ValueError('not 3DMD')
        self.raw = b
        p = 8
        self.chunk_len = {}

        def tag(expect):
            nonlocal p
            t = b[p:p + 4].decode('latin-1')
            if t != expect:
                raise ValueError('expected %s at %d, got %r' % (expect, p, t))
            self.chunk_len[t] = struct.unpack_from('<I', b, p + 4)[0]
            self.chunk_at = getattr(self, 'chunk_at', {})
            self.chunk_at[t] = p
            p += 8

        def u(fmt):
            nonlocal p
            v = struct.unpack_from('<' + fmt, b, p)
            p += struct.calcsize('<' + fmt)
            return v if len(v) > 1 else v[0]

        tag('HEAD')
        self.major, self.minor = u('HH')
        tag('VERT')
        self.verts = []
        for _ in range(u('I')):
            flags, cnt, fmt = u('HHI')
            if fmt != 0x80004001:
                raise ValueError('vertex format 0x%08X not read' % fmt)
            vs = [struct.unpack_from('<5f', b, p + 20 * k) for k in range(cnt)]
            p += 20 * cnt
            self.verts.append({'flags': flags, 'format': fmt, 'v': vs})
        tag('INDX')
        self.indices = []
        for _ in range(u('I')):
            flags, stride, cnt = u('HHH')
            if stride != 2:
                raise ValueError('index stride %d' % stride)
            self.indices.append({'flags': flags, 'i': list(struct.unpack_from('<%dH' % cnt, b, p))})
            p += 2 * cnt
        tag('PRIM')
        self.prims = []
        for _ in range(u('I')):
            n = u('H')
            self.prims.append([u('III') for _ in range(n)])
        tag('MATS')
        self.mats = []
        for _ in range(u('I')):
            flags = u('I')
            afunc, dfunc, sblend, dblend = u('BBBB')
            athr = u('H')
            mclass = u('I')
            reserved, ntex = u('BB')
            texs = []
            for _ in range(ntex):
                tid = u('I')
                ws, wt, mag, mn = u('BBBB')
                arate, amode = u('HH')
                nl = u('B')
                name = b[p:p + nl].rstrip(b'\0').decode('latin-1')
                p += nl
                texs.append({'id': tid, 'wrap': (ws, wt), 'filter': (mag, mn), 'anim': (arate, amode),
                             'name': name})
            self.mats.append({'flags': flags, 'alpha_func': afunc, 'depth_func': dfunc, 'blend': (sblend, dblend),
                              'alpha_threshold': athr, 'class': mclass, 'reserved': reserved, 'tex': texs})
        tag('ANIM')
        nfr, rate, mode = u('HHH')
        aflags = u('I')
        disp = u('f')
        nmesh = u('H')
        meshes = []
        for _ in range(nmesh):
            nl, mflags = u('BB')
            name = b[p:p + nl].rstrip(b'\0').decode('latin-1')
            p += nl
            frames = [u('HHHH') for _ in range(nfr)]
            meshes.append({'name': name, 'flags': mflags, 'frames': frames})
        self.anim = {'frames': nfr, 'rate': rate, 'mode': mode, 'flags': aflags, 'displacement': disp,
                     'meshes': meshes}
        tag('PROP')
        self.nprop = u('I')
        if self.nprop:
            raise ValueError('PROP entries not read')
        tag('REGP')
        self.nregp = u('I')
        if self.nregp:
            raise ValueError('REGP entries not read')
        if p != len(b):
            raise ValueError('S3D: %d bytes left after REGP' % (len(b) - p))

    def meshes(self):
        """(positions, uvs, triangles, material) per ANIM mesh, frame 0."""
        out = []
        for m in self.anim['meshes']:
            vg, ig, pg, mg = m['frames'][0]
            vs = self.verts[vg]['v']
            idx = self.indices[ig]['i']
            tris = []
            for (ptype, first, cnt) in self.prims[pg]:
                if ptype != 0:
                    raise ValueError('prim type %d' % ptype)
                seg = idx[first:first + cnt]
                tris += [tuple(seg[k:k + 3]) for k in range(0, len(seg) - 2, 3)]
            out.append(([v[:3] for v in vs], [v[3:] for v in vs], tris, self.mats[mg], m['name']))
        return out
