#!/usr/bin/env python3
r"""pt_summary.py - per-phase table of a pausetrips arm's jsonl (verify/pausetrips/PRE.md).

  py -3.12 pt_summary.py ARM.jsonl [--skip 3] [--json out.json] [--detail]

Per phase: seconds counted (the first --skip seconds of each phase are dropped, PRE), sum and per-second mean of every
counter, router steps, distinct vehicles moved per second, validity of the pause state (PRE validity rule), and with
--detail the caller / thread buckets and backtraces.
"""
import argparse
import collections
import json

COLS = ["day_aa4d", "issuer_97b9", "trip_6fe3", "trip_706a", "route_trip", "route_trip.arrive", "route_trip.fail",
        "steps", "deposit_6edd", "stats_9242", "publish_93e9", "strt_c750", "veh"]


def load(path):
    meta, ticks, marks, timers = None, [], [], []
    for line in open(path):
        r = json.loads(line)
        if r.get("phase") == "meta":
            meta = r
        elif r.get("t") and "c" in r:
            ticks.append(r)
        elif "mark" in r:
            marks.append(r)
        elif "timers" in r:
            timers.append(r)
    return meta, ticks, marks, timers


def phases(ticks, skip):
    order, per = [], collections.OrderedDict()
    seen = collections.Counter()
    for r in ticks:
        ph = r["phase"]
        seen[ph] += 1
        if ph not in per:
            per[ph] = []
            order.append(ph)
        if seen[ph] > skip:
            per[ph].append(r)
    return per


def valid(ph, rows, game_tid):
    what = ph.split(":")[0]
    bad = 0
    for r in rows:
        st = r.get("st", {})
        if what in ("P", "PH"):
            bad += (st.get("user_pause") or 0) < 1
        elif what.startswith("s") or what == "H":
            want = int(what[1:]) if what.startswith("s") else None
            bad += (st.get("user_pause") or 0) != 0 or (want is not None and st.get("speed_last") != want)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--skip", type=int, default=3)
    ap.add_argument("--json")
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args()
    meta, ticks, marks, timers = load(a.jsonl)
    per = phases(ticks, a.skip)
    allrows = phases(ticks, 0)
    out = {"meta": meta, "phases": []}
    hdr = "%-8s %4s %6s " % ("phase", "n", "bad") + " ".join("%12s" % c.replace("route_trip", "rt") for c in COLS)
    print(hdr)
    for ph, rows in per.items():
        if ph in ("boot", "meta", "end") or ph.startswith("sw>"):
            continue
        sums = collections.Counter()
        for r in rows:
            for k, v in r["c"].items():
                sums[k] += v
            sums["steps"] += r.get("steps", 0)
            sums["veh"] += r.get("veh", 0)
        n = len(rows)
        bad = valid(ph, rows, meta and meta.get("game_tid"))
        st0 = rows[0]["st"] if rows else {}
        st1 = rows[-1]["st"] if rows else {}
        rec = {"phase": ph, "n": n, "bad": bad, "sum": dict(sums),
               "cam_hold_secs": sum(1 for r in rows if (r["st"].get("cam_hold") or 0) >= 1),
               "clk_pause_secs": sum(1 for r in rows if (r["st"].get("clk_pause") or 0) >= 1),
               "veh_phase": rows[-1].get("vehp") if rows else None,
               "day0": st0.get("day"), "day1": st1.get("day"),
               "att0": st0.get("l_attempts"), "att1": st1.get("l_attempts"),
               "fail0": st0.get("l_fails"), "fail1": st1.get("l_fails")}
        if a.detail:
            for key in ("route_trip.caller", "trip_6fe3.caller", "trip_706a.caller", "strt_c750.caller"):
                b = collections.Counter()
                for r in rows:
                    for k, v in r.get("by", {}).get(key, {}).items():
                        b[k] += v
                if b:
                    rec[key] = dict(b.most_common())
            for key in ("route_trip", "trip_706a", "strt_c750"):
                b = collections.Counter()
                for r in rows:
                    for k, v in r.get("th", {}).get(key, {}).items():
                        b[k] += v
                if b:
                    rec["th." + key] = dict(b)
            rec["bt"] = [x for r in allrows[ph] for x in r.get("bt", [])]
        out["phases"].append(rec)
        print("%-8s %4d %6d " % (ph, n, bad) + " ".join("%12d" % sums.get(c, 0) for c in COLS) +
              "  hold%d clkp%d day %s->%s vehphase %s" % (rec["cam_hold_secs"], rec["clk_pause_secs"], rec["day0"],
                                                              rec["day1"], rec["veh_phase"]))
    if a.detail:
        for rec in out["phases"]:
            print("\n==", rec["phase"])
            for k, v in rec.items():
                if k not in ("phase", "n", "bad", "sum", "bt"):
                    print("  %s: %s" % (k, v))
            for b in rec.get("bt", []):
                print("  bt %s tid %s: %s" % (b["fn"], b["tid"], " < ".join(b["frames"][:8])))
        for t in timers[:1] + timers[-1:]:
            print("\ntimers @", t["phase"])
            for e in t["timers"] or []:
                print("  ", e)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
