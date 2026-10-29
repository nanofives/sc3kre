#!/usr/bin/env python3
r"""hwsc_build.py - the highway S-curve package (task hwyscurve, owner request 2026-10-29: "i need this S curve for
highways", MAIN\verify\hwyscurve\owner_report.png).

The case. Two parallel straight highways drawn one cell apart (half the band) that overlap by L columns leave stock
15149 "Highway Construction" in the overlap: the middle row would hold one band's -a carriageway and the other's +a
carriageway in the same cells, which no stock piece draws. HWAY_GRND_final.txt #6 / #9 / #15 write the 15149 (offline
`netrules explain`, verify/hwyscurve/RESULTS.md). Overlap 1 is already a stock one-column diagonal (11223 / 11224).
This package draws an S over the overlap for L = 2..4: the whole two-cell deck shifts one cell sideways as a straight,
two opposite arcs of radius R turning theta, and a straight (tan(theta / 2) = 1 / L, R = (L / 2) / sin theta:
L 2 -> R 1.25, 53.1 deg; L 3 -> R 2.5, 36.9 deg; L 4 -> R 4.25, 28.1 deg).

Canonical frame (state 0; the block, sc3netmod_hwsc.c, turns it): axis a = world x, cross c = world z, cell (a, c)
covers a..a+1 x c..c+1. Hand 0 (S): band 1 rows c 0 / 1 for a <= L - 1, band 2 rows 1 / 2 for a >= 0. Hand 1 (Z):
band 1 rows 1 / 2, band 2 rows 0 / 1. The footprint is a 0..L-1 x c 0..2 (3L cells, every one a cell the player built).
Every footprint cell is its own piece (no reuse by the S's point symmetry: the curve's dashes are drawn from the arc
length, so a cell turned 180 degrees would not meet its neighbour's dash phase).

Ids (granted 2026-10-29): pieces 28200..28263, lit twins 28300..28363 (piece + 100), lane curve shapes 28400..28599.
Pieces: hand 0 L 2 / 3 / 4 then hand 1 L 2 / 3 / 4, cells in (a, c) order -> 28200..28253.
Base 15051 (plain: a retile re-places them), frame table 15127 + ground_under (the corner cells show ground). Saved
(hwys) as what the stock tiler leaves in each cell: 15149.0 on the shared row and at the two band ends, the plain
straight elsewhere, so a game without the mod loads the city exactly as stock shows it. With the mod the variant
section brings the S back (and the block would rebuild it from the stock layout anyway).

  py -3.12 hwsc_build.py art      <pkg> [--jobs N] [--only ID,...]   paint pieces + lit twins into <pkg>/art/<id>
  py -3.12 hwsc_build.py lanes    <pkg>                              hwsc_<id>.lanes.json (curves 28400..)
  py -3.12 hwsc_build.py check    <pkg>                              compile the lane specs (lanekit), twin check
  py -3.12 hwsc_build.py manifest <pkg>                              <pkg>/manifest.json
  py -3.12 hwsc_build.py preview  <pkg> <out.png> [--zoom 3]         sheet: every (hand, L) assembled with stock lead-ins
Game art never goes in git (examples/*/art is gitignored).
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

ID0, TWIN_OFF, SHAPE0, SHAPE_END = 28200, 100, 28400, 28599
LS = (2, 3, 4)
LEAD = 3                                  # straight lead-in (cells) each side of the S in the painted scene
ART_FROM = 15127
BASE = 15051
SAVE = (15149, 0)


def pieces():
    """{id: (hand, L, a, c)} in id order"""
    out, pid = {}, ID0
    for hand in (0, 1):
        for L in LS:
            for a in range(L):
                for c in range(3):
                    out[pid] = (hand, L, a, c)
                    pid += 1
    return out


# a band's lower row (c) drives +a, its upper row -a; the stock straight for that heading at turn k (hwpaint: 15051.2
# drives +x, 15051.0 -x, 73.0 +z, 73.2 -z; turn 1 takes +a to +z)
LOW_ROW = ((15051, 2), (73, 0), (15051, 0), (73, 2))
HIGH_ROW = ((15051, 0), (73, 2), (15051, 2), (73, 0))


def saved_as(hand, L, a, c, k):
    """(id, state) a footprint cell saves as at turn k: what the stock tiler leaves there (measured 2026-10-29, overlap
    2 and 3): 15149.0 on the shared row, on band 1's other row at its last column and on band 2's other row at its
    first; the plain straight of the band elsewhere. A game without the mod then loads exactly the stock layout"""
    b1, b2 = bands(hand)
    if c == 1 or (c in b1 and a == L - 1) or (c in b2 and a == 0):
        return SAVE
    if c in b1:
        return (LOW_ROW if c == b1[0] else HIGH_ROW)[k]
    return (LOW_ROW if c == b2[0] else HIGH_ROW)[k]


def bands(hand):
    """(band 1 rows, band 2 rows) in the canonical frame"""
    return ((0, 1), (1, 2)) if hand == 0 else ((1, 2), (0, 1))


def s_path(hand, L):
    """the median of the two-cell deck: band 1's median (c 1 for S, 2 for Z) to band 2's, over a 0..L"""
    from netmod import hwpaint as HP
    th = 2.0 * math.atan(1.0 / L)
    R = (L / 2.0) / math.sin(th)
    c0 = 1.0 if hand == 0 else 2.0
    sg = 1.0 if hand == 0 else -1.0                   # positive sweep turns toward +c (the left of +a)
    p = HP.Path.line((-LEAD, c0), (0.0, c0)).then_arc(R, sg * math.degrees(th)).then_arc(R, -sg * math.degrees(th))
    return p.then_line(LEAD)


def scene(hand, L):
    from netmod import hwpaint as HP
    return HP.Scene(HP.highway(s_path(hand, L)))


def _paint(job):
    pid, twin, out = job
    from netmod import hwpaint as HP
    hand, L, a, c = pieces()[pid]
    sc = scene(hand, L)
    d = os.path.join(out, str(pid + (TWIN_OFF if twin else 0)))
    if twin:
        HP.paint_twin(sc, (a, c), d)
    else:
        HP.paint_cell(sc, (a, c), d)
    return d


def cmd_art(a):
    from multiprocessing import Pool
    only = {int(x) for x in a.only.split(",")} if a.only else None
    jobs = [(pid, tw, os.path.join(a.pkg, "art")) for pid in pieces() for tw in (False, True)
            if not only or pid in only]
    os.makedirs(os.path.join(a.pkg, "art"), exist_ok=True)
    with Pool(a.jobs) as pool:
        for i, d in enumerate(pool.imap_unordered(_paint, jobs)):
            print("[%d/%d] %s PASS" % (i + 1, len(jobs), d), flush=True)
    return 0


def cmd_lanes(a):
    from netmod import hwlanes as HL
    ps = pieces()
    shape, n = SHAPE0, 0
    for hand in (0, 1):
        for L in LS:
            group = {(pa, pc): pid for pid, (h, l_, pa, pc) in ps.items() if h == hand and l_ == L}
            specs, shape = HL.build_cells(scene(hand, L).decks, sorted(group), shape, group, states=(0, 1, 2, 3))
            for cell in sorted(group):
                pid = group[cell]
                spec = specs.get(cell)
                f = os.path.join(a.pkg, "hwsc_%d.lanes.json" % pid)
                if spec is None:                          # the deck only grazes the cell: no lane, no turn
                    if os.path.isfile(f):
                        os.remove(f)
                    print(pid, "hand", hand, "L", L, cell, "no lane")
                    continue
                json.dump(spec, open(f, "w", encoding="utf-8"), indent=1)
                print(pid, "hand", hand, "L", L, cell, "%d lanes" % len(spec["vehicle"]["lanes"]),
                      [(ln["from"], ln["to"]) for ln in spec["vehicle"]["lanes"]])
                n += 1
    if shape - 1 > SHAPE_END:
        raise SystemExit("lane curves need shapes up to %d, the grant ends at %d" % (shape - 1, SHAPE_END))
    print("lanes: %d specs, curve shapes %d..%d" % (n, SHAPE0, shape - 1))
    return 0


def cmd_check(a):
    from netmod import hwlanes as HL
    from netmod import lanekit as LK
    from netmod import hwpaint as HP
    bad = 0
    for pid, (hand, L, pa, pc) in pieces().items():
        if not os.path.isfile(os.path.join(a.pkg, "hwsc_%d.lanes.json" % pid)):
            print(pid, "hand", hand, "L", L, (pa, pc), "no lane")
            continue
        spec = json.load(open(os.path.join(a.pkg, "hwsc_%d.lanes.json" % pid), encoding="utf-8"))
        masks, warns = HL.compile_check(spec)
        sides = sorted({(min(LK.boundary_sides(ln["from"][0], ln["from"][2])),
                         min(LK.boundary_sides(ln["to"][0], ln["to"][2]))) for ln in spec["vehicle"]["lanes"]})
        print(pid, "hand", hand, "L", L, (pa, pc), "turns", sides, "masks", masks)
        for w in warns:
            print("   ", w)
        bad += len(warns)
        tw = os.path.join(a.pkg, "art", str(pid + TWIN_OFF))
        if hasattr(HP, "twin_check") and os.path.isdir(tw):
            r = HP.twin_check(os.path.join(a.pkg, "art", str(pid)), tw)
            print("    twin", r)
    return 1 if bad else 0


def cmd_manifest(a):
    variants, lanes, connects, lines = [], [], [], []
    ps = pieces()
    for pid, (hand, L, pa, pc) in ps.items():
        nm = "Highway S-curve %s%d %d,%d" % ("S" if hand == 0 else "Z", L, pa, pc)
        for vid, extra in ((pid, ""), (pid + TWIN_OFF, " (lit twin of %d)" % pid)):
            variants.append({"id": vid, "base": BASE, "network": "HWAY",
                             "name": {"*": nm + extra, "ENGLISH": "Highway"},
                             "art": {"from": ART_FROM, "png_dir": "art/%d" % vid, "ground_under": True},
                             "trblkatt": "copy_base"})
            if os.path.isfile(os.path.join(a.pkg, "hwsc_%d.lanes.json" % pid)):
                lanes.append({"piece": vid, "spec": "hwsc_%d.lanes.json" % pid})           # turn matrix: auto
            else:
                connects.append({"piece": vid, "road": {"low": [], "high": []}})          # no lane: no turn
    for pid in ps:
        lines.append("hwyp %d 0" % pid)
    for pid, (hand, L, pa, pc) in ps.items():
        lines.append("hwys %d %s" % (pid, " ".join("%d %d" % saved_as(hand, L, pa, pc, k) for k in range(4))))
    for pid in ps:
        lines.append("hwyl %d %d" % (pid, pid + TWIN_OFF))
    for pid, (hand, L, pa, pc) in ps.items():
        lines.append("hwsc %d %d %d %d %d" % (hand, L, pa, pc, pid))
    man = {
        "netpack": 1, "name": "highway_scurve", "version": "1.0.0", "author": "sc3kre",
        "description": "Task hwyscurve: two parallel highways drawn one cell apart that overlap by 2 to 4 cells "
                       "become an S-curve: the highway shifts sideways over the overlap and keeps going, both "
                       "directions drivable, instead of Highway Construction tiles. Flat ground only; saved as the "
                       "stock Highway Construction tiles, so a game without the mod loads the city as stock shows it.",
        "game": {"Apps/SIMNTWRK.DLL": "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"},
        "variants": variants, "lanes": lanes, "connects": connects, "highway_lines": lines,
    }
    json.dump(man, open(os.path.join(a.pkg, "manifest.json"), "w", encoding="utf-8"), indent=1)
    print("manifest:", len(variants), "variants,", len(lanes), "lane specs,", len(lines), "highway lines")
    return 0


def cmd_preview(a):
    """each (hand, L): the package's own art at its cells plus stock 15051 lead-ins, at one zoom, rotation 0"""
    from PIL import Image
    from netmod import netart as NA
    ps = pieces()
    tiles = []
    for hand in (0, 1):
        for L in LS:
            b1, b2 = bands(hand)
            layout = []
            for pid, (h, l_, pa, pc) in ps.items():
                if h == hand and l_ == L:
                    layout.append({"at": [-pa, pc], "dir": os.path.join(a.pkg, "art", str(pid)), "slot": 0})
            for k in range(1, LEAD + 1):
                for c in b1:      # stock straight along x: low row drives +x (15051.2), high row -x (15051.0)
                    layout.append({"at": [k, c], "piece": 15051, "slot": 2 if c == b1[0] else 0})
                for c in b2:
                    layout.append({"at": [-(L - 1 + k), c], "piece": 15051, "slot": 2 if c == b2[0] else 0})
            tiles.append(NA.preview({"cells": layout}, None, zooms=[a.zoom], rots=[0])[(a.zoom, 0)])
    W = max(t.width for t in tiles)
    H = sum(t.height + 8 for t in tiles)
    sheet = Image.new("RGBA", (W, H), (40, 60, 40, 255))
    y = 0
    for t in tiles:
        sheet.alpha_composite(t.convert("RGBA"), (0, y))
        y += t.height + 8
    sheet.save(a.out)
    print("preview", a.out, sheet.size)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hwsc_build.py")
    ap.add_argument("cmd", choices=("art", "lanes", "check", "manifest", "preview"))
    ap.add_argument("pkg")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--only", default="")
    ap.add_argument("--zoom", type=int, default=3)
    a = ap.parse_args(argv)
    return {"art": cmd_art, "lanes": cmd_lanes, "check": cmd_check, "manifest": cmd_manifest,
            "preview": cmd_preview}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
