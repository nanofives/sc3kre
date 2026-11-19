#!/usr/bin/env python3
r"""civmod_lab.py - in-game checks for civic looks and new rewards (child civmod, round 2026-11-19j).

The game is started by `pwsh re/scripts/sc3dev.ps1 run civmod` with SC3RESIZE_FRAMEDUMP set to <fd>\ ; set SC3_PID
to its PID. Posted input only (sc3io), no focus, no cursor. Frida calls run on the GAME thread from a DispatchMessageA
hook on a private WM_APP message (the place_direct.py pattern), with exceptions: 'propagate' for calls that act.

  py -3.12 re/tools/civmod_lab.py hotkey 0x18 [--fd DIR]   the city view's own DefOnHotKey (SIMSPR 0x10049a80,
                                                            cISC3WinCityView vt+0x80): 0x18 = Police Station, the
                                                            GetCommand path a civic button press takes.
                                                            (civtest) 0x3b opens Rewards and Opportunities, 0x12 arms
                                                            Demolish. A modal dialog runs inside the call, so the job
                                                            returns only after the dialog closes: start it in the
                                                            background (timeout 60), dump, post the OK click
  py -3.12 re/tools/civmod_lab.py command 0xC2FF057A    (civtest) the same GetCommand the hotkey makes (view +0x230
                                                            vt+0xc, riid 0x6856f7), for a class id with no hotkey
                                                            (library, museum, zoo, ...); the command is released, not
                                                            executed: the factory builds the tool, so CIVVAR picks the key
  py -3.12 re/tools/civmod_lab.py empty X0 Z0 X1 Z1 N      (civtest) N x N squares with no occupant in a cell box
  py -3.12 re/tools/civmod_lab.py tool                      the city view's current tool (+0x228): vtable, key +0x108
  py -3.12 re/tools/civmod_lab.py find GROUP:INST|TYPE [X0 Z0 X1 Z1]   occupants with that key (hex group:instance)
                                                            or type id, whole map or a cell box
  py -3.12 re/tools/civmod_lab.py dump NAME --fd DIR        one frame -> DIR\NAME.png (SC3RESIZE_FRAMEDUMP)
  py -3.12 re/tools/civmod_lab.py click X Y [--right]       posted click at client X, Y
  py -3.12 re/tools/civmod_lab.py move X Y                  posted mouse move
  py -3.12 re/tools/civmod_lab.py key VK                    posted key
  py -3.12 re/tools/civmod_lab.py unpause                   sc3wait.run_after_load
"""
import argparse
import json
import os
import pathlib
import sys
import time

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io  # noqa: E402

WM_LAB = 0x8000 + 0x5D3

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var simcity = Process.getModuleByName('SIMCITY.DLL').base;
var ui = Process.getModuleByName('SIMUI.DLL').base;
var spr = Process.getModuleByName('SIMSPR.DLL').base;
var geom = Process.getModuleByName('SIMGEOM.DLL').base;
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
function view() {
  /* the cISC3WinCityView (vtable SIMSPR 0x10067894, current tool at +0x228): SIMGEOM FUN_1001be16 = app vt+0x74, as
     sc3resize's picker reads it (pkr_cur_tool). SIMUI 0x1008e800 returns another object (vtable SIMSPR+0x63390). */
  var v = new NativeFunction(geom.add(0x1be16), 'pointer', [])();
  if (v.isNull() || !v.readPointer().equals(spr.add(0x67894))) throw new Error('city view ' + v + ' vtable ' + (v.isNull() ? '-' : modrva(v.readPointer())));
  return v;
}
function key3(p) { return [p.readU32(), p.add(4).readU32(), p.add(8).readU32()].map(function (v) { return '0x' + (v >>> 0).toString(16); }); }
function run(job) {
  if (job.kind === 'hotkey') {
    var v = view();
    var r = vfn(v, 0x80, 'uint8', ['uint32', 'uint32', 'uint32'], 1)(v, job.id, 0, 0);
    return {job: job, ret: r};
  }
  if (job.kind === 'command') {
    var v = view(), f = v.add(0x230).readPointer(), out = Memory.alloc(4);
    out.writePointer(ptr(0));
    var r = vfn(f, 0xc, 'uint8', ['uint32', 'uint32', 'pointer'], 1)(f, job.id >>> 0, 0x6856f7, out);
    var cmd = out.readPointer();
    if (!cmd.isNull()) vfn(cmd, 0x8, 'uint32', [], 1)(cmd);
    return {job: job, ret: r, cmd: '' + cmd};
  }
  if (job.kind === 'empty') {
    var c = city(), om = vfn(c, 0x11c, 'pointer', [])(c);
    var at = vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
    var op = Memory.alloc(4), b = job.box, n = job.n, W = b[2] - b[0] + 1, H = b[3] - b[1] + 1, occ = [];
    for (var z = 0; z < H; z++) for (var x = 0; x < W; x++) { op.writePointer(ptr(0)); occ.push(at(om, b[0] + x, b[1] + z, op) ? 1 : 0); }
    var hits = [];
    for (var z = 0; z + n <= H; z++) for (var x = 0; x + n <= W; x++) {
      var ok = true;
      for (var dz = 0; dz < n && ok; dz++) for (var dx = 0; dx < n && ok; dx++) if (occ[(z + dz) * W + x + dx]) ok = false;
      if (ok) hits.push([b[0] + x, b[1] + z]);
    }
    return {job: job, squares: hits.slice(0, 200), count: hits.length};
  }
  if (job.kind === 'tool') {
    var v = view(), t = v.add(0x228).readPointer();
    if (t.isNull()) return {job: job, tool: null};
    var out = {job: job, tool: '' + t, vtable: modrva(t.readPointer())};
    try { out.key = key3(t.add(0x108)); out.free = t.add(0x114).readU8(); out.oneshot = t.add(0x115).readU8(); } catch (e) {}
    return out;
  }
  if (job.kind === 'find') {
    var c = city(), om = vfn(c, 0x11c, 'pointer', [])(c);
    var nx = vfn(om, 0x14, 'uint32', [])(om), nz = vfn(om, 0x18, 'uint32', [])(om);
    var at = vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
    var op = Memory.alloc(4), rect = Memory.alloc(16), seen = {}, hits = [];
    var b = job.box || [0, 0, nx - 1, nz - 1];
    for (var z = b[1]; z <= b[3]; z++) for (var x = b[0]; x <= b[2]; x++) {
      op.writePointer(ptr(0));
      if (!at(om, x, z, op)) continue;
      var o = op.readPointer();
      if (o.isNull() || seen[o]) continue;
      seen[o] = 1;
      var t = vfn(o, 0x88, 'uint32', [])(o) >>> 0, k = null;
      try { var a = vfn(o, 0x80, 'pointer', [])(o); if (!a.isNull()) { var kp = vfn(a, 0x14, 'pointer', [])(a); if (!kp.isNull()) k = [kp.add(4).readU32() >>> 0, kp.add(8).readU32() >>> 0]; } } catch (e) {}
      var hit = job.type ? t === job.type : (k && k[0] === job.group && k[1] === job.inst);
      if (!hit) continue;
      vfn(o, 0xd0, 'void', ['pointer'])(o, rect);
      hits.push({type: t, key: k ? ['0x' + k[0].toString(16), '0x' + k[1].toString(16)] : null,
                 rect: [0, 1, 2, 3].map(function (i) { return rect.add(4 * i).readS32(); }), flags: '0x' + (vfn(o, 0x48, 'uint32', [])(o) >>> 0).toString(16)});
    }
    return {job: job, hits: hits, cells: nx + 'x' + nz};
  }
  throw new Error('unknown job ' + job.kind);
}
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('DispatchMessageA'), {
  onEnter: function (args) {
    var msg = args[0];
    if (msg.add(4).readU32() !== %WM% || jobs.length === 0) return;
    while (jobs.length) { var j = jobs.shift(); try { results.push(run(j)); } catch (e) { results.push({job: j, error: '' + e}); } }
  }
});
rpc.exports = {
  push: function (j) { jobs.push(j); return jobs.length; },
  take: function () { var r = results; results = []; return r; }
};
""".replace("%WM%", str(WM_LAB))


def frida_job(job, timeout=20.0):
    import ctypes
    import frida
    import sc3pause
    pid = sc3io.game_pid()
    paused, det = sc3pause.pause_state(pid)
    if paused:
        raise SystemExit("game is paused (%s): not attaching" % det)
    s = frida.attach(pid)
    try:
        sc = s.create_script(JS)
        sc.load()
        sc.exports_sync.push(job)
        h = sc3io.game_hwnd()
        t0 = time.time()
        while time.time() - t0 < timeout:
            ctypes.windll.user32.PostMessageW(h, WM_LAB, 0, 0)
            time.sleep(0.25)
            r = sc.exports_sync.take()
            if r:
                return r[0]
        return {"job": job, "error": "timeout"}
    finally:
        s.detach()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["hotkey", "command", "empty", "tool", "find", "dump", "click", "move", "key", "unpause"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--fd", default=os.environ.get("VDSCROLL_FD", "."))
    ap.add_argument("--right", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "hotkey":
        print(json.dumps(frida_job({"kind": "hotkey", "id": int(a.args[0], 0)})))
    elif a.cmd == "command":
        print(json.dumps(frida_job({"kind": "command", "id": int(a.args[0], 0)})))
    elif a.cmd == "empty":
        print(json.dumps(frida_job({"kind": "empty", "box": [int(v) for v in a.args[:4]], "n": int(a.args[4])}, timeout=120)))
    elif a.cmd == "tool":
        print(json.dumps(frida_job({"kind": "tool"})))
    elif a.cmd == "find":
        q = a.args[0]
        job = {"kind": "find", "type": 0}
        if ":" in q:
            g, i = q.split(":")
            job.update(group=int(g, 16), inst=int(i, 16))
        else:
            job["type"] = int(q, 0)
        if len(a.args) == 5:
            job["box"] = [int(v) for v in a.args[1:5]]
        print(json.dumps(frida_job(job, timeout=120)))
    elif a.cmd == "dump":
        import vdscroll_io as vdio
        vdio.FD = pathlib.Path(a.fd)
        print(vdio.dump(a.args[0]))
    elif a.cmd == "click":
        sc3io.click(sc3io.game_hwnd(), int(a.args[0]), int(a.args[1]), button="right" if a.right else "left")
    elif a.cmd == "move":
        sc3io.move(sc3io.game_hwnd(), int(a.args[0]), int(a.args[1]))
    elif a.cmd == "key":
        sc3io.key(sc3io.game_hwnd(), int(a.args[0], 0))
    elif a.cmd == "unpause":
        import sc3wait
        sc3wait.run_after_load(sc3io.game_pid())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
