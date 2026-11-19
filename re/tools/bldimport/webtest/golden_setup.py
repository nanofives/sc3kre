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

Case ports (task airsea, 2026-11-19): make_testmodels.py --ports plus a .bld file, kinds airport / seaport; task plop
adds one landmark (obelisk_2x2) so the case also writes the plugin next to the overlay files.
Case landmarks (task plop, 2026-11-19): make_testmodels.py --landmarks plus a .bld file, kind landmark only (the plugin
in Apps/PlugIn/bldimport, no overlay file), one entry with a description.

Case sc4 (task sc4web, needs --sc4 <SC4 plugin folder>): src\sc4\ is sc4conv.py's output for that folder (the
models folder the Python route installs from), packed like the others. Also py\sc4\rerun_old.json (that models.json
after edits as the page saves them: JSON.stringify layout, whole floats as ints) and py\sc4\rerun\ (sc4conv.py run
again over it: the merge that keeps the player's edits). sc4_golden.mjs converts the SC4 .zip / folder in JS and
compares.
Task sc4diag (2026-11-19c): py\sc4\diagonal\models.json (sc4conv.py --diagonal: buildings set at 45 degrees treated as
any other) and py\sc4\pick_cases.json (sc4conv.pick_colours on made-up designs that mix diagonal and straight colours,
which the JMyers pack has none of).
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
SC4CONV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "sc4conv", "sc4conv.py")

BLD = [  # file, models.json extras
    ("Dupont House.bld", {}),                                             # auto: BAT.DAT art when the tree has it
    ("Garvey Plaza.bld", {"x_bld": {"art": "preview"}}),                    # preview, the BA look
    ("North Shore Cannery.bld", {"x_bld": {"art": "preview"}, "x_bldrender": {"style": "stock"}}),
    ("Hotel Splash.bld", {"x_bld": {"art": "preview"}, "x_bldrender": {"style": "stock_sharp"}}),
    ("Tutorial House.bld", {"class": 3300, "enabled": True}),             # category 0x217: class set by hand
    ("The Joneses.bld", {}),
]
LANDMARK_DESC = "Typed in the page, Córdoba"   # plop2: case landmarkdesc (cp1252 0xF3 in the game's text record)
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
    ap.add_argument("--cases", default="testmodels,bld,kenney,styles,ports,landmarks,landmarkdesc,civic")
    ap.add_argument("--sc4", help="SC4 plugin folder for case sc4 (task sc4web)")
    ap.add_argument("--bld1999", help="folder of 1999 Building Architect .bld files for case bld1999 (sc3compat-a)")
    ap.add_argument("--bldside", help="folder of .bld files + the bld_frames.ixf render_bld.ps1 wrote, for case bldside")
    a = ap.parse_args()
    cases = a.cases.split(",")
    src = os.path.join(a.out, "src")
    for c in cases:
        d = os.path.join(src, c)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        if c == "testmodels":
            subprocess.run([sys.executable, MAKE, d], check=True, capture_output=True)
        elif c == "civic":
            # task civmod: kinds civic and reward (make_testmodels.py --civmod: a police look 3x3, two 2x2 rewards, one
            # locked, a landmark, three refused entries): the plugins Apps/PlugIn/bldimport (+ bldimport_civic.ini) and
            # Apps/PlugIn/bldimport_rewards (.pin, .dat, bldimport_rewards.ini, bldimport_types.ini)
            subprocess.run([sys.executable, MAKE, "--civmod", d], check=True, capture_output=True)
        elif c == "ports":
            # task airsea: kinds airport / seaport (make_testmodels.py --ports: fuel depot 1x1 airport x5 copies,
            # container stack 1x1 + warehouse 2x2 seaport, two refused entries) + a .bld file as a 2x2 seaport
            subprocess.run([sys.executable, MAKE, "--ports", d], check=True, capture_output=True)
            j = json.load(open(os.path.join(d, "models.json"), encoding="utf-8"))
            shutil.copy2(os.path.join(a.game, "Buildings", "North Shore Cannery.bld"), d)
            j["models"].append({"file": "North Shore Cannery.bld", "name": "Cannery dock", "kind": "seaport",
                                "weight": 3, "enabled": True, "x_bld": {"art": "preview"}})
            # task plop: one landmark among the port buildings (overlay files + the plugin in one install)
            tmp = os.path.join(a.out, "tmp_landmarks")
            shutil.rmtree(tmp, ignore_errors=True)
            subprocess.run([sys.executable, MAKE, "--landmarks", tmp], check=True, capture_output=True)
            for f in ("obelisk_2x2.obj", "obelisk_2x2.mtl"):
                shutil.copy2(os.path.join(tmp, f), d)
            shutil.rmtree(tmp, ignore_errors=True)
            j["models"].append({"file": "obelisk_2x2.obj", "name": "Harbour obelisk", "kind": "landmark", "lot": [2, 2],
                                "weight": 1, "scale": 1.0, "rotate_deg": 0, "enabled": True})
            json.dump(j, open(os.path.join(d, "models.json"), "w"), indent=1)
        elif c in ("landmarks", "landmarkdesc"):
            # task plop: kind landmark (make_testmodels.py --landmarks: obelisk 2x2 with a description, pavilion 3x3,
            # a refused 5x5 and a refused kind ploppable) + a .bld file as a landmark
            # plop2 (2026-11-19): case landmarkdesc = the same models, entries in the order the page saves them (by file
            # name), and the obelisk's description as typed in the page's Description box (pagetest.mjs --edit-desc
            # blanks it, types it, installs from the page's own models.json and compares with this case's output)
            subprocess.run([sys.executable, MAKE, "--landmarks", d], check=True, capture_output=True)
            j = json.load(open(os.path.join(d, "models.json"), encoding="utf-8"))
            j["models"][0]["description"] = "Test monument, bldimport" if c == "landmarks" else LANDMARK_DESC
            shutil.copy2(os.path.join(a.game, "Buildings", "Garvey Plaza.bld"), d)
            j["models"].append({"file": "Garvey Plaza.bld", "name": "Garvey Plaza landmark", "kind": "landmark",
                                "weight": 1, "enabled": True, "x_bld": {"art": "preview"}})
            if c == "landmarkdesc":
                j["models"].sort(key=lambda e: e["file"].lower())
            json.dump(j, open(os.path.join(d, "models.json"), "w"), indent=1)
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
        elif c == "bld1999":
            # sc3compat-a: the 1999 BA's .bld files (model version 7, no id), no models.json: every entry comes from
            # the file (auto art; categories that are not house / shop / factory start disabled)
            if not a.bld1999:
                raise SystemExit("case bld1999 needs --bld1999 <folder of 1999 .bld files>")
            for f in sorted(os.listdir(a.bld1999)):
                if f.lower().endswith(".bld"):
                    shutil.copy2(os.path.join(a.bld1999, f), d)
        elif c == "bldside":
            # sc3compat-a: .bld files with the player's own BA render beside them (render_bld.ps1 -> bld_frames.ixf,
            # raw renderer output: random groups, new instances). auto art = the side IXF; one entry forced to preview.
            if not a.bldside:
                raise SystemExit("case bldside needs --bldside <folder with .bld files and bld_frames.ixf>")
            blds = sorted(f for f in os.listdir(a.bldside) if f.lower().endswith(".bld"))
            for f in blds + ["bld_frames.ixf"]:
                shutil.copy2(os.path.join(a.bldside, f), d)
            sys.path.insert(0, os.path.dirname(HERE))
            import bldfile as BF
            b = BF.read_bld(os.path.join(d, blds[0]))
            e = {"file": blds[0], "x_bld": {"art": "preview"}, "kind": "growable", "enabled": True,
                 "class": BF.suggest_class(b) or 3300, "name": b["name"]}
            json.dump({"sc3models": 1, "models": [e]}, open(os.path.join(d, "models.json"), "w"), indent=1)
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
        elif c == "sc4":
            if not a.sc4:
                raise SystemExit("case sc4 needs --sc4 <SC4 plugin folder>")
            with open(os.path.join(a.out, "sc4conv_log.txt"), "w", encoding="utf-8") as log:
                run([SC4CONV, a.sc4, "--out", d], log)
            # the rerun merge: edits as the page saves them (JSON.stringify, indent 2, 1.0 written as 1)
            j = json.load(open(os.path.join(d, "models.json"), encoding="utf-8"))
            ms = j["models"]
            ms[0]["weight"] = 5
            ms[1]["enabled"] = True
            ms[2]["x_bldrender"] = {"style": "baked_raw"}
            ms[3]["name"] = "Renamed in the page"
            ms[4]["lot"] = [2, 2]
            ms[5]["notes"] = "a note, é"

            def ints(v):
                if isinstance(v, float) and v.is_integer():
                    return int(v)
                if isinstance(v, list):
                    return [ints(x) for x in v]
                if isinstance(v, dict):
                    return {k: ints(x) for k, x in v.items()}
                return v
            rd = os.path.join(a.out, "py", "sc4", "rerun")
            shutil.rmtree(rd, ignore_errors=True)
            os.makedirs(rd)
            text = json.dumps(ints(j), indent=2, ensure_ascii=False) + "\n"
            open(os.path.join(a.out, "py", "sc4", "rerun_old.json"), "w", encoding="utf-8", newline="\n").write(text)
            open(os.path.join(rd, "models.json"), "w", encoding="utf-8", newline="\n").write(text)
            with open(os.path.join(a.out, "sc4conv_rerun_log.txt"), "w", encoding="utf-8") as log:
                run([SC4CONV, a.sc4, "--out", rd], log)
            # task sc4diag: --diagonal, and the colour pick on designs that mix diagonal and straight colours
            dd = os.path.join(a.out, "py", "sc4", "diagonal")
            shutil.rmtree(dd, ignore_errors=True)
            with open(os.path.join(a.out, "sc4conv_diagonal_log.txt"), "w", encoding="utf-8") as log:
                run([SC4CONV, a.sc4, "--out", dd, "--diagonal"], log)
            sys.path.insert(0, os.path.dirname(SC4CONV))
            import sc4conv
            groups = [[["a", 0], ["b", 1], ["c", 0]], [["d", 1], ["e", 1]], [["f", 1], ["g", 0], ["h", 1], ["i", 0]],
                      [["j", 0]], [["k", 1]], [["l", 0], ["m", 1]], [["n", 1], ["o", 1], ["p", 0]],
                      [["q", 0], ["r", 0], ["s", 1], ["t", 1], ["u", 1], ["v", 0], ["w", 1], ["x", 1]]]
            picked = sc4conv.pick_colours(groups, lambda m: m[1] == 1)
            json.dump({"groups": groups, "picked": [p[0] if p else None for p in picked]},
                      open(os.path.join(a.out, "py", "sc4", "pick_cases.json"), "w"), indent=1)
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
        for sub in ("folder", "out"):
            shutil.rmtree(os.path.join(dst, sub), ignore_errors=True)
        os.makedirs(dst, exist_ok=True)
        shutil.copytree(os.path.join(src, c), os.path.join(dst, "folder"))
        with open(os.path.join(dst, "log.txt"), "w", encoding="utf-8") as log:
            run([TOOL, "pack", os.path.join(dst, "folder"), "--game", a.game, "--out", os.path.join(dst, "out")], log)
        print("%s: %s" % (c, open(os.path.join(dst, "log.txt"), encoding="utf-8").read().strip()))


if __name__ == "__main__":
    main()
