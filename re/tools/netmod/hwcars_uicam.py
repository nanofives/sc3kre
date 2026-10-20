#!/usr/bin/env python3
r"""hwcars_uicam.py - move the camera like a player (minimap click + zoom buttons), task hwcars 2026-10-19.

Direct camera calls (rb_lab cam / nramp_cam) leave the street sim with no visible movers (roundabout4 trap), so traffic
clips are framed this way: one zoom-out click captures the camera object (nramp_cam hascam), a minimap click centres
the view on the target, then zoom-in clicks until ZOOM. Same arithmetic as inst_rb4\city\uicam.py.

  py -3.12 hwcars_uicam.py X Z [ZOOM]        SC3_PID = the game
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
import frida, sc3io, nramp_cam  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

tx, tz = int(sys.argv[1]), int(sys.argv[2])
want = int(sys.argv[3]) if len(sys.argv) > 3 else 4
W = 256
pid = sc3io.game_pid(); h = sc3io.game_hwnd(pid)
sc3pause.require_running(pid, "hwcars_uicam")
s = frida.attach(pid); sc = s.create_script(nramp_cam.JS); sc.load(); api = sc.exports_sync
sc3io.click(h, 772, 546); time.sleep(1.5)
st = api.hascam(); print("state", st)
r = st["rot"]
view = lambda x, z: [(x, z), (W - 1 - z, x), (W - 1 - x, W - 1 - z), (z, W - 1 - x)][r]
vx, vz = view(tx, tz); cx, cz = view(128, 128)
ex, ez = vx - cx, vz - cz
mx, my = 720 + (ez - ex) / 4.0, 518 + (ex + ez) / 3.96
print("minimap click", round(mx), round(my))
sc3io.click(h, int(round(mx)), int(round(my))); time.sleep(1.5)
for _ in range(6):
    if api.hascam()["zoom"] >= want: break
    sc3io.click(h, 666, 547); time.sleep(1.5)
# Measured 2026-10-19 (Seoul): right after this move the car producer stopped spawning (sc3cartrips spawn_try flat
# for 90 s at zoom 4); one zoom-out + zoom-in click restarted it. So end with that pair.
sc3io.click(h, 772, 546); time.sleep(1.5)
sc3io.click(h, 666, 547); time.sleep(1.5)
print("state", api.hascam()); s.detach()
