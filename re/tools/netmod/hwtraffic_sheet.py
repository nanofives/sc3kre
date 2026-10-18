#!/usr/bin/env python3
r"""hwtraffic_sheet.py - the owner sheet of the hwtraffic before/after test (2026-10-18).

  py -3.12 hwtraffic_sheet.py DIR OUT.png [--site berlin|seoul]
DIR = the run folder: b2.png / a2.png (the site in game after the edit, BEFORE / AFTER), before_probe_city.json /
after_probe_city.json (hwtraffic_probe.py, 12 months, per-cell highway deposits over the whole map),
groups_placements.json (the cells the hwdx block wrote), summary.json (the per-arm month statistics).
Heat panels: highway deposit amount per cell over the 12 months (the final paths of arrived trips), x to the right,
z down, one blue ramp shared by both arms; grey = highway cell with no deposit; outlined = cells the block wrote.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf",
        "#1c5cab", "#184f95", "#104281", "#0d366b"]
INK, MUTED, GRID = (30, 30, 30), (110, 110, 110), (225, 225, 222)
SITES = {
    "berlin": dict(box=(32, 4, 72, 28), save="berlin_before.sc3", placed="groups_placements.json", O=(48, 13),
                   karms=(-3, 10), extra={(44, 9), (45, 9), (57, 23), (58, 23)},
                   title="Berlin, west trunk: does the highway mod change trips?  Same edit in both games",
                   sub="Edit: one diagonal highway (45,10) -> (58,23) across the trunk at (48,13), after a 3-cell power line detour.",
                   tb="BEFORE (stock): 4 cells of 15149 'Highway Construction' cut the trunk",
                   ta="AFTER (mod): flyover + 2 cloverleaf quadrants (north ones refused: wires, lake)"),
    "seoul": dict(box=(222, 96, 255, 122), save="seoul_before.sc3", placed="placements_live.json", O=(245, 109),
                  karms=(-7, 6), extra={(238, 101), (239, 101)},
                  title="Seoul, east highway to the map edge: does the highway mod change trips?  Same edit in both games",
                  sub="Edit: one diagonal highway (238,102) -> (251,115) across the highway at (245,109), on empty land.",
                  tb="BEFORE (stock): 4 cells of 15149 'Highway Construction' cut the highway",
                  ta="AFTER (mod): flyover + 3 cloverleaf quadrants (the 4th, A1, refused in game)"),
}
X0, Z0, X1, Z1 = SITES["berlin"]["box"]


def font(sz, bold=False):
    for f in (("arialbd.ttf", "segoeuib.ttf") if bold else ("arial.ttf", "segoeui.ttf")):
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def hexc(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def cells(path):
    d = json.load(open(path))
    return {tuple(map(int, k.split(","))): v for k, v in d["cells"].items()}


def heat(c, placed, hwy, vmax, K=14):
    im = Image.new("RGB", ((X1 - X0 + 1) * K, (Z1 - Z0 + 1) * K), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for x in range(X0, X1 + 1):
        for z in range(Z0, Z1 + 1):
            px, pz = (x - X0) * K, (z - Z0) * K
            v = c.get((x, z), 0)
            if v:
                col = hexc(RAMP[min(len(RAMP) - 1, int(len(RAMP) * min(1.0, v / vmax)))])
            elif (x, z) in hwy:
                col = (200, 200, 196)
            else:
                col = (250, 250, 248)
            d.rectangle([px + 1, pz + 1, px + K - 2, pz + K - 2], fill=col)
            if (x, z) in placed:
                d.rectangle([px, pz, px + K - 1, pz + K - 1], outline=(60, 60, 60))
    return im


def main(argv):
    global X0, Z0, X1, Z1
    D, out = argv[1], argv[2]
    T = SITES[argv[argv.index("--site") + 1] if "--site" in argv else "berlin"]
    X0, Z0, X1, Z1 = T["box"]
    sb, sa = Image.open(os.path.join(D, "b2.png")), Image.open(os.path.join(D, "a2.png"))
    cb, ca = cells(os.path.join(D, "before_probe_city.json")), cells(os.path.join(D, "after_probe_city.json"))
    placed = {tuple(map(int, k.split(","))) for k in json.load(open(os.path.join(D, T["placed"])))}
    S = json.load(open(os.path.join(D, "summary.json")))
    # highway cells: the save's highway in the box + the diagonal band of the edit (both arms); the block's cells (AFTER)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from netmod import tiler
    city = tiler.City.load(os.path.join(D, T["save"]))
    hwy = {c for c, p in city.layers["surface"].items() if X0 <= c[0] <= X1 and Z0 <= c[1] <= Z1 and
           (p.id in (73, 11223, 11224, 11235, 11237, 14999) or 15000 <= p.id <= 15160)}
    for k in range(T["karms"][0], T["karms"][1] + 1):
        for dd in (-1, 0, 1):
            hwy.add((T["O"][0] + k + dd, T["O"][1] + k))
    hwy |= T["extra"]
    site = [v for c in (cb, ca) for (x, z), v in c.items() if X0 <= x <= X1 and Z0 <= z <= Z1]
    vmax = sorted(site)[int(0.9 * (len(site) - 1))] if site else 1
    hb, ha = heat(cb, set(), hwy, vmax), heat(ca, placed, hwy | placed, vmax)
    W = 1640
    sheet = Image.new("RGB", (W, 1700), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.text((20, 14), T["title"], font=font(26, True), fill=INK)
    d.text((20, 50), T["sub"] + "  BEFORE = SC3NETMOD_HWY=0 (stock), AFTER = mod on.", font=font(16), fill=MUTED)
    for i, (im, t) in enumerate(((sb, T["tb"]), (sa, T["ta"]))):
        x = 20 + i * 810
        d.text((x, 84), t, font=font(17, True), fill=INK)
        sheet.paste(im.crop((0, 0, 700, 540)).resize((790, 610)), (x, 110))
    y = 740
    d.text((20, y), "Highway use per cell, 12 sim months (final paths of arrived trips), x right, z down. Grey = highway, no trips."
           "  Outlined = cells the mod wrote.", font=font(17, True), fill=INK)
    for i, (im, t) in enumerate(((hb, "BEFORE"), (ha, "AFTER"))):
        x = 20 + i * 810
        d.text((x, y + 30), t, font=font(16, True), fill=INK)
        sheet.paste(im, (x, y + 55))
    ly = y + 55 + hb.size[1] + 10
    for j, h in enumerate(RAMP):
        d.rectangle([20 + j * 24, ly, 20 + j * 24 + 22, ly + 12], fill=hexc(h))
    d.text((20 + len(RAMP) * 24 + 10, ly - 3), "0 .. %d+ deposit units per cell (shared scale)" % vmax, font=font(14), fill=MUTED)
    ty = ly + 34
    B, A = S["before"], S["after"]
    rows = [("Sim months measured (per arm)", "%d" % B["months"], "%d" % A["months"]),
            ("Trips through the crossing (straight through)", "%d total, 0 every month" % B["trips_core"]["sum"],
             "%d total, %d..%d per month" % (A["trips_core"]["sum"], A["trips_core"]["min"], A["trips_core"]["max"])),
            ("Trips using a ramp (changing highway)", "%d" % B["trips_ramps"]["sum"], "%d (the new diagonal leads nowhere)" % A["trips_ramps"]["sum"]),
            ("Failed trips, per month (game counter)", "%.1f (%d..%d)" % (B["failed_game"]["mean"], B["failed_game"]["min"], B["failed_game"]["max"]),
             "%.1f (%d..%d)" % (A["failed_game"]["mean"], A["failed_game"]["min"], A["failed_game"]["max"])),
            ("Trips using any highway, per month", "%.1f (%d..%d)" % (B["arrived_hwy"]["mean"], B["arrived_hwy"]["min"], B["arrived_hwy"]["max"]),
             "%.1f (%d..%d)" % (A["arrived_hwy"]["mean"], A["arrived_hwy"]["min"], A["arrived_hwy"]["max"])),
            ("All trips routed, per month (city)", "%.0f (%d..%d)" % (B["trips"]["mean"], B["trips"]["min"], B["trips"]["max"]),
             "%.0f (%d..%d)" % (A["trips"]["mean"], A["trips"]["min"], A["trips"]["max"])),
            ("Failed trips, game's own monthly ratio", "%.2f%% .. %.2f%%" % (100 * B["fail_ratio_game"]["min"], 100 * B["fail_ratio_game"]["max"]),
             "%.2f%% .. %.2f%%" % (100 * A["fail_ratio_game"]["min"], 100 * A["fail_ratio_game"]["max"])),
            ("Highway density grid, city total, per month", "%.0f (%d..%d)" % (B["hwy_snap_total"]["mean"], B["hwy_snap_total"]["min"], B["hwy_snap_total"]["max"]),
             "%.0f (%d..%d)" % (A["hwy_snap_total"]["mean"], A["hwy_snap_total"]["min"], A["hwy_snap_total"]["max"]))]
    cx = [20, 640, 1120]
    d.text((cx[1], ty), "BEFORE (stock)", font=font(16, True), fill=INK)
    d.text((cx[2], ty), "AFTER (mod)", font=font(16, True), fill=INK)
    for r, (a, b, c) in enumerate(rows):
        yy = ty + 30 + r * 30
        d.line([20, yy - 5, W - 20, yy - 5], fill=GRID)
        d.text((cx[0], yy), a, font=font(16), fill=INK)
        d.text((cx[1], yy), b, font=font(16), fill=INK)
        d.text((cx[2], yy), c, font=font(16), fill=INK)
    sheet = sheet.crop((0, 0, W, ty + 30 + len(rows) * 30 + 20))
    sheet.save(out)
    print("wrote", out, sheet.size, "vmax", vmax)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
