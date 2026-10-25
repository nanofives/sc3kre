"""exit_catch.py - attach Frida to one running game and log how it dies (task zoomcrash, 2026-10-25).

For a process that vanishes with no VEH FAULT line and no Windows crash event. Logs, as JSON lines written
synchronously (File API in the agent, so a line survives the process ending right after it):
  * every exception Frida sees first (any type, not only access violations), with module+offset, registers,
    a fuzzy backtrace and module words on the stack; OutputDebugString / C++ throw noise is counted, not logged
  * calls to the exits: ExitProcess, TerminateProcess, NtTerminateProcess, RtlExitUserProcess, RaiseFailFastException,
    UnhandledExceptionFilter, msvcrt exit/_exit/abort, with the caller backtrace.
Read-only (Interceptor.attach + an exception handler that returns false: nothing is changed or stolen).
Do not attach while the game is paused (memory project-frida-paused-attach-deadlock).

    py re/tools/exit_catch.py --pid <SC3U pid> --log <file> [--secs 900]
"""
import argparse
import json
import sys
import time

import frida

JS = r"""
var LOG = %LOG%;
var f = new File(LOG, 'a');
function w(o) { try { f.write(JSON.stringify(o) + '\n'); f.flush(); } catch (e) {} try { send(o); } catch (e) {} }
function where(p) {
  try { var m = Process.findModuleByAddress(p); if (m) return m.name + '+0x' + p.sub(m.base).toString(16); } catch (e) {}
  return p.toString();
}
function stackwords(esp, n) {
  var out = [];
  try { for (var i = 0; i < n; i++) { var v = esp.add(4 * i).readPointer(); var s = where(v); if (s.indexOf('+0x') > 0) out.push('[esp+' + (4 * i).toString(16) + '] ' + s); } } catch (e) {}
  return out;
}
var nq = {};
function seen(key, max) { nq[key] = (nq[key] || 0) + 1; return nq[key] > max; }
Process.setExceptionHandler(function (d) {
  var c = d.context, r = {};
  ['eip', 'eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'esp', 'ebp'].forEach(function (k) { try { r[k] = c[k].toString(); } catch (e) {} });
  if (d.type === 'system' && seen(d.type + '@' + where(d.address), 3)) return false;   /* RaiseException noise */
  var fr = [];
  try { fr = Thread.backtrace(c, Backtracer.FUZZY).slice(0, 24).map(where); } catch (e) {}
  w({ t: 'exc', type: d.type, at: where(d.address), mem: d.memory ? { op: d.memory.operation, addr: d.memory.address.toString() } : null,
      regs: r, tid: Process.getCurrentThreadId(), frames: fr, stack: stackwords(c.esp, 64), ms: Date.now() });
  return false;
});
function hook(mod, name) {
  var p = null;
  try { p = Process.getModuleByName(mod).findExportByName(name); } catch (e) {}
  if (!p) { w({ t: 'nohook', mod: mod, name: name }); return; }
  Interceptor.attach(p, { onEnter: function (args) {
    if (name === 'RaiseException') {   /* ODS 0x40010006/0x4001000a and C++ 0xe06d7363: first 3 per code + caller */
      var code = args[0].toUInt32();
      if (seen('re' + code.toString(16) + '@' + where(this.returnAddress), 3)) return;
    }
    var fr = [];
    try { fr = Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 32).map(where); } catch (e) {}
    var a = [];
    for (var i = 0; i < 3; i++) { try { a.push(args[i].toString()); } catch (e) {} }
    w({ t: 'exit', fn: mod + '!' + name, args: a, tid: Process.getCurrentThreadId(), frames: fr,
        stack: stackwords(this.context.esp, 96), ms: Date.now() });
  } });
}
[['kernel32.dll', 'ExitProcess'], ['kernelbase.dll', 'TerminateProcess'], ['ntdll.dll', 'NtTerminateProcess'],
 ['ntdll.dll', 'RtlExitUserProcess'], ['kernelbase.dll', 'RaiseFailFastException'], ['kernelbase.dll', 'UnhandledExceptionFilter'],
 ['kernelbase.dll', 'RaiseException'], ['ntdll.dll', 'RtlReportException'],
 ['msvcrt.dll', 'exit'], ['msvcrt.dll', '_exit'], ['msvcrt.dll', 'abort'], ['kernel32.dll', 'FatalAppExitA'],
 ['user32.dll', 'PostQuitMessage']].forEach(function (x) { hook(x[0], x[1]); });
w({ t: 'armed', ms: Date.now() });
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--secs", type=float, default=900)
    a = ap.parse_args()
    sess = frida.attach(a.pid)
    sc = sess.create_script(JS.replace("%LOG%", json.dumps(a.log)))
    sc.on("message", lambda m, d: None)
    sc.load()
    print("attached", a.pid, flush=True)
    gone = []
    sess.on("detached", lambda *x: gone.append(x))
    t0 = time.time()
    while not gone and time.time() - t0 < a.secs:
        time.sleep(0.5)
    print("done:", "game gone " + repr(gone) if gone else "timeout", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
