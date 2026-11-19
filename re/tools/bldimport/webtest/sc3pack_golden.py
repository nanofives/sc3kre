#!/usr/bin/env python3
r"""sc3pack_golden.py - task sc3compat-b (2026-11-19e): what sc3pack.py says about each pack, for sc3pack_golden.mjs.

  py -3.12 sc3pack_golden.py --game <pristine game tree> --out <work>\sc3pack --install-pack <bld_parts.zip> <pack>...

Writes <out>/report_<k>.json (with the game) and nogame_<k>.json (no game folder) for every pack, packs.json (the
list), and the install run on a small copy of the game (<out>/game: Apps\BACustom copied, Apps\Res\BA hard-linked,
read only): install.json = the snapshots after
  1. install (no overwrite)
  2. install again, overwriting the conflicting name(s), with a kind picked for the unknown-kind part(s)
  3. remove
Each snapshot = the log + sha256 of every file under Apps/BACustom, Apps/PlugIn and mods/netmod/sc3pack.
Task plop (2026-11-19): --plugin-pack <pack with .pin + .dat plugins> adds a second run on the same game: install,
install again (already installed), remove; the .dat files with 2000 art are written converted (sc3plugin.py).
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import sc3pack as P      # noqa: E402

OVERWRITE = ["Mariners 04.tga"]
KINDS = {"sc3pt loose.tga": "detail"}


def snapshot(game, res):
    files = {}
    for root in ("Apps/BACustom", "Apps/PlugIn", "mods/netmod/sc3pack"):
        rels = []
        P._walk(game, root, rels)
        for r in rels:
            files[r] = hashlib.sha256(game.read(r)).hexdigest()
    return {"log": res["log"], "files": files}


def small_game(src, dst):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(src, "Apps", "BACustom"), os.path.join(dst, "Apps", "BACustom"))
    s = os.path.join(src, "Apps", "Res", "BA")
    for dp, dn, fn in os.walk(s):
        d = os.path.join(dst, "Apps", "Res", "BA", os.path.relpath(dp, s))
        os.makedirs(d, exist_ok=True)
        for f in fn:
            os.link(os.path.join(dp, f), os.path.join(d, f))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--install-pack", required=True)
    ap.add_argument("--plugin-pack")
    ap.add_argument("packs", nargs="+")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    game = P.GameDir(a.game)
    packs = []
    for k, p in enumerate(a.packs):
        ents = P.open_pack(p)
        for name, g in (("report", game), ("nogame", None)):
            with open(os.path.join(a.out, "%s_%d.json" % (name, k)), "w", encoding="ascii", newline="\n") as fh:
                fh.write(P.dumps(P.report(ents, g)))
        packs.append(os.path.abspath(p))
        print("  %s: %d files" % (p, len(ents)))
    with open(os.path.join(a.out, "packs.json"), "w") as fh:
        json.dump(packs, fh, indent=1)
    gdir = os.path.join(a.out, "game")
    small_game(a.game, gdir)
    g = P.GameDir(gdir)
    ents = P.open_pack(a.install_pack)
    name = os.path.basename(a.install_pack)
    snaps = [snapshot(g, {"log": []})]
    snaps.append(snapshot(g, P.install(g, ents, name)))
    snaps.append(snapshot(g, P.install(g, ents, name, OVERWRITE, KINDS)))
    snaps.append(snapshot(g, P.remove(g)))
    out = {"pack": os.path.abspath(a.install_pack), "name": name, "overwrite": OVERWRITE, "kinds": KINDS,
           "snapshots": snaps}
    pok = True
    if a.plugin_pack:
        pe = P.open_pack(a.plugin_pack)
        pn = os.path.basename(os.path.normpath(a.plugin_pack))
        ps = [snapshot(g, {"log": []})]
        ps.append(snapshot(g, P.install(g, pe, pn)))
        ps.append(snapshot(g, P.install(g, pe, pn)))
        ps.append(snapshot(g, P.remove(g)))
        out.update(plugin_pack=os.path.abspath(a.plugin_pack), plugin_name=pn, plugin_snapshots=ps)
        plug = sorted(k for k in ps[1]["files"] if k.startswith("Apps/PlugIn/"))
        pok = bool(plug) and not any(k.startswith("Apps/PlugIn/") for k in ps[3]["files"])
        print("  plugin install: %d files into Apps/PlugIn (%s), reinstall: %s, remove takes them out: %s" % (
            len(plug), ", ".join(plug), [w for _, w in ps[2]["log"]], pok))
    with open(os.path.join(a.out, "install.json"), "w", encoding="ascii", newline="\n") as fh:
        fh.write(P.dumps(out))
    back = {k: v for k, v in snaps[3]["files"].items() if not k.startswith("mods/")}
    ok = back == snaps[0]["files"] and sorted(k for k in snaps[3]["files"] if k.startswith("mods/")) == [
        P.STATE_DIR + "/state.json"]
    print("  install: %d, %d, %d log lines; remove puts Apps/BACustom back: %s" % (
        len(snaps[1]["log"]), len(snaps[2]["log"]), len(snaps[3]["log"]), ok))
    return 0 if ok and pok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
