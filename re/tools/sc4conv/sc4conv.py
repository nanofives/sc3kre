#!/usr/bin/env python3
r"""sc4conv.py - task sc4conv (2026-11-18h): SimCity 4 buildings -> OBJ + MTL + PNG + models.json for bldimport.

  py -3.12 re/tools/sc4conv/sc4conv.py <SC4 plugin folder or .dat> --out <folder> [--all] [--style baked|baked_raw|baked_sharp] [--no-fill]
  py -3.12 re/tools/sc4conv/sc4conv.py <SC4 plugin folder or .dat> --list
  ... --deps "<BSC Common Dependencies Pack V9e.zip>" [--deps <more>] [--deps-cache DIR] [--no-props]   (task sc4props)
  py -3.12 re/tools/sc4conv/sc4conv.py "<SimCity 4 install folder>" --out <folder>        (task sc4civ)
  ... --sc4 "<SimCity 4 install folder>"     SimCity 4's own props for a download's lots (task sc4baseprops)

Then, as for any models folder:   py -3.12 re/tools/bldimport/bldimport.py build <folder> --game <game>

The input is the player's own download. Its licence decides what may be done with the output: the JMyers pack's
terms allow changing it for yourself and forbid passing it on, so the output folder stays on the player's PC.

What one SC4 building becomes (re/analysis/SC4_FORMATS.md 7, decision renders in verify/sc4conv/RESULTS.md):

  <stem>.obj   the four zoom-5 view models (SC4 zoom 5 = S3D zoom index 4), each turned back into one model frame
               (metres, Y up, the SC4 'S' view's frontal wall = +Z = the front, as bldimport expects), one OBJ group
               per SC3 rotation slot: `sc3slot<r>` holds the SC4 view whose camera is 22.5 degrees from SC3 slot r
               (slot 0 <- E, 1 <- N, 2 <- W, 3 <- S). bldrender draws a group only in its slot. Each group also
               holds the box's two back walls and its floor (0.05 m up), uv from the same view's fitted
               projection: where a visible face is transparent (the house is not box-shaped) the ray reaches
               them and shows what the SC4 camera saw along that line (views.hidden_faces; off: --no-fill).
  <stem>_<S|W|N|E>.png  the BAT's own render of that view (the S3D texture, decoded from DXT1 / DXT3), with alpha:
               the texels outside the house are transparent and bldrender sees through them.
  <stem>.mtl   one material per view, map_Kd = the PNG.
  models.json  one entry per building: name from the LText, class 3100/3300/3500 (light) ... from wealth and
               capacity (class_for), lot from the footprint (lot_for), height_m from the occupant size, weight 1,
               x_bldrender.style = 'baked' (the light is painted into the SC4 texture) unless --style says otherwise,
               x_sc4 = where it came from. One colour per design is enabled (the k-th design its k-th colour, for variety) unless --all.

Lot props (task sc4props, 2026-11-19g, props.py / deps.py): the fences, trees, cars of the building's smallest SC4 lot,
found in the download or in the dependency packs given with --deps (read by streaming, indexed once and cached), are
placed at their lot positions and written with the house into <stem>_props.obj; models.json names that file while
x_sc4.props.on is true, x_sc4.props lists what was placed, left outside the 16 m SC3 lot, of another season and not
found; the report names every prop id found in no pack. <stem>.obj stays the house alone.
With --sc4 <the player's SimCity 4 install> (task sc4baseprops, 2026-11-19), the game's own props (shrubs, bushes,
trees, cars of SimCity_1.dat, their textures in SimCity_2..5.dat and EP1.dat) are one more prop source, after the
download and the --deps packs (SC4 loads its own files first, so a plugin's exemplar of the same id wins).
Lot textures (task sc4lottex, 2026-11-20, lottex.py): the driveways, paths, paving and flower beds of the same lot, from
the same sources, composited on the SC3 lot (SC4 grass left to SC3's lawn) into <stem>_lot.png and drawn by a ground
quad (OBJ group sc3ground): <stem>_lot.obj (the house and the textures) and <stem>_props_lot.obj (with the props too).
models.json 'file' follows the two switches x_sc4.props.on and x_sc4.textures.on (a rerun keeps the player's choice;
--no-textures writes them off): <stem>[_props][_lot].obj.

Civic buildings, parks, rewards and landmarks (task sc4civ, 2026-11-19l, re/analysis/SC4_FORMATS.md 10): a building
SC4 files under OccupantGroups 0x1005 (civic), 0x1006 (park), 0x150B (reward) or 0x150A (landmark) is written as the
matching bldimport plugin kind instead of a growable (service_for): civic and parks as "civic" looks of the SC3 button
for the same service (base, the base's lot), rewards as "reward" (lot = the smallest square, population from SC4's own
Lua reward condition when it counts the whole city, else REWARD_POP; year 0), landmarks as "landmark". The player's own
SC4 install (a folder holding SimCity_1.dat) is a source too: the game's 7 data files are read (memory-mapped, entries
read one by one) and only those buildings are converted.

Diagonal buildings (task sc4diag, 2026-11-19c): a house the SC4 author set at 45 degrees on its lot (its foundation
model's outline runs at 45 degrees, views.foundation_diagonal) is written with enabled false and a note, also with
--all, since SC3 has no diagonal buildings; a design whose picked colour is diagonal gets a non-diagonal colour
instead when it has one (pick_colours). --diagonal keeps them as any other building.
"""
import argparse
import json
import math
import os
import re
import shutil
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog as C  # noqa: E402
import deps as DP  # noqa: E402
import lottex as LT  # noqa: E402
import props as PR  # noqa: E402
import rewards as RW  # noqa: E402
import views as V  # noqa: E402

EDITABLE = ('name', 'class', 'lot', 'weight', 'enabled', 'scale', 'rotate_deg', 'notes', 'x_bldrender')
SERVICE_EDITABLE = ('kind', 'base', 'population', 'year', 'description')   # task sc4civ, the fields an entry has


def editable(e):
    """The fields a rerun keeps when the player changed them: EDITABLE, plus for a civic look / reward / landmark from
    SC4 (task sc4civ) those of SERVICE_EDITABLE it holds."""
    if 'service' not in e.get('x_sc4', {}):
        return EDITABLE
    return EDITABLE + tuple(k for k in SERVICE_EDITABLE if k in e)
CELL_M = 16.0             # bldimport's metres per lot cell (BUILDING_ART.md 4); an SC4 tile is 16 m as well
ZOOM5 = 4                 # S3D zoom index of SC4 zoom 5


PURPOSE_NAME = {2: 'service commercial', 3: 'office', 5: 'agriculture', 6: 'dirty industry', 7: 'manufacturing',
                8: 'high-tech industry'}


def class_for(b):
    """SC3 lot class (prop 0x65, batgrow.CLASS_LABEL) from SC4 purpose / wealth / capacity. -> (class, why).
    The density cuts are choices of this tool, not measured equivalences.
    Residential (purpose 1): capacity <= 60 -> light, <= 400 -> medium, else dense; wealth 1 / 2 / 3.
    Task sc4pass2 (2026-11-19f): commercial, SC4 service (CS, purpose 2) and office (CO, purpose 3): SC3 has one
    commercial zone for shops and offices and two commercial wealths (batgrow.CLASS_LABEL: 5100 / 5500 light, 5700 /
    6100 medium, 6300 / 6700 dense), so SC4 $ -> low and $$ / $$$ -> high; jobs <= 100 -> light, <= 1000 -> medium,
    else dense. Industry: agriculture (5) -> farm 9300, dirty (6) and manufacturing (7) -> dirty, high-tech (8) ->
    clean, the same job cuts. A building that needs a lot larger than 4x4 gets no class (SC3 lots are 1x1 to 4x4)."""
    w = b['wealth'] or 1
    cap = sum(c for _, c in b['capacity']) if b['capacity'] else 0
    p = b['purpose']
    n = lot_for(b)
    if p == 1:
        dens = 0 if cap <= 60 else (1 if cap <= 400 else 2)
        cls = (3100, 3700, 4300)[dens] + 200 * (min(max(w, 1), 3) - 1)
        why = 'SC4 residential, wealth %d, capacity %d -> %s density' % (w, cap, ('light', 'medium', 'dense')[dens])
    elif p in (2, 3):
        dens = 0 if cap <= 100 else (1 if cap <= 1000 else 2)
        hi = 1 if min(max(w, 1), 3) >= 2 else 0
        cls = ((5100, 5700, 6300), (5500, 6100, 6700))[hi][dens]
        why = ('SC4 %s, wealth %d, %d jobs -> commercial %s, %s wealth (SC3 has one commercial zone and two wealths:'
               ' SC4 $ -> low, $$ and $$$ -> high)' % (PURPOSE_NAME[p], w, cap, ('light', 'medium', 'dense')[dens],
                                                      ('low', 'high')[hi]))
    elif p in (5, 6, 7, 8):
        if p == 5:
            cls = 9300
            why = 'SC4 agriculture -> farm'
        else:
            dens = 0 if cap <= 100 else (1 if cap <= 1000 else 2)
            clean = 1 if p == 8 else 0
            cls = ((8100, 8300, 8500), (8700, 8900, 9100))[clean][dens]
            why = 'SC4 %s, %d jobs -> industrial %s, %s' % (PURPOSE_NAME[p], cap, ('dirty', 'clean')[clean],
                                                           ('light', 'medium', 'dense')[dens])
    else:
        return None, 'purpose %r: not mapped' % (p,)
    if n > 4:
        return None, why + '; it needs a %dx%d lot and SC3 lots are 1x1 to 4x4' % (n, n)
    if n not in CLASS_LOTS.get(cls, (n,)):
        alt = [c for c in CLASS_FALLBACK.get(cls, ()) if n in CLASS_LOTS.get(c, ())]
        if not alt:                       # task sc4ci: bldimport would skip it ("class 9300 has no 4x4 lot")
            return None, why + "; class %d has no %dx%d base in SC3 (bldimport's class table)" % (cls, n, n)
        why += '; class %d has no %dx%d base, %d does' % (cls, n, n, alt[0])
        if cls in DIRTY and alt[0] not in DIRTY:
            why += ' (SC3 has no %dx%d dirty industry base: the clean class, its pollution is lower)' % (n, n)
        cls = alt[0]
    return cls, why


# Square lot sizes with a stock base per class (batgrow.class_table on the 2026-11-18 release tree, commercial and
# industry read 2026-11-19f on the same tree). bldimport refuses a class without a base of the entry's lot size, so
# a building moves to the first class in CLASS_FALLBACK that has one (residential: the same wealth, medium density;
# commercial / industry: the same wealth or cleanliness, another density).
CLASS_LOTS = {3100: (1,), 3300: (1,), 3500: (1, 2), 3700: (2, 3), 3900: (2,),
              5100: (1,), 5500: (1, 2), 5700: (2, 3, 4), 6100: (2, 3), 6300: (2, 3), 6700: (3, 4),
              8100: (1,), 8300: (2,), 8500: (1, 2, 3), 8700: (1, 2), 8900: (2, 3), 9100: (3, 4), 9300: (1, 2, 3)}
CLASS_FALLBACK = {3100: (3700,), 3300: (3900,), 3500: (3500,),
                  5100: (5700, 6300), 5500: (6100, 6700), 5700: (6300, 5100), 6100: (6700, 5500),
                  6300: (5700, 5100), 6700: (6100, 5500),
                  8100: (8300, 8500, 9100), 8300: (8500, 8100, 9100), 8500: (8300, 8100, 9100),
                  8700: (8900, 9100), 8900: (9100, 8700), 9100: (8900, 8700)}
# Task sc4ci (2026-11-20): no dirty class has a 4x4 base (8100 1x1, 8300 2x2, 8500 1x1-3x3), so a 4x4 dirty or
# manufacturing building (7 of SC4's own) takes the dense clean class 9100 last (SC3Pollution.ini air 100 against
# 8500's 125, the nearest of the clean classes) instead of a class bldimport skips. verify/sc4ci/RESULTS.md 2.
DIRTY = (8100, 8300, 8500)


def lot_for(b):
    """Square SC3 lot from the footprint: the smallest n with both sides <= n x 16 m."""
    w, _, d = b['size_m']
    return max(1, int(math.ceil(max(w, d) / CELL_M - 1e-6)))


def design_of(name):
    m = re.match(r'JFM_(.+?)[ _](blue|blu|gray|gry|grey|green|grn|mauve|white|wht|yellow|yllw)(?=[ _]|$)', name, re.I)
    if m:
        return m.group(1).replace('_', ' '), m.group(2)
    m = re.match(r'JFM_([A-Za-z]+?)(Blue|Gray|Green|Mauve|White|Yellow)', name)
    if m:
        return m.group(1), m.group(2)
    return name, ''


def stem_of(name):
    return re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')


def pick_colours(groups, is_diag):
    """groups: [members] per design in first-seen order -> the member enabled per design (or None). The k-th
    design its k-th colour; task sc4diag: when that one is diagonal, the k-th of its non-diagonal colours, and none
    when every colour is diagonal."""
    out = []
    for k, members in enumerate(groups):
        c = members[k % len(members)]
        if is_diag(c):
            ok = [m for m in members if not is_diag(m)]
            c = ok[k % len(ok)] if ok else None
        out.append(c)
    return out


def diag_note(dg):
    return ('Diagonal, off by default: the SC4 author set this house at 45 degrees on its lot (its foundation %s'
            ' runs at 45 degrees for %d%% of its outline), and SC3 has no diagonal buildings. '
            % (dg['foundation'], int(round(dg['share_45'] * 100))))


def write_building(idx, b, out, enabled, style, fill=True, dg=None, keep_diag=False, versions=None, pctx=None):
    vs = V.load_views(idx, b, ZOOM5)
    stem = stem_of(b['name'])
    obj = ['# %s, converted from SimCity 4 by sc4conv.py (local use only: see the pack licence)' % b['name'],
           'mtllib %s.mtl' % stem]
    mtl = []
    vbase = 1
    for v in vs:
        png = '%s_%s.png' % (stem, v['name'])
        Image.fromarray(v['tex']).save(os.path.join(out, png))
        mtl += ['newmtl sc4_%s' % v['name'], 'Kd 1 1 1', 'map_Kd %s' % png, '']
    for slot in range(4):
        v = V.match_view(vs, slot)
        obj.append('g sc3slot%d' % slot)
        obj.append('usemtl sc4_%s' % v['name'])
        for p in v['P']:
            obj.append('v %.5f %.5f %.5f' % tuple(p))
        for uv in v['UV']:
            obj.append('vt %.6f %.6f' % (uv[0], 1.0 - uv[1]))
        for t in v['tris']:
            obj.append('f ' + ' '.join('%d/%d' % (vbase + i, vbase + i) for i in t))
        vbase += len(v['P'])
        hf = V.hidden_faces(v) if fill else None
        if hf is not None:              # back walls + floor of the same view: what shows through cut-outs
            P, UV, tris = hf
            for p in P:
                obj.append('v %.5f %.5f %.5f' % tuple(p))
            for uv in UV:
                obj.append('vt %.6f %.6f' % (uv[0], 1.0 - uv[1]))
            for t in tris:
                obj.append('f ' + ' '.join('%d/%d' % (vbase + i, vbase + i) for i in t))
            vbase += len(P)
    with open(os.path.join(out, stem + '.obj'), 'w', newline='\n') as fh:
        fh.write('\n'.join(obj) + '\n')
    with open(os.path.join(out, stem + '.mtl'), 'w', newline='\n') as fh:
        fh.write('\n'.join(mtl))
    svc = (pctx or {}).get('services', {}).get(b['tgi']) if pctx is not None else None
    n = svc['lot'] if svc else lot_for(b)
    pinfo, tinfo = write_props(b, vs, stem, obj, mtl, out, pctx, fill, n) if pctx is not None else (None, None)
    cls, why = class_for(b) if not svc else (None, svc['why'])
    design, colour = design_of(b['name'])
    title = (b['title'] or b['name']).splitlines()[0].strip().rstrip(',')
    sc4lots = sorted({'%dx%d' % tuple(sorted(l['size'])) for l in b['lots']})
    diag = bool(dg and dg['diagonal'])
    what = 'house' if b['purpose'] == 1 else 'building'
    entry = {
        'file': stem + '.obj', 'name': title, 'kind': 'growable', 'class': cls, 'lot': [n, n], 'weight': 1,
        'height_m': round(b['size_m'][1], 2), 'scale': 1.0, 'rotate_deg': 0, 'style': 'any',
        'enabled': bool(enabled and cls is not None and (keep_diag or not diag)),
        'notes': (diag_note(dg) if diag else '') + '%s. SC4 lots %s, the SC3 lot keeps the %s (%.1f x %.1f m) and drops the yard.'
                 % (why, ', '.join(sc4lots) or 'none', what, b['size_m'][0], b['size_m'][2]),
        'x_bldrender': {'style': style},
        'x_sc4': {'exemplar': b['name'], 'design': design, 'colour': colour,
                  'building_tgi': '%08X-%08X-%08X' % b['tgi'], 'model_key': '%08X-%08X-%08X' % b['model'],
                  'wealth': b['wealth'], 'purpose': b['purpose'],
                  'capacity': [['%04X' % g, c] for g, c in b['capacity']],
                  'family': ['%08X' % f for f in b['families']], 'size_m': [round(x, 3) for x in b['size_m']],
                  'lots': [{'size': l['size'], 'stage': l['stage'], 'name': l['name']} for l in b['lots']],
                  'diagonal': diag,
                  'foundation': ({'name': dg['foundation'], 'share_45': round(dg['share_45'], 2)} if dg else None),
                  'views': {'slot%d' % s: V.match_view(vs, s)['name'] for s in range(4)},
                  'camera': {v['name']: {'azimuth': round(v['cam']['azimuth_model'], 2),
                                         'elevation': round(v['cam']['elevation'], 2),
                                         'px_per_m': round(v['cam']['px_per_m'], 3)} for v in vs}},
    }
    if svc:                               # task sc4civ: a civic look, a reward or a landmark (service_for)
        entry['kind'] = svc['kind']
        entry['enabled'] = bool(enabled and svc['ok'] and (keep_diag or not diag))
        entry['notes'] = (diag_note(dg) if diag else '') + svc['note']
        if svc['kind'] == 'reward':
            entry['name'] = REWARD_NAME_RE.sub(' ', title).strip() or b['name']
        entry['x_sc4']['service'] = svc['x']
        for k in ('base', 'population', 'year', 'description'):
            if k in svc:
                entry[k] = svc[k]
    tiles = [v['tiles'] for v in vs]
    if max(tiles) > 1:                    # task sc4pass2: a tall building's views come in tiles (views.compose_tiles)
        entry['x_sc4']['tiles'] = {v['name']: v['tiles'] for v in vs}
    if versions:                          # task sc4pass2: the same model on ploppable / landmark lots (not converted)
        entry['x_sc4']['versions'] = versions
    if pinfo is not None:                 # task sc4props: the SC4 lot's props, baked into <stem>_props.obj
        entry['x_sc4']['props'] = pinfo
    if tinfo is not None:                 # task sc4lottex: the SC4 lot's textures, <stem>_lot.obj / _props_lot.obj
        entry['x_sc4']['textures'] = tinfo
    entry['file'] = file_for(stem, pinfo, tinfo)
    return entry


def file_for(stem, pinfo, tinfo):
    """Task sc4lottex: the OBJ the two switches name, <stem>[_props][_lot].obj."""
    return stem + ('_props' if pinfo and pinfo['on'] else '') + ('_lot' if tinfo and tinfo['on'] else '') + '.obj'


# ---------------------------------------------------------------------------------------------- task sc4props
# Lot props (round 2026-11-19g, props.py): the props of the building's smallest SC4 lot, found in the download or
# the dependency packs (--deps), placed at their lot positions in the house's model frame and written with the house
# into <stem>_props.obj (+ .mtl); <stem>.obj stays the house alone, byte for byte as before. models.json 'file'
# names the _props OBJ while x_sc4.props.on is true (the default when at least one prop is placed); a rerun keeps
# the player's x_sc4.props.on. Prop textures are written once per pack texture: sc4prop_<group>_<instance>.png.
def write_props(b, vs, stem, obj, mtl, out, pctx, fill, n=None):
    """-> (x_sc4.props, x_sc4.textures), either None. Task sc4lottex: the lot's textures too (write_lottex)."""
    n = lot_for(b) if n is None else n
    v0 = vs[0]['P']
    box = (float(v0[:, 0].min()), float(v0[:, 0].max()), float(v0[:, 2].min()), float(v0[:, 2].max()))
    pl = PR.plan(b, pctx['lots'], pctx['sources'], box, n)
    if pl is None:
        return None, None
    slots = PR.placed_meshes(pl, pctx['cache'], fill)
    info = PR.summary(pl)
    info = dict({'on': info['placed'] > 0 and not pctx.get('off')}, **info)
    pctx['plans'].append((b, pl))
    y0 = float(min(v['P'][:, 1].min() for v in vs))
    tinfo, lot_png = write_lottex(b, stem, obj, mtl, out, pctx, pl, n, y0)
    if not info['placed']:
        return info, tinfo
    pobj = [obj[0], 'mtllib %s_props.mtl' % stem] + obj[2:]
    pmtl = list(mtl)
    seen = set()
    vbase = sum(1 for ln in obj if ln.startswith('v '))
    tbase = sum(1 for ln in obj if ln.startswith('vt '))
    for slot in range(4):
        pobj.append('g sc3slot%d' % slot)
        cur = None
        for P, UV, tris, fk, src in slots[slot]:
            mname = 'sc4p_%08X_%08X' % (fk[1], fk[2])
            if mname not in seen:
                seen.add(mname)
                png = 'sc4prop_%08X_%08X.png' % (fk[1], fk[2])
                if png not in pctx['pngs']:
                    pctx['pngs'].add(png)
                    Image.fromarray(PR.FS.read_fsh(src.read(fk))[0]['image']).save(os.path.join(out, png))
                pmtl += ['newmtl ' + mname, 'Kd 1 1 1', 'map_Kd ' + png, '']
            if mname != cur:
                pobj.append('usemtl ' + mname)
                cur = mname
            for p in P:
                pobj.append('v %.5f %.5f %.5f' % (p[0], p[1], p[2]))
            for uv in UV:
                pobj.append('vt %.6f %.6f' % (uv[0], 1.0 - uv[1]))
            for t in tris:
                pobj.append('f ' + ' '.join('%d/%d' % (vbase + 1 + i, tbase + 1 + i) for i in t))
            vbase += len(P)
            tbase += len(UV)
    x0, x1, z0, z1 = pl['window']
    pobj += ['g sc4lot', 'usemtl sc4lot',
             'v %.5f %.5f %.5f' % (x0, y0, z0), 'v %.5f %.5f %.5f' % (x1, y0, z1), 'v %.5f %.5f %.5f' % (x1, y0, z1),
             'f %d %d %d' % (vbase + 1, vbase + 2, vbase + 3)]
    pmtl += ['newmtl sc4lot', 'Kd 1 1 1', '']
    with open(os.path.join(out, stem + '_props.obj'), 'w', newline='\n') as fh:
        fh.write('\n'.join(pobj) + '\n')
    with open(os.path.join(out, stem + '_props.mtl'), 'w', newline='\n') as fh:
        fh.write('\n'.join(pmtl))
    if lot_png:                           # task sc4lottex: the house, the props and the lot textures
        write_with_quad(out, stem + '_props_lot', pobj, pmtl, lot_png, pl, y0)
    return info, tinfo


# ---------------------------------------------------------------------------------------------- task sc4lottex
# Lot textures (round 2026-11-19l, lottex.py): the texture rows of the same SC4 lot as the props, composited on the SC3
# lot window into <stem>_lot.png (SC4 grass cleared: SC3's lawn shows there) and drawn by one quad in the OBJ group
# sc3ground, which bldrender lights as its own lawn. <stem>_lot.obj = the house + the quad, <stem>_props_lot.obj = the
# house, the props and the quad (written by write_props when props are placed). On when any texel is drawn.
def write_lottex(b, stem, obj, mtl, out, pctx, pl, n, y0):
    """-> (x_sc4.textures or None, the PNG name when something is drawn, else None)."""
    rows = LT.plan(pl, pctx['sources'])
    if not rows:
        return None, None
    img, stats = LT.composite(pl, rows, n, pctx['texcache'])
    t = LT.summary(pl, rows, stats)
    drawn = stats['drawn'] > 0
    tinfo = dict({'on': drawn and not pctx.get('tex_off')}, **t)
    pctx['tplans'].append((b, rows, stats))
    if not drawn:
        return tinfo, None
    png = stem + '_lot.png'
    Image.fromarray(img, 'RGBA').save(os.path.join(out, png))
    write_with_quad(out, stem + '_lot', obj, mtl, png, pl, y0)
    return tinfo, png


def write_with_quad(out, name, lines, mtl, png, pl, y0):
    """<name>.obj / .mtl = the given OBJ lines (their mtllib renamed) + the ground quad, the MTL + its material."""
    lines = [lines[0], 'mtllib %s.mtl' % name] + list(lines[2:])
    vb = sum(1 for ln in lines if ln.startswith('v '))
    tb = sum(1 for ln in lines if ln.startswith('vt '))
    qo, qm = LT.quad_lines(pl, y0 + LT.Y_LIFT, vb, tb, png)
    with open(os.path.join(out, name + '.obj'), 'w', newline='\n') as fh:
        fh.write('\n'.join(lines + qo) + '\n')
    with open(os.path.join(out, name + '.mtl'), 'w', newline='\n') as fh:
        fh.write('\n'.join(list(mtl) + qm))


def tex_notes(tplans):
    """Report lines for the lot textures of every converted building (sc4web.js texNotes: the same text)."""
    from collections import Counter
    if not tplans:
        return []
    st, miss = Counter(), Counter()
    for _b, rows, _s in tplans:
        for r in rows:
            st[r['state']] += 1
            if r['state'] == 'missing':
                miss[r['id']] += 1
    tot = sum(st.values())
    nb = sum(1 for _b, _r, s in tplans if s['drawn'] > 0)
    lines = ['Lot textures: %d of %d texture rows drawn (%s), %d of them cut at the SC3 lot edge, %d outside the SC3 lot,'
             ' %d in no pack given, %d unreadable' % (st['ok'] + st['cut'], tot, nw(nb, 'building', 'buildings'),
                                                    st['cut'], st['outside'], st['missing'], st['unreadable'])]
    if miss:
        lines.append('Textures not found (%d ids, rows in brackets): %s'
                     % (len(miss), ', '.join('%08X (%d)' % (k, v)
                                             for k, v in sorted(miss.items(), key=lambda kv: (-kv[1], kv[0])))))
    return lines


def props_notes(plans, sc4=False):
    """Report lines for the lot props of every converted building (sc4web.js propsNotes: the same text)."""
    from collections import Counter
    if not plans:
        return []
    st, miss = Counter(), Counter()
    for _b, pl in plans:
        for r in pl['rows']:
            st[r['state'] if r['state'] in ('ok', 'outside', 'season', 'missing') else 'unreadable'] += 1
            if r['state'] == 'missing':
                miss[r['id']] += 1
    tot = sum(st.values())
    nb = sum(1 for _b, pl in plans if any(r['state'] == 'ok' for r in pl['rows']))
    lines = ['Lot props: %d of %d prop rows placed (%s), %d outside the SC3 lot, %d of another season, %d in no pack'
             ' given, %d without a readable model' % (st['ok'], tot, nw(nb, 'building', 'buildings'), st['outside'], st['season'],
                                        st['missing'], st['unreadable'])]
    if miss:
        lines.append("Props not found (%d ids, rows in brackets; %s): %s"
                     % (len(miss), 'a dependency not given' if sc4 else "SimCity 4's own props or a dependency not given",
                        ', '.join('%08X (%d)' % (k, v)
                                             for k, v in sorted(miss.items(), key=lambda kv: (-kv[1], kv[0])))))
    return lines


def props_context(idx, bs, lots, deps, cache, fill, off=False, log=print, services=None, sc4=None, tex_off=False):
    """Task sc4props: the prop sources (the download, then each --deps pack) and one fetch of every prop model the
    buildings' lots place, before any building is written. Task sc4baseprops: sc4 = the player's SimCity 4 install,
    the last source (its own props; read in place, memory-mapped)."""
    sources = [PR.OwnSource(idx)] + [DP.DepsIndex(d, cache, log=log) for d in deps]
    with_sc4 = sc4 is not None and not idx.install
    if with_sc4:
        src = PR.OwnSource(C.Index(sc4))
        log('SimCity 4 install as a prop source: %d prop exemplars, %d cohorts' % (len(src.props), len(src.cohorts)))
        sources.append(src)
    ctx = {'lots': lots, 'sources': sources, 'cache': {}, 'pngs': set(), 'plans': [], 'off': off,
           'services': services or {}, 'sc4': with_sc4, 'texcache': {}, 'tplans': [], 'tex_off': tex_off}
    want = {}
    for b in bs:
        try:
            v0 = V.load_views(idx, b, ZOOM5)[0]['P']
        except ValueError:
            continue
        box = (float(v0[:, 0].min()), float(v0[:, 0].max()), float(v0[:, 2].min()), float(v0[:, 2].max()))
        svc = services.get(b['tgi']) if services else None
        pl = PR.plan(b, lots, sources, box, svc['lot'] if svc else lot_for(b))
        if pl is None:
            continue
        for r in pl['rows']:
            if r['state'] == 'ok' and isinstance(r['msrc'], DP.DepsIndex):
                want.setdefault(id(r['msrc']), (r['msrc'], set()))[1].update(PR.view_keys(r['model']))
        for r in LT.plan(pl, sources):    # task sc4lottex: the lot textures drawn on the SC3 lot
            if r['state'] in ('ok', 'cut') and isinstance(r['src'], DP.DepsIndex):
                want.setdefault(id(r['src']), (r['src'], set()))[1].add(LT.tex_key(r['id']))
    for s, keys in want.values():
        s.fetch(sorted(keys))
    return ctx


# ---------------------------------------------------------------------------------------------- task sc4pass2
# Lot-only packs (round 2026-11-19f). DiegoDL's growable pack holds lots and building descriptions whose models are
# separate downloads; the I-M pack holds lots on a blank placeholder model with SC4's own buildings as lot props.
# The converter says so, names the buildings, quotes the readme's dependency list, and writes nothing when no
# building converts (sc4web.js runs the same steps, its report lines are the same text).
README_RE = re.compile(r'readme', re.I)
README_EXT = ('.htm', '.html', '.txt')
WS_RE = re.compile(r'[ \t\r\n\f\v]+')
ENTITIES = {'amp': '&', 'lt': '<', 'gt': '>', 'quot': '"', 'apos': "'", 'nbsp': ' '}


def unentity(s):
    """The few HTML entities a readme uses (sc4web.js unentity: the same table)."""
    def one(m):
        k = m.group(1)
        if k[0] == '#':
            try:
                c = int(k[2:], 16) if k[1:2] in ('x', 'X') else int(k[1:])
                return chr(c) if 0 < c < 0x110000 else m.group(0)
            except ValueError:
                return m.group(0)
        return ENTITIES.get(k.lower(), m.group(0))
    return re.sub(r'&(#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z]+);', one, s)


def flat(s):
    return WS_RE.sub(' ', unentity(re.sub(r'<[^>]*>', ' ', s))).strip(' ')


def readme_deps(text):
    """The dependency list of a readme: after the first 'Dependenc' (any case), the <li> items of the next <ul> as
    (text, first href); a text readme: the lines after it that hold 'http'. -> [(name, url)]"""
    low = text.lower()
    i = low.find('dependenc')
    if i < 0:
        return []
    u = low.find('<ul', i)
    out = []
    if u >= 0:
        e = low.find('</ul>', u)
        seg = text[u:e if e >= 0 else len(text)]
        for it in re.findall(r'<li\b[^>]*>(.*?)</li>', seg, re.S | re.I):
            h = re.search(r'href\s*=\s*"([^"]*)"', it, re.I)
            name = flat(it)
            if name:
                out.append((name, unentity(h.group(1)) if h else ''))
        return out
    for ln in text[i:].splitlines()[1:]:
        if 'http' in ln:
            out.append((WS_RE.sub(' ', ln).strip(' '), ''))
    return out


def readme_files(src):
    """Readme files under the input, in the plugin walk order (catalog.dbpf_files)."""
    if os.path.isfile(src):
        return []
    out = []
    for dp, dn, fn in os.walk(src):
        dn.sort()
        for n in sorted(fn):
            if README_RE.search(n) and n.lower().endswith(README_EXT):
                out.append(os.path.join(dp, n))
    return out


def nw(n, one, many):
    return '%d %s' % (n, one if n == 1 else many)


def label_of(b):
    lines = (b.get('title') or b['name'] or '').splitlines()
    return lines[0].strip().rstrip(',') if lines else b['name']


def pack_notes(idx, bs, states, lots, deps):
    """-> (report lines, missing [{name, exemplar, reason, lots}], versions {building tgi: [..]}).
    states: {tgi: (state, why)} from views.model_state."""
    lines, missing = [], []
    conv = [b for b in bs if states[b['tgi']][0] == 'ok']
    gone = [b for b in bs if states[b['tgi']][0] == 'missing']
    blank = [b for b in bs if states[b['tgi']][0] == 'blank']
    for b in gone + blank:
        missing.append({'name': label_of(b), 'exemplar': b['name'], 'reason': states[b['tgi']][0],
                        'lots': [l['name'] for l in b['lots']]})
    known = set()
    for b in bs:
        known.add(b['tgi'][2])
        known.update(b['families'])
    oblds, props = C.others(idx)
    for ob in oblds:
        known.add(ob['tgi'][2])
    unres = []
    for lot in lots:
        for o in lot['objects']:
            if o['type'] == 0 and o['ids'] and not any(i in known for i in o['ids']):
                unres.append('%s (building %s)' % (lot['name'], ', '.join('%08X' % i for i in o['ids'])))
    # ploppable / landmark versions: a lot whose building has no model and whose props hold a converted model
    versions = {}
    by_model = {}
    for b in conv:
        by_model.setdefault(b['model'], b)
    for lot in lots:
        bld = None
        for o in lot['objects']:
            if o['type'] == 0:
                bld = next((ob for ob in oblds if ob['tgi'][2] in o['ids']), None)
        if bld is None:
            continue
        for o in lot['objects']:
            if o['type'] != 1:
                continue
            for i in o['ids']:
                pr = props.get(i)
                b = by_model.get(pr['model']) if pr else None
                if b is not None:
                    versions.setdefault(b['tgi'], []).append(
                        {'lot': lot['name'], 'kind': 'landmark' if bld['landmark'] else 'ploppable',
                         'building': label_of(bld), 'jobs': bool(bld['jobs']), 'exemplar': bld['name'],
                         'building_tgi': '%08X-%08X-%08X' % bld['tgi']})
    if not conv:
        lines.append('No building converted: this download holds no building models, only %s and %s'
                     % (nw(len(lots), 'lot', 'lots'), nw(len(bs) + len(oblds), 'building description', 'building descriptions')))
    if gone:
        lines.append('%d %s their model from a separate download: %s'
                     % (len(gone), 'buildings need' if len(gone) > 1 else 'building needs',
                        ', '.join(label_of(b) for b in gone)))
    if deps:
        lines.append("The download's readme lists the models to get: %s"
                     % ', '.join('%s (%s)' % (n, u) if u else n for n, u in deps))
    for b in blank:
        ln = [l['name'] for l in b['lots']]
        lines.append('%d %s use %s, a blank placeholder building: what shows in SimCity 4 is lot props (SimCity 4\'s'
                     ' own buildings or other downloads), not in this download: %s'
                     % (len(ln), 'lots' if len(ln) != 1 else 'lot', label_of(b), ', '.join(ln) or 'no lot'))
    if unres:
        lines.append('%d %s a building that is not in this download: %s'
                     % (len(unres), 'lots name' if len(unres) > 1 else 'lot names', ', '.join(unres)))
    for b in conv:
        vs = versions.get(b['tgi'])
        if vs:
            n = lot_for(b)
            if n not in LANDMARK_LOTS:
                tail = 'not converted: SC3 landmarks are 1x1 to 4x4 and this building needs %dx%d' % (n, n)
            else:
                on = [v['lot'] for v in vs if version_on(vs, v, n)]
                off = [v['lot'] for v in vs if not version_on(vs, v, n)]
                tail = ('converted as %s for the landmark menu (kind landmark), %s on'
                        % ('SC3 landmarks' if len(vs) > 1 else 'an SC3 landmark', ', '.join(on) or 'none'))
                if off:
                    tail += ', %s off (the same building again, and SC3 landmarks have no jobs)' % ', '.join(off)
            lines.append('%s also comes as %s: %s'
                         % (label_of(b), ', '.join('the %s lot %s (building %s)' % (v['kind'], v['lot'], v['building'])
                                                   for v in vs), tail))
    return lines, missing, versions


# ---------------------------------------------------------------------------------------------- task sc4civ
# SC4's civic buildings, parks, rewards and landmarks (round 2026-11-19l, re/analysis/SC4_FORMATS.md 10). The groups
# below are what SC4's own 744 buildings carry in OccupantGroups (0xAA1DD396); the SC3 side is bldimport's plugin kinds
# (CIVIC_REWARD.md 3: a civic look keeps the stock building's type, coverage and price on the base's own lot).
G_CIVIC, G_PARK, G_REWARD, G_LANDMARK = 0x1005, 0x1006, 0x150B, 0x150A
CIVIC_SERVICE = {0x1500: 'police', 0x1501: 'jail', 0x1502: 'fire', 0x1503: 'school', 0x1504: 'college',
                 0x1505: 'library', 0x1506: 'museum', 0x1507: 'hospital', 0x1702: 'zoo'}
# the stock lot of each bldimport civic base (the exemplars the 17 plain civic commands build, CIVIC_REWARD.md 1)
CIVIC_LOT = {'police': 3, 'jail': 3, 'fire': 3, 'hospital': 3, 'school': 3, 'college': 3, 'library': 2, 'museum': 3,
             'small_park': 1, 'big_park': 3, 'zoo': 4, 'baseball': 4, 'playground': 2, 'pond': 2, 'fountain': 1,
             'bus_stop': 1, 'train_station': 2}
CIVIC_LABEL = {'police': 'Police Station', 'jail': 'Jail', 'fire': 'Fire Station', 'hospital': 'Hospital',
               'school': 'School', 'college': 'College', 'library': 'Library', 'museum': 'Museum',
               'small_park': 'Small Park', 'big_park': 'Big Park', 'zoo': 'Zoo', 'baseball': 'Baseball Field',
               'playground': 'Playground', 'pond': 'Pond', 'fountain': 'Fountain', 'bus_stop': 'Bus Stop',
               'train_station': 'Train Station'}
# SC4 gives a park no service group (its parks carry 0x1005 / 0x1006 only), so a park's SC3 button comes from words of
# its SC4 name, else from its footprint: the Small Park when it fits 1x1, the Big Park when it fits 3x3
PARK_WORDS = (('softball', 'baseball'), ('baseball', 'baseball'), ('playground', 'playground'), ('fountain', 'fountain'),
              ('pond', 'pond'), ('zoo', 'zoo'))
REWARD_POP = 20000         # bldimport's own default population of a reward (REWARD in bldimport.py)
REWARD_NAME_RE = re.compile(r'[;=\r\n]+')    # a reward row cannot hold these (bldimport refuses them)
SC4_DESC = 'From SimCity 4'


def groups_hex(gs):
    return ['%04X' % g if g < 0x10000 else '%08X' % g for g in gs]


def reward_words(r):
    """The SC4 reward condition in words, for the card's note."""
    if not r:
        return ''
    cmp_ = ', '.join('%s %s' % (m, v) for m, v in r['compares']) or 'no population'
    oth = ', '.join(r['others'])
    return 'SC4 offers it as a reward when %s%s' % (cmp_, (' (also: %s)' % oth) if oth else '')


def service_for(b, rw):
    """-> None (not a civic / park / reward / landmark building: the growable rules) or {kind, lot, ok, why, note, x,
    base | population + year | description}."""
    gs = b.get('groups') or []
    if G_LANDMARK in gs:
        sk = 'landmark'
    elif G_REWARD in gs:
        sk = 'reward'
    elif G_PARK in gs:
        sk = 'park'
    elif G_CIVIC in gs:
        sk = 'civic'
    else:
        return None
    n = lot_for(b)
    title = label_of(b)
    svc = [CIVIC_SERVICE[g] for g in gs if g in CIVIC_SERVICE]
    r = rw.get(b['tgi'][2])
    x = {'sc4_kind': sk, 'groups': groups_hex(gs)}
    if r:
        x['reward'] = {'advisor': r['advisor'], 'compares': [[m, v] for m, v in r['compares']], 'others': r['others']}
    size = 'footprint %.1f x %.1f m' % (b['size_m'][0], b['size_m'][2])
    rwn = reward_words(r)
    if sk == 'civic' and not svc:
        sk = 'landmark'
        why0 = 'SC4 civic building (group 1005) of no service SC3 has a button for'
    else:
        why0 = None
    if sk in ('civic', 'park'):
        if sk == 'park':
            low = title.lower()
            word = next((w for w, _bs in PARK_WORDS if w in low), None)
            base = dict(PARK_WORDS)[word] if word else ('small_park' if n <= 1 else 'big_park')
            why = ('SC4 park (group 1006), its name says %s: SC3 %s' % (word, CIVIC_LABEL[base]) if word else
                   'SC4 park (group 1006), %s: SC3 %s' % (size, CIVIC_LABEL[base]))
        else:
            base = svc[0]
            why = 'SC4 civic building, service %s (groups %s): SC3 %s' % (base, ', '.join(groups_hex(gs)),
                                                                          CIVIC_LABEL[base])
        bl = CIVIC_LOT[base]
        ok = n <= bl
        note = ('%s. A look of the SC3 %s button: the stock building\'s type, coverage and price on its %dx%d lot.'
                % (why, CIVIC_LABEL[base], bl, bl))
        if not ok:
            note += ' Off: its %s needs %dx%d.' % (size, n, n)
        if rwn:
            note += ' %s; in SC3 it is a look like the others.' % rwn
        return {'kind': 'civic', 'base': base, 'lot': bl, 'ok': ok, 'why': why, 'note': note, 'x': x}
    if sk == 'reward':
        pop = r['population'] if r and r['population'] is not None else None
        why = 'SC4 reward (group 150B)'
        if svc:
            why += ', also SC4 %s service' % '/'.join(svc)
        ok = n in LANDMARK_LOTS
        if pop is not None:
            popw = 'SC3 population %d (%s)' % (pop, r['measure'])
        else:
            popw = ('SC3 population %d, the default: %s' % (REWARD_POP, 'no SC4 condition counts the whole city'
                                                              if r else 'no SC4 reward condition found'))
        note = '%s. %s. %s, year 0 (no SC4 reward condition reads the year).' % (
            why, rwn or 'No SC4 reward record', popw)
        if svc and svc[0] in CIVIC_LOT:
            note += ' As a look of the SC3 %s button instead: kind civic, base %s.' % (CIVIC_LABEL[svc[0]], svc[0])
        if not ok:
            note += ' Off: its %s needs %dx%d and SC3 rewards are 1x1 to 4x4.' % (size, n, n)
        return {'kind': 'reward', 'lot': n, 'ok': ok, 'why': why, 'note': note, 'x': x,
                'population': pop if pop is not None else REWARD_POP, 'year': 0, 'description': SC4_DESC}
    why = why0 or 'SC4 landmark (group 150A)'
    ok = n in LANDMARK_LOTS and not why0
    note = '%s: an SC3 landmark (the landmark menu, one per city).' % why
    if why0:
        note += ' Off: SC3 has no button for it.'
    elif not ok:
        note += ' Off: its %s needs %dx%d and SC3 landmarks are 1x1 to 4x4.' % (size, n, n)
    return {'kind': 'landmark', 'lot': n, 'ok': ok, 'why': why, 'note': note, 'x': x, 'description': SC4_DESC}


def design_key(b, services):
    """One design = one enabled entry (main). A growable: its SC4 family, else its JMyers design name. Task sc4civ: a
    civic look / reward / landmark: its SC4 name (SC4's own 3 Private Schools, 4 Houses of Worship, 3 Cemeteries, 3 City
    Halls, 2 x 4 Mayor's Statues share a name and one is on)."""
    if b['tgi'] in services:
        return ('sc4', services[b['tgi']]['kind'], label_of(b).lower())
    return tuple(b['families']) or design_of(b['name'])[0].lower()


def install_notes(idx, n_all, bs, others_, grow=()):
    """Report lines for an SC4 install (sc4web.js installNotes: the same text). Task sc4ci: grow = the commercial and
    industrial growables converted with --growables (not counted in bs)."""
    nolook = [o for o in others_ if any(g in o['groups'] for g in (G_CIVIC, G_PARK, G_REWARD, G_LANDMARK))]
    lines = ['SimCity 4 install: %d of its %d buildings are civic buildings, parks, rewards or landmarks with a model;'
             ' the others (homes, shops, offices, industry, utilities, transport) are not converted from an install'
             % (len(bs), n_all)]
    if nolook:
        lines.append('%d more civic buildings, parks, rewards or landmarks have no model of their own (their look is lot'
                     ' props), not converted: %s' % (len(nolook), ', '.join(label_of(o) for o in nolook)))
    if grow:
        cnt = [(p, sum(1 for b in grow if b['purpose'] == p)) for p in GROW_PURPOSES]
        lines.append('For testing, %d of its shops, offices, industry and farms (SimCity 4 growables) are converted too,'
                     ' all off: %s' % (len(grow), ', '.join('%d %s' % (k, GROW_LABEL[p][k != 1]) for p, k in cnt if k)))
    return lines


# Task sc4ci (2026-11-20): SimCity 4's own commercial and industrial growables from the install (--growables, the
# page's opt.growables): purpose 2 service commercial, 3 office, 5 agriculture, 6 dirty, 7 manufacturing, 8 high-tech.
# Converted for testing only, every entry off; whether the page offers them to players is the owner's call.
GROW_PURPOSES = (2, 3, 5, 6, 7, 8)
GROW_LABEL = {2: ('shop', 'shops'), 3: ('office', 'offices'), 5: ('farm', 'farms'), 6: ('dirty industry', 'dirty industry'),
              7: ('manufacturing', 'manufacturing'), 8: ('high-tech industry', 'high-tech industry')}
GROW_NOTE = " SimCity 4's own growable from your game, converted for testing: off by default."


def install_growables(bs, services):
    """The install's commercial and industrial growables: purpose in GROW_PURPOSES, not a civic / park / reward /
    landmark building."""
    return [b for b in bs if b['tgi'] not in services and C.sc(b['purpose']) in GROW_PURPOSES]


# ---------------------------------------------------------------------------------------------- task plop2
# SC4 landmark / ploppable versions (round 2026-11-19i): a lot whose building has no model and shows a converted
# building as a lot prop (the Global Office Center's "Landmark" and "Jobs" lots) becomes an SC3 landmark entry
# (bldimport kind landmark: the game's landmark menu, a plugin in Apps\PlugIn\bldimport). Its OBJ is a byte copy of
# the building's own <stem>.obj (same MTL and textures; bldimport keys ids by file, so each entry has its own file),
# without the SC4 lot's props. On: the landmark lot; when a building has no landmark lot, its first ploppable lot.
LANDMARK_LOTS = (1, 2, 3, 4)
LANDMARK_DESC = 'From SimCity 4'
LANDMARK_EDITABLE = EDITABLE + ('kind', 'description')


def version_on(vs, v, n):
    if n not in LANDMARK_LOTS:
        return False
    if v['kind'] == 'landmark':
        return True
    return not any(x['kind'] == 'landmark' for x in vs) and v is vs[0]


def landmark_file(b, v, vs):
    """<building stem>_<landmark|ploppable>.obj, numbered from the second lot of a kind."""
    same = [x for x in vs if x['kind'] == v['kind']]
    k = next(i for i, x in enumerate(same) if x is v)
    return '%s_%s%s.obj' % (stem_of(b['name']), v['kind'], '' if k == 0 else str(k + 1))


def landmark_entry(b, e, v, vs, style, keep_diag):
    n = lot_for(b)
    x = e['x_sc4']
    diag = bool(x['diagonal'])
    notes = ("SC4 %s lot %s (building %s) as an SC3 landmark: the landmark menu, one per city, stats of a stock"
             " landmark of the lot. The model is %s without the SC4 lot's props."
             % (v['kind'], v['lot'], v['building'], label_of(b)))
    if n not in LANDMARK_LOTS:
        notes += ' Off: SC3 landmarks are 1x1 to 4x4, this building needs %dx%d.' % (n, n)
    elif not version_on(vs, v, n):
        notes += ' Off by default: the same building as the landmark entry, and SC3 landmarks have no jobs.'
    return {
        'file': landmark_file(b, v, vs), 'name': v['building'], 'kind': 'landmark',
        'class': None, 'lot': [n, n], 'weight': 1, 'height_m': e['height_m'], 'scale': 1.0, 'rotate_deg': 0,
        'style': 'any', 'enabled': bool(version_on(vs, v, n) and (keep_diag or not diag)),
        'description': LANDMARK_DESC, 'notes': notes,
        'x_bldrender': {'style': style},
        'x_sc4': {'exemplar': v['exemplar'], 'design': v['building'], 'colour': None, 'version': v['kind'],
                  'sc4_lot': v['lot'], 'model_of': b['name'], 'building_tgi': v['building_tgi'],
                  'model_key': x['model_key'], 'size_m': x['size_m'], 'diagonal': diag, 'foundation': x['foundation'],
                  'views': x['views']},
    }


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('src')
    ap.add_argument('--out')
    ap.add_argument('--all', action='store_true', help='enable every colour, not one per design')
    ap.add_argument('--style', default='baked', help='bldrender style written into x_bldrender (default baked)')
    ap.add_argument('--only', help='comma list of exemplar names or designs to convert')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--diagonal', action='store_true',
                    help='treat buildings set at 45 degrees as any other (default: written off, with a note)')
    ap.add_argument('--no-fill', action='store_true',
                    help='leave out the hidden back walls + floor of each view box (cut-outs then show the lot)')
    ap.add_argument('--notes-json', help='also write the pack notes (lot-only packs, versions) and the buildings'
                                         ' without a model to this file (task sc4pass2, for the page golden)')
    ap.add_argument('--deps', action='append', default=[],
                    help='an SC4 dependency download (.zip / .jar / .dat / folder) holding lot props; repeatable'
                         ' (task sc4props)')
    ap.add_argument('--deps-cache', help='where the dependency index and fetched props are cached'
                                         ' (default %%LOCALAPPDATA%%\\sc4conv)')
    ap.add_argument('--sc4', help="the player's SimCity 4 install (the folder holding SimCity_1.dat): its own props"
                                  ' as one more prop source (task sc4baseprops)')
    ap.add_argument('--no-props', action='store_true', help='write the lot props but leave them off'
                                                           ' (x_sc4.props.on false)')
    ap.add_argument('--growables', action='store_true', help="from an SC4 install: also its shops, offices, industry"
                                                             ' and farms, every entry off (task sc4ci, testing)')
    ap.add_argument('--no-textures', action='store_true', help='write the lot textures but leave them off'
                                                              ' (x_sc4.textures.on false, task sc4lottex)')
    a = ap.parse_args(argv[1:])
    if a.sc4 is not None and C.install_files(a.sc4) is None:
        print('--sc4 %s: no SimCity_1.dat in that folder (give the SimCity 4 folder itself)' % a.sc4)
        return 2
    idx = C.Index(a.src)
    bs, lots = C.buildings(idx)
    print('%d DBPF files, %d buildings with S3D models, %d lots' % (len(idx.files), len(bs), len(lots)))
    n_models = len(bs)                    # task sc4civ: before --only, for the install report
    if a.only:
        want = {x.strip().lower() for x in a.only.split(',')}
        bs = [b for b in bs if b['name'].lower() in want or design_of(b['name'])[0].lower() in want]
    rw = RW.lua_rewards(idx)              # task sc4civ: SC4's own reward conditions (an install; a download has none)
    services = {}
    for b in bs:
        sv = service_for(b, rw)
        if sv is not None:
            services[b['tgi']] = sv
    if idx.install:                       # task sc4civ: from an install only the civic, park, reward, landmark buildings
        n_all = n_models + len(C.others(idx)[0])
        grow = install_growables(bs, services) if a.growables else []
        gset = {b['tgi'] for b in grow}
        notes, missing, versions = install_notes(idx, n_all, [b for b in bs if b['tgi'] in services],
                                                 C.others(idx)[0], grow), [], {}
        bs = [b for b in bs if b['tgi'] in services or b['tgi'] in gset]
        states = {b['tgi']: V.model_state(idx, b) for b in bs}
    else:
        gset = set()
        states = {b['tgi']: V.model_state(idx, b) for b in bs}
        deps = []
        for rp in readme_files(a.src):
            for d in readme_deps(open(rp, encoding='utf-8', errors='replace').read()):
                if d not in deps:
                    deps.append(d)
        notes, missing, versions = pack_notes(idx, bs, states, lots, deps)
    for ln in notes:
        print(ln)
    if a.notes_json:
        with open(a.notes_json, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump({'notes': notes, 'missing': missing}, fh, indent=1)
    bs = [b for b in bs if states[b['tgi']][0] == 'ok']
    diag = {b['tgi']: V.foundation_diagonal(idx, b) for b in bs}
    is_diag = (lambda b: False) if a.diagonal else (lambda b: bool(diag[b['tgi']] and diag[b['tgi']]['diagonal']))
    if a.list or not a.out:
        for b in bs:
            dg = diag[b['tgi']]
            sv = services.get(b['tgi'])
            print('  %-32s %-30s %s lot %dx%d %s' % (b['name'], label_of(b)[:30],
                                                    ('%s %s' % (sv['kind'], sv.get('base') or sv.get('population') or ''))
                                                    if sv else 'class %s' % class_for(b)[0],
                                                    sv['lot'] if sv else lot_for(b), sv['lot'] if sv else lot_for(b),
                                                          'foundation not read' if dg is None else
                                                          '%s 45-degree outline %.2f%s' % (dg['foundation'], dg['share_45'],
                                                                                           ', DIAGONAL' if dg['diagonal'] else '')))
        for m in missing:
            print('  %-32s %-30s %s' % (m['exemplar'][:32], m['name'][:30], m['reason']))
        return 0
    if not bs:
        print('nothing written to %s: no building in this download can be converted' % a.out)
        return 3
    os.makedirs(a.out, exist_ok=True)
    mj = os.path.join(a.out, 'models.json')
    old = {}
    if os.path.isfile(mj):
        for m in json.load(open(mj, encoding='utf-8')).get('models', []):
            old[m.get('file')] = m
            ex = (m.get('x_sc4') or {}).get('exemplar')
            if ex:                        # task sc4props: 'file' changes with the props switch, the exemplar does not
                old[ex] = m
    models = []
    fam = {}                              # one SC4 family per design; enable colour k of the k-th design
    for b in bs:
        fam.setdefault(design_key(b, services), []).append(b)
    pick = {}
    for d, c in zip(fam, pick_colours(list(fam.values()), is_diag)):
        pick[d] = c['tgi'] if c is not None else None
        if d[0] == 'sc4':                 # task sc4civ: of SC4's buildings sharing a name, the first (name order) is on
            c = next((m for m in fam[d] if not is_diag(m)), None)
            pick[d] = c['tgi'] if c is not None else None
    pctx = props_context(idx, bs, lots, a.deps, a.deps_cache, not a.no_fill, a.no_props, services=services,
                         sc4=a.sc4, tex_off=a.no_textures)
    for b in bs:
        design = design_key(b, services)
        first = pick[design] == b['tgi'] and b['tgi'] not in gset     # task sc4ci: the install's growables are off
        try:
            e = write_building(idx, b, a.out, a.all or first, a.style, not a.no_fill, diag[b['tgi']], a.diagonal,
                               versions.get(b['tgi']), pctx)
        except ValueError as ex:
            print('  skip %s: %s' % (b['name'], ex))
            continue
        if b['tgi'] in gset:
            e['notes'] += GROW_NOTE
        ed = editable(e)
        auto = {k: e[k] for k in ed}
        e['x_sc4']['auto'] = auto         # what this tool wrote, so a rerun can tell the player's edits apart
        pr = e['x_sc4'].get('props')
        if pr is not None:
            auto['props_on'] = pr['on']
        tx = e['x_sc4'].get('textures')
        if tx is not None:
            auto['textures_on'] = tx['on']
        o = old.get(e['x_sc4']['exemplar']) or old.get(e['file'])
        if o:                             # keep a field the player changed (classifier page) since the last run
            prev = (o.get('x_sc4') or {}).get('auto') or {}
            for k in ed:
                if k in o and k in prev and o[k] != prev[k]:
                    e[k] = o[k]
            op = (o.get('x_sc4') or {}).get('props')
            if pr is not None and isinstance(op, dict) and 'props_on' in prev and op.get('on') != prev['props_on']:
                pr['on'] = bool(op.get('on')) and pr['placed'] > 0     # task sc4props: the player's switch
            ot = (o.get('x_sc4') or {}).get('textures')
            if tx is not None and isinstance(ot, dict) and 'textures_on' in prev and ot.get('on') != prev['textures_on']:
                tx['on'] = bool(ot.get('on')) and tx['ground']['drawn'] > 0     # task sc4lottex: the player's switch
            e['file'] = file_for(stem_of(b['name']), pr, tx)
        models.append(e)
        vs = versions.get(b['tgi']) or []
        for v in vs:                      # task plop2: the building's SC4 landmark / ploppable lots as SC3 landmarks
            le = landmark_entry(b, e, v, vs, a.style, a.diagonal)
            shutil.copyfile(os.path.join(a.out, stem_of(b['name']) + '.obj'), os.path.join(a.out, le['file']))
            la = {k: le[k] for k in LANDMARK_EDITABLE}
            le['x_sc4']['auto'] = la
            o = old.get(le['x_sc4']['exemplar']) or old.get(le['file'])
            if o:                         # the player's edits since the last run (description included)
                prev = (o.get('x_sc4') or {}).get('auto') or {}
                for k in LANDMARK_EDITABLE:
                    if k in o and k in prev and o[k] != prev[k]:
                        le[k] = o[k]
            models.append(le)
            print('  %-32s -> %-36s landmark lot %s %s' % (v['exemplar'][:32], le['file'], le['lot'],
                                                          'enabled' if le['enabled'] else ''))
        print('  %-32s -> %-36s %s lot %s %s%s' % (b['name'], e['file'], e['kind'] if e['kind'] != 'growable' else
                                                 'class %s' % e['class'], e['lot'],
                                                       'enabled' if e['enabled'] else '',
                                                       ' diagonal' if e['x_sc4']['diagonal'] else ''))
    for ln in props_notes(pctx['plans'], pctx['sc4']) + tex_notes(pctx['tplans']):
        print(ln)
    top = {'sc3models': 1, 'models': models}
    if missing:                           # task sc4pass2: buildings of the download without a model, by name
        top['x_sc4_missing'] = missing
    with open(mj, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(top, fh, indent=1)
    print('%d models, %d enabled, %d diagonal -> %s' % (len(models), sum(m['enabled'] for m in models),
                                                       sum(m['x_sc4']['diagonal'] for m in models), mj))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
