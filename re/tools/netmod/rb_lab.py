#!/usr/bin/env python3
r"""rb_lab.py - drive one -multi instance for the roundabout3 building cases (verify/roundabout3/PRE.md arms B, V).

SC3_PID = the game. Keep the sim paused. The camera is moved with the game's own calls (nramp_cam.py's Frida script,
run on the game thread), and a cell's client pixel is computed with the SIMSPR draw point (NET_ART.md 2):
    sx = (vz - vx) * (4 << zoom) - originX,  sy = (vx + vz) * (2 << zoom) - alt * (1 << zoom) - originY
(view coords (vx, vz) per rotation, FUN_1000a62c), + (tile W / 2, 0) for the diamond centre. alt = the camera's own
cell altitude is not known here, so it is calibrated once per camera move from a known road cell (`calib`).

  py -3.12 rb_lab.py cam X,Z ZOOM ROT                    camera on cell X,Z; prints the state (zoom, rot, origin)
  py -3.12 rb_lab.py road X0,Z0 X1,Z1 [--alt A]          Road tool drag between two cells (straight line)
  py -3.12 rb_lab.py demolish X,Z [--alt A]              Demolish tool click on a cell
  py -3.12 rb_lab.py cells X0,Z0,X1,Z1                   live grid (id.state) of a box
  py -3.12 rb_lab.py shot OUT.png                        in-process frame dump (sc3resize DUMP)
State (last camera) is kept in rb_lab_cam.json next to SC3_LAB_DIR (default: cwd).
"""
import json
import os
import subprocess
import sys
import time
import ctypes

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import sc3io  # noqa: E402
import nramp_cam  # noqa: E402

NP = os.path.join(HERE, "np_drive.py")
STATE = os.path.join(os.environ.get("SC3_LAB_DIR", os.getcwd()), "rb_lab_cam.json")
CMD = {"road": 0x10004001, "demolish": 0x1000400A}


def np(*a, capture=False):
    r = subprocess.run([sys.executable, NP] + [str(x) for x in a], capture_output=True, text=True)
    return r.stdout


def cam(x, z, zoom, rot):
    pid = sc3io.game_pid()
    h = sc3io.game_hwnd(pid)
    s = frida.attach(pid)
    sc = s.create_script(nramp_cam.JS)
    sc.load()
    api = sc.exports_sync
    for btn in ((772, 546), (666, 546)):
        sc3io.click(h, *btn)
        time.sleep(1.0)
        if api.hascam():
            break
    if not api.hascam():
        raise SystemExit("camera not captured")
    api.queue({"k": "rot", "v": rot, "f": 1, "x": x, "z": z})
    api.queue({"k": "zoom", "v": zoom, "f": 1, "x": x, "z": z})
    ctypes.windll.user32.PostMessageA(h, nramp_cam.WM_CAM, 0, 0)
    time.sleep(1.5)
    res = api.take()
    s.detach()
    st = [r["state"] for r in res if "state" in r]
    if len(st) < 2:
        raise SystemExit("camera call failed: %s" % res)
    json.dump(st[-1], open(STATE, "w"))
    print(json.dumps(st[-1]))
    return st[-1]


def view(x, z, rot, W=256, H=256):
    return [(x, z), (H - 1 - z, x), (W - 1 - x, H - 1 - z), (z, W - 1 - x)][rot]


def pix(x, z, alt, st=None):
    st = st or json.load(open(STATE))
    zm, rot, (ox, oy) = st["zoom"], st["rot"], st["origin"]
    vx, vz = view(x, z, rot)
    sx = (vz - vx) * (4 << zm) - ox + (4 << zm)
    sy = (vx + vz) * (2 << zm) - alt * (1 << zm) - oy
    return int(sx), int(sy)


def main(argv):
    what = argv[1]
    alt = 0
    if "--alt" in argv:
        alt = int(argv[argv.index("--alt") + 1])
    h = sc3io.game_hwnd(sc3io.game_pid())
    if what == "cam":
        x, z = map(int, argv[2].split(","))
        cam(x, z, int(argv[3]), int(argv[4]))
    elif what == "road":
        a = tuple(map(int, argv[2].split(",")))
        b = tuple(map(int, argv[3].split(",")))
        pa, pb = pix(*a, alt), pix(*b, alt)
        np("cmd", "0x%x" % CMD["road"])
        time.sleep(0.8)
        sc3io.move(h, *pa)
        time.sleep(0.3)
        sc3io.drag(h, pa[0], pa[1], pb[0], pb[1], button="left")
        time.sleep(2.5)
        print("road", a, b, "pixels", pa, pb)
    elif what == "demolish":
        c = tuple(map(int, argv[2].split(",")))
        p = pix(*c, alt)
        np("cmd", "0x%x" % CMD["demolish"])
        time.sleep(0.8)
        sc3io.move(h, *p)
        time.sleep(0.4)
        sc3io.click(h, *p)
        time.sleep(2.5)
        print("demolish", c, "pixel", p)
    elif what == "cells":
        x0, z0, x1, z1 = map(int, argv[2].split(","))
        out = np("cells", argv[2])
        g = {}
        for l in out.splitlines():
            if l.startswith("{"):
                c = json.loads(l)
                if "piece" in c:
                    g[(c["x"], c["z"])] = "%5d.%d" % (c["piece"], c["state"])
                else:
                    g[(c["x"], c["z"])] = "      B"
        for z in range(z0, z1 + 1):
            print("%4d " % z + " ".join(g.get((x, z), "      .") for x in range(x0, x1 + 1)))
        print("     " + " ".join("%7d" % x for x in range(x0, x1 + 1)))
    elif what == "shot":
        np("shot", argv[2])
        print("shot", argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
