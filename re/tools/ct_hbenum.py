#!/usr/bin/env python3
r"""ct_hbenum.py - list who listens to the SC3U.exe heartbeat and which agents its agent loop ticks (read-only).

  py -3.12 ct_hbenum.py [--samples 5]        # SC3_PID = a running game (sc3io.game_pid)

Heartbeat FUN_00426140 (this = the object SIMCITY FUN_1000ee96() returns): lists +0x88 (every call), +0x8c / +0x90 /
+0x94 (masked); each node [2] = listener, called at listener vt+0xc with the time delta; all skipped while the
suspend count +0xb0 != 0 (STRTSIM.md 8, pausetrips). The agent loop FUN_00425a10 walks buckets this+0x30..+0x34
(chains: node[0] next, node[1] agent, node[2] flags; bit 4 = ticked through agent vt+0x100).
Prints each listener's class (vtable) and +0xc target, and per agent-loop owner the agents by vtable and Tick target.
"""
import argparse
import json
import os
import sys

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3io  # noqa: E402

JS = r"""
function where(p) {
  var m = Process.findModuleByAddress(p);
  if (!m) return p.toString();
  var off = p.sub(m.base).toInt32();
  return m.name + ':0x' + ((m.name.toLowerCase().endsWith('.exe') ? 0x400000 : 0x10000000) + off).toString(16);
}
var SC = Process.getModuleByName('SIMCITY.DLL');
var get = new NativeFunction(SC.base.add(0xee96), 'pointer', []);
var AGLOOP = Process.enumerateModules()[0].base.add(0x25a10);
function listOf(head) {
  var out = [], n = head.readPointer(), k = 0;
  while (!n.equals(head) && k++ < 500) { out.push(n.add(8).readPointer()); n = n.readPointer(); }
  return out;
}
function agents(owner) {
  var b0 = owner.add(0x30).readPointer(), b1 = owner.add(0x34).readPointer(), nb = b1.sub(b0).toInt32() >> 2;
  var by = {}, total = 0, ticked = 0;
  for (var i = 0; i < nb && i < 100000; i++) {
    var n = b0.add(4 * i).readPointer(), k = 0;
    while (!n.isNull() && k++ < 10000) {
      var a = n.add(4).readPointer(), fl = n.add(8).readU8(), vt = a.readPointer();
      var key = where(vt) + ' tick=' + where(vt.add(0x100).readPointer()) + ((fl & 4) ? ' [ticked]' : ' [not ticked]');
      by[key] = (by[key] || 0) + 1; total++; if (fl & 4) ticked++;
      n = n.readPointer();
    }
  }
  return { buckets: nb, total: total, ticked: ticked, by: by };
}
rpc.exports = {
  run: function () {
    var hb = get(), out = { hb: hb.toString(), hb_vt: where(hb.readPointer()), susp: hb.add(0xb0).readU32(), lists: {} };
    [0x88, 0x8c, 0x90, 0x94].forEach(function (o) {
      var L = [];
      listOf(hb.add(o).readPointer()).forEach(function (l) {
        var vt = l.readPointer(), f = vt.add(0xc).readPointer(), e = { listener: l.toString(), vt: where(vt), fn: where(f) };
        // the agent loop's owner: the listener's +0xc is a thunk into FUN_00425a10 or calls it; record the bucket view of
        // any listener whose object (or object+4) looks like an agent-loop owner (buckets at +0x30..+0x34)
        try {
          [0, 4, -4].forEach(function (d) {
            var o2 = l.add(d), b0 = o2.add(0x30).readPointer(), b1 = o2.add(0x34).readPointer(), nb = b1.sub(b0).toInt32();
            if (nb > 0 && nb < 0x100000 && (nb & 3) === 0 && f.equals(AGLOOP) || (d === 0 && f.equals(AGLOOP))) e.agents = agents(o2);
          });
        } catch (x) {}
        L.push(e);
      });
      out.lists['+0x' + o.toString(16)] = L;
    });
    return out;
  },
  agentsAt: function (p) { return agents(ptr(p)); }
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    pid = sc3io.game_pid()
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    r = sc.exports_sync.run()
    txt = json.dumps(r, indent=1)
    print(txt)
    if a.out:
        open(a.out, "w").write(txt)
    s.detach()


if __name__ == "__main__":
    main()
