#!/usr/bin/env python3
r"""animrot: trace child-sprite calls (read-only hooks on the SIMSPR bodies), streamed with send() so a crash keeps them.

  py -3.12 childtrace.py <seconds> <out.txt>       (SC3_PID = the game, running)

Logs for every call: body, this, state (+4 >> 30), machine (+0x10), drawbase (+0x798), masks +0x14/+0x18, args, caller.
Bodies: 0x10014083 SetAnimMachine(machine), 0x10014695 Prepare(zoom, rot, b), 0x100148da Unprepare(zoom, rot),
0x10014444 GetAllSpans(zoom, rot, rect), 0x100155bf ViewChange(zoom, rot), 0x1001531f StartAnimation. Only sprites whose
machine has drawbase 0 (children) or that are inside ViewChange are logged, plus every ViewChange / StartAnimation.
"""
import os
import sys
import time

import frida

JS = r"""
var spr = Process.getModuleByName('SIMSPR.DLL').base;
function mr(p) { var m = Process.findModuleByAddress(p); return m ? m.name + '+0x' + p.sub(m.base).toString(16) : '' + p; }
function info(o) {
  var m = o.add(0x10).readPointer();
  return {o: '' + o, st: o.add(4).readU32() >>> 30, m: '' + m, db: m.isNull() ? -1 : m.add(0x798).readU8(),
          m14: o.add(0x14).readU32().toString(16), m18: o.add(0x18).readU32().toString(16)};
}
var inVC = 0;
function h(name, rva, nargs, filt) {
  Interceptor.attach(spr.add(rva), { onEnter: function (a) {
    var o = this.context.ecx;
    if (name === 'StartAnimation') o = o.sub(0xc);
    var i = info(o);
    if (filt && i.db !== 0 && !inVC) return;
    var args = []; for (var k = 0; k < nargs; k++) args.push(a[k].toInt32());
    var bt = [];
    if (name === 'GetAllSpans' && args[1] !== 1) bt = Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 6).map(mr);
    send({t: Date.now(), f: name, i: i, a: args, ret: mr(this.returnAddress), bt: bt});
    if (name === 'ViewChange') inVC++;
  }, onLeave: function () { if (name === 'ViewChange') inVC--; } });
}
h('SetAnimMachine', 0x14083, 1, 0);
h('Prepare', 0x14695, 3, 1);
h('Unprepare', 0x148da, 2, 1);
h('GetAllSpans', 0x14444, 2, 1);
h('ViewChange', 0x155bf, 2, 0);
h('StartAnimation', 0x1531f, 4, 0);
"""


def main(a):
    pid = int(os.environ["SC3_PID"])
    out = open(a[1], "w", encoding="utf-8")
    n = [0]

    def on(msg, data):
        if msg["type"] == "send" and n[0] < 4000:
            n[0] += 1
            out.write(repr(msg["payload"]) + "\n")
            out.flush()
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.on("message", on)
    sc.load()
    t0 = time.time()
    try:
        while time.time() - t0 < float(a[0]):
            time.sleep(0.5)
        sc.unload()
        s.detach()
    except Exception as e:  # noqa: BLE001  (the game may die)
        out.write("detach: %r\n" % e)
    out.close()
    print(n[0], "events")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
