#!/usr/bin/env python3
r"""popslow_run.py - one measurement arm of task popslow: fresh game from `sc3dev.ps1 run`, wait for the city clock,
unpause with a posted click on the bar's play button (no Frida while paused: re/tools/sc3pause.py), optional client
resize (HUD Auto -> factor), then popslow_ab.py, then stop the game it started (its own PID only).

Usage (wrap in test-slot): py -3.12 re/tools/popslow_run.py --name popslow --arm stock|mods --out verify/popslow/<dir>
       [--client 1600x1200] [--speed 3] [--win 20] [--reps 1] [--pops ...] [--city "Moscow, Russia.sc3"] [--env K=V ...]
"""
import argparse
import os
import pathlib
import subprocess
import sys
import time

TOOLS = pathlib.Path(__file__).resolve().parent
WT = TOOLS.parent.parent
sys.path.insert(0, str(TOOLS))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="popslow")
    ap.add_argument("--arm", choices=["stock", "mods"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label")
    ap.add_argument("--client", default="")
    ap.add_argument("--speed", type=int, default=3)
    ap.add_argument("--win", type=float, default=20)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--pops", default="")
    ap.add_argument("--city", default="Moscow, Russia.sc3")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--trace", default="", help="jsonl path: run popslow_holdtrace.py alongside")
    ap.add_argument("--cores", type=int, default=0, help="pin the game to the first N logical CPUs (0 = all)")
    a = ap.parse_args(argv)
    for kv in a.env:
        k, v = kv.split("=", 1)
        os.environ[k] = v
    cmd = ["pwsh", "-NoProfile", "-File", str(WT / "re/scripts/sc3dev.ps1"), "run", a.name, "-City", a.city]
    if a.arm == "stock":
        cmd.append("-Stock")
    subprocess.run(cmd, check=True)
    root = WT.parent
    pid = int((root / "last_pid").read_text().strip())
    os.environ["SC3_PID"] = str(pid)
    os.environ["SC3MODS_DIR"] = str(root / "inst")
    from popslow_meter import Meter
    import sc3io
    try:
        t0 = time.time()
        m = None
        while time.time() - t0 < 240:
            try:
                m = m or Meter(pid)
                s = m.sample()
                if s:
                    break
            except SystemExit:
                pass
            time.sleep(2)
        time.sleep(8)
        h = sc3io.game_hwnd(pid)
        for _ in range(30):            # the city can still be loading (hold > 0): retry for up to ~90 s
            s = m.sample()
            if s and s["upause"] == 0 and s["hold"] == 0:
                break
            if s and s["hold"] == 0:
                sc3io.move(h, 522, 563, repeat=1)
                sc3io.click(h, 522, 563)
            time.sleep(3)
        print("state after unpause:", m.sample(), flush=True)
        if a.cores:
            # stand-in for a weaker PC: pin MY game process to the first N logical CPUs (own PID only)
            import ctypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.OpenProcess.restype = ctypes.c_void_p
            hp = k32.OpenProcess(0x0200 | 0x0400, False, pid)     # PROCESS_SET_INFORMATION | QUERY_INFORMATION
            ok = k32.SetProcessAffinityMask(ctypes.c_void_p(hp), ctypes.c_size_t((1 << a.cores) - 1))
            k32.CloseHandle(ctypes.c_void_p(hp))
            print(f"affinity: first {a.cores} logical CPUs, ok={ok}", flush=True)
        scale = 1.0
        if a.client:
            w, hh = (int(v) for v in a.client.split("x"))
            sc3io.resize_client(h, w, hh)
            time.sleep(4)
            scale = min(w / 800.0, hh / 600.0) if a.arm == "mods" else 1.0
        label = a.label or f"{a.arm}_{a.client or '800x600'}_s{a.speed}" + (f"_c{a.cores}" if a.cores else "")
        ab = [sys.executable, str(TOOLS / "popslow_ab.py"), "--out", a.out, "--label", label, "--win", str(a.win),
              "--reps", str(a.reps), "--scale", str(scale), "--speed", str(a.speed)]
        if a.pops:
            ab += ["--pops", a.pops]
        tr = None
        if a.trace:
            tr = subprocess.Popen([sys.executable, str(TOOLS / "popslow_holdtrace.py"), "--seconds", "100000",
                                   "--out", a.trace])
            time.sleep(4)
        rc = subprocess.run(ab).returncode
        if tr:
            tr.kill()
    finally:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
        if "SC3U.exe" in out:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"])
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
