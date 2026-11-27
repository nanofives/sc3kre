#!/usr/bin/env python3
r"""animrot: who starts / stops building animations? Read-only Frida hooks, counts + caller chains.

  py -3.12 hookanim.py <seconds> [--machines]      (SC3_PID = the game, running, not paused)

Hooks: SIMGEOM 0x10024e50 cISC3Occupant::AnimStart, 0x10024ec2 AnimStop (CodeView slot names, occupant vtable
0x1002a578 +0x64 / +0x68); SIMSPR 0x1001531f sprite StartAnimation (second vtable +0xc), 0x10015409 StopAnimation
(+0x10), 0x100155bf ViewChange, and the sprite's Tick 0x10014df9 (count only; sc3perf ANIMROT's wrapper calls it).
Each distinct caller chain (3 return addresses, module+offset) is counted. --machines: at the end, also list the
animated-class sprites that have a machine (animprobe.py's scan).
"""
import json
import os
import sys
import time

import frida

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "re", "tools"))
import sc3pause  # noqa: E402

JS = r"""
var geom = Process.getModuleByName('SIMGEOM.DLL').base, spr = Process.getModuleByName('SIMSPR.DLL').base;
var counts = {}, chains = {};
function mr(p) { var m = Process.findModuleByAddress(p); return m ? m.name + '+0x' + p.sub(m.base).toString(16) : '' + p; }
function hook(name, addr, deep) {
  counts[name] = 0;
  Interceptor.attach(addr, { onEnter: function () {
    counts[name]++;
    if (!deep) return;
    var bt = [mr(this.returnAddress)];
    try { var f = this.context.ebp; for (var i = 0; i < 3 && !f.isNull(); i++) { bt.push(mr(f.add(4).readPointer())); f = f.readPointer(); } } catch (e) {}
    var k = name + ' <- ' + bt.join(' <- ');
    chains[k] = (chains[k] || 0) + 1;
  } });
}
hook('occ.AnimStart', geom.add(0x24e50), 1);
hook('occ.AnimStop', geom.add(0x24ec2), 1);
hook('spr.StartAnimation', spr.add(0x1531f), 1);
hook('spr.StopAnimation', spr.add(0x15409), 1);
hook('spr.ViewChange', spr.add(0x155bf), 1);
hook('spr.Tick', spr.add(0x14df9), 0);
var vt = spr.add(0x62a5c);
var pat = [0, 1, 2, 3].map(function (i) { return ('0' + vt.shr(i * 8).and(0xff).toString(16)).slice(-2); }).join(' ');
rpc.exports = {
  take: function () { return {counts: counts, chains: chains}; },
  machines: function () {
    var out = [];
    Process.enumerateRanges({ protection: 'rw-', coalesce: true }).forEach(function (r) {
      if (r.size > 512 * 1024 * 1024) return;
      try { Memory.scanSync(r.base, r.size, pat).forEach(function (h) {
        var o = h.address;
        try {
          if (!o.add(0xc).readPointer().equals(spr.add(0x62a44))) return;
          var m = o.add(0x10).readPointer();
          if (m.isNull()) return;
          var ch = [];
          for (var z = 0; z < 5; z++) for (var q = 0; q < 4; q++) {
            var b = m.add(0x1e0 + z * 0x30 + q * 0xc), n = (b.add(4).readU32() - b.readU32()) >> 2;
            if (n) ch.push([z, q, n]);
          }
          out.push({at: '' + o, state: o.add(4).readU32() >>> 30, attrib: '' + o.add(8).readPointer(), machine: '' + m,
                    zoom: m.add(0x780).readS32(), rot: m.add(0x784).readS32(), drawbase: m.add(0x798).readU8(),
                    pos: [m.add(0x788).readS32(), m.add(0x78c).readS32(), m.add(0x790).readS32()], children: ch});
        } catch (x) {}
      }); } catch (e) {}
    });
    return out;
  }
};
"""


def main(a):
    pid = int(os.environ["SC3_PID"])
    secs = float(a[0])
    sc3pause.require_running(pid, "hookanim")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    time.sleep(secs)
    r = sc.exports_sync.take()
    m = sc.exports_sync.machines() if "--machines" in a else None
    sc.unload()
    s.detach()
    print(json.dumps(r["counts"]))
    for k, v in sorted(r["chains"].items(), key=lambda kv: -kv[1]):
        print("%6d  %s" % (v, k))
    if m is not None:
        for e in m:
            print(json.dumps(e))
        print("%d sprites with a machine" % len(m))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
