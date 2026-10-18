#!/usr/bin/env python3
r"""ctm_m2report.py - one M2 arm (verify/cartrips2 PRE addenda 1-2): in-game solver counters, the C-vs-Python match,
the offline route analysis (graphs from the save, or from the DLL's dump with --graphs-from-dump), solve times.

  py -3.12 ctm_m2report.py <inst> <arm> [--city <save>] [--graphs-from-dump] [--cells x0,z0,x1,z1] --out <json>
--cells: also report the routes that enter that box (M2R: the roundabout block).
"""
import argparse
import collections
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctm_lanes as L  # noqa: E402
import ctm_read  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inst")
    ap.add_argument("arm")
    ap.add_argument("--city")
    ap.add_argument("--graphs-from-dump", action="store_true")
    ap.add_argument("--cells")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    f = lambda leaf: os.path.join(a.inst, "%s_%s" % (a.arm, leaf))
    out = {"arm": a.arm}
    log = ctm_read.read_log(f("sc3cartrips.log"))
    m2 = [r for r in log if r["kind"] == "M2"]
    out["ingame"] = {k: v for k, v in m2[-1].items() if k not in ("s", "kind")} if m2 else None
    g = out["ingame"]
    if g and g["routes"]:
        R = g["routes"]
        out["ingame_pct"] = {"exact_w0": 100.0 * g["exact_w0"] / R, "solved_w1": 100.0 * g["solved_w1"] / R,
                             "full_w1": 100.0 * g["full_w1"] / R, "cov90_w1": 100.0 * g["cov90_w1"] / R,
                             "budget_skipped": 100.0 * g["budget_skipped"] / (R + g["budget_skipped"]),
                             "mean_us": g["solve_us_total"] / R}
    out["match"] = L.match(f("cartrips_graphs.bin"), f("cartrips_routes.bin"))["counts"]
    rs = L.read_routes(f("cartrips_routes.bin"))
    us = sorted(r["us"] for r in rs)
    if us:
        out["solve_us"] = {"n": len(us), "median": us[len(us) // 2], "p90": us[int(len(us) * 0.9)],
                           "p99": us[int(len(us) * 0.99)], "max": us[-1], "mean": statistics.mean(us)}
    G = L.DumpGraphs(f("cartrips_graphs.bin")) if a.graphs_from_dump else L.SaveGraphs(a.city)
    trips = ctm_read.read_trips(f("cartrips_trips.bin"))
    an = L.analyse(G, trips, f("lanes.json"))
    out["offline"] = {k: an[k] for k in ("counts", "pct", "fail_reasons_w1", "fail_places", "fail_pieces", "solve_ms")
                      if k in an}
    if a.cells:
        x0, z0, x1, z1 = [int(v) for v in a.cells.split(",")]
        box = lambda c: x0 <= c[0] <= x1 and z0 <= c[1] <= z1
        st = collections.Counter()
        for r in rs:
            if any(box(c) for c in r["cells"]):
                st["routes"] += 1
                st["w1_ok"] += r["w1"]["ok"]
                st["w1_full"] += r["w1"]["ok"] and not r["w1"]["skipped"]
                st["w0_ok"] += r["w0"]["ok"]
                st["w1_path_in_box"] += any(box(p[:2]) for p in r["w1"]["path"])
        out["box"] = dict(st)
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "offline"}, indent=1))
    print(json.dumps({k: out["offline"].get(k) for k in ("pct", "fail_reasons_w1")}, indent=1))


if __name__ == "__main__":
    main()
