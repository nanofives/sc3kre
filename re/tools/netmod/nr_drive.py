#!/usr/bin/env python3
r"""nr_drive.py - drive one SC3 instance for the netrules checks (2026-10-13). sc3io + Frida, never a cursor.

SC3_PID picks the instance (set it: this tool only touches that pid).

  py nr_drive.py retile NETMASK X1,Y1,X2,Y2   # post GZ message 0x637c0dab {mask, x1<<16|y1, x2<<16|y2}
                                              # (FUN_10013afe -> transit layer vt+0xb0 = FUN_100151f1)
  py nr_drive.py conn X0,Y0,X1,Y1             # per surface cell: piece id/state and the exemplar's
                                              # 0x82237425 interface +0x140/+0x144/+0x148 (FUN_1000d73d's masks)
  py nr_drive.py cells X0,Y0,X1,Y1            # piece id/state per surface cell
  py nr_drive.py save                         # menu command 0x10009002 (Save), as nv_arm.py
NETMASK bits (FUN_100151f1): 1|2 highway+road, 4 rail, 8 pipe, 0x10 subway, 0x20 power.
"""
import json
import os
import sys
import time
import ctypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

WM_JOB = 0x8000 + 0x5C6

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var jobs = [], results = [];
function vfn(obj, off, ret, args, prop) {
  // prop: action calls let native exceptions take their normal path (a mod's OutputDebugStringA inside the call raises
  // 0x40010006; Frida's default 'steal' unwinds out of the game code halfway, task sprcrash/fridaprop). Reads keep 'steal'
  return new NativeFunction(obj.readPointer().add(off).readPointer(), ret, ['pointer'].concat(args),
                            prop ? {abi: 'thiscall', exceptions: 'propagate'} : 'thiscall');
}
function city() { return exe.add(0x4fa86c - 0x400000).readPointer().add(0x48).readPointer(); }
function msgsrv() {
  var fw = exe.add(0xFAB74).readPointer();
  var out = Memory.alloc(4); out.writePointer(ptr(0));
  vfn(fw, 0x10, 'int', ['uint32', 'uint32', 'pointer'], 1)(fw, 0x64063387, 0xC1085722, out);
  return out.readPointer();
}
function post4(w) {
  var srv = msgsrv();
  var msg = Memory.alloc(16);
  for (var i = 0; i < 4; i++) msg.add(4 * i).writeU32(w[i] >>> 0);
  return vfn(srv, 0x10, 'int', ['pointer', 'uint8'], 1)(srv, msg, 0);
}
function modname(p) { var m = Process.findModuleByAddress(p); return m ? m.name + '+0x' + p.sub(m.base).toString(16) : '' + p; }
function walk(j, conn) {
  var c = city(), out = [];
  var om = vfn(c, 0x11c, 'pointer', [])(c);
  var at = vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
  var op = Memory.alloc(4), qp = Memory.alloc(4);
  for (var y = j.y0; y <= j.y1; y++) for (var x = j.x0; x <= j.x1; x++) {
    op.writePointer(ptr(0));
    if (!at(om, x, y, op)) continue;
    var o = op.readPointer(); if (o.isNull()) continue;
    var r = {x: x, y: y, cls: modname(o.readPointer())};
    if (r.cls.indexOf('SIMNTWRK') === 0) {
      var w0 = o.add(0x10).readU32(), w1 = o.add(0x14).readU32();
      r.piece = w1 & 0xffff; r.state = w0 >>> 30;
      if (conn) {
        /* FUN_1000cd35: piece primary = o-4; QI *(primary+8) = *(o+4) for 0x82237425, then +0x140.. */
        var ex = o.add(4).readPointer();
        r.ex_cls = modname(ex.readPointer());
        qp.writePointer(ptr(0));
        var ok = new NativeFunction(ex.readPointer().readPointer(), 'uint8', ['pointer', 'uint32', 'pointer'], 'thiscall')(ex, 0x82237425, qp);
        if (ok) {
          var q = qp.readPointer();
          r.if_cls = modname(q.readPointer());
          r.m140 = q.add(0x140).readU32(); r.m144 = q.add(0x144).readU32(); r.m148 = q.add(0x148).readU32();
          vfn(q, 8, 'uint32', [])(q);
        } else { r.qi = 'failed'; }
      }
    }
    out.push(r);
  }
  return out;
}
function run(j) {
  if (j.kind === 'post4') return {ok: post4(j.w)};
  if (j.kind === 'cells') return {cells: walk(j, false)};
  if (j.kind === 'conn') return {cells: walk(j, true)};
  return {error: 'unknown job'};
}
function drain() {
  while (jobs.length) { var j = jobs.shift(); try { results.push(run(j)); } catch (e) { results.push({error: '' + e}); } }
}
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('DispatchMessageA'), {
  onEnter: function (args) {
    if (args[0].add(4).readU32() !== %WM% || jobs.length === 0) return;
    drain();
  }
});
/* 2026-10-13: on the stock tree with the display asleep the main loop removes WM_JOB with PeekMessageA(PM_REMOVE)
   and never passes it to DispatchMessageA (measured: 600 peeks, our message returned once, 0 dispatches), so the
   job also runs when PeekMessageA hands it back. Same thread, between frames. */
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('PeekMessageA'), {
  onEnter: function (args) { this.m = args[0]; },
  onLeave: function (r) {
    if (r.toInt32() === 0 || this.m.add(4).readU32() !== %WM% || jobs.length === 0) return;
    drain();
  }
});
rpc.exports = {
  queue: function (j) { jobs.push(j); return jobs.length; },
  results: function () { var r = results; results = []; return r; },
};
""".replace("%WM%", str(WM_JOB))


def frida_job(job, timeout=60):
    import frida
    sc3pause.require_running(sc3io.game_pid(), "nr_drive")
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    errs = []
    sc.on("message", lambda m, d: errs.append(m) if m.get("type") == "error" else None)
    sc.load()
    if errs:
        raise SystemExit("script error: %r" % errs)
    sc.exports_sync.queue(job)
    hwnd = sc3io.game_hwnd()
    t0 = time.time()
    res = []
    while time.time() - t0 < timeout and not res:
        ctypes.windll.user32.PostMessageA(hwnd, WM_JOB, 0, 0)
        time.sleep(0.2)
        res = sc.exports_sync.results()
    sc.unload()
    s.detach()
    if not res:
        raise SystemExit("no result in %d s (modal dialog open, or the game is not dispatching)" % timeout)
    return res[0]


def rect(s):
    return [int(v) for v in s.split(",")]


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "retile":
        mask = int(argv[2], 0)
        x1, y1, x2, y2 = rect(argv[3])
        print(frida_job({"kind": "post4", "w": [0x637C0DAB, mask, (x1 << 16) | y1, (x2 << 16) | y2]}))
    elif cmd in ("conn", "cells"):
        x0, y0, x1, y1 = rect(argv[2])
        # one job per row: a 30x9 window as one job never came back within 120 s on 2026-10-13, while each of its
        # rows took ~2 s (cause not looked into)
        for y in range(y0, y1 + 1):
            r = frida_job({"kind": cmd, "x0": x0, "y0": y, "x1": x1, "y1": y}, timeout=60)
            for c in r.get("cells", []):
                print(json.dumps(c), flush=True)
            if "error" in r:
                print(r)
    elif cmd == "save":
        print(frida_job({"kind": "post4", "w": [0x025F0A91, 0x10009002, 0, 0]}))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
