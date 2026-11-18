r"""stylemix_switch_run.py - one arm of the STYLEMIX switch test (task stylemix 2026-11-18).

  py -3.12 re/tools/netmod/stylemix_switch_run.py <arm> <city file in tree\Cities> <seconds> [--off]

Copies the city to tree\Cities\<arm>.sc3 (a new file, never a linked one), sets inst\sc3mods.ini [env]
SC3NETMOD_STYLEMIX=0 with --off (the file the "Turn mods on/off" row writes) or removes it, launches the dev tree
windowed through sc3dev.ps1 run, waits for the city, posts P (resume) and 4 (speed), lets it run <seconds> with
autosave every 120 s, then stops the PID it started. Counts are done afterwards with stylemix_verify_count.py on
tree\Cities\<arm> (auto 5 min).sc3. Posted keys only (sc3io.key), never the real mouse or keyboard.
"""
import configparser
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402
import sc3wait  # noqa: E402

MAIN = r"C:\Users\maria\Desktop\Proyectos\Simcity"
DEV = os.path.join(MAIN, "dev", "stylemix")
TREE, INST = os.path.join(DEV, "tree"), os.path.join(DEV, "inst")


def set_ini(off):
    p = os.path.join(INST, "sc3mods.ini")
    lines = open(p, encoding="cp1252").read().splitlines() if os.path.exists(p) else []
    lines = [ln for ln in lines if not ln.strip().upper().startswith("SC3NETMOD_STYLEMIX=")]
    if off:
        if "[env]" not in [ln.strip().lower() for ln in lines]:
            lines.append("[env]")
        i = [ln.strip().lower() for ln in lines].index("[env]")
        lines.insert(i + 1, "SC3NETMOD_STYLEMIX=0")
    open(p, "w", encoding="cp1252", newline="\r\n").write("\n".join(lines) + "\n")


def main(argv):
    arm, city, secs = argv[0], argv[1], float(argv[2])
    off = "--off" in argv
    cities = os.path.join(TREE, "Cities")
    dst = os.path.join(cities, arm + ".sc3")
    if "--keep" not in argv:
        shutil.copyfile(os.path.join(cities, city), dst)
    for f in os.listdir(cities):
        if f.startswith(arm + " (auto"):
            os.remove(os.path.join(cities, f))
    set_ini(off)
    os.environ["SC3AUTOSAVE_SECONDS"] = "120"
    t0 = time.time()
    out = subprocess.run(["pwsh", "-NoProfile", "-File", os.path.join(MAIN, r"re\scripts\sc3dev.ps1"), "run",
                          "stylemix", "-City", arm + ".sc3"], capture_output=True, text=True).stdout
    m = re.search(r"SC3U pid (\d+)", out)
    if not m:
        print(out); return 1
    pid = int(m.group(1))
    print("arm %s pid %d stylemix %s" % (arm, pid, "OFF" if off else "on"), flush=True)
    try:
        ok, _ = sc3wait.wait_log(os.path.join(INST, "sc3resize.log"), sc3wait.CITY_UP, 150, since=t0)
        print("city up" if ok else "### city never came up", flush=True)
        if not ok:
            return 1
        time.sleep(8)
        hwnd = sc3io.game_hwnd(pid)
        sc3io.key(hwnd, 0x50)                     # P: resume (PAUSEKEY)
        time.sleep(1)
        sc3io.key(hwnd, 0x34)                     # 4: fastest speed (SPEEDKEYS)
        t1 = time.time()
        while time.time() - t1 < secs:
            time.sleep(10)
            if subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True).stdout.find(str(pid)) < 0:
                print("### game exited early"); return 2
        print("ran %.0f s" % (time.time() - t1), flush=True)
        return 0
    finally:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
