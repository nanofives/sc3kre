#!/usr/bin/env python3
"""linux_match_all.py - match every SC3 Windows module against its Loki Linux counterpart, iterating with the
framework-naming lever until the total stops growing.

    loop:  linux_match (every module, --fw framework.tsv)  ->  pairs_<stem>.tsv
           framework_names.py (names framework copies from the exe pairs + EXT-callee votes of all pairs)
    until total pairs does not grow (or --max-iter).
Final pass reports per-module coverage and the held-out precision (5 random 50/50 anchor splits).

Module map: win_<x>.tsv <-> lin_lib<x>.tsv (case-insensitive); SC3U.exe AND every GZ*.dll <-> sc3u_demo.x86. Modules without a
counterpart (MaxisAddOn on Windows, libWebCam on Linux) are listed and skipped.
Outputs: re/match_linux/pairs_<stem>.tsv, framework.tsv, match_summary.tsv. Names stay [LINUX-HINT].
"""
import argparse
import glob
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import linux_match as m  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
D = os.path.join(ROOT, "re", "match_linux")
MODS = os.path.join(ROOT, "original", "modules")


def module_pairs():
    wins = {os.path.basename(p)[4:-4]: p for p in glob.glob(os.path.join(D, "win_*.tsv"))}
    lins = {os.path.basename(p)[4:-4]: p for p in glob.glob(os.path.join(D, "lin_*.tsv"))
            if not os.path.basename(p).startswith("lin_vt_")}
    pes = {os.path.splitext(f)[0].lower(): os.path.join(MODS, f) for f in os.listdir(MODS)
           if f.lower().endswith(".dll")}
    pes["sc3u"] = os.path.join(ROOT, "original", "SC3U.exe")
    out, missing = [], []
    for w, wp in sorted(wins.items()):
        # The GZ framework DLLs' Linux namesakes are ~800-function stubs: on Linux the framework itself lives in
        # the exe. Measured 2026-10-05: GZWinD vs libGZWinD 22 pairs, vs sc3u_demo.x86 133; GZResourceD 21 -> 162.
        l = "sc3u_demo" if (w == "sc3u" or w.startswith("gz")) else "lib" + w
        if l not in lins:
            missing.append(f"win {w} (no {l})")
            continue
        vt = os.path.join(D, f"lin_vt_{l}.tsv")
        out.append((w, wp, lins[l], pes.get(w), vt if os.path.exists(vt) else None))
    used = {os.path.basename(lp)[4:-4] for _, _, lp, _, _ in out}
    missing += [f"lin {l} (no windows module)" for l in lins if l not in used]
    return out, missing


def run_module(w, wp, lp, pe, vt, fw, holdout=False):
    W, L = m.load(wp, fw), m.load(lp)
    Wv = m.win_vtables(pe, W) if pe else []
    Lv = m.lin_vtables(vt, L) if vt else []
    seed = m.anchors(W, L, ("strs", "consts", "strs_set", "consts_set", "exts_set", "fw_set"))
    pairs = m.pipeline(W, L, seed, Wv, Lv)
    with open(os.path.join(D, f"pairs_{w}.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("win_entry\tlin_entry\tlin_name\tstage\tevidence\n")
        for x in sorted(pairs):
            l, stage, ev = pairs[x]
            fh.write(f"{x}\t{l}\t{L[l]['name']}\t{stage}\t{ev}\n")
    agree = dis = 0
    if holdout and len(seed) >= 4:
        for t in range(5):
            k = sorted(seed)
            random.Random(t).shuffle(k)
            got = m.pipeline(W, L, {x: seed[x] for x in k[: len(k) // 2]}, Wv, Lv)
            for x in k[len(k) // 2:]:
                if x in got:
                    if got[x][0] == seed[x][0]:
                        agree += 1
                    else:
                        dis += 1
    return len(W), len(seed), len(pairs), agree, dis


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-iter", type=int, default=4)
    a = ap.parse_args(argv)
    mods, missing = module_pairs()
    print(f"{len(mods)} module pairs; skipped: {', '.join(missing) or 'none'}")
    fwpath = os.path.join(D, "framework.tsv")
    prev = -1
    for it in range(1, a.max_iter + 1):
        fw = m.load_fw(fwpath) if os.path.exists(fwpath) else None
        total = 0
        for w, wp, lp, pe, vt in mods:
            total += run_module(w, wp, lp, pe, vt, fw)[2]
        r = subprocess.run([sys.executable, os.path.join(HERE, "framework_names.py")], capture_output=True, text=True)
        named = [l for l in r.stdout.splitlines() if l.startswith("named")]
        print(f"iter {it}: total pairs {total}; {named[0] if named else r.stdout[-300:]}")
        if total <= prev:
            break
        prev = total
    fw = m.load_fw(fwpath)
    rows, T = [], [0, 0, 0, 0, 0]
    for w, wp, lp, pe, vt in mods:
        n, s, p, ag, di = run_module(w, wp, lp, pe, vt, fw, holdout=True)
        rows.append((w, n, s, p, ag, di))
        for i, v in enumerate((n, s, p, ag, di)):
            T[i] += v
    with open(os.path.join(D, "match_summary.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("module\twin_fns\tanchors\tpairs\tpct\tholdout_agree\tholdout_disagree\n")
        for w, n, s, p, ag, di in sorted(rows, key=lambda r: -r[3]):
            fh.write(f"{w}\t{n}\t{s}\t{p}\t{100 * p / max(1, n):.1f}\t{ag}\t{di}\n")
            print(f"{w:14} fns {n:6}  anchors {s:5}  pairs {p:5} ({100 * p / max(1, n):4.1f}%)  holdout {ag}/{ag + di}")
    print(f"TOTAL fns {T[0]}  pairs {T[2]} ({100 * T[2] / max(1, T[0]):.1f}%)  holdout agree {T[3]} disagree {T[4]}"
          + (f" -> precision {100 * T[3] / (T[3] + T[4]):.1f}%" if T[3] + T[4] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
