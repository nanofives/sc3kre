"""OS-level CONTROL for the minimised-input question, needing no game at all.

Creates a plain Win32 window owned by THIS process whose WndProc counts every mouse/key message
it receives, then posts the same messages sc3io posts (WM_MOUSEMOVE / WM_LBUTTONDOWN / WM_LBUTTONUP
/ WM_KEYDOWN / WM_KEYUP / WM_MOUSEWHEEL) in each window state:

    normal (not active)   ->  expected delivered
    SW_MINIMIZE           ->  ?
    SW_SHOWMINNOACTIVE    ->  ?
    moved off-screen      ->  ?
    DWM-cloaked is NOT reproducible here (needs the VirtualDesktop COM API)

It also records what the WndProc SEES as lParam and what GetClientRect / GetWindowRect / IsIconic
return in each state, because the game clamps coordinates to its own stored width/height
[CONFIRMED @ GZGraphicD 0x100178a6 LAB_10017aaa] and a wrong coordinate is the standing confound.

Nothing here touches the cursor or the foreground: the window is created with WS_EX_NOACTIVATE and
shown with SW_SHOWNOACTIVATE; the state changes use ShowWindow(SW_MINIMIZE / SW_SHOWMINNOACTIVE)
and SetWindowPos(SWP_NOACTIVATE). The foreground window is logged before and after as proof.

    python re/tools/minput_os_control.py
"""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HANDLE), ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HANDLE), ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR)]

user32.DefWindowProcW.restype = ctypes.c_long
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = ([wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
                                   + [ctypes.c_int] * 4 + [wintypes.HWND, wintypes.HMENU,
                                                           wintypes.HINSTANCE, wintypes.LPVOID])

seen: list[tuple[int, int, int]] = []

def wndproc(h, m, wp, lp):
    if 0x200 <= m <= 0x20A or m in (0x100, 0x101):
        seen.append((m, wp, lp))
    return user32.DefWindowProcW(h, m, wp, lp)

_proc = WNDPROC(wndproc)

def fg():
    h = user32.GetForegroundWindow()
    b = ctypes.create_unicode_buffer(120)
    user32.GetWindowTextW(h, b, 120)
    return f"0x{h:08X} {b.value[:40]!r}"

def rects(h):
    r = wintypes.RECT(); user32.GetWindowRect(h, ctypes.byref(r))
    c = wintypes.RECT(); user32.GetClientRect(h, ctypes.byref(c))
    return (f"win=({r.left},{r.top},{r.right},{r.bottom}) client={c.right}x{c.bottom} "
            f"iconic={bool(user32.IsIconic(h))} visible={bool(user32.IsWindowVisible(h))}")

def pump(ms):
    msg = wintypes.MSG()
    end = time.time() + ms / 1000
    while time.time() < end:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.01)

def burst(h, x, y):
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    del seen[:]
    P = user32.PostMessageW
    P(h, 0x200, 0, lp); P(h, 0x201, 1, lp); P(h, 0x202, 0, lp)
    P(h, 0x100, 0x41, 1); P(h, 0x101, 0x41, 0xC0000001)
    pt = wintypes.POINT(x, y); user32.ClientToScreen(h, ctypes.byref(pt))
    P(h, 0x20A, 120 << 16, ((pt.y & 0xFFFF) << 16) | (pt.x & 0xFFFF))
    pump(300)
    got = [m for m, _, _ in seen]
    mm = [(lp_ & 0xFFFF, lp_ >> 16) for m, _, lp_ in seen if m == 0x200]
    return got, mm

def main() -> int:
    hinst = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSW()
    wc.lpfnWndProc = _proc
    wc.hInstance = hinst
    wc.lpszClassName = "MinputControl"
    wc.hbrBackground = 6
    if not user32.RegisterClassW(ctypes.byref(wc)):
        print("RegisterClass failed", ctypes.get_last_error()); return 1
    WS_OVERLAPPEDWINDOW = 0x00CF0000
    WS_EX_NOACTIVATE = 0x08000000
    h = user32.CreateWindowExW(WS_EX_NOACTIVATE, "MinputControl", "minput control",
                               WS_OVERLAPPEDWINDOW, 100, 100, 640, 480, None, None, hinst, None)
    if not h:
        print("CreateWindow failed", ctypes.get_last_error()); return 1
    user32.ShowWindow(h, 4)   # SW_SHOWNOACTIVATE
    pump(300)
    print(f"foreground before: {fg()}")
    x, y = 300, 200
    expect = [0x200, 0x201, 0x202, 0x100, 0x101, 0x20A]

    def trial(label):
        pump(200)
        got, mm = burst(h, x, y)
        ok = got == expect
        print(f"{label:24} {rects(h)}")
        print(f"{'':24} delivered={[hex(g) for g in got]} mousemove_lparam={mm} "
              f"{'ALL DELIVERED' if ok else 'MISSING ' + str([hex(e) for e in expect if e not in got])}")
        return ok

    res = {}
    res["normal"] = trial("normal, not active")
    user32.ShowWindow(h, 6); pump(400)                    # SW_MINIMIZE
    res["SW_MINIMIZE"] = trial("SW_MINIMIZE")
    user32.ShowWindow(h, 4); pump(400)                    # SW_SHOWNOACTIVATE (restore)
    user32.ShowWindow(h, 7); pump(400)                    # SW_SHOWMINNOACTIVE
    res["SW_SHOWMINNOACTIVE"] = trial("SW_SHOWMINNOACTIVE")
    user32.ShowWindow(h, 4); pump(400)
    user32.SetWindowPos(h, None, -5000, -5000, 0, 0, 0x0001 | 0x0010 | 0x0004)  # NOSIZE|NOACTIVATE|NOZORDER
    pump(400)
    res["off-screen"] = trial("off-screen (-5000,-5000)")
    user32.SetWindowPos(h, None, 100, 100, 0, 0, 0x0001 | 0x0010 | 0x0004); pump(200)
    print(f"foreground after : {fg()}")
    user32.DestroyWindow(h)
    print("\nverdict (OS delivery of posted mouse/key messages, no game involved):")
    for k, v in res.items():
        print(f"  {k:20} {'delivered' if v else 'NOT delivered'}")
    return 0 if all(res.values()) else 1

if __name__ == "__main__":
    raise SystemExit(main())
