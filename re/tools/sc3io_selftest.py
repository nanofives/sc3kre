"""Prove sc3io's invariants against the LIVE game, dynamically and statically.

Invariants under test:
  1. sc3io never calls a cursor-moving or focus-stealing Win32 entry point.
  2. The foreground window does not change - the game never takes focus.
  3. `raise_without_focus` changes Z-order only: it must not move or resize the window.
  4. A grab either returns a credible frame or raises. It never returns a suspect image.

How invariant 1 is proven: the banned entry points are POISONED before sc3io is imported. The
test monkeypatches `ctypes.WinDLL` so sc3io's `user32` handle is a proxy that raises on
`SetCursorPos`, `mouse_event`, `SendInput`, `SetForegroundWindow` and friends. Then the full
exercise runs. If any code path in sc3io reached for one of them, the exercise raises here rather
than quietly moving the user's mouse. This is a real guarantee, unlike a before/after cursor
sample - which is worthless on this machine because `SmartLife\\scripts\\keychron_m3\\ha_bridge.py`
and the user's own hand move the cursor constantly (measured 2026-09-07: the cursor moved during
a 1.5 s window in which no sc3io call was made at all).

A before/after cursor sample is still taken, but only as an advisory: a baseline idle probe first
decides whether the cursor is externally driven, and if it is, the sample is reported INCONCLUSIVE
instead of being scored.

    python re/tools/sc3io_selftest.py
"""

from __future__ import annotations

import ctypes
import pathlib
import re
import sys
import time
from ctypes import wintypes

BANNED = [
    "SetCursorPos", "mouse_event", "SendInput", "keybd_event",
    "SetForegroundWindow", "BringWindowToTop", "SetActiveWindow", "SetFocus",
    "SetCapture", "SwitchToThisWindow", "AttachThreadInput",
]

_violations: list[str] = []


class _PoisonedDLL:
    """Wraps a real WinDLL and raises on any banned entry point."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        if name in BANNED:
            def _boom(*_a, **_k):
                _violations.append(name)
                raise AssertionError(
                    f"sc3io called the BANNED entry point {name}() - it must never touch the "
                    "cursor or the foreground window"
                )
            return _boom
        return getattr(self._real, name)


_real_windll = ctypes.WinDLL


def _patched_windll(name, *a, **k):
    real = _real_windll(name, *a, **k)
    if name.lower().startswith("user32"):
        return _PoisonedDLL(real)
    return real


ctypes.WinDLL = _patched_windll          # must happen BEFORE importing sc3io
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io                              # noqa: E402
ctypes.WinDLL = _real_windll

# The test's own handle is the real one - the test is allowed to observe.
user32 = _real_windll("user32", use_last_error=True)


def cursor() -> tuple[int, int]:
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def foreground() -> tuple[int, str]:
    h = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(h, buf, 256)
    cls = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(h, cls, 64)
    return h, f"0x{h:08X} [{cls.value}] {buf.value!r}"


def source_audit() -> list[str]:
    """Banned names may appear in prose, never as a call."""
    src = pathlib.Path(sc3io.__file__).read_text(encoding="utf-8")
    bad = []
    for i, line in enumerate(src.splitlines(), 1):
        s = line.strip()
        if s.startswith("#") or s.startswith("*"):
            continue
        for name in BANNED:
            if re.search(rf"\b(?:user32\.)?{name}\s*\(", line):
                bad.append(f"sc3io.py:{i}: calls {name}: {s}")
    return bad


def cursor_is_externally_driven(seconds: float = 1.2) -> tuple[int, int] | None:
    """Watch the cursor while doing nothing. A move here means something else drives it."""
    start = cursor()
    deadline = time.time() + seconds
    while time.time() < deadline:
        if cursor() != start:
            return cursor()
        time.sleep(0.05)
    return None


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []

    print("== 1. static audit ==")
    audit = source_audit()
    if audit:
        fails += audit
        for a in audit:
            print(f"   FAIL {a}")
    else:
        print(f"   PASS none of the {len(BANNED)} banned entry points is called in sc3io.py")
    print("   (and they are poisoned at runtime for the exercise below)")

    print("\n== 2. baseline ==")
    ext = cursor_is_externally_driven()
    c0 = cursor()
    f0 = foreground()
    print(f"   cursor     : {c0}")
    print(f"   foreground : {f0[1]}")
    if ext:
        notes.append(
            "the cursor is being moved by something outside this test (it drifted during an idle "
            "probe), so the before/after cursor sample is INCONCLUSIVE - invariant 1 rests on the "
            "poisoned entry points, which is the stronger proof anyway"
        )
        print(f"   cursor is EXTERNALLY DRIVEN (drifted to {ext} while idle)")
    else:
        print("   cursor is quiet - the before/after sample is meaningful")

    print("\n== 3. gate + grab ==")
    try:
        g = sc3io.check()
    except sc3io.CaptureError as e:
        print(f"   STOP: {e}")
        return 2
    if not g.ok:
        print("   gate BLOCKED - cannot exercise:")
        for p in g.problems:
            print(f"     - {p}")
        return 2
    h = g.hwnd
    print(f"   gate       : OK  hwnd 0x{h:08X}  client {g.w}x{g.h}  dpi {g.scale:.3f}x")

    rect_before = sc3io._window_rect(h)
    sc3io.raise_without_focus(h)
    time.sleep(0.25)
    rect_after = sc3io._window_rect(h)
    if rect_before != rect_after:
        fails.append(f"raise_without_focus MOVED/RESIZED the window {rect_before} -> {rect_after}")
    else:
        print(f"   raise      : Z-order only, rect unchanged {rect_before}")

    try:
        gr = sc3io.grab(h)
    except sc3io.CaptureError as e:
        print(f"   STOP: {e}")
        return 2
    print(f"   grab       : {gr.img.width}x{gr.img.height} credible frame")

    print("\n== 4. input exercise (PostMessage only) ==")
    vw = int(round(g.w / (g.scale or 1)))
    vh = int(round(g.h / (g.scale or 1)))
    cx, cy = vw // 2, vh // 2
    try:
        sc3io.move(h, vw - 40, vh - 200)
        print("   hover      : 3x WM_MOUSEMOVE")
        sc3io.click(h, vw - 40, vh - 200)
        print("   click      : WM_LBUTTONDOWN/UP")
        sc3io.drag(h, cx, cy, cx - 60, cy - 40, button="right", steps=6)
        print("   right-drag : down + 6 moves + up")
        sc3io.wheel(h, cx, cy, notches=-1)
        print("   wheel      : WM_MOUSEWHEEL -1")
    except AssertionError as e:
        fails.append(str(e))
        print(f"   FAIL {e}")

    print("\n== 5. after ==")
    c1 = cursor()
    f1 = foreground()
    print(f"   cursor     : {c1}")
    print(f"   foreground : {f1[1]}")

    if _violations:
        fails.append(f"banned entry points were called: {sorted(set(_violations))}")
    else:
        print("   PASS no banned entry point was reached during the exercise")

    if f1[0] != f0[0]:
        fails.append(f"FOREGROUND CHANGED\n         was {f0[1]}\n         now {f1[1]}")
    else:
        print("   PASS foreground window unchanged")
    if f1[0] == h:
        fails.append("the GAME is now the foreground window - it took focus")

    if ext:
        print(f"   SKIP cursor sample (externally driven): {c0} -> {c1}")
    elif c1 != c0:
        fails.append(f"CURSOR MOVED {c0} -> {c1} with no banned call - investigate")
    else:
        print("   PASS cursor did not move")

    print()
    for n in notes:
        print(f"NOTE: {n}")
    if fails:
        print("\nSELFTEST FAILED:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nSELFTEST PASSED: capture works, cursor APIs unreachable, focus untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
