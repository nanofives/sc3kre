"""Look AT the bottom strip, not at a before/after difference.

My earlier "minimize is fixed" rested on diffing the frames before and after a minimize, which
cannot see a defect that is present in both. This captures the bottom band and reports, per row,
how much of it is the bar's colour versus city - so a strip that should be city and is not shows up
as a number instead of an impression.

Usage: bottom_band.py [--minimize] [--rows 80]
"""
import ctypes
import glob
import os
import subprocess
import sys
import time
from collections import Counter
from ctypes import wintypes

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DUMPS = os.path.join(ROOT, "verify", "resize_clicklab", "dumps")
SHARE = os.path.join(ROOT, ".happy-share", "cmtjbgk1sassbqj1cz1js6rwh")

rows = 80
if "--rows" in sys.argv:
    rows = int(sys.argv[sys.argv.index("--rows") + 1])

user32 = ctypes.WinDLL("user32", use_last_error=True)
out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
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
print(f"client {cw}x{ch}")


def capture(tag):
    for f in glob.glob(os.path.join(DUMPS, "*.bmp")):
        try:
            os.remove(f)
        except OSError:
            pass
    open(os.path.join(DUMPS, "DUMP"), "w").close()
    for _ in range(40):
        time.sleep(0.2)
        if not os.path.exists(os.path.join(DUMPS, "DUMP")):
            break
    time.sleep(0.6)
    fs = glob.glob(os.path.join(DUMPS, "*frame_with_hud*.bmp"))
    if not fs:
        print(f"  {tag}: composite not mapped")
        return None
    im = Image.open(max(fs, key=os.path.getmtime)).convert("RGB")
    band = im.crop((0, im.height - rows, im.width, im.height))
    band.save(os.path.join(SHARE, f"band_{tag}.png"))
    print(f"  {tag}: surface {im.width}x{im.height}, band saved")
    px = band.load()
    print(f"    row  distinct-colours  dominant  share")
    for y in range(0, band.height, 4):
        c = Counter(px[x, y] for x in range(0, band.width, 4))
        dom, n = c.most_common(1)[0]
        share = 100.0 * n / sum(c.values())
        abs_y = im.height - rows + y
        print(f"    {abs_y:5d}  {len(c):5d}            {dom}  {share:5.1f}%")
    return im


if "--minimize" in sys.argv:
    print("BEFORE minimize")
    capture("before")
    user32.ShowWindow(hwnd, 6)
    time.sleep(2.0)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(3.5)
    print("AFTER restore")
    capture("after")
else:
    capture("now")
