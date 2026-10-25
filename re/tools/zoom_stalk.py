"""zoom_stalk.py - task zoomcrash (2026-10-25): follow the game thread from the iso view zoom-in slot (SIMSPR vt slot
+0x633f0, sc3resize's zc_wrap0 when ZOOMCENTER is on) and write every basic block it runs (module+offset, esp, ebp) to
a file, flushed per line, so the trail survives a process kill that no exception handler sees.

Read-only: Interceptor.attach + Stalker (code runs from Stalker's copy, nothing in the game is written).
    py re/tools/zoom_stalk.py --pid <pid> --log <file> [--calls 2] [--blocks 40000]
--calls: stalk from the N-th zoom-in call on (earlier calls only log their caller).
"""
import argparse
import json
import sys
import time

import frida

JS = r"""
var LOG = %LOG%, FROM = %CALLS%, MAXB = %BLOCKS%, STALKWRAP = false;
var f = new File(LOG, 'a');
function w(s) { f.write(s + '\n'); f.flush(); }
var mods = Process.enumerateModules();
function where(p) {
  for (var i = 0; i < mods.length; i++) { var m = mods[i]; if (p.compare(m.base) >= 0 && p.compare(m.base.add(m.size)) < 0) return m.name + '+0x' + p.sub(m.base).toString(16); }
  return p.toString();
}
var ss = Process.getModuleByName('SIMSPR.DLL');
var slot = ss.base.add(0x633f0), target = slot.readPointer();
w('armed: slot ' + where(slot) + ' -> ' + where(target));
var n = 0, nb = 0, following = false;
Interceptor.attach(target, { onEnter: function () {
  n++;
  var fr = Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 12).map(where);
  w('call #' + n + ' tid ' + this.threadId + ' ecx ' + this.context.ecx + ' esp ' + this.context.esp + ' ret ' + where(this.returnAddress) + ' | ' + fr.join(' < '));
  if (STALKWRAP && n >= FROM && !following) { following = true; startStalk(this.threadId); }
}, onLeave: function (r) { w('leave #' + n + ' ret ' + r); } });
function startStalk(tid) {
  {
    Stalker.follow(tid, { transform: function (it) {
      var ins = it.next(), first = true;
      while (ins !== null) {
        if (first) { it.putCallout(function (c) {
          nb++;
          if (nb <= MAXB) w('B ' + where(c.pc) + ' esp ' + c.esp + ' ebp ' + c.ebp + ' eax ' + c.eax);
          else if (nb === MAXB + 1) { w('block cap reached'); }
        }); first = false; }
        it.keep();
        ins = it.next();
      }
    } });
    w('stalking tid ' + tid);
  }
}
var nr = 0;
Interceptor.attach(ss.base.add(0x42e1b), function () {   /* back in ZoomIn FUN_10042d8a after the vt+0x60 call */
  nr++;
  var c = this.context;
  w('at SIMSPR+0x42e1b #' + nr + ' esp ' + c.esp + ' ebp ' + c.ebp + ' esi ' + c.esi + ' ebx ' + c.ebx + ' [esp] ' + c.esp.readPointer() +
    ' | ebp-0x20 ' + c.ebp.sub(0x20) + ' [ebp+8] ' + c.ebp.add(8).readPointer() + ' ret ' + where(c.ebp.add(4).readPointer()));
  if (nr >= FROM && !following) { following = true; startStalk(this.threadId); }
});
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--calls", type=int, default=2)
    ap.add_argument("--blocks", type=int, default=40000)
    ap.add_argument("--secs", type=float, default=900)
    a = ap.parse_args()
    sess = frida.attach(a.pid)
    sc = sess.create_script(JS.replace("%LOG%", json.dumps(a.log)).replace("%CALLS%", str(a.calls))
                            .replace("%BLOCKS%", str(a.blocks)))
    sc.on("message", lambda m, d: print(m, flush=True) if m.get("type") == "error" else None)
    sc.load()
    print("attached", a.pid, flush=True)
    gone = []
    sess.on("detached", lambda *x: gone.append(x))
    t0 = time.time()
    while not gone and time.time() - t0 < a.secs:
        time.sleep(0.5)
    print("done:", repr(gone) if gone else "timeout", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
