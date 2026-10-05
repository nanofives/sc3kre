"""Maximize / restore the game window WITHOUT activating it.

`ShowWindow(SW_MAXIMIZE)` activates the window - that is what the old one-liner did, and it stole
focus on every call. `sc3io` uses `SetWindowPlacement` instead, which sets the same show state and
does not activate.

Usage: do_maximize.py [max|restore|toggle]     (default: max)
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402


def main(argv):
    what = (argv[0] if argv else "max").lower()
    try:
        h = sc3io.game_hwnd()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2

    if what == "toggle":
        what = "restore" if sc3io.is_maximized(h) else "max"
    if what in ("max", "maximize"):
        w, ht = sc3io.maximize_without_focus(h)
    elif what in ("restore", "restore-down", "down"):
        w, ht = sc3io.restore_without_focus(h)
    else:
        print("usage: do_maximize.py [max|restore|toggle]", file=sys.stderr)
        return 3

    print(f"{what}: client {w}x{ht}  (width%32={w % 32})  maximized={sc3io.is_maximized(h)}  "
          f"- focus not taken")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
