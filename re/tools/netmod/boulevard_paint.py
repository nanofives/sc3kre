#!/usr/bin/env python3
r"""boulevard_paint.py - the boulevard's ground art as world scenes (task boulevard, 2026-10-17).

A boulevard is three parallel straight roads drawn side by side. Canonical frame: the boulevard runs along world x,
its rows are world z 0 (north carriageway), 1 (middle) and 2 (south carriageway); T = z * 256 is the cross position
in lane units (0 .. 768), s = x the position along it (cells). Every piece is one cell of a scene painted with
diagave_paint.paint_cell: each output pixel is unprojected to world (s, T) and coloured by SAMPLING STOCK FRAMES at
the same screen position, so plain road equals stock and neighbouring pieces meet exactly.

Cross-section (stock road 29 at zoom 4, lane units across its cell: sidewalk 0..34, curb and gutter 34..56, lane 1
56..116, centre line 124..132, lane 2 148..200, gutter and curb 200..224, sidewalk 224..256; car lanes at 80 / 175):
  * each outer row is its own stock 29, yellow centre line kept; its inner sidewalk becomes one more lane EXTRA units
    wide (stock lane asphalt folded from its own lane band), then its own gutter and curb, moved over by EXTRA;
  * the middle row holds the two extra lanes' far parts, the two curbs and between them a grass median (avenue
    11204's grass) with 11204's trees on its centre line: curb to curb about twice the stock avenue's.

Scenes: Boulevard (straight, optional median nose at either end), Junction (stock 4-way 43 with the boulevard's
inner edges opened, crosswalks are 43's own lines), Taper (the boulevard narrows to one of its three roads: the two
outer curbs move in, the single road's centre line runs straight to the median nose, as the diagonal avenue merge).
"""
import math

from netmod import netart as NA
from netmod import diagave_paint as DP
from netmod.diagave_paint import CLEAR, STOCK, light, pick, paint_cell   # noqa: F401  (paint_cell re-exported)
from netmod import lanelines as LL

EXTRA = 104.0            # extra lane width, lane units (two folds of the 52-unit lane band: ends on its edge again)
LANE_N = (56.0, 116.0)   # 29's lane 1 dark band (fold source for the south carriageway's extra lane)
LANE_S = (148.0, 200.0)  # 29's lane 2 dark band (fold source for the north carriageway's extra lane)
SIDE_N = 34.0            # 29's north sidewalk ends here (the south carriageway's inner sidewalk -> median grass)
SIDE_S = 224.0           # 29's south sidewalk starts here
CURB = 56.0              # sidewalk + curb + gutter band kept along a moving outer edge
NOSE = 0.12              # cells: the median ends in concrete this long
DIVIDER = 220.0          # the line between a carriageway's inner lane and its extra lane, units from its outer edge
                         # (between the car lanes at 175 and 270)


def s29(z, r, x, zl, state=0):
    """stock 29 at lane point (x, zl), stepping inward when the point is on its frame's border (the stock leaves that
    pixel to the neighbour's frame)"""
    x = min(255.5, max(0.5, x))
    zl = min(255.5, max(0.5, zl))
    c = STOCK(29, state, z, r, x, zl)
    k = 0
    while not c[3] and k < 8:
        k += 1
        x2 = x + (k if x < 128 else -k)
        z2 = zl + (k if zl < 128 else -k)
        c = STOCK(29, state, z, r, x2, z2)
    return c


def fold(u, band):
    """u >= 0 units from the band's start edge -> a point of the band, reflected back and forth (no seams)"""
    a, b = band
    w = b - a
    u = u % (2 * w)
    return a + u if u < w else b - (u - w)


class Boulevard:
    """The straight boulevard. nose_lo / nose_hi: the median ends with a concrete nose at s = nose_lo (going -x) /
    nose_hi (going +x); None = runs on."""

    def __init__(self, nose_lo=None, nose_hi=None):
        self.nose_lo, self.nose_hi = nose_lo, nose_hi

    def median(self, z, r, x, s, T):
        nose = (self.nose_hi is not None and s >= self.nose_hi - NOSE) or \
               (self.nose_lo is not None and s < self.nose_lo + NOSE)
        if nose:
            return s29(z, r, x, 240.0)                       # concrete: 29's sidewalk
        return pick("grass", z, s, T / 256.0)

    def carriageway(self, z, r, x, s, T):
        """the boulevard proper at (s, T), T in 0 .. 768"""
        return self.section(z, r, x, s, T, 0.0, EXTRA, 512.0, EXTRA, 384.0, True)

    def section(self, z, r, x, s, T, t0n, wn, t0s, ws, mid, dividers):
        """Two carriageways: north = stock 29 with its frame at T t0n and an extra lane wn wide on its south side, south
        = 29 at T t0s with wn's mirror ws on its north side; T < mid belongs to the north one. Beyond a carriageway's
        inner curb: median. Lane lines (owner, 2026-10-17): each carriageway's centre line and, with `dividers`, the
        line between its inner lane and the extra lane are white dashes (lanelines.py), no yellow."""
        if T < mid:
            zl = T - t0n
            if zl < 0:
                return CLEAR
            if zl < LANE_S[1]:
                c = self.centre(z, r, x, s, T, zl)
                if c is not None:
                    return c
                base = s29(z, r, x, zl)
            elif zl < LANE_S[1] + wn:
                base = self._fold_down(z, r, x, zl - LANE_S[1])
            elif zl - wn < SIDE_S:
                base = s29(z, r, x, zl - wn)
            else:
                return self.median(z, r, x, s, T)
            if dividers:
                c = self.divider(z, r, x, s, T, zl - DIVIDER, base)
                if c is not None:
                    return c
            return base
        zl = T - t0s
        if zl >= 256.0:
            return CLEAR
        if zl >= LANE_N[0]:
            c = self.centre(z, r, x, s, T, zl)
            if c is not None:
                return c
            base = s29(z, r, x, zl)
        elif zl >= LANE_N[0] - ws:
            base = self._fold_up(z, r, x, LANE_N[0] - zl)
        elif zl + ws >= SIDE_N:
            base = s29(z, r, x, zl + ws)
        else:
            return self.median(z, r, x, s, T)
        if dividers:
            c = self.divider(z, r, x, s, T, zl - (256.0 - DIVIDER), base)
            if c is not None:
                return c
        return base

    @staticmethod
    def centre(z, r, x, s, T, zl):
        """a carriageway's own centre line (29's yellow footprint at lane point zl) as white dashes, or None"""
        cl = centre_line(z, r)
        if cl is None or abs(zl - cl[0]) > cl[1] + 8.0:
            return None
        d = zl - cl[0]
        side = 1.0 if d >= 0 else -1.0
        c = s29(z, r, x, zl)
        if not yellowish(c):
            return None if abs(d) > cl[1] else c
        # a yellow pixel (also one the rounding of a moving frame brings in beside the footprint): dash or asphalt
        return LL.dashed(z, s, T / 256.0, s, abs(d) <= cl[1],
                         lambda: s29(z, r, x, cl[0] + side * (2.0 * cl[1] + 3.0 + abs(d))))

    @staticmethod
    def divider(z, r, x, s, T, d, base):
        """the dashed line `d` units from its centre (29's centre-line footprint moved there), or None"""
        cl = centre_line(z, r)
        if cl is None or abs(d) > cl[1]:
            return None
        return LL.dashed(z, s, T / 256.0, s, yellow(s29(z, r, x, cl[0] + d)), lambda: base)

    @staticmethod
    def _fold_down(z, r, x, u):
        """u units past lane 2's outer edge: lane 2's band read from that edge inward and back"""
        a, b = LANE_S
        w = b - a
        u = u % (2 * w)
        return s29(z, r, x, b - u if u < w else a + (u - w))

    @staticmethod
    def _fold_up(z, r, x, u):
        a, b = LANE_N
        w = b - a
        u = u % (2 * w)
        return s29(z, r, x, a + u if u < w else b - (u - w))

    def colour(self, z, r, wx, wz):
        if wz < 0 or wz >= 3:
            return CLEAR
        return self.carriageway(z, r, (wx % 1.0) * 256.0, wx, wz * 256.0)


# ------------------------------------------------------------------------------------------------ junctions

def s43(z, r, x, zl, state=0, pid=43):
    x = min(255.5, max(0.5, x))
    zl = min(255.5, max(0.5, zl))
    c = STOCK(pid, state, z, r, x, zl)
    k = 0
    while not c[3] and k < 8:
        k += 1
        c = STOCK(pid, state, z, r, x + (k if x < 128 else -k), zl + (k if zl < 128 else -k))
    return c


EDGE_IN = 42.0           # a 43 edge band (corner squares, crosswalk lines at 8..15 / 32..38) ends here
EDGE_OUT = 214.0


class Junction:
    """A single straight road along z crossing the boulevard (canonical: crossing column at s 0..1).
    kind 'N' = the outer row the crossing road enters by (stock 43 with its S edge opened: reflected about EDGE_OUT),
    'M' = the middle row (43 with both N and S edges opened), 'F' = the far outer row of a T (stock T 39 state 1,
    closed side S, with its N edge opened). Crosswalks are the stock pieces' own lines, which now run across the
    whole boulevard along both sides of the crossing road."""

    def __init__(self, kind):
        self.kind = kind

    def colour(self, z, r, wx, wz):
        x, zl = (wx % 1.0) * 256.0, (wz % 1.0) * 256.0
        if self.kind == "N":
            if zl > EDGE_OUT:
                zl = 2 * EDGE_OUT - zl
            return s43(z, r, x, zl)
        if self.kind == "M":
            if zl > EDGE_OUT:
                zl = 2 * EDGE_OUT - zl
            elif zl < EDGE_IN:
                zl = 2 * EDGE_IN - zl
            return s43(z, r, x, zl)
        if zl < EDGE_IN:                                          # 'F'
            zl = 2 * EDGE_IN - zl
        return s43(z, r, x, zl, state=1, pid=39)


# ------------------------------------------------------------------------------------------------ tapers

TAPER_LEN = 3.0          # cells


def outer_curve(t):
    """THE shape of the far curb when the boulevard narrows to an OUTER road (keep 0 / 2), 0..1 over the taper: the
    share of the two rows it has moved in. Eased (t^3) so that every cell of the ending rows still holds road (both
    ending drags stop on the same column); owner decision pending (mockup note 2026-10-17): change it here only."""
    return t ** 3


class Taper(Boulevard):
    """The boulevard narrows to row `keep` (0 north, 1 middle, 2 south) going +x: s < 0 is the boulevard (its median
    ends in a nose at s 0), 0 <= s < TAPER_LEN the taper, beyond it the single road (stock 29). keep 1: both outer
    curbs move in linearly; keep 0 / 2: the far curb moves in two rows, easing in (t^3) so that every cell of the
    ending rows still holds road. Inside the taper the markings are asphalt except the single road's yellow centre
    line, which runs straight from where the taper closes to the median nose (owner rule for the diagonal avenue
    merge, 2026-10-17)."""

    def __init__(self, keep):
        Boulevard.__init__(self, nose_hi=0.0)
        self.keep = keep

    def edges(self, t):
        k = self.keep
        if k == 1:
            return 256.0 * t, 768.0 - 256.0 * t
        e = outer_curve(t)
        if k == 0:
            return 0.0, 768.0 - 512.0 * e
        return 512.0 * e, 768.0

    def colour(self, z, r, wx, wz):
        if wz < 0 or wz >= 3:
            return CLEAR
        x, s, T = (wx % 1.0) * 256.0, wx, wz * 256.0
        if s < 0:
            return self.carriageway(z, r, x, s, T)
        if s >= TAPER_LEN:
            k = self.keep
            return s29(z, r, x, T - 256.0 * k) if 256.0 * k <= T < 256.0 * (k + 1) else CLEAR
        t = s / TAPER_LEN
        N, S = self.edges(t)
        if T < N or T >= S:
            return CLEAR
        if T - N < CURB:
            return s29(z, r, x, T - N)
        if S - T < CURB:
            return s29(z, r, x, 256.0 - (S - T))
        cl = centre_line(z, r)
        pc = 384.0 + (256.0 * self.keep - 256.0) * t
        if cl is not None and abs(T - pc) <= cl[1]:
            return s29(z, r, x, cl[0] + (T - pc))
        zs = T - 256.0 * self.keep                               # the single road's own lane point
        if LANE_N[0] <= zs <= LANE_S[1] and (cl is None or abs(zs - cl[0]) > cl[1] + 10.0):
            return s29(z, r, x, zs)
        return s29(z, r, x, fold(T, LANE_S))


_CL = {}


def yellow(c):
    """a pixel of 29's yellow centre line"""
    return bool(c[3]) and c[0] > 150 and c[1] > 120 and c[0] - c[2] > 50


def yellowish(c):
    """yellow or a yellow edge pixel (the line's blend into the asphalt)"""
    return bool(c[3]) and c[0] > 115 and c[1] > 95 and c[0] - c[2] > 30


def centre_line(z, r):
    """(centre, half width) in lane units of stock 29's yellow centre line at this zoom and view, None when under a
    pixel (zoom 0, 1): the run of yellow-ish majority bins nearest zl 128"""
    k = (z, r)
    if k in _CL:
        return _CL[k]
    alongs = [1.0 + 254.0 * i / 63.0 for i in range(64)]
    bins = []
    for i in range(48, 80):                                      # zl 96 .. 160 in 2-unit bins
        zl = (i + 0.5) * 2.0
        n = sum(1 for a in alongs if yellow(s29(z, r, a, zl)))
        bins.append((zl, n >= 0.3 * len(alongs)))
    ys = [zl for zl, y in bins if y]
    if not ys:
        _CL[k] = None
    else:
        _CL[k] = ((min(ys) + max(ys)) / 2.0, (max(ys) - min(ys)) / 2.0 + 1.5)
    return _CL[k]


# ------------------------------------------------------------------------------------------------ trees

def tree_layer(z, slot, spots):
    """layer-1 frame: 11204's trees standing at lane points `spots` [(x, zl), ...] of a cell in view slot `slot`
    (the piece's state + view). -> (image, anchor)"""
    from PIL import Image
    from netmod.diagave import tree_sprites
    W = NA.TILE_W[z]
    H = W // 2
    T = H // 2 - 1
    trees = tree_sprites(z)
    up = max(t.height for t, _ in trees) + 2
    Tc = up + T
    layer = Image.new("RGBA", (W, up + H), (0, 0, 0, 0))
    pts = []
    for (x, zl) in spots:
        u, v = NA.rot_uv(1.0 - x / 256.0, zl / 256.0, slot)
        X, Y = NA.project(z, u, v)
        pts.append((int(round(X)), int(round(Y + Tc))))
    for k, (bx, by) in enumerate(sorted(pts, key=lambda p: p[1])):     # back to front
        spr, (tx, ty) = trees[k % len(trees)]
        tmp = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        tmp.paste(spr, (bx - tx, by - ty))
        layer.alpha_composite(tmp)
    return layer, (0, Tc)


MEDIAN_TREES = ((64.0, 128.0), (192.0, 128.0))


class Cap(Boulevard):
    """All three roads stop: the end column (canonical s 0..1, +x end) closes the boulevard with a half ellipse of
    curb (1 cell along, the full 3 rows across); the median ends in a nose at s 0, the markings stop there."""

    def __init__(self):
        Boulevard.__init__(self, nose_hi=0.0)

    def colour(self, z, r, wx, wz):
        if wz < 0 or wz >= 3:
            return CLEAR
        x, s, T = (wx % 1.0) * 256.0, wx, wz * 256.0
        if s < 0:
            return self.carriageway(z, r, x, s, T)
        su, tu, a, b = s * 256.0, T - 384.0, 256.0, 384.0
        rho = math.sqrt((su / a) ** 2 + (tu / b) ** 2)
        if rho >= 1.0:
            return CLEAR
        g = math.sqrt((su / a ** 2) ** 2 + (tu / b ** 2) ** 2) / max(rho, 1e-9)
        d = (1.0 - rho) / max(g, 1e-9)                          # lane units in from the curb line
        if d < CURB:
            return s29(z, r, x, d)
        return s29(z, r, x, fold(T, LANE_S))


class AvenueNarrow(Boulevard):
    """The boulevard narrows to an avenue going +x: rows `keep` = (0, 1) or (1, 2) go on as stock avenue 11204. Over
    the last TAPER_LEN columns the ending side's carriageway slides one row in (its frame moves 256 units, linearly),
    both extra lanes close (104 -> 0) and the median narrows from the boulevard's to the avenue's, its centre moving
    from T 384 to 256 (keep 0, 1) or 512 (keep 1, 2); its trees stay on that centre. The carriageways' centre lines
    stay white dashes all the way (the avenue's own lines, reskinned by avenue_markings, go on from there); the
    extra-lane dividers end where the taper starts."""

    def __init__(self, keep):
        Boulevard.__init__(self)
        self.keep = keep

    def params(self, t):
        t = min(1.0, max(0.0, t))
        w = EXTRA * (1.0 - t)
        if self.keep == (0, 1):
            return 0.0, w, 512.0 - 256.0 * t, w, 384.0 - 128.0 * t
        return 256.0 * t, w, 512.0, w, 384.0 + 128.0 * t

    def colour(self, z, r, wx, wz):
        if wz < 0 or wz >= 3:
            return CLEAR
        x, s, T = (wx % 1.0) * 256.0, wx, wz * 256.0
        if s < 0:
            return self.carriageway(z, r, x, s, T)
        t0n, wn, t0s, ws, mid = self.params(s / TAPER_LEN)
        return self.section(z, r, x, s, T, t0n, wn, t0s, ws, mid, False)

    def tree_spots(self, cell):
        """lane points of the trees of cell (column, row): two per column on the median centre, in the cell holding it"""
        col, row = cell
        out = []
        for lx in (64.0, 192.0):
            mid = self.params((col + lx / 256.0) / TAPER_LEN)[4]
            if row * 256.0 <= mid < (row + 1) * 256.0:
                out.append((lx, mid - row * 256.0))
        return out
