#!/usr/bin/env python3
r"""cs_gif.py - turn sc3resize FRAMEDUMP frames (<prefix><tag>_<k>.bmp, written by cs_run.py's '*' phases) into GIFs.

  py -3.12 cs_gif.py --prefix <abs prefix> --tag <arm>_<idx>_<kind> --out x.gif [--ms 120] [--crop x0,y0,x1,y1] [--scale 1]
  py -3.12 cs_gif.py --prefix ... --list            # tags found

Frames are taken in counter order. --ms is the GIF frame time (the capture interval, CS_FRAME_MS).
"""
import argparse
import collections
import glob
import os
import re

from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--tag")
    ap.add_argument("--out")
    ap.add_argument("--ms", type=int, default=120)
    ap.add_argument("--crop")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    files = glob.glob(a.prefix + "*.bmp")
    tags = collections.defaultdict(list)
    for f in files:
        m = re.match(re.escape(os.path.basename(a.prefix)) + r"(.+)_(\d{3})\.bmp$", os.path.basename(f))
        if m:
            tags[m.group(1)].append((int(m.group(2)), f))
    if a.list or not a.tag:
        for t, fs in sorted(tags.items()):
            print(t, len(fs))
        return
    fs = [f for _, f in sorted(tags[a.tag])]
    if not fs:
        raise SystemExit("no frames for tag %s" % a.tag)
    imgs = []
    for f in fs:
        im = Image.open(f).convert("RGB")
        if a.crop:
            im = im.crop(tuple(int(v) for v in a.crop.split(",")))
        if a.scale != 1.0:
            im = im.resize((int(im.width * a.scale), int(im.height * a.scale)), Image.LANCZOS)
        imgs.append(im.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.NONE))
    imgs[0].save(a.out, save_all=True, append_images=imgs[1:], duration=a.ms, loop=0, optimize=True)
    print("%s: %d frames, %d bytes" % (a.out, len(imgs), os.path.getsize(a.out)))


if __name__ == "__main__":
    main()
