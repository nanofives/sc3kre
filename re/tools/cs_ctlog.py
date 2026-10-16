#!/usr/bin/env python3
r"""cs_ctlog.py - sc3cartrips CARS> counters per phase of a carscroll arm (cartrips.ini log_s=1).

  py -3.12 cs_ctlog.py <arm.jsonl> <arm_sc3cartrips.log> [--drop 2] [--json out.json]

Each CARS> line carries epoch=<ms> and cumulative counters; consecutive lines give per-interval deltas, assigned to the
phase whose [start, end) contains the interval's end. Gauges (alive, target, route_cars, queued_routes) are averaged.
Per (kind, animate) the deltas are pooled into per-second rates. Phases and the animate state come from the jsonl
marks, as cs_summary.py.
"""
import argparse
import collections
import json
import re

GAUGES = ("alive", "target", "route_cars", "queued_routes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("log")
    ap.add_argument("--drop", type=float, default=2)
    ap.add_argument("--json")
    a = ap.parse_args()
    phases, anim, cur = [], 1, None
    for line in open(a.jsonl):
        r = json.loads(line)
        if r.get("mark") == "animate":
            anim = 1 if r["on"] else 0
        elif r.get("mark") == "start":
            cur = {"tok": r["phase"], "anim": anim, "t0": r["t"], "t1": None}
            phases.append(cur)
        elif r.get("mark") == "end" and cur:
            cur["t1"] = r["t"]
            cur = None
    recs = []
    for line in open(a.log, errors="replace"):
        if "CARS>" not in line:
            continue
        kv = dict(re.findall(r"(\w+)=(-?\d+)", line.split("CARS>", 1)[1]))
        recs.append({k: int(v) for k, v in kv.items()})
    pool = collections.defaultdict(lambda: collections.defaultdict(float))
    for prev, r in zip(recs, recs[1:]):
        t = r["epoch"] / 1000.0
        dt = (r["epoch"] - prev["epoch"]) / 1000.0
        if dt <= 0:
            continue
        ph = next((p for p in phases if p["t1"] and p["t0"] + a.drop <= t < p["t1"]), None)
        if not ph:
            continue
        key = (ph["tok"].split(":")[0].rstrip("*"), ph["anim"])
        P = pool[key]
        P["secs"] += dt
        P["n"] += 1
        for k, v in r.items():
            if k == "epoch":
                continue
            if k in GAUGES:
                P[k] += v
            elif k in prev:
                P["d_" + k] += v - prev[k]
    out = {}
    cols = ["route_cars", "queued_routes", "target", "d_spawn_try", "d_spawn_ok", "d_placefail", "d_outrect", "d_noedge",
            "d_noocc", "d_end_arrived", "d_end_other", "d_end_other_edge", "d_end_lost", "d_routes_in", "d_routes_old",
            "d_spawn_fault"]
    print("kind\tanim\tsecs\t" + "\t".join(c.replace("d_", "") + ("/s" if c.startswith("d_") else "") for c in cols))
    for (k, an), P in sorted(pool.items()):
        row = {}
        for c in cols:
            row[c] = P[c] / P["n"] if c in GAUGES else P[c] / P["secs"]
        row["secs"] = P["secs"]
        out["%s/%d" % (k, an)] = row
        print("%s\t%d\t%.0f\t" % (k, an, P["secs"]) + "\t".join("%.2f" % row[c] for c in cols))
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
