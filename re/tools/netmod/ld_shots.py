#!/usr/bin/env python3
r"""ld_shots.py - density heat maps and lane-step diagrams for the lanedensity owner shots.

  heat:  py -3.12 ld_shots.py heat --save S --a LABEL=probe.npz --b LABEL=probe.npz --rect x0,z0,x1,z1
                                   --box x0,z0,x1,z1 [--box ...] --title T --out out.png [--months 3:14]
         Side by side: arm A, arm B, B - A, the 12-month mean of the published density +0x60 per cell, road cells
         outlined from the save, red boxes around the cells under test. Cell (x, z) = save coordinates, x to the right,
         z down.
  steps: py -3.12 ld_shots.py steps --log A=sc3netmod.log --log B=sc3netmod.log --cells x0,z0,x1,z1 --title T --out o.png
         Router steps through the variant cells (last "lanedensity: cell" lines of each log): one arrow per
         (entry side, exit side) pair, width by count, red = against the lanes (the piece's own matrix has no
         such turn), with the counts printed.
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import network_layer as nl  # noqa: E402

DX = [(-1, 0), (0, -1), (1, 0), (0, 1)]   # side 0 x-, 1 z-, 2 x+, 3 z+ (SIMNTWRK dir table 0x10032134)


def font(sz):
    for f in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def heat_colour(v, vmax):
    t = max(0.0, min(1.0, v / vmax)) if vmax else 0.0
    # dark blue -> cyan -> yellow -> white-ish (sequential)
    stops = [(0.0, (20, 24, 48)), (0.3, (30, 110, 170)), (0.6, (90, 200, 160)), (0.85, (250, 220, 90)), (1.0, (255, 250, 230))]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            return tuple(int(c0[i] + (c1[i] - c0[i]) * u) for i in range(3))
    return stops[-1][1]


def diff_colour(v, vmax):
    t = max(-1.0, min(1.0, v / vmax)) if vmax else 0.0
    if t >= 0:
        return (int(240 - 30 * t), int(240 - 200 * t), int(240 - 200 * t))      # more in B: red
    return (int(240 + 200 * t), int(240 + 120 * t), int(240 - 10 * t))           # less in B: blue


def panel(grid, road, rect, cs, colour, vmax, boxes, label):
    x0, z0, x1, z1 = rect
    w, h = (x1 - x0 + 1) * cs, (z1 - z0 + 1) * cs
    im = Image.new("RGB", (w, h + 34), (250, 250, 248))
    d = ImageDraw.Draw(im)
    for x in range(x0, x1 + 1):
        for z in range(z0, z1 + 1):
            px, pz = (x - x0) * cs, (z - z0) * cs + 34
            if road[x, z]:
                d.rectangle([px, pz, px + cs - 1, pz + cs - 1], fill=colour(grid[x, z], vmax))
            else:
                d.rectangle([px, pz, px + cs - 1, pz + cs - 1], fill=(214, 214, 208))
    for (bx0, bz0, bx1, bz1) in boxes:
        d.rectangle([(bx0 - x0) * cs - 2, (bz0 - z0) * cs + 32, (bx1 - x0 + 1) * cs + 1, (bz1 - z0 + 1) * cs + 35],
                    outline=(220, 20, 20), width=3)
    d.text((6, 6), label, fill=(20, 20, 20), font=font(18))
    return im


def cmd_heat(a):
    m0, m1 = (int(v) for v in a.months.split(":"))
    la, pa = a.a.split("=", 1)
    lb, pb = a.b.split("=", 1)
    ga = np.load(pa)["grids"][m0 - 1:m1].astype(float).mean(0)
    gb = np.load(pb)["grids"][m0 - 1:m1].astype(float).mean(0)
    n = ga.shape[0]
    nets, _ = nl.read_networks(a.save)
    road = np.zeros((n, n), dtype=bool)
    for r in nets[1]:
        road[r[0], r[1]] = True
    rect = tuple(int(v) for v in a.rect.split(","))
    boxes = [tuple(int(v) for v in b.split(",")) for b in a.box]
    x0, z0, x1, z1 = rect
    vmax = max(ga[x0:x1 + 1, z0:z1 + 1].max(), gb[x0:x1 + 1, z0:z1 + 1].max(), 1)
    dif = gb - ga
    dmax = max(abs(dif[x0:x1 + 1, z0:z1 + 1]).max(), 1)
    cs = a.cell
    p1 = panel(ga, road, rect, cs, heat_colour, vmax, boxes, la)
    p2 = panel(gb, road, rect, cs, heat_colour, vmax, boxes, lb)
    p3 = panel(dif, road, rect, cs, diff_colour, dmax, boxes, "%s - %s" % (lb, la))
    gap = 16
    W = p1.width * 3 + gap * 4
    H = p1.height + 90
    im = Image.new("RGB", (W, H), (250, 250, 248))
    d = ImageDraw.Draw(im)
    d.text((gap, 10), a.title, fill=(10, 10, 10), font=font(22))
    for i, p in enumerate((p1, p2, p3)):
        im.paste(p, (gap + i * (p1.width + gap), 44))
    d.text((gap, H - 40), "%s. Max %.0f (left, middle); diff +-%.0f (right: red = more in %s, blue = less)." %
           (a.legend, vmax, dmax, lb), fill=(40, 40, 40), font=font(15))
    im.save(a.out, optimize=True)
    print("wrote", a.out, im.size)


CELL_RE = re.compile(r"lanedensity: cell \((\d+),(\d+)\) id (\d+) wrong=(\d+) arrblock=(\d+) steps\[[^\]]*\]\[exit\]=([\d,]+)")


def read_cells(path):
    last = {}
    with open(path, errors="replace") as f:
        for line in f:
            m = CELL_RE.search(line)
            if m:
                x, z, pid, wr, ab, s = m.groups()
                v = [int(t) for t in s.split(",")]
                last[(int(x) & 0x3fff, int(z))] = {"id": int(pid), "wrong": int(wr), "arrblock": int(ab),
                                          "steps": [v[i * 4:i * 4 + 4] for i in range(5)]}
    return last


def cmd_steps(a):
    logs = [(s.split("=", 1)[0], read_cells(s.split("=", 1)[1])) for s in a.log]
    x0, z0, x1, z1 = (int(v) for v in a.cells.split(","))
    cs = a.cell
    allowed = {}
    for spec in a.allow:            # "x,z:e>t,e>t" world sides 0..3, 4 = from a lot
        c, pairs = spec.split(":")
        cx, cz = (int(v) for v in c.split(","))
        allowed[(cx, cz)] = {tuple(int(u) for u in p.split(">")) for p in pairs.split(",") if p}
    panels = []
    for label, cells in logs:
        w, h = (x1 - x0 + 1) * cs, (z1 - z0 + 1) * cs
        im = Image.new("RGB", (w + 40, h + 80), (250, 250, 248))
        d = ImageDraw.Draw(im)
        d.text((10, 8), label, fill=(20, 20, 20), font=font(18))
        tot_ok = tot_bad = 0
        for (x, z), c in cells.items():
            if not (x0 <= x <= x1 and z0 <= z <= z1):
                continue
            px, pz = 20 + (x - x0) * cs, 44 + (z - z0) * cs
            d.rectangle([px, pz, px + cs - 1, pz + cs - 1], fill=(232, 232, 226), outline=(160, 160, 150))
            cx, cz = px + cs / 2, pz + cs / 2
            ok = allowed.get((x, z))
            for e in range(5):
                for t in range(4):
                    n = c["steps"][e][t]
                    if not n:
                        continue
                    bad = ok is not None and (e, t) not in ok
                    if bad:
                        tot_bad += n
                    else:
                        tot_ok += n
                    col = (210, 30, 30) if bad else (40, 120, 60)
                    wdt = max(2, min(12, int(2 + 2.5 * np.log10(1 + n))))
                    # entry point on side e (or the centre for "from a lot"), exit point on side t
                    if e < 4:
                        sx, sz = cx + DX[e][0] * cs * 0.42, cz + DX[e][1] * cs * 0.42
                    else:
                        sx, sz = cx, cz
                    tx, tz = cx + DX[t][0] * cs * 0.42, cz + DX[t][1] * cs * 0.42
                    off = (e * 4 + t) % 5 - 2
                    sx += DX[t][1] * off * 3; sz += DX[t][0] * off * 3
                    d.line([sx, sz, cx, cz, tx, tz], fill=col, width=wdt, joint="curve")
                    hx, hz = DX[t]
                    d.polygon([(tx + hx * 6, tz + hz * 6), (tx - hz * 6, tz + hx * 6), (tx + hz * 6, tz - hx * 6)], fill=col)
            if c["wrong"] or c["arrblock"]:
                d.text((px + 4, pz + cs - 18), "refused %d" % (c["wrong"] + c["arrblock"]), fill=(120, 20, 20), font=font(12))
        d.text((10, h + 52), "with the lanes %d, against %d" % (tot_ok, tot_bad), fill=(20, 20, 20), font=font(16))
        panels.append(im)
    gap = 20
    W = sum(p.width for p in panels) + gap * (len(panels) + 1)
    H = max(p.height for p in panels) + 90
    out = Image.new("RGB", (W, H), (250, 250, 248))
    d = ImageDraw.Draw(out)
    d.text((gap, 10), a.title, fill=(10, 10, 10), font=font(22))
    x = gap
    for p in panels:
        out.paste(p, (x, 44)); x += p.width + gap
    d.text((gap, H - 38), a.legend, fill=(40, 40, 40), font=font(15))
    out.save(a.out, optimize=True)
    print("wrote", a.out, out.size)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("heat")
    h.add_argument("--save", required=True)
    h.add_argument("--a", required=True)
    h.add_argument("--b", required=True)
    h.add_argument("--rect", required=True)
    h.add_argument("--box", action="append", default=[])
    h.add_argument("--title", default="")
    h.add_argument("--legend", default="Mean monthly traffic density per cell, months 3-14")
    h.add_argument("--months", default="3:14")
    h.add_argument("--cell", type=int, default=14)
    h.add_argument("--out", required=True)
    s = sub.add_parser("steps")
    s.add_argument("--log", action="append", required=True)
    s.add_argument("--cells", required=True)
    s.add_argument("--allow", action="append", default=[])
    s.add_argument("--title", default="")
    s.add_argument("--legend", default="")
    s.add_argument("--cell", type=int, default=120)
    s.add_argument("--out", required=True)
    a = ap.parse_args()
    cmd_heat(a) if a.cmd == "heat" else cmd_steps(a)


if __name__ == "__main__":
    main()
