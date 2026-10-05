"""Grab N frames over N seconds so a human can hover by hand and we capture the hover state.

Routed through sc3io: the second BitBlt implementation this file used to carry is gone, so there
is one capture path with one gate. Each frame is graded - a frame that cannot be trusted is
reported and skipped rather than saved, and if NO frame could be captured the run exits 2.

Note this tool is for HUMAN hovering. If you want to hover programmatically, use hover_msg.py /
hover_shot.py, which post WM_MOUSEMOVE and do not need a hand on the mouse.

Usage: hover_watch.py [n_seconds] [out_prefix]
"""

import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

SHARE = os.path.join(".happy-share", "cmtr70o5q0kybro1ji8drcbt6")


def main(argv):
    n = int(argv[0]) if argv else 10
    prefix = argv[1] if len(argv) > 1 else "hw"
    try:
        hwnd = sc3io.game_hwnd()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2

    print(f"watching {n}s - hover a button now (the cursor is yours, this tool never moves it)")
    saved, skipped = 0, []
    for i in range(1, n + 1):
        path = os.path.join(SHARE, f"{prefix}_{i}.png")
        try:
            sc3io.grab_to(path, hwnd)
            saved += 1
            print(f"  frame {i}: saved {path}", flush=True)
        except sc3io.CaptureError as e:
            first = str(e).splitlines()[-1].strip()
            skipped.append((i, first))
            print(f"  frame {i}: SKIPPED - {first}", flush=True)
        time.sleep(1)

    print(f"\ndone: {saved}/{n} frame(s) saved, {len(skipped)} skipped")
    if saved == 0:
        print("STOP: not a single trustworthy frame was captured.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
