#!/usr/bin/env python3
r"""bvtrace_probe.py - which trips come near a boulevard, and where they turn away (task avflow, 2026-10-24).

Frida on SC3_PID, read-only. Boulevard cells = class 2 of sc3netmod's class grid (sc3netmod_avf_grid). Sets:
  bv    the boulevard cells
  adj   road cells (flags & 0x51 == 1) 4-adjacent to a bv cell and not bv: the only cells a road step can enter the
        boulevard from (the ring scan 0x10007a63 offers the 4 sides and the centre)
  near  road cells within --n cells (Chebyshev) of a bv cell, not bv

Hooks (SimTransit, Ghidra VAs):
  FUN_100070d0  route_trip: per trip on this thread; return low byte 1 = arrived.
  FUN_10009e8e  deque back() from the final pop loop (return 0x100072d8..0x100072f3): the arrived path's nodes. Per
                arrived trip: touched near / adj, used bv; for a path that stood on adj cells and never on bv, every
                such adj cell is counted as a turn-away cell.
  FUN_1000755e  select_next, for 1x1 road / bus nodes (types 1, 0x41) on an adj cell: onEnter, before sc3netmod's
                ld_select closes anything (the entry jmp is relocated by Frida), each of the five candidates is read
                (road flag, visited bits of the node type in +0x78, density +0x6c, class); onLeave, the chosen cell's
                class. A step with a bv candidate that is open (not visited, density below TrafficAnnoyanceLevel) is
                an OFFER; its outcome: took bv / took avenue / took plain road / no step. Offers with an open avenue
                candidate too are the cases BVFIRST changes.

  set SC3_PID=<pid>
  py -3.12 bvtrace_probe.py --secs 60 --n 3 --out trace.json
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
var N = Process.getModuleByName('sc3netmod.dll');
var gridf = new NativeFunction(N.getExportByName('sc3netmod_avf_grid'), 'pointer', ['pointer', 'pointer']);
var WH = Memory.alloc(8), G = null, GW = 0, GH = 0, NR = %N%;
function cls(x, z) { if (G === null || x < 0 || z < 0 || x >= GW || z >= GH) return 0; return G.add(z * GW + x).readU8(); }
var L = null, SET = null;     // SET[x * H + z]: 1 near, 2 adj (also near), 3 bv
var W = 0, H = 0;
function rowp(off, x) { return L.add(off).readPointer().add(0xc).readPointer().add(4 * x).readPointer(); }
function build() {
  var p = gridf(WH, WH.add(4)); G = p.isNull() ? null : p; GW = WH.readS32(); GH = WH.add(4).readS32();
  W = L.add(0x14).readS32(); H = L.add(0x18).readS32(); SET = new Uint8Array(W * H);
  var x, z, dx, dz, bv = [];
  for (x = 0; x < W; x++) for (z = 0; z < H; z++) if (cls(x, z) === 2) { bv.push([x, z]); SET[x * H + z] = 3; }
  function road(x, z) { return x >= 0 && z >= 0 && x < W && z < H && (rowp(0x5c, x).add(2 * z).readU16() & 0x51) === 1; }
  bv.forEach(function (c) {
    for (dx = -NR; dx <= NR; dx++) for (dz = -NR; dz <= NR; dz++) { var xx = c[0] + dx, zz = c[1] + dz;
      if (road(xx, zz) && SET[xx * H + zz] === 0) SET[xx * H + zz] = 1; }
    [[-1, 0], [1, 0], [0, -1], [0, 1]].forEach(function (d) { var xx = c[0] + d[0], zz = c[1] + d[1];
      if (road(xx, zz) && SET[xx * H + zz] !== 3) SET[xx * H + zz] = 2; });
  });
  var n = [0, 0, 0, 0]; for (x = 0; x < W * H; x++) n[SET[x]]++;
  return {bv: n[3], adj: n[2], near: n[1] + n[2], bvcells: bv};
}
function st(x, z) { return (SET === null || x < 0 || z < 0 || x >= W || z >= H) ? 0 : SET[x * H + z]; }
var S = null;
function fresh() { return {trips: 0, arrived: 0, failed: 0, arr_near: 0, arr_adj: 0, arr_bv: 0, fail_near: 0,
  turn: {}, steps_adj: 0, offer: 0, offer_av: 0, took: {bv: 0, av: 0, plain: 0, none: 0, other: 0},
  took_av_when_both: 0, took_bv_when_both: 0, bv_visited: 0, bv_hi: 0, nodecell: {}}; }
S = fresh();
var cur = {};
Interceptor.attach(A(0x100070d0), {
  onEnter: function () { L = this.context.ecx; if (SET === null) send({built: build()}); cur[this.threadId] = {near: 0, adj: [], bv: 0, seen: 0}; },
  onLeave: function (r) {
    var c = cur[this.threadId]; delete cur[this.threadId];
    S.trips++;
    var ok = (r.toInt32() & 0xff) !== 0;
    if (!c) return;
    if (!ok) { S.failed++; if (c.seen) S.fail_near++; return; }
    S.arrived++;
    if (c.near) S.arr_near++;
    if (c.adj.length) S.arr_adj++;
    if (c.bv) S.arr_bv++;
    else for (var i = 0; i < c.adj.length; i++) S.turn[c.adj[i]] = (S.turn[c.adj[i]] || 0) + 1;
  }
});
var BACK_LO = A(0x100072d8), BACK_HI = A(0x100072f3);
Interceptor.attach(A(0x10009e8e), {
  onLeave: function (r) {
    var ra = this.returnAddress;
    if (ra.compare(BACK_LO) < 0 || ra.compare(BACK_HI) > 0) return;
    var c = cur[this.threadId]; if (!c) return;
    var x = r.add(4).readS32(), z = r.add(8).readS32(), s = st(x, z);
    if (s >= 1) c.near = 1;
    if (s === 2) { var k = x + ',' + z; if (c.adj.indexOf(k) < 0) c.adj.push(k); }
    if (s === 3) c.bv = 1;
  }
});
var DX = [[-1, 0], [0, -1], [0, 0], [0, 1], [1, 0]];
Interceptor.attach(A(0x1000755e), {
  onEnter: function (a) {
    this.go = 0;
    if (SET === null || L === null) return;
    var n = a[0], t = n.add(0x14).readU8();
    if (t !== 1 && t !== 0x41) return;
    var x = n.add(4).readS32(), z = n.add(8).readS32();
    if (x !== n.add(0xc).readS32() || z !== n.add(0x10).readS32()) return;
    var s0 = st(x, z);
    if (s0 >= 1) { var cc = cur[this.threadId]; if (cc) cc.seen = 1; }
    if (s0 !== 2) return;
    this.go = 1; this.o = a[1]; this.k = x + ',' + z;
    var lvl = A(0x1001f0c0).readU8(), bvopen = 0, avopen = 0;
    for (var i = 0; i < 5; i++) {
      var cx = x + DX[i][0], cz = z + DX[i][1];
      if (cx < 0 || cz < 0 || cx >= W || cz >= H) continue;
      var f = rowp(0x5c, cx).add(2 * cz).readU16(); if ((f & 0x11) !== 1) continue;
      var k2 = cls(cx, cz), vis = (rowp(0x78, cx).add(cz).readU8() & t) === t, d = rowp(0x6c, cx).add(cz).readU8();
      if (k2 === 2) { if (vis) S.bv_visited++; else if (d >= lvl) S.bv_hi++; else bvopen = 1; }
      if (k2 === 1 && !vis && d < lvl) avopen = 1;
    }
    this.bvopen = bvopen; this.avopen = avopen;
  },
  onLeave: function (r) {
    if (!this.go) return;
    S.steps_adj++;
    var nc = S.nodecell[this.k] || (S.nodecell[this.k] = {steps: 0, offer: 0, bv: 0, av: 0, plain: 0, none: 0});
    nc.steps++;
    if (!this.bvopen) return;
    S.offer++; nc.offer++;
    if (this.avopen) S.offer_av++;
    var ok = (r.toInt32() & 0xff) !== 0, what = 'none';
    if (ok) { var t2 = this.o.add(0x14).readU8(); var k = cls(this.o.add(4).readS32(), this.o.add(8).readS32());
      what = (t2 !== 1 && t2 !== 3 && t2 !== 0x41) ? 'other' : k === 2 ? 'bv' : k === 1 ? 'av' : 'plain'; }
    S.took[what]++; if (nc[what] !== undefined) nc[what]++;
    if (this.avopen) { if (what === 'av') S.took_av_when_both++; if (what === 'bv') S.took_bv_when_both++; }
  }
});
rpc.exports = { take: function () { var o = S; S = fresh(); return o; }, ready: function () { return SET !== null; } };
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=60)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pid = int(os.environ.get("SC3_PID") or sc3io.game_pid())
    sc3pause.require_running(pid, "bvtrace_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("%N%", str(a.n)))
    built = {}
    sc.on("message", lambda m, d: built.update(m["payload"]["built"]) if m.get("type") == "send" else print(m, flush=True))
    sc.load()
    api = sc.exports_sync
    t0 = time.time()
    while not api.ready() and time.time() - t0 < 60:
        time.sleep(0.5)
    api.take()
    time.sleep(a.secs)
    o = api.take()
    s.detach()
    o["sets"] = {k: v for k, v in built.items() if k != "bvcells"}
    o["bvcells"] = built.get("bvcells")
    o["secs"] = a.secs
    json.dump(o, open(a.out, "w"), indent=1)
    arr = max(1, o["arrived"])
    print("sets: bv %s adj %s near %s" % (o["sets"].get("bv"), o["sets"].get("adj"), o["sets"].get("near")))
    print("trips %d arrived %d failed %d | arrived paths: near %d (%.2f%%), on adj %d (%.2f%%), on bv %d (%.2f%%) | failed after a step near: %d" % (
        o["trips"], o["arrived"], o["failed"], o["arr_near"], 100.0 * o["arr_near"] / arr, o["arr_adj"], 100.0 * o["arr_adj"] / arr,
        o["arr_bv"], 100.0 * o["arr_bv"] / arr, o["fail_near"]))
    print("router steps on adj cells %d; offers (open bv candidate) %d, of which an avenue candidate also open %d" % (
        o["steps_adj"], o["offer"], o["offer_av"]))
    print("  outcome of offers:", o["took"], "| both open: took avenue %d, took bv %d" % (o["took_av_when_both"], o["took_bv_when_both"]))
    print("  bv candidate already visited %d, at/above level %d" % (o["bv_visited"], o["bv_hi"]))
    top = sorted(o["turn"].items(), key=lambda kv: -kv[1])[:12]
    print("turn-away cells (arrived paths that stood on this adj cell and never on bv):", top)
    for k, v in sorted(o["nodecell"].items(), key=lambda kv: -kv[1]["steps"])[:12]:
        print("  adj cell %-9s %s" % (k, v))


if __name__ == "__main__":
    main()
