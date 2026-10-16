#!/usr/bin/env python3
r"""cs_run.py - one carscroll arm (verify/carscroll/PRE.md): pt_run.py's launcher and key driver with the carscroll
probe (cs_probe.py) and camera-move tokens.

  py -3.12 cs_run.py --inst <instance folder> --city <src.sc3> --arm NAME --schedule "s3:20,A0:0,H:20,I:10,..." [--safe]

Tokens (seconds after the colon):
  sN    run at speed N                       P    user pause                    I    idle (no input), state unchanged
  A0/A1 sc3simrun_animate(0/1) (in-game A/B switch, takes no time)
  X0/X1 the route-car fix off / on: sc3cartrips_fill(0/1) and sc3simrun_carmargin(2 / CS_MARGIN, default 5)
  C     re-centre the camera: left click on the minimap centre (CS_MINIMAP=x,y, default 718,508 at 800 x 600)
  W     warm-up after X0/X1: a gentle drag (as HG, its own kind), so the sim rect is rebuilt with the new margin
  F0/F1 sc3cartrips_fill(0/1): route-car scroll_fill off / on (recorded as the A/B state; use one switch per arm)
  H     right-drag: right button down at the view centre, moves with MK_RBUTTON back and forth every 50 ms
  HB    right button held still at the view centre
  HG    gentle back-and-forth drag: right button down at the centre, the mouse moves 1 px per 50 ms in a triangle wave of
        +-30 px around the press point (H moves 3 px per 50 ms over +-60 px; +-18 px stayed inside the drag dead zone)
  HS    slow pan (pictures): right button down at the centre, then 3 px to the left every 50 ms for the whole phase
        (the right-drag pans by mouse movement; a held offset does not move the camera, V2)
  HD    slow one-way drag: right button down left of centre, moves 8 px per 50 ms to the right for half the phase,
        then back for the other half (a hand pan, not pt_run's +-60 px shake)
  AR    arrows: spoofed arrow state (sc3io.scroll's GZWIND hook), left / right alternating every 0.4 s
  ED    edge scroll: posted mouse moves on the left / right edge bands of the 800 x 600 view, alternating every 0.4 s
  OS    overscroll: spoofed arrow held in one direction for the whole phase (CS_OS_DIR, default left), then the
        opposite direction for the same time in the following idle, so the camera returns
  PH    user pause + right-drag (FREEZE must still win)
  Z     Z:n = n clicks on the zoom-in button
A token ending in '*' also writes presented frames (sc3resize SC3RESIZE_FRAMEDUMP, set CS_FRAMEDUMP=<abs prefix>
before launch) every CS_FRAME_MS (default 120) ms of that phase, tagged <arm>_<phase index>_<frame>.
"""
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pt_run  # noqa: E402
import sc3io  # noqa: E402
from cs_probe import CSRC, JS  # noqa: E402

pt_run.JS = "var CSRC = " + json.dumps(CSRC) + ";\n" + JS.replace("__CS_LITE__", os.environ.get("CS_LITE", "0"))

if os.environ.get("CS_FRAMEDUMP"):
    os.environ["SC3RESIZE_FRAMEDUMP"] = os.environ["CS_FRAMEDUMP"]


class CsArm(pt_run.Arm):
    def on_msg(self, m, data):
        if m.get("type") == "send" and m["payload"].get("faults"):
            print("FAULT", m["payload"]["faults"], flush=True)
        super().on_msg(m, data)

    def rect(self):
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        pt_run.user32.GetClientRect(wintypes.HWND(self.h), ctypes.byref(r))
        return r.right, r.bottom

    def lp(self, x, y):
        return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

    def held(self, secs):
        w, h = self.rect()
        cx, cy = w // 2, h // 2
        sc3io._post(self.h, sc3io.WM_MOUSEMOVE, 0, self.lp(cx, cy))
        time.sleep(0.08)
        sc3io._post(self.h, sc3io.WM_RBUTTONDOWN, sc3io.MK_RBUTTON, self.lp(cx, cy))
        time.sleep(secs)
        sc3io._post(self.h, sc3io.WM_RBUTTONUP, 0, self.lp(cx, cy))

    def gentle(self, secs, amp=30):
        w, h = self.rect()
        cx, cy = w // 2, h // 2
        sc3io._post(self.h, sc3io.WM_MOUSEMOVE, 0, self.lp(cx, cy))
        time.sleep(0.08)
        sc3io._post(self.h, sc3io.WM_RBUTTONDOWN, sc3io.MK_RBUTTON, self.lp(cx, cy))
        t0, k = time.time(), 0
        while time.time() - t0 < secs:
            k += 1
            ph = k % (4 * amp)
            dx = ph if ph < amp else (2 * amp - ph if ph < 3 * amp else ph - 4 * amp)
            sc3io._post(self.h, sc3io.WM_MOUSEMOVE, sc3io.MK_RBUTTON, self.lp(cx + dx, cy))
            time.sleep(0.05)
        sc3io._post(self.h, sc3io.WM_RBUTTONUP, 0, self.lp(cx, cy))

    def slow_pan(self, secs, off=22):
        w, h = self.rect()
        x, y = w // 2, h // 2
        sc3io._post(self.h, sc3io.WM_MOUSEMOVE, 0, self.lp(x, y))
        time.sleep(0.08)
        sc3io._post(self.h, sc3io.WM_RBUTTONDOWN, sc3io.MK_RBUTTON, self.lp(x, y))
        t0, k = time.time(), 0
        while time.time() - t0 < secs:
            k += 1
            sc3io._post(self.h, sc3io.WM_MOUSEMOVE, sc3io.MK_RBUTTON, self.lp(x - 3 * k, y))
            time.sleep(0.05)
        sc3io._post(self.h, sc3io.WM_RBUTTONUP, 0, self.lp(x - 3 * k, y))

    def slow_drag(self, secs):
        w, h = self.rect()
        x, y = w // 2, h // 2
        sc3io._post(self.h, sc3io.WM_MOUSEMOVE, 0, self.lp(x, y))
        time.sleep(0.08)
        sc3io._post(self.h, sc3io.WM_RBUTTONDOWN, sc3io.MK_RBUTTON, self.lp(x, y))
        t0 = time.time()
        while time.time() - t0 < secs:
            x += 8 if time.time() - t0 < secs / 2 else -8
            sc3io._post(self.h, sc3io.WM_MOUSEMOVE, sc3io.MK_RBUTTON, self.lp(x, y))
            time.sleep(0.05)
        sc3io._post(self.h, sc3io.WM_RBUTTONUP, 0, self.lp(x, y))

    def arrows(self, secs, dirs=("left", "right"), period=0.4):
        sc = sc3io._scroll_script_get()
        t0, k = time.time(), 0
        try:
            while time.time() - t0 < secs:
                vk = sc3io.SCROLL_VK[dirs[k % len(dirs)]]
                sc.exports_sync.set([vk])
                t1 = time.time()
                while time.time() - t1 < period and time.time() - t0 < secs:
                    sc3io.key(self.h, vk, hold=0.02)
                    time.sleep(0.1)
                k += 1
        finally:
            sc.exports_sync.clear()
            for vk in sc3io.SCROLL_VK.values():
                sc3io.key(self.h, vk, hold=0.02)

    def edge(self, secs, period=0.4):
        # native view bounds [0 0 704 544], bands 64 px (verify/resize_edgescroll): x = 8 or 696, y = 272
        pts = [(8, 272), (696, 272)]
        t0, k = time.time(), 0
        while time.time() - t0 < secs:
            x, y = pts[k % 2]
            t1 = time.time()
            while time.time() - t1 < period and time.time() - t0 < secs:
                sc3io._post(self.h, sc3io.WM_MOUSEMOVE, 0, self.lp(x, y))
                time.sleep(0.05)
            k += 1
        sc3io._post(self.h, sc3io.WM_MOUSEMOVE, 0, self.lp(352, 272))

    def frames(self, tag, stop):
        prefix = os.environ.get("CS_FRAMEDUMP")
        if not prefix:
            return
        ms = float(os.environ.get("CS_FRAME_MS", "120")) / 1000.0
        k = 0
        while not stop.is_set():
            req = prefix + "req"
            if not os.path.exists(req):
                with open(req, "w") as f:
                    f.write("%s_%03d\n" % (tag, k))
                k += 1
            time.sleep(ms)

    def run_schedule(self):
        os_dir = os.environ.get("CS_OS_DIR", "left")
        back = {"left": "right", "right": "left", "up": "down", "down": "up"}
        os_pending = 0.0
        t0 = time.time()                           # city load time varies (60-120 s): wait for the city and its view
        while time.time() - t0 < 240 and not (self.st().get("speed_last") and self.st().get("view")):
            time.sleep(2)
        time.sleep(5)
        for idx, tok in enumerate(self.a.schedule.split(",")):
            what, secs = tok.split(":")
            dump = what.endswith("*")
            what = what.rstrip("*")
            secs = float(secs)
            self.phase = "sw>" + tok
            if what.startswith("s"):
                self.ensure_speed(int(what[1:]))
                self.ensure_pause(False)
            elif what in ("P", "PH"):
                self.ensure_pause(True)
            elif what == "C":                          # re-centre: left click on the minimap's centre (CS_MINIMAP, 800 x 600)
                mx, my = (int(v) for v in os.environ.get("CS_MINIMAP", "718,508").split(","))
                v0 = self.st().get("view")
                sc3io.click(self.h, mx, my)
                time.sleep(1.5)
                self.write({"t": time.time(), "phase": tok, "mark": "recentre", "from": v0, "to": self.st().get("view")})
                print("%s recentre %s -> %s" % (time.strftime("%H:%M:%S"), v0, self.st().get("view")), flush=True)
                continue
            elif what in ("X0", "X1"):                 # whole route-car fix off / on: sc3cartrips fill + sc3simrun car margin
                on = what == "X1"
                r = self.sc.exports_sync.fill(on)
                m = self.sc.exports_sync.carmargin(int(os.environ.get("CS_MARGIN", "5")) if on else 2)
                self.write({"t": time.time(), "phase": tok, "mark": "animate", "on": on, "was": [r, m], "fix": True})
                print("%s fix %s (was fill %s margin %s)" % (time.strftime("%H:%M:%S"), what, r, m), flush=True)
                continue
            elif what in ("F0", "F1"):                 # sc3cartrips scroll_fill off / on (summaries key on it like A0/A1)
                r = self.sc.exports_sync.fill(what == "F1")
                self.write({"t": time.time(), "phase": tok, "mark": "animate", "on": what == "F1", "was": r, "fill": True})
                print("%s fill %s (was %s)" % (time.strftime("%H:%M:%S"), what, r), flush=True)
                continue
            elif what in ("A0", "A1"):
                r = self.sc.exports_sync.animate(what == "A1")
                self.write({"t": time.time(), "phase": tok, "mark": "animate", "on": what == "A1", "was": r})
                print("%s animate %s (was %s)" % (time.strftime("%H:%M:%S"), what, r), flush=True)
                continue
            elif what == "Z":
                for _ in range(int(secs)):
                    sc3io.click(self.h, 666, 547)
                    time.sleep(2)
                secs = 2
            self.phase = tok
            self.write({"t": time.time(), "phase": tok, "mark": "start", "st": self.st()})
            print("%s phase %s %s" % (time.strftime("%H:%M:%S"), tok, self.st()), flush=True)
            stop = threading.Event()
            th = None
            if dump:
                th = threading.Thread(target=self.frames, args=("%s_%02d_%s" % (self.a.arm, idx, what), stop), daemon=True)
                th.start()
            try:
                if what in ("H", "PH"):
                    self.hold(secs)
                elif what == "W":                     # warm-up after a switch: a gentle drag (no drift), its own kind
                    self.gentle(secs)
                elif what == "HB":
                    self.held(secs)
                elif what == "HG":
                    self.gentle(secs)
                elif what == "HD":
                    self.slow_drag(secs)
                elif what == "HS":
                    self.slow_pan(secs)
                elif what == "AR":
                    self.arrows(secs)
                elif what == "ED":
                    self.edge(secs)
                elif what == "OS":
                    self.arrows(secs, dirs=(os_dir,), period=secs + 1)
                    os_pending = secs
                elif what == "I" and os_pending:
                    self.arrows(os_pending, dirs=(back[os_dir],), period=os_pending + 1)
                    time.sleep(max(0.0, secs - os_pending))
                    os_pending = 0.0
                else:
                    time.sleep(secs)
            finally:
                stop.set()
                if th:
                    th.join(2)
            self.write({"t": time.time(), "phase": tok, "mark": "end", "st": self.st()})


pt_run.Arm = CsArm

if __name__ == "__main__":
    sys.exit(pt_run.main())
