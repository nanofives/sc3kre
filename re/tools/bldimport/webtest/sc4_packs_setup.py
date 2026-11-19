#!/usr/bin/env python3
r"""sc4_packs_setup.py - task sc4pass2 (2026-11-19f): the Python side of sc4_packs.mjs (more SimCity 4 packs).

    py -3.12 re/tools/bldimport/webtest/sc4_packs_setup.py --packs <folder with the SC4 .zip files> --game <tree> --out <dir>

The packs (the owner's downloads, never in git or docs; stage\st_packs\sc4\):
  goc    Global Office Center.zip                   a tall office tower, its views in tiles, growable + ploppable +
                                                    landmark lots, text exemplars
  diego  DiegoDLGrowablePack2019_Vanilla_DN.zip     23 lots + descriptions, every model a separate download
  im     I-M manufacturers lots.zip                 6 lots on a blank placeholder model, SC4's own buildings as props

Writes under <dir>:
  <key>\src\            the zip unpacked (Python's zipfile)
  <key>\conv\           sc4conv.py's output for it (nothing for a lot-only pack: sc4conv exits 3)
  <key>\notes.json      sc4conv.py --notes-json (the report lines the page must show, the buildings without a model)
  <key>\exit.txt        sc4conv.py's exit code
  <key>\exemplars.json  every exemplar of the pack as exemplar.parse_exemplar reads it (text and binary forms)
  goc\folder\, goc\out\ bldimport.py pack --out of goc\conv (the frames + game files the page must equal)
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
SC4CONV = os.path.join(TOOLS, "sc4conv", "sc4conv.py")
BLDIMPORT = os.path.join(TOOLS, "bldimport", "bldimport.py")
PACKS = {"goc": "Global Office Center.zip", "diego": "DiegoDLGrowablePack2019_Vanilla_DN.zip",
         "im": "I-M manufacturers lots.zip"}


def jval(v):
    if isinstance(v, float):
        return {"f": repr(v)} if not math.isfinite(v) else v
    if isinstance(v, list):
        return [jval(x) for x in v]
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packs", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(TOOLS, "sc4conv"))
    import catalog as C
    import dbpf as D
    for key, zname in PACKS.items():
        z = os.path.join(a.packs, zname)
        if not os.path.isfile(z):
            raise SystemExit("missing pack %s" % z)
        d = os.path.join(a.out, key)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        with zipfile.ZipFile(z) as zf:
            for info in zf.infolist():
                # the page's zip reader decodes a name without the UTF-8 flag as latin-1; do the same, so both
                # routes see the same file names (zipfile's default is cp437)
                name = info.filename
                if not info.flag_bits & 0x800:
                    name = name.encode("cp437").decode("latin-1")
                if name.endswith("/"):
                    continue
                p = os.path.join(d, "src", *name.split("/"))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "wb") as fh:
                    fh.write(zf.read(info))
        conv = os.path.join(d, "conv")
        r = subprocess.run([sys.executable, SC4CONV, os.path.join(d, "src"), "--out", conv,
                            "--notes-json", os.path.join(d, "notes.json")], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        open(os.path.join(d, "sc4conv_log.txt"), "w", encoding="utf-8").write(r.stdout + r.stderr)
        open(os.path.join(d, "exit.txt"), "w").write(str(r.returncode))
        if r.returncode not in (0, 3):
            print(r.stdout + r.stderr)
            raise SystemExit("sc4conv.py failed on %s (exit %d)" % (key, r.returncode))
        idx = C.Index(os.path.join(d, "src"))
        ex = []
        for k in idx.of_type(D.T_EXEMPLAR):
            raw = idx.read(k)
            try:
                e = idx.exemplar(k)
            except Exception as err:      # noqa: BLE001 - recorded, the page must fail on the same ones
                ex.append({"tgi": ["%08X" % x for x in k], "error": type(err).__name__})
                continue
            ex.append({"tgi": ["%08X" % x for x in k], "kind": e["kind"], "form": raw[:4].decode("latin-1"),
                       "parent": list(e["parent"]),
                       "props": [[pid, e["props"][pid][0], jval(e["props"][pid][1])] for pid in e["order"]]})
        json.dump(ex, open(os.path.join(d, "exemplars.json"), "w", encoding="utf-8"), indent=0)
        print("%s: sc4conv exit %d, %d exemplars (%d text), %s" % (
            key, r.returncode, len(ex), sum(1 for e in ex if e.get("form") == "EQZT"),
            "%d files converted" % len(os.listdir(conv)) if os.path.isdir(conv) else "nothing written"))
    # the tower through bldimport (render + pack), as golden_setup.py does for its cases
    g = os.path.join(a.out, "goc")
    # plop2 (2026-11-19): the rerun keeps the player's edits on an SC4 landmark entry. models.json as the page saves it
    # (JSON.stringify, indent 2, whole floats as ints) with the ploppable lot's landmark switched on and its
    # description changed; sc4conv.py run again over it (sc4_packs.mjs does the same in JS and compares)
    j = json.load(open(os.path.join(g, "conv", "models.json"), encoding="utf-8"))
    pl = [m for m in j["models"] if m.get("kind") == "landmark" and m["x_sc4"].get("version") == "ploppable"]
    if len(pl) != 1:
        raise SystemExit("the tower has %d ploppable landmark entries, expected 1" % len(pl))
    pl[0]["description"] = "Edited in the page"
    pl[0]["enabled"] = True

    def ints(v):
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, list):
            return [ints(x) for x in v]
        if isinstance(v, dict):
            return {k: ints(x) for k, x in v.items()}
        return v
    rd = os.path.join(g, "rerun")
    shutil.rmtree(rd, ignore_errors=True)
    os.makedirs(rd)
    open(os.path.join(rd, "models.json"), "w", encoding="utf-8", newline="\n").write(
        json.dumps(ints(j), indent=2, ensure_ascii=False) + "\n")
    r = subprocess.run([sys.executable, SC4CONV, os.path.join(g, "src"), "--out", rd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    open(os.path.join(g, "sc4conv_rerun_log.txt"), "w", encoding="utf-8").write(r.stdout + r.stderr)
    if r.returncode:
        raise SystemExit("sc4conv.py rerun failed on the tower")
    shutil.copytree(os.path.join(g, "conv"), os.path.join(g, "folder"))
    r = subprocess.run([sys.executable, BLDIMPORT, "pack", os.path.join(g, "folder"), "--game", a.game, "--out",
                        os.path.join(g, "out")], capture_output=True, text=True)
    open(os.path.join(g, "pack_log.txt"), "w", encoding="utf-8").write(r.stdout + r.stderr)
    if r.returncode:
        print(r.stdout + r.stderr)
        raise SystemExit("bldimport.py pack failed on the tower")
    print("goc: bldimport pack: %s" % r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "goc: packed")


if __name__ == "__main__":
    main()
