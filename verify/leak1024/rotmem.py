#!/usr/bin/env python3
r"""rotmem.py - rotation memory probe (child rotleak, 2026-11-17).

Launches the rotleak tree (sc3dev run), waits for the city, then posts N clicks on the minimap rotate button
(800x600 layout, (752,567), same as cam_soak / nramp_shots) and reads the game's private bytes and largest free
address block from OUTSIDE (GetProcessMemoryInfo + VirtualQueryEx), so stock arms with no sc3perf measure the same way.
Never moves the real cursor: sc3io posts messages only.

  py -3.12 rotmem.py ARM [--stock] [--n 20] [--city "Berlin, Germany.sc3"] [--gap 2.5] [--keep] [--env K=V ...]
                         [--zoom N]  (N zoom in/out round trips instead of rotations, a control)

One line per step "[i/N] rot private=.. MB free=.. MB STATUS". The game is stopped by PID at the end unless --keep.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(MAIN, "re", "tools"))
import sc3io  # noqa: E402

DEV = os.path.join(MAIN, "dev", "leak1024")
ROT, ZIN, ZOUT = (752, 567), (666, 546), (772, 546)
k32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", wt.DWORD),
                ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_size_t), ("State", wt.DWORD),
                ("Protect", wt.DWORD), ("Type", wt.DWORD)]


k32.OpenProcess.restype = wt.HANDLE
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]


def mem(pid):
    """(private MB, largest free block MB below 4 GB, committed private block count)"""
    h = k32.OpenProcess(0x0410, False, pid)   # QUERY_INFORMATION | VM_READ
    if not h:
        return None
    try:
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        if not psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
            return None
        addr, largest = 0x10000, 0
        mbi = MBI()
        while addr < 0xFFFF0000:
            if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            if mbi.State == 0x10000:   # MEM_FREE
                largest = max(largest, mbi.RegionSize)
            addr = (mbi.BaseAddress or 0) + mbi.RegionSize
        return pmc.PrivateUsage / 2**20, largest / 2**20
    finally:
        k32.CloseHandle(h)


def alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def answering(h, ms=60000):
    res = ctypes.c_ulong()
    return ctypes.windll.user32.SendMessageTimeoutW(h, 0, 0, 0, 0, ms, ctypes.byref(res)) != 0


def launch(stock, city, env):
    e = dict(os.environ)
    e.update(env)
    args = ["pwsh", "-NoProfile", "-File", os.path.join(MAIN, "re", "scripts", "sc3dev.ps1"), "run", "leak1024", "-City", city]
    if stock:
        args.append("-Stock")
    subprocess.run(args, env=e, check=True, cwd=MAIN)
    with open(os.path.join(DEV, "last_pid")) as f:
        return int(f.read().strip())


def watch_windowed(pid, secs):
    """Poll for `secs`: the moment the game shows a window without a caption (exclusive fullscreen popup), stop it."""
    u = ctypes.windll.user32
    t0 = time.time()
    while time.time() - t0 < secs:
        if not alive(pid):
            return True
        try:
            h = sc3io.game_hwnd(pid)
        except Exception:
            h = 0
        if h and u.IsWindowVisible(h) and not (u.GetWindowLongW(h, -16) & 0x00C00000):
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            print(f"pid {pid}: window style 0x{u.GetWindowLongW(h, -16) & 0xffffffff:08X} has no caption = fullscreen, STOPPED")
            return False
        time.sleep(0.5)
    return True


def shot(a, i, h=None):
    if i > a.shots or not a.shots:
        return
    try:
        sc3io.grab_to(os.path.join(HERE, "shots", f"{a.arm}_{i}.png"), hwnd=h, settle=0.3)
    except Exception as e:   # CaptureError: occluded etc., the measurement goes on
        print(f"  grab {i}: {e}", flush=True)


def settle_mem(pid, secs=4.0):
    time.sleep(secs)
    return mem(pid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm")
    ap.add_argument("--stock", action="store_true")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--city", default="Berlin, Germany.sc3")
    ap.add_argument("--gap", type=float, default=2.5)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--zoom", action="store_true")
    ap.add_argument("--pid", type=int, default=0, help="use a running game instead of launching")
    ap.add_argument("--wait", type=float, default=75.0)
    ap.add_argument("--env", nargs="*", default=[])
    ap.add_argument("--shots", type=int, default=0, help="desktop grab after steps 0..N (proves the click landed)")
    ap.add_argument("--zout", type=int, default=0, help="zoom-out clicks before the rotations (widest zoom)")
    ap.add_argument("--zin", type=int, default=0, help="zoom-in clicks before the rotations (closest zoom)")
    ap.add_argument("--winonly", action="store_true", help="stock control: loader + sc3winonly.dll only")
    a = ap.parse_args()
    env = dict(kv.split("=", 1) for kv in a.env)
    if a.stock:
        raise SystemExit("--stock runs exclusive fullscreen (changes the display mode): use --winonly")
    if a.winonly:
        env["SC3MODS_LIST"] = "sc3winonly.dll"
    if a.pid:
        pid = a.pid
    else:
        t0 = time.time()
        pid = launch(a.stock, a.city, env)
        print(f"arm {a.arm}: pid {pid} stock={a.stock} env={env}", flush=True)
        if not watch_windowed(pid, a.wait):
            return 3
        if not alive(pid):
            print(f"arm {a.arm}: game gone during load ({time.time() - t0:.0f} s)")
            return 2
    os.environ["SC3_PID"] = str(pid)
    h = sc3io.game_hwnd(pid)
    cx, cy, cw, ch = sc3io.client_rect_on_screen(h)
    print(f"arm {a.arm}: client {cw}x{ch} at ({cx},{cy})", flush=True)
    for _ in range(a.zin):
        sc3io.click(h, *ZIN)
        time.sleep(3.0)
    for _ in range(a.zout):
        sc3io.click(h, *ZOUT)
        time.sleep(3.0)
    m0 = settle_mem(pid)
    print(f"[0/{a.n}] start private={m0[0]:.1f} MB free={m0[1]:.0f} MB PASS", flush=True)
    rows = [m0]
    shot(a, 0, h)
    status = "PASS"
    for i in range(1, a.n + 1):
        if a.zoom:
            sc3io.click(h, *ZOUT)
            time.sleep(a.gap)
            sc3io.click(h, *ZIN)
        else:
            sc3io.click(h, *ROT)
        time.sleep(a.gap)
        if not alive(pid):
            status = "CRASH"
        elif not answering(h):
            status = "HANG"
        m = mem(pid) if status == "PASS" else (0, 0)
        rows.append(m)
        if i <= a.shots:
            shot(a, i, h)
        print(f"[{i}/{a.n}] {'zoomtrip' if a.zoom else 'rot'} private={m[0]:.1f} MB free={m[1]:.0f} MB {status}", flush=True)
        if status != "PASS":
            break
    if status == "PASS":
        m1 = settle_mem(pid, 6.0)
        rows.append(m1)
        d = m1[0] - m0[0]
        print(f"arm {a.arm}: private {m0[0]:.1f} -> {m1[0]:.1f} MB (+{d:.1f}, {d / a.n:.2f} MB per step), "
              f"largest free {m0[1]:.0f} -> {m1[1]:.0f} MB", flush=True)
    if not a.keep and not a.pid and alive(pid):
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
