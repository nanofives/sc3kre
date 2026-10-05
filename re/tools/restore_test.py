"""Test BOTH readings of the minimize complaint, capturing each state.

  A) minimize to the taskbar, then restore   (already fixed by the RESTORE> invalidate)
  B) restore DOWN from maximized to the small window, then back

B is the untested one and the likelier meaning: at a smaller client the bar re-docks, and anything
that assumed the larger size can leave a strip painted in the bar's colour.
"""
import ctypes
import glob
import os
import subprocess
import time
from ctypes import wintypes

from PIL import Image
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); import sc3io as _sc3io

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DUMPS = os.path.join(ROOT, "verify", "resize_clicklab", "dumps")
SHARE = os.path.join(ROOT, ".happy-share", "cmtjbgk1sassbqj1cz1js6rwh")

user32 = ctypes.WinDLL("user32", use_last_error=True)
SW_MINIMIZE, SW_RESTORE, SW_MAXIMIZE = 6, 9, 3

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
hwnd = found[0][0]


def client():
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


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
        print(f"  {tag}: NO CAPTURE")
        return None
    f = max(fs, key=os.path.getmtime)
    im = Image.open(f).convert("RGB")
    p = os.path.join(SHARE, f"state_{tag}.png")
    im.resize((im.width // 2, im.height // 2)).save(p)
    print(f"  {tag}: surface {im.width}x{im.height}, client {client()} -> {os.path.basename(p)}")
    return im


print("A) minimize to taskbar and restore")
capture("A_before")
user32.ShowWindow(hwnd, SW_MINIMIZE)
time.sleep(2.0)
_sc3io.restore_without_focus(hwnd)
_sc3io.raise_without_focus(hwnd)
time.sleep(3.0)
capture("A_after")

print("\nB) restore DOWN from maximized, then maximize again")
_sc3io.restore_without_focus(hwnd)
_sc3io.raise_without_focus(hwnd)
time.sleep(3.5)
print(f"  client after restore-down: {client()}")
capture("B_restored_down")
_sc3io.maximize_without_focus(hwnd)
_sc3io.raise_without_focus(hwnd)
time.sleep(3.5)
print(f"  client after re-maximize: {client()}")
capture("B_remaximized")
