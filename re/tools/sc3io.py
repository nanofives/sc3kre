"""sc3io - the ONE way to see the game and the ONE way to drive it.

Hard rules this module enforces, by construction:

  * NEVER moves the physical cursor. `SetCursorPos`, `mouse_event` and `SendInput` are not
    imported and not called. All mouse input is `PostMessageW` to the game's own HWND.
  * NEVER takes foreground. `SetForegroundWindow`, `SetActiveWindow`, `BringWindowToTop` and
    `SetFocus` are not called. The window is raised with `SetWindowPos(HWND_TOPMOST,
    SWP_NOACTIVATE)`, which changes Z-order without changing focus or the active window.
  * ONE capture method, no fallback. Desktop-DC `BitBlt` at the window's screen rect. That is the
    only method measured to see this game's DirectDraw layer: `PrintWindow`, window-DC `BitBlt`
    and the in-process surface dumper (`iso+0x4ec`, `bits=0` after any resize) all do NOT.
    See re/analysis/RESIZABLE_WINDOW.md and the project memory note on screen-grab + shear.
  * If a grab cannot be TRUSTED, this raises `CaptureError` and writes nothing. It does not try a
    second method and it does not return a suspect image. Callers must let that propagate.

Why a gate is needed at all: desktop-DC capture reads whatever is physically on the screen. If
another window overlaps the game, or the game is minimised, or it is off-screen, the pixels come
back real-looking and WRONG. Every one of those states is checked BEFORE the blit and the frame is
sanity-checked AFTER it.

DPI - READ THIS, the obvious model is BACKWARDS and it cost a wrong conclusion:

  * The game is DPI-UNAWARE. It renders at a VIRTUAL client size (e.g. 800x600) and Windows
    upscales to PHYSICAL (1000x750 at 125%).
  * Capture runs DPI-AWARE, so a grab is in PHYSICAL pixels and matches the glass 1:1.
  * ⭐ INPUT COORDINATES ARE **PHYSICAL** TOO - the same space as the grab. Windows scales the
    lParam of a posted message DOWN into the DPI-unaware window's virtual space for us.
    MEASURED 2026-09-07 by reading the coordinate back from inside the engine (GZWIND window
    manager, slot +0x64, `mgr+0x170/+0x174`): posting x=765 arrived as x=612 (x0.8 = 1/1.25);
    posting x=956 arrived as x=765, the wanted virtual coordinate.

  **So a pixel you read off a `grab` PNG is DIRECTLY clickable. No conversion.** That is the rule
  to remember. The previous docstring here said input takes VIRTUAL coords; that was wrong, and
  acting on it produced clicks that landed ~20% off - which then masqueraded as "input does not
  work when the window is minimised" (it does; see below).

  `Grab.scale` is the physical/virtual factor, and note `GetDpiForWindow` is NOT a reliable source
  for it - it returned 96 (1.0x) in a state where the true factor was 1.25. Trust the measured
  ratio (physical client / the engine's stored rect at `win+0x38..0x44`), not the DPI API.

WINDOW STATE: input needs neither focus NOR screen presence. Measured 2026-09-07 across visible /
buried-under-a-topmost-cover / SW_MINIMIZE / SW_SHOWMINNOACTIVE / off-screen: the WndProc receives
every message and the window manager dispatches it at the SAME coordinate in all of them, and a
click on a side-panel tool button switched the tool while the window was MINIMISED (15 rows of the
panel subtree changed). Only CAPTURE needs the window unoccluded - which is why `raise_without_focus`
exists and why it is called by `check()`/`grab()` and by nothing on the input path.

GetDIBits pads every row to a 4-byte boundary; decoding with a packed w*3 stride shears the image
diagonally at widths where w*3 is not a multiple of 4 (physical 1250 is one). The real DWORD
stride is used for both the buffer and the PIL decode.

CLI:
    python re/tools/sc3io.py --check                 # gate only, no file written; exit 0 = grabbable
    python re/tools/sc3io.py --grab out.png          # grab or fail
    python re/tools/sc3io.py --info                  # window/DPI/z-order report
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass

from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GAME_EXE = "SC3U.exe"
GAME_CLASS = "Gonzo"          # the game's main window class
BORDER_SLOP = 2               # px of window edge allowed to be covered without failing the gate

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000       # include layered/topmost windows in the blit

SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
GW_HWNDPREV = 3

DWMWA_CLOAKED = 14

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0204, 0x0205
WM_MOUSEWHEEL = 0x020A
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SIZING = 0x0214
MK_LBUTTON, MK_RBUTTON = 0x0001, 0x0002

WMSZ = {  # WM_SIZING wParam edge codes
    "left": 1, "right": 2, "top": 3,
    "topleft": 4, "topright": 5, "bottom": 6,
    "bottomleft": 7, "bottomright": 8,
}


class CaptureError(RuntimeError):
    """A trustworthy grab was not possible. There is deliberately no fallback."""


class GameNotFound(CaptureError):
    pass


# ---------------------------------------------------------------------------------------------
# DPI: per-monitor-v2 so GetWindowRect/BitBlt are in physical pixels.
# ---------------------------------------------------------------------------------------------

def _make_dpi_aware() -> None:
    try:
        # -4 = DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except AttributeError:
        user32.SetProcessDPIAware()


_make_dpi_aware()


def _dpi_scale(hwnd: int) -> float:
    try:
        return user32.GetDpiForWindow(hwnd) / 96.0
    except AttributeError:
        return 1.0


# ---------------------------------------------------------------------------------------------
# Window discovery
# ---------------------------------------------------------------------------------------------

def game_pid() -> int:
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {GAME_EXE}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    ).stdout
    if GAME_EXE.split(".")[0] not in out:
        raise GameNotFound(
            f"{GAME_EXE} is not running. Launch it (re/harness/bin/resize_launch.exe) first."
        )
    pids = []
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) > 1:
            try:
                pids.append(int(parts[1].strip('" ')))
            except ValueError:
                pass
    if not pids:
        raise GameNotFound(f"tasklist listed {GAME_EXE} but no pid could be parsed:\n{out}")
    if len(pids) > 1:
        raise CaptureError(
            f"{len(pids)} {GAME_EXE} processes are running (pids {pids}). The game is "
            "single-instance by design; this is a stale process. Refusing to guess which to drive."
        )
    return pids[0]


_ENUM_CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def game_hwnd(pid: int | None = None) -> int:
    """The game's main 'Gonzo' window. Raises if it is absent or ambiguous."""
    pid = game_pid() if pid is None else pid
    found: list[int] = []

    def cb(h, _l):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(h, buf, 64)
            if buf.value == GAME_CLASS:
                found.append(h)
        return True

    user32.EnumWindows(_ENUM_CB(cb), 0)
    if not found:
        raise GameNotFound(
            f"pid {pid} is alive but has no visible '{GAME_CLASS}' window yet. The game is still "
            "booting, or it is showing the intro movie, or it has already lost its window."
        )
    if len(found) > 1:
        # Largest client area wins would be a guess; refuse instead.
        raise CaptureError(f"pid {pid} has {len(found)} visible '{GAME_CLASS}' windows: {found}")
    return found[0]


def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def client_rect_on_screen(hwnd: int) -> tuple[int, int, int, int]:
    """(x, y, w, h) of the CLIENT area in physical screen pixels."""
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, r.right - r.left, r.bottom - r.top


def _is_cloaked(hwnd: int) -> bool:
    v = wintypes.DWORD(0)
    if dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(v), ctypes.sizeof(v)
    ) != 0:
        return False
    return bool(v.value)


def _title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    cls = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, cls, 64)
    return f"0x{hwnd:08X} [{cls.value}] {buf.value!r}"


def occluders(hwnd: int, rect: tuple[int, int, int, int] | None = None) -> list[str]:
    """Visible, non-cloaked windows ABOVE `hwnd` in Z-order whose rect overlaps `rect`.

    Walks the Z-order upward from the game window. Anything returned here would appear in a
    desktop-DC blit INSTEAD of the game, which is exactly the silent-wrong-pixels failure.
    """
    if rect is None:
        rect = _window_rect(hwnd)
    gl, gt, gr, gb = rect
    gl, gt, gr, gb = gl + BORDER_SLOP, gt + BORDER_SLOP, gr - BORDER_SLOP, gb - BORDER_SLOP
    bad: list[str] = []
    h = hwnd
    while True:
        h = user32.GetWindow(h, GW_HWNDPREV)   # PREV in Z-order == drawn on top
        if not h:
            break
        if not user32.IsWindowVisible(h) or user32.IsIconic(h) or _is_cloaked(h):
            continue
        l, t, r, b = _window_rect(h)
        if r <= l or b <= t:
            continue
        if l < gr and r > gl and t < gb and b > gt:
            # A full-screen-sized shell window with an empty rect region still counts: we cannot
            # cheaply prove it is transparent, so we report it and let the caller decide.
            bad.append(f"{_title(h)} rect=({l},{t},{r},{b})")
    return bad


# ---------------------------------------------------------------------------------------------
# Making the window grabbable WITHOUT touching focus or the cursor
# ---------------------------------------------------------------------------------------------

def raise_without_focus(hwnd: int) -> None:
    """Un-minimise and put on top, without activating.

    `SW_SHOWNOACTIVATE` restores without stealing activation. `SetWindowPos(HWND_TOPMOST,
    SWP_NOACTIVATE)` changes Z-order only. Neither gives the window keyboard focus, and neither
    touches the cursor. Whatever the user is typing into keeps focus.
    """
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
        time.sleep(0.4)
    user32.SetWindowPos(
        wintypes.HWND(hwnd), HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
    )


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT), ("flags", wintypes.UINT), ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT), ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


SW_SHOWMAXIMIZED = 3
SW_SHOWNORMAL = 1


def _set_show_cmd(hwnd: int, show_cmd: int) -> None:
    """Change the window's show state WITHOUT activating it.

    `ShowWindow(SW_MAXIMIZE)` and `ShowWindow(SW_RESTORE)` both ACTIVATE the window - that is how
    the old tools (and verify/resize_clicklab/drive.ps1) stole focus on every maximize.
    `SetWindowPlacement` sets the same state and does not activate. This is the whole difference.
    """
    wp = _WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(_WINDOWPLACEMENT)
    if not user32.GetWindowPlacement(wintypes.HWND(hwnd), ctypes.byref(wp)):
        raise RuntimeError(f"GetWindowPlacement failed: {ctypes.get_last_error()}")
    wp.showCmd = show_cmd
    if not user32.SetWindowPlacement(wintypes.HWND(hwnd), ctypes.byref(wp)):
        raise RuntimeError(f"SetWindowPlacement failed: {ctypes.get_last_error()}")
    time.sleep(0.5)


def maximize_without_focus(hwnd: int) -> tuple[int, int]:
    """Maximize and return the resulting (client_w, client_h). Does not activate."""
    _set_show_cmd(hwnd, SW_SHOWMAXIMIZED)
    _, _, w, h = client_rect_on_screen(hwnd)
    return w, h


def restore_without_focus(hwnd: int) -> tuple[int, int]:
    """Restore to the normal (pre-maximize) rect. Does not activate.

    ⚠️ Restoring from MINIMISED is the one case where `SW_SHOWNORMAL` does activate - measured
    2026-09-07: the foreground went from 'WhatsApp Beta' to 'SimCity 3000' across this call.
    `SW_SHOWNOACTIVATE` restores the same window without taking focus, so it is used whenever the
    window is currently iconic. Restoring down from MAXIMISED does not activate either way.
    """
    _set_show_cmd(hwnd, SW_SHOWNOACTIVATE if user32.IsIconic(hwnd) else SW_SHOWNORMAL)
    _, _, w, h = client_rect_on_screen(hwnd)
    return w, h


def is_maximized(hwnd: int) -> bool:
    return bool(user32.IsZoomed(wintypes.HWND(hwnd)))


def drop_topmost(hwnd: int) -> None:
    """Give the window back to the normal Z-order (still without activating it)."""
    user32.SetWindowPos(
        wintypes.HWND(hwnd), HWND_NOTOPMOST, 0, 0, 0, 0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
    )


# ---------------------------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------------------------

@dataclass
class Gate:
    hwnd: int
    pid: int
    x: int
    y: int
    w: int
    h: int
    scale: float
    problems: list[str]

    @property
    def ok(self) -> bool:
        return not self.problems


def check(hwnd: int | None = None, raise_first: bool = True) -> Gate:
    """Everything that must be true for a desktop-DC blit to be the real frame."""
    pid = game_pid()
    hwnd = game_hwnd(pid) if hwnd is None else hwnd
    if raise_first:
        raise_without_focus(hwnd)
        time.sleep(0.15)

    problems: list[str] = []

    if not user32.IsWindow(hwnd):
        problems.append(f"hwnd 0x{hwnd:08X} is no longer a window")
    if user32.IsIconic(hwnd):
        problems.append("the window is MINIMISED - a desktop blit would capture the desktop")
    if _is_cloaked(hwnd):
        problems.append("the window is DWM-CLOAKED (other virtual desktop / hidden UWP state)")

    x, y, w, h = client_rect_on_screen(hwnd)
    if w <= 0 or h <= 0:
        problems.append(f"client area is degenerate: {w}x{h}")

    wl, wt, wr, wb = _window_rect(hwnd)
    mon = user32.MonitorFromWindow(wintypes.HWND(hwnd), 0)   # MONITOR_DEFAULTTONULL
    if not mon:
        problems.append(f"the window rect ({wl},{wt},{wr},{wb}) is not on any monitor")
    else:
        vx = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        vy = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
        vw = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
        vh = user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
        if x < vx or y < vy or x + w > vx + vw or y + h > vy + vh:
            problems.append(
                f"the client rect ({x},{y},{w}x{h}) extends outside the virtual desktop "
                f"({vx},{vy},{vw}x{vh}) - the off-screen part cannot be captured"
            )

    occ = occluders(hwnd, (wl, wt, wr, wb))
    if occ:
        problems.append(
            "another window is ON TOP of the game and would be captured instead:\n      - "
            + "\n      - ".join(occ)
        )

    return Gate(hwnd, pid, x, y, w, h, _dpi_scale(hwnd), problems)


# ---------------------------------------------------------------------------------------------
# The one capture method
# ---------------------------------------------------------------------------------------------

class _BMI(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
        ("biXPPM", wintypes.LONG), ("biYPPM", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD), ("biClrImp", wintypes.DWORD),
    ]


@dataclass
class Grab:
    img: Image.Image
    gate: Gate

    @property
    def scale(self) -> float:
        return self.gate.scale

    def to_client(self, px: int, py: int) -> tuple[int, int]:
        """A pixel in this image -> the coord to feed the input helpers. IDENTITY, deliberately.

        Kept as a named call so the intent is explicit at every call site, but it does NOT scale:
        input lParam is in the same PHYSICAL space as this image (see the DPI note in the module
        docstring). This used to divide by `scale`, which sent every click ~20% off-target.
        """
        return px, py

    def to_engine(self, px: int, py: int) -> tuple[int, int]:
        """A pixel in this image -> the VIRTUAL coord the engine will actually see.

        Only for comparing against rects read out of the engine (which are virtual), never for
        feeding the input helpers.
        """
        s = self.scale or 1.0
        return int(round(px * s)), int(round(py * s))

    def save(self, path: str) -> str:
        d = os.path.dirname(os.path.abspath(path))
        if d:
            os.makedirs(d, exist_ok=True)
        self.img.save(path)
        return path


def _blit(x: int, y: int, w: int, h: int) -> Image.Image:
    desktop = user32.GetDC(0)
    if not desktop:
        raise CaptureError("GetDC(0) failed - no desktop DC available")
    memdc = gdi32.CreateCompatibleDC(desktop)
    bmp = gdi32.CreateCompatibleBitmap(desktop, w, h)
    try:
        gdi32.SelectObject(memdc, bmp)
        if not gdi32.BitBlt(memdc, 0, 0, w, h, desktop, x, y, SRCCOPY | CAPTUREBLT):
            raise CaptureError(f"BitBlt failed: GetLastError={ctypes.get_last_error()}")
        bi = _BMI()
        bi.biSize = ctypes.sizeof(_BMI)
        bi.biWidth = w
        bi.biHeight = -h          # top-down
        bi.biPlanes = 1
        bi.biBitCount = 24
        bi.biCompression = 0
        stride = ((w * 3 + 3) // 4) * 4    # GetDIBits pads rows to DWORD; packed w*3 shears
        buf = ctypes.create_string_buffer(stride * h)
        if gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), 0) == 0:
            raise CaptureError("GetDIBits returned 0 scanlines")
        return Image.frombuffer("RGB", (w, h), buf, "raw", "BGR", stride, 1)
    finally:
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(0, desktop)


def _frame_problems(img: Image.Image) -> list[str]:
    """Post-blit sanity. Catches an all-black / uniform / DC-failure frame that blits fine."""
    bad: list[str] = []
    small = img.resize((min(img.width, 256), min(img.height, 256)))
    colors = small.getcolors(maxcolors=1 << 20) or []
    n = len(colors)
    if n <= 1:
        rgb = colors[0][1] if colors else "?"
        bad.append(f"the frame is a single flat colour {rgb} - not a rendered game frame")
    elif n < 12:
        bad.append(f"the frame has only {n} distinct colours - it is not a rendered game frame")
    total = small.width * small.height
    if colors:
        top_count, top_rgb = max(colors)
        if top_count / total > 0.995:
            bad.append(
                f"{100 * top_count / total:.1f}% of the frame is one colour {top_rgb} - "
                "the game is very likely not presenting"
            )
    return bad


def grab(hwnd: int | None = None, settle: float = 0.0) -> Grab:
    """Capture the true composited frame, or raise. No fallback method is attempted."""
    g = check(hwnd)
    if not g.ok:
        raise CaptureError(
            "CANNOT TAKE A TRUSTWORTHY SCREENSHOT - stopping instead of returning a suspect "
            "image.\n  " + "\n  ".join(g.problems)
        )
    if settle:
        time.sleep(settle)
    img = _blit(g.x, g.y, g.w, g.h)

    # Re-check the gate AFTER the blit: a window could have popped up mid-grab.
    after = check(g.hwnd, raise_first=False)
    if not after.ok:
        raise CaptureError(
            "the window state changed DURING the grab, so the captured pixels are not "
            "trustworthy:\n  " + "\n  ".join(after.problems)
        )
    if (after.x, after.y, after.w, after.h) != (g.x, g.y, g.w, g.h):
        raise CaptureError(
            f"the window moved/resized during the grab: ({g.x},{g.y},{g.w}x{g.h}) -> "
            f"({after.x},{after.y},{after.w}x{after.h}). Re-grab."
        )

    fp = _frame_problems(img)
    if fp:
        raise CaptureError(
            "the blit succeeded but the FRAME IS NOT CREDIBLE - stopping rather than saving "
            "it:\n  " + "\n  ".join(fp)
            + "\n  (the game may still be on the intro movie, mid-load, or not presenting at all)"
        )
    return Grab(img, g)


def grab_to(path: str, hwnd: int | None = None, settle: float = 0.0) -> Grab:
    gr = grab(hwnd, settle)
    gr.save(path)
    return gr


# ---------------------------------------------------------------------------------------------
# Input - PostMessage only. No cursor, no focus, no SendInput.
# ---------------------------------------------------------------------------------------------

def _lp(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def _post(hwnd: int, msg: int, wp: int, lp: int) -> None:
    if not user32.PostMessageW(wintypes.HWND(hwnd), msg, wintypes.WPARAM(wp), wintypes.LPARAM(lp)):
        raise RuntimeError(
            f"PostMessageW(0x{msg:04X}) to 0x{hwnd:08X} failed: {ctypes.get_last_error()}"
        )


def move(hwnd: int, x: int, y: int, repeat: int = 3, delay: float = 0.06) -> None:
    """Hover. Coords are PHYSICAL - the same space as a grab. Cursor is not touched.

    Repeated because some of this UI only latches a hover after more than one move.
    """
    for _ in range(repeat):
        _post(hwnd, WM_MOUSEMOVE, 0, _lp(x, y))
        time.sleep(delay)


def click(hwnd: int, x: int, y: int, button: str = "left", hold: float = 0.12) -> None:
    down, up, mk = (
        (WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON) if button == "right"
        else (WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON)
    )
    lp = _lp(x, y)
    _post(hwnd, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.08)
    _post(hwnd, down, mk, lp)
    time.sleep(hold)
    _post(hwnd, up, 0, lp)


def drag(hwnd: int, x0: int, y0: int, x1: int, y1: int, button: str = "right",
         steps: int = 12, delay: float = 0.05) -> None:
    """Press, move in `steps` interpolated WM_MOUSEMOVEs with the button bit set, release.

    This is how the map is panned (right-drag) without touching the cursor.
    """
    down, up, mk = (
        (WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON) if button == "right"
        else (WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON)
    )
    _post(hwnd, WM_MOUSEMOVE, 0, _lp(x0, y0))
    time.sleep(0.08)
    _post(hwnd, down, mk, _lp(x0, y0))
    time.sleep(0.15)
    steps = max(1, steps)
    for s in range(1, steps + 1):
        _post(hwnd, WM_MOUSEMOVE, mk,
              _lp(x0 + (x1 - x0) * s // steps, y0 + (y1 - y0) * s // steps))
        time.sleep(delay)
    time.sleep(0.15)
    _post(hwnd, up, 0, _lp(x1, y1))


def wheel(hwnd: int, x: int, y: int, notches: int = 1) -> None:
    """WM_MOUSEWHEEL takes SCREEN coords in lParam, unlike every other mouse message."""
    pt = wintypes.POINT(x, y)
    user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(pt))
    _post(hwnd, WM_MOUSEWHEEL, (120 * notches) << 16, _lp(pt.x, pt.y))


def key(hwnd: int, vk: int, hold: float = 0.05) -> None:
    """Post a key. Like the mouse helpers, this needs NO focus - measured and decompiled.

    Delivery is proven focus-free two ways (2026-09-07):
      * Measured: with the game unfocused, the WndProc counted WM_KEYDOWN 4, WM_KEYUP 4 and
        WM_CHAR 4 for 4 posted keys. (WM_CHAR appears because the game's message loop calls
        TranslateMessage; arrows produce no WM_CHAR, as expected.)
      * Decompiled: the WndProc handles 0x100 WM_KEYDOWN, 0x101 WM_KEYUP, 0x102 WM_CHAR,
        0x104/0x105 WM_SYSKEY* and forwards each to the window-manager sink slot **+0x68**
        (the mouse path is +0x64). Its ONLY gate is `this+0x30 != 0` (a sink being installed).
        There is no GetFocus/GetActiveWindow/IsIconic check anywhere in it.
        `WM_ACTIVATE` (0x6) only calls sink `vt+0x74(0)`, which clears the capture window - it
        does not gate input. [CONFIRMED @ GZGraphicD 0x10017e2f]
      * Confirmed END TO END by hooking the sink's `+0x68` slot itself, game unfocused. Posting
        3 keys produced: SPACE 9 hits, '3' 9, ESC 9, RIGHT 6. That is exactly
        3 x (KEYDOWN + KEYUP + CHAR) for character keys and 3 x (KEYDOWN + KEYUP) for an arrow,
        which generates no WM_CHAR - the counts match the decompiled message set precisely.
        A mouse click control hit `+0x64` 4 times in the same run.

    ⚠️ What is NOT established: that any given key DOES anything. No key tried (SPACE, ESC,
    arrows, '1'-'3', '+', '-', 'P', 'Z') produced a visible change. The engine keeps its OWN focus
    window at `sink+0x2c`, separate from the OS one, and that is what decides which in-game window
    receives a key - so a key may be arriving correctly and simply going to a window with no
    binding. The focused control arm that would separate these is not runnable from here:
    Windows blocks SetForegroundWindow from a background process, so the "focused" arm measured
    unfocused too. Treat key EFFECTS as unverified; key DELIVERY is verified.
    """
    _post(hwnd, WM_KEYDOWN, vk, 1)
    time.sleep(hold)
    _post(hwnd, WM_KEYUP, vk, 0xC0000001)


def require_cursor_optin(what: str) -> None:
    """Guard for the few RE experiments that GENUINELY need the physical cursor.

    Two things in this repo cannot be done with messages, because the behaviour under test is a
    property of the real cursor: (a) Windows' sizing modal loop, which reads GetCursorPos, and
    (b) the posted-vs-real click A/B in click_probe.py, whose whole point is that the game may
    treat them differently. Those arms are not deleted - they are made impossible to reach by
    accident. Nothing else may call this.

    Set SC3IO_ALLOW_CURSOR=1 to opt in for one invocation.
    """
    if os.environ.get("SC3IO_ALLOW_CURSOR") != "1":
        raise RuntimeError(
            f"REFUSED: {what} needs the PHYSICAL CURSOR, which this tooling does not use.\n"
            "  The default path is message-based (PostMessage) so it never touches your mouse or\n"
            "  your focus. This arm exists only as an RE control and is opted into explicitly:\n"
            "    SC3IO_ALLOW_CURSOR=1 python <tool> ...\n"
            "  Be aware it WILL move your cursor and take foreground while it runs."
        )


def require_focus_optin(what: str) -> None:
    """Guard for the rare experiment that must genuinely TAKE FOCUS.

    Same principle as require_cursor_optin: the arm is not deleted, it is made impossible to reach
    by accident. The only legitimate use so far is the control arm of the keyboard focus probe -
    and note that arm does NOT work from a background process anyway: Windows blocks
    SetForegroundWindow, so it silently measures the unfocused case (observed 2026-09-07).

    Set SC3IO_ALLOW_FOCUS=1 to opt in for one invocation.
    """
    if os.environ.get("SC3IO_ALLOW_FOCUS") != "1":
        raise RuntimeError(
            f"REFUSED: {what} would TAKE FOCUS, which this tooling never does.\n"
            "  Opt in explicitly for a one-off control arm:\n"
            "    SC3IO_ALLOW_FOCUS=1 python <tool> ...\n"
            "  Note Windows blocks SetForegroundWindow from a background process, so this arm may\n"
            "  measure the UNFOCUSED case regardless - check GetForegroundWindow afterwards."
        )


# ---------------------------------------------------------------------------------------------
# Scrolling the city view.
#
# ⚠️ THIS IS THE ONE INPUT PATH THAT IS NOT PURE PostMessage, and it is not a choice.
#
# The city view's arrow-scroll handler ignores the key code it is handed and re-reads the CURRENT
# PHYSICAL state of all four arrows from a keyboard device whose implementation is
#     ushort GZWIND FUN_10025790(int vk) { return GetAsyncKeyState(vk) >> 0xf; }
#                                                         [CONFIRMED @ GZWIND 0x10025790]
# `GetAsyncKeyState` reads hardware, which PostMessage cannot touch, so posted arrows can never
# scroll - by design, not a defect. See verify/offscreen/KEY_BINDINGS_RUNTIME.md for the full chain.
#
# So scrolling needs ONE of: (a) fake hardware input via SendInput/keybd_event - rejected, that is
# exactly what this module must never do; or (b) intercept that single 19-byte leaf function.
# We do (b). The cursor is still never moved and focus is still never taken. The hook is scoped to
# the scroll and removed by `end_scroll()`.
#
# The same limitation applies to MODIFIERS: the event's modifier word is built from GetKeyState, so
# a posted key always arrives with Ctrl/Shift/Alt clear. Modified input would need the same trick.
# ---------------------------------------------------------------------------------------------

SCROLL_VK = {"up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27}

_SCROLL_JS = r"""
var spoof = {};
var base = null;
var mods = Process.enumerateModules();
for (var i = 0; i < mods.length; i++)
  if (mods[i].name.toLowerCase() === "gzwind.dll") base = mods[i].base;
Interceptor.attach(base.add(0x25790), {
  onEnter: function (a) { this.vk = a[0].toInt32(); },
  onLeave: function (r) { if (spoof[this.vk]) r.replace(1); }
});
rpc.exports = {
  set:   function (vks) { spoof = {}; vks.forEach(function (v) { spoof[v] = true; }); return true; },
  clear: function () { spoof = {}; return true; }
};
"""

_scroll_session = None
_scroll_script = None


def _scroll_script_get():
    """Attach lazily and cache - attaching per scroll costs ~1 s."""
    global _scroll_session, _scroll_script
    if _scroll_script is None:
        import frida                      # only needed for scrolling; keep sc3io importable without it
        _scroll_session = frida.attach(game_pid())
        _scroll_script = _scroll_session.create_script(_SCROLL_JS)
        _scroll_script.load()
    return _scroll_script


def end_scroll() -> None:
    """Remove the key-state hook. Safe to call when no scroll session is open."""
    global _scroll_session, _scroll_script
    if _scroll_script is not None:
        try:
            _scroll_script.exports_sync.clear()
        except Exception:
            pass
    if _scroll_session is not None:
        try:
            _scroll_session.detach()
        except Exception:
            pass
    _scroll_session, _scroll_script = None, None


def scroll(hwnd: int, direction: str | list[str], taps: int = 1, hold: float = 0.12) -> None:
    """Scroll the city view. `direction` is 'up'/'down'/'left'/'right', or a list of them.

    ⚠️ The view scrolls CONTINUOUSLY while the spoofed state is held - there is no fixed step per
    key event. Distance is roughly `taps * hold * 2500 px/s` at 800x600. Keep `hold` small (0.02)
    when you want a short, measurable move; a 2 s scroll crosses the whole map.
    """
    dirs = [direction] if isinstance(direction, str) else list(direction)
    vks = []
    for d in dirs:
        if d not in SCROLL_VK:
            raise ValueError(f"direction must be one of {sorted(SCROLL_VK)}, got {d!r}")
        vks.append(SCROLL_VK[d])

    sc = _scroll_script_get()
    sc.exports_sync.set(vks)
    try:
        for _ in range(max(1, taps)):
            for vk in vks:
                key(hwnd, vk, hold=0.02)
            time.sleep(hold)
    finally:
        sc.exports_sync.clear()
        for vk in vks:            # one event with the spoof off, so the engine clears its flags
            key(hwnd, vk, hold=0.02)
    time.sleep(0.4)


def resize_client(hwnd: int, w: int, h: int, edge: str = "bottomright") -> tuple[int, int]:
    """Resize by replaying the DRAG protocol without a cursor: WM_SIZING then SetWindowPos.

    A real border drag cannot be synthesised by PostMessage - Windows' sizing modal loop reads the
    physical cursor. But the mod has logic hanging off WM_SIZING (the WSNAP width snap at
    sc3resize.c:5147 - default OFF, g_wsnap > 1 required), and a plain SetWindowPos never fires
    that message. So: send the mod the WM_SIZING it expects with the proposed window rect, let it
    adjust the rect in place exactly as it would mid-drag, then apply the rect it handed back.
    Same code path, no cursor.

    Returns the resulting (client_w, client_h). Does not activate the window.
    """
    if edge not in WMSZ:
        raise ValueError(f"edge must be one of {sorted(WMSZ)}")
    wl, wt, wr, wb = _window_rect(hwnd)
    cx, cy, cw, ch = client_rect_on_screen(hwnd)
    chrome_w = (wr - wl) - cw
    chrome_h = (wb - wt) - ch

    proposed = wintypes.RECT(wl, wt, wl + w + chrome_w, wt + h + chrome_h)
    # SendMessage, not Post: we need the mod's in-place edit of the RECT before we use it.
    user32.SendMessageW(
        wintypes.HWND(hwnd), WM_SIZING, wintypes.WPARAM(WMSZ[edge]),
        wintypes.LPARAM(ctypes.addressof(proposed)),
    )
    user32.SetWindowPos(
        wintypes.HWND(hwnd), None, proposed.left, proposed.top,
        proposed.right - proposed.left, proposed.bottom - proposed.top,
        SWP_NOACTIVATE,
    )
    time.sleep(0.8)
    _, _, ncw, nch = client_rect_on_screen(hwnd)
    return ncw, nch


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------

def _report(g: Gate) -> None:
    print(f"pid      : {g.pid}")
    print(f"hwnd     : 0x{g.hwnd:08X}")
    print(f"client   : {g.w}x{g.h} at screen ({g.x},{g.y})  [physical px]")
    print(f"dpi      : {g.scale:.3f}x  -> virtual client "
          f"{int(round(g.w / (g.scale or 1)))}x{int(round(g.h / (g.scale or 1)))}")
    if g.ok:
        print("gate     : OK - nothing on top, on-screen, not minimised")
    else:
        print("gate     : BLOCKED")
        for p in g.problems:
            print(f"    - {p}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="run the gate only, write nothing")
    ap.add_argument("--info", action="store_true", help="window / DPI / occlusion report")
    ap.add_argument("--grab", metavar="PNG", help="capture to PNG, or fail loudly")
    ap.add_argument("--settle", type=float, default=0.0, help="seconds to wait before the blit")
    ap.add_argument("--no-raise", action="store_true",
                    help="do NOT put the window topmost; fail if anything overlaps it")
    a = ap.parse_args(argv)

    try:
        g = check(raise_first=not a.no_raise)
    except CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2

    if a.info or a.check:
        _report(g)
        if not a.grab:
            return 0 if g.ok else 2

    if a.grab:
        try:
            gr = grab_to(a.grab, g.hwnd, settle=a.settle)
        except CaptureError as e:
            print(f"STOP: {e}", file=sys.stderr)
            return 2
        print(f"saved {a.grab}  {gr.img.width}x{gr.img.height}  dpi {gr.scale:.3f}x")
        return 0

    if not (a.info or a.check):
        _report(g)
        return 0 if g.ok else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
