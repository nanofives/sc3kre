#!/usr/bin/env python3
r"""stcompat lab (child stcompat 2026-11-25, copied from verify/lotshape/work/lab.py): one windowed game in the stcompat tree, posted input only (sc3io), game calls by Frida
on the GAME thread from a DispatchMessageA hook on a private WM_APP message (place_direct.py pattern), 'propagate' for
calls that act. Pictures by SC3RESIZE_FRAMEDUMP (vdscroll_io.dump, BMPs deleted).

  py -3.12 lab.py launch "<city>.sc3"            sc3dev.ps1 run lotdraw with log + framedump + autosave env
  py -3.12 lab.py dump <tag>                     frame dump -> fd/<tag>.png
  py -3.12 lab.py cam <x> <z> <zoom> <rot>       city view GetCurrentView (wcv vt+0x94) -> SetZoomAndRotation (vt+0x6c),
                                                 centre tile written to view +0xb0/+0xb4 first (nramp_cam.py)
  py -3.12 lab.py arm <inst>                     building layer (city vt+0x138) vt+0x54 DoPlaceBuildingTool(
                                                 {0x207EDC0E, 0xB1D10002, inst}, one-shot 1, free 0): the stock tool
  py -3.12 lab.py tool                           the city view's current tool (+0x228): vtable, key +0x108, +0x116/+0x117
  py -3.12 lab.py occ <x0> <z0> <x1> <z1>        occupants in a cell box: key, type, rect (vt+0xd0), SizeInCellsX/Z
                                                 (vt+0xd4/+0xd8), rotation (vt+0xb4)
  py -3.12 lab.py cells <x0> <z0> <x1> <z1>      sprite cell map records (iso view +0x158): sprite, reg (+8, +9), size
                                                 (+10), flags (+0x10), GetCellSizeOfSprite (vt+0xa8)
  py -3.12 lab.py click <x> <y> [right] | move <x> <y> | key <vk>      posted input (client coords)
  py -3.12 lab.py occsave <save.sc3> [ids]       occupant records of a save
"""
import json
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WT = HERE.parents[2]
MAIN = WT.parents[2]                       # Simcity\dev\lotdraw\wt -> Simcity
sys.path.insert(0, str(WT / "re" / "tools"))
sys.path.insert(0, str(WT / "re" / "tools" / "netmod"))
FD = HERE / "fd"
FD.mkdir(exist_ok=True)
os.environ.setdefault("VDSCROLL_FD", str(FD))
LOG = HERE / "resize.log"
import sc3io  # noqa: E402
import vdscroll_io as vdio  # noqa: E402
vdio.FD = FD

WM_LAB = 0x8000 + 0x5DB

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var simcity = Process.getModuleByName('SIMCITY.DLL').base;
var geom = Process.getModuleByName('SIMGEOM.DLL').base;
var spr = Process.getModuleByName('SIMSPR.DLL').base;
var jobs = [], results = [];
function vfn(obj, off, ret, args, prop) {
  return new NativeFunction(obj.readPointer().add(off).readPointer(), ret, ['pointer'].concat(args),
                            prop ? {abi: 'thiscall', exceptions: 'propagate'} : 'thiscall');
}
function modrva(p) { var m = Process.findModuleByAddress(p); return m ? m.name + '+0x' + p.sub(m.base).toString(16) : '' + p; }
function city() {
  var app = exe.add(0x4fa86c - 0x400000).readPointer();
  var c = app.add(0x48).readPointer();
  if (!c.readPointer().equals(simcity.add(0x13260))) throw new Error('city vtable ' + c.readPointer());
  return c;
}
function wcv() {
  var v = new NativeFunction(geom.add(0x1be16), 'pointer', [])();
  if (v.isNull() || !v.readPointer().equals(spr.add(0x67894))) throw new Error('city view ' + v);
  return v;
}
function iso() { var w = wcv(); return vfn(w, 0x94, 'pointer', [])(w); }
function hex(v) { return '0x' + (v >>> 0).toString(16); }
function key3(p) { return [p.readU32(), p.add(4).readU32(), p.add(8).readU32()].map(hex); }
function run(j) {
  if (j.kind === 'cam') {
    var v = iso();
    v.add(0xb0).writeS32(j.x); v.add(0xb4).writeS32(j.z);
    vfn(v, 0x6c, 'void', ['int', 'int', 'int'], 1)(v, j.zoom, j.rot, 1);
    var cm = v.add(0x158).readPointer();
    return {job: j, zoom: cm.add(0x28).readS32(), rot: cm.add(0x2c).readS32()};
  }
  if (j.kind === 'arm') {
    var c = city(), bl = vfn(c, 0x138, 'pointer', [])(c), k = Memory.alloc(12);
    k.writeU32(0x207EDC0E); k.add(4).writeU32(j.grp); k.add(8).writeU32(j.inst);
    var r = vfn(bl, 0x54, 'uint8', ['pointer', 'uint8', 'uint8'], 1)(bl, k, 1, 0);
    return {job: j, ret: r};
  }
  if (j.kind === 'place') {
    // building layer vt+0x38 = SIMGEOM 0x10006b02: CanPlace + Place kind 0 (site check 0x100072f6, commit 0x10007760)
    var c = city(), bl = vfn(c, 0x138, 'pointer', [])(c), k = Memory.alloc(12), co = Memory.alloc(12),
        bo = Memory.alloc(24), cost = Memory.alloc(8);
    k.writeU32(j.key[0]); k.add(4).writeU32(j.key[1]); k.add(8).writeU32(j.key[2]);
    co.writeS32(j.x << 8); co.add(4).writeS32(j.z << 8); co.add(8).writeS32(0x7fffffff);
    cost.writeU32(0); cost.add(4).writeU32(0);
    var r = vfn(bl, 0x38, 'uint8', ['pointer', 'pointer', 'pointer', 'pointer', 'uint8'], 1)(bl, co, k, bo, cost, j.free ? 1 : 0);
    return {job: j, placed: r, cost: cost.readU32()};
  }
  if (j.kind === 'alt') {
    // DirtBag (city vt+0x13c) vt+0x48(x, z, &alt) at vertices, as sc3resize QUERYID terrain.corner_alt
    var c = city(), db = vfn(c, 0x13c, 'pointer', [])(c), o = Memory.alloc(4), f = vfn(db, 0x48, 'uint8', ['uint32', 'uint32', 'pointer']),
        rows = [];
    for (var z = j.z0; z <= j.z1; z++) { var row = []; for (var x = j.x0; x <= j.x1; x++) { o.writeU32(0); f(db, x, z, o); row.push(o.readU32()); } rows.push(row); }
    return {job: j, rows_by_z: rows};
  }
  if (j.kind === 'hotkey') {
    // cISC3WinCityView vt+0x80 DefOnHotKey (SIMSPR 0x10049a80): 0x12 arms Demolish (civmod_lab.py)
    var v = wcv();
    return {job: j, ret: vfn(v, 0x80, 'uint8', ['uint32', 'uint32', 'uint32'], 1)(v, j.id, 0, 0)};
  }
  if (j.kind === 'bench') {
    // full view repaint: iso (cell map) vt+0x14c = SIMSPR FUN_1000b4b3 (invalidate 8 x 8 tiles + draw), j.n times
    var v = iso(), f = vfn(v, 0x14c, 'void', [], 1), t = [];
    for (var i = 0; i < j.n; i++) { var t0 = Date.now(); f(v); t.push(Date.now() - t0); }
    t.sort(function (x, y) { return x - y; });
    var sum = t.reduce(function (x, y) { return x + y; }, 0);
    return {job: j, n: j.n, total_ms: sum, median_ms: t[t.length >> 1], min_ms: t[0], max_ms: t[t.length - 1]};
  }
  if (j.kind === 'tool') {
    var t = wcv().add(0x228).readPointer();
    if (t.isNull()) return {job: j, tool: null};
    return {job: j, tool: '' + t, vt: modrva(t.readPointer()), key: key3(t.add(0x108)),
            sx1: t.add(0x116).readU8(), sz1: t.add(0x117).readU8()};
  }
  if (j.kind === 'occ') {
    var c = city(), om = vfn(c, 0x11c, 'pointer', [])(c), seen = {}, out = [], o = Memory.alloc(4), rc = Memory.alloc(16),
        rt = Memory.alloc(4), get = vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
    for (var x = j.x0; x <= j.x1; x++) for (var z = j.z0; z <= j.z1; z++) {
      o.writePointer(ptr(0));
      if (!get(om, x, z, o)) continue;
      var occ = o.readPointer();
      if (occ.isNull()) continue;
      if (seen[occ]) { seen[occ].cells.push([x, z]); continue; }
      vfn(occ, 0xd0, 'void', ['pointer'])(occ, rc);
      vfn(occ, 0xb4, 'uint8', ['pointer'])(occ, rt);
      var e = {occ: '' + occ, key: key3(occ.add(4).readPointer().sub(0x10)), type: vfn(occ, 0x88, 'uint32', [])(occ),
               rect: [rc.readU32(), rc.add(4).readU32(), rc.add(8).readU32(), rc.add(12).readU32()],
               sx: vfn(occ, 0xd4, 'uint8', [])(occ), sz: vfn(occ, 0xd8, 'uint8', [])(occ), sy: vfn(occ, 0xdc, 'uint8', [])(occ),
               rot: rt.readU32(), cells: [[x, z]]};
      seen[occ] = e; out.push(e);
    }
    return {job: j, occ: out};
  }
  if (j.kind === 'cells') {
    var cm = iso().add(0x158).readPointer(), rows = cm.add(0x24).readPointer(), out = [],
        csz = vfn(cm, 0xa8, 'uint32', ['int', 'int']);
    for (var x = j.x0; x <= j.x1; x++) for (var z = j.z0; z <= j.z1; z++) {
      var r = rows.add(x * 4).readPointer().add(z * 0x14);
      var s = r.readPointer();
      out.push({x: x, z: z, spr: s.isNull() ? 0 : '' + s, regx: r.add(8).readU8(), regz: r.add(9).readU8(),
                size: r.add(10).readU8(), layer: r.add(11).readU8(), T: r.add(4).readS16(), B: r.add(6).readS16(),
                flags: hex(r.add(0x10).readU16()), b12: r.add(0x12).readU8(), b13: r.add(0x13).readU8(), cellsize: csz(cm, x, z)});
    }
    return {job: j, zoom: cm.add(0x28).readS32(), rot: cm.add(0x2c).readS32(), cells: out};
  }
  if (j.kind === 'skin') {
    // scheme manager [[0x4fa86c]+0x108]: +0x58 loaded, +0x50 building set (sc3netmod sp_skin, CIVIC_REWARD.md 7.3)
    var sm = exe.add(0x4fa86c - 0x400000).readPointer().add(0x108).readPointer();
    return {job: j, loaded: sm.add(0x58).readU8(), set: hex(sm.add(0x50).readU32())};
  }
  if (j.kind === 'scheme') {
    // scheme vt+0x18 SetCityScheme(landscape +0x18, flora +0x2c, building set, progress) = SIMINIT 0x10006589. Called
    // from here the return address is not SIMUI's, so sc3netmod STYLEPICK passes the set through (its "other" case).
    var sm = exe.add(0x4fa86c - 0x400000).readPointer().add(0x108).readPointer();
    var r = vfn(sm, 0x18, 'uint8', ['uint32', 'uint32', 'uint32', 'uint32'], 1)(sm, sm.add(0x18).readU32(),
                sm.add(0x2c).readU32(), j.set >>> 0, j.prog);
    return {job: j, ret: r, set_now: hex(sm.add(0x50).readU32())};
  }
  if (j.kind === 'seabed') {
    // SIMDIRT renderer singleton DAT_10025bac: +0x18 ground grid, +0x20 water-surface grid (each +0xc = row array by x,
    // one byte per z), +0x2c the per-vertex colour cache (u16, stride 1025 under sc3bigcity, 257 stock).
    // Water function 0x10013fab: depth = water - ground (>= 0) -> PALWATER row. j.d > 0 raises the water surface to
    // ground + d on the box (j.d == 0 only reads). The test game is killed afterwards, nothing is restored. Then the cache is zeroed and the view repainted.
    var dirt = Process.getModuleByName('SIMDIRT.DLL').base, s = dirt.add(0x25bac).readPointer();
    var g = s.add(0x18).readPointer().add(0xc).readPointer(), w = s.add(0x20).readPointer().add(0xc).readPointer();
    var stride = dirt.add(0x130b0 + 2).readU32(), n = 0, before = [];
    for (var x = j.x0; x <= j.x1; x++) {
      var gr = g.add(x * 4).readPointer(), wr = w.add(x * 4).readPointer();
      for (var z = j.z0; z <= j.z1; z++) {
        if (before.length < 4) before.push([x, z, gr.add(z).readU8(), wr.add(z).readU8()]);
        if (j.d > 0) { wr.add(z).writeU8(Math.min(255, gr.add(z).readU8() + j.d)); n++; }
      }
    }
    var cache = s.add(0x2c).readPointer(), sz = 2 * stride * stride;
    if (!j.clear) return {job: j, stride: stride, written: n, sample_ground_water_before: before, cache: '' + cache};
    for (var x = j.x0 - 1; x <= j.x1 + 1; x++) for (var z = j.z0 - 1; z <= j.z1 + 1; z++) cache.add((x * stride + z) * 2).writeU16(0);
    return {job: j, stride: stride, written: n, sample_ground_water_before: before};
  }
  return {job: j, error: 'unknown kind'};
}
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('DispatchMessageA'), {
  onEnter: function (a) {
    if (a[0].add(4).readU32() !== %WM% || !jobs.length) return;
    while (jobs.length) {
      var j = jobs.shift();
      try { results.push(run(j)); } catch (e) { results.push({job: j, error: '' + e, stack: e.stack}); }
    }
  }
});
rpc.exports = { queue: function (j) { jobs.push(j); }, take: function () { var o = results; results = []; return o; } };
""".replace("%WM%", str(WM_LAB))


def pid():
    return int((MAIN / "dev" / "stcompat" / "last_pid").read_text().strip())


def hwnd():
    os.environ["SC3_PID"] = str(pid())
    return sc3io.game_hwnd(pid())


def frida_jobs(jobs, timeout=20.0):
    import ctypes
    import frida
    import sc3pause
    p = pid()
    h = hwnd()
    sc3pause.require_running(p, "lotshape lab")
    s = frida.attach(p)
    sc = s.create_script(JS)
    sc.load()
    api = sc.exports_sync
    for j in jobs:
        api.queue(j)
    out = []
    t0 = time.time()
    while len(out) < len(jobs) and time.time() - t0 < timeout:
        ctypes.windll.user32.PostMessageW(h, WM_LAB, 0, 0)
        time.sleep(0.3)
        out += api.take()
    sc.unload()
    s.detach()
    if len(out) < len(jobs):
        raise SystemExit("timeout: %d of %d jobs ran" % (len(out), len(jobs)))
    return out


def main(a):
    c = a[0]
    if c == "launch":
        if LOG.exists():
            LOG.unlink()
        env = dict(os.environ, SC3RESIZE_LOG=str(LOG), SC3RESIZE_FRAMEDUMP=str(FD) + "\\",
                   SC3AUTOSAVE_SECONDS=os.environ.get("SC3AUTOSAVE_SECONDS", "120"))
        r = subprocess.run(["pwsh", "-NoProfile", "-File", str(MAIN / "re" / "scripts" / "sc3dev.ps1"), "run", "stcompat",
                            "-City", a[1]], env=env, capture_output=True, text=True)
        print(r.stdout, r.stderr)
    elif c == "dump":
        hwnd()
        vdio.dump("_pre")
        time.sleep(0.4)
        print(vdio.dump(a[1]))
        for f in FD.glob("_pre*.png"):
            f.unlink()
        for b in FD.glob("*.bmp"):
            try:
                b.unlink()
            except OSError:
                pass
    elif c == "cam":
        print(json.dumps(frida_jobs([{"kind": "cam", "x": int(a[1]), "z": int(a[2]), "zoom": int(a[3]), "rot": int(a[4])}])))
    elif c == "arm":
        print(json.dumps(frida_jobs([{"kind": "arm", "inst": int(a[1], 0), "grp": int(a[2], 0) if len(a) > 2 else 0x57E}])))
    elif c == "place":                                # place <t,g,i hex> x,z [x,z ...]
        k = [int(v, 16) for v in a[1].split(",")]
        jobs = [{"kind": "place", "key": k, "x": int(p.split(",")[0]), "z": int(p.split(",")[1]), "free": 0} for p in a[2:]]
        for r in frida_jobs(jobs):
            print(json.dumps(r))
    elif c == "seabed":                               # seabed x0 z0 x1 z1 d   (d = 0 restores)
        print(json.dumps(frida_jobs([{"kind": "seabed", "x0": int(a[1]), "z0": int(a[2]), "x1": int(a[3]), "z1": int(a[4]),
                                      "d": int(a[5]), "clear": len(a) > 6}], timeout=60.0)))
    elif c == "scheme":                               # scheme <set hex> [prog]
        print(json.dumps(frida_jobs([{"kind": "scheme", "set": int(a[1], 16), "prog": int(a[2]) if len(a) > 2 else 0}],
                                    timeout=120.0)))
    elif c == "skin":
        print(json.dumps(frida_jobs([{"kind": "skin"}])))
    elif c == "hotkey":
        print(json.dumps(frida_jobs([{"kind": "hotkey", "id": int(a[1], 0)}])))
    elif c == "bench":
        print(json.dumps(frida_jobs([{"kind": "bench", "n": int(a[1])}], timeout=120.0)))
    elif c == "tool":
        print(json.dumps(frida_jobs([{"kind": "tool"}])))
    elif c == "alt":
        r = frida_jobs([{"kind": "alt", "x0": int(a[1]), "z0": int(a[2]), "x1": int(a[3]), "z1": int(a[4])}])[0]
        print("vertex altitudes, x %s..%s across, z down from %s" % (a[1], a[3], a[2]))
        for z, row in zip(range(int(a[2]), int(a[4]) + 1), r["rows_by_z"]):
            print(z, row)
    elif c in ("occ", "cells"):
        r = frida_jobs([{"kind": c, "x0": int(a[1]), "z0": int(a[2]), "x1": int(a[3]), "z1": int(a[4])}])
        print(json.dumps(r, indent=None if c == "occ" else 0))
    elif c == "click":
        sc3io.click(hwnd(), int(a[1]), int(a[2]), button=a[3] if len(a) > 3 else "left")
    elif c == "move":
        sc3io.move(hwnd(), int(a[1]), int(a[2]))
    elif c == "key":
        sc3io.key(hwnd(), int(a[1], 0))
    elif c == "occsave":
        import occupant_layer
        cc, s0, s1, cnt, ver, recs = occupant_layer.parse(a[1])
        ids = [int(x) for x in a[2].split(",")] if len(a) > 2 else None
        for r in recs:
            k = r["key"]
            if ids is None or k[2] in ids:
                print("%08X %08X %d at (%d,%d) rot %s size %sx%s flags %08x" % (k[0], k[1], k[2], r["a"], r["b"], r["rot"],
                      r.get("sa"), r.get("sb"), r["flags"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
