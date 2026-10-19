#!/usr/bin/env python3
r"""hwcap_art.py - task hwcap (2026-10-18): the capped joins' end face taken from the stock cap itself.

  py -3.12 netmod/hwcap_art.py compose PKG_DIR        after `hwdx_paint.py art PKG_DIR 21532 ...`, before `pad`
  py -3.12 netmod/hwcap_art.py sheet PKG_DIR OUT.png  stock cap / capped join / plain join, zoom 3 and 4, views 0..3

A capped join (hwdx.capped_list) is painted by hwdx_paint.py from the hwdx scene with the diagonal ending on the cap
line; hwpaint draws that end with its generic end face, while the stock caps 14999 / 15059 have their own (a facade
with columns, seen in view slot 2 of 14999.0). The piece sits at the stock cap's own state, so slot r of the piece and
slot r of its base show the same cell from the same side: per pixel, a point that lies past the cap line at deck
height is taken from the stock cap frame (the cap line is the cell's diagonal across the band: x + z = 1 for 14999,
x = z for 15059; which side holds the deck is read from the stock frames), every other pixel from the painted frame. The painted frames are kept in
PKG_DIR/art_painted/<id>/ (gitignored, as art/) so compose can be re-run.
Pixel -> cell point: hwpaint._rays (registration point = the cell's left ground vertex, height in zoom-3 px).
"""
import json
import os
import shutil
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from netmod import netart as NA  # noqa: E402
from netmod import hwpaint as HP  # noqa: E402
from netmod import hwdx as H  # noqa: E402


def cell_points(z, r, w, h, L, T, e=HP.H):
    """cell-local (fx, fz) of every pixel of a w x h frame with registration point (L, T), at height e"""
    W = NA.TILE_W[z]
    xx, yy = np.meshgrid(np.arange(w) + 0.5 - L, np.arange(h) + 0.5 - T)
    sp = 2.0 * xx / W
    d = 4.0 * yy / W + e / 16.0
    u, v = (sp - d) / 2.0, (sp + d) / 2.0
    for _ in range((-r) % 4):
        u, v = v, 1.0 - u
    return 1.0 - u, v


def cap_line(base, fx, fz):
    """signed distance-like value of a cell point from the cap line: 14999 (x - z band) ends on x + z = 1, 15059
    (x + z band) on x = z"""
    return fx + fz - 1.0 if base == 14999 else fx - fz


def deck_side(stock, base):
    """+1 when the stock cap's deck lies where cap_line > 0, -1 where < 0 (read from its zoom-3 frames)"""
    n = 0
    for r in range(4):
        im, (L, T) = stock[(3, r)]
        a = np.array(im)[:, :, 3] > 0
        fx, fz = cell_points(3, r, im.width, im.height, L, T)
        g = cap_line(base, fx, fz)[a]
        n += int((g > 0).sum()) - int((g < 0).sum())
    return 1 if n > 0 else -1


def compose_one(painted, stock, z, r, side, base):
    pim, (pL, pT) = painted[(z, r)]
    sim, (sL, sT) = stock[(z, r)]
    left, top = min(-pL, -sL), min(-pT, -sT)
    right, bottom = max(pim.width - pL, sim.width - sL), max(pim.height - pT, sim.height - sT)
    w, h = right - left, bottom - top
    L, T = -left, -top
    P = np.zeros((h, w, 4), dtype=np.uint8)
    S = np.zeros((h, w, 4), dtype=np.uint8)
    P[T - pT:T - pT + pim.height, L - pL:L - pL + pim.width] = np.array(pim)
    S[T - sT:T - sT + sim.height, L - sL:L - sL + sim.width] = np.array(sim)
    fx, fz = cell_points(z, r, w, h, L, T)
    past = cap_line(base, fx, fz) * side < 0
    out = np.where(past[:, :, None], S, P)
    im = Image.fromarray(out, "RGBA")
    bb = im.getbbox()
    if not bb:
        return im.crop((0, 0, 1, 1)), (L, T)
    return im.crop(bb), (L - bb[0], T - bb[1])


def cmd_compose(pkg):
    for cp in H.capped_list():
        d = os.path.join(pkg, "art", str(cp["id"]))
        keep = os.path.join(pkg, "art_painted", str(cp["id"]))
        if not os.path.isdir(keep):
            shutil.copytree(d, keep)
        painted = NA.load_dir(keep)
        stock = NA.stock_frames(cp["base"])
        side = deck_side(stock, cp["base"])
        anchors = {}
        for z in range(NA.ZOOMS):
            for r in range(NA.ROTS):
                im, LT = compose_one(painted, stock, z, r, side, cp["base"])
                name = NA.frame_name(z, r)
                im.save(os.path.join(d, name))
                anchors[name] = [int(LT[0]), int(LT[1])]
        with open(os.path.join(d, "anchors.json"), "w", encoding="utf-8") as fh:
            json.dump(anchors, fh, indent=1)
        print("capped join %d: end face from stock %d (deck side %+d), %d frames" % (cp["id"], cp["base"], side,
                                                                                    len(anchors)))


def cmd_sheet(pkg, out):
    rows = []
    for cp in H.capped_list():
        join = H.ids()[0][(cp["cls"], cp["flavour"])]
        for label, fr in (("stock %d" % cp["base"], NA.stock_frames(cp["base"])),
                          ("capped %d" % cp["id"], NA.load_dir(os.path.join(pkg, "art", str(cp["id"])))),
                          ("join %d" % join, NA.load_dir(os.path.join(pkg, "art", str(join))))):
            rows.append((label, fr))
    zs = (3, 4)
    cw = 2 * NA.TILE_W[4] + 20
    ch = 2 * NA.TILE_W[4]
    sheet = Image.new("RGBA", (cw * 4 * len(zs) + 140, ch * len(rows)), (54, 88, 54, 255))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(sheet)
    for y, (label, fr) in enumerate(rows):
        dr.text((4, y * ch + 4), label, fill=(255, 255, 255, 255))
        for zi, z in enumerate(zs):
            for r in range(4):
                if (z, r) not in fr:
                    continue
                im, (L, T) = fr[(z, r)]
                if not (L or T) and (z, r) in NA.stock_frames(15127):
                    L, T = NA.stock_frames(15127)[(z, r)][1]
                ox = 140 + (zi * 4 + r) * cw + 10
                oy = y * ch + ch // 2
                sheet.alpha_composite(im, (int(ox + NA.TILE_W[z] // 2 - L), int(oy - T)))
    sheet.save(out)
    print("wrote", out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "compose":
        cmd_compose(a[1])
    elif a and a[0] == "sheet":
        cmd_sheet(a[1], a[2])
    else:
        print(__doc__)
