#!/usr/bin/env python3
"""nopause_unpause.py <pid>: wait for the city clock, then unpause with a posted click on the bar's play button
(popslow_run.py's start sequence, without Frida)."""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from popslow_meter import Meter  # noqa: E402
import sc3io  # noqa: E402

pid = int(sys.argv[1])
t0, m = time.time(), None
while time.time() - t0 < 240:
    try:
        m = m or Meter(pid)
        if m.sample():
            break
    except SystemExit:
        pass
    time.sleep(2)
time.sleep(8)
h = sc3io.game_hwnd(pid)
for _ in range(30):
    s = m.sample()
    if s and s["upause"] == 0 and s["hold"] == 0:
        break
    if s and s["hold"] == 0:
        sc3io.move(h, 522, 563, repeat=1)
        sc3io.click(h, 522, 563)
    time.sleep(3)
print(m.sample())
