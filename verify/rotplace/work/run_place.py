#!/usr/bin/env python3
r"""rotplace: place one building per rotation with the stock tool, TAB pressed k times (posted), then read it back.

  py -3.12 run_place.py <inst> <tag> [<k>:]<x,y>[;...]   one click point per rotation 0..3 (or k TABs) (client coords at cam 128,128 z3 r0)

Needs the game running (lab.py launch, unpaused). Prints the log lines and the occupant under each placement.
"""
import json
import re
import subprocess
import sys
import time
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
LAB = [sys.executable, str(HERE / "lab.py")]
LOG = HERE / "resize.log"


def lab(*a):
    r = subprocess.run(LAB + [str(x) for x in a], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
    return r.stdout.strip()


def main(a):
    inst, tag, pts = a[0], a[1], a[2].split(";")
    lab("cam", 128, 128, 3, 0)
    for k, p in enumerate(pts):
        if ":" in p:                      # "<rotation>:<x>,<y>"
            k, p = int(p.split(":")[0]), p.split(":")[1]
        x, y = (int(v) for v in p.split(","))
        n0 = len(LOG.read_text(errors="replace").splitlines())
        print(lab("arm", inst))
        lab("move", x - 2, y - 2); time.sleep(0.4); lab("move", x, y); time.sleep(0.4)
        for _ in range(k):
            lab("key", "0x09"); time.sleep(0.3)
        print(lab("dump", "%s_rot%d_label" % (tag, k)))
        lab("click", x, y); time.sleep(1.0)
        new = LOG.read_text(errors="replace").splitlines()[n0:]
        for l in new:
            if "ROTPLACE" in l or "placement" in l:
                print(l)
        m = [re.search(r"placement \(kind \d\) at \((\d+), (\d+)\): (\w+)", l) for l in new]
        m = [v for v in m if v]
        if m and m[-1].group(3) == "placed":
            cx, cz = int(m[-1].group(1)), int(m[-1].group(2))
            r = json.loads(lab("occ", cx, cz, cx, cz))
            for o in r[0]["occ"]:
                print("  occupant type %s rect %s rot %s" % (o["type"], o["rect"], o["rot"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
