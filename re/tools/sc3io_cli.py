"""Subcommand CLI over sc3io, for PowerShell drivers that must not reimplement capture/input.

Every subcommand exits 0 on success and 2 when the game is not grabbable / drivable, printing the
reason on stderr. A driver should treat exit 2 as fatal - that is the "stop and tell me" contract.

    python re/tools/sc3io_cli.py check
    python re/tools/sc3io_cli.py grab <out.png> [--settle S]
    python re/tools/sc3io_cli.py click <x> <y> [--right]
    python re/tools/sc3io_cli.py move  <x> <y>
    python re/tools/sc3io_cli.py drag  <x0> <y0> <x1> <y1> [--left] [--steps N]
    python re/tools/sc3io_cli.py wheel <x> <y> <notches>
    python re/tools/sc3io_cli.py key   <vk>
    python re/tools/sc3io_cli.py maximize | restore | topmost | untopmost
    python re/tools/sc3io_cli.py resize <client_w> <client_h> [--edge bottomright]
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402


def main(argv) -> int:
    ap = argparse.ArgumentParser(prog="sc3io_cli", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check")
    p = sub.add_parser("grab"); p.add_argument("out"); p.add_argument("--settle", type=float, default=0.0)
    p = sub.add_parser("click"); p.add_argument("x", type=int); p.add_argument("y", type=int); p.add_argument("--right", action="store_true")
    p = sub.add_parser("move"); p.add_argument("x", type=int); p.add_argument("y", type=int)
    p = sub.add_parser("drag")
    for n in ("x0", "y0", "x1", "y1"):
        p.add_argument(n, type=int)
    p.add_argument("--left", action="store_true"); p.add_argument("--steps", type=int, default=12)
    p = sub.add_parser("wheel"); p.add_argument("x", type=int); p.add_argument("y", type=int); p.add_argument("notches", type=int)
    p = sub.add_parser("key"); p.add_argument("vk", type=lambda s: int(s, 0))
    sub.add_parser("maximize"); sub.add_parser("restore")
    sub.add_parser("topmost"); sub.add_parser("untopmost")
    p = sub.add_parser("resize"); p.add_argument("w", type=int); p.add_argument("h", type=int); p.add_argument("--edge", default="bottomright")

    a = ap.parse_args(argv)

    try:
        h = sc3io.game_hwnd()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2

    try:
        if a.cmd == "check":
            g = sc3io.check(h)
            print(f"client {g.w}x{g.h} at ({g.x},{g.y}) dpi {g.scale:.3f}x "
                  f"{'OK' if g.ok else 'BLOCKED'}")
            if not g.ok:
                print("STOP: " + "; ".join(g.problems), file=sys.stderr)
                return 2

        elif a.cmd == "grab":
            gr = sc3io.grab_to(a.out, h, settle=a.settle)
            print(f"{gr.img.width}x{gr.img.height} -> {a.out}")

        elif a.cmd == "click":
            sc3io.click(h, a.x, a.y, button="right" if a.right else "left")
            print(f"click {'right' if a.right else 'left'} ({a.x},{a.y})")

        elif a.cmd == "move":
            sc3io.move(h, a.x, a.y)
            print(f"move ({a.x},{a.y})")

        elif a.cmd == "drag":
            sc3io.drag(h, a.x0, a.y0, a.x1, a.y1,
                       button="left" if a.left else "right", steps=a.steps)
            print(f"drag ({a.x0},{a.y0}) -> ({a.x1},{a.y1})")

        elif a.cmd == "wheel":
            sc3io.wheel(h, a.x, a.y, a.notches)
            print(f"wheel {a.notches} at ({a.x},{a.y})")

        elif a.cmd == "key":
            sc3io.key(h, a.vk)
            print(f"key 0x{a.vk:02X}")

        elif a.cmd == "maximize":
            w, ht = sc3io.maximize_without_focus(h)
            print(f"maximized client {w}x{ht} (no focus taken)")

        elif a.cmd == "restore":
            w, ht = sc3io.restore_without_focus(h)
            print(f"restored client {w}x{ht} (no focus taken)")

        elif a.cmd == "topmost":
            sc3io.raise_without_focus(h)
            print("topmost, not activated")

        elif a.cmd == "untopmost":
            sc3io.drop_topmost(h)
            print("back to the normal Z-order")

        elif a.cmd == "resize":
            w, ht = sc3io.resize_client(h, a.w, a.h, edge=a.edge)
            print(f"resize -> client {w}x{ht} (asked {a.w}x{a.h}, edge {a.edge})")

    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
