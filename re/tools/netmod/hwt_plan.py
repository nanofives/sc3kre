#!/usr/bin/env python3
r"""hwt_plan.py - top-down plan sheet for the connecting highway T (stream hwt, highway program 2026-10-18).

  py -3.12 hwt_plan.py OUT.png [--loop 2|3] [--cap CROP.png] [--stub CROP.png]
  py -3.12 hwt_plan.py variants OUT.png        loop 2, loop 3 and the right-in / right-out fallback

Draws the layout in its state-0 frame (stem arriving from -z): cell grid, both carriageways, the stem, the four turning
ramps with direction arrows, the bridge deck over the through highway, the level-change cells and the piece id.state
of every cell. Plan axes: x to the right, z up, so the sheet has the game's handedness (+x -> +z is counter-clockwise,
NET_LANES.md 8) and right-hand traffic reads as on a road map. The optional crops are stock screenshots shown beside it.
"""
import math
import sys

from PIL import Image, ImageDraw, ImageFont

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hwt_layout  # noqa: E402

CELL = 70
W, E = 0, 1                               # stem columns: SB (runs -z) at x=W, NB (runs +z) at x=E
BRIDGE_COL = {"NB -> WB": 1.5, "WB -> SB": 0.5}


class Plan:
    """One layout to draw: cells from hwt_layout, movement polylines, the window."""

    def __init__(self, loop=3, rio=False, cell=CELL):
        self.L, self.rio, self.cell = loop, rio, cell
        self.cells, self.new = hwt_layout.layout(loop, rio)
        L = loop
        self.X0, self.X1, self.Z0, self.Z1 = -3, L + 3, -4, (1 if rio else L + 3)
        self.level = set() if rio else {(0, -1), (1, -1), (0, 2), (1, 2)}
        far = self.X1 + 0.9
        self.moves = [
            ("EB through", (90, 90, 90), [(-3, 0.5), (far, 0.5)], 7),
            ("WB through", (90, 90, 90), [(far, 1.5), (-3, 1.5)], 7),
            ("stem NB (inbound)", (90, 90, 90), [(1.5, -4), (1.5, -2.2)], 7),
            ("stem SB (outbound)", (90, 90, 90), [(0.5, -2.2), (0.5, -4)], 7),
            ("NB -> EB (right)", (40, 120, 220), [(1.5, -2.6), (1.5, -2.3), (1.75, -1.75), (2.5, -1.4), (2.5, -0.4),
                                                  (2.8, 0.25), (3.6, 0.5)], 4),
            ("EB -> SB (right)", (40, 160, 70), [(-2.4, 0.5), (-1.5, 0.3), (-0.5, -0.4), (-0.5, -1.4),
                                                 (-0.25, -1.75), (0.5, -2.4), (0.5, -2.7)], 4),
        ]
        if not rio:
            self.moves += [
                ("NB -> WB (left: over EB + WB, then the loop)", (230, 120, 20),
                 [(1.5, -2.6), (1.5, 2.0), (1.5, L + 1.0), (2.0, L + 1.5)] + ([(L, L + 1.5)] if L > 2 else []) +
                 [(L + 0.5, L + 1.0), (L + 0.5, 2.1), (L + 0.2, 1.6), (L - 0.4, 1.5), (L - 1.0, 1.5)], 4),
                ("WB -> SB (left: outer ramp, over WB + EB)", (150, 60, 200),
                 [(L + 2.6, 1.5), (L + 2.0, 1.55), (L + 1.5, 1.9), (L + 1.5, 2.6), (L + 1.5, L + 2.0),
                  (L + 1.0, L + 2.5), (1.0, L + 2.5), (0.5, L + 2.0), (0.5, -2.7)], 4),
            ]

    def px(self, x, z, ox, oy):
        return ox + (x - self.X0) * self.cell, oy + (self.Z1 + 1 - z) * self.cell

    def size(self):
        return (self.X1 - self.X0 + 1) * self.cell, (self.Z1 - self.Z0 + 1) * self.cell


def font(sz, bold=False):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/%s.ttf" % ("arialbd" if bold else "arial"), sz)
    except OSError:
        return ImageFont.load_default()


def smooth(pts, n=10):
    """Catmull-Rom through the points (end points repeated)."""
    p = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(p) - 2):
        for k in range(n):
            t = k / n
            q = []
            for a in range(2):
                p0, p1, p2, p3 = p[i - 1][a], p[i][a], p[i + 1][a], p[i + 2][a]
                q.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
            out.append(tuple(q))
    out.append(pts[-1])
    return out


def arrow(d, a, b, col, size=9):
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    tip = b
    l = (b[0] - size * math.cos(ang - 0.45), b[1] - size * math.sin(ang - 0.45))
    r = (b[0] - size * math.cos(ang + 0.45), b[1] - size * math.sin(ang + 0.45))
    d.polygon([tip, l, r], fill=col)


def draw_plan(img, P, ox, oy, note=True):
    d = ImageDraw.Draw(img, "RGBA")
    C = P.cell
    f9, f10 = font(10 if C >= 60 else 8), font(11 if C >= 60 else 9)
    px = P.px
    for x in range(P.X0, P.X1 + 1):
        for z in range(P.Z0, P.Z1 + 1):
            a = px(x, z + 1, ox, oy)
            b = px(x + 1, z, ox, oy)
            fill = (236, 236, 228)
            if z in (0, 1) or z < 0 and x in (W, E):
                fill = (200, 200, 200)
            if (x, z) in P.new:
                fill = (250, 238, 200)
            d.rectangle([a, b], fill=fill, outline=(160, 160, 160))
    hatch = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hatch)
    for k in range(-C, C, 10):
        hd.line([(k, C), (k + C, 0)], fill=(120, 120, 255, 110), width=2)
    for (x, z) in P.level:
        a = px(x, z + 1, ox, oy)
        img.paste(hatch, (int(a[0]), int(a[1])), hatch)
    if not P.rio:                         # bridge deck: the stem (2 cells wide) over both carriageways
        a, b = px(W, 2, ox, oy), px(E + 1, 0, ox, oy)
        d.rectangle([a[0] + 6, a[1] + 1, b[0] - 6, b[1] - 1], fill=(120, 120, 255, 70), outline=(40, 40, 200),
                    width=3)
    else:                                 # the stock caps stay
        for x in (W, E):
            a, b = px(x, 0, ox, oy), px(x + 1, -1, ox, oy)
            d.rounded_rectangle([a[0] + 4, a[1] + 4, b[0] - 4, b[1] - 4], radius=10, outline=(60, 60, 60), width=2)
            d.text((a[0] + 6, a[1] + C // 2 - 6), "stock cap", fill=(60, 60, 60), font=f9)
    for name, col, pts, wd in P.moves:
        s = [px(x, z, ox, oy) for x, z in smooth(pts)]
        d.line(s, fill=col, width=wd, joint="curve")
        for i in range(12, len(s) - 1, 26):
            arrow(d, s[i - 1], s[i], col, 11 if wd > 5 else 9)
        arrow(d, s[-2], s[-1], col, 11)
    for name, col, pts, wd in P.moves:    # the bridge lanes drawn again on top: over the through highway
        cx = [v for k, v in BRIDGE_COL.items() if name.startswith(k)]
        if not cx:
            continue
        seg = [px(*q, ox, oy) for q in smooth(pts) if 0.0 <= q[1] <= 2.0 and abs(q[0] - cx[0]) < 0.2]
        if len(seg) > 1:
            d.line(seg, fill=(255, 255, 255), width=wd + 6)
            d.line(seg, fill=col, width=wd)
            arrow(d, seg[len(seg) // 2 - 1], seg[len(seg) // 2], col, 10)
    for (x, z), (pid, st, role) in P.cells.items():
        a = px(x, z + 1, ox, oy)
        d.text((a[0] + 3, a[1] + 2), "%d.%d" % (pid, st), fill=(0, 0, 0), font=f10)
        if role and C >= 60:
            d.text((a[0] + 3, a[1] + C - 14), role, fill=(70, 70, 70), font=f9)
    for x in range(P.X0, P.X1 + 1):
        p = px(x + 0.5, P.Z0, ox, oy)
        d.text((p[0] - 6, p[1] + 4), "%+d" % x if x else "0", fill=(0, 0, 0), font=f10)
    for z in range(P.Z0, P.Z1 + 1):
        p = px(P.X0, z + 0.5, ox, oy)
        d.text((p[0] - 26, p[1] - 6), "%+d" % z if z else "0", fill=(0, 0, 0), font=f10)
    if note:
        p = px(P.X0, P.Z0, ox, oy)
        d.text((p[0], p[1] + 22), "x to the right, z up (the game's handedness). Cells relative to the stem: SB "
               "column x=0,\nNB column x=1, through highway rows z=0 (EB, runs +x) and z=1 (WB, runs -x). "
               "Right-hand traffic.", fill=(0, 0, 0), font=f10)
    return d


def variants(out):
    """Loop 2, loop 3 and the right-in / right-out fallback side by side."""
    ps = [(Plan(2, cell=48), "full, loop 2x2 (switch --loop 2): box 5 x 7, 16 new cells"),
          (Plan(3, cell=48), "full, loop 3x3 (default, matches hwx): box 6 x 8, 22 new cells"),
          (Plan(2, rio=True, cell=48), "fallback right-in / right-out: 4 new cells")]
    w = sum(p.size()[0] + 60 for p, _ in ps) + 20
    h = max(p.size()[1] for p, _ in ps) + 110
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 10), "hwt layouts (rule twin hwt_layout.py, every movement routed offline)", fill=(0, 0, 0),
           font=font(18, True))
    x = 50
    for p, title in ps:
        d.text((x, 44), title, fill=(0, 0, 0), font=font(13, True))
        draw_plan(img, p, x, 70, note=False)
        x += p.size()[0] + 60
    img.save(out)
    print("wrote", out, img.size)


def main(argv):
    if argv[1] == "variants":
        return variants(argv[2])
    out = argv[1]
    P = Plan(int(argv[argv.index("--loop") + 1]) if "--loop" in argv else 3)
    crops = {}
    for k in ("--cap", "--stub"):
        if k in argv:
            crops[k] = Image.open(argv[argv.index(k) + 1]).convert("RGB")
    pw, ph = P.size()
    right = 560
    img = Image.new("RGB", (pw + 90 + right, max(ph + 130, 1200)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 10), "hwt plan: highway T that connects every movement (trumpet, stem bridges over, loop on the far "
           "side)", fill=(0, 0, 0), font=font(18, True))
    draw_plan(img, P, 50, 50)
    x = pw + 80
    y = 50
    fb, fr = font(13, True), font(12)
    d.text((x, y), "Legend", fill=(0, 0, 0), font=fb)
    y += 20
    for name, col, pts, wd in P.moves:
        if name.startswith(("WB through", "stem")):
            continue
        if name == "EB through":
            name = "through highway and stem (one direction, 2 lanes per cell)"
        d.line([(x, y + 7), (x + 30, y + 7)], fill=col, width=wd)
        d.text((x + 38, y), name, fill=(0, 0, 0), font=fr)
        y += 18
    d.rectangle([x, y + 2, x + 30, y + 14], fill=(200, 200, 255), outline=(40, 40, 200), width=2)
    d.text((x + 38, y), "bridge deck (stem one level above the through deck)", fill=(0, 0, 0), font=fr)
    y += 18
    for k in range(0, 30, 8):
        d.line([(x + k, y + 14), (x + k + 8, y + 2)], fill=(120, 120, 255), width=2)
    d.text((x + 38, y), "level change cell (ramp up / down, 1 cell, as the stock X arms)", fill=(0, 0, 0), font=fr)
    y += 18
    d.rectangle([x, y + 2, x + 30, y + 14], fill=(250, 238, 200), outline=(160, 160, 160))
    d.text((x + 38, y), "new cell the T claims (must be free: no building, zone, network)", fill=(0, 0, 0), font=fr)
    y += 18
    d.text((x, y), "id.state per cell (state 0 = this frame); ids 21200..21214 (hwt_layout.py)", fill=(0, 0, 0), font=fr)
    y += 26
    for k, title in (("--cap", "Stock now, gesture 1: stem dragged up to the side (or started on the far "
                      "carriageway):\ncap 11235/11237 beside the through highway, no connection"),
                     ("--stub", "Stock now, gesture 2: drag started on the near carriageway: a 4x4 X flyover\n"
                      "(15113/15114, arms 15107/15108, 15150/15153) with a 1-cell stub arm, no ramps")):
        if k in crops:
            d.text((x, y), title, fill=(0, 0, 0), font=fr)
            y += 34
            c = crops[k]
            c = c.resize((right - 20, int(c.height * (right - 20) / c.width)))
            img.paste(c, (x, y))
            y += c.height + 12
    notes = [
        "Rule: both gestures convert, to the same layout (4 rotations).",
        " 1) caps 11235/11237 next to a straight through highway (15051 or 73),",
        "    stem straight for 3+ cells, perpendicular.",
        " 2) the stub X: stock 4x4 X whose arm on one side ends after 1 cell",
        "    (no highway beyond it). hwx keeps every X with both arms continuing.",
        "Refused (stays stock): any footprint cell not free or not plain straight",
        " highway, slope cells, diagonals, an X, a stem shorter than 3, another",
        " junction within the footprint. Fallback when only the far side is",
        " blocked: right-in/right-out (NB->EB, EB->SB ramps only), stem keeps cap.",
        "Footprint (loop 3x3, default, matches hwx): 6 x 8 cells (x -1..4, z -2..5),",
        " 4 new cells on the stem side, 18 on the far side (the 2 eye cells inside",
        " the loop are not claimed). Loop 2x2 switch: 5 x 7, 16 new cells.",
        " The through highway stays level and straight.",
    ]
    for t in notes:
        d.text((x, y), t, fill=(0, 0, 0), font=fr)
        y += 16
    img.save(out)
    print("wrote", out, img.size)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
