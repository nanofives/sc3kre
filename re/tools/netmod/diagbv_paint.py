#!/usr/bin/env python3
r"""diagbv_paint.py - the diagonal boulevard's ground art as world scenes (task diagbv, 2026-10-17).

A diagonal boulevard is three diagonal road drags joined side by side, each one cell over from the last, so every row
of the band is four cells: d0 (staircase A), d1 (A + B), d2 (B + C), d3 (C). Stock diagonal 35 draws only the road half
of its cell, so the band is the strip 0 <= p < 3 with p = x - z (axis 0, band offset 0): A on p 0..1, B on 1..2, C on
2..3 (diagave_paint.py has the strip geometry). q = x + z runs along it (one row = 2 in q).

Cross-section: the straight boulevard's (boulevard_paint.Boulevard.section) turned 45 degrees. Measured 2026-10-17:
stock 35's profile across its strip, in p_rel * 256, is stock 29's profile across its cell in lane units within a few
units (sidewalk, curb, lane bands, centre line, curb, sidewalk at the same places), so T = 256 * p is the boulevard's
cross position and the section is evaluated as is, with a sampler that reads STOCK 35 at strip position zl / 256
instead of stock 29 at lane point zl. The section is not copied: it is boulevard_paint's own code, so a change of the
straight boulevard's look after the owner's review carries over (only the sampler and its centre-line cache are
swapped while a diagonal piece is painted, `diagonal()`).

Symmetry: only the section's NORTH half is evaluated (one carriageway, its extra lane, its curb, the median beyond).
The south half of every scene is the north half turned half a circle about (1.5, 0) (p -> 3 - p, q -> 3 - q, view
r -> r + 2), which is how stock places staircase C against A (35 state + 2). So the band is exactly symmetric, the C
carriageway is pixel-exact stock 35 where plain, and a piece turned by 2 states is the same piece on the other side
(the band's d3 is d0 turned, d2 is d1 turned, a top end is the bottom end turned).

Sampler: a carriageway whose stock frame sits `off` lane units across reads strip 0 at along position q - off / 256:
stock staircase k at (p_rel, q) is staircase 0 at (p_rel, q - k) (the 35 lattice), so a frame that slides across (the
narrowing) meets the diagonal avenue's B staircase exactly when it arrives at off 256.

Along coordinate s = (x + z) / sqrt(2) (world cells along the diagonal): the dash phase of lanelines.py, as the
diagonal avenue's.

Scenes (canonical: axis 0; ends at the BOTTOM, the band's last full row is row 0 = cells (0..3, 0)):
  Band                 the straight boulevard
  Junction             a straight single road crossing / meeting / closing the band (row road along x or column road
                       along z); medians end in noses parallel to the road, crosswalks as stock 43's
  Narrow               the band narrows to the diagonal avenue (C ends: A, B go on; or A ends: B, C go on)
  Taper                the band narrows to one of its three roads (the single road's yellow line jogs to the nose)
  Turned               any bottom-end scene turned half a circle: the same end at the top
"""
import contextlib
import math

from netmod import boulevard_paint as BP
from netmod import diagave_paint as DP
from netmod import lanelines as LL
from netmod.diagave_paint import CLEAR, WHITE_LINES

SQ2 = math.sqrt(2.0)


class _Cur:
    """the pixel being painted: real world point (for noses), along position q and frame offset for the sampler"""
    q = 0.0
    off = 0.0
    wx = 0.0
    wz = 0.0


CUR = _Cur()


def s35(z, r, x, zl, state=0):
    """stock 35 of staircase 0 at strip position zl / 256 and along position CUR.q - CUR.off / 256; the lane-unit
    signature of boulevard_paint.s29, which the section calls"""
    zl = min(255.5, max(0.5, zl))
    return DP.diag_at(0, zl / 256.0, CUR.q - CUR.off / 256.0, z, r)


_CL35 = {}


@contextlib.contextmanager
def diagonal():
    """boulevard_paint's sampler and centre-line cache swapped for stock 35's while painting a diagonal piece"""
    old = BP.s29, BP._CL
    BP.s29, BP._CL = s35, _CL35
    try:
        yield
    finally:
        BP.s29, BP._CL = old


def paint_cell(scene, cell, out_dir, canvas=None, zooms=None):
    with diagonal():
        if zooms is None:
            return DP.paint_cell(scene, cell, out_dir, canvas=canvas)
        return DP.paint_cell(scene, cell, out_dir, canvas=canvas, zooms=zooms)


def along(wx, wz):
    return LL.along_diag(wx, wz)


def turn(wx, wz):
    """the half turn about (1.5, 0): band strip A <-> C, row k <-> row -1 - k, cell (X, Z) <-> (2 - X, -1 - Z)"""
    return 3.0 - wx, -wz


# north carriageway landmarks in T (lane units across the band), from boulevard_paint's section
OPEN_FROM = BP.LANE_S[1]           # + extra width: the extra lane's far edge, curb and median beyond


class Scene(BP.Boulevard):
    """Shared machinery. Subclasses define colour(z, r, wx, wz); `half` paints a north-type carriageway (frame at T t0,
    extra lane w on its +T side, median beyond) at a world point; `both` adds the turned south half beyond `mid`.
    nose(wx, wz) -> 'normal' | 'nose' | 'open': the median at that point (nose = concrete, open = asphalt, curbs too)."""

    def __init__(self):
        BP.Boulevard.__init__(self)

    def nose(self, wx, wz):
        return "normal"

    def half(self, z, r, wx, wz, t0, w, dividers=True, real=None):
        p, q = wx - wz, wx + wz
        T = 256.0 * p
        CUR.q, CUR.off = q, t0
        CUR.wx, CUR.wz = real if real else (wx, wz)
        if T >= t0 + OPEN_FROM + w:
            k = self.nose(CUR.wx, CUR.wz)
            if k == "open":
                return BP.s29(z, r, 0.0, BP.fold(T - t0, BP.LANE_S))
            if k == "nose" and T >= t0 + OPEN_FROM + w + (BP.SIDE_S - BP.LANE_S[1]):
                return BP.s29(z, r, 0.0, 240.0)
        return self.section(z, r, 0.0, along(wx, wz), T, t0, w, 0.0, 0.0, 768.0, dividers)

    def both(self, z, r, wx, wz, t0n, wn, t0s, ws, mid, dividers=True):
        """north half for T < mid; beyond it the south carriageway (frame at T t0s, extra lane ws on its -T side) as the
        turned north carriageway"""
        if 256.0 * (wx - wz) < mid:
            return self.half(z, r, wx, wz, t0n, wn, dividers)
        X, Z = turn(wx, wz)
        return self.half(z, (r + 2) % 4, X, Z, 512.0 - t0s, ws, dividers, real=(wx, wz))

    def band(self, z, r, wx, wz):
        p = wx - wz
        if p < 0.0 or p >= 3.0:
            return CLEAR
        return self.both(z, r, wx, wz, 0.0, BP.EXTRA, 512.0, BP.EXTRA, 384.0)

    def median(self, z, r, x, s, T):
        return BP.pick("grass", z, s, T / 256.0)

    def tree_at(self, q):
        """median trees: at integer q on the median centre p 1.5 (one per cell piece of it, two per row like the
        diagonal avenue's 20500); a scene whose median moves or ends overrides it (on_median filters noses)"""
        return 1.5 if abs(q - round(q)) < 1e-9 else None

    def tree_points(self, cell):
        """world points of the trees standing in `cell` (median grass around them, diagbv.py drops them from cells
        whose frames do not cover the full tile)"""
        X, Z = cell
        out = []
        for k in range(int(math.floor(2 * (X + Z))), int(math.ceil(2 * (X + Z + 2))) + 1):
            q = k / 2.0
            pm = self.tree_at(q)
            if pm is None:
                continue
            wx, wz = (pm + q) / 2.0, (q - pm) / 2.0
            if X <= wx < X + 1 and Z <= wz < Z + 1 and on_median(self, wx, wz):
                out.append((wx, wz))
        return out


class Band(Scene):
    def colour(self, z, r, wx, wz):
        return self.band(z, r, wx, wz)


# median trees: on the median centre line p 1.5 at integer q (one per cell piece of it, two per row like the diagonal
# avenue's 20500): the lane points of the canonical cells d1 = (1, 0) and d2 = (2, 0)
TREES = {1: ((192.0, 64.0),), 2: ((64.0, 192.0),)}


def grassy(c):
    return bool(c[3]) and c[1] > c[0] + 12 and c[1] > c[2] + 8


def on_median(scene, wx, wz, reach=0.15):
    """a tree may stand at (wx, wz): the scene shows median grass there and `reach` cells along the band each way"""
    with diagonal():
        for k in (-1, 0, 1):
            d = k * reach / SQ2
            if not grassy(scene.colour(4, 0, wx + d, wz + d)):
                return False
    return True


def tree_layer(z, slot, spots):
    """layer-1 frame: 11204's trees standing at lane points of a cell, spots [(x, zl, which tree 0 / 1)] in view slot
    `slot` (boulevard_paint.tree_layer with the tree chosen per spot, so the two trees alternate along the median as
    in 11204). -> (image, anchor)"""
    from PIL import Image
    from netmod import netart as NA
    from netmod.diagave import tree_sprites
    W = NA.TILE_W[z]
    H = W // 2
    T = H // 2 - 1
    trees = tree_sprites(z)
    up = max(t.height for t, _ in trees) + 2
    Tc = up + T
    layer = Image.new("RGBA", (W, up + H), (0, 0, 0, 0))
    pts = []
    for (x, zl, k) in spots:
        u, v = NA.rot_uv(1.0 - x / 256.0, zl / 256.0, slot)
        X, Y = NA.project(z, u, v)
        pts.append((int(round(Y + Tc)), int(round(X)), k))
    for by, bx, k in sorted(pts):                                       # back to front
        spr, (tx, ty) = trees[k % len(trees)]
        tmp = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        tmp.paste(spr, (bx - tx, by - ty))
        layer.alpha_composite(tmp)
    return layer, (0, Tc)


def tree_points(pm_of_q, q0, q1):
    """world points of median trees: at each integer q in [q0, q1] where pm_of_q(q) (the median centre p, or None)"""
    out = []
    for q in range(int(math.ceil(q0)), int(math.floor(q1)) + 1):
        pm = pm_of_q(q)
        if pm is not None:
            out.append(((pm + q) / 2.0, (q - pm) / 2.0))
    return out


# ------------------------------------------------------------------------------------------------ junctions

def white(z, wx, wz):
    return DP.pick("white", z, wx, wz)


def crossing(z, r, wx, wz, o, o_state=None):
    """the crossing road's own surface: stock 29 along x (o 0) or z (o 1) at the world point"""
    x, zl = (wx % 1.0) * 256.0, (wz % 1.0) * 256.0
    return DP.STOCK(29, o if o_state is None else o_state, z, r, x, zl)


def crossing_asphalt(z, r, wx, wz, o):
    """the crossing road's lane asphalt at the point (its markings and sidewalks mirrored to asphalt, as DAV's junction)"""
    x, zl = (wx % 1.0) * 256.0, (wz % 1.0) * 256.0
    base = DP.STOCK(29, o, z, r, x, zl)
    if DP.lane_grey(base):
        return base
    alongs = [1.0 + 254.0 * k / 63.0 for k in range(64)]
    if o == 0:
        prof = DP.lane_bins((29, 0, z, r), lambda t, a: DP.STOCK(29, 0, z, r, a, t), 0.0, 256.0, 128, alongs)
        c = DP.mirror(prof, lambda t: DP.STOCK(29, 0, z, r, x, t), zl)
    else:
        prof = DP.lane_bins((29, 1, z, r), lambda t, a: DP.STOCK(29, 1, z, r, t, a), 0.0, 256.0, 128, alongs)
        c = DP.mirror(prof, lambda t: DP.STOCK(29, 1, z, r, t, zl), x)
    return c if c is not None else DP.pick("asphalt", z, wx, wz)


def in_lines(d):
    return any(a <= d < b for a, b in WHITE_LINES)


class Junction(Scene):
    """A straight single road meeting the band. o 0: a row road along x on row 0 (the band's row 0 cells d0..d3 are
    the junction); o 1: a column road along z on column 0 (its cells (0, 0), (0, -1), (0, -2), (0, -3) are d0..d3).
    arms: which sides the road goes on: 'both' (crossing), 'A' (from the A side only: a T), 'C' (from the C side),
    'stem-after' / 'stem-before' (the band ends on the road: no band beyond it along +q / -q; the road goes on both
    ways and keeps its far curb). Inside the road strip the band is asphalt with crosswalks (two white lines, stock
    43's metrics) across the band along the road's edges and across the road along the band's outer edges; outside it
    the band's medians end in a nose parallel to the road."""

    NOSE_W = BP.NOSE                 # cells: the concrete nose's length

    def __init__(self, o, arms="both"):
        Scene.__init__(self)
        self.o, self.arms = o, arms

    def strip(self, wx, wz):
        """(inside the road strip, distance from its -side edge in cells, the edge-to-edge coordinate)"""
        u = wz if self.o == 0 else wx
        return 0.0 <= u < 1.0, u

    def side(self, wx, wz):
        """+1 when the point is on the band's +q side of the road (after it), -1 before"""
        u = wz if self.o == 0 else wx
        return 1 if u >= 1.0 else -1

    def nose(self, wx, wz):
        u = wz if self.o == 0 else wx
        if self.arms == "stem-after" and u >= 1.0 or self.arms == "stem-before" and u < 0.0:
            return "normal"
        d = -u if u < 0.0 else u - 1.0             # cells from the road edge
        return "nose" if d < self.NOSE_W else "normal"

    def colour(self, z, r, wx, wz):
        p = wx - wz
        inside, u = self.strip(wx, wz)
        if not inside:
            if self.arms == "stem-after" and u >= 1.0 or self.arms == "stem-before" and u < 0.0:
                return CLEAR
            return self.band(z, r, wx, wz)
        o = self.o
        road_here = (0.0 <= p < 3.0) or self.arms in ("both", "stem-after", "stem-before") or \
            (self.arms == "A" and p < 0.0) or (self.arms == "C" and p >= 3.0)
        if not road_here:
            # the far side of a T: the band's outer edge (curb, sidewalk) goes on through the junction row
            return self.band(z, r, wx, wz)
        if not (0.0 <= p < 3.0):
            return crossing(z, r, wx, wz, o)
        # a T's far carriageway keeps its outer curb and sidewalk
        if self.arms == "A" and p >= 3.0 - 0.17 or self.arms == "C" and p < 0.17:
            c = self.band(z, r, wx, wz)
            if DP.light(c) or not DP.lane_grey(c):
                return c
        # a stem keeps the road's far curb (its sidewalk on the side away from the band)
        if self.arms in ("stem-after", "stem-before"):
            far = (1.0 - u) if self.arms == "stem-after" else u
            c = crossing(z, r, wx, wz, o)
            if far * 256.0 < BP.CURB and not DP.lane_grey(c):
                return c
        if z >= 2:
            # across the band along the road's edges (not along a stem's far edge)
            for e in (0, 1):
                if (self.arms == "stem-after" and e == 1) or (self.arms == "stem-before" and e == 0):
                    continue
                d = (u if e == 0 else 1.0 - u) * 256.0
                if in_lines(d):
                    return white(z, wx, wz)
            # across the road along the band's outer edges (where the road comes in)
            for e in (0, 1):
                if (self.arms == "A" and e == 1) or (self.arms == "C" and e == 0):
                    continue
                d = (p if e == 0 else 3.0 - p) * 256.0 / SQ2
                if in_lines(d):
                    return white(z, wx, wz)
        return crossing_asphalt(z, r, wx, wz, o)


# ------------------------------------------------------------------------------------------------ ends

class Narrow(Scene):
    """The band narrows to the diagonal avenue at its bottom end. ends 'C': A and B go on (the avenue on strips 0..2),
    'A': B and C go on (strips 1..3). Over q_s..q_e the ending carriageway's frame slides one strip in, both extra
    lanes close and the median narrows to the avenue's, its centre moving from p 1.5 to 1.0 / 2.0
    (boulevard_paint.AvenueNarrow.params: the same moves as the straight narrowing); past q_e the diagonal avenue
    (diagave_paint.StraightAvenue). Measured with `diagbv.py fit`: the narrowing stays inside the cells the drags
    leave and is done where the avenue's own pieces start."""

    def __init__(self, ends, q_s, q_e):
        Scene.__init__(self)
        self.ends, self.q_s, self.q_e = ends, q_s, q_e
        self.av = BP.AvenueNarrow((0, 1) if ends == "C" else (1, 2))

    def t(self, q):
        return min(1.0, max(0.0, (q - self.q_s) / (self.q_e - self.q_s)))

    def colour(self, z, r, wx, wz):
        p, q = wx - wz, wx + wz
        if q < self.q_s:
            return self.band(z, r, wx, wz)
        if q >= self.q_e:
            if self.ends == "C":
                return DP.StraightAvenue().colour(z, r, wx, wz)
            return DP.StraightAvenue().colour(z, r, wx - 1.0, wz)     # strips 1..3: one cell over (the 35 lattice)
        if p < -0.5 or p >= 3.5:
            return CLEAR
        t0n, wn, t0s, ws, mid = self.av.params(self.t(q))
        if 256.0 * p < t0n or 256.0 * p >= t0s + 256.0:
            return CLEAR
        return self.both(z, r, wx, wz, t0n, wn, t0s, ws, mid, False)

    def tree_at(self, q):
        whole = abs(q - round(q)) < 1e-9
        if q < self.q_e:
            return self.av.params(self.t(q))[4] / 256.0 if whole else None
        # past the narrowing: the diagonal avenue's 20500 trees, two per cell on its median at half-integer q
        if abs(q - math.floor(q) - 0.5) < 1e-9:
            return 1.0 if self.ends == "C" else 2.0
        return None


class Taper(Scene):
    """The band narrows to its road `keep` (0 A, 1 B, 2 C) at its bottom end: the median ends in a nose at the start,
    the two outer curbs move in (each over its own along range: the band's end is cut obliquely by the cell grid, so
    the A side and the C side close at different q), inside the taper the markings are asphalt except the single
    road's yellow centre line, which runs straight from where the taper closes to the median nose (owner rule for
    the diagonal avenue merge, 2026-10-17). lo(q) / hi(q): the A side's / C side's outer curb (p) along the taper,
    from 0 / 3 to the kept road's edges keep / keep + 1; q_close: where both have arrived (diagbv.py fits them to the
    cells the drags leave)."""

    def __init__(self, keep, q_nose, lo, hi, q_close):
        Scene.__init__(self)
        self.keep, self.q_nose, self.lo, self.hi, self.q_close = keep, q_nose, lo, hi, q_close

    def nose(self, wx, wz):
        return "nose" if wx + wz >= self.q_nose - BP.NOSE * SQ2 else "normal"     # (wx, wz) is the real point

    def edge(self, side, q):
        return self.lo(q) if side == "A" else self.hi(q)

    def colour(self, z, r, wx, wz):
        p, q = wx - wz, wx + wz
        lo, hi = self.edge("A", q), self.edge("C", q)
        if p < lo or p >= hi:
            return CLEAR
        k = self.keep
        if q < self.q_nose and lo <= 0.0 and hi >= 3.0:
            return self.band(z, r, wx, wz)
        T = 256.0 * p
        cl = BP.centre_line(z, r)
        # the curbs: the stock outer edge band moved with the edge (the A side as a north edge, the C side turned)
        if (p - lo) * 256.0 < BP.CURB and lo > 0.0 or (p < 0.0 + BP.CURB / 256.0 and lo <= 0.0):
            CUR.q, CUR.off = q, 256.0 * lo
            return BP.s29(z, r, 0.0, (p - lo) * 256.0)
        if (hi - p) * 256.0 < BP.CURB:
            X, Z = turn(wx, wz)
            CUR.q, CUR.off = 3.0 - q, 256.0 * (3.0 - hi)
            return BP.s29(z, (r + 2) % 4, 0.0, (hi - p) * 256.0)
        if q >= self.q_nose:
            # the single road's centre line: from the nose (p 1.5) to the kept road's centre where the taper closes
            tt = min(1.0, max(0.0, (q - self.q_nose) / (self.q_close - self.q_nose)))
            CUR.q, CUR.off = q, 256.0 * k
            if cl is not None:
                pc = 384.0 + (256.0 * k + cl[0] - 384.0) * tt       # ends on the single road's own stock line
                if abs(T - pc) <= cl[1]:
                    return BP.s29(z, r, 0.0, cl[0] + (T - pc))
            zs = T - 256.0 * k                                          # the single road's own lane point
            if BP.LANE_N[0] <= zs <= BP.LANE_S[1] and (cl is None or abs(zs - cl[0]) > cl[1] + 10.0):
                return BP.s29(z, r, 0.0, zs)
            return BP.s29(z, r, 0.0, BP.fold(T - 256.0 * k if T >= 256.0 * k else 256.0 * k - T, BP.LANE_S))
        return self.band(z, r, wx, wz)



class Turned:
    """a bottom-end scene turned half a circle about (1.5, 0): the same end at the top of the band"""

    def __init__(self, scene):
        self.scene = scene

    def colour(self, z, r, wx, wz):
        X, Z = turn(wx, wz)
        return self.scene.colour(z, (r + 2) % 4, X, Z)

    def tree_points(self, cell):
        X, Z = cell
        return [turn(wx, wz) for (wx, wz) in self.scene.tree_points((2 - X, -1 - Z))]


class Cap(Scene):
    """All three roads end at the bottom of the band: past wz0 the band is closed by a curb that runs along the edges
    `ends` [('z', Zm) for wz <= Zm, ('x', Xm) for wx <= Xm] and the two outer curbs, corners rounded by `rho` cells
    (a convex rounded polygon); inside it plain asphalt (the markings stop at wz0), the median ends in a nose parallel
    to the closure (boulevard_paint.Cap is the straight boulevard's: a half ellipse across its last column)."""

    def __init__(self, wz0, ends, rho=0.35):
        Scene.__init__(self)
        self.wz0, self.ends, self.rho = wz0, ends, rho

    def nose(self, wx, wz):
        return "nose" if wz >= self.wz0 - BP.NOSE else "normal"

    def dist(self, wx, wz):
        """distance (world cells) from the closure's rounded boundary, > 0 inside"""
        p = wx - wz
        s = [p / SQ2, (3.0 - p) / SQ2]
        for kind, m in self.ends:
            s.append(m - (wz if kind == "z" else wx))
        rho = self.rho
        if min(s) >= rho:
            return min(s)
        return rho - math.sqrt(sum(max(0.0, rho - v) ** 2 for v in s))

    def colour(self, z, r, wx, wz):
        p, q = wx - wz, wx + wz
        if p < 0.0 or p >= 3.0:
            return CLEAR
        if wz < self.wz0:
            return self.band(z, r, wx, wz)
        d = self.dist(wx, wz)
        if d <= 0.0:
            return CLEAR
        CUR.q, CUR.off, CUR.wx, CUR.wz = q, 0.0, wx, wz
        zl = d * 256.0 * SQ2                                 # strip lane units across the curb (stock outer edge)
        if zl < BP.CURB:
            return BP.s29(z, r, 0.0, zl)
        return BP.s29(z, r, 0.0, BP.fold(256.0 * p, BP.LANE_S))
