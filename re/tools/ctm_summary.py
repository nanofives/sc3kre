#!/usr/bin/env python3
r"""ctm_summary.py - per phase of a ct_run arm, the sc3cartrips STAT counters per second (task cartrips2).

  py -3.12 ctm_summary.py <inst> <arm>     reads <arm>.jsonl (phase marks) and <arm>_sc3cartrips.log
STAT windows (log_s long, epoch-stamped at their end) count toward a phase when they lie inside it, first 3 s dropped.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ctm_read

def main():
    inst, arm = sys.argv[1], sys.argv[2]
    recs = [json.loads(l) for l in open(os.path.join(inst, arm + ".jsonl"), encoding="utf-8") if l.strip()]
    marks, cur = [], None
    for r in recs:
        if r.get("mark") == "start": cur = [r["phase"], r["t"] + 3]
        elif r.get("mark") == "end" and cur: marks.append(cur + [r["t"]]); cur = None
    faults = sum(1 for r in recs if r.get("t") == "fault")
    log = ctm_read.read_log(os.path.join(inst, arm + "_sc3cartrips.log"))
    stats = [s for s in log if s["kind"] == "STAT"]
    out = {"arm": arm, "probe_faults": faults, "phases": []}
    keys = ("paths", "nodes", "flagged", "roadonly", "mixed", "transit", "vp", "vpflag", "vproad", "vpnodes", "commits", "drops", "drained")
    for name, t0, t1 in marks:
        sw = [s for s in stats if t0 * 1000 <= s["epoch"] - s["dt"] * 1000 and s["epoch"] <= t1 * 1000]
        if not sw: continue
        d = sum(s["dt"] for s in sw)
        row = {"phase": name, "secs": round(d, 1)}
        for k in keys: row[k + "_s"] = round(sum(s[k] for s in sw) / d, 2)
        row["threads"] = max(s["threads"] for s in sw)
        row["lat_max_ms"] = max(s["lat_max_ms"] for s in sw)
        out["phases"].append(row)
    for kind in ("VERIFY", "CHOICE", "M2", "TIME"):
        last = [s for s in log if s["kind"] == kind]
        if last: out[kind] = {k: v for k, v in last[-1].items() if k not in ("s", "kind")}
    out["callers"] = [{k: v for k, v in s.items() if k not in ("s", "kind")} for s in log if s["kind"] == "CALLER"][-60:]
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main()
