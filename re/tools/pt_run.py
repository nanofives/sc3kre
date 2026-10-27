#!/usr/bin/env python3
r"""pt_run.py - one pausetrips arm (verify/pausetrips/PRE.md): launch, drive the pause/speed schedule, count per second.

  py -3.12 pt_run.py --inst <instance folder> --city <src.sc3> --arm NAME --schedule "s3:60,P:90,s1:120,..." [--safe]
  py -3.12 pt_run.py --attach --arm NAME --schedule ...     # SC3_PID already set, no launch / no kill

<inst> holds the mod DLLs of the arm; the city is copied into it as <arm>.sc3 and launched with sc3wait.launch_game
(Apps\SC3U.exe, SC3MODS_DIR=<inst>, SC3MODS_MULTI=1). Only the pid this script started is ever killed. Input is posted to the game window (sc3io): no focus, no
cursor. Keys: P = sc3resize PAUSEKEY (posts 0xc2a35d7e / 0xc2a35d80, city+0x140), 1-4 = SPEEDKEYS (0xc2684065).

Schedule tokens (seconds after the colon):
  sN  run at speed N (key N, then P if user-paused)        P   user pause (P if not paused)
  PW  run until a second with weekly-issuer calls (FUN_100097b9) arrives, then user pause (P at once)
  H   camera hold while running: right button down at the view centre, mouse moves with MK_RBUTTON back and forth
      every 50 ms for the whole phase, button up at the end (the SIMSPR 0x10043daf scroll hold, SIM_WHILE_SCROLLING.md)
  PH  user pause, then the same camera hold
  Z   Z:n = n clicks on the zoom-in button (client 666,547 at 800 x 600), then 2 s

Output: <out>.jsonl, one line per second: wall time, phase, counters and state from pt_probe.py; plus 'timers' lines.
"""
import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from ctypes import wintypes

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = HERE
sys.path.insert(0, TOOLS)
import sc3io  # noqa: E402
from pt_probe import JS  # noqa: E402
import sc3pause  # noqa: E402
import sc3wait  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

user32 = ctypes.WinDLL("user32", use_last_error=True)


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout


def find_pid(exe_path, not_in):
    out = ps("Get-CimInstance Win32_Process -Filter \"Name like 'SC3U%'\" | ForEach-Object { \"$($_.ProcessId)|$($_.ExecutablePath)\" }")
    for line in out.splitlines():
        if "|" in line:
            pid, path = line.split("|", 1)
            if os.path.normcase(path.strip()) == os.path.normcase(exe_path) and int(pid) not in not_in:
                return int(pid)
    return None


class Arm:
    def __init__(self, a):
        self.a = a
        self.phase = "boot"
        self.issuer_seen = 0
        self.out = open(a.out, "a", buffering=1)
        self.lock = threading.Lock()
        self.last = {}

    def write(self, rec):
        with self.lock:
            self.out.write(json.dumps(rec) + "\n")

    def on_msg(self, m, data):
        if m.get("type") != "send":
            self.write({"t": time.time(), "phase": self.phase, "error": m})
            print("probe:", m, flush=True)
            return
        p = m["payload"]
        self.last = p.get("st", {})
        if p.get("c", {}).get("issuer_97b9", 0) > 0:
            self.issuer_seen = time.time()
        self.write({"t": time.time(), "phase": self.phase, **p})

    def st(self):
        return self.sc.exports_sync.state()

    def key(self, vk):
        sc3io.key(self.h, vk)
        time.sleep(0.6)

    def ensure_pause(self, want):
        for _ in range(4):
            s = self.st()
            if (s.get("user_pause") or 0) >= 1 if want else (s.get("user_pause") or 0) == 0:
                return s
            self.key(0x50)
        raise SystemExit("could not set pause=%s: %s" % (want, self.st()))

    def ensure_speed(self, n):
        for _ in range(8):                         # 3 tries missed once right after a pause (cartrips3 R1)
            if self.st().get("speed_last") == n:
                return
            self.key(0x30 + n)
            time.sleep(0.6)
        raise SystemExit("could not set speed %d: %s" % (n, self.st()))

    def hold(self, secs):
        r = wintypes.RECT()
        user32.GetClientRect(wintypes.HWND(self.h), ctypes.byref(r))
        cx, cy = r.right // 2, r.bottom // 2
        lp = lambda x, y: ((y & 0xFFFF) << 16) | (x & 0xFFFF)
        sc3io._post(self.h, sc3io.WM_MOUSEMOVE, 0, lp(cx, cy))
        time.sleep(0.08)
        sc3io._post(self.h, sc3io.WM_RBUTTONDOWN, sc3io.MK_RBUTTON, lp(cx, cy))
        t0, k = time.time(), 0
        while time.time() - t0 < secs:
            k += 1
            dx = (k % 40) - 20 if (k // 40) % 2 == 0 else 20 - (k % 40)
            sc3io._post(self.h, sc3io.WM_MOUSEMOVE, sc3io.MK_RBUTTON, lp(cx + 3 * dx, cy + dx))
            time.sleep(0.05)
        sc3io._post(self.h, sc3io.WM_RBUTTONUP, 0, lp(cx, cy))

    def run_schedule(self):
        for tok in self.a.schedule.split(","):
            what, secs = tok.split(":")
            secs = float(secs)
            self.phase = "sw>" + tok              # seconds while the keys of the next phase are posted: not counted
            if what.startswith("s"):
                self.ensure_speed(int(what[1:]))
                self.ensure_pause(False)
            elif what in ("P", "PH"):
                self.ensure_pause(True)
            elif what == "PW":                     # running until the weekly issuer is active, then pause at once
                self.ensure_pause(False)
                self.issuer_seen = 0
                t0 = time.time()
                while not self.issuer_seen and time.time() - t0 < 180:
                    time.sleep(0.05)
                sc3io.key(self.h, 0x50)
                time.sleep(0.6)
                self.ensure_pause(True)
            elif what == "H":
                self.ensure_pause(False)
            elif what == "Z":                      # Z:n = n clicks on the zoom-in button (client 666,547 at 800 x 600)
                for _ in range(int(secs)):            # (posted wheel messages do not zoom: cartrips3 R2)
                    sc3io.click(self.h, 666, 547)
                    time.sleep(2)
                secs = 2
            self.phase = tok
            self.sc.exports_sync.phase(tok)
            self.write({"t": time.time(), "phase": tok, "mark": "start", "st": self.st()})
            print("%s phase %s %s" % (time.strftime("%H:%M:%S"), tok, self.st()), flush=True)
            if what in ("H", "PH"):
                self.hold(secs)
            else:
                time.sleep(secs)
            if self.a.timers_each:
                self.write({"t": time.time(), "phase": tok, "timers": self.sc.exports_sync.timers()})
            self.write({"t": time.time(), "phase": tok, "mark": "end", "st": self.st()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst")
    ap.add_argument("--city")
    ap.add_argument("--arm", required=True)
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--out")
    ap.add_argument("--safe", action="store_true", help="sc3perf loaded: do not hook its patched entries")
    ap.add_argument("--attach", action="store_true")
    ap.add_argument("--settle", type=float, default=60, help="seconds after launch before tips are dismissed")
    ap.add_argument("--timers-each", action="store_true", default=True)
    ap.add_argument("--keep", action="store_true", help="leave the game running at the end")
    a = ap.parse_args()
    a.out = a.out or os.path.join(a.inst or ".", "%s.jsonl" % a.arm)
    pid = None
    if not a.attach:
        exe = os.path.join(os.path.abspath(os.path.join(a.inst, "..", "..", "..")), "Apps", "SC3U.exe")
        if find_pid(exe, set()):
            raise SystemExit("a game from this tree is already running; stop it first")
        dst = os.path.join(a.inst, "%s.sc3" % a.arm)
        shutil.copyfile(a.city, dst)
        log = open(os.path.join(a.inst, "launch_%s.out" % a.arm), "w")
        proc, t_launch = sc3wait.launch_game(a.inst, dst, out=log)
        pid = proc.pid
        time.sleep(1)
        if proc.poll() is not None:
            raise SystemExit("game did not start (exit %s, see %s)" % (proc.returncode, log.name))
        os.environ["SC3_PID"] = str(pid)
        print("arm %s pid %d" % (a.arm, pid), flush=True)
        with open(os.path.join(a.inst, "pid_%s.txt" % a.arm), "w") as f:
            f.write("%d %s\n" % (pid, time.strftime("%Y-%m-%d %H:%M:%S")))
        # --settle is now the fallback fixed wait; the city-up log signal ends it early (cap 110 s or settle)
        sc3wait.wait_city_up(os.environ.get("SC3RESIZE_LOG", os.path.join(a.inst, "sc3resize.log")), t_launch,
                             timeout=max(110.0, a.settle), fallback_sleep=a.settle, pid=pid)
        subprocess.run([sys.executable, os.path.join(TOOLS, "dismiss_tips.py")], env=os.environ)
        time.sleep(2)
    else:
        pid = sc3io.game_pid()
    arm = Arm(a)
    arm.h = sc3io.game_hwnd(pid)
    tid = user32.GetWindowThreadProcessId(wintypes.HWND(arm.h), None)
    sc3pause.require_running(pid, "pt_run")
    s = frida.attach(pid)
    arm.sc = s.create_script(JS)
    arm.sc.on("message", arm.on_msg)
    arm.sc.load()
    print("cfg", arm.sc.exports_sync.config({"safe": a.safe}), flush=True)
    arm.write({"t": time.time(), "phase": "meta", "arm": a.arm, "pid": pid, "game_tid": tid, "safe": a.safe,
               "schedule": a.schedule, "city": a.city, "inst": a.inst})
    try:
        arm.run_schedule()
    finally:
        try:
            arm.write({"t": time.time(), "phase": "end", "timers": arm.sc.exports_sync.timers()})
            s.detach()
        except Exception as e:  # noqa: BLE001
            print("detach:", e)
        if not a.attach and not a.keep:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            print("killed pid %d" % pid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
