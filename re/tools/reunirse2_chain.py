"""verify/reunirse2 driver: walk the Reunirse page chain, dragging the open page before every switch, and record
where each next page opens. Honours SC3_PID. Input via sc3io (posted, physical = game client coords here).

Steps: open list, drag, advisor 1, drag, topic 1, drag, back arrow (-> advisor), drag, topic 2, X close, reopen,
advisor (if the list came back), X close. After each switch: rect of the new page, slots, one grab.
Expectation per switch: top-left == top-left of the page before it (both are 383/384 x 354), clamped on screen.

Usage: python re/tools/reunirse2_chain.py --out <dir> [--maximize] [--scale 1]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402
import reunirse2_probe as rp  # noqa: E402

CAT = "SIMUI.DLL+0xa8f60"
ADV = "SIMUI.DLL+0xa3ad8"


def page_id(d):
    return d["ids"][0][1] if d and d["ids"] else None


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--maximize", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    h = sc3io.game_hwnd()
    if a.maximize and not sc3io.is_maximized(h):
        sc3io.maximize_without_focus(h); time.sleep(6)
    if a.restore and sc3io.is_maximized(h):
        sc3io.restore_without_focus(h); time.sleep(6)
    rec = {"steps": []}
    quiet = open(out / "state.txt", "a")

    def st():
        so = sys.stdout; sys.stdout = quiet
        try:
            return rp.state()
        finally:
            sys.stdout = so

    def dlg(s):
        ds = [d for d in s["dialogs"] if d["abs"][2] - d["abs"][0] >= 300 and d["abs"][3] - d["abs"][1] >= 300]
        return ds[0] if ds else None

    prev = {"tl": None}

    def step(label, expect_follow=True):
        time.sleep(1.3)
        s = st()
        d = dlg(s)
        cw, ch = s["client"]
        png = out / f"{label}.png"
        try:
            sc3io.grab_to(str(png), h); g = png.name
        except sc3io.CaptureError as e:
            g = "grab refused: " + str(e).splitlines()[0]
        r = {"step": label, "page": page_id(d), "win": d["p"] if d else None, "rect": d["abs"] if d else None,
             "slot": s["slot"], "client": s["client"], "grab": g}
        if expect_follow and prev["tl"] and d:
            w, hh = d["abs"][2] - d["abs"][0], d["abs"][3] - d["abs"][1]
            ex = min(max(prev["tl"][0], 0), cw - w); ey = min(max(prev["tl"][1], 0), ch - hh)
            r["expect"] = [ex, ey]
            r["verdict"] = "FOLLOWS" if d["abs"][:2] == [ex, ey] else "JUMPS"
        rec["steps"].append(r)
        print(f"{label:12} page {r['page']} rect {r['rect']} expect {r.get('expect')} {r.get('verdict', '')}  {g}")
        return d, s

    def drag_title(d, dx, dy):
        x0, y0 = d["abs"][0] + 120, d["abs"][1] + 17
        sc3io.drag(h, x0, y0, x0 + dx, y0 + dy, button="left", steps=12)
        time.sleep(1.2)
        s = st(); d2 = dlg(s)
        prev["tl"] = d2["abs"][:2]
        print(f"   dragged to {d2['abs'][:2]}")
        rec["steps"].append({"step": "drag", "rect": d2["abs"]})
        return d2

    def kid(d, pid):
        return next((k for k in d["kids"] if k["ids"] and k["ids"][0][1] == pid), None)

    def topic(d, row):
        lst = kid(d, "62be5df5")["abs"]
        sc3io_dbl(lst[0] + 60, lst[1] + 7 + 13 * row)

    def sc3io_dbl(x, y):
        lp = sc3io._lp(x, y)
        sc3io._post(h, 0x200, 0, lp); time.sleep(0.05)
        for _ in range(2):
            sc3io._post(h, 0x201, 1, lp); time.sleep(0.03); sc3io._post(h, 0x202, 0, lp); time.sleep(0.03)

    s = st()
    cw, ch = s["client"]
    rec["client"] = s["client"]
    import frida  # category buttons: same class lookup as reunirse_ab.py
    from uiwin_dump import JS as TREE_JS
    fs = frida.attach(sc3io.game_pid()); sc = fs.create_script(TREE_JS); sc.load()
    cats = sorted([n for n in sc.exports_sync.d(6, False)["nodes"] if n.get("cls") == CAT and n.get("vis")],
                  key=lambda n: n["abs"][1])
    fs.detach()
    meet = ((cats[6]["abs"][0] + cats[6]["abs"][2]) // 2, (cats[6]["abs"][1] + cats[6]["abs"][3]) // 2)
    sc3io.click(h, *meet)
    d, s = step("01_list", expect_follow=False)
    big = cw > 1000
    d = drag_title(d, -100 if not big else 300, 60 if not big else 200)
    advs = sorted([k for k in d["kids"] if k["cls"] == ADV], key=lambda k: k["abs"][0])
    sc3io.click(h, (advs[0]["abs"][0] + advs[0]["abs"][2]) // 2, (advs[0]["abs"][1] + advs[0]["abs"][3]) // 2)
    d, s = step("02_advisor")
    d = drag_title(d, 80, -40)
    topic(d, 0)
    d, s = step("03_topic")
    d = drag_title(d, 120, 80)
    b = d["abs"]; sc3io.click(h, b[2] - 46, b[1] + 17)          # back arrow
    d, s = step("04_back_advisor")
    d = drag_title(d, -150, -30)
    topic(d, 1)
    d, s = step("05_topic2")
    b = d["abs"]; sc3io.click(h, b[2] - 21, b[1] + 17)          # X
    time.sleep(1.2)
    sc3io.click(h, *meet)
    time.sleep(1.2)
    if not dlg(st()):
        sc3io.click(h, *meet)
    d, s = step("06_reopen")
    if d and page_id(d) == "62be5dd2":
        advs = sorted([k for k in d["kids"] if k["cls"] == ADV], key=lambda k: k["abs"][0])
        sc3io.click(h, (advs[-1]["abs"][0] + advs[-1]["abs"][2]) // 2, (advs[-1]["abs"][1] + advs[-1]["abs"][3]) // 2)
        d, s = step("07_advisor_last")
    if d:
        b = d["abs"]; sc3io.click(h, b[2] - 21, b[1] + 17)
    (out / "chain.json").write_text(json.dumps(rec, indent=1))
    n = sum(1 for r in rec["steps"] if r.get("verdict") == "FOLLOWS")
    m = sum(1 for r in rec["steps"] if r.get("verdict"))
    print(f"FOLLOWS {n}/{m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
