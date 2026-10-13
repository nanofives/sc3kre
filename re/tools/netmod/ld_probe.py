#!/usr/bin/env python3
r"""ld_probe.py - read-only monthly traffic-density sampler for the lanedensity arms (verify/lanedensity/PRE.md).

Frida on SC3_PID. Nothing is written to the game except, with --start, the sc3resize keys P (unpause) and 1-4
(speed) posted to the game window (sc3io.key), after dismiss_tips.py has closed the startup tips.

Hooks:
  SimTransit FUN_100093e9  monthly publish (fastcall, ecx = traffic layer): the decayed live grid +0x6c is copied to
                           the snapshot +0x60 [CONFIRMED @ SimTransit 0x100093e9]. On leave the whole +0x60 grid
                           (rows[x][z], x < layer+0x14, z < layer+0x18) is sent, with the day count.
  SIMCITY FUN_1000aa4d     the day fire: days counted, clock +0x4c read (as lk_probe.py).

  py -3.12 ld_probe.py --months 14 --out arm.npz [--start 4]
Output: npz with grids (months x W x H, uint8, index [m, x, z] = save (x, z)), days (per month), dayno.
"""
import argparse
import os
import sys
import threading
import time

import frida
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402

JS = r"""
function mod(n) { return Process.getModuleByName(n); }
var TR = mod('SimTransit.dll').base, SC = mod('SIMCITY.DLL').base;
function A(b, va) { return b.add(va - 0x10000000); }
var days = 0, clock = null;
Interceptor.attach(A(SC, 0x1000aa4d), function () { days++; clock = this.context.ecx; });
Interceptor.attach(A(TR, 0x100093e9), {
  onEnter: function () { this.layer = this.context.ecx; },
  onLeave: function () {
    var L = this.layer, w = L.add(0x14).readU32(), h = L.add(0x18).readU32();
    var rows = L.add(0x60).readPointer().add(0xc).readPointer();
    var buf = new Uint8Array(w * h);
    for (var x = 0; x < w; x++) buf.set(new Uint8Array(rows.add(4 * x).readPointer().readByteArray(h)), x * h);
    send({w: w, h: h, days: days, dayno: clock ? clock.add(0x4c).readU32() : null}, buf.buffer);
  }
});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=14)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=int, default=0, help="unpause (P) and set this speed (1-4) first")
    ap.add_argument("--timeout", type=float, default=1800)
    a = ap.parse_args()
    pid = sc3io.game_pid()
    got, meta = [], []
    done = threading.Event()

    def on_msg(m, data):
        if m.get("type") != "send":
            print(m, flush=True)
            return
        p = m["payload"]
        got.append(np.frombuffer(data, dtype=np.uint8).reshape(p["w"], p["h"]).copy())
        meta.append((p["days"], p["dayno"] if p["dayno"] is not None else -1))
        print("month %d: days %d dayno %s sum %d" % (len(got), p["days"], p["dayno"], int(got[-1].sum())), flush=True)
        if len(got) >= a.months:
            done.set()

    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.on("message", on_msg)
    sc.load()
    if a.start:
        h = sc3io.game_hwnd(pid)
        sc3io.key(h, 0x50)
        time.sleep(1.0)
        sc3io.key(h, 0x30 + a.start)
    t0 = time.time()
    while not done.wait(5):
        if time.time() - t0 > a.timeout:
            print("timeout", flush=True)
            break
    s.detach()
    np.savez_compressed(a.out, grids=np.array(got), days=np.array([m[0] for m in meta]),
                        dayno=np.array([m[1] for m in meta]), secs=time.time() - t0)
    print("wrote %s (%d months, %.0f s)" % (a.out, len(got), time.time() - t0))


if __name__ == "__main__":
    main()
