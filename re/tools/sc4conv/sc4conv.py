#!/usr/bin/env python3
r"""sc4conv.py - task sc4conv (2026-11-18h): SimCity 4 buildings -> OBJ + MTL + PNG + models.json for bldimport.

  py -3.12 re/tools/sc4conv/sc4conv.py <SC4 plugin folder or .dat> --out <folder> [--all] [--style baked|baked_raw|baked_sharp] [--no-fill]
  py -3.12 re/tools/sc4conv/sc4conv.py <SC4 plugin folder or .dat> --list

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
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog as C  # noqa: E402
import views as V  # noqa: E402

EDITABLE = ('name', 'class', 'lot', 'weight', 'enabled', 'scale', 'rotate_deg', 'notes', 'x_bldrender')
CELL_M = 16.0             # bldimport's metres per lot cell (BUILDING_ART.md 4); an SC4 tile is 16 m as well
ZOOM5 = 4                 # S3D zoom index of SC4 zoom 5


def class_for(b):
    """SC3 lot class (prop 0x65, batgrow.CLASS_LABEL) from SC4 purpose / wealth / capacity. -> (class, why).
    Residential (purpose 1) only: the pack has nothing else. The density cut is a choice of this tool, not a
    measured equivalence: capacity <= 60 -> light, <= 400 -> medium, else dense."""
    w = b['wealth'] or 1
    cap = sum(c for _, c in b['capacity']) if b['capacity'] else 0
    if b['purpose'] != 1:
        return None, 'purpose %r: only residential (1) is mapped' % b['purpose']
    dens = 0 if cap <= 60 else (1 if cap <= 400 else 2)
    cls = (3100, 3700, 4300)[dens] + 200 * (min(max(w, 1), 3) - 1)
    why = 'SC4 residential, wealth %d, capacity %d -> %s density' % (w, cap, ('light', 'medium', 'dense')[dens])
    n = lot_for(b)
    if n not in CLASS_LOTS.get(cls, (n,)):
        alt = [c for c in CLASS_FALLBACK.get(cls, ()) if n in CLASS_LOTS.get(c, ())]
        if alt:
            why += '; class %d has no %dx%d base, %d does' % (cls, n, n, alt[0])
            cls = alt[0]
    return cls, why


# Square lot sizes with a stock base per residential class (batgrow.class_table on the 2026-11-18 release tree:
# 3100 / 3300 1x1 only, 3500 1x1 + 2x2, 3700 2x2 + 3x3, 3900 2x2). bldimport refuses a class without a base of the
# entry's lot size, so a larger light-density house moves to the class of the same wealth that has one.
CLASS_LOTS = {3100: (1,), 3300: (1,), 3500: (1, 2), 3700: (2, 3), 3900: (2,)}
CLASS_FALLBACK = {3100: (3700,), 3300: (3900,), 3500: (3500,)}


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


def write_building(idx, b, out, enabled, style, fill=True, dg=None, keep_diag=False):
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
    cls, why = class_for(b)
    n = lot_for(b)
    design, colour = design_of(b['name'])
    title = (b['title'] or b['name']).splitlines()[0].strip().rstrip(',')
    sc4lots = sorted({'%dx%d' % tuple(sorted(l['size'])) for l in b['lots']})
    diag = bool(dg and dg['diagonal'])
    entry = {
        'file': stem + '.obj', 'name': title, 'kind': 'growable', 'class': cls, 'lot': [n, n], 'weight': 1,
        'height_m': round(b['size_m'][1], 2), 'scale': 1.0, 'rotate_deg': 0, 'style': 'any',
        'enabled': bool(enabled and cls is not None and (keep_diag or not diag)),
        'notes': (diag_note(dg) if diag else '') + '%s. SC4 lots %s, the SC3 lot keeps the house (%.1f x %.1f m) and drops the yard.'
                 % (why, ', '.join(sc4lots) or 'none', b['size_m'][0], b['size_m'][2]),
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
    return entry


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
    a = ap.parse_args(argv[1:])
    idx = C.Index(a.src)
    bs, lots = C.buildings(idx)
    print('%d DBPF files, %d buildings with S3D models, %d lots' % (len(idx.files), len(bs), len(lots)))
    if a.only:
        want = {x.strip().lower() for x in a.only.split(',')}
        bs = [b for b in bs if b['name'].lower() in want or design_of(b['name'])[0].lower() in want]
    diag = {b['tgi']: V.foundation_diagonal(idx, b) for b in bs}
    is_diag = (lambda b: False) if a.diagonal else (lambda b: bool(diag[b['tgi']] and diag[b['tgi']]['diagonal']))
    if a.list or not a.out:
        for b in bs:
            dg = diag[b['tgi']]
            print('  %-32s %-30s class %s lot %dx%d %s' % (b['name'], (b['title'] or '').splitlines()[0][:30],
                                                          class_for(b)[0], lot_for(b), lot_for(b),
                                                          'foundation not read' if dg is None else
                                                          '%s 45-degree outline %.2f%s' % (dg['foundation'], dg['share_45'],
                                                                                           ', DIAGONAL' if dg['diagonal'] else '')))
        return 0
    os.makedirs(a.out, exist_ok=True)
    mj = os.path.join(a.out, 'models.json')
    old = {}
    if os.path.isfile(mj):
        for m in json.load(open(mj, encoding='utf-8')).get('models', []):
            old[m.get('file')] = m
    models = []
    fam = {}                              # one SC4 family per design; enable colour k of the k-th design
    for b in bs:
        fam.setdefault(tuple(b['families']) or design_of(b['name'])[0].lower(), []).append(b)
    pick = {}
    for d, c in zip(fam, pick_colours(list(fam.values()), is_diag)):
        pick[d] = c['tgi'] if c is not None else None
    for b in bs:
        design = tuple(b['families']) or design_of(b['name'])[0].lower()
        first = pick[design] == b['tgi']
        try:
            e = write_building(idx, b, a.out, a.all or first, a.style, not a.no_fill, diag[b['tgi']], a.diagonal)
        except ValueError as ex:
            print('  skip %s: %s' % (b['name'], ex))
            continue
        auto = {k: e[k] for k in EDITABLE}
        e['x_sc4']['auto'] = auto         # what this tool wrote, so a rerun can tell the player's edits apart
        o = old.get(e['file'])
        if o:                             # keep a field the player changed (classifier page) since the last run
            prev = (o.get('x_sc4') or {}).get('auto') or {}
            for k in EDITABLE:
                if k in o and k in prev and o[k] != prev[k]:
                    e[k] = o[k]
        models.append(e)
        print('  %-32s -> %-36s class %s lot %s %s%s' % (b['name'], e['file'], e['class'], e['lot'],
                                                       'enabled' if e['enabled'] else '',
                                                       ' diagonal' if e['x_sc4']['diagonal'] else ''))
    with open(mj, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({'sc3models': 1, 'models': models}, fh, indent=1)
    print('%d models, %d enabled, %d diagonal -> %s' % (len(models), sum(m['enabled'] for m in models),
                                                       sum(m['x_sc4']['diagonal'] for m in models), mj))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
