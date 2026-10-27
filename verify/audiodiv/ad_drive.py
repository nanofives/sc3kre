"""Push the camera past the map edges with posted input (sc3io scroll: posted keys + key-state spoof, no cursor).

Usage: py -3.12 ad_drive.py <pid> <plan>
  plan = comma list of <dirs>:<taps>[:<hold s>], dirs joined by '+', e.g. "up+right:40,up:30,left:60"
  or "mm:<x>:<y>" to click the minimap at client (x, y) and jump the camera there.
Stops at once if the pid is gone and prints DEAD with the step index.
"""
import subprocess
import sys
import time

sys.path.insert(0, r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
import os  # noqa: E402
os.environ.setdefault("SC3_PID", sys.argv[1] if len(sys.argv) > 1 else "")
import sc3io  # noqa: E402


def alive(pid):
    return b"SC3U" in subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True).stdout


def main():
    pid, plan = int(sys.argv[1]), sys.argv[2]
    h = sc3io.game_hwnd(pid)
    items = [x for x in plan.split(",") if x]
    try:
        for n, it in enumerate(items, 1):
            if it.startswith("mm:"):
                _, x, y = it.split(":")
                sc3io.click(h, int(x), int(y))
                time.sleep(3)
            elif it.startswith("wait:"):
                time.sleep(float(it.split(":")[1]))
            else:
                f = it.split(":")
                dirs, taps, hold = f[0], int(f[1]), float(f[2]) if len(f) > 2 else 0.15
                for _ in range(taps):
                    sc3io.scroll(h, dirs.split("+"), taps=1, hold=hold)
                    if not alive(pid):
                        break
            ok = alive(pid)
            print("[%d/%d] %s %s" % (n, len(items), it, "PASS" if ok else "DEAD"), flush=True)
            if not ok:
                return 1
    finally:
        sc3io.end_scroll()
    return 0


if __name__ == "__main__":
    sys.exit(main())
