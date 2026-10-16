#!/usr/bin/env python3
r"""ctm_shots.py - owner pictures of a running game (verify/cartrips3, arm SH): a few screenshots and one short GIF of
the game window, through sc3io.grab_to (screen copy of the client area; refuses when something covers the window).

  set SC3_PID=<pid>
  py -3.12 ctm_shots.py --out <folder> --prefix replace --stills 3 --every 10 --gif-frames 40 --gif-dt 0.15
"""
import argparse
import os
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sc3io  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="shot")
    ap.add_argument("--stills", type=int, default=3)
    ap.add_argument("--every", type=float, default=10)
    ap.add_argument("--gif-frames", type=int, default=40)
    ap.add_argument("--gif-dt", type=float, default=0.15)
    ap.add_argument("--crop", help="x0,y0,x1,y1 in client pixels for the GIF (default: centre half)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    h = sc3io.game_hwnd(sc3io.game_pid())
    sc3io.raise_without_focus(h)
    time.sleep(0.5)
    for i in range(a.stills):
        p = os.path.join(a.out, "%s_%d.png" % (a.prefix, i + 1))
        g = sc3io.grab_to(p, h, settle=0.2)
        print("still", p)
        time.sleep(a.every)
    frames = []
    for i in range(a.gif_frames):
        g = sc3io.grab(h)
        img = g.img
        w, hh = img.size
        if a.crop:
            x0, y0, x1, y1 = [int(v) for v in a.crop.split(",")]
        else:
            x0, y0, x1, y1 = w // 4, hh // 4, 3 * w // 4, 3 * hh // 4
        frames.append(img.crop((x0, y0, x1, y1)).convert("P", palette=Image.ADAPTIVE, colors=128))
        time.sleep(a.gif_dt)
    gp = os.path.join(a.out, "%s_clip.gif" % a.prefix)
    frames[0].save(gp, save_all=True, append_images=frames[1:], duration=int(a.gif_dt * 1000), loop=0)
    print("gif", gp, len(frames))


if __name__ == "__main__":
    main()
