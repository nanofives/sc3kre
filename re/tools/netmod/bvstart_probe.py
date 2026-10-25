#!/usr/bin/env python3
r"""bvstart_probe.py - where trips that start next to a boulevard step first (task bventry, 2026-10-25).

Frida on SC3_PID, read-only. A trip's start node (type 0x80, the lot) is expanded by SimTransit FUN_1000755e's radius
scan: every road cell within r of the lot rect (corners excluded), r = layer+0xc5 / +0xc6 / +0xc7 by the lot's kind
from FUN_100057f6 (thiscall on the layer: mov edi, ecx ... ret 8; (occupant, &kind)), else layer+0xc8. The keep rule is the ring scan's: the busiest road
candidate below TrafficAnnoyanceLevel (DAT_1001f0c0) wins [CONFIRMED @ 0x1000755e, the 0x80 branch]. AVFIRST does not
act on start nodes (sc3netmod ld_select passes type 0x80 straight to the game).

Per start whose scan box (radius from the same call) holds a boulevard cell: the candidates offered (road, not visited
by 0x80), whether a boulevard / avenue cell was open below the level, the class of the cell taken and the density of
the taken cell vs the best open boulevard cell.

  set SC3_PID=<pid>
  py -3.12 bvstart_probe.py --secs 60 --out start.json
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
var kindf = new NativeFunction(A(0x100057f6), 'uint32', ['pointer', 'pointer', 'pointer'], 'thiscall', {exceptions: 'propagate'});
var WH = Memory.alloc(8), G = null, GW = 0, GH = 0, built = false;
function build() { var p = gridf(WH, WH.add(4)); G = p.isNull() ? null : p; GW = WH.readS32(); GH = WH.add(4).readS32(); built = true; }
function cls(x, z) { if (G === null || x < 0 || z < 0 || x >= GW || z >= GH) return 0; return G.add(z * GW + x).readU8(); }
function rows(l, off) { return l.add(off).readPointer().add(0xc).readPointer(); }
function fresh() { return {starts: 0, near: 0, bv_open: 0, av_open: 0, took: {bv: 0, av: 0, plain: 0, station: 0, none: 0},
  took_when_bv_open: {bv: 0, av: 0, plain: 0, station: 0, none: 0}, dens_taken: 0, dens_bv: 0, n_dens: 0, kinds: {}, radius: {}}; }
var S = fresh();
var KB = Memory.alloc(4);
Interceptor.attach(A(0x1000755e), {
  onEnter: function (a) {
    this.go = 0;
    if (!built) build();
    var n = a[0]; if (n.add(0x14).readU8() !== 0x80) return;
    S.starts++;
    var L = this.context.ecx, occ = n.readPointer(), r, kind = -1;
    if (occ.isNull()) r = L.add(0xc8).readU8();
    else { KB.writeU8(0xee); var ok = kindf(L, occ, KB) & 0xff; kind = KB.readU8();
      if (!ok) return;
      r = kind === 0 ? L.add(0xc5).readU8() : kind === 1 ? L.add(0xc6).readU8() : kind === 2 ? L.add(0xc7).readU8() : L.add(0xc8).readU8(); }
    var W = L.add(0x14).readS32(), H = L.add(0x18).readS32();
    var x0 = Math.max(0, n.add(4).readS32() - r), z0 = Math.max(0, n.add(8).readS32() - r);
    var x1 = Math.min(W - 1, n.add(0xc).readS32() + r), z1 = Math.min(H - 1, n.add(0x10).readS32() + r);
    var bx0 = n.add(4).readS32() - r, bz0 = n.add(8).readS32() - r, bx1 = n.add(0xc).readS32() + r, bz1 = n.add(0x10).readS32() + r;
    var hasbv = 0, bvopen = 0, avopen = 0, bvbest = -1, x, z, lvl = A(0x1001f0c0).readU8();
    var fr = rows(L, 0x5c), vr = rows(L, 0x78), dr = rows(L, 0x6c);
    for (x = x0; x <= x1; x++) { var fx = fr.add(4 * x).readPointer(), vx = vr.add(4 * x).readPointer(), dx = dr.add(4 * x).readPointer();
      for (z = z0; z <= z1; z++) {
        if ((x === bx0 || x === bx1) && (z === bz0 || z === bz1)) continue;
        var k = cls(x, z); if (k === 2) hasbv = 1;
        if (!k) continue;
        var f = fx.add(2 * z).readU16(); if ((f & 0x11) !== 1) continue;
        if ((vx.add(z).readU8() & 0x80) === 0x80) continue;
        var d = dx.add(z).readU8(); if (d >= lvl) continue;
        if (k === 2) { bvopen = 1; if (d > bvbest) bvbest = d; } else avopen = 1;
      } }
    if (!hasbv) return;
    S.near++; S.kinds[kind] = (S.kinds[kind] || 0) + 1; S.radius[r] = (S.radius[r] || 0) + 1;
    if (bvopen) S.bv_open++; if (avopen) S.av_open++;
    this.go = 1; this.o = a[1]; this.bvopen = bvopen; this.bvbest = bvbest; this.L = L;
  },
  onLeave: function (ret) {
    if (!this.go) return;
    var what = 'none', o = this.o;
    if ((ret.toInt32() & 0xff) !== 0) {
      var t = o.add(0x14).readU8(), ox = o.add(4).readS32(), oz = o.add(8).readS32();
      if (t !== 1 && t !== 0x41 && t !== 3) what = 'station';
      else { var k = cls(ox, oz); what = k === 2 ? 'bv' : k === 1 ? 'av' : 'plain';
        if (this.bvopen) { S.dens_taken += rows(this.L, 0x6c).add(4 * ox).readPointer().add(oz).readU8(); S.dens_bv += this.bvbest; S.n_dens++; } }
    }
    S.took[what]++; if (this.bvopen) S.took_when_bv_open[what]++;
  }
});
rpc.exports = { take: function () { var o = S; S = fresh(); return o; } };
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=60)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    pid = int(os.environ.get("SC3_PID") or sc3io.game_pid())
    sc3pause.require_running(pid, "bvstart_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    api = sc.exports_sync
    time.sleep(2)
    api.take()
    time.sleep(a.secs)
    o = api.take()
    s.detach()
    o["secs"] = a.secs
    json.dump(o, open(a.out, "w"), indent=1)
    nd = max(1, o["n_dens"])
    print("starts %d, with a boulevard cell in the scan box %d (lot kinds %s, radius %s)" % (o["starts"], o["near"], o["kinds"], o["radius"]))
    print("  boulevard cell open below the level %d, avenue cell open %d" % (o["bv_open"], o["av_open"]))
    print("  first step taken:", o["took"], "| when a boulevard cell was open:", o["took_when_bv_open"])
    print("  density of the cell taken %.1f vs the best open boulevard cell %.1f (means, %d starts)" % (o["dens_taken"] / nd, o["dens_bv"] / nd, o["n_dens"]))


if __name__ == "__main__":
    main()
