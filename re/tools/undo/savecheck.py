"""savecheck.py - the sc3undo save check (verify/undo_mod/RESULTS.md method) as one command.

For each action: save S(4k) before, pick the tool (GZ command), GZ-event drag (sc3undo SC3UNDO_TEST command 12), save
S(4k+1) after, undo, save S(4k+2), redo, save S(4k+3). Then compare S(4k) vs S(4k+2) (undo exact?) and S(4k+1) vs
S(4k+3) (redo exact?) with cmp_saves.py. A paused city saves byte-identically, so both are exact tests.

    py re/tools/undo/savecheck.py --city <city.sc3> --out <dir> road:0x10004001:0x00960190 rail:0x10004101:0x003C00C8

Action = name:tool_id:lparam, lparam = (y << 16) | x client coords of the drag start (the drag runs +150, +100).
The game lease must be held by %SC3_SESSION% (default undo-left); the launcher refuses otherwise.
Prints [i/N] name STATUS per action.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import undo_drive as D  # noqa: E402


def alive() -> bool:
    pid = D.st()["pid"]
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
    return "SC3U" in out


def step(*args: str) -> None:
    D.main(list(args))
    time.sleep(5 if args[:2] == ("cmd", "12") else 2.5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pre", action="append", default=[], help="extra undo_drive step before the actions, e.g. 'cmd 10 0x...'")
    ap.add_argument("--dump", action="store_true", help="frame-dump after each action and after each undo")
    ap.add_argument("actions", nargs="+")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    if D.main(["launch", os.path.abspath(a.city), out]) != 0:
        print("launch failed")
        return 2
    time.sleep(1)
    for p in a.pre:
        step(*p.split())
    n = len(a.actions)
    died = None
    applied = []
    logp = os.path.join(out, "undo.log")

    def napply() -> int:
        try:
            return open(logp, encoding="utf-8", errors="replace").read().count("APPLY> ")
        except OSError:
            return 0
    for i, act in enumerate(a.actions):
        name, tool, lp = act.split(":")
        k = 4 * i
        seq = [("cmd", "13", str(k)), ("cmd", "10", tool), ("cmd", "12", lp)]
        seq += [("dump", name)] if a.dump else []
        seq += [("cmd", "13", str(k + 1)), ("cmd", "1")]
        seq += [("dump", name + "_undo")] if a.dump else []
        seq += [("cmd", "13", str(k + 2)), ("cmd", "2"), ("cmd", "13", str(k + 3))]
        before = napply()
        for s in seq:
            if not alive():
                died = f"{name} before {' '.join(s)}"
                break
            step(*s)
            if s[:2] == ("cmd", "12"):
                applied.append(napply() > before)
        if died:
            break
    t0 = time.time()                      # big cities: the last saves may still be running; wait for every TEST> save line
    while not died and time.time() - t0 < 180:
        if open(logp, encoding="utf-8", errors="replace").read().count("TEST> save") >= 4 * n:
            break
        time.sleep(1)
    log = open(os.path.join(out, "undo.log"), encoding="utf-8", errors="replace").read()
    m = re.search(r"snapshots in (.*)", log)
    if m:
        for f in glob.glob(os.path.join(m.group(1).strip(), "test_*.sc3")):
            shutil.copy2(f, out)
    D.main(["stop"])
    if died:
        print("GAME DIED:", died)
    for i, act in enumerate(a.actions):
        name = act.split(":")[0]
        k = 4 * i
        r = subprocess.run([sys.executable, os.path.join(HERE, "cmp_saves.py"), out, str(k), str(k + 2), str(k + 1), str(k + 3)],
                           capture_output=True, text=True)
        lines = r.stdout.strip().splitlines()
        ok = len(lines) == 2 and all("byte-identical" in l or "EXACT" in l for l in lines)
        did = applied[i] if i < len(applied) else False
        print(f"[{i + 1}/{n}] {name} {'NOT APPLIED (the drag changed nothing, test says nothing)' if not did else 'PASS' if ok else 'FAIL'}")
        for l in lines + r.stderr.strip().splitlines()[-3:]:
            print("     ", l)
    print("\n".join("   log: " + l[:200] for l in log.splitlines()
                    if re.search(r"APPLY|UNDO|REDO|history|barrier|threw|unknown", l)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
