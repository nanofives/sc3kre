"""verify/reunirse: Reunirse across window size changes. At the current size: open, drag far past the bottom-right
corner, open an advisor (expect: clamped inside, at the corner). Then maximize with it open (expect: stays), close
with the X, reopen (expect: same spot, not docked), open an advisor (same spot), close. Prints rects. SC3_PID.

Usage: python re/tools/reunirse_resize.py
"""

from __future__ import annotations

import pathlib
import sys
import time

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402
from uiwin_dump import JS  # noqa: E402


def main() -> int:
    h = sc3io.game_hwnd()
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()

    def nodes():
        return sc.exports_sync.d(6, False)["nodes"]

    def dl(ns):
        return [n for n in ns if n.get("cls") == "SIMUI.DLL+0xa4d64" and n.get("vis") and n["abs"][2] - n["abs"][0] >= 300]

    def c(b):
        return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)

    def wait(pred, t=4.0):
        end = time.time() + t
        while time.time() < end:
            ns = nodes()
            if pred(ns):
                return ns
            time.sleep(0.2)
        return nodes()

    def open_meet():
        for _ in range(3):
            cats = sorted([n for n in nodes() if n.get("cls") == "SIMUI.DLL+0xa8f60" and n.get("vis")], key=lambda n: n["abs"][1])
            sc3io.click(h, *c(cats[6]["abs"]))
            ns = wait(lambda ns: dl(ns))
            if dl(ns):
                return ns
        raise SystemExit("no Reunirse dialog after 3 clicks")

    def advisor(ns, k):
        d = dl(ns)[0]
        advs = sorted([n for n in ns if n.get("parent") == d["p"] and n.get("cls") == "SIMUI.DLL+0xa3ad8" and n.get("vis")],
                      key=lambda n: n["abs"][0])
        sc3io.click(h, *c(advs[k]["abs"]))
        ns = wait(lambda ns: dl(ns) and dl(ns)[0]["abs"][2] - dl(ns)[0]["abs"][0] == 384)
        return dl(ns)[0]["abs"]

    _, _, cw, ch = sc3io.client_rect_on_screen(h)
    ns = open_meet()
    d = dl(ns)[0]
    print(f"client {cw}x{ch} open {d['abs']}")
    t = next(n for n in ns if n.get("parent") == d["p"] and n.get("cls") == "SIMUI.DLL+0xa4b1c")["abs"]
    x0, y0 = t[0] + 100, (t[1] + t[3]) // 2
    sc3io.drag(h, x0, y0, x0 + 900, y0 + 500, button="left", steps=14)
    time.sleep(1.2)
    print(f"dragged {dl(nodes())[0]['abs']}")
    print(f"advisor {advisor(nodes(), 2)}")
    sc3io.maximize_without_focus(h)
    time.sleep(7)
    _, _, cw, ch = sc3io.client_rect_on_screen(h)
    b = dl(nodes())[0]["abs"]
    print(f"maximized client {cw}x{ch} dlg {b}")
    sc3io.click(h, b[2] - 21, b[1] + 17)
    time.sleep(1.5)
    ns = open_meet()
    print(f"reopen {dl(ns)[0]['abs']}")
    b = advisor(ns, 4)
    print(f"advisor {b}")
    sc3io.click(h, b[2] - 21, b[1] + 17)
    time.sleep(1.0)
    s.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
