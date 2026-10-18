#!/usr/bin/env python3
r"""hwtraffic_edit.py - the one edit of the hwtraffic before/after test, made the same way in both games (2026-10-18).

SC3_PID = the game, SC3_LAB_DIR = the folder of rb_lab's camera state. Sim paused, camera already on the site with
`rb_lab.py cam 50,15 3 0` (check the printed state). Berlin's west trunk (straight highway along x, rows 12 / 13) has
a power line on row 10 that the Highway tool will not cross with a diagonal (measured: the drag stopped at (45, 9) and
left a 15149). So the power line is first routed around the diagonal's north end, then the diagonal is dragged:

  1. Wires (0x10005001): (43,8) -> (47,8), (43,10) -> (43,8), (47,10) -> (47,8)   the detour, while the line still runs
  2. Demolish (44,10), (45,10), (46,10)                                         the three wire cells under the diagonal
  3. Highway (45,10) -> (58,23)                                                 the diagonal (its cap lands on row 9)

  py -3.12 hwtraffic_edit.py [--alt 32]

--site seoul (second pair, 2026-10-18): Seoul's highway on rows 108 / 109 runs to the east map edge with empty flat
land on both sides (x 231..254), so the edit is the diagonal alone: Highway (238,102) -> (251,115), crossing at
O = (245,109) (camera `rb_lab.py cam 245,109 3 0`, --alt 73). The south arm stops at row 115: water from (253,116).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rb_lab  # noqa: E402

WIRES, HIGHWAY = 0x10005001, 0x10004301


def drag(cmd, a, b, alt):
    rb_lab.CMD["road"] = cmd
    rb_lab.main(["rb_lab.py", "road", "%d,%d" % a, "%d,%d" % b, "--alt", str(alt)])


def main(argv):
    alt = int(argv[argv.index("--alt") + 1]) if "--alt" in argv else 32
    if "--site" in argv and argv[argv.index("--site") + 1] == "seoul":
        drag(HIGHWAY, (238, 102), (251, 115), alt)
        return 0
    for a, b in (((43, 8), (47, 8)), ((43, 10), (43, 8)), ((47, 10), (47, 8))):
        drag(WIRES, a, b, alt)
    for c in ((44, 10), (45, 10), (46, 10)):
        rb_lab.main(["rb_lab.py", "demolish", "%d,%d" % c, "--alt", str(alt)])
    drag(HIGHWAY, (45, 10), (58, 23), alt)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
