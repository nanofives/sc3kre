"""closex_drive.py - launch one -multi instance and drive the CLOSEX test (verify/closex/PRE.md).

Only ever touches the PID it started. `launch` starts SC3U.exe directly (sc3wait.launch_game) and does not take the
game lease: the caller must hold it. Subcommands:

    py -3.12 re/tools/closex_drive.py launch <inst_dir> <city.sc3> [--env K=V ...]   -> prints pid, writes <inst>/pid.txt
    py -3.12 re/tools/closex_drive.py close  <pid>          # PostMessage WM_CLOSE to that PID's game window
    py -3.12 re/tools/closex_drive.py altf4  <pid>          # post WM_SYSKEYDOWN/UP VK_F4 with the Alt context bit
    py -3.12 re/tools/closex_drive.py syscls <pid>          # post WM_SYSCOMMAND SC_CLOSE (system menu / taskbar Close)
    py -3.12 re/tools/closex_drive.py grab   <pid> <out.png>
    py -3.12 re/tools/closex_drive.py alive  <pid>          # prints alive / exited <code>
    py -3.12 re/tools/closex_drive.py watch  <pid> <out>    # block until exit, write the exit code to <out>
    py -3.12 re/tools/closex_drive.py kill   <pid>
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")))

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
WM_CLOSE, WM_SYSKEYDOWN, WM_SYSKEYUP, WM_SYSCOMMAND, SC_CLOSE, VK_F4 = 0x10, 0x104, 0x105, 0x112, 0xF060, 0x73


def hwnd_of(pid: int) -> int:
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        p = wt.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(h):
            cls = ctypes.create_unicode_buffer(64)
            u32.GetClassNameW(h, cls, 64)
            if cls.value == "Gonzo":
                found.append(h)
                return False
        return True
    u32.EnumWindows(cb, 0)
    if not found:
        raise SystemExit(f"no visible Gonzo window for pid {pid}")
    return found[0]


def status(pid: int) -> str:
    h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return "gone (cannot open)"
    code = wt.DWORD()
    k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    return "alive" if code.value == 259 else f"exited 0x{code.value:08X}"


def main(a: list[str]) -> int:
    cmd = a[0]
    if cmd == "launch":
        inst = pathlib.Path(a[1]).resolve()
        city = None if a[2] == "-" else str(pathlib.Path(a[2]).resolve())
        env = dict(os.environ)
        env["SC3RESIZE_LOG"] = str(inst / "sc3resize.log")
        for kv in a[3:]:
            if kv == "--env":
                continue
            k, v = kv.split("=", 1)
            env[k] = v
        out = open(inst / "launch.out", "w")
        import sc3wait
        lp, _ = sc3wait.launch_game(inst, city, env=env, out=out)
        pid = lp.pid
        (inst / "pid.txt").write_text(str(pid))
        print(pid)
        return 0
    pid = int(a[1])
    if cmd == "alive":
        print(status(pid)); return 0
    if cmd == "watch":   # hold a handle so the exit code survives; write "<epoch> exited 0x..." to a[2]
        h = k32.OpenProcess(0x101000, False, pid)   # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
        if not h:
            raise SystemExit(f"cannot open pid {pid}")
        k32.WaitForSingleObject(h, 0xFFFFFFFF)
        code = wt.DWORD()
        k32.GetExitCodeProcess(h, ctypes.byref(code))
        pathlib.Path(a[2]).write_text(f"{time.strftime('%H:%M:%S')} pid {pid} exited 0x{code.value:08X}\n")
        return 0
    if cmd == "kill":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"]); return 0
    if cmd == "grab":
        os.environ["SC3_PID"] = str(pid)
        import sc3io
        g = sc3io.grab_to(a[2], sc3io.game_hwnd(pid))
        print("grab ok", a[2]); return 0
    h = hwnd_of(pid)
    if cmd == "close":
        u32.PostMessageW(h, WM_CLOSE, 0, 0)
    elif cmd == "altf4":
        u32.PostMessageW(h, WM_SYSKEYDOWN, VK_F4, 0x20000001 | (0x3E << 16))
        time.sleep(0.08)
        u32.PostMessageW(h, WM_SYSKEYUP, VK_F4, 0xE0000001 | (0x3E << 16))
    elif cmd == "syscls":
        u32.PostMessageW(h, WM_SYSCOMMAND, SC_CLOSE, 0)
    else:
        raise SystemExit("unknown command " + cmd)
    print(cmd, "posted to hwnd", hex(h)); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
