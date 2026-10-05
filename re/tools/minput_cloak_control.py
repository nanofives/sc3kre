"""Cross-process DWM CLOAK control: can THIS process cloak ANOTHER process's window, and do posted
messages still reach the cloaked window?

Cloaking (DWMWA_CLOAK = 13) is the state a window is in on another Windows virtual desktop: still
a real window with a real client rect, composed by DWM, but not on the glass. If a foreign process
can set it, it is a candidate "free the screen without minimising" state for the game.

Child: a plain window whose WndProc counts mouse/key messages, pumping for ~8 s, then prints the
count. Parent: cloaks the child window, checks DWMWA_CLOAKED, posts the sc3io message set, uncloaks,
and reads the child's count. No cursor, no focus involved (WS_EX_NOACTIVATE, SW_SHOWNOACTIVATE).

    python re/tools/minput_cloak_control.py
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
import time
from ctypes import wintypes

CHILD = r'''
import ctypes, sys, time
from ctypes import wintypes
user32 = ctypes.WinDLL("user32", use_last_error=True); kernel32 = ctypes.WinDLL("kernel32")
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]
user32.DefWindowProcW.restype = ctypes.c_long
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = ([wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD] + [ctypes.c_int]*4 + [wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID])
seen = []
def wp(h, m, w, l):
    if 0x200 <= m <= 0x20A or m in (0x100, 0x101): seen.append((m, l & 0xFFFF, l >> 16))
    return user32.DefWindowProcW(h, m, w, l)
proc = WNDPROC(wp)
wc = WNDCLASSW(); wc.lpfnWndProc = proc; wc.hInstance = kernel32.GetModuleHandleW(None); wc.lpszClassName = "MinputCloakChild"; wc.hbrBackground = 6
user32.RegisterClassW(ctypes.byref(wc))
h = user32.CreateWindowExW(0x08000000, "MinputCloakChild", "cloak child", 0x00CF0000, 150, 150, 500, 400, None, None, wc.hInstance, None)
user32.ShowWindow(h, 4)
print("HWND", h, flush=True)
msg = wintypes.MSG(); end = time.time() + 8
while time.time() < end:
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
        user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))
    time.sleep(0.01)
print("SEEN", seen, flush=True)
'''

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

def fg():
    h = user32.GetForegroundWindow(); b = ctypes.create_unicode_buffer(80); user32.GetWindowTextW(h, b, 80)
    return f"0x{h:08X} {b.value[:40]!r}"

def cloaked(h):
    v = wintypes.DWORD(0)
    hr = dwmapi.DwmGetWindowAttribute(wintypes.HWND(h), 14, ctypes.byref(v), 4)
    return hr, v.value

def main() -> int:
    p = subprocess.Popen([sys.executable, "-c", CHILD], stdout=subprocess.PIPE, text=True)
    line = p.stdout.readline().strip()
    h = int(line.split()[1])
    time.sleep(0.5)
    print(f"child hwnd 0x{h:08X}  foreground before: {fg()}")
    print(f"cloaked before: {cloaked(h)}")
    on = wintypes.BOOL(1)
    hr = dwmapi.DwmSetWindowAttribute(wintypes.HWND(h), 13, ctypes.byref(on), 4)
    print(f"DwmSetWindowAttribute(DWMWA_CLOAK=1) cross-process HRESULT = 0x{hr & 0xFFFFFFFF:08X}")
    time.sleep(0.4)
    print(f"cloaked after : {cloaked(h)}  IsWindowVisible={bool(user32.IsWindowVisible(h))}")
    r = wintypes.RECT(); user32.GetClientRect(h, ctypes.byref(r)); print(f"client while cloaked: {r.right}x{r.bottom}")
    x, y = 250, 120; lp = ((y & 0xFFFF) << 16) | x
    P = user32.PostMessageW
    P(h, 0x200, 0, lp); P(h, 0x201, 1, lp); P(h, 0x202, 0, lp); P(h, 0x100, 0x41, 1); P(h, 0x101, 0x41, 0xC0000001)
    pt = wintypes.POINT(x, y); user32.ClientToScreen(h, ctypes.byref(pt))
    P(h, 0x20A, 120 << 16, ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF))
    time.sleep(0.5)
    off = wintypes.BOOL(0)
    hr2 = dwmapi.DwmSetWindowAttribute(wintypes.HWND(h), 13, ctypes.byref(off), 4)
    print(f"uncloak HRESULT = 0x{hr2 & 0xFFFFFFFF:08X}  cloaked now: {cloaked(h)}")
    print(f"foreground after : {fg()}")
    out = p.communicate(timeout=15)[0]
    print("child reports:", out.strip().splitlines()[-1])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
