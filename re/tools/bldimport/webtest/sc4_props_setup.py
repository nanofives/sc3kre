#!/usr/bin/env python3
r"""sc4_props_setup.py - task sc4props (2026-11-19g): the Python side of sc4_props.mjs (SC4 lot props baked in).

    py -3.12 re/tools/bldimport/webtest/sc4_props_setup.py --sc4 <JMyers plugin folder> --deps <BSC Common
          Dependencies Pack .zip> --game <tree> --out <dir>

Writes (all local: the pack and the dependency pack are the owner's downloads, never in git or docs):
  src\sc4props\    sc4conv.py <sc4> --deps <zip> (props baked into <stem>_props.obj, sc4prop_*.png); the layout of
                   golden_setup.py, so pagetest.mjs --case sc4props compares the page's install with it
  noprops\         the same with --no-props (models.json only is compared: x_sc4.props.on false, file = <stem>.obj)
  rerun_old.json   src\sc4props\models.json after edits as the page saves them (JSON.stringify, whole floats as ints): the
                   props switched off on the first building that has them, on on the first that has none placed
  rerun\           sc4conv.py run again over rerun_old.json (the merge keeps the player's switch)
  py\sc4props\folder\, out\   src\sc4props\ through `bldimport.py pack` (the enabled buildings with their props)
  depscache\       the dependency index + fetched props (deps.DepsIndex), so the run does not touch %LOCALAPPDATA%
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


def ints(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, list):
        return [ints(x) for x in v]
    if isinstance(v, dict):
        return {k: ints(x) for k, x in v.items()}
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sc4", required=True)
    ap.add_argument("--deps", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cache = os.path.join(a.out, "depscache")
    base = [SC4CONV, a.sc4, "--deps", a.deps, "--deps-cache", cache]
    conv = os.path.join(a.out, "src", "sc4props")
    pyd = os.path.join(a.out, "py", "sc4props")
    for sub in (conv, pyd, os.path.join(a.out, "noprops"), os.path.join(a.out, "rerun")):
        shutil.rmtree(sub, ignore_errors=True)
    os.makedirs(pyd)
    out = run(base + ["--out", conv], os.path.join(a.out, "sc4conv_log.txt"))
    print("\n".join(ln for ln in out.splitlines() if ln.startswith(("deps:", "Lot props", "Props not", "110 models"))))
    run(base + ["--out", os.path.join(a.out, "noprops"), "--no-props"], os.path.join(a.out, "sc4conv_noprops_log.txt"))
    j = json.load(open(os.path.join(conv, "models.json"), encoding="utf-8"))
    ms = j["models"]
    off = next(m for m in ms if (m["x_sc4"].get("props") or {}).get("on"))
    off["x_sc4"]["props"]["on"] = False
    on = next((m for m in ms if m["x_sc4"].get("props") and not m["x_sc4"]["props"]["placed"]), None)
    if on is not None:
        on["x_sc4"]["props"]["on"] = True       # nothing placed: the converter keeps it off
    rd = os.path.join(a.out, "rerun")
    os.makedirs(rd)
    text = json.dumps(ints(j), indent=2, ensure_ascii=False) + "\n"
    open(os.path.join(a.out, "rerun_old.json"), "w", encoding="utf-8", newline="\n").write(text)
    open(os.path.join(rd, "models.json"), "w", encoding="utf-8", newline="\n").write(text)
    run(base + ["--out", rd], os.path.join(a.out, "sc4conv_rerun_log.txt"))
    print("rerun: props switched off on %s, on asked for %s" % (off["x_sc4"]["exemplar"],
                                                                on["x_sc4"]["exemplar"] if on else "-"))
    shutil.copytree(conv, os.path.join(pyd, "folder"))
    out = run([BLDIMPORT, "pack", os.path.join(pyd, "folder"), "--game", a.game, "--out", os.path.join(pyd, "out")],
              os.path.join(a.out, "pack_log.txt"))
    print("pack: " + (out.strip().splitlines()[-1] if out.strip() else "done"))


if __name__ == "__main__":
    main()
