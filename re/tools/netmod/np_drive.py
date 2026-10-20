#!/usr/bin/env python3
r"""np_drive.py - drive one SC3 instance for the newpiece tests (2026-10-12). Uses sc3io, never a cursor.

Works with a renamed game exe (SC3_EXE, default SC3U.exe): the 16-bit DWM mitigation can keep a window white
(memory project-dwm16-mitigation-root-cause), and a renamed copy of SC3U.exe renders. SC3_PID picks the instance.

  py np_drive.py grab OUT.png
  py np_drive.py shot OUT.png              # in-process frame dump (sc3resize DUMP trigger), for when screen grabs are white
  py np_drive.py cmd 0x10004001            # fire a menu command: GZ message {0x025F0A91, cmd, 0, 0} (SIMUI 0x1004c209)
  py np_drive.py drag X0,Y0 X1,Y1          # client-pixel left drag (sc3io posted input)
  py np_drive.py click X,Y | rclick X,Y | key VK
  py np_drive.py cells X0,Z0,X1,Z1         # network pieces live in cells: piece id, state, attrib key (Frida, read only)
  py np_drive.py where X,Z                 # client pixel of a cell centre, from the game's own projection (if found)
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

EXE = os.environ.get("SC3_EXE", "SC3U.exe")
sc3io.GAME_EXE = EXE
WM_JOB = 0x8000 + 0x5C5

JS = r"""
var exe = Process.getModuleByName('%EXE%').base;
var jobs = [], results = [];
function vfn(obj, off, ret, args) {
  return new NativeFunction(obj.readPointer().add(off).readPointer(), ret, ['pointer'].concat(args), 'thiscall');
}
function city() {
  var app = exe.add(0x4fa86c - 0x400000).readPointer();
  return app.add(0x48).readPointer();
}
function post(id, arg) {
  var fw = exe.add(0xFAB74).readPointer();
  var out = Memory.alloc(4); out.writePointer(ptr(0));
  vfn(fw, 0x10, 'int', ['uint32', 'uint32', 'pointer'])(fw, 0x64063387, 0xC1085722, out);
  var srv = out.readPointer();
  var msg = Memory.alloc(16); msg.writeU32(id); msg.add(4).writeU32(arg); msg.add(8).writeU32(0); msg.add(12).writeU32(0);
  return vfn(srv, 0x10, 'int', ['pointer', 'uint8'])(srv, msg, 0);
}
function modname(p) { var m = Process.findModuleByAddress(p); return m ? m.name + '+0x' + p.sub(m.base).toString(16) : '' + p; }
function cells(j) {
  /* surface occupant manager (city vt+0x11c) GetOccupantAtCell vt+0x7c; a network piece occupant is piece+4:
     piece+0x14 = word0 (state bits 30-31), piece+0x18 low 16 = piece id (QUERY_ID.md section 2) */
  var c = city(), out = [];
  var om = vfn(c, 0x11c, 'pointer', [])(c);
  var at = vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
  var op = Memory.alloc(4);
  for (var z = j.z0; z <= j.z1; z++) for (var x = j.x0; x <= j.x1; x++) {
    op.writePointer(ptr(0));
    if (!at(om, x, z, op)) continue;
    var o = op.readPointer(); if (o.isNull()) continue;
    var r = {x: x, z: z, cls: modname(o.readPointer())};
    try {
      var a = vfn(o, 0x80, 'pointer', [])(o);
      if (!a.isNull()) { var k = vfn(a, 0x14, 'pointer', [])(a); if (!k.isNull()) r.attrib = [k.readU32(), k.add(4).readU32(), k.add(8).readU32()].map(function (v) { return '0x' + v.toString(16); }); }
    } catch (e) { r.err = '' + e; }
    if (r.cls.indexOf('SIMNTWRK') === 0) {
      var w0 = o.add(0x10).readU32(), w1 = o.add(0x14).readU32();
      r.piece = w1 & 0xffff; r.state = w0 >>> 30; r.w0 = '0x' + w0.toString(16); r.w1 = '0x' + w1.toString(16);
    }
    out.push(r);
  }
  return out;
}
function run(j) {
  if (j.kind === 'post') return {ok: post(j.id, j.arg)};
  if (j.kind === 'cells') return {cells: cells(j)};
  return {error: 'unknown job'};
}
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('DispatchMessageA'), {
  onEnter: function (args) {
    if (args[0].add(4).readU32() !== %WM% || jobs.length === 0) return;
    while (jobs.length) { var j = jobs.shift(); try { results.push(run(j)); } catch (e) { results.push({error: '' + e}); } }
  }
});
rpc.exports = {
  queue: function (j) { jobs.push(j); return jobs.length; },
  results: function () { var r = results; results = []; return r; },
};
""".replace("%EXE%", EXE).replace("%WM%", str(WM_JOB))


def frida_job(job, timeout=30):
    import frida
    sc3pause.require_running(sc3io.game_pid(), "np_drive")
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


def game_dir():
    """Apps folder of the game exe = its cwd = sc3resize's default dump dir."""
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, sc3io.game_pid())
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.c_uint(1024)
    k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
    k.CloseHandle(h)
    return os.path.dirname(buf.value)


def shot(out, timeout=None):
    """sc3resize writes dumpNN_frame_with_hud_WxH.bmp right after the next full present when a file DUMP appears.
    A paused game can take over 15 s to present: SC3_SHOT_TIMEOUT (s) raises the wait."""
    timeout = timeout or float(os.environ.get("SC3_SHOT_TIMEOUT", "15"))
    import glob
    from PIL import Image
    d = game_dir()
    before = set(glob.glob(os.path.join(d, "dump*_frame_with_hud_*.bmp")))
    open(os.path.join(d, "DUMP"), "w").close()
    t0 = time.time()
    while time.time() - t0 < timeout:
        new = set(glob.glob(os.path.join(d, "dump*_frame_with_hud_*.bmp"))) - before
        if new:
            f = sorted(new)[-1]
            for _ in range(50):                      # the game may still be writing the BMP
                time.sleep(0.3)
                try:
                    Image.open(f).convert("RGB").save(out)
                    break
                except (PermissionError, OSError):
                    continue
            for b in glob.glob(os.path.join(d, "dump*.bmp")):
                os.remove(b)
            return out
        time.sleep(0.2)
    raise SystemExit("no dump within %d s (sc3resize not loaded, or the game is not presenting)" % timeout)


def xy(s):
    a, b = s.split(",")
    return int(a), int(b)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "grab":
        g = sc3io.grab_to(argv[2])
        print("grabbed -> %s" % argv[2])
    elif cmd == "shot":
        print("dumped ->", shot(argv[2]))
    elif cmd == "cmd":
        print(frida_job({"kind": "post", "id": 0x025F0A91, "arg": int(argv[2], 0)}))
    elif cmd == "post":
        print(frida_job({"kind": "post", "id": int(argv[2], 0), "arg": int(argv[3], 0) if len(argv) > 3 else 0}))
    elif cmd == "drag":
        (x0, y0), (x1, y1) = xy(argv[2]), xy(argv[3])
        sc3io.drag(sc3io.game_hwnd(), x0, y0, x1, y1, button="left")
        print("dragged", (x0, y0), (x1, y1))
    elif cmd == "click":
        sc3io.click(sc3io.game_hwnd(), *xy(argv[2]))
    elif cmd == "rclick":
        sc3io.click(sc3io.game_hwnd(), *xy(argv[2]), button="right")
    elif cmd == "key":
        sc3io.key(sc3io.game_hwnd(), int(argv[2], 0))
    elif cmd == "cells":
        x0, z0, x1, z1 = (int(v) for v in argv[2].split(","))
        r = frida_job({"kind": "cells", "x0": x0, "z0": z0, "x1": x1, "z1": z1}, timeout=60)
        for c in r.get("cells", []):
            print(json.dumps(c))
        if "error" in r:
            print(r)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
