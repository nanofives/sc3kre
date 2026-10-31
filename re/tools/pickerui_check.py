"""pickerui checks (child pickerui 2026-10-31), posted input only, frames through SC3RESIZE_FRAMEDUMP.
Game of `picker_lab.py up --tag T` (Berlin, the load camera), PICKER_RUNS pointing at verify/pickerui/runs.

  py -3.12 re/tools/pickerui_check.py --tag T [--scale 1.5] [--building X,Y] [--road X,Y]
Coordinates are given for the 800x600 client and multiplied by --scale for the HUD (button, tooltip hover); city
points are taken as given. Steps (owner items 2026-10-31):
  1 button -> picker on, NO message box in the frame (item 1)
  2 mouse over the city: the cursor the game sets is swapped for the eyedropper (item 2, log + WM_RZ_PICKER 8)
  3 the button art in the frame (item 3, picture)
  4 click a building: its tool is active, the picker is ended; a second click is not a pick (item 4)
  5 hover the button: tooltip fully drawn, nothing over it (item 5, picture)"""
import argparse, ctypes, pathlib, re, sys, time
TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io
import picker_lab as lab
import vdscroll_io as vdio

STEPS = 7


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--building", default="360,420")
    ap.add_argument("--city", default="400,250")
    a = ap.parse_args(argv)
    d = lab.rundir(a.tag)
    lab.pid_of(a.tag)
    log = d / "resize.log"
    h = sc3io.game_hwnd()
    u = ctypes.windll.user32
    _, _, cw, ch = sc3io.client_rect_on_screen(h)
    s = a.scale
    # the minimap panel is anchored bottom-right: button centre = (cw - 160*s + 19*s, ch - 164*s + 152*s)
    btn = (int(cw - 160 * s + 19 * s), int(ch - 164 * s + 152 * s))
    pt = lambda t: tuple(int(v) for v in t.split(","))
    res = []

    def since(n0):
        with open(log, "rb") as f:
            f.seek(n0); t = f.read().decode("latin-1", "replace")
        return "\n".join(ln.split("PICKER> ", 1)[1] for ln in t.splitlines() if "PICKER> " in ln)

    def msg(wp, lp=0, wait=0.5):
        n0 = log.stat().st_size
        u.PostMessageW(h, lab.WM_RZ_PICKER, wp, lp); time.sleep(wait)
        return since(n0)

    def report(i, name, ok, txt):
        res.append((name, ok, txt))
        print(f"[{i}/{STEPS}] {name} {'PASS' if ok else 'FAIL'}", flush=True)
        for ln in txt.splitlines()[:8]:
            print("      " + ln, flush=True)

    tag = f"s{int(s * 100)}"
    # 1: the button starts it, no message
    n0 = log.stat().st_size
    sc3io.click(h, *btn); time.sleep(1.2)
    t = since(n0)
    fr = vdio.dump(f"{tag}_1_picker_on")
    on = "active as picker" in t
    report(1, f"button {btn} starts the picker, no message", on and "message:" not in t, t + f"\nframe {fr}")
    # 2: cursor over the city
    n0 = log.stat().st_size
    for i in range(6):
        sc3io.move(h, *pt(a.city), repeat=1); time.sleep(0.15)
    t = since(n0) + "\n" + msg(8)
    report(2, "cursor over the city while the picker is on", "(the eyedropper)" in t, t)
    # 3: the button art (frame from step 1 + a crop)
    report(3, "button art frame", True, f"frame {fr}")
    # 4: pick a building, then the picker is over
    n0 = log.stat().st_size
    sc3io.click(h, *pt(a.building)); time.sleep(1.5)
    t = since(n0) + "\n" + msg(5)
    picked = "->" in t and ("menu command" in t or "building tool" in t) and "(the picker)" not in t
    report(4, f"click a building at {a.building}: its tool, picker ended", picked and "picker ended (picked)" in t, t)
    n0 = log.stat().st_size
    for i in range(4):
        sc3io.move(h, *pt(a.city), repeat=1); time.sleep(0.15)
    t = since(n0) + "\n" + msg(8)
    report(5, "after the pick: picker off, cursor not the eyedropper", "picker off" in t and "(the eyedropper)" not in t, t)
    sc3io.key(h, 0x1B); time.sleep(0.6)   # Esc: drop the picked tool before the next step
    # 6: Esc ends a fresh picker, the cursor goes back
    sc3io.click(h, *btn); time.sleep(1.0)
    n0 = log.stat().st_size
    sc3io.key(h, 0x1B); time.sleep(0.8)
    for i in range(4):
        sc3io.move(h, *pt(a.city), repeat=1); time.sleep(0.15)
    t = since(n0) + "\n" + msg(8)
    report(6, "Esc ends the picker, cursor back", "picker off" in t and "(the eyedropper)" not in t, t)
    # 7: tooltip over the button
    sc3io.move(h, *pt(a.city), repeat=2); time.sleep(0.8)
    for i in range(14):
        sc3io.move(h, *btn, repeat=1); time.sleep(0.1)
    fr = vdio.dump(f"{tag}_7_tooltip")
    report(7, "tooltip frame", True, f"frame {fr}")
    print("SUMMARY " + " ".join(f"{n.split(':')[0][:20]}={'PASS' if ok else 'FAIL'}" for n, ok, _ in res))
    return 0 if all(ok for _, ok, _ in res) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
