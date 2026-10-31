"""picker lab (child picker 2026-10-30, owner: "Add a picker tool (also Ctrl+F) to pick a selected building/road/entity").
Posted input only (sc3io), no focus, no z-order change, frames through SC3RESIZE_FRAMEDUMP.

  py -3.12 re/tools/picker_lab.py up   --tag T [--city "Berlin, Germany"] [--env K=V ...]   launch, unpause, keep running
  py -3.12 re/tools/picker_lab.py dump --tag T NAME                 one frame -> verify/picker/runs/T/fd/NAME.png
  py -3.12 re/tools/picker_lab.py click --tag T X Y [--right]       posted click at client X,Y
  py -3.12 re/tools/picker_lab.py key  --tag T VK                   posted key (hex or decimal virtual-key)
  py -3.12 re/tools/picker_lab.py trace --tag T [--secs 20]         read-only Frida trace of the query / picker path
  py -3.12 re/tools/picker_lab.py kill --tag T

The pid of the run is kept in verify/picker/runs/T/pid; SC3_PID is set from it."""
import argparse, os, pathlib, subprocess, sys, time
TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io, sc3wait
import vdscroll_io as vdio

ROOT = TOOLS.parents[1]            # the worktree
MAIN = ROOT.parents[2]             # Simcity
RUNS = pathlib.Path(os.environ.get("PICKER_RUNS") or (MAIN / "verify" / "picker" / "runs"))   # pickerui: PICKER_RUNS=verify/pickerui/runs
WM_RZ_PICKER = 0x8000 + 0x5F0

TRACE_JS = r"""
var ui = Process.getModuleByName('SIMUI.DLL').base;
function modrva(p) { var m = Process.findModuleByAddress(p); return m ? m.name + '+0x' + p.sub(m.base).toString(16) : '' + p; }
function bt(ctx) { return Thread.backtrace(ctx, Backtracer.FUZZY).slice(0, 8).map(modrva).join(' < '); }
function hook(rva, name, f) {
  Interceptor.attach(ui.add(rva), { onEnter: function (a) { try { send(name + ' ' + f(a, this) + ' | ' + bt(this.context)); } catch (e) { send(name + ' err ' + e); } } });
}
hook(0x10bb3, 'query_ctor', function (a, t) { return 'this=' + t.context.ecx; });
hook(0x10c10, 'query_c10', function (a, t) { return 'this=' + t.context.ecx; });
hook(0x10c39, 'query_click', function (a, t) { var c = a[0]; return 'this=' + t.context.ecx + ' cell=' + c.readS32() + ',' + c.add(4).readS32() + ' a1=' + a[1] + ' a2=' + a[2]; });
hook(0x11f0b, 'create', function (a, t) { return 'clsid=0x' + (a[0].toUInt32() >>> 0).toString(16) + ' riid=0x' + (a[1].toUInt32() >>> 0).toString(16); });
"""


def rundir(tag):
    d = RUNS / tag
    (d / "fd").mkdir(parents=True, exist_ok=True)
    vdio.FD = d / "fd"
    return d


def pid_of(tag):
    p = int((rundir(tag) / "pid").read_text())
    os.environ["SC3_PID"] = str(p)
    return p


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["up", "dump", "click", "key", "trace", "kill", "msg", "log", "drag"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--city", default="Berlin, Germany")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--right", action="store_true")
    ap.add_argument("--secs", type=float, default=20)
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
    pid = pid_of(a.tag)
    if a.cmd == "kill":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"])
        return 0
    h = sc3io.game_hwnd()
    if a.cmd == "dump":
        print(vdio.dump(a.args[0]))
    elif a.cmd == "click":
        sc3io.click(h, int(a.args[0]), int(a.args[1]), button="right" if a.right else "left")
    elif a.cmd == "key":
        sc3io.key(h, int(a.args[0], 0))
    elif a.cmd == "msg":   # WM_RZ_PICKER: 1 start (button path), 2 Ctrl+F handler, 3 pick cell X Z, 4 cancel, 5 log current tool, 6 post menu command
        wp = int(a.args[0], 0)
        lp = (int(a.args[1]) & 0xffff) | ((int(a.args[2]) & 0xffff) << 16) if wp == 3 else int(a.args[1], 0) if wp == 6 else 0
        import ctypes
        ctypes.windll.user32.PostMessageW(h, WM_RZ_PICKER, wp, lp)
    elif a.cmd == "drag":   # left-button drag X0 Y0 X1 Y1 (a tool drag)
        x0, y0, x1, y1 = (int(v) for v in a.args[:4])
        sc3io.drag(h, x0, y0, x1, y1, button="left")
    elif a.cmd == "log":
        n = int(a.args[0]) if a.args else 40
        lines = [ln for ln in log.read_text(errors="replace").splitlines() if "PICKER>" in ln]
        print("\n".join(lines[-n:]))
    elif a.cmd == "trace":
        import frida, sc3pause
        paused, det = sc3pause.pause_state(pid)
        if paused:
            print("game is paused (%s): not attaching" % det); return 3
        s = frida.attach(pid)
        sc = s.create_script(TRACE_JS)
        sc.on("message", lambda m, _d: print(m.get("payload", m), flush=True))
        sc.load()
        print("tracing %.0f s" % a.secs, flush=True)
        time.sleep(a.secs)
        s.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
