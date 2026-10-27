r"""stock_run.py - lateguard proof run: an UNPATCHED SC3U.exe with the mod DLLs in Apps must come up as the stock game.

Starts <tree>\Apps\SC3U.exe under Frida with no SC3MODS_* variables, so nothing but the game's own *.dll component
scan (FUN_0040b00f -> FUN_0048a575 LoadLibraryA / FUN_0048a675 FreeLibrary) can map the mods. Frida only does what
the owner's windowed rule needs and the stock game cannot do by itself: the three GZGraphicD bytes sc3bigcity's
patch_windowed + patch_surfacefmt write (windowed flag +0x6cdac, fullscreen re-force nop +0x117d6, FIX16 cave at
+0x19349), applied when LoadLibraryExW returns GZGraphicD. No mod DLL is involved in that.

Records: every LoadLibraryExW of an sc3*.dll (path, HMODULE) and every FreeLibrary of one, the sc3* modules still
mapped at the end, the window, an sc3io grab (posted input / no cursor / no focus), alive-at-N-seconds.

    py -3.12 verify/lateguard/stock_run.py --tree <tree> --out <dir> [--seconds 60] [--city <file.sc3>] [--env K=V ...]
"""
import argparse
import os
import subprocess
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "re", "tools"))

JS = r"""
const kb = Process.getModuleByName('KERNELBASE.dll');
let gzDone = false;
const keep = [];   /* Memory.alloc is freed when its JS handle is collected: the cave must stay referenced */
function patchGz(base) {
  const p = base.add(0x6cdac);
  Memory.protect(p, 1, 'rw-');
  const before = p.readU8(); p.writeU8(1);
  send('WINDOWED: GZGraphicD+0x6cdac ' + before + ' -> 1');
  const q = base.add(0x117d6);
  const qb = new Uint8Array(q.readByteArray(4));
  if (qb[0] == 0xC6 && qb[1] == 0x43 && qb[2] == 0x48 && qb[3] == 0x01) {
    Memory.protect(q, 4, 'rwx'); q.writeByteArray([0x90, 0x90, 0x90, 0x90]);
    send('WINDOWED: GZGraphicD+0x117d6 -> nop x4');
  } else send('WINDOWED: +0x117d6 pattern mismatch');
  const site = base.add(0x19349);
  const orig = [0xF6,0xDB,0x1B,0xDB,0x81,0xE3,0xC0,0x0F,0x00,0x00];
  const sb = new Uint8Array(site.readByteArray(10));
  for (let i = 0; i < 10; i++) if (sb[i] != orig[i]) { send('FIX16: pattern mismatch'); return; }
  const c = [];
  const d32 = v => [v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff];
  const movd = (off, imm) => c.push(0xC7, 0x86, ...d32(off), ...d32(imm));
  c.push(0x50, 0x83, 0xBE, 0x10, 0, 0, 0, 0x07, 0x75, 0x00);
  const fix = c.length - 1, start = c.length;
  movd(0x10, 0x1007); movd(0x54, 0x20);
  c.push(0x83, 0x8E, 0x58, 0, 0, 0, 0x40);
  movd(0x60, 0x10); movd(0x64, 0xF800); movd(0x68, 0x07E0); movd(0x6C, 0x001F);
  c[fix] = c.length - start;
  c.push(0x58, ...orig, 0xE9);
  const cave = Memory.alloc(Process.pageSize);
  keep.push(cave);
  Memory.protect(cave, Process.pageSize, 'rwx');
  const jmpBack = base.add(0x19353).sub(cave.add(c.length + 4)).toInt32();
  c.push(...d32(jmpBack >>> 0));
  cave.writeByteArray(c);
  Memory.protect(site, 10, 'rwx');
  const rel = cave.sub(site.add(5)).toInt32();
  site.writeByteArray([0xE9, ...d32(rel >>> 0), 0x90, 0x90, 0x90, 0x90, 0x90]);
  send('FIX16: 16bpp branch at +0x19349 -> cave ' + cave);
}
Interceptor.attach(kb.getExportByName('LoadLibraryExW'), {
  onEnter(args) { this.n = args[0].isNull() ? '' : args[0].readUtf16String(); },
  onLeave(ret) {
    const n = this.n || '';
    const b = n.split('\\').pop().toLowerCase();
    if (b.startsWith('sc3')) send('LOAD ' + n + ' -> ' + ret);
    if (!gzDone && b == 'gzgraphicd.dll' && !ret.isNull()) { gzDone = true; send('GZGraphicD mapped at ' + ret); patchGz(ret); }
  }
});
Interceptor.attach(kb.getExportByName('FreeLibrary'), {
  onEnter(args) {
    const m = Process.findModuleByAddress(args[0]);
    if (m && m.name.toLowerCase().startsWith('sc3')) send('FREE ' + m.name + ' ' + args[0]);
  }
});
rpc.exports.sc3mods = () => Process.enumerateModules().filter(m => m.name.toLowerCase().startsWith('sc3'))
                                     .map(m => m.name + ' @ ' + m.base + ' ' + m.path);
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--grab-at", type=float, default=30, help="seconds after resume to grab the window")
    ap.add_argument("--city")
    ap.add_argument("--arg", action="append", default=[], help="game argument, e.g. -intro:off")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--plain", action="store_true", help="start normally, no Frida (patched exe runs)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    log = open(os.path.join(a.out, "run.txt"), "w", encoding="utf-8")
    t0 = time.time()

    def emit(s):
        line = f"[{time.time() - t0:6.1f}s] {s}"
        print(line, flush=True)
        log.write(line + "\n"); log.flush()

    for k in [k for k in os.environ if k.upper().startswith("SC3MODS_")]:
        del os.environ[k]
    os.environ["SC3RESIZE_WINMEM"] = "0"
    for kv in a.env:
        k, v = kv.split("=", 1); os.environ[k] = v
    exe = os.path.join(a.tree, "Apps", "SC3U.exe")
    argv = [exe] + a.arg + ([a.city] if a.city else [])
    gone = []
    if a.plain:   # patched exe: a normal start, sc3resize does the windowed part itself
        proc = subprocess.Popen(argv, cwd=os.path.dirname(exe))
        pid = proc.pid
        sess = sc = None
        emit(f"[1/6] start pid {pid} (plain, no Frida) argv {argv} env {a.env}")
    else:
        dev = frida.get_local_device()
        pid = dev.spawn(argv, cwd=os.path.dirname(exe))
        emit(f"[1/6] spawn pid {pid} argv {argv} env {a.env}")
        sess = dev.attach(pid)
        sess.on("detached", lambda reason, crash: (emit(f"DETACHED {reason} crash={crash}"), gone.append(reason)))
        sc = sess.create_script(JS)
        sc.on("message", lambda m, d: emit("  js: " + (m.get("payload") if m["type"] == "send" else str(m))))
        sc.load()
        dev.resume(pid)
    os.environ["SC3_PID"] = str(pid)
    t1 = time.time()
    emit("[2/6] resumed")
    import sc3io  # noqa: E402
    grabbed = False
    mods_mid = None
    while time.time() - t1 < a.seconds and not gone:
        if a.plain and proc.poll() is not None:
            emit(f"EXITED code 0x{proc.returncode & 0xffffffff:08X}"); gone.append("exit"); break
        el = time.time() - t1
        if not grabbed and el >= a.grab_at:
            grabbed = True
            try:
                hwnd = sc3io.game_hwnd(pid)
                emit(f"[3/6] window hwnd 0x{hwnd:x} title '{sc3io._title(hwnd)}' rect {sc3io._window_rect(hwnd)}")
                g = sc3io.grab_to(os.path.join(a.out, "grab.png"), hwnd)
                emit(f"[4/6] grab saved {g.img.size if hasattr(g, 'img') else ''} OK")
            except Exception as e:  # report, do not retry with another method
                emit(f"[4/6] grab FAILED: {e}")
            if sc:
                try:
                    mods_mid = sc.exports_sync.sc3mods()
                except Exception as e:
                    mods_mid = [f"rpc failed: {e}"]
        time.sleep(0.25)
    alive = not gone
    emit(f"[5/6] alive after {time.time() - t1:.0f} s: {alive}")
    if mods_mid is not None:
        emit("  sc3* modules mapped at grab time: " + (", ".join(mods_mid) if mods_mid else "none"))
    if alive:
        if sc:
            try:
                emit("  sc3* modules mapped at end: " + (", ".join(sc.exports_sync.sc3mods()) or "none"))
            except Exception as e:
                emit(f"  rpc failed: {e}")
            sess.detach()
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)   # own pid only
        emit(f"[6/6] killed own pid {pid}")
    else:
        emit(f"[6/6] process gone before {a.seconds} s")
    return 0 if alive else 1


if __name__ == "__main__":
    sys.exit(main())
