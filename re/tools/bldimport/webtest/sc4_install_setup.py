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
  grow\, grow_notes.json  sc4conv.py --growables --only <GROW_SUBSET> (task sc4ci: SC4's own shops, offices, industry)

--set <sc4_install_set.json> (task suitespeed, 2026-11-20): conv\ and rerun\ hold the install set only (sc4conv.py
--only <its exemplars>), the suite's normal mode. Without it: the whole install (SUITE_DEEP=1, releases).
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
# task sc4ci (2026-11-20): SC4's own shops, offices, industry and farms (--growables), a subset: one of each purpose, a
# 4x4 dirty factory (class 9100, SC3 has no 4x4 dirty base), a 5x5 factory and a 4x4 farm (no class), a police station
GROW_SUBSET = ("CS$14x14_1ChiSmallShop1_05CD,CS$$14x22_4ChiMediumStore5_05B9,CO$$$44x26_6ChiOfficeBldg9_0507,"
               "ID30x30_1DirtyAnchor5_07DE,ID64x46_3DirtyAnchor11_07E4,IM28x74_3ManuOut14_0829,IH28x28_1HTAnchor3_082D,"
               "IR30x24_1Farm1_084D,IR60x50_3Farm2_084E,CV24X24_4carLocalPrecinct_030C")


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
    ap.add_argument("--set", help="sc4_install_set.json: convert only its buildings (the suite's normal mode)")
    a = ap.parse_args()
    only = []
    if a.set:
        st = json.load(open(a.set, encoding="utf-8"))
        names = [b["exemplar"] for b in st["buildings"]]
        miss = [x for x in SUBSET.split(",") if x not in names]
        if miss:
            raise SystemExit("the install set must hold the packed subset: %s missing" % ", ".join(miss))
        only = ["--only", ",".join(names)]
    py = sys.executable
    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(a.out)
    conv = os.path.join(a.out, "conv")
    run([py, SC4CONV, a.install, "--out", conv, "--notes-json", os.path.join(a.out, "notes.json")] + only)
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
    run([py, SC4CONV, a.install, "--out", rr] + only)
    # the subset, packed
    sub = os.path.join(a.out, "sub", "conv")
    run([py, SC4CONV, a.install, "--out", sub, "--only", SUBSET])
    folder = os.path.join(a.out, "sub", "folder")
    shutil.copytree(sub, folder)
    run([py, BLDIMPORT, "pack", folder, "--game", a.game, "--out", os.path.join(a.out, "sub", "out")])
    # task sc4ci: the growables subset
    run([py, SC4CONV, a.install, "--growables", "--only", GROW_SUBSET, "--out", os.path.join(a.out, "grow"),
         "--notes-json", os.path.join(a.out, "grow_notes.json")])
    print("sc4_install_setup: done")


if __name__ == "__main__":
    main()
