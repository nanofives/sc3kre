#!/usr/bin/env python3
r"""nramp_cam.py - put the camera on a tile at a given zoom and rotation, through the game's own camera calls (2026-10-13).

SIMSPR camera vt+0x38 FUN_10006752(zoom, flag, tile x, tile z) and vt+0x48 FUN_10006a55(rotation, flag, tile x,
tile z) (re/tools/zoomcenter_run_arm.py, verify/leftclick ZOOMCENTER). The camera object is captured from the first
call the game makes (the script clicks the minimap zoom-out button once, (772,546)); the calls then run on the GAME
thread from a DispatchMessageA hook on a private message, as place_direct.py does. Then a frame DUMP (np_drive shot).

Task sprcrash (2026-10-24): the jobs go through the city view's own SetZoomAndRotation, FUN_1001d1d9 (view vt+0x6c,
the view captured from the same click), with the target tile written to the view's stored centre +0xb0/+0xb4 first.
That method brackets the two camera calls with City LockGraphics / UnlockGraphics (city vt+0x240 / +0x244) and the
view messages 0xa36cf3d1 / 0x835ee78b, as every game zoom / rotate method does (0x1001d2d6, 0x1001d3f3). The bare
calls skipped both. A camera change rebuilds the sprite caches and repaints at once (SetZoom flag 1 -> vt+0x14c ->
UpdateAllDirtyRects). The calls are made with exceptions 'propagate': Frida's default 'steal' took the 0x40010006
that OutputDebugStringA raises for every mod log line (sc3resize logf writes one during a zoom change) and unwound out of
SetZoom halfway, so a zoom change came back "Error: system error" and left the camera rebuild unfinished. Game PID
14180 died in the next paint on a freed occupant, other runs deadlocked (verify/sprcrash/RESULTS.md).
SC3_CAM_RAW=1 restores the old bare calls with 'steal' (repro arm only); SC3_CAM_RAW=2 = bare calls with 'propagate'.

  py -3.12 nramp_cam.py OUTDIR PREFIX X,Z [zooms=0,1,2,3,4] [rots=0] [flag=1]
Writes OUTDIR\PREFIX_z<zoom>_r<rot>.png and prints the camera state after each call.
"""
import json
import os
import subprocess
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

WM_CAM = 0x8000 + 0x5C7

JS = r"""
var ss = Process.getModuleByName('SIMSPR.DLL').base;
var RAW = %RAW%, RAWPROP = %RAWPROP%;
// 'propagate': a mod's log line inside the call (OutputDebugStringA raises 0x40010006, KERNELBASE handles it) must not be
// taken by Frida. The default 'steal' unwound out of SetZoom halfway on every zoom change (task sprcrash)
var OPT = RAW && !RAWPROP ? 'thiscall' : {abi: 'thiscall', exceptions: 'propagate'};
var cam = null, view = null, jobs = [], out = [];
var zoomf = new NativeFunction(ss.add(0x6752), 'void', ['pointer', 'int', 'uint8', 'int', 'int'], OPT);
var rotf = new NativeFunction(ss.add(0x6a55), 'void', ['pointer', 'int', 'uint8', 'int', 'int'], OPT);
// city view SetZoomAndRotation(zoom, rot, flag): lock + messages + the camera calls, the game's own path (sprcrash)
var setzr = new NativeFunction(ss.add(0x1d1d9), 'void', ['pointer', 'int', 'int', 'int'], OPT);
Interceptor.attach(ss.add(0x6752), { onEnter: function () { if (!cam) cam = this.context.ecx; } });
Interceptor.attach(ss.add(0x6a55), { onEnter: function () { if (!cam) cam = this.context.ecx; } });
// view zoom in / out / rotate left / right / set (ecx = the city view; sc3resize ZOOMCENTER wraps the vtable slots and
// jumps here)
[0x1d2d6, 0x1d365, 0x1d3f3, 0x1d47b, 0x1d1d9].forEach(function (o) {
  Interceptor.attach(ss.add(o), { onEnter: function () { if (!view) view = this.context.ecx; } });
});
function state() { return {zoom: cam.add(0x28).readS32(), rot: cam.add(0x2c).readS32(),
                           origin: [cam.add(0x54).readS32(), cam.add(0x58).readS32()]}; }
function ready() { return cam && (RAW || (view && view.add(0x158).readPointer().equals(cam))); }
function setcam(zoom, rot, f, x, z) {
  view.add(0xb0).writeS32(x); view.add(0xb4).writeS32(z);   // the stored centre tile the method passes to the camera
  setzr(view, zoom, rot, f);
}
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('DispatchMessageA'), {
  onEnter: function (a) {
    if (a[0].add(4).readU32() !== %WM% || !jobs.length) return;
    while (jobs.length) {
      var j = jobs.shift();
      try {
        if (RAW) { if (j.k === 'zoom') zoomf(cam, j.v, j.f, j.x, j.z); else rotf(cam, j.v, j.f, j.x, j.z); }
        else if (j.k === 'zoom') setcam(j.v, state().rot, j.f, j.x, j.z);
        else setcam(state().zoom, j.v, j.f, j.x, j.z);
        out.push({ok: 1, job: j, state: state()});
      } catch (e) { out.push({error: '' + e, job: j}); }
    }
  }
});
rpc.exports = {
  hascam: function () { return ready() ? state() : null; },
  queue: function (j) { jobs.push(j); },
  take: function () { var o = out; out = []; return o; }
};
""".replace("%WM%", str(WM_CAM)).replace("%RAW%", "true" if os.environ.get("SC3_CAM_RAW") in ("1", "2") else "false")     .replace("%RAWPROP%", "true" if os.environ.get("SC3_CAM_RAW") == "2" else "false")


def shot(path):
    # SC3_CAM_GRAB=1: a window grab (sc3io) instead of sc3resize's in-process dump, for when the dump trigger has
    # stopped answering (seen twice after camera calls, roundabout and roundabout2 2026-10-13)
    how = "grab" if os.environ.get("SC3_CAM_GRAB") == "1" else "shot"
    if how == "grab":
        time.sleep(1.5)
    subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py"), how, path], check=True, stdout=subprocess.DEVNULL)


def main(argv):
    out, pre = argv[1], argv[2]
    tx, tz = map(int, argv[3].split(","))
    kw = dict(a.split("=", 1) for a in argv[4:])
    zooms = [int(v) for v in kw.get("zooms", "0,1,2,3,4").split(",")]
    rots = [int(v) for v in kw.get("rots", "0").split(",")]
    flag = int(kw.get("flag", "1"))
    os.makedirs(out, exist_ok=True)
    pid = sc3io.game_pid()
    h = sc3io.game_hwnd(pid)
    sc3pause.require_running(pid, "nramp_cam")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    api = sc.exports_sync
    for btn in ((772, 546), (666, 546)):          # one game zoom call hands us the camera object (out, else in)
        sc3io.click(h, *btn)
        time.sleep(1.0)
        if api.hascam():
            break
    if not api.hascam():
        raise SystemExit("camera not captured")
    import ctypes
    for r in rots:
        for z in zooms:
            api.queue({"k": "rot", "v": r, "f": flag, "x": tx, "z": tz})
            api.queue({"k": "zoom", "v": z, "f": flag, "x": tx, "z": tz})
            ctypes.windll.user32.PostMessageA(h, WM_CAM, 0, 0)
            time.sleep(1.5)
            res = api.take()
            print(json.dumps({"z": z, "r": r, "res": res}), flush=True)
            sc3io.move(h, 760, 120)
            time.sleep(0.5)
            shot(os.path.join(out, "%s_z%d_r%d.png" % (pre, z, r)))
    s.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
