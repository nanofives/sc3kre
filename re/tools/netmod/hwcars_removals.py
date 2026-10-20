#!/usr/bin/env python3
r"""hwcars_removals.py - read-only: WHY street cars end, per cell (task hwcars 2026-10-19). Frida on SC3_PID, STRTSIM:
  FUN_1001eec4  NeedVehicleDisappear (producer vt+0x14; sc3cartrips calls it for non-route cars): returns 1 = the
                density despawn (CAR_TRIPS.md 1.2) [CONFIRMED @ STRTSIM 0x1001eec4]; arg 1 = car + 0x18
  FUN_1001c750  SelectPathFromConnectingNodeOnNextCell: returns 0 = no path into the next cell (off map, outside the
                sim rect, not road, no lane graph, or no arrival node) [CONFIRMED @ STRTSIM 0x1001c750]; ecx = car
  FUN_1001c440  SelectNextPath: returns 0 = no path (dead end / no edge) [CONFIRMED @ STRTSIM 0x1001c440]; ecx = car
  FUN_1001c9e0  Shutdown (the car leaves) [CONFIRMED @ STRTSIM 0x1001c9e0]
The cause recorded for a Shutdown is the last of these events the car had (within 2 s), else "other".

  py -3.12 hwcars_removals.py X0,Z0,X1,Z1 SECS OUT.json
"""
import json, os, sys, time
import frida
import os as _os  # noqa: E402
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var B = %s;
var S = Process.getModuleByName('STRTSIM.DLL').base;
function A(va) { return S.add(va - 0x10000000); }
var last = {}, out = {};
function pos(c) { return [c.add(0x0c).readS32() >> 8, c.add(0x14).readS32() >> 8]; }
function mark(c, why) { last[c.toString()] = [why, Date.now(), pos(c)]; }
Interceptor.attach(A(0x1001eec4), { onEnter: function (a) { this.c = a[0].sub(0x18); },
  onLeave: function (r) { if ((r.toInt32() & 0xff) === 1) try { mark(this.c, 'density'); } catch (e) {} } });
Interceptor.attach(A(0x1001c750), { onEnter: function () { this.c = this.context.ecx; },
  onLeave: function (r) { if ((r.toInt32() & 0xff) === 0) try { mark(this.c, 'nextcell'); } catch (e) {} } });
Interceptor.attach(A(0x1001c440), { onEnter: function () { this.c = this.context.ecx; },
  onLeave: function (r) { if ((r.toInt32() & 0xff) === 0) try { mark(this.c, 'nopath'); } catch (e) {} } });
Interceptor.attach(A(0x1001c9e0), { onEnter: function () {
  var c = this.context.ecx, k = c.toString();
  try {
    var p = pos(c);
    if (p[0] < B[0] || p[0] > B[2] || p[1] < B[1] || p[1] > B[3]) return;
    var l = last[k], why = (l && Date.now() - l[1] < 2000) ? l[0] : 'other';
    var key = p[0] + ',' + p[1] + ',' + why; out[key] = (out[key] || 0) + 1;
  } catch (e) {}
  delete last[k];
} });
rpc.exports = { take: function () { return out; } };
"""
box = list(map(int, sys.argv[1].split(","))); secs = float(sys.argv[2])
sc3pause.require_running(int(os.environ["SC3_PID"]), "hwcars_removals")
s = frida.attach(int(os.environ["SC3_PID"]))
sc = s.create_script(JS % json.dumps(box)); sc.load()
time.sleep(secs)
r = sc.exports_sync.take(); s.detach()
json.dump({"box": box, "secs": secs, "ends": r}, open(sys.argv[3], "w"), indent=1)
tot = {}
for k, n in r.items():
    tot[k.split(",")[2]] = tot.get(k.split(",")[2], 0) + n
print("ends by cause", tot)
