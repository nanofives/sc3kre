"""Hover a point by POSTING WM_MOUSEMOVE, then capture the hover state. No cursor, no focus.

Unchanged in spirit from the original - it already used PostMessage - but it no longer shells out
to a capture that could steal focus, and it now FAILS LOUDLY if the frame cannot be trusted rather
than leaving a stale PNG in place that looks like a result.

Usage: hover_msg.py <client_x> <client_y> [out_name_or_path]
"""

import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

SHARE = os.path.join(".happy-share", "cmtr70o5q0kybro1ji8drcbt6")


def main(argv):
    if len(argv) < 2:
        print("usage: hover_msg.py <client_x> <client_y> [out]", file=sys.stderr)
        return 3
    cx, cy = int(argv[0]), int(argv[1])
    out = argv[2] if len(argv) > 2 else "hovermsg"
    path = out if out.lower().endswith(".png") else os.path.join(SHARE, f"{out}.png")

    try:
        hwnd = sc3io.game_hwnd()
        sc3io.move(hwnd, cx, cy)
        time.sleep(0.7)
        gr = sc3io.grab_to(path, hwnd)
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2
    print(f"posted WM_MOUSEMOVE to client ({cx},{cy}); saved {path} "
          f"({gr.img.width}x{gr.img.height}); cursor NOT moved, focus NOT taken")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
