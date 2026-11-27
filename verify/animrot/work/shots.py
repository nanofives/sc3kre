#!/usr/bin/env python3
r"""animrot shots: frame dumps of the two test groups at given zooms and all four views.

  py -3.12 shots.py <prefix> [zooms=2,3] [groups=sp,sc] [views=0,1,2,3]

Groups (cells of AnimRotSaved.sc3): sp = the four Spaceports (rotations 0-3 at (129,121) (123,128) (116,115) (136,134)),
centre (128,127); sc = the four Science Centers (rotations 0-3 at x 130, z 156 / 165 / 174 / 183), centre (132,172).
Needs SC3_PID, game running and unpaused. Writes fd/<prefix>_<group>_z<zoom>_v<view>.png via lab.py.
"""
import subprocess
import sys
import time
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
GROUPS = {"sp": (128, 127), "sc": (132, 171),
          "sp0": (131, 123), "sp1": (125, 130), "sp2": (118, 117), "sp3": (138, 136),   # one building each (centre cell)
          "sc1": (132, 167), "sc2": (132, 176), "sc3": (132, 185), "cp": (93, 170)}


def lab(*a):
    r = subprocess.run([sys.executable, str(HERE / "lab.py")] + [str(x) for x in a], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
    return r.stdout.strip()


def main(a):
    pre = a[0]
    zooms = [int(z) for z in (a[1] if len(a) > 1 else "2,3").split(",")]
    groups = (a[2] if len(a) > 2 else "sp,sc").split(",")
    views = [int(v) for v in (a[3] if len(a) > 3 else "0,1,2,3").split(",")]
    for g in groups:
        x, z = GROUPS[g]
        for zoom in zooms:
            for v in views:
                lab("cam", x, z, 1 if zoom != 1 else 2, v)      # a different zoom first: the view recentres on a change
                lab("cam", x, z, zoom, v)
                if __import__("os").environ.get("NUDGE"):   # the game's animation reconcile is skipped while the view moves
                    time.sleep(2)
                    lab("cam", x, z + 1, zoom, v)
                time.sleep(float(__import__("os").environ.get("SETTLE", "1.2")))
                nf = int(__import__("os").environ.get("FRAMES", "1"))
                for f in range(nf):
                    print(lab("dump", "%s_%s_z%d_v%d" % (pre, g, zoom, v) + ("_f%d" % f if nf > 1 else "")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
