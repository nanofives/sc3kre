#!/usr/bin/env python3
r"""budget_closer.py - close the yearly budget dialog during long unattended runs (task avflow, 2026-10-24).

Every January the game opens the budget window (Presupuesto) and the sim waits until it is closed: a measurement run
stalls there. This loop asks sc3resize's FRAMEDUMP for a frame every --every seconds (writes <prefix>req, reads
<prefix>bchk.bmp; the game must run with SC3RESIZE_FRAMEDUMP=<prefix>), compares two patches of the frame (the dialog
title row and its OK button) with the same patches of a reference dump of the open dialog (--ref, 800x600 client),
and when both match posts a click on the OK button (sc3io.click: posted input, no cursor, no focus). No Frida.

  set SC3_PID=<pid>
  py -3.12 budget_closer.py --prefix <inst>\fd\ --ref <inst>\fd\stall.bmp [--every 3] [--secs 3600]
"""
import argparse
import os
import sys
import time

from PIL import Image, ImageChops, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402

PATCHES = [(105, 38, 330, 62), (545, 476, 597, 500)]    # title row with "Presupuesto" + the tabs, the OK button
OK = (571, 488)


def diff(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--every", type=float, default=3.0)
    ap.add_argument("--secs", type=float, default=3600)
    ap.add_argument("--tol", type=float, default=6.0)
    a = ap.parse_args()
    pid = int(os.environ.get("SC3_PID") or sc3io.game_pid())
    h = sc3io.game_hwnd(pid)
    ref = Image.open(a.ref).convert("RGB")
    refp = [ref.crop(p) for p in PATCHES]
    req, bmp = a.prefix + "req", a.prefix + "bchk.bmp"
    t0, n = time.time(), 0
    while time.time() - t0 < a.secs:
        time.sleep(a.every)
        with open(req, "w") as f:
            f.write("bchk\n")
        t1 = time.time()
        while os.path.exists(req) and time.time() - t1 < 10:
            time.sleep(0.2)
        if os.path.exists(req) or not os.path.exists(bmp):
            continue
        try:
            im = Image.open(bmp).convert("RGB")
        except OSError:
            continue
        if im.size != ref.size:
            continue
        d = [diff(im.crop(p), r) for p, r in zip(PATCHES, refp)]
        if max(d) < a.tol:
            n += 1
            print("%.0f s: budget dialog (patch diff %.1f / %.1f) -> OK clicked (%d)" % (time.time() - t0, d[0], d[1], n), flush=True)
            sc3io.click(h, *OK)
            time.sleep(1.0)


if __name__ == "__main__":
    main()
