#!/usr/bin/env python3
r"""nramp_shots.py - frame dumps of the netramp test strip at every zoom and rotation (verify/netramp arm R), 2026-10-13.

Clicks the city view's own zoom and rotate buttons (minimap panel of the 800x600 client: zoom in (666,546), zoom out
(772,546), rotate (752,567); positions read off the frame dumps), re-centres the target cell after every step
(nramp_view.View.center: On-ramp tool hover + arrow-key scroll), parks the cursor on the side panel, and saves an
in-process DUMP (np_drive.py shot, sc3resize).

  py -3.12 nramp_shots.py TRACE OUTDIR PREFIX X,Z
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import sc3io  # noqa: E402
from nramp_view import View  # noqa: E402

ZIN, ZOUT, ROTR = (666, 546), (772, 546), (752, 567)
PARK = (760, 120)


def shot(path):
    subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py"), "shot", path], check=True, stdout=subprocess.DEVNULL)


def main(argv):
    v = View(argv[1])
    out, pre = argv[2], argv[3]
    tx, tz = map(int, argv[4].split(","))
    os.makedirs(out, exist_ok=True)
    subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py"), "cmd", "0x10004302"], stdout=subprocess.DEVNULL)
    time.sleep(0.6)

    def snap(name):
        p = v.center(tx, tz)
        sc3io.move(v.h, *PARK)
        time.sleep(0.8)
        shot(os.path.join(out, "%s_%s.png" % (pre, name)))
        print(name, "target at", p, flush=True)

    for _ in range(5):
        sc3io.click(v.h, *ZOUT)
        time.sleep(0.8)
    for z in range(5):
        if z:
            sc3io.click(v.h, *ZIN)
            time.sleep(1.2)
        snap("z%d_r0" % z)
    for z in (4, 3):
        for r in range(1, 5):
            sc3io.click(v.h, *ROTR)
            time.sleep(1.5)
            if r < 4:
                snap("z%d_r%d" % (z, r))
        if z == 4:
            sc3io.click(v.h, *ZOUT)
            time.sleep(1.2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
