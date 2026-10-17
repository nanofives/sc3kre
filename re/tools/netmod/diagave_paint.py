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

from netmod import netart as NA

DIAG_STATE = {0: 2, 1: 0}          # axis 0: a cell at d (x - z - strip offset) 0 / 1 of a strip holds 35 in this state
WHITE_LINES = ((8.0, 15.0), (32.0, 38.0))     # crosswalk lines, lane units in from the edge (stock 43, zoom 4)


class Stock:
    """Colour of a stock piece at a lane-frame point (x, z in 0..256 of the cell) in view rotation r."""

    def __init__(self):
        self.fr = {}

    def frames(self, pid):
        if pid not in self.fr:
            self.fr[pid] = {k: (im, im.load(), LT) for k, (im, LT) in NA.stock_frames(pid).items()}
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


def lane_fill(strip, wx, wz, z, r):
    """Stock asphalt for a point of a strip whose own pixel is a marking, curb or sidewalk (same q, so the 2D texture
    along the strip is kept); a lane pixel (specks included) stays."""
    p, q = wx - wz, wx + wz
    prof = lane_bins((35, z, r), lambda t, a: diag_at(0, t, a, z, r), 0.0, 1.0, 128,
                     [0.05 + 4.0 * k / 97.0 for k in range(97)])
    c = mirror(prof, lambda t: diag_at(strip, t, q, z, r), p - strip)
    return c if c is not None else diag(strip, wx, wz, z, r)


def lane_grey(c):
    """lane asphalt only (the gutter greys 115..131 are not)"""
    return c[3] and max(c[:3]) < 118 and max(c[:3]) - min(c[:3]) < 22


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
        return col

    def colour(self, z, r, wx, wz):
        p, q = wx - wz, wx + wz
        if p < -0.5 or p >= 2.5:
            return CLEAR
        return self.strip_colour(z, r, wx, wz, p, q)


class Merge(StraightAvenue):
    """One carriageway ends: `ends` = 'B' (A continues) or 'A'. Its outer edge moves linearly from full width at q_s to
    nothing at q_e, keeping a curb band `curb` wide (x - z units) sampled from the stock outer edge; the median ends at
    q_s and the other carriageway's inner sidewalk is asphalt until q_e."""

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
                if p >= 1.0:
                    return lane_fill(1, wx, wz, z, r)            # B's lanes, markings dropped: they merge
            else:
                edge = t                                         # A's outer edge moves from 0 to 1
                if p < edge:
                    return CLEAR
                if p - edge < self.curb:
                    return diag_at(0, p - edge, q, z, r)
                if p < 1.0:
                    return lane_fill(0, wx, wz, z, r)
            if kp[0] <= p < kp[1]:                               # the continuing carriageway: inner side opens
                s = int(kp[0])
                near = (kp[1] - p) < self.inner if keep == "A" else (p - kp[0]) < self.inner
                return lane_fill(s, wx, wz, z, r) if near else diag(s, wx, wz, z, r)
            return CLEAR
        if kp[0] <= p < kp[1]:
            return diag(int(kp[0]), wx, wz, z, r)
        return CLEAR


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
