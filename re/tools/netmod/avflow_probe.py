#!/usr/bin/env python3
r"""avflow_probe.py - in-game measurement of the sc3netmod AVFLOW blocks (task avflow, 2026-10-24). Frida on SC3_PID.

Arms, switched live through sc3netmod's exports at the game's own month boundary, so every month runs under one arm:
  off  = AVFIRST off, AVDEPOSIT off      F = AVFIRST only      FD = both
Schedule: blocks of (off F FD FD F off) (each arm before and after the others), --mpw months per window; the first
--settle month(s) of each window are recorded but marked settle (density carried over from the previous arm).

Hooks (SimTransit.dll, Ghidra VAs, base 0x10000000):
  FUN_100070d0  route_trip (thiscall, ecx = traffic layer). Return low byte 1 = arrived [CONFIRMED @ 0x100070d0].
  FUN_10009e8e  deque back(); from route_trip's final pop loop (return address 0x100072d8..0x100072f3) it hands out each
                node of the arrived path (node +4 x, +8 z, +0x14 type). A road node (1, 3, 0x41) on a class-1 / class-2
                cell of sc3netmod's class grid (sc3netmod_avf_grid) marks the trip as using an avenue / boulevard.
  FUN_100093e9  monthly publish (fastcall, ecx = layer). onEnter: month counters +0xb0 (trips routed) and +0xb4 (failed),
                which the function then zeroes; onLeave: +0xb8 (failed / routed, float, only written when +0xb4 != 0),
                +0xc0 (published traffic average), and the +0x60 snapshot (the decayed live grid +0x6c) summed per cell
                group [CONFIRMED @ 0x100093e9].
  SIMCITY FUN_1000aa4d  day fire (days per month).
Cell groups (fixed at the first publish, from the class grid and the flags grid +0x5c; road = flags & 0x51 == 1):
  av = class 1 road cells, bv = class 2, side = class-0 road cells 2..R cells (Chebyshev) from an avenue / boulevard
  cell (parallel and crossing side streets near the avenues), adj = class-0 road cells 1 cell away (junction arms, the
  cells beside the avenue), rest = every other road cell.

  set SC3_PID=<pid>
  py -3.12 avflow_probe.py --blocks 3 --mpw 2 --settle 1 --out run.json [--start 4]
  py -3.12 avflow_probe.py --set FD --out x        (switch only)
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
import sc3pause  # noqa: E402  (refuse a Frida attach while the game is paused)

JS = r"""
var TR = Process.getModuleByName('SimTransit.dll').base;
function A(va) { return TR.add(va - 0x10000000); }
var N = Process.getModuleByName('sc3netmod.dll');
var gridf = new NativeFunction(N.getExportByName('sc3netmod_avf_grid'), 'pointer', ['pointer', 'pointer']);
var setF = new NativeFunction(N.getExportByName('sc3netmod_avf_set'), 'int', ['int']);
var setD = new NativeFunction(N.getExportByName('sc3netmod_avd_set'), 'int', ['int']);
var WH = Memory.alloc(8), G = null, GW = 0, GH = 0;
function grid() { var p = gridf(WH, WH.add(4)); G = p.isNull() ? null : p; GW = WH.readS32(); GH = WH.add(4).readS32(); }
function cls(x, z) { if (G === null || x < 0 || z < 0 || x >= GW || z >= GH) return 0; return G.add(z * GW + x).readU8(); }
var L = null, RADIUS = %RADIUS%;
function rows(l, off) { return l.add(off).readPointer().add(0xc).readPointer(); }
var S = null;
function fresh() { return {trips: 0, arrived: 0, failed: 0, arr_av: 0, arr_bv: 0, arr_any: 0, nodes: 0, nodes_av: 0,
  nodes_bv: 0, nodes_road: 0}; }
S = fresh();
var cur = {};
Interceptor.attach(A(0x100070d0), {
  onEnter: function () { L = this.context.ecx; cur[this.threadId] = {n: 0, r: 0, av: 0, bv: 0}; },
  onLeave: function (r) {
    var c = cur[this.threadId]; delete cur[this.threadId];
    S.trips++;
    if ((r.toInt32() & 0xff) === 0 || !c) { S.failed++; return; }
    S.arrived++; S.nodes += c.n; S.nodes_road += c.r; S.nodes_av += c.av; S.nodes_bv += c.bv;
    if (c.av) S.arr_av++;
    if (c.bv) S.arr_bv++;
    if (c.av || c.bv) S.arr_any++;
  }
});
var BACK_LO = A(0x100072d8), BACK_HI = A(0x100072f3);
Interceptor.attach(A(0x10009e8e), {
  onLeave: function (r) {
    var ra = this.returnAddress;
    if (ra.compare(BACK_LO) < 0 || ra.compare(BACK_HI) > 0) return;
    var c = cur[this.threadId]; if (!c) return;
    c.n++;
    var t = r.add(0x14).readU8();
    if (t !== 1 && t !== 3 && t !== 0x41) return;
    c.r++;
    var k = cls(r.add(4).readS32(), r.add(8).readS32());
    if (k === 1) c.av++; else if (k === 2) c.bv++;
  }
});
var days = 0;
Interceptor.attach(Process.getModuleByName('SIMCITY.DLL').base.add(0xaa4d), function () { days++; });
var GRP = null, GNAMES = ['av', 'bv', 'side', 'adj', 'rest'];
function groups(l) {
  grid();
  var w = l.add(0x14).readS32(), h = l.add(0x18).readS32(), fr = rows(l, 0x5c);
  var dist = new Uint8Array(w * h), g = [[], [], [], [], []], x, z, dx, dz;
  for (x = 0; x < w * h; x++) dist[x] = 255;
  for (x = 0; x < w; x++) for (z = 0; z < h; z++) if (cls(x, z)) {
    for (dx = -RADIUS; dx <= RADIUS; dx++) for (dz = -RADIUS; dz <= RADIUS; dz++) {
      var xx = x + dx, zz = z + dz; if (xx < 0 || zz < 0 || xx >= w || zz >= h) continue;
      var d = Math.max(Math.abs(dx), Math.abs(dz)); if (d < dist[xx * h + zz]) dist[xx * h + zz] = d; } }
  for (x = 0; x < w; x++) { var rp = fr.add(4 * x).readPointer();
    for (z = 0; z < h; z++) { var f = rp.add(2 * z).readU16(); if ((f & 0x51) !== 1) continue;
      var k = cls(x, z), d2 = dist[x * h + z];
      g[k === 1 ? 0 : k === 2 ? 1 : d2 === 1 ? 3 : d2 <= RADIUS ? 2 : 4].push([x, z]); } }
  return g;
}
function gstats(l, annoy) {
  var sr = rows(l, 0x60), out = {};
  for (var i = 0; i < 5; i++) {
    var s = {n: GRP[i].length, sum: 0, zero: 0, hi: 0, h: new Array(16).fill(0)};
    for (var j = 0; j < GRP[i].length; j++) { var c = GRP[i][j], v = sr.add(4 * c[0]).readPointer().add(c[1]).readU8();
      s.sum += v; if (!v) s.zero++; if (v >= annoy) s.hi++; s.h[v >> 4]++; }
    out[GNAMES[i]] = s;
  }
  return out;
}
var MONTHS = [], SCHED = [], mi = 0, ARM = 'pre';
var ARMS = {off: [0, 0], F: [1, 0], FD: [1, 1], D: [0, 1]};
function apply(a) { var v = ARMS[a]; setF(v[0]); setD(v[1]); ARM = a; }
Interceptor.attach(A(0x100093e9), {
  onEnter: function () { this.l = this.context.ecx; this.b0 = this.l.add(0xb0).readU32(); this.b4 = this.l.add(0xb4).readU32(); },
  onLeave: function () {
    var l = this.l, annoy = A(0x1001f0c0).readU8();
    if (GRP === null) GRP = groups(l);
    var m = {arm: ARM, idx: mi, routed: this.b0, failed: this.b4, ratio: l.add(0xb8).readFloat(), avg: l.add(0xc0).readU32(),
             days: days, probe: S, dens: gstats(l, annoy), t: Date.now()};
    MONTHS.push(m); days = 0; S = fresh();
    if (SCHED.length) { if (mi < SCHED.length) apply(SCHED[mi]); else if (ARM !== 'off') apply('off'); }
    mi++;
  }
});
rpc.exports = {
  sched: function (s) { SCHED = s; mi = 0; },
  months: function () { var o = MONTHS; MONTHS = []; return o; },
  set: function (a) { apply(a); return ARM; },
  grid: function () { grid(); return G === null ? null : G.readByteArray(GW * GH); },
  info: function () { grid(); return {gw: GW, gh: GH, grid: G === null ? 0 : 1, groups: GRP === null ? null : GRP.map(function (g) { return g.length; }),
    annoy: A(0x1001f0c0).readU8(), adder: A(0x1001f0be).readU8()}; }
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--blocks", type=int, default=3, help="blocks of (off F FD FD F off)")
    ap.add_argument("--mpw", type=int, default=2, help="game months per window")
    ap.add_argument("--settle", type=int, default=1, help="months at the start of each window marked settle")
    ap.add_argument("--radius", type=int, default=4)
    ap.add_argument("--arms", default="off,F,FD", help="three arms, the block is a b c c b a")
    ap.add_argument("--baseline", type=int, default=0, help="only record N months under the current state, no switching")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--set", default="", help="only switch to this arm (off, F, FD, D) and exit")
    ap.add_argument("--grid", default="", help="only write the class grid (npy, [x, z]) and exit")
    a = ap.parse_args()
    pid = int(os.environ.get("SC3_PID") or sc3io.game_pid())
    if a.start:                                     # unpause BEFORE the attach (sc3pause: attach while paused deadlocks)
        h = sc3io.game_hwnd(pid)
        sc3io.key(h, 0x50)
        time.sleep(1.0)
        sc3io.key(h, 0x30 + a.start)
        time.sleep(2.0)
    sc3pause.require_running(pid, "avflow_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("%RADIUS%", str(a.radius)))
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    api = sc.exports_sync
    print("info", api.info(), flush=True)
    if a.set:
        print("arm now", api.set(a.set))
        s.detach()
        return
    if a.grid:
        import numpy as np
        inf = api.info()
        g = np.frombuffer(api.grid(), dtype=np.uint8).reshape(inf["gh"], inf["gw"]).T.copy()   # [x, z] like ld_probe
        np.save(a.grid, g)
        print("class grid", g.shape, "avenue", int((g == 1).sum()), "boulevard", int((g == 2).sum()), "->", a.grid)
        s.detach()
        return
    sched = []
    if not a.baseline:
        x, y, z = a.arms.split(",")
        win = []
        for _ in range(a.blocks):
            win += [x, y, z, z, y, x]
        for w in win:
            sched += [w] * a.mpw
        api.sched(sched)
    want = (a.baseline or len(sched)) + 1          # the first month after attach is partial
    got = []
    t0 = time.time()
    while len(got) < want:
        time.sleep(1.0)
        for m in api.months():
            if m["idx"] == 0:
                m["partial"] = True
            elif not a.baseline:
                k = m["idx"] - 1                    # month idx ran under sched[idx - 1]
                m["settle"] = (k % a.mpw) < a.settle
            got.append(m)
            p, d = m["probe"], m["dens"]
            print("[%d/%d] month %d arm %-3s days %2d routed %6d failed %5d (%.2f%%) | probe trips %6d arr %6d avenue-use %.1f%% "
                  "av-nodes %.1f%% nodes/trip %.1f | dens av %.1f side %.1f adj %.1f rest %.1f, >=lvl av %d side %d%s" % (
                      len(got), want, m["idx"], m["arm"], m["days"], m["routed"], m["failed"],
                      100.0 * m["failed"] / max(1, m["routed"]), p["trips"], p["arrived"],
                      100.0 * p["arr_any"] / max(1, p["arrived"]), 100.0 * (p["nodes_av"] + p["nodes_bv"]) / max(1, p["nodes_road"]),
                      p["nodes"] / max(1, p["arrived"]),
                      d["av"]["sum"] / max(1, d["av"]["n"]), d["side"]["sum"] / max(1, d["side"]["n"]),
                      d["adj"]["sum"] / max(1, d["adj"]["n"]), d["rest"]["sum"] / max(1, d["rest"]["n"]),
                      d["av"]["hi"], d["side"]["hi"], " (partial)" if m.get("partial") else " (settle)" if m.get("settle") else ""),
                  flush=True)
        if time.time() - t0 > 3 * 3600:
            print("timeout")
            break
        json.dump({"sched": sched, "mpw": a.mpw, "settle": a.settle, "info": api.info(), "months": got},
                  open(a.out, "w"), indent=1)
    if not a.baseline:
        api.set("off")
    info = api.info()
    s.detach()
    json.dump({"sched": sched, "mpw": a.mpw, "settle": a.settle, "info": info, "months": got}, open(a.out, "w"), indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
