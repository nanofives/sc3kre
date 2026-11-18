#!/usr/bin/env python3
r"""ba_gate.py - task bldbat (2026-11-18): launch the patched Building Architect (BaappW.exe) windowed and prove that
no display mode changed, from OUTSIDE the process.

  py -3.12 re/tools/bldbat/ba_gate.py --tree dev\bldbat\tree --out verify\bldbat\runs\gate [--secs 40] [--keep]

- Samples every attached display's current mode (EnumDisplaySettingsExW ENUM_CURRENT_SETTINGS: size, bpp, Hz,
  position) every 20 ms in this process (not shimmed, not the game), from before the launch to after the exit.
  Any change = the Baapp PID this script started is killed at once and the run fails.
- Logs every top-level window of that PID (style, ex style, rect, title) once a second, and saves PrintWindow
  pictures of the main window (no input, no focus change).
- Reads bawinonly.log (the in-process patch report) at the end.
Exit 0 only if: bawinonly reported all patterns matched, no mode change was seen, and the main window was a captioned,
non-topmost window smaller than its monitor.
Also importable: launch(tree, args) -> (Popen, ModeWatch) for the render driver.
"""
import argparse
import ctypes
import ctypes.wintypes as W
import json
import os
import subprocess
import sys
import threading
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:   # physical pixels for window rects and PrintWindow (the dev display is 3840x2160 at >100 %)
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

ENUM_CURRENT_SETTINGS = -1
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 1


class DEVMODEW(ctypes.Structure):
    _fields_ = [("dmDeviceName", W.WCHAR * 32), ("dmSpecVersion", W.WORD), ("dmDriverVersion", W.WORD),
                ("dmSize", W.WORD), ("dmDriverExtra", W.WORD), ("dmFields", W.DWORD),
                ("dmPositionX", W.LONG), ("dmPositionY", W.LONG), ("dmDisplayOrientation", W.DWORD),
                ("dmDisplayFixedOutput", W.DWORD), ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
                ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short),
                ("dmFormName", W.WCHAR * 32), ("dmLogPixels", W.WORD), ("dmBitsPerPel", W.DWORD),
                ("dmPelsWidth", W.DWORD), ("dmPelsHeight", W.DWORD), ("dmDisplayFlags", W.DWORD),
                ("dmDisplayFrequency", W.DWORD), ("rest", ctypes.c_byte * 64)]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [("cb", W.DWORD), ("DeviceName", W.WCHAR * 32), ("DeviceString", W.WCHAR * 128),
                ("StateFlags", W.DWORD), ("DeviceID", W.WCHAR * 128), ("DeviceKey", W.WCHAR * 128)]


def modes():
    out = {}
    i = 0
    while True:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(dd)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not dd.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP:
            continue
        dm = DEVMODEW()
        dm.dmSize = ctypes.sizeof(DEVMODEW) - 64
        if user32.EnumDisplaySettingsExW(dd.DeviceName, ENUM_CURRENT_SETTINGS, ctypes.byref(dm), 0):
            out[dd.DeviceName] = (dm.dmPelsWidth, dm.dmPelsHeight, dm.dmBitsPerPel, dm.dmDisplayFrequency,
                                  dm.dmPositionX, dm.dmPositionY)
    return out


class ModeWatch(threading.Thread):
    def __init__(self, log, kill_pid=None):
        super().__init__(daemon=True)
        self.log, self.kill_pid, self.stop_ev = log, kill_pid, threading.Event()
        self.base = modes()
        self.samples, self.changes = 0, []
        log("modes at start: %s" % json.dumps(self.base))

    def run(self):
        while not self.stop_ev.is_set():
            m = modes()
            self.samples += 1
            if m != self.base:
                self.changes.append((time.time(), m))
                self.log("MODE CHANGE: %s (was %s)" % (json.dumps(m), json.dumps(self.base)))
                if self.kill_pid:
                    subprocess.run(["taskkill", "/PID", str(self.kill_pid), "/F"], capture_output=True)
                    self.log("killed pid %d" % self.kill_pid)
                    self.kill_pid = None
                self.base = m
            time.sleep(0.02)

    def stop(self):
        self.stop_ev.set()
        self.join(2)


WNDENUMPROC = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
user32.GetWindowLongW.restype = ctypes.c_long


def windows_of(pid):
    res = []

    def cb(h, _):
        p = W.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            r = W.RECT()
            user32.GetWindowRect(h, ctypes.byref(r))
            t = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, t, 256)
            c = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, c, 256)
            res.append({"hwnd": h, "title": t.value, "class": c.value, "visible": bool(user32.IsWindowVisible(h)),
                        "style": user32.GetWindowLongW(h, -16) & 0xFFFFFFFF,
                        "exstyle": user32.GetWindowLongW(h, -20) & 0xFFFFFFFF,
                        "rect": (r.left, r.top, r.right, r.bottom)})
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return res


def monitor_rect(hwnd):
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT), ("dwFlags", W.DWORD)]
    user32.MonitorFromWindow.restype = W.HANDLE
    m = user32.MonitorFromWindow(hwnd, 2)
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(mi)
    user32.GetMonitorInfoW(m, ctypes.byref(mi))
    r = mi.rcMonitor
    return (r.left, r.top, r.right, r.bottom)


def print_window(hwnd, path):
    """PrintWindow(PW_RENDERFULLCONTENT) into a PNG. No input, no focus."""
    from PIL import Image
    r = W.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return False
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(hwnd, mdc, 2)

    class BMI(ctypes.Structure):
        _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD),
                    ("biBitCount", W.WORD), ("biCompression", W.DWORD), ("biSizeImage", W.DWORD),
                    ("x", W.LONG), ("y", W.LONG), ("c1", W.DWORD), ("c2", W.DWORD)]
    bi = BMI(ctypes.sizeof(BMI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    return bool(ok)


def launch(tree, args=("-w", "-r800x600"), env_extra=None):
    apps = os.path.abspath(os.path.join(tree, "Apps"))
    exe = os.path.join(apps, "BaappW.exe")
    if not os.path.exists(os.path.join(apps, "bawinonly.dll")):
        raise SystemExit("no bawinonly.dll in %s (run ba_patch.py)" % apps)
    log = os.path.join(apps, "bawinonly.log")
    if os.path.exists(log):
        os.remove(log)
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.Popen([exe] + list(args), cwd=apps, env=env)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--secs", type=float, default=40)
    ap.add_argument("--keep", action="store_true", help="leave it running (prints the PID)")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    logf = open(os.path.join(a.out, "gate.log"), "w", encoding="utf-8")

    def log(s):
        line = "%8.3f %s" % (time.time() - t0, s)
        print(line)
        logf.write(line + "\n")
        logf.flush()
    t0 = time.time()
    watch = ModeWatch(log)
    watch.start()
    time.sleep(0.5)
    p = launch(a.tree)
    watch.kill_pid = p.pid
    log("started BaappW.exe pid %d" % p.pid)
    seen, main_w, shots = {}, None, 0
    end = time.time() + a.secs
    while time.time() < end and p.poll() is None:
        for w in windows_of(p.pid):
            key = (w["hwnd"], w["style"], w["exstyle"], w["rect"], w["visible"], w["title"])
            if key not in seen:
                seen[key] = 1
                log("window %(hwnd)s class=%(class)r title=%(title)r visible=%(visible)s style=0x%(style)08X "
                    "ex=0x%(exstyle)08X rect=%(rect)s" % w)
            if w["visible"] and w["style"] & 0x00C00000 and (main_w is None or w["hwnd"] == main_w["hwnd"]):
                main_w = w
        if main_w and time.time() > t0 + 8 + shots * 8 and shots < 4:
            path = os.path.join(a.out, "window_%d.png" % shots)
            log("PrintWindow -> %s ok=%s" % (path, print_window(main_w["hwnd"], path)))
            shots += 1
        time.sleep(0.25)
    rc = p.poll()
    log("process %s after %.1f s" % ("exited %s" % rc if rc is not None else "running", time.time() - t0))
    if rc is None and not a.keep:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/F"], capture_output=True)
        p.wait(10)
        log("stopped pid %d" % p.pid)
    time.sleep(1.0)
    watch.stop()
    log("mode samples: %d, changes: %d" % (watch.samples, len(watch.changes)))
    blog = os.path.join(a.tree, "Apps", "bawinonly.log")
    btxt = open(blog, encoding="latin-1").read() if os.path.exists(blog) else ""
    log("bawinonly.log:\n" + btxt.strip())
    ok_patch = "All patterns matched" in btxt
    ok_win = False
    if main_w:
        mon = monitor_rect(main_w["hwnd"]) if user32.IsWindow(main_w["hwnd"]) else None
        r = main_w["rect"]
        ok_win = (main_w["style"] & 0x00C00000 == 0x00C00000 and not main_w["exstyle"] & 0x8
                  and (mon is None or (r[2] - r[0] < mon[2] - mon[0] and r[3] - r[1] < mon[3] - mon[1])))
        log("main window caption=%s topmost=%s rect=%s monitor=%s" % (
            bool(main_w["style"] & 0x00C00000 == 0x00C00000), bool(main_w["exstyle"] & 0x8), r, mon))
    verdict = ok_patch and not watch.changes and ok_win
    log("GATE %s (patch=%s, mode changes=%d, windowed=%s)" % ("PASS" if verdict else "FAIL", ok_patch,
                                                               len(watch.changes), ok_win))
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
