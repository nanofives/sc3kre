#!/usr/bin/env python3
r"""sc4_install_setup.py - task sc4civ (2026-11-19l): the Python side of sc4_install.mjs (the player's SC4 install).

    py -3.12 re/tools/bldimport/webtest/sc4_install_setup.py --install "<SimCity 4 install folder>" --game <tree> --out <dir>

The install is EA's game, read in place (never copied): what is written under <dir> stays on this PC.
  conv\            sc4conv.py <install> --out conv: SC4's civic buildings, parks, rewards and landmarks
  notes.json       its report lines (--notes-json)
  rerun\old.json   conv\models.json with three edits, as the page saves it (JSON, indent 2): the Mayor's House reward's
                   population 1234 and switched off, the Gazebo's base fountain
  rerun\models.json  sc4conv.py run again into a copy of conv\ holding old.json as its models.json
  sub\conv\        sc4conv.py --only <4 buildings: a police station, a park, a reward, a landmark>
  sub\folder\, sub\out\  bldimport.py pack --out of sub\conv (the frames + game files the page must equal)
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
SUBSET = "CV24X24_4carLocalPrecinct_030C,PZ11x9x11_Gazebo_1DDE,RW16x14_MayorsHouse_031F,Lm16x16_Big Ben_04CD"


def run(args):
    print("  $ " + " ".join(args[1:3]) + " ...", flush=True)
    r = subprocess.run(args)
    if r.returncode:
        raise SystemExit("exit %d: %s" % (r.returncode, " ".join(args)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    py = sys.executable
    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(a.out)
    conv = os.path.join(a.out, "conv")
    run([py, SC4CONV, a.install, "--out", conv, "--notes-json", os.path.join(a.out, "notes.json")])
    # the rerun with the player's edits
    rr = os.path.join(a.out, "rerun")
    shutil.copytree(conv, rr)
    j = json.load(open(os.path.join(conv, "models.json"), encoding="utf-8"))
    for m in j["models"]:
        if m["x_sc4"]["exemplar"] == "RW16x14_MayorsHouse_031F":
            m["population"], m["enabled"] = 1234, False
        if m["x_sc4"]["exemplar"] == "PZ11x9x11_Gazebo_1DDE":
            m["base"] = "fountain"
    txt = json.dumps(j, indent=2, ensure_ascii=False) + "\n"
    open(os.path.join(rr, "old.json"), "w", encoding="utf-8", newline="\n").write(txt)
    open(os.path.join(rr, "models.json"), "w", encoding="utf-8", newline="\n").write(txt)
    run([py, SC4CONV, a.install, "--out", rr])
    # the subset, packed
    sub = os.path.join(a.out, "sub", "conv")
    run([py, SC4CONV, a.install, "--out", sub, "--only", SUBSET])
    folder = os.path.join(a.out, "sub", "folder")
    shutil.copytree(sub, folder)
    run([py, BLDIMPORT, "pack", folder, "--game", a.game, "--out", os.path.join(a.out, "sub", "out")])
    print("sc4_install_setup: done")


if __name__ == "__main__":
    main()
