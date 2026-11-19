#!/usr/bin/env python3
r"""exemplar.py - task sc4conv (2026-11-18h): SimCity 4 exemplar / cohort and LText readers.

Binary exemplar (re/analysis/SC4_FORMATS.md 3):
  +0x00 'EQZB1###' (cohort: 'CQZB1###')   +0x08 parent cohort {type, group, instance}   +0x14 u32 property count
  property: u32 id, u16 value type, u16 key type (0x00 one value, 0x80 a list), u8 (0), [u32 count if 0x80], values
  value types: 0x0100 u8, 0x0200 u16, 0x0300 u32, 0x0700 s32, 0x0800 s64, 0x0900 f32, 0x0B00 bool, 0x0C00 string
  (a string is a list of count bytes)
Text exemplars ('EQZT1###') are not used by the pack and are not read.

LText (type 0x2026960B): u16 character count, u16 0x1000 (UTF-16 marker), count x UTF-16LE.
"""
import struct

VT = {0x0100: ('B', 1), 0x0200: ('H', 2), 0x0300: ('I', 4), 0x0700: ('i', 4), 0x0800: ('q', 8), 0x0900: ('f', 4),
      0x0B00: ('?', 1), 0x0C00: ('c', 1)}

# Property ids used here (names: the SC4 property names as the community tools list them; the meaning the
# converter needs is checked against the pack's own values, SC4_FORMATS.md 3).
PROP_NAMES = {
    0x00000010: 'Exemplar Type', 0x00000020: 'Exemplar Name', 0x00000021: 'Exemplar ID',
    0x27812810: 'Occupant Size', 0x27812832: 'Wealth', 0x27812833: 'Purpose', 0x27812834: 'Capacity Satisfied',
    0x27812837: 'Building Value', 0x27812840: 'Pollution at center', 0x27812851: 'Power Consumed',
    0x27812821: 'Resource Key Type 1', 0x2781284F: 'Occupant Groups?', 0x27812870: 'Item Name',
    0x88EDC789: 'Item Icon?', 0x8A2602B8: 'Occupant Types?', 0xAA1DD396: 'OccupantGroups',
    0xAA1DD397: 'SFX:Query Sound', 0x88EDC790: 'Item Order', 0x899AFBAD: 'Item Description Key',
    0xC8ED2D84: 'Bulldoze Cost', 0xE91A0B5F: 'Building value', 0x4A0F4C28: 'Is Conditional?',
    0x87CD6399: 'Capacity Satisfied', 0x0A1C8A5F: 'Occupant Groups?',
    0x88FCD877: 'LotConfigPropertySize', 0x88EDC793: 'LotConfigPropertyLotObject',
    0x88EDC795: 'LotConfigPropertyLotObject+', 0x88EDC796: 'LotConfigPropertyLotObject++',
    0x4A0F4C2E: 'Growth stage', 0x27812860: 'Max Slope?', 0x88EDC792: 'LotConfigPropertyZoneTypes',
    0x88EDC794: 'LotConfigPropertyWealthTypes', 0x88EDC791: 'LotConfigPropertyPurposeTypes',
    0x88EDC797: 'LotConfigPropertyLotObjectsTexture?', 0x49BEDA31: 'Item Description', 0x8A416A99: 'User Visible Name Key',
    0x0A3C1080: 'Is LotConfig?', 0x88EDC798: 'LotConfigPropertyRetainingWall?',
    0x8A2602A9: 'Lot Resource Key?', 0xCA2A5B0F: 'Query exemplar GUID?',
}


def parse_exemplar(b):
    sig = b[:8]
    if sig[:4] not in (b'EQZB', b'CQZB'):
        raise ValueError('not a binary exemplar: %r' % sig)
    parent = struct.unpack_from('<III', b, 8)
    n = struct.unpack_from('<I', b, 20)[0]
    p = 24
    props = {}
    order = []
    for _ in range(n):
        pid, vt, kt = struct.unpack_from('<IHH', b, p)
        p += 8
        fmt, sz = VT[vt]
        if kt == 0x80:
            p += 1
            cnt = struct.unpack_from('<I', b, p)[0]
            p += 4
            if vt == 0x0C00:
                val = b[p:p + cnt].decode('latin-1')
            else:
                val = list(struct.unpack_from('<%d%s' % (cnt, fmt), b, p))
            p += cnt * sz
        else:
            p += 1
            if vt == 0x0C00:
                raise ValueError('single string')
            val = struct.unpack_from('<' + fmt, b, p)[0]
            p += sz
        props[pid] = (vt, val)
        order.append(pid)
    return {'kind': sig[:4].decode(), 'parent': parent, 'props': props, 'order': order}


def ltext(b):
    n, mark = struct.unpack_from('<HH', b, 0)
    if mark == 0x1000:
        return b[4:4 + 2 * n].decode('utf-16-le')
    return b[4:4 + n].decode('latin-1')


def fmt_prop(pid, vt, val):
    name = PROP_NAMES.get(pid, '')
    if isinstance(val, list):
        if vt in (0x0300, 0x0200, 0x0100):
            v = '[' + ', '.join('0x%X' % x for x in val) + ']'
        else:
            v = repr(val)
    elif isinstance(val, int) and not isinstance(val, bool):
        v = '0x%X (%d)' % (val & 0xFFFFFFFF, val)
    else:
        v = repr(val)
    return '0x%08X %-32s %04X %s' % (pid, name, vt, v)
