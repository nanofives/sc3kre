"""One arm of verify/leftclick ZOOMCENTER: launch an instance, zoom and rotate at 800x600 and maximized, and record for
every camera zoom/rotate call whether the tile at the map-area centre stayed there.

Hooks (read-only, SIMSPR from the live base): camera vt+0x38 FUN_10006752(zoom, flag, tx, ty) and vt+0x48
FUN_10006a55(rot, flag, tx, ty). onEnter: the game's own pick FUN_1000902f (mode 0, then 1) at the map-area centre.
onLeave: the same pick again, and where the passed tile landed on screen (tile -> world FUN_1000a513 minus the new
origin +0x54/+0x58). The map-area centre is read from the live side panel / bar rects and handed to the script.

Usage: py -3.12 re/tools/zoomcenter_run_arm.py --inst <abs instance folder> --city <abs .sc3> --out <abs dir>
       [--env NAME=VALUE ...]
Also clicks the four minimap buttons twice each (pair order A B C D A B C D).
Kills only the PID it started.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time

import frida

TOOLS = pathlib.Path(r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
sys.path.insert(0, str(TOOLS))
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var ss = Process.getModuleByName("SIMSPR.DLL").base;
var pick = new NativeFunction(ss.add(0x902f), 'int',
    ['pointer', 'pointer', 'int', 'int', 'pointer', 'pointer', 'int', 'pointer', 'int'], 'fastcall');
var t2w = new NativeFunction(ss.add(0xa513), 'void', ['pointer', 'int', 'int', 'pointer', 'pointer'], 'thiscall');
var cx = 352, cy = 272;
rpc.exports = { setc: function(x, y){ cx = x; cy = y; } };
function pk(cam){ var b = Memory.alloc(8);
  var ok = pick(cam, ptr(0), cx, cy, b, b.add(4), 0, ptr(0), 0) & 0xff;
  if (!ok) ok = pick(cam, ptr(0), cx, cy, b, b.add(4), 1, ptr(0), 0) & 0xff;
  return ok ? [b.readS32(), b.add(4).readS32()] : null; }
function hook(off, name){
  Interceptor.attach(ss.add(off), {
    onEnter: function(){ var sp = this.context.esp; this.cam = this.context.ecx;
      this.a = [sp.add(4).readS32(), sp.add(8).readU8(), sp.add(12).readS32(), sp.add(16).readS32()];
      this.old = name == "zoom" ? this.cam.add(0x28).readS32() : this.cam.add(0x2c).readS32();
      this.bt = Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 4).map(function(x){
        var m = Process.findModuleByAddress(x); return m ? m.name + "+0x" + x.sub(m.base).toString(16) : x.toString(); });
      this.p0 = pk(this.cam); this.o0 = [this.cam.add(0x54).readS32(), this.cam.add(0x58).readS32()]; },
    onLeave: function(){ var c = this.cam, r = {t:name, from:this.old, to:this.a[0], tile:[this.a[2], this.a[3]],
        centre:[cx, cy], pick_before:this.p0, pick_after:pk(c), origin_before:this.o0,
        origin_after:[c.add(0x54).readS32(), c.add(0x58).readS32()],
        rect64:[c.add(0x64).readS32(), c.add(0x68).readS32(), c.add(0x6c).readS32(), c.add(0x70).readS32()], bt:this.bt};
      if (this.a[2] != 0x7fffffff && this.a[3] != 0x7fffffff) { var b = Memory.alloc(8);
        t2w(c, this.a[2], this.a[3], b, b.add(4));
        r.landed = [b.readS32() - r.origin_after[0], b.add(4).readS32() - r.origin_after[1]]; }
      send(r); }});
}
hook(0x6752, "zoom");
hook(0x6a55, "rotate");
"""


def game_child(launcher_pid: int, timeout: float = 30) -> int:
    t0 = time.time()
    while time.time() - t0 < timeout:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              f"(Get-CimInstance Win32_Process -Filter \"ParentProcessId={launcher_pid} and Name='SC3U.exe'\").ProcessId"],
                             capture_output=True, text=True).stdout.strip()
        if out.isdigit():
            return int(out)
        time.sleep(0.5)
    raise SystemExit("no SC3U child")


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inst", required=True); ap.add_argument("--city", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--env", action="append", default=[])
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["SC3RESIZE_LOG"] = str(out / "resize.log")
    for kv in a.env:
        k, v = kv.split("=", 1); env[k] = v
    lp = subprocess.Popen([str(pathlib.Path(a.inst) / "mods_launch.exe"), "-multi", "--", a.city],
                          stdout=open(out / "launch.out", "w"), stderr=subprocess.STDOUT, env=env,
                          creationflags=0x08000000)
    pid = game_child(lp.pid)
    os.environ["SC3_PID"] = str(pid)
    print("game pid", pid, flush=True)
    import sc3io  # noqa: E402
    log = out / "resize.log"
    t0 = time.time()
    while time.time() - t0 < 120:
        if log.exists() and "city HUD became visible" in log.read_text(errors="replace"):
            break
        time.sleep(1)
    else:
        print("city never came up"); subprocess.run(["taskkill", "/PID", str(pid), "/F"]); return 2
    time.sleep(6)
    subprocess.run([sys.executable, str(TOOLS / "dismiss_tips.py")], env=os.environ)
    hwnd = sc3io.game_hwnd()
    rec = open(out / "zoom.jsonl", "w", encoding="utf-8")

    def emit(d):
        rec.write(json.dumps(d) + "\n"); rec.flush()

    sc3pause.require_running(pid, "zoomcenter_run_arm")
    sess = frida.attach(pid)
    scr = sess.create_script(JS)
    scr.on("message", lambda m, _d: emit(m.get("payload", m)))
    scr.load()

    def tree_centre():
        r = subprocess.run([sys.executable, str(TOOLS / "uiwin_dump.py")], capture_output=True, text=True, env=os.environ)
        side = bar = mini = None
        for ln in r.stdout.splitlines():
            if "abs [" not in ln: continue
            rect = json.loads(ln.split("abs ")[1].split(" loc")[0])
            if "SIMUI.DLL+0xa9834" in ln: side = rect
            elif "SIMUI.DLL+0xa40ec" in ln: bar = rect
            elif "SIMUI.DLL+0xaa180" in ln: mini = rect
        return side, bar, mini

    state = {}

    def setc(label):
        side, bar, mini = tree_centre()
        c = (side[0] // 2, bar[1] // 2)
        state["mini"] = mini
        scr.exports_sync.setc(*c)
        emit({"t": "mark", "label": label, "side": side, "bar": bar, "mini": mini, "centre": c})
        print(label, "side", side, "bar", bar, "mini", mini, "centre", c, flush=True)

    # the four 26x29 GZWIND buttons inside the minimap (local rects from the tree): centres, minimap-local
    MINI_BTNS = (("mini btn A (100,120)", 113, 134), ("mini btn B (34,120)", 47, 134),
                 ("mini btn C (120,100)", 133, 114), ("mini btn D (14,100)", 27, 114))

    def step(label, fn, wait=2.5):
        emit({"t": "mark", "label": label}); fn(); time.sleep(wait)

    VK_ADD, VK_SUB, VK_PGDN, VK_PGUP = 0x6B, 0x6D, 0x22, 0x21

    def block(tag, click_xy, drag):
        step(f"{tag} click {click_xy}", lambda: sc3io.click(hwnd, *click_xy))
        for nm, vk in (("zoom in", VK_ADD), ("zoom out", VK_SUB), ("PageDown", VK_PGDN), ("PageUp", VK_PGUP)):
            step(f"{tag} {nm}", lambda vk=vk: sc3io.key(hwnd, vk))
        step(f"{tag} right-drag {drag}", lambda: sc3io.drag(hwnd, *drag, button="right"))
        for nm, vk in (("zoom in", VK_ADD), ("zoom out", VK_SUB)):
            step(f"{tag} {nm} after drag", lambda vk=vk: sc3io.key(hwnd, vk))
        m = state["mini"]
        for nm, lx, ly in MINI_BTNS + MINI_BTNS:
            step(f"{tag} {nm}", lambda lx=lx, ly=ly: sc3io.click(hwnd, m[0] + lx, m[1] + ly))

    setc("800x600")
    block("800x600", (200, 200), (400, 300, 300, 250))
    emit({"t": "mark", "label": "maximize"}); sc3io.maximize_without_focus(hwnd); time.sleep(6)
    setc("maximized")
    block("max", (1400, 800), (900, 500, 700, 400))
    emit({"t": "mark", "label": "restore"}); sc3io.restore_without_focus(hwnd); time.sleep(6)
    setc("restored")
    for nm, vk in (("zoom in", VK_ADD), ("zoom out", VK_SUB)):
        step(f"restored {nm}", lambda vk=vk: sc3io.key(hwnd, vk))
    scr.unload(); sess.detach(); rec.close()
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
