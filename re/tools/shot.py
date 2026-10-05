"""One-shot HUD screenshot: trigger the mod's dump, convert, and stage it for the chat.

The whole point: external screen capture cannot see this game's HUD layer, so screenshots have to
come from the engine's own composited surface (iso+0x4ec, captured right after the final present).
This wraps that into a single command and writes viewable PNGs, downscaled to stay attachable.

Usage:
  shot.py                          capture now
  shot.py --click 2010 508         post a click first, then capture
  shot.py --strip                  also write a crop of the right-hand panel band
  shot.py --scale 2                downscale by N (default 2)
"""
import ctypes
import glob
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(ROOT, "..", ".."))
DUMPS = os.path.join(ROOT, "verify", "resize_clicklab", "dumps")
SHARE = os.path.join(ROOT, ".happy-share", "cmtjbgk1sassbqj1cz1js6rwh")

scale = 2
if "--scale" in sys.argv:
    scale = int(sys.argv[sys.argv.index("--scale") + 1])
want_strip = "--strip" in sys.argv

os.makedirs(DUMPS, exist_ok=True)
os.makedirs(SHARE, exist_ok=True)
for f in glob.glob(os.path.join(DUMPS, "*.bmp")) + glob.glob(os.path.join(DUMPS, "*.png")):
    try:
        os.remove(f)
    except OSError:
        pass

user32 = ctypes.WinDLL("user32", use_last_error=True)


def game_window():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    if "SC3U" not in out:
        return None, 0, 0
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
    return found[0] if found else (None, 0, 0)


hwnd, cw, ch = game_window()
if not hwnd:
    print("SC3U is not running")
    raise SystemExit(1)
print(f"game window 0x{hwnd:X} client {cw}x{ch}")

if "--click" in sys.argv:
    i = sys.argv.index("--click")
    x, y = int(sys.argv[i + 1]), int(sys.argv[i + 2])
    lp = (y << 16) | (x & 0xFFFF)
    import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); import sc3io as _sc3io
    _sc3io.raise_without_focus(hwnd)  # was SetForegroundWindow: raise Z-order only, never take focus
    time.sleep(0.3)
    user32.PostMessageW(hwnd, 0x0200, 0, lp)
    time.sleep(0.2)
    user32.PostMessageW(hwnd, 0x0201, 1, lp)
    time.sleep(0.15)
    user32.PostMessageW(hwnd, 0x0202, 0, lp)
    print(f"clicked ({x},{y})")
    time.sleep(1.2)

trig = os.path.join(DUMPS, "DUMP")
open(trig, "w").close()
for _ in range(40):
    time.sleep(0.2)
    if not os.path.exists(trig):
        break
else:
    print("WARNING: the mod never consumed the trigger - is SC3RESIZE_DUMPDIR set to this dir?")

time.sleep(0.4)
made = []
for f in sorted(glob.glob(os.path.join(DUMPS, "*frame_with_hud*.bmp"))):
    im = Image.open(f).convert("RGB")
    small = im.resize((im.width // scale, im.height // scale))
    out = os.path.join(SHARE, "hud_frame.png")
    small.save(out)
    made.append(out)
    print(f"{os.path.basename(f)} {im.width}x{im.height} -> {out} ({small.width}x{small.height})")
    if want_strip:
        crop = im.crop((max(0, im.width - 280), 0, im.width, im.height))
        out2 = os.path.join(SHARE, "hud_strip.png")
        crop.save(out2)
        made.append(out2)
        print(f"    strip -> {out2} ({crop.width}x{crop.height})")

if not made:
    print("no frame dump found - did the capture fire?")
else:
    print("\nSTAGED FOR CHAT:")
    for m in made:
        print("  " + m)
