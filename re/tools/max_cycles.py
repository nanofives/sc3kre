#!/usr/bin/env python3
r"""max_cycles.py - maximize/restore one game N times, no focus taken (2026-10-11, dirtcrash task).

Usage: SC3_PID=<pid> py max_cycles.py <n> [--hold <s>] [--log <file>]
Each cycle: maximize, wait --hold seconds, restore, wait --hold seconds. Stops early, with a non-zero exit, if the
game process is gone (a crash). The window must be the one SC3_PID names.
"""
import argparse
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3io  # noqa: E402


def alive(pid: int) -> bool:
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(h)
    return code.value == 259                                        # STILL_ACTIVE


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("--hold", type=float, default=6.0)
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    pid = sc3io.game_pid()
    hwnd = sc3io.game_hwnd(pid)
    out = open(a.log, "a", encoding="utf-8") if a.log else sys.stdout
    t0 = time.time()

    def emit(s: str) -> None:
        out.write("%s %8.1f %s\n" % (time.strftime("%H:%M:%S"), time.time() - t0, s))
        out.flush()

    for i in range(1, a.n + 1):
        for what, fn in (("maximize", sc3io.maximize_without_focus), ("restore", sc3io.restore_without_focus)):
            if not alive(pid):
                emit("cycle %d: game %d is GONE before %s" % (i, pid, what))
                return 2
            try:
                wh = fn(hwnd)
            except Exception as e:   # noqa: BLE001 - a dead window raises from user32
                emit("cycle %d: %s failed: %s" % (i, what, e))
                return 3
            emit("cycle %d: %s -> client %s" % (i, what, wh))
            time.sleep(a.hold)
    emit("done: %d cycles, game %s" % (a.n, "alive" if alive(pid) else "GONE"))
    return 0 if alive(pid) else 2


if __name__ == "__main__":
    sys.exit(main())
