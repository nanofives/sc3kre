"""Headless control of the Parsec Virtual Display Adapter, so the game can run OFF-SCREEN.

Why: `sc3io` can drive the game with no cursor and no focus, and (measured 2026-09-07) even while
minimised - but CAPTURE needs the window present and unoccluded, because the only method that sees
this game's DirectDraw layer is a desktop-DC BitBlt of the glass. A virtual display resolves that
tension: the game gets a real, always-unoccluded desktop that is not on any physical monitor, so
input AND screenshots both work while nothing appears on the user's screens.

Protocol (nomi-san/parsec-vdd). The driver alone does nothing: a client must hold the device open
and PING it, or the driver culls the virtual displays after a couple of seconds. So `--daemon` is
the normal mode, and killing the daemon is the clean teardown - there is no persistent state to
leave behind.

    python re/tools/vdd.py --version        # read-only: open the device and report the driver version
    python re/tools/vdd.py --list           # current desktop layout
    python re/tools/vdd.py --daemon         # add ONE virtual display and hold it until killed
    python re/tools/vdd.py --daemon --keep-alive-only   # ping without adding (diagnostic)

`--daemon` prints the new display's DeviceName and bounds once Windows reports it, so a caller can
place a window there.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

# Parsec VDD device interface class GUID.
VDD_ADAPTER_GUID = "{00b41627-04c4-429e-a26e-0265cf50c8fa}"

VDD_IOCTL_VERSION = 0x0022E000
VDD_IOCTL_ADD     = 0x0022E004
VDD_IOCTL_REMOVE  = 0x0022A008
VDD_IOCTL_UPDATE  = 0x0022A00C

GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
FILE_SHARE_READ, FILE_SHARE_WRITE = 1, 2
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

DIGCF_PRESENT, DIGCF_DEVICEINTERFACE = 0x02, 0x10

# ⚠️ Prototypes MUST be declared. ctypes defaults every return to a 32-bit int, which TRUNCATES a
# 64-bit HANDLE - SetupDiGetClassDevsW then looked like it had failed (its real handle was valid,
# the top 32 bits were just thrown away) and this reported "no device interface present" against a
# driver that was working fine. Measured 2026-09-07.
setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.HWND,
                                          wintypes.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                                 wintypes.DWORD, ctypes.c_void_p]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                                      ctypes.c_void_p, wintypes.DWORD,
                                                      ctypes.POINTER(wintypes.DWORD),
                                                      ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel32.DeviceIoControl.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ctypes.POINTER(wintypes.ULONG))]


def _guid(s: str) -> GUID:
    g = GUID()
    ole32 = ctypes.WinDLL("ole32")
    if ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g)) != 0:
        raise RuntimeError(f"bad GUID {s}")
    return g


def device_path() -> str:
    """The \\\\?\\ROOT#DISPLAY#... interface path for the Parsec VDD, via SetupAPI."""
    g = _guid(VDD_ADAPTER_GUID)
    hdev = setupapi.SetupDiGetClassDevsW(ctypes.byref(g), None, None,
                                         DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if not hdev or hdev == INVALID_HANDLE_VALUE:
        raise RuntimeError("SetupDiGetClassDevsW failed - is the Parsec VDD driver installed?")
    try:
        did = SP_DEVICE_INTERFACE_DATA()
        did.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
        if not setupapi.SetupDiEnumDeviceInterfaces(hdev, None, ctypes.byref(g), 0,
                                                    ctypes.byref(did)):
            raise RuntimeError(
                "no Parsec VDD device interface present. The adapter shows in Device Manager but "
                "exposes no interface - the driver may need a reinstall "
                "(C:\\Program Files\\ParsecVDisplay\\driver\\parsec-vdd-setup.exe)")
        need = wintypes.DWORD()
        setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(did), None, 0,
                                                  ctypes.byref(need), None)
        buf = ctypes.create_string_buffer(need.value)
        # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize is 6 on x86, 8 on x64
        ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
        if not setupapi.SetupDiGetDeviceInterfaceDetailW(hdev, ctypes.byref(did), buf,
                                                         need.value, None, None):
            raise RuntimeError(f"SetupDiGetDeviceInterfaceDetailW failed: {ctypes.get_last_error()}")
        return ctypes.wstring_at(ctypes.addressof(buf) + ctypes.sizeof(wintypes.DWORD))
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(hdev)


def open_device() -> int:
    path = device_path()
    h = kernel32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE,
                             FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING,
                             FILE_ATTRIBUTE_NORMAL, None)
    if not h or h == INVALID_HANDLE_VALUE:
        raise RuntimeError(f"CreateFileW on {path} failed: {ctypes.get_last_error()}")
    return h


def _ioctl(h: int, code: int, inbuf: bytes = b"", outlen: int = 32) -> bytes:
    out = ctypes.create_string_buffer(outlen)
    ret = wintypes.DWORD()
    ok = kernel32.DeviceIoControl(
        wintypes.HANDLE(h), wintypes.DWORD(code),
        ctypes.c_char_p(inbuf) if inbuf else None, wintypes.DWORD(len(inbuf)),
        out, wintypes.DWORD(outlen), ctypes.byref(ret), None)
    if not ok:
        raise RuntimeError(f"DeviceIoControl(0x{code:08X}) failed: {ctypes.get_last_error()}")
    return out.raw[:ret.value]


def version(h: int) -> int:
    r = _ioctl(h, VDD_IOCTL_VERSION, outlen=4)
    return int.from_bytes(r[:4], "little") if r else -1


def ping(h: int) -> None:
    _ioctl(h, VDD_IOCTL_UPDATE, outlen=4)


def add_display(h: int) -> int:
    r = _ioctl(h, VDD_IOCTL_ADD, outlen=4)
    return int.from_bytes(r[:4], "little") if r else -1


def remove_display(h: int, index: int) -> None:
    _ioctl(h, VDD_IOCTL_REMOVE, inbuf=index.to_bytes(4, "little"), outlen=4)


def screens() -> list[tuple[str, tuple[int, int, int, int], bool]]:
    """(DeviceName, (x, y, w, h), is_primary) for every active desktop monitor."""
    out: list[tuple[str, tuple[int, int, int, int], bool]] = []

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32)]

    CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                            ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def cb(hmon, _hdc, _lprc, _lp):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcMonitor
        out.append((mi.szDevice, (r.left, r.top, r.right - r.left, r.bottom - r.top),
                    bool(mi.dwFlags & 1)))
        return True

    user32.EnumDisplayMonitors(None, None, CB(cb), 0)
    return out




# ---------------------------------------------------------------------------------------------
# Attaching: the driver "add" only makes a virtual MONITOR exist. Windows still has to extend the
# desktop onto it, which is a ChangeDisplaySettingsEx call, not a VDD one. Measured 2026-09-07:
# after the add, \.\DISPLAY5..20 all exist with a monitor child and StateFlags 0 (detached), and
# the ParsecVDisplay UI shows the display as "[offline]" until this runs.
# ---------------------------------------------------------------------------------------------

DM_BITSPERPEL, DM_PELSWIDTH, DM_PELSHEIGHT = 0x00040000, 0x00080000, 0x00100000
DM_DISPLAYFREQUENCY, DM_POSITION = 0x00400000, 0x00000020
CDS_UPDATEREGISTRY, CDS_NORESET, CDS_SET_PRIMARY = 0x01, 0x10000000, 0x10
DISP_CHANGE_SUCCESSFUL = 0
ATTACHED_FLAG, PRIMARY_FLAG = 0x1, 0x4


class DEVMODEW(ctypes.Structure):
    _fields_ = [("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
                ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
                ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                ("dmPositionX", wintypes.LONG), ("dmPositionY", wintypes.LONG),
                ("dmDisplayOrientation", wintypes.DWORD), ("dmDisplayFixedOutput", wintypes.DWORD),
                ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
                ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
                ("dmCollate", ctypes.c_short), ("dmFormName", wintypes.WCHAR * 32),
                ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
                ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD),
                ("dmDisplayFlags", wintypes.DWORD), ("dmDisplayFrequency", wintypes.DWORD),
                ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
                ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
                ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
                ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32),
                ("DeviceString", wintypes.WCHAR * 128), ("StateFlags", wintypes.DWORD),
                ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]


def display_devices() -> list[DISPLAY_DEVICEW]:
    out, n = [], 0
    while True:
        d = DISPLAY_DEVICEW()
        d.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        if not user32.EnumDisplayDevicesW(None, n, ctypes.byref(d), 0):
            break
        out.append(d)
        n += 1
    return out


def first_detached_vdd() -> str | None:
    for d in display_devices():
        if "Parsec Virtual Display" in d.DeviceString and not (d.StateFlags & ATTACHED_FLAG):
            return d.DeviceName
    return None


def desktop_right_edge() -> int:
    return max((b[0] + b[2] for _, b, _ in screens()), default=0)


def attach(device: str, w: int, h: int, x: int, y: int = 0, freq: int = 60) -> None:
    """Extend the desktop onto `device`. Two-phase: stage with NORESET, then apply globally."""
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    dm.dmDeviceName = device
    dm.dmPelsWidth, dm.dmPelsHeight = w, h
    dm.dmBitsPerPel, dm.dmDisplayFrequency = 32, freq
    dm.dmPositionX, dm.dmPositionY = x, y
    dm.dmFields = (DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT
                   | DM_BITSPERPEL | DM_DISPLAYFREQUENCY)
    r = user32.ChangeDisplaySettingsExW(ctypes.c_wchar_p(device), ctypes.byref(dm), None,
                                        CDS_UPDATEREGISTRY | CDS_NORESET, None)
    if r != DISP_CHANGE_SUCCESSFUL:
        raise RuntimeError(f"ChangeDisplaySettingsExW(stage) on {device} returned {r}")
    r = user32.ChangeDisplaySettingsExW(None, None, None, 0, None)
    if r != DISP_CHANGE_SUCCESSFUL:
        raise RuntimeError(f"ChangeDisplaySettingsExW(apply) returned {r}")


def detach(device: str) -> None:
    """Remove `device` from the desktop - an all-zero DEVMODE is the documented way."""
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    dm.dmDeviceName = device
    dm.dmFields = DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT
    user32.ChangeDisplaySettingsExW(ctypes.c_wchar_p(device), ctypes.byref(dm), None,
                                    CDS_UPDATEREGISTRY | CDS_NORESET, None)
    user32.ChangeDisplaySettingsExW(None, None, None, 0, None)




# ---------------------------------------------------------------------------------------------
# End-to-end setup. Three separate things have to be true, and they are easy to confuse:
#   1. ParsecVDisplay.exe RUNNING  - it holds the device open and PINGs it. The driver culls
#      virtual displays without that ping, so this process is the display's lifetime.
#   2. A virtual display ADDED     - the app's "ADD DISPLAY" button. This only makes a virtual
#      MONITOR exist; \.\DISPLAY5..20 appear with StateFlags 0.
#   3. The desktop EXTENDED onto it - ChangeDisplaySettingsEx. Until this, the app shows the
#      display as "[offline]" and nothing can be placed there.
#
# The app exposes no CLI for step 2 (only -silent), and its "ADD DISPLAY" is a custom-styled WPF
# element that UIA reports as Text - but its PARENT is a real Button with InvokePattern, which
# invokes cleanly with no cursor and no focus. Posting a click at its rect does NOT work.
# ---------------------------------------------------------------------------------------------

PARSEC_APP = r"C:\Program Files\ParsecVDisplay\ParsecVDisplay.exe"

_UIA_INVOKE = r"""
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$p = Get-Process ParsecVDisplay -EA SilentlyContinue | Select-Object -First 1
if (-not $p) { Write-Output 'NOPROC'; exit 1 }
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition(
          [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $p.Id)
$w = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
if (-not $w) { Write-Output 'NOWINDOW'; exit 1 }
$el = $w.FindFirst([System.Windows.Automation.TreeScope]::Descendants,
        (New-Object System.Windows.Automation.PropertyCondition(
          [System.Windows.Automation.AutomationElement]::NameProperty, 'ADD DISPLAY')))
if (-not $el) { Write-Output 'NOBUTTON'; exit 1 }
$walker = [System.Windows.Automation.TreeWalker]::RawViewWalker
$cur = $el; $d = 0
while ($cur -ne $null -and $d -lt 6) {
  if (($cur.GetSupportedPatterns() | ForEach-Object { $_.ProgrammaticName }) -match 'Invoke') {
    $cur.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Write-Output 'INVOKED'; exit 0
  }
  $cur = $walker.GetParent($cur); $d++
}
Write-Output 'NOPATTERN'; exit 1
"""


def parsec_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ParsecVDisplay.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return "ParsecVDisplay" in out


def ensure(size: str = "1920x1080", at: int | None = None) -> int:
    """Get to a state where one Parsec virtual display is attached. Idempotent."""
    if any("Parsec Virtual Display" in d.DeviceString and (d.StateFlags & ATTACHED_FLAG)
           for d in display_devices()):
        print("[=] a Parsec virtual display is already attached")
        show("layout")
        return 0

    if not parsec_running():
        if not os.path.exists(PARSEC_APP):
            print(f"STOP: {PARSEC_APP} not found", file=sys.stderr)
            return 2
        print("[*] starting ParsecVDisplay (it must stay running - it pings the driver)")
        subprocess.Popen([PARSEC_APP])
        time.sleep(6)

    if first_detached_vdd() is None:
        print("[*] invoking 'ADD DISPLAY' via UI Automation")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", _UIA_INVOKE],
                           capture_output=True, text=True)
        print(f"    -> {r.stdout.strip() or r.stderr.strip()}")
        time.sleep(4)

    dev = first_detached_vdd()
    if dev is None:
        print("STOP: no detached Parsec virtual display slot appeared.", file=sys.stderr)
        return 2
    w, h = (int(v) for v in size.lower().split("x"))
    x = at if at is not None else desktop_right_edge() + 100
    print(f"[*] attaching {dev} as {w}x{h} at x={x}")
    attach(dev, w, h, x, 0)
    time.sleep(1.5)
    show("after")
    print()
    print("ATTACH BEFORE LAUNCHING THE GAME. Changing the display topology while SC3U.exe is")
    print("running KILLED it (measured 2026-09-07) - DirectDraw does not survive a topology change.")
    return 0


def teardown() -> int:
    for d in display_devices():
        if "Parsec Virtual Display" in d.DeviceString and (d.StateFlags & ATTACHED_FLAG):
            print(f"[*] detaching {d.DeviceName}")
            detach(d.DeviceName)
    time.sleep(1.0)
    subprocess.run(["taskkill", "/IM", "ParsecVDisplay.exe", "/F"],
                   capture_output=True, text=True)
    print("[*] ParsecVDisplay stopped - the driver culls the virtual display without its ping")
    show("after teardown")
    return 0


def show(label: str) -> list:
    s = screens()
    print(f"{label} ({len(s)} display(s)):")
    for name, b, prim in s:
        print(f"   {name:14} {b[2]}x{b[3]} at ({b[0]},{b[1]}){'  PRIMARY' if prim else ''}")
    return s


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--keep-alive-only", action="store_true")
    ap.add_argument("--ensure", action="store_true",
                    help="one command: start the app, add a display, attach it (idempotent)")
    ap.add_argument("--teardown", action="store_true",
                    help="detach the virtual display and stop the app")
    ap.add_argument("--attach", action="store_true",
                    help="extend the desktop onto the first DETACHED Parsec virtual display")
    ap.add_argument("--detach", metavar="DEVICE", help=r"remove e.g. \.\DISPLAY5 from the desktop")
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--at", type=int, default=None, help="x position; default = right of everything")
    a = ap.parse_args(argv)

    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

    if a.list:
        show("current layout")
        for d in display_devices():
            if "Parsec" in d.DeviceString:
                st = "ATTACHED" if d.StateFlags & ATTACHED_FLAG else "detached"
                print(f"   [vdd] {d.DeviceName:14} {st}")
        return 0

    if a.ensure:
        return ensure(a.size, a.at)

    if a.teardown:
        return teardown()

    if a.detach:
        detach(a.detach)
        show("after detach")
        return 0

    if a.attach:
        dev = first_detached_vdd()
        if not dev:
            print("STOP: no DETACHED Parsec virtual display exists. Add one first "
                  "(ParsecVDisplay 'ADD DISPLAY'), then re-run --attach.", file=sys.stderr)
            return 2
        w, h = (int(v) for v in a.size.lower().split("x"))
        x = a.at if a.at is not None else desktop_right_edge() + 100
        print(f"[*] attaching {dev} as {w}x{h} at x={x}")
        attach(dev, w, h, x, 0)
        time.sleep(1.5)
        show("after attach")
        return 0

    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

    try:
        path = device_path()
    except RuntimeError as e:
        print(f"STOP: {e}", file=sys.stderr)
        return 2
    print(f"[*] device: {path}")
    h = open_device()
    try:
        v = version(h)
        print(f"[*] driver version: {v}")
        if a.version:
            return 0

        before = show("before")
        names_before = {n for n, _, _ in before}

        if not a.keep_alive_only:
            idx = add_display(h)
            print(f"[+] added virtual display, index {idx}")

        # The driver culls displays unless pinged. Hold them up until we are killed.
        deadline = time.time() + 8
        new = None
        while time.time() < deadline:
            ping(h)
            cur = screens()
            fresh = [s for s in cur if s[0] not in names_before]
            if fresh:
                new = fresh[0]
                break
            time.sleep(0.2)

        if new:
            print(f"[+] NEW DISPLAY {new[0]}  {new[1][2]}x{new[1][3]} at ({new[1][0]},{new[1][1]})")
        elif not a.keep_alive_only:
            print("[!] no new display appeared within 8 s (the ping loop is running; "
                  "it may still show up)")
        show("after")
        print("[*] holding the display up - PING every 100 ms. Kill this process to remove it.",
              flush=True)
        while True:
            ping(h)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[*] released")
        return 0
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(h))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
