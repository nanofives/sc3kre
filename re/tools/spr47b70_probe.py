"""Read-only probe for the SIMSPR+0x47B70 null read (child spr47b70, 2026-10-25).

SIMSPR FUN_10044471 (sc3spr_view_register_cursors) loads 'UI\\Shared\\cursors\\anchor point cursor.BMP' into
this+0x1fc through (image manager)->vt+0xc at SIMSPR+0x47B5F and never checks the result; +0x47B70 then reads the
vtable of the null object. This probe logs, for every city-view init: the loader's target (module+rva), its
arguments, the return value and the out pointer. It hooks nothing that changes game state.

    py re/tools/spr47b70_probe.py --pid PID [--out log.txt]
    py re/tools/spr47b70_probe.py --spawn <SC3U.exe> [--city <file.sc3>] [--out log.txt]

--spawn starts the game suspended under Frida (env inherited: set SC3MODS_DIR / SC3MODS_MULTI / SC3RESIZE_WINMEM
first), so the hooks are in before the first city load. Prints 'PID <n>' first.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import frida

JS = r"""
function modOf(p) {
  const m = Process.findModuleByAddress(p);
  return m ? m.name + '+0x' + p.sub(m.base).toString(16) : p.toString();
}
function cstr(p) { try { return p.readCString(); } catch (e) { return '?'; } }
let installed = false;
function install(base) {
  if (installed) return; installed = true;
  send('SIMSPR base ' + base);
  // 0x47b58 = 'lea ecx,[ebp-0x3c]' just before the loader call: eax = manager, edi = &this->+0x1fc,
  // ebp-0x3c = path string object, ebp-0x28 = pixel format argument
  Interceptor.attach(base.add(0x47b58), function () {
    const c = this.context;
    const obj = c.eax, vt = obj.readPointer(), fn = vt.add(0xc).readPointer();
    const a0 = c.ebp.sub(0x3c), a3 = c.ebp.sub(0x28);
    const w = [];
    for (let i = 0; i < 4; i++) w.push(a0.add(4 * i).readPointer().toString());
    let path = '?';
    for (let i = 1; i < 4; i++) { const s = a0.add(4 * i).readPointer(); const t = cstr(s); if (t && t.toLowerCase().indexOf('cursor') >= 0) { path = t; break; } }
    send('LOAD this=' + c.ebx + ' mgr=' + obj + ' vt=' + modOf(vt) + ' fn=' + modOf(fn) +
         ' out=' + c.edi + ' (pre ' + c.edi.readPointer() + ') fmt=[' + a3.readU32() + '] path=' + path +
         ' words=' + w.join(','));
  });
  Interceptor.attach(base.add(0x47b62), function () {
    const c = this.context;
    send('RET eax=' + c.eax + ' out=' + c.edi.readPointer() + ' tid=' + Process.getCurrentThreadId());
  });
}
const t = setInterval(function () {
  const m = Process.findModuleByName('SIMSPR.DLL');
  if (m) { clearInterval(t); install(m.base); }
}, 2);
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--spawn")
    ap.add_argument("--city")
    ap.add_argument("--out")
    ap.add_argument("--seconds", type=float, default=0, help="exit after N s (0 = until the game exits)")
    a = ap.parse_args()
    out = open(a.out, "a", encoding="utf-8") if a.out else None

    def emit(s: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {s}"
        print(line, flush=True)
        if out:
            out.write(line + "\n"); out.flush()

    dev = frida.get_local_device()
    if a.spawn:
        argv = [a.spawn] + ([a.city] if a.city else [])
        pid = dev.spawn(argv, cwd=os.path.dirname(a.spawn))
    else:
        pid = a.pid
    emit(f"PID {pid}")
    sess = dev.attach(pid)
    done = []
    sess.on("detached", lambda reason, crash: (emit(f"DETACHED {reason}"), done.append(1)))
    sc = sess.create_script(JS)
    sc.on("message", lambda m, d: emit(m.get("payload") if m["type"] == "send" else str(m)))
    sc.load()
    if a.spawn:
        dev.resume(pid)
    t0 = time.time()
    while not done and (a.seconds <= 0 or time.time() - t0 < a.seconds):
        time.sleep(0.2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
