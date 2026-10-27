#!/usr/bin/env python3
r"""avslope_trips.py - read-only: which way do trips run over avenue halves on slopes? (task avslope, 2026-10-26)

Frida on SC3_PID, SimTransit.dll (Ghidra VAs, the hooks of avxroad_trips.py / hwtraffic_probe.py):
  FUN_100070d0  route one trip (thiscall); return low byte 1 = arrived [CONFIRMED @ 0x100070d0].
  FUN_10006edd  the density deposit, once per node while an ARRIVED trip's path is popped, same thread; stack args
                (x, z, amount, mask) [CONFIRMED @ 0x10006edd].
Sites (JSON [[x, z, dx, dz, kind], ...]): a one-way half cell and the world step (dx, dz) its lanes run along; kind is
a label ("slope", "flat"). A trip steps ALONG a site when its deposit sequence has the site cell next to (x + dx, z + dz)
(counted "with") or next to (x - dx, z - dz) ("against"). The deposit order is the pop order of the path, which this
probe does not assume: the flat one-way halves (21700) calibrate it, the slope halves must agree with them.

  py -3.12 avslope_trips.py sites CITY.sc3 OUT.json      # sites from a save written with the mod (netvariant section)
  py -3.12 avslope_trips.py run --sites OUT.json --secs 300 --out run.json
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

JS = r"""
var TR = Process.getModuleByName('SimTransit.dll').base;
function A(va) { return TR.add(va - 0x10000000); }
var SITES = %SITES%, at = {};
SITES.forEach(function (s, i) { at[s[0] + ',' + s[1]] = i; });
var cur = {}, trips = 0, arrived = 0, w = {}, ag = {};
function step(c0, c1) {
  var i = at[c0]; if (i === undefined) return;
  var s = SITES[i], q = c1.split(','), dx = (+q[0]) - s[0], dz = (+q[1]) - s[1];
  if (dx === s[2] && dz === s[3]) w[i] = (w[i] || 0) + 1;
  else if (dx === -s[2] && dz === -s[3]) ag[i] = (ag[i] || 0) + 1;
}
Interceptor.attach(A(0x100070d0), {
  onEnter: function () { cur[this.threadId] = []; },
  onLeave: function (ret) {
    var p = cur[this.threadId]; delete cur[this.threadId];
    trips++;
    if ((ret.toInt32() & 0xff) === 0 || !p) return;
    arrived++;
    for (var i = 1; i < p.length; i++) step(p[i - 1], p[i]);
  }
});
Interceptor.attach(A(0x10006edd), {
  onEnter: function (a) {
    var p = cur[this.threadId]; if (!p) return;
    var c = a[0].toInt32() + ',' + a[1].toInt32();
    if (!p.length || p[p.length - 1] !== c) p.push(c);
  }
});
rpc.exports = { stats: function () { return {trips: trips, arrived: arrived, with_: w, against: ag}; } };
"""

D = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}              # N E S W


def cmd_sites(city, out):
    """one-way half cells of a save made with the mod: 21700 (11204 state s runs toward (s + 3) % 4) and the AVL slope
    ids (avenue_lanes avlc: lanes toward side at state 0, (side + s) % 4 at state s)"""
    from netmod import hwave_twin
    g, tiler_mod, netrules, opts, c = hwave_twin.load(city)
    man = json.load(open(os.path.join(HERE, "examples", "avenue_lanes", "manifest.json"), encoding="utf-8"))
    side = {int(p[1]): int(p[3]) for p in (ln.split() for ln in man["avenue_lines"]) if p[0] == "avlc" and
            int(p[2]) in (31, 32, 11201, 11202)}
    sites = []
    lay = c.layers["surface"]
    for (x, z), pc in sorted(lay.items()):
        if pc.id == 21700:
            d = (pc.state + 3) % 4
            sites.append([x, z, D[d][0], D[d][1], "flat"])
        elif pc.id in side:
            d = (side[pc.id] + pc.state) % 4
            sites.append([x, z, D[d][0], D[d][1], "slope"])
    json.dump(sites, open(out, "w"))
    print("%d sites: %d slope, %d flat -> %s" % (len(sites), sum(s[4] == "slope" for s in sites),
                                                 sum(s[4] == "flat" for s in sites), out))


def cmd_run(a):
    import frida
    import sc3io
    import sc3pause
    sites = json.load(open(a.sites))
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "avslope_trips")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("%SITES%", json.dumps([x[:4] for x in sites])))
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    t0 = time.time()
    n = 0

    def summary(st):
        out = {}
        for kind in ("flat", "slope"):
            wi = sum(st["with_"].get(str(i), 0) for i, x in enumerate(sites) if x[4] == kind)
            ag = sum(st["against"].get(str(i), 0) for i, x in enumerate(sites) if x[4] == kind)
            out[kind] = (wi, ag)
        return out
    while time.time() - t0 < a.secs:
        time.sleep(min(30, a.secs - (time.time() - t0)))
        st = sc.exports_sync.stats()
        n += 1
        sm = summary(st)
        print("[%d] %.0f s: trips %d arrived %d | flat halves: with %d against %d | slope halves: with %d against %d" % (
            n, time.time() - t0, st["trips"], st["arrived"], sm["flat"][0], sm["flat"][1], sm["slope"][0],
            sm["slope"][1]), flush=True)
    st = sc.exports_sync.stats()
    s.detach()
    st["summary"] = summary(st)
    st["sites"] = sites
    st["secs"] = time.time() - t0
    json.dump(st, open(a.out, "w"), indent=1)
    print("wrote %s" % a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("sites")
    s.add_argument("city")
    s.add_argument("out")
    r = sp.add_parser("run")
    r.add_argument("--sites", required=True)
    r.add_argument("--secs", type=float, default=300)
    r.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "sites":
        cmd_sites(a.city, a.out)
    else:
        cmd_run(a)


if __name__ == "__main__":
    main()
