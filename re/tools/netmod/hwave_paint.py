#!/usr/bin/env python3
r"""hwave_paint.py - art of the highway <-> avenue transition (task hwave, highway program wave 2, 2026-10-19).

Four pieces, painted for state 0 = the avenue at +z of the highway (world frame below; the block turns them):
    21601 (46,29) entry carriageway, deck H -> H/2      21600 (47,29) exit carriageway, deck H -> H/2
    21603 (46,30) entry, H/2 -> ground (road side)      21602 (47,30) exit, H/2 -> ground (road side)
Highway rows z <= 28 (73.2 at x 46, 73.0 at x 47), avenue rows z >= 31 (11204.1 / 11204.3, avenue_markings reskin).

  py -3.12 hwave_paint.py mockup OUT.png [--zooms 3,4] [--rots 0,1]
  py -3.12 hwave_paint.py mockup-diag OUT.png [--zooms 3,4] [--rots 0,1]     the diagonal set 21604..21609 (phase 2)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from netmod import hwpaint as HP  # noqa: E402
from netmod import netart as NA  # noqa: E402

AVE_ART = os.path.join(HERE, "examples", "avenue_markings", "art")
CELLS = {(47, 29): 21600, (46, 29): 21601, (47, 30): 21602, (46, 30): 21603}
Z_TOP, Z_GROUND = 29.0, 31.0          # the deck leaves H at the near edge of the cap row, lands at the avenue's edge


MEDIAN_HALF = 0.11      # half the avenue median (grass + curb) at the cell line, 11204 zoom 4 frames
NOSE = (30.6, 31.0)     # world z where the median nose starts (a point) and reaches MEDIAN_HALF


def nose_half(wz):
    """half-width of the median nose cut into the ground row (0 before NOSE[0], MEDIAN_HALF at the avenue edge)"""
    t = np.clip((np.asarray(wz, dtype=float) - NOSE[0]) / (NOSE[1] - NOSE[0]), 0.0, 1.0)
    return MEDIAN_HALF * np.sqrt(t)


def keep(wx, wz):
    """deck clip: everything but the median nose (the terrain shows there, as the avenue's median grass)"""
    return np.abs(np.asarray(wx, dtype=float) - 47.0) >= nose_half(wz)


def scene():
    path = HP.Path.line((47.0, 24.0), (47.0, Z_GROUND))
    L = path.length
    return HP.Scene(HP.highway(path, height=HP.ramp(HP.H, 0.0, Z_TOP - 24.0, L, ease=True), clip=keep, ends=(False, False)))


def context(z0=26, z1=33):
    """stock / reskinned neighbours for the preview"""
    out = []
    for z in range(z0, int(Z_TOP)):
        out += [{"at": [-46, z], "piece": 73, "slot": 2}, {"at": [-47, z], "piece": 73, "slot": 0}]
    for z in range(int(Z_GROUND), z1 + 1):
        out += [{"at": [-46, z], "dir": os.path.join(AVE_ART, "11204"), "slot": 1},
                {"at": [-47, z], "dir": os.path.join(AVE_ART, "11204"), "slot": 3}]
    return out


def cmd_mockup(a):
    sc = scene()
    root = os.path.join(a.work, "cells")
    zooms = [int(t) for t in a.zooms.split(",")]
    rots = [int(t) for t in a.rots.split(",")]
    shots = []
    HP.paint_cells(sc, list(CELLS), root, zooms=sorted(set(zooms)))    # one anchors.json per cell for every zoom
    for z in zooms:
        for r in rots:
            im = HP.preview_cells(sc, list(CELLS), z, r, root, extra=context(), paint=False)
            shots.append(((z, r), im))
    rowsz = {z: [im for (zz, _), im in shots if zz == z] for z in zooms}
    w = max(sum(im.size[0] for im in row) for row in rowsz.values())
    h = sum(max(im.size[1] for im in row) + 24 for row in rowsz.values())
    sheet = Image.new("RGB", (w, h), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    y = 0
    for z in zooms:
        x = 0
        for (zz, r), im in [(k, im) for k, im in shots if k[0] == z]:
            sheet.paste(im.convert("RGB"), (x, y + 24))
            d.text((x + 6, y + 4), "zoom %d view %d" % (zz, r), fill=(255, 255, 255))
            x += im.size[0]
        y += max(im.size[1] for im in rowsz[z]) + 24
    sheet.save(a.out)
    print(a.out)


# ================================================================================================ diagonal (phase 2)
# State 0 = the x - z family, avenue toward +x +z. World frame: band middle line x - z = 0, the highway's cap in cell
# (10, 10); a = x + z runs along the band (a cell spans a in [X + Z, X + Z + 2]). Roles by j = X + Z - 20 and side
# p = X - Z (-1 low, 0 middle, +1 high): j-1 high 21604 / low 21605 (highway, exit / entry), j0 21606 (the cap),
# j+1 high 21607 / low 21608 (the far one empty in stock), j+2 middle 21609 (road side). The deck is at H up to a = 20,
# eased to the ground at a = 23, where the avenue's j+3 cells (DAV 20505) begin.
DAV_ART = os.path.join(HERE, "examples", "diagonal_avenue", "art")
DCELLS = {(10, 9): 21604, (9, 10): 21605, (10, 10): 21606, (11, 10): 21607, (10, 11): 21608, (11, 11): 21609}
D_TOP, D_LAND = 20.0, 23.0           # a where the deck leaves H / reaches the ground
D_NOSE = (22.0, 23.0)                # a where the median nose starts (a point) and reaches D_MEDIAN_HALF
D_MEDIAN_HALF = 0.19                 # |x - z| of DAV's median grass at the cell diagonal (20500 frames, zoom 4)
D_MIDDLE = (11, 11)                  # the one cell that reaches past the landing: the avenue's 20500 art there
SQ2 = 2 ** 0.5


def d_nose(wx, wz):
    a = np.asarray(wx, dtype=float) + np.asarray(wz, dtype=float)
    t = np.clip((a - D_NOSE[0]) / (D_NOSE[1] - D_NOSE[0]), 0.0, 1.0)
    return np.abs(np.asarray(wx, dtype=float) - np.asarray(wz, dtype=float)) < D_MEDIAN_HALF * np.sqrt(t)


def d_keep(wx, wz):
    return ~d_nose(wx, wz)


def diag_scene():
    path = HP.Path.line((4.0, 4.0), (D_LAND / 2.0, D_LAND / 2.0))
    s_top = (D_TOP - 8.0) / SQ2
    return HP.Scene(HP.highway_diag(path, height=HP.ramp(HP.H, 0.0, s_top, path.length, ease=True), clip=d_keep,
                                    ends=(False, False)))


_DAV = {}


def dav_sample(pid, state, z, r, lx, lz):
    """colour of DAV piece `pid` (its painted frames) at lane-frame point (lx, lz) on the ground, view r"""
    if pid not in _DAV:
        _DAV[pid] = {k: (np.asarray(im.convert("RGBA")), LT) for k, (im, LT) in
                     NA.load_dir(os.path.join(DAV_ART, str(pid))).items()}
    a, (L, T) = _DAV[pid][(z, (state + r) & 3)]
    u, v = NA.rot_uv(1.0 - lx / 256.0, lz / 256.0, r)
    X, Y = NA.project(z, u, v, 0.0)
    X, Y = int(np.floor(X + L)), int(np.floor(Y + T))
    if 0 <= X < a.shape[1] and 0 <= Y < a.shape[0]:
        return tuple(int(c) for c in a[Y, X])
    return (0, 0, 0, 0)


D_ROLE = {(11, 10): (20505, 0), (10, 11): (20505, 2), (11, 11): (20500, 0)}   # the DAV piece each cell would be
D_SIDE = (20.6, 22.2)                # a where the avenue's sidewalks start beside the deck (none) / are full width
W_AVE = 1.0 / SQ2                    # DAV carriageway (one stock-35 strip) width across, cells


def d_height(q):
    """the deck's height (hwpaint e) at a = x + z: diag_scene's eased ramp"""
    t = min(1.0, max(0.0, (q - D_TOP) / (D_LAND - D_TOP)))
    return HP.H * (1.0 - t * t * (3.0 - 2.0 * t))


def _world(z, r, X0, Z0, px, py, L, T, e):
    u, v = NA.unproject(z, px + 0.5 - L, py + 0.5 - T, e)
    u, v = NA.rot_uv(u, v, -r % 4)
    lx, lz = (1.0 - u) * 256.0, v * 256.0
    return lx, lz, X0 + lx / 256.0, Z0 + lz / 256.0


def diag_render(scene, cell, z, r):
    """the deck (hwpaint); in the three cells next to the avenue the avenue's own DAV frames (the piece the cell would
    hold in a band): past the landing and in the median nose on the ground, and a sidewalk SHOULDER beside the deck at
    the deck's own height, widening from the deck's edge (W_DIAG) to the avenue's (W_AVE) over D_SIDE, so the avenue's
    outer edge grows out of the deck instead of stepping out at the first avenue cell"""
    im, (L, T) = HP.render_cell(scene, cell, z, r)
    role = D_ROLE.get(tuple(cell))
    if role is None:
        return im, (L, T)
    X0, Z0 = cell
    a = np.array(im)
    h, w = a.shape[:2]
    for y in range(h):
        for xx in range(w):
            # 1. the shoulder: the ray's point on the deck-height surface (fixed point over e)
            e = 0.0
            for _ in range(6):
                lx, lz, wx, wz = _world(z, r, X0, Z0, xx, y, L, T, e)
                e = d_height(wx + wz)
            if 0.0 <= lx <= 256.0 and 0.0 <= lz <= 256.0:
                q = wx + wz
                across = abs(wx - wz) / SQ2
                t = min(1.0, max(0.0, (q - D_SIDE[0]) / (D_SIDE[1] - D_SIDE[0])))
                if q >= D_SIDE[0] and HP.W_DIAG - 0.01 <= across <= HP.W_DIAG + (W_AVE - HP.W_DIAG + 0.02) * t:
                    c = dav_sample(role[0], role[1], z, r, min(255.9, max(0.1, lx)), min(255.9, max(0.1, lz)))
                    if c[3]:
                        a[y, xx] = c
                        continue
            # 2. on the ground: past the landing, the median nose
            lx, lz, wx, wz = _world(z, r, X0, Z0, xx, y, L, T, 0.0)
            if not (0.0 <= lx <= 256.0 and 0.0 <= lz <= 256.0):
                continue
            q = wx + wz
            past = q >= D_LAND
            nose = bool(d_nose(wx, wz)) and q >= D_NOSE[0]
            if (a[y, xx, 3] and not past) or not (past or nose):
                continue
            c = dav_sample(role[0], role[1], z, r, min(255.9, max(0.1, lx)), min(255.9, max(0.1, lz)))
            if c[3]:
                a[y, xx] = c
    return Image.fromarray(a, "RGBA"), (L, T)


def diag_paint_cell(scene, cell, out_dir, zooms=range(NA.ZOOMS)):
    os.makedirs(out_dir, exist_ok=True)
    anchors = {}
    for z in zooms:
        for r in range(NA.ROTS):
            im, LT = diag_render(scene, cell, z, r)
            im, LT = HP._crop(im, LT)
            name = NA.frame_name(z, r)
            im.save(os.path.join(out_dir, name))
            anchors[name] = [int(LT[0]), int(LT[1])]
    with open(os.path.join(out_dir, "anchors.json"), "w", encoding="utf-8") as f:
        json.dump(anchors, f, indent=1)
    return anchors


def diag_context(a0=12, a1=30):
    """stock highway band before the transition, DAV's avenue band after it (state 0 frame)"""
    out = []
    for X in range(0, 24):
        for Z in range(0, 24):
            p, a = X - Z, X + Z
            if abs(p) > 1 or (X, Z) in DCELLS or a < a0 or a > a1:
                continue
            if a <= 19:
                out.append({"at": [-X, Z], "piece": 11224 if p == 0 else 11223, "slot": 0 if p >= 0 else 2})
            elif a >= 23:
                pid = 20500 if p == 0 else 20505
                out.append({"at": [-X, Z], "dir": os.path.join(DAV_ART, str(pid)), "slot": 0 if p >= 0 else 2})
    return out


def cmd_mockup_diag(a):
    sc = diag_scene()
    root = os.path.join(a.work, "dcells")
    zooms = [int(t) for t in a.zooms.split(",")]
    rots = [int(t) for t in a.rots.split(",")]
    for c in DCELLS:
        diag_paint_cell(sc, c, os.path.join(root, "%d_%d" % c), zooms=sorted(set(zooms)))
    shots = []
    for z in zooms:
        for r in rots:
            lay = [{"at": [-c[0], c[1]], "dir": os.path.join(root, "%d_%d" % c), "slot": 0} for c in DCELLS]
            im = NA.preview({"cells": lay + diag_context()}, None, zooms=[z], rots=[r])[(z, r)]
            shots.append(((z, r), im))
    rowsz = {z: [im for (zz, _), im in shots if zz == z] for z in zooms}
    w = max(sum(im.size[0] for im in row) for row in rowsz.values())
    h = sum(max(im.size[1] for im in row) + 24 for row in rowsz.values())
    sheet = Image.new("RGB", (w, h), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    y = 0
    for z in zooms:
        x = 0
        for (zz, r), im in [(k, im) for k, im in shots if k[0] == z]:
            sheet.paste(im.convert("RGB"), (x, y + 24))
            d.text((x + 6, y + 4), "zoom %d view %d" % (zz, r), fill=(255, 255, 255))
            x += im.size[0]
        y += max(im.size[1] for im in rowsz[z]) + 24
    sheet.save(a.out)
    print(a.out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hwave_paint.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mockup")
    m.add_argument("out")
    m.add_argument("--zooms", default="3,4")
    m.add_argument("--rots", default="0,1")
    m.add_argument("--work", default=os.path.join(HERE, "..", "..", "..", "verify", "hwave", "art"))
    m = sub.add_parser("mockup-diag")
    m.add_argument("out")
    m.add_argument("--zooms", default="3,4")
    m.add_argument("--rots", default="0,1")
    m.add_argument("--work", default=os.path.join(HERE, "..", "..", "..", "verify", "hwave", "art"))
    a = ap.parse_args(argv)
    return {"mockup": cmd_mockup, "mockup-diag": cmd_mockup_diag}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
