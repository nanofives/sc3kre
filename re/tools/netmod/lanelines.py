#!/usr/bin/env python3
r"""lanelines.py - white dashed lane lines for avenues (owner, 2026-10-17: "on avenues instead of yellow lines they
should be white striped lines for every lane"). Shared by every avenue-program painter; copy it, do not fork it.

Rule: on any road with a median (stock avenue 11204, the diagonal avenue, the boulevard, avenue arms of junctions and
roundabouts) every lane boundary inside a carriageway is a WHITE DASHED line; single roads keep their yellow centre
line. Where a single road meets an avenue its yellow line still runs to the median nose.

Pattern, measured on stock elevated highway 73 (zoom 4, state 0, the deck's dash components at screen x 45.7, 61.4,
77.4, 93.4: one every 16 px = 4 per cell): period 0.25 cell along the road, dash 0.375 of it. The phase comes from the
WORLD along-coordinate, so dashes run on across cells and pieces (dash centred in its period):
    road along x: along = x        road along z: along = z        diagonal: along = (x + z) / sqrt(2)
Footprint: the stock yellow centre line's own cross-section (its run in the strip profile), so the line keeps the stock
width in every zoom and view. Colour: the dash pixels of 73 at that zoom. None at zoom 0 and 1 (no stock line there).
"""
import math

from netmod import netart as NA

DASH_PERIOD = 0.25          # cells along the road
DASH_ON = 0.375             # painted share of a period
MIN_ZOOM = 2
_PAL = {}


def dash_on(along):
    """True where a dash is painted, `along` in world cells along the road (see the module docstring). Each dash is
    centred in its period, so the pattern is the same whichever way a piece's lane frame runs (a stock frame whose
    lane x runs against world x still meets its neighbours)."""
    return abs((along / DASH_PERIOD) % 1.0 - 0.5) < DASH_ON / 2.0


def along_diag(wx, wz):
    return (wx + wz) / math.sqrt(2.0)


def white_palette(z):
    """the dash whites of stock highway 73 at zoom z (all four states), components of 3+ light pixels"""
    if z in _PAL:
        return _PAL[z]
    out = []
    for s in range(4):
        im, _ = NA.stock_frames(73)[(z, s)]
        px = im.load()
        W, H = im.size
        lit = {(x, y) for y in range(H) for x in range(W)
               if px[x, y][3] and min(px[x, y][:3]) >= 170 and max(px[x, y][:3]) - min(px[x, y][:3]) < 30}
        seen = set()
        for p in sorted(lit):
            if p in seen:
                continue
            stack, comp = [p], []
            seen.add(p)
            while stack:
                q = stack.pop()
                comp.append(q)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        r = (q[0] + dx, q[1] + dy)
                        if r in lit and r not in seen:
                            seen.add(r)
                            stack.append(r)
            if len(comp) >= 3:
                out += [px[x, y][:3] + (255,) for (x, y) in comp]
    _PAL[z] = out or [(205, 206, 205, 255)]
    return _PAL[z]


def white(z, wx, wz):
    pal = white_palette(z)
    h = (int(wx * 512) * 73856093) ^ (int(wz * 512) * 19349663) ^ (z * 83492791)
    return pal[h % len(pal)]


def dashed(z, wx, wz, along, on_line, fill):
    """Colour of a pixel of a lane line's footprint: white when a dash covers `along` (world cells) and the stock
    pixel there was line (`on_line`), else `fill()` (the lane asphalt, e.g. the mirror fill). Below MIN_ZOOM: fill()."""
    if z >= MIN_ZOOM and on_line and dash_on(along):
        return white(z, wx, wz)
    return fill()
