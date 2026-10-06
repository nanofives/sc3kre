"""Where do the game's dialogs open, at the current window size? (verify/resize_dialogs)

Opens Reunirse (advisors category) and every item of the city-data category flyout, records each
new visible window (>= 120x80) with its parent and class, grabs the frame, then closes it with its X
(top-right of the window, measured on two dialogs: right-21, top+17). Input through sc3io.

Usage: python re/tools/dialog_survey.py --out verify/resize_dialogs/<state>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402
from uiwin_dump import JS  # noqa: E402

CAT = "SIMUI.DLL+0xa8f60"
SUB = "SIMUI.DLL+0xa917c"


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
    _, _, cw, ch = sc3io.client_rect_on_screen(h)

    def tree():
        return sc.exports_sync.d(4, False)["nodes"]

    def vis_big(nodes):
        return {n["p"]: n for n in nodes if n.get("vis") and n.get("abs")
                and n["abs"][2] - n["abs"][0] >= 120 and n["abs"][3] - n["abs"][1] >= 80
                and not (n["abs"][2] - n["abs"][0] >= cw - 4 and n["abs"][3] - n["abs"][1] >= ch - 4)}

    def cats():
        c = [n for n in tree() if n.get("cls") == CAT and n.get("vis")]
        c.sort(key=lambda n: n["abs"][1])
        return c

    def center(b):
        return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)

    rec = {"client": [cw, ch], "dialogs": []}
    print(f"client {cw}x{ch}")

    def open_and_record(label, clicks):
        base = vis_big(tree())
        for (x, y) in clicks:
            sc3io.click(h, x, y)
            time.sleep(1.0)
        sc3io.move(h, 5, ch // 2)
        time.sleep(0.6)
        nodes = tree()
        new = [n for p, n in vis_big(nodes).items() if p not in base]
        new.sort(key=lambda n: n["d"])
        if not new:
            print(f"  {label:22} no new window")
            rec["dialogs"].append({"label": label, "win": None})
            return
        w = new[0]
        par = next((n for n in nodes if n["p"] == w["parent"]), None)
        b = w["abs"]
        c = center(b)
        png = out / f"{label.replace(' ', '_')}.png"
        try:
            sc3io.grab_to(str(png), h)
        except sc3io.CaptureError as e:
            png = None
            print(f"  grab refused: {e}")
        print(f"  {label:22} {w['cls']} abs {b} center {c} (client center {(cw // 2, ch // 2)}) "
              f"depth {w['d']} parent {par['cls'] if par else 'ROOT'}")
        rec["dialogs"].append({"label": label, "win": w, "parent_cls": par["cls"] if par else "ROOT",
                               "center": c, "png": png.name if png else None})
        sc3io.click(h, b[2] - 21, b[1] + 17)               # its X
        time.sleep(1.0)
        if any(n["p"] == w["p"] and n.get("vis") for n in tree()):
            sc3io.click(h, b[2] - 30, b[3] - 24)           # no X (e.g. the budget): its check button
            time.sleep(1.0)
            if any(n["p"] == w["p"] and n.get("vis") for n in tree()):
                print(f"  !! {label}: could not close the window, stopping")
                raise SystemExit(3)

    cs = cats()
    if len(cs) < 9:
        print(f"STOP: {len(cs)} category buttons", file=sys.stderr)
        return 2
    adv, data = cs[6]["abs"], cs[7]["abs"]
    open_and_record("reunirse", [center(adv)])
    # city-data flyout items: open the category, read the visible sub-tool buttons, click item i
    sc3io.click(h, *center(data))
    time.sleep(1.0)
    subs = sorted([n for n in tree() if n.get("cls") == SUB and n.get("vis")], key=lambda n: n["abs"][1])
    sc3io.click(h, *center(data))                         # close the flyout again
    time.sleep(0.8)
    print(f"  city-data flyout: {len(subs)} items")
    for i, sb in enumerate(subs):
        open_and_record(f"citydata {i}", [center(data), center(sb["abs"])])
    (out / "dialogs.json").write_text(json.dumps(rec, indent=1))
    s.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
