"""verify/reunirse2 size rule: a spot noted at one client size is not reused at another (page centred), and the
next page after that follows the new page. Honours SC3_PID. Starts and ends at 800x600 (restored).

Steps: 800x600 open list, drag, X | maximize, reopen (expect centred in the map area), advisor (expect follows), X |
restore, reopen (expect centred in the map area), advisor (expect follows), X.

Usage: python re/tools/reunirse2_sizes.py --out <dir>
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
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

ADV = "SIMUI.DLL+0xa3ad8"
CAT = "SIMUI.DLL+0xa8f60"


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    h = sc3io.game_hwnd()
    quiet = open(out / "state.txt", "a")
    rec = []

    def st():
        so = sys.stdout; sys.stdout = quiet
        try:
            return rp.state()
        finally:
            sys.stdout = so

    def dlg(s):
        ds = [d for d in s["dialogs"] if d["abs"][2] - d["abs"][0] >= 300 and d["abs"][3] - d["abs"][1] >= 300]
        return ds[0] if ds else None

    def meet_btn():
        import frida
        from uiwin_dump import JS as TREE_JS
        sc3pause.require_running(sc3io.game_pid(), "reunirse2_sizes")
        fs = frida.attach(sc3io.game_pid()); sc = fs.create_script(TREE_JS); sc.load()
        cats = sorted([n for n in sc.exports_sync.d(6, False)["nodes"] if n.get("cls") == CAT and n.get("vis")],
                      key=lambda n: n["abs"][1])
        fs.detach()
        b = cats[6]["abs"]
        return (b[0] + b[2]) // 2, (b[1] + b[3]) // 2

    def snap(label, expect=None, how=""):
        time.sleep(1.3)
        s = st(); d = dlg(s)
        png = out / f"{label}.png"
        try:
            sc3io.grab_to(str(png), h); g = png.name
        except sc3io.CaptureError as e:
            g = "grab refused: " + str(e).splitlines()[0]
        r = {"step": label, "client": s["client"], "page": d["ids"][0][1] if d else None,
             "rect": d["abs"] if d else None, "expect": expect, "how": how, "grab": g}
        if expect and d:
            r["verdict"] = "PASS" if d["abs"][:2] == expect else "FAIL"
        rec.append(r)
        print(f"{label:14} client {s['client']} page {r['page']} rect {r['rect']} expect {how} {expect} {r.get('verdict', '')}  {g[:40]}")
        return d, s

    def close(d):
        b = d["abs"]; sc3io.click(h, b[2] - 21, b[1] + 17); time.sleep(1.2)

    def reopen(m):
        sc3io.click(h, *m); time.sleep(1.2)
        if not dlg(st()):
            sc3io.click(h, *m)

    def advisor(d):
        advs = sorted([k for k in d["kids"] if k["cls"] == ADV], key=lambda k: k["abs"][0])
        k = advs[2]["abs"]; sc3io.click(h, (k[0] + k[2]) // 2, (k[1] + k[3]) // 2)

    def centre(s, d):
        # the poll's map-area centre is not readable from here; report the client centre for reference only
        cw, ch = s["client"]; w = d["abs"][2] - d["abs"][0]; hh = d["abs"][3] - d["abs"][1]
        return [(cw - w) // 2, (ch - hh) // 2]

    if sc3io.is_maximized(h):
        sc3io.restore_without_focus(h); time.sleep(6)
    m = meet_btn()
    reopen(m)
    d, s = snap("01_open_800")
    x0, y0 = d["abs"][0] + 120, d["abs"][1] + 17
    sc3io.drag(h, x0, y0, x0 - 90, y0 + 70, button="left", steps=12); time.sleep(1.2)
    d, s = snap("02_dragged_800")
    close(d)
    sc3io.maximize_without_focus(h); time.sleep(6)
    m = meet_btn()
    reopen(m)
    d, s = snap("03_reopen_max", how="centred, not", expect=None)
    rec[-1]["not_at"] = rec[1]["rect"][:2]
    rec[-1]["verdict"] = "PASS" if d["abs"][:2] != rec[1]["rect"][:2] else "FAIL"
    print(f"   not at the 800x600 spot {rec[1]['rect'][:2]}: {rec[-1]['verdict']} (client centre {centre(s, d)})")
    tl = d["abs"][:2]
    advisor(d)
    d, s = snap("04_advisor_max", expect=tl, how="follows")
    close(d)
    sc3io.restore_without_focus(h); time.sleep(6)
    m = meet_btn()
    reopen(m)
    d, s = snap("05_reopen_800")
    rec[-1]["not_at"] = tl
    rec[-1]["verdict"] = "PASS" if d["abs"][:2] != tl else "FAIL"
    print(f"   not at the maximized spot {tl}: {rec[-1]['verdict']} (client centre {centre(s, d)})")
    tl = d["abs"][:2]
    advisor(d)
    d, s = snap("06_advisor_800", expect=tl, how="follows")
    close(d)
    (out / "sizes.json").write_text(json.dumps(rec, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
