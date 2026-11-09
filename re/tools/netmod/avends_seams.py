#!/usr/bin/env python3
r"""avends_seams.py - read-only lane seam check over a window of LIVE cells (task avends, 2026-11-09).

Every pair of side-by-side road cells in the window where at least one holds a variant (id >= 20000) is checked with
avlanes.check (every exit of one piece meets an entry of the other at the same position and direction), against the
merged lane data of a tree's netmod overlay, per language.

  SC3_PID=<pid> py -3.12 -m netmod.avends_seams X0,Z0,X1,Z1 [--tree DIR] [--lang ENGLISH --lang English-UK] [-v]
Exit 1 when any seam has a problem.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from netmod import avlanes as AL, lanekit as LK      # noqa: E402

TREE = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tree"))
SIDE = {(1, 0): "E", (0, 1): "S"}


def live(w):
    out = subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py"), "cells", w], capture_output=True,
                         text=True).stdout
    g = {}
    for ln in out.splitlines():
        if ln.startswith("{"):
            c = json.loads(ln)
            if "piece" in c:
                g[(c["x"], c["z"])] = (c["piece"], c["state"])
    if not g:
        raise SystemExit("no live cells read: %s" % out[:300])
    return g


def main(argv):
    a = list(argv)
    langs = []
    while "--lang" in a:
        i = a.index("--lang"); langs.append(a[i + 1]); del a[i:i + 2]
    tree = TREE
    if "--tree" in a:
        i = a.index("--tree"); tree = a[i + 1]; del a[i:i + 2]
    verbose = "-v" in a
    w = [x for x in a if not x.startswith("-")][0]
    langs = langs or ["ENGLISH", "English-UK"]
    game = LK.Game(os.path.join(tree, "mods", "netmod", "overlay"))
    road = set(int(v) for v in __import__("re").findall(r"\d+", open(os.path.join(
        tree, "Apps", "Res", "TilingRules", "ROAD_GRND_Set.txt")).read()))
    g = live(w)
    bad = 0
    for lang in langs:
        n = probs = 0
        for (x, z), (pa, sa) in sorted(g.items()):
            for (dx, dz), side in SIDE.items():
                q = g.get((x + dx, z + dz))
                if not q:
                    continue
                pb, sb = q
                if pa < 20000 and pb < 20000:
                    continue
                if not ((pa in road or pa >= 20000) and (pb in road or pb >= 20000)):
                    continue
                try:
                    pr = AL.check(pa, sa, pb, sb, side, game=game, lang=lang)
                except SystemExit as e:
                    pr = ["no record: %s" % e]
                n += 1
                if pr:
                    probs += len(pr)
                    for p in pr:
                        print("  %s (%d,%d)%s %d.%d | %d.%d: %s" % (lang, x, z, side, pa, sa, pb, sb, p))
                elif verbose:
                    print("  %s (%d,%d)%s %d.%d | %d.%d ok" % (lang, x, z, side, pa, sa, pb, sb))
        print("%s: %d seams checked, %d problem(s)" % (lang, n, probs))
        if lang == "ENGLISH":
            bad += probs
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
