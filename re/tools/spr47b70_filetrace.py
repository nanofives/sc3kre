"""spr47b70: trace every open / close of one file in a game (child spr47b70, 2026-10-25). Read-only.

Hooks KERNELBASE CreateFileW (CreateFileA lands there too), CloseHandle, CreateFileMappingW and MapViewOfFile for
handles of files whose path contains --match, and logs time, access, share mode, the caller module and how long each
handle stayed open. Spawns the game suspended so the hooks see startup.

    py re/tools/spr47b70_filetrace.py --spawn <SC3U.exe> [--city <file.sc3>] [--match "anchor point"] [--writes] [--seconds 90]
    py re/tools/spr47b70_filetrace.py --pid <PID> --writes [--seconds 90]
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import frida

JS = r"""
const MATCH = %s;
const WRITES = %s;   // also log every open that asks for write access (any file)
const t0 = Date.now();
const open = {};      // handle -> {t, name}
const maps = {};      // section handle -> file handle
function ms() { return ((Date.now() - t0) / 1000).toFixed(3) + 's'; }
function who(ctx, ra) {
  const m = Process.findModuleByAddress(ra);
  let s = m ? m.name + '+0x' + ra.sub(m.base).toString(16) : ra.toString();
  try {
    const bt = Thread.backtrace(ctx, Backtracer.FUZZY).slice(0, 8).map(function (a) {
      const mm = Process.findModuleByAddress(a); return mm ? mm.name + '+0x' + a.sub(mm.base).toString(16) : a.toString(); });
    s += ' [' + bt.join(' < ') + ']';
  } catch (e) {}
  return s;
}
const kb = Process.getModuleByName('KERNELBASE.dll');
Interceptor.attach(kb.getExportByName('CreateFileW'), {
  onEnter(a) { this.n = a[0].isNull() ? '' : a[0].readUtf16String(); this.acc = a[1].toUInt32(); this.sh = a[2].toUInt32();
               this.hit = this.n && (this.n.toLowerCase().indexOf(MATCH) >= 0 || (WRITES && (this.acc & 0x40000000))); if (this.hit) this.w = who(this.context, this.returnAddress); },
  onLeave(r) {
    if (!this.hit) return;
    const h = r.toUInt32();
    send(ms() + ' OPEN  h=0x' + h.toString(16) + (h === 0xffffffff ? ' FAILED' : '') + ' acc=0x' + this.acc.toString(16) + ' share=' + this.sh + ' tid=' + Process.getCurrentThreadId() + ' ' + this.n + ' by ' + this.w);
    if (h !== 0xffffffff) open[h] = { t: Date.now(), n: this.n };
  }
});
Interceptor.attach(kb.getExportByName('CloseHandle'), {
  onEnter(a) { const h = a[0].toUInt32();
    if (open[h]) { send(ms() + ' CLOSE h=0x' + h.toString(16) + ' after ' + (Date.now() - open[h].t) + ' ms by ' + who(this.context, this.returnAddress)); delete open[h]; }
    if (maps[h] !== undefined) { send(ms() + ' CLOSE section h=0x' + h.toString(16)); delete maps[h]; } }
});
Interceptor.attach(kb.getExportByName('CreateFileMappingW'), {
  onEnter(a) { this.f = a[0].toUInt32(); },
  onLeave(r) { if (open[this.f]) { maps[r.toUInt32()] = this.f; send(ms() + ' MAP   section h=0x' + r.toUInt32().toString(16) + ' of file h=0x' + this.f.toString(16)); } }
});
send('hooks in');
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spawn")
    ap.add_argument("--city")
    ap.add_argument("--match", default="anchor point")
    ap.add_argument("--seconds", type=float, default=90)
    ap.add_argument("--out")
    ap.add_argument("--writes", action="store_true", help="also log every open with write access")
    ap.add_argument("--pid", type=int, help="attach to a running game instead of spawning (it must not be paused)")
    a = ap.parse_args()
    out = open(a.out, "w", encoding="utf-8") if a.out else None

    def emit(s):
        print(s, flush=True)
        if out:
            out.write(s + "\n"); out.flush()

    dev = frida.get_local_device()
    pid = a.pid or dev.spawn([a.spawn] + ([a.city] if a.city else []), cwd=os.path.dirname(a.spawn))
    emit(f"PID {pid}")
    sess = dev.attach(pid)
    done = []
    sess.on("detached", lambda reason, crash: (emit(f"DETACHED {reason}"), done.append(1)))
    sc = sess.create_script(JS % (repr(a.match.lower()), 'true' if a.writes else 'false'))
    sc.on("message", lambda m, d: emit(m.get("payload") if m["type"] == "send" else str(m)))
    sc.load()
    if not a.pid:
        dev.resume(pid)
    t0 = time.time()
    while not done and time.time() - t0 < a.seconds:
        time.sleep(0.2)
    emit(f"PID {pid} end")
    return 0


if __name__ == "__main__":
    sys.exit(main())
