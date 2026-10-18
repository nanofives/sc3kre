#!/usr/bin/env python3
r"""hwdx_paint.py - the hwdx cloverleaf as an hwpaint scene (stream hwdx, 2026-10-18): mockup previews and, later, the
per-cell art of the package.

  py -3.12 hwdx_paint.py mockup OUT.png [--art DIR]    zoom 3 and 4, views 0 and 1, case A (plan clover)
  py -3.12 hwdx_paint.py art PKG_DIR [id ...]          the package art: PKG_DIR/art/<id>/ (gitignored)
  py -3.12 hwdx_paint.py pad PKG_DIR                   grow every frame to its full cell diamond (after art)

The geometry is hwdx_plan.py (case frame = world frame of case A with O at (0, 0)); hwpaint.py is hwcore's painter,
copied verbatim. Plain highway cells inside the view stay stock pieces (15051 for S, 11223 / 11224 for D); every cell a
ramp or the bridge touches is painted.
Heights: S rises H -> H_HIGH over its arm cell and crosses the band on a slab (the stock X's upper deck); D dips
H -> H_LOW over its arm rows and runs under S (the stock X's lower deck); ramps stay at H on walls.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from netmod import hwpaint as HP  # noqa: E402
from netmod import hwdx_plan as G  # noqa: E402
from netmod import netart as NA  # noqa: E402

R2 = math.sqrt(2.0)
RAMP_W = 2 * G.W      # 0.62, the stock ramp width (program decision 2026-10-18)
N = 14                # mainline half length in the scene


def seg_paths(t, flip=False):
    """an hwdx_plan Turtle -> hwpaint Path (S tapers as short lines); flip = the 180-degree twin"""
    f = (lambda p: (-p[0], -p[1])) if flip else (lambda p: p)
    out = []
    for s in t.segs:
        if s[0] == "line":
            out.append(HP.Line(f(s[1]), f(s[2])))
        elif s[0] == "arc":
            c, R, a0, dh = f(s[1]), s[2], s[3] + (180.0 if flip else 0.0), s[4]
            out.append(HP.Arc(c, R, math.radians(a0), math.radians(dh)))
        else:
            p0, p1, p2, p3 = s[1], s[2], s[3], s[4]
            pts = []
            for k in range(13):
                u = k / 12
                a, b, c, d = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
                pts.append(f((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                              a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])))
            out += [HP.Line(pts[k], pts[k + 1]) for k in range(12) if pts[k] != pts[k + 1]]
    return HP.Path(out)


def s_height(x0, x1):
    """S carriageway height along its path: rises over the arm cell [x0 - 1, x0], bridge to x1, falls over [x1, x1+1]
    (x measured along the direction of travel)"""
    return lambda s: np.minimum(HP.ramp(HP.H, HP.H_HIGH, x0 - 1, x0)(s), HP.ramp(HP.H_HIGH, HP.H, x1, x1 + 1)(s))


def _gaps(ramps):
    """parapet openings on the mainline decks where the ramps join: {deck name: [(s0, s1, "outer")]}. A ramp's first /
    last segment is its S taper; its end on the carriageway's outer lane says which deck it joins."""
    out = {}
    for t, flip in ramps:
        for g in (t.segs[0], t.segs[-1]):
            if g[0] != "bez":
                continue
            p0, p3 = g[1], g[4]
            if flip:
                p0, p3 = (-p0[0], -p0[1]), (-p3[0], -p3[1])
            on = p0 if g is t.segs[0] else p3                  # the end on the carriageway
            if abs(abs(on[1]) - G.S_OUT) < 1e-6:
                name = "S+x" if on[1] < 0 else "S-x"
                along = (lambda q: q[0] + N) if name == "S+x" else (lambda q: N - q[0])
            else:
                k = on[0] - on[1]
                name = "D+" if k > 0 else "D-"
                L = 2 * N * R2
                along = (lambda q: (q[0] + q[1] + 2 * N) / R2) if name == "D+" else                     (lambda q: L - (q[0] + q[1] + 2 * N) / R2)
            a, b = sorted((along(p0), along(p3)))
            out.setdefault(name, []).append((a - 0.15, b + 0.15, "outer"))
    return out


def scene_A():
    ramps = [(t, False) for t in G.ramps_north("clover").values()] +             [(t, True) for t in G.ramps_north("clover").values()]
    gaps = _gaps(ramps)
    decks = []
    # S: +x-bound in row -1 (bridge over cells -2..0, arms -3 and 1), -x-bound in row 0 (bridge -1..1, arms -2, 2)
    eb = HP.Path.line((-N, -0.5), (N, -0.5))                       # s = x + N
    decks.append(HP.Deck(eb, 1.0, "hw", "right", height=s_height(N - 2, N + 1), slab=[(N - 2, N + 1)],
                         gaps=gaps.get("S+x", []), name="S+x"))
    wb = HP.Path.line((N, 0.5), (-N, 0.5))                         # s = N - x
    decks.append(HP.Deck(wb, 1.0, "hw", "right", height=s_height(N - 2, N + 1), slab=[(N - 2, N + 1)],
                         gaps=gaps.get("S-x", []), name="S-x"))
    # D (hwpaint.highway_diag: stock band width, tops and walls from the stock band pieces): dips over rows -2 and 1,
    # runs at H_LOW under S; s along the median = (z + N) * sqrt 2
    zs = lambda z: (z + N) * R2                                    # noqa: E731
    dn = lambda s: np.maximum(HP.ramp(HP.H, HP.H_LOW, zs(-2), zs(-1))(s), HP.ramp(HP.H_LOW, HP.H, zs(1), zs(2))(s))  # noqa
    d_up, d_down = HP.highway_diag(HP.Path.line((-N, -N), (N, N)), height=dn, gaps=gaps.get("D+", []))
    d_down.gaps = [(g0, g1, sd) for g0, g1, sd in gaps.get("D-", [])]
    d_up.name, d_down.name = "D+", "D-"
    decks += [d_up, d_down]
    for name, t in G.ramps_north("clover").items():
        for flip in (False, True):
            path = seg_paths(t, flip)
            spans, piers = slab_spans(path)
            decks.append(HP.ramp_deck(path, outer="right", width=RAMP_W, slab=spans, thick=RAMP_SLAB, pillars=piers,
                                      name=G.twin_names("clover")[name] if flip else name))
    return HP.Scene(decks)


RAMP_SLAB = 10.25         # ramp slab thickness: the fitted stock 15127 (hwpaint proof), as hwx / hwt
WALL_NEAR = 0.45          # a ramp keeps its embankment walls within this of a highway edge (alongside, merging)
PILLAR_STEP = 1.25        # cells of slab between pillars (hwt 1.25 .. 1.3)
PILLAR_CLEAR = 0.7        # a pillar stands at least this far from a highway edge


def _edge_dist(x, z):
    """distance from a point to the nearest highway edge (negative inside a carriageway): S rows |z| <= 1, D band
    |x - z| / sqrt2 <= W_DIAG"""
    return min(abs(z) - 1.0, abs(x - z) / R2 - HP.W_DIAG)


def slab_spans(path, step=0.05):
    """the free-standing stretches of a ramp (farther than WALL_NEAR from every highway edge) -> ([(s0, s1)] slab
    spans, pillar points). The rest stays on embankment walls, so a ramp merges into the highway's wall as stock."""
    n = max(2, int(path.length / step))
    free = []
    for k in range(n + 1):
        sk = path.length * k / n
        (x, z), _ = path.at(sk)
        free.append((sk, _edge_dist(x, z) > WALL_NEAR))
    spans, s0 = [], None
    for sk, f in free:
        if f and s0 is None:
            s0 = sk
        if not f and s0 is not None:
            spans.append((s0, sk))
            s0 = None
    if s0 is not None:
        spans.append((s0, path.length))
    spans = [(a, b) for a, b in spans if b - a >= 0.4]
    piers = []
    for a, b in spans:
        m = max(1, int(round((b - a) / PILLAR_STEP)))
        for i in range(m):
            sk = a + (b - a) * (i + 0.5) / m
            (x, z), _ = path.at(sk)
            if _edge_dist(x, z) > PILLAR_CLEAR:
                piers.append((x, z))
    return spans, piers


def _xpt(p, rot, mirror):
    x, z = p
    if mirror:
        z = -z
    for _ in range(rot % 4):
        x, z = -z, x                                   # (x, z) -> (-z, x): one state
    return (x, z)


def _xseg(g, rot, mirror):
    """a Line / Arc mirrored (z -> -z, then reversed so the direction of travel is mirrored + reversed: case B) and
    turned rot quarter turns"""
    if isinstance(g, HP.Line):
        a, _ = g.at(0.0)
        b, _ = g.at(g.length)
        if mirror:
            a, b = b, a
        return HP.Line(_xpt(a, rot, mirror), _xpt(b, rot, mirror))
    a0, sw = g.a0, g.sweep
    if mirror:
        a0, sw = -a0, -sw                              # mirrored
        a0, sw = a0 + sw, -sw                          # reversed
    return HP.Arc(_xpt(g.c, rot, mirror), g.R, a0 + rot * math.pi / 2, sw)


def xdeck(d, rot, mirror):
    segs = [_xseg(g, rot, mirror) for g in d.path.segs]
    if mirror:
        segs.reverse()
    path = HP.Path(segs)
    L = d.path.length
    h = d.h
    slab = list(d.slab)
    if mirror:
        h = (lambda f: (lambda s: f(L - np.asarray(s, dtype=float))))(d.h)
        slab = [(L - s1, L - s0) for s0, s1 in d.slab]
    gaps = [(L - g1, L - g0, sd) for g0, g1, sd in d.gaps] if mirror else list(d.gaps)
    return HP.Deck(path, d.w, d.profile, d.outer, h, d.support, d.thick, [_xpt(p, rot, mirror) for p in d.pillars],
                   d.pw, None, d.ends[::-1] if mirror else d.ends, d.name, d.fascia, slab, gaps=gaps)


def scene(case="A", rot=0):
    """the cloverleaf of `case` (B = A mirrored, directions reversed) turned `rot` quarter turns about O = (0, 0)"""
    base = scene_A()
    if case == "A" and rot % 4 == 0:
        return base
    return HP.Scene([xdeck(d, rot, case == "B") for d in base.decks])


def stock_cell(c):
    """the stock piece of a plain mainline cell of case A, or None"""
    i, j = c
    if j == -1:
        return (15051, 2)
    if j == 0:
        return (15051, 0)
    k = i - j
    return {1: (11223, 0), 0: (11224, 0), -1: (11223, 2)}.get(k)


def layout(box):
    g, core, att, ramp = G.classify("clover", "A")
    paint = sorted(g)
    extra = []
    i0, i1, j0, j1 = box
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            if (i, j) in g:
                continue
            p = stock_cell((i, j))
            if p:
                extra.append({"at": [-i, j], "piece": p[0], "slot": p[1]})
    return paint, extra


def label(im, text):
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype("arialbd.ttf", 16)
    except OSError:
        f = ImageFont.load_default()
    d.rectangle([0, 0, 8 + 9 * len(text), 24], fill=(20, 20, 20, 255))
    d.text((5, 3), text, fill=(255, 255, 255, 255), font=f)
    return im


def paint_missing(sc, cells, z, art):
    """paint the cells whose zoom-z frames are not on disk yet (a killed run resumes)"""
    n = 0
    for c in cells:
        d = os.path.join(art, "%d_%d" % c)
        if all(os.path.exists(os.path.join(d, "z%d_r%d.png" % (z, r))) for r in range(4)) and                 os.path.exists(os.path.join(d, "anchors.json")):
            continue
        HP.paint_cell(sc, c, d, zooms=[z])
        n += 1
    return n


def cmd_mockup(out, art):
    sc = scene_A()
    views = {3: (-13, 12, -10, 9), 4: (-6, 5, -5, 4)}           # zoom 4: the middle (core and the four corners)
    shots = {}
    for z, box in views.items():
        paint, extra = layout(box)
        paint = [c for c in paint if box[0] <= c[0] <= box[1] and box[2] <= c[1] <= box[3]]
        print("z%d: painted %d new cells" % (z, paint_missing(sc, paint, z, art)), flush=True)
        for r in (0, 1):
            im = HP.preview_cells(sc, paint, z, r, art, extra=extra, paint=False)
            im.save(os.path.join(art, "mockup_z%d_r%d.png" % (z, r)))
            shots[(z, r)] = im
            print("z%d r%d" % (z, r), im.size, flush=True)
    rows = []
    for z in (3, 4):
        a, b = shots[(z, 0)], shots[(z, 1)]
        row = Image.new("RGBA", (a.width + b.width, max(a.height, b.height)), (20, 20, 20, 255))
        row.paste(label(a.copy(), "zoom %d, view 0%s" % (z, "" if z == 3 else " (middle)")), (0, 0))
        row.paste(label(b.copy(), "zoom %d, view 1%s" % (z, "" if z == 3 else " (middle)")), (a.width, 0))
        rows.append(row)
    W = max(r.width for r in rows)
    sheet = Image.new("RGBA", (W, sum(r.height for r in rows)), (20, 20, 20, 255))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.convert("RGB").save(out)
    print("wrote", out, sheet.size, flush=True)


def cmd_art(pkg, only=None):
    """paint every piece of the package into <pkg>/art/<id>/ (all zooms, state 0): the rep cell of its class in the
    crossing turned so that cell's piece sits at state 0 (hwdx.pieces_list). Resumes: complete folders are skipped."""
    from netmod import hwdx as H
    cache = {}
    P = H.pieces_list()
    done = 0
    for p in P:
        if only and p["id"] not in only:
            continue
        d = os.path.join(pkg, "art", str(p["id"]))
        if os.path.exists(os.path.join(d, "anchors.json")) and all(
                os.path.exists(os.path.join(d, "z%d_r%d.png" % (z, r))) for z in range(5) for r in range(4)):
            continue
        case, c = p["rep"]
        key = (case, p["r"])
        if key not in cache:
            cache[key] = scene(case, p["r"])
        w = H.to_world((0, 0), p["r"], c)
        HP.paint_cell(cache[key], w, d, crop=os.environ.get("HWDX_FULL") != "1")   # HWDX_FULL=1: full-column frames
        done += 1
        print("piece %d (%s, class %d, flavour %d): case %s cell %s at r %d -> world %s" % (
            p["id"], p["kind"], p["cls"], p["flavour"], case, c, p["r"], w), flush=True)
    print("painted %d pieces" % done)


def cmd_lanes(pkg, shape0):
    """lane specs for every piece: <pkg>/lanes/<id>.json. Lanes are cut by hwcore's hwlanes from the same decks the art
    is painted from (rep cell, crossing turned so it sits at state 0), records for all four states; the turn matrix is
    hwdx's own table (hwdx.pieces_list flows), not "auto": in the core the true-geometry lanes would merge S and D
    (README section 4). -> next free curve shape"""
    import json
    from netmod import hwdx as H
    from netmod import hwlanes as HL
    os.makedirs(os.path.join(pkg, "lanes"), exist_ok=True)
    cache = {}
    shape = shape0
    nl = 0
    for p in H.pieces_list():
        case, c = p["rep"]
        key = (case, p["r"])
        if key not in cache:
            cache[key] = scene(case, p["r"])
        w = H.to_world((0, 0), p["r"], c)
        specs, shape = HL.build_cells(cache[key].decks, [w], shape, {w: p["id"]}, states=(0, 1, 2, 3))
        spec = specs.get(w)
        low = [list(f) for f in p["flows"]]
        if spec is None:                                  # no lane crosses the cell (a deck edge): matrix only
            spec = {"piece": p["id"], "states": [0, 1, 2, 3], "flag": 0, "vehicle": {"class": "car", "lanes": []}}
        spec["connects"] = {"road": {"low": low, "high": [[l, e] for e, l in low]}}
        nl += len(spec["vehicle"]["lanes"])
        with open(os.path.join(pkg, "lanes", "%d.json" % p["id"]), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(spec, fh, indent=1)
    print("lane specs for %d pieces, %d lanes, curve shapes %d..%d" % (len(H.pieces_list()), nl, shape0, shape - 1))
    return shape


def cmd_pad(pkg):
    """grow every frame to cover its whole cell diamond (transparent padding, anchors moved), as hwt_build.py pad:
    with ground_under the engine draws the terrain only under the frame's rectangle, so a frame cropped to its art
    leaves the rest of the diamond undrawn (stale pixels). With art "from" 15127 (its frame table) this is the
    program's ground rule (HWY_BASE.md, 2026-10-18)."""
    import json
    n = 0
    for d in sorted(os.listdir(os.path.join(pkg, "art"))):
        ad = os.path.join(pkg, "art", d)
        a = json.load(open(os.path.join(ad, "anchors.json")))
        for name, (L, T) in list(a.items()):
            z = int(name[1])
            W = NA.TILE_W[z]
            im = Image.open(os.path.join(ad, name)).convert("RGBA")
            ox = max(0, -L)
            L2 = L + ox
            q = W // 4 + 1
            oy = max(0, q - T)
            T2 = T + oy
            w2 = max(ox + im.width, L2 + W + 1)
            h2 = max(oy + im.height, T2 + q)
            if (w2, h2) == im.size and (ox, oy) == (0, 0):
                continue
            out = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
            out.alpha_composite(im, (ox, oy))
            out.save(os.path.join(ad, name))
            a[name] = [L2, T2]
            n += 1
        with open(os.path.join(ad, "anchors.json"), "w") as fh:
            json.dump(dict(sorted(a.items())), fh, indent=1)
    print("pad: %d frames grown to their full cell diamond" % n)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "mockup":
        art = a[a.index("--art") + 1] if "--art" in a else os.path.join(HERE, "..", "..", "..", "verify", "hwdx", "art",
                                                                        "mockup")
        os.makedirs(art, exist_ok=True)
        cmd_mockup(a[1], art)
    elif a and a[0] == "lanes":
        cmd_lanes(a[1], int(a[2]))
    elif a and a[0] == "pad":
        cmd_pad(a[1])
    elif a and a[0] == "art":
        cmd_art(a[1], {int(x) for x in a[2:]} or None)
    else:
        print(__doc__)
