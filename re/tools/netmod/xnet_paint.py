#!/usr/bin/env python3
r"""xnet_paint.py - art of the diagonal level crossing and the diagonal underpass (task diagxnet, round 2026-11-15b,
xsect 68 69 72 73; owner 2026-11-15: "Yes, build them" on verify/diagxnet/owner_shots/mock_sheet_v1.png, stop lines
"Keep them").

Both looks are world scenes on the diagave / diagbv painters' own band elements (diagave_paint.DiagEl, DiagBEl here =
diagbv_paint.Band), so a crossing cell meets the band's other cells exactly.

RailX (look 1): the band crossed by a rail along x on row m (stock 69 at state 1 / rail 44 at state 0 there).
  carriageway        the band's own asphalt and lane lines; where stock 69 draws its track panel (lz runs measured per
                     zoom and view, `track_rows`: the stock frames place the tracks a few units apart per view, and 44
                     matches 69 in every view) the panel replaces it; a white stop line STOP lane units before the
                     tracks on each carriageway's approach side (right-hand: the high p = x - z carriageway drives +q)
  sidewalk / kerb /  rail on ballast (44) inside the track strip, else the band's own pixel
  median
  outside the band   rail 44 (the line goes on through the outer cells' empty halves)
  Painted on the 69 frame (`paint_rail_cell`), so the extra pixel row stock rail frames have (65 rows, the 39 diamond
  has 64) is drawn too: no rim at the cell edge.

Underpass (look 2): the band under a highway deck (two rows along x, or two columns along z). Per cell the stock
crossing frame (15098 on a 15051 highway, 11258 on 73) at the cell's own state and view is the canvas, so deck top,
slab edge and outer walls are stock pixels lit as stock; layer 1 = the deck top plus this cell's deck, slab and wall
pixels (paint_under_cell: the game draws it after the highway cells beside it). Every opaque pixel
is followed down its view ray from the slab's underside (a point at height e, zoom-3 px, projects where the ground
point (u - e/32, v + e/32) does; NET_ART.md): the first solid it meets is what the eye sees.
  the ray is over the deck at the slab height   keep the stock pixel (deck top, slab edge)
  it meets a deck cell outside the band         just after crossing the deck's outer edge: the solid twin's own outer
                                                wall as drawn there (`_twin_px`); else an abutment wall along the
                                                band's edge, drawn with the twin's end face at that height
  it reaches the ground                         the band scene there, shaded SHADE under the deck
Measured on stock 15098 / 15051: slab underside at e = 30, deck top 32.
"""
import contextlib
import math
import os

from PIL import Image

from netmod import netart as NA
from netmod import diagave_paint as P
from netmod import diagbv_paint as DP

SQ2 = math.sqrt(2.0)
RAIL_STATE = 1          # 69 at state 1: rail along x (xsect 68 grid: 69.1)
RAIL44_STATE = 0        # 44 at state 0: rail along x (xsect 68 grid: 44.0)
RAIL_PAD = 9            # lane units of rail beside each track panel run
STOP = (10.0, 22.0)     # stop line, lane units before the track strip
H_SLAB = 30.0           # deck slab underside, zoom-3 px above ground
H_TOP = 32.0            # deck top
SHADE = 0.72            # ground under the deck
SOLID = {15098: 15051, 11258: 73}
_PROF = {}


class DiagBEl:
    """Canonical diagonal boulevard: c <= x - z < c + 3, as DBV's pieces draw it (diagbv_paint.Band)."""

    kind = "diag"
    width = 3.0 / SQ2
    direction = (1.0 / SQ2, 1.0 / SQ2)
    normal = (1.0 / SQ2, -1.0 / SQ2)

    def __init__(self, c=0):
        self.c = c
        self.band = DP.Band()

    def across(self, wx, wz):
        return (wx - wz - self.c) / SQ2

    def colour(self, z, r, wx, wz):
        return self.band.colour(z, r, wx - self.c, wz)

    def median(self, z, r, wx, wz):
        p = wx - wz - self.c
        if not (1.2 <= p < 1.8):
            return None
        col = self.band.colour(z, r, wx - self.c, wz)
        return col if DP.grassy(col) else None

    def fill(self, z, r, wx, wz):
        return self.colour(z, r, wx, wz)

    def sidewalk(self, z, r):
        prof = P.strip_prof(z, r)
        return P._first_lane(prof) / SQ2, (1.0 - P._first_lane(prof, True)) / SQ2

    def cells(self):
        return lambda X, Z: X - Z - self.c in (0, 1, 2, 3)


def band_ctx(kind):
    """the diagonal boulevard painter swaps its sampler while a diagonal piece is painted (diagbv_paint.diagonal)"""
    return DP.diagonal() if kind == "db" else contextlib.nullcontext()


# ---------------------------------------------------------------- look 1: the level crossing
def track_rows(z, r):
    """per lz (0..255): True inside a track of stock 69 (state 1) in its asphalt zone in THIS view. A track = a run of
    the brownish panel (r > b + 4, majority over lx 64..192) widened by RAIL_PAD. -> (row, lo, hi)"""
    k = (z, r)
    if k not in _PROF:
        pan = []
        for i in range(256):
            n = sum(1 for lx in range(64, 193, 8) if (lambda c: c[0] > c[2] + 4)(P.STOCK(69, RAIL_STATE, z, r, lx, i + .5)))
            pan.append(n >= 9)
        runs, s0 = [], None
        for i in range(257):
            v = i < 256 and pan[i]
            if v and s0 is None:
                s0 = i
            if not v and s0 is not None:
                if i - s0 >= 12:
                    runs.append((s0, i - 1))
                s0 = None
        if not runs:                                   # zoom 0 / 1: the panel is too small to see, use zoom 4's
            _PROF[k] = track_rows(4, r)
            return _PROF[k]
        row = [any(a - RAIL_PAD <= i <= b + RAIL_PAD for a, b in runs) for i in range(256)]
        _PROF[k] = (row, min(a for a, _ in runs) - RAIL_PAD, max(b for _, b in runs) + RAIL_PAD)
    return _PROF[k]


class RailX:
    """band element `el` (a diagave_paint.Placed) crossed by a rail along x on row m"""

    def __init__(self, el, m, stop=True):
        self.el, self.m, self.stop = el, m, stop

    def colour(self, z, r, wx, wz):
        Z = math.floor(wz)
        b = self.el.call("colour", z, r, wx, wz) if self.el.inside(wx, wz, 0.36) else P.CLEAR
        if Z != self.m:
            return b
        lx, lz = (wx - math.floor(wx)) * 256.0, (wz - Z) * 256.0
        row, lo, hi = track_rows(z, r)
        in_strip = lo <= lz <= hi
        rail = P.STOCK(44, RAIL44_STATE, z, r, lx, lz)
        e = self.el
        if not e.inside(wx, wz):
            return rail if rail[3] else b
        dlo, dhi = e.edge_dist(wx, wz)
        sw = e.sidewalk(z, r)
        if e.call("median", z, r, wx, wz) is not None or dlo < sw[0] or dhi < sw[1]:
            return rail if in_strip and rail[3] else b
        if row[min(255, max(0, int(lz)))]:
            return P.STOCK(69, RAIL_STATE, z, r, 64.0 + (lx % 128.0), lz)
        if self.stop and z >= 2:
            hi_side = e.across(wx, wz) >= e.el.width / 2.0
            d = (lo - lz) if hi_side else (lz - hi)
            if STOP[0] <= d < STOP[1]:
                return P.pick("white", z, wx, wz)
        return b


def paint_rail_cell(scene, cell, out_dir, kind):
    with band_ctx(kind):
        return P.paint_cell(scene, cell, out_dir, canvas=(69, RAIL_STATE))


# ---------------------------------------------------------------- look 2: the underpass
class Underpass:
    """band element `el` under a highway deck of base 15098 (deck along x: rows m, m + 1) or 11258 (deck along z:
    columns m, m + 1); states = the base's state on the first / second row (column)"""

    def __init__(self, el, m, base, states):
        self.el, self.m, self.base, self.states = el, m, base, states
        self.along_x = base == 15098
        self._face = {}

    def deck_i(self, wx, wz):
        """0 / 1 = the deck row (column) holding (wx, wz), None = not under the deck"""
        i = math.floor(wz if self.along_x else wx) - self.m
        return i if i in (0, 1) else None

    def inside(self, wx, wz):
        return self.el.inside(wx, wz)

    def band(self, z, r, wx, wz):
        return self.el.call("colour", z, r, wx, wz) if self.el.inside(wx, wz, 0.36) else P.CLEAR

    def ground(self, z, r, wx, wz):
        c = self.band(z, r, wx, wz)
        if not c[3]:
            c = P.pick("grass", z, wx, wz)
        return (int(c[0] * SHADE), int(c[1] * SHADE), int(c[2] * SHADE), 255)

    def face(self, f):
        if f not in self._face:
            self._face[f] = open_face(self.base, f)
        return self._face[f]


def open_face(base, f):
    """local face ('u0' / 'v1') open in frame f of the crossing piece (over 600 px below the slab differ from its
    solid twin at zoom 4), else None. 15098: v1, -, -, u0; 11258: u0, v1, -, -"""
    a, (L, T) = NA.stock_frames(base)[(4, f)]
    b, (Lb, Tb) = NA.stock_frames(SOLID[base])[(4, f)]
    pa, pb = a.load(), b.load()
    W = NA.TILE_W[4]
    cnt = {"u0": 0, "v1": 0}
    for y in range(a.height):
        for x in range(a.width):
            ca = pa[x, y]
            X, Y = x - L + Lb, y - T + Tb
            cb = pb[X, Y] if 0 <= X < b.width and 0 <= Y < b.height else (0, 0, 0, 0)
            if ca[3] < 128 or (cb[3] >= 128 and max(abs(ca[i] - cb[i]) for i in range(3)) <= 8):
                continue
            s, d = 2 * (x + .5 - L) / W, 4 * (y + .5 - T) / W
            u0, v0 = (s - d) / 2, (s + d) / 2
            eu, ev = 32 * u0, 32 * (1 - v0)
            if min(eu, ev) < H_SLAB - 2:
                cnt["u0" if eu < ev else "v1"] += 1
    k = max(cnt, key=cnt.get)
    return k if cnt[k] > 600 else None


def _world(r, X0, Z0, u, v):
    uu, vv = NA.rot_uv(u, v, -r % 4)
    return X0 + (1.0 - uu), Z0 + vv


def _twin_px(sc, z, r, solid, wx, wz, e):
    """the solid twin's pixel where the deck cell holding (wx, wz) draws the 3-D point (wx, wz, e) in world view r"""
    X, Z = math.floor(wx), math.floor(wz)
    i = sc.deck_i(wx, wz)
    im, (Ls, Ts) = solid[(z, (sc.states[i] + r) & 3)]
    uu, vv = NA.rot_uv(1.0 - (wx - X), wz - Z, r)
    W = NA.TILE_W[z]
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):        # a pixel off the wall's outline: the next one in
        sx = int(math.floor((uu + vv) * W / 2 + Ls)) + dx
        sy = int(math.floor((vv - uu) * W / 4 - e * W / 64 + Ts)) + dy
        if 0 <= sx < im.width and 0 <= sy < im.height:
            c = im.getpixel((sx, sy))
            if c[3] >= 128:
                return c
    return None


def endface(sc, z, f, solid, e, t):
    """the solid twin's END face (its visible face that is not the open one) at height e, along position t"""
    other = "u0" if sc.face(f) == "v1" else "v1"
    im, (L, T) = solid[(z, f)]
    W = NA.TILE_W[z]
    t = min(0.98, max(0.02, t))
    u, v = (0.0, t) if other == "u0" else (t, 1.0)
    sx = int((u + v) * W / 2 + L + (0.5 if other == "u0" else -0.5))
    sy = int((v - u) * W / 4 - e * W / 64 + T)
    if 0 <= sx < im.width and 0 <= sy < im.height:
        c = im.getpixel((sx, sy))
        if c[3]:
            return c
    return (180, 170, 140, 255)


def march(sc, z, r, X0, Z0, u0, v0, solid, f, own=None):
    """-> (colour, hit). hit = the world point (wx, wz) of the deck or wall the pixel shows, None = it shows the ground.
    colour None = keep the stock pixel (deck top, slab edge: solid). own = this pixel of the
    cell's OWN solid twin frame (same state and view): a wall hit right after the deck's outer edge takes it first (a
    neighbour's frame draws its end face at a cell corner, which the next cell covers in game)"""
    def at(e):
        return _world(r, X0, Z0, u0 - e / 32.0, v0 + e / 32.0)
    wx, wz = at(H_SLAB)
    if sc.deck_i(wx, wz) is not None:                        # deck top or slab rim: whose is it?
        tx, tz = at(H_TOP)                                   # the top face at e = 32 (an end face's rim, between
        return None, ((tx, tz) if sc.deck_i(tx, tz) is not None else (wx, wz))   # 30 and 32, is the next cell's top)
    was_out, e = True, H_SLAB
    while e > 0.0:
        e -= 0.25
        wx, wz = at(e)
        on = sc.deck_i(wx, wz) is not None
        if on and not sc.inside(wx, wz):                     # solid: highway block or abutment
            if was_out:
                c = own if own is not None and own[3] >= 128 else _twin_px(sc, z, r, solid, wx, wz, e)
                if c is not None:
                    return c, (wx, wz)
            return endface(sc, z, f, solid, e, (wx + wz) % 1.0), (wx, wz)
        was_out = not on
    wx, wz = at(0.0)
    return (sc.ground(z, r, wx, wz) if sc.deck_i(wx, wz) is not None else sc.band(z, r, wx, wz)), None


def paint_under_cell(sc, cell, state, out_dir, kind, zooms=range(NA.ZOOMS)):
    """frames of `cell` as WORLD view r (state-0 labelling, as diagave_paint.paint_cell) on the stock crossing frame
    (state + r) & 3, plus layer 1. -> anchors

    Layer 1 = the stock layer 1 (deck top) plus every layer-0 pixel that shows the deck, the slab or a wall OF THIS
    CELL (hit point inside the cell's own square; for the deck, the point at the top face e = 32), at the layer-0
    anchor. Why (owner review 2026-11-16, case 72 view 0, a beige wedge on the near wall right of the opening): the
    game draws every layer 1 AFTER the plain highway cells (15051 / 73, one layer, each frame carrying an end face that
    the next highway cell normally covers), and those after the 2-layer pieces' layer 0. Measured on the in-game shots
    (verify/diagxnet/wedge/gameorder.py, case 72, zoom 4): with that order the offline composite equals the game shot
    in view 0 (0 pixels off by more than 40 after, 13 before); painter order with layer 1 interleaved does not
    reproduce it. So a neighbour's end face landed on our layer-0 wall; stock 15098 uses that overdraw for the
    abutments of its straight opening. The layer-1 copy of the walls covers it. A pixel that belongs to the next cell
    (its wall, its end face, the 30..32 rim of an end face) stays out of layer 1: drawn last, it would show over that
    cell (first build of this fix: 1 px beige seams across the deck at the band edges). The ground under the opening
    stays layer 0 only.
    """
    os.makedirs(out_dir, exist_ok=True)
    X0, Z0 = cell
    anchors = {}
    solid = NA.stock_frames(SOLID[sc.base])
    with band_ctx(kind):
        for z in zooms:
            W = NA.TILE_W[z]
            for r in range(NA.ROTS):
                f = (state + r) & 3
                im0, (L, T) = NA.stock_frames(sc.base)[(z, f)]
                tw, (Lt, Tt) = solid[(z, f)]
                out = im0.copy()
                px = out.load()
                top = Image.new("RGBA", out.size, (0, 0, 0, 0))
                pt = top.load()
                for y in range(out.height):
                    for x in range(out.width):
                        if px[x, y][3] < 128:
                            continue
                        s_, d_ = 2 * (x + .5 - L) / W, 4 * (y + .5 - T) / W
                        xt, yt = x - L + Lt, y - T + Tt
                        own = tw.getpixel((xt, yt)) if 0 <= xt < tw.width and 0 <= yt < tw.height else None
                        col, hit = march(sc, z, r, X0, Z0, (s_ - d_) / 2, (s_ + d_) / 2, solid, f, own)
                        if col is not None:
                            px[x, y] = col
                        if hit is not None and math.floor(hit[0]) == X0 and math.floor(hit[1]) == Z0:
                            pt[x, y] = px[x, y]
                name = NA.frame_name(z, r)
                out.save(os.path.join(out_dir, name))
                anchors[name] = [L, T]
                l1 = NA.stock_frames(sc.base, 1).get((z, f))
                if l1 and l1[1] is not None:                 # stock deck top over our copy, at the layer-0 anchor
                    im1 = l1[0].convert("RGBA")
                    lay = Image.new("RGBA", top.size, (0, 0, 0, 0))
                    lay.paste(im1, (L - l1[1][0], T - l1[1][1]), im1)
                    top.alpha_composite(lay)
                top.save(os.path.join(out_dir, NA.frame_name(z, r, 1)))
                anchors[NA.frame_name(z, r, 1)] = [L, T]
    return anchors
