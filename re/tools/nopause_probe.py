#!/usr/bin/env python3
r"""nopause_probe.py - task nopause helper: drive one step against a running game (SC3_PID) and print what it saw.

Steps (one per call, the game keeps running between calls):
  state                      meter sample (days, hold, user pause) + sc3simrun NOPAUSE counters from its log
  open <pop>                 open a pop-up as popslow_ab does (budget, prefs, modspage, landmarks, rewards, query)
  close <pop>                close it again (popslow_ab close_pop)
  tree [--dlg]               dump the visible UI nodes (inside the top dialog with --dlg) to <out>/tree_<tag>.json
  click x y                  posted click at client px
  grab <tag>                 client grab (full size) to <out>/<tag>.png
  speed n                    set game speed 1..4
  watch secs                 meter window: days/s, held %
Usage: py -3.12 re/tools/nopause_probe.py --out verify/nopause/check <step> [args]
"""
import argparse
import json
import pathlib
import sys
import time

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import popslow_ab  # noqa: E402
import sc3io  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="verify/nopause/check")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--tag", default="t")
    ap.add_argument("--dlg", action="store_true")
    ap.add_argument("step")
    ap.add_argument("args", nargs="*")
    a = ap.parse_args(argv)
    R = popslow_ab.Rig(a.out, a.scale)
    out = pathlib.Path(a.out)
    try:
        if a.step == "state":
            print(json.dumps(R.m.sample()))
        elif a.step == "speed":
            R.sc.exports_sync.post(0xc2684065, int(a.args[0]))
            time.sleep(1.0)
            print(json.dumps(R.m.sample()))
        elif a.step == "watch":
            r = R.m.window(float(a.args[0]))
            print(json.dumps({k: r[k] for k in ("days", "days_per_s", "nominal_days_per_s", "held_pct", "uihold_pct")}))
        elif a.step == "grab":
            png = out / (a.args[0] + ".png")
            sc3io.grab_to(str(png), R.h)
            print(png)
        elif a.step == "click":
            R.click((int(a.args[0]), int(a.args[1])), wait=1.5)
            print(json.dumps({"dialogs": [d["abs"] for d in R.dialogs()]}))
        elif a.step == "tree":
            nodes = R.vis()
            if a.dlg:
                ds = R.dialogs(nodes)
                if ds:
                    top = ds[-1]["p"]
                    byp = {n["p"]: n for n in nodes}

                    def inside(n):
                        q = n
                        while q["parent"] in byp:
                            if q["parent"] == top:
                                return True
                            q = byp[q["parent"]]
                        return False
                    nodes = [n for n in nodes if inside(n)]
            p = out / f"tree_{a.tag}.json"
            p.write_text(json.dumps(nodes, indent=0))
            print(p, len(nodes))
        elif a.step in ("open", "close"):
            # reuse popslow_ab's open/close closures by running its main body pieces
            pop = a.args[0]
            fn = _pop_fns(R)
            fn[a.step](pop)
            print(json.dumps({"dialogs": [d["abs"] for d in R.dialogs()], "state": R.m.sample()}))
        else:
            print("unknown step", a.step)
            return 2
    finally:
        R.sess.detach()
    return 0


def _pop_fns(R):
    """the open_pop / close_pop bodies of popslow_ab.main, bound to R (copied: they are closures there)"""
    BTN = popslow_ab.BTN

    def open_pop(p):
        side = R.side()
        if p in ("landmarks", "rewards"):
            R.click(R.ctr(side[4]))
            f = R.flyout()
            i = 4 if p == "landmarks" else 5
            if len(f) > i:
                R.click(R.ctr(f[i]), wait=2.0)
            if not R.dialogs():
                f2 = R.flyout()
                if f2:
                    R.click(R.ctr(f2[0]), wait=2.0)
        elif p == "budget":
            R.click(R.ctr(side[7]))
            f = R.flyout()
            if len(f) >= 3:
                R.click(R.ctr(f[2]), wait=2.0)
        elif p in ("prefs", "modspage"):
            R.click(R.ctr(side[8]))
            f = R.flyout()
            if f:
                R.click(R.ctr(f[0]), wait=2.0)
            if p == "modspage":
                d = R.dialogs()
                if d:
                    r = d[0]["abs"]
                    R.click(R.dmap((r[0] + 80, r[1] + 448), r), wait=2.0)
        elif p == "query":
            qb = [b for b in R.vis() if b.get("cls") == BTN and b.get("parent") and
                  any(q["p"] == b["parent"] and q.get("cls") == "SIMUI.DLL+0xa40ec" for q in R.vis())]
            if qb:
                R.click(R.ctr(qb[0]["abs"]))
                R.click((380, 300), wait=2.0)
        R.onscreen()
        R.park()

    def close_pop(p):
        R.close_dialogs()
        if R.flyout():
            cat = {"budget": 7, "prefs": 8, "modspage": 8, "landmarks": 4, "rewards": 4}.get(p)
            if cat is not None:
                R.click(R.ctr(R.side()[cat]))
        if p == "query":
            s = R.side()
            R.click(R.ctr(s[1]))
            R.click(R.ctr(s[1]))
        R.park()
        time.sleep(1.0)

    return {"open": open_pop, "close": close_pop}


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
