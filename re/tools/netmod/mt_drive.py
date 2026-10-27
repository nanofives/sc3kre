#!/usr/bin/env python3
r"""mt_drive.py - drive one -multi instance for the multitile tests (verify/multitile/PRE.md), 2026-10-13.

Needs nramp_trace.py running on the same SC3_PID, writing JSON lines to TRACE (cell under the cursor through the
On-ramp tool's cost preview; the TMPL block calls the stock preview first, so it also works in template mode).
LOG = the instance's sc3netmod.log (template mode state and placement results are read from it).
All input is posted to the instance's window (sc3io): no cursor, no focus.

  py -3.12 mt_drive.py TRACE LOG mode NAME|off [ROT]      key T until NAME is chosen (or off), then key R to ROT
  py -3.12 mt_drive.py TRACE LOG place X,Z                hover + click with the anchor on X,Z; prints the log result
  py -3.12 mt_drive.py TRACE LOG road X0,Z0 X1,Z1         Road tool drag (0x10004001)
  py -3.12 mt_drive.py TRACE LOG demolish X,Z             Demolish tool click (0x1000400A)
  py -3.12 mt_drive.py TRACE LOG cells X0,Z0,X1,Z1        live grid (piece.state) of the box
  py -3.12 mt_drive.py TRACE LOG goto X,Z                 minimap + pixel search so X,Z is near the view centre
  py -3.12 mt_drive.py TRACE LOG hover X,Z                hover only (template footprint highlighted, no click)
  py -3.12 mt_drive.py TRACE LOG pix X,Z [X,Z ...]        client pixel of each cell (JSON), for the shot boxes
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import sc3io  # noqa: E402
from nramp_view import View  # noqa: E402

CMD = {"road": 0x10004001, "onramp": 0x10004302, "demolish": 0x1000400A}
NP = os.path.join(HERE, "np_drive.py")


def cmd(c):
    subprocess.run([sys.executable, NP, "cmd", "0x%x" % c], check=True, stdout=subprocess.DEVNULL)
    time.sleep(0.8)


def key(vk):
    subprocess.run([sys.executable, NP, "key", "0x%x" % vk], check=True, stdout=subprocess.DEVNULL)
    time.sleep(0.5)


def log_tail(log, n=0):
    with open(log, errors="replace") as f:
        ls = [l.rstrip() for l in f if "tmpl:" in l]
    return ls[n:]


def mode_now(log):
    for l in reversed(log_tail(log)):
        m = re.search(r"key T -> template \d+ (\S+)", l)
        if m:
            name = m.group(1)
            rot = 0
            for l2 in log_tail(log)[log_tail(log).index(l):]:
                m2 = re.search(r"key R -> \S+ orientation (\d+)", l2)
                if m2:
                    rot = int(m2.group(1))
            return name, rot
        if "template mode OFF" in l:
            return None, 0
    return None, 0


def set_mode(log, name, rot):
    for _ in range(12):
        cur, r = mode_now(log)
        if (name == "off" and cur is None) or (cur is not None and cur.split("/")[-1] == name):
            break
        key(0x54)
    for _ in range(4):
        cur, r = mode_now(log)
        if name == "off" or r == rot:
            break
        key(0x52)
    print("mode:", mode_now(log), flush=True)


def cells(r):
    out = subprocess.run([sys.executable, NP, "cells", r], capture_output=True, text=True)
    return [json.loads(l) for l in out.stdout.splitlines() if l.startswith("{")]


def grid(cs, r):
    x0, z0, x1, z1 = map(int, r.split(","))
    g = {(c["x"], c["z"]): ("%5d.%d" % (c["piece"], c["state"])) if "piece" in c else "      B" for c in cs}
    lines = ["%4d " % z + " ".join(g.get((x, z), "      .") for x in range(x0, x1 + 1)) for z in range(z0, z1 + 1)]
    return "\n".join(lines + ["     " + " ".join("%7d" % x for x in range(x0, x1 + 1))])


def main(argv):
    trace, log, what = argv[1], argv[2], argv[3]
    v = View(trace)
    if what == "mode":
        set_mode(log, argv[4], int(argv[5]) if len(argv) > 5 else 0)
    elif what == "goto":
        x, z = map(int, argv[4].split(","))
        cmd(CMD["onramp"])
        print("pixel", v.goto(x, z), flush=True)
    elif what == "place":
        x, z = map(int, argv[4].split(","))
        cmd(CMD["onramp"])
        v.reset_cap()
        px = v.pix(x, z)
        print("pixel", px, flush=True)
        n0 = len(log_tail(log))
        sc3io.move(v.h, px[0] - 3, px[1] - 2)
        time.sleep(0.3)
        sc3io.move(v.h, *px)
        time.sleep(0.8)
        sc3io.click(v.h, *px)
        # was a blind 2.5 s: return the moment the mod logs its verdict, keep a cap (now 6 s) and stay
        # silent on a miss exactly as before
        t_end = time.time() + 6.0
        while True:
            hits = [l for l in log_tail(log, n0) if "PLACED" in l or "REFUSED" in l or "before any" in l]
            if hits or time.time() >= t_end:
                break
            time.sleep(0.1)
        for l in hits:
            print(l, flush=True)
    elif what == "road":
        a = tuple(map(int, argv[4].split(",")))
        b = tuple(map(int, argv[5].split(",")))
        cmd(CMD["onramp"])
        pa, pb = v.pix(*a), v.pix(*b)
        print("pixels", pa, pb, flush=True)
        cmd(CMD["road"])
        sc3io.drag(v.h, pa[0], pa[1], pb[0], pb[1], button="left")
        time.sleep(3)
    elif what == "demolish":
        x, z = map(int, argv[4].split(","))
        cmd(CMD["onramp"])
        px = v.pix(x, z)
        print("pixel", px, flush=True)
        cmd(CMD["demolish"])
        sc3io.move(v.h, *px)
        time.sleep(0.5)
        sc3io.click(v.h, *px)
        time.sleep(3)
    elif what == "hover":
        x, z = map(int, argv[4].split(","))
        cmd(CMD["onramp"])
        v.reset_cap()
        px = v.pix(x, z)
        sc3io.move(v.h, px[0] - 3, px[1] - 2)
        time.sleep(0.3)
        sc3io.move(v.h, *px)
        time.sleep(0.8)
        print("pixel", px, flush=True)
    elif what == "pix":
        cmd(CMD["onramp"])
        out = {}
        for a in argv[4:]:
            x, z = map(int, a.split(","))
            out[a] = v.pix(x, z)
        print(json.dumps(out), flush=True)
    elif what == "cells":
        print(grid(cells(argv[4]), argv[4]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
