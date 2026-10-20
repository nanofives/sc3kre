#!/usr/bin/env python3
r"""lk_probe.py - live, read-only probe for the lanekit arms (verify/lanekit/PRE.md). Frida on SC3_PID.

Hooks (nothing is written to the game):
  SIMNTWRK FUN_1000cd35  piece connectivity query (vt+0x4c). Counted when the caller is SimTransit.dll: by piece id
                         (occupant +0x18 low 16 bits), state (+0x14 >> 30), half argument, and whether any of the
                         four outputs came back true.
  SimTransit FUN_1000755e  the router's next-cell step: captures the traffic layer (ecx) once; +0x54 is read and
                         the live density grids +0x6c (surface), +0x70 (highway nodes), +0x74 are summed over the --cells list
                         and over the map every sample.
  SIMCITY FUN_1000aa4d   the day fire (ecx = clock): days counted, clock +0x4c read.
  STRTSIM FUN_1001c750   a street-sim vehicle leaving cell (x, z) by an exit edge (+0x16 = exit code): counted per
                         (x, z, code, result != 0) for the cells in --watch.

  py -3.12 lk_probe.py --secs 600 --every 20 --cells hw.json --watch watch.json --out run.jsonl
cells / watch: JSON lists of [x, z] in save order (network_layer tuple x, y). The STRTSIM hook keys cells by
its own (param_1, param_2); --all records every cell so the orientation can be settled offline. Output: one JSON object per sample (cumulative counters).
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
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
function mod(n) { return Process.getModuleByName(n); }
var NT = mod('SIMNTWRK.DLL').base, TR = mod('SimTransit.dll'), SC = mod('SIMCITY.DLL').base, SS = mod('STRTSIM.DLL').base;
function A(b, va) { return b.add(va - 0x10000000); }
var CELLS = %CELLS%, ALLW = %ALLW%, WATCH = {}; %WATCH%.forEach(function (c) { WATCH[c[0] + ',' + c[1]] = 1; });
var conn = {}, layer = null, half54 = null, days = 0, dayno = null, clock = null, trans = {}, nconn = 0;
var trLo = TR.base, trHi = TR.base.add(TR.size);
Interceptor.attach(A(NT, 0x1000cd35), {
  onEnter: function (a) {
    var ra = this.returnAddress;
    this.go = ra.compare(trLo) >= 0 && ra.compare(trHi) < 0;
    if (!this.go) return;
    this.occ = this.context.ecx; this.half = a[1].toInt32() & 0xff; this.dir = a[2].toInt32();
    this.o = [a[3], a[4], a[5], a[6]];
  },
  onLeave: function () {
    if (!this.go) return;
    var any = 0; for (var i = 0; i < 4; i++) any |= this.o[i].readU8() ? 1 : 0;
    var id = this.occ.add(0x18).readU16(), st = this.occ.add(0x14).readU32() >>> 30;
    var k = id + '/' + st + '/h' + this.half + '/' + (any ? 'T' : 'F');
    conn[k] = (conn[k] || 0) + 1; nconn++;
  }
});
var l755e = Interceptor.attach(A(TR.base, 0x1000755e), function () {     // hot path: detached after the first call
  if (layer === null) { layer = this.context.ecx; half54 = layer.add(0x54).readU8(); setTimeout(function () { l755e.detach(); }, 0); }
});
Interceptor.attach(A(SC, 0x1000aa4d), function () { days++; clock = this.context.ecx; });
Interceptor.attach(A(SS, 0x1001c750), {
  onEnter: function (a) {
    var x = a[0].toInt32(), z = a[1].toInt32();
    this.k = (ALLW || WATCH[x + ',' + z]) ? x + ',' + z + ',' + a[2].add(0x16).readU8() : null;
  },
  onLeave: function (r) {
    if (this.k === null) return;
    var k = this.k + ',' + (r.isNull() ? 0 : 1);
    trans[k] = (trans[k] || 0) + 1;
  }
});
function sample() {
  var o = {t: Date.now(), days: days, dayno: clock ? clock.add(0x4c).readU32() : null, half54: half54, nconn: nconn,
           conn: conn, trans: trans};
  if (layer !== null) {
    // every SimTransit grid is rows[save x][save z] (flags +0x5c: the 514 straight-highway cells read 0x2 that way).
    // FUN_10006edd deposits mask 0x35 -> +0x6c, mask 2 (highway nodes, type 2) -> +0x70, mask 8 -> +0x74
    var w = layer.add(0x14).readU32(), h = layer.add(0x18).readU32();
    [0x6c, 0x70, 0x74].forEach(function (off) {
      var rows = layer.add(off).readPointer().add(0xc).readPointer(), s = 0, tot = 0;
      for (var i = 0; i < CELLS.length; i++) s += rows.add(4 * CELLS[i][0]).readPointer().add(CELLS[i][1]).readU8();
      for (var x = 0; x < w; x++) { var b = new Uint8Array(rows.add(4 * x).readPointer().readByteArray(h)); for (var z = 0; z < h; z++) tot += b[z]; }
      o['cells_' + off.toString(16)] = s; o['map_' + off.toString(16)] = tot;
    });
    o.w = w; o.h = h;
  }
  send(o);
}
rpc.exports = {sample: sample};
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=600)
    ap.add_argument("--every", type=float, default=20)
    ap.add_argument("--cells", default=None)
    ap.add_argument("--watch", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--all", action="store_true", help="count street-sim transitions in every cell (no --watch filter)")
    a = ap.parse_args(argv)
    cells = json.load(open(a.cells)) if a.cells else []
    watch = json.load(open(a.watch)) if a.watch else []
    js = JS.replace("%ALLW%", "true" if a.all else "false").replace("%CELLS%", json.dumps(cells)).replace("%WATCH%", json.dumps(watch))
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "lk_probe")
    s = frida.attach(pid)
    sc = s.create_script(js)
    got = []
    sc.on("message", lambda m, d: got.append(m.get("payload") if m.get("type") == "send" else {"error": m}))
    sc.load()
    t0 = time.time()
    with open(a.out, "a") as fh:
        fh.write(json.dumps({"start": t0, "pid": pid, "cells": len(cells), "watch": len(watch)}) + "\n")
        while time.time() - t0 < a.secs:
            time.sleep(a.every)
            sc.exports_sync.sample()
            time.sleep(0.5)
            while got:
                o = got.pop(0)
                fh.write(json.dumps(o) + "\n")
                fh.flush()
                if isinstance(o, dict) and "days" in o:
                    print("t=%4.0f days=%s day#=%s half54=%s nconn=%s cells 6c/70=%s/%s map 6c/70/74=%s/%s/%s trans=%d" % (
                        time.time() - t0, o["days"], o.get("dayno"), o.get("half54"), o.get("nconn"), o.get("cells_6c"),
                        o.get("cells_70"), o.get("map_6c"), o.get("map_70"), o.get("map_74"),
                        sum(o.get("trans", {}).values())), flush=True)
                else:
                    print(o, flush=True)
    s.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main())
