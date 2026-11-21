#!/usr/bin/env python3
r"""nopause_check.py - task nopause functional check in ONE Frida session (sc3perf's BUSY sampler faulted when a
probe's Frida agent unloaded during a month-pass stall, verify/nopause/RESULTS.md), against SC3_PID.

Steps: query window grabbed twice 20 s apart and closed; landmark list open, first item picked, placed on the map,
grabbed; Rewards list the same; mods page (Activar mods) opened and grabbed; every step logs the meter.
Usage: py -3.12 re/tools/nopause_check.py --out verify/nopause/check [--steps query,landmarks,rewards,modspage]
"""
import argparse
import json
import pathlib
import sys
import time

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import popslow_ab  # noqa: E402
import nopause_probe  # noqa: E402
import sc3io  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="verify/nopause/check")
    ap.add_argument("--steps", default="query,landmarks,rewards,modspage")
    ap.add_argument("--place", default="300,330", help="map point to place a list pick (client px)")
    a = ap.parse_args(argv)
    R = popslow_ab.Rig(a.out, 1.0)
    out = pathlib.Path(a.out)
    fn = nopause_probe._pop_fns(R)

    def grab(tag):
        sc3io.grab_to(str(out / (tag + ".png")), R.h)

    def note(tag, **kw):
        s = R.m.sample()
        kw.update({"tag": tag, "days": s and s["days"], "hold": s and s["hold"], "upause": s and s["upause"],
                   "dialogs": [d["abs"] for d in R.dialogs()]})
        print(json.dumps(kw), flush=True)

    try:
        for st in a.steps.split(","):
            if st == "query":
                fn["open"]("query"); note("query_open"); grab("query_a")
                r = R.m.window(20); note("query_20s", days_per_s=r["days_per_s"], held=r["held_pct"]); grab("query_b")
                fn["close"]("query"); note("query_closed")
            elif st in ("landmarks", "rewards"):
                fn["open"](st); note(st + "_open"); grab(st + "_list")
                ds = R.dialogs()
                if not ds:
                    note(st + "_no_dialog"); continue
                d = ds[-1]["abs"]
                nodes = R.vis()
                lst = [q for q in nodes if q["parent"] == ds[-1]["p"] and q.get("cls") == "SC3U.exe+0xd22a0"]
                if lst:   # first row of the list, then the dialog's OK (bottom right)
                    r0 = lst[0]["abs"]
                    R.click((r0[0] + 60, r0[1] + 9), wait=1.5)
                else:
                    note(st + "_no_list", kids=sorted({q.get("cls") for q in nodes if q["parent"] == ds[-1]["p"]}))
                grab(st + "_picked")
                R.click((d[2] - 36, d[3] - 22), wait=2.0)   # OK tick
                note(st + "_after_ok")
                px, py = (int(v) for v in a.place.split(","))
                sc3io.move(R.h, px, py, repeat=3); time.sleep(0.8); grab(st + "_cursor")
                sc3io.click(R.h, px, py); time.sleep(2.0)
                note(st + "_placed"); grab(st + "_placed")
                s = R.side(); R.click(R.ctr(s[1])); R.click(R.ctr(s[1]))   # leave the tool (zoning category twice)
                R.park()
            elif st == "modspage":
                fn["open"]("modspage"); note("modspage_open"); grab("modspage")
                ds = R.dialogs()
                if ds:   # "Activar mods..." top right of the mods page (MODTOGGLE): log the visible buttons
                    v = R.vis()
                    btn = [q["abs"] for q in v if q.get("cls") == popslow_ab.BTN and q["abs"][1] < ds[0]["abs"][1] + 60]
                    note("modspage_buttons", buttons=btn)
            time.sleep(1.0)
    finally:
        R.sess.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
