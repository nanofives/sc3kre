"""Resize the window by one edge and report the size change. No cursor, no focus.

The old version drove a real border drag with SetCursorPos + mouse_event. That needed the game
foreground and it hijacked the physical mouse. A border drag cannot be synthesised with
PostMessage, because Windows' sizing modal loop reads the physical cursor - so this instead
replays the same message the drag would have produced: WM_SIZING with the proposed window rect
(SendMessage, so the mod's in-place RECT adjustment is visible), then SetWindowPos with the rect
the mod handed back, SWP_NOACTIVATE. Same mod code path, no cursor.

Usage: drag_edge.py <right|bottom|corner|left|top|...> <dx> [dy]

`corner` is an alias for bottomright, kept for compatibility with the old CLI.
Exit 0 = the client size changed. Exit 1 = no change. Exit 2 = the game is not grabbable.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

ALIASES = {"corner": "bottomright"}


def main(argv):
    edge = argv[0] if argv else "right"
    edge = ALIASES.get(edge, edge)
    if edge not in sc3io.WMSZ:
        print(f"edge must be one of {sorted(sc3io.WMSZ) + list(ALIASES)}", file=sys.stderr)
        return 3
    dx = int(argv[1]) if len(argv) > 1 else 160
    dy = int(argv[2]) if len(argv) > 2 else dx

    try:
        hwnd = sc3io.game_hwnd()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2

    x0, y0, cw0, ch0 = sc3io.client_rect_on_screen(hwnd)
    wr0 = sc3io._window_rect(hwnd)
    print(f"before: window {wr0} client {cw0}x{ch0}")

    # Only the edges being dragged contribute a delta.
    grow_w = dx if any(k in edge for k in ("left", "right")) else 0
    grow_h = dy if any(k in edge for k in ("top", "bottom")) else 0
    cw1, ch1 = sc3io.resize_client(hwnd, cw0 + grow_w, ch0 + grow_h, edge=edge)

    print(f"after:  window {sc3io._window_rect(hwnd)} client {cw1}x{ch1}")
    changed = (cw1, ch1) != (cw0, ch0)
    print(("RESIZED" if changed else "NO CHANGE") + f" ({cw0}x{ch0}) -> ({cw1}x{ch1})  edge={edge}")
    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
