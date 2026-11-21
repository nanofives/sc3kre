#!/usr/bin/env python3
r"""sc4_set_cover.py - task suitespeed (2026-11-20): which code each SC4 install building reaches, for the small fixed
install set of the suite (sc4_install_set.json).

    py -3.12 re/tools/bldimport/webtest/sc4_set_cover.py --install "<SimCity 4 folder>" --out <dir> [--growables] [--only <list>]

Runs sc4conv.py's main() in this process (same arguments as sc4_install_setup.py's conv run) with a line tracer
(sys.monitoring, Python 3.12): every line of re/tools/sc4conv/*.py and re/tools/bldimport/*.py that runs while a
building is written (write_building) is recorded per building, and every other line once for the run.
Writes <dir>/cover.json: {"global": [[file, line], ...], "buildings": {exemplar: [[file, line], ...]}}.

    py -3.12 sc4_set_cover.py --compare <whole>/cover.json <set>/cover.json [--set sc4_install_set.json]

prints the lines the whole install reaches and the set does not (per file), and a greedy pick of buildings that
would cover them.

    NODE_V8_COVERAGE=<dirA> node <script converting the whole install>; NODE_V8_COVERAGE=<dirB> ... the set
    py -3.12 sc4_set_cover.py --v8 <dirA> <dirB> sc4web.js

the same comparison for the page's converter (V8 block coverage, lines with a byte that ran). Evidence only: the suite
does not run this. Results of 2026-11-20: verify/suitespeed/RESULTS.md.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
WATCH = [os.path.normcase(os.path.join(TOOLS, "sc4conv")), os.path.normcase(os.path.join(TOOLS, "bldimport"))]


def trace_run(a):
    sys.path.insert(0, os.path.join(TOOLS, "sc4conv"))
    import sc4conv as S                      # noqa: E402
    mon = sys.monitoring
    tid = mon.PROFILER_ID if mon.get_tool(mon.PROFILER_ID) is None else 4
    mon.use_tool_id(tid, "sc4_set_cover")
    glob, per, cur = set(), {}, [None]
    watch = {}

    def on_line(code, line):
        f = code.co_filename
        w = watch.get(f)
        if w is None:
            nf = os.path.normcase(os.path.abspath(f))
            w = watch[f] = next((os.path.relpath(nf, os.path.normcase(TOOLS)).replace("\\", "/")
                                 for d in WATCH if nf.startswith(d + os.sep)), False)
        if w:
            (per.setdefault(cur[0], set()) if cur[0] else glob).add((w, line))
        return mon.DISABLE

    mon.register_callback(tid, mon.events.LINE, on_line)
    mon.set_events(tid, mon.events.LINE)
    orig = S.write_building

    def wb(idx, b, *rest):
        cur[0] = b["name"]
        mon.restart_events()
        try:
            return orig(idx, b, *rest)
        finally:
            cur[0] = None
            mon.restart_events()
    S.write_building = wb
    argv = ["sc4conv.py", a.install, "--out", os.path.join(a.out, "conv")]
    if a.growables:
        argv.append("--growables")
    if a.only:
        argv += ["--only", a.only]
    rc = S.main(argv)
    mon.set_events(tid, 0)
    mon.free_tool_id(tid)
    json.dump({"global": sorted(glob), "buildings": {k: sorted(v) for k, v in sorted(per.items())}},
              open(os.path.join(a.out, "cover.json"), "w"), indent=0)
    print("sc4_set_cover: %d global lines, %d buildings, exit %s" % (len(glob), len(per), rc))
    return rc


def compare(a):
    W, Sx = json.load(open(a.compare[0])), json.load(open(a.compare[1]))
    def allof(j):
        s = {tuple(x) for x in j["global"]}
        for v in j["buildings"].values():
            s |= {tuple(x) for x in v}
        return s
    wa, sa = allof(W), allof(Sx)
    miss = wa - sa
    print("whole: %d lines, set: %d lines, reached by the whole install and not the set: %d" % (len(wa), len(sa), len(miss)))
    byf = {}
    for f, ln in sorted(miss):
        byf.setdefault(f, []).append(ln)
    for f, ls in byf.items():
        print("  %s: %s" % (f, ",".join(map(str, ls))))
    # greedy: which whole-install buildings cover the missing per-building lines
    left = set(miss)
    cand = {k: {tuple(x) for x in v} & left for k, v in W["buildings"].items()}
    while left:
        k = max(cand, key=lambda c: len(cand[c] & left))
        got = cand[k] & left
        if not got:
            break
        print("  + %-44s covers %d: %s" % (k, len(got), ", ".join("%s:%d" % g for g in sorted(got)[:8])))
        left -= got
    if left:
        print("  not reached by any one building (run-level lines): %d" % len(left))


def v8_lines(cov_dir, name):
    """NODE_V8_COVERAGE=<dir> output -> the set of lines of <name> (e.g. sc4web.js) that ran (block coverage: a byte
    runs when the innermost range holding it has count > 0)."""
    import glob
    import urllib.parse
    import urllib.request
    runs, src = None, None
    for p in glob.glob(os.path.join(cov_dir, "*.json")):
        for s in json.load(open(p, encoding="utf-8"))["result"]:
            if not s["url"].lower().endswith("/" + name.lower()):
                continue
            if src is None:
                src = open(urllib.request.url2pathname(urllib.parse.urlparse(s["url"]).path), encoding="utf-8").read()
                runs = bytearray(len(src) + 1)
            # ranges: the first of each function is the whole function; nested ranges override (V8 block coverage)
            loc = bytearray(len(src) + 1)
            rs = sorted((r for f in s["functions"] for r in f["ranges"]), key=lambda r: (r["startOffset"], -r["endOffset"]))
            for r in rs:
                a, b = r["startOffset"], min(r["endOffset"], len(src))
                loc[a:b] = (b"\x01" if r["count"] > 0 else b"\x00") * (b - a)
            for i, v in enumerate(loc):       # one process's coverage, or-ed into the others'
                if v:
                    runs[i] = 1
    if src is None:
        return set(), 0
    lines, ln = set(), 1
    for i, ch in enumerate(src):
        if runs[i] and not ch.isspace():
            lines.add(ln)
        if ch == "\n":
            ln += 1
    return lines, ln


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v8", nargs=3, metavar=("WHOLE_DIR", "SET_DIR", "FILE"),
                    help="compare NODE_V8_COVERAGE output of sc4_install.mjs whole vs --set for one script")
    ap.add_argument("--install")
    ap.add_argument("--out")
    ap.add_argument("--growables", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--compare", nargs=2)
    a = ap.parse_args()
    if a.v8:
        w, _ = v8_lines(a.v8[0], a.v8[2])
        st, _ = v8_lines(a.v8[1], a.v8[2])
        miss = sorted(w - st)
        print("%s: %d lines ran on the whole install, %d with the set, %d only on the whole: %s"
              % (a.v8[2], len(w), len(st), len(miss), ",".join(map(str, miss))))
        return 0
    if a.compare:
        return compare(a)
    os.makedirs(a.out, exist_ok=True)
    return trace_run(a)


if __name__ == "__main__":
    sys.exit(main())
