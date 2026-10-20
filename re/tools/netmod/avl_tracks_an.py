#!/usr/bin/env python3
r"""avl_tracks_an.py - per-car check of avcore's one-way cells from hwcars_tracks.py output (task avcore, 2026-10-19).

  py -3.12 -m netmod.avl_tracks_an TRACKS.json GRID.json            (run from re/tools)

For every avcore cell (ids 21700..21749) in the grid: the car visits (entry -> exit direction of each pass through the
cell, at least 1/8 cell of travel), the lateral sample positions (both lanes used?), and the most common cell paths
through avcore cells. A visit against a straight half's travel side is printed as WRONG; bends (21701 / 21726) turn, so
their visits are listed for reading only.
"""
import collections, json, sys


def main(argv):
    T, g = json.load(open(argv[1])), json.load(open(argv[2]))
    mine = {k: v for k, v in g.items() if 21700 <= v[0] <= 21749}
    visits = collections.defaultdict(collections.Counter)
    lat = collections.defaultdict(collections.Counter)
    paths = collections.Counter()
    for s in T["cars"].values():
        cur, start, last, seq = None, None, None, []
        for smp in s + [None]:
            c = None if smp is None else "%d,%d" % (smp[1] >> 8, smp[3] >> 8)
            if smp is not None and c in mine:
                st = mine[c][1] & 3
                along_z = mine[c][0] == 21700 and st in (1, 3)
                lat[c][((smp[1] if along_z else smp[3]) & 255) // 32 * 32] += 1
            if c != cur:
                if cur in mine and start and last:
                    dx, dz = last[1] - start[1], last[3] - start[3]
                    if abs(dx) + abs(dz) >= 32:
                        visits[cur][("E" if dx > 0 else "W") if abs(dx) >= abs(dz) else ("S" if dz > 0 else "N")] += 1
                if c in mine:
                    seq.append(c)
                cur, start = c, smp
            last = smp
        if seq:
            paths[" > ".join(seq)] += 1
    wrong = 0
    for c in sorted(mine, key=lambda k: tuple(map(int, k.split(",")))):
        pid, st = mine[c]
        want = "NESW"[(st + 3) % 4] if pid == 21700 else None
        v = dict(visits[c])
        bad = {d: n for d, n in v.items() if want and d != want}
        wrong += sum(bad.values())
        print("%-8s %d.%d  visits %s%s  lateral %s" % (c, pid, st, v, ("  WRONG %s" % bad) if bad else "",
                                                     dict(sorted(lat[c].items()))))
    print("paths:")
    for p, n in paths.most_common(10):
        print("  %3d  %s" % (n, p))
    print("wrong-way visits on straight halves: %d" % wrong)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
