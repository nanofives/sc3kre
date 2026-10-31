"""picker screen checks (child picker 2026-10-30): the paths a player uses, driven with posted input only.
Game of `picker_lab.py up --tag T` (Berlin, 800x600 client, the load camera). Frames into verify/picker/runs/T/fd.

  py -3.12 re/tools/picker_screen.py --tag T
Steps: minimap button -> picker on (frame with the message) -> click a building -> its tool; button -> click a road;
button -> click empty land -> message, picker still on (frame); Esc -> off (a click opens nothing); button ->
right-click -> off; stock "?" -> a click opens the query dialog (frame); Ctrl+F through the real WM_KEYDOWN path with
GetKeyState(VK_CONTROL) faked for 2 s by Frida (reference-posted-modifier-keys) -> picker on."""
import argparse, ctypes, pathlib, re, sys, time
TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io
import picker_lab as lab
import vdscroll_io as vdio

BTN = (659, 588)        # the picker button, minimap panel (640,436) + (10,142) + half its 18x20
QUERY = (566, 572)      # the game's "?" button
STEPS = 10


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--building", default="360,420")
    ap.add_argument("--road", default="480,330")
    ap.add_argument("--empty", default="200,30")
    a = ap.parse_args(argv)
    d = lab.rundir(a.tag)
    pid = lab.pid_of(a.tag)
    log = d / "resize.log"
    h = sc3io.game_hwnd()
    u = ctypes.windll.user32
    pt = lambda s: tuple(int(v) for v in s.split(","))

    def since(n0):
        with open(log, "rb") as f:
            f.seek(n0); t = f.read().decode("latin-1", "replace")
        return "\n".join(ln.split("PICKER> ", 1)[1] for ln in t.splitlines() if "PICKER> " in ln)

    def cur():
        n0 = log.stat().st_size
        u.PostMessageW(h, lab.WM_RZ_PICKER, 5, 0); time.sleep(0.5)
        m = re.search(r"current tool \S+ vtable (\S+)", since(n0))
        return m.group(1) if m else "?"

    def esc():
        u.PostMessageW(h, 0x0100, 0x1B, 0x00010001); u.PostMessageW(h, 0x0101, 0x1B, 0xC0010001); time.sleep(0.6)

    def report(i, name, ok, txt):
        print(f"[{i}/{STEPS}] {name} {'PASS' if ok else 'FAIL'}", flush=True)
        for ln in txt.splitlines():
            print("      " + ln, flush=True)

    esc()
    # 1 button -> on, message in the frame
    n0 = log.stat().st_size
    sc3io.click(h, *BTN); time.sleep(0.5)
    vdio.dump("s1_picker_on")
    t = since(n0); c = cur()
    report(1, "minimap button starts the picker", "active as picker" in t and c.endswith("SIMGEOM.DLL+0x2984C"), t + "\ncurrent " + c)
    # 2 click a building -> its tool
    n0 = log.stat().st_size
    sc3io.click(h, *pt(a.building)); time.sleep(1.0)
    c = cur(); t = since(n0)
    vdio.dump("s2_building_picked")
    report(2, "click a building", ("posted" in t or ": active" in t) and not c.endswith("0x2984C") and c != "none+0x0", t + "\ncurrent " + c)
    esc()
    # 3 button -> click a road
    sc3io.click(h, *BTN); time.sleep(0.8)
    n0 = log.stat().st_size
    sc3io.click(h, *pt(a.road)); time.sleep(1.0)
    c = cur(); t = since(n0)
    vdio.dump("s3_road_picked")
    report(3, "click a road", "0x10004001 posted" in t and c.startswith("SIMNTWRK.DLL+0x2BEF8"), t + "\ncurrent " + c)
    esc()
    # 4 button -> empty land -> message, picker stays on
    sc3io.click(h, *BTN); time.sleep(0.8)
    n0 = log.stat().st_size
    sc3io.click(h, *pt(a.empty)); time.sleep(0.4)
    vdio.dump("s4_nothing_message")
    time.sleep(0.4)
    c = cur(); t = since(n0)
    report(4, "click with no tool: message, picker stays on", "message:" in t and c.endswith("SIMGEOM.DLL+0x2984C"), t + "\ncurrent " + c)
    # 5 a zoned empty lot: zone the empty spot Res Low (menu command + a drag), then pick it
    ex, ey = pt(a.empty)
    u.PostMessageW(h, lab.WM_RZ_PICKER, 6, 0x10003101); time.sleep(0.8)
    sc3io.drag(h, ex - 12, ey - 6, ex + 12, ey + 6, button="left"); time.sleep(1.0)
    esc()
    sc3io.click(h, *BTN); time.sleep(0.8)
    n0 = log.stat().st_size
    sc3io.click(h, ex, ey); time.sleep(1.0)
    c = cur(); t = since(n0)
    vdio.dump("s5_zoned_lot_picked")
    report(5, "zoned empty lot", "zoned lot" in t and "0x10003101 posted" in t and c.startswith("SIMRCI.DLL+0x4C06C"), t + "\ncurrent " + c)
    esc()
    # 6 Esc -> off, a click does nothing
    sc3io.click(h, *BTN); time.sleep(0.8)
    esc()
    n0 = log.stat().st_size
    sc3io.click(h, *pt(a.building)); time.sleep(1.0)
    c = cur(); t = since(n0)
    report(6, "Esc ends it (a click after it picks nothing)", "click at" not in t and c == "none+0x0", t + "\ncurrent " + c)
    # 7 button -> right-click -> off
    sc3io.click(h, *BTN); time.sleep(0.8)
    n0 = log.stat().st_size
    sc3io.click(h, 400, 300, button="right"); time.sleep(0.8)
    c = cur(); t = since(n0)
    report(7, "right-click ends it", "right-click: cancelled" in t and c == "none+0x0", t + "\ncurrent " + c)
    # 8 stock "?" still opens the dialog, no pick
    n0 = log.stat().st_size
    sc3io.click(h, *QUERY); time.sleep(0.8)
    sc3io.click(h, *pt(a.building)); time.sleep(1.5)
    vdio.dump("s8_stock_query")
    t = since(n0)
    report(8, "stock \"?\" untouched (dialog frame, no pick)", "click at" not in t, t or "(no PICKER line)")
    esc(); esc()
    # 9 the Ctrl+F handler path (test message 2 = the handler the key calls)
    n0 = log.stat().st_size
    u.PostMessageW(h, lab.WM_RZ_PICKER, 2, 0); time.sleep(0.6)
    c = cur(); t = since(n0)
    report(9, "Ctrl+F handler", "Ctrl+F: query tool" in t and c.endswith("0x2984C"), t + "\ncurrent " + c)
    esc()
    # 10 Ctrl+F through WM_KEYDOWN, GetKeyState(VK_CONTROL) faked by Frida for 2 s
    import frida, sc3pause
    paused, det = sc3pause.pause_state(pid)
    if paused:
        report(10, "Ctrl+F posted key", False, "game paused (%s): not attaching" % det); return 1
    s = frida.attach(pid)
    sc = s.create_script("""
      var f = Process.getModuleByName('USER32.dll').getExportByName('GetKeyState');
      Interceptor.attach(f, { onEnter: function (a) { this.vk = a[0].toInt32(); },
                               onLeave: function (r) { if (this.vk === 0x11) r.replace(ptr(0xffff8000)); } });""")
    sc.load()
    n0 = log.stat().st_size
    u.PostMessageW(h, 0x0100, ord("F"), 0x00210001); u.PostMessageW(h, 0x0101, ord("F"), 0xC0210001)
    time.sleep(1.5)
    s.detach()
    time.sleep(0.3)
    c = cur(); t = since(n0)
    report(10, "Ctrl+F as a posted key (Ctrl faked)", "Ctrl+F: query tool" in t and c.endswith("0x2984C"), t + "\ncurrent " + c)
    esc()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
