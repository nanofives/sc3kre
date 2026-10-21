"""av_catch.py - attach Frida to one game and log every access violation: module+offset, registers, backtrace (2026-10-21).

Read-only. For crashes the game swallows or exits on without a dump (Big One under the probe launcher).
Waits for SC3U to appear as a child of --launcher (or takes --pid), attaches, and writes JSON lines to --log.
Do not attach while the game is paused (memory: Frida attach while paused deadlocks); a loading game is fine.

    py re/tools/av_catch.py --launcher <sc3launch pid> --log <file> [--secs 120]
"""
import argparse
import json
import subprocess
import sys
import time

import frida

JS = r"""
function where(p) {
  try { var m = Process.findModuleByAddress(p); if (m) return m.name + '+0x' + p.sub(m.base).toString(16); } catch (e) {}
  return p.toString();
}
Process.setExceptionHandler(function (d) {
  if (d.type !== 'access-violation') return false;
  var c = d.context, r = {};
  ['eip', 'eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'esp', 'ebp'].forEach(function (k) { r[k] = c[k].toString(); });
  var fr = [];
  try { fr = Thread.backtrace(c, Backtracer.FUZZY).slice(0, 20).map(where); } catch (e) {}
  var stk = [];
  try { for (var i = 0; i < 48; i++) { var v = c.esp.add(4 * i).readPointer(); var w = where(v); if (w.indexOf('+0x') > 0) stk.push('[esp+' + (4 * i).toString(16) + '] ' + w); } } catch (e) {}
  send({ t: 'av', at: where(d.address), mem: d.memory ? { op: d.memory.operation, addr: d.memory.address.toString() } : null,
         regs: r, tid: Process.getCurrentThreadId(), frames: fr, stack: stk });
  return false;
});
send({ t: 'armed' });
"""


def child_of(ppid: int) -> int | None:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"(Get-CimInstance Win32_Process -Filter \"ParentProcessId={ppid} and Name='SC3U.exe'\").ProcessId"],
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--launcher", type=int)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--log", required=True)
    ap.add_argument("--secs", type=float, default=120)
    a = ap.parse_args()
    pid = a.pid
    t0 = time.time()
    while not pid and time.time() - t0 < 30:
        pid = child_of(a.launcher)
        time.sleep(0.1)
    if not pid:
        print("no game")
        return 2
    out = open(a.log, "a", encoding="utf-8")
    sess = frida.attach(pid)
    sc = sess.create_script(JS)
    sc.on("message", lambda m, d: (out.write(json.dumps(m.get("payload", m)) + "\n"), out.flush()))
    sc.load()
    print("attached", pid, "after %.1f s" % (time.time() - t0), flush=True)
    detached = []
    sess.on("detached", lambda *x: detached.append(x))
    while not detached and time.time() - t0 < a.secs:
        time.sleep(0.5)
    print("done:", "game gone" if detached else "timeout")
    return 0


if __name__ == "__main__":
    sys.exit(main())
