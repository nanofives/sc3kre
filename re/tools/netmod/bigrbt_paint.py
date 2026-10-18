#!/usr/bin/env python3
r"""bigrbt_paint.py - ground art of the automatic 3x3 roundabout as one world scene (task bigrbt, 2026-10-17).

The block is 3x3 cells, world lane units 0..768 (cell = 256), cell (0, 0) at the origin, x right / z down as the
lane frames (NET_LANES.md 2.2). Every piece is one cell of this scene (diagave_paint.paint_cell unprojects each
output pixel to world coordinates and asks colour()), so neighbouring pieces meet exactly. Colours are SAMPLED FROM
STOCK FRAMES: road 29 for the ring and the single-road arms, 11204's median grass for the island, the corners and
the avenue medians.

Geometry (all distances in lane units):
  core      the square [CORE0, CORE1]^2 round the block centre; D = distance of a point from it
  ring      asphalt for D_I <= D <= D_O; the outer profile (edge line, gutter, sidewalk) is road 29's own profile
            beyond its asphalt boundary at offset D - D_O, PROF deep, so it ends exactly on the block edge at the
            sides (CORE0 - D_O - PROF = 0). Cars (bigrbt.py lanes) run the stock lane slots: x 80 in the side cells,
            the r175 curves round the centre cell's corners in the corner cells, D 194..200 from the core.
  island    a circle of radius R_ISL about the block centre (island="core": D < D_I instead): a yellow edge line
            (29's centre line pixels), gutter, a concrete apron, then 11204's median grass. The ring asphalt runs
            from the outer boundary to the island; past the cars' lane (29's outer lane profile) it is the lane
            reflected back and forth (fill="fold")
  arms      a straight road (29) or an avenue half (carriageway of 29, grass median on the partner side) entering
            through one boundary cell edge; it exists inside its own block cell only. A point is asphalt when it is
            inside the ring's or any arm's asphalt; else it takes the profile of the NEAREST asphalt edge at its
            distance (ring: 29's high-side profile; arm: its own stock pixels), so curbs follow the union; beyond
            PROF it is grass. An arm's markings stop at the ring edge; give-way dashes across its inbound half there.
"""
import math

from netmod import diagave_paint as DP
from netmod import lanelines as LL

CORE0, CORE1 = 274.0, 494.0
D_O = 229.0                       # ring asphalt outer boundary (29.1's high-side boundary x 211 maps here)
D_I = 135.0                       # ring asphalt inner boundary, island "core" (island edge line starts inside it)
R_ISL = 250.0                     # island "circle": radius about the block centre (the lanes run 304..356 from it)
PROF = 45.0                       # outer profile depth: CORE0 - D_O - PROF = 0, the block edge at the sides
RING_B = 211.0                    # 29 state 1: asphalt boundary on its high-x side (edge line at 218..222)
YELLOW = (130.0, 138.0)           # 29 state 1: centre line x range at zoom 4 (prof2 measurement)
GIVEWAY = (0.0, 7.0)              # give-way band: this far outside the ring asphalt, inside an arm's asphalt
DASH = (24.0, 13.0)               # period, on (lane units across the arm)
GRASS_FROM = 14.0                 # an avenue median: grass this far from the carriageway's asphalt boundary

# 29's asphalt boundaries per state across its cut (local z for state 0, local x for state 1), chosen so the white
# edge line sits at offset 7..11 outside them on both sides, as on the ring (measured at zoom 4, prof2.py: state 1
# edge lines x 44..48 and 218..222, centre 130..138; state 0 is state 1 turned: z = 255 - x)
ARM_B = {1: (55.0, 211.0), 0: (44.0, 200.0)}
ARM_C = {1: 134.0, 0: 121.0}      # centre line


def _yellow(c):
    return c[3] and c[0] > 150 and c[2] < 110 and c[0] - c[2] > 50


def core_d(X, Z):
    dx = max(CORE0 - X, 0.0, X - CORE1)
    dz = max(CORE0 - Z, 0.0, Z - CORE1)
    return math.hypot(dx, dz)


_SIDE = CORE1 - CORE0
_CRUN = {}
_ARC = 512.0 - _SIDE               # each quarter (side + arc) is 512 long: a 90 degree turn moves t by
_ARC_R = _ARC / (math.pi / 2.0)   # a multiple of road 29's 256 period, so a piece turned to another corner
                                  # samples the same pixels (the canonical pieces equal the scene)


def ring_t(X, Z):
    """Perimeter coordinate round the core (counter-clockwise on the lane frame: N side going -x first)."""
    if Z < CORE0 and CORE0 <= X <= CORE1:                          # N
        return CORE1 - X
    if X < CORE0 and Z < CORE0:                                    # NW
        return _SIDE + _ARC_R * math.atan2(CORE0 - X, CORE0 - Z)
    if X < CORE0 and CORE0 <= Z <= CORE1:                          # W
        return _SIDE + _ARC + (Z - CORE0)
    if X < CORE0 and Z > CORE1:                                    # SW
        return 2 * _SIDE + _ARC + _ARC_R * math.atan2(Z - CORE1, CORE0 - X)
    if Z > CORE1 and CORE0 <= X <= CORE1:                          # S
        return 2 * _SIDE + 2 * _ARC + (X - CORE0)
    if X > CORE1 and Z > CORE1:                                    # SE
        return 3 * _SIDE + 2 * _ARC + _ARC_R * math.atan2(X - CORE1, Z - CORE1)
    if X > CORE1 and CORE0 <= Z <= CORE1:                          # E
        return 3 * _SIDE + 3 * _ARC + (CORE1 - Z)
    if X > CORE1 and Z < CORE0:                                    # NE
        return 4 * _SIDE + 3 * _ARC + _ARC_R * math.atan2(CORE0 - Z, X - CORE1)
    return 0.0


def stock(pid, st, z, r, x, zl):
    """DP.STOCK, stepping toward the tile centre when the point lands on a transparent frame-border pixel (the stock
    frames leave some edge pixels to the neighbour cell)"""
    x, zl = min(255.6, max(0.4, x)), min(255.6, max(0.4, zl))
    for _ in range(12):
        c = DP.STOCK(pid, st, z, r, x, zl)
        if c[3]:
            return c
        x, zl = x + (128.0 - x) * 0.03, zl + (128.0 - zl) * 0.03
    return c


def s29(z, r, xp, t, o):
    """road 29 at cut x' = xp of its state-1 profile (a road along z), position t along it, in sector o (0 E, 1 S,
    2 W, 3 N about the block centre: |dx| > |dz| is E / W). Sector o samples 29 at state 1 + o with the point turned
    o times ((x, z) -> (256 - z, x), the lanekit / view rotation), so the grain follows the ring and a piece turned to
    another sector shows exactly the pixels of the scene there (stock 29 at state 1 + o in view v = state 1 in view
    v + o, measured 1200 / 1200 points; 29's slots k and k + 2 differ in their dither, so turning by two is not free)."""
    x, zz = xp, t % 256.0
    for _ in range(o):
        x, zz = 256.0 - zz, x
    return stock(29, (1 + o) % 4, z, r, x, zz)


def sector(X, Z):
    dx, dz = X - 384.0, Z - 384.0
    if abs(dx) > abs(dz):
        return 0 if dx > 0 else 2
    return 1 if dz > 0 else 3


# ------------------------------------------------------------------------------------------------ arms

SIDES = {0: "x-", 1: "z-", 2: "x+", 3: "z+"}       # SIMNTWRK dir index (NET_LANES.md 1.1)


class Arm:
    """An arm through the outer edge of block cell `cell` on world side `side` (0 x-, 1 z-, 2 x+, 3 z+).
    kind 'road' (stock 29) or 'avenue' (a half of 11204: median on the side toward `partner`, a world side)."""

    def __init__(self, cell, side, kind="road", partner=None):
        self.cell, self.side, self.kind, self.partner = cell, side, kind, partner
        self.st = 0 if side in (0, 2) else 1                       # 29 along x / along z
        self.lo, self.hi = ARM_B[self.st]
        self.c = ARM_C[self.st]
        # the inbound lane's slot in the cell frame: W z 80, N x 175, E z 175, S x 80 (bigrbt.py LANES)
        self.in_high = side in (1, 2)
        # median side across the cut: toward +across (z+ / x+ partner) = high
        self.med_high = None if kind == "road" else partner in (2, 3)

    def local(self, X, Z):
        """-> (across, depth from the block edge) or None outside this arm's block cell"""
        cx, cz = self.cell
        if not (cx * 256 <= X < cx * 256 + 256 and cz * 256 <= Z < cz * 256 + 256):
            return None
        across = (Z - cz * 256) if self.st == 0 else (X - cx * 256)
        depth = {0: X, 1: Z, 2: 768.0 - X, 3: 768.0 - Z}[self.side]
        return across, depth

    def dist(self, s):
        """signed distance from the carriageway's asphalt (negative inside)"""
        if s < self.lo:
            return self.lo - s
        if s > self.hi:
            return s - self.hi
        return -min(s - self.lo, self.hi - s)

    def _row(self, z, r, X, Z):
        """sample(t) of 29 across its cut at this point's position along the road"""
        a = (X if self.st == 0 else Z) % 256.0
        if self.st == 0:
            return lambda t: stock(29, 0, z, r, a, t)
        return lambda t: stock(29, 1, z, r, t, a)

    def centre_run(self, z, r):
        """(lane_bins profile, (lo, hi)) of 29's centre line across its cut at this zoom and view: the non-lane run
        nearest the profile centre (the yellow line's own footprint), None when no lane shows (low zooms)"""
        key = (29, self.st, z, r)
        if key not in _CRUN:
            if self.st == 0:
                samp = lambda t, a: stock(29, 0, z, r, a, t)          # noqa: E731
            else:
                samp = lambda t, a: stock(29, 1, z, r, t, a)          # noqa: E731
            alongs = [2.0 + 252.0 * k / 63.0 for k in range(64)]
            prof = DP.lane_bins(("bigrbt",) + key, samp, 0.0, 256.0, 128, alongs)
            # the yellow line's own footprint: cut positions near the centre where most samples along are yellow
            yel = [i for i in range(128) if abs(1.0 + i * 2.0 - self.c) < 30.0 and
                   sum(1 for al in alongs if _yellow(samp(1.0 + i * 2.0, al))) >= 0.5 * len(alongs)]
            run = (min(yel) * 2.0, max(yel) * 2.0 + 2.0) if yel else None
            _CRUN[key] = (prof, run)
        return _CRUN[key]

    def sample(self, z, r, X, Z, s=None):
        c = stock(29, self.st, z, r, X % 256.0, Z % 256.0)
        if self.kind != "avenue" or s is None:
            return c
        # owner 2026-10-17: on an avenue the lane line is WHITE DASHED (lanelines.py), single roads keep yellow
        prof, run = self.centre_run(z, r)
        if run is None or not (run[0] <= s < run[1]):
            return c
        row = self._row(z, r, X, Z)
        along = (X if self.st == 0 else Z) / 256.0

        def fill():
            f = DP.mirror(prof, row, s)
            return f if f is not None else c
        return LL.dashed(z, X / 256.0, Z / 256.0, along, True, fill)

    def profile(self, z, r, X, Z, s, d, wx, wz):
        """the arm's colour at offset d outside its asphalt, on the side of cut position s"""
        high = s > self.hi
        if self.med_high is not None and high == self.med_high and d > GRASS_FROM:
            return DP.pick("grass", z, wx, wz)
        sp = self.hi + d if high else self.lo - d
        xl, zl = (X % 256.0, sp) if self.st == 0 else (sp, Z % 256.0)
        return stock(29, self.st, z, r, xl, zl)

    def inbound(self, s):
        return (s > self.c + 8.0) if self.in_high else (s < self.c - 8.0)


# ------------------------------------------------------------------------------------------------ the scene

class Roundabout3:
    """The 3x3 roundabout with `arms` (list of Arm)."""

    def __init__(self, arms=(), island="circle", fill="fold"):
        self.arms = list(arms)
        self.island_kind = island
        self.fill = fill

    def ring_asphalt(self, z, r, D, t, wx, wz, o):
        u = D_O - D
        if u < RING_B - 152.0:                          # the outer lane: 29.1's lane x 211..152 (the cars, D 194..200)
            return s29(z, r, RING_B - u, t, o)
        if self.fill == "fold":                         # inner part: the lane reflected back and forth
            k = (u - (RING_B - 152.0)) % 96.0
            return s29(z, r, 152.0 + (k if k < 48.0 else 96.0 - k), t, o)
        return DP.pick("asphalt", z, wx, wz)            # inner part: 29's asphalt palette, no tyre tracks

    def island(self, z, r, a, t, wx, wz, o):
        """a = depth inside the island edge"""
        if a < 6.5:                                     # yellow edge line
            return s29(z, r, YELLOW[0] + (YELLOW[1] - YELLOW[0]) * a / 6.5, t, o)
        if a < 14.5:                                    # gutter into the curb (29's low-side x 44 -> 36)
            return s29(z, r, 44.0 - (a - 6.5), t, o)
        if a < 32.0:                                    # concrete apron (29's sidewalk, x 34..16)
            return s29(z, r, 34.0 - (a - 14.5), t, o)
        return DP.pick("grass", z, wx, wz)

    def colour(self, z, r, wx, wz):
        X, Z = wx * 256.0, wz * 256.0
        D = core_d(X, Z)
        t = ring_t(X, Z)
        o = sector(X, Z)
        a_isl = (R_ISL - math.hypot(X - 384.0, Z - 384.0)) if self.island_kind == "circle" else D_I - D
        if a_isl > 0:
            ti = math.atan2(Z - 384.0, X - 384.0) * (512.0 / (math.pi / 2.0))   # 512 per quarter, as t
            return self.island(z, r, a_isl, ti, wx, wz, o)
        dR = D - D_O
        here = []
        for a in self.arms:
            loc = a.local(X, Z)
            if loc is not None:
                here.append((a.dist(loc[0]), a, loc[0]))
        inside = [h for h in here if h[0] < 0]
        if dR < 0:
            return self.ring_asphalt(z, r, D, t, wx, wz, o)
        if inside:
            if len(inside) > 1:                         # two arms cross (a corner with both): plain asphalt
                return self.ring_asphalt(z, r, D_O - 30.0 - (abs(dR) % 40.0), t, wx, wz, o)
            d, a, s = inside[0]
            if z >= 3 and GIVEWAY[0] <= dR < GIVEWAY[1] and a.inbound(s) and (s % DASH[0]) < DASH[1]:
                return DP.pick("white", z, wx, wz)
            return a.sample(z, r, X, Z, s)
        best = min(here, key=lambda h: h[0]) if here else None
        d = min(dR, best[0]) if best else dR
        if d > PROF:
            return DP.pick("grass", z, wx, wz)
        if best is None or dR <= best[0]:
            return s29(z, r, RING_B + dR, t, o)
        return best[1].profile(z, r, X, Z, best[2], best[0], wx, wz)
