"""Restore the window down to a known origin and size, so drags/resizes have room.

WAS: `ShowWindow(h, SW_RESTORE)`, which ACTIVATES the window and steals focus. Now uses
sc3io.restore_without_focus (SetWindowPlacement), then a SWP_NOACTIVATE reposition.

Usage: restore_down.py [x] [y] [client_w] [client_h]     (default 120 80 800 600)
"""

import ctypes
import pathlib
import sys
from ctypes import wintypes

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010


def main(argv):
    x = int(argv[0]) if len(argv) > 0 else 120
    y = int(argv[1]) if len(argv) > 1 else 80
    cw = int(argv[2]) if len(argv) > 2 else 800
    ch = int(argv[3]) if len(argv) > 3 else 600
    try:
        h = sc3io.game_hwnd()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2

    sc3io.restore_without_focus(h)

    # Convert the wanted CLIENT size into a window size using the live chrome, rather than the
    # old hardcoded 816x639 which drifts whenever the frame style changes (WS_THICKFRAME did).
    wl, wt, wr, wb = sc3io._window_rect(h)
    _, _, ccw, cch = sc3io.client_rect_on_screen(h)
    ww = cw + ((wr - wl) - ccw)
    wh = ch + ((wb - wt) - cch)
    user32.SetWindowPos(wintypes.HWND(h), None, x, y, ww, wh, SWP_NOZORDER | SWP_NOACTIVATE)

    _, _, fw, fh = sc3io.client_rect_on_screen(h)
    print(f"restored client {fw}x{fh} at ({x},{y})  window {ww}x{wh}  "
          f"chrome {ww - cw}x{wh - ch}  - focus not taken")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
