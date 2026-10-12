"""One arm of verify/leftclick: launch an instance, drive the left-click rows of PRE.md, record the trace.

Usage: py -3.12 re/tools/leftclick_run_arm.py --inst <abs instance folder> --city <abs .sc3> --out <abs dir>
       [--env NAME=VALUE ...] [--keep]
Kills only the PID it started. Rows: 800x600 clicks (352,272) (200,200); maximized clicks (792,461) (1400,800)
and the minimap centre; restored click (352,272). Map-area centre and minimap are read from the live tree first.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

TOOLS = pathlib.Path(r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
WT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))


def game_child(launcher_pid: int, timeout: float = 30) -> int:
    t0 = time.time()
    while time.time() - t0 < timeout:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              f"(Get-CimInstance Win32_Process -Filter \"ParentProcessId={launcher_pid} and Name='SC3U.exe'\").ProcessId"],
                             capture_output=True, text=True).stdout.strip()
        if out.isdigit():
            return int(out)
        time.sleep(0.5)
    raise SystemExit("no SC3U child")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", required=True); ap.add_argument("--city", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["SC3RESIZE_LOG"] = str(out / "resize.log")
    for kv in a.env:
        k, v = kv.split("=", 1); env[k] = v
    lo = open(out / "launch.out", "w")
    lp = subprocess.Popen([str(pathlib.Path(a.inst) / "mods_launch.exe"), "-multi", "--", a.city],
                          stdout=lo, stderr=subprocess.STDOUT, env=env, creationflags=0x08000000)
    pid = game_child(lp.pid)
    os.environ["SC3_PID"] = str(pid)
    print("game pid", pid, flush=True)
    import sc3io  # noqa: E402  (reads SC3_PID)
    log = out / "resize.log"
    t0 = time.time()
    while time.time() - t0 < 120:
        if log.exists() and "city HUD became visible" in log.read_text(errors="replace"):
            break
        time.sleep(1)
    else:
        print("city never came up"); return 2
    time.sleep(6)
    subprocess.run([sys.executable, str(TOOLS / "dismiss_tips.py")], env=os.environ)
    tr = subprocess.Popen([sys.executable, str(WT / "re/tools/leftclick_trace.py"), "--seconds", "90",
                           "--out", str(out / "trace.jsonl")], stdout=open(out / "trace.out", "w"),
                          stderr=subprocess.STDOUT, env=os.environ)
    time.sleep(5)

    def cli(*args):
        r = subprocess.run([sys.executable, str(TOOLS / "sc3io_cli.py"), *map(str, args)],
                           capture_output=True, text=True, env=os.environ)
        print(" ".join(map(str, args)), "->", (r.stdout + r.stderr).strip(), flush=True)

    def mark(label):
        with open(out / "trace.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": "mark", "label": label}) + "\n")

    def tree():
        r = subprocess.run([sys.executable, str(TOOLS / "uiwin_dump.py")], capture_output=True, text=True, env=os.environ)
        (out / "tree_last.txt").write_text(r.stdout)
        side = bar = mini = None
        for ln in r.stdout.splitlines():
            if "abs [" not in ln: continue
            rect = json.loads(ln.split("abs ")[1].split(" loc")[0])
            if "SIMUI.DLL+0xa9834" in ln: side = rect
            elif "SIMUI.DLL+0xa40ec" in ln: bar = rect
            elif "SIMUI.DLL+0xaa180" in ln: mini = rect
        return side, bar, mini

    cli("check")
    for x, y in ((352, 272), (200, 200)):
        mark(f"800x600 click {x},{y}"); cli("click", x, y); time.sleep(2.5)
    cli("maximize"); time.sleep(6); cli("check")
    side, bar, mini = tree()
    print("side", side, "bar", bar, "mini", mini, flush=True)
    cx, cy = side[0] // 2, bar[1] // 2
    mark(f"max map area [0 0 {side[0]} {bar[1]}] centre {cx},{cy}")
    for x, y in ((cx, cy), (1400, 800)):
        mark(f"max click {x},{y}"); cli("click", x, y); time.sleep(2.5)
    mx, my = (mini[0] + mini[2]) // 2, (mini[1] + mini[3]) // 2
    mark(f"max minimap click {mx},{my}"); cli("click", mx, my); time.sleep(2.5)
    mark("max grab"); cli("grab", out / "max_after_minimap.png")
    cli("restore"); time.sleep(6); cli("check")
    mark("restored click 352,272"); cli("click", 352, 272); time.sleep(2.5)
    tr.terminate(); time.sleep(1)
    if not a.keep:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
