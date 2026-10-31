#!/usr/bin/env python3
r"""avdb_lab.py - lab driver for task avdiagbreak (2026-10-30): diagonal avenue cells changed by unrelated road edits.

Game-thread calls only (nb_drive.py's Frida session: manager vt+0xf0 build, vt+0xb4 remove), never a cursor.
SC3_PID = your game, running (not paused).

  py avdb_lab.py stair X,Z N [--axis 1]          one diagonal road drag: N rows of a staircase from (X,Z)
                                                 (axis 0 runs +x +z, axis 1 runs -x +z), 2 cells per row
  py avdb_lab.py avenue X,Z N [--axis 1]         a 3-cell diagonal avenue: two joined drags, the second one cell over
  py avdb_lab.py dboulevard X,Z N [--axis 1]     a diagonal boulevard: three joined drags, one cell over each
  py avdb_lab.py road X0,Z0 X1,Z1                straight road drag
  py avdb_lab.py remove X,Z                      bulldoze one cell
  py avdb_lab.py snap X0,Z0,X1,Z1 OUT.json       piece.state of every network cell in the box
  py avdb_lab.py occ X0,Z0,X1,Z1 [STEP]          map of occupied cells ('#' anything, 'r' network, '.' empty), every STEP
  py avdb_lab.py diff A.json B.json              cells that differ
  py avdb_lab.py grid A.json                     ASCII view (piece ids) of a snapshot
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nb_drive  # noqa: E402


def xy(s):
    return [int(v) for v in s.split(",")]


def stair(x, z, n, axis):
    sx = -1 if axis else 1
    cells = []
    for k in range(n):
        cells.append((x + sx * k, z + k))
        cells.append((x + sx * (k + 1), z + k))
    return cells


def build(cells):
    s = nb_drive.Session()
    s.job({"kind": "post4", "w": [0x637C0DAB, 0, 0, 0]})
    r = s.job(timeout=300, j={"kind": "build", "net": 1, "cost": 10 * len(cells), "cells": [[x, z, 0] for x, z in cells]})
    s.close()
    return r


def snap(box, out):
    x0, z0, x1, z1 = box
    s = nb_drive.Session()
    cells = {}
    for z in range(z0, z1 + 1):
        r = s.job({"kind": "cells", "x0": x0, "y0": z, "x1": x1, "y1": z})
        for c in r.get("cells", []):
            if "piece" in c:
                cells["%d,%d" % (c["x"], c["y"])] = [c["piece"], c["state"]]
    s.close()
    json.dump({"box": box, "cells": cells}, open(out, "w"))
    print("%d network cells -> %s" % (len(cells), out))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, a = argv[1], argv[2:]
    axis = int(a[a.index("--axis") + 1]) if "--axis" in a else 0
    if cmd == "stair":
        x, z = xy(a[0])
        print(json.dumps(build(stair(x, z, int(a[1]), axis))))
    elif cmd == "avenue":
        x, z = xy(a[0])
        n = int(a[1])
        print(json.dumps(build(stair(x, z, n, axis))))
        print(json.dumps(build(stair(x + (-1 if axis else 1), z, n, axis))))
    elif cmd == "dboulevard":
        x, z = xy(a[0])
        n = int(a[1])
        for d in range(3):
            print(json.dumps(build(stair(x + d * (-1 if axis else 1), z, n, axis))))
    elif cmd == "road":
        print(json.dumps(build(nb_drive.line(xy(a[0]), xy(a[1])))))
    elif cmd == "remove":
        x, z = xy(a[0])
        s = nb_drive.Session()
        s.job({"kind": "post4", "w": [0x637C0DAB, 0, 0, 0]})
        print(json.dumps(s.job({"kind": "remove", "x": x, "z": z}, timeout=300)))
        s.close()
    elif cmd == "occ":
        x0, z0, x1, z1 = xy(a[0])
        st = int(a[1]) if len(a) > 1 else 1
        s = nb_drive.Session()
        for z in range(z0, z1 + 1, st):
            r = s.job({"kind": "cells", "x0": x0, "y0": z, "x1": x1, "y1": z})
            got = {c["x"]: ("r" if "piece" in c else "#") for c in r.get("cells", [])}
            print("%4d " % z + "".join(got.get(x, ".") for x in range(x0, x1 + 1, st)), flush=True)
        s.close()
    elif cmd == "snap":
        snap(xy(a[0]), a[1])
    elif cmd == "diff":
        A, B = json.load(open(a[0]))["cells"], json.load(open(a[1]))["cells"]
        n = 0
        for k in sorted(set(A) | set(B), key=lambda s: tuple(int(v) for v in s.split(",")[::-1])):
            if A.get(k) != B.get(k):
                n += 1
                print("%-9s %-12s -> %s" % (k, "%s.%s" % tuple(A[k]) if k in A else "-", "%s.%s" % tuple(B[k]) if k in B else "-"))
        print("%d cell(s) differ" % n)
    elif cmd == "grid":
        d = json.load(open(a[0]))
        x0, z0, x1, z1 = d["box"]
        for z in range(z0, z1 + 1):
            row = []
            for x in range(x0, x1 + 1):
                v = d["cells"].get("%d,%d" % (x, z))
                row.append("%5s.%d" % (v[0], v[1]) if v else "    . ")
            print("%4d " % z + " ".join(row))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
