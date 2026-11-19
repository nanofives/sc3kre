#!/usr/bin/env python3
r"""views.py - task sc4conv (2026-11-18h): the four SC4 view models of a building, in one model frame.

What an SC4 BAT export holds per zoom and rotation (re/analysis/SC4_FORMATS.md 6, measured on all 2,560 S3D of the
JMyers pack): a mesh in VIEW space (the building turned by the view rotation, the camera fixed) whose texture is
the BAT's own render of that view, mapped by screen projection. In the pack the zoom 0-1 meshes are always the
7-corner bounding box (3 faces: the top and the two walls that face the camera); zooms 2-4 are the box on 440 of
512 models and a finer mesh (24-125 vertices) on the rest.

Fitted camera (least squares of uv x texture size against position, zoom 4 = SC4 zoom 5, every view of the first
model; error <= 0.38 px): forward direction the same in all four views, elevation 44.7-45.8 degrees, azimuth 22.5
degrees off the model's +z axis towards +x, 7.0 px per metre. Views r = 0, 1, 2, 3 (BAT names Z5S, Z5W, Z5N, Z5E)
hold the model turned so that view-space (x, z) = model (x, z) turned r quarter turns; model = view turned back:
(x, z) -> (z, -x) per step (checked: the four boxes coincide to 1e-3 m).

Model frame here = SC4 view 0 ('S'): x, y up, z, metres. Its camera is at azimuth +22.5 degrees from +z towards +x.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dbpf as D  # noqa: E402
import fsh as FS  # noqa: E402
from s3d import S3D  # noqa: E402

VIEW_NAMES = ('S', 'W', 'N', 'E')
# SC4 camera azimuth of view r in the model frame, degrees from +z towards +x (derivation: views.camera_azimuth)
# SC3 slot r camera azimuth in the same frame, after bldrender's model axes (+X -> u, +Z -> v, slot rule
# (u, v) -> (v, n - u)): slot 0 sees the +z and -x walls.
SC3_SLOT_AZ = (-45.0, -135.0, 135.0, 45.0)


def to_model(p, r):
    """view-r coordinates (N, 3) -> model frame."""
    p = np.array(p, dtype=np.float64)
    for _ in range(r % 4):
        p = np.stack([p[:, 2], p[:, 1], -p[:, 0]], 1)
    return p


def _solve(G, R):
    """G (n x n) X = R (n x m), Gaussian elimination with partial pivoting (first largest |pivot|), plain float
    arithmetic in a fixed order. Task sc4web: the importer page (sc4web.js) runs the same steps, so the fit is the
    same to the last bit in both (numpy's lstsq goes through LAPACK, whose rounding JS cannot reproduce)."""
    n, m = len(G), len(R[0])
    a = [list(G[i]) + list(R[i]) for i in range(n)]
    for c in range(n):
        p = c
        for i in range(c + 1, n):
            if abs(a[i][c]) > abs(a[p][c]):
                p = i
        if a[p][c] == 0.0:
            raise ValueError('camera fit: singular normal equations')
        a[c], a[p] = a[p], a[c]
        for i in range(c + 1, n):
            f = a[i][c] / a[c][c]
            for j in range(c, n + m):
                a[i][j] = a[i][j] - f * a[c][j]
    x = [[0.0] * m for _ in range(n)]
    for i in range(n - 1, -1, -1):
        for j in range(m):
            s = a[i][n + j]
            for k in range(i + 1, n):
                s = s - a[i][k] * x[k][j]
            x[i][j] = s / a[i][i]
    return x


def fit_camera(P, UV, tw, th):
    """Orthographic projection fit: [u*tw, v*th] = A [x y z 1]. -> (A (4x2), max error px, forward unit vector
    in the same frame (pointing from the camera into the scene: the 2x3 part's cross product, sign chosen so that
    it points down)).
    Least squares by the normal equations, every sum in point order (task sc4web, for byte identity with the page;
    the 2026-11-18h prototype used np.linalg.lstsq: same fit to about 1e-13 px)."""
    X = [[float(p[0]), float(p[1]), float(p[2]), 1.0] for p in P]
    T = [[float(t[0]) * tw, float(t[1]) * th] for t in UV]
    G = [[0.0] * 4 for _ in range(4)]
    R = [[0.0] * 2 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            s = 0.0
            for k in range(len(X)):
                s = s + X[k][i] * X[k][j]
            G[i][j] = s
        for j in range(2):
            s = 0.0
            for k in range(len(X)):
                s = s + X[k][i] * T[k][j]
            R[i][j] = s
    A = _solve(G, R)
    err = 0.0
    for k in range(len(X)):
        for j in range(2):
            e = abs((((X[k][0] * A[0][j] + X[k][1] * A[1][j]) + X[k][2] * A[2][j]) + A[3][j]) - T[k][j])
            err = max(err, e)
    m0 = (A[0][0], A[1][0], A[2][0])
    m1 = (A[0][1], A[1][1], A[2][1])
    d = [m0[1] * m1[2] - m0[2] * m1[1], m0[2] * m1[0] - m0[0] * m1[2], m0[0] * m1[1] - m0[1] * m1[0]]
    ln = math.sqrt((d[0] * d[0] + d[1] * d[1]) + d[2] * d[2])
    d = [d[0] / ln, d[1] / ln, d[2] / ln]
    if d[1] > 0:
        d = [-d[0], -d[1], -d[2]]
    return np.array(A, dtype=np.float64), float(err), np.array(d, dtype=np.float64)


def azimuth(d):
    """azimuth of the CAMERA position (opposite of forward d), degrees from +z towards +x."""
    return math.degrees(math.atan2(-d[0], -d[2]))


def elevation(d):
    return math.degrees(math.asin(-d[1]))


def load_views(idx, b, zoom=4):
    """-> list of 4 dicts {r, name, P (model frame), P_view, UV, tris, tex (RGBA uint8), tex_id, cam}"""
    t, g, base = b['model']
    out = []
    for r in range(4):
        key = (t, g, base + (zoom << 8) + (r << 4))
        s = S3D(idx.read(key))
        meshes = s.meshes()
        if len(meshes) != 1 or len(meshes[0][3]['tex']) != 1:
            raise ValueError('%s view %d: %d meshes, only one textured mesh is read' % (b['name'], r, len(meshes)))
        P, UV, tris, mat, mname = meshes[0]
        tid = mat['tex'][0]['id']
        fk = (D.T_FSH, g, tid)
        if not idx.has(fk):
            raise ValueError('%s view %d: texture %08X not found' % (b['name'], r, tid))
        bm = FS.read_fsh(idx.read(fk))[0]
        A, err, d = fit_camera(P, UV, bm['w'], bm['h'])
        dm = to_model(d[None, :], r)[0]
        out.append({'r': r, 'name': VIEW_NAMES[r], 'P_view': np.array(P), 'P': to_model(P, r), 'A': A,
                    'tex_size': (bm['w'], bm['h']),
                    'UV': np.array(UV), 'tris': tris, 'tex': bm['image'], 'tex_id': tid, 'tex_code': bm['code'],
                    'mesh_name': mname, 'mat': mat,
                    'cam': {'fit_err_px': err, 'forward_view': d.tolist(), 'forward_model': dm.tolist(),
                            'azimuth_model': azimuth(dm), 'elevation': elevation(d),
                            'px_per_m': math.sqrt((A[0, 0] * A[0, 0] + A[1, 0] * A[1, 0]) + A[2, 0] * A[2, 0])}})
    return out


def match_view(views, slot):
    """The SC4 view whose camera azimuth (model frame) is nearest the SC3 slot's."""
    a = SC3_SLOT_AZ[slot]
    return min(views, key=lambda v: abs((v['cam']['azimuth_model'] - a + 180) % 360 - 180))


def face_normals(P, tris):
    P = np.asarray(P)
    out = []
    for a, b_, c in tris:
        n = np.cross(P[b_] - P[a], P[c] - P[a])
        ln = np.linalg.norm(n)
        out.append(n / ln if ln else n)
    return np.array(out)


def hidden_faces(v, floor_y=0.05):
    """The box faces the SC4 camera does not see (the two back walls and the floor, lifted floor_y metres so the
    lot ground stays behind it), with uv from the view's fitted projection: uv = A [x y z 1] / texture size, the
    same mapping the visible faces have. -> (P (N, 3) model frame, UV (N, 2), tris) or None for a non-box mesh."""
    Pv = v['P_view']
    if len(Pv) != 7:
        return None
    lo, hi = Pv.min(0), Pv.max(0)
    d = np.array(v['cam']['forward_view'])
    quads = []
    for ax in (0, 2):                                  # walls x = lo / hi, z = lo / hi facing away from the camera
        for side, val in ((-1, lo[ax]), (1, hi[ax])):
            if side * d[ax] > 0:                       # outward normal along the view direction = back wall
                o = [i for i in (0, 2) if i != ax][0]
                q = []
                for a_, b_ in ((lo[o], lo[1]), (hi[o], lo[1]), (hi[o], hi[1]), (lo[o], hi[1])):
                    p = np.zeros(3)
                    p[ax], p[o], p[1] = val, a_, b_
                    q.append(p)
                quads.append(q)
    y = lo[1] + floor_y
    quads.append([np.array([lo[0], y, lo[2]]), np.array([hi[0], y, lo[2]]), np.array([hi[0], y, hi[2]]),
                  np.array([lo[0], y, hi[2]])])
    P = np.array([p for q in quads for p in q])
    A, (tw, th) = v['A'], v['tex_size']
    UV = np.array([[(((p[0] * A[0, j] + p[1] * A[1, j]) + p[2] * A[2, j]) + A[3, j]) / (tw, th)[j] for j in range(2)]
                   for p in P], dtype=np.float64)                   # task sc4web: sums in a fixed order (no BLAS)
    tris = []
    for k in range(len(quads)):
        tris += [(4 * k, 4 * k + 1, 4 * k + 2), (4 * k, 4 * k + 2, 4 * k + 3)]
    return to_model(P, v['r']), UV, tris
