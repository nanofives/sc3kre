#!/usr/bin/env python3
r"""ct_lanefeas.py - can a car drive a router path on the street-sim lanes? (task cartrips, offline)

For every sampled final path in a cartrips arm (ct_probe.py samples: cells + node types, popped destination first),
walk it in travel order (origin first) and test each road step against the car lanes of the piece under it:

  piece and state at a cell  : the city save's network layer (network_layer.read_networks, surface instance)
  turns a piece's lanes allow: lanekit.lane_turns(TrBlkAtt record id*0x100+state, class 0), sides 0 x-, 1 z-, 2 x+, 3 z+
  a middle step a -> b -> c  : drivable when (side of b facing a, side of b facing c) is one of b's turns

Sides follow STRTSIM's EXIT_STEP (code>>2 = 0 (-1,0), 2 (0,-1), 4 (1,0), 6 (0,1)) and NET_LANES 1.1.
Cell (x, z) of a router node is compared with the save tile (x, y); the share of road nodes with a tile under them is
reported for both (x, y) and the transposed pairing, so a wrong pairing shows.

  py -3.12 ct_lanefeas.py <arm.jsonl> <city.sc3> [--lang ENGLISH] [--json out.json]
Run from re/tools with SC3_GAME_ROOT set to a stock install (lanekit reads Apps\Res).
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import network_layer  # noqa: E402
from netmod import lanekit  # noqa: E402

ROAD = (1, 2, 3)            # router node types a car can drive: road, highway, ramp-road
SIDE = {(-1, 0): 0, (0, -1): 1, (1, 0): 2, (0, 1): 3}


def side_towards(b, a):
    return SIDE.get((a[0] - b[0], a[1] - b[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("city")
    ap.add_argument("--lang", default="ENGLISH")
    ap.add_argument("--json")
    ap.add_argument("--rect", help="x0,z0,x1,z1: count only steps whose middle cell is inside (the vehicle sim rect)")
    ap.add_argument("--skip-avenue-sideways", action="store_true",
                    help="count a step that enters or leaves 11204 sideways as a corridor step, not a failure")
    a = ap.parse_args()
    R = [int(v) for v in a.rect.split(",")] if a.rect else None

    tiles = {}
    for x, y, z, state, piece, props in network_layer.read_networks(a.city)[0][1]:
        tiles[(x, y)] = (piece, state)
    g = lanekit.Game()
    trb = g.trblkatt(a.lang)
    turns_cache = {}

    def turns(piece, state):
        k = (piece, state)
        if k not in turns_cache:
            blob = trb.get(piece * 0x100 + state)
            turns_cache[k] = None if blob is None else lanekit.lane_turns(lanekit.decode(blob), cls=0)
        return turns_cache[k]

    samples = []
    for line in open(a.jsonl, encoding="utf-8"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        for s in r.get("samples") or []:
            if s["n"] <= len(s["p"]):          # whole path stored (MAXN 128)
                samples.append(s)

    st = collections.Counter()
    per_path = []
    bad_pieces = collections.Counter()
    for s in samples:
        path = list(reversed(s["p"]))        # travel order: origin (0x80) first
        road = [(x, z, ty) for x, z, ty in path if ty in ROAD]
        for x, z, ty in road:
            st["road_nodes"] += 1
            st["tile_xy"] += (x, z) in tiles
            st["tile_transposed"] += (z, x) in tiles
        ok_path = True
        steps = 0
        for i in range(1, len(path) - 1):
            pa, pb, pc = path[i - 1], path[i], path[i + 1]
            if pb[2] not in ROAD:
                continue
            b = (pb[0], pb[1])
            if R and not (R[0] <= b[0] <= R[2] and R[1] <= b[1] <= R[3]):
                continue
            s_in = side_towards(b, (pa[0], pa[1]))
            s_out = side_towards(b, (pc[0], pc[1]))
            if pa[2] not in ROAD or pc[2] not in ROAD:
                st["steps_mode_change"] += 1        # lot / station on one side: not a lane-to-lane step
                continue
            if (pa[0], pa[1]) == b or (pc[0], pc[1]) == b:
                st["steps_same_cell"] += 1
                continue
            if s_in is None or s_out is None:
                st["steps_not_adjacent"] += 1
                ok_path = False
                continue
            t = tiles.get(b)
            if t is None:
                st["steps_no_tile"] += 1
                ok_path = False
                continue
            tt = turns(*t)
            steps += 1
            if not tt:
                st["steps_no_lanes"] += 1
                bad_pieces[(t[0], "no-lanes")] += 1
                ok_path = False
            elif (s_in, s_out) in tt:
                st["steps_ok"] += 1
            else:
                if a.skip_avenue_sideways and t[0] == 11204:
                    st["steps_avenue_corridor"] += 1
                    continue
                st["steps_no_turn"] += 1
                bad_pieces[(t[0], "turn %d->%d" % (s_in, s_out))] += 1
                ok_path = False
        per_path.append({"n": s["n"], "road_steps": steps, "ok": ok_path})
    out = {"samples": len(samples), "counts": dict(st),
           "paths_all_steps_drivable": sum(1 for p in per_path if p["ok"]),
           "paths_with_road_steps": sum(1 for p in per_path if p["road_steps"] > 0),
           "undrivable_by_piece": {"%d %s" % k: v for k, v in bad_pieces.most_common(25)}}
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
