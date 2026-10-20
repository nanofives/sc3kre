#!/usr/bin/env python3
r"""sc3pause.py - read SC3's user-pause state WITHOUT Frida, and refuse a Frida attach while the game is paused
(task avcore, 2026-10-19).

Why: a Frida attach made while the game is paused (even one that detaches again, e.g. a camera call), followed by an
unpause, deadlocked SC3 three times on 2026-10-19 (avjunc, avcore, bvlanes): main thread in the STRTSIM car move ->
SIMSPR -> SIMCITY EnterCriticalSection. Attaching to a running sim was clean every time. re/analysis/AVENUE_LANES.md 6.

The pause state, ReadProcessMemory only:
  app   = *(SC3U.exe 0x004fa86c)       the app singleton: SC3U FUN_00402e74 (the app ctor) stores DAT_004fa86c = this
                                       [CONFIRMED @ 0x00402e74]
  city  = *(app + 0x48)                the city / sim coordinator, vtable SIMCITY.DLL 0x10013260 (re/tools/sim_status.py).
                                       No static writer of app+0x48 was found in the export, so every read CHECKS the
                                       vtable; a mismatch is reported as "unknown", never guessed
  depth = *(int *)(city + 0x140)       the user-pause depth: SIMCITY FUN_100056bb increments it and posts 0xc2a35d7f when
                                       it reaches 1, FUN_10005773 decrements it (not below 0) and posts 0xc2a35d81 at 0
                                       [CONFIRMED @ 0x100056bb, 0x10005773]
paused = depth > 0. A DLL's runtime base comes from the process's module list (EnumProcessModulesEx).

  py -3.12 sc3pause.py [PID]          print the state (exit 0 running, 1 paused, 2 unknown)

In a tool, before any frida.attach:
  import sc3pause; sc3pause.require_running(pid)     exits 3 if paused / unknown, unless --force-paused was given on
                                                      the command line or SC3_FORCE_PAUSED=1 is set (inherited by
                                                      subprocesses, so rb_lab -> np_drive passes it on)
Importing this module removes --force-paused from sys.argv (and sets SC3_FORCE_PAUSED=1), so a tool's own argument
parsing never sees it.
"""
import ctypes
import ctypes.wintypes as wt
import os
import struct
import sys

APP_GLOBAL = 0x004FA86C            # SC3U.exe VA, image base 0x00400000
APP_CITY = 0x48
CITY_VTABLE_RVA = 0x13260          # SIMCITY.DLL 0x10013260 - 0x10000000
CITY_PAUSE = 0x140
EXIT_REFUSED = 3

if "--force-paused" in sys.argv:
    while "--force-paused" in sys.argv:
        sys.argv.remove("--force-paused")
    os.environ["SC3_FORCE_PAUSED"] = "1"

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_size_t)]
_k32.CloseHandle.argtypes = [wt.HANDLE]
_psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD),
                                        wt.DWORD]
_psapi.GetModuleBaseNameW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]
PROCESS_QUERY_INFORMATION, PROCESS_VM_READ, LIST_MODULES_32BIT = 0x0400, 0x0010, 0x01


def _modules(h):
    n = wt.DWORD()
    arr = (wt.HMODULE * 1024)()
    if not _psapi.EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(n), LIST_MODULES_32BIT):
        return {}
    out = {}
    for i in range(n.value // ctypes.sizeof(wt.HMODULE)):
        buf = ctypes.create_unicode_buffer(260)
        _psapi.GetModuleBaseNameW(h, arr[i], buf, 260)
        out[buf.value.lower()] = arr[i] or 0
    return out


def _u32(h, addr):
    b = ctypes.create_string_buffer(4)
    got = ctypes.c_size_t()
    if not _k32.ReadProcessMemory(h, ctypes.c_void_p(addr), b, 4, ctypes.byref(got)) or got.value != 4:
        return None
    return struct.unpack("<I", b.raw)[0]


def pause_state(pid):
    """-> (paused: True / False / None for unknown, detail str)"""
    h = _k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, int(pid))
    if not h:
        return None, "cannot open pid %s (error %d)" % (pid, ctypes.get_last_error())
    try:
        mods = _modules(h)
        exe, simcity = mods.get("sc3u.exe"), mods.get("simcity.dll")
        if not exe or not simcity:
            return None, "SC3U.exe / SIMCITY.DLL not in pid %s's modules (still loading?)" % pid
        app = _u32(h, exe + (APP_GLOBAL - 0x00400000))
        if not app:
            return None, "no app object yet (DAT_004fa86c = 0)"
        city = _u32(h, app + APP_CITY)
        if not city:
            return None, "no city loaded (app+0x48 = 0)"
        vt = _u32(h, city)
        if vt != simcity + CITY_VTABLE_RVA:
            return None, "app+0x48 does not hold the city (vtable 0x%08x, expected SIMCITY+0x%x = 0x%08x)" % (
                vt or 0, CITY_VTABLE_RVA, simcity + CITY_VTABLE_RVA)
        depth = _u32(h, city + CITY_PAUSE)
        if depth is None:
            return None, "city+0x140 unreadable"
        return depth > 0, "pause depth %d" % depth
    finally:
        _k32.CloseHandle(h)


def sim_paused(pid):
    """True = paused, False = running, None = cannot tell"""
    return pause_state(pid)[0]


def require_running(pid, what="attach"):
    """call before frida.attach: exits EXIT_REFUSED when the game is paused (or the state cannot be read), unless
    --force-paused / SC3_FORCE_PAUSED=1"""
    paused, detail = pause_state(pid)
    if paused is False:
        return
    if os.environ.get("SC3_FORCE_PAUSED") == "1":
        print("sc3pause: %s while %s (--force-paused)" % (what, "paused" if paused else "pause state unknown: " + detail),
              file=sys.stderr)
        return
    if paused:
        print("game is paused: unpause by keys (sc3io) first, then attach (%s; refused %s, pid %s; --force-paused to "
              "override)" % (detail, what, pid), file=sys.stderr)
    else:
        print("cannot read the pause state (%s): refused %s, pid %s; --force-paused to override" % (detail, what, pid),
              file=sys.stderr)
    sys.exit(EXIT_REFUSED)


def main(argv):
    if len(argv) > 1:
        pid = int(argv[1])
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import sc3io
        pid = sc3io.game_pid()
    paused, detail = pause_state(pid)
    print("pid %s: %s (%s)" % (pid, {True: "PAUSED", False: "running", None: "unknown"}[paused], detail))
    return {True: 1, False: 0, None: 2}[paused]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
