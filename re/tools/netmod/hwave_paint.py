#!/usr/bin/env python3
r"""hwave_paint.py - art of the highway <-> avenue transition (task hwave, highway program wave 2, 2026-10-19).

Four pieces, painted for state 0 = the avenue at +z of the highway (world frame below; the block turns them):
    21601 (46,29) entry carriageway, deck H -> H/2      21600 (47,29) exit carriageway, deck H -> H/2
    21603 (46,30) entry, H/2 -> ground (road side)      21602 (47,30) exit, H/2 -> ground (road side)
Highway rows z <= 28 (73.2 at x 46, 73.0 at x 47), avenue rows z >= 31 (11204.1 / 11204.3, avenue_markings reskin).

  py -3.12 hwave_paint.py mockup OUT.png [--zooms 3,4] [--rots 0,1]
"""
import argparse
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hwave_paint.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mockup")
    m.add_argument("out")
    m.add_argument("--zooms", default="3,4")
    m.add_argument("--rots", default="0,1")
    m.add_argument("--work", default=os.path.join(HERE, "..", "..", "..", "verify", "hwave", "art"))
    a = ap.parse_args(argv)
    return {"mockup": cmd_mockup}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
