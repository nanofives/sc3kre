#!/usr/bin/env python3
r"""ld_paths.py - read-only: direction of the FINAL trip paths through watched cells (verify/lanedensity PRE addendum 4).

Density is deposited only along a trip's final path: after arrival the router FUN_100070d0 pops its DFS stack and calls
the deposit FUN_10006edd(layer, x, z, amount, mask) once per cell of each popped node [CONFIRMED @ SimTransit
0x100070d0, 0x10006edd], so on one thread the deposits of one trip come in REVERSE path order. This probe hooks
0x10006edd (sc3perf's atomic replacement sits behind the same entry) and, per thread, pairs each deposit with the
previous one: when both are adjacent cells and at least one is watched, the forward step is (this cell -> previous
cell). Pairs that straddle two trips are counted only if adjacent (rare; reported as is).

  py -3.12 ld_paths.py --cells 147,46,157,46 --cells 61,95,62,96 --secs 120 --out paths.json
Output: {"from x,z>to x,z": count}, sides as world steps.
"""
import argparse
import json
import os
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402

JS = r"""
var TR = Process.getModuleByName('SimTransit.dll').base;
var RECTS = %RECTS%;
function watched(x, z) { for (var i = 0; i < RECTS.length; i++) { var r = RECTS[i]; if (x >= r[0] && x <= r[2] && z >= r[1] && z <= r[3]) return true; } return false; }
var last = {}, cnt = {}, n = 0;
Interceptor.attach(TR.add(0x6edd), {
  onEnter: function (a) {
    var x = a[0].toInt32(), z = a[1].toInt32(), t = this.threadId, p = last[t];
    last[t] = [x, z];
    n++;
    if (!p || (p[0] === x && p[1] === z)) return;
    var dx = Math.abs(p[0] - x), dz = Math.abs(p[1] - z);
    if (dx + dz !== 1) return;
    if (!watched(x, z) && !watched(p[0], p[1])) return;
    var k = x + ',' + z + '>' + p[0] + ',' + p[1];       // forward order: this cell, then the one deposited before
    cnt[k] = (cnt[k] || 0) + 1;
  }
});
rpc.exports = { get: function () { return {n: n, cnt: cnt}; } };
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", action="append", required=True)
    ap.add_argument("--secs", type=float, default=120)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rects = [[int(v) for v in c.split(",")] for c in a.cells]
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS.replace("%RECTS%", json.dumps(rects)))
    sc.load()
    time.sleep(a.secs)
    r = sc.exports_sync.get()
    s.detach()
    with open(a.out, "w") as f:
        json.dump({"deposits": r["n"], "secs": a.secs, "pairs": r["cnt"]}, f, indent=1, sort_keys=True)
    print("deposits %d, %d watched pairs -> %s" % (r["n"], len(r["cnt"]), a.out))


if __name__ == "__main__":
    main()
