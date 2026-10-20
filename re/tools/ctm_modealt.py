#!/usr/bin/env python3
r"""ctm_modealt.py - in-game paired cost of route cars (verify/cartrips3 PRE): one game alternates sc3cartrips between
mode 2 (replace: route cars only) and mode 1 (capture only: the stock random cars) in ABBA blocks, through the export
sc3cartrips_mode(int). Per window (after a settle so the street turns over): agent-loop time per second (SC3U
FUN_00425a10, the DLL's time_agents=1 wrapper), sc3cartrips' own game-thread cycles per second (spawning, solving,
SelectAnEdge / NeedVehicleDisappear hooks), and the car count (sampled each second).

  set SC3_PID=<pid>
  py -3.12 ctm_modealt.py --window 45 --settle 30 --blocks 6 --out alt.json
"""
import argparse
import json
import os
import statistics
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sc3io  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var M = Process.getModuleByName('sc3cartrips.dll');
var fmode = new NativeFunction(M.getExportByName('sc3cartrips_mode'), 'int', ['int']);
var fcars = new NativeFunction(M.getExportByName('sc3cartrips_cars'), 'int', ['pointer', 'int']);
var buf = Memory.alloc(64);
rpc.exports = {
  read: function () { var n = fcars(buf, 14), v = []; for (var i = 0; i < n; i++) v.push(buf.add(4 * i).readU32()); return { v: v, t: Date.now() }; },
  mode: function (m) { return fmode(m); }
};
"""
TSC_MHZ = 3593.3   # measured in every sc3cartrips log on this machine (STAT tsc_mhz)


def c64(v, lo):
    return v[lo + 1] * 2 ** 32 + v[lo]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=float, default=45)
    ap.add_argument("--settle", type=float, default=30)
    ap.add_argument("--blocks", type=int, default=6)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sc3pause.require_running(sc3io.game_pid(), "ctm_modealt")
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()
    api = sc.exports_sync
    order = []
    for _ in range(a.blocks):
        order += [1, 2, 2, 1]
    wins = []
    for m in order:
        api.mode(m)
        time.sleep(a.settle)
        r0 = api.read()
        alive, route = [], []
        t_end = time.time() + a.window
        while time.time() < t_end:
            time.sleep(1)
            v = api.read()["v"]
            alive.append(v[1]); route.append(v[3])
        r1 = api.read()
        v0, v1 = r0["v"], r1["v"]
        dt = (r1["t"] - r0["t"]) / 1000.0
        w = {"mode": "route" if m == 2 else "stock", "secs": dt,
             "ag_ms_per_s": (c64(v1, 5) - c64(v0, 5)) / TSC_MHZ / 1000.0 / dt,
             "ag_calls_per_s": (v1[4] - v0[4]) / dt,
             "mod_ms_per_s": (c64(v1, 7) - c64(v0, 7)) / TSC_MHZ / 1000.0 / dt,
             "alive_mean": statistics.mean(alive) if alive else None, "route_mean": statistics.mean(route) if route else None,
             "target_end": v1[2]}
        w["ag_ms_per_car_s"] = w["ag_ms_per_s"] / w["alive_mean"] if w["alive_mean"] else None
        wins.append(w)
        print("%-5s ag %.1f ms/s (%.0f calls/s)  mod %.2f ms/s  alive %.1f route %.1f" % (
            w["mode"], w["ag_ms_per_s"], w["ag_calls_per_s"], w["mod_ms_per_s"], w["alive_mean"] or 0, w["route_mean"] or 0),
            flush=True)
        json.dump({"windows": wins}, open(a.out, "w"), indent=1)
    api.mode(2)
    s.detach()
    out = {"windows": wins}
    for key in ("ag_ms_per_s", "ag_ms_per_car_s", "mod_ms_per_s", "alive_mean"):
        rat = []
        for i in range(0, len(wins) - 3, 4):
            blk = wins[i:i + 4]
            r = [w[key] for w in blk if w["mode"] == "route" and w[key] is not None]
            st = [w[key] for w in blk if w["mode"] == "stock" and w[key] is not None]
            if r and st and statistics.mean(st):
                rat.append(statistics.mean(r) / statistics.mean(st))
        pr = statistics.mean([w[key] for w in wins if w["mode"] == "route" and w[key] is not None])
        ps = statistics.mean([w[key] for w in wins if w["mode"] == "stock" and w[key] is not None])
        out[key] = {"route": pr, "stock": ps, "ratio": pr / ps if ps else None, "block_ratios": rat}
        print("%s: route %.3f stock %.3f ratio %s | blocks %s" % (key, pr, ps, "%.3f" % (pr / ps) if ps else "-",
              " ".join("%.3f" % x for x in rat)))
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
