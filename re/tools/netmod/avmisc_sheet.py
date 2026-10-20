#!/usr/bin/env python3
r"""avmisc_sheet.py - the milestone 1 plan picture of task avmisc (big roundabout avenue arms, hwave straight transition).

  py -3.12 avmisc_sheet.py plan OUT.png
"""
import sys

from PIL import Image, ImageDraw, ImageFont

BG, ROAD, MED, HWY = (247, 247, 247), (150, 150, 150), (60, 150, 60), (186, 186, 186)
RED, BLUE, RING, WHITE = (214, 40, 40), (30, 90, 220), (120, 60, 160), (255, 255, 255)


def font(sz, bold=False):
    for n in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(n, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def bez(p0, p1, p2, n=24):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]


def smooth(p0, p1, n=24):
    """smoothstep S from p0 to p1 along the longer axis"""
    out = []
    for i in range(n + 1):
        t = i / n
        s = t * t * (3 - 2 * t)
        if abs(p1[0] - p0[0]) >= abs(p1[1] - p0[1]):
            out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * s))
        else:
            out.append((p0[0] + (p1[0] - p0[0]) * s, p0[1] + (p1[1] - p0[1]) * t))
    return out


class Panel:
    def __init__(self, d, ox, oy, scale):
        self.d, self.ox, self.oy, self.k = d, ox, oy, scale

    def p(self, pt):
        return (self.ox + pt[0] * self.k, self.oy + pt[1] * self.k)

    def rect(self, x0, z0, x1, z1, col):
        a, b = self.p((x0, z0)), self.p((x1, z1))
        self.d.rectangle([a[0], a[1], b[0], b[1]], fill=col)

    def line(self, pts, col, w=3, arrow=False, dash=False):
        q = [self.p(t) for t in pts]
        if dash:
            for i in range(0, len(q) - 1, 2):
                self.d.line([q[i], q[i + 1]], fill=col, width=w)
        else:
            self.d.line(q, fill=col, width=w, joint="curve")
        if arrow:
            (x0, y0), (x1, y1) = q[-2], q[-1]
            dx, dy = x1 - x0, y1 - y0
            n = max((dx * dx + dy * dy) ** 0.5, 1e-6)
            dx, dy = dx / n, dy / n
            s = 9
            self.d.polygon([(x1, y1), (x1 - s * dx + s * 0.55 * dy, y1 - s * dy - s * 0.55 * dx),
                            (x1 - s * dx - s * 0.55 * dy, y1 - s * dy + s * 0.55 * dx)], fill=col)


def roundabout(d, ox, oy, k, new):
    """3x3 block at cells 0..3, avenue arm east on cell rows 0 and 1 (pieces 20612 NE corner, 20603 side), 3 cells long"""
    P = Panel(d, ox, oy, k)
    P.rect(0, 0, 3, 3, ROAD)
    P.rect(3, 0, 6.2, 2, ROAD)
    P.rect(3, 0.97, 6.2, 1.03, MED)
    P.rect(1.05, 1.05, 1.95, 1.95, (110, 150, 80))                      # island
    ring = [(0.31, 0.31), (2.69, 0.31), (2.69, 2.69), (0.31, 2.69), (0.31, 0.31)]
    for a, b in zip(ring[:-1], ring[1:]):
        P.line([a, b], RING, 3, arrow=True)
    if not new:                                                          # today: one lane each way per half
        P.line([(2.0, 0.31), (6.0, 0.31)], RED, 3, arrow=True)
        P.line([(6.0, 0.69), (3.0, 0.69), (2.69, 1.0), (2.69, 2.0)], BLUE, 3, arrow=True)
        P.line([(2.69, 1.0), (3.0, 1.31), (6.0, 1.31)], RED, 3, arrow=True)
        P.line([(6.0, 1.69), (3.0, 1.69), (2.69, 2.0)], BLUE, 3, arrow=True)
        return P
    P.line([(2.0, 0.31), (6.0, 0.31)], RED, 3, arrow=True)                                   # out, stock straight
    P.line(smooth((2.0, 0.31), (3.0, 0.69)) + [(6.0, 0.69)], RED, 3, arrow=True)             # out, new lane 2
    P.line(bez((6.0, 1.69), (3.0, 1.69), (2.69, 2.0)), BLUE, 3, arrow=True)                  # in, stock right turn
    P.line(bez((6.0, 1.31), (3.0, 1.31), (2.69, 2.0)), BLUE, 3, arrow=True)                  # in, new lane
    for z in (0.5, 1.5):
        pts = []
        x = 3.2
        while x < 6.1:
            pts += [(x, z), (x + 0.12, z)]
            x += 0.3
        P.line(pts, WHITE, 2, dash=True)
    return P


def transition(d, ox, oy, k, new):
    """cap row z 0..1 (deck), ground row z 1..2, avenue z 2..4; exit carriageway x 1..2 (+z), entry x 0..1 (-z)"""
    P = Panel(d, ox, oy, k)
    P.rect(0, 0, 2, 1, HWY)
    P.rect(0, 1, 2, 1.5, (170, 170, 170))
    P.rect(0, 1.5, 2, 4, ROAD)
    P.rect(0.96, 0, 1.04, 0.9, (235, 235, 225))
    P.rect(0.96, 2.2, 1.04, 4, MED)
    ex_o, ex_i = 1 + 145 / 255.0, 1 + 61 / 255.0                         # highway exit lanes (drive +z)
    en_o, en_i = 110 / 255.0, 194 / 255.0                                # highway entry lanes (drive -z)
    a_up, a_dn = 175 / 255.0, 80 / 255.0                                 # stock 11204 along z
    if not new:
        P.line([(ex_o, 0), (ex_o, 1.0)] + smooth((ex_o, 1.0), (1 + a_up, 2.0)) + [(1 + a_up, 4)], RED, 3, arrow=True)
        P.line([(ex_i, 0), (ex_i, 1.0)] + smooth((ex_i, 1.0), (a_up, 2.0)) + [(a_up, 4)], RED, 3, arrow=True)
        P.line([(a_dn, 4), (a_dn, 2.0)] + smooth((a_dn, 2.0), (en_o, 1.0)) + [(en_o, 0)], BLUE, 3, arrow=True)
        P.line([(1 + a_dn, 4), (1 + a_dn, 2.0)] + smooth((1 + a_dn, 2.0), (en_i, 1.0)) + [(en_i, 0)], BLUE, 3, arrow=True)
        return P
    for a, b in ((ex_i, 1 + a_dn), (ex_o, 1 + a_up)):
        P.line([(a, 0), (a, 1.0)] + smooth((a, 1.0), (b, 2.0)) + [(b, 4)], RED, 3, arrow=True)
    for a, b in ((en_o, a_dn), (en_i, a_up)):
        P.line([(b, 4), (b, 2.0)] + smooth((b, 2.0), (a, 1.0)) + [(a, 0)], BLUE, 3, arrow=True)
    return P


def plan(out):
    W, H = 1560, 1180
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    T, S, B = font(24, True), font(15), font(17, True)
    d.text((14, 12), "avmisc plan: big roundabout avenue arms + highway <-> avenue transition, one-way avenue halves",
           fill=(0, 0, 0), font=T)
    d.text((14, 46), "red / blue = the two directions.  purple = ring lane (unchanged).  green = median.  "
                     "Drawn in the plan frame (x right, z down), right-hand traffic as the highways.",
           fill=(60, 60, 60), font=S)
    k = 86
    d.text((30, 80), "ROUNDABOUT ARM TODAY", fill=(0, 0, 0), font=B)
    d.text((30, 102), "each half of the avenue is two-way: one lane each way", fill=(60, 60, 60), font=S)
    roundabout(d, 30, 135, k, False)
    d.text((620, 80), "ROUNDABOUT ARM PROPOSED", fill=(0, 0, 0), font=B)
    d.text((620, 102), "each half one-way, 2 lanes: the out half (top) leaves the ring on 2 lanes, the in half (bottom) joins it on 2",
           fill=(60, 60, 60), font=S)
    roundabout(d, 620, 135, k, True)
    txt = [
        "Ring lanes unchanged (one lane, stock slots). Piece frames (state 0 = E side cell, NE corner cell):",
        "- 20603 side, median toward z-: x+ edge IN twice (z 80, z 175), both merge into the ring's exit node",
        "- 20604 side, median toward z+: x+ edge OUT twice, both leave from the ring's entry node (stock curve + 1 new)",
        "- corner, kE = 2 (x+ arm): OUT twice (stock straight 512 + one new curve (0,80) -> (255,175))",
        "- corner, kN = 2 (z- arm): IN twice (stock 259 + one new curve (80,0) -> (175,255))",
        "- checked on all 16 placements (4 sides x 2 cell pairs): the arm half's direction by the avenue rule",
        "  (state s: median on side s, travels toward side (s-1)%4) always matches the piece frame (avmisc_plan.py check).",
    ]
    y = 135 + 3 * k + 20
    for t in txt:
        d.text((30, y), t, fill=(30, 30, 30), font=S)
        y += 20
    d.text((30, y + 10), "NEW IDS (free 20605..20649, shapes 23900..23999): the two-way pieces stay for arms the avenue block leaves stock",
           fill=(30, 30, 30), font=B)
    ids = ["side 20603 -> 20605, 20604 -> 20606   (one-way arm)",
           "corner 20612, 20615, 20616, 20617, 20618 -> 20622, 20625, 20626, 20627, 20628   (+10)",
           "base ids (what a game without the mod loads) stay the originals'; table lines get a one-way form",
           "RBT9 picks the set per arm from avcore's 'is this band converted' API; arm cells written as the one-way 11204 variant"]
    for t in ids:
        y += 20
        d.text((30, y + 22), "- " + t, fill=(30, 30, 30), font=S)

    ty = 700
    d.text((30, ty), "HIGHWAY <-> AVENUE TRANSITION TODAY", fill=(0, 0, 0), font=B)
    d.text((30, ty + 22), "lane swap in the ground row (owner saw cars cross)", fill=(60, 60, 60), font=S)
    transition(d, 30, ty + 55, 100, False)
    d.text((400, ty), "PROPOSED: each highway lane continues straight", fill=(0, 0, 0), font=B)
    d.text((400, ty + 22), "x 61 -> 80, 145 -> 175 (exit, +z)   194 -> 175, 110 -> 80 (entry, -z)", fill=(60, 60, 60), font=S)
    transition(d, 400, ty + 55, 100, True)
    notes = [
        "Only the ground row changes (21602 / 21603 -> new 21850 / 21851, bases 15141 / 15140, same art and hwrc classes).",
        "Cap row 21600 / 21601 keeps its lanes (highway positions, straight).",
        "Each lane shifts at most 30 lane units sideways over the row (no crossing, no two lane points in one 72-unit bucket).",
        "Matrices: 21850 z- => z+ only, 21851 z+ => z- only (the swap's z+ => x- and x+ => z- turns go away).",
        "If the avenue band stays stock two-way (all-or-nothing rule) the block keeps building the crossover set 21600..21603.",
    ]
    x0, y0 = 640, ty + 55
    for t in notes:
        d.text((x0, y0), t, fill=(30, 30, 30), font=S)
        y0 += 22
    d.text((640, y0 + 10), "Needs from avcore:", fill=(0, 0, 0), font=B)
    for i, t in enumerate(["- is_converted(cell) and half_dir(cell) for a band touching my pieces",
                           "- a band may END at an hwave transition / an rbt9 arm (no U-turn needed there)",
                           "- the one-way 11204 variant id + a call to write it into my arm cells",
                           "- lane positions 80 / 175 on both halves (as the plan)"]):
        d.text((640, y0 + 36 + 20 * i), t, fill=(30, 30, 30), font=S)
    im.save(out)
    print("wrote", out)


if __name__ == "__main__":
    if sys.argv[1:2] == ["plan"]:
        plan(sys.argv[2])
    else:
        print(__doc__)
