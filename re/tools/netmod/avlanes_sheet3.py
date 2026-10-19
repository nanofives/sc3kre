#!/usr/bin/env python3
r"""avlanes_sheet3.py - owner plan sheet for 3-wide avenues (boulevards) in the lane rework (task avlanes 2026-10-19).
Schematic, drawn as the game shows it (right-hand traffic everywhere).

  py -3.12 avlanes_sheet3.py OUT.png
"""
import math, sys
from PIL import Image, ImageDraw, ImageFont

F = ImageFont.truetype("arial.ttf", 15); FB = ImageFont.truetype("arialbd.ttf", 18); FT = ImageFont.truetype("arialbd.ttf", 22)
UP, DN = (210, 40, 40), (30, 90, 220)
L = 34                               # px per lane: a cell = 3 lane slots wide in this drawing
W, H = 1600, 1100
im = Image.new("RGB", (W, H), (246, 246, 246)); d = ImageDraw.Draw(im)


def arrow(pts, col, w=4):
    d.line(pts, fill=col, width=w)
    (x1, y1), (x2, y2) = pts[-2], pts[-1]; a = math.atan2(y2 - y1, x2 - x1)
    for s in (2.6, -2.6):
        d.line([(x2, y2), (x2 + 11 * math.cos(a + s), y2 + 11 * math.sin(a + s))], fill=col, width=w)


def road(x, y, w, h, col=(150, 150, 150)):
    d.rectangle([x, y, x + w, y + h], fill=col)


def dashes(x, y0, y1):
    for y in range(int(y0), int(y1), 22):
        d.line([(x, y), (x, min(y + 11, y1))], fill=(255, 255, 255), width=2)


# lane x positions (left to right) for a boulevard of width 8 slots: lanes at 0.5,1.5,2.5 | median 2.9..5.1 | 5.5,6.5,7.5
LANES = [0.5, 1.5, 2.5, 5.5, 6.5, 7.5]
BW = 8 * L


def boulevard(x, y, h, dirs, dash=True):
    road(x, y, BW, h)
    d.rectangle([x + 3.0 * L, y, x + 5.0 * L, y + h], fill=(70, 150, 70))
    for t in (1, 2, 6, 7):
        if dash: dashes(x + t * L, y, y + h)
    for k, up in enumerate(dirs):
        lx = x + LANES[k] * L
        arrow([(lx, y + h - 10), (lx, y + 10)] if up else [(lx, y + 10), (lx, y + h - 10)], UP if up else DN)


def title(x, y, t, sub):
    d.text((x, y - 50), t, font=FB, fill=(0, 0, 0)); d.text((x, y - 28), sub, font=F, fill=(60, 60, 60))


d.text((14, 10), "3-wide avenue (boulevard) lane rework (plan): 3 lanes each way, right-hand, wide median in the middle", font=FT, fill=(0, 0, 0))
d.text((14, 40), "red = one direction, blue = the other.  Drawn as seen in game.  Green = median.  The art already paints 3 lanes a side.", font=F, fill=(40, 40, 40))
Y, Hh = 140, 330
title(30, Y, "TODAY", "each outer road two-way, middle lanes mixed")
boulevard(30, Y, Hh, [0, 1, 1, 0, 0, 1])
title(370, Y, "PROPOSED", "3 lanes one way on each side")
boulevard(370, Y, Hh, [0, 0, 0, 1, 1, 1])
d.text((30, Y + Hh + 10), "Today cars meet head-on in the outer roads;", font=F, fill=(0, 0, 0))
d.text((30, Y + Hh + 28), "the lanes ignore the painted lines.", font=F, fill=(0, 0, 0))
d.text((370, Y + Hh + 10), "Same lane lines as now, only the directions", font=F, fill=(0, 0, 0))
d.text((370, Y + Hh + 28), "change: lanes follow the paint.", font=F, fill=(0, 0, 0))

# end U-turn
x, y = 710, Y
title(x, y, "END", "3-lane U-turn round the median nose")
road(x, y + 130, BW, Hh - 130); d.pieslice([x, y, x + BW, y + 260], 180, 360, fill=(150, 150, 150))
d.rectangle([x + 3.0 * L, y + 150, x + 5.0 * L, y + Hh], fill=(70, 150, 70)); d.pieslice([x + 3.0 * L, y + 115, x + 5.0 * L, y + 185], 180, 360, fill=(70, 150, 70))
cx, cy = x + 4 * L, y + 130
for lo in (0, 1, 2):
    r = (3.5 - lo) * L
    pts = [(cx - r, y + Hh - 10)] + [(cx - r * math.cos(t), cy - r * math.sin(t) * 0.95) for t in [i * math.pi / 18 for i in range(19)]] + [(cx + r, y + Hh - 10)]
    arrow(pts[::-1], UP, 3)
d.text((x, y + Hh + 10), "Outer to outer, middle to middle,", font=F, fill=(0, 0, 0))
d.text((x, y + Hh + 28), "inner to inner.", font=F, fill=(0, 0, 0))

# narrowing to an avenue
x, y = 1060, Y
title(x, y, "INTO AN AVENUE", "3 -> 2 lanes each way (a merge)")
road(x, y, BW, 120); d.rectangle([x + 3.0 * L, y, x + 5.0 * L, y + 100], fill=(70, 150, 70))
road(x + 1 * L, y + 120, 6 * L, Hh - 120); d.rectangle([x + 4 * L - 4, y + 150, x + 4 * L + 4, y + Hh], fill=(70, 150, 70))
for tx, bx in ((0.5, 1.5), (1.5, 2.5), (2.5, 2.5)):
    arrow([(x + tx * L, y + 10), (x + tx * L, y + 100), (x + bx * L, y + 200), (x + bx * L, y + Hh - 10)], DN, 3)
for tx, bx in ((5.5, 5.5), (6.5, 5.5), (7.5, 6.5)):
    arrow([(x + bx * L, y + Hh - 10), (x + bx * L, y + 200), (x + tx * L, y + 100), (x + tx * L, y + 10)], UP, 3)
d.text((x, y + Hh + 10), "Each side loses one lane: the inner two", font=F, fill=(0, 0, 0))
d.text((x, y + Hh + 28), "lanes merge. The median narrows.", font=F, fill=(0, 0, 0))

# taper to a single road
x, y = 30, 650
title(x, y, "INTO A SINGLE ROAD", "3 -> 1 lane each way")
road(x, y, BW, 120); d.rectangle([x + 3.0 * L, y, x + 5.0 * L, y + 100], fill=(70, 150, 70))
road(x + 2.5 * L, y + 120, 3 * L, 220)
for tx in (0.5, 1.5, 2.5):
    arrow([(x + tx * L, y + 10), (x + tx * L, y + 100), (x + 3.25 * L, y + 210), (x + 3.25 * L, y + 330)], DN, 3)
for tx in (5.5, 6.5, 7.5):
    arrow([(x + 4.75 * L, y + 330), (x + 4.75 * L, y + 210), (x + tx * L, y + 100), (x + tx * L, y + 10)], UP, 3)
d.text((x, y + 345), "Two merges on each side, the median", font=F, fill=(0, 0, 0))
d.text((x, y + 363), "ends in its nose.", font=F, fill=(0, 0, 0))

# junction with a road
x, y = 370, 650
title(x, y, "ROAD x BOULEVARD", "median opening, every turn")
road(x + 60, y, BW, 330); road(x, y + 120, BW + 160, 70)
d.rectangle([x + 60 + 3.0 * L, y, x + 60 + 5.0 * L, y + 112], fill=(70, 150, 70)); d.rectangle([x + 60 + 3.0 * L, y + 198, x + 60 + 5.0 * L, y + 330], fill=(70, 150, 70))
for k, up in enumerate([0, 0, 0, 1, 1, 1]):
    lx = x + 60 + LANES[k] * L
    arrow([(lx, y + 320), (lx, y + 10)] if up else [(lx, y + 10), (lx, y + 320)], UP if up else DN, 3)
arrow([(x + 5, y + 172), (x + BW + 150, y + 172)], (120, 60, 160), 3)
arrow([(x + BW + 150, y + 138), (x + 5, y + 138)], (120, 60, 160), 3)
arrow([(x + 60 + 5.5 * L, y + 300), (x + 60 + 5.5 * L, y + 172), (x + 60 + 3.5 * L, y + 145), (x + 10, y + 140)], (240, 140, 0), 3)

tx, ty = 840, 610
lines = [("What changes", FB, (0, 0, 0)),
 ("- Each side of a boulevard runs one way on 3 lanes: the outer road's 2 lanes and the middle", F, (0, 0, 0)),
 ("  road's lane next to it. The wide grass median stays in the middle.", F, (0, 0, 0)),
 ("- The lane lines are already painted that way; only the car lanes change to follow them.", F, (0, 0, 0)),
 ("- Ends: a 3-lane U-turn. Into an avenue: 3 -> 2 lanes. Into a single road: 3 -> 1 lane.", F, (0, 0, 0)),
 ("- Crossings with roads, avenues and other boulevards: a median opening with every turn.", F, (0, 0, 0)),
 ("- Diagonal boulevards and their bends into straight ones follow the same rule.", F, (0, 0, 0)),
 ("", F, 0),
 ("Same as the avenue plan", FB, (0, 0, 0)),
 ("- Right-hand traffic everywhere, English-UK included.", F, (0, 0, 0)),
 ("- Trips follow the one-way sides too.", F, (0, 0, 0)),
 ("- A game without the mod sees the stock pieces (two avenue halves with a road between).", F, (0, 0, 0)),
 ("", F, 0),
 ("Not in this plan", FB, (150, 0, 0)),
 ("- Big roundabouts take no boulevard arms today, and there is no highway-to-boulevard", F, (0, 0, 0)),
 ("  transition. A highway would meet a boulevard as 2 -> 3 lanes: later, if you want it.", F, (0, 0, 0))]
for t, f, c in lines:
    if t: d.text((tx, ty), t, font=f, fill=c)
    ty += 26 if f is FB else 22
im.save(sys.argv[1]); print(sys.argv[1], im.size)
