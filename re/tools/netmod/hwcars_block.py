#!/usr/bin/env python3
r"""hwcars_block.py - TEST LEVER (task hwcars 2026-10-19): hold the highway traffic byte of some cells at V for SECS,
then put the original values back. Used to make trips take a cloverleaf loop: at a highway node the router keeps the
last allowed neighbour in the order z-1, x-1, z+1, x+1 whose traffic is below TrafficAnnoyanceLevel 165
(HIGHWAY_TRIPS.md, [CONFIRMED @ SimTransit 0x10007881, 0x100086e7]), so a straight-on cell held at 200 is skipped and the
loop exit is taken. This is a congestion signal the stock router already reads; nothing in the mods changes.

Layer: SimTransit FUN_10006edd (thiscall, ecx = the traffic layer, called on every deposit) gives the layer pointer;
highway grid = [[layer + 0x70] + 0xc][x] + z (bytes), as the road grid +0x6c that function writes
[CONFIRMED @ SimTransit 0x10006edd]; +0x70 = highway grid (hwtrips_probe.py, HIGHWAY_TRIPS.md).

  py -3.12 hwcars_block.py X,Z[;X,Z...] V SECS        SC3_PID = the game
"""
import os, sys, time
import frida
import os as _os  # noqa: E402
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var TR = Process.getModuleByName('SimTransit.dll').base;
var L = null;
var h = Interceptor.attach(TR.add(0x6edd), { onEnter: function () { if (!L) L = this.context.ecx; } });
function cell(x, z) { return L.add(0x70).readPointer().add(0xc).readPointer().add(4 * x).readPointer().add(z); }
rpc.exports = {
  ready: function () { if (L) { h.detach(); } return L !== null; },
  get: function (cs) { return cs.map(function (c) { return cell(c[0], c[1]).readU8(); }); },
  set: function (cs, vs) { for (var i = 0; i < cs.length; i++) cell(cs[i][0], cs[i][1]).writeU8(vs[i]); return 1; }
};
"""
cells = [tuple(map(int, c.split(","))) for c in sys.argv[1].split(";")]
v, secs = int(sys.argv[2]), float(sys.argv[3])
sc3pause.require_running(int(os.environ["SC3_PID"]), "hwcars_block")
s = frida.attach(int(os.environ["SC3_PID"]))
sc = s.create_script(JS); sc.load(); api = sc.exports_sync
t0 = time.time()
while not api.ready():
    if time.time() - t0 > 60:
        raise SystemExit("no deposit within 60 s (sim paused?)")
    time.sleep(0.2)
orig = api.get([list(c) for c in cells])
print("cells", cells, "original", orig, "-> holding", v, "for", secs, "s")
t0 = time.time()
try:
    while time.time() - t0 < secs:
        api.set([list(c) for c in cells], [v] * len(cells))
        time.sleep(0.25)
finally:
    api.set([list(c) for c in cells], orig)
    print("restored", api.get([list(c) for c in cells]))
    s.detach()
