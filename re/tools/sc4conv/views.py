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
import struct
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dbpf as D  # noqa: E402
import fsh as FS  # noqa: E402
from s3d import S3D  # noqa: E402

VIEW_NAMES = ('S', 'W', 'N', 'E')
# Task sc4civ (2026-11-19l): SimCity 4's own models. Every S3D of SimCity_1.dat and EP1.dat is in group 0xBADB57F1
# (42,895 of 42,895) and the textures their MATS name are FSH entries of group 0x1ABE787D in SimCity_2..5.dat and EP1.dat
# (the S3D's own group holds no FSH there). A download's BAT keeps the texture in the S3D's own group (the JMyers, tower
# and BSC packs), which is tried first.
MAXIS_S3D_GROUP, MAXIS_FSH_GROUP = 0xBADB57F1, 0x1ABE787D


def tex_key(idx, g, tid):
    """The FSH key a mesh's texture id names: the S3D's own group, else for SC4's own models group 0x1ABE787D."""
    k = (D.T_FSH, g, tid)
    if g == MAXIS_S3D_GROUP and not idx.has(k):
        k2 = (D.T_FSH, MAXIS_FSH_GROUP, tid)
        if idx.has(k2):
            return k2
    return k
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


TILE_SNAP = 0.35          # task sc4pass2: largest distance of a tile offset from whole pixels that is accepted
TILE_FIT = 2.0            # task sc4civ: largest error of the joint tile fit (the tower: 0.59 px; SC4's atlases: 9-108)
ATLAS_FIT = 2.0           # task sc4civ: largest error of an atlas piece against the reference projection (measured
                          # on SC4's civic / park / reward / landmark views: 1.58 px after rounding the offset)


def compose_tiles(idx, g, meshes, label):
    """Task sc4pass2 (2026-11-19f): one view drawn as several textured meshes (a tall building: the Global Office
    Center's zoom-5 views are 12 / 14 meshes, one 256 x 256 texture each). The BAT cut ONE screen render into tiles
    on a 256-pixel grid (measured on the tower: the tile offsets of a view differ by multiples of 256 to 0.15 px), and
    every mesh is mapped by the same screen projection plus its tile's offset. So: fit the projection's linear part
    jointly (each mesh centred on its own means: pixel = L p + t_i), round each tile's offset against the first
    tile's to whole pixels, paste the tiles into one canvas (a texel replaces the canvas only where its alpha is
    higher), and give every vertex its own pixel shifted by its tile's offset. The view is then one mesh with one
    texture, as the one-mesh views are. Plain float arithmetic in a fixed order (sc4web.js composeTiles).
    -> (P, UV, tris, bitmap {w, h, image, code}, first texture id, tile count)"""
    pieces = []
    for P, UV, tris, mat, _mname in meshes:
        tid = mat['tex'][0]['id']
        fk = tex_key(idx, g, tid)
        if not idx.has(fk):
            raise ValueError('%s: texture %08X not found' % (label, tid))
        bm = FS.read_fsh(idx.read(fk))[0]
        q = [[float(uv[0]) * bm['w'], float(uv[1]) * bm['h']] for uv in UV]
        pieces.append((P, q, tris, bm, tid))
    G = [[0.0] * 3 for _ in range(3)]
    R = [[0.0] * 2 for _ in range(3)]
    means = []
    for P, q, _t, _bm, _id in pieces:
        n = len(P)
        if not n:
            raise ValueError('%s: a tile without vertices' % label)
        mp = [0.0, 0.0, 0.0]
        mq = [0.0, 0.0]
        for k in range(n):
            for c in range(3):
                mp[c] = mp[c] + float(P[k][c])
            for c in range(2):
                mq[c] = mq[c] + q[k][c]
        mp = [x / n for x in mp]
        mq = [x / n for x in mq]
        means.append((mp, mq))
        for k in range(n):
            dp = [float(P[k][c]) - mp[c] for c in range(3)]
            dq = [q[k][c] - mq[c] for c in range(2)]
            for i in range(3):
                for j in range(3):
                    G[i][j] = G[i][j] + dp[i] * dp[j]
                for j in range(2):
                    R[i][j] = R[i][j] + dp[i] * dq[j]
    L = _solve(G, R)
    ts = [[mq[j] - ((mp[0] * L[0][j] + mp[1] * L[1][j]) + mp[2] * L[2][j]) for j in range(2)] for mp, mq in means]
    for (P, q, _t, _bm, _id), t in zip(pieces, ts):     # task sc4civ: one screen picture, else an atlas (None)
        for k in range(len(P)):
            for j in range(2):
                e = ((float(P[k][0]) * L[0][j] + float(P[k][1]) * L[1][j]) + float(P[k][2]) * L[2][j]) + t[j] - q[k][j]
                if abs(e) > TILE_FIT:
                    return None
    offs = []
    for t in ts:
        o = []
        for j in range(2):
            x = ts[0][j] - t[j]
            r = math.floor(x + 0.5)
            if abs(x - r) > TILE_SNAP:
                return None
            o.append(int(r))
        offs.append(o)
    x0 = min(o[0] for o in offs)
    y0 = min(o[1] for o in offs)
    offs = [[o[0] - x0, o[1] - y0] for o in offs]
    W = max(o[0] + pc[3]['w'] for o, pc in zip(offs, pieces))
    H = max(o[1] + pc[3]['h'] for o, pc in zip(offs, pieces))
    canvas = np.zeros((H, W, 4), dtype=np.uint8)
    for o, (_P, _q, _t, bm, _id) in zip(offs, pieces):
        reg = canvas[o[1]:o[1] + bm['h'], o[0]:o[0] + bm['w']]
        m = bm['image'][:, :, 3] > reg[:, :, 3]
        reg[m] = bm['image'][m]
    Pall, UVall, tall = [], [], []
    for o, (P, q, tris, _bm, _id) in zip(offs, pieces):
        base = len(Pall)
        tall += [tuple(base + i for i in t) for t in tris]
        Pall += [[float(p[0]), float(p[1]), float(p[2])] for p in P]
        UVall += [[(qq[0] + o[0]) / W, (qq[1] + o[1]) / H] for qq in q]
    return Pall, UVall, tall, {'w': W, 'h': H, 'image': canvas, 'code': pieces[0][3]['code']}, pieces[0][4], len(pieces)


def _covered(q, tris, w, h):
    """Task sc4civ: texels (x, y) of a w x h texture whose square [x, x+1] x [y, y+1] meets one of the triangles (q:
    texture pixels): inside the triangle's bounding box, and for every edge at least one corner of the square on its inner
    side or on it (a separating-axis test on the two box axes and the three edge normals). Zero-area triangles cover nothing. -> bool array (h, w). Elementwise float arithmetic in
    a fixed order (sc4web.js atlasCovered: the same operations)."""
    out = np.zeros((h, w), dtype=bool)
    for t in tris:
        a, b, c = q[t[0]], q[t[1]], q[t[2]]
        ar = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if ar == 0.0:
            continue
        sg = 1.0 if ar > 0 else -1.0
        x0 = max(0, int(math.floor(min(a[0], b[0], c[0]))))
        x1 = min(w - 1, int(math.ceil(max(a[0], b[0], c[0]))) - 1)
        y0 = max(0, int(math.floor(min(a[1], b[1], c[1]))))
        y1 = min(h - 1, int(math.ceil(max(a[1], b[1], c[1]))) - 1)
        if x1 < x0 or y1 < y0:
            continue
        X = np.arange(x0, x1 + 1, dtype=np.float64)[None, :]
        Y = np.arange(y0, y1 + 1, dtype=np.float64)[:, None]
        ok = np.ones((y1 - y0 + 1, x1 - x0 + 1), dtype=bool)
        for p_, r_ in ((a, b), (b, c), (c, a)):
            ex, ey = r_[0] - p_[0], r_[1] - p_[1]
            inside = np.zeros_like(ok)
            for dx, dy in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)):
                e = sg * (ex * ((Y + dy) - p_[1]) - ey * ((X + dx) - p_[0]))
                inside |= e >= 0.0
            ok &= inside
        out[y0:y1 + 1, x0:x1 + 1] |= ok
    return out


def compose_atlas(idx, g, meshes, label):
    """Task sc4civ (2026-11-19l): one view whose meshes are pieces of one screen render packed into textures (SC4's
    own civic, park, reward and landmark models: 316 of 452 zoom-5 views, 2,343 pieces). Each piece fits an
    orthographic camera of its own to 0.6 px; against the projection fitted on the piece with the most vertices it is
    the same picture moved, unturned (1,605) or transposed (x and y swapped: 738), 1.58 px off at most once its offset
    is rounded to whole pixels. So: per piece a 2D affine fit of its texture pixels against the reference projection
    (normal equations, _solve) decides transposed (determinant < 0); the mean offset, rounded, says where its texels
    go; the texels its triangles cover (_covered) are copied to one canvas, a texel replacing the canvas only where its
    alpha is higher (as compose_tiles), pieces in mesh order. Every vertex keeps its own texel, moved with it.
    -> as compose_tiles."""
    pieces = []
    for P, UV, tris, mat, _mname in meshes:
        tid = mat['tex'][0]['id']
        fk = tex_key(idx, g, tid)
        if not idx.has(fk):
            raise ValueError('%s: texture %08X not found' % (label, tid))
        bm = FS.read_fsh(idx.read(fk))[0]
        q = [[float(uv[0]) * bm['w'], float(uv[1]) * bm['h']] for uv in UV]
        pieces.append((P, UV, q, tris, bm, tid))
    ref = 0
    for i, pc in enumerate(pieces):
        if len(pc[0]) > len(pieces[ref][0]):
            ref = i
    A, _err, _d = fit_camera(pieces[ref][0], pieces[ref][1], pieces[ref][4]['w'], pieces[ref][4]['h'])
    A = [[float(A[i, j]) for j in range(2)] for i in range(4)]
    placed = []
    for P, _UV, q, tris, bm, tid in pieces:
        n = len(P)
        c = [[((float(p[0]) * A[0][j] + float(p[1]) * A[1][j]) + float(p[2]) * A[2][j]) + A[3][j] for j in range(2)]
             for p in P]
        G = [[0.0] * 3 for _ in range(3)]
        R = [[0.0] * 2 for _ in range(3)]
        for k in range(n):
            x = (c[k][0], c[k][1], 1.0)
            for i in range(3):
                for j in range(3):
                    G[i][j] = G[i][j] + x[i] * x[j]
                for j in range(2):
                    R[i][j] = R[i][j] + x[i] * q[k][j]
        M = _solve(G, R)
        tr = (M[0][0] * M[1][1] - M[0][1] * M[1][0]) < 0.0
        cc = [[ck[1], ck[0]] if tr else [ck[0], ck[1]] for ck in c]
        off = []
        for j in range(2):
            sm = 0.0
            for k in range(n):
                sm = sm + (q[k][j] - cc[k][j])
            off.append(int(math.floor(sm / n + 0.5)))
        for k in range(n):
            for j in range(2):
                e = abs((cc[k][j] + off[j]) - q[k][j])
                if e > ATLAS_FIT:
                    raise ValueError("%s: atlas piece of texture %08X is %.2f px off the view's projection"
                                     % (label, tid, e))
        ys, xs = np.nonzero(_covered(q, tris, bm['w'], bm['h']))
        placed.append((P, q, tris, bm, tr, off, xs, ys))

    def to_canvas(tr, off, x, y):             # a texture position -> canvas, before the shift to 0
        return (y - off[1], x - off[0]) if tr else (x - off[0], y - off[1])
    box = None
    for _P, _q, _t, _bm, tr, off, xs, ys in placed:
        if len(xs):
            cx, cy = to_canvas(tr, off, xs, ys)
            b = [int(cx.min()), int(cy.min()), int(cx.max()), int(cy.max())]
            box = b if box is None else [min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3])]
    if box is None:
        raise ValueError('%s: the atlas pieces cover no texel' % label)
    X0, Y0 = box[0], box[1]
    W, H = box[2] - X0 + 1, box[3] - Y0 + 1
    canvas = np.zeros((H, W, 4), dtype=np.uint8)
    for _P, _q, _t, bm, tr, off, xs, ys in placed:
        if not len(xs):
            continue
        cx, cy = to_canvas(tr, off, xs, ys)
        cx, cy = cx - X0, cy - Y0
        src = bm['image'][ys, xs]
        m = src[:, 3] > canvas[cy, cx, 3]     # one piece never puts two texels on one canvas pixel
        canvas[cy[m], cx[m]] = src[m]
    Pall, UVall, tall = [], [], []
    for P, q, tris, _bm, tr, off, _xs, _ys in placed:
        base = len(Pall)
        tall += [tuple(base + i for i in t) for t in tris]
        Pall += [[float(p[0]), float(p[1]), float(p[2])] for p in P]
        for qq in q:
            ux, uy = to_canvas(tr, off, qq[0], qq[1])
            UVall.append([(ux - X0) / W, (uy - Y0) / H])
    return Pall, UVall, tall, {'w': W, 'h': H, 'image': canvas, 'code': pieces[0][4]['code']}, pieces[0][5], len(pieces)


def load_views(idx, b, zoom=4):
    """-> list of 4 dicts {r, name, P (model frame), P_view, UV, tris, tex (RGBA uint8), tex_id, cam, tiles}"""
    t, g, base = b['model']
    out = []
    for r in range(4):
        key = (t, g, base + (zoom << 8) + (r << 4))
        if not idx.has(key):
            raise ValueError('%s view %d: S3D %08X not found' % (b['name'], r, key[2]))
        s = S3D(idx.read(key))
        meshes = s.meshes()
        if not meshes or any(len(m[3]['tex']) != 1 for m in meshes):
            raise ValueError('%s view %d: %d meshes, only meshes with one texture each are read'
                             % (b['name'], r, len(meshes)))
        if len(meshes) == 1:
            P, UV, tris, mat, mname = meshes[0]
            tid = mat['tex'][0]['id']
            fk = tex_key(idx, g, tid)
            if not idx.has(fk):
                raise ValueError('%s view %d: texture %08X not found' % (b['name'], r, tid))
            bm = FS.read_fsh(idx.read(fk))[0]
            tiles = 1
        else:                                 # task sc4pass2: a view cut into tiles (tall buildings)
            got = compose_tiles(idx, g, meshes, '%s view %d' % (b['name'], r))
            if got is None:                   # task sc4civ: SC4's own models, the view packed into an atlas
                got = compose_atlas(idx, g, meshes, '%s view %d' % (b['name'], r))
            P, UV, tris, bm, tid, tiles = got
            mat, mname = meshes[0][3], meshes[0][4]
        A, err, d = fit_camera(P, UV, bm['w'], bm['h'])
        dm = to_model(d[None, :], r)[0]
        out.append({'r': r, 'name': VIEW_NAMES[r], 'P_view': np.array(P), 'P': to_model(P, r), 'A': A,
                    'tex_size': (bm['w'], bm['h']),
                    'UV': np.array(UV), 'tris': tris, 'tex': bm['image'], 'tex_id': tid, 'tex_code': bm['code'],
                    'mesh_name': mname, 'mat': mat, 'tiles': tiles,
                    'cam': {'fit_err_px': err, 'forward_view': d.tolist(), 'forward_model': dm.tolist(),
                            'azimuth_model': azimuth(dm), 'elevation': elevation(d),
                            'px_per_m': math.sqrt((A[0, 0] * A[0, 0] + A[1, 0] * A[1, 0]) + A[2, 0] * A[2, 0])}})
    return out


def model_state(idx, b, zoom=4):
    """Task sc4pass2: can this building's model be converted? -> ('ok', None); ('missing', why) when the download
    has no S3D view of it (a lot-only pack: the model is a separate download); ('blank', why) when every texel of
    every view at that zoom is transparent (a placeholder, the I-M lots' blank.SC4Model: what shows in SC4 there is
    lot props)."""
    t, g, base = b['model']
    keys = [(t, g, base + (zoom << 8) + (r << 4)) for r in range(4)]
    miss = [k for k in keys if not idx.has(k)]
    if miss:
        return 'missing', 'no model in this download (S3D %08X-%08X-%08X)' % miss[0]
    try:
        for k in keys:
            for _P, _UV, _tris, mat, _n in S3D(idx.read(k)).meshes():
                for tx in mat['tex']:
                    fk = tex_key(idx, g, tx['id'])
                    if idx.has(fk) and FS.read_fsh(idx.read(fk))[0]['image'][:, :, 3].max() > 0:
                        return 'ok', None
    except (ValueError, KeyError, IndexError, struct.error):
        return 'ok', None                 # unreadable: load_views reports why, as before
    return 'blank', 'a blank placeholder model (every texel transparent)'


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


# ---------------------------------------------------------------------------------------------------- task sc4diag
# Diagonal (45 degree) buildings, round 2026-11-19c. SC4 lots turn a building in quarter turns only (lot object
# word 2, rotation 0-3, SC4_FORMATS.md 3), so a house the BAT author set at 45 degrees is drawn turned inside its
# axis-aligned box and no lot field says so. Its FOUNDATION model does: the building exemplar's 0x88FCD877 names a
# foundation exemplar (type 0x11, group 0x361CF9D5) whose S3D mesh is real geometry (24-125 vertices, not the view
# box), and on the JMyers pack its outline runs either along the box axes (12 designs) or at 45 degrees (6 designs):
# share of the outline at 26.6-63.4 degrees 0.00-0.06 against 1.00 (verify/sc4diag/RESULTS.md).
FND_GROUP = 0x361CF9D5
DIAG_SHARE = 0.5          # a foundation whose outline runs at 45 degrees for at least half its length is diagonal


def _cross(P, t):
    a, b, c = P[t[0]], P[t[1]], P[t[2]]
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def outline_share_45(P, tris):
    """Share of the length of a mesh's horizontal outline edges that runs diagonally. -> (share, length) or None.
    Outline = an edge with one triangle, or more than two, or two that are not coplanar (a flat quad's own diagonal
    is not outline). Horizontal = the ends differ by at most 0.05 m in height, length >= 0.05 m. Diagonal = the
    shorter of |dx|, |dz| is at least half the longer (26.6-63.4 degrees from an axis). Plain float arithmetic,
    edges in first-seen order (sc4web.js runs the same steps)."""
    edges = {}
    for ti, t in enumerate(tris):
        for i in range(3):
            a, b = tuple(P[t[i]]), tuple(P[t[(i + 1) % 3]])
            k = (a, b) if a <= b else (b, a)
            edges.setdefault(k, []).append(ti)
    tot = diag = 0.0
    for (a, b), ts in edges.items():
        if len(ts) == 2:
            n1, n2 = _cross(P, tris[ts[0]]), _cross(P, tris[ts[1]])
            d = (n1[0] * n2[0] + n1[1] * n2[1]) + n1[2] * n2[2]
            l1 = (n1[0] * n1[0] + n1[1] * n1[1]) + n1[2] * n1[2]
            l2 = (n2[0] * n2[0] + n2[1] * n2[1]) + n2[2] * n2[2]
            if d > 0 and d * d >= 0.998 * (l1 * l2):
                continue
        dx, dy, dz = abs(b[0] - a[0]), abs(b[1] - a[1]), abs(b[2] - a[2])
        ln = math.sqrt(dx * dx + dz * dz)
        if dy > 0.05 or ln < 0.05:
            continue
        tot += ln
        if min(dx, dz) >= 0.5 * max(dx, dz):
            diag += ln
    return (diag / tot, tot) if tot > 0 else None


def foundation_diagonal(idx, b, zoom=4):
    """-> {'diagonal': bool, 'foundation': exemplar name, 'share_45': float} from the building's foundation model
    (rotation 0 view at that zoom), or None when the building names no foundation or it cannot be read."""
    inst = b.get('foundation')
    if not isinstance(inst, int) or isinstance(inst, bool):
        return None
    k = (D.T_EXEMPLAR, FND_GROUP, inst & 0xFFFFFFFF)
    if not idx.has(k):
        return None
    try:
        ex = idx.exemplar(k)
        rk = ex['props'].get(0x27812821)
        rk = rk[1] if rk else None
        if not isinstance(rk, list) or len(rk) < 3 or rk[0] != D.T_S3D:
            return None
        key = (rk[0], rk[1], rk[2] + (zoom << 8))
        if not idx.has(key):
            return None
        P, tris = [], []
        for mP, _uv, mt, _mat, _n in S3D(idx.read(key)).meshes():
            tris += [tuple(len(P) + i for i in t) for t in mt]
            P += [list(p) for p in mP]
    except (ValueError, KeyError, IndexError, struct.error):
        return None
    r = outline_share_45(P, tris)
    if r is None:
        return None
    name = ex['props'].get(0x20)
    return {'diagonal': r[0] >= DIAG_SHARE, 'foundation': name[1] if name else '%08X' % k[2], 'share_45': r[0]}
