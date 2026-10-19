#!/usr/bin/env python3
r"""hwave_build.py - art and lanes of the highway <-> avenue transition package (task hwave, 2026-10-19).

  py -3.12 hwave_build.py art   <package_dir>    paint the four pieces into <package_dir>/art/<id> (game art, gitignored)
  py -3.12 hwave_build.py lanes <package_dir>    write hwave_<id>.lanes.json (lanes, new curves 23400.., turn matrix auto)
  py -3.12 hwave_build.py check <package_dir>    compile the lane specs with lanekit, print the turn matrices

World frame of state 0 (hwave_paint.py): highway at z <= 29 (cap row z 29), avenue U-turn row z 30, avenue from z 31;
entry carriageway x 46 (drives -z, 73.2), exit carriageway x 47 (drives +z, 73.0).

Lanes (lane units, 255 per cell). Highway side: stock 73.0 lanes x 145 (outer) / 61 (inner) at y 1024, 73.2 at
110 (outer) / 194 (inner). Avenue side: stock 11204 carries both directions in each cell (`lanekit show 11204`): along
z, +z at x 175 and -z at x 80, in both cells, y 0. So the exit's outer lane goes on in its own cell (47 + 145 ->
47 + 175), its inner lane crosses to the entry cell's +z lane (47 + 61 -> 46 + 175), and the avenue's two -z lanes climb
onto the entry carriageway (46 + 80 -> 46 + 110, 47 + 80 -> 46 + 194). The crossings sit in the ground row (z 30..31), half a cell apart.
Heights follow the art's deck: H at z 29, H/2 (y 512) at z 30, 0 at z 31, eased.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import hwave_paint as WP  # noqa: E402
from netmod import hwpaint as HP  # noqa: E402
from netmod import hwlanes as HL  # noqa: E402

SHAPE0 = 23400                    # this stream's curve shapes 23400..23599 (protocol section 5, wave 2)
EXIT_IN, EXIT_OUT = 61 / 255.0, 145 / 255.0
ENTRY_OUT, ENTRY_IN = 110 / 255.0, 194 / 255.0
AVE_UP, AVE_DOWN = 175 / 255.0, 80 / 255.0          # 11204 along z: +z lane, -z lane


# Turn matrices of the ground pieces (low half; the high half is its transpose): the lanes' turns minus the two that
# only the crossover lanes add when read as U-turns (21602 z- -> x-, 21603 x+ -> z+). With them the router, which keeps
# the LAST gated exit in the order z-, x-, z+, x+ [SimTransit 0x10007881], sent a trip entering 21602 from the avenue
# back onto the avenue through 21603 (hwave_probe.py walk, 2026-10-19). The animated cars still follow the lanes.
CONNECTS = {21602: [["z-", "z+"], ["z+", "x-"]], 21603: [["z+", "z-"], ["x+", "z-"]]}


def height_z(z):
    """the art's deck height at world z (hwave_paint.scene: H to z 29, eased to 0 at z 31)"""
    t = np.clip((np.asarray(z, dtype=float) - WP.Z_TOP) / (WP.Z_GROUND - WP.Z_TOP), 0.0, 1.0)
    return HP.H * (1.0 - t * t * (3.0 - 2.0 * t))


def lane(points):
    """a one-lane deck along the polyline `points` (direction of travel), height from world z"""
    segs = [HP.Line(points[i], points[i + 1]) for i in range(len(points) - 1)]
    path = HP.Path(segs)

    def h(s):
        s = np.atleast_1d(np.asarray(s, dtype=float))
        return np.array([height_z(path.at(float(v))[0][1]) for v in s])
    return HP.ramp_deck(path, height=h, width=0.2)


def smooth(x0, x1, z0, z1, n=8):
    """points from (x0, z0) to (x1, z1) on a smoothstep across, n segments"""
    out = []
    for k in range(n + 1):
        t = k / float(n)
        out.append((x0 + (x1 - x0) * t * t * (3 - 2 * t), z0 + (z1 - z0) * t))
    return out


def lane_decks():
    """the four lanes; the two that change cell cross the cell line x 47 half a cell apart (z ~30.23 and ~30.73), so
    their border nodes stay apart (the street sim matches nodes in 72-unit buckets)"""
    zt, zg = WP.Z_TOP, WP.Z_GROUND
    zm = (zt + zg) / 2.0
    ex_o, ex_i = 47 + EXIT_OUT, 47 + EXIT_IN
    en_o, en_i = 46 + ENTRY_OUT, 46 + ENTRY_IN
    return [
        lane([(ex_o, zt - 0.5)] + smooth(ex_o, 47 + AVE_UP, zm, zg) + [(47 + AVE_UP, zg + 0.5)]),
        lane([(ex_i, zt - 0.5)] + smooth(ex_i, 46 + AVE_UP, zm, zm + 0.5) + [(46 + AVE_UP, zg + 0.5)]),
        lane([(46 + AVE_DOWN, zg + 0.5)] + smooth(46 + AVE_DOWN, en_o, zg, zm) + [(en_o, zt - 0.5)]),
        lane([(47 + AVE_DOWN, zg + 0.5)] + smooth(47 + AVE_DOWN, en_i, zg, zm + 0.5) + [(en_i, zt - 0.5)]),
    ]


def cmd_art(a):
    sc = WP.scene()
    for cell, pid in sorted(WP.CELLS.items(), key=lambda kv: kv[1]):
        d = os.path.join(a.pkg, "art", str(pid))
        HP.paint_cell(sc, cell, d)
        print("art", pid, "<-", cell, d)
    return 0


def cmd_lanes(a):
    specs, nxt = HL.build_cells(lane_decks(), list(WP.CELLS), SHAPE0, WP.CELLS, states=(0, 1, 2, 3))
    if nxt > 23600:
        raise SystemExit("curve shapes past this stream's range: %d" % nxt)
    for cell, spec in sorted(specs.items(), key=lambda kv: kv[1]["piece"]):
        if spec["piece"] in CONNECTS:
            spec["connects"] = {"road": CONNECTS[spec["piece"]]}
        p = os.path.join(a.pkg, "hwave_%d.lanes.json" % spec["piece"])
        json.dump(spec, open(p, "w"), indent=1)
        print(spec["piece"], cell, "%d lanes" % len(spec["vehicle"]["lanes"]),
              [(l["from"], l["to"]) for l in spec["vehicle"]["lanes"]])
    print("curve shapes %d..%d" % (SHAPE0, nxt - 1))
    return 0


def cmd_check(a):
    bad = 0
    for pid in sorted(WP.CELLS.values()):
        spec = json.load(open(os.path.join(a.pkg, "hwave_%d.lanes.json" % pid)))
        masks, warns = HL.compile_check(spec)
        print(pid, "masks", masks)
        for w in warns:
            print("   ", w)
        bad += len(warns)
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hwave_build.py")
    ap.add_argument("cmd", choices=("art", "lanes", "check"))
    ap.add_argument("pkg")
    a = ap.parse_args(argv)
    return {"art": cmd_art, "lanes": cmd_lanes, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
