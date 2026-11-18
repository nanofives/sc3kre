#!/usr/bin/env python3
r"""hwyspeed_probe.py - measure animated car speed per lane speed (task hwyspeed, 2026-11-18). Read-only Frida.

What moves a car (re/analysis/VEHICLE_SPEED.md):
  STRTSIM 0x1001b900  MoveToPoint update fn (action code 2, table 0x10033158 filled by 0x1001d060):
                      +0x148 = 0; dist = dt (u32, real-time heartbeat) * [veh+0x10c] (0x1001b940); MoveDist 0x1001b680
                      adds the distance actually moved to +0x148 (capped by the gap to the car ahead, 0x1001b6a3).
  veh+0x10c           lane speed of the current path = TrBlkAtt edge e3 * 2.2222e-9 (0x1002066a, 0x1001b110).
  veh+0x0c/+0x10/+0x14 x / y / z position, cell = >> 8.
Hook: onEnter keeps (veh, dt, speed, cell), onLeave reads +0x148. Aggregates per e3 (speed / 2.2222e-9, rounded) and
per (cell, e3). Nothing is written to the game.

  py -3.12 hwyspeed_probe.py measure SECONDS [--json OUT] [--every 10]        SC3_PID = the game, running, unpaused
  py -3.12 hwyspeed_probe.py ab SECONDS [--pcts 100,150,100,150] [--json OUT]  A/B in one game (SC3SIMRUN_HWYSPEED=1)
  py -3.12 hwyspeed_probe.py factor PCT                                         set the factor at run time
  py -3.12 hwyspeed_probe.py cells X0,Z0,X1,Z1 [--json OUT]                   network piece ids live (np_drive job)
A/B also counts position jumps (displacement > 3 steps + 8 units between two updates of one car), car-ahead centre
distances under 16 / 28 units (+0x104), and car pairs on any lane closer than 8 / 16 units (4 scans a second).
Prints "[k/M] ... PASS" every --every seconds.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "netmod"))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402

E3_SCALE = 2.22222e-09   # STRTSIM 0x1002d264 (float 0x3118b5b5)

JS = r"""
var ST = Process.getModuleByName('STRTSIM.DLL').base;
function A(va) { return ST.add(va - 0x10000000); }
var S = {e3: {}, cell: {}, calls: 0, aborted: 0, t0: Date.now(), veh: {}};
var pend = {};
Interceptor.attach(A(0x1001b900), {
  onEnter: function (a) {
    var v = this.context.ecx;
    this.v = v; this.dt = a[0].toUInt32(); this.ab = a[1].toInt32() & 0xff;
    this.sp = v.add(0x10c).readFloat();
    this.x = v.add(0xc).readS32(); this.z = v.add(0x14).readS32();
  },
  onLeave: function () {
    S.calls++;
    if (this.ab) { S.aborted++; return; }
    var moved = this.v.add(0x148).readFloat();
    var e3 = Math.round(this.sp / 2.22222e-09 / 100) * 100;
    var k = '' + e3;
    var r = S.e3[k] || (S.e3[k] = {n: 0, dt: 0, nominal: 0, moved: 0, clamped: 0, veh: 0});
    r.n++; r.dt += this.dt; r.nominal += this.dt * this.sp; r.moved += moved;
    if (moved + 1e-6 < this.dt * this.sp) r.clamped++;
    var vk = this.v.toString() + ':' + k;
    if (!S.veh[vk]) { S.veh[vk] = 1; r.veh++; }
    var ck = (this.x >> 8) + ',' + (this.z >> 8) + ',' + k;
    var c = S.cell[ck] || (S.cell[ck] = [0, 0, 0]);
    c[0]++; c[1] += this.dt; c[2] += moved;
    /* jumps: displacement since this car's previous update against the step it was allowed */
    var px = this.v.add(0xc).readS32(), py = this.v.add(0x10).readS32(), pz = this.v.add(0x14).readS32();
    var key = this.v.toString(), now = Date.now(), lp = LAST[key], step = this.dt * this.sp;
    if (lp && now - lp.t < 200) {
      var dd = Math.sqrt((px - lp.x) * (px - lp.x) + (pz - lp.z) * (pz - lp.z));
      S.steps++;
      if (dd > 3 * Math.max(step, lp.step) + 8) { S.jumps++; if (S.jumpx.length < 20) S.jumpx.push([k, Math.round(dd), Math.round(step), Math.round(lp.step)]); }
      if (dd > S.maxstep) S.maxstep = dd;
    }
    LAST[key] = {x: px, y: py, z: pz, t: now, step: step, e3: e3};
    /* car ahead on the same queue (+0x104, MoveDist 0x1001b691): centre distance */
    var ah = this.v.add(0x104).readPointer();
    if (!ah.isNull()) {
      try {
        var ax = ah.add(0xc).readS32(), az = ah.add(0x14).readS32();
        var d = Math.sqrt((px - ax) * (px - ax) + (pz - az) * (pz - az));
        S.ahead_n++; if (d < 16) S.ahead16++; if (d < 28) S.ahead28++;
      } catch (e) {}
    }
  }
});
var LAST = {};
S.steps = 0; S.jumps = 0; S.jumpx = []; S.maxstep = 0; S.ahead_n = 0; S.ahead16 = 0; S.ahead28 = 0;
S.pair_scans = 0; S.pairs8 = 0; S.pairs16 = 0; S.pairs16_fast = 0;
/* any two cars (any lane, merges included) closer than 8 / 16 units, same height band, 4 scans a second */
setInterval(function () {
  var now = Date.now(), L = [];
  for (var k in LAST) { var p = LAST[k]; if (now - p.t < 150) L.push(p); else if (now - p.t > 5000) delete LAST[k]; }
  S.pair_scans++;
  for (var i = 0; i < L.length; i++) for (var j = i + 1; j < L.length; j++) {
    var a = L[i], b = L[j];
    if (Math.abs(a.y - b.y) > 64) continue;
    var dx = a.x - b.x, dz = a.z - b.z, d2 = dx * dx + dz * dz;
    if (d2 < 256) { S.pairs16++; if (a.e3 > 66000 || b.e3 > 66000) S.pairs16_fast++; if (d2 < 64) S.pairs8++; }
  }
}, 250);
var simrun = Process.findModuleByName('sc3simrun.dll');
var hwsx = simrun ? simrun.findExportByName('sc3simrun_hwyspeed') : null;
var hws = hwsx ? new NativeFunction(hwsx, 'int', ['int'], 'mscdecl') : null;
rpc.exports = {
  snap: function () {
    var o = {e3: S.e3, cell: S.cell, calls: S.calls, aborted: S.aborted, ms: Date.now() - S.t0, nveh: Object.keys(S.veh).length,
             steps: S.steps, jumps: S.jumps, jumpx: S.jumpx, maxstep: S.maxstep, ahead_n: S.ahead_n, ahead16: S.ahead16,
             ahead28: S.ahead28, pair_scans: S.pair_scans, pairs8: S.pairs8, pairs16: S.pairs16, pairs16_fast: S.pairs16_fast};
    return JSON.parse(JSON.stringify(o));
  },
  reset: function () {
    S.e3 = {}; S.cell = {}; S.calls = 0; S.aborted = 0; S.t0 = Date.now(); S.veh = {};
    S.steps = 0; S.jumps = 0; S.jumpx = []; S.maxstep = 0; S.ahead_n = 0; S.ahead16 = 0; S.ahead28 = 0;
    S.pair_scans = 0; S.pairs8 = 0; S.pairs16 = 0; S.pairs16_fast = 0;
  },
  factor: function (pct) { return hws ? hws(pct) : -999; }
};
"""


FACTOR_JS = r"""
var m = Process.findModuleByName('sc3simrun.dll'), x = m ? m.findExportByName('sc3simrun_hwyspeed') : null;
var f = x ? new NativeFunction(x, 'int', ['int'], 'mscdecl') : null;
rpc.exports = {factor: function (pct) { return f ? f(pct) : -999; }};
"""


def summary(snap):
    ms = snap["ms"]
    rows = []
    for k, r in sorted(snap["e3"].items(), key=lambda kv: int(kv[0])):
        if not r["dt"]:
            continue
        # dt units per real second, from this bucket's own vehicles: cannot be split per vehicle here, so report
        # distance per dt unit (= speed actually achieved) against the lane's nominal speed
        rows.append({"e3": int(k), "ticks": r["n"], "veh": r["veh"], "nominal_per_dt": r["nominal"] / r["dt"],
                     "achieved_per_dt": r["moved"] / r["dt"], "achieved_frac": r["moved"] / r["nominal"] if r["nominal"] else 0,
                     "clamped_frac": r["clamped"] / r["n"], "dt_sum": r["dt"]})
    extra = {k: snap.get(k) for k in ("steps", "jumps", "jumpx", "maxstep", "ahead_n", "ahead16", "ahead28",
                                       "pair_scans", "pairs8", "pairs16", "pairs16_fast")}
    return dict({"ms": ms, "calls": snap["calls"], "aborted": snap["aborted"], "nveh": snap["nveh"], "rows": rows}, **extra)


def measure(pid, secs, every, out):
    import frida
    sc3pause.require_running(pid, "hwyspeed_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    t0 = time.time()
    steps = max(1, int(secs // every))
    snap = None
    for k in range(1, steps + 1):
        time.sleep(max(0.0, t0 + k * every - time.time()))
        snap = sc.exports_sync.snap()
        sm = summary(snap)
        top = " ".join("%d:%.0f%%" % (r["e3"], 100 * r["achieved_frac"]) for r in sm["rows"])
        print("[%d/%d] t=%ds calls=%d veh=%d %s PASS" % (k, steps, int(time.time() - t0), sm["calls"], sm["nveh"], top),
              flush=True)
    sc.unload()
    s.detach()
    res = {"summary": summary(snap), "raw": snap}
    print(json.dumps(res["summary"], indent=1), flush=True)
    if out:
        with open(out, "w") as f:
            json.dump(res, f, indent=1, sort_keys=True)
    return res


def line(sm):
    rows = " ".join("%d:%.3f" % (r["e3"], r["achieved_per_dt"] * 1e6 / 256) for r in sm["rows"] if r["ticks"] > 200)
    return ("veh=%d jumps=%d/%d maxstep=%.0f ahead<16=%d ahead<28=%d/%d pairs<8=%d pairs<16=%d (fast %d) scans=%d | cells/s %s"
            % (sm["nveh"], sm["jumps"], sm["steps"], sm["maxstep"], sm["ahead16"], sm["ahead28"], sm["ahead_n"],
               sm["pairs8"], sm["pairs16"], sm["pairs16_fast"], sm["pair_scans"], rows))


def ab(pid, secs, pcts, settle, out):
    import frida
    sc3pause.require_running(pid, "hwyspeed_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    api = sc.exports_sync
    res = []
    for k, pct in enumerate(pcts, 1):
        was = api.factor(pct)
        if was == -999:
            raise SystemExit("sc3simrun_hwyspeed export not found (sc3simrun not loaded?)")
        time.sleep(settle)
        api.reset()
        time.sleep(secs)
        sm = summary(api.snap())
        sm["pct"] = pct
        res.append(sm)
        print("[%d/%d] pct=%d %s PASS" % (k, len(pcts), pct, line(sm)), flush=True)
    api.factor(100)
    sc.unload()
    s.detach()
    if out:
        with open(out, "w") as f:
            json.dump(res, f, indent=1)
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("seconds", type=float)
    m.add_argument("--json")
    m.add_argument("--every", type=float, default=10)
    b = sub.add_parser("ab", help="A/B inside one game: factor pcts in turn (needs SC3SIMRUN_HWYSPEED=1)")
    b.add_argument("seconds", type=float, help="per block")
    b.add_argument("--pcts", default="100,150,100,150")
    b.add_argument("--settle", type=float, default=10)
    b.add_argument("--json")
    f = sub.add_parser("factor", help="set the HWYSPEED factor at run time (sc3simrun export)")
    f.add_argument("pct", type=int)
    c = sub.add_parser("cells")
    c.add_argument("box")
    c.add_argument("--json")
    a = ap.parse_args(argv)
    if a.cmd == "ab":
        return ab(sc3io.game_pid(), a.seconds, [int(v) for v in a.pcts.split(",")], a.settle, a.json)
    if a.cmd == "factor":
        import frida
        sc3pause.require_running(sc3io.game_pid(), "hwyspeed_probe")
        ses = frida.attach(sc3io.game_pid())
        sc = ses.create_script(FACTOR_JS)
        sc.load()
        was = sc.exports_sync.factor(a.pct)
        sc.unload()
        ses.detach()
        if was == -999:
            raise SystemExit("sc3simrun_hwyspeed export not found")
        print("factor %d%% -> %d%%" % (was, a.pct))
        return 0
    if a.cmd == "measure":
        measure(sc3io.game_pid(), a.seconds, a.every, a.json)
        return 0
    import np_drive
    x0, z0, x1, z1 = [int(v) for v in a.box.split(",")]
    res = np_drive.frida_job({"kind": "cells", "x0": x0, "z0": z0, "x1": x1, "z1": z1}, timeout=120)
    cells = [{"x": r["x"], "z": r["z"], "piece": r.get("piece"), "state": r.get("state")} for r in res.get("cells", [])
             if "piece" in r]
    print("network cells: %d" % len(cells))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(cells, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
