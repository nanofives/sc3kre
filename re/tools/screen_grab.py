"""Grab the game's true composited frame. Thin CLI over sc3io - the ONE capture path.

This used to be a standalone desktop-DC BitBlt that called SetForegroundWindow first (stealing
focus) and had no way to tell a real frame from "another window was on top". Both are fixed by
delegating to `sc3io`, which:

  * never takes foreground and never touches the cursor,
  * raises the window topmost WITHOUT activating it so nothing can occlude the blit,
  * refuses to save anything if the frame cannot be trusted (occluded / minimised / off-screen /
    flat-colour), exiting 2 with the reason instead of writing a misleading PNG.

Usage:
    python re/tools/screen_grab.py [out.png] [--settle SECONDS]

With no argument it writes the historical default path, so existing callers keep working.
Exit 0 = a credible frame was saved. Exit 2 = STOPPED, nothing written, reason on stderr.
"""

import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

DEFAULT_OUT = os.path.join(".happy-share", "cmtr70o5q0kybro1ji8drcbt6", "screen_grab.png")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", nargs="?", default=DEFAULT_OUT)
    ap.add_argument("--settle", type=float, default=0.0)
    a = ap.parse_args(argv)
    try:
        gr = sc3io.grab_to(a.out, settle=a.settle)
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2
    print(f"client {gr.gate.w}x{gr.gate.h} at screen ({gr.gate.x},{gr.gate.y})")
    print(f"saved {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
