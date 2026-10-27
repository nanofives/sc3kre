"""Launch one hudclick arm on a stock tree: start, wait for the city, dismiss tips, maximize, report.

Usage: py -3.12 re/tools/hudclick_launch.py --tree <abs tree> --city <abs .sc3> --out <abs dir> [--inst <mod dir>] [--env K=V ...]

Writes <out>/pid.txt, <out>/resize.log (SC3RESIZE_LOG), <prefix>max.bmp when SC3RESIZE_FRAMEDUMP is set
(desktop grabs show white/black while the game is not in the foreground), prints the pid, client size and the logged
HUD factor. The caller must hold the game lease (the direct launch does not take it). The game is left running; kill it by the pid in pid.txt (only that pid).
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys
import time

TOOLS = pathlib.Path(r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
sys.path.insert(0, str(TOOLS))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True); ap.add_argument("--city", required=True)
    ap.add_argument("--inst", default=None, help="folder with the mod DLLs + logs (SC3MODS_DIR); default <tree>/Apps")
    ap.add_argument("--out", required=True); ap.add_argument("--env", action="append", default=[])
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    apps = pathlib.Path(a.tree) / "Apps"
    env = dict(os.environ)
    env["SC3RESIZE_LOG"] = str(out / "resize.log")
    for kv in a.env:
        k, v = kv.split("=", 1); env[k] = v
    (out / "env.txt").write_text("\n".join(a.env) + "\n")
    import sc3wait  # noqa: E402
    lp, _ = sc3wait.launch_game(a.inst or apps, a.city, env=env, out=open(out / "launch.out", "w"), tree=a.tree,
                                pre_args=["-intro:off"])
    pid = lp.pid
    os.environ["SC3_PID"] = str(pid)
    (out / "pid.txt").write_text(str(pid))
    print("game pid", pid, flush=True)
    import sc3io  # noqa: E402
    log = out / "resize.log"
    t0 = time.time()
    while time.time() - t0 < 150:
        if log.exists() and "city HUD became visible" in log.read_text(errors="replace"):
            break
        time.sleep(1)
    else:
        print("city never came up (pid left running)"); return 2
    time.sleep(6)
    sc3wait.run_after_load(pid)
    subprocess.run([sys.executable, str(TOOLS / "dismiss_tips.py")], env=os.environ)
    hwnd = sc3io.game_hwnd()
    sc3io.maximize_without_focus(hwnd)
    time.sleep(8)
    env_fd = env.get("SC3RESIZE_FRAMEDUMP")
    if env_fd:
        pathlib.Path(env_fd + "req").write_text("max")
        time.sleep(1.5)
    _, _, cw, ch = sc3io.client_rect_on_screen(hwnd)
    txt = log.read_text(errors="replace")
    m = re.findall(r"HUDSCALE> \d+ window\(s\) enlarged ([0-9.]+)x about \((\d+),(\d+)\)", txt)
    print(f"client {cw}x{ch}, HUD factor {m[-1][0] if m else 'none'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
