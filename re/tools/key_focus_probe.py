"""Does POSTED keyboard input reach and act on the game without focus?

Every mouse result in this tooling is verified focus-free. No keyboard result is. This settles it
with a 2x2 - key ARRIVES at the window procedure, and key ACTS on the game - measured with and
without focus, so "the game ignores this key" is separated from "the key never got there".

  arrival : GZGraphicD FUN_10017e2f, the Gonzo WndProc, hooked and counted per message id.
            [CONFIRMED @ GZGraphicD 0x10017e2f; registered thunk RVA 0x17e11]
            WM_KEYDOWN 0x100, WM_KEYUP 0x101, WM_CHAR 0x102, WM_SYSKEYDOWN 0x104.
  effect  : full-frame screenshot diff, reported as CHANGED-PIXELS and, separately, as a
            TRANSLATION test - because a large pixel delta is NOT evidence of a view move
            (verify/offscreen/MAP_INPUT.md: a 29k-pixel "pan" was a selection highlight).

⚠️ This tool DOES take focus, deliberately, in the focused arm only - that is the control. It
records the foreground window first and restores it afterwards. It never moves the cursor.

    python re/tools/key_focus_probe.py                 # sweep a default key set
    python re/tools/key_focus_probe.py --keys 0x20,0x27,0x50
"""

from __future__ import annotations

import argparse
import ctypes
import pathlib
import sys
import time
from ctypes import wintypes

import frida
import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
OUT = pathlib.Path("verify/offscreen/keyprobe")

JS = r"""
var counts = {};
function mb(w){var m=Process.enumerateModules();
  for(var i=0;i<m.length;i++) if(m[i].name.toLowerCase()===w.toLowerCase()) return m[i].base;
  return null;}
var base = mb("GZGraphicD.dll");
var wndproc = base.add(0x17e2f);
Interceptor.attach(wndproc, { onEnter: function(a){
  /* the registered thunk at RVA 0x17e11 loads `this` then tail-calls here; the Win32 wndproc
     argument order (hwnd, msg, wp, lp) is preserved on the stack. */
  try { var m = this.context.esp.add(8).readU32(); counts[m] = (counts[m]||0) + 1; } catch(e){}
}});
rpc.exports = {
  reset: function(){ counts = {}; return true; },
  get:   function(){ return counts; },
  where: function(){ return wndproc.toString(); }
};
"""

# Keys worth trying: sim speed, pause, zoom, arrows, escape.
DEFAULT_KEYS = [0x20, 0x1B, 0x25, 0x26, 0x27, 0x28,
                0x31, 0x32, 0x33, 0xBB, 0xBD, 0x50, 0x5A]
NAMES = {0x20: "SPACE", 0x1B: "ESC", 0x25: "LEFT", 0x26: "UP", 0x27: "RIGHT", 0x28: "DOWN",
         0x31: "'1'", 0x32: "'2'", 0x33: "'3'", 0xBB: "'+'", 0xBD: "'-'", 0x50: "'P'", 0x5A: "'Z'"}
MSG = {0x100: "WM_KEYDOWN", 0x101: "WM_KEYUP", 0x102: "WM_CHAR", 0x104: "WM_SYSKEYDOWN",
       0x105: "WM_SYSKEYUP", 0x8: "WM_KILLFOCUS", 0x7: "WM_SETFOCUS"}


def fg() -> tuple[int, str]:
    h = user32.GetForegroundWindow()
    b = ctypes.create_unicode_buffer(90)
    user32.GetWindowTextW(h, b, 90)
    return h, b.value[:34]


def cursor() -> tuple[int, int]:
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def frame(h: int, name: str) -> Image.Image:
    OUT.mkdir(parents=True, exist_ok=True)
    sc3io.grab_to(str(OUT / name), h, settle=0.4)
    return Image.open(OUT / name).convert("RGB")


def diff_px(a: Image.Image, b: Image.Image) -> int:
    x = np.asarray(a, np.int16)
    y = np.asarray(b, np.int16)
    return int(np.count_nonzero(np.abs(x - y).max(axis=2) > 12))


def translated(a: Image.Image, b: Image.Image, rng: int = 32) -> tuple[int, int]:
    """Best (dx,dy) registering b onto a. (0,0) means the view did not move."""
    ga = np.asarray(a.convert("L").crop((100, 100, min(a.width, 1500), min(a.height, 900)))
                    .resize((300, 180)), np.float32)
    gb = np.asarray(b.convert("L").crop((100, 100, min(b.width, 1500), min(b.height, 900)))
                    .resize((300, 180)), np.float32)
    best = (0, 0, float("inf"))
    for dy in range(-rng, rng + 1, 2):
        for dx in range(-rng, rng + 1, 2):
            ax0, ax1 = max(0, dx), min(ga.shape[1], ga.shape[1] + dx)
            ay0, ay1 = max(0, dy), min(ga.shape[0], ga.shape[0] + dy)
            if ax1 - ax0 < 80 or ay1 - ay0 < 60:
                continue
            e = float(np.mean(np.abs(ga[ay0:ay1, ax0:ax1] - gb[ay0 - dy:ay1 - dy, ax0 - dx:ax1 - dx])))
            if e < best[2]:
                best = (dx, dy, e)
    zero = float(np.mean(np.abs(ga - gb)))
    return (best[0] * 4, best[1] * 4) if best[2] < zero * 0.75 else (0, 0)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keys")
    ap.add_argument("--repeat", type=int, default=4)
    a = ap.parse_args(argv)
    keys = [int(k, 0) for k in a.keys.split(",")] if a.keys else DEFAULT_KEYS

    h = sc3io.game_hwnd()
    sess = frida.attach(sc3io.game_pid())
    sc = sess.create_script(JS)
    sc.load()
    print(f"[*] wndproc hooked at {sc.exports_sync.where()}")

    fg0, c0 = fg(), cursor()
    print(f"[*] foreground before: {fg0[1]!r}   cursor {c0}")

    def burst(vk: int) -> dict:
        sc.exports_sync.reset()
        before = frame(h, f"k{vk:02x}_before.png")
        for _ in range(a.repeat):
            sc3io.key(h, vk)
            time.sleep(0.2)
        time.sleep(1.4)
        after = frame(h, f"k{vk:02x}_after.png")
        got = {int(k): v for k, v in sc.exports_sync.get().items()}
        return {"msgs": {MSG.get(k, hex(k)): v for k, v in got.items()
                         if k in (0x100, 0x101, 0x102, 0x104, 0x105)},
                "px": diff_px(before, after), "shift": translated(before, after)}

    results: dict[str, dict] = {}

    print("\n=== ARM A: NOT focused (the mode this tooling actually runs in) ===")
    for vk in keys:
        r = burst(vk)
        results[f"A{vk}"] = r
        print(f"  {NAMES.get(vk, hex(vk)):7} arrived={r['msgs'] or 'NOTHING'}  "
              f"px={r['px']:<7} shift={r['shift']}")

    print(f"\n  focus still {fg()[1]!r} (unchanged: {fg()[0] == fg0[0]}), "
          f"cursor unchanged: {cursor() == c0}")

    print("\n=== ARM B: WITH focus (control - this arm deliberately takes foreground) ===")
    try:
        sc3io.require_focus_optin("the keyboard probe's focused control arm")
    except RuntimeError as e:
        print(f"  SKIPPED.\n  {e}")
        sess.detach()
        return 0
    user32.SetForegroundWindow(wintypes.HWND(h))
    time.sleep(1.0)
    print(f"  foreground now {fg()[1]!r}  game focused: {fg()[0] == h}")
    for vk in keys:
        r = burst(vk)
        results[f"B{vk}"] = r
        print(f"  {NAMES.get(vk, hex(vk)):7} arrived={r['msgs'] or 'NOTHING'}  "
              f"px={r['px']:<7} shift={r['shift']}")

    # Give focus back to whatever had it. Only reachable when Arm B ran, which already required
    # the opt-in - but re-assert it here: putting focus anywhere is itself a focus operation, and
    # this line must not become reachable if the control flow above is ever changed.
    sc3io.require_focus_optin("restoring the previous foreground window after the control arm")
    if fg0[0] and user32.IsWindow(fg0[0]):
        user32.SetForegroundWindow(wintypes.HWND(fg0[0]))
        time.sleep(0.5)
    print(f"\n[*] foreground restored to {fg()[1]!r}; cursor unchanged: {cursor() == c0}")

    print("\n=== VERDICT ===")
    noise = max([results[f"A{k}"]["px"] for k in keys] + [1])
    print(f"  (idle/pixel noise ceiling across the unfocused arm: {noise} px)")
    any_arrive_nofocus = any(results[f"A{k}"]["msgs"] for k in keys)
    any_arrive_focus = any(results[f"B{k}"]["msgs"] for k in keys)
    print(f"  keys ARRIVE at the WndProc without focus : {any_arrive_nofocus}")
    print(f"  keys ARRIVE at the WndProc with focus    : {any_arrive_focus}")
    for k in keys:
        A, B = results[f"A{k}"], results[f"B{k}"]
        if B["shift"] != (0, 0) or B["px"] > noise * 2:
            print(f"  {NAMES.get(k, hex(k))} ACTS when focused (px {B['px']}, shift {B['shift']}) "
                  f"-> unfocused: px {A['px']}, shift {A['shift']}")
    sess.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
