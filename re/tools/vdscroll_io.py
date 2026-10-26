"""vdscroll helpers (child vdscroll 2026-10-26): posted input only, no z-order change, no focus, frames from
SC3RESIZE_FRAMEDUMP. Used by vdscroll_bench.py."""
import ctypes, sys, time, os, pathlib
from ctypes import wintypes
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io
u = ctypes.windll.user32
SWP_NOZORDER, SWP_NOACTIVATE = 0x4, 0x10
WM_SIZING = 0x214
FD = pathlib.Path(os.environ.get("VDSCROLL_FD", "."))   # the SC3RESIZE_FRAMEDUMP prefix folder (the bench sets it)


def hwnd():
    return sc3io.game_hwnd()


def resize(h, w, hh):
    """Client to w x hh through the mod's WM_SIZING, then SetWindowPos with NOZORDER|NOACTIVATE (no raise)."""
    wl, wt, wr, wb = sc3io._window_rect(h)
    cx, cy, cw, ch = sc3io.client_rect_on_screen(h)
    r = wintypes.RECT(wl, wt, wl + w + (wr - wl - cw), wt + hh + (wb - wt - ch))
    u.SendMessageW(wintypes.HWND(h), WM_SIZING, 8, wintypes.LPARAM(ctypes.addressof(r)))
    u.SetWindowPos(wintypes.HWND(h), None, r.left, r.top, r.right - r.left, r.bottom - r.top, SWP_NOZORDER | SWP_NOACTIVATE)
    time.sleep(1.0)
    return sc3io.client_rect_on_screen(h)[2:]


def moveto(h, x, y):
    u.SetWindowPos(wintypes.HWND(h), None, x, y, 0, 0, 0x1 | SWP_NOZORDER | SWP_NOACTIVATE)


def dump(tag, timeout=8.0):
    """Ask sc3resize FRAMEDUMP for the next presented frame, save it as <FD>/<tag>.png."""
    req = FD / "req"
    req.write_text(tag)
    t = time.time()
    while req.exists() and time.time() - t < timeout:
        time.sleep(0.1)
    p = FD / f"{tag}.bmp"
    time.sleep(0.3)
    for _ in range(20):   # the game may still be writing the bmp
        try:
            if p.exists():
                from PIL import Image
                with Image.open(p) as im:
                    im.load(); im.save(FD / f"{tag}.png")
                p.unlink()
                return FD / f"{tag}.png"
        except (PermissionError, OSError):
            pass
        time.sleep(0.5)
    return None
