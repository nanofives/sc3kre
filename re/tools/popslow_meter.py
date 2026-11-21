#!/usr/bin/env python3
r"""popslow_meter.py - game days per real second and what holds the clock, read from OUTSIDE the game (task popslow,
2026-11-21). ReadProcessMemory only: no injection, no Frida, so the stock game and the modded game are measured by the
same instrument.

Fields (all [CONFIRMED], see re/analysis/formats/SIM_WHILE_SCROLLING.md and re/tools/sc3pause.py):
  app   = *(SC3U 0x004fa86c)              city = *(app + 0x48), vtable SIMCITY+0x13260 (checked)
  city+0x130 = clock (vtable SIMCITY+0x13988, checked)
  clock+0x4c = day count (bumped by tick_day SIMCITY 0x1000aa4d)
  clock+0x50 = speed (game minutes per real day: 10080/43200/129600/525600; 120 = paused speed)
  clock+0x54 = clock pause count (callback skips every fire while != 0, SIMCITY 0x1000a885)
  clock+0x60 = ms per game day
  city+0x140 = user pause depth, city+0x144 = camera / UI hold, city+0x148 = month-pass bracket

Thread CPU: every thread of the process (GetThreadTimes), the game's UI thread = owner of the "Gonzo" window.

As a module: Meter(pid).window(seconds) -> dict. CLI: py -3.12 popslow_meter.py [--pid N] [--seconds 30] [--hz 50]
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3pause  # noqa: E402

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.OpenThread.restype = wt.HANDLE
k32.OpenThread.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.GetThreadTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.CloseHandle.argtypes = [wt.HANDLE]


class THREADENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ThreadID", wt.DWORD),
                ("th32OwnerProcessID", wt.DWORD), ("tpBasePri", ctypes.c_long), ("tpDeltaPri", ctypes.c_long),
                ("dwFlags", wt.DWORD)]


def _ft(f):
    return (f.dwHighDateTime << 32 | f.dwLowDateTime) / 1e7


def ui_tid(pid):
    found = []
    EnumProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _):
        p = wt.DWORD()
        tid = u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid:
            buf = ctypes.create_unicode_buffer(64)
            u32.GetClassNameW(hwnd, buf, 64)
            if buf.value == "Gonzo" or not found:
                found.insert(0, tid) if buf.value == "Gonzo" else found.append(tid)
        return True
    u32.EnumWindows(EnumProc(cb), 0)
    return found[0] if found else 0


class Meter:
    def __init__(self, pid):
        self.pid = int(pid)
        self.h = k32.OpenProcess(0x0400 | 0x0010, False, self.pid)
        if not self.h:
            raise SystemExit("cannot open pid %d" % self.pid)
        mods = sc3pause._modules(self.h)
        self.exe, self.simcity = mods.get("sc3u.exe"), mods.get("simcity.dll")
        self.city = self.clock = 0
        self.tid_ui = ui_tid(self.pid)
        self._th = {}

    def rd(self, addr, n=4):
        b = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), b, n, ctypes.byref(got)) or got.value != n:
            return None
        return b.raw

    def u(self, addr):
        r = self.rd(addr)
        return struct.unpack("<I", r)[0] if r else None

    def resolve(self):
        if not self.simcity:
            self.simcity = sc3pause._modules(self.h).get("simcity.dll")
        if not (self.exe and self.simcity):
            return False
        app = self.u(self.exe + 0xFA86C)
        city = self.u(app + 0x48) if app else None
        if not city or self.u(city) != self.simcity + 0x13260:
            return False
        clock = self.u(city + 0x130)
        if not clock or self.u(clock) != self.simcity + 0x13988:
            return False
        self.city, self.clock = city, clock
        return True

    def sample(self):
        if not self.clock and not self.resolve():
            return None
        c = self.rd(self.clock + 0x4c, 0x18)
        k = self.rd(self.city + 0x140, 12)
        if not c or not k:
            self.clock = 0
            return None
        days, speed, cpause = struct.unpack("<Iii", c[0:12])     # +0x4c, +0x50, +0x54
        msday = struct.unpack("<i", c[0x14:0x18])[0]             # +0x60
        up, hold, brk = struct.unpack("<iii", k)
        return {"t": time.perf_counter(), "days": days, "speed": speed, "cpause": cpause, "msday": msday,
                "upause": up, "hold": hold, "bracket": brk}

    def threads(self):
        """-> {tid: cpu seconds}"""
        snap = k32.CreateToolhelp32Snapshot(0x4, 0)
        te = THREADENTRY32()
        te.dwSize = ctypes.sizeof(te)
        out = {}
        ok = k32.Thread32First(snap, ctypes.byref(te))
        while ok:
            if te.th32OwnerProcessID == self.pid:
                tid = te.th32ThreadID
                th = self._th.get(tid)
                if th is None:
                    th = k32.OpenThread(0x0800, False, tid)   # THREAD_QUERY_LIMITED_INFORMATION
                    self._th[tid] = th
                if th:
                    a, b, kk, uu = wt.FILETIME(), wt.FILETIME(), wt.FILETIME(), wt.FILETIME()
                    if k32.GetThreadTimes(th, ctypes.byref(a), ctypes.byref(b), ctypes.byref(kk), ctypes.byref(uu)):
                        out[tid] = _ft(kk) + _ft(uu)
            ok = k32.Thread32Next(snap, ctypes.byref(te))
        k32.CloseHandle(snap)
        return out

    def window(self, seconds, hz=50):
        """Sample for `seconds`. Days/s = day-count delta / wall time. Held = share of samples with the clock pause
        count > 0 (and which counter explains it)."""
        dt = 1.0 / hz
        s0 = None
        while s0 is None:
            s0 = self.sample()
            if s0 is None:
                time.sleep(0.2)
        th0 = self.threads()
        n = held = h140 = h144 = h148 = 0
        steps = {}
        last_days, last = s0["days"], s0
        end = s0["t"] + seconds
        while True:
            time.sleep(dt)
            s = self.sample()
            if s is None:
                continue
            n += 1
            held += s["cpause"] > 0
            h140 += s["upause"] > 0
            h144 += s["hold"] > 0
            h148 += s["bracket"] > 0
            d = s["days"] - last_days
            if d:
                steps[d] = steps.get(d, 0) + 1
                last_days = s["days"]
            last = s
            if s["t"] >= end:
                break
        th1 = self.threads()
        wall = last["t"] - s0["t"]
        cpu = {t: th1[t] - th0.get(t, 0.0) for t in th1}
        top = sorted(cpu.items(), key=lambda kv: -kv[1])[:6]
        return {"wall_s": round(wall, 2), "days": last["days"] - s0["days"],
                "days_per_s": round((last["days"] - s0["days"]) / wall, 3) if wall > 0 else 0,
                "speed": last["speed"], "msday": last["msday"],
                "nominal_days_per_s": round(1000.0 / last["msday"], 3) if last["msday"] > 0 else 0,
                "held_pct": round(100.0 * held / max(n, 1), 1), "upause_pct": round(100.0 * h140 / max(n, 1), 1),
                "uihold_pct": round(100.0 * h144 / max(n, 1), 1), "bracket_pct": round(100.0 * h148 / max(n, 1), 1),
                "day_steps": dict(sorted(steps.items())),
                "cpu_ui_pct": round(100.0 * cpu.get(self.tid_ui, 0.0) / wall, 1) if wall > 0 else 0,
                "cpu_all_pct": round(100.0 * sum(cpu.values()) / wall, 1) if wall > 0 else 0,
                "cpu_top": [[t, round(100.0 * c / wall, 1)] for t, c in top], "tid_ui": self.tid_ui}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=int(os.environ.get("SC3_PID", "0") or 0))
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--hz", type=float, default=50)
    ap.add_argument("--once", action="store_true", help="print one raw sample")
    a = ap.parse_args(argv)
    m = Meter(a.pid)
    if a.once:
        print(json.dumps(m.sample()))
        return 0
    print(json.dumps(m.window(a.seconds, a.hz)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
