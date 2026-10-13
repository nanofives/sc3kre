#!/usr/bin/env python3
r"""nramp_view.py - cell <-> client pixel for the netramp in-game tests, measured from the game itself (2026-10-13).

The On-ramp tool's cost preview calls SIMNTWRK netmgr vt+0x90 (FUN_100145aa) with the cell under the cursor on every
mouse move; nramp_trace.py logs it as {"ev": "cost90", "pts": [[x, z, y]]}. So with the On-ramp tool selected and the
trace running (its JSON lines in TRACE), a posted WM_MOUSEMOVE tells which cell a pixel hits. No cursor, no focus.

  py -3.12 nramp_view.py TRACE goto X,Z        # minimap clicks until X,Z is near the view centre, then prints its pixel
  py -3.12 nramp_view.py TRACE pix X,Z [X,Z..] # pixel of each cell (local search), JSON
  py -3.12 nramp_view.py TRACE center X,Z     # arrow-key scroll until X,Z sits at the view centre (350,270)
  py -3.12 nramp_view.py TRACE cell PX,PY      # cell under a pixel
SC3_PID picks the instance.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402

MM_C = (720, 518)          # minimap centre pixel on the 800x600 client (measured on Berlin and Roadless Paradise)


class View:
    def __init__(self, trace):
        self.trace = trace
        self.h = sc3io.game_hwnd(int(os.environ["SC3_PID"]))

    def _last(self):
        with open(self.trace) as f:
            ls = [l for l in f.read().splitlines() if '"cost90"' in l]
        if not ls:
            return None
        pts = json.loads(ls[-1])["pts"]
        return pts[0][:2] if pts else None

    def reset_cap(self):
        """The tool's points stop at the global cap DAT_100322a4 < 0x200 (FUN_10004754); a road drag tool hover runs
        FUN_1000488d, which resets it. Then reselect the On-ramp tool."""
        import subprocess
        np = os.path.join(HERE, "np_drive.py")
        subprocess.run([sys.executable, np, "cmd", "0x10004001"], stdout=subprocess.DEVNULL)
        time.sleep(0.6)
        sc3io.move(self.h, 300, 200)
        time.sleep(0.4)
        sc3io.move(self.h, 310, 205)
        time.sleep(0.4)
        subprocess.run([sys.executable, np, "cmd", "0x10004302"], stdout=subprocess.DEVNULL)
        time.sleep(0.6)

    def cell(self, x, y):
        for attempt in range(2):
            before = os.path.getsize(self.trace)
            sc3io.move(self.h, x, y)
            for _ in range(20):
                time.sleep(0.1)
                if os.path.getsize(self.trace) != before:
                    break
            time.sleep(0.15)
            c = self._last()
            if c is not None:
                return tuple(c)
            self.reset_cap()
        raise RuntimeError("no cell under (%d,%d): is the On-ramp tool selected and nramp_trace.py running?" % (x, y))

    def center(self, tx, tz, cx=350, cy=270, tol=40):
        """Scroll (sc3io.scroll, arrow keys) until cell tx,tz is within tol px of (cx, cy). Returns its pixel."""
        p = None
        for _ in range(10):
            p = self.pix(tx, tz, start=(cx, cy))
            if p is None:
                return None
            dx, dy = p[0] - cx, p[1] - cy
            if abs(dx) <= tol and abs(dy) <= tol:
                return p
            if abs(dx) > tol:
                sc3io.scroll(self.h, "right" if dx > 0 else "left", taps=1, hold=min(0.4, abs(dx) / 2500.0))
            if abs(dy) > tol:
                sc3io.scroll(self.h, "down" if dy > 0 else "up", taps=1, hold=min(0.4, abs(dy) / 2500.0))
        return p

    def pix(self, tx, tz, start=(400, 300)):
        x, y = start
        for _ in range(16):
            c = self.cell(x, y)
            if c == (tx, tz):
                return (x, y)
            cx, cy = self.cell(x + 30, y), self.cell(x, y + 30)
            a, b = (cx[0] - c[0]) / 30.0, (cy[0] - c[0]) / 30.0
            cc, d = (cx[1] - c[1]) / 30.0, (cy[1] - c[1]) / 30.0
            det = a * d - b * cc
            if abs(det) < 1e-9:
                x, y = x + 7, y + 5
                continue
            ex, ez = tx - c[0], tz - c[1]
            nx, ny = x + (d * ex - b * ez) / det, y + (-cc * ex + a * ez) / det
            x, y = int(round(min(690, max(10, nx)))), int(round(min(520, max(10, ny))))
        # last resort: small ring search
        for r in range(1, 12):
            for dx in range(-r, r + 1):
                for dy in (-r, r):
                    for (px, py) in ((x + 3 * dx, y + 3 * dy), (x + 3 * dy, y + 3 * dx)):
                        if self.cell(px, py) == (tx, tz):
                            return (px, py)
        return None

    def goto(self, tx, tz):
        mx, my = MM_C
        for _ in range(4):
            sc3io.click(self.h, int(round(mx)), int(round(my)))
            time.sleep(1.5)
            c = self.cell(400, 300)
            ex, ez = tx - c[0], tz - c[1]
            if abs(ex) + abs(ez) <= 6:
                break
            # minimap: +1 px right = (-2, +2) cells, +1 px down = (+2, +2) cells (measured)
            mx += (ez - ex) / 4.0
            my += (ex + ez) / 3.96
        return self.pix(tx, tz)


def main(argv):
    v = View(argv[1])
    cmd = argv[2]
    if cmd == "goto":
        tx, tz = map(int, argv[3].split(","))
        print(json.dumps({"cell": [tx, tz], "pix": v.goto(tx, tz)}))
    elif cmd == "pix":
        out = {}
        for a in argv[3:]:
            tx, tz = map(int, a.split(","))
            out[a] = v.pix(tx, tz)
        print(json.dumps(out))
    elif cmd == "center":
        tx, tz = map(int, argv[3].split(","))
        print(json.dumps({"cell": [tx, tz], "pix": v.center(tx, tz)}))
    elif cmd == "cell":
        x, y = map(int, argv[3].split(","))
        print(json.dumps(v.cell(x, y)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
