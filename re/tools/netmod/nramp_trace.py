#!/usr/bin/env python3
r"""nramp_trace.py - live, read-only trace of the SIMNTWRK on-ramp / tunnel / slope builders (netramp, 2026-10-13).

Attaches Frida to SC3_PID (or the only SC3U.exe) and logs, until Ctrl+C or --secs:
  - netmgr vt+0x90 FUN_100145aa (on-ramp cost): the selection's points, read after the sel vt+0xc call at 0x1001462d
  - netmgr vt+0xac FUN_1000abde (on-ramp build): caller (module+offset), the 3 points read at 0x1000ad8d, result
  - FUN_10008919 (piece placer) when called from inside FUN_1000abde, FUN_1001ca1a or FUN_1001c102: id, state, cell
  - netmgr vt+0x138 FUN_1001ca1a / vt+0x13c FUN_1001c102 (tunnel builders): netType, result
  - FUN_1001a2c0 (slope piece lookup): netType and the piece it returns (first 50 calls)
Nothing is written to the game. Output: JSON lines on stdout.

  py -3.12 nramp_trace.py [--secs N]
"""
import json
import os
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var m = Process.getModuleByName('SIMNTWRK.DLL'); var B = m.base;
function A(va) { return B.add(va - 0x10000000); }
function where(p) { var mm = Process.findModuleByAddress(p); return mm ? mm.name + '+0x' + p.sub(mm.base).toString(16) : '' + p; }
function pts(p, n) { var o = []; for (var i = 0; i < n && i < 8; i++) { var q = p.add(12 * i); o.push([q.readS32() >> 8, q.add(4).readS32() >> 8, q.add(8).readS32()]); } return o; }
var inside = 0, slopeN = 0;
var ranges = [[0x1000abde, 0x1000abde + 4375, 'onramp'], [0x1001ca1a, 0x1001ca1a + 3285, 'tunnel_hwy'], [0x1001c102, 0x1001c102 + 2328, 'tunnel_rr']];
Interceptor.attach(A(0x1001462d), function () {
  var ebp = this.context.ebp; var n = ebp.sub(0x10).readU32();
  send({ev: 'cost90', n: n, pts: pts(ebp.sub(0x1828), n)});
});
Interceptor.attach(A(0x1000abde), {
  onEnter: function (a) { this.t = Date.now(); send({ev: 'onramp_enter', caller: where(this.returnAddress), sel_vt: where(a[0].readPointer()), bt: Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 8).map(where)}); },
  onLeave: function (r) { send({ev: 'onramp_leave', ret: r.toInt32() & 0xff, ms: Date.now() - this.t}); }
});
Interceptor.attach(A(0x1000ad8d), function () {
  var ebp = this.context.ebp; var n = ebp.sub(0xf4).readU32();
  send({ev: 'onramp_pts', n: n, pts: pts(ebp.sub(0x130), n)});
});
Interceptor.attach(A(0x10008919), function (a) {
  var ra = this.returnAddress.sub(B).toInt32() + 0x10000000, who = null;
  for (var i = 0; i < ranges.length; i++) if (ra >= ranges[i][0] && ra < ranges[i][1]) who = ranges[i][2];
  if (!who) return;
  var cell = a[1]; var v = a[2].toUInt32();
  send({ev: 'place', from: who, site: '0x' + ra.toString(16), id: v >>> 8, state: v & 0xff, cell: [cell.readS32() >> 8, cell.add(4).readS32() >> 8, cell.add(12).readS32() >> 8, cell.add(16).readS32() >> 8]});
});
[[0x1001ca1a, 'tunnel_hwy'], [0x1001c102, 'tunnel_rr']].forEach(function (f) {
  Interceptor.attach(A(f[0]), {
    onEnter: function (a) { send({ev: f[1] + '_enter', caller: where(this.returnAddress)}); },
    onLeave: function (r) { send({ev: f[1] + '_leave', ret: r.toInt32() & 0xff}); }
  });
});
Interceptor.attach(A(0x1001a2c0), {
  onEnter: function (a) { this.go = slopeN++ < 50; if (this.go) { this.net = a[1].toInt32(); this.id = a[3]; this.st = a[4]; this.c = [a[0].readS32() >> 8, a[0].add(4).readS32() >> 8]; this.ra = where(this.returnAddress); } },
  onLeave: function (r) { if (this.go && (r.toInt32() & 0xff)) send({ev: 'slope', net: this.net, cell: this.c, id: this.id.readU32(), state: this.st.readU8(), caller: this.ra}); }
});
send({ev: 'ready', base: '' + B});
"""


def main(argv):
    secs = float(argv[argv.index("--secs") + 1]) if "--secs" in argv else 1e9
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "nramp_trace")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.on("message", lambda m, d: print(json.dumps(m.get("payload", m)), flush=True))
    sc.load()
    t0 = time.time()
    try:
        while time.time() - t0 < secs:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    s.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
