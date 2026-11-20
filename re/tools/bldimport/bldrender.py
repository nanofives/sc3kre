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

Render styles (task bldlook 2026-11-18c, BUILDING_ART.md 4.1): `stock` (default: the stock art's axis wall light,
zoom 4 = zoom 3 doubled, 255-colour palette per frame, stock contrast / saturation / lawn per zoom, surface grain,
darker front lawn edge), `stock_sharp` (the same with a native zoom 4), `clean` (the 2026-11-18b look, byte for
byte). Pick one with render_model(..., style=) or $SC3BLD_STYLE.

Public: load_obj, place, render_model -> {(z, r): (RGBA image, (L, T))}, CALIB, STYLES, DEFAULT_STYLE.
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

# ============================================================================================== styles (task bldlook)
# Measured on 75 stock growables x 16 frames (verify/bldlook/RESULTS.md, BUILDING_ART.md 4.1). The `stock` style's
# numbers are fitted to that table; `clean` is the 2026-11-18b look, unchanged.
#   light    "sun": one directional sun fixed to the screen (clean).
#            "axis": stock wall light follows the model's axis, not the screen: the model's +-u walls are the light
#            ones and the +-v walls the dark ones in EVERY slot, so the lit side swaps with each view rotation
#            (stock right/left luminance 0.81 / 1.27 / 0.81 / 1.23 in slots 0-3; the same world-axis rule as the
#            stock highway walls). Roof light from the up component.
#   zoom4    "native": own zoom-4 render. "double": zoom 3 pixel-doubled, as 1,908 of 1,936 stock zoom-4 frames are.
#   palette  None, or the colour count per frame: every stock frame holds <= 255 colours (1,200 of 1,200 frames,
#            zoom 3 median 248): the art went through an 8-bit palette per frame before the RGB565 export.
#   shadow_sun  the sun the shadow map uses (v, u, h), fixed to the screen; None = SUN. In "axis" light only
#            surfaces facing it take shadow (lawn, roofs), never a wall turned away from it.
#   rim      the stock lawn is darker along the lot's two FRONT edges (heat map of the dark lawn pixels over every
#            stock 1x1 / 2x2 lot), not in a cast shadow beside the building: a patchy band `width` cells deep.
#   values given as {zoom: value} change per zoom: stock contrast, saturation and lawn shadows all fall at the
#   smaller zooms (contrast 1.23 / 0.94 / 0.70 / 0.51, dark-lawn share 0.18 / 0.10 / 0.04 / 0.00 at zooms 3..0).
STYLES = {
    "clean": {"light": "sun", "ambient": AMBIENT, "diffuse": DIFFUSE, "shadow_keep": SHADOW_KEEP, "zoom4": "native",
              "palette": None, "dither": False, "sat": 1.0, "contrast": 1.0, "pivot": 0.45, "grain": 0.0,
              "edge": 0.0, "grass": None, "grass_amp": 0.07},
    "stock": {"light": "axis", "ambient": 0.47, "top": 0.42, "ku": 0.37, "kv": 0.20,
              "shadow_sun": None, "shadow_keep": {0: 0.25, 1: 0.40, 2: 0.55, 3: 0.70},
              "zoom4": "double", "palette": 255, "dither": False,
              "sat": {0: 2.6, 1: 2.2, 2: 2.0, 3: 2.0}, "contrast": {0: 1.4, 1: 1.2, 2: 1.3, 3: 1.35}, "pivot": 0.42,
              "grain": {0: 0.12, 1: 0.18, 2: 0.24, 3: 0.30}, "edge": 0.0,
              "rim": {"width": 0.30, "dark": {0: 0.10, 1: 0.30, 2: 0.50, 3: 0.62}},
              # lit lawn colour per zoom, fitted so the measured lit lawn = the stock median (zooms 0..3:
              # 114/137/104, 104/131/90, 99/133/81, 94/136/73)
              "grass": {0: (120, 144, 110), 1: (106, 134, 93), 2: (102, 138, 84), 3: (100, 145, 78)},
              "grass_amp": 0.10},
}
STYLES["stock_sharp"] = dict(STYLES["stock"], zoom4="native")     # stock colours and light, zoom 4 drawn natively
# task sc4conv: art that already has its light painted in (SC4 BAT renders): the texture as it is (no light, no
# vibrance, contrast or grain), the stock style's lawn, rim, zoom-3-doubled zoom 4 and 255-colour palette.
# `tone` = (gamma, gain) on the albedo luminance, hue kept: fitted on the 18 JMyers designs (72 zoom-3 frames:
# structure luminance p10 / p50 / p90 0.098 / 0.203 / 0.449 raw against the stock 0.201 / 0.400 / 0.688; with the
# tone 0.75 / 1.33 the prediction is 0.23 / 0.40 / 0.73, measured in verify/sc4conv/RESULTS.md). `baked_raw` = none.
STYLES["baked"] = dict(STYLES["stock"], light="sun", ambient=1.0, diffuse=0.0, shadow_keep=0.0, sat=1.0,
                       contrast=1.0, grain=0.0, tone=(0.75, 1.33))
STYLES["baked_raw"] = dict(STYLES["baked"], tone=None)
STYLES["baked_sharp"] = dict(STYLES["baked"], zoom4="native")   # SC4 zoom 5 has 7.0 px/m, SC3 zoom 4 5.66
DEFAULT_STYLE = "stock"

# task sc4conv switches (2026-11-18h). Both are inert for models without transparent texels / sc3slot groups.
ALPHA_TEST = os.environ.get("SC3BLD_ALPHA", "1") != "0"      # texture alpha < 0.5 = see-through (depth peeling)
SLOT_GROUPS = os.environ.get("SC3BLD_SLOTGROUPS", "1") != "0"  # OBJ group/object sc3slot<r> = drawn in slot r only
PEEL_LAYERS = 4
# task sc4lottex (2026-11-20): faces in an OBJ group / object named `sc3ground` are ground art (a converted SC4 lot's
# driveways and paths): drawn in every slot and lit like the lawn below them (the rim of the stock lots, no tone,
# saturation, grain or contrast of the model), never a shadow caster; where their texture is transparent the sample is
# the lawn itself (it lies 1 cm below), not a peeled layer. Inert for models without such a group. Off switch:
# SC3BLD_GROUNDGROUP=0.
GROUND_GROUP = os.environ.get("SC3BLD_GROUNDGROUP", "1") != "0"


def _pz(v, z):
    """A style value that may be given per zoom ({zoom: value}, the highest key <= z wins)."""
    if isinstance(v, dict):
        ks = [k for k in sorted(v) if k <= z]
        return v[ks[-1]] if ks else v[min(v)]
    return v


def _sun(v):
    if v is None:
        return SUN
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def style_of(style=None):
    """-> (name, params). None = $SC3BLD_STYLE, else DEFAULT_STYLE. A dict is taken as the params."""
    if isinstance(style, dict):
        return style.get("name", "custom"), style
    name = style or os.environ.get("SC3BLD_STYLE") or DEFAULT_STYLE
    if name not in STYLES:
        raise RenderError("render style %r: choose one of %s" % (name, ", ".join(sorted(STYLES))))
    return name, STYLES[name]


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
                im = Image.open(tp)
                cur["tex"] = np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0
                cur["tex_file"] = name
                # task sc4conv: texture alpha (cut-out art, SC4 view textures). Kept only when some texel is
                # transparent, so an opaque texture renders exactly as before. Off switch: SC3BLD_ALPHA=0.
                if ALPHA_TEST and ("A" in im.getbands() or "transparency" in im.info):
                    a = np.asarray(im.convert("RGBA"), dtype=np.uint8)[..., 3]
                    if (a < 128).any():
                        cur["alpha"] = a.astype(np.float32) / 255.0
    return mats


def load_obj(path):
    """-> mesh dict: tri (N,3,3) xyz metres, uv (N,3,2) or None per tri via has_uv (N,), mat (N,), mats [dict],
    slot (N,) int8: -1 = drawn in every rotation slot, r = only in slot r (faces in an OBJ group or object named
    `sc3slot<r>`, task sc4conv: a model that brings its own art per view, such as a converted SC4 building),
    ground (N,) bool: faces of the group `sc3ground` (task sc4lottex, GROUND_GROUP)."""
    V, VT = [], []
    tris, uvs, has, mid, slots, gnd = [], [], [], [], [], []
    cur_ground = False
    mats = {}
    mat_names = ["_default"]
    mat_list = [{"kd": (0.8, 0.8, 0.8), "tex": None, "name": "_default"}]
    cur = 0
    cur_slot = -1
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
        elif k in ("g", "o"):
            nm = " ".join(p[1:]).lower()
            cur_slot = int(nm[7]) if SLOT_GROUPS and nm.startswith("sc3slot") and nm[7:8] in "0123" \
                and len(nm) >= 8 else -1
            cur_ground = GROUND_GROUP and nm == "sc3ground"
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
                slots.append(cur_slot)
                gnd.append(cur_ground)
    if not tris:
        raise RenderError("%s: no faces" % path)
    return {"tri": np.array(tris, dtype=np.float64), "uv": np.array(uvs, dtype=np.float64),
            "has_uv": np.array(has, dtype=bool), "mat": np.array(mid, dtype=np.int32), "mats": mat_list,
            "slot": np.array(slots, dtype=np.int8), "ground": np.array(gnd, dtype=bool)}


def slot_mesh(mesh, r):
    """The faces drawn in rotation slot r (every face of a model without sc3slot groups)."""
    s = mesh.get("slot")
    if s is None or not (s >= 0).any():
        return mesh
    keep = (s < 0) | (s == r)
    out = dict(mesh)
    for k in ("tri", "uv", "has_uv", "mat", "slot", "ground"):
        if k in mesh:
            out[k] = mesh[k][keep]
    return out


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


def rasterize(sx, sy, dep, w, h, cull=None, zmin=None):
    """Triangles (N,3) in sample space -> (tri id buffer (h, w) int32 (-1 empty), barycentrics (h, w, 3), depth).
    Pixel (i, j) samples at (i + 0.5, j + 0.5). zmin (h, w): a sample only takes surfaces farther than it (depth
    peeling for alpha-tested textures; inf = take nothing there)."""
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
        if zmin is not None:
            m &= d > zmin[j0:j1 + 1, i0:i1 + 1] + 1e-7
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


def _shadow_map(t_all, res=0.004, sun=None):
    """Orthographic depth map along SUN over every triangle. -> (basis a, basis b, grid origin, res, depth map)."""
    L = SUN if sun is None else sun
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
        return _shadow_map(t_all, res, sun)
    sx, sy = (pa - amin) / res, (pb - bmin) / res
    _, _, zb = rasterize(sx, sy, -pl, W, H)                      # nearest to the light = largest p . L
    return a, b, amin, bmin, res, zb, L


def _in_shadow(pts, sm, bias):
    a, b, amin, bmin, res, zb, L = sm
    p = pts[..., [1, 0, 2]]
    i = np.clip(((p @ a - amin) / res).astype(int), 0, zb.shape[1] - 1)
    j = np.clip(((p @ b - bmin) / res).astype(int), 0, zb.shape[0] - 1)
    return zb[j, i] < (-(p @ L) - bias)


def _sample_tex(tex, uv):
    h, w = tex.shape[:2]
    x = np.mod(uv[..., 0], 1.0) * (w - 1)
    y = (1.0 - np.mod(uv[..., 1], 1.0)) * (h - 1)
    return tex[np.clip(np.rint(y).astype(int), 0, h - 1), np.clip(np.rint(x).astype(int), 0, w - 1)]


def _hash_noise(p, freq, seed=0):
    """Stable per-position value noise in [-1, 1]: one value per (1 / freq)-cell voxel of the slot-0 model space,
    so the grain sticks to the surface in every slot."""
    q = np.floor(p * freq).astype(np.int64)
    h = (q[:, 0] * 73856093) ^ (q[:, 1] * 19349663) ^ (q[:, 2] * 83492791) ^ (seed * 2654435761)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return ((h & 0xFFFF).astype(np.float32) / 32767.5) - 1.0


def _value_noise(p, freq, seed=0):
    """Smooth (trilinear) value noise in about [-1, 1] over 3D points: soft blotches of 1 / freq cells, not salt."""
    q = p * freq
    i = np.floor(q)
    f = q - i
    f = f * f * (3 - 2 * f)
    out = np.zeros(len(p), dtype=np.float32)
    for c in range(8):
        o = np.array([(c >> 0) & 1, (c >> 1) & 1, (c >> 2) & 1], dtype=np.float64)
        w = np.prod(np.where(o == 1, f, 1 - f), axis=1)
        out += w * _hash_noise((i + o) + 0.5, 1.0, seed)
    return out


def _grain(p, W, seed=0):
    """Two octaves of smooth noise at about 6 and 2 px (at the frame's zoom) on the slot-0 surface position."""
    return 0.65 * _value_noise(p, W / 6.0, seed) + 0.35 * _value_noise(p, W / 2.0, seed + 1)


def _edge_mask(ib, nrm_buf, kind_buf, ss):
    """Samples of the model next to (within ss / 2 samples) a sample of another face orientation, of the ground or
    of nothing: the creases and the silhouette that the stock renders draw a shade lighter."""
    model = (ib >= 0) & (kind_buf == 0)
    out = np.zeros_like(model)
    k = max(ss // 2, 1)
    for dy, dx in ((0, k), (0, -k), (k, 0), (-k, 0)):
        nb_i = np.roll(np.roll(ib, dy, 0), dx, 1)
        nb_k = np.roll(np.roll(kind_buf, dy, 0), dx, 1)
        nb_n = np.roll(np.roll(nrm_buf, dy, 0), dx, 1)
        diff = (nb_i < 0) | (nb_k != 0) | ((nrm_buf * nb_n).sum(-1) < 0.8)
        out |= model & diff
    return out


def render_frame(mesh, n, z, r, ss=4, ground="grass", shadows=True, calib=None, ground_tex=None, style=None):
    """One frame. mesh tri in slot-0 tile coords (u, v, h). -> (RGBA PIL image, (L, T))."""
    sname, st = style_of(style)
    mesh = slot_mesh(mesh, r)
    W = 8 << z
    dx, dy, g_px = (calib or CALIB)[z]
    g_px = _growth(g_px, n)
    g = g_px / (W / 2.0)                                         # px of growth -> tile units along u / v
    parts = [_rot_slot(mesh["tri"], n, r)]
    parts0 = [mesh["tri"]]
    # kind 0 model, 1 the lawn, 2 ground art of the model (sc3ground faces, task sc4lottex)
    gf = mesh.get("ground")
    kinds = [np.where(gf, 2, 0).astype(np.int8) if gf is not None else np.zeros(len(mesh["tri"]), dtype=np.int8)]
    n_ground = int((kinds[0] == 2).sum())
    gmesh = gf if n_ground else None
    if ground:
        gt, guv = ground_mesh(n, g)
        parts.append(_rot_slot(gt, n, r))
        parts0.append(gt)
        kinds.append(np.ones(2, dtype=np.int8))
    t = np.concatenate(parts)
    t0 = np.concatenate(parts0)                                  # the same triangles in slot 0 (model axes)
    kind = np.concatenate(kinds)
    X, Y = _screen(t, W)
    B = n * W // 4 + 1
    top = max(int(math.ceil(-Y.min() + 1)), n * W // 4)
    Hh = top + B
    Ww = n * W
    sx = (X + dx) * ss
    sy = (Y + top + dy) * ss
    dep = depth_of(t)
    ib, bb, zb = rasterize(sx, sy, dep, Ww * ss, Hh * ss)
    alpha_mats = [k for k, m in enumerate(mesh["mats"]) if m.get("alpha") is not None]
    for _ in range(PEEL_LAYERS if alpha_mats else 0):
        # task sc4conv: a sample whose texel is transparent (alpha < 0.5) takes the next surface behind it
        hole = np.zeros(ib.shape, dtype=bool)
        c = ib >= 0
        ids = ib[c]
        nm = len(mesh["tri"])
        mod = ids < nm
        idm = ids[mod]
        mids = mesh["mat"][idm]
        tr = np.zeros(len(idm), dtype=bool)
        uvt = (mesh["uv"][idm] * bb[c][mod][:, :, None]).sum(1)
        for k in alpha_mats:
            sel = (mids == k) & mesh["has_uv"][idm]
            if sel.any():
                tr[sel] = _sample_tex(mesh["mats"][k]["alpha"][..., None], uvt[sel])[:, 0] < 0.5
        if gmesh is not None:                                   # ground art: its clear texels are the lawn (below)
            tr &= ~gmesh[idm]
        cm = np.zeros(len(ids), dtype=bool)
        cm[np.where(mod)[0]] = tr
        hole[c] = cm
        if not hole.any():
            break
        ib2, bb2, zb2 = rasterize(sx, sy, dep, Ww * ss, Hh * ss, zmin=np.where(hole, zb, np.inf))
        ib[hole] = ib2[hole]
        bb[hole] = bb2[hole]
        zb[hole] = zb2[hole]
    cov = ib >= 0
    rgb = np.zeros(ib.shape + (3,), dtype=np.float32)
    if cov.any():
        ids = ib[cov]
        bw = bb[cov]
        pts = (t[ids] * bw[:, :, None]).sum(1)                   # (u, v, h) of every covered sample
        nrm = _face_normals(t)[ids]
        nrm0 = _face_normals(t0)[ids]                            # (v, u, h) of slot 0
        flip = (nrm @ F) > 0                                     # face points away from the camera: use its back
        nrm[flip] *= -1
        nrm0[flip] *= -1
        sh = None
        if shadows and (kind == 0).any():
            sm = _shadow_map(t[kind == 0], sun=_sun(st.get("shadow_sun")))   # ground art (kind 2) casts none
            sh = _in_shadow(pts, sm, bias=0.02)
            if st["light"] == "axis":           # shadows fall on what faces the shadow sun (ground, roofs), never
                sh &= (nrm @ _sun(st.get("shadow_sun"))) > 0.05     # on a wall turned away from it
        if st["light"] == "axis":
            direct = st["top"] * np.clip(nrm0[:, 2], 0, None) + st["ku"] * np.abs(nrm0[:, 1]) \
                + st["kv"] * np.abs(nrm0[:, 0])
            if sh is not None:
                direct = np.where(sh, direct * (1 - _pz(st["shadow_keep"], z)), direct)
            light = st["ambient"] + direct
        else:
            nl = np.clip(nrm @ SUN, 0, None)
            if sh is not None:
                nl = np.where(sh, nl * (1 - _pz(st["shadow_keep"], z)), nl)   # a shadowed sample keeps part of its light
            light = st["ambient"] + st["diffuse"] * nl
        alb = np.empty((len(ids), 3), dtype=np.float32)
        is_g = kind[ids] == 1
        is_l = kind[ids] == 2                                     # task sc4lottex: ground art, lit as the lawn
        if is_l.any() and alpha_mats:                             # its transparent texels: the lawn below
            li = np.where(is_l)[0]
            ml = mesh["mat"][ids[li]]
            uvl = (mesh["uv"][ids[li]] * bw[li][:, :, None]).sum(1)
            hl = mesh["has_uv"][ids[li]]
            clear = np.zeros(len(li), dtype=bool)
            for k in alpha_mats:
                sel = (ml == k) & hl
                if sel.any():
                    clear[sel] = _sample_tex(mesh["mats"][k]["alpha"][..., None], uvl[sel])[:, 0] < 0.5
            is_g = is_g.copy()
            is_g[li[clear]] = True
            is_l[li[clear]] = False
        rim = st.get("rim")
        if rim and (is_g | is_l).any() and _pz(rim["dark"], z):
            # stock lots are darker along their two FRONT edges (the lower-left u = 0 and lower-right v = n edges
            # of the frame, in every slot): a patchy band about rim["width"] cells deep (BUILDING_ART.md 4.1)
            ig = is_g | is_l
            pg = pts[ig]
            d = np.minimum(pg[:, 0], n - pg[:, 1])
            fall = np.clip(1.0 - d / rim["width"], 0, 1) ** 1.5
            patch = np.clip(0.55 + 0.6 * _value_noise(_rot_slot(pg, n, (4 - r) % 4), 4.0, 11), 0, 1)
            lg = light[ig] * (1.0 - _pz(rim["dark"], z) * fall * patch)
            light = light.copy()
            light[ig] = lg
        if is_g.any():
            gtex = ground_tex if ground_tex is not None else grass_texture(**_grass_args(st, z))
            # ground uv in slot-0 lot coordinates: undo the slot rotation of the sample position
            p0 = _rot_slot(pts[is_g], n, (4 - r) % 4)
            k_uv = GRASS_TEXELS_PER_CELL / gtex.shape[0]
            alb[is_g] = _sample_tex(gtex, np.stack([p0[:, 0] * k_uv, p0[:, 1] * k_uv], 1))
        if is_l.any():                                            # task sc4lottex: ground art, its texture as it is
            mids = mesh["mat"][ids[is_l]]
            a3 = np.array([m["kd"] for m in mesh["mats"]], dtype=np.float32)[mids]
            uvt = (mesh["uv"][ids[is_l]] * bw[is_l][:, :, None]).sum(1)
            hu = mesh["has_uv"][ids[is_l]]
            for k, m in enumerate(mesh["mats"]):
                if m.get("tex") is None:
                    continue
                sel = (mids == k) & hu
                if sel.any():
                    a3[sel] = _sample_tex(m["tex"], uvt[sel])
            alb[is_l] = a3
        mi = ~(is_g | is_l)
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
            if st.get("tone"):                                           # task sc4conv: pre-lit art
                gam, gain = st["tone"]
                y = (a2 @ np.array([0.299, 0.587, 0.114], dtype=np.float32))[:, None]
                y2 = np.clip(gain * np.power(np.maximum(y, 0), gam), 0, 1)
                a2 = np.clip(a2 * (y2 / np.maximum(y, 1e-4)), 0, 1)
            if _pz(st["sat"], z) != 1.0:
                # vibrance: stock walls and roofs are more saturated, but a colour that is already saturated is
                # pushed less (a plain gain turns a red roof pure red)
                y = (a2 @ np.array([0.299, 0.587, 0.114], dtype=np.float32))[:, None]
                s0 = (a2.max(1) - a2.min(1))[:, None] / np.maximum(a2.max(1), 1e-6)[:, None]
                k = 1.0 + (_pz(st["sat"], z) - 1.0) * (1.0 - s0)
                a2 = np.clip(y + (a2 - y) * k, 0, 1)
            if _pz(st["grain"], z):                                      # surface grain of the stock textures
                nz = _grain(_rot_slot(pts[mi], n, (4 - r) % 4), W)
                a2 = np.clip(a2 * (1.0 + _pz(st["grain"], z) * nz)[:, None], 0, 1)
            alb[mi] = a2
        if _pz(st["edge"], z):
            nb = np.zeros(ib.shape + (3,), dtype=np.float32)
            nb[cov] = nrm
            kb = np.full(ib.shape, -1, dtype=np.int8)
            kb[cov] = kind[ids]
            em = _edge_mask(ib, nb, kb, ss)[cov]
            light = np.where(em, light * (1.0 + _pz(st["edge"], z)), light)
        rgb[cov] = np.clip(alb * light[:, None], 0, 1)
        if _pz(st["contrast"], z) != 1.0:
            mo = kind[ids] == 0                                  # the model only: the lawn keeps its measured colour
            v = rgb[cov]
            y = v[mo] @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
            y2 = np.clip(st["pivot"] + (y - st["pivot"]) * _pz(st["contrast"], z), 0, 1)
            v[mo] = np.clip(v[mo] * (y2 / np.maximum(y, 1e-4))[:, None], 0, 1)   # luminance only, hue kept
            rgb[cov] = v
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
    if st["palette"]:
        img = palette_cut(img, st["palette"], st["dither"])
    return quantize565(Image.fromarray(img, "RGBA")), (0, top - cut)


def palette_cut(img, colours=255, dither=False):
    """Opaque pixels through an adaptive palette of `colours` entries per frame (median cut), as the stock frames
    were: <= 255 colours each. Transparent pixels untouched."""
    op = img[..., 3] >= 128
    if op.sum() == 0:
        return img
    px = np.ascontiguousarray(img[..., :3][op])
    if len(np.unique(px[:, 0].astype(np.int32) << 16 | px[:, 1].astype(np.int32) << 8 | px[:, 2])) <= colours:
        return img
    strip = Image.fromarray(px.reshape(1, -1, 3), "RGB")
    dm = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    q = strip.quantize(colors=colours, method=Image.Quantize.MEDIANCUT, dither=dm)
    out = img.copy()
    out[..., :3][op] = np.asarray(q.convert("RGB")).reshape(-1, 3)
    return out


def _grass_args(st, z):
    """grass_texture() keywords for a style at zoom z: base = the style's lit lawn colour / the ground's light."""
    g = st.get("grass")
    if not g:
        return {}
    c = g[min(z, max(g))]
    lit = st["ambient"] + (st["top"] if st["light"] == "axis" else st["diffuse"] * max(SUN[2], 0))
    return {"base": tuple(min(x / 255.0 / lit, 1.0) for x in c), "amp": st.get("grass_amp", 0.07)}


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


def render_model(mesh_tile, n, zooms=range(ZOOMS), ss=4, ground="grass", shadows=True, calib=None, style=None):
    """-> {(z, r): (image, (L, T))} for every zoom x slot. style: a STYLES name (None = $SC3BLD_STYLE, else
    DEFAULT_STYLE `stock`). With zoom4 "double" the zoom-4 frame is the zoom-3 frame at twice the size, anchor x 2,
    which is what the stock scale-2 frames draw."""
    sname, st = style_of(style)
    zooms = list(zooms)
    need = sorted(set(zooms) | ({3} if 4 in zooms and st["zoom4"] == "double" else set()))
    out, gts = {}, {}
    for z in need:
        if z == 4 and st["zoom4"] == "double":
            for r in range(ROTS):
                im, (L, T) = out[(3, r)]
                out[(4, r)] = (im.resize((im.width * 2, im.height * 2), Image.NEAREST), (2 * L, 2 * T))
            continue
        ga = _grass_args(st, z)
        key = tuple(sorted(ga.items()))
        if key not in gts:
            gts[key] = grass_texture(**ga)
        for r in range(ROTS):
            out[(z, r)] = render_frame(mesh_tile, n, z, r, ss=ss if z >= 2 else 8, ground=ground,
                                       shadows=shadows, calib=calib, ground_tex=gts[key], style=st)
    return {k: out[k] for k in sorted(out) if k[0] in zooms}


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
