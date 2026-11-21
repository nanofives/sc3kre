#!/usr/bin/env python3
r"""popslow_table.py - markdown tables from popslow_ab.py's ab*.jsonl (task popslow, 2026-11-21).

Per arm (label) and pop-up: mean over repetitions of the closed window just before the open window, and of the open
window. Days/s, the clock-held share (and the UI-hold part), frames/s, UI-thread CPU per frame (ms) and, for modded
runs, sc3perf surface Locks per second.

Usage: py -3.12 re/tools/popslow_table.py verify/popslow/ab/ab.jsonl [more.jsonl ...] [--labels a,b]
"""
import argparse
import collections
import json


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--labels", default="")
    a = ap.parse_args(argv)
    rows = []
    for f in a.files:
        rows += [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    want = a.labels.split(",") if a.labels else None
    by = collections.OrderedDict()
    prev = {}
    for r in rows:
        lab = r["label"]
        if want and lab not in want:
            continue
        if r["phase"] == "closed":
            prev[lab] = r
            continue
        c = prev.get(lab)
        if not c or c["pop"] != r["pop"]:
            continue
        by.setdefault(lab, collections.OrderedDict()).setdefault(r["pop"], []).append((c, r))

    def ms(x):
        return 10.0 * x["cpu_ui_pct"] / x["frames_per_s"] if x["frames_per_s"] > 0.5 else float("nan")

    def mean(v):
        v = [x for x in v if x == x]
        return sum(v) / len(v) if v else float("nan")

    for lab, pops in by.items():
        print(f"\n**{lab}**\n")
        print("| pop-up | n | days/s closed | days/s open | clock held open (UI hold) | frames/s closed | frames/s open "
              "| UI ms/frame closed | UI ms/frame open | Locks/s open |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for p, pairs in pops.items():
            c = [x[0] for x in pairs]
            o = [x[1] for x in pairs]
            lk = [x.get("perf_locks_per_s") for x in o if x.get("perf_locks_per_s") is not None]
            print(f"| {p} | {len(pairs)} | {mean([x['days_per_s'] for x in c]):.2f} | {mean([x['days_per_s'] for x in o]):.2f} "
                  f"| {mean([x['held_pct'] for x in o]):.0f}% ({mean([x['uihold_pct'] for x in o]):.0f}%) "
                  f"| {mean([x['frames_per_s'] for x in c]):.1f} | {mean([x['frames_per_s'] for x in o]):.1f} "
                  f"| {mean([ms(x) for x in c]):.1f} | {mean([ms(x) for x in o]):.1f} "
                  f"| {('%.0f' % mean(lk)) if lk else '-'} |")


if __name__ == "__main__":
    main()
