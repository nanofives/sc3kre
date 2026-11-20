#!/usr/bin/env python3
r"""lottex.py - task sc4lottex (2026-11-20): an SC4 lot's textures (driveways, paths, paving, flower beds) drawn on the
ground under the converted building.

A lot object of kind 2 (catalog.buildings, re/analysis/SC4_FORMATS.md 12) is a texture: word 2 the rotation (low 2 bits)
and a mirror bit (0x80000000), words 6-9 its square in the lot frame (16 x 16 m on every row of the JMyers lots and of
SimCity 4's own lots, up to float rounding), word 12 the texture: an FSH of group 0x0986135E, instance = that id + zoom
(0..4 = SC4 zooms 1..5; the zoom-5 one, + 4, is 128 x 128 px = 8 px per metre). Rules, each measured (SC4_FORMATS.md 12):

1. Orientation. The texture image turned 180 degrees, then q = rotation quarter turns clockwise (image columns along
   +x, rows along +z), the mirror bit mirroring the image's columns first. Of the 16 ways to lay an image on a square,
   this one puts the most parked cars of the lots on paving (SimCity 4's own lots 197 of 239 cars, JMyers 20 of 29).
2. Layering. Textures without a transparent texel first (the lot's base: lawn, parking), then the others, each group in
   lot order (the cars test again: 197 against 182 for plain lot order on SimCity 4's lots, 20 against 11 on JMyers).
3. The SC3 lot. The canvas is the SC3 lot window of the props (props.plan) at 8 px per metre, in the house's model frame:
   a texture square wholly inside is placed, one partly inside is cut at the window edge, one wholly outside is left out.
4. Lawn. Where the composite is grass (green the strongest channel, hue 60-108 degrees, saturation above 0.15: GRASS) the
   texel is cleared, so SC3's own lawn (bldrender's ground) shows there, as it does on stock lots: the SC4 grass is
   darker and yellower than SC3's lawn (SC4_FORMATS.md 12.4). Paving, paths, soil, flowers and walls stay.

The canvas is written as <stem>_lot.png and drawn by one quad in the OBJ group `sc3ground`, which bldrender lights as its
own lawn (no tone of the pre-lit SC4 art, the rim of the stock lots). Plain float64 arithmetic in a fixed order and
integer rounding as floor(x + 0.5): sc4web.js runs the same steps and gets the same bytes.
"""
import math
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dbpf as D  # noqa: E402
import fsh as FS  # noqa: E402
import props as PR  # noqa: E402

G_LOTTEX = 0x0986135E     # FSH group of lot textures (1,453 FSH in SimCity 4's own files, 26,171 in the BSC pack)
ZOOM5 = 4                 # instance + 4 = the SC4 zoom-5 texture
PX_PER_M = 8              # 128 px over 16 m
Y_LIFT = 0.01             # the quad sits 1 cm above the house's lowest point (the lawn is drawn just below 0)
EDGE_TOL = 1e-6


def tex_key(tid):
    return (D.T_FSH, G_LOTTEX, (tid + ZOOM5) & 0xFFFFFFFF)


def grass(r, g, b):
    """The lawn test on one 8-bit colour (integers only): green the strictly strongest channel, hue <= 108 degrees
    (5 (r - b) >= g - min) and saturation above 0.15 (20 (g - min) > 3 g)."""
    mn = min(r, b)
    return g > r and g > b and 5 * (r - b) >= g - mn and 20 * (g - mn) > 3 * g


def grass_mask(rgb):
    """grass() over an (..., 3) uint8 array."""
    c = rgb.astype(np.int32)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    mn = np.minimum(r, b)
    return (g > r) & (g > b) & (5 * (r - b) >= g - mn) & (20 * (g - mn) > 3 * g)


def owner(sources, key):
    """The first source holding the texture (the download, then the --deps packs, then the SC4 install: a plugin's file
    replaces the game's, as for props)."""
    return next((s for s in sources if s.has(key)), None)


def plan(pl, sources):
    """-> rows [{row, id, rot, flip, box (x0, x1, z0, z1 in the house's model frame), src, state}] for the lot of a props
    plan (props.plan). state: 'ok' (inside the SC3 lot window), 'cut' (partly), 'outside', 'missing' (in no source)."""
    lot, hrow, kb = pl['lot'], pl['house'], pl['kb']
    x0w, x1w, z0w, z1w = pl['window']
    out = []
    for k, o in enumerate(lot['objects']):
        if o['type'] != 2 or not o['ids']:
            continue
        tid = o['ids'][0] & 0xFFFFFFFF
        b = o['bounds']
        cs = [PR.turn(cx - hrow['x'], cz - hrow['z'], -(kb - 2)) for cx, cz in ((b[0], b[1]), (b[2], b[3]))]
        box = (min(cs[0][0], cs[1][0]), max(cs[0][0], cs[1][0]), min(cs[0][1], cs[1][1]), max(cs[0][1], cs[1][1]))
        r = {'row': k, 'id': tid, 'rot': o['rot'] & 3, 'flip': bool(o.get('flip')), 'bounds': list(b), 'box': box,
             'src': None, 'state': 'ok'}
        s = owner(sources, tex_key(tid))
        if s is None:
            r['state'] = 'missing'
        else:
            r['src'] = s
            if box[1] <= x0w or box[0] >= x1w or box[3] <= z0w or box[2] >= z1w:
                r['state'] = 'outside'
            elif box[0] < x0w - EDGE_TOL or box[1] > x1w + EDGE_TOL or box[2] < z0w - EDGE_TOL or box[3] > z1w + EDGE_TOL:
                r['state'] = 'cut'
        out.append(r)
    return out


def needed_keys(rows):
    return [tex_key(r['id']) for r in rows if r['src'] is not None and r['state'] in ('ok', 'cut')]


def texture(r, cache):
    """The zoom-5 RGBA of a row's texture (cache: {(key, src id): image or error text})."""
    ck = (tex_key(r['id']), id(r['src']))
    if ck not in cache:
        try:
            bm = FS.read_fsh(r['src'].read(ck[0]))[0]
            im = bm['image']
            cache[ck] = im if im.shape[0] == im.shape[1] else 'not square (%d x %d)' % (im.shape[1], im.shape[0])
        except (ValueError, KeyError, IndexError, struct.error) as e:
            cache[ck] = str(e)
    return cache[ck]


def composite(pl, rows, n, cache):
    """-> (RGBA uint8 (P, P, 4), stats) with P = n x 16 x PX_PER_M: column i = model x, row j = model z, both from the
    window's low corner, pixel centre (i + 0.5) / PX_PER_M metres. Rows drawn: state 'ok' and 'cut'; a texture that
    cannot be read becomes 'unreadable'."""
    lot, hrow, kb = pl['lot'], pl['house'], pl['kb']
    x0w, _x1w, z0w, _z1w = pl['window']
    P = int(n * 16 * PX_PER_M)
    k = (np.arange(P, dtype=np.float64) + 0.5) * (1.0 / PX_PER_M)
    mx = x0w + k[None, :] + np.zeros((P, 1))
    mz = z0w + k[:, None] + np.zeros((1, P))
    # model -> lot frame: the inverse of props' turn(lot - house, -(kb - 2))
    q = (kb - 2) % 4
    ax, az = mx, mz
    for _ in range(q):
        if PR.QUARTER == 1:
            ax, az = az, -ax
        else:
            ax, az = -az, ax
    lx = ax + hrow['x']
    lz = az + hrow['z']
    draw = [r for r in rows if r['state'] in ('ok', 'cut')]
    ims = []
    for r in draw:
        im = texture(r, cache)
        if isinstance(im, str):
            r['state'] = 'unreadable'
            r['why'] = im
            continue
        ims.append((r, im))
    opq = [(r, im) for r, im in ims if bool((im[..., 3] == 255).all())]
    order = opq + [(r, im) for r, im in ims if not bool((im[..., 3] == 255).all())]
    ca = np.zeros((P, P), dtype=np.float64)
    cc = np.zeros((P, P, 3), dtype=np.float64)
    for r, im in order:
        b = r['bounds']
        u = (lx - b[0]) / (b[2] - b[0])
        v = (lz - b[1]) / (b[3] - b[1])
        ins = (u >= 0.0) & (u < 1.0) & (v >= 0.0) & (v < 1.0)
        if not ins.any():
            continue
        N = im.shape[0]
        c = np.floor(u[ins] * N).astype(np.int64)
        rr = np.floor(v[ins] * N).astype(np.int64)
        # displayed image A = (CW x (2 + rot))(mirror(T)): A[r][c] = CW^(t-1)(X)[N-1-c][r], X[r][c] = T[r][N-1-c]
        for _ in range((2 + r['rot']) % 4):
            rr, c = N - 1 - c, rr
        if r['flip']:
            c = N - 1 - c
        px = im[rr, c].astype(np.float64)
        sa = px[:, 3] / 255.0
        da = ca[ins]
        oa = sa + da * (1.0 - sa)
        dc = cc[ins]
        num = px[:, :3] * sa[:, None] + dc * (da * (1.0 - sa))[:, None]
        nc = np.where(oa[:, None] > 0.0, num / np.where(oa > 0.0, oa, 1.0)[:, None], 0.0)
        ca[ins] = oa
        cc[ins] = nc
    out = np.zeros((P, P, 4), dtype=np.uint8)
    out[..., :3] = np.clip(np.floor(cc + 0.5), 0, 255).astype(np.uint8)
    a8 = np.clip(np.floor(ca * 255.0 + 0.5), 0, 255).astype(np.uint8)
    sc4 = a8 >= 128
    lawn = sc4 & grass_mask(out[..., :3])
    out[..., 3] = np.where(lawn, 0, a8).astype(np.uint8)
    drawn = out[..., 3] >= 128
    tot = float(P * P)
    stats = {'sc4_ground': round(float(sc4.sum()) / tot, 4), 'lawn': round(float(lawn.sum()) / tot, 4),
             'drawn': round(float(drawn.sum()) / tot, 4)}
    return out, stats


def summary(pl, rows, stats):
    """-> x_sc4.textures (without 'on')."""
    from collections import Counter
    st = Counter(r['state'] for r in rows)
    miss = Counter(r['id'] for r in rows if r['state'] == 'missing')
    used = Counter(r['id'] for r in rows if r['state'] in ('ok', 'cut'))
    return {'lot': pl['lot']['name'], 'rows': len(rows), 'placed': st.get('ok', 0), 'cut': st.get('cut', 0),
            'outside_sc3_lot': st.get('outside', 0), 'missing': st.get('missing', 0),
            'unreadable': st.get('unreadable', 0),
            'ground': stats,
            'used': [['%08X' % k, v] for k, v in sorted(used.items())],
            'missing_ids': [['%08X' % k, v] for k, v in sorted(miss.items())]}


def quad_lines(pl, y, vbase, tbase, png_name):
    """OBJ lines of the ground quad over the window (group sc3ground) and its MTL lines. vbase / tbase = the vertex and uv
    counts before it."""
    x0, x1, z0, z1 = pl['window']
    V3 = lambda x, z: 'v %.5f %.5f %.5f' % (x, y, z)  # noqa: E731
    obj = ['g sc3ground', 'usemtl sc4lottex', V3(x0, z0), V3(x1, z0), V3(x1, z1), V3(x0, z1),
           'vt 0.000000 1.000000', 'vt 1.000000 1.000000', 'vt 1.000000 0.000000', 'vt 0.000000 0.000000',
           'f %d/%d %d/%d %d/%d' % (vbase + 1, tbase + 1, vbase + 3, tbase + 3, vbase + 2, tbase + 2),
           'f %d/%d %d/%d %d/%d' % (vbase + 1, tbase + 1, vbase + 4, tbase + 4, vbase + 3, tbase + 3)]
    mtl = ['newmtl sc4lottex', 'Kd 1 1 1', 'map_Kd ' + png_name, '']
    return obj, mtl
