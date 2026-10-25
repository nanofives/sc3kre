#!/usr/bin/env python3
r"""bventry_probe.py - what the trip router does on and beside a boulevard (task bventry, 2026-10-24).

Frida on SC3_PID. Boulevard cells = class 2 of sc3netmod's class grid (sc3netmod_avf_grid). Watched cells: every road
cell within --pad cells of the boulevard's bounding box.

Hooks (SimTransit, Ghidra VAs):
  FUN_1000755e  select_next (behind sc3netmod's ld_stub / ld_select: the entry jmp is relocated by Frida, so the hook
                sees the call as the DFS makes it and the result after ld_select). For 1x1 road / bus / ramp nodes
                (types 1, 3, 0x41) on a watched cell, per (cell, entry side): the outcome
                  exit side 0..3 (x-, z-, x+, z+), 'self' (a step onto its own cell), 'other' (non-road node),
                  'budget' (param_3 < node cost +0x18: FUN_1000755e's first test, goto 0x1000847c),
                  'wrong'  (sc3netmod refused it: the piece's matrix row for the entry side is empty; read here with
                            the same call ld_eval makes, piece vt+0x4c(0, layer+0x54, entry)),
                  'none'   (no step for another reason).
                For each boulevard cell the piece id, state and the four matrix rows of the half the router uses
                are read once (QI 0x41658d28 on the occupant, as ld_piece; game calls with exceptions 'propagate').
  FUN_100070d0  route_trip: per trip, whether it stepped on a boulevard cell and whether it arrived; the final path
                (deque back() from the pop loop, FUN_10009e8e returning to 0x100072d8..0x100072f3): used a bv cell.

  set SC3_PID=<pid>
  py -3.12 bventry_probe.py --secs 90 --out trace.json
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
var PAD = %PAD%;
var WH = Memory.alloc(8), G = null, GW = 0, GH = 0;
function cls(x, z) { if (G === null || x < 0 || z < 0 || x >= GW || z >= GH) return 0; return G.add(z * GW + x).readU8(); }
var X0 = 0, X1 = -1, Z0 = 0, Z1 = -1, built = false, nbv = 0;
function build() {
  var p = gridf(WH, WH.add(4)); G = p.isNull() ? null : p; GW = WH.readS32(); GH = WH.add(4).readS32();
  var x, z, a = 1e9, b = -1, c = 1e9, d = -1;
  for (z = 0; z < GH; z++) for (x = 0; x < GW; x++) if (cls(x, z) === 2) { nbv++; if (x < a) a = x; if (x > b) b = x; if (z < c) c = z; if (z > d) d = z; }
  X0 = a - PAD; X1 = b + PAD; Z0 = c - PAD; Z1 = d + PAD; built = true;
  return {bv: nbv, box: [X0, Z0, X1, Z1]};
}
var OPT = {exceptions: 'propagate'};
var MAT = {};          // "x,z" -> {id, state, half, rows[4]}
function matrix(layer, node, key) {
  var m = MAT[key]; if (m !== undefined) return m;
  m = null;
  try {
    var occ = node.readPointer(); if (occ.isNull()) { MAT[key] = null; return null; }
    var vt = occ.readPointer();
    var qi = new NativeFunction(vt.readPointer(), 'char', ['pointer', 'uint32', 'pointer'], 'thiscall', OPT);
    var out = Memory.alloc(4); out.writePointer(ptr(0));
    if (qi(occ, 0x41658d28, out) !== 0 && !out.readPointer().isNull()) {
      var pc = out.readPointer(), pvt = pc.readPointer();
      new NativeFunction(pvt.add(8).readPointer(), 'void', ['pointer'], 'thiscall', OPT)(pc);
      var id = pc.add(0x18).readU32() & 0xffff, state = pc.add(0x14).readU32() >>> 30, half = layer.add(0x54).readU8();
      var conn = new NativeFunction(pvt.add(0x4c).readPointer(), 'void',
        ['pointer', 'uint32', 'uint32', 'uint32', 'pointer', 'pointer', 'pointer', 'pointer'], 'thiscall', OPT);
      var o = Memory.alloc(4), rows = [], rows2 = [];
      for (var hh = 0; hh < 2; hh++) for (var e = 0; e < 4; e++) {
        o.writeU32(0);
        conn(pc, 0, hh, e, o, o.add(1), o.add(2), o.add(3));
        var r = (o.readU8() ? 1 : 0) | (o.add(1).readU8() ? 2 : 0) | (o.add(2).readU8() ? 4 : 0) | (o.add(3).readU8() ? 8 : 0);
        if (hh === half) rows.push(r); else rows2.push(r);
      }
      m = {id: id, state: state, half: half, rows: rows, other_half: rows2};
    }
  } catch (err) { m = {err: String(err)}; }
  MAT[key] = m; return m;
}
var S = null;
function fresh() { return {cells: {}, trips: 0, arrived: 0, trips_bv: 0, trips_bv_arr: 0, trips_bv_final: 0, steps_seen: 0}; }
S = fresh();
var cur = {};
Interceptor.attach(A(0x100070d0), {
  onEnter: function () { if (!built) send({built: build()}); cur[this.threadId] = {bv: 0, fin: 0}; },
  onLeave: function (r) {
    var c = cur[this.threadId]; delete cur[this.threadId]; if (!c) return;
    S.trips++; var ok = (r.toInt32() & 0xff) !== 0; if (ok) S.arrived++;
    if (c.bv) { S.trips_bv++; if (ok) S.trips_bv_arr++; if (c.fin) S.trips_bv_final++; }
  }
});
var BACK_LO = A(0x100072d8), BACK_HI = A(0x100072f3);
Interceptor.attach(A(0x10009e8e), {
  onLeave: function (r) {
    var ra = this.returnAddress; if (ra.compare(BACK_LO) < 0 || ra.compare(BACK_HI) > 0) return;
    var c = cur[this.threadId]; if (!c) return;
    if (cls(r.add(4).readS32(), r.add(8).readS32()) === 2) c.fin = 1;
  }
});
var SIDE = ['x-', 'z-', 'x+', 'z+'];
Interceptor.attach(A(0x1000755e), {
  onEnter: function (a) {
    this.go = 0;
    if (!built) return;
    var n = a[0], t = n.add(0x14).readU8();
    if (t !== 1 && t !== 3 && t !== 0x41) return;
    var x = n.add(4).readS32(); if (x < X0 || x > X1) return;
    var z = n.add(8).readS32(); if (z < Z0 || z > Z1) return;
    if (x !== n.add(0xc).readS32() || z !== n.add(0x10).readS32()) return;
    var k = cls(x, z);
    this.go = 1; this.n = n; this.o = a[1]; this.x = x; this.z = z; this.k = k;
    this.e = n.add(0x1c).readU8() & 3; this.prev = n.add(0x15).readU8();
    this.budget = a[2].toUInt32(); this.cost = n.add(0x18).readU32();
    if (k === 2) { var c = cur[this.threadId]; if (c) c.bv = 1; matrix(this.context.ecx, n, x + ',' + z); }
  },
  onLeave: function (r) {
    if (!this.go) return;
    S.steps_seen++;
    var key = this.x + ',' + this.z, c = S.cells[key];
    if (!c) c = S.cells[key] = {cls: this.k, by: {}};
    var net = (this.prev === 1 || this.prev === 2 || this.prev === 3 || this.prev === 0x41 || this.prev === 0x42 || this.prev === 0x43);
    var ek = net ? SIDE[this.e] : 'p' + this.prev.toString(16);
    var b = c.by[ek] || (c.by[ek] = {});
    var what;
    if ((r.toInt32() & 0xff) !== 0) {
      var o = this.o, t2 = o.add(0x14).readU8(), ox = o.add(4).readS32(), oz = o.add(8).readS32();
      if (t2 !== 1 && t2 !== 3 && t2 !== 0x41) what = 'other' + t2.toString(16);
      else if (ox === this.x && oz === this.z) what = 'self';
      else {
        var dx = ox - this.x, dz = oz - this.z;
        var s = dx < 0 ? 0 : dz < 0 ? 1 : dx > 0 ? 2 : 3;
        what = SIDE[s] + (cls(ox, oz) === 2 ? '>bv' : cls(ox, oz) === 1 ? '>av' : '');
      }
    } else if (this.budget < this.cost) what = 'budget';
    else {
      var m = MAT[key];
      if (net && m && m.rows && this.k === 2) {
        what = (m.rows[this.e] === 0) ? 'wrong' : 'none';
      } else what = 'none';
    }
    b[what] = (b[what] || 0) + 1;
  }
});
rpc.exports = {
  take: function () { var o = S; S = fresh(); o.mat = MAT; return o; },
  ready: function () { return built; },
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=60)
    ap.add_argument("--pad", type=int, default=3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pid = int(os.environ.get("SC3_PID") or sc3io.game_pid())
    sc3pause.require_running(pid, "bventry_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("%PAD%", str(a.pad)))
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
    o["built"] = built
    o["secs"] = a.secs
    json.dump(o, open(a.out, "w"), indent=1)
    print("built", built, "| trips %d arrived %d | stepped on bv %d, of them arrived %d, final path on bv %d" % (
        o["trips"], o["arrived"], o["trips_bv"], o["trips_bv_arr"], o["trips_bv_final"]))


if __name__ == "__main__":
    main()
