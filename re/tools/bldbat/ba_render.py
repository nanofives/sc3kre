#!/usr/bin/env python3
r"""ba_render.py - task bldbat (2026-11-18): render .bld files with the Building Architect's own batch renderer.

  py -3.12 re/tools/bldbat/ba_render.py --tree dev\bldbat\tree --out x.ixf a.bld [b.bld ...] [--log run.log]

Starts the patched BaappW.exe in <tree> windowed (bawinonly.dll, ba_patch.py; an external display-mode watcher kills
it on any mode change), waits for its menu, attaches Frida and, on Baapp's main thread (inside a PeekMessageA hook),
calls the BA application's batch export:

  app = *(0x004954e0)                    BA app singleton (getter FUN_004010c9, ctor FUN_00405189, vtable 0x480c78)
  app->vt[+0x10](out, n, &paths, 0, 0)   FUN_0040446b -> FUN_004044a9(..., param_6 = 0), the same 2,044-byte body as
                                         SIMBABLD's sc3_bat_export_rendered_buildings_ixf (0x12001faf)
  out, paths[i]                          cRZString objects (vtable 0x480344, built by FUN_00402c4c, refcount at +0x10
                                         pinned so the renderer's AddRef / Release pair (0x44f17d / 0x44f184) never
                                         frees them)
  app+0x4d = 0                           no progress window (FUN_00408c67 / FUN_00408d7a)

The output is an IXF in BAT.DAT format (override records 0x856CD19A + 0x6300 frame tables + pixel records), read by
bldfile.bat_frames / batgrow.bat_buildings. Every Frida NativeFunction uses exceptions: 'propagate'. The process is
stopped by PID at the end. Never touches the real mouse, keyboard or foreground.
"""
import argparse
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ba_gate as G   # noqa: E402

JS = r"""
'use strict';
var keep = [];
var mkstr = new NativeFunction(ptr('0x402c4c'), 'pointer', ['pointer', 'pointer'], 'thiscall', {exceptions: 'propagate'});
var getapp = new NativeFunction(ptr('0x4010c9'), 'pointer', [], 'mscdecl', {exceptions: 'propagate'});
function rzs(s) {
  var o = Memory.alloc(0x20); keep.push(o);
  var c = Memory.allocAnsiString(s); keep.push(c);
  mkstr(o, c);
  o.add(0x10).writeU32(1000);
  return o;
}
function mod(a) { var m = Process.findModuleByAddress(a); return m ? m.name + '+0x' + a.sub(m.base).toString(16) : '' + a; }
var job = null, beats = 0, mainTid = null;
Interceptor.attach(Process.getModuleByName('user32.dll').getExportByName('PeekMessageA'), {
  onEnter: function () {
    beats++;
    if (mainTid === null) mainTid = this.threadId;
    if (job === null || this.threadId !== mainTid) return;
    var j = job; job = null;
    var t0 = Date.now();
    try {
      var app = ptr('0x4954e0').readPointer();
      var created = false;
      if (app.isNull()) { app = getapp(); created = true; }
      var vt = app.readPointer();
      if (!vt.equals(ptr('0x480c78'))) throw new Error('app vtable ' + vt + ' is not 0x480c78');
      var fn = new NativeFunction(vt.add(0x10).readPointer(), 'uint8',
                                  ['pointer', 'pointer', 'int', 'pointer', 'int', 'pointer'], 'thiscall',
                                  {exceptions: 'propagate'});
      var out = rzs(j.out);
      var n = j.paths.length;
      var arr = Memory.alloc(4 * Math.max(1, n)); keep.push(arr);
      for (var i = 0; i < n; i++) arr.add(4 * i).writePointer(rzs(j.paths[i]));
      var parr = Memory.alloc(4); keep.push(parr); parr.writePointer(arr);
      app.add(0x4d).writeU8(j.progress ? 1 : 0);
      var r = fn(app, out, n, parr, 0, ptr(0));
      send({type: 'done', ok: r, created: created, ms: Date.now() - t0, tid: this.threadId});
    } catch (e) {
      send({type: 'error', error: '' + e, stack: e.stack || ''});
    }
  }
});
Process.setExceptionHandler(function (d) {
  send({type: 'exception', what: d.type + ' at ' + mod(d.address),
        bt: Thread.backtrace(d.context, Backtracer.FUZZY).slice(0, 16).map(mod)});
  return false;
});
rpc.exports = {
  render: function (out, paths, progress) { job = {out: out, paths: paths, progress: progress}; return beats; },
  beats: function () { return [beats, mainTid, ptr('0x4954e0').readPointer().toString()]; }
};
"""


class _Pid:
    """Popen-like handle for a process Frida spawned."""
    def __init__(self, pid):
        self.pid = pid

    def poll(self):
        import psutil
        try:
            pr = psutil.Process(self.pid)
            return None if pr.status() != psutil.STATUS_ZOMBIE else 0
        except psutil.NoSuchProcess:
            return -1

    def wait(self, t=None):
        end = time.time() + (t or 0)
        while self.poll() is None and time.time() < end:
            time.sleep(0.1)


TRACE_FILES_JS = r"""
var kb = Process.getModuleByName('kernelbase.dll');
Interceptor.attach(kb.getExportByName('CreateFileA'), {onEnter: function (a) { this.n = a[0].readCString(); },
  onLeave: function (r) { if (!/\Windows\|^\\|NVIDIA/i.test(this.n)) send('open ' + this.n + (r.toInt32() === -1 ? ' FAILED' : '')); }});
Interceptor.attach(kb.getExportByName('FindFirstFileA'), {onEnter: function (a) { send('list ' + a[0].readCString()); }});
Interceptor.attach(kb.getExportByName('GetFileAttributesA'), {onEnter: function (a) { this.n = a[0].readCString(); },
  onLeave: function (r) { send('attr ' + this.n + ' -> ' + r.toInt32()); }});
"""


def render(tree, out_ixf, blds, log=print, timeout=600, progress=False, shot=None, menu_wait=4.0, extra_js=None):
    """-> dict(ok, ms, mode_changes, exit). Raises RuntimeError when the run fails."""
    import frida
    out_ixf = os.path.abspath(out_ixf)
    blds = [os.path.abspath(b) for b in blds]
    for b in blds:
        if not os.path.isfile(b):
            raise RuntimeError("no such .bld: %s" % b)
    if os.path.exists(out_ixf):
        os.remove(out_ixf)
    watch = G.ModeWatch(log)
    watch.start()
    res = {"ok": False, "mode_changes": 0, "exit": None}
    sess = xsess = None
    if extra_js:
        # spawn suspended so extra_js (file / registry tracing) sees the whole start-up, then resume
        dev = frida.get_local_device()
        apps = os.path.abspath(os.path.join(tree, "Apps"))
        try:
            os.remove(os.path.join(apps, "bawinonly.log"))
        except OSError:
            pass
        pid = dev.spawn([os.path.join(apps, "BaappW.exe"), "-w", "-r800x600"], cwd=apps)
        xsess = dev.attach(pid)
        xs = xsess.create_script(extra_js)
        xs.on("message", lambda m, _d: log("trace: %s" % (m.get("payload", m),)))
        xs.load()
        dev.resume(pid)
        p = _Pid(pid)
    else:
        p = G.launch(tree)
    watch.kill_pid = p.pid
    log("BaappW.exe pid %d" % p.pid)
    try:
        t0 = time.time()
        hw = None
        while time.time() - t0 < 30 and p.poll() is None:
            ws = [w for w in G.windows_of(p.pid) if w["visible"] and w["class"] == "Gonzo"]
            if ws:
                hw = ws[0]["hwnd"]
                break
            time.sleep(0.25)
        if hw is None:
            raise RuntimeError("no Baapp window (exit %s)" % p.poll())
        time.sleep(menu_wait)
        if p.poll() is not None:
            raise RuntimeError("Baapp exited before the render (%s)" % p.poll())
        sess = frida.attach(p.pid)
        sc = sess.create_script(JS)
        done = threading.Event()
        msgs = []

        def on(m, _d):
            pl = m.get("payload", m)
            msgs.append(pl)
            log("frida: %s" % (pl,))
            if isinstance(pl, dict) and pl.get("type") in ("done", "error", "exception"):
                done.set()
            if m.get("type") == "error":
                done.set()
        sc.on("message", on)
        sc.load()
        time.sleep(0.5)
        log("main loop beats/tid/app before: %s" % (sc.exports_sync.beats(),))
        sc.exports_sync.render(out_ixf, blds, progress)
        t1 = time.time()
        while not done.is_set() and time.time() - t1 < timeout and p.poll() is None:
            done.wait(0.5)
        r = [m for m in msgs if isinstance(m, dict) and m.get("type") in ("done", "error", "exception")]
        if not r:
            raise RuntimeError("no answer from the render (exit %s, beats %s)" % (
                p.poll(), sc.exports_sync.beats() if p.poll() is None else "-"))
        if r[0]["type"] != "done":
            raise RuntimeError("render failed: %s" % (r[0],))
        res.update(ok=bool(r[0]["ok"]), ms=r[0]["ms"], created=r[0]["created"])
        if shot and p.poll() is None:
            G.print_window(hw, shot)
    finally:
        for se in (sess, xsess):
            if se is not None:
                try:
                    se.detach()
                except Exception:
                    pass
        res["exit"] = p.poll()
        if p.poll() is None:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/F"], capture_output=True)
            p.wait(10)
        time.sleep(0.5)
        watch.stop()
        res["mode_changes"] = len(watch.changes)
        log("mode changes: %d" % res["mode_changes"])
    if res["mode_changes"]:
        raise RuntimeError("display mode changed during the run")
    if not os.path.isfile(out_ixf):
        raise RuntimeError("the renderer returned %s but wrote no %s" % (res["ok"], out_ixf))
    res["bytes"] = os.path.getsize(out_ixf)
    return res


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--log")
    ap.add_argument("--shot")
    ap.add_argument("--progress", action="store_true")
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--trace-files", action="store_true", help="spawn and log every file Baapp opens or lists")
    ap.add_argument("blds", nargs="+")
    a = ap.parse_args(argv)
    paths = []
    for b in a.blds:
        if os.path.isdir(b):
            paths += [os.path.join(b, n) for n in sorted(os.listdir(b)) if n.lower().endswith(".bld")]
        else:
            paths.append(b)
    lf = open(a.log, "w", encoding="utf-8") if a.log else None
    t0 = time.time()

    def log(s):
        line = "%7.2f %s" % (time.time() - t0, s)
        print(line, flush=True)
        if lf:
            lf.write(line + "\n")
            lf.flush()
    try:
        r = render(a.tree, a.out, paths, log, a.timeout, a.progress, a.shot,
                   extra_js=TRACE_FILES_JS if a.trace_files else None)
    except RuntimeError as e:
        log("FAILED: %s" % e)
        return 1
    log("result: %s" % r)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
