#!/usr/bin/env python3
r"""avlanes_sheet.py - the owner plan sheet for the avenue lane rework (task avlanes 2026-10-19): schematic lane
diagrams, drawn as the game shows them (right-hand traffic, the side the highways already use).

  py -3.12 avlanes_sheet.py OUT.png
"""
import math, sys
from PIL import Image, ImageDraw, ImageFont

F = ImageFont.truetype("arial.ttf", 15); FB = ImageFont.truetype("arialbd.ttf", 18); FT = ImageFont.truetype("arialbd.ttf", 22)
UP, DN = (210, 40, 40), (30, 90, 220)
C = 44                               # px per lane slot
W, H = 1560, 1080
im = Image.new("RGB", (W, H), (246, 246, 246)); d = ImageDraw.Draw(im)


def arrow(pts, col, w=4):
    d.line(pts, fill=col, width=w)
    (x1, y1), (x2, y2) = pts[-2], pts[-1]; a = math.atan2(y2 - y1, x2 - x1)
    for s in (2.6, -2.6):
        d.line([(x2, y2), (x2 + 12 * math.cos(a + s), y2 + 12 * math.sin(a + s))], fill=col, width=w)


def road(x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(150, 150, 150))


def dashes(x, y0, y1, col=(255, 255, 255)):
    for y in range(int(y0), int(y1), 22):
        d.line([(x, y), (x, min(y + 11, y1))], fill=col, width=2)


def median(x, y0, y1):
    d.rectangle([x - 5, y0, x + 5, y1], fill=(60, 150, 60))


def straight(x, y, h, dirs, title, sub):
    d.text((x, y - 50), title, font=FB, fill=(0, 0, 0)); d.text((x, y - 28), sub, font=F, fill=(60, 60, 60))
    road(x, y, 4 * C, h)
    median(x + 2 * C, y, y + h)
    for k, up in enumerate(dirs):
        lx = x + C / 2 + k * C
        arrow([(lx, y + h - 10), (lx, y + 10)] if up else [(lx, y + 10), (lx, y + h - 10)], UP if up else DN)
    if dirs == [0, 0, 1, 1]:
        dashes(x + C, y, y + h); dashes(x + 3 * C, y, y + h)


d.text((14, 10), "Avenue lane rework (plan): 2 lanes each way, one direction per half, right-hand traffic like the highways", font=FT, fill=(0, 0, 0))
d.text((14, 40), "red = one direction, blue = the other.  Drawn as seen in game.  Green = median.", font=F, fill=(40, 40, 40))
Y = 140; Hh = 330
straight(30, Y, Hh, [1, 0, 1, 0], "TODAY (stock avenue)", "each half is a two-way road")
straight(270, Y, Hh, [0, 0, 1, 1], "PROPOSED", "each half one-way, 2 lanes")
d.text((30, Y + Hh + 10), "Today cars meet head-on inside one half and", font=F, fill=(0, 0, 0))
d.text((30, Y + Hh + 28), "there is no lane order to follow.", font=F, fill=(0, 0, 0))

# end U-turn
x, y = 540, Y
d.text((x, y - 50), "AVENUE END", font=FB, fill=(0, 0, 0)); d.text((x, y - 28), "U-turn from one half to the other", font=F, fill=(60, 60, 60))
road(x, y + 90, 4 * C, Hh - 90); d.pieslice([x, y, x + 4 * C, y + 180], 180, 360, fill=(150, 150, 150))
median(x + 2 * C, y + 140, y + Hh)
for k, r in ((0, 2 * C - C / 2), (1, C - C / 2)):
    cx, cy = x + 2 * C, y + 90
    pts = [(cx - r, y + Hh - 10)] + [(cx - r * math.cos(t), cy - r * math.sin(t) * 0.9) for t in [i * math.pi / 16 for i in range(17)]] + [(cx + r, y + Hh - 10)]
    pts = pts[::-1]
    arrow(pts, UP)
d.text((x, y + Hh + 10), "Outer lane to outer lane, inner to", font=F, fill=(0, 0, 0))
d.text((x, y + Hh + 28), "inner. Replaces the 11203 bend pair.", font=F, fill=(0, 0, 0))

# road x avenue crossing
x, y = 820, Y
d.text((x, y - 50), "ROAD x AVENUE", font=FB, fill=(0, 0, 0)); d.text((x, y - 28), "median opening, every turn", font=F, fill=(60, 60, 60))
bx, by = x + 90, y + 100
road(bx, y, 4 * C, Hh); road(x, by, 4 * C + 150, 2 * C)
median(bx + 2 * C, y, by - 6); median(bx + 2 * C, by + 2 * C + 6, y + Hh)
for k, up in enumerate([0, 0, 1, 1]):
    lx = bx + C / 2 + k * C
    arrow([(lx, by + 2 * C + 120), (lx, by - 90)] if up else [(lx, by - 90), (lx, by + 2 * C + 120)], UP if up else DN, 3)
arrow([(x + 10, by + C * 1.5), (x + 4 * C + 140, by + C * 1.5)], (120, 60, 160), 3)
arrow([(x + 4 * C + 140, by + C * 0.5), (x + 10, by + C * 0.5)], (120, 60, 160), 3)
arrow([(bx + C * 3.5, by + 2 * C + 40), (bx + C * 3.5, by + C * 1.2), (bx + C * 2.5, by + C * 0.6), (x + 30, by + C * 0.45)], (240, 140, 0), 3)
d.text((x, y + Hh + 10), "Road traffic (purple) crosses or turns.", font=F, fill=(0, 0, 0))
d.text((x, y + Hh + 28), "Left turn (orange) uses the opening.", font=F, fill=(0, 0, 0))

# T
x, y = 1190, Y
d.text((x, y - 50), "ROAD MEETS ONE SIDE (T)", font=FB, fill=(0, 0, 0)); d.text((x, y - 28), "a median opening too", font=F, fill=(60, 60, 60))
bx, by = x + 150, y + 100
road(bx, y, 4 * C, Hh); road(x, by, 150, 2 * C)
median(bx + 2 * C, y, by - 6); median(bx + 2 * C, by + 2 * C + 6, y + Hh)
for k, up in enumerate([0, 0, 1, 1]):
    lx = bx + C / 2 + k * C
    arrow([(lx, by + 2 * C + 120), (lx, by - 90)] if up else [(lx, by - 90), (lx, by + 2 * C + 120)], UP if up else DN, 3)
arrow([(x + 5, by + C * 1.5), (bx + C * 0.3, by + C * 1.7), (bx + C * 0.5, by + 2 * C + 40)], (120, 60, 160), 3)
arrow([(x + 5, by + C * 1.3), (bx + C * 2.5, by + C * 1.0), (bx + C * 3.5, by - 30)], (240, 140, 0), 3)
d.text((x, y + Hh + 10), "Today the road only touches the near half", font=F, fill=(0, 0, 0))
d.text((x, y + Hh + 28), "(plain T piece). New: a box across both.", font=F, fill=(0, 0, 0))

# transition
x, y = 30, 640
d.text((x, y - 50), "HIGHWAY <-> AVENUE TRANSITION", font=FB, fill=(0, 0, 0)); d.text((x, y - 28), "no lane swap any more", font=F, fill=(60, 60, 60))
d.rectangle([x, y, x + 4 * C, y + 150], fill=(185, 185, 185)); d.rectangle([x + 2 * C - 3, y, x + 2 * C + 3, y + 150], fill=(230, 230, 220))
road(x, y + 150, 4 * C, 180); median(x + 2 * C, y + 200, y + 330)
for k, up in enumerate([0, 0, 1, 1]):
    lx = x + C / 2 + k * C
    arrow([(lx, y + 320), (lx, y + 10)] if up else [(lx, y + 10), (lx, y + 320)], UP if up else DN)
d.text((x + 4 * C + 14, y + 60), "highway deck", font=F, fill=(0, 0, 0)); d.text((x + 4 * C + 14, y + 250), "avenue", font=F, fill=(0, 0, 0))

tx, ty = 420, 600
lines = [("What changes", FB, (0, 0, 0)),
 ("- Every avenue cell gets new car lanes: both lanes of a half run the same way.", F, (0, 0, 0)),
 ("- Trips follow the halves too: the router never sends a car the wrong way down a half.", F, (0, 0, 0)),
 ("- Avenue ends become a two-lane U-turn. Road crossings and road T's get a median opening", F, (0, 0, 0)),
 ("  with every turn (the junction boxes the avenue mods already paint).", F, (0, 0, 0)),
 ("- Lane dashes between the two lanes of each half, the median between the directions.", F, (0, 0, 0)),
 ("", F, 0),
 ("What you will notice", FB, (0, 0, 0)),
 ("- A lot on one side reaches the other direction at the next junction or the avenue end.", F, (0, 0, 0)),
 ("- Old cities convert on load. An avenue the mod cannot convert whole (it turns into two", F, (0, 0, 0)),
 ("  parallel roads, rare stock junctions) stays as today, so one-way and two-way lanes never meet.", F, (0, 0, 0)),
 ("- A game without the mod sees stock avenues again (the saved pieces stay stock).", F, (0, 0, 0)),
 ("", F, 0),
 ("First step, then your calls", FB, (150, 0, 0)),
 ("- One test before any art: failed trips in Seoul with one-way halves in routing only.", F, (0, 0, 0)),
 ("- Boulevards: keep their lanes, or 2 lanes one way per outer row too?", F, (0, 0, 0)),
 ("- English-UK: drive on the left there (mirrored), or on the right everywhere?", F, (0, 0, 0))]
for t, f, c in lines:
    if t: d.text((tx, ty), t, font=f, fill=c)
    ty += 26 if f is FB else 22
im.save(sys.argv[1]); print(sys.argv[1], im.size)
