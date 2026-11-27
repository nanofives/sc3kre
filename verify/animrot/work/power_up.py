#!/usr/bin/env python3
r"""animrot: power the 8 test buildings of AnimRotSaved.sc3 with one coal plant (4x4, key 57E:CF) touching each,
placed by the game's own PlaceBuilding (building layer vt+0x38, lab.py place). Tries east, west, south, north.

  py -3.12 power_up.py            (SC3_PID = the game)
"""
import json
import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
BLD = [(129, 121), (123, 128), (116, 115), (136, 134), (130, 156), (130, 165), (130, 174), (130, 183)]   # 5x5 min corners


def place(x, z):
    r = subprocess.run([sys.executable, str(HERE / "lab.py"), "place", "207EDC0E,57E,CF", "%d,%d" % (x, z)],
                       capture_output=True, text=True)
    return json.loads(r.stdout.strip().splitlines()[-1]).get("placed", 0)


def main():
    for x0, z0 in BLD:
        done = None
        for name, (x, z) in (("east", (x0 + 5, z0)), ("south", (x0, z0 + 5)), ("west", (x0 - 4, z0)), ("north", (x0, z0 - 4)),
                             ("east+1", (x0 + 5, z0 + 1)), ("south+1", (x0 + 1, z0 + 5)), ("west+1", (x0 - 4, z0 + 1)),
                             ("north+1", (x0 + 1, z0 - 4))):
            if place(x, z):
                done = (name, x, z)
                break
        print("building at (%d,%d): plant %s" % (x0, z0, done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
