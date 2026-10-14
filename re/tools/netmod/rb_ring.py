#!/usr/bin/env python3
r"""rb_ring.py - classify street-sim moves around a 2x2 roundabout from an lk_probe.py run (task roundabout, 2026-10-13).

lk_probe's STRTSIM hook counts trans["x,z,code,ok"]: a vehicle leaving cell (x, z) through exit code `code`.
code / 8 = side 0 x-, 1 z-, 2 x+, 3 z+ (settled from lanekit's probe_D3 counts: from the exit road (25,183), south of
ring cell (25,182), only codes 8 and 24 occur; from (24,181), west of (25,181), only 0 and 16; and every ring cell's
codes fall on its two ring arms and its exit).

  py -3.12 rb_ring.py PROBE.jsonl X,Z        # X,Z = anchor (top-left cell) of the 2x2 pinwheel 3,0 / 2,1
Ring order of that layout: (X+1,Z) -> (X,Z) -> (X,Z+1) -> (X+1,Z+1) -> (X+1,Z) (lanekit RESULTS arm D2).
Prints, for the LAST sample: ring-to-ring with / against the order, ring -> outside, outside -> ring (ok / failed),
and SimTransit cells_6c (density over the --cells list) at every sample.
"""
import json
import sys

SIDE = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}


def main(argv):
    rows = [json.loads(l) for l in open(argv[1]) if l.strip().startswith("{")]
    X, Z = map(int, argv[2].split(","))
    ring = [(X + 1, Z), (X, Z), (X, Z + 1), (X + 1, Z + 1)]
    nxt = {ring[i]: ring[(i + 1) % 4] for i in range(4)}
    out = {"with": 0, "against": 0, "ring_to_out": 0, "ring_to_out_failed": 0, "in_ok": 0, "in_failed": 0,
           "ring_failed": 0}
    trans = rows[-1].get("trans", {})
    for k, n in trans.items():
        x, z, code, ok = map(int, k.split(","))
        dx, dz = SIDE[code // 8]
        a, b = (x, z), (x + dx, z + dz)
        if a in nxt and b in nxt:
            if not ok:
                out["ring_failed"] += n
            elif nxt[a] == b:
                out["with"] += n
            else:
                out["against"] += n
        elif a in nxt:
            out["ring_to_out" if ok else "ring_to_out_failed"] += n
        elif b in nxt:
            out["in_ok" if ok else "in_failed"] += n
    print(json.dumps(out))
    by_in = {}
    for k, n in trans.items():
        x, z, code, ok = map(int, k.split(","))
        dx, dz = SIDE[code // 8]
        if (x + dx, z + dz) in nxt and (x, z) not in nxt:
            by_in["%d,%d->%d,%d %s" % (x, z, x + dx, z + dz, "ok" if ok else "failed")] = n
    print("into the ring:", json.dumps(by_in, sort_keys=True))
    for r in rows:
        print("days=%s cells_6c=%s map_6c=%s" % (r.get("days"), r.get("cells_6c"), r.get("map_6c")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
