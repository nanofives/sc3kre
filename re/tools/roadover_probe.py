#!/usr/bin/env python3
r"""roadover_probe.py - read-only cell map for the ROADOVER tests (task roadover, 2026-10-28).

One character per cell of a box, from the surface occupant manager (city vt+0x11c, GetOccupantAtCell vt+0x7c) and the
zone layer (city vt+0x14c, vt+0x34), on the game thread (DispatchMessageA hook, the relocate_probe.py pattern):
  .  no occupant          t  flora (GeomFlag 0x400)        =  network piece (0x800, not a building)
  1..9 a b  building (0x100) on zone 1..11 (a = 10, b = 11): what PLOPOVER / ROADOVER demolish
  B  any other building (zone 0, 22, 14, ...: civic, reward, landmark, plopped)
  ?  anything else
Then the funds (budget city vt+0x15c, int64 at +0x38). Reads only, except `funds`.

  py -3.12 re/tools/roadover_probe.py map X0 Z0 X1 Z1        # SC3_PID = the game
  py -3.12 re/tools/roadover_probe.py at X Z                  # flags / type / rect / zone of one cell's occupant
  py -3.12 re/tools/roadover_probe.py pred X Z                # road / highway / rail / power drag predicates on it
  py -3.12 re/tools/roadover_probe.py funds N                 # test setup: set the funds (writes +0x38 / +0x40)
"""
import argparse
import ctypes
import json
import os
import sys
import time

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402

WM_PROBE = 0x8000 + 0x5C9

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var simcity = Process.getModuleByName('SIMCITY.DLL').base;
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
function info(o, zl, zb) {
  var r = {flags: vfn(o, 0x48, 'uint32', [])(o) >>> 0, type_id: vfn(o, 0x88, 'uint32', [])(o),
           removable: vfn(o, 0x74, 'uint8', [])(o)};
  var rect = Memory.alloc(16); vfn(o, 0xd0, 'void', ['pointer'])(o, rect);
  r.rect = [0, 1, 2, 3].map(function (i) { return rect.add(4 * i).readS32(); });
  zb.writeU8(255); vfn(zl, 0x34, 'uint8', ['uint32', 'uint32', 'pointer'])(zl, r.rect[0], r.rect[1], zb);
  r.zone = zb.readU8();
  return r;
}
function ch(r) {
  if ((r.flags & 0x100) === 0x100) {
    if (r.zone >= 1 && r.zone <= 9) return '' + r.zone;
    if (r.zone === 10) return 'a';
    if (r.zone === 11) return 'b';
    return 'B';
  }
  if ((r.flags & 0x400) === 0x400) return 't';
  if ((r.flags & 0x800) === 0x800) return '=';
  return '?';
}
function job(j) {
  var c = city(), om = vfn(c, 0x11c, 'pointer', [])(c), zl = vfn(c, 0x14c, 'pointer', [])(c);
  var op = Memory.alloc(4), zb = Memory.alloc(4), at = vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
  var bu = vfn(c, 0x15c, 'pointer', [])(c), funds = bu.add(0x38).readS64().toString();
  if (j.kind === 'funds') {   /* test setup: the two fields SetTotalFunds writes (set_funds.py), on the city's budget */
    bu.add(0x38).writeS64(int64(j.x0)); bu.add(0x40).writeS64(int64(j.x0));
    return {funds: bu.add(0x38).readS64().toString()};
  }
  if (j.kind === 'pred') {   /* the 4 drag predicates' Test (vt+0xc) on the occupant of one cell, as 0x10010731 calls it */
    var nt = Process.getModuleByName('SIMNTWRK.DLL').base, out = {};
    op.writePointer(ptr(0));
    if (!at(om, j.x0, j.z0, op) || op.readPointer().isNull()) return {none: [j.x0, j.z0]};
    var oc = op.readPointer(), names = {road: 0x32418, highway: 0x32424, rail: 0x3241c, power: 0x32420};
    for (var n in names) {
      var p = nt.add(names[n]).readPointer(), f = p.readPointer().add(0xc).readPointer();
      var t = new NativeFunction(f, 'uint8', ['pointer', 'pointer'], 'thiscall', {exceptions: 'propagate'});
      var m = Process.findModuleByAddress(f);
      out[n] = {accepts: t(p, oc), test: (m ? m.name + '+0x' + f.sub(m.base).toString(16) : f.toString())};
    }
    var r2 = info(oc, zl, zb); vfn(oc, 8, 'uint32', [])(oc);
    out.occupant = {flags: '0x' + r2.flags.toString(16), type_id: r2.type_id, rect: r2.rect, zone: r2.zone};
    return out;
  }
  if (j.kind === 'at') {
    op.writePointer(ptr(0));
    if (!at(om, j.x0, j.z0, op) || op.readPointer().isNull()) return {none: [j.x0, j.z0], funds: funds};
    var o = op.readPointer(), r = info(o, zl, zb); vfn(o, 8, 'uint32', [])(o);
    r.flags = '0x' + r.flags.toString(16); r.funds = funds; return r;
  }
  var rows = [], seen = {};
  for (var z = j.z0; z <= j.z1; z++) {
    var s = '';
    for (var x = j.x0; x <= j.x1; x++) {
      op.writePointer(ptr(0));
      if (!at(om, x, z, op) || op.readPointer().isNull()) { s += '.'; continue; }
      var o2 = op.readPointer(), k = o2.toString();
      if (seen[k] === undefined) {
        try {
          var fl = vfn(o2, 0x48, 'uint32', [])(o2) >>> 0;   /* rect + zone only for buildings: flora is most cells */
          seen[k] = (fl & 0x100) === 0x100 ? ch(info(o2, zl, zb)) : ch({flags: fl});
        } catch (e) { seen[k] = '!'; }
      }
      s += seen[k];
      vfn(o2, 8, 'uint32', [])(o2);
    }
    rows.push(s);
  }
  return {rows: rows, funds: funds};
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
    sc3pause.require_running(pid, "roadover_probe")
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


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("map")
    for k in ("x0", "z0", "x1", "z1"):
        m.add_argument(k, type=int)
    a1 = sub.add_parser("at"); a1.add_argument("x", type=int); a1.add_argument("z", type=int)
    a2 = sub.add_parser("pred"); a2.add_argument("x", type=int); a2.add_argument("z", type=int)
    a3 = sub.add_parser("funds"); a3.add_argument("amount", type=int)
    a = ap.parse_args()
    if a.cmd == "funds":
        print(json.dumps(run({"kind": "funds", "x0": a.amount})))
        return 0
    if a.cmd in ("at", "pred"):
        print(json.dumps(run({"kind": a.cmd, "x0": a.x, "z0": a.z})))
        return 0
    r = run({"kind": "map", "x0": a.x0, "z0": a.z0, "x1": a.x1, "z1": a.z1})
    if "rows" not in r:
        print(r)
        return 1
    print("     x %d..%d" % (a.x0, a.x1))
    for i, row in enumerate(r["rows"]):
        print("%4d  %s" % (a.z0 + i, row))
    print("funds", r["funds"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
