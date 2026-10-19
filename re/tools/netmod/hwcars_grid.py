#!/usr/bin/env python3
r"""hwcars_grid.py - live piece grid of a box, row by row (np_drive cells times out on big boxes), as JSON.

  py -3.12 hwcars_grid.py X0,Z0,X1,Z1 OUT.json        SC3_PID = the game.   OUT: {"x,z": [piece, state], ...}
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
x0, z0, x1, z1 = map(int, sys.argv[1].split(","))
g = {}
for z in range(z0, z1 + 1):
    out = subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py"), "cells", "%d,%d,%d,%d" % (x0, z, x1, z)],
                         capture_output=True, text=True).stdout
    for l in out.splitlines():
        if l.startswith("{"):
            c = json.loads(l)
            if "piece" in c:
                g["%d,%d" % (c["x"], c["z"])] = [c["piece"], c["state"]]
json.dump(g, open(sys.argv[2], "w"))
print(len(g), "network cells")
