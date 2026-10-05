"""Launch the game with the resize mod and park it on the VIRTUAL display, off the real monitors.

Standard workflow now that `vdd.py` exists. Order matters and is enforced here:

  1. The virtual display must ALREADY be attached. Changing the display topology while SC3U.exe is
     running KILLS it (measured 2026-09-07) - so this refuses to launch if no virtual display is
     attached rather than attaching one under a live game.
  2. Launch via resize_launch.exe (injects sc3resize.dll).
  3. Wait for the mod to report the city loaded.
  4. Move the window onto the virtual display with SWP_NOACTIVATE - no cursor, no focus.

    python re/tools/launch_offscreen.py [--city Europolis] [--minutes 60] [--env K=V ...]

Prints the client rect and the DPI factor for that display, because input/grab coordinates depend
on it (on a 100%-scaled virtual display they coincide, which is the main ergonomic win).
"""

from __future__ import annotations

import argparse
import ctypes
import os
import pathlib
import subprocess
import sys
import time
from ctypes import wintypes

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402
import vdd  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
ROOT = pathlib.Path(__file__).resolve().parents[2]
SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0004, 0x0010


def virtual_display() -> tuple[str, tuple[int, int, int, int]] | None:
    attached = {d.DeviceName for d in vdd.display_devices()
                if "Parsec Virtual Display" in d.DeviceString and (d.StateFlags & vdd.ATTACHED_FLAG)}
    for name, box, _prim in vdd.screens():
        if name in attached:
            return name, box
    return None


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--city", default="Europolis")
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--env", action="append", default=[], metavar="K=V")
    ap.add_argument("--log")
    ap.add_argument("--on-screen", action="store_true",
                    help="skip the virtual display and leave the window where it lands")
    a = ap.parse_args(argv)

    vd = virtual_display()
    if vd is None and not a.on_screen:
        print("STOP: no Parsec virtual display is attached. Run `python re/tools/vdd.py --ensure` "
              "FIRST - attaching one while the game runs kills the game.", file=sys.stderr)
        return 2

    city = ROOT / "Cities" / f"{a.city}.sc3"
    if not city.exists():
        print(f"STOP: city not found: {city}", file=sys.stderr)
        return 2
    log = pathlib.Path(a.log) if a.log else ROOT / "verify" / "offscreen" / "run.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if log.exists():
        log.unlink()

    env = dict(os.environ)
    for k in ("SC3RESIZE_KIDFIX", "SC3RESIZE_ARTGUARD"):
        env.pop(k, None)                      # prove the defaults
    env["SC3RESIZE_CLUSTER"] = "1"
    env["SC3RESIZE_LOG"] = str(log)
    for pair in a.env:
        k, _, v = pair.partition("=")
        env[k] = v

    exe = ROOT / "re" / "harness" / "bin" / "resize_launch.exe"
    print(f"[*] launching {exe.name} with {a.city}, log {log}")
    subprocess.Popen([str(exe), "-kill", str(a.minutes * 60), "--", str(city)], env=env)

    deadline = time.time() + 150
    while time.time() < deadline:
        if log.exists() and "bridge captured" in log.read_text(encoding="utf-8", errors="replace"):
            break
        time.sleep(1.0)
    else:
        print("STOP: the mod never reported 'bridge captured' - the city did not load",
              file=sys.stderr)
        return 2
    time.sleep(4)

    try:
        h = sc3io.game_hwnd()
    except sc3io.CaptureError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2

    if vd and not a.on_screen:
        name, (vx, vy, vw, vh) = vd
        wl, wt, wr, wb = sc3io._window_rect(h)
        x, y = vx + 50, vy + 120
        user32.SetWindowPos(wintypes.HWND(h), None, x, y, 0, 0,
                            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        time.sleep(1.5)
        print(f"[+] parked on {name} ({vw}x{vh} at {vx},{vy}) -> window {sc3io._window_rect(h)}")

    g = sc3io.check()
    print(f"[+] client {g.w}x{g.h} at ({g.x},{g.y})  dpi {g.scale:.3f}x  "
          f"gate {'OK' if g.ok else g.problems}")
    if abs(g.scale - 1.0) < 1e-6:
        print("    scaling is 100% here: input coords, engine coords and grab pixels all coincide.")
    else:
        print(f"    ⚠️ scaling is not 100%: a grab pixel is still the right INPUT coord, but the "
              f"engine sees it as x{1 / g.scale:.2f}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
