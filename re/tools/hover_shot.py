"""Hover a client point and grab the hover state. Message-based - no cursor, no focus.

WAS: moved the real cursor with SetCursorPos + a synthetic MOUSEEVENTF_MOVE, which required the
game foreground and hijacked the physical mouse. NOW: identical observable (the game renders the
hover highlight / flyout from the WM_MOUSEMOVE it receives) driven entirely by PostMessage, and
the grab refuses rather than saving an untrustworthy frame.

Coords are the game's VIRTUAL client space (the game is DPI-unaware) - which is exactly what
WM_MOUSEMOVE lParam means to it, so no DPI correction is applied. If you read the point off a
screen_grab PNG, convert with sc3io's `Grab.to_client()` first.

Usage: hover_shot.py <client_x> <client_y> [out_name_or_path]
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
        print("usage: hover_shot.py <client_x> <client_y> [out]", file=sys.stderr)
        return 3
    cx, cy = int(argv[0]), int(argv[1])
    out = argv[2] if len(argv) > 2 else "hover"
    path = out if out.lower().endswith(".png") else os.path.join(SHARE, f"{out}.png")

    try:
        hwnd = sc3io.game_hwnd()
        _, _, w, h = sc3io.client_rect_on_screen(hwnd)
        print(f"client {w}x{h} (physical); hover client ({cx},{cy}) virtual")
        # Approach from a neighbouring pixel first: some of this UI only latches a hover on a
        # CHANGE of position, not on a repeat of the same one.
        sc3io.move(hwnd, cx - 6, cy - 6, repeat=1)
        sc3io.move(hwnd, cx, cy, repeat=3)
        time.sleep(0.7)
        gr = sc3io.grab_to(path, hwnd)
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2
    print(f"saved {path} ({gr.img.width}x{gr.img.height}) - cursor NOT moved, focus NOT taken")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
