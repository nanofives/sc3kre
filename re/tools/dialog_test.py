"""Pre-registered checks for dialog placement, RCI-under-dialog and resize (verify/resize_dialogs/PRE.md).

Run with the game loaded, on a 100% display. Input via sc3io, geometry read in-process.
Usage: python re/tools/dialog_test.py --out verify/resize_dialogs/T
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import frida
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402
from uiwin_dump import JS  # noqa: E402

CAT, SUB, DLG = "SIMUI.DLL+0xa8f60", "SIMUI.DLL+0xa917c", "SIMUI.DLL+0xa4d64"


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    h = sc3io.game_hwnd()
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()
    rec = {}

    def tree():
        return sc.exports_sync.d(4, False)["nodes"]

    def client():
        _, _, cw, ch = sc3io.client_rect_on_screen(h)
        return cw, ch

    def dialogs():
        return {n["p"]: n for n in tree() if n.get("cls") == DLG and n.get("vis") and n.get("abs")
                and n["abs"][2] - n["abs"][0] >= 120 and n["abs"][3] - n["abs"][1] >= 80}

    def map_area():
        nodes = tree()
        cw, ch = client()
        ax, ay = cw, ch
        for n in nodes:
            if n.get("cls") == "SIMUI.DLL+0xa9834" and n.get("vis") and n["abs"][0] > cw // 2:
                ax = n["abs"][0]
            if n.get("cls") == "SIMUI.DLL+0xa40ec" and n.get("vis") and n["abs"][1] > ch // 2:
                ay = n["abs"][1]
        return ax, ay

    def cats():
        c = sorted([n for n in tree() if n.get("cls") == CAT and n.get("vis")], key=lambda n: n["abs"][1])
        return c

    def ctr(b):
        return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)

    def open_dialog(clicks):
        base = set(dialogs())
        for (x, y) in clicks:
            sc3io.click(h, x, y)
            time.sleep(1.0)
        time.sleep(0.5)                                     # let the 100 ms poll place it
        new = [n for p, n in dialogs().items() if p not in base]
        return new[0] if new else None

    def close(w):
        b = next((n["abs"] for p, n in dialogs().items() if p == w["p"]), w["abs"])
        sc3io.click(h, b[2] - 21, b[1] + 17)
        time.sleep(1.0)
        if w["p"] in dialogs():
            sc3io.click(h, b[2] - 30, b[3] - 24)
            time.sleep(1.0)
        return w["p"] not in dialogs()

    def rect_of(w):
        d = dialogs()
        return d[w["p"]]["abs"] if w["p"] in d else None

    def centered(b):
        ax, ay = map_area()
        cx, cy = ctr(b)
        w, hh = b[2] - b[0], b[3] - b[1]
        ex, ey = max(0, (ax - w) // 2) + w // 2, max(0, (ay - hh) // 2) + hh // 2
        return abs(cx - ex) <= 2 and abs(cy - ey) <= 2, (cx, cy), (ex, ey)

    def resize(w, hh):
        sc3io.restore_without_focus(h)
        time.sleep(1.5)
        sc3io.resize_client(h, w, hh)
        time.sleep(4)

    def maximize():
        sc3io.maximize_without_focus(h)
        time.sleep(6)

    def adv_and_data():
        c = cats()
        return ctr(c[6]["abs"]), ctr(c[7]["abs"])

    # ---- 1. maximized: open each, centered?
    maximize()
    adv, data = adv_and_data()
    sc3io.click(h, *data)
    time.sleep(1.0)
    subs = sorted([n for n in tree() if n.get("cls") == SUB and n.get("vis")], key=lambda n: n["abs"][1])
    sc3io.click(h, *data)
    time.sleep(0.8)
    r1 = []
    for label, clicks in [("reunirse", [adv]), ("budget", [data, ctr(subs[2]["abs"])]),
                          ("snapshots", [data, ctr(subs[0]["abs"])]), ("citydata4", [data, ctr(subs[4]["abs"])]),
                          ("citydata6", [data, ctr(subs[6]["abs"])])]:
        w = open_dialog(clicks)
        if not w:
            r1.append({"label": label, "ok": None})
            print(f"1 {label:10} NO WINDOW")
            continue
        b = rect_of(w)
        ok, got, exp = centered(b)
        sc3io.grab_to(str(out / f"1_{label}.png"), h)
        print(f"1 {label:10} {b} center {got} expected {exp} -> {'PASS' if ok else 'FAIL'}")
        r1.append({"label": label, "rect": b, "ok": ok})
        close(w)
    rec["1"] = r1

    # ---- 2. budget open across resizes
    adv, data = adv_and_data()
    w = open_dialog([data, ctr(subs[2]["abs"])])
    r2 = []
    for st in ("1280x700", "max"):
        if st == "max":
            maximize()
        else:
            resize(1280, 700)
        time.sleep(0.5)
        b = rect_of(w) if w else None
        ok = centered(b)[0] if b else None
        print(f"2 budget at {st:8} {b} -> {'PASS' if ok else 'FAIL'}")
        r2.append({"state": st, "rect": b, "ok": ok})
    if w:
        close(w)
    rec["2"] = r2

    # ---- 3. dragged dialog only clamps
    adv, data = adv_and_data()
    w = open_dialog([adv])
    b0 = rect_of(w)
    sc3io.drag(h, (b0[0] + b0[2]) // 2, b0[1] + 15, (b0[0] + b0[2]) // 2 - 200, b0[1] + 115, button="left")
    time.sleep(0.8)
    b1 = rect_of(w)
    resize(1280, 700)
    time.sleep(0.5)
    b2 = rect_of(w)
    cw, ch = client()
    exp = list(b1)
    dx = min(0, cw - b1[2]) if b1[2] > cw else 0
    dy = min(0, ch - b1[3]) if b1[3] > ch else 0
    exp = [b1[0] + dx, b1[1] + dy, b1[2] + dx, b1[3] + dy]
    ok3 = (b2 == exp)
    print(f"3 reunirse dragged {b0} -> {b1}; after resize {b2}, expected {exp} -> {'PASS' if ok3 else 'FAIL'}")
    rec["3"] = {"opened": b0, "dragged": b1, "after": b2, "expected": exp, "ok": ok3}
    close(w)

    # ---- 4. dialog over the RCI
    maximize()
    rci = next((n["abs"] for n in tree() if n.get("cls") == "SIMUI.DLL+0xab274" and n.get("vis")), None)
    adv, data = adv_and_data()
    before = np.asarray(sc3io.grab(h).img.convert("RGB")).astype(int)
    w = open_dialog([adv])
    b0 = rect_of(w)
    tx, ty = rci[0] - 60, rci[1] - 120                      # dialog top-left so it covers the RCI
    sc3io.drag(h, (b0[0] + b0[2]) // 2, b0[1] + 15, (b0[0] + b0[2]) // 2 + (tx - b0[0]), b0[1] + 15 + (ty - b0[1]),
               button="left", steps=20)
    time.sleep(1.0)
    b1 = rect_of(w)
    img = sc3io.grab(h).img
    img.save(out / "4_rci_covered.png")
    after = np.asarray(img.convert("RGB")).astype(int)
    covered = b1 and b1[0] <= rci[0] and b1[1] <= rci[1] and b1[2] >= rci[2] and b1[3] >= rci[3]
    x0, y0, x1, y1 = rci
    diff = float(np.abs(after[y0:y1, x0:x1] - before[y0:y1, x0:x1]).mean())
    print(f"4 RCI {rci}, dialog {b1}, covers={covered}, mean pixel change over the RCI = {diff:.1f} "
          f"-> {'PASS' if covered and diff > 20 else 'CHECK IMAGE'}")
    rec["4"] = {"rci": rci, "dialog": b1, "covered": bool(covered), "diff": diff}
    close(w)

    # ---- 5. 800x600
    resize(800, 600)
    time.sleep(1)
    adv, data = adv_and_data()
    w = open_dialog([adv])
    b = rect_of(w)
    ok5a = (b == [8, 8, 391, 362])
    print(f"5 reunirse at 800x600 {b} -> {'PASS' if ok5a else 'FAIL'}")
    close(w)
    sc3io.click(h, *data)
    time.sleep(1.0)
    subs = sorted([n for n in tree() if n.get("cls") == SUB and n.get("vis")], key=lambda n: n["abs"][1])
    sc3io.click(h, *data)
    time.sleep(0.8)
    w = open_dialog([data, ctr(subs[0]["abs"])])
    b = rect_of(w)
    ok5b = bool(b) and b[0] >= 0 and b[1] >= 0 and b[2] <= 800 and b[3] <= 600
    print(f"5 snapshots at 800x600 {b} -> {'PASS' if ok5b else 'FAIL'}")
    if w:
        sc3io.grab_to(str(out / "5_snapshots_native.png"), h)
        close(w)
    rec["5"] = {"reunirse_ok": ok5a, "snapshots_ok": ok5b}
    (out / "dialog_test.json").write_text(json.dumps(rec, indent=1))
    s.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
