#!/usr/bin/env python3
r"""landfill_check.py - the in-game check for the LANDFILL mod (task landfill, 2026-10-30, re/analysis/LANDFILL.md).

Posted input only (sc3io), no cursor or focus. On a running, unpaused game (SC3_PID): camera on tile X,Z at zoom 3
(netmod/nramp_cam.py), the "?" button, a click on screen point PX,PY (a landfill cell in that view), a frame dump of the
query dialog, then optionally "Vaciar" and the dialog's OK, with a dump after each. Pictures go to OUTDIR as
<prefix>_1_query.png, <prefix>_2_emptied.png, <prefix>_3_closed.png. Positions are for the 800x600 default window
with the HUD at 1x (the "?" at 565,573; in a 308x395 query dialog at its default place, Vaciar at 87,412, OK at 318,412).

  py -3.12 re/tools/landfill_check.py OUTDIR PREFIX X,Z PX,PY [--empty]
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sc3io  # noqa: E402


def shot(path):
    subprocess.run([sys.executable, os.path.join(HERE, "netmod", "np_drive.py"), "shot", path], check=True,
                   stdout=subprocess.DEVNULL)


def click(h, x, y, wait):
    sc3io.move(h, x, y)
    time.sleep(0.3)
    sc3io.click(h, x, y)
    time.sleep(wait)


def main(argv):
    out, pre, tile, pt = argv[1], argv[2], argv[3], argv[4]
    empty = "--empty" in argv
    os.makedirs(out, exist_ok=True)
    h = sc3io.game_hwnd()
    subprocess.run([sys.executable, os.path.join(HERE, "netmod", "nramp_cam.py"), out, pre + "_0_cam", tile, "zooms=3",
                    "rots=0"], check=True, stdout=subprocess.DEVNULL)
    px, py = map(int, pt.split(","))
    click(h, 565, 573, 1.0)                     # "?"
    click(h, px, py, 2.0)                       # the landfill cell
    shot(os.path.join(out, pre + "_1_query.png"))
    if empty:
        click(h, 87, 412, 2.0)                  # Vaciar
        shot(os.path.join(out, pre + "_2_emptied.png"))
    click(h, 318, 412, 2.0)                     # OK
    sc3io.move(h, 760, 120)
    time.sleep(1.0)
    shot(os.path.join(out, pre + "_3_closed.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
