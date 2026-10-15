#!/usr/bin/env python3
r"""ct_summary.py - per-phase tables of one cartrips arm (verify/cartrips/PRE.md) from its <arm>.jsonl.

  py -3.12 ct_summary.py <arm.jsonl> [--json out.json] [--drop 3]

Phases are grouped in run order (a label that repeats is a new phase). The first --drop seconds of each phase and every
'sw>' second (keys being posted) are not counted. Trip counters in the probe are cumulative per thread; per-second
values are the differences between consecutive lines.
"""
import argparse
import collections
import json
import statistics

VIS_PASSES = 3        # PRE addendum 1: drawn (k0 or k1) within the last 3 agent-loop passes
VIS_PASSES_LOOSE = 250


def load(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def phases(rows, drop):
    """[(label, [tick rows])] in run order, without the first `drop` seconds of each phase."""
    out, cur, label, n = [], None, None, 0
    for r in rows:
        if r.get("t") == "fault" or "c" not in r:
            continue
        ph = r.get("phase", "")
        if ph != label:
            label, n = ph, 0
            cur = (ph, [])
            if not ph.startswith("sw>") and ph not in ("boot", "meta", "end"):
                out.append(cur)
        n += 1
        if n > drop and cur is not None:
            cur[1].append(r)
    return out


def trip_deltas(rows):
    """per row: summed per-second deltas of the trip counters over all threads"""
    prev = {}
    for r in rows:
        if "c" not in r:
            continue
        d = collections.Counter()
        nh = [0] * 8
        vh = [0] * 8
        ty = [0] * 14
        for tid, v in (r.get("trips") or {}).get("by_thread", {}).items():
            p = prev.get(tid)
            for k in ("calls", "arrived", "nodes", "flagged", "vp", "vpnodes", "vpflag", "roadonly", "vproadonly", "ticks"):
                d[k] += v[k] - (p[k] if p else 0)
            for i in range(8):
                nh[i] += v["nhist"][i] - (p["nhist"][i] if p else 0)
                vh[i] += v["vphist"][i] - (p["vphist"][i] if p else 0)
            for i in range(14):
                ty[i] += v["types"][i] - (p["types"][i] if p else 0)
            prev[tid] = v
        d["threads"] = len((r.get("trips") or {}).get("by_thread", {}))
        r["_trip"] = d
        r["_nh"], r["_vh"], r["_ty"] = nh, vh, ty


def visible(rem, passes):
    a = rem.get("acc") or [0, 0, 0, 0]
    ag = rem.get("ag") or 0
    last = max(a[0], a[1])
    return last > 0 and ag - last <= passes


def mean(xs):
    return statistics.mean(xs) if xs else None


def summarize(path, drop=3):
    rows = load(path)
    meta = next((r for r in rows if r.get("phase") == "meta"), {})
    trip_deltas(rows)
    faults = [r for r in rows if r.get("t") == "fault"]
    out = {"arm": meta.get("arm"), "pid": meta.get("pid"), "schedule": meta.get("schedule"), "faults": len(faults),
           "phases": []}
    all_cells_car = collections.Counter()
    all_rem = []
    samples = []
    for r in rows:
        samples += r.get("samples") or []
    for label, rs in phases(rows, drop):
        n = len(rs)
        if not n:
            continue
        P = {"phase": label, "seconds": n}
        c = collections.Counter()
        by = collections.defaultdict(collections.Counter)
        rem = []
        st = [r.get("st") or {} for r in rs]
        for r in rs:
            for k, v in (r.get("c") or {}).items():
                c[k] += v
            for k, b in (r.get("by") or {}).items():
                for kk, vv in b.items():
                    by[k][kk] += vv
            rem += r.get("rem") or []
            for e in r.get("cells") or []:
                if e.get("f") == 0:
                    all_cells_car[(e["x"], e["z"])] += 1
        for x in rem:
            x["_phase"] = label
        all_rem += rem
        days = [s.get("day") for s in st if s.get("day") is not None]
        P["days_per_s"] = (days[-1] - days[0]) / max(1, len(days) - 1) if len(days) > 1 else None
        P["cars_mean"] = mean([s["p_count"] for s in st if s.get("p_count") is not None])
        P["target_mean"] = mean([s["p_target"] for s in st if s.get("p_target") is not None])
        P["avg_density_mean"] = mean([s["p_avg"] for s in st if s.get("p_avg") is not None])
        P["simrect"] = st[-1].get("simrect")
        P["zoom"] = st[-1].get("zoom")
        P["count_over_target_plus1"] = sum(1 for s in st if s.get("p_count") is not None and
                                           (s["p_count"] > s["p_target"] + 1 or s["p_count"] > 200))
        for k in ("spawn", "removed", "cell_moves", "nvd_calls", "nvd_true", "nopath", "view_update", "produce_off", "day"):
            P[k + "_per_s"] = c[k] / n
        P["spawn_by_caller"] = dict(by["spawn_by_caller"])
        P["removed_by"] = dict(by["removed_by"])
        P["nopath_why"] = dict(by["nopath_why"])
        P["movenstages"] = dict(by["movenstages"])
        vis = [x for x in rem if visible(x, VIS_PASSES)]
        vis_l = [x for x in rem if visible(x, VIS_PASSES_LOOSE)]
        P["removed_visible"] = len(vis)
        P["removed_visible_by"] = dict(collections.Counter(x["cause"] for x in vis))
        P["removed_visible_loose"] = len(vis_l)
        P["removed_visible_loose_by"] = dict(collections.Counter(x["cause"] for x in vis_l))
        ages = [x["age"] for x in rem if x.get("age") is not None and x["cause"] != "placement-failed"]
        P["age_s_median_tracked"] = statistics.median(ages) / 1000 if ages else None
        P["cells_median_tracked"] = statistics.median([x["cells"] for x in rem if x.get("tracked") and x.get("cells") is not None
                                                        and x["cause"] != "placement-failed"] or [0])
        ag = [r.get("ag") or {} for r in rs]
        P["agent_loop_per_s"] = mean([a.get("calls", 0) for a in ag])
        P["agent_loop_ms_per_s"] = mean([a.get("ms", 0) for a in ag])
        P["draw_calls_per_s"] = mean([(r.get("acc") or [0])[0] for r in rs])
        # trip side
        t = collections.Counter()
        nh = [0] * 8
        vh = [0] * 8
        ty = [0] * 14
        for r in rs:
            t.update(r["_trip"])
            nh = [a + b for a, b in zip(nh, r["_nh"])]
            vh = [a + b for a, b in zip(vh, r["_vh"])]
            ty = [a + b for a, b in zip(ty, r["_ty"])]
        for k in ("calls", "arrived", "nodes", "flagged", "vp", "vpnodes", "vpflag", "roadonly", "vproadonly"):
            P["trip_" + k + "_per_s"] = t[k] / n
        P["trip_threads_max"] = max(r["_trip"]["threads"] for r in rs)
        P["route_ms_per_s"] = t["ticks"] / 1e4 / n          # QPC 10 MHz
        P["route_ms_per_trip"] = (t["ticks"] / 1e4 / t["calls"]) if t["calls"] else None
        P["nodes_per_arrived"] = t["nodes"] / t["arrived"] if t["arrived"] else None
        P["path_len_hist"] = nh
        P["vp_innodes_hist"] = vh
        P["node_types"] = dict(zip(["0x80", "1", "2", "3", "4", "8", "0x14", "0x18", "0x30", "0x41", "0x42", "0x43", "0x50", "other"], ty))
        out["phases"].append(P)
    # whole-arm checks
    # prediction 3
    dens = [x for x in all_rem if x["cause"] == "density"]
    out["p3_density_removals"] = len(dens)
    out["p3_density_counter_ge1"] = sum(1 for x in dens if (x.get("mc") or 0) >= 1)
    # prediction 4: outside-sim-rect removals: failing next cell (fx, fz) relative to the rect at that second is not
    # stored per removal; the removal cell (x, z) on the rect edge is checked against the phase's last sim rect
    edge = tot = 0
    for x in all_rem:
        if x["cause"] != "nopath:next-cell-outside-sim-rect" or x.get("x") is None:
            continue
        ph = next(p for p in out["phases"] if p["phase"] == x["_phase"])
        r = ph["simrect"]
        if not r:
            continue
        tot += 1
        if x["x"] in (r[0], r[2]) or x["z"] in (r[1], r[3]):
            edge += 1
    out["p4_outside_rect_removals"] = tot
    out["p4_on_rect_edge"] = edge
    # prediction 7
    ok7 = sum(1 for s in samples if s["p"] and s["p"][-1][2] == 0x80 and (len(s["p"]) == 1 or s["p"][0][2] != 0x80))
    out["p7_samples"] = len(samples)
    out["p7_last_is_origin_first_not"] = ok7
    out["p7_single_node"] = sum(1 for s in samples if s["n"] == 1)
    # prediction 8: car-entered cells vs road/highway node cells of sampled paths
    road = set()
    for s in samples:
        for x, z, ty in s["p"]:
            if ty in (1, 2, 3):
                road.add((x, z))
    cars = set(all_cells_car)
    out["p8_car_cells"] = len(cars)
    out["p8_car_cells_in_sampled_paths"] = len(cars & road)
    tr = set((z, x) for x, z in road)
    out["p8_transposed_check"] = len(cars & tr)
    # removal positions and visibility, whole arm
    out["removals"] = len(all_rem)
    out["removals_by_cause"] = dict(collections.Counter(x["cause"] for x in all_rem))
    out["removals_visible_by_cause"] = dict(collections.Counter(x["cause"] for x in all_rem if visible(x, VIS_PASSES)))
    gaps = collections.Counter()
    for x in all_rem:
        a = x.get("acc") or [0, 0]
        last = max(a[0], a[1])
        g = "never" if not last else ("0-3" if x["ag"] - last <= 3 else "4-50" if x["ag"] - last <= 50 else "51-250" if x["ag"] - last <= 250 else ">250")
        gaps[g] += 1
    out["passes_since_draw_at_removal"] = dict(gaps)
    return out, all_rem, samples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--json")
    ap.add_argument("--drop", type=int, default=3)
    a = ap.parse_args()
    out, rem, samples = summarize(a.jsonl, a.drop)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    print(json.dumps(out, indent=1)[:20000])


if __name__ == "__main__":
    main()
