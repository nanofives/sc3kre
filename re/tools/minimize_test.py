"""Minimize/restore the game, then capture - the owner reports a bottom strip keeping the bar's
colour instead of the city after a minimize.

Captures before and after so the two frames can be compared directly.
"""
import ctypes
import glob
import os
import subprocess
import time
from ctypes import wintypes

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DUMPS = os.path.join(ROOT, "verify", "resize_clicklab", "dumps")
SHARE = os.path.join(ROOT, ".happy-share", "cmtjbgk1sassbqj1cz1js6rwh")

user32 = ctypes.WinDLL("user32", use_last_error=True)
SW_MINIMIZE, SW_RESTORE, SW_SHOWMAXIMIZED = 6, 9, 3

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
hwnd, cw, ch = found[0]
print(f"hwnd 0x{hwnd:X} client {cw}x{ch}")


def capture(tag):
    for f in glob.glob(os.path.join(DUMPS, "*.bmp")):
        try:
            os.remove(f)
        except OSError:
            pass
    trig = os.path.join(DUMPS, "DUMP")
    open(trig, "w").close()
    for _ in range(40):
        time.sleep(0.2)
        if not os.path.exists(trig):
            break
    time.sleep(0.5)
    fs = glob.glob(os.path.join(DUMPS, "*frame_with_hud*.bmp"))
    if not fs:
        print(f"  {tag}: no capture")
        return None
    f = max(fs, key=os.path.getmtime)
    im = Image.open(f).convert("RGB")
    out = os.path.join(SHARE, f"minimize_{tag}.png")
    im.resize((im.width // 2, im.height // 2)).save(out)
    print(f"  {tag}: {im.width}x{im.height} -> {out}")
    return im


print("capturing BEFORE")
before = capture("before")

print("minimizing...")
user32.ShowWindow(hwnd, SW_MINIMIZE)
time.sleep(2.0)
print("restoring...")
user32.ShowWindow(hwnd, SW_RESTORE)
time.sleep(1.0)
user32.SetForegroundWindow(hwnd)
time.sleep(2.5)

r = wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(r))
print(f"client after restore: {r.right - r.left}x{r.bottom - r.top}")

print("capturing AFTER")
after = capture("after")

if before and after:
    # how much of the bottom band differs between the two frames
    h = before.height
    band = before.crop((0, h - 120, before.width, h))
    band2 = after.crop((0, h - 120, after.width, h))
    from PIL import ImageChops
    d = ImageChops.difference(band, band2).convert("L")
    px = d.load()
    n = sum(1 for y in range(0, d.height, 2) for x in range(0, d.width, 4) if px[x, y] > 24)
    print(f"bottom 120px band: {n} sampled pixels differ between before and after")
