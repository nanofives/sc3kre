r"""frida_devtrace.py - trace GZGraphicD draw-device raster lifecycle from process start (child startcrash, 2026-10-29).

For the startup crash at GZGraphicD+0x14904 (FUN_10014894, `mov eax,[ecx]` with ecx = device+0x44 = 0). Spawns
<tree>\Apps\SC3U.exe suspended with the mods of <inst> (same env as sc3wait.launch_game), hooks GZGraphicD as it maps
(before the game runs any of it), resumes, and logs for <seconds>:
  INIT   FUN_10009efb  device vt+0x0c (this, w, h, mode, bpp) -> result, device+0x44 after
  MAKE   FUN_1001420d  device vt+0x1dc: new raster into +0x44, then raster vt+0x1e0 init; on failure +0x44 = 0
  SURFX  FUN_10019273  raster vt+0x40 (DirectDraw surface create) returned failure
  FREE   FUN_10014410  device vt+0x1e8: release +0x48 and +0x44
  SCRMK / SCRRL  screen device rebuild (FUN_1001611b, vt+0x208) / release-all (FUN_1001673b, vt+0x20c), with caller
  ACTAPP --activate T1,..: WM_ACTIVATEAPP 0 then 1 sent to the game's windows (no focus change)
  NULLED / RESTORE  --nullat MS: one FUN_0043d489 draw runs with its target's +0x44 = 0 (entry to exit)
  TEARDN --teardown MS: GZ's own release-all (vt+0x20c) run on the first window draw's target, never restored
  DUMPRQ --dumpat T,..: sc3resize FRAMEDUMP requests (what the player sees)
  FORCE  --failsurf W,H,N: the Nth FUN_10019273 of WxH is made to return failure (as a transient CreateSurface error)
  NULL   FUN_10014894  entered with this+0x44 == 0 (the crash), with a backtrace; first 20 only
  WDRAW  SC3U FUN_0043d489 (window background draw): each distinct window / target device / image once
  BLIT   per-device blit counts (dispatcher entries), printed at the end
Every line: ms since resume, thread id, device pointer. Backtraces are module+offset.

    py re/tools/frida_devtrace.py --inst dev\startcrash\inst --tree dev\startcrash\tree --city <city.sc3> --seconds 20

The game is killed (our pid) at the end. Interceptor.attach only, no NativeFunction calls into the game.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3wait  # noqa: E402

JS = r"""
const T0 = Date.now();
const FAIL = FAILSPEC;   // [w, h, nth] or null: force the nth surface create of that size to report failure
let failSeen = 0;
const NULLAT = NULLATSPEC;   // ms or -1: once, the first FUN_0043d489 blit after it runs with its target's +0x44 = 0
let nullSaved = null, nullDev = null;
const TEARAT = TEARATSPEC;   // ms or -1: once, the first FUN_0043d489 draw after it first runs GZ's own release-all
let tornDown = false;        // (vt+0x20c FUN_1001673b) on its target device, and nothing puts it back
if (TEARAT >= 0) {
  Interceptor.attach(ptr('0x43d489'), {
    onEnter() {
      if (tornDown || ms() < TEARAT) return;
      const d = this.context.ecx.add(0x5c).readPointer();
      if (d.isNull()) return;
      tornDown = true;
      const fn = d.readPointer().add(0x20c).readPointer();
      const before = d.add(0x44).readPointer();
      const r = new NativeFunction(fn, 'uint8', ['pointer'], {abi: 'thiscall', exceptions: 'propagate'})(d);
      send({t: 'TEARDN', ms: ms(), tid: Process.getCurrentThreadId(), dev: d.toString(), fn: fn.toString(), ret: r,
            r44_before: before.toString(), r44_after: d.add(0x44).readPointer().toString(), init8: d.add(8).readU8()});
    }
  });
}
if (NULLAT >= 0) {
  // At FUN_0043d489 entry (a function start: mid-function probes on its `call [ebx+0x118]` corrupted the call),
  // the window's target device [win+0x5c] loses its raster for the whole draw, as after a failed rebuild.
  Interceptor.attach(ptr('0x43d489'), {
    onEnter() {
      if (nullSaved !== null || ms() < NULLAT) return;
      const d = this.context.ecx.add(0x5c).readPointer();
      if (d.isNull()) return;
      nullDev = d; nullSaved = d.add(0x44).readPointer(); this.mine = true;
      d.add(0x44).writePointer(ptr(0));
      send({t: 'NULLED', ms: ms(), tid: Process.getCurrentThreadId(), dev: d.toString(), saved: nullSaved.toString(),
            w: d.add(0x24).readS32(), h: d.add(0x28).readS32()});
    },
    onLeave() {
      if (!this.mine) return;
      nullDev.add(0x44).writePointer(nullSaved);
      send({t: 'RESTORE', ms: ms(), dev: nullDev.toString()});
    }
  });
}
function ms() { return Date.now() - T0; }
function bt(ctx) {
  try {
    return Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, 14).map(a => {
      const m = Process.findModuleByAddress(a);
      return m ? m.name + '+0x' + a.sub(m.base).toString(16) : a.toString();
    }).join(' ');
  } catch (e) { return 'bt? ' + e; }
}
let hooked = false, nulls = 0;
const blits = {};
function hook(m) {
  if (hooked) return; hooked = true;
  const b = m.base;
  send({t: 'MAP', ms: ms(), base: b.toString()});
  Interceptor.attach(b.add(0x9efb), {
    onEnter(a) { this.d = this.context.ecx; this.w = a[0].toInt32(); this.h = a[1].toInt32();
                 this.mode = a[2].toInt32(); this.bpp = a[3].toInt32();
                 this.bt = (this.w >= 640) ? bt(this.context) : undefined; },
    onLeave(r) { send({t: 'INIT', ms: ms(), tid: Process.getCurrentThreadId(), dev: this.d.toString(),
                       w: this.w, h: this.h, mode: this.mode, bpp: this.bpp, ok: r.toInt32() & 0xff,
                       r44: this.d.add(0x44).readPointer().toString(), bt: this.bt}); }
  });
  // FUN_10019273 (raster vt+0x40): the two IDirectDraw::CreateSurface calls (video memory, then system memory).
  // A failing HRESULT is the only way a device INIT leaves +0x44 = 0. Log every non-zero result.
  Interceptor.attach(b.add(0x19273), {
    onEnter(a) { this.r = this.context.ecx; this.w = a[0].toInt32(); this.h = a[1].toInt32(); this.mode = a[3].toInt32(); },
    onLeave(r) {
                 if (FAIL && this.w === FAIL[0] && this.h === FAIL[1] && ++failSeen === FAIL[2]) {
                   r.replace(ptr(0));
                   send({t: 'FORCE', ms: ms(), tid: Process.getCurrentThreadId(), raster: this.r.toString(), w: this.w,
                         h: this.h, nth: failSeen, bt: bt(this.context)});
                   return;
                 }
                 if ((r.toInt32() & 0xff) === 0)
                   send({t: 'SURFX', ms: ms(), tid: Process.getCurrentThreadId(), raster: this.r.toString(), w: this.w,
                         h: this.h, mode: this.mode}); }
  });
  // Screen device: FUN_1001611b (vt+0x208, build primary + device + back buffers), FUN_1001673b (vt+0x20c, release all).
  [[0x1611b, 'SCRMK'], [0x1673b, 'SCRRL']].forEach(([off, tag]) => Interceptor.attach(b.add(off), {
    onEnter(a) { this.d = this.context.ecx; this.bt = bt(this.context); },
    onLeave(r) { send({t: tag, ms: ms(), tid: Process.getCurrentThreadId(), dev: this.d.toString(), ok: r.toInt32() & 0xff,
                       r44: this.d.add(0x44).readPointer().toString(), bt: this.bt}); }
  }));
  Interceptor.attach(b.add(0x1420d), {
    onEnter(a) { this.d = this.context.ecx; },
    onLeave(r) { send({t: 'MAKE', ms: ms(), tid: Process.getCurrentThreadId(), dev: this.d.toString(),
                       ok: r.toInt32() & 0xff, r44: this.d.add(0x44).readPointer().toString()}); }
  });
  Interceptor.attach(b.add(0x14410), {
    onEnter(a) { const d = this.context.ecx;
                 send({t: 'FREE', ms: ms(), tid: Process.getCurrentThreadId(), dev: d.toString(),
                       r44: d.add(0x44).readPointer().toString(), bt: bt(this.context)}); }
  });
  Interceptor.attach(b.add(0x14894), {
    onEnter(a) {
      const d = this.context.ecx, k = d.toString();
      blits[k] = (blits[k] || 0) + 1;
      if (d.add(0x44).readPointer().isNull() && nulls < 20) {
        nulls++;
        send({t: 'NULL', ms: ms(), tid: Process.getCurrentThreadId(), dev: k, init8: d.add(8).readU8(),
              w: d.add(0x24).readS32(), h: d.add(0x28).readS32(), bt: bt(this.context)});
      }
    }
  });
}
// SC3U FUN_0043d489 (window background draw): blits image [win+0xac] into target device [win+0x5c] through
// the dispatcher. Log each distinct (win, target, image) once, with the target's raster and size.
const seenWin = {};
Interceptor.attach(ptr('0x43d489'), {
  onEnter(a) {
    const w = this.context.ecx, tgt = w.add(0x5c).readPointer(), img = w.add(0xac).readPointer();
    const k = w.toString() + '/' + tgt.toString() + '/' + img.toString();
    if (seenWin[k]) return; seenWin[k] = 1;
    const info = {t: 'WDRAW', ms: ms(), tid: Process.getCurrentThreadId(), win: w.toString(), tgt: tgt.toString(),
                  img: img.toString()};
    if (!tgt.isNull()) { info.tgt44 = tgt.add(0x44).readPointer().toString(); info.tw = tgt.add(0x24).readS32();
                         info.th = tgt.add(0x28).readS32(); }
    if (!img.isNull()) { info.img44 = img.add(0x44).readPointer().toString(); info.iw = img.add(0x24).readS32();
                         info.ih = img.add(0x28).readS32(); }
    info.bt = bt(this.context);
    send(info);
  }
});
const g = Process.findModuleByName('GZGraphicD.dll');
if (g) hook(g);
Process.attachModuleObserver({ onAdded(m) { if (m.name.toLowerCase() === 'gzgraphicd.dll') hook(m); } });
rpc.exports = { blits() { return blits; } };
"""


def send_activateapp(pid: int) -> int:
    """WM_ACTIVATEAPP FALSE then TRUE to every top-level window of pid; a message only, focus never moves."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    hw = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            hw.append(h)
        return True
    u.EnumWindows(enum_proc(cb), 0)
    res = wintypes.DWORD()
    for h in hw:
        for on in (0, 1):
            u.SendMessageTimeoutW(h, 0x1C, on, 0, 2, 2000, ctypes.byref(res))   # WM_ACTIVATEAPP, SMTO_ABORTIFHUNG
    return len(hw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", required=True)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--city", default=None)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--out", default=None, help="also write the lines here")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--activate", default="", help="T1,T2,...: at each time (s) send WM_ACTIVATEAPP 0 then 1 "
                    "to the game's top-level windows (SendMessageTimeout, no focus change)")
    ap.add_argument("--nullat", type=int, default=-1, help="ms: the first window background draw (SC3U FUN_0043d489) after it "
                    "runs once with its target device's +0x44 zeroed, restored at its exit (the GZGraphicD+0x14904 case)")
    ap.add_argument("--teardown", type=int, default=-1, help="ms: the first window background draw after it first runs "
                    "the target device's own release-all (vt+0x20c), never restored")
    ap.add_argument("--dumpat", default="", help="T1,T2,..: s after resume, request an sc3resize FRAMEDUMP (needs "
                    "--env SC3RESIZE_FRAMEDUMP=<prefix>); tag t<seconds>")
    ap.add_argument("--failsurf", default="", help="W,H,N: the Nth surface create of WxH returns failure (fault injection)")
    a = ap.parse_args()

    inst = os.path.abspath(a.inst)
    apps = os.path.join(os.path.abspath(a.tree), "Apps")
    exe = os.path.join(apps, "SC3U.exe")
    present = [m for m in sc3wait.MODS if os.path.exists(os.path.join(inst, m))]
    env = dict(os.environ, SC3MODS_DIR=inst, SC3MODS_LIST=";".join(present), SC3MODS_ANYLOAD="1",
               SC3MODS_MULTI="1", SC3RESIZE_WINMEM="0", SC3_SESSION=os.environ.get("SC3_SESSION", "startcrash"))
    env.pop("SC3MODS_OFF", None)
    for kv in a.env:
        k, v = kv.split("=", 1)
        env[k] = v
    argv = [exe] + ([os.path.abspath(a.city)] if a.city else [])
    out = open(a.out, "w", encoding="utf-8") if a.out else None

    def emit(s: str) -> None:
        print(s, flush=True)
        if out:
            out.write(s + "\n")
            out.flush()

    dev = frida.get_local_device()
    pid = dev.spawn(argv, env=env, cwd=apps)
    emit(f"spawned pid {pid}")
    sess = dev.attach(pid)
    fail = "null"
    if a.failsurf:
        w, h, n = (int(x) for x in a.failsurf.split(","))
        fail = "[%d, %d, %d]" % (w, h, n)
    try:
        scr = sess.create_script(JS.replace("FAILSPEC", fail).replace("NULLATSPEC", str(a.nullat))
                                 .replace("TEARATSPEC", str(a.teardown)))
    except Exception:
        os.system(f"taskkill /PID {pid} /F >nul 2>&1")   # never leave a suspended game behind
        raise

    def on_msg(m, _d):
        if m["type"] != "send":
            emit(f"ERR {m}")
            return
        p = m["payload"]
        t = p.pop("t")
        bt = p.pop("bt", None)
        emit(f"{t:5s} " + " ".join(f"{k}={v}" for k, v in p.items()) + (f"\n      bt {bt}" if bt else ""))
    scr.on("message", on_msg)
    try:
        scr.load()
    except Exception:
        os.system(f"taskkill /PID {pid} /F >nul 2>&1")
        raise
    dev.resume(pid)
    t0 = time.time()
    t_end = t0 + a.seconds
    acts = sorted(float(x) for x in a.activate.split(",") if x.strip())
    dumps = sorted(float(x) for x in a.dumpat.split(",") if x.strip())
    fdp = env.get("SC3RESIZE_FRAMEDUMP", "")
    try:
        while time.time() < t_end:
            if acts and time.time() - t0 >= acts[0]:
                acts.pop(0)
                n = send_activateapp(pid)
                emit(f"ACTAPP sent 0/1 to {n} window(s) at {int((time.time() - t0) * 1000)} ms (wall, since resume)")
            if dumps and fdp and time.time() - t0 >= dumps[0]:
                tag = "t%d" % dumps.pop(0)
                with open(fdp + "req", "w") as f:
                    f.write(tag + chr(10))
                emit(f"DUMPRQ {tag} requested at {int((time.time() - t0) * 1000)} ms")
            time.sleep(0.02)
        try:
            for k, v in sorted(scr.exports_sync.blits().items(), key=lambda kv: -kv[1]):
                emit(f"BLIT  dev={k} n={v}")
        except Exception as e:  # noqa: BLE001  (game may have died)
            emit(f"BLIT  unavailable: {e}")
    finally:
        try:
            sess.detach()
        except Exception:  # noqa: BLE001
            pass
        os.system(f"taskkill /PID {pid} /F >nul 2>&1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
