#!/usr/bin/env python3
r"""sc4_baseprops_setup.py - task sc4baseprops (2026-11-19): the Python side of sc4_baseprops.mjs (SimCity 4's own props
from the player's install as one more prop source for a download).

    py -3.12 re/tools/bldimport/webtest/sc4_baseprops_setup.py --sc4 <JMyers plugin folder> --deps <BSC Common
          Dependencies Pack .zip> --install <SimCity 4 folder> --game <tree> --out <dir>

Writes (all local: the download, the dependency pack and EA's install are the owner's, never in git or docs):
  src\sc4baseprops\       sc4conv.py <sc4> --deps <zip> --sc4 <install>  (both sources)
  src\sc4baseprops_inst\  sc4conv.py <sc4> --sc4 <install>               (the install alone; pagetest.mjs --case
                          sc4baseprops_inst compares the page's install with it)
  py\<case>\folder\, out\ each through `bldimport.py pack` (the enabled buildings with their props)
  depscache\              the dependency index + fetched props (deps.DepsIndex), so the run does not touch %LOCALAPPDATA%
  counts.json             the "Lot props" line of each run, for RESULTS
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
SC4CONV = os.path.join(TOOLS, "sc4conv", "sc4conv.py")
BLDIMPORT = os.path.join(TOOLS, "bldimport", "bldimport.py")


def run(args, log):
    r = subprocess.run([sys.executable] + args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    open(log, "w", encoding="utf-8").write(r.stdout + r.stderr)
    if r.returncode:
        print(r.stdout[-3000:] + r.stderr[-3000:])
        raise SystemExit("%s failed (exit %d)" % (os.path.basename(args[0]), r.returncode))
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sc4", required=True)
    ap.add_argument("--deps", required=True)
    ap.add_argument("--install", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cache = os.path.join(a.out, "depscache")
    runs = {"sc4baseprops": ["--deps", a.deps, "--deps-cache", cache, "--sc4", a.install],
            "sc4baseprops_inst": ["--sc4", a.install]}
    counts = {}
    for case, extra in runs.items():
        conv = os.path.join(a.out, "src", case)
        pyd = os.path.join(a.out, "py", case)
        for sub in (conv, pyd):
            shutil.rmtree(sub, ignore_errors=True)
        os.makedirs(pyd)
        out = run([SC4CONV, a.sc4, "--out", conv] + extra, os.path.join(a.out, "sc4conv_%s_log.txt" % case))
        keep = [ln for ln in out.splitlines() if ln.startswith(("deps:", "SimCity 4 install", "Lot props", "Props not"))]
        print(case + ":\n  " + "\n  ".join(ln[:300] for ln in keep))
        counts[case] = keep
        shutil.copytree(conv, os.path.join(pyd, "folder"))
        out = run([BLDIMPORT, "pack", os.path.join(pyd, "folder"), "--game", a.game, "--out", os.path.join(pyd, "out")],
                  os.path.join(a.out, "pack_%s_log.txt" % case))
        print("  pack: " + (out.strip().splitlines()[-1] if out.strip() else "done"))
    json.dump(counts, open(os.path.join(a.out, "counts.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
