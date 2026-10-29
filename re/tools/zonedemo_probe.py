#!/usr/bin/env python3
r"""zonedemo_probe.py - zone raster and zone-layer calls for the ZONEDEMO tests (task zonedemo, 2026-10-29).

Runs on the game thread (DispatchMessageA hook, the roadover_probe.py pattern). SC3_PID = the game.
Zone layer = city vt+0x14c. Its interface at object+0x10 (SIMRCI vtable 0x1004d1e0) holds CanZone vt+0x84
(0x1003559f, thiscall(zoneType, rect*, cost*), ret 0xc) and PlaceZone vt+0x88 (0x1003591f, thiscall(zoneType, rect*,
cost*, 0), ret 0x10), the two calls the zone tool makes (re/analysis/ZONEDEMO.md). rect = 6 dwords {x0<<8, z0<<8,
0x7fffffff, x1<<8, z1<<8, 0x7fffffff}, cells inclusive.

  py -3.12 re/tools/zonedemo_probe.py zmap X0 Z0 X1 Z1          zone byte per cell (hex digit, m = 22, . = 0)
  py -3.12 re/tools/zonedemo_probe.py map X0 Z0 X1 Z1           occupants (roadover_probe.py map)
  py -3.12 re/tools/zonedemo_probe.py canzone ZT X0 Z0 X1 Z1    CanZone through the slot: ok + cost (no change)
  py -3.12 re/tools/zonedemo_probe.py placezone ZT X0 Z0 X1 Z1  PlaceZone through the slot (CHANGES the city)
  py -3.12 re/tools/zonedemo_probe.py funds N                   set the funds (roadover_probe.py funds)
Calls from here have a Frida return address, so a mod gated on the zone tool's call sites sees them as stock calls.
"""
import ctypes
import json
import os
import sys
import time

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402
import roadover_probe  # noqa: E402

WM_PROBE = 0x8000 + 0x5CA

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var simcity = Process.getModuleByName('SIMCITY.DLL').base;
var rci = Process.getModuleByName('SIMRCI.DLL').base;
var jobs = [], results = [];
var fcache = {};
function vfn(obj, off, ret, args) {
  var f = obj.readPointer().add(off).readPointer(), k = f + ret + args.join();
  if (!fcache[k]) fcache[k] = new NativeFunction(f, ret, ['pointer'].concat(args), 'thiscall', {exceptions: 'propagate'});
  return fcache[k];
}
function city() {
  var app = exe.add(0x4fa86c - 0x400000).readPointer();
  var c = app.add(0x48).readPointer();
  if (!c.readPointer().equals(simcity.add(0x13260))) throw new Error('city vtable ' + c.readPointer());
  return c;
}
function job(j) {
  var c = city(), zl = vfn(c, 0x14c, 'pointer', [])(c), zb = Memory.alloc(4);
  var bu = vfn(c, 0x15c, 'pointer', [])(c), funds = bu.add(0x38).readS64().toString();
  var vt = zl.readPointer(), iface;
  if (vt.equals(rci.add(0x4d274))) iface = zl.add(0x10);
  else if (vt.equals(rci.add(0x4d1e0))) iface = zl;
  else throw new Error('zone layer vtable ' + vt);
  if (j.kind === 'zmap') {
    var rows = [];
    for (var z = j.z0; z <= j.z1; z++) {
      var s = '';
      for (var x = j.x0; x <= j.x1; x++) {
        zb.writeU8(255); vfn(zl, 0x34, 'uint8', ['uint32', 'uint32', 'pointer'])(zl, x, z, zb);
        var b = zb.readU8();
        s += b === 0 ? '.' : b === 22 ? 'm' : b < 16 ? b.toString(16) : '?';
      }
      rows.push(s);
    }
    return {rows: rows, funds: funds};
  }
  var rect = Memory.alloc(24), cost = Memory.alloc(4);
  [j.x0 << 8, j.z0 << 8, 0x7fffffff, j.x1 << 8, j.z1 << 8, 0x7fffffff].forEach(function (v, i) {
    rect.add(4 * i).writeS32(v); });
  cost.writeU32(0);
  var slot = iface.readPointer().add(j.kind === 'canzone' ? 0x84 : 0x88).readPointer(), r;
  if (j.kind === 'canzone')
    r = new NativeFunction(slot, 'uint8', ['pointer', 'uint32', 'pointer', 'pointer'], 'thiscall',
                           {exceptions: 'propagate'})(iface, j.zt, rect, cost);
  else
    r = new NativeFunction(slot, 'uint8', ['pointer', 'uint32', 'pointer', 'pointer', 'uint32'], 'thiscall',
                           {exceptions: 'propagate'})(iface, j.zt, rect, cost, 0);
  var m = Process.findModuleByAddress(slot);
  return {ok: r, cost: cost.readU32(), funds_before: funds, funds_after: bu.add(0x38).readS64().toString(),
          slot: m ? m.name + '+0x' + slot.sub(m.base).toString(16) : slot.toString()};
}
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('DispatchMessageA'), {
  onEnter: function (args) {
    if (args[0].add(4).readU32() !== %WM% || jobs.length === 0) return;
    var j = jobs.shift();
    try { results.push(job(j)); } catch (e) { results.push({error: '' + e}); }
  }
});
rpc.exports = {
  queue: function (j) { jobs.push(j); return jobs.length; },
  results: function () { var r = results; results = []; return r; }
};
""".replace("%WM%", str(WM_PROBE))


def run(job):
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "zonedemo_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    sc.exports_sync.queue(job)
    hwnd = sc3io.game_hwnd(pid)
    res = []
    for i in range(1200):   # a 256x64 map takes over 10 s on the game thread
        if i % 10 == 0:
            ctypes.windll.user32.PostMessageA(hwnd, WM_PROBE, 0, 0)
        time.sleep(0.05)
        res += sc.exports_sync.results()
        if res:
            break
    s.detach()
    return res[0] if res else {"error": "the game did not dispatch the message"}


def main(a):
    if len(a) < 2:
        print(__doc__)
        return 2
    verb = a[1]
    if verb in ("map", "funds"):
        sys.argv = ["roadover_probe.py"] + a[1:]
        return roadover_probe.main()
    if verb == "zmap":
        x0, z0, x1, z1 = map(int, a[2:6])
        r = run({"kind": "zmap", "x0": x0, "z0": z0, "x1": x1, "z1": z1})
        if "rows" not in r:
            print(r)
            return 1
        print("     x %d..%d" % (x0, x1))
        for i, row in enumerate(r["rows"]):
            print("%4d  %s" % (z0 + i, row))
        print("funds", r["funds"])
        return 0
    if verb in ("canzone", "placezone"):
        zt, x0, z0, x1, z1 = map(int, a[2:7])
        print(json.dumps(run({"kind": verb, "zt": zt, "x0": x0, "z0": z0, "x1": x1, "z1": z1})))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
