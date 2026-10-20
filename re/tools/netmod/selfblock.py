#!/usr/bin/env python3
r"""selfblock.py - offline check of the street car's entry test against a lane spec (task avdiag, 2026-10-20).

The game lets a car onto a lane edge only when no edge in that edge's intersect list holds a car
(cSSStrtSimTrBlock::EnterVehicle FUN_10016520, rule "trblock+8[i] != 0" over edge+0x2c..0x30) and the asking car
is not excluded. The list is built once per lane graph from the edges' straight CHORDS (FUN_1001ff93 ->
FUN_10020063 -> FUN_10020904 / FUN_100167fe): two chords intersect unless they share their START point or have
equal slopes; otherwise the infinite lines' crossing x must lie inside both chords' x-ranges, inclusive. A car keeps
its previous edge until its tail leaves it, so at an INTERIOR node (inside the cell) the edge it arrives on is still
occupied by itself: when that edge is in the next edge's list, the car never gets in and is removed after the
40,000,000-unit wait (0x1001d553). [CONFIRMED @ STRTSIM 0x10016520, 0x1001ff93, 0x100167fe, LAB_1001d4f0; the release
timing rests on the Linux build's MoveToPointMoveDist, UNCERTAIN on Windows]

  py -3.12 selfblock.py SPEC.lanes.json [...]      prints every (edge in -> edge out) at an interior node that blocks
Exit 1 when any spec has one.
"""
import json
import sys


def edges_of(spec):
    out = []
    for ln in spec["vehicle"]["lanes"]:
        pts = [tuple(ln["from"])] + [tuple(p) for p in ln.get("via", [])] + [tuple(ln["to"])]
        for a, b in zip(pts, pts[1:]):
            out.append((a, b))
    return out


def _slope(a, b):
    dx = b[0] - a[0]
    return None if dx == 0 else (b[1] - a[1]) / dx


def intersects(e1, e2):
    """FUN_10020904 / FUN_100167fe on two chords (x, z); flat lanes, so the height test always passes"""
    (a1, b1), (a2, b2) = e1, e2
    if a1 == a2:
        return False
    s1, s2 = _slope(a1, b1), _slope(a2, b2)
    if s1 == s2:
        return False
    if s1 is None:
        x = a1[0]
    elif s2 is None:
        x = a2[0]
    else:
        c1, c2 = a1[1] - s1 * a1[0], a2[1] - s2 * a2[0]
        x = (c2 - c1) / (s1 - s2)
    x = round(x)
    return min(a1[0], b1[0]) <= x <= max(a1[0], b1[0]) and min(a2[0], b2[0]) <= x <= max(a2[0], b2[0])


def on_border(p):
    return p[0] in (0, 255) or p[1] in (0, 255)


def self_blocks(spec):
    E = sorted(set(edges_of(spec)))
    out = []
    for e_in in E:
        n = e_in[1]
        if on_border(n):
            continue
        for e_out in E:
            if e_out[0] == n and e_out != e_in and intersects(e_out, e_in):
                out.append((e_in, e_out))
    return out


def main(argv):
    bad = 0
    for f in argv[1:]:
        hits = self_blocks(json.load(open(f)))
        if hits:
            bad += 1
            print("%s: %d" % (f, len(hits)), " ".join("%s>%s>%s" % (a, b[0], b[1]) for (a, _), b in hits))
    print("%d of %d spec(s) with a self-blocking interior node" % (bad, len(argv) - 1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
