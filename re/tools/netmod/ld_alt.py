#!/usr/bin/env python3
r"""ld_alt.py - in-game paired perf measurement of the sc3netmod LANEDENSITY block (verify/lanedensity PRE addendum 7).

One running game alternates the block between OFF (both patch sites back to SimTransit's shipped bytes) and ON (the
detours), through sc3netmod's export `sc3netmod_ld_set(int)`, in ABBA blocks (off on on off, ...). At the start and
end of each window it reads sc3perf's TRAFFIC_MT counters (trips routed by the workers and the wall time of their
batches), so every window gets its own ms per trip, and adjacent windows share the city state.

sc3perf counters are found through its own log call (the `push "TRAFFIC_MT> %ld batches..."` site): the loads
before it (fixed offsets, opcodes checked) give the addresses of the batch / trip counters and of the routing-ms double;
a different sc3perf build is refused, not misread. Read only, apart from the toggle calls.

  set SC3_PID=<pid>
  py -3.12 ld_alt.py --warmup 60 --window 30 --settle 2 --blocks 10 --out alt.json
Output: windows [{state, t0, t1, trips, ms, batches, ms_per_trip}], plus the summary printed at the end.
"""
import argparse
import json
import os
import statistics
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var P = Process.getModuleByName('sc3perf.dll');
var N = Process.getModuleByName('sc3netmod.dll');
var setp = N.findExportByName('%EXPORT%');   // task hwtrips: --export
if (setp === null) throw new Error('%EXPORT% not exported (build without ALT)');
var ldset = new NativeFunction(setp, 'int', ['int'], {exceptions: 'propagate'});
// find the log call: push imm32 (the format string) followed by call
var fmt = null, site = null;
P.enumerateRanges('r--').forEach(function (r) {
  if (fmt !== null) return;
  Memory.scanSync(r.base, r.size, '54 52 41 46 46 49 43 5f 4d 54 3e 20 25 6c 64 20 62 61 74 63 68 65 73').forEach(function (m) { if (fmt === null) fmt = m.address; });
});
if (fmt === null) throw new Error('format string not found');
var pat = '68 ' + [0, 8, 16, 24].map(function (s) { var b = (fmt.toUInt32() >>> s) & 0xff; return ('0' + b.toString(16)).slice(-2); }).join(' ');
P.enumerateRanges('r-x').forEach(function (r) {
  if (site !== null) return;
  Memory.scanSync(r.base, r.size, pat).forEach(function (m) { if (site === null) site = m.address; });
});
if (site === null) throw new Error('log call site not found');
// argument loads before the call (2026-10-13 build, 0x100091af): A1 imm32 = mov eax,[batches] at site-6,
// mov eax,[trips] at site-0x28, F2 0F 10 05 imm32 = movsd xmm0,[routing ms] at site-0x1a. Checked, never assumed.
function op(at, bytes) { for (var i = 0; i < bytes.length; i++) if (at.add(i).readU8() !== bytes[i]) return null; return at.add(bytes.length).readPointer(); }
var ab = op(site.sub(6), [0xa1]), at = op(site.sub(0x28), [0xa1]), am = op(site.sub(0x1a), [0xf2, 0x0f, 0x10, 0x05]);
if (ab === null || at === null || am === null) throw new Error('argument setup differs from the 2026-10-13 sc3perf build');
send({ site: site.toString(), batches: ab.toString(), trips: at.toString(), ms: am.toString() });
var A = {};
recv('addrs', function (m) { A = { batches: ptr(m.batches), trips: ptr(m.trips), ms: ptr(m.ms) }; });
rpc.exports = {
  read: function () { return [A.batches.readS32(), A.trips.readS32(), A.ms.readDouble(), Date.now()]; },
  set: function (on) { return ldset(on); }
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--warmup", type=float, default=60)
    ap.add_argument("--window", type=float, default=30)
    ap.add_argument("--settle", type=float, default=2)
    ap.add_argument("--blocks", type=int, default=10, help="ABBA blocks (4 windows each)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--export", default="sc3netmod_ld_set", help="toggle export (task hwtrips: sc3netmod_rf_set)")
    a = ap.parse_args()
    sc3pause.require_running(sc3io.game_pid(), "ld_alt")
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS.replace("%EXPORT%", a.export))
    got = []
    sc.on("message", lambda m, d: got.append(m))
    sc.load()
    while not got:
        time.sleep(0.05)
    m = got[0]
    if m.get("type") != "send":
        sys.exit("script error: %s" % m)
    pl = m["payload"]
    batches, trips, ms = pl["batches"], pl["trips"], pl["ms"]
    print("log site", pl["site"], "batches @", batches, "trips @", trips, "routing ms @", ms)
    sc.post({"type": "addrs", "batches": batches, "trips": trips, "ms": ms})
    time.sleep(0.2)
    api = sc.exports_sync
    b0, t0, m0, _ = api.read()
    print("now: %d batches, %d trips, %.0f ms routing; warm-up %.0f s" % (b0, t0, m0, a.warmup))
    if api.set(0) < 0:
        sys.exit("sc3netmod_ld_set refused (block not installed / not variants mode)")
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
        w = {"state": "on" if st else "off", "t0": r0[3], "t1": r1[3], "batches": r1[0] - r0[0],
             "trips": r1[1] - r0[1], "ms": r1[2] - r0[2]}
        w["ms_per_trip"] = w["ms"] / w["trips"] if w["trips"] else None
        wins.append(w)
        print("%-3s trips %7d  ms %8.0f  ms/trip %s" % (w["state"], w["trips"], w["ms"],
              "%.5f" % w["ms_per_trip"] if w["ms_per_trip"] else "-"))
        json.dump({"windows": wins}, open(a.out, "w"), indent=1)
    api.set(1)
    s.detach()
    on = [w for w in wins if w["state"] == "on" and w["trips"]]
    off = [w for w in wins if w["state"] == "off" and w["trips"]]
    pon = sum(w["ms"] for w in on) / sum(w["trips"] for w in on)
    poff = sum(w["ms"] for w in off) / sum(w["trips"] for w in off)
    print("pooled: off %.5f  on %.5f  on/off %.4f (%+.1f%%)" % (poff, pon, pon / poff, 100 * (pon / poff - 1)))
    rat = []
    for i in range(0, len(wins) - 3, 4):            # within each ABBA block: (on1+on2)/(off1+off2) by pooled ms/trip
        blk = wins[i:i + 4]
        bo = [w for w in blk if w["state"] == "on" and w["trips"]]
        bf = [w for w in blk if w["state"] == "off" and w["trips"]]
        if bo and bf:
            rat.append((sum(w["ms"] for w in bo) / sum(w["trips"] for w in bo)) /
                       (sum(w["ms"] for w in bf) / sum(w["trips"] for w in bf)))
    if rat:
        print("per block on/off: %s | median %.4f mean %.4f" % (" ".join("%.3f" % r for r in rat),
              statistics.median(rat), statistics.mean(rat)))
    json.dump({"windows": wins, "pooled_off": poff, "pooled_on": pon, "on_over_off": pon / poff, "block_ratios": rat},
              open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
