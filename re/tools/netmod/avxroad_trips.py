#!/usr/bin/env python3
r"""avxroad_trips.py - read-only: do trips cross the junctions avx_drops builds? (task avxroad, 2026-10-26)

Frida on SC3_PID, SimTransit.dll (Ghidra VAs, the hooks of hwtraffic_probe.py):
  FUN_100070d0  route one trip (thiscall, ecx = traffic layer); return low byte 1 = arrived [CONFIRMED @ 0x100070d0].
  FUN_10006edd  the density deposit, called once per node while an ARRIVED trip's path is popped, inside route_trip
                on the same thread; stack args (x, z, amount, mask) [CONFIRMED @ 0x10006edd].
Sites (JSON [[cx, cz, nx, nz], ...]): an avenue half (cx, cz) and the plain road cell (nx, nz) whose arm points into it
(avjunc_rule.dropped_tees). Stock leaves the two unconnected. A site is CROSSED by a trip whose deposit sequence has
the two cells next to each other (either order).

  py -3.12 avxroad_trips.py --sites sites.json --secs 300 --out run.json
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
var SITES = %SITES%, key = {};
SITES.forEach(function (s, i) { key[s[0] + ',' + s[1] + '|' + s[2] + ',' + s[3]] = i; key[s[2] + ',' + s[3] + '|' + s[0] + ',' + s[1]] = i; });
var cur = {}, trips = 0, arrived = 0, crossing = 0, hits = {};
Interceptor.attach(A(0x100070d0), {
  onEnter: function () { cur[this.threadId] = []; },
  onLeave: function (ret) {
    var p = cur[this.threadId]; delete cur[this.threadId];
    trips++;
    if ((ret.toInt32() & 0xff) === 0 || !p) return;
    arrived++;
    var any = 0, seen = {};
    for (var i = 1; i < p.length; i++) {
      var k = key[p[i - 1] + '|' + p[i]];
      if (k !== undefined && !seen[k]) { seen[k] = 1; hits[k] = (hits[k] || 0) + 1; any = 1; }
    }
    crossing += any;
  }
});
Interceptor.attach(A(0x10006edd), {
  onEnter: function (a) {
    var p = cur[this.threadId]; if (!p) return;
    var c = a[0].toInt32() + ',' + a[1].toInt32();
    if (!p.length || p[p.length - 1] !== c) p.push(c);
  }
});
rpc.exports = { stats: function () { return {trips: trips, arrived: arrived, crossing: crossing, hits: hits}; } };
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", required=True)
    ap.add_argument("--secs", type=float, default=300)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sites = json.load(open(a.sites))
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "avxroad_trips")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("%SITES%", json.dumps(sites)))
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    t0 = time.time()
    n = 0
    while time.time() - t0 < a.secs:
        time.sleep(min(30, a.secs - (time.time() - t0)))
        st = sc.exports_sync.stats()
        n += 1
        print("[%d] %.0f s: trips %d arrived %d crossing a site %d, sites crossed %d of %d" % (
            n, time.time() - t0, st["trips"], st["arrived"], st["crossing"], len(st["hits"]), len(sites)), flush=True)
    st = sc.exports_sync.stats()
    s.detach()
    st["sites"] = sites
    st["secs"] = time.time() - t0
    json.dump(st, open(a.out, "w"), indent=1)
    print("wrote %s" % a.out)


if __name__ == "__main__":
    main()
