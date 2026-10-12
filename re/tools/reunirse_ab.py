"""verify/reunirse driver: open Reunirse, drag it by the title bar, open the first advisor, close, reopen.
Records the dialog rect and the game's two stored positions after every step, grabs a frame per step.
Input through sc3io (posted messages, physical coords). Honours SC3_PID. Sends nothing else.

Usage: python re/tools/reunirse_ab.py --out <dir> [--dx -120 --dy 80] [--maximize]
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
from uiwin_dump import JS as TREE_JS  # noqa: E402

SLOT_JS = r"""
rpc.exports.slots = function(){
  var sui = Process.getModuleByName("SIMUI.DLL").base;
  var o = new NativeFunction(sui.add(0x8e998), 'pointer', [])();
  var f = new NativeFunction(o.readPointer().add(0x5c).readPointer(), 'pointer', ['pointer'], 'thiscall');
  var s = f(o);
  return {flag: s.readU8(), list: [s.add(4).readS32(), s.add(8).readS32()], det: [s.add(12).readS32(), s.add(16).readS32()]};
};
"""
DLG = "SIMUI.DLL+0xa4d64"
CAT = "SIMUI.DLL+0xa8f60"
ADV = "SIMUI.DLL+0xa3ad8"
TITLE = "SIMUI.DLL+0xa4b1c"


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dx", type=int, default=-120)
    ap.add_argument("--dy", type=int, default=80)
    ap.add_argument("--maximize", action="store_true")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    h = sc3io.game_hwnd()
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(TREE_JS + SLOT_JS)
    sc.load()
    rec = {"steps": []}

    if a.maximize and not sc3io.is_maximized(h):
        sc3io.maximize_without_focus(h)
        time.sleep(6)
    _, _, cw, ch = sc3io.client_rect_on_screen(h)
    rec["client"] = [cw, ch]
    print(f"client {cw}x{ch}")

    def tree():
        return sc.exports_sync.d(6, False)["nodes"]

    seen = set()

    def dialogs(nodes):
        return [n for n in nodes if n.get("cls") == DLG and n.get("vis") and n["abs"][2] - n["abs"][0] >= 300
                and n["abs"][3] - n["abs"][1] >= 300]

    def dialog(nodes):
        d = dialogs(nodes)
        new = [n for n in d if n["p"] not in seen]          # prefer a window that was not visible before
        return (new or d or [None])[0]

    def step(label):
        time.sleep(1.2)
        nodes = tree()
        d = dialog(nodes)
        sl = sc.exports_sync.slots()
        png = out / f"{label}.png"
        try:
            sc3io.grab_to(str(png), h)
            g = png.name
        except sc3io.CaptureError as e:
            g = f"grab refused: {str(e).splitlines()[0]}"
        alld = [(n["p"], n["abs"]) for n in dialogs(nodes)]
        seen.clear(); seen.update(p for p, _ in alld)
        r = {"step": label, "win": d["p"] if d else None, "rect": d["abs"] if d else None, "all": alld,
             "slots": sl, "grab": g}
        rec["steps"].append(r)
        print(f"{label:10} {r['win']} rect {r['rect']} visible {len(alld)} slots list {sl['list']} det {sl['det']} flag {sl['flag']}  {g}")
        return d, nodes

    def center(b):
        return ((b[0] + b[2]) // 2, (b[1] + b[3]) // 2)

    cats = sorted([n for n in tree() if n.get("cls") == CAT and n.get("vis")], key=lambda n: n["abs"][1])
    if len(cats) < 9:
        print(f"STOP: {len(cats)} category buttons")
        return 2
    meet = center(cats[6]["abs"])
    sc3io.click(h, *meet)
    d, nodes = step("1_open")
    if not d:
        print("STOP: no Reunirse dialog")
        return 2
    title = next(n for n in nodes if n.get("parent") == d["p"] and n.get("cls") == TITLE)["abs"]
    x0, y0 = title[0] + 100, (title[1] + title[3]) // 2
    sc3io.drag(h, x0, y0, x0 + a.dx, y0 + a.dy, button="left", steps=12)
    d, nodes = step("2_dragged")
    rec["P"] = d["abs"][:2]
    advs = sorted([n for n in nodes if n.get("parent") == d["p"] and n.get("cls") == ADV and n.get("vis")],
                  key=lambda n: n["abs"][0])
    sc3io.click(h, *center(advs[0]["abs"]))
    d, nodes = step("3_advisor")
    b = d["abs"]
    sc3io.click(h, b[2] - 21, b[1] + 17)                    # its X (dialog_survey.py geometry)
    time.sleep(1.0)
    if dialog(tree()):
        print("STOP: X did not close it")
        (out / "ab.json").write_text(json.dumps(rec, indent=1))
        return 3
    sc3io.click(h, *meet)
    d, nodes = step("4_reopen")
    if d:
        advs = sorted([n for n in nodes if n.get("parent") == d["p"] and n.get("cls") == ADV and n.get("vis")],
                      key=lambda n: n["abs"][0])
        if advs and d["abs"][2] - d["abs"][0] != 384:       # reopened on the list page: open an advisor again
            sc3io.click(h, *center(advs[-1]["abs"]))
            d, nodes = step("5_advisor2")
        b = d["abs"]
        sc3io.click(h, b[2] - 21, b[1] + 17)
        time.sleep(1.0)
    (out / "ab.json").write_text(json.dumps(rec, indent=1))
    s.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
