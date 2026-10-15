#!/usr/bin/env python3
r"""rb_island.py - street-sim moves AND vehicle positions on a 2x2 roundabout, live, read only (task roundabout2, 2026-10-13).

Frida on SC3_PID. Hook STRTSIM FUN_1001c750 (a street-sim vehicle leaving cell (x, z) by an exit edge, this = the
vehicle, +0x16 of the edge = exit code; NET_LANES.md 2.3). The vehicle's world position is s32 +0x0c (x) and +0x14 (z),
256 units per cell (measured on 30 / 30 hook calls: +0x0c >> 8 == x and +0x14 >> 8 == z; +0x10 is the height, +0x3c
is a float angle). Every vehicle that moves in the watched box is
polled every --every-ms milliseconds while it stays alive; samples inside the 4 ring cells are kept as the distance from
the block centre.

  py -3.12 rb_island.py X,Z --secs 480 --out run.json [--every-ms 40]
X,Z = anchor (top-left cell) of the 2x2 block; the block centre is the corner ((X+1)*256, (Z+1)*256).
Output: {"trans": {"x,z,code,ok": n}, "samples": n, "r_hist": {bucket: n}, "r_min": .., "inside": {radius: n}}
Feed "trans" to rb_ring.py's classification with --order (same rows as lk_probe output).
"""
import argparse
import json
import os
import sys
import time

import frida

JS = r"""
var SS = Process.getModuleByName('STRTSIM.DLL').base;
var X0 = %X0%, Z0 = %Z0%, CX = (X0 + 1) * 256, CZ = (Z0 + 1) * 256;
var trans = {}, veh = {}, last = {}, near = [], nS = 0, hist = {}, rmin = 1e9, inside = {}, RADII = [120, 126, 129.5, 150, 160, 170];
RADII.forEach(function (r) { inside[r] = 0; });
Interceptor.attach(SS.add(0x1001c750 - 0x10000000), {
  onEnter: function (a) {
    this.x = a[0].toInt32(); this.z = a[1].toInt32();
    this.w = this.x >= X0 - 2 && this.x <= X0 + 3 && this.z >= Z0 - 2 && this.z <= Z0 + 3;
    if (!this.w) return;
    this.code = a[2].add(0x16).readU8();
    veh[this.context.ecx.toString()] = Date.now();
  },
  onLeave: function (r) {
    if (!this.w) return;
    var k = this.x + ',' + this.z + ',' + this.code + ',' + (r.isNull() ? 0 : 1);
    trans[k] = (trans[k] || 0) + 1;
  }
});
setInterval(function () {
  var now = Date.now();
  for (var p in veh) {
    if (now - veh[p] > 60000) { delete veh[p]; delete last[p]; continue; }
    try {
      var v = ptr(p);
      var x = v.add(0x0c).readS32(), z = v.add(0x14).readS32();
      var o = last[p];
      last[p] = [x, z];
      // a vehicle moves less than a cell between two polls; a jump means the slot was freed / reused
      if (o && (Math.abs(x - o[0]) > 256 || Math.abs(z - o[1]) > 256)) { delete veh[p]; delete last[p]; continue; }
      if (x < (X0 - 3) * 256 || x >= (X0 + 5) * 256 || z < (Z0 - 3) * 256 || z >= (Z0 + 5) * 256) {
        delete veh[p]; delete last[p]; continue;
      }
      if (x < X0 * 256 || x >= (X0 + 2) * 256 || z < Z0 * 256 || z >= (Z0 + 2) * 256) continue;
      var r = Math.sqrt((x - CX) * (x - CX) + (z - CZ) * (z - CZ));
      nS++; if (r < rmin) rmin = r;
      if (r < 129.5 && near.length < 50) near.push([p, x, z, Math.round(r), v.add(0x3c).readFloat()]);
      var b = Math.floor(r / 10) * 10; hist[b] = (hist[b] || 0) + 1;
      RADII.forEach(function (R) { if (r < R) inside[R]++; });
    } catch (e) { delete veh[p]; delete last[p]; }
  }
}, %EVERY%);
rpc.exports = { get: function () { return {trans: trans, samples: nS, r_hist: hist, r_min: rmin, inside: inside, near: near,
                                           tracked: Object.keys(veh).length}; } };
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("anchor")
    ap.add_argument("--secs", type=float, default=480)
    ap.add_argument("--every-ms", type=int, default=40)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    X0, Z0 = map(int, a.anchor.split(","))
    s = frida.attach(int(os.environ["SC3_PID"]))
    sc = s.create_script(JS.replace("%X0%", str(X0)).replace("%Z0%", str(Z0)).replace("%EVERY%", str(a.every_ms)))
    sc.load()
    t0 = time.time()
    rows = []
    while time.time() - t0 < a.secs:
        time.sleep(min(30, a.secs - (time.time() - t0)) if a.secs > time.time() - t0 else 0)
        r = sc.exports_sync.get()
        r["t"] = round(time.time() - t0, 1)
        rows.append(r)
        print(json.dumps({k: r[k] for k in ("t", "samples", "r_min", "inside", "tracked")}), flush=True)
    with open(a.out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    s.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main())
