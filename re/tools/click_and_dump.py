"""Post a click at a client coordinate, then trigger a surface dump of that exact frame.

This closes the loop that cost this project hours: the mod can capture the composited frame
(including the HUD, which external screen capture cannot see), and this drives the state change
that provokes the defect. No human in the loop.

Usage: click_and_dump.py <dumpdir> <x> <y> [--wait 1.5]
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

dumpdir = sys.argv[1]
x, y = int(sys.argv[2]), int(sys.argv[3])
wait = 1.5
if "--wait" in sys.argv:
    wait = float(sys.argv[sys.argv.index("--wait") + 1])

import subprocess
out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
if "SC3U" not in out:
    print("SC3U not running")
    raise SystemExit(1)
pid = int(out.split(",")[1].strip('" '))

found = []
CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def cb(h, _l):
    p = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    if p.value == pid and user32.IsWindowVisible(h):
        r = wintypes.RECT()
        user32.GetClientRect(h, ctypes.byref(r))
        found.append((h, r.right - r.left, r.bottom - r.top))
    return True
user32.EnumWindows(CB(cb), 0)
found.sort(key=lambda t: t[1] * t[2], reverse=True)
if not found:
    print("no window")
    raise SystemExit(1)
hwnd, cw, ch = found[0]
print(f"pid {pid} hwnd 0x{hwnd:X} client {cw}x{ch}")

lp = (y << 16) | (x & 0xFFFF)
user32.SetForegroundWindow(hwnd)
time.sleep(0.3)
user32.PostMessageW(hwnd, 0x0200, 0, lp)          # WM_MOUSEMOVE
time.sleep(0.2)
user32.PostMessageW(hwnd, 0x0201, 1, lp)          # WM_LBUTTONDOWN
time.sleep(0.15)
user32.PostMessageW(hwnd, 0x0202, 0, lp)          # WM_LBUTTONUP
print(f"clicked ({x},{y}); waiting {wait}s then dumping")
time.sleep(wait)

trig = os.path.join(dumpdir, "DUMP")
open(trig, "w").close()
for _ in range(30):
    time.sleep(0.2)
    if not os.path.exists(trig):
        print("dump taken")
        break
else:
    print("WARNING: trigger file was never consumed - is the poll running?")
