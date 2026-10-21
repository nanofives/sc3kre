"""startup_loop.py - launch the game N times from an instance folder and record how each start ended (2026-10-21).

For the intermittent startup death (game gone ~0.3 s in, no dump, sc3resize log ending after its SIMUI detours,
verify/undo_mod n1 / handtest2 / t7). Each launch: mods_launch.exe -multi from <inst>, a copy of <city>, logs
into <out>/<i>/. A launch is "alive" if SC3U still runs <alive> s after start (then killed by OUR pid); else it
records the exit code mods_launch printed, the lifetime and every mod log's last line.

The caller must hold the game lease and pass its owner (the launchers refuse otherwise, lease_gate.h):

    pwsh re/harness/game_lock.ps1 -Acquire -Owner <you> -Minutes 60 -Note "startup loop"   # check its exit code
    py re/tools/startup_loop.py --owner <you> --inst re/harness/inst_undoleft --city <city.sc3> --out <dir> -n 30

Options: --gap <s> pause between launches (default 15, memory: launches < 15 s apart died), --alive <s> (10),
--delay <ms> passed to mods_launch -delay, --env K=V (repeatable) extra environment for the game.
Prints one line per launch: [i/N] name STATUS.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time


def sc3u_child(launcher_pid: int) -> int | None:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"(Get-CimInstance Win32_Process -Filter \"ParentProcessId={launcher_pid} and Name='SC3U.exe'\").ProcessId"],
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def other_games(mine: set[int]) -> list[int]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-Process SC3U -EA SilentlyContinue | ForEach-Object { $_.Id }"],
                         capture_output=True, text=True).stdout.split()
    return [int(x) for x in out if x.isdigit() and int(x) not in mine]


def last_line(path: str) -> str:
    try:
        lines = [l for l in open(path, encoding="utf-8", errors="replace").read().splitlines() if l.strip()]
        return lines[-1][:200] if lines else "(empty)"
    except OSError:
        return "(no log)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--inst", required=True)
    ap.add_argument("--city", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--gap", type=float, default=15.0)
    ap.add_argument("--alive", type=float, default=10.0)
    ap.add_argument("--delay", type=int, default=0)
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--tag", default="")
    a = ap.parse_args()

    inst = os.path.abspath(a.inst)
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    launcher = os.path.join(inst, "mods_launch.exe")
    mods = [f for f in os.listdir(inst) if f.lower().endswith(".dll")]
    results = []
    prev_exit = None
    for i in range(1, a.n + 1):
        d = os.path.join(out, f"{a.tag}{i:02d}")
        os.makedirs(d, exist_ok=True)
        city = os.path.join(d, "city.sc3")
        shutil.copy2(a.city, city)
        env = dict(os.environ, SC3_SESSION=a.owner, SC3RESIZE_WINMEM="0",
                   SC3RESIZE_LOG=os.path.join(d, "resize.log"), SC3UNDO_LOG=os.path.join(d, "undo.log"))
        for kv in a.env:
            k, v = kv.split("=", 1)
            env[k] = v
        args = [launcher, "-multi"] + (["-delay", str(a.delay)] if a.delay else []) + ["--", city]
        others = other_games(set())
        since_prev = None if prev_exit is None else round(time.time() - prev_exit, 1)
        t0 = time.time()
        lo = open(os.path.join(d, "launch.out"), "w")
        lp = subprocess.Popen(args, cwd=inst, stdout=lo, stderr=subprocess.STDOUT, env=env, creationflags=0x08000000)
        pid = None
        while time.time() - t0 < a.alive:
            if pid is None:
                pid = sc3u_child(lp.pid)
            if lp.poll() is not None:
                break
            time.sleep(0.25)
        alive = lp.poll() is None
        if alive:
            if pid:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            try:
                lp.wait(10)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/PID", str(lp.pid), "/F"], capture_output=True)
        lo.close()
        prev_exit = time.time()
        text = open(os.path.join(d, "launch.out"), errors="replace").read()
        m = re.search(r"game exited, code = (0x[0-9A-F]+) after (\d+) ms", text)
        lm = re.search(r"\[!\] lease: REFUSED", text)
        r = {"i": i, "dir": d, "alive": alive, "pid": pid, "others_running": others, "s_since_prev_exit": since_prev,
             "exit_code": m.group(1) if m else None, "lifetime_ms": int(m.group(2)) if m else None,
             "refused_by_lease": bool(lm),
             "last": {mod: last_line(os.path.join(d, mod.replace(".dll", "").replace("sc3", "") + ".log"))
                      for mod in ("sc3resize.dll", "sc3undo.dll")}}
        for mod in mods:
            lg = os.path.join(inst, mod[:-4] + ".log")
            if os.path.exists(lg) and mod.lower() not in ("sc3resize.dll", "sc3undo.dll"):
                r["last"][mod] = last_line(lg)
        results.append(r)
        status = "REFUSED" if lm else ("ALIVE" if alive else f"DIED {r['exit_code']} at {r['lifetime_ms']} ms")
        print(f"[{i}/{a.n}] {a.tag}{i:02d} {status}" + (f" others={others}" if others else ""), flush=True)
        if lm:
            break
        if i < a.n:
            time.sleep(a.gap)
    json.dump(results, open(os.path.join(out, f"results{a.tag}.json"), "w"), indent=1)
    died = [r for r in results if not r["alive"]]
    print(f"\n{len(results)} launches, {len(died)} died early, results in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
