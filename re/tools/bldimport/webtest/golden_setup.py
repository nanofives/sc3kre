#!/usr/bin/env python3
r"""golden_setup.py - task bldweb (2026-11-18d): the Python side of the page's golden test.

    py -3.12 re/tools/bldimport/webtest/golden_setup.py --game <tree> --kits <stage\kits> --out <dir>

Writes into <dir>:
  src\<case>\            the model folders, untouched (the page's input): testmodels (make_testmodels.py), bld (.bld
                         files of <tree>\Buildings with a models.json that mixes BAT.DAT art, preview art and styles),
                         kenney (3 CC0 Kenney buildings, one per zone)
  py\<case>\folder\      a copy of src\<case> after `bldimport.py pack --out` (sc3build\ids.json + the render cache)
  py\<case>\out\         the files pack --out wrote (game-root relative)
  py\<case>\log.txt      the tool's report
golden.mjs runs bldweb.js over src\<case> against the same game and compares every byte.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "bldimport.py")
MAKE = os.path.join(os.path.dirname(HERE), "make_testmodels.py")

BLD = [  # file, models.json extras
    ("Dupont House.bld", {}),                                             # auto: BAT.DAT art when the tree has it
    ("Garvey Plaza.bld", {"x_bld": {"art": "preview"}}),                    # preview, the BA look
    ("North Shore Cannery.bld", {"x_bld": {"art": "preview"}, "x_bldrender": {"style": "stock"}}),
    ("Hotel Splash.bld", {"x_bld": {"art": "preview"}, "x_bldrender": {"style": "stock_sharp"}}),
    ("Tutorial House.bld", {"class": 3300, "enabled": True}),             # category 0x217: class set by hand
    ("The Joneses.bld", {}),
]
KENNEY = [  # kit, file, name, class, lot, scale
    ("suburban", "building-type-a.obj", "Kenney house A", 3300, 1, 9.0),
    ("commercial", "building-a.obj", "Kenney shop A", 5100, 1, 12.0),
    ("industrial", "building-a.obj", "Kenney works A", 8700, 2, 12.0),
]


def run(args, log):
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True)
    log.write(p.stdout + p.stderr)
    if p.returncode:
        raise SystemExit("failed: %s\n%s%s" % (" ".join(args), p.stdout, p.stderr))
    return p.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--kits", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cases", default="testmodels,bld,kenney,styles")
    a = ap.parse_args()
    cases = a.cases.split(",")
    src = os.path.join(a.out, "src")
    for c in cases:
        d = os.path.join(src, c)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        if c == "testmodels":
            subprocess.run([sys.executable, MAKE, d], check=True, capture_output=True)
        elif c == "bld":
            models = []
            for f, extra in BLD:
                shutil.copy2(os.path.join(a.game, "Buildings", f), d)
                if extra:
                    e = {"file": f}
                    e.update(extra)
                    models.append(e)
            # entries with only some keys: bldimport fills the rest from the file (read_models merges only unlisted
            # .bld files, so the listed ones carry lot / class / kind / enabled themselves)
            sys.path.insert(0, os.path.dirname(HERE))
            import bldfile as BF
            for e in models:
                b = BF.read_bld(os.path.join(d, e["file"]))
                e.setdefault("kind", "growable")
                e.setdefault("enabled", True)
                e.setdefault("class", BF.suggest_class(b))
                e.setdefault("name", b["name"])
            json.dump({"sc3models": 1, "models": models}, open(os.path.join(d, "models.json"), "w"), indent=1)
        elif c == "kenney":
            models = []
            tex = os.path.join(d, "Textures")
            os.makedirs(tex)
            for kit, f, name, cls, lot, scale in KENNEY:
                base = os.path.join(a.kits, kit, "Models", "OBJ format")
                stem = os.path.splitext(f)[0]
                new = "%s_%s" % (kit, stem)
                obj = open(os.path.join(base, f), encoding="utf-8").read()
                obj = obj.replace("mtllib %s.mtl" % stem, "mtllib %s.mtl" % new)
                open(os.path.join(d, new + ".obj"), "w", encoding="utf-8", newline="\n").write(obj)
                mtl = open(os.path.join(base, stem + ".mtl"), encoding="utf-8").read()
                mtl = mtl.replace("Textures/colormap.png", "Textures/%s_colormap.png" % kit)
                open(os.path.join(d, new + ".mtl"), "w", encoding="utf-8", newline="\n").write(mtl)
                shutil.copy2(os.path.join(base, "Textures", "colormap.png"), os.path.join(tex, "%s_colormap.png" % kit))
                models.append({"file": new + ".obj", "name": name, "kind": "growable", "class": cls, "lot": [lot, lot],
                               "weight": 2, "scale": scale, "rotate_deg": 0, "enabled": True})
            json.dump({"sc3models": 1, "models": models}, open(os.path.join(d, "models.json"), "w"), indent=1)
        elif c == "styles":
            # every render style and option bldrender has: clean (screen sun), stock_sharp (native zoom 4), rotation,
            # no shadow, no ground, a cell size, a model wider than its lot
            subprocess.run([sys.executable, MAKE, d], check=True, capture_output=True)
            kit = os.path.join(a.kits, "industrial", "Models", "OBJ format")
            obj = open(os.path.join(kit, "building-c.obj"), encoding="utf-8").read().replace("mtllib building-c.mtl", "mtllib works_c.mtl")
            open(os.path.join(d, "works_c.obj"), "w", encoding="utf-8", newline="\n").write(obj)
            os.makedirs(os.path.join(d, "Textures"), exist_ok=True)
            shutil.copy2(os.path.join(kit, "building-c.mtl"), os.path.join(d, "works_c.mtl"))
            shutil.copy2(os.path.join(kit, "Textures", "colormap.png"), os.path.join(d, "Textures", "colormap.png"))
            models = [
                {"file": "house_tex.obj", "name": "Clean house", "class": 3300, "lot": [1, 1], "weight": 3, "x_bldrender": {"style": "clean"}},
                {"file": "block_2x2.obj", "name": "Sharp block", "class": 3900, "lot": [2, 2], "weight": 1, "rotate_deg": 90,
                 "x_bldrender": {"style": "stock_sharp"}},
                {"file": "house_plain.obj", "name": "Flat house", "class": 3100, "lot": [1, 1], "weight": 1, "rotate_deg": 45, "scale": 1.3,
                 "x_bldrender": {"style": "clean", "shadow": False, "ground": "none"}},
                {"file": "works_c.obj", "name": "Works C", "class": 8100, "lot": [1, 1], "weight": 5, "scale": 9.5, "rotate_deg": 180,
                 "x_bldrender": {"cell_m": 15}},
                {"file": "missing.obj", "name": "Not here", "class": 3300, "lot": [1, 1]},
                {"file": "house_tex.obj.bak", "name": "Bad ext", "class": 3300},
            ]
            json.dump({"sc3models": 1, "models": models}, open(os.path.join(d, "models.json"), "w"), indent=1)
    for c in cases:
        dst = os.path.join(a.out, "py", c)
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(os.path.join(src, c), os.path.join(dst, "folder"))
        with open(os.path.join(dst, "log.txt"), "w", encoding="utf-8") as log:
            run([TOOL, "pack", os.path.join(dst, "folder"), "--game", a.game, "--out", os.path.join(dst, "out")], log)
        print("%s: %s" % (c, open(os.path.join(dst, "log.txt"), encoding="utf-8").read().strip()))


if __name__ == "__main__":
    main()
