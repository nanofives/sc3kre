"""netart.py -- authoring kit for NEW network piece art (task artkit, re/analysis/NET_ART.md).

Everything here works in the game's own sprite geometry, measured from the stock frames and the SIMSPR draw code
(NET_ART.md). A piece's art is 20 frames: zoom z = 0..4 (tile width 8 << z px), rotation slot r = 0..3. Each frame
is a sprite plus a registration point (anchor L, T): the pixel of the sprite that lands on the tile's LEFT ground
vertex. Output of every route is a netpack `png_dir` (z{z}_r{r}.png + anchors.json when a size changes).

    py -3.12 re/tools/netmod/netart.py geometry [--json out.json]        # measured tables + checks
    py -3.12 re/tools/netmod/netart.py check-rot                         # slot r+1 = slot r turned 90 deg CCW
    py -3.12 re/tools/netmod/netart.py template <dir> --like 73 [--ghost 73]   # route a: guide PNGs
    py -3.12 re/tools/netmod/netart.py compose <recipe.json> <dir>       # route b: parts of stock frames
    py -3.12 re/tools/netmod/netart.py render <scene.json> <dir>         # route c: Blender (netart_blender.py)
    py -3.12 re/tools/netmod/netart.py calibrate <piece> <dir>           # route c: render vs stock, error report
    py -3.12 re/tools/netmod/netart.py preview <png_dir> <layout.json> <out.png>   # piece among stock neighbours
    py -3.12 re/tools/netmod/netart.py lint <png_dir> --like 73          # sizes, anchors, colour key, tile edges

Tile-plane coordinates (u, v), both 0..1, in ROTATION SLOT 0: u runs from the left vertex to the top vertex,
v from the left vertex to the bottom vertex. So left = (0,0), top = (1,0), bottom = (0,1), right = (1,1).
A point at height e (in zoom-3 pixels above ground) is drawn at, relative to the registration point:
    x = (u + v) * W / 2,   y = (v - u) * W / 4 - e * W / 64          (W = 8 << zoom)
Slot r shows the slot-0 content turned r x 90 degrees counter-clockwise on screen: (u, v) -> (v, 1 - u) per step
(`check-rot` measures this over every flat stock piece).

Game art never goes in the public repo: outputs land wherever you point them (keep them under a gitignored path).
"""
import argparse
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from PIL import Image, ImageDraw  # noqa: E402

ZOOMS = 5
ROTS = 4
TILE_W = [8 << z for z in range(ZOOMS)]           # measured: road 29 / 39 widths 8, 16, 32, 64, 128
KEY_RGB = (255, 0, 255)                           # both colour keys decode to magenta (SPRITE_MODDING.md rule 3)
FULL_TILE_PIECE = 39                              # a full, flat, symmetric tile: the measured ground mask
ELEVATED_PIECE = 73                               # straight highway: the measured deck height


def frame_name(z, r, layer=0):
    return ("z%d_r%d.png" % (z, r)) if layer == 0 else ("l%d_z%d_r%d.png" % (layer, z, r))


# ----------------------------------------------------------------------------------------------- stock frames

_CAT = None


def catalog():
    global _CAT
    if _CAT is None:
        from netmod import catalog as C
        _CAT = C.Catalog(with_dims=False)
    return _CAT


def stock_frames(pid, layer=0):
    """-> {(z, r): (RGBA image, (L, T))} of a stock piece (via its exemplar's frame table)."""
    import qfs
    import sprite_render as sr
    cat = catalog()
    art = cat.art(pid, cat.ex.get(pid))
    out = {}
    for fr in art["frames"]:
        k = fr["frame"]
        if k // 20 != layer or not fr["container"]:
            continue
        kind, block, inf = qfs.decode_record(cat.cont.payload(fr["container"], fr["slot"]))
        if kind != "qfs" or inf["format"] != 1:
            continue
        a = sr.parse_anchor(cat.cont.payload(fr["container"], fr["anchor_slot"]))
        out[((k % 20) // 4, k % 4)] = (sr.span_to_image(block), (a["spanL"], a["spanT"]))
    return out


def load_dir(d):
    """png_dir -> {(z, r): (image, (L, T) or None)}; anchors from anchors.json when listed."""
    anc = {}
    p = os.path.join(d, "anchors.json")
    if os.path.isfile(p):
        anc = {k: tuple(v) for k, v in json.load(open(p, encoding="utf-8")).items() if not k.startswith("_")}
    out = {}
    for z in range(ZOOMS):
        for r in range(ROTS):
            f = os.path.join(d, frame_name(z, r))
            if os.path.isfile(f):
                out[(z, r)] = (Image.open(f).convert("RGBA"), anc.get(frame_name(z, r)))
    return out


# ------------------------------------------------------------------------------------------------- geometry

def project(z, u, v, e=0.0):
    """tile-plane point (slot-0 coords) at height e (zoom-3 px) -> pixel offset from the registration point."""
    W = TILE_W[z]
    return (u + v) * W / 2.0, (v - u) * W / 4.0 - e * W / 64.0


def unproject(z, x, y, e=0.0):
    """pixel offset from the registration point -> (u, v) on the plane at height e."""
    W = TILE_W[z]
    y = y + e * W / 64.0
    s, d = 2.0 * x / W, 4.0 * y / W          # s = u + v, d = v - u
    return (s - d) / 2.0, (s + d) / 2.0


def rot_uv(u, v, steps):
    """slot r -> slot r + steps: turn (u, v) 90 degrees counter-clockwise on screen per step."""
    for _ in range(steps % 4):
        u, v = v, 1.0 - u
    return u, v


_MASKS = {}


def ground_mask(z):
    """-> set of (dx, dy) pixel offsets from the registration point covered by a full flat tile at zoom z,
    measured from piece 39's frames (all four slots identical, checked in `geometry`)."""
    if z not in _MASKS:
        im, (L, T) = stock_frames(FULL_TILE_PIECE)[(z, 0)]
        px = im.load()
        _MASKS[z] = {(x - L, y - T) for y in range(im.height) for x in range(im.width) if px[x, y][3]}
    return _MASKS[z]


def mask_spans(m):
    rows = {}
    for x, y in m:
        lo, hi = rows.get(y, (x, x))
        rows[y] = (min(lo, x), max(hi, x))
    return [(y,) + rows[y] for y in sorted(rows)]


def geometry_table():
    """Measured facts, re-derived from the stock files on every run."""
    out = {"zooms": []}
    for z in range(ZOOMS):
        fr = stock_frames(FULL_TILE_PIECE)
        im, a = fr[(z, 0)]
        same = all(stock_frames(FULL_TILE_PIECE)[(z, r)][1] == a for r in range(ROTS))
        hw, ha = stock_frames(ELEVATED_PIECE)[(z, 0)]
        m = ground_mask(z)
        out["zooms"].append({
            "zoom": z, "tile_w": TILE_W[z], "tile_h": TILE_W[z] // 2,
            "ground_frame": list(im.size), "ground_anchor": list(a), "anchor_same_all_slots": same,
            "ground_mask_px": len(m), "ground_rows": len(mask_spans(m)),
            "ground_rows_y": [mask_spans(m)[0][0], mask_spans(m)[-1][0]],
            "elevated_frame": list(hw.size), "elevated_anchor": list(ha),
            "deck_rise_px": ha[1] - a[1],
        })
    return out


def check_rot(pids=None, min_px=12):
    """For every flat piece (frame height <= ground frame height), map each opaque pixel of slot r through
    unproject -> rot_uv(+1) -> project into slot r+1 and score the overlap (IoU of the two silhouettes).
    -> list of (pid, z, r, iou)."""
    cat = catalog()
    if pids is None:
        pids = [p for p in cat.ids if "ROAD" in cat.rules.sets_of(p)]
    res = []
    for pid in pids:
        try:
            fr = stock_frames(pid)
        except Exception:
            continue
        for z in (2, 3):
            gh = stock_frames(FULL_TILE_PIECE)[(z, 0)][0].height
            for r in range(ROTS):
                if (z, r) not in fr or (z, (r + 1) % 4) not in fr:
                    continue
                a, (La, Ta) = fr[(z, r)]
                b, (Lb, Tb) = fr[(z, (r + 1) % 4)]
                if a.height > gh + 1 or b.height > gh + 1:
                    continue                                    # not flat: has height, skip
                pa, pb = a.load(), b.load()
                sa = {(x - La, y - Ta) for y in range(a.height) for x in range(a.width) if pa[x, y][3]}
                sb = {(x - Lb, y - Tb) for y in range(b.height) for x in range(b.width) if pb[x, y][3]}
                if len(sa) < min_px or len(sb) < min_px:
                    continue
                # sample the DESTINATION grid through the inverse turn: the screen map of a 90 degree tile turn
                # doubles x and halves y, so a forward pixel map leaves holes
                xs = [x for x, _ in sa | sb]
                ys = [y for _, y in sa | sb]
                moved = set()
                for Y in range(min(ys) - 2, max(ys) + 3):
                    for X in range(min(xs) - 2, max(xs) + 3):
                        u, v = unproject(z, X + 0.5, Y + 0.5)
                        u, v = rot_uv(u, v, 3)
                        x, y = project(z, u, v)
                        if (int(math.floor(x)), int(math.floor(y))) in sa:
                            moved.add((X, Y))
                iou = len(moved & sb) / float(len(moved | sb))
                res.append((pid, z, r, iou))
    return res


# ----------------------------------------------------------------------------------------- route a: templates

GUIDE = {"ground": (40, 160, 40, 255), "fill": (90, 120, 90, 90), "edge": (255, 255, 255, 255),
         "mid": (255, 60, 60, 255), "lane": (255, 210, 0, 255), "deck": (60, 140, 255, 255),
         "nb": (160, 160, 160, 160), "reg": (255, 0, 0, 255)}
EDGES = {  # slot-0 tile edges by screen position, as (u0, v0, u1, v1)
    "NW": (0, 0, 1, 0), "NE": (1, 0, 1, 1), "SE": (0, 1, 1, 1), "SW": (0, 0, 0, 1)}


def _poly(z, pts, e, ox, oy):
    return [(ox + project(z, u, v, e)[0], oy + project(z, u, v, e)[1]) for u, v in pts]


def template(out_dir, like=ELEVATED_PIECE, ghost=None, levels=(0.0,), canvas=None, scale=1):
    """Guide PNGs, one per frame, at the SAME size and registration point as piece `like`'s frames (or `canvas`
    {"z3": [w, h, L, T], ...}). Draws: the ground diamond (stock mask), its 4 edges with the slot-0 names
    turned per slot, edge midpoints (arm centres) and quarter points (lane centres), each level in `levels`
    (zoom-3 px above ground, e.g. 32 for the highway deck), the 8 neighbour tiles' outlines and the
    registration point. `ghost`: a stock piece drawn underneath at 35% opacity."""
    os.makedirs(out_dir, exist_ok=True)
    base = stock_frames(like)
    gh = stock_frames(ghost) if ghost is not None else {}
    anchors = {}
    for z in range(ZOOMS):
        for r in range(ROTS):
            im0, (L, T) = base[(z, r)]
            w, h = im0.size
            if canvas and ("z%d" % z) in canvas:
                w, h, L, T = canvas["z%d" % z]
                anchors[frame_name(z, r)] = [L, T]
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            if (z, r) in gh:
                g, (gl, gt) = gh[(z, r)]
                g = g.copy()
                g.putalpha(g.getchannel("A").point(lambda a: a * 35 // 100))
                img.alpha_composite(g, (L - gl, T - gt)) if (L - gl >= 0 and T - gt >= 0) else \
                    img.paste(g, (L - gl, T - gt), g)
            big = img.resize((w * scale, h * scale), Image.NEAREST)
            d = ImageDraw.Draw(big, "RGBA")
            s = scale
            ox, oy = L * s, T * s
            for du in (-1, 0, 1):
                for dv in (-1, 0, 1):
                    if du or dv:
                        pts = [(du, dv), (du + 1, dv), (du + 1, dv + 1), (du, dv + 1)]
                        d.polygon([(x * s, y * s) for x, y in _poly(z, pts, 0, L, T)], outline=GUIDE["nb"])
            for e in levels:
                col = GUIDE["ground"] if e == 0 else GUIDE["deck"]
                poly = _poly(z, [(0, 0), (1, 0), (1, 1), (0, 1)], e, L, T)
                d.polygon([(x * s, y * s) for x, y in poly], outline=col)
                for name, (u0, v0, u1, v1) in EDGES.items():
                    a0, b0 = rot_uv(u0, v0, r)
                    a1, b1 = rot_uv(u1, v1, r)
                    for t, c, rad in ((0.5, GUIDE["mid"], 2), (0.25, GUIDE["lane"], 1), (0.75, GUIDE["lane"], 1)):
                        u, v = a0 + (a1 - a0) * t, b0 + (b1 - b0) * t
                        X, Y = project(z, u, v, e)
                        d.ellipse([(L + X) * s - rad, (T + Y) * s - rad, (L + X) * s + rad, (T + Y) * s + rad],
                                  fill=c)
                    if z >= 3 and e == levels[0]:
                        u, v = a0 + (a1 - a0) * 0.5, b0 + (b1 - b0) * 0.5
                        cu, cv = (u - 0.5) * 0.75 + 0.5, (v - 0.5) * 0.75 + 0.5
                        X, Y = project(z, cu, cv, e)
                        d.text(((L + X) * s - 6, (T + Y) * s - 5), name, fill=GUIDE["edge"])
            if levels and levels[-1] != 0:
                for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    x0, y0 = project(z, u, v, 0)
                    x1, y1 = project(z, u, v, levels[-1])
                    d.line([((L + x0) * s, (T + y0) * s), ((L + x1) * s, (T + y1) * s)], fill=GUIDE["deck"])
            d.rectangle([ox - 1, oy - 1, ox + 1, oy + 1], fill=GUIDE["reg"])
            big.save(os.path.join(out_dir, ("guide_" if scale > 1 else "") + frame_name(z, r)))
    if anchors:
        with open(os.path.join(out_dir, "anchors.json"), "w") as fh:
            json.dump(anchors, fh, indent=1)
    with open(os.path.join(out_dir, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE_README % {"like": like, "levels": list(levels)})
    return out_dir


TEMPLATE_README = """Guide frames generated by netart.py template (like piece %(like)d, levels %(levels)s).

One PNG per frame z{zoom}_r{slot}.png, at the size and registration point of the frame you are replacing.
- green diamond: the tile on the ground; blue diamond(s): the given height(s) in zoom-3 px (32 = highway deck)
- red dots: edge midpoints = where an arm's centre crosses the tile edge; yellow dots: quarter points = lane centres
- grey outlines: the 8 neighbour tiles; red square: the registration point (left ground vertex of the tile)
- the NW/NE/SE/SW labels name the slot-0 edges; slot r shows slot 0 turned r x 90 degrees counter-clockwise
Paint over these at the same size, delete the guide marks, leave unused pixels fully transparent
(alpha < 128 becomes the colour key). Opaque pure magenta is moved one step (it IS the key).
"""


# --------------------------------------------------------------------------------------- route b: compositor

def _region_mask(z, r, size, LT, region, src_e=0.0):
    """Rasterise a tile-space region (slot-0 coords, turned to slot r) into a frame-sized L mask.
    region: {"poly": [[u, v], ...], "e": height, "down": px_extrude} | {"all": true} | {"half": "NE"|...}
    "down": the polygon is extruded straight down by this many zoom-3 px (walls under a deck edge)."""
    w, h = size
    L, T = LT
    m = Image.new("L", (w, h), 0)
    if region.get("all"):
        m.paste(255, (0, 0, w, h))
        return m
    pts = region.get("poly")
    if region.get("half"):
        pts = HALVES[region["half"]]
    e = region.get("e", src_e)
    d = ImageDraw.Draw(m)
    tp = [rot_uv(u, v, r) for u, v in pts]
    poly = [(L + project(z, u, v, e)[0], T + project(z, u, v, e)[1]) for u, v in tp]
    down = region.get("down", 0)
    if down:
        W = TILE_W[z]
        k = down * W / 64.0
        n = len(poly)
        for i in range(n):                      # sweep every edge down: union of quads
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
            d.polygon([(x0, y0), (x1, y1), (x1, y1 + k), (x0, y0 + k)], fill=255)
    d.polygon(poly, fill=255)
    return m


HALVES = {  # slot-0 half tiles cut along a diagonal, named by the screen corner they keep
    "N": [(0, 0), (1, 0), (1, 1)], "S": [(0, 0), (1, 1), (0, 1)],
    "W": [(0, 0), (1, 0), (0, 1)], "E": [(1, 0), (1, 1), (0, 1)]}


def compose(recipe, out_dir, src_dir=None):
    """Route b. recipe = {
        "canvas": <piece> | {"z3": [w, h, L, T], ...}  (frame sizes; default the first layer's piece),
        "layers": [ {"piece": 73 | "dir": "<png_dir>", "slot_offset": 0..3, "region": {...}, "shift": [du, dv],
                     "erase": false}, ... ]   (drawn in order, later on top)
      }
    Each layer takes the source frame for slot (r + slot_offset) % 4 and keeps only the region (tile space,
    slot-0 coords, turned with r). "shift" moves the source by whole/fractional tiles in slot-0 tile space,
    "erase": the region is cleared instead of drawn. Writes z{z}_r{r}.png (+ anchors.json if sizes differ
    from the canvas piece's stock frames)."""
    os.makedirs(out_dir, exist_ok=True)
    srcs = {}

    def frames_of(spec):
        key = json.dumps(spec, sort_keys=True)
        if key not in srcs:
            if "piece" in spec:
                srcs[key] = stock_frames(spec["piece"])
            else:
                p = spec["dir"]
                if src_dir and not os.path.isabs(p):
                    p = os.path.join(src_dir, p)
                fr = load_dir(p)
                srcs[key] = {k: (im, a) for k, (im, a) in fr.items()}
        return srcs[key]

    cv = recipe.get("canvas", recipe["layers"][0].get("piece"))
    anchors = {}
    for z in range(ZOOMS):
        for r in range(ROTS):
            if isinstance(cv, dict):
                w, h, L, T = cv["z%d" % z]
                anchors[frame_name(z, r)] = [L, T]
            else:
                im0, (L, T) = stock_frames(cv)[(z, r)]
                w, h = im0.size
            out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            for lay in recipe["layers"]:
                fr = frames_of(lay)
                sr_ = (r + lay.get("slot_offset", 0)) % 4
                if (z, sr_) not in fr:
                    continue
                src, a = fr[(z, sr_)]
                if a is None:
                    a = stock_frames(cv)[(z, sr_)][1] if not isinstance(cv, dict) else (L, T)
                # shift is a vector in slot-0 tile space: turned with the slot, no translation
                du, dv = _rot_vec(*lay.get("shift", (0, 0)), r)
                sx, sy = project(z, du, dv)
                layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                layer.paste(src, (int(round(L - a[0] + sx)), int(round(T - a[1] + sy))), src)
                reg = lay.get("region", {"all": True})
                m = _region_mask(z, r, (w, h), (L, T), reg)
                if lay.get("erase"):
                    keep = Image.eval(m, lambda v: 255 - v)
                    a_ = out.getchannel("A")
                    out.putalpha(Image.composite(a_, Image.new("L", (w, h), 0), keep))
                    continue
                cut = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                cut.paste(layer, (0, 0), Image.composite(layer.getchannel("A"), Image.new("L", (w, h), 0), m))
                out.alpha_composite(cut)
            out.save(os.path.join(out_dir, frame_name(z, r)))
    if anchors:
        with open(os.path.join(out_dir, "anchors.json"), "w") as fh:
            json.dump(anchors, fh, indent=1)
    return out_dir


def _rot_vec(du, dv, steps):
    for _ in range(steps % 4):
        du, dv = dv, -du
    return du, dv


# ------------------------------------------------------------------------------------- route c: Blender render

BLENDER = os.environ.get("SC3_BLENDER", r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe")
BLENDER_SCRIPT = os.path.join(HERE, "netart_blender.py")
CALIB_DEFAULT = os.path.join(HERE, "netart_calib.json")


def _canvas(z, n=1):
    W = TILE_W[z]
    return 2 * (n + 2) * W, 2 * (n + 3) * W


def run_blender(job, work, blend=None):
    import subprocess
    os.makedirs(work, exist_ok=True)
    jp = os.path.join(work, "job.json")
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(job, fh)
    cmd = [BLENDER, "-b"] + ([blend] if blend else ["--factory-startup"]) + ["-P", BLENDER_SCRIPT, "--", jp]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0 or "Traceback" in (r.stdout or "") + (r.stderr or ""):
        raise RuntimeError("blender failed (%d): %s" % (r.returncode, ((r.stdout or "") + (r.stderr or ""))[-1500:]))
    return r


def crop_frame(render_png, size, LT):
    """Cut a frame of `size` whose registration point LT sits on the render centre pixel (cw/2, ch/2)."""
    im = Image.open(render_png).convert("RGBA")
    cw, ch = im.size
    x0, y0 = cw // 2 - LT[0], ch // 2 - LT[1]
    return im.crop((x0, y0, x0 + size[0], y0 + size[1]))


def auto_frame(render_png, n=1, z=3):
    """Frame for NEW art: the opaque bounding box, clipped horizontally to the footprint (the engine clips a
    piece to n * (8 << z) px from the left vertex, SIMSPR 0x1000be25). -> (image, (L, T))."""
    im = Image.open(render_png).convert("RGBA")
    cw, ch = im.size
    a = im.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    bb = a.getbbox()
    if not bb:
        raise RuntimeError("%s: empty render" % render_png)
    x0, x1 = cw // 2, cw // 2 + n * TILE_W[z]
    return im.crop((x0, bb[1], x1, bb[3])), (cw // 2 - x0, ch // 2 - bb[1])


def cut_alpha(im, threshold=128):
    """Alpha is a cut, not a channel: >= threshold becomes opaque, the rest the colour key."""
    out = im.copy()
    out.putalpha(im.getchannel("A").point(lambda v: 255 if v >= threshold else 0))
    return out


def quantize565(im, palette=None):
    """-> the exact colours the game will show (5/6/5, expanded like the exporter), never the colour key.
    palette: optional RGB list; each opaque pixel snaps to the nearest entry first (the 'materials' step)."""
    import numpy as np
    pal = np.array(palette, dtype=float) if palette else None
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a < 128:
                px[x, y] = (0, 0, 0, 0)
                continue
            if pal is not None:
                r, g, b = [int(v) for v in pal[int(np.argmin(((pal - (r, g, b)) ** 2).sum(1)))]]
            q = (r >> 3, g >> 2, b >> 3)
            if q == (31, 0, 31):
                q = (31, 0, 30)
            px[x, y] = (q[0] * 255 // 31, q[1] * 255 // 63, q[2] * 255 // 31, 255)
    return im


def stock_palette(pid, max_colors=256):
    """The most used colours of a stock piece's frames."""
    from collections import Counter
    c = Counter()
    for (im, _a) in stock_frames(pid).values():
        for p in im.getdata():
            if p[3]:
                c[p[:3]] += 1
    return [k for k, _ in c.most_common(max_colors)]


def load_calib(path=None):
    """-> ({zoom: (dx, dy)}, {zoom: bleed}) from a calibrate report (default netart_calib.json)."""
    p = path or CALIB_DEFAULT
    if os.path.isfile(p):
        j = json.load(open(p))
        return ({int(k[1:]): tuple(v) for k, v in j["shift"].items()},
                {int(k[1:]): v for k, v in j.get("bleed", {}).items()} or {z: 0.0 for z in range(ZOOMS)})
    return {z: (0.0, 0.0) for z in range(ZOOMS)}, {z: 0.0 for z in range(ZOOMS)}


def mask_of(im):
    px = im.load()
    return {(x, y) for y in range(im.height) for x in range(im.width) if px[x, y][3] >= 128}


def compare_masks(a, b):
    """-> px in each, xor, IoU, and 'gross': xor pixels more than 1 px away from b's silhouette edge."""
    x = a ^ b
    bd = set()
    for p in b:
        if not all((p[0] + dx, p[1] + dy) in b for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            bd |= {(p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    return {"a": len(a), "b": len(b), "xor": len(x), "iou": len(a & b) / float(len(a | b) or 1),
            "gross": len([p for p in x if p not in bd])}


STEPS = tuple(k / 4.0 for k in range(-6, 7))      # -1.5 .. +1.5 px in quarter steps
BLEEDS = (0.0, 0.25, 0.5, 0.75, 1.0)


def calibrate(pid, model, work, steps=STEPS, bleeds=BLEEDS, out_json=None):
    """Route c calibration: render `model` (netart_blender scene spec, e.g. {"build": "box", "height": 4}) with
    every sub-pixel camera shift (dx, dy) and footprint bleed per zoom, compare its silhouette with stock piece
    `pid` at every zoom x slot, keep the combination with the fewest mismatched pixels (ties: the smallest
    change). -> report dict, written to out_json; its "shift" + "bleed" feed `render` (netart_calib.json)."""
    stock = stock_frames(pid)
    n = model.get("n", 1)
    name = lambda z, r, dx, dy, b: os.path.join(  # noqa: E731
        work, "c_z%d_r%d_%+.2f_%+.2f_b%.2f.png" % (z, r, dx, dy, b))
    combos = [(dx, dy, b) for b in bleeds for dx in steps for dy in steps]
    renders = [{"z": z, "r": r, "dx": dx, "dy": dy, "bleed": b, "canvas": list(_canvas(z, n)),
                "out": name(z, r, dx, dy, b).replace("\\", "/")}
               for z in range(ZOOMS) for dx, dy, b in combos for r in range(ROTS)]
    run_blender({"scene": model, "engine": "WORKBENCH", "renders": renders}, work)
    rep = {"piece": pid, "model": model, "shift": {}, "bleed": {}, "frames": {}}
    sm = {k: mask_of(im) for k, (im, _) in stock.items()}
    for z in range(ZOOMS):
        best = None
        for dx, dy, b in combos:
            tot = 0
            for r in range(ROTS):
                im, LT = stock[(z, r)]
                tot += len(mask_of(crop_frame(name(z, r, dx, dy, b), im.size, LT)) ^ sm[(z, r)])
            key = (tot, b, abs(dx) + abs(dy))
            if best is None or key < best[0]:
                best = (key, dx, dy, b)
        _, dx, dy, b = best
        rep["shift"]["z%d" % z] = [dx, dy]
        rep["bleed"]["z%d" % z] = b
        for r in range(ROTS):
            im, LT = stock[(z, r)]
            rep["frames"]["z%d_r%d" % (z, r)] = compare_masks(
                mask_of(crop_frame(name(z, r, dx, dy, b), im.size, LT)), sm[(z, r)])
    if out_json:
        with open(out_json, "w") as fh:
            json.dump(rep, fh, indent=1)
    return rep


def evaluate(pid, model, work, calib=None, out_json=None):
    """Render `model` with a FIXED calibration (default netart_calib.json) and compare with stock piece `pid`
    at every zoom x slot: measures the model, not the camera. -> report dict."""
    sh, bl = calib or load_calib()
    stock = stock_frames(pid)
    n = model.get("n", 1)
    name = lambda z, r: os.path.join(work, "e_z%d_r%d.png" % (z, r))  # noqa: E731
    run_blender({"scene": model, "engine": "WORKBENCH",
                 "renders": [{"z": z, "r": r, "dx": sh[z][0], "dy": sh[z][1], "bleed": bl[z],
                              "canvas": list(_canvas(z, n)), "out": name(z, r).replace("\\", "/")}
                             for z in range(ZOOMS) for r in range(ROTS)]}, work)
    rep = {"piece": pid, "model": model, "shift": {"z%d" % z: list(sh[z]) for z in range(ZOOMS)},
           "bleed": {"z%d" % z: bl[z] for z in range(ZOOMS)}, "frames": {}}
    for z in range(ZOOMS):
        for r in range(ROTS):
            im, LT = stock[(z, r)]
            rep["frames"]["z%d_r%d" % (z, r)] = compare_masks(mask_of(crop_frame(name(z, r), im.size, LT)),
                                                              mask_of(im))
    if out_json:
        with open(out_json, "w") as fh:
            json.dump(rep, fh, indent=1)
    return rep


def render(scene, out_dir, work, like=None, calib=None, engine="CYCLES", samples=16, blend=None, palette=None,
           zooms=range(ZOOMS), n=1):
    """Route c: render a piece at every zoom x slot, cut alpha, quantise, write a netpack png_dir.
    like: a stock piece whose frame sizes / anchors to reuse (else auto frames + anchors.json)."""
    sh, bl = calib or load_calib()
    renders = [{"z": z, "r": r, "dx": sh[z][0], "dy": sh[z][1], "bleed": bl[z], "canvas": list(_canvas(z, n)),
                "out": os.path.join(work, "b_z%d_r%d.png" % (z, r)).replace("\\", "/")}
               for z in zooms for r in range(ROTS)]
    run_blender({"scene": scene, "engine": engine, "samples": samples, "renders": renders}, work, blend=blend)
    os.makedirs(out_dir, exist_ok=True)
    base = stock_frames(like) if like is not None else None
    anchors = {}
    for z in zooms:
        for r in range(ROTS):
            src = os.path.join(work, "b_z%d_r%d.png" % (z, r))
            if base:
                im, LT = base[(z, r)]
                fr = crop_frame(src, im.size, LT)
            else:
                fr, LT = auto_frame(src, n, z)
                anchors[frame_name(z, r)] = list(LT)
            quantize565(cut_alpha(fr), palette).save(os.path.join(out_dir, frame_name(z, r)))
    if anchors:
        with open(os.path.join(out_dir, "anchors.json"), "w") as fh:
            json.dump(anchors, fh, indent=1)
    return out_dir


# ------------------------------------------------------------------------------------------------- preview

def preview(layout, out_png, src_dir=None, zooms=range(ZOOMS), rots=range(ROTS), pad=8, bg=(54, 88, 54, 255)):
    """Assemble pieces on a small tile grid, every zoom x rotation, as the engine draws them (back to front).
    layout = {"cells": [{"at": [u, v], "piece": 73 | "dir": "<png_dir>", "slot": 0..3}, ...]} in view-0 tile
    coordinates (u, v integers). For view rotation r every cell moves with rot_uv about the layout centre and
    its slot becomes (slot + r) % 4. Writes one sheet: rows = zoom, columns = rotation.
    Returns {(z, r): image}."""
    cells = layout["cells"]
    us = [c["at"][0] for c in cells]
    vs = [c["at"][1] for c in cells]
    cu, cv = (min(us) + max(us) + 1) / 2.0, (min(vs) + max(vs) + 1) / 2.0
    srcs = {}

    def frames_of(c):
        k = c.get("piece", c.get("dir"))
        if k not in srcs:
            if "piece" in c:
                srcs[k] = stock_frames(c["piece"])
            else:
                p = c["dir"] if (not src_dir or os.path.isabs(c["dir"])) else os.path.join(src_dir, c["dir"])
                srcs[k] = load_dir(p)
        return srcs[k]

    shots = {}
    for z in zooms:
        W = TILE_W[z]
        for r in rots:
            placed = []
            for c in cells:
                u, v = c["at"]
                # turn the cell's centre about the layout centre
                du, dv = _rot_vec(u + 0.5 - cu, v + 0.5 - cv, r)
                u2, v2 = cu + du - 0.5, cv + dv - 0.5
                placed.append((u2, v2, c, (c.get("slot", 0) + r) % 4))
            # painter's order: back (screen top) to front; screen depth = u... draw by (v - u) then x
            placed.sort(key=lambda p: (p[1] - p[0], p[0] + p[1]))
            n = max(max(us) - min(us), max(vs) - min(vs)) + 3
            w = int(n * W + 2 * pad)
            h = int(n * W + 2 * pad)
            img = Image.new("RGBA", (w, h), bg)
            ox, oy = pad, h // 2
            for u2, v2, c, s in placed:
                fr = frames_of(c)
                if (z, s) not in fr:
                    continue
                im, a = fr[(z, s)]
                if a is None:
                    a = stock_frames(c.get("like", ELEVATED_PIECE))[(z, s)][1]
                X, Y = project(z, u2 - min(us) + 1, v2 - min(vs) + 1)
                img.alpha_composite(im, (int(round(ox + X - a[0])), int(round(oy + Y - a[1] - W / 2))))
            shots[(z, r)] = img
    if out_png:
        cw = max(i.width for i in shots.values())
        ch = max(i.height for i in shots.values())
        sheet = Image.new("RGBA", (cw * len(list(rots)), ch * len(list(zooms))), (20, 20, 20, 255))
        for (z, r), im in shots.items():
            sheet.paste(im, (list(rots).index(r) * cw, list(zooms).index(z) * ch))
        sheet.save(out_png)
    return shots


# ---------------------------------------------------------------------------------------------------- lint

def lint(png_dir, like=ELEVATED_PIECE):
    """Checks a png_dir before netpack sees it. -> list of (severity, text)."""
    out = []
    fr = load_dir(png_dir)
    base = stock_frames(like)
    for z in range(ZOOMS):
        for r in range(ROTS):
            n = frame_name(z, r)
            if (z, r) not in fr:
                out.append(("WARN", "%s missing: the variant keeps the source frame" % n))
                continue
            im, a = fr[(z, r)]
            bim, ba = base[(z, r)]
            if im.size != bim.size and a is None:
                out.append(("ERROR", "%s is %dx%d, source frame %dx%d, and anchors.json has no entry"
                            % (n, im.width, im.height, bim.width, bim.height)))
            al = im.getchannel("A")
            soft = sum(1 for v in al.getdata() if 0 < v < 255)
            if soft:
                out.append(("INFO", "%s: %d semi-transparent pixels (cut at alpha 128, no blending in game)" % (n, soft)))
            mag = sum(1 for p in im.getdata() if p[3] >= 128 and (p[0] >> 3, p[1] >> 2, p[2] >> 3) == (31, 0, 31))
            if mag:
                out.append(("WARN", "%s: %d opaque pixels quantise onto the colour key (nudged one step blue)" % (n, mag)))
    return out


# ------------------------------------------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("geometry")
    g.add_argument("--json")
    sub.add_parser("check-rot")
    t = sub.add_parser("template")
    t.add_argument("dir")
    t.add_argument("--like", type=int, default=ELEVATED_PIECE)
    t.add_argument("--ghost", type=int)
    t.add_argument("--levels", default=None, help="comma list of heights in zoom-3 px (default: 0, plus 32 "
                                                    "when --like is elevated)")
    t.add_argument("--scale", type=int, default=1, help=">1 also writes enlarged guide_*.png for viewing")
    c = sub.add_parser("compose")
    c.add_argument("recipe")
    c.add_argument("dir")
    p = sub.add_parser("preview")
    p.add_argument("layout")
    p.add_argument("out")
    p.add_argument("--zoom", type=int, action="append")
    cb = sub.add_parser("calibrate")
    cb.add_argument("piece", type=int)
    cb.add_argument("work")
    cb.add_argument("--model", default='{"build": "box", "height": 4}')
    cb.add_argument("--out", help="report json (default <work>/calib_<piece>.json)")
    cb.add_argument("--fixed", action="store_true", help="no search: evaluate the model with netart_calib.json")
    rn = sub.add_parser("render")
    rn.add_argument("scene", help="scene json for netart_blender.py, or a .blend with SC3_PIECE / SC3_ROOT")
    rn.add_argument("dir")
    rn.add_argument("--work", required=True)
    rn.add_argument("--like", type=int)
    rn.add_argument("--engine", default="CYCLES")
    rn.add_argument("--samples", type=int, default=16)
    rn.add_argument("--palette-from", type=int)
    li = sub.add_parser("lint")
    li.add_argument("dir")
    li.add_argument("--like", type=int, default=ELEVATED_PIECE)
    a = ap.parse_args(argv)

    if a.cmd == "geometry":
        t = geometry_table()
        for zr in t["zooms"]:
            print("zoom %(zoom)d: tile %(tile_w)dx%(tile_h)d, ground frame %(ground_frame)s anchor %(ground_anchor)s"
                  " (same all slots: %(anchor_same_all_slots)s), mask %(ground_mask_px)d px in %(ground_rows)d rows;"
                  " elevated frame %(elevated_frame)s anchor %(elevated_anchor)s, deck rise %(deck_rise_px)d px" % zr)
        if a.json:
            with open(a.json, "w") as fh:
                json.dump(t, fh, indent=1)
        return 0
    if a.cmd == "check-rot":
        res = check_rot()
        ious = sorted(x[3] for x in res)
        good = sum(1 for x in ious if x >= 0.6)
        print("flat ROAD frames compared slot r -> r+1 (CCW turn): %d pairs, IoU >= 0.6 in %d, median %.3f, min %.3f"
              % (len(res), good, ious[len(ious) // 2], ious[0]))
        ccw = good
        # the opposite turn, for contrast
        global rot_uv
        keep = rot_uv
        rot_uv = lambda u, v, s: keep(u, v, -s % 4)   # noqa: E731
        res2 = check_rot()
        rot_uv = keep
        ious2 = sorted(x[3] for x in res2)
        print("same pairs with a CLOCKWISE turn: IoU >= 0.6 in %d, median %.3f"
              % (sum(1 for x in ious2 if x >= 0.6), ious2[len(ious2) // 2]))
        bad = [x for x in res if x[3] < 0.6]
        for x in bad[:20]:
            print("  low: piece %d zoom %d slot %d->%d IoU %.2f" % (x[0], x[1], x[2], (x[2] + 1) % 4, x[3]))
        return 0 if ccw else 1
    if a.cmd == "template":
        base = stock_frames(a.like)
        rise = base[(3, 0)][1][1] - stock_frames(FULL_TILE_PIECE)[(3, 0)][1][1]
        lv = [float(x) for x in a.levels.split(",")] if a.levels else ([0.0, float(rise)] if rise > 0 else [0.0])
        template(a.dir, like=a.like, ghost=a.ghost, levels=lv)
        if a.scale > 1:
            template(a.dir, like=a.like, ghost=a.ghost, levels=lv, scale=a.scale)
        print("guide frames for piece %d (levels %s) in %s" % (a.like, lv, a.dir))
        return 0
    if a.cmd == "compose":
        rec = json.load(open(a.recipe, encoding="utf-8"))
        compose(rec, a.dir, src_dir=os.path.dirname(os.path.abspath(a.recipe)))
        print("composed 20 frames into", a.dir)
        return 0
    if a.cmd == "preview":
        lay = json.load(open(a.layout, encoding="utf-8"))
        preview(lay, a.out, src_dir=os.path.dirname(os.path.abspath(a.layout)),
                zooms=a.zoom or range(ZOOMS))
        print(a.out)
        return 0
    if a.cmd == "calibrate":
        fn = evaluate if a.fixed else calibrate
        rep = fn(a.piece, json.loads(a.model), a.work,
                 out_json=a.out or os.path.join(a.work, "%s_%d.json" % ("eval" if a.fixed else "calib", a.piece)))
        for z in range(ZOOMS):
            fr = [rep["frames"]["z%d_r%d" % (z, r)] for r in range(ROTS)]
            print("zoom %d shift %s bleed %s: stock px %s, mismatched %s, IoU %s, beyond 1 px of the edge %s"
                  % (z, rep["shift"]["z%d" % z], rep["bleed"]["z%d" % z], [f["b"] for f in fr], [f["xor"] for f in fr],
                     ["%.3f" % f["iou"] for f in fr], [f["gross"] for f in fr]))
        return 0
    if a.cmd == "render":
        blend = a.scene if a.scene.lower().endswith(".blend") else None
        scene = {"build": "blend"} if blend else json.load(open(a.scene, encoding="utf-8"))
        pal = stock_palette(a.palette_from) if a.palette_from else None
        render(scene, a.dir, a.work, like=a.like, engine=a.engine, samples=a.samples, blend=blend, palette=pal)
        print("rendered 20 frames into", a.dir)
        return 0
    if a.cmd == "lint":
        probs = lint(a.dir, a.like)
        for s, t in probs:
            print(s, t)
        return 1 if any(s == "ERROR" for s, _ in probs) else 0


if __name__ == "__main__":
    sys.exit(main())
