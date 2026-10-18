"""Summarize the verify/hudperf final campaign (bench.json of each fin_* run) as a markdown table.

Per phase the first 10-s log window is dropped (it straddles the previous phase). Values are medians of the rest.
Usage: py -3.12 re/tools/hudperf_summary.py <MAIN verify/hudperf dir>
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys


def med(v):
    return statistics.median(v) if v else None


def load(d: pathlib.Path, name: str):
    p = d / name / "bench.json"
    return json.loads(p.read_text()) if p.exists() else None


def f(x, nd=1):
    return "-" if x is None else f"{x:.{nd}f}"


def main(argv):
    d = pathlib.Path(argv[0])
    phases = ["static", "scroll", "hover", "flyout"]
    out = ["| scale | phase | A cycles M (pass+restore) | B cycles M | B/A | A presents/10s | B presents/10s | A pass ms | B pass ms | B lazy paid late / dropped |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    chk = ["| scale | phase | frames compared | frames with a pixel difference | px | coverage frames / px |", "|---|---|---|---|---|---|"]
    for sc in ["125", "150", "200", "1"]:
        A, B, C = load(d, f"fin_s{sc}_A"), load(d, f"fin_s{sc}_B"), load(d, f"fin_s{sc}_chk")
        label = "Fit" if sc == "1" else sc
        for ph in phases:
            row = []
            vals = {}
            for arm, R in (("A", A), ("B", B)):
                r = R["phases"].get(ph) if R else None
                if not r:
                    vals[arm] = (None, None, None, None)
                    continue
                cyc = [p + q for p, q in r.get("cycles_M", [])][1:]
                pres = r.get("presents_per_10s", [])[1:]
                ms = r.get("pass_ms", [])[1:]
                lz = r.get("lazy", [])[1:]
                late = sum(sum(int(v) for v in t[1:6]) for t in lz)
                drop = sum(int(t[6]) for t in lz)
                vals[arm] = (med(cyc), med(pres), med(ms), f"{late} / {drop}" if lz else "-")
            a, b = vals["A"], vals["B"]
            ratio = f"{100 * b[0] / a[0]:.0f}%" if a[0] and b[0] else "-"
            out.append(f"| {label} | {ph} | {f(a[0])} | {f(b[0])} | {ratio} | {f(a[1], 0)} | {f(b[1], 0)} | {f(a[2], 2)} | {f(b[2], 2)} | {b[3]} |")
            r = C["phases"].get(ph) if C else None
            if r:
                ck = r.get("check", [])
                fr = sum(int(t[0]) for t in ck); fd = sum(int(t[1]) for t in ck); px = sum(int(t[2]) for t in ck)
                cf = sum(int(t[3]) for t in ck); cp = sum(int(t[4]) for t in ck)
                chk.append(f"| {label} | {ph} | {fr} | {fd} | {px} | {cf} / {cp} |")
    print("\n".join(out))
    print()
    print("\n".join(chk))
    for name in ("fin_normal", "fin_lazy0"):
        R = load(d, name)
        if not R:
            continue
        print(f"\n{name}:")
        for ph, r in R["phases"].items():
            cyc = [p + q for p, q in r.get("cycles_M", [])][1:]
            print(f"  {ph}: sc3perf fps median {r.get('fps_median')}, cycles M {med(cyc)}, presents {med(r.get('presents_per_10s', [])[1:])}, pass ms {med(r.get('pass_ms', [])[1:])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
