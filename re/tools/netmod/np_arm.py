#!/usr/bin/env python3
r"""np_arm.py - one newpiece test arm: launch, draw the two pre-registered roads, save, copy the save (2026-10-12).

  py -3.12 np_arm.py <tree> <arm> [--city <src.sc3>] [--no-draw] [--keep]

<tree>\re\harness\inst_newpiece holds the mod DLLs (sc3resize.dll...). The city is copied to <inst>\roadless_<arm>.sc3
and launched through sc3wait.launch_game (SC3U.exe + SC3MODS_DIR/MULTI); this script only ever touches the pid it started. The window is moved to the 100 % monitor
DISPLAY2 so game, input and dump coordinates coincide (grabs of this machine's 125 % monitors came back white on
2026-10-12; frames come from sc3resize's in-process DUMP instead, np_drive.py shot).

Input sequence (identical in every arm, PRE.md): left drag 20,450 -> 120,500 with no tool (pans the camera onto the
empty island), Roads tool (0x10004001), drag 150,300 -> 270,360, drag 300,240 -> 180,300, Save (0x10009002).
"""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
STOCK_CITY = r"C:\Users\maria\Desktop\Proyectos\Simcity\Cities\Roadless Paradise.sc3"


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout


def find_pid(exe_path, not_in):
    out = ps("Get-CimInstance Win32_Process -Filter \"Name like 'SC3U%'\" | ForEach-Object { \"$($_.ProcessId)|$($_.ExecutablePath)\" }")
    for line in out.splitlines():
        if "|" in line:
            pid, path = line.split("|", 1)
            if os.path.normcase(path.strip()) == os.path.normcase(exe_path) and int(pid) not in not_in:
                return int(pid)
    return None


def drive(*args):
    r = subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py")] + list(args), capture_output=True, text=True,
                       env=os.environ)
    print("  np_drive", " ".join(args), "->", (r.stdout + r.stderr).strip().splitlines()[-1:] or "")
    return r.returncode


def main(argv):
    tree, arm = argv[1], argv[2]
    city = argv[argv.index("--city") + 1] if "--city" in argv else STOCK_CITY
    inst = os.path.join(tree, "re", "harness", "inst_newpiece")
    exe = os.path.join(tree, "Apps", "SC3U.exe")
    vdir = os.path.join(REPO, "verify", "newpiece")
    dst = os.path.join(inst, "roadless_%s.sc3" % arm)
    if os.path.abspath(city) != os.path.abspath(dst):
        shutil.copyfile(city, dst)
    before = set()
    p0 = find_pid(exe, set())
    if p0:
        raise SystemExit("a game from this tree is already running (pid %d); stop it first" % p0)
    log = open(os.path.join(inst, "launch_%s.out" % arm), "w")
    sys.path.insert(0, os.path.join(REPO, "re", "tools"))
    import sc3wait
    proc, t_launch = sc3wait.launch_game(inst, dst, out=log, tree=tree)
    pid = proc.pid
    time.sleep(1)
    if proc.poll() is not None:
        raise SystemExit("game did not start (exit %s, see %s)" % (proc.returncode, log.name))
    print("arm %s pid %d" % (arm, pid))
    os.environ["SC3_PID"] = str(pid)
    import sc3io
    import ctypes
    sc3wait.wait_city_up(os.environ.get("SC3RESIZE_LOG", os.path.join(inst, "sc3resize.log")), t_launch)
    h = sc3io.game_hwnd()
    ctypes.windll.user32.SetWindowPos(h, 0, 2700, 60, 0, 0, 0x0001 | 0x0004 | 0x0010)
    time.sleep(2)
    subprocess.run([sys.executable, os.path.join(REPO, "re", "tools", "dismiss_tips.py")], env=os.environ)
    time.sleep(2)
    drive("shot", os.path.join(vdir, "%s_01_city.png" % arm))
    if "--no-draw" not in argv:
        drive("drag", "20,450", "120,500")
        time.sleep(1.5)
        drive("cmd", "0x10004001")
        time.sleep(1)
        drive("drag", "150,300", "270,360")
        time.sleep(1.5)
        drive("drag", "300,240", "180,300")
        time.sleep(1.5)
        drive("shot", os.path.join(vdir, "%s_04_roads.png" % arm))
        t_save = time.time()
        drive("cmd", "0x10009002")
        sc3wait.wait_file_saved(dst, t_save)
        shutil.copyfile(dst, os.path.join(inst, "%s_after.sc3" % arm))
        print("saved copy -> %s" % os.path.join(inst, "%s_after.sc3" % arm))
    print("pid %d left running" % pid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
