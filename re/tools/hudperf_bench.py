"""One arm of verify/hudperf: launch an instance, maximize it, run timed phases, report per-phase cost and fps.

Task hudperf 2026-10-12. Phases (each --phase seconds, default 32, so each holds at least two full 10-s HUDSCALE windows; the first window of a phase straddles the previous one):
  static  camera still, sim at speed 3 (date, funds, RCI and minimap tick on their own)
  scroll  camera scrolling left/right continuously (spoofed arrow keys, sc3io.scroll)
  hover   posted mouse moves across the enlarged side-panel buttons (highlights + tooltips appear and go)
  flyout  one side-panel category clicked open, hover over its items, then clicked closed
Per phase the script records the byte range of resize.log and sc3perf.log it covered, and prints:
  HUDSCALE "ms per frame in the pre-present pass" lines, HUDPERF lines, and the sc3perf CSV fps (median, min).
Kills only the PID it started.

Usage: py -3.12 re/tools/hudperf_bench.py --inst <abs instance> --city <abs .sc3> --out <abs dir>
       [--env NAME=VALUE ...] [--phases static,scroll,hover,flyout] [--phase 25] [--keep]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import statistics
import subprocess
import sys
import threading
import time

TOOLS = pathlib.Path(r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
sys.path.insert(0, str(TOOLS))
import sc3wait  # noqa: E402


def game_child(launcher_pid: int, timeout: float = 40) -> int:
    t0 = time.time()
    while time.time() - t0 < timeout:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              f"(Get-CimInstance Win32_Process -Filter \"ParentProcessId={launcher_pid} and Name='SC3U.exe'\").ProcessId"],
                             capture_output=True, text=True).stdout.strip()
        if out.isdigit():
            return int(out)
        time.sleep(0.5)
    raise SystemExit("no SC3U child")


def size(p: pathlib.Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def chunk(p: pathlib.Path, a: int, b: int) -> str:
    try:
        with open(p, "rb") as f:
            f.seek(a)
            return f.read(max(0, b - a)).decode("utf-8", "replace")
    except OSError:
        return ""


def side_buttons():
    """Native rects of visible side-panel children (class SIMUI+0xa9834 parent), from uiwin_dump."""
    r = subprocess.run([sys.executable, str(TOOLS / "uiwin_dump.py"), "--maxdepth", "4"], capture_output=True,
                       text=True, env=os.environ)
    side = None
    kids = []
    lines = r.stdout.splitlines()
    for ln in lines:
        if "abs [" in ln and "SIMUI.DLL+0xa9834" in ln:
            side = json.loads(ln.split("abs ")[1].split(" loc")[0])
    if side:
        for ln in lines:
            if "abs [" not in ln or "SIMUI.DLL+0xa9834" in ln:
                continue
            rc = json.loads(ln.split("abs ")[1].split(" loc")[0])
            w, h = rc[2] - rc[0], rc[3] - rc[1]
            if rc[0] >= side[0] and rc[2] <= side[2] and rc[1] >= side[1] and rc[3] <= side[3] and 20 <= w <= 60 and 20 <= h <= 60:
                kids.append(rc)
    return side, kids


def fwd(p, c, s):
    return int(c + s * (p - c))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", required=True); ap.add_argument("--city", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--phases", default="static,scroll,hover,flyout")
    ap.add_argument("--phase", type=float, default=32.0)
    ap.add_argument("--keep", action="store_true", help="leave the game running at the end")
    ap.add_argument("--speed", default="3")
    ap.add_argument("--at", default="-2400,100", help="move the window here (screen px) before maximizing, '' = leave")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    inst = pathlib.Path(a.inst)
    env = dict(os.environ)
    env["SC3RESIZE_LOG"] = str(out / "resize.log")
    for kv in a.env:
        k, v = kv.split("=", 1); env[k] = v
    perf = inst / "sc3perf.log"
    lp = subprocess.Popen([str(inst / "mods_launch.exe"), "-multi", "--", a.city],
                          stdout=open(out / "launch.out", "w"), stderr=subprocess.STDOUT, env=env,
                          creationflags=0x08000000)
    pid = game_child(lp.pid)
    os.environ["SC3_PID"] = str(pid)
    (out / "pid.txt").write_text(str(pid))
    print("game pid", pid, flush=True)
    import sc3io  # noqa: E402
    log = out / "resize.log"
    t0 = time.time()
    while time.time() - t0 < 150:
        if log.exists() and "city HUD became visible" in log.read_text(errors="replace"):
            break
        time.sleep(1)
    else:
        print("city never came up"); subprocess.run(["taskkill", "/PID", str(pid), "/F"]); return 2
    time.sleep(6)
    subprocess.run([sys.executable, str(TOOLS / "dismiss_tips.py")], env=os.environ)
    hwnd = sc3io.game_hwnd()
    if a.at:
        import ctypes
        x, y = (int(v) for v in a.at.split(","))
        ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004 | 0x0010)  # NOSIZE NOZORDER NOACTIVATE
        time.sleep(3)
    n_rz = len(log.read_text(errors="replace"))
    sc3io.maximize_without_focus(hwnd)
    sc3wait.wait_layout(log, n_rz)      # was a blind 8 s
    if a.speed:
        sc3io.key(hwnd, ord(a.speed[0]))
        time.sleep(0.5)
        for _ in range(3):   # P toggles the pause (sc3resize PAUSEKEY); the speed keys do not unpause
            sc3io.key(hwnd, ord("P"))
            time.sleep(1.0)
            pk = re.findall(r"PAUSEKEY> depth \d+ -> (\w+)", log.read_text(errors="replace"))
            if pk and pk[-1] == "resume":
                break
        print("pause key:", pk[-1] if pk else "no PAUSEKEY line", flush=True)
    time.sleep(2)
    try:
        g = sc3io.grab(hwnd, settle=0.3)
        g.img.save(out / "max.png")
    except Exception as e:  # noqa: BLE001
        print("grab failed:", e)
    _, _, cw, ch = sc3io.client_rect_on_screen(hwnd)
    txt = log.read_text(errors="replace")
    m = re.findall(r"HUDSCALE> \d+ window\(s\) enlarged ([0-9.]+)x about \((\d+),(\d+)\)", txt)
    s = float(m[-1][0]) if m else 1.0
    cx, cy = (int(m[-1][1]), int(m[-1][2])) if m else (cw, ch)
    print(f"client {cw}x{ch}, HUD factor {s} about ({cx},{cy})", flush=True)
    side, kids = side_buttons()
    print("side panel", side, "buttons", len(kids), flush=True)
    res = {"pid": pid, "s": s, "client": [cw, ch], "phases": {}}

    def run_phase(name, body):
        a0, p0 = size(log), size(perf)
        t = time.time()
        body(t + a.phase)
        while time.time() < t + a.phase:
            time.sleep(0.2)
        a1, p1 = size(log), size(perf)
        rl, pl = chunk(log, a0, a1), chunk(perf, p0, p1)
        ms = [float(x) for x in re.findall(r"([0-9.]+) ms per frame in the pre-present pass", rl)]
        hp = [ln.split("] ", 1)[-1] for ln in rl.splitlines() if "HUDPERF>" in ln][-8:]
        st = [ln.split("] ", 1)[-1] for ln in rl.splitlines() if "stages ms/frame" in ln]
        fps = []
        for ln in pl.splitlines():
            if "CSV," in ln:
                f = ln.split("CSV,")[1].split(",")
                try:
                    fps.append(float(f[1]))
                except (ValueError, IndexError):
                    pass
        fps = fps[2:] if len(fps) > 4 else fps
        cyc = [(float(x), float(y)) for x, y in re.findall(r"thread cycles per frame: pass ([0-9.]+) M, restore ([0-9.]+) M", rl)]
        pres = [int(x) * 10000.0 / int(t) for x, t in re.findall(r"HUDSCALE> (\d+) enlarged frames in (\d+) ms", rl)]
        lazy = re.findall(r"cancelled by it (\d+), paid late (\d+) (\d+) (\d+) (\d+) (\d+) .*dropped (\d+)", rl)
        chk = re.findall(r"CHECK: (\d+) frames compared, (\d+) with a difference, (\d+) px differ.*coverage: (\d+) frames with a difference, (\d+) px", rl)
        r = {"pass_ms": ms, "fps_median": statistics.median(fps) if fps else None,
             "cycles_M": cyc, "presents_per_10s": pres, "lazy": lazy, "check": chk,
             "fps_min": min(fps) if fps else None, "fps_n": len(fps), "hudperf": hp, "stages": st}
        res["phases"][name] = r
        print(f"[{name}] pass ms {ms}  fps median {r['fps_median']} min {r['fps_min']} (n={len(fps)})", flush=True)
        for x in st + hp:
            print("    ", x, flush=True)
        try:
            sc3io.grab(hwnd, settle=0.0).img.save(out / f"{name}.png")
        except Exception as e:  # noqa: BLE001
            print("grab failed:", e)

    def body_static(_end):
        pass

    def body_scroll(end):
        def go():
            d = 0
            while time.time() < end - 1.0:
                sc3io.scroll(hwnd, "right" if d % 2 == 0 else "left", taps=8, hold=0.15)
                d += 1
        th = threading.Thread(target=go, daemon=True); th.start()

    def pts():
        return [(fwd((k[0] + k[2]) // 2, cx, s), fwd((k[1] + k[3]) // 2, cy, s)) for k in kids]

    def body_hover(end):
        def go():
            p = pts()
            i = 0
            while p and time.time() < end - 0.5:
                x, y = p[i % len(p)]
                sc3io.move(hwnd, x, y, repeat=2, delay=0.05)
                time.sleep(0.6)
                i += 1
            sc3io.move(hwnd, cw // 3, ch // 3, repeat=2)
        th = threading.Thread(target=go, daemon=True); th.start()

    def body_flyout(end):
        def go():
            p = pts()
            if not p:
                return
            x, y = p[-1]
            sc3io.click(hwnd, x, y)
            time.sleep(1.0)
            fx = x - int(60 * s)
            j = 0
            while time.time() < end - 2.5:
                sc3io.move(hwnd, fx, y - int(40 * s) * (j % 4), repeat=2, delay=0.05)
                time.sleep(0.5)
                j += 1
            sc3io.click(hwnd, x, y)
            sc3io.move(hwnd, cw // 3, ch // 3, repeat=2)
        th = threading.Thread(target=go, daemon=True); th.start()

    bodies = {"static": body_static, "scroll": body_scroll, "hover": body_hover, "flyout": body_flyout}
    for ph in a.phases.split(","):
        run_phase(ph, bodies[ph])
        time.sleep(1.5)
    (out / "bench.json").write_text(json.dumps(res, indent=1))
    if not a.keep:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
