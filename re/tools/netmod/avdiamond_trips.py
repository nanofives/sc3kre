#!/usr/bin/env python3
r"""avdiamond_trips.py - read-only: which way do routed trips step through the cells of a box? (task avdiamond, 2026-11-09)

The street cars on screen are few where an avenue carries little traffic, so this reads the trips themselves. Same hooks
as avxroad_trips.py (SimTransit.dll, Ghidra VAs):
  FUN_100070d0  route one trip (thiscall); return low byte 1 = arrived [CONFIRMED @ 0x100070d0]
  FUN_10006edd  the density deposit, once per node while an ARRIVED trip's path is popped, same thread; stack args
                (x, z, amount, mask) [CONFIRMED @ 0x10006edd]
For every arrived trip, every pair of consecutive deposit cells inside the box is counted as an ordered step (a -> b).
The deposit order is the popped order: calibrate the direction on a band whose one-way direction is known (a pair
counted only as b -> a on a one-way half means the pop runs against travel).

  py -3.12 avdiamond_trips.py --box X0,Z0,X1,Z1 --secs 300 --out run.json
OUT: {"box", "secs", "trips", "arrived", "steps": {"mask|x,z>x,z": n}} (mask = the deposit's 4th argument at b)
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
import sc3pause  # noqa: E402

JS = r"""
var TR = Process.getModuleByName('SimTransit.dll').base;
function A(va) { return TR.add(va - 0x10000000); }
var B = %BOX%, cur = {}, trips = 0, arrived = 0, steps = {};
function inb(x, z) { return x >= B[0] && x <= B[2] && z >= B[1] && z <= B[3]; }
Interceptor.attach(A(0x100070d0), {
  onEnter: function () { cur[this.threadId] = []; },
  onLeave: function (ret) {
    var p = cur[this.threadId]; delete cur[this.threadId];
    trips++;
    if ((ret.toInt32() & 0xff) === 0 || !p) return;
    arrived++;
    for (var i = 1; i < p.length; i++) {
      var a = p[i - 1], b = p[i];
      if (!inb(a[0], a[1]) || !inb(b[0], b[1])) continue;
      var k = b[2] + '|' + a[0] + ',' + a[1] + '>' + b[0] + ',' + b[1];
      steps[k] = (steps[k] || 0) + 1;
    }
  }
});
Interceptor.attach(A(0x10006edd), {
  onEnter: function (a) {
    var p = cur[this.threadId]; if (!p) return;
    var x = a[0].toInt32(), z = a[1].toInt32(), m = a[3].toInt32(), l = p[p.length - 1];
    if (!l || l[0] !== x || l[1] !== z) p.push([x, z, m]);
  }
});
rpc.exports = { stats: function () { return {trips: trips, arrived: arrived, steps: steps}; } };
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--box", required=True)
    ap.add_argument("--secs", type=float, default=300)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    box = [int(v) for v in a.box.split(",")]
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "avdiamond_trips")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("%BOX%", json.dumps(box)))
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    t0 = time.time()
    n = 0
    while time.time() - t0 < a.secs:
        time.sleep(min(30, a.secs - (time.time() - t0)))
        st = sc.exports_sync.stats()
        n += 1
        print("[%d] %.0f s: trips %d arrived %d, ordered steps in the box %d" % (
            n, time.time() - t0, st["trips"], st["arrived"], sum(st["steps"].values())), flush=True)
    st = sc.exports_sync.stats()
    s.detach()
    st["box"] = box
    st["secs"] = time.time() - t0
    json.dump(st, open(a.out, "w"), indent=1)
    print("wrote %s" % a.out)


if __name__ == "__main__":
    main()
