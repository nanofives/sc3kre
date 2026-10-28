#!/usr/bin/env python3
r"""relocate_probe.py - read-only occupant census for the RELOCATE work (task relocate, 2026-10-28).

For every distinct occupant on the surface manager: its class (vtable as module+RVA), GetGeomFlag (vt+0x48),
CanUserRemove (vt+0x74), TypeId (vt+0x88), own key (3 dwords at *(occ+4) - 0x10, QUERY_ID.md), cell rect (vt+0xd0)
and the zone byte under its first cell (city vt+0x14c zone layer, vt+0x34 GetValue). Grouped by class, with every
occupant of the classes asked for listed in full. Runs on the game thread from a DispatchMessageA hook, the
place_direct.py pattern. Reads only.

  py -3.12 re/tools/relocate_probe.py census OUT.json         # SC3_PID = the game
  py -3.12 re/tools/relocate_probe.py at X Z                   # the occupant at one cell, same fields
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

WM_PROBE = 0x8000 + 0x5C7

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var simcity = Process.getModuleByName('SIMCITY.DLL').base;
var jobs = [], results = [], progress = null;
var fcache = {};
function vfn(obj, off, ret, args) {
  var f = obj.readPointer().add(off).readPointer(), k = f + ret + args.join();
  if (!fcache[k]) fcache[k] = new NativeFunction(f, ret, ['pointer'].concat(args), 'thiscall');
  return fcache[k];
}
function city() {
  var app = exe.add(0x4fa86c - 0x400000).readPointer();
  var c = app.add(0x48).readPointer();
  if (!c.readPointer().equals(simcity.add(0x13260))) throw new Error('city vtable ' + c.readPointer());
  return c;
}
function modrva(p) {
  var m = Process.findModuleByAddress(p);
  return m ? m.name + '+0x' + p.sub(m.base).toString(16) : p.toString();
}
function describe(o, zl, zb) {
  var r = {};
  r.cls = modrva(o.readPointer());
  try { r.flags = '0x' + (vfn(o, 0x48, 'uint32', [])(o) >>> 0).toString(16); } catch (e) { r.flags = 'err'; }
  try { r.removable = vfn(o, 0x74, 'uint8', [])(o); } catch (e) { r.removable = 'err'; }
  try { r.type_id = vfn(o, 0x88, 'uint32', [])(o); } catch (e) { r.type_id = 'err'; }
  try { var k = o.add(4).readPointer().sub(0x10); r.key = [k.readU32(), k.add(4).readU32(), k.add(8).readU32()].map(function (v) { return '0x' + (v >>> 0).toString(16); }); } catch (e) {}
  try { var rect = Memory.alloc(16); vfn(o, 0xd0, 'void', ['pointer'])(o, rect);
        r.rect = [0, 1, 2, 3].map(function (i) { return rect.add(4 * i).readS32(); }); } catch (e) {}
  if (r.rect) { try { zb.writeU8(255); vfn(zl, 0x34, 'uint8', ['uint32', 'uint32', 'pointer'])(zl, r.rect[0], r.rect[1], zb); r.zone = zb.readU8(); } catch (e) {} }
  return r;
}
var cs = null;   /* census state, advanced a few rows per dispatch */
function census_step() {
  var c = city();
  if (!cs) {
    var om = vfn(c, 0x11c, 'pointer', [])(c), zl = vfn(c, 0x14c, 'pointer', [])(c);
    cs = {om: om, zl: zl, nx: vfn(om, 0x14, 'uint32', [])(om), nz: vfn(om, 0x18, 'uint32', [])(om), z: 0,
          seen: {}, by: {}, list: [], op: Memory.alloc(4), zb: Memory.alloc(4), t0: Date.now()};
  }
  var at = vfn(cs.om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
  for (var rows = 0; rows < 8 && cs.z < cs.nz; rows++, cs.z++) for (var x = 0; x < cs.nx; x++) {
    cs.op.writePointer(ptr(0));
    if (!at(cs.om, x, cs.z, cs.op)) continue;
    var o = cs.op.readPointer();
    if (o.isNull() || cs.seen[o]) continue;
    cs.seen[o] = 1;
    var d = describe(o, cs.zl, cs.zb), g = d.cls + ' ' + d.flags, by = cs.by;
    if (!by[g]) by[g] = {cls: d.cls, flags: d.flags, n: 0, removable: {}, zones: {}, type_ids: {}, sample: d};
    by[g].n++; by[g].removable[d.removable] = (by[g].removable[d.removable] || 0) + 1;
    by[g].zones[d.zone] = (by[g].zones[d.zone] || 0) + 1; by[g].type_ids[d.type_id] = 1;
    if (d.zone === 22 || (d.rect && (d.rect[2] > d.rect[0] || d.rect[3] > d.rect[1]))) cs.list.push(d);
  }
  if (cs.z < cs.nz) return {progress: cs.z, of: cs.nz};
  var r = {classes: cs.by, multi_or_plopped: cs.list, size: [cs.nx, cs.nz], ms: Date.now() - cs.t0};
  cs = null;
  return r;
}
function one(x, z) {
  var c = city(), om = vfn(c, 0x11c, 'pointer', [])(c), zl = vfn(c, 0x14c, 'pointer', [])(c);
  var op = Memory.alloc(4), zb = Memory.alloc(4); op.writePointer(ptr(0));
  if (!vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer'])(om, x, z, op) || op.readPointer().isNull()) return {none: [x, z]};
  return describe(op.readPointer(), zl, zb);
}
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('DispatchMessageA'), {
  onEnter: function (args) {
    if (args[0].add(4).readU32() !== %WM% || jobs.length === 0) return;
    var j = jobs[0];
    try {
      if (j.kind === 'census') { var r = census_step(); if (r.progress === undefined) { jobs.shift(); results.push(r); } else progress = r; }
      else { jobs.shift(); results.push(one(j.x, j.z)); }
    } catch (e) { jobs.shift(); cs = null; results.push({error: '' + e}); }
  }
});
rpc.exports = {
  queue: function (j) { jobs.push(j); return jobs.length; },
  results: function () { var r = results; results = []; return r; },
  progress: function () { return progress; }
};
""".replace("%WM%", str(WM_PROBE))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("census"); c.add_argument("out")
    a1 = sub.add_parser("at"); a1.add_argument("x", type=int); a1.add_argument("z", type=int)
    a = ap.parse_args()
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "relocate_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    sc.exports_sync.queue({"kind": a.cmd, "x": getattr(a, "x", 0), "z": getattr(a, "z", 0)})
    hwnd = sc3io.game_hwnd()
    res = []
    for _ in range(9000):
        ctypes.windll.user32.PostMessageA(hwnd, WM_PROBE, 0, 0)
        time.sleep(0.02)
        res += sc.exports_sync.results()
        if res:
            break
        pr = sc.exports_sync.progress()
        if pr and pr["progress"] % 64 == 0:
            print("  row %d of %d" % (pr["progress"], pr["of"]), flush=True)
    s.detach()
    if not res:
        print("no result: the game did not dispatch the message")
        return 1
    r = res[0]
    if a.cmd == "census":
        json.dump(r, open(a.out, "w"), indent=1)
        if "classes" in r:
            for g in sorted(r["classes"].values(), key=lambda g: -g["n"]):
                print("%-28s flags=%-10s n=%-6d removable=%s zones=%s type_ids=%s" % (
                    g["cls"], g["flags"], g["n"], g["removable"], g["zones"], list(g["type_ids"])[:6]))
        else:
            print(r)
    else:
        print(json.dumps(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
