#!/usr/bin/env python3
r"""avflow_report.py - pool an avflow_probe.py run per arm (task avflow, 2026-10-24).

Settle months and the partial first month are dropped. Per arm: months, trips routed / month, failed %, share of
arrived trips that used an avenue / boulevard cell, avenue / boulevard share of path road nodes, nodes per trip,
monthly density mean per group (av, bv, side, adj, rest) and cells at or above TrafficAnnoyanceLevel. Then the range
of the per-window means (every window = mpw - settle months), so overlap between arms is visible.

  py -3.12 avflow_report.py run.json [--md]
"""
import argparse
import json
from collections import defaultdict


def window_rows(d):
    mpw = d["mpw"]
    wins = defaultdict(list)
    for m in d["months"]:
        if m.get("partial") or m.get("settle") or m["arm"] == "pre":
            continue
        wins[(m["idx"] - 1) // mpw].append(m)
    return [ms for _, ms in sorted(wins.items())]


def metrics(ms):
    t = lambda f: sum(f(m) for m in ms)
    arr = t(lambda m: m["probe"]["arrived"])
    road = t(lambda m: m["probe"]["nodes_road"])
    r = {
        "months": len(ms),
        "routed_pm": t(lambda m: m["routed"]) / len(ms),
        "failed_pct": 100.0 * t(lambda m: m["failed"]) / max(1, t(lambda m: m["routed"])),
        "use_pct": 100.0 * t(lambda m: m["probe"]["arr_any"]) / max(1, arr),
        "avnode_pct": 100.0 * t(lambda m: m["probe"]["nodes_av"] + m["probe"]["nodes_bv"]) / max(1, road),
        "nodes_trip": t(lambda m: m["probe"]["nodes"]) / max(1, arr),
        "avg": t(lambda m: m["avg"]) / len(ms),
        "use_bv_pct": 100.0 * t(lambda m: m["probe"]["arr_bv"]) / max(1, arr),
        "bvnode_pct": 100.0 * t(lambda m: m["probe"]["nodes_bv"]) / max(1, road),
    }
    for g in ("av", "bv", "side", "adj", "rest"):
        n = t(lambda m: m["dens"][g]["n"])
        r["d_" + g] = t(lambda m: m["dens"][g]["sum"]) / n if n else None
        r["hi_" + g] = t(lambda m: m["dens"][g]["hi"]) / len(ms)
    return r


COLS = [("months", "%d"), ("routed_pm", "%.0f"), ("failed_pct", "%.2f"), ("use_pct", "%.1f"), ("avnode_pct", "%.1f"),
        ("nodes_trip", "%.1f"), ("avg", "%.1f"), ("d_av", "%.1f"), ("d_side", "%.1f"), ("d_adj", "%.1f"), ("d_rest", "%.1f"),
        ("hi_av", "%.1f"), ("hi_side", "%.1f")]
COLS_BV = [("use_bv_pct", "%.2f"), ("bvnode_pct", "%.2f"), ("d_bv", "%.1f"), ("hi_bv", "%.2f")]


def fmt(f, v):
    return "-" if v is None else f % v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    d = json.load(open(a.run))
    wins = window_rows(d)
    by = defaultdict(list)
    for w in wins:
        by[w[0]["arm"]].append(w)
    arms = [x for x in ("off", "F", "FD", "D") if x in by]
    sep = " | " if a.md else "  "
    print(sep.join(["arm"] + [c for c, _ in COLS]))
    if a.md:
        print("|".join(["---"] * (len(COLS) + 1)))
    for arm in arms:
        r = metrics([m for w in by[arm] for m in w])
        print(sep.join([arm] + [fmt(f, r[c]) for c, f in COLS]))
    if any(m["dens"]["bv"]["n"] for w in wins for m in w):
        COLS.extend(COLS_BV)
        print()
        print(sep.join(["arm"] + [c for c, _ in COLS_BV]))
        for arm in arms:
            r = metrics([m for w in by[arm] for m in w])
            print(sep.join([arm] + [fmt(f, r[c]) for c, f in COLS_BV]))
    print()
    print("per-window range (min..max of window means):")
    for arm in arms:
        ws = [metrics(w) for w in by[arm]]
        print("  %-3s %d windows: " % (arm, len(ws)) + ", ".join(
            "%s %s..%s" % (c, fmt(f, min(w[c] for w in ws)), fmt(f, max(w[c] for w in ws)))
            for c, f in COLS[1:] if ws[0][c] is not None))


if __name__ == "__main__":
    main()
