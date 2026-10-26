"""vdscroll bench (child vdscroll 2026-10-26, verify/vdscroll/RESULTS.md): one game, phases with and without the
Ver datos dialog, still and scrolling, and an in-game A/B of the sc3resize VDSCROLL block.

Posted input only (sc3io PostMessage), SetWindowPos with NOZORDER|NOACTIVATE, SetWindowPlacement for maximize.
No cursor, no focus, no topmost, no Frida. Kills only the PID it started.
Scrolling uses the test-only SC3RESIZE_DIAG_ARROWS=1 (set here): a posted WM_APP+0x5D0 makes GZWIND's
GetAsyncKeyState report that arrow as held, and posted arrow keys drive the handler.
Phases: still*/scroll* (measured: sc3perf CSV fps, HUDSCALE pass ms, DLGSCALE/VERDATOS/VDSCROLL lines),
OPEN (views flyout -> Ver datos), FLYX (flyout closed), CLOSE (dialog X), VIEWn (data view n),
T0/T1 (VDSCROLL off/on through WM_APP+0x5D1).

py -3.12 re/tools/vdscroll_bench.py --tag A --city Europolis [--size 2560x1351 | --max] [--env K=V ...]
    [--phases scrollN,OPEN,FLYX,T0,scrollA,T1,scrollB,scrollB,T0,scrollA] [--phase 20] [--paused] [--inst <dir>]
Env: VDSCROLL_TREE (test tree), VDSCROLL_OUT (run folders).
"""
from __future__ import annotations
import argparse, json, os, pathlib, re, statistics, subprocess, sys, threading, time

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
TREE = pathlib.Path(os.environ.get("VDSCROLL_TREE", r"C:\Users\maria\Desktop\Proyectos\Simcity_stock_vdscroll"))
INST = TREE / "re" / "harness" / "inst_vdscroll"
OUT = pathlib.Path(os.environ.get("VDSCROLL_OUT", str(pathlib.Path(os.environ.get("TEMP", ".")) / "vdscroll_runs")))


def size(p):
    try:
        return p.stat().st_size
    except OSError:
        return 0


def chunk(p, a, b):
    try:
        with open(p, "rb") as f:
            f.seek(a); return f.read(max(0, b - a)).decode("utf-8", "replace")
    except OSError:
        return ""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True); ap.add_argument("--city", default="Europolis")
    ap.add_argument("--size", default="2560x1351"); ap.add_argument("--max", action="store_true")
    ap.add_argument("--env", action="append", default=[]); ap.add_argument("--phase", type=float, default=21.0)
    ap.add_argument("--phases", default="still0,scroll0,OPEN,FLYX,still1,scroll1,CLOSE,scroll2,OPEN,FLYX,scroll3")
    ap.add_argument("--keep", action="store_true"); ap.add_argument("--stock", action="store_true")
    ap.add_argument("--load", type=float, default=150)
    ap.add_argument("--inst", default=str(INST))
    ap.add_argument("--paused", action="store_true", help="leave the sim paused (cities load paused)")
    a = ap.parse_args(argv)
    out = OUT / a.tag; out.mkdir(parents=True, exist_ok=True)
    fd = out / "fd"; fd.mkdir(exist_ok=True)
    for old in ("resize.log", "perf.log"):
        if (out / old).exists():
            (out / old).unlink()
    env = dict(os.environ)
    env.update({"SC3MODS_DIR": a.inst, "SC3MODS_MULTI": "1", "SC3RESIZE_WINMEM": "0",
                "SC3RESIZE_LOG": str(out / "resize.log"), "SC3RESIZE_FRAMEDUMP": str(fd) + "\\",
                "SC3PERF_LOG": str(out / "perf.log"), "SC3RESIZE_DIAG_ARROWS": "1"})
    if a.stock:
        env["SC3MODS_OFF"] = "1"
    for kv in a.env:
        k, v = kv.split("=", 1); env[k] = v
    city = TREE / "Cities" / f"{a.city}.sc3"
    p = subprocess.Popen([str(TREE / "Apps" / "SC3U.exe"), str(city)], cwd=str(TREE / "Apps"), env=env)
    pid = p.pid
    os.environ["SC3_PID"] = str(pid)
    (out / "pid.txt").write_text(str(pid))
    print(f"[0/9] launch pid {pid} env {a.env} OK", flush=True)
    import sc3io, vdscroll_io as vdio  # noqa: E402
    vdio.FD = fd
    log, perf = out / "resize.log", out / "perf.log"
    t0 = time.time()
    while time.time() - t0 < a.load:
        if a.stock and time.time() - t0 > 60:
            break
        if log.exists() and "city HUD became visible" in log.read_text(errors="replace"):
            break
        time.sleep(1)
    else:
        print("city never came up"); subprocess.run(["taskkill", "/PID", str(pid), "/F"]); return 2
    time.sleep(5)
    h = sc3io.game_hwnd()
    vdio.moveto(h, 60, 60); time.sleep(1)
    if a.max:
        print("maximized client", sc3io.maximize_without_focus(h), flush=True)
    else:
        w, hh = (int(v) for v in a.size.split("x"))
        print("client", vdio.resize(h, w, hh), flush=True)
    time.sleep(6)
    _, _, cw, ch = sc3io.client_rect_on_screen(h)
    # unpause (cities start paused); PAUSEKEY logs the depth change
    for _ in range(0 if a.paused else 3):
        sc3io.key(h, ord("P")); time.sleep(1.2)
        pk = re.findall(r"PAUSEKEY> depth \d+ -> (\w+)", log.read_text(errors="replace")) if log.exists() else []
        if pk and pk[-1] == "resume":
            break
    if not a.paused:
        print("pause:", pk[-1] if pk else "no PAUSEKEY line", flush=True)
        sc3io.key(h, ord("3")); time.sleep(1)
    # no dismiss_tips: its Frida attach hung twice on this PC and a later attach crashed the game
    txt = log.read_text(errors="replace") if log.exists() else ""
    m = re.findall(r"HUDSCALE> \d+ window\(s\) enlarged ([0-9.]+)x about \((\d+),(\d+)\)", txt)
    s = float(m[-1][0]) if m else 1.0
    cx, cy = (int(m[-1][1]), int(m[-1][2])) if m else (cw, ch)
    print(f"client {cw}x{ch} HUD {s} about ({cx},{cy})", flush=True)

    def q(nx, ny):   # native -> enlarged (posted) coords
        return int(cx + s * (nx - cx)), int(cy + s * (ny - cy))

    import ctypes
    u = ctypes.windll.user32
    WM_DIAGARROW = 0x8000 + 0x5D0
    res = {"pid": pid, "client": [cw, ch], "s": s, "env": a.env, "phases": {}}
    phases = a.phases.split(",")
    n_ph = len(phases)

    def scroll_body(end):
        def go():
            d = 0
            while time.time() < end - 1.0:   # DIAGARROWS: posted "held" arrow + posted key events, no Frida
                vk = 0x27 if d % 2 == 0 else 0x25   # held continuously, direction flips every 3 s with no gap
                u.PostMessageW(h, WM_DIAGARROW, vk, 0)
                t1 = time.time() + 3.0
                while time.time() < t1 and time.time() < end - 1.0:
                    sc3io.key(h, vk, hold=0.02); time.sleep(0.08)
                d += 1
            u.PostMessageW(h, WM_DIAGARROW, 0, 0)
            sc3io.key(h, 0x25, hold=0.02)
        th = threading.Thread(target=go, daemon=True); th.start(); return th

    cur_vds = 1
    for i, ph in enumerate(phases, 1):
        if ph == "OPEN":
            sc3io.click(h, *q(cw - 35, ch - 257)); time.sleep(1.2)   # views category
            sc3io.click(h, *q(cw - 82, ch - 240)); time.sleep(3.0)   # Ver datos
            ok = "VERDATOS> first twin draw" in chunk(log, 0, size(log)) or a.stock
            print(f"[{i}/{n_ph}] open Ver datos {'OK' if ok else 'CHECK'}", flush=True)
            vdio.dump(f"{ph}{i}")
            continue
        if ph in ("T0", "T1"):
            cur_vds = int(ph[1])
        if ph in ("T0", "T1"):   # DIAGARROWS: in-game A/B of the VDSCROLL block
            u.PostMessageW(h, WM_DIAGARROW + 1, int(ph[1]), 0); time.sleep(0.5)
            print(f"[{i}/{n_ph}] VDSCROLL={ph[1]}", flush=True)
            continue
        if ph.startswith("VIEW"):   # click data-view icon n in the dialog column (native local x 21, y 45 + 32 * (n - 1))
            dl = re.findall(r"DLGSCALE>   dialog \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\] -> \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]", chunk(log, 0, size(log)))
            nview = int(ph[4:])
            if dl:
                x0, y0, x1, y1 = (int(v) for v in dl[-1][4:8])
                f = (x1 - x0) / (int(dl[-1][2]) - int(dl[-1][0]))
                sc3io.click(h, int(x0 + 21 * f), int(y0 + (45 + 32 * (nview - 1)) * f))
            time.sleep(2.5)
            print(f"[{i}/{n_ph}] view {nview}", flush=True)
            vdio.dump(f"{ph}_{i}")
            continue
        if ph == "FLYX":
            sc3io.click(h, *q(cw - 35, ch - 257)); time.sleep(1.5)   # views category again: flyout closed
            print(f"[{i}/{n_ph}] flyout toggled", flush=True)
            vdio.dump(f"{ph}{i}")
            continue
        if ph == "CLOSE":
            dl = re.findall(r"DLGSCALE>   dialog \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\] -> \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]", chunk(log, 0, size(log)))
            if dl:
                x0, y0, x1, y1 = (int(v) for v in dl[-1][4:8])
                f = (x1 - x0) / (int(dl[-1][2]) - int(dl[-1][0]))
                sc3io.click(h, int(x1 - 19 * f), int(y0 + 17 * f))
            time.sleep(2)
            print(f"[{i}/{n_ph}] close {'OK' if dl else 'no DLGSCALE rect'}", flush=True)
            vdio.dump(f"{ph}{i}")
            continue
        a0, p0 = size(log), size(perf)
        t = time.time(); end = t + a.phase
        th = scroll_body(end) if ph.startswith("scroll") else None
        if ph.startswith("scroll"):
            ph = f"{ph}_vds{cur_vds}"
        time.sleep(a.phase * 0.5)
        vdio.dump(f"{ph}_{i}_mid".replace("/", "_"))
        while time.time() < end:
            time.sleep(0.2)
        if th:
            th.join(5)
        rl, pl = chunk(log, a0, size(log)), chunk(perf, p0, size(perf))
        ms = [float(x) for x in re.findall(r"([0-9.]+) ms per frame in the pre-present pass", rl)]
        fps, fms = [], []
        for ln in pl.splitlines():
            if "CSV," in ln and "t_s" not in ln:
                f = ln.split("CSV,")[1].split(",")
                try:
                    fps.append(float(f[1])); fms.append(float(f[2]))
                except (ValueError, IndexError):
                    pass
        fps2, fms2 = (fps[2:-1], fms[2:-1]) if len(fps) > 5 else (fps, fms)
        keep = [ln.split("] ", 1)[-1] for ln in rl.splitlines() if any(k in ln for k in ("VERDATOS>", "HUDPERF>", "DLGOCC>", "MININAT>", "VEH FAULT", "DLGSCALE> ", "VDSCROLL>"))]
        r = {"pass_ms": ms, "fps": fps2, "fps_median": statistics.median(fps2) if fps2 else None,
             "ms_median": statistics.median(fms2) if fms2 else None, "lines": keep}
        res["phases"][f"{i}_{ph}"] = r
        print(f"[{i}/{n_ph}] {ph}: fps median {r['fps_median']} ms/frame {r['ms_median']} pass ms {ms} OK", flush=True)
        for x in keep[-10:]:
            print("     ", x[:260], flush=True)
    (out / "bench.json").write_text(json.dumps(res, indent=1))
    if not a.keep:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
