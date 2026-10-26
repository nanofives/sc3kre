"""zoomband_run.py - one test game for task zoomband (2026-10-26, from zoomcrash_run.py): launch through version.dll, size the client from
outside, attach exit_catch, then drive the zoom with posted clicks. No cursor, no keyboard, no foreground.

    py re/tools/zoomcrash_run.py --tree <TREE> --inst <inst dir> --city Europolis --client 2560x1351 --tag t1 \
        --script "in:6,dump:a,out:1,in:1,scroll:4,..." [--env K=V ...] [--nocatch]

Script items: in:n / out:n = n clicks on the minimap zoom buttons (1.5 s apart), key:addx2 / key:subx1 = posted
numpad +/- keys, audit:name = run hook_audit.py on the game, dump:tag = frame dump,
wait:s, scroll:n = n right-drags across the map, arrow:dir:taps[:hold] = arrow-key scroll (key_state_spoof hook,
no real keys), size:WxH = resize the client again, quit = close + wait.
Prints one "[N/M] item STATUS" line per item. The game is closed at the end (WM_CLOSE, then our own pid only).
"""
import argparse
import ctypes
import os
import re
import shutil
import subprocess
import sys
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # per-monitor v2: physical pixels, like the game
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import key_state_spoof as kss  # noqa: E402
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP, WM_CLOSE = 0x200, 0x201, 0x202, 0x204, 0x205, 0x10
SWP_NOZORDER, SWP_NOACTIVATE, SWP_NOMOVE = 0x4, 0x10, 0x2


def lp(x, y):
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def post(h, m, wp, l):
    user32.PostMessageW(wintypes.HWND(h), m, wintypes.WPARAM(wp), wintypes.LPARAM(l))


def hwnd_of(pid):
    found = []
    cb_t = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(h, buf, 64)
            if buf.value == "Gonzo":
                found.append(h)
        return True
    user32.EnumWindows(cb_t(cb), 0)
    return found[0] if found else None


def client(h):
    r = wintypes.RECT()
    user32.GetClientRect(wintypes.HWND(h), ctypes.byref(r))
    return r.right, r.bottom


def set_client(h, w, ht):
    wr, cr = wintypes.RECT(), wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(h), ctypes.byref(wr))
    user32.GetClientRect(wintypes.HWND(h), ctypes.byref(cr))
    dw = (wr.right - wr.left) - cr.right
    dh = (wr.bottom - wr.top) - cr.bottom
    user32.SetWindowPos(wintypes.HWND(h), None, 0, 0, w + dw, ht + dh, SWP_NOZORDER | SWP_NOACTIVATE)


class Proc:   # a game started earlier: poll / wait / kill by handle, our own pid only
    def __init__(self, pid):
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k, self.pid, self.returncode = k, pid, None
        self.h = k.OpenProcess(0x1000 | 0x100000 | 0x0001, False, pid)   # QUERY_LIMITED | SYNCHRONIZE | TERMINATE

    def poll(self):
        c = wintypes.DWORD()
        if self.k.GetExitCodeProcess(self.h, ctypes.byref(c)) and c.value != 259:
            self.returncode = c.value
        return self.returncode

    def wait(self, secs):
        self.k.WaitForSingleObject(self.h, int(secs * 1000))
        if self.poll() is None:
            raise subprocess.TimeoutExpired("SC3U", secs)
        return self.returncode

    def kill(self):
        self.k.TerminateProcess(self.h, 1)


class Log:
    def __init__(self, path):
        self.path, self.pos = path, 0

    def text(self):
        try:
            with open(self.path, "rb") as f:
                return f.read().decode("latin-1")
        except OSError:
            return ""

    def wait(self, pat, secs, since=0, alive=None):
        t0 = time.time()
        rx = re.compile(pat)
        while time.time() - t0 < secs:
            t = self.text()
            m = rx.search(t, since)
            if m:
                return m, len(t)
            if alive and not alive():
                return None, len(t)
            time.sleep(0.25)
        return None, len(self.text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--inst", required=True)
    ap.add_argument("--city", default="Europolis")
    ap.add_argument("--client", default="2560x1351")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--script", default="in:6")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--nocatch", action="store_true")
    ap.add_argument("--stalk", action="store_true", help="attach zoom_stalk.py instead of exit_catch.py")
    ap.add_argument("--pid", type=int, help="drive a game this session already started instead of launching one")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--keep", action="store_true", help="leave the game running at the end (reuse with --pid)")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    want_max = a.client.lower() == "max"   # maximized through sc3io.maximize_without_focus (no activation)
    cw, ch = (0, 0) if want_max else map(int, a.client.lower().split("x"))
    env = dict(os.environ)
    env.update({"SC3MODS_DIR": a.inst, "SC3MODS_MULTI": "1", "SC3RESIZE_WINMEM": "0",
                "SC3RESIZE_FRAMEDUMP": os.path.join(a.outdir, a.tag + "_")})
    for kv in a.env:
        k, v = kv.split("=", 1)
        env[k] = v
    apps = os.path.join(a.tree, "Apps")
    city = os.path.join(a.tree, "Cities", a.city + ".sc3")
    if a.pid:
        p = Proc(a.pid)
    else:
        p = subprocess.Popen([os.path.join(apps, "SC3U.exe"), city], cwd=apps, env=env)
    pid = p.pid
    alive = lambda: p.poll() is None
    print(f"launched pid {pid} client {cw}x{ch} tag {a.tag}", flush=True)
    log = Log(os.path.join(a.inst, "sc3resize.log"))
    t0 = time.time()
    h = None
    while time.time() - t0 < 400 and alive():
        h = hwnd_of(pid)
        if h:
            break
        time.sleep(0.5)
    if not h:
        print("no window", flush=True)
        return 2
    if a.pid and client(h) == (cw, ch):
        m, pos = True, len(log.text())
    else:
        m, pos = log.wait(r"HOLD> released|RZ   TIMING pass|SRCRECT> tile step \[0 0 600 56\]", 600, alive=alive)
    print("city up" if m else "city NOT seen in log", "after %.0f s" % (time.time() - t0), flush=True)
    if want_max:
        import sc3io
        time.sleep(10)
        sc3io.maximize_without_focus(h)
        time.sleep(1)
        cw, ch = client(h)
        m, pos = log.wait(r"RZ   TIMING pass %dx%d" % (cw, ch), 60, pos, alive=alive)
    elif client(h) != (cw, ch):
        time.sleep(10)
        set_client(h, cw, ch)
        m, pos = log.wait(r"RZ   TIMING pass %dx%d" % (cw, ch), 60, pos, alive=alive)
    print(f"client now {client(h)} layout {'done' if m else 'NOT seen'}", flush=True)
    time.sleep(3)
    cat = None
    if not a.nocatch:
        tool = "zoom_stalk.py" if a.stalk else "exit_catch.py"
        cat = subprocess.Popen([sys.executable, os.path.join(HERE, tool), "--pid", str(pid), "--log",
                                os.path.join(a.outdir, a.tag + ("_stalk.txt" if a.stalk else "_catch.jsonl")), "--secs", "3000"])
        time.sleep(6)
    items = [s for s in a.script.split(",") if s]
    spoof = None
    status = 0
    for i, it in enumerate(items, 1):
        if not alive():
            print(f"[{i}/{len(items)}] {it} SKIP (game gone, exit code {p.returncode})", flush=True)
            status = 1
            continue
        what, _, arg = it.partition(":")
        cw, ch = client(h)
        t = log.text()
        fs = re.findall(r"HUDSCALE> Auto: client %dx%d -> factor ([0-9.]+)" % (cw, ch), t)
        f = float(fs[-1]) if fs and env.get("SC3RESIZE_HUDSCALE") != "0" else 1.0
        before = len(t)
        if what in ("in", "out"):
            # minimap zoom buttons, native offsets from the client's bottom-right corner (800x600: in at 666,547)
            ox, oy = (134, 53) if what == "in" else (28, 53)
            x, y = int(cw - ox * f), int(ch - oy * f)
            for _ in range(int(arg or 1)):
                post(h, WM_MOUSEMOVE, 0, lp(x, y)); time.sleep(0.08)
                post(h, WM_LBUTTONDOWN, 1, lp(x, y)); time.sleep(0.12)
                post(h, WM_LBUTTONUP, 0, lp(x, y)); time.sleep(1.5)
                if not alive():
                    break
        elif what == "key":
            # posted key, no focus: add / sub = numpad + / - (ZOOMKEYS maps the main-row +/- to these), n times
            name, _, cnt = arg.partition("x")
            vk = {"add": 0x6B, "sub": 0x6D, "plus": 0xBB, "minus": 0xBD}[name]
            for _ in range(int(cnt or 1)):
                post(h, 0x100, vk, 1); time.sleep(0.05)
                post(h, 0x101, vk, 0xC0000001); time.sleep(1.5)
                if not alive():
                    break
        elif what == "audit":
            subprocess.run([sys.executable, os.path.join(HERE, "hook_audit.py"), "--pid", str(pid), "--out",
                            os.path.join(a.outdir, a.tag + "_" + (arg or "audit") + ".txt"), "--save",
                            os.path.join(a.outdir, a.tag + "_" + (arg or "audit") + ".pkl")], timeout=900)
        elif what == "dump":
            with open(env["SC3RESIZE_FRAMEDUMP"] + "req", "w") as fo:
                fo.write(arg + "\n")
            log.wait(r"FRAMEDUMP> " + re.escape(arg), 15, before, alive=alive)
        elif what == "wait":
            t1 = time.time()
            while time.time() - t1 < float(arg) and alive():
                time.sleep(0.25)
        elif what == "scroll":
            mx, my = cw // 2, ch // 2
            for k in range(int(arg or 1)):
                dx = 300 if k % 2 == 0 else -300
                post(h, WM_MOUSEMOVE, 0, lp(mx, my)); time.sleep(0.08)
                post(h, WM_RBUTTONDOWN, 2, lp(mx, my)); time.sleep(0.15)
                for s in range(1, 13):
                    post(h, WM_MOUSEMOVE, 2, lp(mx + dx * s // 12, my + dx * s // 24)); time.sleep(0.08)
                time.sleep(1.0)
                post(h, WM_RBUTTONUP, 0, lp(mx + dx, my + dx // 2)); time.sleep(0.8)
        elif what == "arrow":
            d, _, rest = arg.partition(":")
            taps, _, hold = rest.partition(":")
            if spoof is None:
                os.environ["SC3_PID"] = str(pid)
                for _ in range(3):   # a loaded city starts paused: the sc3resize P key unpauses (posted, no focus)
                    if kss.sc3pause.sim_paused(pid) is False:
                        break
                    post(h, 0x100, 0x50, 1); time.sleep(0.05); post(h, 0x101, 0x50, 0xC0000001)
                    t1 = time.time()   # a loaded PC can take seconds to act on it: a second P would pause again
                    while time.time() - t1 < 8 and kss.sc3pause.sim_paused(pid) is not False:
                        time.sleep(0.25)
                spoof = kss.Spoof().__enter__()
            kss.scroll(h, d.split("+"), int(taps or 1), spoof, gap=float(hold or 0.12))
        elif what == "size":
            w2, h2 = map(int, arg.lower().split("x"))
            set_client(h, w2, h2)
            log.wait(r"RZ   TIMING pass %dx%d" % (w2, h2), 60, before, alive=alive)
            time.sleep(2)
        time.sleep(0.5)
        new = log.text()[before:]
        cz = [l.split("] ", 2)[-1] for l in new.splitlines() if "CITYZOOM>" in l or "FAULT" in l or "CREATEFAIL" in l]
        ok = alive()
        print(f"[{i}/{len(items)}] {it} {'PASS' if ok else 'FAIL'} client {client(h) if ok else '-'} " +
              (" | ".join(cz)[:400] if cz else ""), flush=True)
        if not ok:
            status = 1
    if spoof is not None:
        try:
            spoof.__exit__(None, None, None)
        except Exception as e:
            print("spoof detach:", e, flush=True)
    if alive() and not a.keep:
        post(h, WM_CLOSE, 0, 0)
        try:
            p.wait(20)
        except subprocess.TimeoutExpired:
            print("no exit after WM_CLOSE: killing our own pid", pid, flush=True)
            p.kill()
            p.wait(10)
    rc = p.poll()
    if a.keep and rc is None:
        print(f"game left running: pid {pid}", flush=True)
        return status
    print(f"game exit code: {rc if rc is None else '0x%08X' % (rc & 0xffffffff)}", flush=True)
    if cat:
        try:
            cat.wait(15)
        except subprocess.TimeoutExpired:
            cat.kill()
    shutil.copy(log.path, os.path.join(a.outdir, a.tag + "_sc3resize.log"))
    perf = os.path.join(a.inst, "sc3perf.log")
    if os.path.exists(perf):
        shutil.copy(perf, os.path.join(a.outdir, a.tag + "_sc3perf.log"))
    return status


if __name__ == "__main__":
    sys.exit(main())
