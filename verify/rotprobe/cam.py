#!/usr/bin/env python3
r"""showcase camera (2026-11-17): one Frida session on the game, the camera moved by the city view's own
SetZoomAndRotation (nramp_cam.py's script, game thread, exceptions 'propagate'), frame dumps by np_drive.shot.
The camera object is captured from one posted click on a minimap zoom button (CAPTURE_PIXELS), so capture BEFORE
hiding the UI. Never attach while the game is paused (sc3pause guard).

  from cam import Cam
  c = Cam(click=(x, y)); c.go(x, z, zoom, rot); c.shot(path); c.close()
"""
import ctypes
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(MAIN, "re", "tools"))
sys.path.insert(0, os.path.join(MAIN, "re", "tools", "netmod"))
import frida  # noqa: E402
import nramp_cam  # noqa: E402
import np_drive  # noqa: E402
import sc3io  # noqa: E402
import sc3pause  # noqa: E402


class Cam:
    def __init__(self, clicks):
        self.pid = sc3io.game_pid()
        self.h = sc3io.game_hwnd(self.pid)
        sc3pause.require_running(self.pid, "showcase cam")
        self.s = frida.attach(self.pid)
        js = nramp_cam.JS if "%RAW%" not in nramp_cam.JS else nramp_cam.JS.replace("%RAW%", "0").replace("%RAWPROP%", "0") \
            .replace("%WM%", str(nramp_cam.WM_CAM))
        self.sc = self.s.create_script(js)
        self.sc.load()
        self.api = self.sc.exports_sync
        for vk in (0x6D, 0x6B, 0x6D):           # numpad - / +: the view's zoom path, works with the HUD hidden
            sc3io.key(self.h, vk)
            time.sleep(1.2)
            if self.api.hascam():
                break
        for btn in ([] if self.api.hascam() else clicks):
            sc3io.click(self.h, *btn)
            time.sleep(1.0)
            if self.api.hascam():
                break
        if not self.api.hascam():
            raise SystemExit("camera not captured")

    def go(self, x, z, zoom, rot, settle=1.5):
        for k in range(4):
            try:
                return self._go(x, z, zoom, rot, settle + k)
            except SystemExit:
                time.sleep(2)
        return self._go(x, z, zoom, rot, settle + 4)

    def _go(self, x, z, zoom, rot, settle=1.5):
        self.api.take()
        # SetZoomAndRotation does nothing when zoom and rotation are unchanged, so it would not recentre: step the zoom
        # away and back (a zoom change costs ~1 MB, a rotation ~10 MB: ISSUES.md 1)
        self.api.queue({"k": "zoom", "v": zoom - 1 if zoom > 0 else 1, "f": 1, "x": x, "z": z})
        self.api.queue({"k": "rot", "v": rot, "f": 1, "x": x, "z": z})
        self.api.queue({"k": "zoom", "v": zoom, "f": 1, "x": x, "z": z})
        ctypes.windll.user32.PostMessageA(self.h, nramp_cam.WM_CAM, 0, 0)
        time.sleep(settle)
        res = self.api.take()
        st = [r["state"] for r in res if "state" in r]
        if len(st) < 3:
            raise SystemExit("camera call failed: %s" % res)
        return st[-1]

    def shot(self, path):
        import glob
        try:
            np_drive.shot(path)
        except PermissionError:               # the game still held a BMP np_drive tried to delete: the PNG is written
            time.sleep(1.5)
            for b in glob.glob(os.path.join(np_drive.game_dir(), "dump*.bmp")):
                try:
                    os.remove(b)
                except OSError:
                    pass
        from PIL import Image
        im = Image.open(path)
        if im.height > 1080:                  # the dump carries the render target's slack rows
            im.crop((0, 0, im.width, 1080)).save(path)
        return path

    def close(self):
        try:
            self.s.detach()
        except Exception:
            pass
