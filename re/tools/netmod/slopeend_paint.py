"""slopeend_paint.py -- art for the road slope ends (task slopeend, 2026-10-26).

A slope end is the stock sloped straight piece (11202 / 11201 at magnitude 1, 32 / 31 at magnitude 2) with one or both
ends rounded like the flat dead end 11225. Every pixel of the stock frame is mapped back to its tile point on the
frame's own slope plane (fitted per frame: which edge is high, by how many altitude units, and where the registration
point sits), and the end half is the piece's OWN cross profile bent round a half circle centred on the cell centre,
radius 0.5 (the flat cap 11225 measured this way: shape IoU 0.97..0.99 per slot at zoom 4 against the same bend of
road 29). So the cap has the slope piece's palette, dither and lighting, and its straight half (and the open edge) is
the stock piece's own pixels: the seam with the next road cell is the stock seam. Outside the half circle the art is
transparent; the variant carries the frame-table ground bit (netpack art.ground_under) so the terrain is drawn there,
as under 11225. Frames keep the base frame's size and anchor: a frame cropped to its opaque box shrinks the cell's
vertical clip range (anchor T / B) and the terrain under the piece was clipped with it (holes in game, run 2).

    py -3.12 re/tools/netmod/slopeend_paint.py build <package dir>          # art/<id>/z*_r*.png + anchors.json
    py -3.12 re/tools/netmod/slopeend_paint.py preview <out.png> [--zoom 4] [--package <dir>]   # stock vs mod scenes
    py -3.12 re/tools/netmod/slopeend_paint.py fit                          # the fitted plane of every base frame

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
from PIL import Image, ImageDraw  # noqa: E402

ZOOMS, ROTS = 5, 4
BASES = (11202, 11201, 32, 31)
ENDS = ("up", "down", "both")
CAP_PIECE = 11225
EDGES = {"NW": ("L", "T"), "NE": ("T", "R"), "SE": ("B", "R"), "SW": ("L", "B")}   # slot tile corners per edge
OPP = {"NW": "SE", "SE": "NW", "NE": "SW", "SW": "NE"}
# (across a, along t) with t = 0 on the OPEN edge and 1 on the closed edge, per open edge, and back
TO_AT = {"NW": lambda u, v: (u, v), "SE": lambda u, v: (u, 1 - v), "NE": lambda u, v: (v, 1 - u),
         "SW": lambda u, v: (v, u)}
FROM_AT = {"NW": lambda a, t: (a, t), "SE": lambda a, t: (a, 1 - t), "NE": lambda a, t: (1 - t, a),
           "SW": lambda a, t: (t, a)}
CAP_TC = 0.5          # the half circle starts at the cell centre ...
CAP_R = 0.5           # ... and its outer sidewalk edge has radius 0.5 (flat 11225 fit, module docstring)

_FR = {}
_GAME = None


def set_game(root):
    global _GAME
    _GAME = root


def frames(pid):
    """{(z, r): (RGBA image, (L, T))} of a stock piece"""
    if pid not in _FR:
        import netart as A
        if _GAME:
            A.set_game(_GAME)
        _FR[pid] = A.stock_frames(pid)
    return _FR[pid]


# ----------------------------------------------------------------------------------------------- plane fit

def heights(edge, m, ref):
    """corner heights (altitude units) above the registration point's reference altitude"""
    return {c: (m if c in EDGES[edge] else 0) - ref for c in "LTBR"}


def tile_uv(z, size, LT, h):
    """per pixel of a frame -> tile (u, v) on the plane h (pixel centres)"""
    W, pu = 8 << z, 1 << z
    w, hh = size
    ys, xs = np.mgrid[0:hh, 0:w]
    X = xs + 0.5 - LT[0]
    Y = ys + 0.5 - LT[1]
    eL, eT, eB = h["L"], h["T"], h["B"]
    s = 2 * X / W                                  # u + v
    a = -W / 2 - (eT - eL) * pu + (eB - eL) * pu
    b = s * W / 4 - (eL + (eB - eL) * s) * pu - Y
    u = -b / a
    return u, s - u


def project(z, LT, h, u, v):
    """tile (u, v) on the plane h -> frame pixel (x, y)"""
    W, pu = 8 << z, 1 << z
    e = h["L"] + (h["T"] - h["L"]) * u + (h["B"] - h["L"]) * v
    return (u + v) * W / 2 + LT[0], (v - u) * W / 4 - e * pu + LT[1]


def fit_plane(im, LT, z):
    """-> (IoU, high edge, magnitude, ref) that best explains the frame's opaque pixels"""
    al = np.array(im)[..., 3] >= 128
    best = None
    for edge in EDGES:
        for m in (1, 2):
            for ref in (0, m):
                u, v = tile_uv(z, im.size, LT, heights(edge, m, ref))
                ins = (u >= -0.004) & (u <= 1.004) & (v >= -0.004) & (v <= 1.004)
                iou = (ins & al).sum() / max(1, (ins | al).sum())
                if best is None or iou > best[0]:
                    best = (float(iou), edge, m, ref)
    return best


# ----------------------------------------------------------------------------------------------- painting

def _bend(a, t):
    dt = np.maximum(t - CAP_TC, 0)
    r = np.sqrt((a - 0.5) ** 2 + dt ** 2)
    xp = np.where(t > CAP_TC, 0.5 + np.where(a >= 0.5, 1.0, -1.0) * r, a)
    return xp, np.where(t > CAP_TC, r, np.abs(a - 0.5))


def cap_frame(im, LT, z, h, opn, both=False):
    """the frame of a straight sloped piece with its `OPP[opn]` end rounded (both=True: both ends)"""
    src = np.array(im).astype(np.float32)
    w, hh = im.size
    u, v = tile_uv(z, im.size, LT, h)
    a, t = TO_AT[opn](u, v)
    xp, rr = _bend(a, t)
    tt = np.minimum(t, CAP_TC)                 # sample the profile on the cell's middle row: the plane's own shading
    bent = t > CAP_TC
    if both:
        xp2, rr2 = _bend(a, 1 - t)
        lo = t < 0.5
        xp, rr = np.where(lo, xp2, xp), np.where(lo, rr2, rr)
        tt = np.where(lo, np.maximum(t, 1 - CAP_TC), tt)
        bent = bent | (t < 1 - CAP_TC)
    uu, vv = FROM_AT[opn](np.clip(xp, 0.0, 1.0), tt)
    X, Y = project(z, LT, h, uu, vv)
    got = src[np.clip(np.floor(Y).astype(int), 0, hh - 1), np.clip(np.floor(X).astype(int), 0, w - 1)]
    out = src.copy()
    out[bent] = got[bent]
    out[bent & (rr > CAP_R), 3] = 0
    out[..., 3] = np.where(out[..., 3] >= 128, 255, 0)
    out[out[..., 3] == 0, :3] = 0
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def crop(img, LT):
    bb = img.getchannel("A").getbbox()
    if not bb:
        return img, LT
    return img.crop(bb), (LT[0] - bb[0], LT[1] - bb[1])


def slot_plane(base, r):
    """the slope plane of `base` in rotation slot r, fitted on the zoom-4 frame (zoom 0 / 1 frames are too small to fit:
    some pick the wrong edge; zooms 2..4 agree on every slot). The plane does not change with the zoom."""
    im, LT = frames(base)[(4, r)]
    return fit_plane(im, LT, 4)


def variant_art(base, end, state=None):
    """-> {(z, r): (image, (L, T), info)} for a variant of `base` capped at `end` (up / down / both), used at `state`.
    The variants use 11225's sprite class (frame table header +0x08 = 0x0672, `art.from` 11225): the slope piece's own
    class 0x059D draws no terrain under a ground-bit piece (holes in game, verify/slopeend/RESULTS.md 4). Class 0x0672
    puts the anchor at the occupant's altitude, the cell's (x, z) corner (`piece writer` height -1 = terrain vt+0x4c):
    min + m at state 0, min at state 2 (slope table rows 0 / 1 vs 2 / 3). The stock frame's anchor sits at min + ref
    (the plane fit), so T moves by (ref - want) altitude units; state None keeps the stock anchor."""
    out = {}
    for (z, r), (im, LT) in frames(base).items():
        iou, high, m, ref = slot_plane(base, r)
        closed = high if end in ("up", "both") else OPP[high]
        img = cap_frame(im, LT, z, heights(high, m, ref), OPP[closed], both=(end == "both"))
        # NOT cropped: a frame cropped to its opaque box shrank the cell's clip range in the first in-game run.
        if state is not None:
            want = m if state == 0 else 0
            LT = (LT[0], LT[1] + (ref - want) * (1 << z))
        out[(z, r)] = (img, LT, dict(iou=round(iou, 3), high=high, mag=m, ref=ref, closed=closed))
    return out


def load_manifest(pkg):
    man = json.load(open(os.path.join(pkg, "manifest.json"), encoding="utf-8"))
    roles = {}
    for ln in man.get("road_end_lines", []):        # sle <base> <up0> <down0> <both0> <up2> <down2> <both2>
        p = ln.split()
        if p[0] == "sle":
            b = int(p[1])
            for k, vid in enumerate(int(x) for x in p[2:8]):
                roles[vid] = (b, ENDS[k % 3], 0 if k < 3 else 2)
    return man, roles


def cmd_build(pkg):
    man, roles = load_manifest(pkg)
    for v in man["variants"]:
        base, end, state = roles[v["id"]]
        d = os.path.join(pkg, "art", str(v["id"]))
        os.makedirs(d, exist_ok=True)
        anc = {"_note": "slopeend_paint.py: base %d, end %s, state %d; base frame sizes, anchors for class 0x0672" %
               (base, end, state)}
        worst = 1.0
        for (z, r), (img, LT, info) in sorted(variant_art(base, end, state).items()):
            name = "z%d_r%d.png" % (z, r)
            img.save(os.path.join(d, name))
            anc[name] = [int(LT[0]), int(LT[1])]
            worst = min(worst, info["iou"]) if z == 4 else worst
        json.dump(anc, open(os.path.join(d, "anchors.json"), "w", encoding="utf-8"), indent=1)
        print("%d: base %d end %-4s state %d -> %s (zoom-4 plane fit IoU >= %.3f)" % (v["id"], base, end, state, d, worst))


def cmd_fit():
    for base in BASES:
        for z in range(ZOOMS):
            print(base, z, " ".join("r%d %s/%d/%d %.3f" % ((r,) + fit_plane(*frames(base)[(z, r)], z)[1:] +
                                                           (fit_plane(*frames(base)[(z, r)], z)[0],))
                                    for r in range(ROTS)))


# ----------------------------------------------------------------------------------------------- scene preview

# ROAD slope table (SIMNTWRK 0x1003195C): slope row -> (piece, state); row from the corner pattern (FUN_1001a1f3)
SLOPE_ROWS = [[0, -1, -1, 0], [0, 0, -1, -1], [0, 1, 1, 0], [0, 0, 1, 1],
              [0, -2, -2, 0], [0, 0, -2, -2], [0, 2, 2, 0], [0, 0, 2, 2]]
SLOPE_PIECE = [(11202, 0), (11201, 0), (11202, 2), (11201, 2), (32, 0), (31, 0), (32, 2), (31, 2)]


class Scene:
    """a small world: vertex heights H[(X, Z)] (altitude units) and road cells {(x, z): piece frames + state}"""

    def __init__(self, n):
        self.n = n
        self.H = {(X, Z): 0 for X in range(n + 1) for Z in range(n + 1)}
        self.cells = {}

    def row(self, x, z):
        h0 = self.H[(x, z)]
        c = [0, self.H[(x + 1, z)] - h0, self.H[(x + 1, z + 1)] - h0, self.H[(x, z + 1)] - h0]
        return SLOPE_ROWS.index(c) if c in SLOPE_ROWS else None

    def render(self, z, view, bg=(54, 88, 54, 255), pad=10):
        n, W, pu = self.n, 8 << z, 1 << z

        def vert(X, Z):                     # world vertex -> view vertex (FUN_1000a62c, vertex form)
            return [(X, Z), (n - Z, X), (n - X, n - Z), (Z, n - X)][view]

        def scr(VX, VZ, alt):
            return (VZ - VX) * W / 2.0, (VX + VZ) * W / 4.0 - alt * pu

        def cellv(x, z_):                   # world cell -> view cell
            return [(x, z_), (n - 1 - z_, x), (n - 1 - x, n - 1 - z_), (z_, n - 1 - x)][view]
        inv = {}
        for (X, Z), a in self.H.items():
            inv[vert(X, Z)] = a
        xs = [scr(VX, VZ, a)[0] for (VX, VZ), a in inv.items()]
        ys = [scr(VX, VZ, a)[1] for (VX, VZ), a in inv.items()]
        ox, oy = pad - min(xs), pad + 3 * pu - min(ys)
        img = Image.new("RGBA", (int(max(xs) - min(xs) + 2 * pad), int(max(ys) - min(ys) + 2 * pad + 3 * pu)), bg)
        dr = ImageDraw.Draw(img)
        order = sorted(((cellv(x, z_), (x, z_)) for x in range(n) for z_ in range(n)), key=lambda c: c[0][0] + c[0][1])
        for (vx, vz), (x, z_) in order:             # terrain, shaded by its slope
            q = [(vx, vz), (vx, vz + 1), (vx + 1, vz + 1), (vx + 1, vz)]
            pts = [scr(VX, VZ, inv[(VX, VZ)]) for VX, VZ in q]
            hs = [inv[p] for p in q]
            shade = int(max(-40, min(40, ((hs[0] + hs[1]) - (hs[2] + hs[3])) * 12 + ((hs[1] + hs[2]) - (hs[0] + hs[3])) * 6)))
            col = (70 + shade // 2, 120 + shade, 60 + shade // 2, 255)
            dr.polygon([(p[0] + ox, p[1] + oy) for p in pts], fill=col, outline=(58, 100, 50, 255))
        for (vx, vz), (x, z_) in order:             # pieces, back to front
            if (x, z_) not in self.cells:
                continue
            fr, state = self.cells[(x, z_)]
            slot = (state + view) & 3
            if (z, slot) not in fr:
                continue
            im, LT = fr[(z, slot)][0], fr[(z, slot)][1]
            base_im, base_LT = fr.get(("plane", 4, slot), fr.get((4, slot)))
            iou, high, m, ref = fit_plane(base_im, base_LT, 4) if self.row(x, z_) is not None else (1, "NW", 0, 0)
            hL = heights(high, m, ref)["L"] if self.row(x, z_) is not None else 0
            VX, VZ = vx + 1, vz                     # the cell's left vertex
            px, py = scr(VX, VZ, inv[(VX, VZ)] - hL)
            img.alpha_composite(im, (int(round(px + ox - LT[0])), int(round(py + oy - LT[1]))))
        return img


def _variant_frames(base, end, pkg=None):
    if pkg:
        man, roles = load_manifest(pkg)
        vid = [k for k, v in roles.items() if v[:2] == (base, end)][0]
        d = os.path.join(pkg, "art", str(vid))
        anc = json.load(open(os.path.join(d, "anchors.json"), encoding="utf-8"))
        fr = {}
        for z in range(ZOOMS):
            for r in range(ROTS):
                nm = "z%d_r%d.png" % (z, r)
                fr[(z, r)] = (Image.open(os.path.join(d, nm)).convert("RGBA"), tuple(anc[nm]))
    else:
        fr = {k: (v[0], v[1]) for k, v in variant_art(base, end).items()}
    for (z, r), v in frames(base).items():
        fr[("plane", z, r)] = v                     # the plane is the base frame's (for the draw point)
    return fr


def slope_scene(axis, downhill_sign, end_kind, mag=1, mod=True, pkg=None):
    """a 5-cell strip along `axis` on terrain that has ONE sloped cell in the middle (cell 2).
    end_kind: 'end_up' = road on the downhill side only (the road climbs and stops), 'end_down' = road on the uphill
    side only, 'run' = road on both sides, 'stub' = the sloped cell alone."""
    n = 5
    s = Scene(n)
    for X in range(n + 1):
        for Z in range(n + 1):
            k = X if axis == "x" else Z
            k = k if downhill_sign > 0 else n - k
            s.H[(X, Z)] = (mag if k <= 2 else 0)        # vertices up to line 2 are high: cell 2 slopes down
    roads = {"end_up": (2, 3, 4), "end_down": (0, 1, 2), "run": (0, 1, 2, 3, 4), "stub": (2,)}[end_kind]
    cells = []
    for i in roads:
        k = i if downhill_sign > 0 else n - 1 - i
        cells.append(((k, 2) if axis == "x" else (2, k)))
    for c in cells:
        row = s.row(*c)
        if row is None:
            s.cells[c] = (frames(29), 0 if axis == "x" else 1)
            continue
        pid, st = SLOPE_PIECE[row]
        if mod and end_kind != "run":
            end = {"end_up": "up", "end_down": "down", "stub": "both"}[end_kind]
            s.cells[c] = (_variant_frames(pid, end, pkg), st)
        else:
            s.cells[c] = (frames(pid), st)
    # stock flat end caps where the strip ends on flat ground
    for c in cells:
        if s.row(*c) is None:
            nb = [d for d in cells if abs(d[0] - c[0]) + abs(d[1] - c[1]) == 1]
            if len(nb) == 1:
                dx, dz = nb[0][0] - c[0], nb[0][1] - c[1]
                arm_state = {(0, 1): 0, (-1, 0): 1, (0, -1): 2, (1, 0): 3}[(dx, dz)]   # 11225 arm(s) = (3 + s) % 4
                s.cells[c] = (frames(CAP_PIECE), arm_state)
    return s


def cmd_preview(out_png, zoom, pkg=None, views=(0, 1, 2, 3)):
    cases = [(a, sg, e) for a in ("x", "z") for sg in (1, -1) for e in ("end_up", "end_down")]
    tiles = []
    for a, sg, e in cases:
        row = []
        for mod in (False, True):
            for vw in views:
                row.append(slope_scene(a, sg, e, mod=mod, pkg=pkg).render(zoom, vw))
        tiles.append(((a, sg, e), row))
    cw = max(im.width for _, r in tiles for im in r)
    ch = max(im.height for _, r in tiles for im in r)
    lab = 150
    sheet = Image.new("RGBA", (lab + cw * len(views) * 2 + 20, ch * len(tiles) + 30), (24, 24, 24, 255))
    d = ImageDraw.Draw(sheet)
    d.text((lab, 8), "STOCK (views %s)" % ",".join(map(str, views)), fill=(255, 255, 255, 255))
    d.text((lab + cw * len(views) + 20, 8), "WITH THE MOD", fill=(255, 255, 255, 255))
    for i, ((a, sg, e), row) in enumerate(tiles):
        d.text((6, 30 + i * ch + ch // 2), "slope along %s\ndownhill %s%s\n%s" % (a, "+" if sg > 0 else "-", a,
                                                                                  e.replace("_", " ")),
               fill=(255, 255, 255, 255))
        for j, im in enumerate(row):
            x = lab + j * cw + (20 if j >= len(views) else 0)
            sheet.alpha_composite(im, (x, 30 + i * ch))
    sheet.save(out_png)
    print("wrote", out_png, sheet.size)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", default=os.environ.get("SC3_GAME_ROOT"))
    sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build")
    b.add_argument("package")
    p = sp.add_parser("preview")
    p.add_argument("out")
    p.add_argument("--zoom", type=int, default=4)
    p.add_argument("--package")
    sp.add_parser("fit")
    a = ap.parse_args(argv)
    if a.game:
        set_game(a.game)
    if a.cmd == "build":
        cmd_build(a.package)
    elif a.cmd == "preview":
        cmd_preview(a.out, a.zoom, a.package)
    elif a.cmd == "fit":
        cmd_fit()


if __name__ == "__main__":
    main()
