#!/usr/bin/env python3
r"""hwcars_tracks.py - read-only: record the street cars' positions in a box (task hwcars 2026-10-19).

Frida on SC3_PID. Hooks in STRTSIM (Ghidra VAs, CAR_TRIPS.md 1.1):
  FUN_1001d2c0  car Tick (thiscall, ecx = car): x = car+0x0c, z = car+0x14 (1/256 cell), +0x10 read as the height,
                +0x2d class (0 car, 1 train, 2 subway), +0x22 visible [CONFIRMED @ STRTSIM 0x1001d2c0 for x / z]
  FUN_1001c9e0  car Shutdown (the car leaves the city) [CONFIRMED @ STRTSIM 0x1001c9e0]
sc3cartrips swaps vtable slots only (car +0x154 / +0x158, producer +0x10 / +0x14) and patches SC3U.exe+0x25a10, so
these two entries are free. A sample is kept when the car is inside the box and moved, or 0.25 s passed.

  py -3.12 hwcars_tracks.py X0,Z0,X1,Z1 SECS OUT.json
OUT: {"box", "t0", "cars": {"ptr/n": [[ms, x, y, z, cls, vis], ...]}, "ends": {"ptr/n": ms}}; n counts Shutdowns
at that address (a car address is reused after a removal). Analyse with hwcars_tracks_an.py.
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
var cars = {}, ends = {}, last = {}, gen = {};
function key(c) { var p = c.toString(); return p + '/' + (gen[p] || 0); }
var t0 = Date.now();
Interceptor.attach(A(0x1001d2c0), {
  onEnter: function () {
    var c = this.context.ecx;
    try {
      var x = c.add(0x0c).readS32(), y = c.add(0x10).readS32(), z = c.add(0x14).readS32();
      var cx = x >> 8, cz = z >> 8;
      if (cx < B[0] || cx > B[2] || cz < B[1] || cz > B[3]) return;
      var k = key(c), t = Date.now() - t0, l = last[k];
      if (l && l[1] === x && l[2] === z && t - l[0] < 250) return;
      last[k] = [t, x, z];
      (cars[k] || (cars[k] = [])).push([t, x, y, z, c.add(0x2d).readU8(), c.add(0x22).readU8()]);
    } catch (e) {}
  }
});
Interceptor.attach(A(0x1001c9e0), {
  onEnter: function () {   /* the address is reused by the next car: later samples go to a new key */
    var c = this.context.ecx, p = c.toString(), k = key(c);
    if (cars[k]) ends[k] = Date.now() - t0;
    gen[p] = (gen[p] || 0) + 1;
  }
});
rpc.exports = { take: function () { return {cars: cars, ends: ends}; } };
"""


def main(a):
    box = list(map(int, a[1].split(","))); secs = float(a[2])
    sc3pause.require_running(int(os.environ["SC3_PID"]), "hwcars_tracks")
    s = frida.attach(int(os.environ["SC3_PID"]))
    sc = s.create_script(JS % json.dumps(box)); sc.load()
    t0 = time.time()
    time.sleep(secs)
    r = sc.exports_sync.take(); s.detach()
    r.update(box=box, secs=secs, t0=t0)
    json.dump(r, open(a[3], "w"))
    n = sum(len(v) for v in r["cars"].values())
    print("cars", len(r["cars"]), "samples", n, "ends in box", len(r["ends"]))


if __name__ == "__main__":
    main(sys.argv)
