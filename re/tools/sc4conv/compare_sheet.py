#!/usr/bin/env python3
r"""compare_sheet.py - task sc4cmp (round 2026-11-20b): side-by-side pictures, SimCity 4 on the left, SimCity 3000 on
the right, for the forum post about converted SC4 buildings.

The SimCity 4 side is drawn through SimCity 4's own camera, not grabbed from the game. An SC4 building view is a box
whose texture is SC4's own render of that view, mapped by screen projection (views.py). Drawing the same box, the
lot's props (each one its own SC4 view, props.py) and the lot's textures (lottex.py, here over the WHOLE SC4 lot, SC4's
grass kept) through the fitted camera of one view gives what SC4 shows for the lot: the building and every prop are
SC4's own pixels, placed where SC4 places them, and the paving and lawns are SC4's lot textures. What is not drawn:
SC4's terrain under bare lot cells (a grass lot texture of the install stands in), animated people and cars (no
readable model, as in the converter), shadows SC4 casts at run time, and night lights.

The SimCity 3000 side is the converted building as the game draws it: the bldrender frame at zoom 4 (`bldimport.py
render <converted folder>`), with the SC3 lawn, the props and the lot textures the converter kept. Where a game
screenshot of the same building exists (round sc4civ / sc4ci frame dumps, local only) a third column shows it in a city,
found in the screenshot by matching the frame.

    py -3.12 compare_sheet.py <SC4 install> <converted folder> <out folder> [--ingame <spec.json>] [--only a,b]

The SC4 install is read in place and nothing of it is written except the pictures (EA's art: keep them local). This
file holds no SC4 data: building names come from the install, the picture list from SHEET below (exemplar names).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog as C  # noqa: E402
import fsh as FS  # noqa: E402
import lottex as LT  # noqa: E402
import props as PR  # noqa: E402
import views as V  # noqa: E402

ZOOM5 = 4
SC3_PX_PER_M = 128.0 / (16.0 * math.sqrt(2.0))   # zoom 4: a 16 m cell's diagonal is 128 px wide
MATCH_MAX = 30.0 ** 2                            # in-game match: mean squared error per channel
GRASS_TILE = 0xD400F050                          # an SC4 plain-grass lot texture: stands in for terrain under bare cells

# The pictures: (file stem, exemplar name). The first twelve are the forum set, in post order. The rest go to extra/
# (kept for the record: the SC4 lot is much larger than the SC3 one, or the SC3 frame reads poorly at this size).
SHEET = [
    ('01_small_police_station', 'CV24X24_4carLocalPrecinct_030C'),
    ('02_courthouse', 'RW44x28_CourtHouse_0322'),
    ('03_gazebo', 'PZ11x9x11_Gazebo_1DDE'),
    ('04_alamo', 'Lm26x32_Alamo_04DA'),
    ('05_independence_hall', 'Lm30x24_IndependenceHall_04D7'),
    ('06_small_shops', 'CS$14x14_1ChiSmallShop1_05CD'),
    ('07_retail_stores', 'CS$$12x28_1HouMediumStore1_05C5'),
    ('08_lam_banking', 'CO$$24x24_1ChiOfficeBldg5_04ED'),
    ('09_ferrrara_inc', 'CO$$$44x26_6ChiOfficeBldg9_0507'),
    ('10_eyler_refining', 'ID30x30_1DirtyAnchor5_07DE'),
    ('11_vilett_textiles', 'IM28x40_2ManuOut8_0823'),
    ('12_pumpkin_acres', 'IR15x7_1Farm4_0850'),
    ('extra/city_hall', 'RW46x34_CityHall_03C1'),
    ('extra/small_fire_station', 'CV12x14_2engineStationHouse_0310'),
    ('extra/mayors_house', 'RW16x14_MayorsHouse_031F'),
    ('extra/lee_avionics', 'IH28x28_1HTAnchor3_082D'),
]

# ------------------------------------------------------------------------------------------------ text and colours
BG_TOP, BG_BOT = (236, 233, 226), (214, 210, 201)
INK, INK2 = (38, 38, 42), (96, 94, 90)
FONT_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')


def font(size, bold=False):
    for nm in (('segoeuib.ttf', 'arialbd.ttf') if bold else ('segoeui.ttf', 'arial.ttf')):
        p = os.path.join(FONT_DIR, nm)
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ------------------------------------------------------------------------------------------------ SC4 scene
def to_view(Pm, r):
    """model frame -> view-r frame (the inverse of views.to_model)."""
    P = np.array(Pm, dtype=np.float64).reshape(-1, 3)
    for _ in range(r % 4):
        P = np.stack([-P[:, 2], P[:, 1], P[:, 0]], 1)
    return P


class Install:
    def __init__(self, path):
        self.idx = C.Index(path)
        self.bs, self.lots = C.buildings(self.idx)
        self.by = {b['name']: b for b in self.bs}
        self.src = PR.OwnSource(self.idx)
        self.sources = [self.src]
        self.pv = {}
        self.tex = {}
        self.ltex = {}

    def fsh(self, src, key):
        k = (id(src), key)
        if k not in self.tex:
            self.tex[k] = FS.read_fsh(src.read(key))[0]['image']
        return self.tex[k]

    def title(self, b):
        return (b['title'] or b['name']).splitlines()[0].strip().rstrip(',')


def sample(tex, u, v):
    """Bilinear RGBA sample (premultiplied), u, v in [0, 1] (v down the image). -> (N, 4) float, alpha 0..1."""
    h, w = tex.shape[:2]
    x = np.clip(u * w - 0.5, 0, w - 1)
    y = np.clip(v * h - 0.5, 0, h - 1)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    fx = (x - x0)[:, None]
    fy = (y - y0)[:, None]
    t = tex.astype(np.float32) / 255.0
    out = 0
    for yy, xx, wgt in ((y0, x0, (1 - fx) * (1 - fy)), (y0, x1, fx * (1 - fy)), (y1, x0, (1 - fx) * fy),
                        (y1, x1, fx * fy)):
        p = t[yy, xx]
        out = out + np.concatenate([p[:, :3] * p[:, 3:4], p[:, 3:4]], 1) * wgt
    return out


class Canvas:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.rgb = np.zeros((H, W, 3), np.float32)
        self.a = np.zeros((H, W), np.float32)
        self.z = np.full((H, W), np.inf)

    def tri(self, xy, dep, uv, tex, ztest=True):
        (x0, y0), (x1, y1), (x2, y2) = xy
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-9:
            return
        i0 = max(int(math.floor(min(x0, x1, x2))), 0)
        i1 = min(int(math.ceil(max(x0, x1, x2))), self.W - 1)
        j0 = max(int(math.floor(min(y0, y1, y2))), 0)
        j1 = min(int(math.ceil(max(y0, y1, y2))), self.H - 1)
        if i0 > i1 or j0 > j1:
            return
        px = np.arange(i0, i1 + 1) + 0.5
        py = np.arange(j0, j1 + 1)[:, None] + 0.5
        w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area
        w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area
        w2 = 1.0 - w0 - w1
        ins = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if not ins.any():
            return
        jj, ii = np.nonzero(ins)
        a, b_, c = w0[ins], w1[ins], w2[ins]
        d = a * dep[0] + b_ * dep[1] + c * dep[2] if dep is not None else a
        J, I = jj + j0, ii + i0
        u = a * uv[0][0] + b_ * uv[1][0] + c * uv[2][0]
        v = a * uv[0][1] + b_ * uv[1][1] + c * uv[2][1]
        s = sample(tex, u, v)
        ok = s[:, 3] >= 0.5
        if ztest:
            ok &= d < self.z[J, I] - 1e-6
        if not ok.any():
            return
        J, I, s, d = J[ok], I[ok], s[ok], d[ok]
        self.rgb[J, I] = s[:, :3] / s[:, 3:4]
        self.a[J, I] = 1.0
        if ztest:
            self.z[J, I] = d


def lot_ground(ins, pl):
    """The whole SC4 lot's textures, SC4's grass kept, at 8 px per metre, over pl['lot_box'] in the house's model
    frame: column = model x, row = model z (lottex.composite's rules: orientation, opaque first, alpha over).
    Bare texels take the plain grass lot texture."""
    L = pl['lot_box']
    pl = dict(pl, window=tuple(L))
    rows = LT.plan(pl, ins.sources)
    Px = int(round((L[1] - L[0]) * LT.PX_PER_M))
    Pz = int(round((L[3] - L[2]) * LT.PX_PER_M))
    lot, hrow, kb = pl['lot'], pl['house'], pl['kb']
    kx = (np.arange(Px, dtype=np.float64) + 0.5) / LT.PX_PER_M
    kz = (np.arange(Pz, dtype=np.float64) + 0.5) / LT.PX_PER_M
    mx = L[0] + kx[None, :] + np.zeros((Pz, 1))
    mz = L[2] + kz[:, None] + np.zeros((1, Px))
    q = (kb - 2) % 4
    ax, az = mx, mz
    for _ in range(q):
        if PR.QUARTER == 1:
            ax, az = az, -ax
        else:
            ax, az = -az, ax
    lx, lz = ax + hrow['x'], az + hrow['z']
    ims = []
    for r in rows:
        if r['state'] not in ('ok', 'cut'):
            continue
        im = LT.texture(r, ins.ltex)
        if not isinstance(im, str):
            ims.append((r, im))
    order = [x for x in ims if (x[1][..., 3] == 255).all()] + [x for x in ims if not (x[1][..., 3] == 255).all()]
    ca = np.zeros((Pz, Px))
    cc = np.zeros((Pz, Px, 3))
    gk = LT.tex_key(GRASS_TILE)
    if ins.src.has(gk):                    # terrain stand-in: the plain grass texture, tiled every 16 m
        g = ins.fsh(ins.src, gk).astype(np.float64)
        N = g.shape[0]
        gi = (np.floor((lx % 16.0) / 16.0 * N).astype(int)) % N
        gj = (np.floor((lz % 16.0) / 16.0 * N).astype(int)) % N
        cc[:] = g[gj, gi, :3]
    else:
        cc[:] = (93, 115, 44)
    base = cc.copy()
    for r, im in order:
        b = r['bounds']
        u = (lx - b[0]) / (b[2] - b[0])
        v = (lz - b[1]) / (b[3] - b[1])
        m = (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
        if not m.any():
            continue
        N = im.shape[0]
        c = np.floor(u[m] * N).astype(np.int64)
        rr = np.floor(v[m] * N).astype(np.int64)
        for _ in range((2 + r['rot']) % 4):
            rr, c = N - 1 - c, rr
        if r['flip']:
            c = N - 1 - c
        px = im[rr, c].astype(np.float64)
        sa = px[:, 3] / 255.0
        da = ca[m]
        oa = sa + da * (1 - sa)
        num = px[:, :3] * sa[:, None] + cc[m] * (da * (1 - sa))[:, None]
        cc[m] = np.where(oa[:, None] > 0, num / np.where(oa > 0, oa, 1)[:, None], cc[m])
        ca[m] = oa
    out = np.where(ca[..., None] > 0, cc * np.minimum(1, ca[..., None]) + base * (1 - np.minimum(1, ca[..., None])), base)
    img = np.zeros((Pz, Px, 4), np.uint8)
    img[..., :3] = np.clip(np.rint(out), 0, 255)
    img[..., 3] = 255
    return img, L, rows


def sc4_render(ins, b, r, scale=1.0, ss=3, lot=True):
    """-> (RGBA PIL image, info) the building in SC4 view r with its lot, drawn through that view's camera at
    `scale` x SC4's zoom-5 pixels. info: camera, props drawn, texture rows, the building's own picture (for the check)."""
    vs = V.load_views(ins.idx, b, ZOOM5)
    v = vs[r]
    A = np.array(v['A'], dtype=np.float64)
    if abs(A[1, 0]) > abs(A[1, 1]):    # an atlas canvas laid transposed (views.compose_atlas): screen x, y swapped
        A = A[:, ::-1].copy()
    fwd = np.array(v['cam']['forward_model'])
    az = v['cam']['azimuth_model']
    k = scale * ss
    items = []                                          # (Pm (3,3), UV (3,2), tex)
    for t in v['tris']:
        items.append((v['P'][list(t)], v['UV'][list(t)], v['tex'], 'bld'))
    info = {'props': 0, 'prop_rows': 0, 'tex_rows': 0, 'fit_err_px': v['cam']['fit_err_px'],
            'elevation': v['cam']['elevation'], 'azimuth': az, 'px_per_m': v['cam']['px_per_m']}
    ground = None
    if lot:
        v0 = vs[0]['P']
        box = (float(v0[:, 0].min()), float(v0[:, 0].max()), float(v0[:, 2].min()), float(v0[:, 2].max()))
        pl = PR.plan(b, ins.lots, ins.sources, box, 1)
        if pl is not None:
            L = pl['lot_box']
            info['lot_m'] = (L[1] - L[0], L[3] - L[2])
            for row in pl['rows']:
                info['prop_rows'] += 1
                if row['state'] == 'outside':           # outside the SC3 lot only: SC4 shows the whole lot
                    row['state'] = 'ok'
                if row['state'] != 'ok':
                    continue
                ck = (row['model'], id(row['msrc']))
                if ck not in ins.pv:
                    try:
                        ins.pv[ck] = PR.prop_views(row['msrc'], row['model'], row['name'])
                    except (ValueError, KeyError, IndexError) as e:
                        ins.pv[ck] = str(e)
                pv = ins.pv[ck]
                if isinstance(pv, str):
                    continue
                w = min(pv, key=lambda x: abs((PR.az_turned(x['az'], row['q']) - az + 180) % 360 - 180))
                info['props'] += 1
                for P, UV, tris, fk in w['meshes']:
                    tex = ins.fsh(row['msrc'], fk)
                    Pt = []
                    for p in P:
                        x, z = PR.turn(p[0], p[2], row['q'])
                        Pt.append([x + row['x'], p[1], z + row['z']])
                    Pt = np.array(Pt)
                    UV = np.array(UV)
                    for t in tris:
                        items.append((Pt[list(t)], UV[list(t)], tex, 'prop'))
            gimg, L, trows = lot_ground(ins, pl)
            info['tex_rows'] = sum(1 for x in trows if x['state'] in ('ok', 'cut'))
            y0 = float(min(vv['P'][:, 1].min() for vv in vs))
            y0 = min(y0, 0.0)
            gq = np.array([[L[0], y0, L[2]], [L[1], y0, L[2]], [L[1], y0, L[3]], [L[0], y0, L[3]]])
            guv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
            ground = (gq, guv, gimg)

    def scr(Pm):
        Pv = to_view(Pm, r)
        return (Pv @ A[:3] + A[3]) * k

    pts = [scr(it[0]) for it in items]
    allp = np.concatenate(pts + ([scr(ground[0])] if ground else []))
    pad = 2 * ss
    ox, oy = -allp[:, 0].min() + pad, -allp[:, 1].min() + pad
    W = int(math.ceil(allp[:, 0].max() + ox + pad))
    H = int(math.ceil(allp[:, 1].max() + oy + pad))
    W += (-W) % ss
    H += (-H) % ss
    cv = Canvas(W, H)
    if ground:
        gs = scr(ground[0]) + [ox, oy]
        for t in ((0, 1, 2), (0, 2, 3)):
            cv.tri(gs[list(t)], None, ground[1][list(t)], ground[2], ztest=False)
    for (Pm, UV, tex, _kind), p in zip(items, pts):
        cv.tri(p + [ox, oy], Pm @ fwd, UV, tex)
    h, w = H // ss, W // ss
    rgb = (cv.rgb * cv.a[..., None]).reshape(h, ss, w, ss, 3).sum((1, 3))
    a = cv.a.reshape(h, ss, w, ss).sum((1, 3))
    col = np.where(a[..., None] > 0, rgb / np.maximum(a, 1e-9)[..., None], 0)
    img = np.zeros((h, w, 4), np.uint8)
    img[..., :3] = np.clip(np.rint(col * 255), 0, 255)
    img[..., 3] = np.clip(np.rint(a / (ss * ss) * 255), 0, 255)
    info['view'] = v
    info['offset'] = (ox / ss, oy / ss)                 # screen = A . p x scale + offset (output pixels)
    info['swapped'] = bool(abs(np.array(v['A'])[1, 0]) > abs(np.array(v['A'])[1, 1]))
    return Image.fromarray(img, 'RGBA'), info


def own_picture(v, scale=1.0):
    """SC4's own picture of the building in this view (the view texture, cropped to its pixels), at scale."""
    t = Image.fromarray(v['tex'])
    if scale != 1.0:
        t = t.resize((max(1, round(t.width * scale)), max(1, round(t.height * scale))), Image.LANCZOS)
    return t.crop(t.getbbox())


def check(ins, b, r):
    """How close the SC4 side's building is to SC4's own picture of it. The building is drawn alone (no lot) at SC4's
    scale, and every pixel it covers is looked up in the view texture through the fitted projection (texture pixel =
    screen pixel - offset). -> {share of the drawn pixels that are opaque in SC4's picture too, mean absolute difference
    per channel (0-255) on those, share within 16 levels on every channel, camera fit error, elevation, px per metre}."""
    im, info = sc4_render(ins, b, r, 1.0, ss=4, lot=False)
    v = info['view']
    tex = v['tex'] if not info['swapped'] else np.transpose(v['tex'], (1, 0, 2))
    pa = np.asarray(im, np.float64)
    ox, oy = info['offset']
    jj, ii = np.nonzero(pa[..., 3] >= 255)            # fully covered pixels (edges are blended with the background)
    tx = np.floor(ii + 0.5 - ox).astype(int)
    ty = np.floor(jj + 0.5 - oy).astype(int)
    ok = (tx >= 0) & (ty >= 0) & (tx < tex.shape[1]) & (ty < tex.shape[0])
    jj, ii, tx, ty = jj[ok], ii[ok], tx[ok], ty[ok]
    t = tex[ty, tx].astype(np.float64)
    both = t[:, 3] >= 128
    d = np.abs(pa[jj, ii, :3] - t[:, :3])[both]
    return {'opaque_in_own': round(float(both.mean()), 4), 'mad': round(float(d.mean()), 2),
            'within16': round(float((d.max(1) <= 16).mean()), 4), 'pixels': int(both.sum()),
            'fit_err_px': round(info['fit_err_px'], 3), 'elevation': round(info['elevation'], 2),
            'px_per_m': round(info['px_per_m'], 3)}


# ------------------------------------------------------------------------------------------------ the pictures
CLASS_WORDS = {'51': 'Shops', '55': 'Shops', '57': 'Shops', '61': 'Shops', '67': 'Offices', '83': 'Dirty industry',
               '85': 'Manufacturing', '87': 'High-tech industry', '93': 'Farm'}


def subtitle(m):
    ex = m['x_sc4']['exemplar']
    n = '%dx%d' % tuple(m['lot'])
    if m['kind'] == 'reward':
        return 'Reward building, %s lot in SimCity 3000' % n
    if m['kind'] == 'landmark':
        return 'Landmark, %s lot in SimCity 3000' % n
    if m['kind'] == 'civic':
        w = ('Police station' if 'Precinct' in ex else 'Fire station' if 'engineStation' in ex
             else 'Park' if ex.startswith('PZ') else 'Civic building')
        return '%s, %s lot in SimCity 3000' % (w, n)
    w = 'Offices' if ex.startswith('CO') else CLASS_WORDS.get(str(m.get('class') or '')[:2], 'Growable building')
    return '%s, grows on a %s lot in SimCity 3000' % (w, n)


def shadowed(im, blur=10, off=(0, 8), alpha=0.35):
    """RGBA image with a soft shadow under it (for a light background). -> (image, pad)."""
    pad = blur * 3
    W, H = im.width + 2 * pad, im.height + 2 * pad + off[1]
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh = Image.new('RGBA', im.size, (40, 36, 30, 255))
    sh.putalpha(im.split()[3].point(lambda x: int(x * alpha)))
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    layer.paste(sh, (pad + off[0], pad + off[1]))
    out.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    out.alpha_composite(im, (pad, pad))
    return out, pad


def framed(im, border=(255, 255, 255), w=4):
    """A screenshot crop: white border and a shadow."""
    b = Image.new('RGBA', (im.width + 2 * w, im.height + 2 * w), border + (255,))
    b.paste(im.convert('RGB'), (w, w))
    return shadowed(b, blur=8, off=(0, 6), alpha=0.45)


def gradient(W, H):
    t = np.linspace(0, 1, H)[:, None, None]
    a = np.array(BG_TOP, float)[None, None] * (1 - t) + np.array(BG_BOT, float)[None, None] * t
    return Image.fromarray(np.repeat(a, W, 1).astype(np.uint8), 'RGB').convert('RGBA')


def trim(im):
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def resize(im, f):
    if abs(f - 1) < 1e-3:
        return im
    return im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))), Image.LANCZOS)


def ingame_crop(spec, game_root, f, cw, ch):
    """A crop of a game frame around the matched building, cw x ch output pixels at factor f."""
    g = Image.open(os.path.join(game_root, spec['frame'])).convert('RGB')
    cx, cy = spec['x'] + spec['w'] / 2, spec['y'] + spec['h'] / 2
    k = max(1.0, spec['h'] / (0.92 * ch / f))          # a tall building: zoom the strip out so it fits
    w, h = min(cw / f * k, 1430), min(ch / f * k, 900)
    best = None
    lum = np.asarray(g.convert('L'), np.float32)
    for dx in np.linspace(-0.3, 0.3, 13):                # slide sideways off the map edge (dark), building kept in
        x0 = int(round(min(max(cx - w / 2 + dx * w, 0), 1430 - w)))
        y0 = int(round(min(max(cy - h / 2, 0), 900 - h)))
        if x0 > spec['x'] or x0 + w < spec['x'] + spec['w']:
            continue
        dark = float((lum[y0:y0 + int(h), x0:x0 + int(w)] < 50).mean()) + abs(dx) * 0.05
        if best is None or dark < best[0]:
            best = (dark, x0, y0)
    if best is None:
        best = (0, int(round(min(max(cx - w / 2, 0), 1430 - w))), int(round(min(max(cy - h / 2, 0), 900 - h))))
    _, x0, y0 = best
    return g.crop((x0, y0, x0 + int(round(w)), y0 + int(round(h)))).resize((cw, ch), Image.LANCZOS).convert('RGBA')


def compose(title, sub, cols, out, game=None, W=1280, max_scale=1.75, max_h=560, game_h=400):
    """cols: [(label, kind, payload)], kind 'sc4' (callable scale -> RGBA, 7.0 px per metre at scale 1) or 'sc3' (RGBA
    frame at zoom 4), side by side at the same metres per pixel. game: (label, callable (f, w, h) -> RGBA), a strip
    under them at the same scale (the building in a city)."""
    M, G = 36, 28
    n = len(cols)
    cw = (W - 2 * M - (n - 1) * G) // n
    sizes = []
    for _, k, p in cols:
        if k == 'sc3':
            sizes.append(p.size)
        else:
            im = trim(p(1.0))
            sizes.append((im.width * SC3_PX_PER_M / 7.0, im.height * SC3_PX_PER_M / 7.0))
    f = min([max_scale] + [cw * 0.92 / w for w, _ in sizes] + [max_h / h for _, h in sizes])
    ims = [trim(p(f * SC3_PX_PER_M / 7.0)) if k == 'sc4' else trim(resize(p, f)) for _, k, p in cols]
    hmax = max(im.height for im in ims)
    top = 118
    yb = top + 34 + hmax
    H = yb + 44
    gim = None
    if game:
        gim = game[1](f, W - 2 * M - 8, game_h)
        gy = H + 34
        H = gy + game_h + 8 + 40
    can = gradient(W, H)
    d = ImageDraw.Draw(can)
    d.text((M, 22), title, font=font(36, True), fill=INK)
    d.text((M, 72), sub, font=font(19), fill=INK2)
    lf = font(20, True)
    for i, ((lab, k, _), im) in enumerate(zip(cols, ims)):
        x0 = M + i * (cw + G)
        tw = d.textlength(lab, font=lf)
        d.text((x0 + (cw - tw) / 2, top), lab, font=lf, fill=INK)
        sh, pad = shadowed(im)
        can.alpha_composite(sh, (int(x0 + (cw - im.width) / 2 - pad), int(yb - im.height - pad)))
    for i in range(1, n):
        x = M + i * (cw + G) - G // 2
        d.line([(x, top + 4), (x, yb + 20)], fill=(200, 196, 188), width=1)
    if gim is not None:
        tw = d.textlength(game[0], font=lf)
        d.text(((W - tw) / 2, gy - 34), game[0], font=lf, fill=INK)
        sh, pad = framed(gim)
        can.alpha_composite(sh, (M - pad, gy - pad))
    can.convert('RGB').save(out, quality=90)
    return can, f


def rotations(ins, b, m, sc3dir, out, W=1280):
    """One building in its four views: SC4 on the top row, SC3 below, the same side of the building in a column."""
    pairs = [(m['x_sc4']['views']['slot%d' % s], s) for s in (3, 2, 1, 0)]
    M, G = 30, 16
    cw = (W - 2 * M - 3 * G) // 4
    sc3 = [Image.open(os.path.join(sc3dir, 'z4_r%d.png' % s)).convert('RGBA') for _, s in pairs]
    probe = [trim(sc4_render(ins, b, V.VIEW_NAMES.index(vn), 1.0)[0]) for vn, _ in pairs]
    sizes = [im.size for im in sc3] + [(im.width * SC3_PX_PER_M / 7.0, im.height * SC3_PX_PER_M / 7.0) for im in probe]
    f = min([1.5] + [cw * 0.94 / w for w, _ in sizes])
    r4 = [trim(sc4_render(ins, b, V.VIEW_NAMES.index(vn), f * SC3_PX_PER_M / 7.0)[0]) for vn, _ in pairs]
    r3 = [trim(resize(im, f)) for im in sc3]
    h4, h3 = max(i.height for i in r4), max(i.height for i in r3)
    top = 118
    y4 = top + 34 + h4
    y3 = y4 + 30 + 34 + h3
    H = y3 + 40
    can = gradient(W, H)
    d = ImageDraw.Draw(can)
    d.text((M, 22), ins.title(b) + ', all four sides', font=font(36, True), fill=INK)
    d.text((M, 72), 'Top: SimCity 4. Bottom: converted for SimCity 3000, turned the same way.', font=font(19), fill=INK2)
    lf = font(20, True)
    d.text((M, top), 'SimCity 4', font=lf, fill=INK)
    d.text((M, y4 + 30), 'SimCity 3000', font=lf, fill=INK)
    for i in range(4):
        x0 = M + i * (cw + G)
        for im, yb in ((r4[i], y4), (r3[i], y3)):
            sh, pad = shadowed(im, blur=8, off=(0, 6))
            can.alpha_composite(sh, (int(x0 + (cw - im.width) / 2 - pad), int(yb - im.height - pad)))
    can.convert('RGB').save(out, quality=90)
    return can


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('install')
    ap.add_argument('conv', help='the converted folder (sc4conv.py --out), rendered with bldimport.py render')
    ap.add_argument('out')
    ap.add_argument('--ingame', help='json {exemplar: [{frame, slot, x, y, w, h}]} of game frame matches')
    ap.add_argument('--game-root', default='.', help='folder the ingame frame paths are relative to')
    ap.add_argument('--only', help='comma list of picture stems (and "rotations")')
    ap.add_argument('--rotations', default='CV24X24_4carLocalPrecinct_030C')
    a = ap.parse_args(argv)
    os.makedirs(os.path.join(a.out, 'extra'), exist_ok=True)
    ins = Install(a.install)
    models = {m['x_sc4']['exemplar']: m for m in json.load(open(os.path.join(a.conv, 'models.json')))['models']}
    ing = json.load(open(a.ingame)) if a.ingame else {}
    only = set(a.only.split(',')) if a.only else None
    report = []
    for stem, ex in SHEET:
        if only and stem not in only:
            continue
        b, m = ins.by.get(ex), models.get(ex)
        if b is None or m is None:
            print('skip', stem, ex, '(not in the install or not converted)')
            continue
        sc3dir = os.path.join(a.conv, 'sc3build', m['file'][:-4])
        games = [g for g in ing.get(ex) or [] if g.get('score', 0) <= MATCH_MAX]   # a clear match only
        games.sort(key=lambda g: g['slot'] != 3)                                  # SC4's front view first
        slot = games[0]['slot'] if games else 3
        r = V.VIEW_NAMES.index(m['x_sc4']['views']['slot%d' % slot])
        frame = Image.open(os.path.join(sc3dir, 'z4_r%d.png' % slot)).convert('RGBA')
        cols = [('SimCity 4', 'sc4', lambda s, b=b, r=r: sc4_render(ins, b, r, s)[0]),
                ('SimCity 3000', 'sc3', frame)]
        game = None
        if games:
            g = games[0]
            game = ('SimCity 3000, in a city', lambda f, cw, ch, g=g: ingame_crop(g, a.game_root, f, cw, ch))
        _, f = compose(ins.title(b), subtitle(m), cols, os.path.join(a.out, stem + '.jpg'), game)
        _, info = sc4_render(ins, b, r, 0.25, ss=1)
        report.append({'stem': stem, 'exemplar': ex, 'name': ins.title(b), 'sc4_view': V.VIEW_NAMES[r],
                       'sc3_slot': slot, 'scale_vs_zoom4': round(f, 3), 'ingame': bool(games),
                       'props': [info['props'], info['prop_rows']], 'tex_rows': info['tex_rows'],
                       'lot_m': info.get('lot_m'), 'check': check(ins, b, r)})
        print(stem, ins.title(b), 'view', V.VIEW_NAMES[r], 'slot', slot, 'x%.2f' % f, 'in game' if games else '')
    if a.rotations and (not only or 'rotations' in only):
        ex = a.rotations
        m = models[ex]
        nm = ins.title(ins.by[ex]).lower().replace(' ', '_')
        rotations(ins, ins.by[ex], m, os.path.join(a.conv, 'sc3build', m['file'][:-4]),
                  os.path.join(a.out, '00_%s_four_sides.jpg' % nm))
    json.dump(report, open(os.path.join(a.out, 'sheet.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
