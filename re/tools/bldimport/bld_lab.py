#!/usr/bin/env python3
r"""bld_lab.py - task bldrender (2026-11-18): do the imported buildings grow, and how do they look in game.

One game in a dev tree where `bldimport.py build` has run. Posted input only (sc3io), no focus, no real mouse; the
camera moves through the city view's own SetZoomAndRotation on the game thread (verify/showcase/cam.py, nramp_cam.py,
exceptions 'propagate'); pictures through SC3RESIZE_FRAMEDUMP.

  py -3.12 re/tools/bldimport/bld_lab.py --tag run1 [--city "Sacramento, CA"] [--minutes 20] [--want 3]
          [--ids 38000,38001,38002] [--anarchy 5000] [--keep]

Steps: launch (windowed, mods of dev\bldrender\inst, autosave every 150 s, churn anarchy_res so built-up lots
redevelop), unpause at speed 4, read every autosave with occupant_layer until each id has `--want` lots or time runs
out, then put the camera on the lot of each id with the most stock neighbours and dump zoom 4 (every view rotation
for the first id) and zoom 3. Output <out>/<tag>/: resize.log, counts.json, fd/*.png, saves/*.sc3 (copies).
"""
import argparse
import collections
import glob
import json
import os
import pathlib
import shutil
import sys
import time

TOOLS = pathlib.Path(__file__).resolve().parents[1]
WT = TOOLS.parents[1]
MAIN = WT.parents[2]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "netmod"))
sys.path.insert(0, str(MAIN / "verify" / "showcase"))
import occupant_layer  # noqa: E402
import sc3io  # noqa: E402
import sc3wait  # noqa: E402
import vdscroll_io as vdio  # noqa: E402

BLD = (0x207EDC0E, 0x57E)


def counts(path, ids):
    c, s0, s1, cnt, ver, recs = occupant_layer.parse(path)
    out = collections.defaultdict(list)
    for r in recs:
        if tuple(r["key"][:2]) == BLD and r["key"][2] in ids:
            out[r["key"][2]].append((r["a"], r["b"], r["rot"], r["t18"]))
    stock = sum(1 for r in recs if tuple(r["key"][:2]) == BLD and r["key"][2] < 36000)
    return out, stock, recs


def best_spot(lots, recs):
    """The lot with the most building occupants within 3 cells (so the picture shows stock neighbours)."""
    pts = [(r["a"], r["b"]) for r in recs if tuple(r["key"][:2]) == BLD]
    best = None
    for (x, z, rot, t) in lots:
        n = sum(1 for (a, b) in pts if abs(a - x) <= 3 and abs(b - z) <= 3)
        if best is None or n > best[0]:
            best = (n, x, z, rot, t)
    return best


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--city", default="Sacramento, CA")
    ap.add_argument("--minutes", type=float, default=20)
    ap.add_argument("--want", type=int, default=3)
    ap.add_argument("--ids", default="38000,38001,38002")
    ap.add_argument("--anarchy", type=int, default=5000)
    ap.add_argument("--size", default="1600x1000")
    ap.add_argument("--tree", default=str(WT.parent / "tree"))
    ap.add_argument("--inst", default=str(WT.parent / "inst"))
    ap.add_argument("--out", default=str(MAIN / "verify" / "bldrender" / "runs"))
    ap.add_argument("--keep", action="store_true", help="leave the game running at the end")
    a = ap.parse_args(argv)
    ids = [int(x) for x in a.ids.split(",")]
    out = pathlib.Path(a.out) / a.tag
    fd = out / "fd"
    saves = out / "saves"
    for d in (fd, saves):
        d.mkdir(parents=True, exist_ok=True)
    vdio.FD = fd
    log = out / "resize.log"
    if log.exists():
        log.unlink()
    ini = pathlib.Path(a.inst) / "simrun.ini"
    ini_old = ini.read_bytes() if ini.exists() else None
    ini.write_text("[churn]\r\nanarchy_res=%d\r\n" % a.anarchy)
    cities = pathlib.Path(a.tree) / "Cities"
    for f in cities.glob("%s (auto*" % a.city):
        f.unlink()
    env = dict(os.environ)
    env.update({"SC3RESIZE_WINMEM": "0", "SC3RESIZE_LOG": str(log), "SC3RESIZE_FRAMEDUMP": str(fd) + "\\",
                "SC3AUTOSAVE_SECONDS": "150"})
    S = 6
    p, _ = sc3wait.launch_game(a.inst, str(cities / ("%s.sc3" % a.city)), env=env, tree=a.tree)
    os.environ["SC3_PID"] = str(p.pid)
    print("[1/%d] launch pid %d OK" % (S, p.pid), flush=True)
    res = {"tag": a.tag, "pid": p.pid, "city": a.city, "ids": ids, "anarchy_res": a.anarchy, "saves": []}
    try:
        ok, _ = sc3wait.wait_log(log, r"city HUD became visible", 400)
        if not ok:
            print("[2/%d] city up FAIL" % S)
            return 2
        time.sleep(5)
        h = sc3io.game_hwnd()
        vdio.moveto(h, 40, 40)
        time.sleep(1)
        w, hh = (int(v) for v in a.size.split("x"))
        n0 = log.stat().st_size
        vdio.resize(h, w, hh)
        sc3wait.wait_layout(log, n0, timeout=60)
        print("[2/%d] city up OK" % S, flush=True)
        for ch in "P4":                      # lab games start paused (sc3resize P toggles, 4 = fastest)
            sc3io.key(h, ord(ch))
            time.sleep(0.5)
        t0, seen, got = time.time(), {}, {}
        while time.time() - t0 < a.minutes * 60:
            time.sleep(10)
            if p.poll() is not None:
                print("[3/%d] game exited (code %s) FAIL" % (S, p.returncode))
                return 3
            for f in sorted(cities.glob("%s (auto*).sc3" % a.city)):
                if ".tmp." in f.name:
                    continue
                m = f.stat().st_mtime
                if seen.get(f.name) == m:
                    continue
                time.sleep(2)
                seen[f.name] = f.stat().st_mtime
                k = len(res["saves"]) + 1
                cp = saves / ("save%02d.sc3" % k)
                shutil.copy2(f, cp)
                try:
                    got, stock, recs = counts(cp, ids)
                except Exception as e:                 # noqa: BLE001  a save caught mid-write: next one
                    print("    save %d unreadable (%s)" % (k, e), flush=True)
                    continue
                row = {"save": cp.name, "minute": round((time.time() - t0) / 60, 1), "stock": stock,
                       "per_id": {str(i): len(got.get(i, [])) for i in ids}}
                res["saves"].append(row)
                print("    save %d at %.1f min: stock %d, %s" % (k, row["minute"], stock, row["per_id"]), flush=True)
            if got and all(len(got.get(i, [])) >= a.want for i in ids):
                break
        okc = bool(got) and all(len(got.get(i, [])) >= 1 for i in ids)
        print("[3/%d] grown %s %s" % (S, {i: len(got.get(i, [])) for i in ids}, "OK" if okc else "FAIL"), flush=True)
        if not got:
            return 4
        from cam import Cam
        c = Cam([])
        spots = {}
        _, _, recs = counts(saves / res["saves"][-1]["save"], ids)
        for i in ids:
            if got.get(i):
                spots[i] = best_spot(got[i], recs)
        res["spots"] = {str(k): v for k, v in spots.items()}
        n = 0
        for j, (i, (nb, x, z, rot, t)) in enumerate(spots.items()):
            for view in ((0, 1, 2, 3) if j == 0 else (0,)):
                c.go(x, z, 4, view)
                time.sleep(1.0)
                vdio.dump("_pre")
                time.sleep(0.5)
                f = vdio.dump("id%d_z4_v%d_at_%d_%d" % (i, view, x, z))
                n += bool(f)
            c.go(x, z, 3, 0)
            time.sleep(1.0)
            vdio.dump("_pre")
            n += bool(vdio.dump("id%d_z3_v0_at_%d_%d" % (i, x, z)))
        for f in fd.glob("_pre*.png"):
            f.unlink()
        c.close()
        res["dumps"] = sorted(x.name for x in fd.glob("*.png"))
        print("[4/%d] %d frame dumps %s" % (S, n, "OK" if n else "FAIL"), flush=True)
        txt = log.read_text(errors="replace")
        faults = [ln for ln in txt.splitlines() if "VEH FAULT" in ln or "EXCEPTION" in ln.upper()]
        res["faults"] = faults[:20]
        print("[5/%d] %d fault line(s) in resize.log %s" % (S, len(faults), "OK" if not faults else "CHECK"), flush=True)
    finally:
        with open(out / "counts.json", "w") as fh:
            json.dump(res, fh, indent=1)
        for b in fd.glob("*.bmp"):
            try:
                b.unlink()
            except OSError:
                pass
        if ini_old is None:
            ini.unlink()
        else:
            ini.write_bytes(ini_old)
        if not a.keep and p.poll() is None:
            os.system("taskkill /PID %d /F >NUL 2>&1" % p.pid)       # the PID this lab started, never by name
            print("[6/%d] stopped pid %d OK" % (S, p.pid), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
