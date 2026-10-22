#!/usr/bin/env python3
r"""hwave_build.py - art and lanes of the highway <-> avenue transition package (task hwave, 2026-10-19).

  py -3.12 hwave_build.py art   <package_dir>    paint the four pieces into <package_dir>/art/<id> (game art, gitignored)
  py -3.12 hwave_build.py lanes <package_dir>    write hwave_<id>.lanes.json (lanes, new curves 23400.., turn matrix auto)
  py -3.12 hwave_build.py check <package_dir>    compile the lane specs with lanekit, print the turn matrices
  py -3.12 hwave_build.py twart <package_dir>    task hwlight: art of the LIT TWINS (lit_twins.json) of every piece, the
                                                 scene turned one state (the block writes each set at all four turns;
                                                 at odd turns the twin goes in, so the walls get the stock shading).
                                                 Run after art / dart / sart, then hwlight.py manifest + check

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


# ---------------------------------------------------------------------------------------------- straight lanes
# task avmisc (avenue lane rework): where the avenue is one-way per half (avcore: AVENUE_LANES.md 2) the ground row has
# no lane swap: every highway lane goes on straight into the avenue lane of its own half. Exit carriageway (cell 47,
# drives +z) 61 -> 80 (inner), 145 -> 175 (outer); entry carriageway (cell 46, drives -z) the avenue's 80 -> 110
# (outer) and 175 -> 194 (inner). Only the ground row differs: pieces 21850 / 21851 replace 21602 / 21603 (same art,
# same bases) when the avenue band is converted; the cap row 21600 / 21601 is unchanged.
SHAPE_S = 23950                   # avmisc hwave straight ground row: shapes 23950..23999 (23900..23949 = rbt9); reverse shapes +4: 23954..23957
S_CELLS = {(47, 30): 21850, (46, 30): 21851}
S_CONNECTS = {21850: [["z-", "z+"]], 21851: [["z+", "z-"]]}
ART_COPY = {21602: 21850, 21603: 21851}


def straight_decks():
    zt, zg = WP.Z_TOP, WP.Z_GROUND
    zm = (zt + zg) / 2.0
    out = []
    for a, b in ((47 + EXIT_IN, 47 + 80 / 255.0), (47 + EXIT_OUT, 47 + AVE_UP)):          # exit, drives +z
        out.append(lane([(a, zt - 0.5)] + smooth(a, b, zm, zg) + [(b, zg + 0.5)]))
    for b, a in ((46 + AVE_DOWN, 46 + ENTRY_OUT), (46 + AVE_UP, 46 + ENTRY_IN)):           # entry, drives -z
        out.append(lane([(b, zg + 0.5)] + smooth(b, a, zg, zm) + [(a, zt - 0.5)]))
    return out


def cmd_sart(a):
    import shutil
    for src, dst in ART_COPY.items():
        s, d = os.path.join(a.pkg, "art", str(src)), os.path.join(a.pkg, "art", str(dst))
        if os.path.isdir(d):
            shutil.rmtree(d)
        shutil.copytree(s, d)
        print("art", dst, "<-", s)
    return 0


def cmd_slanes(a):
    specs, nxt = HL.build_cells(straight_decks(), list(S_CELLS), SHAPE_S, S_CELLS, states=(0, 1, 2, 3))
    if nxt + (nxt - SHAPE_S) > 24000:
        raise SystemExit("curve shapes past this stream's range: %d" % nxt)
    n = nxt - SHAPE_S
    for cell, spec in sorted(specs.items(), key=lambda kv: kv[1]["piece"]):
        # avcore's rule: no path keys (curves found by end points per language); English-UK's curve file holds every
        # curve reversed, so each curve also gets a reverse shape whose UK copy is the forward lane
        for ln in spec["vehicle"]["lanes"]:
            ln.pop("path")
        spec["curves"] += [{"shape": c["shape"] + n, "pts": [list(q) for q in reversed(c["pts"])]} for c in spec["curves"]]
        spec["connects"] = {"road": S_CONNECTS[spec["piece"]]}
        spec["mirror_uk"] = False
        p = os.path.join(a.pkg, "hwave_%d.lanes.json" % spec["piece"])
        json.dump(spec, open(p, "w"), indent=1)
        print(spec["piece"], cell, "%d lanes" % len(spec["vehicle"]["lanes"]),
              [(l["from"], l["to"]) for l in spec["vehicle"]["lanes"]])
    print("curve shapes %d..%d" % (SHAPE_S, nxt - 1))
    return 0


def cmd_scheck(a):
    return cmd_check(a, S_CELLS.values())


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


def cmd_check(a, pieces=None):
    bad = 0
    for pid in sorted(pieces or WP.CELLS.values()):
        spec = json.load(open(os.path.join(a.pkg, "hwave_%d.lanes.json" % pid)))
        masks, warns = HL.compile_check(spec)
        print(pid, "masks", masks)
        for w in warns:
            print("   ", w)
        bad += len(warns)
    return 1 if bad else 0


# ================================================================================================ diagonal (phase 2)
# hwave_paint.py's diagonal frame (state 0): band middle line x - z = 0 (p = x - z), cap cell (10, 10), q = x + z.
# Highway band lanes (hwlanes DIAG_LANES, cells across from the median, p = across * sqrt 2): exit carriageway (high p,
# drives +x +z) outer 0.396 / inner 0.170, entry (low p) the same mirrored. DAV avenue (each strip = stock 35, both
# directions): lane points on the borders of the j+3 cells (lanekit show 35, states 0 / 2 for the high / low cell):
#   high strip, cell (12, 11) x- side: in (away from the highway) at z 80, out at z 175
#   low strip,  cell (11, 12) z- side: in at x 175, out at x 80
# So the exit's outer lane goes on in the high strip, its inner lane crosses to the low strip, and the avenue's two
# outgoing lanes climb onto the entry carriageway (the high strip's crossing). The two crossings use different cells:
# the exit's inner lane crosses through 21608 / 21609, the high strip's outgoing lane stays high through 21607 and
# crosses in the cap 21606, so no two lane points share a cell border within the street sim's 72-unit buckets.
SHAPE_D = 23420                   # this phase's curve shapes (stream range 23400..23599)
CONNECTS_D = {}                   # filled after the router check (hwave_probe.py walk)


def d_lane(points):
    segs = [HP.Line(points[i], points[i + 1]) for i in range(len(points) - 1)]
    path = HP.Path(segs)

    def h(s):
        s = np.atleast_1d(np.asarray(s, dtype=float))
        out = []
        for v in s:
            p, _ = path.at(float(v))
            out.append(WP.d_height(p[0] + p[1]))
        return np.array(out)
    return HP.ramp_deck(path, height=h, width=0.2)


def _pq(p, q):
    return ((q + p) / 2.0, (q - p) / 2.0)


def _across(p0, p1, q0, q1, n=8):
    out = []
    for k in range(n + 1):
        t = k / float(n)
        out.append(_pq(p0 + (p1 - p0) * t * t * (3 - 2 * t), q0 + (q1 - q0) * t))
    return out


def d_lane_decks():
    r2 = 2 ** 0.5
    ex_o, ex_i, en_o, en_i = 0.396 * r2, 0.170 * r2, -0.396 * r2, -0.170 * r2
    hi_in, hi_out = (12.0, 11.0 + 80 / 255.0), (12.0, 11.0 + 175 / 255.0)
    lo_in, lo_out = (11.0 + 175 / 255.0, 12.0), (11.0 + 80 / 255.0, 12.0)

    def p_of(pt):
        return pt[0] - pt[1]

    def q_of(pt):
        return pt[0] + pt[1]

    def beyond(pt, k):                      # a little further along the band, into the DAV cell (+x+z / -x-z)
        return (pt[0] + k * 0.3, pt[1] + k * 0.3)
    q0 = 14.0
    return [
        # exit outer -> high strip in
        d_lane([_pq(ex_o, q0)] + _across(ex_o, p_of(hi_in), 20.5, q_of(hi_in)) + [beyond(hi_in, 1)]),
        # exit inner -> low strip in (crosses the median early)
        d_lane([_pq(ex_i, q0)] + _across(ex_i, p_of(lo_in), 19.8, 22.0) + [lo_in, beyond(lo_in, 1)]),
        # low strip out -> entry outer
        d_lane([beyond(lo_out, 1), lo_out] + _across(p_of(lo_out), en_o, q_of(lo_out), 20.5) + [_pq(en_o, q0)]),
        # high strip out -> entry inner (crosses the median late)
        d_lane([beyond(hi_out, 1), hi_out] + _across(p_of(hi_out), en_i, 21.4, 20.1) + [_pq(en_i, q0)]),
    ]


def cmd_dart(a):
    sc = WP.diag_scene()
    for cell, pid in sorted(WP.DCELLS.items(), key=lambda kv: kv[1]):
        d = os.path.join(a.pkg, "art", str(pid))
        WP.diag_paint_cell(sc, cell, d)
        print("art", pid, "<-", cell, d)
    return 0


def cmd_dlanes(a):
    specs, nxt = HL.build_cells(d_lane_decks(), list(WP.DCELLS), SHAPE_D, WP.DCELLS, states=(0, 1, 2, 3))
    if nxt > 23600:
        raise SystemExit("curve shapes past this stream's range: %d" % nxt)
    for cell, spec in sorted(specs.items(), key=lambda kv: kv[1]["piece"]):
        if spec["piece"] in CONNECTS_D:
            spec["connects"] = {"road": CONNECTS_D[spec["piece"]]}
        p = os.path.join(a.pkg, "hwave_%d.lanes.json" % spec["piece"])
        json.dump(spec, open(p, "w"), indent=1)
        print(spec["piece"], cell, "%d lanes" % len(spec["vehicle"]["lanes"]),
              [(l["from"], l["to"]) for l in spec["vehicle"]["lanes"]])
    missing = sorted(set(WP.DCELLS.values()) - {s["piece"] for s in specs.values()})
    print("curve shapes %d..%d%s" % (SHAPE_D, nxt - 1, ("  NO LANES: %s" % missing) if missing else ""))
    return 0


def cmd_dcheck(a):
    return cmd_check(a, WP.DCELLS.values())


def cmd_twart(a):
    """task hwlight: the lit twins. Straight set: hwpaint.paint_twin of the same scene; the one-way ground row copies
    the crossover row's twins (as sart copies the art); diagonal set: the deck from the turned scene, DAV's flat parts
    drawn over it as diag_render draws them for the piece itself"""
    import shutil
    import hwlight
    tw = hwlight.twins(a.pkg)
    sc = WP.scene()
    for cell, pid in sorted(WP.CELLS.items(), key=lambda kv: kv[1]):
        d = os.path.join(a.pkg, "art", str(tw[pid]))
        HP.paint_twin(sc, cell, d)
        print("twin art", tw[pid], "of", pid, "<-", cell, d)
    for src, dst in ART_COPY.items():
        s, d = os.path.join(a.pkg, "art", str(tw[src])), os.path.join(a.pkg, "art", str(tw[dst]))
        if os.path.isdir(d):
            shutil.rmtree(d)
        shutil.copytree(s, d)
        print("twin art", tw[dst], "of", dst, "<-", s)
    dsc = WP.diag_scene()
    for cell, pid in sorted(WP.DCELLS.items(), key=lambda kv: kv[1]):
        d = os.path.join(a.pkg, "art", str(tw[pid]))

        def render(st, ct, z, g, cell=cell):
            return WP.diag_render(dsc, cell, z, (g + 1) % 4, base=HP.render_cell(st, ct, z, g))
        HP.paint_twin(dsc, cell, d, render=render)
        print("twin art", tw[pid], "of", pid, "<-", cell, d)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hwave_build.py")
    ap.add_argument("cmd", choices=("art", "lanes", "check", "dart", "dlanes", "dcheck", "sart", "slanes", "scheck",
                                    "twart"))
    ap.add_argument("pkg")
    a = ap.parse_args(argv)
    return {"art": cmd_art, "lanes": cmd_lanes, "check": cmd_check, "dart": cmd_dart, "dlanes": cmd_dlanes,
            "dcheck": cmd_dcheck, "sart": cmd_sart, "slanes": cmd_slanes, "scheck": cmd_scheck,
            "twart": cmd_twart}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
