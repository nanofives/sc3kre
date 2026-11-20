#!/usr/bin/env python3
r"""props.py - task sc4props (2026-11-19g): an SC4 lot's props (fences, trees, cars) baked into the converted building.

SC3 growables have no prop layer: a lot is one sprite per view and zoom. So the props of the building's SC4 lot are
added to the building's own OBJ, at their lot positions, and bldimport draws them with the house in every SC3 view
and zoom. Each prop is an SC4 model like a building (re/analysis/SC4_FORMATS.md 9): its zoom-5 view models, each in
view space with the BAT's render of that view as its texture; per SC3 rotation slot the prop view whose SC4 camera is
nearest the slot's camera is used (as views.match_view does for the house), with its back walls + floor when it is a
7-vertex box (views.hidden_faces).

Steps (all plain float arithmetic in a fixed order; sc4web.js runs the same steps):

1. The lot. A building may grow on several SC4 lots; the props come from its smallest one (area, then the order
   catalog.buildings lists them). Lot objects of kind 1 are props: word 2 rotation, words 3 / 5 the centre, word 12
   the prop: an exemplar instance (type 0x1E) or a prop family (0x27812870). Task sc4ground (2026-11-20c): word 4 is the
   prop's height above the lot (2,431 prop rows on 815 of the install's lots, 0.25 to 324 m, none below 0; 0 on every
   JMyers and Global Office Center row): the wall and roof signs of SC4's shops and offices. It is added to the prop's y
   (before, the signs hung up to 5.5 m below the ground and bldrender lifted the whole lot by that much).
2. Resolve. The building's own download first, then the dependency packs (deps.DepsIndex), a later file winning as
   SC4 loads them. A family: its members, those active on DATE (below) only, sorted by instance; the row takes member
   number (row index in the lot's object list) mod count, so the choice is fixed and differs from row to row.
   Timed props (SimulatorDateInterval 0x0A751675 = 365 days: the seasonal trees, which a lot places as four props at
   one spot, one per season): kept when DATE falls in [SimulatorDateStart 0xCA7515CC (month, day), + duration
   0x4A764564 days). DATE = 1 July (SC3 has no seasons; its trees are summer green). Model: Resource Key Type 1
   (0x27812821); Type 4 (0x27812824, records of 8 words {state, 0, 0, 0, 0x27812821, type, group, instance}): the
   first record of state 0. Type 0 (0x27812820) is not read (98 of 17,410 BSC props).
   Task sc4baseprops (2026-11-19): the player's SimCity 4 install is the last source (sc4conv.py --sc4). SC4 has one
   exemplar space, so a family's members are pooled over all sources (resolve) and a prop's model is read from the
   first source holding its 4 views (plan: row 'msrc'), the prop's own source first (re/analysis/SC4_FORMATS.md 11).
3. Place. Lot frame -> building model frame: the house's lot row has rotation kb and centre (bx, bz); in the JMyers
   lots a house with kb = 2 faces the lot's +z edge (the street: the front setback is 13.3-13.7 m on every 1x2 and
   1x3 lot, the back yard 9-25 m), and the house model's front is +Z, so the lot frame turned by kb - 2 quarter turns
   is the model frame. A prop with rotation kp is turned kp - kb quarter turns (QUARTER below) and moved to its centre.
4. The SC3 lot window: an n x n x 16 m square in the model frame holding the house (task lotshape: a w x d lot, w
   along model x and d along z, for a landmark or reward on its SC4 lot, sc4conv.real_lot). Per axis: when the SC4 lot is no
   longer than the window, the window is centred on the SC4 lot (a 1-tile-wide lot keeps its exact width, the house
   off-centre as SC4 draws it); else across the street (x) the window is centred on the house and slid into the lot,
   along the depth (z) it starts at the house's back wall and keeps the front yard up to the street (the cars, the
   street fence), slid into the lot. A prop whose centre is outside is left out; one whose model reaches past the
   window by up to NUDGE_M (1 m: the fences on the SC4 lot's edge) is moved in, else left out (clipping a view box
   would cut away the faces some SC3 views see). One zero-area triangle spans the window's corners, so bldrender's
   centring (place: the bounding box centred on the lot) puts the window on the SC3 lot.
"""
import math
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dbpf as D  # noqa: E402
import exemplar as X  # noqa: E402
import fsh as FS  # noqa: E402
import views as V  # noqa: E402
from s3d import S3D  # noqa: E402

CELL_M = 16.0
ZOOM5 = 4
DATE = (7, 1)
MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
P_TYPE, P_NAME, P_SIZE, P_FAMILY = 0x10, 0x20, 0x27812810, 0x27812870
P_RKT0, P_RKT1, P_RKT4 = 0x27812820, 0x27812821, 0x27812824
P_INTERVAL, P_START, P_DURATION = 0x0A751675, 0xCA7515CC, 0x4A764564
# one quarter turn of a prop relative to the house, (x, z) -> QUARTER(x, z): the same turn as views.to_model
QUARTER = -1


def turn(x, z, q):
    """(x, z) turned q quarter turns (QUARTER = 1: (x, z) -> (z, -x) per step, as views.to_model; -1 the other way)."""
    for _ in range(q % 4):
        if QUARTER == 1:
            x, z = z, -x
        else:
            x, z = -z, x
    return x, z


def day_of_year(m, d):
    return sum(MONTH_DAYS[:max(0, min(12, int(m)) - 1)]) + int(d) - 1


# ---------------------------------------------------------------------------------------------- sources
class OwnSource:
    """The building's own download as a prop source (its prop exemplars, e.g. the JMyers houses as props)."""

    def __init__(self, idx):
        self.idx = idx
        self.props = {}
        self.cohorts = {}
        for k in idx.of_type(D.T_EXEMPLAR) + idx.of_type(D.T_COHORT):
            try:
                ex = idx.exemplar(k)
            except (ValueError, KeyError, struct.error, IndexError):
                continue
            rec = {'g': k[1], 'parent': list(ex['parent']),
                   'p': {'%08X' % p: v[1] for p, v in ex['props'].items()}}
            if k[0] == D.T_COHORT:
                self.cohorts[k] = rec
            else:
                t = ex['props'].get(P_TYPE)
                t = t[1] if t else None
                t = t[0] if isinstance(t, list) and len(t) == 1 else t
                if t == 0x1E:
                    self.props[k[2]] = rec
        self._fam = None

    def prop_value(self, inst, pid, default=None):
        rec, seen = self.props.get(inst), 0
        while rec is not None and seen < 8:
            v = rec['p'].get('%08X' % pid)
            if v is not None:
                return v
            par = tuple(rec['parent'])
            rec = self.cohorts.get(par) if any(par) else None
            seen += 1
        return default

    def family_members(self, fam):
        if self._fam is None:
            self._fam = {}
            for inst in self.props:
                v = self.prop_value(inst, P_FAMILY)
                for f in (v if isinstance(v, list) else [v] if v is not None else []):
                    self._fam.setdefault(f & 0xFFFFFFFF, []).append(inst)
            for v in self._fam.values():
                v.sort()
        return self._fam.get(fam, [])

    def has(self, tgi):
        return self.idx.has(tgi)

    def read(self, tgi):
        return self.idx.read(tgi)


def active(src, inst, date=DATE):
    iv = src.prop_value(inst, P_INTERVAL)
    if iv != 365:
        return True
    st = src.prop_value(inst, P_START)
    du = src.prop_value(inst, P_DURATION)
    if not isinstance(st, list) or len(st) < 2 or not isinstance(du, int):
        return True
    return (day_of_year(*date) - day_of_year(st[0], st[1])) % 365 < du


def model_of(src, inst):
    """-> ((type, group, instance) of the model, None) or (None, why)."""
    r1 = src.prop_value(inst, P_RKT1)
    if isinstance(r1, list) and len(r1) >= 3:
        return (r1[0] & 0xFFFFFFFF, r1[1] & 0xFFFFFFFF, r1[2] & 0xFFFFFFFF), None
    r4 = src.prop_value(inst, P_RKT4)
    if isinstance(r4, list) and len(r4) >= 8:
        recs = [r4[k:k + 8] for k in range(0, len(r4) - 7, 8)]
        ok = [r for r in recs if r[4] == P_RKT1]
        pick = next((r for r in ok if r[0] == 0), ok[0] if ok else None)
        if pick is not None:
            return (pick[5] & 0xFFFFFFFF, pick[6] & 0xFFFFFFFF, pick[7] & 0xFFFFFFFF), None
        return None, 'resource key type 4 without a type-1 record'
    if src.prop_value(inst, P_RKT0) is not None:
        return None, 'resource key type 0 (not read)'
    return None, 'no model key'


def owner(sources, inst):
    """The first source holding prop exemplar inst (the one SC4 uses: a plugin's exemplar replaces the game's)."""
    return next((s for s in sources if inst in s.props), None)


def resolve(sources, pid, row):
    """-> (source, instance, None) or (None, None, reason): reason 'missing' (in no pack), 'season' (a timed prop not
    shown on DATE), or a model problem.
    Task sc4baseprops: a family's members are pooled over all sources (SC4 has one exemplar space: the BSC pack adds
    502 cars to SimCity 4's own car family A0000038, which holds 23), each member read from its owner(), and a member
    counts only when its owner's exemplar still names the family."""
    s = owner(sources, pid)
    if s is not None:
        if not active(s, pid):
            return None, None, 'season'
        return s, pid, None
    cand = set()
    for s in sources:
        cand.update(s.family_members(pid))
    if not cand:
        return None, None, 'missing'
    live = []
    for m in sorted(cand):
        s = owner(sources, m)
        if m in s.family_members(pid) and active(s, m):
            live.append((s, m))
    if not live:
        return None, None, 'season'
    s, m = live[row % len(live)]
    return s, m, None


def view_keys(model, zoom=ZOOM5):
    t, g, i = model
    return [(t, g, i + (zoom << 8) + (r << 4)) for r in range(4)]


def choose_lot(b, lots):
    """The building's smallest SC4 lot (area, then catalog order) with its object list. -> (lot, house row) or None."""
    best = None
    for k, bl in enumerate(b['lots']):
        lot = next((l for l in lots if l['name'] == bl['name'] and l['size'] == bl['size']), None)
        if lot is None:
            continue
        row = next((o for o in lot['objects'] if o['type'] == 0), None)
        if row is None:
            continue
        key = (lot['size'][0] * lot['size'][1], k)
        if best is None or key < best[0]:
            best = (key, lot, row)
    return (best[1], best[2]) if best else None


# ---------------------------------------------------------------------------------------------- prop models
def prop_views(src, model, label):
    """-> 4 views (r = 0..3) {r, meshes: [(P model frame (list of [x, y, z]), UV, tris, fsh key)], fill: (P, UV,
    tris) or None, fill_key, az (camera azimuth, prop model frame)}. Raises ValueError when a view is missing."""
    out = []
    t, g, _ = model
    for r, key in enumerate(view_keys(model)):
        if not src.has(key):
            raise ValueError('%s: S3D %08X-%08X-%08X not found' % (label, key[0], key[1], key[2]))
        meshes = []
        for P, UV, tris, mat, _n in S3D(src.read(key)).meshes():
            if not mat['tex'] or not tris:
                continue
            fk = V.tex_key(src, g, mat['tex'][0]['id'])   # task sc4civ: SC4's own props keep theirs in 0x1ABE787D
            if not src.has(fk):
                raise ValueError('%s: texture %08X not found' % (label, fk[2]))
            meshes.append((P, UV, tris, fk))
        if not meshes:
            raise ValueError('%s view %d: no textured mesh' % (label, r))
        fill = None
        if len(meshes) == 1 and len(meshes[0][0]) == 7:
            P, UV, tris, fk = meshes[0]
            bm = FS.read_fsh(src.read(fk))[0]
            A, _err, d = V.fit_camera(P, UV, bm['w'], bm['h'])
            v = {'r': r, 'P_view': np.array(P, dtype=np.float64), 'A': A, 'tex_size': (bm['w'], bm['h']),
                 'cam': {'forward_view': d.tolist()}}
            fill = V.hidden_faces(v)
        ms = []
        for P, UV, tris, fk in meshes:
            Pm = V.to_model(P, r)
            ms.append(([[float(p[0]), float(p[1]), float(p[2])] for p in Pm], [[float(u[0]), float(u[1])] for u in UV],
                       [tuple(x) for x in tris], fk))
        if fill is not None:
            fP, fUV, ftris = fill
            fill = ([[float(p[0]), float(p[1]), float(p[2])] for p in fP], [[float(u[0]), float(u[1])] for u in fUV],
                    [tuple(x) for x in ftris])
        out.append({'r': r, 'meshes': ms, 'fill': fill, 'fill_key': meshes[0][3],
                    'az': (22.5 + 90.0 * r + 180.0) % 360.0 - 180.0})
    return out


def az_turned(az, q):
    """A camera azimuth (degrees from +z towards +x) after the scene is turned q quarter turns (turn())."""
    x, z = turn(math.sin(math.radians(az)), math.cos(math.radians(az)), q)
    return math.degrees(math.atan2(x, z))


def match_prop_view(pv, q, slot):
    a = V.SC3_SLOT_AZ[slot]
    return min(pv, key=lambda v: abs((az_turned(v['az'], q) - a + 180) % 360 - 180))


NUDGE_M = 1.0             # a prop reaching at most this far past the SC3 lot window is moved in, else left out


def nudge(lo, hi, w0, w1):
    """Shift that puts [lo, hi] inside [w0, w1], or None when it is more than NUDGE_M or the span does not fit."""
    if hi - lo > w1 - w0:
        return None
    d = 0.0
    if lo < w0:
        d = w0 - lo
    elif hi > w1:
        d = w1 - hi
    return d if abs(d) <= NUDGE_M else None


# ---------------------------------------------------------------------------------------------- the lot plan
def window_axis(L0, L1, h0, h1, S, front):
    if L1 - L0 <= S:
        c = (L0 + L1) / 2.0
        return c - S / 2.0, c + S / 2.0
    if front:
        w1 = min(L1, h0 + S)
        return w1 - S, w1
    c = (h0 + h1) / 2.0
    w0 = c - S / 2.0
    w0 = max(L0, min(w0, L1 - S))
    return w0, w0 + S


def plan(b, lots, sources, house_box, n):
    """-> plan dict: lot, window, rows [{row, id, inst, name, src, model, x, z, q, state}] or None when the building
    has no SC4 lot. house_box = (x0, x1, z0, z1) of the house in its model frame. state: 'ok', 'outside' (centre
    out of the SC3 window), 'missing', 'season', or a model problem."""
    got = choose_lot(b, lots)
    if got is None:
        return None
    lot, hrow = got
    kb = hrow['rot'] & 3
    W, Dp = lot['size'][0] * CELL_M, lot['size'][1] * CELL_M
    corners = [turn(cx - hrow['x'], cz - hrow['z'], -(kb - 2)) for cx, cz in ((0.0, 0.0), (W, Dp))]
    L = [min(corners[0][0], corners[1][0]), max(corners[0][0], corners[1][0]),
         min(corners[0][1], corners[1][1]), max(corners[0][1], corners[1][1])]
    if isinstance(n, (tuple, list)):      # task lotshape: (w, d) cells
        Sx, Sz = n[0] * CELL_M, n[1] * CELL_M
    else:
        Sx = Sz = n * CELL_M
    wx = window_axis(L[0], L[1], house_box[0], house_box[1], Sx, False)
    wz = window_axis(L[2], L[3], house_box[2], house_box[3], Sz, True)
    win = (wx[0], wx[1], wz[0], wz[1])
    rows = []
    for k, o in enumerate(lot['objects']):
        if o['type'] != 1 or not o['ids']:
            continue
        pid = o['ids'][0] & 0xFFFFFFFF
        s, inst, why = resolve(sources, pid, k)
        x, z = turn(o['x'] - hrow['x'], o['z'] - hrow['z'], -(kb - 2))
        r = {'row': k, 'id': pid, 'inst': inst, 'name': None, 'src': s, 'msrc': None, 'model': None, 'x': x, 'z': z,
             'y': o.get('y', 0.0), 'q': ((o['rot'] & 3) - kb) % 4, 'state': why or 'ok'}
        if s is not None:
            r['name'] = s.prop_value(inst, P_NAME) or '%08X' % inst
            m, mwhy = model_of(s, inst)
            if m is None:
                r['state'] = mwhy
            else:
                r['model'] = m
                # task sc4baseprops: the model from the first source holding its 4 views, the prop's own first (the
                # BSC prop CP_MaxisFluffyMed names SimCity 4's own S3D 1EDA0000, which only the install holds)
                vk = view_keys(m)
                r['msrc'] = next((s2 for s2 in [s] + [x for x in sources if x is not s]
                                  if all(s2.has(k2) for k2 in vk)), None)
                if r['msrc'] is None:
                    r['state'] = 'model not in the packs'
        if r['state'] == 'ok' and not (win[0] <= x <= win[1] and win[2] <= z <= win[3]):
            r['state'] = 'outside'
        rows.append(r)
    return {'lot': lot, 'house': hrow, 'kb': kb, 'window': win, 'lot_box': L, 'rows': rows}


def needed_keys(pl):
    """S3D keys of the placed props (for deps.DepsIndex.fetch)."""
    out = []
    for r in pl['rows']:
        if r['model'] is not None and r['state'] in ('ok', 'outside'):
            out += view_keys(r['model'])
    return out


def placed_meshes(pl, cache, fill=True):
    """-> per slot [(P, UV, tris, fsh key, src)] in the house's model frame, in row order. A prop whose model extent
    (all four views) reaches past the window by at most NUDGE_M is moved in (row 'nudge_m'), else its state becomes
    'outside'. cache: {(model, src id): prop_views or the error text}; a model that fails to load: 'unreadable'."""
    slots = [[] for _ in range(4)]
    x0w, x1w, z0w, z1w = pl['window']
    for r in pl['rows']:
        if r['state'] != 'ok':
            continue
        ck = (r['model'], id(r['msrc']))
        if ck not in cache:
            try:
                cache[ck] = prop_views(r['msrc'], r['model'], r['name'])
            except (ValueError, KeyError, IndexError, struct.error) as e:
                cache[ck] = str(e)
        pv = cache[ck]
        if isinstance(pv, str):
            r['state'] = 'unreadable'
            r['why'] = pv
            continue
        xs, zs = [], []
        for v in pv:
            for m in v['meshes']:
                for p in m[0]:
                    x, z = turn(p[0], p[2], r['q'])
                    xs.append(x + r['x'])
                    zs.append(z + r['z'])
        dx = nudge(min(xs), max(xs), x0w, x1w)
        dz = nudge(min(zs), max(zs), z0w, z1w)
        if dx is None or dz is None:
            r['state'] = 'outside'
            continue
        if dx or dz:
            r['nudge_m'] = [dx, dz]
        ox, oz = r['x'] + dx, r['z'] + dz
        oy = r['y']                       # task sc4ground: the lot row's height (word 4): the shop signs on the wall
        for slot in range(4):
            v = match_prop_view(pv, r['q'], slot)
            parts = [(m[0], m[1], m[2], m[3]) for m in v['meshes']]
            if fill and v['fill'] is not None:
                parts.append((v['fill'][0], v['fill'][1], v['fill'][2], v['fill_key']))
            for P, UV, tris, fk in parts:
                Pt = []
                for p in P:
                    x, z = turn(p[0], p[2], r['q'])
                    Pt.append([x + ox, p[1] + oy if oy else p[1], z + oz])
                slots[slot].append((Pt, UV, tris, fk, r['msrc']))
    return slots


def summary(pl):
    """-> x_sc4.props dict (without 'on')."""
    from collections import Counter
    st = Counter(r['state'] for r in pl['rows'])
    miss = Counter(r['id'] for r in pl['rows'] if r['state'] == 'missing')
    used = Counter(r['name'] for r in pl['rows'] if r['state'] == 'ok')
    w = pl['window']
    return {'lot': pl['lot']['name'], 'rows': len(pl['rows']), 'placed': st.get('ok', 0),
            'nudged': sum(1 for r in pl['rows'] if r['state'] == 'ok' and r.get('nudge_m')),
            'outside_sc3_lot': st.get('outside', 0), 'other_season': st.get('season', 0),
            'missing': st.get('missing', 0),
            'unreadable': sum(v for k, v in st.items() if k not in ('ok', 'outside', 'season', 'missing')),
            'window_m': [round(x, 2) for x in w],
            'used': [[k, v] for k, v in sorted(used.items())],
            'missing_ids': [['%08X' % k, v] for k, v in sorted(miss.items())]}
