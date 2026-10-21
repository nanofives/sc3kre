"""undo_drive.py - drive a live sc3undo test game step by step (from the 2026-10-20 sc3undo session).

Instance folder: %SC3UNDO_INST% (default re/harness/inst_undoleft); owner: %SC3_SESSION% (default undo-left).

  launch <city.sc3> <outdir>     acquire the lease, start bin/mods_launch.exe -multi, wait for the city
  shot <name>                    grab the window to <outdir>/<name>.png
  click x y | drag x0 y0 x1 y1   posted left-button input (sc3io)
  key VK [ctrl]                  posted key
  cmd 1|2                        post WM_UNDO_CMD (1 undo, 2 redo) straight to the window
  log                            tail the mod log
  stop                           kill OUR game (the lease stays held)
State in %TEMP%/sc3undo_drive_state.json.
"""
import json, os, subprocess, sys, time, pathlib, ctypes

ROOT = pathlib.Path(r"C:\Users\maria\Desktop\Proyectos\Simcity")
BIN = pathlib.Path(os.environ.get("SC3UNDO_INST", str(ROOT / "re" / "harness" / "inst_undoleft")))
STATE = pathlib.Path(os.environ.get("TEMP", ".")) / "sc3undo_drive_state.json"
OWNER = os.environ.get("SC3_SESSION", "undo-left")
sys.path.insert(0, str(ROOT / "re" / "tools"))


def lock(*args):
    r = subprocess.run(["pwsh", "-NoProfile", "-File", str(ROOT / "re" / "harness" / "game_lock.ps1"), *args],
                       capture_output=True, text=True)
    print(r.stdout.strip()[-400:])
    return r.returncode


def st():
    return json.loads(STATE.read_text())


def io():
    os.environ["SC3_PID"] = str(st()["pid"])
    import sc3io
    return sc3io


def main(a):
    cmd = a[0]
    if cmd == "launch":
        city, out = a[1], pathlib.Path(a[2]); out.mkdir(parents=True, exist_ok=True)
        if lock("-Acquire", "-Owner", OWNER, "-Minutes", "60", "-Note", "sc3undo mod test") != 0:
            print("LEASE NOT HELD - not launching"); return 2
        env = dict(os.environ, SC3_SESSION=OWNER, SC3UNDO_LOG=str(out / "undo.log"), SC3RESIZE_LOG=str(out / "resize.log"),
                   SC3RESIZE_WINMEM="0", SC3UNDO_TEST="1", SC3RESIZE_FRAMEDUMP=str(out / "fd_"))
        lo = open(out / "launch.out", "w")
        lp = subprocess.Popen([str(BIN / "mods_launch.exe"), "-multi", "--", city], cwd=str(BIN),
                              stdout=lo, stderr=subprocess.STDOUT, env=env, creationflags=0x08000000)
        pid = None
        for _ in range(60):
            o = subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"(Get-CimInstance Win32_Process -Filter \"ParentProcessId={lp.pid} and Name='SC3U.exe'\").ProcessId"],
                               capture_output=True, text=True).stdout.strip()
            if o.isdigit(): pid = int(o); break
            time.sleep(0.5)
        if not pid: print("no SC3U child"); return 2
        STATE.write_text(json.dumps({"pid": pid, "launcher": lp.pid, "out": str(out)}))
        print("game pid", pid)
        t0 = time.time()
        while time.time() - t0 < 120:
            p = out / "resize.log"
            if p.exists() and "city HUD became visible" in p.read_text(errors="replace"): break
            time.sleep(1)
        else:
            print("city HUD never reported visible (continuing)")
        time.sleep(3)
        print("ready after %.0f s" % (time.time() - t0))
        return 0
    s = st()
    out = pathlib.Path(s["out"])
    if cmd == "shot":
        m = io(); m.grab_to(str(out / (a[1] + ".png"))); print("shot", out / (a[1] + ".png"))
    elif cmd == "click":
        m = io(); m.click(m.game_hwnd(), int(a[1]), int(a[2]))
    elif cmd == "drag":
        m = io(); m.drag(m.game_hwnd(), int(a[1]), int(a[2]), int(a[3]), int(a[4]), button="left")
    elif cmd == "key":
        m = io(); h = m.game_hwnd()
        u = ctypes.windll.user32
        vk = int(a[1], 0)
        if len(a) > 2 and a[2] == "ctrl":
            u.PostMessageW(h, 0x100, 0x11, 0x001D0001)
        u.PostMessageW(h, 0x100, vk, 0x00000001); time.sleep(0.05); u.PostMessageW(h, 0x101, vk, 0xC0000001)
        if len(a) > 2 and a[2] == "ctrl":
            u.PostMessageW(h, 0x101, 0x11, 0xC01D0001)
    elif cmd == "cmd":
        m = io(); ctypes.windll.user32.PostMessageW(m.game_hwnd(), 0x8000 + 0x5d0, int(a[1]), int(a[2], 0) if len(a) > 2 else 0)
    elif cmd == "dump":
        tag = a[1]
        (out / "fd_req").write_text(tag)
        for _ in range(60):
            time.sleep(0.25)
            f = out / ("fd_" + tag + ".bmp")
            if f.exists() and not (out / "fd_req").exists():
                time.sleep(0.5)
                from PIL import Image
                Image.open(f).save(out / ("fd_" + tag + ".png")); f.unlink()
                print("dump", out / ("fd_" + tag + ".png")); break
        else:
            print("no frame dump")
    elif cmd == "log":
        p = out / "undo.log"
        print("\n".join(p.read_text(errors="replace").splitlines()[-int(a[1]) if len(a) > 1 else -25:]))
    elif cmd == "stop":
        for pid in (s["pid"], s["launcher"]):
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        time.sleep(2)
        print("game stopped; the lease is still held: release it with game_lock.ps1 -Release -Owner", OWNER)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
