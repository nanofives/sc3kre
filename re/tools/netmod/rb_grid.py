#!/usr/bin/env python3
r"""rb_grid.py - live surface pieces of a box vs a save, for the roundabout3 arms (read only).

  py -3.12 rb_grid.py SAVE X,Z [R]           SC3_PID = the game. Box = origin (X,Z) of a 2x2 block, +-R cells (default 3).
Prints the live grid (np_drive.py cells, Frida), and every cell whose network piece (id.state) differs from SAVE.
The 4 block cells are listed apart: they are expected to be 20400 when the block is converted.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def live(x0, z0, x1, z1):
    out = subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py"), "cells", "%d,%d,%d,%d" % (x0, z0, x1, z1)],
                         capture_output=True, text=True)
    g = {}
    for l in out.stdout.splitlines():
        if l.startswith("{"):
            c = json.loads(l)
            if "piece" in c:
                g[(c["x"], c["z"])] = (c["piece"], c["state"])
    return g


def main(argv):
    from netmod import tiler
    save, at = argv[1], argv[2]
    R = int(argv[3]) if len(argv) > 3 else 3
    X, Z = (int(t) for t in at.split(","))
    x0, z0, x1, z1 = X - R, Z - R, X + 1 + R, Z + 1 + R
    city = tiler.City.load(save)
    sv = {c: (p.id, p.state) for c, p in city.layers["surface"].items() if x0 <= c[0] <= x1 and z0 <= c[1] <= z1}
    lv = live(x0, z0, x1, z1)
    block = {(X, Z), (X + 1, Z), (X, Z + 1), (X + 1, Z + 1)}
    for z in range(z0, z1 + 1):
        print("%4d " % z + " ".join(("%s%5d.%d" % ("[" if (x, z) in block else " ", *lv[(x, z)])) if (x, z) in lv
                                     else "      ." for x in range(x0, x1 + 1)))
    print("     " + " ".join("%7d" % x for x in range(x0, x1 + 1)))
    diff = [(c, sv.get(c), lv.get(c)) for c in sorted(set(sv) | set(lv)) if sv.get(c) != lv.get(c)]
    out_block = [d for d in diff if d[0] not in block]
    print("block cells:", " ".join("(%d,%d) save %s live %s" % (c[0], c[1], sv.get(c), lv.get(c)) for c in sorted(block)))
    print("cells outside the block that differ from the save: %d %s" % (len(out_block), out_block[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
