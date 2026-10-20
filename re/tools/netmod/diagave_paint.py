#!/usr/bin/env python3
r"""diagave_paint.py - the diagonal avenue's ground art as world scenes (task diagave, 2026-10-17).

Every piece of the avenue is one cell of a scene drawn in WORLD coordinates (x, z in cells; axis 0, the down-right
diagonal, band offset c = 0: staircase A is the strip 0 <= x - z < 1, B is 1 <= x - z < 2). Each output pixel of each
zoom x rotation slot is unprojected to the cell's lane frame (netpaint.paint's method), moved to world coordinates and
coloured by the scene, which SAMPLES THE STOCK PIECES' OWN FRAMES at the same screen position: the diagonal road 35
(the cell's stock state for that strip position), road 29 for crossing roads. So a scene pixel equals the stock pixel
wherever the scene shows plain stock road, and every piece made from the same scene meets its neighbours exactly.

Scenes: StraightAvenue (median grass where the two inner sidewalks meet), Junction (road 29 with the avenue's halves
over it as asphalt, crosswalks, a stem keeps the far curb), Merge (one carriageway ends: its outer curb tapers into
the other one, the median ends where the taper starts).
"""
import math
import os

from PIL import Image

from netmod import lanelines as LL
from netmod import netart as NA
from netmod import lanelines as LL

DIAG_STATE = {0: 2, 1: 0}          # axis 0: a cell at d (x - z - strip offset) 0 / 1 of a strip holds 35 in this state
WHITE_LINES = ((8.0, 15.0), (32.0, 38.0))     # crosswalk lines, lane units in from the edge (stock 43, zoom 4)


class Stock:
    """Colour of a stock piece at a lane-frame point (x, z in 0..256 of the cell) in view rotation r."""

    def __init__(self, layer=0):
        self.fr = {}
        self.layer = layer

    def frames(self, pid):
        if pid not in self.fr:
            self.fr[pid] = {k: (im, im.load(), LT) for k, (im, LT) in NA.stock_frames(pid, self.layer).items()}
        return self.fr[pid]

    def __call__(self, pid, state, z, r, x, zl):
        im, px, (L, T) = self.frames(pid)[(z, (state + r) & 3)]
        u, v = NA.rot_uv(1.0 - x / 256.0, zl / 256.0, r)
        X, Y = NA.project(z, u, v)
        X, Y = int(math.floor(X + L)), int(math.floor(Y + T))
        if 0 <= X < im.width and 0 <= Y < im.height:
            return px[X, Y]
        return (0, 0, 0, 0)


STOCK = Stock()
STOCK1 = Stock(1)                  # task diagx: layer 1 (11204's front trees)
CLEAR = (0, 0, 0, 0)


def light(c):
    return c[3] and min(c[:3]) >= 140 and max(c[:3]) - min(c[:3]) <= 40


def asphaltish(c):
    return c[3] and max(c[:3]) < 135 and max(c[:3]) - min(c[:3]) < 22


_PAL = {}


def palette(kind, z):
    """'grass' (11204's median grass), 'asphalt' (road 29's asphalt), 'white' (29's brightest paint)"""
    k = (kind, z)
    if k in _PAL:
        return _PAL[k]
    out = []
    if kind == "grass":
        im, (L, T) = NA.stock_frames(11204, 0)[(z, 0)]
        W = NA.TILE_W[z]
        px = im.load()
        for y in range(im.height):
            for x in range(im.width):
                gx = x - (0 - L)
                if gx < 0 or gx > W or y < T - (gx / 2.0 if gx <= W / 2 else (W - gx) / 2.0):
                    continue
                r, g, b, a = px[x, y]
                if a and g > r + 12 and g > b + 8 and g < 150:
                    out.append((r, g, b, 255))
        out = out or [(74, 105, 57, 255)]
    elif kind == "asphalt":
        for s in range(4):
            im, _ = NA.stock_frames(29)[(z, s)]
            out += [c for c in im.getdata() if asphaltish(c)]
        out = [(c[0], c[1], c[2], 255) for c in out] or [(90, 93, 98, 255)]
    elif kind == "concrete":                            # task diagx: stock 35's light sidewalk pixels (median noses)
        im, _ = NA.stock_frames(35)[(z, 0)]
        out = [(c[0], c[1], c[2], 255) for c in im.getdata() if light(c)] or [(170, 170, 165, 255)]
    else:
        best = (0, 0, 0, 0)
        for s in range(4):
            im, _ = NA.stock_frames(29)[(z, s)]
            for c in im.getdata():
                if c[3] and sum(c[:3]) > sum(best[:3]):
                    best = c
        out = [best]
    _PAL[k] = out
    return out


def pick(kind, z, wx, wz):
    pal = palette(kind, z)
    h = (int(wx * 512) * 73856093) ^ (int(wz * 512) * 19349663) ^ (z * 83492791)
    return pal[h % len(pal)]


# ------------------------------------------------------------------------------------------------ geometry

def diag(strip, wx, wz, z, r, cell=None):
    """Stock 35 at world point (wx, wz) as a lone staircase occupying strip offset `strip` would draw it. `cell`
    forces the cell whose frame is read (the point's own cell by default)."""
    X, Z = cell if cell else (math.floor(wx), math.floor(wz))
    d = X - Z - strip
    if d not in DIAG_STATE:
        return CLEAR
    c = STOCK(35, DIAG_STATE[d], z, r, (wx - X) * 256.0, (wz - Z) * 256.0)
    if c[3] or cell or not (strip <= wx - wz < strip + 1):
        return c
    # a point of the strip on its cell's frame border: the stock leaves that pixel to the neighbour cell's frame
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d2 = X + dx - (Z + dz) - strip
        if d2 in DIAG_STATE:
            c = STOCK(35, DIAG_STATE[d2], z, r, (wx - X - dx) * 256.0, (wz - Z - dz) * 256.0)
            if c[3]:
                return c
    return CLEAR


def diag_at(strip, p_rel, q, z, r):
    """Stock 35 of strip `strip` at offset p_rel across it (0 = its x - z = strip edge) and position q = x + z."""
    p = strip + p_rel
    wx, wz = (p + q) / 2.0, (q - p) / 2.0
    return diag(strip, wx, wz, z, r)


_SEAM = {}


def seam(z, r):
    """(centre, half width) in x - z units of the light run where A's and B's inner sidewalks meet, minus one pixel each
    side (the curb pixel stays): the median grass band, measured on the straight avenue at this zoom and view."""
    k = (z, r & 1)
    if k in _SEAM:
        return _SEAM[k]
    q = 3.0
    step = 1.0 / 512.0
    ps = [1.0 + i * step for i in range(-200, 201)]
    run = [p for p in ps if light(diag(0 if p < 1 else 1, (p + q) / 2.0, (q - p) / 2.0, z, r))]
    W = NA.TILE_W[z]
    px = 1.0 / (W / 2.0) if r % 2 == 0 else 1.0 / (W / 4.0)     # one pixel in x - z units (vertical / flat strip)
    if not run:
        _SEAM[k] = (1.0, 0.0)
    else:
        lo, hi = run[0], run[-1]
        for i in range(len(run) - 1):                   # the contiguous run that holds p = 1
            if run[i + 1] - run[i] > 2 * step and run[i] < 1.0:
                lo = run[i + 1]
            if run[i + 1] - run[i] > 2 * step and run[i] >= 1.0:
                hi = run[i]
                break
        _SEAM[k] = ((lo + hi) / 2.0, max(0.0, (hi - lo) / 2.0 - px))
    return _SEAM[k]


# ------------------------------------------------------------------------------------------------ scenes

LANE_FRAC = 0.9                    # a cut position is lane when this share of its samples along the road is asphalt
_PROF = {}


def lane_bins(key, sample, lo, hi, bins, alongs):
    """Which of `bins` equal cut positions over [lo, hi) across a road are lane asphalt, from sample(t, a) at the
    `alongs` positions along it. Measured once per key (piece, zoom, view): the profile is fixed, so every row of a
    fill reflects about the same edge (a per-row edge search follows the texture's specks and leaves streaks)."""
    if key not in _PROF:
        w = (hi - lo) / bins
        _PROF[key] = (lo, w, [sum(1 for a in alongs if lane_grey(sample(lo + (i + 0.5) * w, a))) >= LANE_FRAC * len(alongs)
                              for i in range(bins)])
    return _PROF[key]


def mirror(prof, sample, t0):
    """Asphalt for a marking / curb / sidewalk point at cut position t0 (sample(t) -> colour along this row): the cut
    reflected about the nearer lane edge of the non-lane run holding t0, so the fill continues the lane texture right
    beside it (a fixed shift lands on the darker tyre tracks). None when t0 is lane or no lane is in reach."""
    lo, w, lane = prof
    n = len(lane)
    i = int(math.floor((t0 - lo) / w))
    if 0 <= i < n and lane[i]:
        return None
    a = i
    while 0 <= a < n and not lane[a]:
        a -= 1
    b = i
    while 0 <= b < n and not lane[b]:
        b += 1
    left = lo + (a + 1) * w if a >= 0 else None             # the lane edge below t0, if there is lane below
    right = lo + b * w if b < n else None
    if left is None and right is None:
        return None
    def lane_at(t):
        return lane[min(n - 1, max(0, int(math.floor((t - lo) / w))))]

    def opaque(t, toward):
        for k in range(8):                                  # a frame-border pixel is empty: step on into the lane
            c = sample(t + toward * k * w)
            if c[3]:
                return c
        return None

    if right is None or (left is not None and t0 - left <= right - t0):
        t = max(lo + 0.5 * w, 2 * left - t0)
        while not lane_at(t) and t < left:
            t += w                                          # a run wider than the lane beside it: stay inside lane
        return opaque(min(t, left - 0.5 * w), -1.0)
    t = min(lo + (n - 0.5) * w, 2 * right - t0)
    while not lane_at(t) and t > right:
        t -= w
    return opaque(max(t, right + 0.5 * w), 1.0)


def strip_prof(z, r):
    """lane_bins of stock 35 across its strip (p_rel 0..1)"""
    return lane_bins((35, z, r), lambda t, a: diag_at(0, t, a, z, r), 0.0, 1.0, 128,
                     [0.05 + 4.0 * k / 97.0 for k in range(97)])


def centre_line(z, r):
    """(centre, half width) in p_rel of stock 35's yellow centre line at this zoom and view: the non-lane run of the
    strip profile nearest its middle. None when no such run (the line is under a pixel)."""
    lo, w, lane = strip_prof(z, r)
    n = len(lane)
    mids = [i for i in range(n) if not lane[i] and 0.3 < lo + (i + 0.5) * w < 0.7]
    if not mids:
        return None
    a = b = min(mids, key=lambda i: abs(i + 0.5 - n / 2.0))
    while a > 0 and not lane[a - 1]:
        a -= 1
    while b < n - 1 and not lane[b + 1]:
        b += 1
    if (b - a + 1) * w > 0.3:
        return None                                     # no lane in the profile at all (zoom 0): no line to move
    return lo + (a + b + 1) * w / 2.0, (b - a + 1) * w / 2.0


def lane_fill(strip, wx, wz, z, r):
    """Stock asphalt for a point of a strip whose own pixel is a marking, curb or sidewalk (same q, so the 2D texture
    along the strip is kept); a lane pixel (specks included) stays."""
    p, q = wx - wz, wx + wz
    c = mirror(strip_prof(z, r), lambda t: diag_at(strip, t, q, z, r), p - strip)
    return c if c is not None else diag(strip, wx, wz, z, r)


def lane_grey(c):
    """lane asphalt only (the gutter greys 115..131 are not)"""
    return c[3] and max(c[:3]) < 118 and max(c[:3]) - min(c[:3]) < 22


def yellowish(c):
    """a stock yellow centre-line pixel or its anti-aliased edge (asphalt is bluish: blue above red)"""
    return c[3] and c[0] - c[2] > 15


def avenue_line(c, s, p, wx, wz, z, r):
    """Owner, 2026-10-17: avenues carry white dashed lane lines, no yellow. A yellow pixel of strip s becomes a white
    dash where the stock centre line's footprint meets a dash (lanelines.py), else the lane asphalt."""
    if not yellowish(c):
        return c
    fill = lambda: lane_fill(s, wx, wz, z, r)                                    # noqa: E731
    cl = centre_line(z, r)
    if cl is not None and abs(p - s - cl[0]) <= cl[1]:
        return LL.dashed(z, wx, wz, LL.along_diag(wx, wz), True, fill)
    return fill()


class StraightAvenue:
    """The joined avenue: A (0 <= p < 1) and B (1 <= p < 2) as stock 35, median grass on the inner sidewalks; with
    `median_end` set, the median stops there with a concrete nose (the stock sidewalk pixels) NOSE long."""

    median_end = None
    NOSE = 0.12

    def strip_colour(self, z, r, wx, wz, p, q):
        s = 0 if p < 1.0 else 1
        col = diag(s, wx, wz, z, r)
        cen, hw = seam(z, r)
        if light(col) and abs(p - cen) < hw:
            if self.median_end is not None and q >= self.median_end - self.NOSE:
                return col                                      # the nose: concrete
            return pick("grass", z, wx, wz)
        return avenue_line(col, s, p, wx, wz, z, r)

    def colour(self, z, r, wx, wz):
        p, q = wx - wz, wx + wz
        if p < -0.5 or p >= 2.5:
            return CLEAR
        return self.strip_colour(z, r, wx, wz, p, q)


class Merge(StraightAvenue):
    """One carriageway ends: `ends` = 'B' (A continues) or 'A'. Its outer edge moves linearly from full width at q_s to
    nothing at q_e, keeping a curb band `curb` wide (x - z units) sampled from the stock outer edge; the median ends at
    q_s and the other carriageway's inner sidewalk is asphalt until q_e. Lane divider (owner sketch, 2026-10-17): the
    continuing carriageway's yellow centre line leaves its lane at q_e and runs straight to the median nose at q_s,
    so both carriageways' own centre lines start at the nose; stock 35's own centre-line pixels, moved across."""

    def __init__(self, ends, q_s, q_e, curb=0.17, inner=0.2):
        self.ends, self.q_s, self.q_e, self.curb, self.inner = ends, q_s, q_e, curb, inner
        self.median_end = q_s

    def colour(self, z, r, wx, wz):
        p, q = wx - wz, wx + wz
        if q < self.q_s:
            return StraightAvenue.colour(self, z, r, wx, wz)
        keep, gone = ("A", "B") if self.ends == "B" else ("B", "A")
        kp = (0.0, 1.0) if keep == "A" else (1.0, 2.0)
        if q < self.q_e:
            t = (q - self.q_s) / (self.q_e - self.q_s)
            # the curb band follows the moving edge into the other strip too, so at q_e it is exactly the continuing
            # carriageway's inner sidewalk (same side of a strip, same stock profile) and nothing steps
            if gone == "B":
                edge = 2.0 - t                                  # B's outer edge moves from 2 to 1
                if p >= edge:
                    return CLEAR
                if edge - p < self.curb:
                    return diag_at(1, 1.0 - (edge - p), q, z, r)
                c = self.divider(t, p, q, z, r)
                if c is not None:
                    return c
                if p >= 1.0:
                    return lane_fill(1, wx, wz, z, r)            # B's lanes, markings dropped: they merge
            else:
                edge = t                                         # A's outer edge moves from 0 to 1
                if p < edge:
                    return CLEAR
                if p - edge < self.curb:
                    return diag_at(0, p - edge, q, z, r)
                c = self.divider(t, p, q, z, r)
                if c is not None:
                    return c
                if p < 1.0:
                    return lane_fill(0, wx, wz, z, r)
            if kp[0] <= p < kp[1]:                               # the continuing carriageway: inner side opens
                s = int(kp[0])
                near = (kp[1] - p) < self.inner if keep == "A" else (p - kp[0]) < self.inner
                cl = centre_line(z, r)
                on_line = cl is not None and abs(p - s - cl[0]) <= cl[1]
                return lane_fill(s, wx, wz, z, r) if near or on_line else diag(s, wx, wz, z, r)
            return CLEAR
        if kp[0] <= p < kp[1]:
            return diag(int(kp[0]), wx, wz, z, r)
        return CLEAR

    def divider(self, t, p, q, z, r):
        """The taper's yellow line, or None: from the median nose (p 1, t 0) to the continuing carriageway's centre
        line (t 1), straight."""
        cl = centre_line(z, r)
        if cl is None:
            return None
        cy, hw = cl
        ks = 0 if self.ends == "B" else 1                    # the strip that goes on
        pc = 1.0 + (ks + cy - 1.0) * t
        if abs(p - pc) <= hw:
            c = diag_at(ks, cy + (p - pc), q, z, r)
            if c[3]:
                return c
        return None


class CapCombo:
    """A shared cell where one carriageway starts or ends (cap piece 18004 / 1999) beside the other one: stock piece
    `pa` at state 0 (staircase A, strip 0) under stock piece `pb` at state `delta` (B, strip 1), as diagave.mid_frame
    stacked them, with the avenue's dashed lane lines. Paint it at cell (1, 0)."""

    def __init__(self, pa, pb, delta):
        self.pa, self.pb, self.delta = pa, pb, delta

    def colour(self, z, r, wx, wz):
        x, zl = (wx % 1.0) * 256.0, (wz % 1.0) * 256.0
        c = STOCK(self.pb, self.delta, z, r, x, zl)
        if not c[3]:
            c = STOCK(self.pa, 0, z, r, x, zl)
        if not c[3]:
            return CLEAR
        p = wx - wz
        return avenue_line(c, 0 if p < 1.0 else 1, p, wx, wz, z, r)


class Junction:
    """A junction cell in its own lane frame (state 0): road 29 in state `o` with stock 35 halves at `halves` over it
    as asphalt, white crosswalk lines across the road at the avenue's edge (a cell holding one half) and across the
    avenue at the road's edges, a stem's far curb (`edge`: 0 N, 1 E, 2 S, 3 W) kept."""

    def __init__(self, halves, o, edge):
        self.halves, self.o, self.edge = halves, o, edge

    def colour(self, z, r, wx, wz):
        x, zl = (wx % 1.0) * 256.0, (wz % 1.0) * 256.0
        base = STOCK(29, self.o, z, r, x, zl)
        if not base[3]:
            return CLEAR
        av = CLEAR
        for s in self.halves:
            c = STOCK(35, s, z, r, x, zl)
            if c[3]:
                av = c
        if not av[3]:
            return base
        far = self.edge
        dfar = None if far < 0 else (zl, 256.0 - x, 256.0 - zl, x)[far]
        if dfar is not None and dfar < 0.22 * 256.0 and light(base):
            return base                                          # the stem's far curb stays
        # crosswalks: across the road along the avenue's outer edge (the half's base diagonal) ...
        if len(self.halves) == 1:
            s = self.halves[0]
            dd = abs(x - zl) / math.sqrt(2.0) if s % 2 == 0 else abs(x + zl - 256.0) / math.sqrt(2.0)
            if any(a <= dd < b for a, b in WHITE_LINES) and z >= 2:
                return pick("white", z, wx, wz)
        # ... and across the avenue along the road's edges (not the stem's far edge)
        edges = (0, 2) if self.o == 0 else (1, 3)
        for e in edges:
            if e == far:
                continue
            de = (zl, 256.0 - x, 256.0 - zl, x)[e]
            if any(a <= de < b for a, b in WHITE_LINES) and z >= 2:
                return pick("white", z, wx, wz)
        if lane_grey(base):
            return base
        # road 29's centre line and sidewalks become its own asphalt, mirrored across the cut over the road (the
        # avenue's frame sampled along road 29's centre line streaks: it cuts its tyre tracks at an angle)
        alongs = [1.0 + 254.0 * k / 63.0 for k in range(64)]
        if self.o == 0:                             # the road runs along x: the cut is z
            prof = lane_bins((29, 0, z, r), lambda t, a: STOCK(29, 0, z, r, a, t), 0.0, 256.0, 128, alongs)
            c = mirror(prof, lambda t: STOCK(29, 0, z, r, x, t), zl)
        else:
            prof = lane_bins((29, 1, z, r), lambda t, a: STOCK(29, 1, z, r, t, a), 0.0, 256.0, 128, alongs)
            c = mirror(prof, lambda t: STOCK(29, 1, z, r, t, zl), x)
        if c is not None:
            return c
        return av if lane_grey(av) else pick("asphalt", z, wx, wz)


class Opening(Junction):
    """task avdiag: the far cell of a median opening (a road that meets one carriageway goes on across the median):
    the far carriageway's stock 35 half (state halves[0]) with its outer curb kept along the cut diagonal, road 29
    (state o) only inside the half, as asphalt with the avenue (Junction's rules); outside the half nothing (the
    ground drawn under, on 35's frames)"""

    def __init__(self, halves, o, end):
        Junction.__init__(self, halves, o, -1)
        self.end = end

    def colour(self, z, r, wx, wz):
        x, zl = (wx % 1.0) * 256.0, (wz % 1.0) * 256.0
        s = self.halves[0]
        av = STOCK(35, s, z, r, x, zl)
        if not av[3]:
            return CLEAR                                          # past the outer curb: no road
        dd = abs(x - zl) / math.sqrt(2.0) if s % 2 == 0 else abs(x + zl - 256.0) / math.sqrt(2.0)
        if dd < 0.16 * 256.0 and light(av):
            return av                                             # the far carriageway's outer curb stays
        if not STOCK(29, self.o, z, r, x, zl)[3]:
            return av
        return Junction.colour(self, z, r, wx, wz)


# ------------------------------------------------------------------------------------------------ painting

def paint_cell(scene, cell, out_dir, canvas=None, zooms=range(NA.ZOOMS)):
    """Frames z{z}_r{r}.png of the cell `cell` (world X, Z of its corner) of `scene`, on the frames of piece `canvas`
    (default 39: the full flat diamond; e.g. 35 at the cell's stock state for an outer cell). -> anchors dict."""
    os.makedirs(out_dir, exist_ok=True)
    cpid, cstate = canvas if isinstance(canvas, tuple) else ((canvas or NA.FULL_TILE_PIECE), 0)
    cv = NA.stock_frames(cpid)
    anchors = {}
    X0, Z0 = cell
    for z in zooms:
        for r in range(NA.ROTS):
            im0, (L, T) = cv[(z, (cstate + r) & 3)]
            w, h = im0.size
            out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            mpx, opx = im0.load(), out.load()
            full = cpid == NA.FULL_TILE_PIECE
            for y in range(h):
                for xx in range(w):
                    if full and mpx[xx, y][3] < 128:
                        continue
                    u, v = NA.unproject(z, xx + 0.5 - L, y + 0.5 - T)
                    u, v = NA.rot_uv(u, v, -r % 4)
                    lx, lz = (1.0 - u) * 256.0, v * 256.0
                    if not (-2.0 <= lx <= 258.0 and -2.0 <= lz <= 258.0):
                        continue
                    lx, lz = min(255.9, max(0.1, lx)), min(255.9, max(0.1, lz))
                    opx[xx, y] = scene.colour(z, r, X0 + lx / 256.0, Z0 + lz / 256.0)
            name = NA.frame_name(z, r)
            out.save(os.path.join(out_dir, name))
            anchors[name] = [L, T]
    return anchors


class Lone(StraightAvenue):
    """No merge: the avenue up to row `last` (the band's last full row), then only the continuing strip."""

    def __init__(self, keep, last):
        self.keep, self.last = keep, last

    def colour(self, z, r, wx, wz):
        if math.floor(wz) <= self.last:
            return StraightAvenue.colour(self, z, r, wx, wz)
        p = wx - wz
        s = 0 if self.keep == "A" else 1
        return diag(s, wx, wz, z, r) if s <= p < s + 1 else CLEAR


# canonical merges (axis 0, the band's bottom end at row 0, row z holding cells z .. z+2): the carriageway that ends,
# its taper from q_s to q_e (the longest that stays inside the cells the drags leave), and the continuing one
MERGES = {"L": ("B", 2.0, 5.0), "R": ("A", 0.0, 3.0)}


def merge_footprint(kind, rows=(-6, 5)):
    ends = MERGES[kind][0]
    cells = set()
    for z in range(rows[0], rows[1] + 1):
        xs = [z, z + 1, z + 2] if z <= 0 else ([z, z + 1] if ends == "B" else [z + 1, z + 2])
        cells |= {(x, z) for x in xs}
    return cells


def merge_cells(kind, zoom=3):
    """-> sorted cells of the canonical footprint whose art differs between the Merge scene and no merge."""
    ends, q_s, q_e = MERGES[kind]
    keep = "A" if ends == "B" else "B"
    m, n = Merge(ends, q_s, q_e), Lone(keep, 0)
    out = []
    for (X, Z) in sorted(merge_footprint(kind)):
        if not (-2 <= Z <= 3):
            continue
        diff = False
        for r in (0, 1):
            for k in range(0, 33):
                for j in range(0, 33):
                    wx, wz = X + (k + 0.5) / 33.5, Z + (j + 0.5) / 33.5
                    if m.colour(zoom, r, wx, wz) != n.colour(zoom, r, wx, wz):
                        diff = True
                        break
                if diff:
                    break
            if diff:
                break
        if diff:
            out.append((X, Z))
    return out


def _rot_cell(c, k):
    """world cell turned k states (lane frame (x, z) -> (1 - z, x) per state: cell (x, z) -> (-z - 1, x))"""
    x, z = c
    for _ in range(k % 4):
        x, z = -z - 1, x
    return (x, z)


def merge_case_footprint(axis, end, cont, rows=6):
    """DAV's axis-space convention: the band's end row at z 0 with left a 0; `end` 0 = bottom (the chain goes up from
    it), 1 = top; `cont` 'A' or 'B' continues past it. -> set of REAL cells."""
    cells = set()
    for z in range(-rows, rows + 1):
        band = z <= 0 if end == 0 else z >= 0
        if band:
            xs = [z, z + 1, z + 2]
        else:
            xs = [z, z + 1] if cont == "A" else [z + 1, z + 2]
        cells |= {(x, z) for x in xs}
    return {(-x, z) if axis else (x, z) for (x, z) in cells}


def merge_table(ids):
    """ids: {kind: [piece per canonical merge cell]} -> {(axis, end, cont): [(dx, dz, piece, state), ...]} with dx, dz
    in DAV's axis space relative to the end row's left cell; found by turning the canonical footprints until they
    coincide with the case's footprint."""
    canon = {}
    for kind in MERGES:
        ends = MERGES[kind][0]
        cont = "A" if ends == "B" else "B"
        canon[kind] = (merge_case_footprint(0, 0, cont), merge_cells(kind))
    out = {}
    for axis in (0, 1):
        for end in (0, 1):
            for cont in ("A", "B"):
                F = merge_case_footprint(axis, end, cont)
                hit = None
                win = lambda S, o: {c for c in S if max(abs(c[0] - o[0]), abs(c[1] - o[1])) <= 4}   # noqa: E731
                Fw = win(F, (0, 0))
                for kind, (Fc, Mc) in canon.items():
                    for k in range(4):
                        R = {_rot_cell(c, k) for c in Fc}
                        for tx in range(-6, 7):
                            for tz in range(-6, 7):
                                if win({(x + tx, z + tz) for (x, z) in R}, (0, 0)) == Fw:
                                    hit = (kind, k, (tx, tz))
                                    break
                            if hit:
                                break
                        if hit:
                            break
                    if hit:
                        break
                if not hit:
                    raise SystemExit("no canonical merge for case %s" % ((axis, end, cont),))
                kind, k, t = hit
                rows = []
                for i, c in enumerate(canon[kind][1]):
                    x, z = _rot_cell(c, k)
                    x, z = x + t[0], z + t[1]
                    ax = -x if axis else x
                    rows.append((ax, z, ids[kind][i], k))
                out[(axis, end, cont)] = rows
    return out


# ------------------------------------------------------------------------------------------------ crossings (task diagx)
# Two roads crossing, or one ending on the other (a T). Each road is an ELEMENT in its own canonical frame (DiagEl: the
# diagonal avenue of axis 0, strips c .. c+2 in x - z; StraightEl: stock avenue 11204 along x, rows m and m+1), placed
# in the world turned by k states and moved by whole cells. Measured 2026-10-17 (diagx, 4,000 random points, 0
# mismatches): a scene turned one state shows at view r what the unturned scene shows at view r + 1 at the point
# (wz, -wx), because a piece at state s + 1 in view r draws the frame slot of state s in view r + 1. So an axis-1
# diagonal is DiagEl turned one state, and an avenue along z is StraightEl turned one state.

SQ2 = math.sqrt(2.0)
NOSE_CELLS = 0.12 / SQ2            # the median nose, as long as StraightAvenue.NOSE (q units), measured along the road


def _rinv(wx, wz, k):
    """world point -> the point it came from before k turns (one turn: (x, z) -> (-z, x))"""
    for _ in range(k % 4):
        wx, wz = wz, -wx
    return wx, wz


def _rot(wx, wz, k):
    for _ in range(k % 4):
        wx, wz = -wz, wx
    return wx, wz


def _yellow(c):
    """a stock yellow centre-line pixel or its anti-aliased edge (asphalt is bluish: blue above red)"""
    return c[3] and c[0] - c[2] > 15


def _grassy(c):
    """11204's median grass (the test grass_palette uses)"""
    return c[3] and c[1] > c[0] + 12 and c[1] > c[2] + 8 and c[1] < 150


PAVE_IN = (48.0, 208.0)            # stock 43's clean asphalt, lane units (its crosswalks end at 38, corners at 40)


def paved(z, r, wx, wz):
    """Asphalt for a paved crossing: stock 4-way 43's own interior, at the world point folded into PAVE_IN (a
    triangle wave of the world lane coordinate, so it is continuous across cells)."""
    lo, hi = PAVE_IN
    span = hi - lo

    def fold(t):
        u = (t / span) % 2.0
        return lo + span * (u if u < 1.0 else 2.0 - u)
    return STOCK(43, 0, z, r, fold(wx * 256.0), fold(wz * 256.0))


def _first_lane(prof, from_hi=False):
    """cut position where the first lane bin starts, from the low (or high) end of a lane_bins profile"""
    lo, w, lane = prof
    n = len(lane)
    for i in (range(n - 1, -1, -1) if from_hi else range(n)):
        if lane[i]:
            return lo + (i + 1) * w if from_hi else lo + i * w
    return lo if from_hi else lo + n * w


class DiagEl:
    """Canonical diagonal avenue: strips c <= x - z < c + 2 (A then B), as the DAV pieces draw it (StraightAvenue)."""

    kind = "diag"
    width = 2.0 / SQ2              # cells across
    direction = (1.0 / SQ2, 1.0 / SQ2)
    normal = (1.0 / SQ2, -1.0 / SQ2)

    def __init__(self, c=0):
        self.c = c
        self.av = StraightAvenue()

    def across(self, wx, wz):
        return (wx - wz - self.c) / SQ2

    def colour(self, z, r, wx, wz):
        """the plain avenue, its carriageway lines white and dashed (owner, 2026-10-17; lanelines.py): a yellow pixel
        on the stock centre line's footprint becomes a dash at the along-coordinate (x + z) / sqrt 2 of the avenue's
        own frame, as the diagonal avenue scenes phase it, else lane asphalt (already-white pixels pass)"""
        c = self.av.colour(z, r, wx - self.c, wz)
        if not _yellow(c):
            return c
        p = wx - wz - self.c
        st = 0 if p < 1.0 else 1
        fill = lambda: lane_fill(st, wx - self.c, wz, z, r)                     # noqa: E731
        cl = centre_line(z, r)
        if cl is not None and abs(p - st - cl[0]) <= cl[1]:
            return LL.dashed(z, wx, wz, LL.along_diag(wx - self.c, wz), True, fill)
        return fill()

    def median(self, z, r, wx, wz):
        """the stock pixel where the plain avenue draws median grass, else None"""
        p = wx - wz - self.c
        if not (0.0 <= p < 2.0):
            return None
        col = diag(0 if p < 1.0 else 1, wx - self.c, wz, z, r)
        cen, hw = seam(z, r)
        return col if light(col) and abs(p - cen) < hw else None

    def fill(self, z, r, wx, wz):
        p = wx - wz - self.c
        return lane_fill(0 if p < 1.0 else 1, wx - self.c, wz, z, r)

    def own(self, z, r, wx, wz):
        p = wx - wz - self.c
        return diag(0 if p < 1.0 else 1, wx - self.c, wz, z, r)

    def sidewalk(self, z, r):
        """(low edge, high edge) sidewalk + curb widths in cells, from stock 35's lane profile"""
        prof = strip_prof(z, r)
        return _first_lane(prof) / SQ2, (1.0 - _first_lane(prof, True)) / SQ2

    def cells(self):
        return lambda X, Z: X - Z - self.c in (0, 1, 2)


class StraightEl:
    """Canonical stock avenue 11204 along x: row m at state 2, row m + 1 at state 0 (measured with tiler.py)."""

    kind = "straight"
    width = 2.0
    direction = (1.0, 0.0)
    normal = (0.0, 1.0)
    PID = 11204

    def __init__(self, m=0):
        self.m = m

    def across(self, wx, wz):
        return wz - self.m

    def ground(self, z, r, wx, wz):
        """11204's ground without its trees. Its layer 0 carries the trees too; in slots 1 and 2 they stand in front
        of the road (layer 1 holds the same trees alone). A pixel under them is read from the nearest point along the
        road (x, wrapping: every cell draws the same frame) that no tree covers, so the lane lines stay put; from the
        opposite view (slot + 2, the trees behind) only when the whole line is covered, as its texture differs (10%
        of pixels equal at the same ground point, measured 2026-10-17)."""
        if not (self.m <= wz < self.m + 2):
            return CLEAR
        X, Z = math.floor(wx), math.floor(wz)
        st, lx, lz = 2 if Z == self.m else 0, (wx - X) * 256.0, (wz - Z) * 256.0
        if (st + r) & 3 in (1, 2) and STOCK1(self.PID, st, z, r, lx, lz)[3]:
            for k in range(1, 65):
                for sgn in (1, -1):
                    l2 = (lx + sgn * 2.0 * k) % 256.0
                    if not STOCK1(self.PID, st, z, r, l2, lz)[3]:
                        return STOCK(self.PID, st, z, r, l2, lz)
            return STOCK(self.PID, st, z, (r + 2) % 4, lx, lz)
        return STOCK(self.PID, st, z, r, lx, lz)

    def grass_band(self, z, r):
        """half width (cells) of the median grass about row m + 1: the farthest offset (up to 0.35) where both sides
        are grass in most samples along the road (the stock median has a dark line of trunk bases at its centre)"""
        k = (self.PID, "grass", z, r)
        if k not in _PROF:
            alongs = [0.03 + 0.94 * j / 31.0 for j in range(32)]
            hw = 0.0
            for i in range(1, 46):
                t = i / 128.0
                if all(sum(1 for a in alongs if _grassy(self.ground(z, r, a, self.m + 1 + sgn * t))) >= len(alongs) // 2
                       for sgn in (-1, 1)):
                    hw = t + 0.5 / 128.0
            _PROF[k] = hw
        return _PROF[k]

    def colour(self, z, r, wx, wz):
        """the tree-free ground; on the median strip the trunk bases become grass (no tree stands on these cells); the
        yellow centre line of each carriageway white and dashed, phased by x as the 11204 reskin (avenue_markings.py:
        4 centred dashes per cell)"""
        c = self.ground(z, r, wx, wz)
        if c[3] and abs(wz - (self.m + 1)) < self.grass_band(z, r) and not _grassy(c):
            return pick("grass", z, wx, wz)
        t = wz - self.m
        if _yellow(c) and min(abs(t - 0.5), abs(t - 1.5)) < 0.25:
            return LL.dashed(z, wx, wz, wx, True, lambda: self.fill(z, r, wx, wz))
        return c

    own = colour

    def median(self, z, r, wx, wz):
        if abs(wz - (self.m + 1)) > 0.4:
            return None
        c = self.colour(z, r, wx, wz)
        return c if _grassy(c) else None

    def prof(self, z, r):
        return lane_bins((self.PID, "x", z, r), lambda t, a: self.ground(z, r, a, self.m + t), 0.0, 2.0, 256,
                         [0.03 + 0.94 * k / 63.0 for k in range(64)])

    def fill(self, z, r, wx, wz):
        c = mirror(self.prof(z, r), lambda t: self.ground(z, r, wx, self.m + t), wz - self.m)
        return c if c is not None else pick("asphalt", z, wx, wz)

    def sidewalk(self, z, r):
        prof = self.prof(z, r)
        return _first_lane(prof), 2.0 - _first_lane(prof, True)

    def cells(self):
        return lambda X, Z: Z in (self.m, self.m + 1)


class Placed:
    """An element turned k states, then moved by (tx, tz) whole cells."""

    def __init__(self, el, k=0, t=(0, 0)):
        self.el, self.k, self.t = el, k % 4, t

    def canon(self, wx, wz):
        return _rinv(wx - self.t[0], wz - self.t[1], self.k)

    def call(self, fn, z, r, wx, wz):
        cx, cz = self.canon(wx, wz)
        return getattr(self.el, fn)(z, (r + self.k) % 4, cx, cz)

    def across(self, wx, wz):
        return self.el.across(*self.canon(wx, wz))

    def inside(self, wx, wz, margin=0.0):
        a = self.across(wx, wz)
        return -margin <= a < self.el.width + margin

    def edge_dist(self, wx, wz):
        """(distance to the low edge, to the high edge) in cells"""
        a = self.across(wx, wz)
        return a, self.el.width - a

    def direction(self):
        return _rot(self.el.direction[0], self.el.direction[1], self.k)

    def along_dist(self, wx, wz, d):
        """distance along d (either way) from (wx, wz) to this element's band; 0 inside"""
        if self.inside(wx, wz):
            return 0.0
        n = _rot(self.el.normal[0], self.el.normal[1], self.k)
        nd = n[0] * d[0] + n[1] * d[1]
        if abs(nd) < 1e-9:
            return 1e9
        a = self.across(wx, wz)
        return min(abs(a / nd), abs((a - self.el.width) / nd))

    def sidewalk(self, z, r):
        return self.el.sidewalk(z, (r + self.k) % 4)

    def has_cell(self, X, Z):
        cx, cz = self.canon(X + 0.5, Z + 0.5)
        return self.el.cells()(math.floor(cx), math.floor(cz))


class Crossing:
    """Two placed elements. Where both are: the crossing, paved (stock 43s interior asphalt, `paved`),
    corner sidewalks where both outer sidewalks meet (the element whose edge is relatively farther is sampled, so each
    side keeps its own curb), two white crosswalk lines (WHITE_LINES, lane units from the edge) along every edge where
    an arm leaves the crossing. Where one is: that element as stock, its median ending NOSE_CELLS before the other
    element with a concrete nose. stem = (i, e): element i ends at the other element's edge e (0 low, 1 high): nothing
    of i past it, the other's sidewalk along it kept, no crosswalk there (a T)."""

    def __init__(self, els, stem=None):
        self.els, self.stem = els, stem

    def has(self, i, wx, wz, margin=0.0):
        e = self.els[i]
        if not e.inside(wx, wz, margin):
            return False
        if self.stem and self.stem[0] == i:
            o = self.els[1 - i]
            a = o.across(wx, wz)
            if (self.stem[1] == 1 and a >= o.el.width) or (self.stem[1] == 0 and a < 0.0):
                return False
        return True

    def colour(self, z, r, wx, wz):
        ins = [self.has(i, wx, wz) for i in (0, 1)]
        if not any(ins):
            for i in (0, 1):                        # the stock frames' own edge pixels just outside the band
                if self.has(i, wx, wz, 0.36) and not self.has(1 - i, wx, wz, 0.02):
                    return self.els[i].call("colour", z, r, wx, wz)
            return CLEAR
        if ins[0] != ins[1]:
            i = 0 if ins[0] else 1
            e, o = self.els[i], self.els[1 - i]
            m = e.call("median", z, r, wx, wz)
            if m is not None and o.along_dist(wx, wz, e.direction()) < NOSE_CELLS:
                return m if e.el.kind == "diag" else pick("concrete", z, wx, wz)
            return e.call("colour", z, r, wx, wz)
        if self.stem:                                       # a T: the through road's far sidewalk and curb go on
            o = self.els[1 - self.stem[0]]
            if o.edge_dist(wx, wz)[self.stem[1]] < o.sidewalk(z, r)[self.stem[1]]:
                return o.call("colour", z, r, wx, wz)
        rel = []
        for e in self.els:
            lo, hi = e.edge_dist(wx, wz)
            sw = e.sidewalk(z, r)
            rel.append(min(lo / sw[0] if sw[0] else 9.0, hi / sw[1] if sw[1] else 9.0))
        if rel[0] < 1.0 and rel[1] < 1.0:                   # corner: both outer sidewalks
            return self.els[0 if rel[0] >= rel[1] else 1].call("colour", z, r, wx, wz)
        if z >= 2:
            for i in (0, 1):                               # element i's arms leave through the other's edges
                o = self.els[1 - i]
                for side, dist in enumerate(o.edge_dist(wx, wz)):
                    if self.stem and self.stem[0] == i and side == self.stem[1]:
                        continue                           # the stem does not go on past the far edge
                    if any(a <= dist * 256.0 < b for a, b in WHITE_LINES):
                        return pick("white", z, wx, wz)
        return paved(z, r, wx, wz)

    def plain(self, z, r, wx, wz, i):
        """element i alone, as its own pieces draw it"""
        return self.els[i].call("colour", z, r, wx, wz) if self.els[i].inside(wx, wz, 0.36) else CLEAR
