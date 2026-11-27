#!/usr/bin/env python3
r"""animrot probe: list live cSC3CitySpriteInstAnim objects (SIMSPR vtable 0x10062a5c) and their anim machine.

  py -3.12 animprobe.py            (SC3_PID = the game, running, not paused)

Read only. Finds instances by scanning rw- memory for the vtable pointer (set_funds.py pattern), then prints per
instance: +4 state (bits 30-31), +0x10 machine, machine +0x780 zoom / +0x784 rot / +0x798 draw-base flag, the
prepared masks +0x14 / +0x18, and for every [zoom][rot] the lengths of the machine's frame vector (+0x3c0) and of its
child-sprite list (+0x1e0), the script list (+0x0) and the attribute's RegRect frame list (attrib +0x30 + ...).
"""
import json
import os
import sys

import frida

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "re", "tools"))
import sc3pause  # noqa: E402

JS = r"""
var spr = Process.getModuleByName('SIMSPR.DLL').base;
var vt = spr.add(0x62a5c);
var pat = [0, 1, 2, 3].map(function (i) { return ('0' + vt.shr(i * 8).and(0xff).toString(16)).slice(-2); }).join(' ');
function vlen(p) { var b = p.readU32(), e = p.add(4).readU32(); return (e - b) >> 2; }
rpc.exports = { scan: function () {
  var out = [];
  Process.enumerateRanges({ protection: 'rw-', coalesce: true }).forEach(function (r) {
    if (r.size > 512 * 1024 * 1024) return;
    try { Memory.scanSync(r.base, r.size, pat).forEach(function (h) {
      var o = h.address;
      try {
        if (!o.add(0xc).readPointer().equals(spr.add(0x62a44))) return;   // second vtable at +0xc
        var e = {at: '' + o, w4: '0x' + (o.add(4).readU32() >>> 0).toString(16), state: o.add(4).readU32() >>> 30,
                 attrib: '' + o.add(8).readPointer(), m14: '0x' + o.add(0x14).readU32().toString(16),
                 m18: '0x' + o.add(0x18).readU32().toString(16)};
        var m = o.add(0x10).readPointer();
        e.machine = '' + m;
        if (!m.isNull()) {
          e.zoom = m.add(0x780).readS32(); e.rot = m.add(0x784).readS32(); e.drawbase = m.add(0x798).readU8();
          e.pos = [m.add(0x788).readS32(), m.add(0x78c).readS32(), m.add(0x790).readS32()];
          var fr = [], ch = [], sc = [];
          for (var z = 0; z < 5; z++) { var a = [], b = [], c = [];
            for (var q = 0; q < 4; q++) { a.push(vlen(m.add(0x3c0 + z * 0x30 + q * 0xc)));
              b.push(vlen(m.add(0x1e0 + z * 0x30 + q * 0xc))); c.push(vlen(m.add(z * 0x30 + q * 0xc))); }
            fr.push(a); ch.push(b); sc.push(c); }
          e.frames = fr; e.children = ch; e.scripts = sc;
        }
        out.push(e);
      } catch (x) {}
    }); } catch (e) {}
  });
  return out;
} };
"""


def main():
    pid = int(os.environ["SC3_PID"])
    sc3pause.require_running(pid, "animprobe")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    r = sc.exports_sync.scan()
    sc.unload()
    s.detach()
    for e in r:
        print(json.dumps(e))
    print("%d instances" % len(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
