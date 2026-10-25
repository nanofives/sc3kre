#!/usr/bin/env python3
r"""hwtrips_probe.py - why so few trips use highways (task hwtrips, 2026-10-18). Frida on SC3_PID, SimTransit.dll.

Read-only unless --lever is given. Ghidra VAs (SimTransit, base 0x10000000):
  FUN_100070d0  route_trip (thiscall, ecx = traffic layer; stack: start node, dest kind, budget base, deposit flag,
                three mode flag bytes). Return low byte 1 = arrived.
  FUN_10009e8e  deque back(); called from route_trip's final pop loop (return address 0x100072d8..0x100072f3) it
                hands out each node of the arrived path; node +0x14 = type (1 road, 2 highway, 3 ramp-road, ...).
  FUN_1000755e  select_next (thiscall; stack: node, out node, budget, ...). For a 1x1 road node (type 1) this probe
                re-derives the ring-scan candidates the way the code does (visited grid +0x78 lacks bit 1, flags +0x5c
                not 0x10 and has bit 1; a candidate with 0x40 becomes type 3) and records whether a type-3 (ramp)
                candidate was offered, its road density (+0x6c) against the best other candidate, and what was taken.

Layer grids (cRZCellMap, rows at +0xc, rows[x] + z): +0x5c u16 flags, +0x6c road density, +0x70 highway density,
+0x78 visited. Dims +0x14 / +0x18.

Levers (--lever, applied by rpc on a timer; window schedule ABBA... of --secs each):
  annoy:N   write DAT_1001f0c0 (TrafficAnnoyanceLevel, INI 165) = N in B windows, the read-back value in A windows.
  rampd:N   in B windows, every 0.5 s set the road density +0x6c of every type-3 cell (flags & 0x41 == 0x41, not 0x10)
            to N; in A windows set them back to the value read at the start of the run.
  hwcost:N  write DAT_1001f0b2 (TripCellCostBaseHighway, INI 2) = N in B windows.
  rf:1      sc3netmod RAMPFIRST block (sc3netmod_rampfirst.c) on in B windows, off in A (sc3netmod_rf_set); left off.

  py -3.12 hwtrips_probe.py census --out census.json
  py -3.12 hwtrips_probe.py run --secs 20 --windows 8 [--lever rampd:120] [--start 4] --out run.json
"""
import argparse
import json
import sys
import threading
import time
import os

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var TR = Process.getModuleByName('SimTransit.dll').base;
function A(va) { return TR.add(va - 0x10000000); }
var L = null;
var K32 = Process.getModuleByName('kernel32.dll');
var QPC = new NativeFunction(K32.getExportByName('QueryPerformanceCounter'), 'int', ['pointer']), QB = Memory.alloc(8);
var QPF = new NativeFunction(K32.getExportByName('QueryPerformanceFrequency'), 'int', ['pointer']), QF = Memory.alloc(8);
QPF(QF); var QFREQ = QF.readU64().toNumber();
function rows(off) { return L.add(off).readPointer().add(0xc).readPointer(); }
function rowp(off, x) { return rows(off).add(4 * x).readPointer(); }
function u16(x, z) { return rowp(0x5c, x).add(2 * z).readU16(); }
function b(off, x, z) { return rowp(off, x).add(z).readU8(); }
function wb(off, x, z, v) { rowp(off, x).add(z).writeU8(v); }
var S = null;
function fresh() { return {trips: 0, arrived: 0, arr_hwy: 0, arr_ramp: 0, arr_hwy_nodes: 0, path_nodes: 0,
  arr_dep: 0, arr_dep_hwy: 0, trips_off: 0, arr_off: 0, arr_off_hwy: 0, plen: {}, args: {}, trans: {}, qt: 0, qt_arr: 0, pred_ok: 0, pred_bad: 0, pred_bad3: 0, pred3: 0, steps1: 0, offer3: 0, took3_when_offered: 0, took3: 0, offer3_only: 0,
  d3_lt_best: 0, d3_eq_best: 0, d3_gt_best: 0, d3_hist: {}, dbest_hist: {}}; }
S = fresh();
var cur = {};
Interceptor.attach(A(0x100070d0), {
  onEnter: function (a) {
    L = this.context.ecx;
    if (%TIMING%) { QPC(QB); this.q0 = QB.readU64().toNumber(); }
    var k = [a[1].toInt32(), a[2].toInt32(), a[3].toInt32() & 0xff, a[4].toInt32() & 0xff, a[5].toInt32() & 0xff,
             a[6].toInt32() & 0xff].join(',');
    S.args[k] = (S.args[k] || 0) + 1;
    cur[this.threadId] = {hw: 0, rp: 0, n: 0, off: 0, dep: a[3].toInt32() & 0xff};
  },
  onLeave: function (r) {
    var c = cur[this.threadId]; delete cur[this.threadId];
    if (%TIMING%) { QPC(QB); var dq = QB.readU64().toNumber() - this.q0; S.qt += dq; if ((r.toInt32() & 0xff) !== 0) S.qt_arr += dq; }
    S.trips++;
    if (c && c.off) S.trips_off++;
    if ((r.toInt32() & 0xff) === 0 || !c) return;
    if (c.off) { S.arr_off++; if (c.hw) S.arr_off_hwy++; }
    var pk = c.n < 4 ? '<4' : c.n < 8 ? '4-7' : c.n < 16 ? '8-15' : c.n < 32 ? '16-31' : c.n < 64 ? '32-63' : c.n < 128 ? '64-127' : '128+';
    S.plen[pk] = (S.plen[pk] || 0) + 1;
    S.arrived++; S.path_nodes += c.n; S.arr_hwy_nodes += c.hw;
    if (c.hw) S.arr_hwy++;
    if (c.rp) S.arr_ramp++;
    if (c.dep) { S.arr_dep++; if (c.hw) S.arr_dep_hwy++; }
  }
});
var BACK_LO = A(0x100072d8), BACK_HI = A(0x100072f3);
if (!%TIMING%) Interceptor.attach(A(0x10009e8e), {
  onLeave: function (r) {
    var ra = this.returnAddress;
    if (ra.compare(BACK_LO) < 0 || ra.compare(BACK_HI) > 0) return;
    var c = cur[this.threadId]; if (!c) return;
    var t = r.add(0x14).readU8(); c.n++;
    if (t === 2 || t === 0x42) c.hw++;
    if (t === 3) c.rp = 1;
  }
});
function hk(h, v) { var k = v < 0 ? 'none' : String(Math.min(255, v) >> 4 << 4); h[k] = (h[k] || 0) + 1; }
if (%STEP%) Interceptor.attach(A(0x1000755e), {
  onEnter: function (a) {
    this.n = a[0]; this.o = a[1];
    var t = this.n.add(0x14).readU8(); this.t = t; this.off = 0;
    if (t !== 1 || !L) return;
    var x0 = this.n.add(4).readS32(), z0 = this.n.add(8).readS32(), x1 = this.n.add(0xc).readS32(), z1 = this.n.add(0x10).readS32();
    if (x0 !== x1 || z0 !== z1) return;
    var w = L.add(0x14).readS32(), h = L.add(0x18).readS32();
    var cs = [[x0 - 1, z0], [x0 + 1, z0], [x0, z0 - 1], [x0, z0 + 1], [x0, z0]];
    var d3 = -1, best = -1, n3 = 0, nother = 0, annoy = A(0x1001f0c0).readU8();
    var kept = -1, under = false, bv = 0, sta = 0;
    var order = [0, 2, 4, 3, 1];   // scan order: x outer (x-1, x, x+1), z inner
    for (var i = 0; i < 5; i++) {
      var x = cs[i][0], z = cs[i][1];
      if (x < 0 || z < 0 || x >= w || z >= h) continue;
      if ((b(0x78, x, z) & 1) === 1) continue;
      var f = u16(x, z);
      if (f & 0x10) { sta = 1; continue; }
      if (!(f & 1)) continue;
      var d = b(0x6c, x, z);
      cs[i].push(d);
      if (f & 0x40) { n3++; d3 = Math.max(d3, d); } else { nother++; best = Math.max(best, d); }
    }
    for (var j = 0; j < 5; j++) { var c = cs[order[j]]; if (c.length < 3) continue; var d = c[2];
      if (d < annoy) { if (under && d < bv) continue; kept = order[j]; under = true; bv = d; }
      else if (kept < 0) kept = order[j]; }
    this.pred = (sta || kept < 0) ? null : cs[kept]; this.pred3 = this.pred ? ((u16(this.pred[0], this.pred[1]) & 0x40) ? 1 : 0) : 0;
    this.off = n3 ? 1 : 0; this.d3 = d3; this.best = best; this.only = (n3 && !nother) ? 1 : 0;
  },
  onLeave: function (r) {
    var ok = (r.toInt32() & 0xff) !== 0;
    var nt = ok ? this.o.add(0x14).readU8() : 0;
    var k = this.t + '>' + (ok ? nt : 'x'); S.trans[k] = (S.trans[k] || 0) + 1;
    if (this.t !== 1) return;
    S.steps1++;
    if (this.pred && ok) {
      var ox0 = this.o.add(4).readS32(), oz0 = this.o.add(8).readS32(), ox1 = this.o.add(0xc).readS32(), oz1 = this.o.add(0x10).readS32();
      var px = this.pred[0], pz = this.pred[1];
      if (px >= ox0 && px <= ox1 && pz >= oz0 && pz <= oz1) S.pred_ok++; else { S.pred_bad++; if (nt === 3 || this.pred3) S.pred_bad3++; }
      if (this.pred3) S.pred3++;
    }
    if (nt === 3) S.took3++;
    if (!this.off) return;
    S.offer3++;
    var cc = cur[this.threadId]; if (cc) cc.off = 1;
    if (this.only) S.offer3_only++;
    if (nt === 3) S.took3_when_offered++;
    hk(S.d3_hist, this.d3); hk(S.dbest_hist, this.best);
    if (this.best >= 0) { if (this.d3 < this.best) S.d3_lt_best++; else if (this.d3 === this.best) S.d3_eq_best++; else S.d3_gt_best++; }
  }
});
var days = 0;
Interceptor.attach(Process.getModuleByName('SIMCITY.DLL').base.add(0xaa4d), function () { days++; });
var ramps = null, rampOrig = null, rampVal = -1, annoyOrig = A(0x1001f0c0).readU8(), hwcOrig = A(0x1001f0b2).readU8();
function findRamps() {
  ramps = []; rampOrig = [];
  var w = L.add(0x14).readS32(), h = L.add(0x18).readS32();
  for (var x = 0; x < w; x++) for (var z = 0; z < h; z++) {
    var f = u16(x, z); if ((f & 0x41) === 0x41 && !(f & 0x10)) { ramps.push([x, z]); rampOrig.push(b(0x6c, x, z)); } }
}
setInterval(function () {
  if (rampVal < 0 || !L) return;
  if (!ramps) findRamps();
  for (var i = 0; i < ramps.length; i++) wb(0x6c, ramps[i][0], ramps[i][1], rampVal);
}, 500);
rpc.exports = {
  ready: function () { return L !== null; },
  take: function () { var o = S; S = fresh(); o.days = days; days = 0; o.qfreq = QFREQ; return o; },
  consts: function () { return {annoy: annoyOrig, hwcost: hwcOrig, road: A(0x1001f0b0).readU8(), adder: A(0x1001f0be).readU8(),
    maxd: A(0x1001f0bf).readU8(), divroad: A(0x1001f0c1).readU8(), divhwy: A(0x1001f0c3).readU8()}; },
  lever: function (kind, v) {
    if (kind === 'annoy') A(0x1001f0c0).writeU8(v < 0 ? annoyOrig : v);
    else if (kind === 'hwcost') A(0x1001f0b2).writeU8(v < 0 ? hwcOrig : v);
    else if (kind === 'rf') return new NativeFunction(Process.getModuleByName('sc3netmod.dll').getExportByName('sc3netmod_rf_set'),
      'int', ['int'], {exceptions: 'propagate'})(v < 0 ? 0 : 1);
    else if (kind === 'rampd') {
      if (!ramps) findRamps();
      if (v < 0) { rampVal = -1; for (var i = 0; i < ramps.length; i++) wb(0x6c, ramps[i][0], ramps[i][1], rampOrig[i]); }
      else rampVal = v;
    }
    return 1;
  },
  census: function () {
    var w = L.add(0x14).readS32(), h = L.add(0x18).readS32();
    var cnt = {}, r40 = [], e800 = [], e400 = [];
    for (var x = 0; x < w; x++) for (var z = 0; z < h; z++) {
      var f = u16(x, z); if (!f) continue;
      var k = '0x' + (f & 0x3c5f).toString(16); cnt[k] = (cnt[k] || 0) + 1;
      if (f & 0x40) r40.push([x, z, f, b(0x6c, x, z), b(0x70, x, z)]);
      if (f & 0x800) e800.push([x, z]);
      if (f & 0x400) e400.push([x, z]);
    }
    var road = [], hwy = [];
    for (var x = 0; x < w; x++) for (var z = 0; z < h; z++) {
      var f = u16(x, z);
      if ((f & 0x51) === 1) road.push(b(0x6c, x, z));
      if ((f & 0x52) === 2) hwy.push(b(0x70, x, z));
    }
    return {w: w, h: h, flags: cnt, cells40: r40, e800: e800, e400: e400, road_d: road, hwy_d: hwy};
  }
};
"""


NOSTEP = False
TIMING = False


def attach():
    pid = int(os.environ.get("SC3_PID") or sc3io.game_pid())
    sc3pause.require_running(pid, "hwtrips_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("%STEP%", "false" if NOSTEP else "true").replace("%TIMING%", "true" if TIMING else "false"))
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    return pid, s, sc


def wait_ready(sc, t=120):
    t0 = time.time()
    while not sc.exports_sync.ready():
        if time.time() - t0 > t:
            raise SystemExit("no route_trip call seen (game paused?)")
        time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["census", "run"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--secs", type=float, default=20)
    ap.add_argument("--windows", type=int, default=8)
    ap.add_argument("--lever", default="")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--nostep", action="store_true", help="skip the select_next hook (fast; no offer stats)")
    ap.add_argument("--timing", action="store_true", help="time each route_trip call (QueryPerformanceCounter); implies "
                    "--nostep and drops the path hook, so the share columns read 0")
    a = ap.parse_args()
    global NOSTEP, TIMING
    NOSTEP = a.nostep or a.timing
    TIMING = a.timing
    pid, s, sc = attach()
    if a.start:
        h = sc3io.game_hwnd(pid)
        sc3io.key(h, 0x50)
        time.sleep(1.0)
        sc3io.key(h, 0x30 + a.start)
    wait_ready(sc)
    out = {"consts": sc.exports_sync.consts()}
    if a.cmd == "census":
        out["census"] = sc.exports_sync.census()
    else:
        kind, val = (a.lever.split(":") + [""])[:2] if a.lever else ("", "")
        sc.exports_sync.take()
        wins = []
        for i in range(a.windows):
            arm = "AB"[[0, 1, 1, 0][i % 4]] if kind else "A"
            if kind:
                sc.exports_sync.lever(kind, int(val) if arm == "B" else -1)
            time.sleep(a.secs)
            o = sc.exports_sync.take()
            o["arm"] = arm
            o["args"] = dict(sorted(o["args"].items(), key=lambda kv: -kv[1])[:40])
            wins.append(o)
            if TIMING:
                print("win %d %s: days %d trips %d arrived %d  us/trip %.2f  us/arrived %.2f" % (
                    i, arm, o["days"], o["trips"], o["arrived"], 1e6 * o["qt"] / o["qfreq"] / max(1, o["trips"]),
                    1e6 * o["qt_arr"] / o["qfreq"] / max(1, o["arrived"])), flush=True)
                continue
            print("win %d %s: days %d trips %d arrived %d hwy %d (%.2f%%) ramp %d dep %d dephwy %d pred ok/bad %d/%d | steps1 %d offer3 %d took3|offer %d "
                  "d3<best %d =%d >%d only3 %d" % (
                      i, arm, o["days"], o["trips"], o["arrived"], o["arr_hwy"],
                      100.0 * o["arr_hwy"] / max(1, o["arrived"]), o["arr_ramp"], o["arr_dep"], o["arr_dep_hwy"],
                      o["pred_ok"], o["pred_bad"], o["steps1"], o["offer3"],
                      o["took3_when_offered"], o["d3_lt_best"], o["d3_eq_best"], o["d3_gt_best"], o["offer3_only"]),
                  flush=True)
        if kind:
            sc.exports_sync.lever(kind, -1)
        out["lever"] = a.lever
        out["windows"] = wins
    s.detach()
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
