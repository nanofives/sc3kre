#!/usr/bin/env python3
r"""nv_arm.py - one netvariant load arm: launch (nv_run.py), dump a frame, read the live road cells, optionally save,
stop the pid it started (2026-10-13).

  py -3.12 nv_arm.py <instance dir> <city.sc3> <arm> <x0,y0,x1,y1> [--save] [ENV=VAL ...]

Prints the live piece histogram over the rectangle and the cells holding the variant (20029) or its base (29).
Frame -> verify/netvariant/<arm>_01_city.png; with --save the saved city is copied to <instance>\<arm>_after.sc3.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
VDIR = os.path.join(REPO, "verify", "netvariant")


def drive(env, *args, timeout=120):
    r = subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py")] + list(args), capture_output=True,
                       text=True, env=env, timeout=timeout)
    return r.stdout


def main(argv):
    inst, city, arm, rect = argv[1], argv[2], argv[3], argv[4]
    save = "--save" in argv
    extra = [a for a in argv[5:] if "=" in a]
    r = subprocess.run([sys.executable, os.path.join(HERE, "nv_run.py"), inst, city, arm] + extra,
                       capture_output=True, text=True)
    got = [l for l in r.stdout.splitlines() if l.startswith("PID=")]
    if not got:
        raise SystemExit("nv_run failed: %s %s" % (r.stdout, r.stderr))
    pid = int(got[0][4:])
    env = dict(os.environ, SC3_PID=str(pid))
    print("arm %s pid %d" % (arm, pid))
    drive(env, "shot", os.path.join(VDIR, "%s_01_city.png" % arm))
    cells = [json.loads(l) for l in drive(env, "cells", rect).splitlines() if l.startswith("{")]
    p = [c for c in cells if "piece" in c]
    print("live pieces:", dict(Counter(c["piece"] for c in p)))
    print("20029:", sorted((c["x"], c["z"], c["state"]) for c in p if c["piece"] == 20029))
    print("29:   ", sorted((c["x"], c["z"], c["state"]) for c in p if c["piece"] == 29))
    if save:
        copy = os.path.join(inst, "nv_%s.sc3" % arm)
        t0 = os.path.getmtime(copy)
        drive(env, "cmd", "0x10009002")
        for _ in range(60):
            time.sleep(1)
            if os.path.getmtime(copy) != t0:
                break
        time.sleep(4)
        shutil.copyfile(copy, os.path.join(inst, "%s_after.sc3" % arm))
        print("saved -> %s" % os.path.join(inst, "%s_after.sc3" % arm))
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    print("stopped pid %d" % pid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
