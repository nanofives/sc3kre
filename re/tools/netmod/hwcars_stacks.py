#!/usr/bin/env python3
r"""hwcars_stacks.py - read-only: where each game thread is (PC + module addresses found on its stack), for a hang.

Frida Process.enumerateThreads() gives each thread's context; the top 64 stack words that fall inside a module image
are printed as module+offset (candidate return addresses, not a verified unwind).

  py -3.12 hwcars_stacks.py [--words 64]       SC3_PID = the game
"""
import os, sys
import frida
import os as _os  # noqa: E402
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

N = int(sys.argv[sys.argv.index("--words") + 1]) if "--words" in sys.argv else 64
JS = r"""
function name(p) { var m = Process.findModuleByAddress(p); return m ? m.name + '+0x' + p.sub(m.base).toString(16) : null; }
rpc.exports = { run: function (n) {
  var out = [];
  Process.enumerateThreads().forEach(function (t) {
    var c = t.context, r = {id: t.id, state: t.state, pc: name(c.pc) || c.pc.toString(), stack: []};
    try { for (var i = 0; i < n; i++) { var v = c.sp.add(4 * i).readPointer(); var s = name(v); if (s) r.stack.push(s); } } catch (e) {}
    out.push(r);
  });
  return out;
} };
"""
sc3pause.require_running(int(os.environ["SC3_PID"]), "hwcars_stacks")
s = frida.attach(int(os.environ["SC3_PID"]))
sc = s.create_script(JS); sc.load()
for t in sc.exports_sync.run(N):
    print("thread", t["id"], t["state"], "pc", t["pc"])
    print("   ", " ".join(t["stack"][:24]))
s.detach()
