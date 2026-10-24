#!/usr/bin/env python3
r"""avflow_sheet.py - owner sheet of the avflow test (task avflow, 2026-10-24).

Top row, whole map, 2 px per cell (x to the right, z down = save coordinates): where the avenue / boulevard cells are
(sc3netmod class grid), the mean monthly published density +0x60 with the blocks off and on (ld_probe.py npz), and
on - off on road cells (blue = less traffic with the blocks on, red = more). Bottom row: the game's own traffic layer
("Capas de la ciudad > Vista de capas > Tráfico"), same camera, blocks off and on (FRAMEDUMP bmp). Text lines from --line.

  py -3.12 avflow_sheet.py --cls class.npy --off off.npz --on on.npz --shot-off off.bmp --shot-on on.bmp
                           --title T [--line "..."]... --out sheet.png
"""
import argparse

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PX = 2


def font(sz):
    for f in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def heat(v, vmax=160.0):
    t = np.clip(v / vmax, 0, 1)
    r = np.clip(3 * t - 1, 0, 1); g = np.clip(3 * t - 0.4, 0, 1) * 0.9 + 0.1 * t; b = np.clip(1.4 - 2 * t, 0, 1) * 0.6 + 0.2
    return (np.stack([r, g, b], -1) * 255).astype(np.uint8)


def panel(rgb):
    im = Image.fromarray(np.transpose(rgb, (1, 0, 2)), "RGB")      # arrays are [x, z]: image rows = z
    return im.resize((im.width * PX, im.height * PX), Image.NEAREST)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cls", required=True)
    ap.add_argument("--off", required=True)
    ap.add_argument("--on", required=True)
    ap.add_argument("--shot-off", required=True)
    ap.add_argument("--shot-on", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--line", action="append", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cls = np.load(a.cls)
    off = np.load(a.off)["grids"].astype(float).mean(0)
    on = np.load(a.on)["grids"].astype(float).mean(0)
    used = (off > 0) | (on > 0) | (cls > 0)
    bg = np.zeros(cls.shape + (3,), np.uint8) + 24
    c = bg.copy(); c[used] = (90, 90, 90); c[cls == 1] = (255, 255, 255); c[cls == 2] = (255, 200, 0)
    ho = bg.copy(); ho[used] = heat(off[used])
    hn = bg.copy(); hn[used] = heat(on[used])
    d = on - off
    t = np.clip(d / 60.0, -1, 1)
    dd = bg.copy()
    dd[used] = np.stack([np.where(t[used] > 0, 255, 255 * (1 + t[used])), 255 * (1 - np.abs(t[used])),
                         np.where(t[used] < 0, 255, 255 * (1 - t[used]))], -1).astype(np.uint8)
    pans = [panel(c), panel(ho), panel(hn), panel(dd)]
    pw, ph = pans[0].size
    so = Image.open(a.shot_off).convert("RGB").crop((0, 20, 700, 540))
    sn = Image.open(a.shot_on).convert("RGB").crop((0, 20, 700, 540))
    sw = 2 * pw
    sh = int(so.height * sw / so.width)
    so = so.resize((sw, sh), Image.LANCZOS); sn = sn.resize((sw, sh), Image.LANCZOS)
    top = 60 + 26 * len(a.line)
    W, H = 4 * pw + 50, top + 30 + ph + 40 + sh + 20
    out = Image.new("RGB", (W, H), (245, 245, 245))
    dr = ImageDraw.Draw(out)
    dr.text((10, 8), a.title, fill=(0, 0, 0), font=font(30))
    for i, ln in enumerate(a.line):
        dr.text((10, 48 + 26 * i), ln, fill=(20, 20, 20), font=font(20))
    caps = ["avenue cells (white), other roads (grey)", "density, blocks OFF (mean of 6 months)",
            "density, blocks ON (AVFIRST + AVDEPOSIT)", "ON - OFF (blue = less traffic, red = more)"]
    for i, p in enumerate(pans):
        x = 10 + i * (pw + 10)
        dr.text((x, top + 4), caps[i], fill=(0, 0, 0), font=font(18))
        out.paste(p, (x, top + 30))
    y = top + 30 + ph + 12
    dr.text((10, y), "game traffic layer, blocks OFF", fill=(0, 0, 0), font=font(18))
    dr.text((10 + sw + 10, y), "game traffic layer, blocks ON (same camera)", fill=(0, 0, 0), font=font(18))
    out.paste(so, (10, y + 26)); out.paste(sn, (10 + sw + 10, y + 26))
    out.save(a.out)
    print("wrote", a.out, out.size)


if __name__ == "__main__":
    main()
