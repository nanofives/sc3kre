r"""bldrender.py - task bldrender (2026-11-18): render a 3D model (OBJ) into SimCity 3000 building art.

No Blender needed: a small numpy rasteriser that uses the engine's own projection (re/analysis/BUILDING_ART.md):

  tile coordinates of rotation slot 0, registration point = the footprint's LEFT ground vertex:
    u = 0..n towards the top vertex, v = 0..n towards the bottom vertex, h = height in cells
    x = (u + v) * W / 2,   y = (v - u) * W / 4 - h * W * cos(30 deg) / sqrt(2)        W = 8 << zoom
  (SIMSPR 0x1000be25 draw point, 0x10006752 tile sizes, 0x1000c678 footprint anchor cell; the vertical factor is
  the 30 degree camera that makes the 2:1 diamond, netart_blender.py ALT).
  slot r = the model turned r x 90 degrees counter-clockwise on screen about the lot centre: (u, v) -> (v, n - u)
  per step (NET_ART.md 6, measured on stock network art; BUILDING_ART.md 3 checks it on stock houses).
  frame = n*W wide, anchor (L, T) = (0, T), B = n*W/4 + 1 rows below the registration row (every stock building
  frame measured, BUILDING_ART.md 2).

OBJ axes: metres, Y up (the classifier page's convention, and what Blender's OBJ exporter writes by default).
Model +X -> tile u, +Z -> tile v, +Y -> up. So the model's front (+Z, the side facing the viewer in Blender's
front view after export) lands on the lot's +v edge, the lower-right face in slot 0, where the stock houses have
their front doors (BUILDING_ART.md 3).

Public: load_obj, place, render_model -> {(z, r): (RGBA image, (L, T))}, CALIB.
"""
import math
import os

import numpy as np
from PIL import Image

ZOOMS = 5
ROTS = 4
VSCALE = math.cos(math.radians(30.0)) / math.sqrt(2.0)      # px per vertical cell unit / W = 0.6124
ELEV = math.radians(30.0)
# camera forward in (v, u, h) = Blender (X, Y, Z) of netart_blender.setup_camera; depth = p . F (larger = farther)
F = np.array([-math.cos(ELEV) / math.sqrt(2.0), math.cos(ELEV) / math.sqrt(2.0), -math.sin(ELEV)])

# Per-zoom pixel calibration of the lot diamond against stock frames (bldimport.py calibrate, BUILDING_ART.md 4):
# dx, dy = sub-pixel offset of the registration point, g = growth of the lot in px on each side, per lot size n.
# Zooms 0-3: 0 differing pixels below the registration row on every slot of 1x1 115 / 3065 / 126, 2x2 3077 / 3020,
# 3x3 3011 / 176, 4x4 3028 / 3071 and flat tile 39. Zoom 4: stock buildings show zoom 3 at scale 2, so nothing native
# to fit; n = 1 matches tile 39's native zoom 4 exactly (the edge stock roads draw next to houses), n >= 2 takes the
# middle of the zoom-3 range [UNCERTAIN: no native stock reference].
CALIB = {0: (0.0, 0.75, {1: 0.5, 2: 0.5, 3: 0.25, 4: 0.5}),
         1: (0.0, 0.25, {1: 0.5, 2: 1.0, 3: 1.0, 4: 1.0}),
         2: (0.0, 0.25, {1: 0.5, 2: 1.0, 3: 1.0, 4: 1.0}),
         3: (0.0, 0.5, {1: 0.25, 2: 0.25, 3: 0.75, 4: 0.75}),
         4: (0.0, 1.0, {1: 0.25, 2: 0.5, 3: 0.5, 4: 0.5})}


def _growth(g, n):
    if not isinstance(g, dict):
        return g
    ks = [k for k in sorted(g) if k <= n]
    return g[ks[-1]] if ks else g[min(g)]


# Sun: direction TOWARDS the light in (v, u, h). Stock art: roof brightest, the lower-left face (normal -u) lit, the
# lower-right face (normal +v) in shade (BUILDING_ART.md 5).
SUN = np.array([0.30, -0.80, 1.25])
SUN = SUN / np.linalg.norm(SUN)
AMBIENT = 0.50
DIFFUSE = 0.62
SHADOW_KEEP = 0.65          # fraction of the direct light a shadowed sample LOSES (stock shadows are soft)


class RenderError(Exception):
    pass


# ============================================================================================== OBJ

def _read_mtl(path):
    mats, cur = {}, None
    if not os.path.isfile(path):
        return mats
    base = os.path.dirname(path)
    for ln in open(path, encoding="utf-8", errors="replace"):
        p = ln.split()
        if not p or p[0].startswith("#"):
            continue
        k = p[0].lower()
        if k == "newmtl":
            cur = mats.setdefault(" ".join(p[1:]), {"kd": (0.8, 0.8, 0.8), "tex": None})
        elif cur is None:
            continue
        elif k == "kd" and len(p) >= 4:
            cur["kd"] = tuple(float(x) for x in p[1:4])
        elif k == "map_kd" and len(p) >= 2:
            name = p[-1]                                       # options (-s, -o ...) come before the file name
            tp = os.path.join(base, name)
            if os.path.isfile(tp):
                cur["tex"] = np.asarray(Image.open(tp).convert("RGB"), dtype=np.float32) / 255.0
                cur["tex_file"] = name
    return mats


def load_obj(path):
    """-> mesh dict: tri (N,3,3) xyz metres, uv (N,3,2) or None per tri via has_uv (N,), mat (N,), mats [dict]."""
    V, VT = [], []
    tris, uvs, has, mid = [], [], [], []
    mats = {}
    mat_names = ["_default"]
    mat_list = [{"kd": (0.8, 0.8, 0.8), "tex": None, "name": "_default"}]
    cur = 0
    base = os.path.dirname(os.path.abspath(path))
    for ln in open(path, encoding="utf-8", errors="replace"):
        p = ln.split()
        if not p or p[0].startswith("#"):
            continue
        k = p[0]
        if k == "v":
            V.append([float(x) for x in p[1:4]])
        elif k == "vt":
            VT.append([float(x) for x in p[1:3]] if len(p) >= 3 else [float(p[1]), 0.0])
        elif k == "mtllib":
            for name in p[1:]:
                mats.update(_read_mtl(os.path.join(base, name)))
        elif k == "usemtl":
            name = " ".join(p[1:])
            if name not in mat_names:
                m = dict(mats.get(name, {"kd": (0.8, 0.8, 0.8), "tex": None}))
                m["name"] = name
                mat_names.append(name)
                mat_list.append(m)
            cur = mat_names.index(name)
        elif k == "f":
            idx = []
            for t in p[1:]:
                a = t.split("/")
                vi = int(a[0])
                vi = vi - 1 if vi > 0 else len(V) + vi
                ti = None
                if len(a) > 1 and a[1]:
                    ti = int(a[1])
                    ti = ti - 1 if ti > 0 else len(VT) + ti
                idx.append((vi, ti))
            for j in range(1, len(idx) - 1):                    # fan
                tri = (idx[0], idx[j], idx[j + 1])
                tris.append([V[a][:3] for a, _ in tri])
                ok = all(b is not None for _, b in tri)
                uvs.append([VT[b] for _, b in tri] if ok else [[0, 0]] * 3)
                has.append(ok)
                mid.append(cur)
    if not tris:
        raise RenderError("%s: no faces" % path)
    return {"tri": np.array(tris, dtype=np.float64), "uv": np.array(uvs, dtype=np.float64),
            "has_uv": np.array(has, dtype=bool), "mat": np.array(mid, dtype=np.int32), "mats": mat_list}


def bbox(mesh):
    p = mesh["tri"].reshape(-1, 3)
    return p.min(0), p.max(0)


def place(mesh, n, cell_m=16.0, scale=1.0, rotate_deg=0.0):
    """Metres (Y up) -> tile coordinates (u, v, h) in cells, footprint centred on the n x n lot, base on the ground.
    rotate_deg turns the model counter-clockwise seen from above (about +Y) before it is placed.
    -> (mesh copy with tri in (u, v, h), info dict)."""
    p = mesh["tri"].reshape(-1, 3) * float(scale)
    a = math.radians(rotate_deg)
    c, s = math.cos(a), math.sin(a)
    x = p[:, 0] * c + p[:, 2] * s                               # CCW seen from +Y looking down
    zz = -p[:, 0] * s + p[:, 2] * c
    y = p[:, 1]
    x0, x1, z0, z1, y0, y1 = x.min(), x.max(), zz.min(), zz.max(), y.min(), y.max()
    u = (x - (x0 + x1) / 2.0) / cell_m + n / 2.0
    v = (zz - (z0 + z1) / 2.0) / cell_m + n / 2.0
    h = (y - y0) / cell_m
    out = dict(mesh)
    out["tri"] = np.stack([u, v, h], 1).reshape(-1, 3, 3)
    info = {"size_m": [float(x1 - x0), float(y1 - y0), float(z1 - z0)], "lot_m": n * cell_m,
            "fits": bool(x1 - x0 <= n * cell_m + 1e-6 and z1 - z0 <= n * cell_m + 1e-6)}
    return out, info


# ============================================================================================== raster core

def _rot_slot(t, n, r):
    """(u, v, h) of slot 0 -> slot r: r x (u, v) -> (v, n - u)."""
    u, v, h = t[..., 0], t[..., 1], t[..., 2]
    for _ in range(r % 4):
        u, v = v, n - u
    return np.stack([u, v, h], -1)


def _screen(t, W):
    u, v, h = t[..., 0], t[..., 1], t[..., 2]
    return (u + v) * W / 2.0, (v - u) * W / 4.0 - h * W * VSCALE


def depth_of(t):
    """depth along the camera forward; (v, u, h) frame: v * F[0] + u * F[1] + h * F[2]."""
    return t[..., 1] * F[0] + t[..., 0] * F[1] + t[..., 2] * F[2]


def rasterize(sx, sy, dep, w, h, cull=None):
    """Triangles (N,3) in sample space -> (tri id buffer (h, w) int32 (-1 empty), barycentrics (h, w, 3), depth).
    Pixel (i, j) samples at (i + 0.5, j + 0.5)."""
    zb = np.full((h, w), np.inf)
    ib = np.full((h, w), -1, dtype=np.int32)
    bb = np.zeros((h, w, 3), dtype=np.float32)
    for k in range(sx.shape[0]):
        x0, x1, x2 = sx[k]
        y0, y1, y2 = sy[k]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-12:
            continue
        i0 = max(int(math.floor(min(x0, x1, x2) - 0.5)), 0)
        i1 = min(int(math.ceil(max(x0, x1, x2) - 0.5)), w - 1)
        j0 = max(int(math.floor(min(y0, y1, y2) - 0.5)), 0)
        j1 = min(int(math.ceil(max(y0, y1, y2) - 0.5)), h - 1)
        if i0 > i1 or j0 > j1:
            continue
        px = np.arange(i0, i1 + 1) + 0.5
        py = np.arange(j0, j1 + 1)[:, None] + 0.5
        w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) / area
        w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) / area
        w2 = 1.0 - w0 - w1
        eps = -1e-9
        inside = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        if not inside.any():
            continue
        d = w0 * dep[k, 0] + w1 * dep[k, 1] + w2 * dep[k, 2]
        sub = zb[j0:j1 + 1, i0:i1 + 1]
        m = inside & (d < sub)
        if not m.any():
            continue
        sub[m] = d[m]
        ib[j0:j1 + 1, i0:i1 + 1][m] = k
        bsub = bb[j0:j1 + 1, i0:i1 + 1]
        bsub[..., 0][m] = w0[m]
        bsub[..., 1][m] = w1[m]
        bsub[..., 2][m] = w2[m]
    return ib, bb, zb


# ============================================================================================== ground

def grass_texture(size=256, seed=7, base=(0.34, 0.46, 0.27), amp=0.07):
    """Procedural lot ground (no game pixels): stock lawn colour (mean 86 / 118 / 70 measured on the lower quarter
    of nine stock 1x1 and 2x2 lots, BUILDING_ART.md 5, divided by the roof-up light) with soft mottling plus a fine
    per-texel grain. Tiles seamlessly; 90 texels per cell side = about one texel per pixel at zoom 4."""
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size))
    for cells, wgt in ((8, 0.45), (32, 0.30)):
        c = rng.random((cells, cells))
        c = np.concatenate([c, c[:1]], 0)
        c = np.concatenate([c, c[:, :1]], 1)
        t = np.linspace(0, cells, size, endpoint=False)
        i = t.astype(int)
        f = t - i
        row = c[i] * (1 - f)[:, None] + c[i + 1] * f[:, None]            # bilinear, periodic
        out += wgt * (row[:, i] * (1 - f)[None, :] + row[:, i + 1] * f[None, :])
    out += 0.25 * rng.random((size, size))
    out = (out - out.mean()) / (out.std() + 1e-9)
    tex = np.empty((size, size, 3), dtype=np.float32)
    for k in range(3):
        tex[..., k] = np.clip(base[k] + out * amp * (0.7 if k == 2 else 1.0), 0, 1)
    return tex


GRASS_TEXELS_PER_CELL = 90.0


def ground_mesh(n, g, kind="grass", paved=None):
    """Two triangles over the lot [-g, n+g]^2 at h = -1e-4, uv = lot coordinates."""
    a, b = -g, n + g
    tri = np.array([[[a, a, -1e-4], [b, a, -1e-4], [b, b, -1e-4]],
                    [[a, a, -1e-4], [b, b, -1e-4], [a, b, -1e-4]]], dtype=np.float64)
    uv = tri[..., :2].copy()
    return tri, uv


# ============================================================================================== shading

def _face_normals(t):
    """t in (u, v, h) -> unit normals in (v, u, h) (the right-handed frame, BUILDING_ART.md 1)."""
    p = t[..., [1, 0, 2]]
    nrm = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return nrm / ln


def _shadow_map(t_all, res=0.004):
    """Orthographic depth map along SUN over every triangle. -> (basis a, basis b, grid origin, res, depth map)."""
    L = SUN
    a = np.cross(L, [0.0, 0.0, 1.0])
    a /= np.linalg.norm(a)
    b = np.cross(L, a)
    p = t_all[..., [1, 0, 2]]                                    # (v, u, h)
    pa, pb, pl = p @ a, p @ b, p @ L
    amin, bmin = pa.min() - 4 * res, pb.min() - 4 * res
    W = int(math.ceil((pa.max() - amin) / res)) + 8
    H = int(math.ceil((pb.max() - bmin) / res)) + 8
    if W * H > 60e6:
        res *= math.sqrt(W * H / 60e6)
        return _shadow_map(t_all, res)
    sx, sy = (pa - amin) / res, (pb - bmin) / res
    _, _, zb = rasterize(sx, sy, -pl, W, H)                      # nearest to the light = largest p . L
    return a, b, amin, bmin, res, zb


def _in_shadow(pts, sm, bias):
    a, b, amin, bmin, res, zb = sm
    p = pts[..., [1, 0, 2]]
    i = np.clip(((p @ a - amin) / res).astype(int), 0, zb.shape[1] - 1)
    j = np.clip(((p @ b - bmin) / res).astype(int), 0, zb.shape[0] - 1)
    return zb[j, i] < (-(p @ SUN) - bias)


def _sample_tex(tex, uv):
    h, w = tex.shape[:2]
    x = np.mod(uv[..., 0], 1.0) * (w - 1)
    y = (1.0 - np.mod(uv[..., 1], 1.0)) * (h - 1)
    return tex[np.clip(np.rint(y).astype(int), 0, h - 1), np.clip(np.rint(x).astype(int), 0, w - 1)]


def render_frame(mesh, n, z, r, ss=4, ground="grass", shadows=True, calib=None, ground_tex=None):
    """One frame. mesh tri in slot-0 tile coords (u, v, h). -> (RGBA PIL image, (L, T))."""
    W = 8 << z
    dx, dy, g_px = (calib or CALIB)[z]
    g_px = _growth(g_px, n)
    g = g_px / (W / 2.0)                                         # px of growth -> tile units along u / v
    parts = [_rot_slot(mesh["tri"], n, r)]
    kinds = [np.zeros(len(mesh["tri"]), dtype=np.int8)]
    if ground:
        gt, guv = ground_mesh(n, g)
        parts.append(_rot_slot(gt, n, r))
        kinds.append(np.ones(2, dtype=np.int8))
    t = np.concatenate(parts)
    kind = np.concatenate(kinds)
    X, Y = _screen(t, W)
    B = n * W // 4 + 1
    top = max(int(math.ceil(-Y.min() + 1)), n * W // 4)
    Hh = top + B
    Ww = n * W
    sx = (X + dx) * ss
    sy = (Y + top + dy) * ss
    ib, bb, zb = rasterize(sx, sy, depth_of(t), Ww * ss, Hh * ss)
    cov = ib >= 0
    rgb = np.zeros(ib.shape + (3,), dtype=np.float32)
    if cov.any():
        ids = ib[cov]
        bw = bb[cov]
        pts = (t[ids] * bw[:, :, None]).sum(1)                   # (u, v, h) of every covered sample
        nrm = _face_normals(t)[ids]
        flip = (nrm @ F) > 0                                     # face points away from the camera: use its back
        nrm[flip] *= -1
        nl = np.clip(nrm @ SUN, 0, None)
        if shadows and (kind == 0).any():
            sm = _shadow_map(t[kind == 0])
            sh = _in_shadow(pts, sm, bias=0.02)
            nl = np.where(sh, nl * (1 - SHADOW_KEEP), nl)      # a shadowed sample keeps part of its direct light
        light = AMBIENT + DIFFUSE * nl
        alb = np.empty((len(ids), 3), dtype=np.float32)
        is_g = kind[ids] == 1
        if is_g.any():
            gtex = ground_tex if ground_tex is not None else grass_texture()
            # ground uv in slot-0 lot coordinates: undo the slot rotation of the sample position
            p0 = _rot_slot(pts[is_g], n, (4 - r) % 4)
            k_uv = GRASS_TEXELS_PER_CELL / gtex.shape[0]
            alb[is_g] = _sample_tex(gtex, np.stack([p0[:, 0] * k_uv, p0[:, 1] * k_uv], 1))
        mi = ~is_g
        if mi.any():
            mids = mesh["mat"][ids[mi]]
            a2 = np.array([m["kd"] for m in mesh["mats"]], dtype=np.float32)[mids]
            uvt = (mesh["uv"][ids[mi]] * bw[mi][:, :, None]).sum(1)
            hu = mesh["has_uv"][ids[mi]]
            for k, m in enumerate(mesh["mats"]):
                if m.get("tex") is None:
                    continue
                sel = (mids == k) & hu
                if sel.any():
                    a2[sel] = _sample_tex(m["tex"], uvt[sel])
            alb[mi] = a2
        rgb[cov] = np.clip(alb * light[:, None], 0, 1)
    # box filter ss x ss -> coverage alpha + mean colour of covered samples
    c = cov.reshape(Hh, ss, Ww, ss).sum((1, 3)).astype(np.float32)
    s = (rgb * cov[..., None]).reshape(Hh, ss, Ww, ss, 3).sum((1, 3))
    col = np.where(c[..., None] > 0, s / np.maximum(c, 1)[..., None], 0)
    alpha = c / (ss * ss)
    img = np.zeros((Hh, Ww, 4), dtype=np.uint8)
    img[..., :3] = np.clip(np.rint(col * 255), 0, 255).astype(np.uint8)
    img[..., 3] = np.where(alpha >= 0.5, 255, 0).astype(np.uint8)
    # trim empty rows above the content (stock T is tight), never below the lot's top vertex row
    rows = np.where(img[..., 3].any(1))[0]
    cut = min(int(rows[0]), top) if len(rows) else 0
    img = img[cut:]
    return quantize565(Image.fromarray(img, "RGBA")), (0, top - cut)


def quantize565(im):
    """The colours the game will show (5/6/5, expanded like the exporter), never the colour key (magenta)."""
    a = np.asarray(im).copy()
    q = a[..., :3].astype(np.int32)
    r5, g6, b5 = q[..., 0] >> 3, q[..., 1] >> 2, q[..., 2] >> 3
    key = (r5 == 31) & (g6 == 0) & (b5 == 31)
    b5 = np.where(key, 30, b5)
    a[..., 0] = (r5 * 255 // 31).astype(np.uint8)
    a[..., 1] = (g6 * 255 // 63).astype(np.uint8)
    a[..., 2] = (b5 * 255 // 31).astype(np.uint8)
    a[a[..., 3] < 128] = 0
    return Image.fromarray(a, "RGBA")


def render_model(mesh_tile, n, zooms=range(ZOOMS), ss=4, ground="grass", shadows=True, calib=None):
    """-> {(z, r): (image, (L, T))} for every zoom x slot."""
    out = {}
    gt = grass_texture()
    for z in zooms:
        for r in range(ROTS):
            out[(z, r)] = render_frame(mesh_tile, n, z, r, ss=ss if z >= 2 else 8, ground=ground,
                                       shadows=shadows, calib=calib, ground_tex=gt)
    return out


def sheet(frames, out_png, scale=1, bg=(60, 100, 60, 255), pad=6):
    """Contact sheet: one row per zoom, slots 0..3 left to right."""
    zs = sorted({z for z, _ in frames})
    rows = [[frames[(z, r)][0] for r in range(ROTS) if (z, r) in frames] for z in zs]
    W = max(sum(i.width for i in rw) + pad * (len(rw) + 1) for rw in rows)
    H = sum(max(i.height for i in rw) + pad for rw in rows) + pad
    im = Image.new("RGBA", (W, H), bg)
    y = pad
    for rw in rows:
        x = pad
        for f in rw:
            im.alpha_composite(f, (x, y))
            x += f.width + pad
        y += max(i.height for i in rw) + pad
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(out_png)
    return out_png
