#!/usr/bin/env python3
r"""hwdd_paint.py - the hwdd cloverleaf as an hwpaint scene: mockup previews now, piece art later (task hwdd, 2026-10-18).

Geometry from hwdd.py (one definition), painter = hwcore's hwpaint.py (copied verbatim, never edited here).

Scene, per parity ('c' = O on a cell centre, 'h' = on a corner), cells relative to hwdd.Geo's frame:
  * the two diagonal highways as hwpaint.highway_diag (W_DIAG 0.63 carriageways read from the stock bands), with
    parapet gaps where a ramp joins (joins(): spans from the geometry, mirrored onto the far carriageway);
  * A rises H -> H_HIGH and B dips H -> H_LOW over 0.8..SLOPE_END (1.6) cells of O along the band (the stock X's decks), A
    on a slab over B for |along| <= 0.8;
  * the 8 ramps (hwdd.ramps_q0, hwx's geometry turned 45 degrees) as one-lane slab decks on pillars at H, RAMP_W_HWX
    wide (hwx's W 0.31 x 2), clipped to outside the bands so they leave the carriageway at its edge.
Preview: painted cells = what the cloverleaf writes; the plain bands around and past them are STOCK pieces (extra
cells), so the picture shows the real seams.

  py -3.12 hwdd_paint.py mockup OUT.png [--art DIR] [--zooms 4,3] [--rots 0,1] [--par c,h]
  py -3.12 hwdd_paint.py time                       one cell render timing
  py -3.12 hwdd_paint.py build [PACK] [--only IDS] [--lanes-only]   the package: art, lanes (curves 23000..), manifest
"""
import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import hwdd  # noqa: E402
import hwpaint as HP  # noqa: E402
from netmod import netart as NA  # noqa: E402

SQ2 = math.sqrt(2.0)
SLAB_HALF = hwdd.SLAB_HALF       # A's slab over B, along the band from O
SLOPE_END = hwdd.SLOPE_END       # deck rise / dip finished this far from O (the loops join at 1.63..2.13)
RAMP_W_HWX = 2 * hwdd.RAMP_HALF  # 0.62 = hwpaint RAMP_W (program call 2026-10-18; hwx W 0.31)
PILLAR_STEP = 1.0                # cells of ramp between pillars


def _world(o, pq):
    return hwdd.to_xz(pq[0], pq[1], o)


def _ramp_path(o, segs, k):
    """plan-frame primitives (hwdd.ramps_q0_segs), turned k quarters, -> hwpaint Path of Lines and Arcs in the world.
    The (u, w) -> world map is a rotation (det +1), so an arc keeps its sweep sign; its world start angle is read off
    the mapped start point."""
    out = []
    for sg in segs:
        if sg[0] == "line":
            a = _world(o, hwdd.rot_pq(sg[1], k))
            b = _world(o, hwdd.rot_pq(sg[2], k))
            if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
                out.append(HP.Line(a, b))
        else:
            _, c, r, a0, a1 = sg
            # the arc's (u, w)-frame start point: c was already turned to (P, Q); rebuild it in (u, w): u = -Q, w = -P
            cu, cw = -c[1], -c[0]
            su, sw = cu + r * math.cos(math.radians(a0)), cw + r * math.sin(math.radians(a0))
            spq = (-sw, -su)
            cwld = _world(o, hwdd.rot_pq(c, k))
            swld = _world(o, hwdd.rot_pq(spq, k))
            th0 = math.atan2(swld[1] - cwld[1], swld[0] - cwld[0])
            out.append(HP.Arc(cwld, r, th0, math.radians(a1 - a0)))
    return HP.Path(out)


def _bbox(deck, pad):
    xs, zs = [], []
    n = max(2, int(deck.path.length * 8) + 1)
    for i in range(n):
        p, _ = deck.path.at(deck.path.length * i / (n - 1))
        xs.append(p[0])
        zs.append(p[1])
    h = deck.w / 2 + pad
    return min(xs) - h, min(zs) - h, max(xs) + h, max(zs) + h


def _outside_bands(o):
    def clip(wx, wz):
        dx, dz = wx - o[0], wz - o[1]
        p, q = (dz - dx) / SQ2, (dx + dz) / SQ2
        return (np.abs(p) > hwdd.DECK_HALF - 0.01) & (np.abs(q) > hwdd.DECK_HALF - 0.01)
    return clip


def _spans(vals, step):
    """sorted arc lengths sampled every `step` -> [(s0, s1)] runs"""
    out = []
    for v in sorted(vals):
        if out and v - out[-1][1] <= 1.5 * step:
            out[-1][1] = v
        else:
            out.append([v, v])
    return [(a, b) for a, b in out]


def _union(spans):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def joins(hw_path, ramps, step=0.02, pad=0.04):
    """where each ramp deck reaches over the carriageway edge of `hw_path` (a highway_diag median): -> (gaps on the
    highway's right-hand deck in its s, {ramp name: [(s0, s1, side)]} on the ramp). The left-hand carriageway's joins
    are the right-hand ones turned a half turn about O (the cloverleaf's symmetry), which is how highway_diag mirrors
    the gap list onto the left deck; checked here (mismatch -> SystemExit)."""
    reach = hwdd.DECK_HALF + hwdd.RAMP_HALF
    right, left, on_ramp = [], [], {}
    Lh = hw_path.length
    for name, rp, outer in ramps:
        pts = {}
        n = int(rp.length / step)
        for i in range(n + 1):
            sr = rp.length * i / n
            (x, z), _ = rp.at(sr)
            sh, t = hw_path.project(np.array([x]), np.array([z]))
            sh, t = float(sh[0]), float(t[0])
            if not (0.0 < sh < Lh) or abs(t) - hwdd.RAMP_HALF >= hwdd.DECK_HALF:
                continue
            # which side of the ramp faces the highway median: v = median point - ramp point = -t * (left normal)
            dh = hw_path.at(sh)[1]
            v = (t * dh[1], -t * dh[0])
            _, dr = rp.at(sr)
            face = "left" if v[0] * -dr[1] + v[1] * dr[0] > 0 else "right"
            pts.setdefault((t < 0, face), []).append((sr, sh))
        for (is_right, face), v in pts.items():
            for a, b in _spans([sh for _, sh in v], step * 2):
                (right if is_right else left).append((max(0.0, a - pad), min(Lh, b + pad)))
            side = "outer" if face == outer else "inner"
            for a, b in _spans([sr for sr, _ in v], step):
                on_ramp.setdefault(name, []).append((max(0.0, a - pad), min(rp.length, b + pad), side))
    right, left = _union(right), _union(left)
    on_ramp = {k: [(a, b, sd) for sd in ("outer", "inner") for a, b in _union([(a, b) for a, b, x in v if x == sd])]
               for k, v in on_ramp.items()}
    mirrored = sorted((round(Lh - b, 2), round(Lh - a, 2)) for a, b in right)
    if sorted((round(a, 2), round(b, 2)) for a, b in left) != mirrored:
        raise SystemExit("left joins are not the right ones turned: %s vs %s" % (sorted(left), mirrored))
    return sorted(right), on_ramp


def scene(g, flyover=False):
    """the cloverleaf (or, flyover=True, the two highways and the crossing only) of parity g as an hwpaint Scene"""
    o = g.o
    L = g.ext + 3.0
    clip = _outside_bands(o)
    segs = hwdd.ramps_q0_segs()
    ramps = []
    for k, qn in enumerate(["NE", "SE", "SW", "NW"]):
        for kind in ("loop", "outer"):
            # path = direction of travel, outer parapet on the driver's right (hwlanes drives "right" decks along
            # their path): the loop's parapet is on its inside, as stock ramp curve 15127
            if not flyover:
                ramps.append((kind + qn, _ramp_path(o, segs[kind], k), "right"))
    # A: direction (1, 1)/sqrt2 through O, s = L at O, over a slab; B: direction (1, -1)/sqrt2, dips under it.
    # highway_diag: right-hand carriageway runs along the path (traffic keeps right, as the stock lanes measured)
    pA = HP.Path.line((o[0] - L / SQ2, o[1] - L / SQ2), (o[0] + L / SQ2, o[1] + L / SQ2))
    pB = HP.Path.line((o[0] - L / SQ2, o[1] + L / SQ2), (o[0] + L / SQ2, o[1] - L / SQ2))
    hA = lambda s: np.minimum(HP.ramp(HP.H, HP.H_HIGH, L - SLOPE_END, L - SLAB_HALF)(s),       # noqa: E731
                              HP.ramp(HP.H_HIGH, HP.H, L + SLAB_HALF, L + SLOPE_END)(s))
    hB = lambda s: np.maximum(HP.ramp(HP.H, HP.H_LOW, L - SLOPE_END, L - SLAB_HALF)(s),        # noqa: E731
                              HP.ramp(HP.H_LOW, HP.H, L + SLAB_HALF, L + SLOPE_END)(s))
    gA, rgA = joins(pA, ramps) if ramps else ([], {})
    gB, rgB = joins(pB, ramps) if ramps else ([], {})
    decks = HP.highway_diag(pA, height=hA, slab=[(L - SLAB_HALF, L + SLAB_HALF)], gaps=gA)
    decks += HP.highway_diag(pB, height=hB, gaps=gB)
    for name, path, outer in ramps:
        piers = []
        n = max(1, int(path.length / PILLAR_STEP))
        for i in range(n):
            pt, _ = path.at(path.length * (i + 0.5) / n)
            dx, dz = pt[0] - o[0], pt[1] - o[1]
            if min(abs(dz - dx), abs(dx + dz)) / SQ2 > hwdd.DECK_HALF + 0.35:
                piers.append(pt)
        decks.append(HP.ramp_deck(path, outer=outer, width=RAMP_W_HWX, height=HP.H, support="slab",
                                  pillars=piers, clip=clip, ends=(False, False), name=name,
                                  gaps=rgA.get(name, []) + rgB.get(name, [])))
    sc = HP.Scene(decks)
    sc.joins = {"A": gA, "B": gB, "ramps": {k: rgA.get(k, []) + rgB.get(k, []) for k, _, _ in ramps}}
    return sc


def stock_band(g, c):
    """the stock piece (id, state) of a plain band cell, from its position across the band (measured 2026-10-18)"""
    o = g.o
    cA = (o[0] - o[1])                    # x - z of the A centreline
    cB = (o[0] + o[1]) - 1.0              # x + z of the cell index on B's middle cells
    dA = (c[0] - c[1]) - cA
    dB = (c[0] + c[1]) - cB
    if abs(dA) <= 1 and dA == int(dA):
        return {-1: (11223, 2), 0: (11224, 0), 1: (11223, 0)}[int(dA)]
    if abs(dB) <= 1 and dB == int(dB):
        return {-1: (15052, 2), 0: (15106, 0), 1: (15052, 0)}[int(dB)]
    return None


def local(sc, cell, pad=0.6):
    """the scene cut down to the decks whose footprint comes near `cell` (a cell's rays only meet decks over its
    column; the full scene makes every ray test all 12 decks)"""
    if not hasattr(sc, "_bb"):
        sc._bb = [_bbox(d, 0.0) for d in sc.decks]
    X, Z = cell
    keep = [d for d, (x0, z0, x1, z1) in zip(sc.decks, sc._bb)
            if x0 <= X + 1 + pad and x1 >= X - pad and z0 <= Z + 1 + pad and z1 >= Z - pad]
    return HP.Scene(keep)


def paint_frames(sc, cell, out_dir, zoom, rots):
    """hwpaint.paint_cell for selected views only (anchors.json merged)"""
    import json
    sc = local(sc, cell)
    os.makedirs(out_dir, exist_ok=True)
    ap = os.path.join(out_dir, "anchors.json")
    anchors = json.load(open(ap)) if os.path.exists(ap) else {}
    for r in rots:
        name = NA.frame_name(zoom, r)
        if os.path.exists(os.path.join(out_dir, name)) and name in anchors:
            continue
        im, LT = HP.render_cell(sc, cell, zoom, r)
        im, LT = HP._crop(im, LT)
        im.save(os.path.join(out_dir, name))
        anchors[name] = [int(LT[0]), int(LT[1])]
    json.dump(anchors, open(ap, "w"), indent=1)


def preview(g, sc, art, zoom, rot, margin=4):
    W = g.written()
    layout = []
    for c in sorted(W):
        d = os.path.join(art, "%d_%d" % c)
        paint_frames(sc, c, d, zoom, [rot])
        layout.append({"at": [-c[0], c[1]], "dir": d, "slot": 0})
    xs = [c[0] for c in W]
    zs = [c[1] for c in W]
    for x in range(min(xs) - margin, max(xs) + margin + 1):
        for z in range(min(zs) - margin, max(zs) + margin + 1):
            if (x, z) in W:
                continue
            sb = stock_band(g, (x, z))
            if sb:
                layout.append({"at": [-x, z], "piece": sb[0], "slot": sb[1]})
    return NA.preview({"cells": layout}, None, zooms=[zoom], rots=[rot])[(zoom, rot)]


def cmd_mockup(a):
    zooms = [int(v) for v in a.zooms.split(",")]
    rots = [int(v) for v in a.rots.split(",")]
    pars = a.par.split(",")
    shots = []
    for par in pars:
        g = hwdd.Geo(par)
        sc = scene(g)
        art = os.path.join(a.art, par)
        for z in zooms:
            for r in rots:
                t = time.time()
                im = preview(g, sc, art, z, r)
                print(par, "zoom", z, "view", r, im.size, "%.0f s" % (time.time() - t), flush=True)
                im.save(os.path.join(a.art, "mock_%s_z%d_r%d.png" % (par, z, r)))
                shots.append(((par, z, r), im))
    sheet(shots, a.out)


def sheet(shots, out):
    F = ImageFont.truetype("arialbd.ttf", 16)
    cols = {}
    for (par, z, r), im in shots:
        cols.setdefault((z, r), []).append(((par, z, r), im))
    rows = []
    for (par, z, r), im in shots:
        pass
    # layout: one row per (zoom, view), the parities side by side; zoom-3 shots shown at 2x
    keys = sorted({(z, r) for (_, z, r), _ in shots}, key=lambda k: (-k[0], k[1]))
    pars = sorted({p for (p, _, _), _ in shots})
    cells = {(p, z, r): im for (p, z, r), im in shots}
    blocks = []
    for (z, r) in keys:
        row = []
        for p in pars:
            im = cells.get((p, z, r))
            if im is None:
                continue
            im = im.convert("RGBA")
            bb = im.getbbox()
            if bb:
                im = im.crop(bb)
            row.append(((p, z, r), im))
        blocks.append(row)
    Wd = max(sum(im.width + 20 for _, im in row) for row in blocks) + 20
    Hd = sum(max(im.height for _, im in row) + 40 for row in blocks) + 60
    out_im = Image.new("RGBA", (Wd, Hd), (24, 26, 30, 255))
    d = ImageDraw.Draw(out_im)
    d.text((20, 14), "hwdd mockup: diagonal x diagonal highway cloverleaf (hwpaint scene, plain bands = stock pieces)",
           font=F, fill=(240, 240, 240, 255))
    y = 50
    for row in blocks:
        x = 20
        for (p, z, r), im in row:
            d.text((x, y), "%s, zoom %d, view %d" % ("O on a cell centre" if p == "c" else "O on a cell corner", z, r),
                   font=F, fill=(230, 230, 230, 255))
            out_im.alpha_composite(im, (x, y + 24))
            x += im.width + 20
        y += max(im.height for _, im in row) + 40
    out_im.save(out)
    print(out, out_im.size)


PACK = os.path.join(HERE, "examples", "highway_dd_cloverleaf")
MATS = {}
HWYS, SAVE_AT = False, {}
# what a ramp piece on land saves as, per piece state (no "empty" save exists): the stock arcs only occur at states 0
# and 2 in the shipped cities (hwcore), and 15128.0 is 15127 turned once (turn x+ -> z+ becomes z+ -> x-), so a piece at
# state s saves as the arc turned s times
LAND_SAVE = {0: (15127, 0), 1: (15128, 0), 2: (15127, 2), 3: (15128, 2)}
SHAPE0, SHAPE1 = 23000, 23299          # this stream's lane curve shapes (protocol section 5)


def pieces():
    """-> [(id, par, flyover, rep cell, states, base, land)] over both parities and both modes (ids from plan_all)"""
    T = hwdd.plan_all()
    out = []
    for par in "ch":
        g = T[par]["geo"]
        for fly, ids in ((False, T[par]["cl"]), (True, T[par]["fl"])):
            by = {}
            for c, (pid, st) in ids.items():
                by.setdefault(pid, []).append((c, st))
            for pid, mem in sorted(by.items()):
                rep = min(c for c, st in mem if st == 0)
                land = g.role(rep) == "R" and not fly
                base = hwdd.LAND_BASE if land else g.stock_piece(rep)[0]
                out.append((pid, par, fly, rep, sorted({st for _, st in mem}), base, land))
    return sorted(out)


def build_lanes(sel=None):
    """lane specs for every piece, curves de-duplicated across pieces (same points -> same shape) -> {id: spec}"""
    import hwlanes as HL
    specs, shapes = {}, {}
    nxt = SHAPE0
    scenes = {}
    global MATS
    MATS = {(par, fly): hwdd.matrices(hwdd.Geo(par), fly) for par in "ch" for fly in (False, True)}
    for pid, par, fly, rep, states, base, land in pieces():
        if sel and pid not in sel:
            continue
        key = (par, fly)
        if key not in scenes:
            scenes[key] = scene(hwdd.Geo(par), flyover=fly)
        loc = local(scenes[key], rep)
        sp, _ = HL.build_cells(loc.decks, [rep], 900000, {rep: pid}, states=tuple(states))
        spec = sp.get(tuple(rep))
        if spec is None:                                  # no lane crosses the cell (a deck edge): matrix only
            spec = {"piece": pid, "states": list(states), "flag": 0,
                    "vehicle": {"class": "car", "speed": HL.HW_SPEED, "lanes": []}, "curves": []}
        # the turn matrix: hwdd's router flows (sides only; the corner parity's B takes other staircases through the
        # crossing so A and B never share an entry), not "auto" from the true-geometry lanes
        low = MATS[(par, fly)].get(tuple(rep), [])
        S = ["x-", "z-", "x+", "z+"]
        spec["connects"] = {"road": {"low": [[S[e], S[l]] for e, l in low], "high": [[S[l], S[e]] for e, l in low]}}
        remap, curves = {}, []
        for cv in spec["curves"]:
            t = tuple(tuple(p) for p in cv["pts"])
            if t not in shapes:
                shapes[t] = nxt
                nxt += 1
                curves.append({"shape": shapes[t], "pts": cv["pts"]})
            remap[cv["shape"]] = shapes[t]
        for ln in spec["vehicle"]["lanes"]:
            ln["path"] = remap[ln["path"] // 256] * 256 + ln["path"] % 256
        spec["curves"] = curves                     # only the curves this spec introduces; the rest are defined once
        specs[pid] = spec
    if nxt - 1 > SHAPE1:
        raise SystemExit("curve shapes run past %d: %d" % (SHAPE1, nxt - 1))
    print("lanes: %d pieces, %d curve shapes (%d..%d)" % (len(specs), nxt - SHAPE0, SHAPE0, nxt - 1))
    return specs


def cmd_build(a):
    """art (all zooms and views) + lane specs + manifest of the package"""
    import json
    pack = a.pack
    plist = pieces()
    sel = None if not a.only else {int(v) for v in a.only.split(",")}
    scenes = {}
    if not a.lanes_only:
        for i, (pid, par, fly, rep, states, base, land) in enumerate(plist):
            if sel and pid not in sel:
                continue
            key = (par, fly)
            if key not in scenes:
                scenes[key] = scene(hwdd.Geo(par), flyover=fly)
            t = time.time()
            HP.paint_cell(local(scenes[key], rep), rep, os.path.join(pack, "art", str(pid)))
            print("art %d/%d: %d (%s %s, cell %s) %.0f s" % (i + 1, len(plist), pid, par, "flyover" if fly else
                                                              "cloverleaf", rep, time.time() - t), flush=True)
    specs = build_lanes()
    os.makedirs(pack, exist_ok=True)
    for pid, spec in specs.items():
        with open(os.path.join(pack, "hwdd_%d.lanes.json" % pid), "w", encoding="utf-8") as f:
            json.dump(spec, f)
    game = json.load(open(os.path.join(HERE, "examples", "highway_core", "manifest.json")))["game"]
    var, lines = [], []
    # hwcore's `hwys` table (sc3netmod_hwy.c): only when the merged base understands it
    hwy_c = open(os.path.join(HERE, "..", "..", "harness", "src", "sc3netmod_hwy.c"), encoding="latin-1").read()
    global HWYS, SAVE_AT
    HWYS = "hwys" in hwy_c
    SAVE_AT = {}
    T = hwdd.plan_all()
    for par in "ch":
        for kind in ("clover", "fly"):
            for (dx, dz, role, pid_, st, base_, bst, land_) in T[par][kind]:
                if pid_ and not land_:
                    SAVE_AT[(pid_, st)] = bst
    for pid, par, fly, rep, states, base, land in plist:
        kind = "flyover" if fly else ("ramp" if land else "cloverleaf")
        var.append({"id": pid, "base": base, "network": "HWAY",
                    "name": {"*": "Highway interchange (diagonal %s)" % kind},
                    # frame table of stock ramp curve 15127 (class 1650, flags 0x440) + ground_under: terrain shows
                    # under transparent art in every view (hwcore, HWY_BASE.md); 73's table loses it in some views
                    "art": {"from": 15127, "png_dir": "art/%d" % pid, "ground_under": True},
                    "trblkatt": "copy_base"})
        lines.append("hwyp %d %d" % (pid, 1 if land else 0))
        if HWYS:
            sv = []
            for st in range(4):
                if land:                            # a ramp on land saves as a stock one-lane ramp arc (Protected,
                    sv += list(LAND_SAVE[st])       # partial-cell slab): no mod -> ramp fragments, not 15099 blocks
                else:                               # on the highway: the stock piece the cell held, at its state
                    c = SAVE_AT.get((pid, st))
                    sv += [base, c if c is not None else st]
            lines.append("hwys %d " % pid + " ".join(str(v) for v in sv))
    man = {"netpack": 1, "name": "highway_dd_cloverleaf", "version": "1.0.0", "author": "sc3kre",
           "description": "Task hwdd: two diagonal highways of the two families that cross become a cloverleaf "
                          "turned 45 degrees (A over B, four loops, four outer ramps), or a flyover when the "
                          "quadrants are not free. Placed by sc3netmod's HWDD block (sc3netmod_hwdd.c).",
           "game": game, "variants": var,
           "lanes": [{"piece": pid, "spec": "hwdd_%d.lanes.json" % pid} for pid in sorted(specs)],
           "highway_lines": lines}
    with open(os.path.join(pack, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    print(os.path.join(pack, "manifest.json"), len(var), "variants")


def cmd_time(a):
    g = hwdd.Geo("c")
    sc = scene(g)
    c = sorted(g.written())[0]
    for z in (3, 4):
        t = time.time()
        HP.render_cell(local(sc, c), c, z, 0)
        print("cell", c, "zoom", z, "%.1f s" % (time.time() - t))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("mockup")
    p.add_argument("out")
    p.add_argument("--art", default=os.path.join(HERE, "..", "..", "..", "verify", "hwdd", "art"))
    p.add_argument("--zooms", default="4,3")
    p.add_argument("--rots", default="0,1")
    p.add_argument("--par", default="c,h")
    sub.add_parser("time")
    p = sub.add_parser("build")
    p.add_argument("pack", nargs="?", default=PACK)
    p.add_argument("--only", default="")
    p.add_argument("--lanes-only", action="store_true")
    a = ap.parse_args(argv)
    {"mockup": cmd_mockup, "time": cmd_time, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    main()
