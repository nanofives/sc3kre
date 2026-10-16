#!/usr/bin/env python3
r"""cs_onscreen.py - on-screen car counts around each camera move of a carscroll arm (verify/carscroll PRE addendum 8).

  py -3.12 cs_onscreen.py <arm.jsonl> [--drop 2] [--json out.json]

For every move phase (H, HB, AR, OS) with an idle phase (I) just before and just after it: the median per second of the
probe's `onscreen` (cars drawn per frame, averaged over the second) over the move's counted seconds (first --drop s
dropped), over the idle before it (its counted seconds) and over the idle after it (all its seconds: "right after").
Ratios move / before and after / before per move; pooled per (kind, state) as the median of the per-move ratios and
the minimum. State = the last A0/A1 or F0/F1 mark (cs_run records both as "animate" marks).
"""
import argparse
import collections
import json
import statistics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--drop", type=float, default=2)
    ap.add_argument("--json")
    ap.add_argument("--log", help="sc3cartrips log (log_s=1): also the route cars inside the view box (CARS> inbox=)")
    a = ap.parse_args()
    box = []
    if a.log:
        import re
        for line in open(a.log, errors="replace"):
            if "CARS>" in line and "inbox=" in line:
                m = re.search(r"epoch=(\d+)", line); n = re.search(r"inbox=(-?\d+)", line)
                box.append((int(m.group(1)) / 1000.0, int(n.group(1))))
    phases, state, cur = [], 1, None
    for line in open(a.jsonl):
        r = json.loads(line)
        if r.get("mark") == "animate":
            state = 1 if r["on"] else 0
        elif r.get("mark") == "start":
            cur = {"tok": r["phase"], "kind": r["phase"].split(":")[0].rstrip("*"), "state": state, "t0": r["t"], "sec": []}
            phases.append(cur)
        elif r.get("mark") == "end":
            cur = None
        elif "d" in r and cur and r.get("phase") == cur["tok"]:
            cur["sec"].append((r["t"] - cur["t0"], r["d"].get("onscreen", 0.0), (r.get("st") or {}).get("p_count")))
    rows = []
    for i, p in enumerate(phases):
        if p["kind"] not in ("H", "HB", "HG", "AR", "OS") or i == 0 or i + 1 >= len(phases):
            continue
        b, f = phases[i - 1], phases[i + 1]
        if b["kind"] != "I" or f["kind"] != "I":
            continue
        mv = [v for t, v, _ in p["sec"] if t >= a.drop + 1]
        bf = [v for t, v, _ in b["sec"] if t >= a.drop + 1]
        af = [v for t, v, _ in f["sec"]]
        if not mv or not bf or not af:
            continue
        mb = statistics.median(bf)
        def boxmed(ph, t_from):
            v = [n for t, n in box if ph["t0"] + t_from <= t < ph["t0"] + (ph["sec"][-1][0] + 1 if ph["sec"] else 0)]
            return statistics.median(v) if v else None
        row = {"i": i, "kind": p["kind"], "state": p["state"], "before": mb, "move": statistics.median(mv),
               "after": statistics.median(af), "move_min": min(mv), "after_min": min(af)}
        row["r_move"] = row["move"] / mb if mb else None
        row["r_after"] = row["after"] / mb if mb else None
        if box:
            bb, bm, ba = boxmed(b, a.drop), boxmed(p, a.drop), boxmed(f, 0)
            row.update({"box_before": bb, "box_move": bm, "box_after": ba,
                        "rb_move": bm / bb if bb and bm is not None else None, "rb_after": ba / bb if bb and ba is not None else None})
        rows.append(row)
    print("i\tkind\tstate\tbefore\tmove\tafter\tr_move\tr_after")
    for r in rows:
        print("%d\t%s\t%d\t%.1f\t%.1f\t%.1f\t%s\t%s" % (r["i"], r["kind"], r["state"], r["before"], r["move"], r["after"],
              "%.2f" % r["r_move"] if r["r_move"] is not None else "-", "%.2f" % r["r_after"] if r["r_after"] is not None else "-"))
    pool = collections.defaultdict(list)
    for r in rows:
        if r["r_move"] is not None:
            pool[(r["kind"], r["state"])].append(r)
    out = {}
    print("\nkind\tstate\tmoves\tbefore\tmove\tafter\tr_move median (min)\tr_after median (min)")
    for (k, s), rs in sorted(pool.items()):
        rm = [r["r_move"] for r in rs]
        ra = [r["r_after"] for r in rs]
        g = {"moves": len(rs), "before": statistics.median([r["before"] for r in rs]),
             "move": statistics.median([r["move"] for r in rs]), "after": statistics.median([r["after"] for r in rs]),
             "r_move": statistics.median(rm), "r_move_min": min(rm), "r_after": statistics.median(ra), "r_after_min": min(ra)}
        rbm = [r["rb_move"] for r in rs if r.get("rb_move") is not None]
        rba = [r["rb_after"] for r in rs if r.get("rb_after") is not None]
        if rbm:
            g.update({"rb_move": statistics.median(rbm), "rb_move_min": min(rbm), "rb_after": statistics.median(rba) if rba else None,
                      "rb_after_min": min(rba) if rba else None,
                      "box_before": statistics.median([r["box_before"] for r in rs if r.get("box_before") is not None])})
        out["%s/%d" % (k, s)] = g
        print("%s\t%d\t%d\t%.1f\t%.1f\t%.1f\t%.2f (%.2f)\t%.2f (%.2f)" % (k, s, g["moves"], g["before"], g["move"], g["after"],
              g["r_move"], g["r_move_min"], g["r_after"], g["r_after_min"]) +
              ("	box: before %.1f, move %.2f (%.2f), after %.2f (%.2f)" % (g["box_before"], g["rb_move"], g["rb_move_min"],
               g["rb_after"] or 0, g["rb_after_min"] or 0) if "rb_move" in g else ""))
    if a.json:
        json.dump({"rows": rows, "pooled": out}, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
