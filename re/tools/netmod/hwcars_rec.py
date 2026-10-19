#!/usr/bin/env python3
r"""hwcars_rec.py - record a short clip from sc3resize FRAMEDUMP frames and make an animated GIF (task hwcars 2026-10-19).

The game must be launched with SC3RESIZE_FRAMEDUMP=<prefix> (absolute). This writes <prefix>req every MS ms with a tag,
sc3resize dumps the next presented frame to <prefix><tag>.bmp, then the frames become OUT.gif (optional crop and
scale) and the BMPs are deleted (C: fills up otherwise: project-disk-full-frame-dumps). Refuses below 3 GB free.

  py -3.12 hwcars_rec.py PREFIX OUT.gif --secs 6 [--ms 150] [--crop x0,y0,x1,y1] [--scale 1.0] [--keep N]
--keep N also saves frame N as OUT_<N>.png (a still for the sheet).
"""
import argparse, glob, os, shutil, time
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("prefix"); ap.add_argument("out")
ap.add_argument("--secs", type=float, default=6); ap.add_argument("--ms", type=int, default=150)
ap.add_argument("--crop"); ap.add_argument("--scale", type=float, default=1.0); ap.add_argument("--keep", type=int)
a = ap.parse_args()
if shutil.disk_usage(os.path.dirname(a.prefix)).free < 3 * 2 ** 30:
    raise SystemExit("refused: under 3 GB free")
tag = "c%d_" % int(time.time())
req = a.prefix + "req"
t0, k = time.time(), 0
while time.time() - t0 < a.secs:
    if not os.path.exists(req):
        with open(req, "w") as f:
            f.write("%s%03d\n" % (tag, k))
        k += 1
    time.sleep(a.ms / 1000.0)
time.sleep(1.0)
files = sorted(glob.glob(a.prefix + tag + "*.bmp"))
frames = []
for f in files:
    for _ in range(20):
        try:
            im = Image.open(f).convert("RGB"); break
        except OSError:
            time.sleep(0.2)
    if a.crop:
        im = im.crop(tuple(map(int, a.crop.split(","))))
    if a.scale != 1.0:
        im = im.resize((int(im.width * a.scale), int(im.height * a.scale)), Image.LANCZOS)
    frames.append(im)
if not frames:
    raise SystemExit("no frames dumped (is SC3RESIZE_FRAMEDUMP set for this game?)")
dt = int(a.secs * 1000 / max(len(frames), 1))
frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=dt, loop=0)
if a.keep is not None and a.keep < len(frames):
    frames[a.keep].save(a.out[:-4] + "_%d.png" % a.keep)
for f in files:
    os.remove(f)
print("gif", a.out, len(frames), "frames,", dt, "ms each,", k, "requests")
