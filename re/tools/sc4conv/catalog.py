#!/usr/bin/env python3
r"""catalog.py - task sc4conv (2026-11-18h): what SimCity 4 buildings a folder of plugin files holds.

Reads every DBPF file under a folder (.dat .sc4desc .sc4lot .sc4model), indexes all entries by TGI (a later file
wins, as SC4 loads plugins), then for each building exemplar (exemplar type 2) collects what the converter needs.
Property ids and what they hold in the JMyers pack (re/analysis/SC4_FORMATS.md 3; meaning checked on the pack's
values: the occupant size matches the S3D box, the model key names an S3D entry, the name key an LText entry):

  0x00000010 exemplar type (2 = building, 0x10 = lot configuration, 0x1E = prop, 0x11 = the foundation model)
  0x00000020 exemplar name (string)
  0x27812810 occupant size, 3 f32 (width x, height y, depth z, metres)
  0x27812821 model key {type 0x5AD0E817, group, base instance}: S3D views at base + zoom << 8 + rotation << 4
  0x27812832 wealth (u8: 1 / 2 / 3)       0x27812833 purpose (u8: 1 = residential in the pack)
  0x27812834 capacity, pairs {demand group, count}, e.g. {0x1010 (R$), 11}
  0x27812870 building family id(s): the lot's building row names this id, any member of the family grows there
  0x8A416A99 name key {0x2026960B, group, instance} -> LText (the in-game building name)
  0x88FCD877 foundation exemplar instance (the 'FND' model, group 0x361CF9D5)
  lot configuration: 0x88EDC790 lot size {width, depth} (u8 x 2), 0x27812837 growth stage (u8; the lot names
  'R$1_' / 'R$2_' / 'R$3_' agree on all 42 lots), 0x88EDC900.. 0x88EDCDFF lot objects (13 u32 each:
  type 0 = building, 1 = prop, 2 = texture, ...; +2 rotation 0-3; +3/+5 x/z centre in 1/65536 m; +6..+9 bounds;
  +12 the object's id: for type 0 the building family or building instance)
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dbpf as D  # noqa: E402
import exemplar as X  # noqa: E402

DBPF_EXT = ('.dat', '.sc4desc', '.sc4lot', '.sc4model')
LOTOBJ_FIRST, LOTOBJ_LAST = 0x88EDC900, 0x88EDCDFF
# Task sc4civ (2026-11-19l): the player's own SimCity 4 install as a source. A folder that holds SimCity_1.dat at its
# top is read as the game's own files only, in this order (no TGI is in two of them: 0 shared over the 7 files of the
# Steam SimCity 4 Deluxe), never its Plugins, Regions or other .dat (Intro.dat, Sound.dat, a shop plugin in Sku_Data).
INSTALL_FILES = ('SimCity_1.dat', 'SimCity_2.dat', 'SimCity_3.dat', 'SimCity_4.dat', 'SimCity_5.dat', 'EP1.dat',
                 'SimCityLocale.DAT')


def install_files(root):
    """The game files of an SC4 install folder, in INSTALL_FILES order (names matched without case; SimCityLocale.DAT
    from the first subfolder, in name order, when the top has none), or None when root is not an install."""
    if not os.path.isdir(root):
        return None
    top = {n.lower(): n for n in os.listdir(root) if os.path.isfile(os.path.join(root, n))}
    if INSTALL_FILES[0].lower() not in top:
        return None
    out = [os.path.join(root, top[n.lower()]) for n in INSTALL_FILES if n.lower() in top]
    if INSTALL_FILES[-1].lower() not in top:
        for d in sorted(n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n))):
            sub = {n.lower(): n for n in os.listdir(os.path.join(root, d))}
            if INSTALL_FILES[-1].lower() in sub:
                out.append(os.path.join(root, d, sub[INSTALL_FILES[-1].lower()]))
                break
    return out


def dbpf_files(root):
    if os.path.isfile(root):
        return [root]
    inst = install_files(root)
    if inst is not None:
        return inst
    out = []
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for n in sorted(fn):
            if n.lower().endswith(DBPF_EXT):
                out.append(os.path.join(dp, n))
    return out


class Index:
    """TGI -> (DBPF, entry) over many files; later files override earlier ones."""

    def __init__(self, root):
        self.files = []
        self.tgi = {}
        self.install = install_files(root) is not None     # task sc4civ: an SC4 install, not a download
        self._ex = {}
        for p in dbpf_files(root):
            try:
                f = D.DBPF(p)
            except (ValueError, struct.error) as e:
                print('  skip %s: %s' % (p, e))
                continue
            self.files.append(f)
            for e in f.entries:
                if e.type != D.T_DIR:
                    self.tgi[e.tgi] = (f, e)

    def read(self, tgi):
        f, e = self.tgi[tgi]
        return f.read(e)

    def has(self, tgi):
        return tgi in self.tgi

    def of_type(self, t):
        return [k for k in self.tgi if k[0] == t]

    def exemplar(self, tgi):
        if tgi not in self._ex:
            self._ex[tgi] = X.parse_exemplar(self.read(tgi))
        return self._ex[tgi]

    def full(self, tgi, depth=0):
        """Task sc4civ: the exemplar with its parent cohort's properties under its own (a parent of the index, 8 deep at
        most, as props.OwnSource.prop_value): 3,160 of SC4's own 8,957 exemplars name a parent, and 63 of its 113
        civic, park, reward and landmark buildings with a model hold their exemplar type (0x10) only there. A parent the
        index does not hold adds nothing (a download's cohort from another pack), so a download reads as before. -> exemplar dict."""
        ex = self.exemplar(tgi)
        par = tuple(ex['parent'])
        if not any(par) or depth >= 8 or not self.has(par):
            return ex
        try:
            pe = self.full(par, depth + 1)
        except (ValueError, KeyError, struct.error):
            return ex
        props = dict(pe['props'])
        props.update(ex['props'])
        order = list(pe['order']) + [k for k in ex['order'] if k not in pe['props']]
        return dict(ex, props=props, order=order)


# Task sc4civ: OccupantGroups (0xAA1DD396, u32 list): what SC4 files a building under. On its own buildings
# (SimCity_1.dat) 0x1005 civic, 0x1006 park, 0x150B reward, 0x150A landmark, 0x1500..0x1507 the service (police, jail,
# fire, school, college, library, museum, health). Counts and names: re/analysis/SC4_FORMATS.md 10.
P_GROUPS = 0xAA1DD396


def pv(ex, pid, default=None):
    v = ex['props'].get(pid)
    return default if v is None else v[1]


def as_list(v):
    return v if isinstance(v, list) else [v]


def sc(v):
    """Task sc4pass2: a one-value property stored as a list of one (the I-M pack's exemplar type, wealth, purpose:
    key type 0x80, count 1) -> the value."""
    return v[0] if isinstance(v, list) and len(v) == 1 else v


def buildings(idx):
    """-> list of building dicts, with the lots that grow them."""
    lots = []
    for k in idx.of_type(D.T_EXEMPLAR):
        try:
            ex = idx.full(k)
        except (ValueError, KeyError, struct.error):
            continue
        t = sc(pv(ex, 0x10))
        if t == 0x10:
            objs = []
            for pid in ex['order']:
                if LOTOBJ_FIRST <= pid <= LOTOBJ_LAST:
                    r = [x & 0xFFFFFFFF for x in as_list(pv(ex, pid))]
                    sgn = [x - (1 << 32) if x & 0x80000000 else x for x in r]
                    objs.append({'type': r[0], 'rot': r[2] & 3, 'x': sgn[3] / 65536.0, 'z': sgn[5] / 65536.0,
                                 'bounds': [sgn[6] / 65536.0, sgn[7] / 65536.0, sgn[8] / 65536.0, sgn[9] / 65536.0],
                                 'ids': r[12:]})
            sz = as_list(pv(ex, 0x88EDC790, [0, 0]))
            lots.append({'tgi': k, 'name': pv(ex, 0x20, ''), 'size': [int(sz[0]), int(sz[1])],
                         'stage': pv(ex, 0x27812837), 'objects': objs})
        elif t == 2:
            pass
    out = []
    for k in idx.of_type(D.T_EXEMPLAR):
        try:
            ex = idx.full(k)
        except (ValueError, KeyError, struct.error):
            continue
        if sc(pv(ex, 0x10)) != 2:
            continue
        rk = pv(ex, 0x27812821)
        if not rk or len(rk) < 3 or rk[0] != D.T_S3D:
            continue
        name_key = pv(ex, 0x8A416A99)
        title = None
        if name_key and len(name_key) == 3 and idx.has(tuple(name_key)):
            title = X.ltext(idx.read(tuple(name_key))).strip()
        fams = [x & 0xFFFFFFFF for x in as_list(pv(ex, 0x27812870, []))]
        cap = as_list(pv(ex, 0x27812834, []))
        b = {'tgi': k, 'name': pv(ex, 0x20, ''), 'title': title, 'model': tuple(rk[:3]),
             'size_m': [float(x) for x in as_list(pv(ex, 0x27812810, [0, 0, 0]))],
             'wealth': sc(pv(ex, 0x27812832)), 'purpose': sc(pv(ex, 0x27812833)),
             'capacity': [(cap[i], cap[i + 1]) for i in range(0, len(cap) - 1, 2)],
             'families': fams, 'foundation': pv(ex, 0x88FCD877), 'lots': [],
             'groups': [int(x) & 0xFFFFFFFF for x in as_list(pv(ex, P_GROUPS, [])) if isinstance(x, int)]}
        for lot in lots:
            for o in lot['objects']:
                if o['type'] == 0 and (k[2] in o['ids'] or any(f in o['ids'] for f in fams)):
                    b['lots'].append({'name': lot['name'], 'size': lot['size'], 'stage': lot['stage'],
                                      'rot': o['rot'], 'x': o['x'], 'z': o['z'],
                                      'via': 'family' if k[2] not in o['ids'] else 'building'})
        out.append(b)
    out.sort(key=lambda b: b['name'].lower())
    return out, lots


def others(idx):
    """Task sc4pass2 (2026-11-19f): what the converter does not convert but should name.
    -> (buildings without an S3D model key [{tgi, name, title, landmark, jobs}], prop exemplars with one
       {instance: {tgi, name, model}}).
    A building exemplar without a model key is drawn by a prop on its lot: the Global Office Center's ploppable
    ('Jobs') and landmark lots hold such a building (occupant size 1 x 0 x 1) and the tower as a lot prop (exemplar
    type 0x1E with the tower's model key). landmark = the building has property 0x2781284F (the JP Stevens landmark
    holds [85, 75] there, the jobs version does not), jobs = it has a capacity (0x27812834)."""
    blds, props = [], {}
    for k in idx.of_type(D.T_EXEMPLAR):
        try:
            ex = idx.full(k)
        except (ValueError, KeyError, struct.error):
            continue
        t = sc(pv(ex, 0x10))
        rk = pv(ex, 0x27812821)
        has_model = isinstance(rk, list) and len(rk) >= 3 and rk[0] == D.T_S3D
        if t == 0x1E and has_model:
            props[k[2]] = {'tgi': k, 'name': pv(ex, 0x20, ''), 'model': tuple(rk[:3])}
        elif t == 2 and not has_model:
            name_key = pv(ex, 0x8A416A99)
            title = None
            if name_key and isinstance(name_key, list) and len(name_key) == 3 and idx.has(tuple(name_key)):
                title = X.ltext(idx.read(tuple(name_key))).strip()
            blds.append({'tgi': k, 'name': pv(ex, 0x20, ''), 'title': title,
                         'landmark': 0x2781284F in ex['props'], 'jobs': 0x27812834 in ex['props'],
                         'groups': [int(x) & 0xFFFFFFFF for x in as_list(pv(ex, P_GROUPS, [])) if isinstance(x, int)]})
    return blds, props


def views(idx, b, zoom=4):
    """S3D keys of the four views (rotation 0-3) at a zoom (0-4 = SC4 zooms 1-5)."""
    t, g, base = b['model']
    return [(t, g, base + (zoom << 8) + (r << 4)) for r in range(4)]


def main(argv):
    root = argv[1]
    idx = Index(root)
    bs, lots = buildings(idx)
    print('%d files, %d entries, %d buildings, %d lots' % (len(idx.files), len(idx.tgi), len(bs), len(lots)))
    for b in bs:
        ok = all(idx.has(v) for v in views(idx, b))
        print('%-28s %-26r %s w%s p%s cap %s size %s lots %s views %s' % (
            b['name'], b['title'], '%08X/%08X' % b['model'][1:], b['wealth'], b['purpose'],
            b['capacity'], ['%.1f' % x for x in b['size_m']],
            ['%dx%d s%s r%d %s' % (l['size'][0], l['size'][1], l['stage'], l['rot'], l['via'][0]) for l in b['lots']],
            'ok' if ok else 'MISSING'))


if __name__ == '__main__':
    main(sys.argv)
