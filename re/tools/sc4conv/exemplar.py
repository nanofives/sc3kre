#!/usr/bin/env python3
r"""exemplar.py - task sc4conv (2026-11-18h): SimCity 4 exemplar / cohort and LText readers.

Binary exemplar (re/analysis/SC4_FORMATS.md 3):
  +0x00 'EQZB1###' (cohort: 'CQZB1###')   +0x08 parent cohort {type, group, instance}   +0x14 u32 property count
  property: u32 id, u16 value type, u16 key type (0x00 one value, 0x80 a list), u8 (0), [u32 count if 0x80], values
  value types: 0x0100 u8, 0x0200 u16, 0x0300 u32, 0x0700 s32, 0x0800 s64, 0x0900 f32, 0x0B00 bool, 0x0C00 string
  (a string is a list of count bytes)
Text exemplar ('EQZT1###', task sc4pass2 2026-11-19f: every exemplar of the Global Office Center and DiegoDL packs):
  lines 'ParentCohort=Key:{0x..,0x..,0x..}', 'PropCount=0x..', then one property per line
  '0x<id>:{"<name>"}=<Type>:<count>:{<values>}'. Type Uint8 / Uint16 / Uint32 / Sint32 / Sint64 / Float32 / Bool /
  String; count 0 = one value, else a list (a String is one quoted value, count 0 or its length). Integers are hex,
  Sint as the two's complement hex, floats decimal (read as float32, as the binary form stores them), Bool True /
  False. parse_exemplar returns the same dict shape for both forms.

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


TEXT_VT = {'uint8': 0x0100, 'uint16': 0x0200, 'uint32': 0x0300, 'sint32': 0x0700, 'sint64': 0x0800,
           'float32': 0x0900, 'bool': 0x0B00, 'string': 0x0C00}
TEXT_BITS = {0x0100: 8, 0x0200: 16, 0x0300: 32, 0x0700: 32, 0x0800: 64}


def _text_value(vt, tok):
    tok = tok.strip()
    if vt == 0x0900:
        try:
            return struct.unpack('<f', struct.pack('<f', float(tok)))[0]
        except OverflowError:
            raise ValueError('text exemplar: float out of range')
    if vt == 0x0B00:
        if tok.lower() in ('true', '1', '0x01'):
            return True
        if tok.lower() in ('false', '0', '0x00'):
            return False
        raise ValueError('text exemplar: bool %r' % tok)
    v = int(tok, 16) if tok.lower().startswith('0x') else int(tok)
    bits = TEXT_BITS[vt]
    v &= (1 << bits) - 1
    if vt in (0x0700, 0x0800) and v >> (bits - 1):
        v -= 1 << bits
    return v


def parse_text_exemplar(b):
    t = b.decode('latin-1')
    lines = [x.strip() for x in t.replace(chr(13), chr(10)).split(chr(10))]
    lines = [x for x in lines if x]
    parent = (0, 0, 0)
    props = {}
    order = []
    for ln in lines[1:]:
        if ln.startswith('ParentCohort='):
            ks = ln[ln.index('{') + 1:ln.rindex('}')].split(',')
            parent = tuple(int(k.strip(), 16) & 0xFFFFFFFF for k in ks[:3])
            continue
        if ln.startswith('PropCount='):
            continue
        c = ln.index(':')
        pid = int(ln[:c], 16) & 0xFFFFFFFF
        e = ln.index('}=', c)
        rest = ln[e + 2:]
        typ, cnt, vals = rest.split(':', 2)
        vt = TEXT_VT.get(typ.strip().lower())
        if vt is None:
            raise ValueError('text exemplar: value type %r' % typ)
        cnt = int(cnt, 16) if cnt.strip().lower().startswith('0x') else int(cnt)
        body = vals[vals.index('{') + 1:vals.rindex('}')]
        if vt == 0x0C00:
            q0, q1 = body.find('"'), body.rfind('"')
            val = body[q0 + 1:q1] if q0 >= 0 and q1 > q0 else body
        else:
            toks = [x for x in body.split(',') if x.strip()]
            vs = [_text_value(vt, x) for x in toks]
            if not cnt and not vs:
                raise ValueError('text exemplar: no value')
            val = vs if cnt else vs[0]
        props[pid] = (vt, val)
        order.append(pid)
    return {'kind': b[:4].decode(), 'parent': parent, 'props': props, 'order': order}


def parse_exemplar(b):
    sig = b[:8]
    if sig[:4] in (b'EQZT', b'CQZT'):
        return parse_text_exemplar(b)
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
