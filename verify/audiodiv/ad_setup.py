"""Bring a freshly loaded Europolis 1024 (800x600 client) into the crash setup with posted clicks only.

Usage: py -3.12 ad_setup.py <pid> <layer: subway|pipes> <out.png>
Layers dialog (minimap stack button) -> Subsuelo -> Metros / Caneria agua -> Aplicar -> close, unpause,
jump to the y=0 edge (top-left minimap edge), zoom in 4 steps (closest), then maximize without focus.
Client coordinates measured on grabs a1_1.png / a1_2.png (800x600, Spanish install).
"""
import os
import sys
import time

pid = sys.argv[1]
os.environ["SC3_PID"] = pid
sys.path.insert(0, r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
import sc3io  # noqa: E402

layer = sys.argv[2]
h = sc3io.game_hwnd(int(pid))
steps = [(771, 458), (108, 233), (50, 259) if layer == "subway" else (50, 276), (98, 307), (298, 341),
         (523, 563), (688, 488)] + [(665, 548)] * 4
for x, y in steps:
    sc3io.click(h, x, y)
    time.sleep(1.5)
time.sleep(2)
sc3io.grab(h).save(sys.argv[3].replace(".png", "_800.png"))
print(sc3io.maximize_without_focus(h), flush=True)
time.sleep(8)
sc3io.grab(h).save(sys.argv[3])
print("setup done", flush=True)
