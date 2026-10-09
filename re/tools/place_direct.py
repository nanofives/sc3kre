#!/usr/bin/env python3
r"""place_direct.py - place buildings and zones in the running game by calling its own placement code (2026-10-08).

No mouse input: works with the window minimized. The calls run on the GAME thread, from a Frida hook on
USER32!DispatchMessageA when it dispatches a private WM_APP message we post to the game window - the same
context sc3resize's DEFERRESIZE uses (message dispatch, no drawing locks held; PERFORMANCE.md Finding 4).

Call path (agent report 2026-10-08, signatures read from disassembly):
  app   = *(SC3U.exe 0x004fa86c)            city = *(app + 0x48)   (check **city == SIMCITY + 0x13260)
  bldg  = city->vt[0x138]()                 zone = city->vt[0x14c]()
  pause = city->vt[0x21c]() / unpause = city->vt[0x220]()   (the zone tool brackets PlaceZone with these)
  PlaceBuilding = bldg->vt[0x38](coord*, key*, bounds_out[6]*, cost*, bool free)   SIMGEOM 0x10006b02, ret 0x14
  PlaceZone     = zone->vt[0x88](int type, bounds[6]*, int* cost_out, bool 0)    SIMRCI 0x1003591f, ret 0x10
  coord  = { x<<8, z<<8, 0x7fffffff }  (8.8 fixed point, footprint minimum corner)
  bounds = { x0<<8, z0<<8, 0x7fffffff, x1<<8, z1<<8, 0x7fffffff }  (inclusive corners)
  keys: coal plant {0x207EDC0E, 0x57E, 0xCF}

Occupant listing (2026-10-09), slot map from the sc3k-gzcom-dll headers (Linux-symbol derived), offsets checked
against the measured +0x3c/+0x74/+0x80/+0xb8 anchors (GZCOM_INTERFACE_CATALOGUE.md section 17):
  om   = city->vt[0x11c]()                  surface cISC3OccupantManager (city slot 71)
  om->vt[0x14]/[0x18] GetCellsInX/Z; om->vt[0x7c](x, z, &occ) GetOccupantAtCell, once per cell
  occ->vt[0x80]() -> attrib; attrib->vt[0x14]() -> cGZResourceKey* {type, group, instance}
  occ->vt[0xd0](rect*) GetBoundingRectInCellCoords, occ->vt[0x54] MajorType, occ->vt[0xb4](&u32) GetRotationFlag

Usage:
  python place_direct.py building X,Z [X,Z ...] [--key 207edc0e,57e,cf] [--free]
  python place_direct.py zone TYPE X0,Z0,X1,Z1
  python place_direct.py dump OUT.json                      every occupant: key, cell rect, major type, rotation
  python place_direct.py batch IN.json [--free]             [{"x":..,"z":..,"key":[t,g,i]}, ...]
"""
import argparse
import os
import sys
import time

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3io

WM_PLACE = 0x8000 + 0x5C4

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var simcity = Process.getModuleByName('SIMCITY.DLL').base;
var jobs = [], results = [];
function vfn(obj, off, ret, args) {
  return new NativeFunction(obj.readPointer().add(off).readPointer(), ret, ['pointer'].concat(args), 'thiscall');
}
function city() {
  var app = exe.add(0x4fa86c - 0x400000).readPointer();
  var c = app.add(0x48).readPointer();
  if (!c.readPointer().equals(simcity.add(0x13260))) throw new Error('city vtable ' + c.readPointer() + ' != SIMCITY+0x13260');
  return c;
}
function post(id, arg) {
  /* sc3simrun gz_post: framework *(SC3U+0xFAB74) vt+0x10 -> message service, then service vt+0x10(msg[4], 0) */
  var fw = exe.add(0xFAB74).readPointer();
  var out = Memory.alloc(4); out.writePointer(ptr(0));
  vfn(fw, 0x10, 'int', ['uint32', 'uint32', 'pointer'])(fw, 0x64063387, 0xC1085722, out);
  var srv = out.readPointer();
  var msg = Memory.alloc(16); msg.writeU32(id); msg.add(4).writeU32(arg); msg.add(8).writeU32(0); msg.add(12).writeU32(0);
  return vfn(srv, 0x10, 'int', ['pointer', 'uint8'])(srv, msg, 0);
}
function dump() {
  /* One GetOccupantAtCell (om vt+0x7c) per cell, distinct pointers only. The manager iterator (vt+0x70) returns
     an occupant once per cell it touches and took >10 min on a 256 city; this is 65,536 calls. */
  var c = city(), out = [], seen = {}, total = 0;
  var om = vfn(c, 0x11c, 'pointer', [])(c);
  var nx = vfn(om, 0x14, 'uint32', [])(om), nz = vfn(om, 0x18, 'uint32', [])(om);
  var at = vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
  var op = Memory.alloc(4), rect = Memory.alloc(16), rot = Memory.alloc(4);
  for (var z = 0; z < nz; z++) for (var x = 0; x < nx; x++) {
    op.writePointer(ptr(0));
    if (!at(om, x, z, op)) continue;
    var o = op.readPointer();
    if (o.isNull()) continue;
    var id = o.toString();
    if (seen[id]) continue;
    seen[id] = 1; total++;
    if (out.length >= 5000) { send({dump: out}); out = []; }
    try {
      var a = vfn(o, 0x80, 'pointer', [])(o), key = null;
      if (!a.isNull()) { var k = vfn(a, 0x14, 'pointer', [])(a); if (!k.isNull()) key = [k.readU32(), k.add(4).readU32(), k.add(8).readU32()]; }
      vfn(o, 0xd0, 'void', ['pointer'])(o, rect); rot.writeU32(0); vfn(o, 0xb4, 'uint8', ['pointer'])(o, rot);
      out.push({key: key, r: [0, 1, 2, 3].map(function (i) { return rect.add(4 * i).readU32(); }),
                major: vfn(o, 0x54, 'uint32', [])(o), rot: rot.readU32(), cell: [x, z]});
    } catch (e) { out.push({err: '' + e, cell: [x, z]}); }
  }
  send({dump: out, done: total});
  return total;
}
function run(job) {
  if (job.kind === 'post') return {job: job, ok: post(job.id, job.arg)};
  if (job.kind === 'dump') return {job: job, total: dump()};
  var c = city();
  var pause = vfn(c, 0x21c, 'void', []), unpause = vfn(c, 0x220, 'void', []);
  if (!job.held) pause(c);
  try {
    if (job.kind === 'building') {
      var bl = vfn(c, 0x138, 'pointer', [])(c);
      var coord = Memory.alloc(12); coord.writeS32(job.x << 8); coord.add(4).writeS32(job.z << 8); coord.add(8).writeS32(0x7fffffff);
      var key = Memory.alloc(12); key.writeU32(job.key[0]); key.add(4).writeU32(job.key[1]); key.add(8).writeU32(job.key[2]);
      var bounds = Memory.alloc(24), cost = Memory.alloc(4); cost.writeU32(0);
      var ok = vfn(bl, 0x38, 'uint8', ['pointer', 'pointer', 'pointer', 'pointer', 'uint8'])(bl, coord, key, bounds, cost, job.free ? 1 : 0);
      return {job: job, ok: ok, cost: cost.readU32(), bounds: [0,1,2,3,4,5].map(function (i) { return bounds.add(4 * i).readS32() >> 8; })};
    } else {
      var zl = vfn(c, 0x14c, 'pointer', [])(c);
      var b = Memory.alloc(24);
      [job.x0 << 8, job.z0 << 8, 0x7fffffff, job.x1 << 8, job.z1 << 8, 0x7fffffff].forEach(function (v, i) { b.add(4 * i).writeS32(v); });
      var cost = Memory.alloc(4); cost.writeS32(0);
      var ok = vfn(zl, 0x88, 'uint8', ['int', 'pointer', 'pointer', 'uint8'])(zl, job.type, b, cost, 0);
      return {job: job, ok: ok, cost: cost.readS32()};
    }
  } finally { if (!job.held) unpause(c); }
}
Interceptor.attach(Module.getExportByName('USER32.dll', 'DispatchMessageA'), {
  onEnter: function (args) {
    var msg = args[0];
    if (msg.add(4).readU32() !== %WM% || jobs.length === 0) return;
    /* Building batches pause the city ONCE around the whole batch (vt+0x21c/0x220), not per building:
       per-building pause/unpause made a 22k batch take >10 min once the map filled up (2026-10-09). */
    var c = null, held = jobs.length > 1 && jobs[0].kind === 'building', budget = 300;
    if (held) { c = city(); vfn(c, 0x21c, 'void', [])(c); }
    try {
      /* at most 300 jobs per dispatch: a whole 22k batch in one dispatch kept the window frozen for ~6 min
         (owner: "no puedo abrir la ventana"); the Python side keeps posting until the queue is empty */
      while (jobs.length && budget-- > 0) {
        var j = jobs.shift();
        if (held) j.held = 1;
        try { var r = run(j); if (held) delete j.held; results.push(r); }
        catch (e) { results.push({job: j, error: '' + e}); }
      }
    } finally { if (held) vfn(c, 0x220, 'void', [])(c); }
  }
});
rpc.exports = {
  queue: function (list) { list.forEach(function (j) { jobs.push(j); }); return jobs.length; },
  results: function () { var r = results; results = []; return r; },
  pending: function () { return jobs.length; }
};
""".replace("%WM%", str(WM_PLACE))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("building"); b.add_argument("at", nargs="+"); b.add_argument("--key", default="207edc0e,57e,cf")
    b.add_argument("--free", action="store_true")
    z = sub.add_parser("zone"); z.add_argument("type", type=int); z.add_argument("rect")
    pm = sub.add_parser("post", help="post a GZ message: unpause 0xc2a35d80 0, speed 0xc2684065 N")
    pm.add_argument("id"); pm.add_argument("arg", nargs="?", default="0"); pm.add_argument("--times", type=int, default=1)
    dm = sub.add_parser("dump"); dm.add_argument("out")
    bt = sub.add_parser("batch"); bt.add_argument("inp"); bt.add_argument("--free", action="store_true")
    a = ap.parse_args()
    if a.cmd == "building":
        key = [int(v, 16) for v in a.key.split(",")]
        jobs = [{"kind": "building", "x": int(p.split(",")[0]), "z": int(p.split(",")[1]), "key": key, "free": a.free}
                for p in a.at]
    elif a.cmd == "dump":
        jobs = [{"kind": "dump"}]
    elif a.cmd == "batch":
        import json
        jobs = [{"kind": "building", "x": b["x"], "z": b["z"], "key": b["key"], "free": a.free}
                for b in json.load(open(a.inp))]
    elif a.cmd == "post":
        jobs = [{"kind": "post", "id": int(a.id, 16), "arg": int(a.arg, 0)}] * a.times
    else:
        x0, z0, x1, z1 = (int(v) for v in a.rect.split(","))
        jobs = [{"kind": "zone", "type": a.type, "x0": x0, "z0": z0, "x1": x1, "z1": z1}]
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    streamed, done = [], []

    def on_msg(m, d):
        p = m.get("payload") if m.get("type") == "send" else None
        if isinstance(p, dict) and "dump" in p:
            streamed.extend(p["dump"])
            if "done" in p:
                done.append(p["done"])
    sc.on("message", on_msg)
    sc.load()
    sc.exports_sync.queue(jobs)
    import ctypes
    hwnd = sc3io.game_hwnd()
    for _ in range(100 + len(jobs) // 20):
        ctypes.windll.user32.PostMessageA(hwnd, WM_PLACE, 0, 0)
        time.sleep(0.1)
        if sc.exports_sync.pending() == 0:
            break
    res = []
    for _ in range(6000):                      # a dump or a big batch can run for minutes
        if sc.exports_sync.pending():          # keep knocking until the game thread takes the jobs
            ctypes.windll.user32.PostMessageA(hwnd, WM_PLACE, 0, 0)
        time.sleep(0.1)
        res += sc.exports_sync.results()
        if len(res) >= len(jobs) or done:
            break
    if a.cmd == "dump":
        import json
        if not done:
            print("dump did not finish:", res)
        else:
            json.dump(streamed, open(a.out, "w"))
            print("%d distinct occupants (game says %d) -> %s" % (len(streamed), done[0], a.out))
    elif a.cmd == "batch":
        ok = sum(1 for r in res if r.get("ok"))
        print("placed %d of %d; failed %d" % (ok, len(jobs), len(res) - ok))
        for r in [r for r in res if not r.get("ok")][:5]:
            print("  fail:", r)
    else:
        for r in res:
            print(r)
    if sc.exports_sync.pending():
        print("NOT RUN: %d job(s) still pending - the game did not dispatch the message" % sc.exports_sync.pending())
    s.detach()


if __name__ == "__main__":
    main()
