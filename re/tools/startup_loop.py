r"""startup_loop.py - launch the game N times from an instance folder and record how each start ended (2026-10-21).

For the intermittent startup death (game gone ~0.3 s in, no dump, sc3resize log ending after its SIMUI detours,
verify/undo_mod n1 / handtest2 / t7). Each launch: SC3U.exe via sc3wait.launch_game with the mods of <inst>, a copy of <city>, logs
into <out>/<i>/. A launch is "alive" if SC3U still runs <alive> s after start (then killed by OUR pid); else it
records the process exit code, the lifetime and every mod log's last line.

The caller must hold the game lease and pass its owner (a direct launch does not check it; --owner becomes SC3_SESSION):

    pwsh re/harness/game_lock.ps1 -Acquire -Owner <you> -Minutes 60 -Note "startup loop"   # check its exit code
    py re/tools/startup_loop.py --owner <you> --inst re/harness/inst_undoleft --city <city.sc3> --out <dir> -n 30

A dev workspace (re/scripts/sc3dev.ps1) runs its own tree, so pass it (2026-10-29, child startcrash):

    py re/tools/startup_loop.py --owner <you> --inst dev\<name>\inst --tree dev\<name>\tree --city <city> --out <dir>

Options: --gap <s> pause between launches (default 15, memory: launches < 15 s apart died), --alive <s> (10),
--delay <ms> sleeps that long before each launch (the loader has no -delay), --env K=V (repeatable) extra environment for the game.
--tree <dir> the game tree (default inst\..\..\.., as sc3wait.launch_game).
--fresh: each launch runs a copy of <inst> whose mod DLLs carry a unique overlay tail, so every start loads DLLs with
a new hash, as the first start after a build does (Defender scans them). --mods a,b (with --fresh) keeps only those.
--paintstorm <s>: for the first <s> seconds of each launch, InvalidateRect every top-level window of the game's pid every
1 ms (no input, no focus: it only queues WM_PAINT, as an overlapping window moving away does). Makes a paint that
lands while GZGraphicD's draw device has no raster (+0x44) likely instead of rare (child startcrash, 2026-10-29).
Prints one line per launch: [i/N] name STATUS, plus the first access violation sc3resize's VEH logged
(FAULT ...), since the game's own top-level handler swallows the crash and Windows logs nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3wait  # noqa: E402

FAULT_RE = re.compile(r"\[\s*([\d.]+) ms\]\[tid (\w+)\].*VEH FAULT \*\*\* code=(0x[0-9A-F]+) at (\S+)")
ACCESS_RE = re.compile(r"access=(\w+) addr=(0x[0-9A-F]+)")


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


def paint_storm(pid: int, seconds: float, stop: threading.Event, count: list) -> None:
    """InvalidateRect every visible top-level window of pid, every ~1 ms, for `seconds` (or until stop)."""
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    t_end = time.time() + seconds
    while time.time() < t_end and not stop.is_set():
        hw = []

        def cb(h, _):
            p = wintypes.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == pid:
                hw.append(h)
            return True
        u.EnumWindows(enum_proc(cb), 0)
        for h in hw:
            if u.InvalidateRect(h, None, False):
                count[0] += 1
        time.sleep(0.001)


def first_fault(log: str) -> str:
    """'<code> <at> READ <addr> @<ms> ms tid <t>' for the first VEH FAULT in an sc3resize log other than the game's
    own 0xC0000096 probe at SC3U.exe+0x84122; '' if none."""
    try:
        lines = open(log, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return ""
    for k, l in enumerate(lines):
        m = FAULT_RE.search(l)
        if not m or m.group(3) == "0xC0000096":
            continue
        a = ACCESS_RE.search(lines[k + 1]) if k + 1 < len(lines) else None
        acc = (" %s %s" % a.groups()) if a else ""
        return "%s %s%s @%d ms tid %s" % (m.group(3), m.group(4), acc, int(float(m.group(1))), m.group(2))
    return ""


def fresh_copy(inst: str, dst: str, tag: str, keep: list[str]) -> str:
    """Copy inst's mod DLLs (plus its .ini files) into dst, each DLL with a unique overlay tail (new hash)."""
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(inst):
        src = os.path.join(inst, f)
        if not os.path.isfile(src):
            continue
        low = f.lower()
        if low.endswith(".dll"):
            if keep and low[:-4] not in keep:
                continue
            tail = ("\0fresh %s %f\0" % (tag, time.time())).encode()
            with open(os.path.join(dst, f), "wb") as o:
                o.write(open(src, "rb").read() + tail)
        elif low.endswith(".ini"):
            shutil.copy2(src, os.path.join(dst, f))
    return dst


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
    ap.add_argument("--tree", default=None)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--mods", default="")
    ap.add_argument("--paintstorm", type=float, default=0.0)
    a = ap.parse_args()

    inst = os.path.abspath(a.inst)
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    keep = [m.strip().lower() for m in a.mods.split(",") if m.strip()]
    if keep and not a.fresh:
        raise SystemExit("--mods needs --fresh (it builds the per-launch instance copy)")
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
        if a.delay:
            time.sleep(a.delay / 1000.0)
        others = other_games(set())
        since_prev = None if prev_exit is None else round(time.time() - prev_exit, 1)
        run_inst = fresh_copy(inst, os.path.join(d, "inst"), a.tag + str(i), keep) if a.fresh else inst
        lo = open(os.path.join(d, "launch.out"), "w")
        lp, t0 = sc3wait.launch_game(run_inst, city, env=env, out=lo, tree=a.tree)
        pid = lp.pid
        storm_stop, storm_n = threading.Event(), [0]
        if a.paintstorm > 0:
            threading.Thread(target=paint_storm, args=(pid, a.paintstorm, storm_stop, storm_n), daemon=True).start()
        while time.time() - t0 < a.alive:
            if lp.poll() is not None:
                break
            time.sleep(0.25)
        alive = lp.poll() is None
        storm_stop.set()
        life_ms = None
        code = None
        if alive:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            try:
                lp.wait(10)
            except subprocess.TimeoutExpired:
                pass
        else:
            life_ms = int((time.time() - t0) * 1000)   # upper bound: poll granularity 0.25 s
            code = "0x%08X" % (lp.returncode & 0xFFFFFFFF)
        lo.close()
        prev_exit = time.time()
        r = {"i": i, "dir": d, "alive": alive, "pid": pid, "others_running": others, "s_since_prev_exit": since_prev,
             "exit_code": code, "lifetime_ms": life_ms, "fault": first_fault(os.path.join(d, "resize.log")),
             "refused_by_lease": False, "invalidates": storm_n[0],
             "last": {mod: last_line(os.path.join(d, mod.replace(".dll", "").replace("sc3", "") + ".log"))
                      for mod in ("sc3resize.dll", "sc3undo.dll")}}
        for mod in mods:
            lg = os.path.join(run_inst, mod[:-4] + ".log")
            if os.path.exists(lg) and mod.lower() not in ("sc3resize.dll", "sc3undo.dll"):
                r["last"][mod] = last_line(lg)
        results.append(r)
        status = "ALIVE" if alive else f"DIED {r['exit_code']} at {r['lifetime_ms']} ms"
        print(f"[{i}/{a.n}] {a.tag}{i:02d} {status}" + (f" FAULT {r['fault']}" if r["fault"] else "") +
              (f" others={others}" if others else "") +
              (f" invalidates={storm_n[0]}" if a.paintstorm > 0 else ""), flush=True)
        if i < a.n:
            time.sleep(a.gap)
    json.dump(results, open(os.path.join(out, f"results{a.tag}.json"), "w"), indent=1)
    died = [r for r in results if not r["alive"]]
    faulted = [r for r in results if r["fault"]]
    print(f"\n{len(results)} launches, {len(died)} died early, {len(faulted)} logged an access violation, "
          f"results in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
