#!/usr/bin/env python3
r"""bvbranch_probe.py - why trips that enter a boulevard back out of it (task bventry, 2026-10-24).

Frida on SC3_PID. Boulevard cells = class 2 of sc3netmod_avf_grid. Per trip (route_trip FUN_100070d0, per thread):
a BRANCH starts when a select_next step (FUN_1000755e) goes from a non-boulevard cell A onto a boulevard cell; it
ends when select_next is called again for a node on A (the DFS came back: the branch failed), or the trip ends while
it is open (arrived: the branch holds the final path). Inside a branch every select_next outcome is counted: step /
'budget' (param_3 < node cost +0x18, FUN_1000755e's first test) / 'none'. Budget headroom = (param_3 - cost) / param_3.
The same headroom is sampled for every road step in the city as the control.
Also reads the destination bitmaps layer+0x84 / +0x88 / +0x8c (FUN_1000559e marks every cell within a per-kind radius
of a destination lot; FUN_10008a94 arrives on a set bit) and flags & 0x400 at every boulevard cell vs all road cells.

  set SC3_PID=<pid>
  py -3.12 bvbranch_probe.py --secs 60 --out branch.json
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
var WH = Memory.alloc(8), G = null, GW = 0, GH = 0, built = false, L0 = null;
function build() { var p = gridf(WH, WH.add(4)); G = p.isNull() ? null : p; GW = WH.readS32(); GH = WH.add(4).readS32(); built = true; }
var BOX = %BOX%;
function cls(x, z) {
  if (BOX) return (x >= BOX[0] && x <= BOX[2] && z >= BOX[1] && z <= BOX[3]) ? 2 : 0;
  if (G === null || x < 0 || z < 0 || x >= GW || z >= GH) return 0; return G.add(z * GW + x).readU8(); }
function z11() { var a = []; for (var i = 0; i < 11; i++) a.push(0); return a; }
function fresh() { return {trips: 0, arrived: 0, branches: 0, br_arrived: 0, br_failed: 0, br_open_at_end: 0,
  br_calls: 0, br_ok: 0, br_budget: 0, br_none: 0, hr_branch: z11(), hr_branch_fail: z11(), hr_all: z11(),
  all_calls: 0, all_budget: 0, all_none: 0, kinds: [0, 0, 0, 0, 0], kinds_br: [0, 0, 0, 0, 0],
  br_maxfrac_fail: z11(), br_len_fail: 0, entries: {}, fin_set: [0, 0, 0, 0, 0], arr_kind: [0, 0, 0, 0, 0], fin_cells: 0, fin_cells_set: 0}; }
var S = fresh(), cur = {};
function hb(h, budget, cost) { var f = budget > 0 ? (budget - cost) / budget : 0; var i = Math.max(0, Math.min(10, Math.floor(f * 10))); h[i]++; }
Interceptor.attach(A(0x100070d0), {
  onEnter: function (a) { if (!built) build(); if (L0 === null) L0 = this.context.ecx;
    cur[this.threadId] = {br: null, kind: a[1].toUInt32(), fin: 0, nfin: 0, nfs: 0}; },
  onLeave: function (r) {
    var c = cur[this.threadId]; delete cur[this.threadId]; if (!c) return;
    S.trips++; var ok = (r.toInt32() & 0xff) !== 0; if (ok) S.arrived++;
    S.kinds[Math.min(4, c.kind)]++;
    if (ok) { S.arr_kind[Math.min(4, c.kind)]++; if (c.fin) S.fin_set[Math.min(4, c.kind)]++; S.fin_cells += c.nfin; S.fin_cells_set += c.nfs; }
    if (c.br) { if (ok) S.br_arrived++; else S.br_open_at_end++; }
  }
});
var BACK_LO = A(0x100072d8), BACK_HI = A(0x100072f3);
Interceptor.attach(A(0x10009e8e), {
  onLeave: function (r) {
    var ra = this.returnAddress; if (ra.compare(BACK_LO) < 0 || ra.compare(BACK_HI) > 0) return;
    var c = cur[this.threadId]; if (!c) return;
    var t = r.add(0x14).readU8(); if (t !== 1 && t !== 0x41) return;
    c.nfin++; if (cls(r.add(4).readS32(), r.add(8).readS32()) === 2) { c.fin = 1; c.nfs++; }
  }
});
Interceptor.attach(A(0x1000755e), {
  onEnter: function (a) {
    this.go = 0; if (!built) return;
    var c = cur[this.threadId]; if (!c) return;
    var n = a[0];
    this.c = c; this.o = a[1]; this.t = n.add(0x14).readU8();
    this.x = n.add(4).readS32(); this.z = n.add(8).readS32();
    this.budget = a[2].toUInt32(); this.cost = n.add(0x18).readU32();
    if (c.br && this.x === c.br.ax && this.z === c.br.az) {
      S.br_failed++; S.br_len_fail += c.br.calls; S.br_maxfrac_fail[Math.min(10, Math.floor(c.br.maxfrac * 10))]++;
      hb(S.hr_branch_fail, c.br.budget, c.br.cost0);
      c.br = null;
    }
    this.go = 1;
  },
  onLeave: function (r) {
    if (!this.go) return;
    var c = this.c, ok = (r.toInt32() & 0xff) !== 0, what = ok ? 'ok' : (this.budget < this.cost ? 'budget' : 'none');
    if (this.t === 1 || this.t === 0x41) {
      S.all_calls++; if (what === 'budget') S.all_budget++; else if (what === 'none') S.all_none++;
      if (ok) hb(S.hr_all, this.budget, this.cost);
    }
    if (c.br) {
      S.br_calls++; c.br.calls++; if (what === 'ok') S.br_ok++; else if (what === 'budget') S.br_budget++; else S.br_none++;
      var f = this.budget > 0 ? this.cost / this.budget : 0; if (f > c.br.maxfrac) c.br.maxfrac = f;
      return;
    }
    if (!ok || cls(this.x, this.z) === 2) return;
    var o = this.o, ox = o.add(4).readS32(), oz = o.add(8).readS32();
    if (cls(ox, oz) !== 2) return;
    S.branches++; S.kinds_br[Math.min(4, c.kind)]++;
    var k = this.x + ',' + this.z; S.entries[k] = (S.entries[k] || 0) + 1;
    hb(S.hr_branch, this.budget, this.cost);
    c.br = {ax: this.x, az: this.z, budget: this.budget, cost0: this.cost, calls: 0, maxfrac: 0};
  }
});
function bit(bm, x, z) { if (bm.isNull()) return 0; var rows = bm.add(0x10).readPointer(); if (rows.isNull()) return 0;
  var row = rows.add(4 * x).readPointer(); if (row.isNull()) return 0;
  return (row.add((z >>> 5) * 4).readU32() >>> (z & 31)) & 1; }
rpc.exports = {
  take: function () { var o = S; S = fresh(); return o; },
  ready: function () { return built && L0 !== null; },
  bitmaps: function () {
    var L = L0, W = L.add(0x14).readS32(), H = L.add(0x18).readS32();
    var bms = [L.add(0x84).readPointer(), L.add(0x88).readPointer(), L.add(0x8c).readPointer()];
    var res = {bv: {n: 0, k0: 0, k1: 0, k2: 0, f400: 0, any: 0}, road: {n: 0, k0: 0, k1: 0, k2: 0, f400: 0, any: 0}, bvcells: {}};
    for (var x = 0; x < W; x++) { var fr = L.add(0x5c).readPointer().add(0xc).readPointer().add(4 * x).readPointer();
      for (var z = 0; z < H; z++) {
        var f = fr.add(2 * z).readU16(); if ((f & 0x11) !== 1) continue;
        var s = cls(x, z) === 2 ? res.bv : res.road;
        var b0 = bit(bms[0], x, z), b1 = bit(bms[1], x, z), b2 = bit(bms[2], x, z), q = (f & 0x400) ? 1 : 0;
        s.n++; s.k0 += b0; s.k1 += b1; s.k2 += b2; s.f400 += q; if (b0 || b1 || b2 || q) s.any++;
        if (s === res.bv) res.bvcells[x + ',' + z] = '' + b0 + b1 + b2 + q;
      } }
    res.radius = [L.add(0xc5).readU8(), L.add(0xc6).readU8(), L.add(0xc7).readU8()];
    return res;
  },
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=60)
    ap.add_argument("--out", required=True)
    ap.add_argument("--box", default="", help="x0,z0,x1,z1: road cells in this box are the set (instead of class 2)")
    a = ap.parse_args()
    pid = int(os.environ.get("SC3_PID") or sc3io.game_pid())
    sc3pause.require_running(pid, "bvbranch_probe")
    s = frida.attach(pid)
    box = "[%s]" % a.box if a.box else "null"
    sc = s.create_script(JS.replace("%BOX%", box))
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    api = sc.exports_sync
    t0 = time.time()
    while not api.ready() and time.time() - t0 < 60:
        time.sleep(0.5)
    api.take()
    time.sleep(a.secs)
    o = api.take()
    try:
        o["bitmaps"] = api.bitmaps()
    except Exception as e:
        o["bitmaps"] = {"radius": None, "bv": str(e), "road": None}
    s.detach()
    o["secs"] = a.secs
    json.dump(o, open(a.out, "w"), indent=1)
    b = o["bitmaps"]
    print("trips %d arrived %d | branches into the boulevard %d: arrived on it %d, failed back to A %d, trip ended inside %d" % (
        o["trips"], o["arrived"], o["branches"], o["br_arrived"], o["br_failed"], o["br_open_at_end"]))
    print("inside branches: calls %d ok %d budget %d none %d | all road calls %d budget %d none %d" % (
        o["br_calls"], o["br_ok"], o["br_budget"], o["br_none"], o["all_calls"], o["all_budget"], o["all_none"]))
    print("headroom deciles at branch start", o["hr_branch"], "| failed branches", o["hr_branch_fail"], "| all road steps", o["hr_all"])
    print("max cost/budget in failed branches (deciles)", o["br_maxfrac_fail"],
          "mean calls per failed branch %.1f" % (o["br_len_fail"] / max(1, o["br_failed"])))
    print("trip kinds", o["kinds"], "in branches", o["kinds_br"], "| entries", o["entries"])
    print("arrived by kind", o["arr_kind"], "| arrived trips with a final-path road cell in the set, by kind", o["fin_set"],
          "| final-path road cells in the set %d of %d (%.3f%%)" % (o["fin_cells_set"], o["fin_cells"], 100.0 * o["fin_cells_set"] / max(1, o["fin_cells"])))
    print("bitmaps radius", b["radius"], "bv", b["bv"], "road", b["road"])


if __name__ == "__main__":
    main()
