#!/usr/bin/env python3
r"""soak.py - 15 min soak with rotations (child rotleak, 2026-11-17). All mods, Berlin, 800x600, sim RUNNING.
Each minute: 6 rotations, a zoom out / in round trip and 2 minimap jumps (posted clicks), then a memory read from outside
(private / largest free block). One line per minute "[m/M] ... STATUS"; stops at a crash or a hang.

  py -3.12 soak.py ARM [--min 15] [--env K=V ...]       (--env SC3PERF_SPR_IMGREF=0 = the control)
"""
import argparse
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(MAIN, "re", "tools"))
import sc3io  # noqa: E402
import sc3wait  # noqa: E402
from rotmem import mem, alive, answering, ROT, ZIN, ZOUT, DEV  # noqa: E402

LOG = os.path.join(DEV, "inst", "sc3resize.log")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm")
    ap.add_argument("--min", type=int, default=15)
    ap.add_argument("--city", default="Berlin, Germany.sc3")
    ap.add_argument("--env", nargs="*", default=[])
    a = ap.parse_args()
    e = dict(os.environ)
    e.update(dict(kv.split("=", 1) for kv in a.env))
    t0 = time.time()
    subprocess.run(["pwsh", "-NoProfile", "-File", os.path.join(MAIN, "re", "scripts", "sc3dev.ps1"), "run", "leak1024",
                    "-City", a.city], env=e, check=True, cwd=MAIN, capture_output=True)
    pid = int(open(os.path.join(DEV, "last_pid")).read().strip())
    sc3wait.wait_city_up(LOG, t0 - 1, timeout=150)
    time.sleep(5)
    sc3wait.run_after_load(pid, timeout=90)
    h = sc3io.game_hwnd(pid)
    m0 = mem(pid)
    print(f"arm {a.arm}: pid {pid} env {a.env} start private={m0[0]:.1f} MB free={m0[1]:.0f} MB", flush=True)
    rng = random.Random(1117)
    status, rots = "PASS", 0
    for m in range(1, a.min + 1):
        t_end = time.time() + 60
        acts = ["rot"] * 6 + ["zoom"] + ["jump"] * 2
        rng.shuffle(acts)
        for act in acts:
            if act == "rot":
                sc3io.click(h, *ROT); rots += 1
            elif act == "zoom":
                sc3io.click(h, *ZOUT); time.sleep(2.5); sc3io.click(h, *ZIN)
            else:
                u, v = rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7)
                sc3io.click(h, int(717 + (u - v) * 31), int(511 + (u + v) * 32))
            time.sleep(max(0.5, (t_end - time.time()) / 10))
        while time.time() < t_end:
            time.sleep(0.5)
        if not alive(pid):
            status = "CRASH"
        elif not answering(h):
            status = "HANG"
        mm = mem(pid) if status == "PASS" else (0, 0)
        print(f"[{m}/{a.min}] min {m} rotations {rots} private={mm[0]:.1f} MB free={mm[1]:.0f} MB {status}", flush=True)
        if status != "PASS":
            break
    txt = open(LOG, encoding="utf-8", errors="replace").read()
    fl = [l.strip() for l in txt.splitlines() if "*** VEH FAULT" in l and "0xC0000096 at SC3U.exe+0x84122" not in l]
    if status == "PASS":
        print(f"arm {a.arm}: private {m0[0]:.1f} -> {mm[0]:.1f} MB, largest free {m0[1]:.0f} -> {mm[1]:.0f} MB, "
              f"{rots} rotations, VEH faults after startup {len(fl)}", flush=True)
    for l in fl[:10]:
        print("  " + l)
    for f in ("sc3perf.log", "sc3resize.log"):
        try:
            import shutil
            shutil.copyfile(os.path.join(DEV, "inst", f), os.path.join(HERE, "runs", f"{a.arm}_{f}"))
        except OSError:
            pass
    if alive(pid):
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    return 0 if status == "PASS" and not fl else 1


if __name__ == "__main__":
    sys.exit(main())
