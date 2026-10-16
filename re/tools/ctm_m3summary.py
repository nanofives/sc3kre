#!/usr/bin/env python3
r"""ctm_m3summary.py - one cartrips3 (M3) arm per phase, from the run's phase marks and sc3cartrips' CARS> lines
(verify/cartrips3/PRE.md predictions 1-5).

  py -3.12 ctm_m3summary.py <inst> <arm> [--json out]
CARS> lines are cumulative counters stamped with epoch ms; a line counts toward a phase when its stamp lies inside
the phase (first 3 s dropped). Per phase: counter deltas, per-sample alive / target / route cars.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctm_read  # noqa: E402

CUM = ("spawn_try", "spawn_ok", "placefail", "retry_ok", "end_arrived", "end_lost", "end_other", "end_other_edge",
       "decisions", "followed", "cross_followed", "lost_events", "need_route", "need_true", "steps_covered",
       "steps_total", "zone_excluded", "carried", "dropped", "spawn_fault", "decisions_after_end", "routes_in",
       "paused_ticks", "cyc")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inst")
    ap.add_argument("arm")
    ap.add_argument("--json")
    a = ap.parse_args()
    recs = [json.loads(l) for l in open(os.path.join(a.inst, a.arm + ".jsonl"), encoding="utf-8") if l.strip()]
    marks, cur = [], None
    for r in recs:
        if r.get("mark") == "start":
            cur = [r["phase"], r["t"]]
        elif r.get("mark") == "end" and cur:
            marks.append(cur + [r["t"]])
            cur = None
    faults = sum(1 for r in recs if r.get("t") == "fault")
    log = ctm_read.read_log(os.path.join(a.inst, a.arm + "_sc3cartrips.log"))
    cars = [c for c in log if c["kind"] == "CARS"]
    m2 = [c for c in log if c["kind"] == "M2"]
    out = {"arm": a.arm, "probe_faults": faults, "phases": [],
           "graph_faults": m2[-1].get("fault") if m2 else None, "spawn_faults": cars[-1].get("spawn_fault") if cars else None}
    running_since = None
    for name, t0, t1 in marks:
        ins = [c for c in cars if (t0 + 3) * 1000 <= c["epoch"] <= t1 * 1000]
        before = [c for c in cars if c["epoch"] < (t0 + 3) * 1000]
        if not ins:
            continue
        base = before[-1] if before else ins[0]
        last = ins[-1]
        d = {k: last.get(k, 0) - base.get(k, 0) for k in CUM}
        secs = (last["epoch"] - base["epoch"]) / 1000.0
        row = {"phase": name, "secs": round(secs, 1), "samples": len(ins), "delta": d}
        al = [c["alive"] for c in ins]
        tg = [c["target"] for c in ins]
        rc = [c["route_cars"] for c in ins]
        row["alive_mean"] = sum(al) / len(al)
        row["target_mean"] = sum(tg) / len(tg)
        row["route_mean"] = sum(rc) / len(rc)
        row["alive_max"] = max(al)
        q = [c for c in ins if c["queued_routes"] > 0 and c["target"] > 0]
        row["p1_within10_share"] = (sum(1 for c in q if abs(c["alive"] - c["target"]) <= 0.1 * c["target"]) / len(q)) if q else None
        row["p1_queued_samples"] = len(q)
        if name.startswith("s") and running_since is None:
            running_since = t0
        late = [c for c in ins if running_since is not None and c["epoch"] >= (running_since + 60) * 1000 and c["alive"] > 0]
        row["p2_route_share_min"] = min(c["route_cars"] / c["alive"] for c in late) if late else None
        row["p2_seconds_ge99"] = (sum(1 for c in late if c["route_cars"] >= 0.99 * c["alive"]) / len(late)) if late else None
        row["p3_followed_share"] = d["followed"] / d["decisions"] if d["decisions"] else None
        ends = d["end_arrived"] + d["end_lost"] + d["end_other"]
        row["ends"] = ends
        row["p3_lost_share"] = d["end_lost"] / ends if ends else None
        row["p3_covered"] = d["steps_covered"] / d["steps_total"] if d["steps_total"] else None
        row["p4_need_true_ok"] = d["need_true"] <= d["end_arrived"] + d["end_lost"] + 0   # by construction
        row["p4_other_not_edge_per_min"] = (d["end_other"] - d["end_other_edge"]) / secs * 60 if secs else None
        row["route_cars_first_last"] = [rc[0], rc[-1]]
        row["mod_ms_per_s"] = d["cyc"] / 3593.3e3 / secs if secs else None
        out["phases"].append(row)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    for p in out["phases"]:
        dd = p["delta"]
        print("%-8s %5.0fs alive %.1f target %.1f route %.1f | P1 %s | P2 min %s | dec %d fol %s | ends arr %d lost %d other %d (edge %d) | cov %s | spawn ok %d try %d | mod %.2f ms/s" % (
            p["phase"], p["secs"], p["alive_mean"], p["target_mean"], p["route_mean"],
            "%.2f" % p["p1_within10_share"] if p["p1_within10_share"] is not None else "-",
            "%.3f" % p["p2_route_share_min"] if p["p2_route_share_min"] is not None else "-",
            dd["decisions"], "%.3f" % p["p3_followed_share"] if p["p3_followed_share"] else "-",
            dd["end_arrived"], dd["end_lost"], dd["end_other"], dd["end_other_edge"],
            "%.3f" % p["p3_covered"] if p["p3_covered"] else "-", dd["spawn_ok"], dd["spawn_try"], p["mod_ms_per_s"] or 0))
    print("faults: probe %d, graph %s, spawn %s" % (faults, out["graph_faults"], out["spawn_faults"]))


if __name__ == "__main__":
    main()
