#!/usr/bin/env python3
r"""nramp_arm.py - replay the netramp build sequence on one -multi instance (verify/netramp/PRE.md), 2026-10-13.

Needs nramp_trace.py running on the same SC3_PID, writing JSON lines to TRACE (it reports the cell under the cursor
while the On-ramp tool is selected, which is how pixels are found: nramp_view.py).

  py -3.12 nramp_arm.py TRACE build                 highway (95,145)->(108,145), road (101,139)->(101,151)
  py -3.12 nramp_arm.py TRACE onramp X,Z            On-ramp tool click on cell X,Z (hover cap reset first)
  py -3.12 nramp_arm.py TRACE bulldoze X,Z          Bulldozer click on cell X,Z
  py -3.12 nramp_arm.py TRACE cells X0,Z0,X1,Z1     live grid (piece ids) + JSON lines to stdout
All input is posted to the instance's window (sc3io), no cursor, no focus.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import sc3io  # noqa: E402
from nramp_view import View  # noqa: E402

CMD = {"road": 0x10004001, "highway": 0x10004301, "onramp": 0x10004302, "bulldoze": None}


def cmd(c):
    subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py"), "cmd", "0x%x" % c], check=True,
                   stdout=subprocess.DEVNULL)
    time.sleep(0.8)


def cells(r):
    out = subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py"), "cells", r], capture_output=True, text=True)
    return [json.loads(l) for l in out.stdout.splitlines() if l.startswith("{")]


def grid(cs, r):
    x0, z0, x1, z1 = map(int, r.split(","))
    g = {(c["x"], c["z"]): ("%5d.%d" % (c["piece"], c["state"])) if "piece" in c else "     B " for c in cs}
    lines = ["%4d " % z + " ".join(g.get((x, z), "      .") for x in range(x0, x1 + 1)) for z in range(z0, z1 + 1)]
    return "\n".join(lines + ["     " + " ".join("%7d" % x for x in range(x0, x1 + 1))])


def reset_cap(v):
    cmd(CMD["road"])
    sc3io.move(v.h, 300, 200)
    time.sleep(0.4)
    sc3io.move(v.h, 310, 205)
    time.sleep(0.4)


def main(argv):
    v = View(argv[1])
    what = argv[2]
    if what == "build":
        cmd(CMD["onramp"])
        v.goto(101, 146)
        p = {c: v.pix(*c) for c in [(95, 145), (108, 145), (101, 139), (101, 151)]}
        print("pixels", p, flush=True)
        cmd(CMD["highway"])
        sc3io.drag(v.h, *p[(95, 145)], *p[(108, 145)], button="left")
        time.sleep(3)
        cmd(CMD["road"])
        sc3io.drag(v.h, *p[(101, 139)], *p[(101, 151)], button="left")
        time.sleep(3)
    elif what in ("onramp", "bulldoze"):
        x, z = map(int, argv[3].split(","))
        cmd(CMD["onramp"])
        px = v.pix(x, z)
        print("pixel", px, flush=True)
        if what == "onramp":
            reset_cap(v)
            cmd(CMD["onramp"])
            sc3io.move(v.h, *px)
            time.sleep(0.8)
            sc3io.click(v.h, *px)
        else:
            cmd(int(argv[4], 16))            # the bulldozer command id is passed in (MenuItem.INI)
            sc3io.click(v.h, *px)
        time.sleep(3)
    elif what == "cells":
        cs = cells(argv[3])
        print(grid(cs, argv[3]))
        for c in cs:
            print(json.dumps(c))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
