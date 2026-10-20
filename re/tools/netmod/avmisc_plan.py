#!/usr/bin/env python3
r"""avmisc_plan.py - plan check for the big roundabout's avenue arms with one-way halves (task avmisc, 2026-10-19).

Rule (verify/avlanes/PLAN.md 2): an 11204 half of state s has its median on avenue side s (N E S W = 0 1 2 3) and
travels toward avenue side (s - 1) % 4. bigrbt writes the arm cell of an avenue arm as (11204, state) (bigrbt.wanted).
This script derives, for every block placement of an avenue arm, whether each arm half runs INTO the block or OUT of
it, and checks it against what the canonical piece frames need: side 20603 (code 2) in, side 20604 (code 3) out,
corner local x+ arm (kE = 2) out, corner local z- arm (kN = 2) in.

  py -3.12 avmisc_plan.py check
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(HERE, ".."))

from netmod import bigrbt as B  # noqa: E402

AVE_DIR = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}     # avenue side -> world step (N = z-, E = x+, S = z+, W = x-)


def travel(state):
    return AVE_DIR[(state - 1) % 4]


def check():
    bad = 0
    rows = 0
    for s in range(4):                                  # world side of the block carrying the avenue
        for pair in ((0, 1), (1, 2)):                   # which two of the three arm cells
            road = {(x, z) for x in range(3) for z in range(3)}
            dx, dz = B.OUT[s]
            for i in pair:
                cx, cz = B.SIDE_CELLS[s][i]
                for n in range(1, 4):
                    road.add((cx + dx * n, cz + dz * n))
            arms, why = B.check(road, {c: 29 for c in road}, 0, 0)
            assert arms is not None, why
            want, extra = B.wanted(arms)
            for ((cx, cz), side), (kind, partner) in sorted(arms.items()):
                t, st = B.cell_state((cx, cz))
                ex = B.OUT[side]
                arm_cell = (cx + ex[0], cz + ex[1])
                _pid, ast = extra[arm_cell]
                tv = travel(ast)
                into = tv == (-ex[0], -ex[1])
                piece, pst = want[(cx, cz)]
                if t == "side":
                    need_in = piece == B.SIDE_IDS[2]
                else:
                    k = piece - B.CORNER0
                    kN, kE = k // 3, k % 3
                    local = (side - pst) % 4                # the arm's side in the piece's own frame: 1 = z-, 2 = x+
                    need_in = local == 1
                ok = into == need_in
                rows += 1
                bad += not ok
                print("%s side %d cells %s: block cell %s %s %d.%d arm half %s %s -> piece needs %s  %s" % (
                    "ok " if ok else "BAD", s, pair, (cx, cz), t, piece, pst, arm_cell,
                    "in " if into else "out", "in" if need_in else "out", ""))
    print("%d arm halves, %d disagreements" % (rows, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(check() if sys.argv[1:] == ["check"] else print(__doc__))
