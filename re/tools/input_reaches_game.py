"""Prove posted input REACHES the game, in states where no screenshot is possible.

The question this answers: does `sc3io`'s PostMessage input require the window to be focused, or
on top? Pixels cannot answer it - a buried window cannot be captured, which is the whole point.
So instead this counts invocations of the game's own UI event dispatcher.

Instrument: `SIMUI FUN_1006d1af`, the per-child mouse event walk. It tests each child's
`vt+0x100` (IsVisible) and `vt+0xe4` (HitTest) and dispatches
`[CONFIRMED @ SIMUI 0x1006d1af]`. If its call count rises while we post clicks, the engine
processed our input. If it does not rise, the input did not arrive.

States tested, each with the SAME posted clicks:
  1. normal, visible, unfocused
  2. buried - not topmost, fully covered by another window
  3. minimised - not on screen at all

Usage: python re/tools/input_reaches_game.py
"""

from __future__ import annotations

import ctypes
import pathlib
import sys
import time
from ctypes import wintypes

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)

JS = r"""
var hits = 0;
function mb(w){var m=Process.enumerateModules();
  for(var i=0;i<m.length;i++) if(m[i].name.toLowerCase()===w.toLowerCase()) return m[i].base;
  return null;}
var base = mb("SIMUI.DLL");
/* FUN_1006d1af - the per-child mouse event walk. RVA 0x6d1af off the SIMUI image base. */
var target = base.add(0x6d1af);
Interceptor.attach(target, { onEnter: function(){ hits++; } });
rpc.exports = {
  n: function(){ return hits; },
  where: function(){ return { base: base.toString(), fn: target.toString() }; }
};
"""


def occlude(hwnd: int):
    """A topmost cover that does NOT steal activation (WS_EX_NOACTIVATE)."""
    l, t, r, b = sc3io._window_rect(hwnd)
    WS_POPUP, WS_VISIBLE = 0x80000000, 0x10000000
    WS_EX_TOPMOST, WS_EX_NOACTIVATE = 0x8, 0x08000000
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = ([wintypes.DWORD] + [wintypes.LPCWSTR] * 2
                                       + [wintypes.DWORD] + [ctypes.c_int] * 4
                                       + [wintypes.HWND, wintypes.HMENU,
                                          wintypes.HINSTANCE, wintypes.LPVOID])
    ov = user32.CreateWindowExW(WS_EX_TOPMOST | WS_EX_NOACTIVATE, "Static", "COVER",
                                WS_POPUP | WS_VISIBLE, l - 20, t - 20,
                                (r - l) + 40, (b - t) + 40, None, None, None, None)
    user32.SetWindowPos(wintypes.HWND(ov), wintypes.HWND(-1), 0, 0, 0, 0,
                        0x0001 | 0x0002 | 0x0010)
    time.sleep(0.6)
    return ov


def fg() -> tuple[int, str]:
    h = user32.GetForegroundWindow()
    b = ctypes.create_unicode_buffer(120)
    user32.GetWindowTextW(h, b, 120)
    return h, b.value[:40]


def main() -> int:
    hwnd = sc3io.game_hwnd()
    pid = sc3io.game_pid()
    sess = frida.attach(pid)
    sc = sess.create_script(JS)
    sc.load()
    print(f"[*] hooked {sc.exports_sync.where()}")

    _, _, cw, ch = sc3io.client_rect_on_screen(hwnd)
    # click points inside the city view, which always has a hit-testable window under it
    pts = [(cw // 2, ch // 2), (cw // 3, ch // 2), (cw // 2, ch // 3)]

    def burst(label: str) -> int:
        n0 = sc.exports_sync.n()
        for (x, y) in pts:
            sc3io.move(hwnd, x, y, repeat=1)
            sc3io.click(hwnd, x, y)
            time.sleep(0.5)
        time.sleep(1.2)
        n1 = sc.exports_sync.n()
        f = fg()
        print(f"  {label:36} dispatcher calls {n0:6d} -> {n1:6d}   "
              f"delta {n1 - n0:5d}   {'REACHED' if n1 > n0 else 'did NOT reach'}")
        print(f"  {'':36} foreground: {f[1]!r}  game has focus: {f[0] == hwnd}")
        return n1 - n0

    results = {}

    print("\n=== 1. normal, visible, NOT topmost, NOT focused ===")
    sc3io.restore_without_focus(hwnd)
    sc3io.drop_topmost(hwnd)
    time.sleep(0.8)
    print(f"  rect {sc3io._window_rect(hwnd)}  occluders {len(sc3io.occluders(hwnd))}")
    results["visible"] = burst("visible + unfocused")

    print("\n=== 2. BURIED: fully covered by a topmost window ===")
    ov = occlude(hwnd)
    try:
        print(f"  occluders {len(sc3io.occluders(hwnd))}")
        results["buried"] = burst("buried under a full cover")
        orig = sc3io.raise_without_focus
        sc3io.raise_without_focus = lambda _h: None
        try:
            sc3io.grab(hwnd)
            print("  !!! capture unexpectedly SUCCEEDED while buried")
        except sc3io.CaptureError:
            print("  capture correctly REFUSED in this same state (as it must)")
        finally:
            sc3io.raise_without_focus = orig
    finally:
        user32.DestroyWindow(wintypes.HWND(ov))
    time.sleep(0.5)

    print("\n=== 3. MINIMISED: not on screen at all ===")
    user32.ShowWindow(hwnd, 6)   # SW_MINIMIZE
    time.sleep(1.0)
    print(f"  IsIconic={bool(user32.IsIconic(hwnd))} rect {sc3io._window_rect(hwnd)}")
    results["minimised"] = burst("minimised")

    # leave it usable
    sc3io.restore_without_focus(hwnd)
    sess.detach()

    print("\n=== verdict ===")
    for k, v in results.items():
        print(f"  {k:12} {'input reaches the game' if v > 0 else 'input does NOT reach'} "
              f"(delta {v})")
    return 0 if results.get("visible", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
