#!/usr/bin/env python3
r"""hwtraffic_probe.py - read-only: monthly trip counts and highway use for the hwtraffic before/after test (2026-10-18).

Frida on SC3_PID. Nothing is written to the game except, with --start, the sc3resize keys P (unpause) and 1-4 (speed).

Hooks (SimTransit.dll, Ghidra VAs):
  FUN_100070d0  route one trip (thiscall, ecx = traffic layer). It counts every call in layer +0xb0 and every failure
                in +0xb4 (piVar7[0x2d] on the failure path); the return's low byte is 1 on arrival [CONFIRMED @
                0x100070d0]. Density is deposited only while the arrived trip's path is popped, inside this call, on
                the same thread: FUN_10006edd(layer, x, z, amount, mask), mask 2 = a highway node [CONFIRMED @
                0x100070d0, 0x10006edd]. So per trip this probe knows which highway cells its final path used.
  FUN_10006edd  the deposit: per thread, the highway cells (mask & 2) of the trip being popped are matched against the
                named cell groups (--groups JSON); per-cell highway deposit amounts are summed inside --box.
  FUN_100093e9  monthly publish (fastcall, ecx = layer). onEnter: the game's own month counters +0xb0 (trips routed)
                and +0xb4 (failed); onLeave: +0xb8 (failed / routed, float, written only when +0xb4 != 0), +0xc0
                (the published traffic average), and the highway snapshot grid +0x64 summed per group.

  py -3.12 hwtraffic_probe.py --groups groups.json --box 30,0,75,30 --months 6 --out arm.json [--start 4]
groups.json: {"name": [[x0, z0, x1, z1], ...], ...} (inclusive cell rects, the coordinates the deposit receives).
Output JSON: per month the game counters, this probe's trip counts (all / arrived / arrived using each group), the
highway deposit amount per group, the +0x64 snapshot sum per group; at the end the per-cell deposit sums in --box.
"""
import argparse
import json
import os
import sys
import threading
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var TR = Process.getModuleByName('SimTransit.dll').base;
function A(va) { return TR.add(va - 0x10000000); }
var G = %GROUPS%, NAMES = Object.keys(G), BOX = %BOX%;
function inr(r, x, z) { return x >= r[0] && x <= r[2] && z >= r[1] && z <= r[3]; }
function grp(x, z) { var m = 0; for (var i = 0; i < NAMES.length; i++) { var rs = G[NAMES[i]];
  for (var j = 0; j < rs.length; j++) if (inr(rs[j], x, z)) { m |= 1 << i; break; } } return m; }
var cur = {};                // thread -> {m: groups touched, hw: any highway deposit}
var M = null;
function fresh() { var o = {trips: 0, arrived: 0, arrived_hwy: 0, grp_trips: {}, grp_amt: {}};
  NAMES.forEach(function (n) { o.grp_trips[n] = 0; o.grp_amt[n] = 0; }); return o; }
M = fresh();
var cell = {};               // "x,z" -> highway deposit amount inside BOX
Interceptor.attach(A(0x100070d0), {
  onEnter: function () { cur[this.threadId] = {m: 0, hw: 0}; },
  onLeave: function (ret) {
    var c = cur[this.threadId]; delete cur[this.threadId];
    M.trips++;
    if ((ret.toInt32() & 0xff) === 0 || !c) return;
    M.arrived++;
    if (c.hw) M.arrived_hwy++;
    for (var i = 0; i < NAMES.length; i++) if (c.m & (1 << i)) M.grp_trips[NAMES[i]]++;
  }
});
Interceptor.attach(A(0x10006edd), {
  onEnter: function (a) {
    if (!(a[3].toInt32() & 2)) return;
    var c = cur[this.threadId]; if (!c) return;
    var x = a[0].toInt32(), z = a[1].toInt32(), amt = a[2].toInt32() & 0xff;
    c.hw = 1;
    var m = grp(x, z); c.m |= m;
    for (var i = 0; i < NAMES.length; i++) if (m & (1 << i)) M.grp_amt[NAMES[i]] += amt;
    if (inr(BOX, x, z)) { var k = x + ',' + z; cell[k] = (cell[k] || 0) + amt; }
  }
});
var days = 0;
Interceptor.attach(Process.getModuleByName('SIMCITY.DLL').base.add(0xaa4d), function () { days++; });
Interceptor.attach(A(0x100093e9), {
  onEnter: function () { this.L = this.context.ecx; this.b0 = this.L.add(0xb0).readU32(); this.b4 = this.L.add(0xb4).readU32(); },
  onLeave: function () {
    var L = this.L, w = L.add(0x14).readU32(), h = L.add(0x18).readU32();
    var rows = L.add(0x64).readPointer().add(0xc).readPointer();
    var snap = {}; NAMES.forEach(function (n) { snap[n] = 0; }); var tot = 0;
    for (var x = 0; x < w; x++) {
      var row = new Uint8Array(rows.add(4 * x).readPointer().readByteArray(h));
      for (var z = 0; z < h; z++) { var v = row[z]; if (!v) continue; tot += v;
        var m = grp(x, z); for (var i = 0; i < NAMES.length; i++) if (m & (1 << i)) snap[NAMES[i]] += v; }
    }
    var o = M; M = fresh();
    o.days = days; o.game_trips = this.b0; o.game_failed = this.b4; o.game_fail_ratio = L.add(0xb8).readFloat();
    o.game_avg_c0 = L.add(0xc0).readU32(); o.game_bc = L.add(0xbc).readU32(); o.hwy_snap = snap; o.hwy_snap_total = tot;
    send({month: o});
  }
});
rpc.exports = { cells: function () { return cell; } };
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", required=True)
    ap.add_argument("--box", default="0,0,0,0")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=int, default=0, help="unpause (P) and set this speed (1-4) first")
    ap.add_argument("--timeout", type=float, default=3600)
    a = ap.parse_args()
    with open(a.groups) as f:
        groups = json.load(f)
    box = [int(v) for v in a.box.split(",")]
    pid = sc3io.game_pid()
    months, done = [], threading.Event()

    def on_msg(m, data):
        if m.get("type") != "send":
            print(m, flush=True)
            return
        mo = m["payload"]["month"]
        months.append(mo)
        print("month %d: days %d trips %d arrived %d (game %d / failed %d, ratio %.4f) hwy %d snap %d | %s" % (
            len(months), mo["days"], mo["trips"], mo["arrived"], mo["game_trips"], mo["game_failed"],
            mo["game_fail_ratio"], mo["arrived_hwy"], mo["hwy_snap_total"],
            " ".join("%s=%d/%d/%d" % (n, mo["grp_trips"][n], mo["grp_amt"][n], mo["hwy_snap"][n]) for n in groups)),
            flush=True)
        if len(months) >= a.months:
            done.set()

    sc3pause.require_running(pid, "hwtraffic_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("%GROUPS%", json.dumps(groups)).replace("%BOX%", json.dumps(box)))
    sc.on("message", on_msg)
    sc.load()
    if a.start:
        h = sc3io.game_hwnd(pid)
        sc3io.key(h, 0x50)
        time.sleep(1.0)
        sc3io.key(h, 0x30 + a.start)
    t0 = time.time()
    while not done.wait(5):
        if time.time() - t0 > a.timeout:
            print("timeout", flush=True)
            break
    cells = sc.exports_sync.cells()
    s.detach()
    with open(a.out, "w") as f:
        json.dump({"groups": groups, "box": box, "secs": time.time() - t0, "months": months, "cells": cells}, f, indent=1)
    print("wrote %s (%d months, %.0f s)" % (a.out, len(months), time.time() - t0))


if __name__ == "__main__":
    main()
