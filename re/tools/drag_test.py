"""Resize by the right edge and report the change. Message-based - no cursor, no focus.

WAS: a real border drag (SetCursorPos + mouse_event down / 8 moves / up) against the right edge.
That needed the game foreground and moved the physical mouse. NOW: the same WM_SIZING the drag
would have produced, then SetWindowPos with the rect the mod handed back (see
sc3io.resize_client). The mod's WM_SIZING logic is exercised identically.

What this can NO LONGER test: whether Windows' own sizing modal loop starts, i.e. whether
WM_NCHITTEST answers with an edge code. That is a cursor-loop property and cannot be observed
without the cursor. Test it directly instead - send WM_NCHITTEST and read the reply, which is what
commit db1fd42 did:  `nchittest.py` style probe, no drag required.

Usage: drag_test.py [dx]      (default 160)
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402


def main(argv):
    dx = int(argv[0]) if argv else 160
    try:
        hwnd = sc3io.game_hwnd()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2

    w0 = sc3io._window_rect(hwnd)
    _, _, cw0, ch0 = sc3io.client_rect_on_screen(hwnd)
    print(f"before: window {w0} client {cw0}x{ch0}")

    cw1, ch1 = sc3io.resize_client(hwnd, cw0 + dx, ch0, edge="right")
    print(f"after:  window {sc3io._window_rect(hwnd)} client {cw1}x{ch1}")

    if (cw1, ch1) == (cw0, ch0):
        print(f"NO CHANGE ({cw0}x{ch0}) - the mod refused the size, or WM_SIZING clamped it back")
        return 1
    print(f"RESIZED ({cw0}x{ch0}) -> ({cw1}x{ch1})  right edge +{dx} requested, "
          f"{cw1 - cw0} granted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
