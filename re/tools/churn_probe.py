#!/usr/bin/env python3
r"""churn_probe.py - count zone-developer work per game day (task churn, 2026-11-01). Read-only Frida hooks.

Hooks (all Interceptor.attach, nothing written):
  SIMCITY 0x1000aa4d  daily clock tick (PERFORMANCE.md Finding 10)                  -> days
  SIMRCI  0x1003372a  zone layer Simulate(interval 2) body, fastcall ecx = layer      -> ticks, tiles per tick = ecx+0x270
  SIMRCI  0x10028f12 / 0x1000fd53 / 0x10017fc0  res / com / ind per-tile evaluator    -> calls + return-status histogram
  SIMRCI  0x10029666  res "develop lot" (called at LAB_10029595)                      -> res develops
  SIMRCI  0x10029a38  thiscall(bldg, coords*, flags): res and com evaluators call it   -> by flags & 3
  SC3U-side reads: city date is not read; days come from the clock tick count.

  py -3.12 re/tools/churn_probe.py SECONDS [--json OUT]     (SC3_PID = the game, running and unpaused)
"""
import json
import os
import sys
import time

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402

JS = r"""
var rci = Process.getModuleByName('SIMRCI.DLL').base;
var sim = Process.getModuleByName('SIMCITY.DLL').base;
function A(m, va) { return m.add(va - 0x10000000); }
var S = {days: 0, ticks: 0, per_tick: {}, ev: {res: {}, com: {}, ind: {}}, dev_res: 0, a38: {}};
Interceptor.attach(A(sim, 0x1000aa4d), {onEnter: function () { S.days++; }});
Interceptor.attach(A(rci, 0x1003372a), {onEnter: function () {
  S.ticks++; var n = this.context.ecx.add(0x270).readU32(); S.per_tick[n] = (S.per_tick[n] || 0) + 1; }});
[['res', 0x10028f12], ['com', 0x1000fd53], ['ind', 0x10017fc0]].forEach(function (e) {
  var h = S.ev[e[0]];
  Interceptor.attach(A(rci, e[1]), {onLeave: function (r) { var k = r.toInt32(); h[k] = (h[k] || 0) + 1; }});
});
// develop(coords*, newClass, oldClass, dist) -> char ok. old 0 = empty lot; old == new = same-class rebuild
// (the anarchy branch sets local_28 = local_18); old != new = upgrade (higher land value / density).
S.dev = {};
[['res', 0x10029666], ['com', 0x1001049e], ['ind', 0x10018bc1]].forEach(function (e) {
  Interceptor.attach(A(rci, e[1]), {
    onEnter: function (a) {
      var nw = a[1].toUInt32(), old = a[2].toUInt32();
      this.k = e[0] + ':' + (old === 0 ? 'new' : (old === nw ? 'same' : 'upgrade'));
      if (e[0] === 'res') S.dev_res++;
    },
    onLeave: function (r) { var k = this.k + ((r.toInt32() & 0xff) ? ':ok' : ':fail');
      S.dev[k] = (S.dev[k] || 0) + 1; }});
});
Interceptor.attach(A(rci, 0x10029a38), {onEnter: function (a) {
  var f = a[2].toInt32() & 0xffff; var who = this.returnAddress.sub(rci).add(0x10000000).toString(16);
  var k = who + ':' + f.toString(16); S.a38[k] = (S.a38[k] || 0) + 1; }});
rpc.exports = {snap: function () { return S; }};
"""


def main(argv):
    secs = float(argv[0])
    out = argv[argv.index("--json") + 1] if "--json" in argv else None
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "churn_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    t0 = time.time()
    time.sleep(secs)
    snap = sc.exports_sync.snap()
    snap["seconds"] = round(time.time() - t0, 1)
    sc.unload()
    s.detach()
    print(json.dumps(snap, indent=1, sort_keys=True))
    if out:
        with open(out, "w") as f:
            json.dump(snap, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1:])
