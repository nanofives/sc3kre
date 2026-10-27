"""slopeend_lab.py -- the in-game drags of task slopeend on lab_slope.sc3 (slopeend.py lab), through rb_lab.py.

SC3_PID / SC3_LAB_DIR as rb_lab. Posted input only (sc3io), the camera by rb_lab cam (game-thread calls).
    py -3.12 slopeend_lab.py plan P1|P2          # print the drags and their pixels for the current camera
    py -3.12 slopeend_lab.py run P1|P2 [name]    # do them (all, or one by name)
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rb_lab  # noqa: E402
import time  # noqa: E402

# (name, from, to, alt): P1 = vertices X 50..56, Z 18..24 at 83 (flat around at 82); P2 = X 62..68, Z 18..24 at 84
DRAGS = {
    "P1": [("W_up", (44, 20), (49, 20), 82), ("W_down", (51, 22), (49, 22), 83),
           ("E_up", (60, 21), (56, 21), 82), ("E_down", (54, 19), (56, 19), 83),
           ("N_up", (53, 13), (53, 17), 82), ("N_down", (51, 20), (51, 17), 83),
           ("S_up", (52, 29), (52, 24), 82), ("S_down", (54, 21), (54, 24), 83),
           ("stub", (49, 18), (49, 18), 82), ("corner", (46, 24), (49, 24), 82)],
    "EXT": [("extend", (49, 20), (52, 20), 83)],
    "P2": [("W_up", (58, 19), (61, 19), 82), ("S_down", (66, 21), (66, 24), 84),
           ("N_up", (65, 13), (65, 17), 82), ("E_up", (73, 20), (68, 20), 82), ("N_up2", (63, 13), (63, 17), 83)],
}


def main(argv):
    what, grp = argv[1], argv[2]
    only = argv[3:] or None
    h = rb_lab.sc3io.game_hwnd(rb_lab.sc3io.game_pid())
    picked = False
    for name, a, b, alt in DRAGS[grp]:
        if only and name not in only:
            continue
        pa, pb = rb_lab.pix(*a, alt), rb_lab.pix(*b, alt)
        ok = all(120 <= p[0] < 600 and 80 <= p[1] < 480 for p in (pa, pb))     # clear of the edges and the HUD
        print("%-7s %s -> %s alt %d  pixels %s %s %s" % (name, a, b, alt, pa, pb, "" if ok else "OUT OF VIEW"),
              flush=True)
        if what != "run" or not ok:
            continue
        if not picked:                       # the Road tool, once (np_drive cmd: one Frida attach)
            rb_lab.np("cmd", "0x%x" % rb_lab.CMD["road"])
            time.sleep(0.8)
            picked = True
        rb_lab.sc3io.move(h, *pa)
        time.sleep(0.3)
        rb_lab.sc3io.drag(h, pa[0], pa[1], pb[0], pb[1], button="left")
        time.sleep(2.0)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
