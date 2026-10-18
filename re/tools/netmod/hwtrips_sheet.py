#!/usr/bin/env python3
"""hwtrips_sheet.py - owner sheet for the hwtrips lever test (2026-10-18).

Reads verify/hwtrips/data/sac_{rampd120,rampd164,hwcost0}.json (hwtrips_probe.py run output) and draws one dot per
window: share of arrived trips whose final path holds a highway node, stock (A) vs lever (B), one panel per lever.
  py -3.12 hwtrips_sheet.py --data <verify/hwtrips/data> --out <png>
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COL = {"A": "#2a78d6", "B": "#eb6834"}
MARK = {"A": "o", "B": "s"}
RUNS = [("sac_hwcost0.json", "Highway trip cost 2 -> 0\n(STTraffic.ini TripCellCostBaseHighway)"),
        ("sac_rampd120.json", "Ramp cells get road traffic 120\n(they always hold 0 in stock)"),
        ("sac_rampd164.json", "Ramp cells get road traffic 164\n(a ramp always wins when offered)")]
RUNS_PATCH = [("sac_rampd164.json", "Test: ramp cells get road traffic 164\n(written by the probe, upper-bound lever)"),
              ("sac_rf.json", "The mod: sc3netmod RAMPFIRST\n(road and bus steps take an offered ramp first)")]
NOTES_PATCH = [
    "Ramp-first patch (owner picked option B of the ramp patch, rank ramps first, 2026-10-18), Sacramento, one game,",
    "   block switched off (A) and on (B) live, ABBA, about 93 sim days per window:",
    "1. When a road or bus step has an unused on-ramp beside it, the other road cells are hidden for that one step,",
    "   so the trip takes the ramp. If the search comes back to that cell, the stock busiest-road order applies.",
    "2. Highway share of arrived trips doubles: 4.7% -> 9.5% pooled, every on window above every off window.",
    "3. Failed trips unchanged (0.47..0.80% off, 0.41..0.82% on). Arrived paths 43 -> 49 nodes on average.",
    "4. It writes only the per-trip visited grid, never traffic density or the save. SC3NETMOD_RAMPFIRST=0 turns it off.",
    "Still under 10%: trips stop at the first destination they reach, and only about 7% of trips ever pass an on-ramp.",
]
NOTES = [
    "Why so few trips use highways (Sacramento, one game, windows of about 90 sim days, A and B alternated ABBA):",
    "1. The router is not a shortest-path search. A trip walks road by road and stops at the FIRST cell that serves",
    "   its destination kind. Trip costs only cap the length, so a cheaper highway does not attract trips (left panel).",
    "2. Only 6.6 to 7.6% of trips ever stand next to an on-ramp in their whole search (50 ramp entries, 7,904 road cells).",
    "3. At each step the walk takes the busiest road below the jam level (165). Ramp cells never receive traffic,",
    "   so they lose to any used road: 85% of ramp offers had a busier rival, 38% were taken.",
    "4. On the highway a trip can only end at a map edge, and the exit-or-continue choice ignores the destination.",
    "Giving ramps traffic raises the highway share 1.4x to 1.8x, still under 10%: the rest of the gap is points 1 and 2.",
]


def font(sz, bold=False):
    return ImageFont.truetype("C:/Windows/Fonts/%s.ttf" % ("segoeuib" if bold else "segoeui"), sz)


def hexc(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--patch", action="store_true", help="the RAMPFIRST sheet (two panels)")
    a = ap.parse_args()
    runs, notes = (RUNS_PATCH, NOTES_PATCH) if a.patch else (RUNS, NOTES)
    W, H = 1320, 860
    im = Image.new("RGB", (W, H), hexc(SURF))
    g = ImageDraw.Draw(im)
    g.text((40, 22), "Share of arrived trips that use a highway, stock (A) vs lever (B)", font=font(26, True), fill=hexc(INK))
    pw, ph, top, y0 = 360, 330, 140, 0.0
    ymax = 10.0
    for i, (fn, title) in enumerate(runs):
        left = 90 + i * 420
        d = json.load(open(os.path.join(a.data, fn)))
        for k, t in enumerate(title.split("\n")):
            g.text((left, top - 62 + k * 24), t, font=font(18, k == 0), fill=hexc(INK if k == 0 else INK2))
        def Y(v):
            return top + ph - (v - y0) / (ymax - y0) * ph
        for v in range(0, 11, 2):
            g.line([(left, Y(v)), (left + pw, Y(v))], fill=hexc(GRID), width=1)
            g.text((left - 34, Y(v) - 11), "%d%%" % v, font=font(15), fill=hexc(INK2))
        for arm, xpos in (("A", 0), ("B", 1)):
            ws = [w for w in d["windows"] if w["arm"] == arm]
            ys = [100.0 * w["arr_hwy"] / w["arrived"] for w in ws]
            pooled = 100.0 * sum(w["arr_hwy"] for w in ws) / sum(w["arrived"] for w in ws)
            cx = left + 90 + xpos * 170
            c = hexc(COL[arm])
            g.line([(cx - 40, Y(pooled)), (cx + 40, Y(pooled))], fill=c, width=3)
            for k, v in enumerate(ys):
                x, y, r = cx + (k - 1.5) * 18, Y(v), 7
                if arm == "A":
                    g.ellipse([x - r - 2, y - r - 2, x + r + 2, y + r + 2], fill=hexc(SURF))
                    g.ellipse([x - r, y - r, x + r, y + r], fill=c)
                else:
                    g.rectangle([x - r - 2, y - r - 2, x + r + 2, y + r + 2], fill=hexc(SURF))
                    g.rectangle([x - r, y - r, x + r, y + r], fill=c)
            g.text((cx + 46, Y(pooled) - 12), "%.1f%%" % pooled, font=font(18, True), fill=hexc(INK))
            g.text((cx - 40, top + ph + 10), "A stock" if arm == "A" else "B lever", font=font(17), fill=hexc(INK2))
    g.text((90, top + ph + 40), "dot / square = one window of about 90 sim days, bar = pooled share of the 4 windows",
           font=font(15), fill=hexc(INK2))
    for i, line in enumerate(notes):
        g.text((40, 560 + i * 34), line, font=font(18, i == 0), fill=hexc(INK if i == 0 or line[0].isdigit() else INK2))
    im.save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
