#!/usr/bin/env python3
r"""roadover_drive.py - posted-input driver for the ROADOVER tests (task roadover, 2026-10-28). No cursor, no focus.

SC3_PID = the game, SC3_CITY = the save it loaded (terrain heights for the cell -> pixel map, hwcars_drag.cell_alt).
Camera and pixels: rb_lab.py (game's own camera call, SIMSPR draw point).

  py -3.12 roadover_drive.py cam X,Z [ZOOM]            camera on a cell (rotation 0), state saved for the pixel map
  py -3.12 roadover_drive.py tool road|hway|rail|police|bulldoze   menu command (GZ message, np_drive)
  py -3.12 roadover_drive.py hold X0,Z0 X1,Z1          press on X0,Z0, move to X1,Z1, keep the button down (preview)
  py -3.12 roadover_drive.py release X,Z               button up on X,Z (builds the held drag)
  py -3.12 roadover_drive.py drag X0,Z0 X1,Z1          press, move, release
  py -3.12 roadover_drive.py click X,Z                 one left click on a cell
  py -3.12 roadover_drive.py key VK                    posted key (0x1B Escape)
  py -3.12 roadover_drive.py shot OUT.png              sc3resize frame dump (mods on) or a window grab (-Stock)
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "netmod"))
import sc3io  # noqa: E402
import rb_lab  # noqa: E402
import hwcars_drag  # noqa: E402

CMDS = {"road": 0x10004001, "hway": 0x10004301, "rail": 0x10004101,   # hwcars_drag.py
        "police": 0x10006201,                                             # LAUNCH_CONTROL.md
        "bulldoze": 0x1000400A}                                           # rb_lab.py
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON = 0x200, 0x201, 0x202, 1


def px(c):
    alt = hwcars_drag.cell_alt(c, [])
    st = json.load(open(rb_lab.STATE))
    return rb_lab.pix(c[0], c[1], alt, st)


def cell(s):
    return tuple(map(int, s.split(",")))


def main(a):
    verb = a[1]
    h = sc3io.game_hwnd(sc3io.game_pid())
    if verb == "cam":
        x, z = cell(a[2])
        st = hwcars_drag.safe_cam(x, z, int(a[3]) if len(a) > 3 else 2)
        print("cam", json.dumps(st))
    elif verb == "tool":
        print(rb_lab.np("cmd", "0x%x" % CMDS[a[2]]).strip())
        time.sleep(0.8)
    elif verb in ("hold", "drag"):
        p0, p1 = px(cell(a[2])), px(cell(a[3]))
        sc3io.move(h, *p0)
        time.sleep(0.3)
        sc3io._post(h, WM_LBUTTONDOWN, MK_LBUTTON, sc3io._lp(*p0))
        time.sleep(0.2)
        for s in range(1, 13):
            sc3io._post(h, WM_MOUSEMOVE, MK_LBUTTON, sc3io._lp(p0[0] + (p1[0] - p0[0]) * s // 12,
                                                              p0[1] + (p1[1] - p0[1]) * s // 12))
            time.sleep(0.06)
        if verb == "drag":
            time.sleep(0.3)
            sc3io._post(h, WM_LBUTTONUP, 0, sc3io._lp(*p1))
            time.sleep(2.0)
        print(verb, a[2], a[3], "pixels", p0, p1)
    elif verb == "release":
        p = px(cell(a[2]))
        sc3io._post(h, WM_MOUSEMOVE, MK_LBUTTON, sc3io._lp(*p))
        time.sleep(0.2)
        sc3io._post(h, WM_LBUTTONUP, 0, sc3io._lp(*p))
        time.sleep(2.0)
        print("release", a[2], "pixel", p)
    elif verb == "click":
        p = px(cell(a[2]))
        sc3io.move(h, *p)
        time.sleep(0.4)
        sc3io.click(h, *p)
        time.sleep(1.5)
        print("click", a[2], "pixel", p)
    elif verb == "key":
        sc3io.key(h, int(a[2], 0))
        time.sleep(0.5)
    elif verb == "shot":
        out = a[2]
        pre = os.environ.get("SC3RESIZE_FRAMEDUMP")
        if pre and os.environ.get("SC3MODS_OFF") != "1":
            tag = os.path.splitext(os.path.basename(out))[0]
            bmp = pre + tag + ".bmp"
            if os.path.exists(bmp):
                os.remove(bmp)
            open(pre + "req", "w").write(tag + "\n")
            for _ in range(100):
                if os.path.exists(bmp) and not os.path.exists(pre + "req"):
                    break
                time.sleep(0.1)   # no hover here: it would move a held drag's end
            time.sleep(0.3)
            from PIL import Image
            Image.open(bmp).save(out)
            os.remove(bmp)
        else:
            g = sc3io.grab_to(out, h, settle=0.3)
            print("grab problems:", getattr(g, "problems", None))
        print("shot", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
