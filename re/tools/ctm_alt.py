#!/usr/bin/env python3
r"""ctm_alt.py - in-game paired cost of the sc3cartrips capture (verify/cartrips2 PRE, the ld_alt.py method).

One running game alternates the capture OFF (SimTransit 0x100072f8 back to the shipped `call 0x10009eed`) and ON (our
pop stub) through sc3cartrips' export `sc3cartrips_set(int)`, in ABBA blocks (off on on off, ...). Between games the
routing cost per trip lands in fast or slow states at random (LANE_DENSITY 4, verify/lanedensity RESULTS (c)), so only
windows of the same game are compared.

Cost source: sc3cartrips `time_route=1` (TSC cycles inside route_trip FUN_100070d0 and its calls, every thread),
read through `sc3cartrips_stats`. With --perf the sc3perf TRAFFIC_MT counters are read too (worker trips and the wall
time of their chunks, located as ld_alt.py locates them), a second witness on a traffic_mt game.

  set SC3_PID=<pid>
  py -3.12 ctm_alt.py --warmup 60 --window 30 --settle 2 --blocks 10 --out alt.json [--perf]
"""
import argparse
import json
import statistics
import sys
import time
import os

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sc3io  # noqa: E402

JS = r"""
var M = Process.getModuleByName('sc3cartrips.dll');
var fset = new NativeFunction(M.getExportByName('sc3cartrips_set'), 'int', ['int']);
var fstats = new NativeFunction(M.getExportByName('sc3cartrips_stats'), 'int', ['pointer', 'int']);
var buf = Memory.alloc(64);
var PERF = null;
function findPerf() {
  var P = Process.getModuleByName('sc3perf.dll');
  var fmt = null, site = null;
  P.enumerateRanges('r--').forEach(function (r) {
    if (fmt !== null) return;
    Memory.scanSync(r.base, r.size, '54 52 41 46 46 49 43 5f 4d 54 3e 20 25 6c 64 20 62 61 74 63 68 65 73').forEach(function (m) { if (fmt === null) fmt = m.address; });
  });
  if (fmt === null) throw new Error('sc3perf format string not found');
  var pat = '68 ' + [0, 8, 16, 24].map(function (s) { var b = (fmt.toUInt32() >>> s) & 0xff; return ('0' + b.toString(16)).slice(-2); }).join(' ');
  P.enumerateRanges('r-x').forEach(function (r) {
    if (site !== null) return;
    Memory.scanSync(r.base, r.size, pat).forEach(function (m) { if (site === null) site = m.address; });
  });
  if (site === null) throw new Error('sc3perf log call site not found');
  function op(at, bytes) { for (var i = 0; i < bytes.length; i++) if (at.add(i).readU8() !== bytes[i]) return null; return at.add(bytes.length).readPointer(); }
  var ab = op(site.sub(6), [0xa1]), at = op(site.sub(0x28), [0xa1]), am = op(site.sub(0x1a), [0xf2, 0x0f, 0x10, 0x05]);
  if (ab === null || at === null || am === null) throw new Error('sc3perf argument setup differs from the 2026-10-13 build');
  PERF = { batches: ab, trips: at, ms: am };
  return true;
}
rpc.exports = {
  perf: function () { return findPerf(); },
  read: function () {
    var n = fstats(buf, 16), v = [];
    for (var i = 0; i < n; i++) v.push(buf.add(4 * i).readU32());
    var p = PERF ? [PERF.batches.readS32(), PERF.trips.readS32(), PERF.ms.readDouble()] : null;
    return { v: v, perf: p, t: Date.now() };
  },
  set: function (on) { return fset(on); }
};
"""

# sc3cartrips_stats indices
PATHS, NODES, VP, VPFLAG, COMMITS, DROPS, DRAINED, RT_CALLS, CYC_LO, CYC_HI, CAP_ON, THREADS = range(12)


def cyc(v):
    return v[CYC_HI] * 2 ** 32 + v[CYC_LO]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--warmup", type=float, default=60)
    ap.add_argument("--window", type=float, default=30)
    ap.add_argument("--settle", type=float, default=2)
    ap.add_argument("--blocks", type=int, default=10, help="ABBA blocks (4 windows each)")
    ap.add_argument("--perf", action="store_true", help="also read sc3perf TRAFFIC_MT counters")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()
    api = sc.exports_sync
    if a.perf:
        api.perf()
    r = api.read()
    if r["v"][RT_CALLS] == 0:
        print("warning: rt_calls 0 so far (time_route=1 in cartrips.ini? game routing yet?)")
    if api.set(0) < 0:
        sys.exit("sc3cartrips_set refused (capture not armed)")
    print("warm-up %.0f s with capture off" % a.warmup, flush=True)
    time.sleep(a.warmup)
    order = []
    for _ in range(a.blocks):
        order += [0, 1, 1, 0]
    wins = []
    for st in order:
        api.set(st)
        time.sleep(a.settle)
        r0 = api.read()
        time.sleep(a.window)
        r1 = api.read()
        v0, v1 = r0["v"], r1["v"]
        w = {"state": "on" if st else "off", "t0": r0["t"], "t1": r1["t"], "calls": v1[RT_CALLS] - v0[RT_CALLS],
             "cycles": cyc(v1) - cyc(v0), "paths": v1[PATHS] - v0[PATHS], "nodes": v1[NODES] - v0[NODES],
             "vp": v1[VP] - v0[VP], "drops": v1[DROPS] - v0[DROPS], "cap": v1[CAP_ON]}
        w["cyc_per_call"] = w["cycles"] / w["calls"] if w["calls"] else None
        if r0["perf"] and r1["perf"]:
            w["perf_trips"] = r1["perf"][1] - r0["perf"][1]
            w["perf_ms"] = r1["perf"][2] - r0["perf"][2]
            w["perf_ms_per_trip"] = w["perf_ms"] / w["perf_trips"] if w["perf_trips"] else None
        wins.append(w)
        print("%-3s calls %7d  cyc/call %10s  paths %7d  nodes %8d%s" % (
            w["state"], w["calls"], "%.0f" % w["cyc_per_call"] if w["cyc_per_call"] else "-", w["paths"], w["nodes"],
            "  perf ms/trip %.5f" % w["perf_ms_per_trip"] if w.get("perf_ms_per_trip") else ""), flush=True)
        json.dump({"windows": wins}, open(a.out, "w"), indent=1)
    api.set(1)
    s.detach()
    out = {"windows": wins}

    def pooled(ws, num, den):
        ws = [w for w in ws if w.get(den)]
        return sum(w[num] for w in ws) / sum(w[den] for w in ws) if ws else None

    for num, den, name in (("cycles", "calls", "time_route"), ("perf_ms", "perf_trips", "sc3perf")):
        on = [w for w in wins if w["state"] == "on"]
        off = [w for w in wins if w["state"] == "off"]
        pon, poff = pooled(on, num, den), pooled(off, num, den)
        if not pon or not poff:
            continue
        rat = []
        for i in range(0, len(wins) - 3, 4):
            blk = wins[i:i + 4]
            bo = pooled([w for w in blk if w["state"] == "on"], num, den)
            bf = pooled([w for w in blk if w["state"] == "off"], num, den)
            if bo and bf:
                rat.append(bo / bf)
        print("%s pooled: off %.4g  on %.4g  on/off %.4f (%+.2f%%)" % (name, poff, pon, pon / poff, 100 * (pon / poff - 1)))
        if rat:
            print("  per block on/off: %s | median %.4f mean %.4f sd %.4f" % (
                " ".join("%.3f" % x for x in rat), statistics.median(rat), statistics.mean(rat),
                statistics.stdev(rat) if len(rat) > 1 else 0))
        out[name] = {"pooled_off": poff, "pooled_on": pon, "on_over_off": pon / poff, "block_ratios": rat}
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
