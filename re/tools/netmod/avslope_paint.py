"""avslope_paint.py -- art for avenue and boulevard halves on a slope (task avslope, 2026-10-26).

On a legal slope the stock game puts a plain sloped road (11202 / 11201, steep 32 / 31) in every avenue cell, so a sloped
stretch of avenue loses the median trees, the white dashes and the wide asphalt of 11204. The AVL block already writes
one-way variants of those slope pieces on the halves of a converted band (21718..21725, avenue_lanes). This painter
draws them as the avenue half they stand for: the flat avenue frame (avenue_markings' white-dash 11204 layer 0 + the
stock trees) laid on the slope piece's own plane.

Per variant slot r: the 11204 slot q with the same median side (the variant's median is on world side side + 1 at
state 0, AVENUE_LANES.md: a half at 11204 state s runs toward s + 3), the slope plane of the base in slot r
(slopeend_paint.slot_plane, fitted at zoom 4 from the stock frame), then
  ground  every opaque pixel of the stock slope frame -> its tile point on the plane -> the flat avenue frame's pixel
          at that point; where a tree covers the flat ground, the same point seen from the opposite slot (q ^ 2, tile
          (1 - u, 1 - v)), else the median grass beside it along the road. Scaled by the slope frame's own lighting
          (its asphalt against road 29's in the same slot).
  trees   each tree's pixels (11204 layer 1 in slots 1 / 2, the layer-0 pixels that are not ground in slots 0 / 3)
          moved up by the plane's height at the tree's foot (trunks found at zoom 4, on the median strip).
One layer, the base's frame table (its sprite class draws the slope at the right height), first-pass bit cleared
(the trees stand above the tile: NET_ART.md 8).

    py -3.12 re/tools/netmod/avslope_paint.py [--game ROOT] build <avenue_lanes package dir>   # art/<id>/ + anchors
    py -3.12 re/tools/netmod/avslope_paint.py [--game ROOT] preview OUT.png [--package DIR]   # stock vs mod scenes

Game art never goes in git: the package's art/ folder is gitignored.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from PIL import Image  # noqa: E402
import slopeend_paint as SE  # noqa: E402

ZOOMS, ROTS = 5, 4
SLOPE_BASES = (31, 32, 11201, 11202)
SE.SLOPE_PIECES_AXIS = {11202: "x", 32: "x", 11201: "z", 31: "z"}
AVENUE = 11204
_CACHE = {}


def set_game(root):
    SE.set_game(root)
    import netart as A
    A.set_game(root)
    from netmod import netart as NA                 # avenue_markings' own import of the same module
    NA.set_game(root)


def stock(pid, layer=0):
    k = ("stock", pid, layer)
    if k not in _CACHE:
        import netart as A
        _CACHE[k] = A.stock_frames(pid, layer)
    return _CACHE[k]


def avenue_l0(z, q):
    """the white-dash 11204 frame (avenue_markings.frame, the art the release ships for 11204 / 21700)"""
    k = ("av", z, q)
    if k not in _CACHE:
        import avenue_markings as AM
        im, LT, _ = AM.frame(AVENUE, z, q)
        _CACHE[k] = (np.array(im.convert("RGBA")).astype(np.float32), LT)
    return _CACHE[k]


# ------------------------------------------------------------------------------------------- flat avenue frame model

def flat_uv(z, shape, LT):
    W = 8 << z
    hh, w = shape[:2]
    ys, xs = np.mgrid[0:hh, 0:w]
    X = xs + 0.5 - LT[0]
    Y = ys + 0.5 - LT[1]
    s, d = 2 * X / W, 4 * Y / W
    return (s - d) / 2, (s + d) / 2


def flat_xy(z, LT, u, v):
    W = 8 << z
    return (u + v) * W / 2 + LT[0], (v - u) * W / 4 + LT[1]


def across_along(q, u, v):
    """11204 slot q (state q seen from view 0): median on world side q. -> (a = distance from the median edge,
    t = along the road) in tile units. View 0 tile edges: N v = 0, E u = 0, S v = 1, W u = 1."""
    return [(v, u), (u, v), (1 - v, u), (1 - u, v)][q]


def from_at(q, a, t):
    return [(t, a), (a, t), (t, 1 - a), (1 - a, t)][q]


def tree_mask(z, q):
    """bool mask over avenue_l0(z, q): the tree pixels"""
    k = ("tm", z, q)
    if k in _CACHE:
        return _CACHE[k]
    src, LT = avenue_l0(z, q)
    al = src[..., 3] >= 128
    u, v = flat_uv(z, src.shape, LT)
    inside = (u >= -0.01) & (u <= 1.01) & (v >= -0.01) & (v <= 1.01)
    near = (u >= -0.04) & (u <= 1.04) & (v >= -0.04) & (v <= 1.04)      # the rim pixels are curb, not tree
    m = al & ~near
    if q in (1, 2):                              # the stock tree layer
        l1 = stock(AVENUE, 1).get((z, q))
        if l1:
            im1, LT1 = l1
            a1 = np.array(im1)[..., 3] >= 128
            ys, xs = np.nonzero(a1)
            X = xs - LT1[0] + LT[0]
            Y = ys - LT1[1] + LT[1]
            ok = (X >= 0) & (X < src.shape[1]) & (Y >= 0) & (Y < src.shape[0])
            m[Y[ok], X[ok]] = True
    else:                                        # differs from the opposite slot's ground at the same tile point
        o, LTo = avenue_l0(z, q ^ 2)
        mo = tree_mask(z, q ^ 2)
        X, Y = flat_xy(z, LTo, 1 - u, 1 - v)
        Xi = np.clip(np.floor(X).astype(int), 0, o.shape[1] - 1)
        Yi = np.clip(np.floor(Y).astype(int), 0, o.shape[0] - 1)
        g = o[Yi, Xi]
        valid = inside & al & ~mo[Yi, Xi] & (g[..., 3] >= 128)
        diff = np.abs(src[..., :3] - g[..., :3]).sum(-1)
        cand = valid & (diff > 60)
        # keep a candidate only if it hangs from a tree above it (a trunk, a crown over the road); the median strip's
        # own edge differs between the two slots too and must stay ground
        keep = np.zeros_like(cand)
        for y in range(1, cand.shape[0]):
            keep[y] = cand[y] & (keep[y - 1] | m[y - 1])
        m |= keep
        # the trunks' lowest pixels lie on the road's rim, which the masks above leave as ground: run each trunk
        # down to its foot (trunks() is measured in slots 1 / 2 only, so this does not recurse)
        _CACHE[k] = m
        for a, t in trunks(q):
            fu, fv = from_at(q, a, t)
            Xf, Yf = flat_xy(z, LT, fu, fv)
            Xf, Yf = int(Xf), int(round(Yf))
            for X in range(Xf - (1 if z >= 3 else 0), Xf + (2 if z >= 3 else 1)):
                if not (0 <= X < m.shape[1]):
                    continue
                ys = np.nonzero(m[:Yf, X])[0]
                if len(ys):
                    col = slice(ys.max(), min(Yf + 1, m.shape[0]))
                    m[col, X] |= al[col, X]
    _CACHE[k] = m
    return m


def is_green(px):
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    return (g > r + 8) & (g > b + 8) | ((r > b + 25) & (g < r))      # foliage, or the pink / brown trunks


def dilate(m, n):
    out = m.copy()
    for _ in range(n):
        g = out.copy()
        g[1:] |= out[:-1]
        g[:-1] |= out[1:]
        g[:, 1:] |= out[:, :-1]
        g[:, :-1] |= out[:, 1:]
        out = g
    return out


def ground_mask_bad(z, q):
    """pixels of avenue_l0(z, q) that are not clean ground: the trees grown by their anti-aliased rim (layer 0's
    crowns are a pixel or two wider than layer 1's)"""
    k = ("gb", z, q)
    if k not in _CACHE:
        _CACHE[k] = dilate(tree_mask(z, q), 1 if z < 3 else 2)
    return _CACHE[k]


def ground_sample(z, q, u, v):
    """-> (RGBA float array, ok bool) of the flat avenue ground (no trees) at tile points (u, v) of slot q"""
    src, LT = avenue_l0(z, q)
    m = ground_mask_bad(z, q)
    hh, w = src.shape[:2]
    X, Y = flat_xy(z, LT, u, v)
    Xi = np.clip(np.floor(X).astype(int), 0, w - 1)
    Yi = np.clip(np.floor(Y).astype(int), 0, hh - 1)
    out = src[Yi, Xi].copy()
    ok = (out[..., 3] >= 128) & ~m[Yi, Xi]
    o, LTo = avenue_l0(z, q ^ 2)
    mo = ground_mask_bad(z, q ^ 2)
    X2, Y2 = flat_xy(z, LTo, 1 - u, 1 - v)
    X2i = np.clip(np.floor(X2).astype(int), 0, o.shape[1] - 1)
    Y2i = np.clip(np.floor(Y2).astype(int), 0, o.shape[0] - 1)
    g2 = o[Y2i, X2i]
    ok2 = ~ok & (g2[..., 3] >= 128) & ~mo[Y2i, X2i]
    out[ok2] = g2[ok2]
    return out, ok | ok2


def ground(z, q, u, v):
    """ground_sample with the holes (tree feet in both slots) filled from the same across position along the road"""
    out, ok = ground_sample(z, q, u, v)
    a, t = across_along(q, u, v)
    for dt in (0.06, -0.06, 0.12, -0.12, 0.2, -0.2, 0.3, -0.3, 0.45, -0.45):
        if ok.all():
            break
        uu, vv = from_at(q, a, (t + dt) % 1.0)
        g, gok = ground_sample(z, q, uu, vv)
        take = ~ok & gok
        out[take] = g[take]
        ok = ok | take
    return out, ok


def _feet_seen(q):
    """tree feet seen in slot q at zoom 4: the lowest tree pixel of each column on the median strip, per run of
    columns -> [(a, t)]"""
    z = 4
    src, LT = avenue_l0(z, q)
    m = tree_mask(z, q)
    u, v = flat_uv(z, m.shape, LT)
    cols = []
    for X in range(m.shape[1]):
        ys = np.nonzero(m[:, X])[0]
        if not len(ys):
            continue
        Y = ys.max()
        a, t = across_along(q, u[Y, X], v[Y, X])
        if -0.03 <= a <= 0.08 and -0.05 <= t <= 1.05:
            cols.append((X, Y, a, t))
    runs, cur = [], []
    for c in cols:
        if cur and c[0] != cur[-1][0] + 1:
            runs.append(cur)
            cur = []
        cur.append(c)
    if cur:
        runs.append(cur)
    return [tuple(float(x) for x in max(r, key=lambda c: c[1])[2:]) for r in runs if len(r) >= 2]


def trunks(q):
    """tree feet (a, t) in slot q. The trees stand ON the median strip only in slots 1 / 2 (the median at the front
    edge, every foot visible); in slots 0 / 3 the strip is the back edge and the feet hide under the road's rim. The
    trees are the same in every slot (slot q + 1 = slot q turned 90 degrees: a and t keep, 180 degrees: t -> 1 - t),
    so the feet are measured in slots 1 and 2 and averaged."""
    k = ("tr", q)
    if k in _CACHE:
        return _CACHE[k]
    f1, f2 = sorted(_feet_seen(1), key=lambda f: f[1]), sorted(_feet_seen(2), key=lambda f: f[1])
    feet = []
    for a, t in f1:
        b = min(f2, key=lambda f: abs(f[1] - t)) if f2 else (a, t)
        feet.append(((a + b[0]) / 2, (t + b[1]) / 2))
    if q in (0, 3):
        feet = [(a, 1 - t) for a, t in feet]
    _CACHE[k] = feet
    return feet


# ------------------------------------------------------------------------------------------------- the variant frame

def lighting(base, z, r):
    """per-channel factor: the slope frame's asphalt against road 29's in the same slot"""
    def asphalt(im):
        a = np.array(im).astype(np.float32)
        px = a[a[..., 3] >= 128][:, :3]
        grey = px[(px.max(1) < 118) & (px.max(1) - px.min(1) < 22)]
        return grey.mean(0) if len(grey) > 20 else None
    s = asphalt(stock(base)[(z, r)][0])
    f = asphalt(stock(29)[(z, r)][0])
    if s is None or f is None:
        return np.ones(3, np.float32)
    return np.clip(s / f, 0.7, 1.4)


def avenue_trees(z, q):
    """the trees of the flat avenue frame (slot q): -> (x, y offsets from the registration point, colours, the foot
    each pixel belongs to, the feet in tile (u, v))"""
    src, LT = avenue_l0(z, q)
    ys, xs = np.nonzero(tree_mask(z, q))
    feet = [from_at(q, a, t) for a, t in trunks(q)]
    return xs - LT[0], ys - LT[1], src[ys, xs], _nearest_foot(z, xs - LT[0], feet), feet


def _nearest_foot(z, tx, feet):
    if not feet or not len(tx):
        return np.zeros(len(tx), int)
    W = 8 << z
    fxs = np.array([(fu + fv) * W / 2 for fu, fv in feet])
    return np.abs(np.asarray(tx)[:, None] + 0.5 - fxs[None, :]).argmin(1)


class PngSource:
    """a package's flat art (png_dir with anchors.json, layer 0 = ground without trees, layer 1 = trees, as the
    boulevard pieces 20700 / 20701 ship)"""

    def __init__(self, d):
        anc = json.load(open(os.path.join(d, "anchors.json"), encoding="utf-8"))
        self.l0, self.l1 = {}, {}
        for z in range(ZOOMS):
            for r in range(ROTS):
                for layer, store in ((0, self.l0), (1, self.l1)):
                    nm = ("z%d_r%d.png" if layer == 0 else "l1_z%d_r%d.png") % (z, r)
                    f = os.path.join(d, nm)
                    if os.path.isfile(f):
                        store[(z, r)] = (np.array(Image.open(f).convert("RGBA")).astype(np.float32), tuple(anc[nm]))
        self._feet = {}

    def ground(self, z, q, u, v):
        src, LT = self.l0[(z, q)]
        X, Y = flat_xy(z, LT, u, v)
        Xi = np.clip(np.floor(X).astype(int), 0, src.shape[1] - 1)
        Yi = np.clip(np.floor(Y).astype(int), 0, src.shape[0] - 1)
        out = src[Yi, Xi].copy()
        ok = out[..., 3] >= 128
        for f in (0.015, 0.03, 0.05):                # the frame's rim pixel is transparent: take the one just inside
            if ok.all():
                break
            g, gok = self.ground_at(z, q, 0.5 + (u - 0.5) * (1 - 2 * f), 0.5 + (v - 0.5) * (1 - 2 * f))
            take = ~ok & gok
            out[take] = g[take]
            ok |= take
        return out, ok

    def ground_at(self, z, q, u, v):
        src, LT = self.l0[(z, q)]
        X, Y = flat_xy(z, LT, u, v)
        Xi = np.clip(np.floor(X).astype(int), 0, src.shape[1] - 1)
        Yi = np.clip(np.floor(Y).astype(int), 0, src.shape[0] - 1)
        out = src[Yi, Xi].copy()
        return out, out[..., 3] >= 128

    def feet(self, q):
        """tree feet in tile (u, v), from the zoom-4 tree layer: the lowest trunk pixel (pink / brown, redder than
        green) of each run of trunk columns"""
        if q in self._feet:
            return self._feet[q]
        feet = []
        if (4, q) in self.l1:
            a, LT = self.l1[(4, q)]
            al = a[..., 3] >= 128
            trunk = al & (a[..., 0] > a[..., 1] + 5)
            cols = [(X, np.nonzero(trunk[:, X])[0].max()) for X in range(a.shape[1]) if trunk[:, X].any()]
            runs, cur = [], []
            for c in cols:
                if cur and c[0] > cur[-1][0] + 1:
                    runs.append(cur)
                    cur = []
                cur.append(c)
            if cur:
                runs.append(cur)
            for rn in runs:
                X, Y = max(rn, key=lambda c: c[1])
                s_, d_ = 2 * (X + 0.5 - LT[0]) / 128.0, 4 * (Y + 0.5 - LT[1]) / 128.0
                feet.append(((s_ - d_) / 2, (s_ + d_) / 2))
        self._feet[q] = feet
        return feet

    def trees(self, z, q):
        if (z, q) not in self.l1:
            e = np.zeros(0, int)
            return e, e, np.zeros((0, 4), np.float32), e, []
        a, LT = self.l1[(z, q)]
        ys, xs = np.nonzero(a[..., 3] >= 128)
        feet = self.feet(q)
        return xs - LT[0], ys - LT[1], a[ys, xs], _nearest_foot(z, xs - LT[0], feet), feet


def variant_frame(base, side, z, r):
    """-> (RGBA image, (L, T), info) of the avenue half on slope `base` whose lanes run toward world side `side` at
    state 0, in rotation slot r"""
    return slope_frame(base, z, r, (r + side + 1) & 3, ground, avenue_trees)


def slope_frame(base, z, r, q, ground_fn, trees_fn):
    """slot r of a variant of slope piece `base` drawn as slot q of a flat piece: ground_fn(z, q, u, v) -> (RGBA, ok),
    trees_fn(z, q) -> (x, y offsets, colours, foot index, feet (u, v))"""
    sim, sLT = stock(base)[(z, r)]
    iou, high, mag, ref = SE.slot_plane(base, r)
    h = SE.heights(high, mag, ref)
    salpha = np.array(sim)[..., 3] >= 128
    u, v = SE.tile_uv(z, sim.size, sLT, h)
    uc, vc = np.clip(u, 0.0, 1.0), np.clip(v, 0.0, 1.0)
    g, gok = ground_fn(z, q, uc, vc)
    g[..., :3] *= lighting(base, z, r)
    pu = 1 << z
    # trees: moved up by the plane height at their foot (one whole-pixel shift per tree)
    tx, ty, col, k, feet = trees_fn(z, q)
    tpx = None
    if len(tx) and feet:
        e = np.array([h["L"] + (h["T"] - h["L"]) * fu + (h["B"] - h["L"]) * fv for fu, fv in feet])
        tpx = (tx, ty + np.round(-e * pu)[k], col)
    # canvas: the slope frame, grown to hold the trees
    w, hh = sim.size
    x0, y0, x1, y1 = -sLT[0], -sLT[1], w - sLT[0], hh - sLT[1]
    if tpx is not None:
        x0, y0 = min(x0, int(np.floor(tpx[0].min()))), min(y0, int(np.floor(tpx[1].min())))
        x1, y1 = max(x1, int(np.ceil(tpx[0].max())) + 1), max(y1, int(np.ceil(tpx[1].max())) + 1)
    W, H = x1 - x0, y1 - y0
    out = np.zeros((H, W, 4), np.float32)
    oy, ox = -sLT[1] - y0, -sLT[0] - x0
    sub = out[oy:oy + hh, ox:ox + w]
    fill = salpha & gok
    sub[fill] = g[fill]
    keep = salpha & ~gok                             # no flat ground found: the slope piece's own pixel
    sub[keep] = np.array(sim).astype(np.float32)[keep]
    sub[salpha, 3] = 255
    if tpx is not None:
        X = np.round(tpx[0] - x0).astype(int)
        Y = np.round(tpx[1] - y0).astype(int)
        ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
        out[Y[ok], X[ok]] = tpx[2][ok]
        out[Y[ok], X[ok], 3] = 255
    out[..., 3] = np.where(out[..., 3] >= 128, 255, 0)
    out[out[..., 3] == 0, :3] = 0
    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    info = dict(q=q, iou=round(iou, 3), high=high, mag=mag, ref=ref, trees=len(feet),
                ground_missing=int((salpha & ~gok).sum()))
    return img, (-x0, -y0), info


def avl_slopes(pkg):
    """avlc lines of the package on the slope bases -> {piece: (base, side)}"""
    man = json.load(open(os.path.join(pkg, "manifest.json"), encoding="utf-8"))
    out = {}
    for ln in man.get("avenue_lines", []):
        p = ln.split()
        if p[0] == "avlc" and int(p[2]) in SLOPE_BASES:
            out[int(p[1])] = (int(p[2]), int(p[3]))
    return man, out


def cmd_build(pkg):
    man, roles = avl_slopes(pkg)
    for vid, (base, side) in sorted(roles.items()):
        d = os.path.join(pkg, "art", str(vid))
        os.makedirs(d, exist_ok=True)
        anc = {"_note": "avslope_paint.py: avenue half on slope %d, lanes toward side %d at state 0" % (base, side)}
        infos = []
        for z in range(ZOOMS):
            for r in range(ROTS):
                img, LT, info = variant_frame(base, side, z, r)
                name = "z%d_r%d.png" % (z, r)
                img.save(os.path.join(d, name))
                anc[name] = [int(LT[0]), int(LT[1])]
                infos.append((z, r, info))
        json.dump(anc, open(os.path.join(d, "anchors.json"), "w", encoding="utf-8"), indent=1)
        z4 = [i for z, r, i in infos if z == 4]
        print("%d: base %d side %d -> %s (zoom 4: q %s, trees %s, ground missing %s px)" % (
            vid, base, side, d, [i["q"] for i in z4], [i["trees"] for i in z4], [i["ground_missing"] for i in z4]))


# ------------------------------------------------------------------------------------------ boulevards on slopes

BV_OUTER, BV_MIDDLE = 20700, 20701
LF = chr(10)
BVS_FIRST = 27100                                 # task avslope ids 27100..27199 (STATUS_avslope.md)
SLOPE_AXIS = {11202: "x", 32: "x", 11201: "z", 31: "z"}


def bvs_layout():
    """-> [(id, role, slope piece, side)] of package boulevard_slopes: the sloped outer per slope piece and direction
    (in avenue_lanes' order: 31 S N, 32 E W, 11201 S N, 11202 E W), then the sloped middle per slope piece"""
    out, vid = [], BVS_FIRST
    for b, sides in ((31, (2, 0)), (32, (1, 3)), (11201, (2, 0)), (11202, (1, 3))):
        for sd in sides:
            out.append((vid, "o", b, sd))
            vid += 1
    for b in (31, 32, 11201, 11202):
        out.append((vid, "m", b, None))
        vid += 1
    return out


def bvs_manifest(pkg, avl_pkg):
    """write package boulevard_slopes (manifest + lanes specs: the outer = avenue_lanes' one-way slope lanes, the
    middle keeps the slope piece's own two-way lanes)"""
    _, avl = avl_slopes(avl_pkg)
    by = {(b, sd): vid for vid, (b, sd) in avl.items()}
    variants, lanes, lines = [], [], []
    for vid, role, b, sd in bvs_layout():
        name = ({"*": "Boulevard (one way), slope", "ENGLISH": "Bulevar (un sentido), pendiente"} if role == "o" else
                {"*": "Boulevard, slope", "ENGLISH": "Bulevar, pendiente"})
        variants.append({"id": vid, "base": b, "network": "ROAD", "name": name, "trblkatt": "copy_base",
                         "art": {"from": b, "png_dir": "art/%d" % vid, "first_pass": False}})
        if role == "o":
            spec = json.load(open(os.path.join(avl_pkg, "avl_%d.lanes.json" % by[(b, sd)]), encoding="utf-8"))
            spec["piece"] = vid
            spec["_comment"] = ("task avslope: the sloped boulevard outer on %d, lanes toward side %d at state 0 = "
                                "avenue_lanes %d's (20700 has avenue 21700's lane positions)" % (b, sd, by[(b, sd)]))
            fn = "bvs_%d.lanes.json" % vid
            json.dump(spec, open(os.path.join(pkg, fn), "w", encoding="utf-8", newline=LF), indent=1)
            lanes.append({"piece": vid, "spec": fn})
            lines.append("bvs o %d %d %d" % (vid, b, sd))
        else:
            lines.append("bvs m %d %d" % (vid, b))
    man = {"netpack": 1, "name": "boulevard_slopes", "version": "1.0.0", "author": "netmod (task avslope)",
           "description": "Boulevards on slopes (owner 2026-10-26: 'check for 3 road avenues for the same'). On a legal "
           "slope the stock game puts the plain slope piece (11202 / 11201, steep 32 / 31) in every road cell; sc3netmod's "
           "BV block writes these instead on a boulevard's sloped cells (sc3netmod_bvs.c): %d..%d the sloped outer "
           "carriageway, one per slope piece and direction (one-way lanes as avenue_lanes' slope pieces), %d..%d the "
           "sloped middle (two-way, the tree median), one per slope piece. Art: the boulevard package's own 20700 / "
           "20701 laid on the slope piece's plane (avslope_paint.py bvbuild). All save as the slope piece, so a game "
           "without the mod loads the stock slope." % (BVS_FIRST, BVS_FIRST + 7, BVS_FIRST + 8, BVS_FIRST + 11),
           "variants": variants, "lanes": lanes, "boulevard_slope_lines": lines}
    json.dump(man, open(os.path.join(pkg, "manifest.json"), "w", encoding="utf-8", newline=LF), indent=1,
              ensure_ascii=False)
    print("wrote", os.path.join(pkg, "manifest.json"), len(variants), "variants")


def cmd_bvbuild(pkg, bv_pkg):
    """art of package boulevard_slopes from the boulevard package's flat art (bv_pkg/art/20700, 20701)"""
    outer, middle = PngSource(os.path.join(bv_pkg, "art", str(BV_OUTER))), PngSource(os.path.join(bv_pkg, "art", str(BV_MIDDLE)))
    for vid, role, b, sd in bvs_layout():
        d = os.path.join(pkg, "art", str(vid))
        os.makedirs(d, exist_ok=True)
        src = outer if role == "o" else middle
        anc = {"_note": "avslope_paint.py bvbuild: boulevard %s on slope %d%s" % (
            "outer" if role == "o" else "middle", b, ", lanes toward side %d at state 0" % sd if role == "o" else "")}
        infos = []
        for z in range(ZOOMS):
            for r in range(ROTS):
                # outer: 20700 at state s runs toward (s + 3) % 4 (as 11204); middle: two-way, 180-degree symmetric,
                # BV writes it at state 0 along x and 1 along z
                q = ((r + sd + 1) if role == "o" else (r + (0 if SLOPE_AXIS[b] == "x" else 1))) & 3
                img, LT, info = slope_frame(b, z, r, q, src.ground, src.trees)
                name = "z%d_r%d.png" % (z, r)
                img.save(os.path.join(d, name))
                anc[name] = [int(LT[0]), int(LT[1])]
                infos.append((z, info))
        json.dump(anc, open(os.path.join(d, "anchors.json"), "w", encoding="utf-8"), indent=1)
        z4 = [i for z, i in infos if z == 4]
        print("%d: %s on %d -> q %s, trees %s, ground missing %s px" % (vid, role, b, [i["q"] for i in z4],
                                                                        [i["trees"] for i in z4],
                                                                        [i["ground_missing"] for i in z4]))


# ----------------------------------------------------------------------------------------------- scene preview

def _merge(layers):
    """[(image, (L, T))] -> one (image, (L, T)) holding them all, in order"""
    L = max(LT[0] for _, LT in layers)
    T = max(LT[1] for _, LT in layers)
    R = max(im.width - LT[0] for im, LT in layers)
    B = max(im.height - LT[1] for im, LT in layers)
    out = Image.new("RGBA", (L + R, T + B), (0, 0, 0, 0))
    for im, LT in layers:
        out.alpha_composite(im.convert("RGBA"), (L - LT[0], T - LT[1]))
    return out, (L, T)


def flat_avenue_frames():
    """{(z, r): (image, LT)} of the release's flat 11204 (white-dash layer 0 + stock tree layer 1)"""
    out = {}
    l1 = stock(AVENUE, 1)
    for z in range(ZOOMS):
        for r in range(ROTS):
            a, LT = avenue_l0(z, r)
            parts = [(Image.fromarray(a.astype(np.uint8)), LT)]
            if (z, r) in l1:
                parts.append(l1[(z, r)])
            out[(z, r)] = _merge(parts)
    return out


def load_art(d):
    anc = json.load(open(os.path.join(d, "anchors.json"), encoding="utf-8"))
    fr = {}
    for z in range(ZOOMS):
        for r in range(ROTS):
            nm = "z%d_r%d.png" % (z, r)
            fr[(z, r)] = (Image.open(os.path.join(d, nm)).convert("RGBA"), tuple(anc[nm]))
    return fr


def avenue_scene(axis, mag, rows, mod, pkg, n=9):
    """an avenue (rows = [(row offset, 11204 state, flat frames, {base: {state: variant frames}})]) along `axis`
    over a plateau `mag` units high on cells 3..5 of a strip of n cells: slope cells 2 (up) and 6 (down)."""
    s = SE.Scene(n)
    for X in range(n + 1):
        for Z in range(n + 1):
            k = X if axis == "x" else Z
            s.H[(X, Z)] = mag if 3 <= k <= 6 else 0
    for off, st11204, flat, slopes in rows:
        for i in range(n):
            c = (i, 3 + off) if axis == "x" else (3 + off, i)
            row = s.row(*c)
            if row is None:
                s.cells[c] = (flat, st11204)
                continue
            pid, st = SE.SLOPE_PIECE[row]
            fr = slopes.get(pid, {}).get(st) if mod else None
            if fr is None:
                fr = {k: v for k, v in stock(pid).items()}
            fr = dict(fr)
            for (z, r), v in stock(pid).items():
                fr[("plane", z, r)] = v
            s.cells[c] = (fr, st)
    return s


def avenue_rows(axis, pkg):
    """the two halves of an avenue along `axis`: (row offset, 11204 state, flat frames, sloped variant frames)"""
    _, roles = avl_slopes(pkg)
    flat = flat_avenue_frames()
    out = []
    for off, st in ((0, 2), (1, 0)) if axis == "x" else ((0, 1), (1, 3)):
        d = (st + 3) % 4                               # the half's direction
        sl = {}
        for vid, (base, side) in roles.items():
            for vst in (0, 2):
                if (side + vst) % 4 == d and SE.SLOPE_PIECES_AXIS[base] == axis:
                    sl.setdefault(base, {})[vst] = load_art(os.path.join(pkg, "art", str(vid)))
        out.append((off, st, flat, sl))
    return out


def png_frames(d):
    """{(z, r): (image, LT)} of a package art dir, layer 1 merged over layer 0"""
    src = PngSource(d)
    out = {}
    for k, (a, LT) in src.l0.items():
        parts = [(Image.fromarray(a.astype(np.uint8)), LT)]
        if k in src.l1:
            parts.append((Image.fromarray(src.l1[k][0].astype(np.uint8)), src.l1[k][1]))
        out[k] = _merge(parts)
    return out


def bv_rows(axis, pkg, bv_pkg):
    """the three rows of a boulevard along `axis` (BV: outer rows at the 11204 states, the middle at 0 + axis)"""
    fo, fm = png_frames(os.path.join(bv_pkg, "art", str(BV_OUTER))), png_frames(os.path.join(bv_pkg, "art", str(BV_MIDDLE)))
    lay = bvs_layout()
    rows = []
    for off, role, st in (((0, "o", 2), (1, "m", 0), (2, "o", 0)) if axis == "x" else ((0, "o", 1), (1, "m", 1), (2, "o", 3))):
        sl = {}
        for vid, rl, b, sd in lay:
            if rl != role or SLOPE_AXIS[b] != axis:
                continue
            for vst in (0, 2):
                if role == "m" or (sd + vst) % 4 == (st + 3) % 4:
                    sl.setdefault(b, {})[vst] = load_art(os.path.join(pkg, "art", str(vid)))
        rows.append((off, st, fo if role == "o" else fm, sl))
    return rows


def cmd_preview(out_png, pkg, zoom=4, views=(0, 1, 2, 3), bv_pkg=None):
    tiles = []
    for axis in ("x", "z"):
        rows = bv_rows(axis, pkg, bv_pkg) if bv_pkg else avenue_rows(axis, pkg)
        for mag in (1, 2):
            tiles.append(("%s along %s, slope %d" % ("boulevard" if bv_pkg else "avenue", axis, mag),
                          [avenue_scene(axis, mag, rows, mod, pkg).render(zoom, vw) for mod in (False, True)
                           for vw in views]))
    cw = max(im.width for _, r in tiles for im in r)
    ch = max(im.height for _, r in tiles for im in r)
    from PIL import ImageDraw
    sheet = Image.new("RGBA", (cw * len(views) * 2 + 20, (ch + 18) * len(tiles) + 24), (24, 24, 24, 255))
    d = ImageDraw.Draw(sheet)
    d.text((6, 6), "STOCK LOOK (views %s)" % ",".join(map(str, views)), fill=(255, 255, 255, 255))
    d.text((cw * len(views) + 26, 6), "WITH THE SLOPED ART", fill=(255, 255, 255, 255))
    for i, (lab, row) in enumerate(tiles):
        y = 24 + i * (ch + 18)
        d.text((6, y), lab, fill=(255, 255, 255, 255))
        for j, im in enumerate(row):
            sheet.alpha_composite(im, (j * cw + (20 if j >= len(views) else 0), y + 14))
    sheet.save(out_png)
    print("wrote", out_png, sheet.size)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", default=os.environ.get("SC3_GAME_ROOT"))
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build")
    b.add_argument("package")
    m = sp.add_parser("bvmanifest")
    m.add_argument("package")
    m.add_argument("--avenue-lanes", required=True)
    bb = sp.add_parser("bvbuild")
    bb.add_argument("package")
    bb.add_argument("--boulevard", required=True, help="the boulevard package dir (its art/20700, art/20701)")
    p = sp.add_parser("preview")
    p.add_argument("out")
    p.add_argument("--package", required=True)
    p.add_argument("--zoom", type=int, default=4)
    p.add_argument("--boulevard", help="preview boulevard_slopes (--package) with this boulevard package's flat art")
    a = ap.parse_args(argv)
    if a.game:
        set_game(a.game)
    if a.cmd == "build":
        cmd_build(a.package)
    elif a.cmd == "bvmanifest":
        bvs_manifest(a.package, a.avenue_lanes)
    elif a.cmd == "bvbuild":
        cmd_bvbuild(a.package, a.boulevard)
    elif a.cmd == "preview":
        cmd_preview(a.out, a.package, a.zoom, bv_pkg=a.boulevard)


if __name__ == "__main__":
    main()
