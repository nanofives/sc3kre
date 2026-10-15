#!/usr/bin/env python3
r"""ld_perf.py - read-only: ms per trip and validity of lanedensity perf arms (verify/lanedensity PRE addenda 6, 7).

Per instance folder inst_ld_<arm>: the last `TRAFFIC_MT> N batches, T trips, R ms routing ... F faults` line of
sc3perf.log (ms per trip = R / T), the SC3U census of others.txt (written by the run driver: count before launch, then
one count every 10 s; valid = 0 before and 1 = the arm's own game at every sample), the last lanedensity counters line
of sc3netmod.log, and the rbt line if any.

  py -3.12 ld_perf.py <harness dir> Q_off1 Q_on1 ... [--json out.json]
Bound (PRE): every *_on arm <= max(*_off) or <= 1.05 x mean(*_off), over the valid arms.
"""
import argparse
import json
import os
import re
import statistics

MT = re.compile(r"TRAFFIC_MT> (\d+) batches, (\d+) trips, (\d+) ms routing.*?(\d+) faults")
LD = re.compile(r"lanedensity: (evals=.*)")
RBT = re.compile(r"(\d+ qualify, \d+ converted.*)")


def arm(hdir, name):
    d = os.path.join(hdir, "inst_ld_" + name)
    r = {"arm": name}
    m = None
    with open(os.path.join(d, "sc3perf.log"), errors="replace") as f:
        for line in f:
            x = MT.search(line)
            if x:
                m = x
    if m:
        b, t, ms, fa = (int(v) for v in m.groups())
        r.update(batches=b, trips=t, routing_ms=ms, faults=fa, ms_per_trip=ms / t if t else None)
    cen = open(os.path.join(d, "others.txt")).read().splitlines()
    before = int(re.search(r"before: (\d+)", cen[0]).group(1))
    samples = [int(s.split()[1]) for s in cen[1:] if s.strip()]
    r.update(census_before=before, census_samples=len(samples), census_max=max(samples) if samples else None)
    p = os.path.join(d, "sc3netmod.log")
    if os.path.exists(p):
        ld = rb = None
        for line in open(p, errors="replace"):
            x = LD.search(line)
            if x:
                ld = x.group(1)
            y = RBT.search(line)
            if y and "rbt" in line.lower():
                rb = y.group(1)
        r.update(lanedensity=ld, rbt=rb)
    r["valid"] = bool(m and before == 0 and samples and max(samples) == 1 and min(samples) == 1 and r["trips"] >= 500000)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hdir")
    ap.add_argument("arms", nargs="+")
    ap.add_argument("--json")
    ap.add_argument("--min-trips", type=int, default=500000)
    a = ap.parse_args()
    rows = [arm(a.hdir, n) for n in a.arms]
    for r in rows:
        if r.get("trips") is not None and r["trips"] < a.min_trips:
            r["valid"] = False
        print("%-10s trips=%-9s routing=%-7s ms/trip=%-9s faults=%s census before=%s max=%s n=%s valid=%s" % (
            r["arm"], r.get("trips"), r.get("routing_ms"),
            "%.5f" % r["ms_per_trip"] if r.get("ms_per_trip") else None, r.get("faults"),
            r["census_before"], r["census_max"], r["census_samples"], r["valid"]))
        if r.get("lanedensity"):
            print("           " + r["lanedensity"][:150])
        if r.get("rbt"):
            print("           rbt: " + r["rbt"])
    off = [r["ms_per_trip"] for r in rows if r["valid"] and "_off" in r["arm"]]
    on = [r for r in rows if r["valid"] and "_on" in r["arm"]]
    out = {"arms": rows}
    if off and on:
        mo, mx = statistics.mean(off), max(off)
        verdict = all(r["ms_per_trip"] <= mx or r["ms_per_trip"] <= 1.05 * mo for r in on)
        ratio = statistics.mean(r["ms_per_trip"] for r in on) / mo
        print("off: mean %.5f max %.5f spread %.1f%% | on: %s | mean(on)/mean(off) = %.4f (%+.1f%%) | bound %s" % (
            mo, mx, 100 * (mx - min(off)) / min(off), ", ".join("%.5f" % r["ms_per_trip"] for r in on),
            ratio, 100 * (ratio - 1), "MET" if verdict else "NOT MET"))
        out.update(off_mean=mo, off_max=mx, on_over_off=ratio, bound_met=verdict)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
