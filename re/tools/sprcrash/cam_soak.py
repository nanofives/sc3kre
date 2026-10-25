#!/usr/bin/env python3
r"""cam_soak.py - zoom / rotate soak for the SIMSPR+0xDF01 crash (task sprcrash, 2026-10-24).

SC3_PID = the game (a city loaded, sim running). One line per step: "[N/M] what STATUS". Stops at the first crash
(process gone) or hang (window not answering for 60 s) and prints the verdict.

  py -3.12 cam_soak.py buttons N [--edits K]   game path: minimap zoom in / out / rotate buttons, numpad + / -, a minimap
                                               click; every K steps a Road tool drag in the map area (edits)
  py -3.12 cam_soak.py cam N                   nramp_cam's Frida jobs, one attach, random zoom 0..4 / rot 0..3 / tile
                                               (SC3_CAM_RAW=1: the old bare SetZoom / SetRotate calls, Frida 'steal'; =2: bare calls, 'propagate')
Client coordinates are the 800x600 layout (nramp_shots.py): zoom in (666,546), zoom out (772,546), rotate (752,567),
minimap diamond centre (717,511) about 62 x 64 px half-size.
SC3_BUDGET_REF = a dump of the open budget dialog: every 5 steps a frame dump closes that dialog if it is up.
"""
import ctypes
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "netmod"))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402

user32 = ctypes.windll.user32
ZIN, ZOUT, ROT = (666, 546), (772, 546), (752, 567)
VK_ADD, VK_SUB = 0x6B, 0x6D
NP = os.path.join(HERE, "..", "netmod", "np_drive.py")


def alive(pid):
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def answering(h, ms=10000):
    res = ctypes.c_ulong()
    return user32.SendMessageTimeoutW(h, 0, 0, 0, 0x0, ms, ctypes.byref(res)) != 0   # WM_NULL, SMTO_NORMAL (ABORTIFHUNG gives up at 5 s)


def check(pid, h):
    if not alive(pid):
        return "CRASH"
    if not answering(h, 60000):   # 60 s: the PC runs several games at once, a zoom can take 10+ s
        return "HANG" if alive(pid) else "CRASH"
    return "PASS"


def budget(h):
    """Close the yearly budget dialog (it holds the sim and eats clicks): a frame dump (sc3resize DUMP trigger, np_drive
    shot) compared on budget_closer.py's two patches with SC3_BUDGET_REF (a dump of the open dialog). 1 = closed."""
    ref = os.environ.get("SC3_BUDGET_REF")
    if not ref:
        return 0
    import np_drive
    import budget_closer
    from PIL import Image
    out = os.path.join(os.path.dirname(ref), "soak_chk.png")
    try:
        np_drive.shot(out, timeout=30)
        im = Image.open(out).convert("RGB")
    except (SystemExit, OSError):   # no present in time, or a dump file still held by the game
        return 0
    rf = Image.open(ref).convert("RGB")
    if im.size != rf.size:
        return 0
    if max(budget_closer.diff(im.crop(p), rf.crop(p)) for p in budget_closer.PATCHES) < 6.0:
        sc3io.click(h, *budget_closer.OK)
        time.sleep(1.5)
        return 1
    return 0


def minimap_click(h):
    # a point inside the minimap diamond (centre (717,511)), camera jumps there
    u, v = random.uniform(-0.8, 0.8), random.uniform(-0.8, 0.8)
    x = int(717 + (u - v) * 31)
    y = int(511 + (u + v) * 32)
    sc3io.click(h, x, y)


def road_drag(h):
    subprocess.run([sys.executable, NP, "cmd", "0x10004001"], capture_output=True)
    time.sleep(0.6)
    x0, y0 = random.randint(80, 620), random.randint(80, 460)
    x1, y1 = x0 + random.choice((-1, 1)) * random.randint(40, 160), y0 + random.choice((-1, 1)) * random.randint(20, 80)
    sc3io.drag(h, x0, y0, max(10, min(690, x1)), max(10, min(530, y1)), button="left", steps=8)
    time.sleep(0.4)
    sc3io.key(h, 0x1B)   # Esc: leave the tool


def buttons(pid, h, n, edits):
    for i in range(1, n + 1):
        r = random.random()
        if r < 0.25:
            what = "zoom in"; sc3io.click(h, *ZIN)
        elif r < 0.50:
            what = "zoom out"; sc3io.click(h, *ZOUT)
        elif r < 0.75:
            what = "rotate"; sc3io.click(h, *ROT)
        elif r < 0.85:
            what = "key +"; sc3io.key(h, VK_ADD)
        elif r < 0.95:
            what = "key -"; sc3io.key(h, VK_SUB)
        else:
            what = "minimap"; minimap_click(h)
        time.sleep(random.uniform(0.3, 1.0))
        if i % 5 == 0 and budget(h):
            what += " (budget dialog closed)"
        if edits and i % edits == 0:
            road_drag(h)
            what += " + road drag"
        st = check(pid, h)
        print(f"[{i}/{n}] {what} {st}", flush=True)
        if st != "PASS":
            return st, i
    return "PASS", n


def cam(pid, h, n):
    import frida
    import nramp_cam
    sc3pause.require_running(pid, "cam_soak")
    budget(h)
    s = frida.attach(pid)
    sc = s.create_script(nramp_cam.JS)
    sc.load()
    api = sc.exports_sync
    for btn in (ZOUT, ZIN, ZOUT, ZIN):
        sc3io.click(h, *btn)
        for _ in range(10):   # up to 5 s: a slow frame can hold the click back
            time.sleep(0.5)
            if api.hascam():
                break
        if api.hascam():
            break
    if not api.hascam():
        raise SystemExit("camera not captured")
    raw = os.environ.get("SC3_CAM_RAW") in ("1", "2")
    verdict, done, joberr = "PASS", n, 0
    try:
        for i in range(1, n + 1):
            if i % 5 == 0 and budget(h):
                print(f"[{i}/{n}] budget dialog closed", flush=True)
            st0 = api.hascam()
            zoom, rot = random.randint(0, 4), random.randint(0, 3)
            x, z = random.randint(20, 235), random.randint(20, 235)
            api.queue({"k": "rot", "v": rot, "f": 1, "x": x, "z": z})
            api.queue({"k": "zoom", "v": zoom, "f": 1, "x": x, "z": z})
            user32.PostMessageA(h, nramp_cam.WM_CAM, 0, 0)
            time.sleep(random.uniform(0.6, 1.2))
            st = check(pid, h)
            res, t0 = [], time.time()
            while st == "PASS" and len(res) < 2 and time.time() - t0 < 90:   # a slow frame can hold the jobs back
                res += api.take()
                if len(res) < 2:
                    time.sleep(0.5)
                    st = check(pid, h)
                    if time.time() - t0 > 20 and budget(h):   # the budget dialog came up and holds the jobs
                        print(f"[{i}/{n}] budget dialog closed (jobs were held)", flush=True)
            err = [r for r in res if "error" in r]
            if st == "PASS" and len(res) < 2 and not err:
                err = [{"error": "no result in 90 s", "got": res}]
            if st == "PASS" and (err or len(res) < 2):
                st = "JOBERR"
                joberr += 1
            print(f"[{i}/{n}] {('raw' + os.environ.get('SC3_CAM_RAW', '')) if raw else 'view'} z{st0['zoom']}r{st0['rot']} -> z{zoom}r{rot} at ({x},{z}) {st}"
                  + (f" {err}" if err else ""), flush=True)
            if st == "JOBERR" and raw:
                continue   # the raw arm runs on to a crash or a hang; the aborted calls are counted
            if st != "PASS":
                verdict, done = st, i
                break
    finally:
        try:
            s.detach()
        except Exception:
            pass
    print(f"aborted camera calls (JOBERR): {joberr}", flush=True)
    return verdict, done


def main(argv):
    what, n = argv[1], int(argv[2])
    edits = int(argv[argv.index("--edits") + 1]) if "--edits" in argv else 0
    pid = sc3io.game_pid()
    h = sc3io.game_hwnd(pid)
    t0 = time.time()
    if what == "buttons":
        verdict, done = buttons(pid, h, n, edits)
    elif what == "cam":
        verdict, done = cam(pid, h, n)
    else:
        raise SystemExit(__doc__)
    print(f"VERDICT {what}{(' raw' + os.environ.get('SC3_CAM_RAW', '')) if os.environ.get('SC3_CAM_RAW') in ('1', '2') and what == 'cam' else ''}: {verdict} "
          f"after {done} of {n} steps, {time.time() - t0:.0f} s, pid {pid}", flush=True)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
