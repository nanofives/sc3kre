#!/usr/bin/env python3
r"""sc4_lottex_setup.py - task sc4lottex (2026-11-20): the Python side of sc4_lottex.mjs (SC4 lot textures drawn on the
ground under the converted building).

    py -3.12 re/tools/bldimport/webtest/sc4_lottex_setup.py --sc4 <JMyers plugin folder> --deps <BSC Common
          Dependencies Pack .zip> --install <SimCity 4 folder> --game <tree> --out <dir>

Writes (all local: the download, the dependency pack and EA's install are the owner's, never in git or docs):
  src\<case>\     sc4conv.py over the four source sets: dl (the download alone), bsc (+ --deps), inst (+ --sc4), both
  notex\          both sources with --no-textures (models.json is compared: x_sc4.textures.on false, no _lot file named)
  rerun_old.json  src\both\models.json after edits as the page saves them (JSON.stringify, whole floats as ints):
                  building A textures off (its file <stem>_props.obj), building B props off and enabled (its file
                  <stem>_lot.obj: the house and the textures without props), building C (texture rows, nothing drawn)
                  textures asked on (stays off), every other building off
  rerun\          sc4conv.py run again over rerun_old.json (the merge keeps the player's two switches)
  py\rerun\folder\, out\   rerun\ through `bldimport.py pack` (A and B: one OBJ without the ground art, one with it alone)
  depscache\      the dependency index (deps.DepsIndex), so the run does not touch %LOCALAPPDATA%
  counts.json     per case the report lines "Lot props", "Lot textures", "Textures not found", for RESULTS
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
KEEP = ("Lot props", "Lot textures", "Textures not found")


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
    ap.add_argument("--install", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cache = os.path.join(a.out, "depscache")
    deps = ["--deps", a.deps, "--deps-cache", cache]
    cases = {"dl": [], "bsc": deps, "inst": ["--sc4", a.install], "both": deps + ["--sc4", a.install]}
    counts = {}
    for case, extra in cases.items():
        conv = os.path.join(a.out, "src", case)
        shutil.rmtree(conv, ignore_errors=True)
        out = run([SC4CONV, a.sc4, "--out", conv] + extra, os.path.join(a.out, "sc4conv_%s_log.txt" % case))
        counts[case] = [ln for ln in out.splitlines() if ln.startswith(KEEP)]
        print(case + ":\n  " + "\n  ".join(ln[:300] for ln in counts[case]))
    json.dump(counts, open(os.path.join(a.out, "counts.json"), "w", encoding="utf-8"), indent=1)
    both = cases["both"]
    nt = os.path.join(a.out, "notex")
    shutil.rmtree(nt, ignore_errors=True)
    run([SC4CONV, a.sc4, "--out", nt, "--no-textures"] + both, os.path.join(a.out, "sc4conv_notex_log.txt"))
    j = json.load(open(os.path.join(a.out, "src", "both", "models.json"), encoding="utf-8"))
    ms = j["models"]
    on = [m for m in ms if (m["x_sc4"].get("textures") or {}).get("on") and (m["x_sc4"].get("props") or {}).get("on")]
    A, B = on[0], on[1]
    A["x_sc4"]["textures"]["on"] = False
    B["x_sc4"]["props"]["on"] = False
    C = next((m for m in ms if m["x_sc4"].get("textures") and not m["x_sc4"]["textures"]["ground"]["drawn"]), None)
    if C is not None:
        C["x_sc4"]["textures"]["on"] = True     # nothing drawn: the converter keeps it off
    for m in ms:
        m["enabled"] = m is A or m is B
    rd = os.path.join(a.out, "rerun")
    shutil.rmtree(rd, ignore_errors=True)
    os.makedirs(rd)
    text = json.dumps(ints(j), indent=2, ensure_ascii=False) + "\n"
    open(os.path.join(a.out, "rerun_old.json"), "w", encoding="utf-8", newline="\n").write(text)
    open(os.path.join(rd, "models.json"), "w", encoding="utf-8", newline="\n").write(text)
    run([SC4CONV, a.sc4, "--out", rd] + both, os.path.join(a.out, "sc4conv_rerun_log.txt"))
    got = {m["x_sc4"]["exemplar"]: m["file"] for m in json.load(open(os.path.join(rd, "models.json"), encoding="utf-8"))["models"]}
    print("rerun: textures off on %s -> %s, props off on %s -> %s, textures asked on for %s" % (
        A["x_sc4"]["exemplar"], got[A["x_sc4"]["exemplar"]], B["x_sc4"]["exemplar"], got[B["x_sc4"]["exemplar"]],
        C["x_sc4"]["exemplar"] if C else "-"))
    pyd = os.path.join(a.out, "py", "rerun")
    shutil.rmtree(pyd, ignore_errors=True)
    os.makedirs(pyd)
    shutil.copytree(rd, os.path.join(pyd, "folder"))
    out = run([BLDIMPORT, "pack", os.path.join(pyd, "folder"), "--game", a.game, "--out", os.path.join(pyd, "out")],
              os.path.join(a.out, "pack_rerun_log.txt"))
    print("pack: " + (out.strip().splitlines()[-1] if out.strip() else "done"))


if __name__ == "__main__":
    main()
