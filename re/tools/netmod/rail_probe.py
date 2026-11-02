#!/usr/bin/env python3
r"""rail_probe.py - does a rail station have to touch the track? (task railgap, 2026-11-02). Frida on SC3_PID.

Read-only. Same SimTransit hooks as hwtrips_probe.py (VAs at base 0x10000000):
  FUN_100070d0  route_trip (thiscall, ecx = traffic layer; stack: start node, dest kind, budget base, deposit flag,
                mode flag bytes bus / rail / subway). Return low byte 1 = arrived.
  FUN_10009e8e  deque back(); from route_trip's final pop loop (return address 0x100072d8..0x100072f3) it hands out
                each node of the arrived path. Node: +4 x0, +8 z0, +0xc x1, +0x10 z1 (cells), +0x14 type.
  FUN_1000755e  select_next (thiscall; stack: node, out node, ...). Every call is counted as "type>next type".
Node types: 1 road, 2 highway, 3 ramp-road, 4 rail, 8 subway, 0x14 rail station, 0x18 subway station,
0x30 rail-subway station, 0x50 bus stop, 0x41..0x43 bus, 0x80 origin lot.

  py -3.12 rail_probe.py census --out c.json [--rect X0,Z0,X1,Z1]   flags grid (+0x5c) of every station cell (0x10)
                                                                    and its 4 neighbours; with --rect, the raw flags
  py -3.12 rail_probe.py run --secs 20 --windows 3 --out r.json     per window: trips, arrived, arrived paths holding
                                                                    rail / station nodes, transitions, station rects
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
var L = null;
function rows(off) { return L.add(off).readPointer().add(0xc).readPointer(); }
function u16(x, z) { return rows(0x5c).add(4 * x).readPointer().add(2 * z).readU16(); }
function fresh() { return {trips: 0, arrived: 0, modeargs: {}, arr_types: {}, arr_rail: 0, arr_rsta: 0, trans: {},
  sta_out: {}, sta_in: {}, path_sta: {}}; }
var S = fresh(), cur = {};
function rk(n) { return n.add(4).readS32() + ',' + n.add(8).readS32() + ',' + n.add(0xc).readS32() + ',' + n.add(0x10).readS32(); }
function inc(o, k) { o[k] = (o[k] || 0) + 1; }
Interceptor.attach(A(0x100070d0), {
  onEnter: function (a) {
    L = this.context.ecx;
    inc(S.modeargs, [a[4].toInt32() & 0xff, a[5].toInt32() & 0xff, a[6].toInt32() & 0xff].join(','));
    cur[this.threadId] = {types: {}, sta: {}};
  },
  onLeave: function (r) {
    var c = cur[this.threadId]; delete cur[this.threadId];
    S.trips++;
    if ((r.toInt32() & 0xff) === 0 || !c) return;
    S.arrived++;
    for (var t in c.types) inc(S.arr_types, t);
    if (c.types['4']) S.arr_rail++;
    if (c.types['20']) S.arr_rsta++;
    for (var k in c.sta) inc(S.path_sta, k);
  }
});
var BACK_LO = A(0x100072d8), BACK_HI = A(0x100072f3);
Interceptor.attach(A(0x10009e8e), {
  onLeave: function (r) {
    var ra = this.returnAddress;
    if (ra.compare(BACK_LO) < 0 || ra.compare(BACK_HI) > 0) return;
    var c = cur[this.threadId]; if (!c) return;
    var t = r.add(0x14).readU8(); c.types[String(t)] = 1;
    if (t === 0x14 || t === 0x18 || t === 0x30 || t === 0x50) c.sta[t.toString(16) + '@' + rk(r)] = 1;
  }
});
Interceptor.attach(A(0x1000755e), {
  onEnter: function (a) { this.n = a[0]; this.o = a[1]; this.t = this.n.add(0x14).readU8(); },
  onLeave: function (r) {
    var ok = (r.toInt32() & 0xff) !== 0, nt = ok ? this.o.add(0x14).readU8() : -1;
    inc(S.trans, this.t.toString(16) + '>' + (ok ? nt.toString(16) : 'x'));
    if (this.t === 0x14) inc(S.sta_out, rk(this.n) + '>' + (ok ? nt.toString(16) : 'x'));
    if (ok && nt === 0x14) inc(S.sta_in, this.t.toString(16) + '>' + rk(this.o));
  }
});
var days = 0;
Interceptor.attach(Process.getModuleByName('SIMCITY.DLL').base.add(0xaa4d), function () { days++; });
rpc.exports = {
  ready: function () { return L !== null; },
  take: function () { var o = S; S = fresh(); o.days = days; days = 0; return o; },
  census: function (rect) {
    var w = L.add(0x14).readS32(), h = L.add(0x18).readS32(), out = {w: w, h: h, sta: [], rail_cells: 0, raw: []};
    for (var x = 0; x < w; x++) for (var z = 0; z < h; z++) {
      var f = u16(x, z);
      if (f & 4) out.rail_cells++;
      if (!(f & 0x10)) continue;
      var nb = [];
      [[x - 1, z], [x + 1, z], [x, z - 1], [x, z + 1]].forEach(function (p) {
        nb.push((p[0] < 0 || p[1] < 0 || p[0] >= w || p[1] >= h) ? -1 : u16(p[0], p[1])); });
      out.sta.push([x, z, f, nb]);
    }
    if (rect) for (var z = rect[1]; z <= rect[3]; z++) { var row = [];
      for (var x = rect[0]; x <= rect[2]; x++) row.push(u16(x, z)); out.raw.push(row); }
    return out;
  }
};
"""


def attach():
    pid = int(os.environ.get("SC3_PID") or sc3io.game_pid())
    sc3pause.require_running(pid, "rail_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    t0 = time.time()
    while not sc.exports_sync.ready():
        if time.time() - t0 > 120:
            raise SystemExit("no route_trip call seen (game paused?)")
        time.sleep(0.5)
    return s, sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["census", "run"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--secs", type=float, default=20)
    ap.add_argument("--windows", type=int, default=3)
    ap.add_argument("--rect", default="")
    a = ap.parse_args()
    s, sc = attach()
    if a.cmd == "census":
        out = sc.exports_sync.census([int(v) for v in a.rect.split(",")] if a.rect else None)
        print("rail cells %d, station cells %d" % (out["rail_cells"], len(out["sta"])))
    else:
        sc.exports_sync.take()
        wins = []
        for i in range(a.windows):
            time.sleep(a.secs)
            o = sc.exports_sync.take()
            wins.append(o)
            tr = {k: v for k, v in o["trans"].items() if any(t in k.split(">") for t in ("4", "14"))}
            print("[%d/%d] days %d trips %d arrived %d with-rail %d with-railstation %d | modeargs %s | rail/station "
                  "steps %s" % (i + 1, a.windows, o["days"], o["trips"], o["arrived"], o["arr_rail"], o["arr_rsta"],
                                o["modeargs"], tr), flush=True)
        out = {"windows": wins}
    s.detach()
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
