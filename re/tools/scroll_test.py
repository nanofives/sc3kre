"""Right-drag the map to pan, at a chosen client point. No cursor, no focus.

The old version used SetCursorPos + mouse_event, which needed the game foreground and moved the
physical mouse. This posts the same sequence as messages: WM_RBUTTONDOWN, interpolated
WM_MOUSEMOVEs with MK_RBUTTON set, WM_RBUTTONUP.

Client coords are VIRTUAL (the game is DPI-unaware), which is exactly what WM_MOUSEMOVE lParam
means to the game - so no DPI correction is applied or wanted here. If you picked the point off a
screen_grab PNG, divide by sc3io's `Grab.scale` first (or use `Grab.to_client`).

Usage: scroll_test.py <cx> <cy> <dx> <dy>
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402


def main(argv):
    if len(argv) < 4:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 3
    cx, cy, dx, dy = (int(a) for a in argv[:4])
    try:
        hwnd = sc3io.game_hwnd()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2
    steps = max(abs(dx), abs(dy)) // 15 or 1
    sc3io.drag(hwnd, cx, cy, cx + dx, cy + dy, button="right", steps=steps, delay=0.05)
    print(f"right-drag from client({cx},{cy}) by ({dx},{dy}) in {steps} steps "
          f"- messages only, cursor not moved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
