"""restore lab (child restore 2026-11-02). Posted input only (sc3io), no focus, frames through SC3RESIZE_FRAMEDUMP.

  py -3.12 re/tools/restore_lab.py up   --tag T [--city "Berlin, Germany"] [--env K=V ...]   launch, unpause, keep running
  py -3.12 re/tools/restore_lab.py query --tag T X Z        open the "?" dialog on cell (X, Z) (WM_RZ_RESTORE 1)
  py -3.12 re/tools/restore_lab.py btn  --tag T             log the restore button's absolute rect (WM_RZ_RESTORE 2)
  py -3.12 re/tools/restore_lab.py msg  --tag T WP [LP]     any WM_RZ_RESTORE (restorefix: 8 age cell LP = x | z << 16 past its
                                                            life, 9 one list scan, 10 break its date as 11-02c did)
  RESTORE_RUNS=<dir> moves the run folders (restorefix used MAIN/verify/restorefix/runs)
  py -3.12 re/tools/restore_lab.py dump --tag T NAME        one frame -> verify/restore/runs/T/fd/NAME.png
  py -3.12 re/tools/restore_lab.py click --tag T X Y        posted left click at client X,Y
  py -3.12 re/tools/restore_lab.py key  --tag T VK          posted key
  py -3.12 re/tools/restore_lab.py log  --tag T [N]         last N RESTORE> lines of resize.log, then sc3restore.log
  py -3.12 re/tools/restore_lab.py kill --tag T

The pid of the run is kept in verify/restore/runs/T/pid; SC3_PID is set from it."""
import argparse, ctypes, os, pathlib, subprocess, sys, time
TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io, sc3wait
import vdscroll_io as vdio

ROOT = TOOLS.parents[1]            # the worktree
MAIN = ROOT.parents[2]             # Simcity
RUNS = pathlib.Path(os.environ.get("RESTORE_RUNS") or (MAIN / "verify" / "restore" / "runs"))
WM_RZ_RESTORE = 0x8000 + 0x5F8


def rundir(tag):
    d = RUNS / tag
    (d / "fd").mkdir(parents=True, exist_ok=True)
    vdio.FD = d / "fd"
    return d


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["up", "query", "btn", "msg", "dump", "click", "key", "log", "kill"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--city", default="Berlin, Germany")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--tree", default=str(ROOT.parents[0] / "tree"))
    ap.add_argument("--inst", default=str(ROOT.parents[0] / "inst"))
    a = ap.parse_args(argv)
    d = rundir(a.tag)
    log = d / "resize.log"
    if a.cmd == "up":
        if log.exists():
            log.unlink()
        env = dict(os.environ)
        env.update({"SC3RESIZE_WINMEM": "0", "SC3RESIZE_LOG": str(log), "SC3RESIZE_FRAMEDUMP": str(d / "fd") + "\\"})
        for kv in a.env:
            k, v = kv.split("=", 1); env[k] = v
        city = pathlib.Path(a.tree) / "Cities" / f"{a.city}.sc3"
        p, t0 = sc3wait.launch_game(a.inst, str(city), env=env, tree=a.tree)
        (d / "pid").write_text(str(p.pid))
        os.environ["SC3_PID"] = str(p.pid)
        print(f"[1/3] launch pid {p.pid} OK", flush=True)
        ok, _ = sc3wait.wait_log(log, r"city HUD became visible", 400)
        print(f"[2/3] city up {'OK' if ok else 'FAIL'}", flush=True)
        if not ok:
            return 2
        time.sleep(4)
        sc3wait.run_after_load(p.pid)
        h = sc3io.game_hwnd()
        _, _, cw, ch = sc3io.client_rect_on_screen(h)
        print(f"[3/3] running, client {cw}x{ch} OK", flush=True)
        return 0
    pid = int((d / "pid").read_text())
    os.environ["SC3_PID"] = str(pid)
    if a.cmd == "kill":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"])
        return 0
    if a.cmd == "log":
        n = int(a.args[0]) if a.args else 40
        lines = [ln for ln in log.read_text(errors="replace").splitlines() if "RESTORE>" in ln]
        print("\n".join(lines[-n:]))
        rl = pathlib.Path(a.inst) / "sc3restore.log"
        if rl.exists():
            print("--- sc3restore.log")
            print("\n".join(rl.read_text(errors="replace").splitlines()[-n:]))
        return 0
    h = sc3io.game_hwnd()
    if a.cmd == "query":
        x, z = int(a.args[0]), int(a.args[1])
        ctypes.windll.user32.PostMessageW(h, WM_RZ_RESTORE, 1, (x & 0xffff) | ((z & 0xffff) << 16))
    elif a.cmd == "btn":
        ctypes.windll.user32.PostMessageW(h, WM_RZ_RESTORE, 2, 0)
    elif a.cmd == "msg":
        ctypes.windll.user32.PostMessageW(h, WM_RZ_RESTORE, int(a.args[0], 0), int(a.args[1], 0) if len(a.args) > 1 else 0)
    elif a.cmd == "dump":
        print(vdio.dump(a.args[0]))
    elif a.cmd == "click":
        sc3io.click(h, int(a.args[0]), int(a.args[1]))
    elif a.cmd == "key":
        sc3io.key(h, int(a.args[0], 0))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
