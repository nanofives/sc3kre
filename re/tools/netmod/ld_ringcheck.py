#!/usr/bin/env python3
r"""ld_ringcheck.py - final-path steps on 2x2 roundabout blocks from ld_paths.py output (verify/lanedensity addendum 7).

Per block (anchor X,Z; ring order (X+1,Z) -> (X,Z) -> (X,Z+1) -> (X+1,Z+1) -> (X+1,Z), the order of quarters placed
with states 3/0/2/1): steps between two ring cells with / against that order, and steps between a given quarter (the
3-arm block's 20401 cell) and any cell outside the block, both ways.

  py -3.12 ld_ringcheck.py paths.json --block 29,86,30,86 --block 57,167,57,168 --block 145,102,145,102
--block X,Z,CX,CZ: anchor and the closed (20401) quarter; CX,CZ = -1,-1 for a 4-arm block.
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--block", action="append", required=True)
    ap.add_argument("--ring400", action="store_true",
                    help="ring of package roundabout 4.0.0: (X,Z) -> (X+1,Z) -> (X+1,Z+1) -> (X,Z+1) (quarter.lanes.json x- -> z+)")
    a = ap.parse_args()
    out = {}
    for p in a.paths:
        steps = json.load(open(p))
        steps = steps.get("pairs", steps)
        res = {}
        for b in a.block:
            x, z, cx, cz = (int(v) for v in b.split(","))
            ring = [(x, z), (x + 1, z), (x + 1, z + 1), (x, z + 1)] if a.ring400 else [(x + 1, z), (x, z), (x, z + 1), (x + 1, z + 1)]
            nxt = {ring[i]: ring[(i + 1) % 4] for i in range(4)}
            cells = set(ring)
            w = ag = cin = cout = touch = 0
            for k, n in steps.items():
                f, t = k.split(">")
                f = tuple(int(v) for v in f.split(","))
                t = tuple(int(v) for v in t.split(","))
                if f in cells or t in cells:
                    touch += n
                if f in cells and t in cells:
                    if nxt[f] == t:
                        w += n
                    elif nxt[t] == f:
                        ag += n
                if (cx, cz) != (-1, -1):
                    if f == (cx, cz) and t not in cells:
                        cout += n
                    if t == (cx, cz) and f not in cells:
                        cin += n
            res["%d,%d" % (x, z)] = {"ring_with": w, "ring_against": ag, "closed_out": cout, "closed_in": cin,
                                     "steps_touching": touch}
            print("%-40s block (%d,%d): ring with %d against %d | closed quarter (%d,%d) -> outside %d, outside -> it %d | steps touching block %d"
                  % (p[-40:], x, z, w, ag, cx, cz, cout, cin, touch))
        out[p] = res
    return out


if __name__ == "__main__":
    main()
