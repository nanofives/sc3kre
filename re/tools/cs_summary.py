#!/usr/bin/env python3
r"""cs_summary.py - per-phase and per-(kind, animate) tables of a carscroll arm (cs_run.py jsonl).

  py -3.12 cs_summary.py <arm.jsonl> [--drop 2] [--json out.json]

A phase's first --drop seconds are not counted. The animate state of a phase is the last A0 / A1 mark before it
(the ini default, A1, before the first mark). Kind = the phase token without its seconds and '*'.
"""
import argparse
import collections
import json
import statistics


def mean(xs):
    return statistics.mean(xs) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--drop", type=float, default=2)
    ap.add_argument("--json")
    a = ap.parse_args()
    recs = [json.loads(l) for l in open(a.jsonl) if l.strip()]
    anim = 1
    phases = []          # (index, token, animate, start_t, [ticks])
    cur = None
    for r in recs:
        if r.get("mark") == "animate":
            anim = 1 if r["on"] else 0
            continue
        if r.get("mark") == "start":
            cur = {"tok": r["phase"], "anim": anim, "t0": r["t"], "ticks": [], "st0": r.get("st")}
            phases.append(cur)
            continue
        if r.get("mark") == "end":
            if cur:
                cur["st1"] = r.get("st")
            cur = None
            continue
        if "d" in r:
            if cur and r.get("phase") == cur["tok"] and r["t"] - cur["t0"] >= a.drop + 1:
                cur["ticks"].append(r)
    faults = sum(len(r.get("faults") or []) for r in recs)
    rows = []
    for i, p in enumerate(phases):
        ts = p["ticks"]
        if not ts:
            continue
        D = [t["d"] for t in ts]
        n = len(D)
        sp = [s for t in ts for s in t.get("spawns", [])]
        rm = [x for t in ts for x in t.get("rem", [])]
        st = [t.get("st", {}) for t in ts]
        row = {
            "i": i, "tok": p["tok"], "kind": p["tok"].split(":")[0].rstrip("*"), "anim": p["anim"], "secs": n,
            "frames_s": mean([d["frames"] for d in D]), "scroll_s": mean([d["scroll"] for d in D]),
            "stub_s": mean([d["scroll_stub"] for d in D]), "passes_s": mean([d["ag"] for d in D]),
            "agent_ticks_s": mean([d["agent_ticks"] for d in D]), "frozen_s": mean([d["frozen_ticks"] for d in D]), "strips_s": mean([d.get("strip_refills", 0) for d in D]),
            "moves_s": mean([d["moves"] for d in D]), "ag_ms_s": mean([d["ag_ms"] for d in D]),
            "maxgap_ms_mean": mean([d["maxgap_ms"] for d in D]), "maxgap_ms_max": max(d["maxgap_ms"] for d in D),
            "cars": mean([s.get("p_count") or 0 for s in st]), "target": mean([s.get("p_target") or 0 for s in st]),
            "spawn_min": len(sp) * 60.0 / n, "spawn_vis_min": sum(s["vis"] for s in sp) * 60.0 / n,
            "spawn_box_min": sum(s.get("vbox", 0) for s in sp) * 60.0 / n, "rem_box_min": sum(x.get("vbox", 0) for x in rm) * 60.0 / n,
            "spawn_box_by": dict(collections.Counter(s["ctx"] for s in sp if s.get("vbox"))),
            "rem_box_by": dict(collections.Counter(x["ctx"] for x in rm if x.get("vbox"))),
            "spawn_by": dict(collections.Counter(s["ctx"] for s in sp)),
            "spawn_vis_by": dict(collections.Counter(s["ctx"] for s in sp if s["vis"])),
            "rem_min": len(rm) * 60.0 / n, "rem_vis_min": sum(x["vis"] for x in rm) * 60.0 / n,
            "rem_by": dict(collections.Counter(x["ctx"] for x in rm)),
            "rem_vis_by": dict(collections.Counter(x["ctx"] for x in rm if x["vis"])),
            "view_updates_s": mean([t.get("c", {}).get("view_update", 0) for t in ts]),
            "pause": max((s.get("user_pause") or 0) for s in st), "hold": max((s.get("cam_hold") or 0) for s in st),
            "zoom": st[-1].get("zoom"),
        }
        v0, v1 = (p.get("st0") or {}).get("view"), (p.get("st1") or {}).get("view")
        row["view_moved"] = (abs(v1[0] - v0[0]) + abs(v1[1] - v0[1])) if v0 and v1 else None
        rows.append(row)
    keys = ["i", "tok", "anim", "secs", "frames_s", "scroll_s", "passes_s", "agent_ticks_s", "frozen_s", "moves_s",
            "maxgap_ms_mean", "maxgap_ms_max", "cars", "strips_s", "spawn_vis_min", "spawn_box_min", "rem_vis_min", "rem_box_min", "spawn_min", "rem_min", "view_updates_s"]
    print("\t".join(keys))
    for r in rows:
        print("\t".join(("%.1f" % r[k]) if isinstance(r[k], float) else str(r[k]) for k in keys))
    # pooled by (kind, anim)
    pool = collections.defaultdict(list)
    for r in rows:
        pool[(r["kind"], r["anim"])].append(r)
    print("\npooled (seconds-weighted)")
    agg = {}
    pk = ["frames_s", "scroll_s", "passes_s", "agent_ticks_s", "frozen_s", "moves_s", "maxgap_ms_mean", "ag_ms_s",
          "cars", "strips_s", "spawn_vis_min", "spawn_box_min", "rem_vis_min", "rem_box_min", "spawn_min", "rem_min",
          "view_updates_s"]
    print("\t".join(["kind", "anim", "secs"] + pk + ["maxgap_ms_max"]))
    for (k, an), rs in sorted(pool.items()):
        n = sum(r["secs"] for r in rs)
        g = {q: sum((r[q] or 0) * r["secs"] for r in rs) / n for q in pk}
        g["maxgap_ms_max"] = max(r["maxgap_ms_max"] for r in rs)
        g["secs"] = n
        g["spawn_vis_by"] = dict(sum((collections.Counter(r["spawn_vis_by"]) for r in rs), collections.Counter()))
        g["rem_vis_by"] = dict(sum((collections.Counter(r["rem_vis_by"]) for r in rs), collections.Counter()))
        g["spawn_box_by"] = dict(sum((collections.Counter(r["spawn_box_by"]) for r in rs), collections.Counter()))
        g["rem_box_by"] = dict(sum((collections.Counter(r["rem_box_by"]) for r in rs), collections.Counter()))
        agg["%s/%d" % (k, an)] = g
        print("\t".join([k, str(an), str(n)] + ["%.1f" % g[q] for q in pk] + ["%.1f" % g["maxgap_ms_max"]]))
    print("\nfaults:", faults)
    if a.json:
        json.dump({"rows": rows, "pooled": agg, "faults": faults}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
