#!/usr/bin/env python3
r"""hwcars_strip.py - contact sheet of every Nth GIF frame (optional crop and zoom), to read a clip as stills.

  py -3.12 hwcars_strip.py IN.gif OUT.png [--every 8] [--crop x0,y0,x1,y1] [--zoom 1.0] [--cols 4]
"""
import argparse
from PIL import Image, ImageDraw, ImageSequence

ap = argparse.ArgumentParser()
ap.add_argument("gif"); ap.add_argument("out")
ap.add_argument("--every", type=int, default=8); ap.add_argument("--crop"); ap.add_argument("--zoom", type=float, default=1.0)
ap.add_argument("--cols", type=int, default=4)
a = ap.parse_args()
fr = [f.convert("RGB") for f in ImageSequence.Iterator(Image.open(a.gif))]
sel = list(range(0, len(fr), a.every))
ims = []
for i in sel:
    im = fr[i]
    if a.crop:
        im = im.crop(tuple(map(int, a.crop.split(","))))
    if a.zoom != 1.0:
        im = im.resize((int(im.width * a.zoom), int(im.height * a.zoom)), Image.NEAREST)
    d = ImageDraw.Draw(im); d.rectangle([0, 0, 34, 12], fill=(0, 0, 0)); d.text((2, 0), "#%d" % i, fill=(255, 255, 0))
    ims.append(im)
w, h = ims[0].size
rows = (len(ims) + a.cols - 1) // a.cols
sheet = Image.new("RGB", (w * a.cols, h * rows), (255, 255, 255))
for k, im in enumerate(ims):
    sheet.paste(im, ((k % a.cols) * w, (k // a.cols) * h))
sheet.save(a.out)
print(a.out, len(fr), "frames, shown", sel)
