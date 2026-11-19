#!/usr/bin/env python3
r"""reproject.py - task sc4conv (2026-11-18h): draw SC4 view boxes through SimCity 3000's camera (the decision renders).

The SC4 view textures are screen-projected renders, so drawing a view's box with its own uv through any camera is a
projective texture: every box face shows what the SC4 camera saw through it. This draws candidate rebuilds into one
SC3 frame with bldrender's projection (re/analysis/BUILDING_ART.md 4), unlit (the SC4 light is in the texture),
alpha-tested per sample (the texels outside the house are transparent, so the ray goes on to the next face or the
ground), faces one-sided (a box face turned away from the camera is not drawn).

Variants (`build_faces`):
  match     slot r draws the one SC4 view whose camera is 22.5 degrees from it (views.match_view): its 3 faces.
  back      match + the box's two back walls and floor with the same projected uv (views.hidden_faces): what
            sc4conv.py writes.
  frontal   each wall from the view that sees it most frontally (22.5 degrees off its normal), the top from the
            matched view of the slot.
  fixed     every face from one view choice for all slots (walls frontal, top from view 0): one model for all four
            SC3 slots, which bldimport could render as a single OBJ.
"""
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'bldimport'))
import bldrender as R  # noqa: E402
import views as V  # noqa: E402


def box_faces(v):
    """Group a view's triangles into faces (quads) by normal; -> list of (normal (model frame), tri indices)."""
    P = v['P']
    c = P.mean(0)
    faces = {}
    for k, (a, b, cc) in enumerate(v['tris']):
        n = np.cross(P[b] - P[a], P[cc] - P[a])
        n /= np.linalg.norm(n)
        if np.dot(n, P[[a, b, cc]].mean(0) - c) < 0:
            n = -n
        key = tuple(np.round(n, 2))
        faces.setdefault(key, []).append(k)
    return faces


def az_of_normal(n):
    return math.degrees(math.atan2(n[0], n[2]))


def build_faces(vs, slot, variant):
    """-> list of (P (3,3) model frame, UV (3,2), tex, normal) to draw for an SC3 slot."""
    out = []

    def add(v, ks, n):
        for k in ks:
            a, b, c = v['tris'][k]
            out.append((v['P'][[a, b, c]], v['UV'][[a, b, c]], v['tex'], np.array(n)))

    if variant in ('match', 'back'):
        v = V.match_view(vs, slot)
        for n, ks in box_faces(v).items():
            add(v, ks, n)
        if variant == 'back':
            hf = V.hidden_faces(v)
            if hf is not None:
                P, UV, tris = hf
                for a, b, c in tris:
                    out.append((P[[a, b, c]], UV[[a, b, c]], v['tex'], None))
        return out
    top_view = V.match_view(vs, slot) if variant == 'frontal' else vs[0]
    for v in vs:
        for n, ks in box_faces(v).items():
            if n[1] > 0.9:
                if v is top_view:
                    add(v, ks, n)
                continue
            a = az_of_normal(n)
            best = min(vs, key=lambda w: abs((w['cam']['azimuth_model'] - a + 180) % 360 - 180))
            if best is v:
                add(v, ks, n)
    return out


def render(vs, slot, z, variant='match', n=1, ss=4, cell_m=16.0, ground=(100, 140, 80), offset=(0.0, 0.0)):
    """-> (RGBA PIL image, (L, T)) one SC3 frame, frame size and anchor rules of bldrender (lot ground drawn as a
    flat colour diamond)."""
    faces = build_faces(vs, slot, variant)
    allp = np.concatenate([f[0] for f in faces])
    x0, x1 = allp[:, 0].min(), allp[:, 0].max()
    z0, z1 = allp[:, 2].min(), allp[:, 2].max()
    y0 = allp[:, 1].min()

    def tile(P):
        u = (P[:, 0] - (x0 + x1) / 2) / cell_m + n / 2.0 + offset[0]
        vv = (P[:, 2] - (z0 + z1) / 2) / cell_m + n / 2.0 + offset[1]
        h = (P[:, 1] - y0) / cell_m
        return np.stack([u, vv, h], 1)

    W = 8 << z
    tris = []
    for P, UV, tex, nm in faces:
        t = R._rot_slot(tile(P), n, slot)
        if nm is None:                       # hidden-face fill: drawn from either side
            tris.append((t, UV, tex))
            continue
        # facing: normal in tile frame (u, v, h) = model (x, z, y), rotated like the positions
        nt = R._rot_slot(np.array([[nm[0], nm[2], nm[1]]]) + np.array([[n / 2, n / 2, 0]]), n, slot)[0] \
            - R._rot_slot(np.array([[n / 2, n / 2, 0.0]]), n, slot)[0]
        facing = (nt[1] * R.F[0] + nt[0] * R.F[1] + nt[2] * R.F[2]) < 0
        if facing:
            tris.append((t, UV, tex))
    B = n * W // 4 + 1
    allt = np.concatenate([t for t, _, _ in tris]) if tris else np.zeros((1, 3))
    X, Y = R._screen(allt, W)
    top = max(int(math.ceil(-Y.min() + 1)), n * W // 4)
    Hh, Ww = top + B, n * W
    S = (Hh * ss, Ww * ss)
    best_d = np.full(S, np.inf)
    col = np.zeros(S + (3,), np.float32)
    cov = np.zeros(S, bool)
    for t, UV, tex in tris:
        sx, sy = R._screen(t, W)
        ib, bb, zb = R.rasterize((sx * ss)[None], ((sy + top) * ss)[None], R.depth_of(t)[None], Ww * ss, Hh * ss)
        m = ib >= 0
        if not m.any():
            continue
        uv = (bb[m][:, :, None] * UV[None]).sum(1)
        th, tw = tex.shape[:2]
        px = np.clip((uv[:, 0] * tw).astype(int), 0, tw - 1)
        py = np.clip((uv[:, 1] * th).astype(int), 0, th - 1)
        tx = tex[py, px]
        ok = tx[:, 3] >= 128
        d = zb[m]
        nearer = ok & (d < best_d[m])
        idx = np.where(m)
        sel = (idx[0][nearer], idx[1][nearer])
        best_d[sel] = d[nearer]
        col[sel] = tx[nearer, :3] / 255.0
        cov[sel] = True
    # ground diamond (flat colour) under everything
    gt = R._rot_slot(np.array([[[0, 0, 0], [n, 0, 0], [n, n, 0]], [[0, 0, 0], [n, n, 0], [0, n, 0]]], float), n, slot)
    gx, gy = R._screen(gt, W)
    gib, _, _ = R.rasterize(gx * ss, (gy + top) * ss, np.zeros((2, 3)), Ww * ss, Hh * ss)
    gm = (gib >= 0) & ~cov
    col[gm] = np.array(ground, np.float32) / 255.0
    allm = cov | gm
    c = allm.reshape(Hh, ss, Ww, ss).sum((1, 3)).astype(np.float32)
    s = (col * allm[..., None]).reshape(Hh, ss, Ww, ss, 3).sum((1, 3))
    rgb = np.where(c[..., None] > 0, s / np.maximum(c, 1)[..., None], 0)
    img = np.zeros((Hh, Ww, 4), np.uint8)
    img[..., :3] = np.clip(np.rint(rgb * 255), 0, 255)
    img[..., 3] = np.where(c / (ss * ss) >= 0.5, 255, 0)
    return Image.fromarray(img, 'RGBA'), (0, top)
