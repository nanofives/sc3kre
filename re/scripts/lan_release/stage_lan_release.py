#!/usr/bin/env python3
r"""stage_lan_release.py - build the LAN dev-build folder for the mini-server (owner request 2026-10-20: "upload
everything to the server", modelled on TD5RE's td5re-files / td5re_update.ps1).

The folder is a complete, playable SimCity 3000 Unlimited install plus the mods, laid out as a player PC keeps it:
  Apps\                      stock game files (SIMSPR.DLL / GZGraphicD.dll from original\modules: the dev PC's copies
                             are patched on disk, see STOCK_INSTALL.md) + the mod DLLs + sc3mods.dll (the loader) +
                             perf.ini + menu_bg.bmp. SC3U.exe is the STOCK anchor here; the updater patches the local
                             copy on each PC to import sc3mods.dll (2026-10-27, replaces the version.dll proxy).
  Cities\ Buildings\ Scripts\ the game's own folders
  mods\netmod\overlay|tables  the installed netpack packages (sc3netmod serves them; nothing under Apps\ is replaced)
  (no launcher file)         the updater creates "SimCity 3000 (mods).lnk" -> Apps\SC3U.exe on each PC
  sc3_update.ps1, update.bat the updater (copies of the files beside this script)
  sc3mods_patch.ps1          adds the sc3mods.dll import to this PC's SC3U.exe; the updater runs it, -Restore undoes it
  manifest.json              {path, size, sha256, seed}: seed files are downloaded only when missing (per-PC prefs)

Files are hard-linked from the sources when they share a volume (no extra disk), copied otherwise.
Never stage into a git checkout or the game folders (they are game files; the LAN server is private).

  py -3.12 stage_lan_release.py --game <stock tree with packages installed> --bins <built mods dir>
                                --stock-modules <original\modules> --menu-bg <menu_bg.bmp> --out <folder> [--label X]
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

GAME_DIRS = ["Apps", "Cities", "Buildings", "Scripts"]
# SC3U.exe is NOT shipped at the root since 2026-10-26 (owner): it is a copy of Apps\SC3U.exe that cannot run there
# (no game DLLs beside it: "missing UV.dll"). The updater makes a "SimCity 3000 (mods)" shortcut to Apps\SC3U.exe instead.
GAME_ROOT_FILES = ["GameuxInstallHelper.dll", "Support.ico", "icon.ico", "EULA.txt", "README.TXT"]
# dev-PC leftovers inside Apps (RE dumps, harness configs, the untouched originals kept beside patched DLLs)
APPS_SKIP = {"sc3u_stkdmp.txt", "sc3portable.ini", "gzgraphicd.dll.shipped", "simspr.dll.shipped",
             "sc3resize.ini"}   # task uiscale: the player's Preferencias choice (per PC); shipped, an update would reset it
APPS_STOCK_FROM_ORIGINAL = ["SIMSPR.DLL", "GZGraphicD.dll"]
# per-PC state the game or a mod writes: shipped once, never overwritten by the updater
SEED = {"apps/sc3.cfg", "apps/sc3net.cfg", "apps/sc3u.ini",
        "apps/sc3u.exe",               # 2026-10-27: SC3U.exe is seeded so the updater never overwrites a locally
                                       # patched exe (sc3_update runs sc3mods_patch.ps1 to add the sc3mods import on
                                       # each PC). The server copy stays the stock anchor; no modified exe is hosted.
        "cities/europolis 1024.sc3"}   # owner 2026-10-23: the 1024 test city, in the stage source's Cities. Seed so a save over it survives updates
MOD_BINS = ["sc3resize.dll", "sc3bigcity.dll", "sc3overscroll.dll", "sc3simrun.dll", "sc3perf.dll",
            "sc3netmod.dll", "sc3undo.dll", "sc3autosave.dll",
            "sc3mods.dll"]   # sc3mods.dll = the mod loader (sc3mods.c). 2026-10-27: it replaces the version.dll proxy
            # (flagged Program:Win32/Contebrew.A!ml as a system-DLL-named sideloader). It has its own name and no
            # forwarders; SC3U.exe loads it because sc3mods_patch.ps1 adds an import for it to the exe (run per PC by
            # sc3_update). "Stock" = run sc3mods_patch.ps1 -Restore, or set SC3MODS_OFF=1. See verify/importldr/RESULTS.md.
NETMOD_PARTS = ["overlay", "tables"]          # not ledger.json (dev-PC paths) nor packs (sources, reinstall only)


def place(src, dst, copy=False):
    """hard link when possible; copy=True for files a game run writes (prefs) and for original/modules (anchored refs)"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    if copy:
        shutil.copy2(src, dst)
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--bins", required=True)
    ap.add_argument("--stock-modules", required=True)
    ap.add_argument("--menu-bg", required=True)
    ap.add_argument("--perf-ini", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    if os.path.exists(os.path.join(out, ".git")) or os.path.exists(os.path.join(out, "Apps", "SC3U.exe")) and \
            not os.path.exists(os.path.join(out, "manifest.json")):
        sys.exit("refusing: %s looks like a checkout or a live game folder, not a staging folder" % out)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    for d in GAME_DIRS:
        base = os.path.join(a.game, d)
        for r, _ds, fs in os.walk(base):
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), a.game)
                if d == "Apps" and os.path.dirname(rel) == "Apps" and f.lower() in APPS_SKIP:
                    continue
                place(os.path.join(r, f), os.path.join(out, rel), copy=rel.replace("\\", "/").lower() in SEED)
    for f in GAME_ROOT_FILES:
        place(os.path.join(a.game, f), os.path.join(out, f))
    for f in APPS_STOCK_FROM_ORIGINAL:
        place(os.path.join(a.stock_modules, f), os.path.join(out, "Apps", f), copy=True)
    for f in MOD_BINS:
        place(os.path.join(a.bins, f), os.path.join(out, "Apps", f))
    place(a.menu_bg, os.path.join(out, "Apps", "menu_bg.bmp"))
    place(a.perf_ini, os.path.join(out, "Apps", "perf.ini"))
    for part in NETMOD_PARTS:
        base = os.path.join(a.game, "mods", "netmod", part)
        for r, _ds, fs in os.walk(base):
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), a.game)
                place(os.path.join(r, f), os.path.join(out, rel))
    for f in ("sc3_update.ps1", "update.bat"):
        shutil.copy2(os.path.join(HERE, f), os.path.join(out, f))
    # sc3mods_patch.ps1 (one level up, re/scripts) adds the sc3mods.dll import to this PC's SC3U.exe. sc3_update runs
    # it after downloading; it also ships so a player can -Restore to stock by hand.
    shutil.copy2(os.path.join(HERE, "..", "sc3mods_patch.ps1"), os.path.join(out, "sc3mods_patch.ps1"))
    # No launcher file since 2026-10-26: the mods load on a normal start once SC3U.exe is patched, and sc3_update.ps1
    # creates a "SimCity 3000 (mods)" shortcut to this PC's Apps\SC3U.exe (a .lnk holds absolute paths, so it cannot ship).

    files = []
    for r, _ds, fs in os.walk(out):
        for f in fs:
            p = os.path.join(r, f)
            rel = os.path.relpath(p, out).replace("\\", "/")
            if rel == "manifest.json":
                continue
            files.append({"path": rel, "size": os.path.getsize(p), "sha256": sha256(p),
                          "seed": rel.lower() in SEED})
    files.sort(key=lambda e: e["path"].lower())
    man = {"generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "label": a.label,
           "count": len(files), "bytes": sum(e["size"] for e in files), "files": files}
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(man, fh, indent=1)
    print("staged %s: %d files, %.1f MB (%d seed)" % (out, len(files), man["bytes"] / 1e6, sum(e["seed"] for e in files)))


if __name__ == "__main__":
    main()
