"""verify/reunirse: how often does the first click on the Reunirse button fail to open it right after the X close?
Cycles: open (count clicks until a dialog shows, max 3), open an advisor, close with the X. Prints the rect of each
open so the position can be checked too. Honours SC3_PID. Input through sc3io only.

Usage: python re/tools/reunirse_reopen.py [--cycles 6] [--gap 1.0]
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402
from uiwin_dump import JS  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=6)
    ap.add_argument("--gap", type=float, default=1.0)
    a = ap.parse_args(argv)
    h = sc3io.game_hwnd()
    sc3pause.require_running(sc3io.game_pid(), "reunirse_reopen")
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()

    def nodes():
        return sc.exports_sync.d(6, False)["nodes"]

    def dl(ns):
        return [n for n in ns if n.get("cls") == "SIMUI.DLL+0xa4d64" and n.get("vis") and n["abs"][2] - n["abs"][0] >= 300]

    def c(b):
        return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)

    def wait_dlg(t=3.0):
        end = time.time() + t
        while time.time() < end:
            ns = nodes()
            if dl(ns):
                return ns
            time.sleep(0.2)
        return None

    cats = sorted([n for n in nodes() if n.get("cls") == "SIMUI.DLL+0xa8f60" and n.get("vis")], key=lambda n: n["abs"][1])
    meet = c(cats[6]["abs"])
    fails = 0
    for i in range(a.cycles):
        clicks = 0
        ns = None
        while clicks < 3 and not ns:
            sc3io.click(h, *meet)
            clicks += 1
            ns = wait_dlg()
        if not ns:
            print(f"cycle {i}: no dialog after 3 clicks, stop")
            return 2
        fails += clicks > 1
        d = dl(ns)[0]
        advs = sorted([n for n in ns if n.get("parent") == d["p"] and n.get("cls") == "SIMUI.DLL+0xa3ad8" and n.get("vis")],
                      key=lambda n: n["abs"][0])
        line = f"cycle {i}: clicks {clicks} open {d['abs']}"
        if advs and d["abs"][2] - d["abs"][0] != 384:
            sc3io.click(h, *c(advs[i % len(advs)]["abs"]))
            time.sleep(1.5)
            d = dl(nodes())[0]
            line += f" advisor {d['abs']}"
        b = d["abs"]
        sc3io.click(h, b[2] - 21, b[1] + 17)
        time.sleep(a.gap)
        print(line)
    print(f"first-click failures: {fails}/{a.cycles}")
    s.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
