#!/usr/bin/env python3
r"""hwcars_deposits.py - read-only: which cells of a box receive trip density, per mask (task hwcars 2026-10-19).

Frida on SC3_PID, one hook: SimTransit FUN_10006edd(x, z, amount, mask), the deposit made only while an ARRIVED
trip's final path is popped (mask 1 road node, 2 highway node; hwtraffic_probe.py, CAR_TRIPS.md) [CONFIRMED @
SimTransit 0x10006edd]. route_trip's entry is not hooked (sc3cartrips has its own trampoline there).

  py -3.12 hwcars_deposits.py X0,Z0,X1,Z1 SECS OUT.json
Prints per mask the number of deposits and the cells, and a text grid of deposit counts (any mask) over the box.
"""
import json, sys, time
import frida

JS = r"""
var B = %s;
var base = Process.getModuleByName('SimTransit.dll').base;
var cell = {};
Interceptor.attach(base.add(0x10006edd - 0x10000000), {
  onEnter: function (a) {
    var x = a[0].toInt32(), z = a[1].toInt32();
    if (x < B[0] || x > B[2] || z < B[1] || z > B[3]) return;
    var k = x + ',' + z + ',' + (a[3].toInt32() & 0xff);
    var e = cell[k] || (cell[k] = [0, 0]); e[0]++; e[1] += a[2].toInt32() & 0xff;
  }
});
rpc.exports = { take: function () { var c = cell; cell = {}; return c; } };
"""


def main(a):
    box = list(map(int, a[1].split(","))); secs = float(a[2])
    import os
    s = frida.attach(int(os.environ["SC3_PID"]))
    sc = s.create_script(JS % json.dumps(box)); sc.load()
    time.sleep(secs)
    c = sc.exports_sync.take(); s.detach()
    out = {}
    for k, (n, amt) in c.items():
        x, z, m = map(int, k.split(","))
        out.setdefault(m, {})["%d,%d" % (x, z)] = [n, amt]
    json.dump({"box": box, "secs": secs, "by_mask": out}, open(a[3], "w"), indent=1)
    for m, cells in sorted(out.items()):
        print("mask", m, "cells", len(cells), "deposits", sum(v[0] for v in cells.values()))
    tot = {}
    for m, cells in out.items():
        for k, v in cells.items():
            tot[k] = tot.get(k, 0) + v[0]
    x0, z0, x1, z1 = box
    print("     " + "".join("%4d" % x for x in range(x0, x1 + 1)))
    for z in range(z0, z1 + 1):
        print("%4d " % z + "".join("%4s" % (tot.get("%d,%d" % (x, z), "") or ".") for x in range(x0, x1 + 1)))


if __name__ == "__main__":
    main(sys.argv)
