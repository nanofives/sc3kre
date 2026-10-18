#!/usr/bin/env python3
r"""hwpaint.py - elevated highway art as world scenes with height (task hwcore, highway program 2026-10-18).

Shared by every highway-program stream (hwx, hwt, hwdx, hwdd): copy it verbatim, ask hwcore for changes.

Method (diagave_paint.py's world-scene painting, plus height). A scene is a set of DECKS in world coordinates (x, z in
cells, e = height in zoom-3 pixels, the unit netart.project uses; the stock highway deck is at e = H). Each output
pixel of each zoom x rotation frame of a cell is a ray; it is marched down through the cell's column (the volume over
the cell's diamond) and the first solid point it meets is coloured by sampling the STOCK highway frames at the same
point and view:
  * deck top   -> stock 73 (deck running along z) or 15051 (along x), or the stock diagonal band (11223/11224,
                  15052/15106) for a 45-degree heading, whichever runs nearest the deck's own heading (blended between
                  two), at the same across share from the outer parapet and the same world along-coordinate; on axis
                  decks the lane dashes are re-drawn from the world arc length (lanelines.py pattern, measured on 73);
  * walls      -> the stock outer wall (buttresses) of the axis piece or diagonal band facing that way (blended
                  between the two nearest), or the plain inner wall blended between the two visible axis faces;
  * cell-edge cuts, deck ends, abutments -> the stock end face (across the road);
  * slab decks (bridges, loop ramps) have a fascia (the top band of the stock wall) and open space under them,
    optional pillars (boxes with the stock inner-wall texture); a surface under another deck is shaded.
So a straight deck along z / x at height H in one cell reproduces 73 / 15051, and every cell cut from one scene meets
its neighbours exactly (same rays, same samples). Measured proof: `py -3.12 hwpaint.py proof <out>`.

Coordinates. World cell (X, Z) covers X <= x < X + 1, Z <= z < Z + 1. A cell's frames are painted for state 0 (slot r =
view r); netart.preview places it at "at": [-X, Z]. Lane frame of a stock piece: lx = (x - X) * 256, lz = (z - Z) *
256. Stock highway pieces in their own lane frame (measured, `hwpaint.py profile`): 73 runs along lane z, 15051 along
lane x; state 0 has its outer parapet at the high lane coordinate, state 2 at the low one. A straight highway along z
is 73.2 (low x) + 73.0 (high x); along x 15051.2 (low z) + 15051.0 (high z).

API (all a sibling needs):
    P = Path.line((x0, z0), (x1, z1)) | Path.arc((cx, cz), R, a0_deg, sweep_deg) | Path([seg, ...]) (chain)
        .offset(d)  -> the path moved d cells to its LEFT (left of the direction of travel = normal (-dz, dx))
        .reversed() -> the same centreline run the other way
    Deck(path, width=1.0, profile="hw" | "ramp", outer="right" | "left",
         height=H | ramp(h0, h1, s0, s1) | callable(s ndarray) -> ndarray,
         support="wall" | "slab", thick=SLAB, pillars=[(x, z), ...], pillar_w=0.14, clip=callable(wx, wz) -> bool
         ndarray, ends=(True, True) draw end faces at s = 0 / length, name="", slab=[(s0, s1)] bridge spans,
         gaps=[(s0, s1[, "outer" | "inner" | "both"])] parapet openings where a ramp joins: the top runs to the edge)
    highway_diag(path, ...) -> [Deck, Deck]: highway() on a 45-degree stock band median (x - z or x + z an
         integer): W_DIAG-wide carriageways read from the stock band pieces, meeting stock 11223/11224 or 15052/15106
    highway(path, height=H, **kw) -> [Deck, Deck]: the two carriageways (1 cell each) either side of `path`, outer
         parapets outward (the stock two-cell highway when `path` runs along a cell edge); the right-hand one runs
         along `path`, the left-hand one against it (traffic keeps right; hwlanes reads the decks' directions)
    ramp_deck(path, **kw) -> Deck: one-lane ramp (RAMP_W = 0.44 wide unless width= is given)
    Scene(decks)                      later decks win where two tops coincide (a ramp merging onto a deck)
    paint_cell(scene, (X, Z), out_dir, zooms=range(5), canvas=None) -> anchors dict (also written as anchors.json)
    paint_cells(scene, cells, root) -> {(X, Z): dir}   root/<X>_<Z>/z{z}_r{r}.png + anchors.json
    preview_cells(scene, cells, zoom, rot, extra=[{"at": [-X, Z], "piece": 73, "slot": 2}, ...]) -> PIL image
Heights: H (stock deck), H_LOW / H_HIGH (the stock X's lower and upper decks), SLAB (bridge slab thickness).

CLI:
    py -3.12 hwpaint.py profile                    measured stock geometry (deck profile, dash band, heights)
    py -3.12 hwpaint.py proof <out_dir>            73 / 15051 / curve 15127 repainted vs stock: match % + sheet
    py -3.12 hwpaint.py demo <out_dir>             demo sheet: one-lane loop arc, a bridge over a highway, a ramp
    py -3.12 hwpaint.py core <package_dir>         art of hwcore's proof pieces 21100 / 21101 (examples/highway_core)
Game art never goes in the repo: point <out_dir> at a gitignored path (verify/hwcore/art/...).
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", ".."))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from netmod import lanelines as LL  # noqa: E402
from netmod import netart as NA  # noqa: E402

H = 31.75                 # stock deck height, zoom-3 px (73 / 15051: frame top 63..64 zoom-4 px above the top vertex)
H_LOW = 16.0              # the stock X's lower highway (15107 arms: frame top 31 zoom-4 px above the top vertex)
H_HIGH = 47.5             # the stock X's upper highway (15150 arms: 95 zoom-4 px)
SLAB = 5.0                # bridge slab thickness (zoom-3 px)
DASH_ON = 0.5             # painted share of the 0.25-cell dash period on the stock deck (73 / 15051 zoom 4: 8 of 16)
RAMP_W = 0.44             # one-lane ramp width, cells (program decision 2026-10-18: hwx's geometry, W = 0.22)
W_DIAG = 0.63             # stock diagonal carriageway width across (11223/11224, 15052/15106 bands; zoom 4, at H)
GAP_OUT, GAP_IN = 0.28, 0.93   # th past which a parapet gap turns the stock edge (parapet, edge line / curb) to lane
CLEAR = (0, 0, 0, 0)

AXES = {(1, 0): (73, 0), (-1, 0): (73, 2), (0, 1): (15051, 0), (0, -1): (15051, 2)}   # outer normal -> stock piece
# stock diagonal bands (measured, `hwpaint.py proof`): family xmz = the line x - z = m (m integer), cells by role
# X - Z - m = -1 / 0 / +1; family xpz = the line x + z = m, role X + Z + 1 - m. Outer normal (unscaled) -> (family, side)
DIAG_PIECES = {"xmz": {-1: (11223, 2), 0: (11224, 0), 1: (11223, 0)},
               "xpz": {-1: (15052, 2), 0: (15106, 0), 1: (15052, 0)}}
DIAGS = {(1, -1): ("xmz", 1), (-1, 1): ("xmz", -1), (1, 1): ("xpz", 1), (-1, -1): ("xpz", -1)}
SQ2 = math.sqrt(2.0)
C45 = math.cos(math.pi / 4.0)


# ------------------------------------------------------------------------------------------------ stock sampling

class Stock:
    """Colour of a stock piece at a point of its own lane frame (lx, lz in 0..256) at height e, view r."""

    def __init__(self):
        self.fr = {}

    def frames(self, pid):
        if pid not in self.fr:
            self.fr[pid] = {k: (np.asarray(im.convert("RGBA")), LT) for k, (im, LT) in NA.stock_frames(pid).items()}
        return self.fr[pid]

    def __call__(self, pid, state, z, r, lx, lz, e=0.0):
        a, (L, T) = self.frames(pid)[(z, (state + r) & 3)]
        u, v = NA.rot_uv(1.0 - lx / 256.0, lz / 256.0, r)
        X, Y = NA.project(z, u, v, e)
        X, Y = int(math.floor(X + L)), int(math.floor(Y + T))
        if 0 <= X < a.shape[1] and 0 <= Y < a.shape[0]:
            return tuple(int(c) for c in a[Y, X])
        return CLEAR


STOCK = Stock()


# ------------------------------------------------------------------------------------------------ paths

class Line:
    def __init__(self, p0, p1):
        self.p0 = (float(p0[0]), float(p0[1]))
        dx, dz = p1[0] - p0[0], p1[1] - p0[1]
        self.length = math.hypot(dx, dz)
        self.d = (dx / self.length, dz / self.length)

    def project(self, wx, wz):
        rx, rz = wx - self.p0[0], wz - self.p0[1]
        s = rx * self.d[0] + rz * self.d[1]
        t = -rx * self.d[1] + rz * self.d[0]               # left normal (-dz, dx)
        return s, t

    def at(self, s):
        return (self.p0[0] + s * self.d[0], self.p0[1] + s * self.d[1]), self.d

    def reversed(self):
        a, _ = self.at(0.0)
        b, _ = self.at(self.length)
        return Line(b, a)

    def offset(self, o):
        n = (-self.d[1], self.d[0])
        a, _ = self.at(0.0)
        b, _ = self.at(self.length)
        return Line((a[0] + o * n[0], a[1] + o * n[1]), (b[0] + o * n[0], b[1] + o * n[1]))


class Arc:
    """centre c, radius R, start angle a0 (radians, from +x toward +z), signed sweep (positive = toward +z first)."""

    def __init__(self, c, R, a0, sweep):
        self.c, self.R, self.a0, self.sweep = (float(c[0]), float(c[1])), float(R), a0, sweep
        self.length = abs(sweep) * R
        self.sg = 1.0 if sweep >= 0 else -1.0

    def project(self, wx, wz):
        rx, rz = wx - self.c[0], wz - self.c[1]
        rho = np.hypot(rx, rz)
        th = np.arctan2(rz, rx)
        phi = (th - self.a0) * self.sg
        phi = np.mod(phi + math.pi - abs(self.sweep) / 2.0, 2 * math.pi) - math.pi + abs(self.sweep) / 2.0
        s = phi * self.R
        # direction of travel at angle th: sg * (-sin, cos); its left normal (-dz, dx) = sg * (-cos, -sin): inward
        t = self.sg * (self.R - rho)
        return s, t

    def at(self, s):
        th = self.a0 + self.sg * s / self.R
        p = (self.c[0] + self.R * math.cos(th), self.c[1] + self.R * math.sin(th))
        return p, (-self.sg * math.sin(th), self.sg * math.cos(th))

    def reversed(self):
        return Arc(self.c, self.R, self.a0 + self.sweep, -self.sweep)

    def offset(self, o):
        return Arc(self.c, self.R - self.sg * o, self.a0, self.sweep)


class Path:
    """A chain of Line / Arc segments (each should start where the previous ends). s = arc length from the start."""

    def __init__(self, segs):
        self.segs = list(segs)
        self.cum = [0.0]
        for g in self.segs:
            self.cum.append(self.cum[-1] + g.length)
        self.length = self.cum[-1]

    @staticmethod
    def line(p0, p1):
        return Path([Line(p0, p1)])

    @staticmethod
    def arc(c, R, a0_deg, sweep_deg):
        return Path([Arc(c, R, math.radians(a0_deg), math.radians(sweep_deg))])

    def then_line(self, length):
        """append a straight of `length` cells tangent to the end"""
        p, d = self.at(self.length)
        return Path(self.segs + [Line(p, (p[0] + d[0] * length, p[1] + d[1] * length))])

    def then_arc(self, R, sweep_deg):
        """append a tangent arc of radius R turning sweep_deg (positive = toward the left normal (-dz, dx))"""
        p, d = self.at(self.length)
        n = (-d[1], d[0])
        sg = 1.0 if sweep_deg >= 0 else -1.0
        c = (p[0] + sg * R * n[0], p[1] + sg * R * n[1])
        a0 = math.atan2(p[1] - c[1], p[0] - c[0])
        # Arc's positive sweep runs toward +angle; its travel direction sg*(-sin, cos) must equal d
        th_dir = (-math.sin(a0), math.cos(a0))
        s_arc = 1.0 if th_dir[0] * d[0] + th_dir[1] * d[1] > 0 else -1.0
        return Path(self.segs + [Arc(c, R, a0, s_arc * abs(math.radians(sweep_deg)))])

    def offset(self, o):
        return Path([g.offset(o) for g in self.segs])

    def reversed(self):
        """the same centreline run the other way (a height function of s must be mirrored by the caller)"""
        return Path([g.reversed() for g in reversed(self.segs)])

    def project(self, wx, wz):
        """-> (s, t) arrays: nearest segment whose span holds the point (t = signed offset, left positive); points
        beside no span get s outside [0, length]"""
        best_s = best_t = None
        for i, g in enumerate(self.segs):
            s, t = g.project(wx, wz)
            s = np.asarray(s, dtype=float)
            t = np.asarray(t, dtype=float)
            ok = (s >= -1e-6) & (s <= g.length + 1e-6)
            if i == 0:
                ok = ok | (s < 0)
            if i == len(self.segs) - 1:
                ok = ok | (s > g.length)
            key = np.where(ok, np.abs(t), np.inf)
            if best_s is None:
                best_s, best_t, best_k = s + self.cum[i], t, key
            else:
                take = key < best_k
                best_s = np.where(take, s + self.cum[i], best_s)
                best_t = np.where(take, t, best_t)
                best_k = np.where(take, key, best_k)
        return best_s, best_t

    def at(self, s):
        """-> ((x, z), unit direction) at arc length s (clamped to the path)"""
        s = min(max(s, 0.0), self.length)
        for i, g in enumerate(self.segs):
            if s <= self.cum[i + 1] or i == len(self.segs) - 1:
                return g.at(s - self.cum[i])


# ------------------------------------------------------------------------------------------------ heights

def ramp(h0, h1, s0, s1, ease=False):
    """height h0 up to s0, h1 from s1, linear (or smoothstep with ease=True) between: a rising or falling ramp"""
    def h(s):
        t = np.clip((np.asarray(s, dtype=float) - s0) / max(1e-9, s1 - s0), 0.0, 1.0)
        if ease:
            t = t * t * (3.0 - 2.0 * t)
        return h0 + (h1 - h0) * t
    return h


def _hfun(height):
    if callable(height):
        return height
    return lambda s: np.full(np.shape(s), float(height))


# ------------------------------------------------------------------------------------------------ stock profile

_PROF = {}


def _across(ax, th):
    """lane coordinate across a stock piece with outer normal `ax` at th (share of the width from its outer parapet)"""
    return 256.0 * (1.0 - th) if (ax[0] + ax[1]) > 0 else 256.0 * th


def deck_profile(z, ax=(1, 0)):
    """Measured on the stock piece AXES[ax] at zoom z, view 0 (cached): the dash band (th = share of the width from
    the outer parapet) where a full cell along the deck shows both white dash and asphalt, and the lane span."""
    k = (z, ax)
    if k in _PROF:
        return _PROF[k]
    pid, st = AXES[ax]
    n = 128
    alongs = [(j + 0.5) * 256.0 / 64 for j in range(64)]
    white, dark = [0] * n, [0] * n
    for i in range(n):
        acr = _across(ax, (i + 0.5) / n)
        for a in alongs:
            c = STOCK(pid, st, z, 0, acr, a, H) if ax[0] != 0 else STOCK(pid, st, z, 0, a, acr, H)
            if not c[3]:
                continue
            if min(c[:3]) >= 150:
                white[i] += 1
            elif max(c[:3]) < 135:
                dark[i] += 1
    band = [i for i in range(n) if 0.3 < (i + 0.5) / n < 0.75 and 0.12 * 64 <= white[i] <= 0.75 * 64]
    dash = None
    if band:                                             # the contiguous run nearest the stock dash line (th 0.58)
        c = min(band, key=lambda i: abs((i + 0.5) / n - 0.58))
        lo = hi = c
        while lo - 1 in band:
            lo -= 1
        while hi + 1 in band:
            hi += 1
        dash = ((lo - 0.5) / n, (hi + 1.5) / n)
    lane = [i for i in range(n) if dark[i] >= 0.6 * 64]
    _PROF[k] = {"dash": dash, "lane": ((min(lane) + 0.0) / n, (max(lane) + 1.0) / n) if lane else (0.27, 0.9)}
    return _PROF[k]


# ------------------------------------------------------------------------------------------------ decks

class Deck:
    def __init__(self, path, width=1.0, profile="hw", outer="right", height=H, support="wall", thick=SLAB,
                 pillars=(), pillar_w=0.14, clip=None, ends=(True, True), name="", fascia="inner", slab=(),
                 gaps=()):
        self.path, self.w, self.profile, self.outer = path, float(width), profile, outer
        self.fascia = fascia                             # slab edge material: 'inner' (plain concrete), 'outer', 'end'
        self.h = _hfun(height)
        self.support, self.thick = support, float(thick)
        self.slab = list(slab)                           # (s0, s1) spans that are slab on a wall deck: bridges
        # (s0, s1[, "outer" | "inner" | "both"]) spans where the deck's parapet / curb is open: the top runs to its
        # edge as lane (a ramp joins there; the ramp deck drawn after it goes on from that edge)
        self.gaps = [(g[0], g[1], g[2] if len(g) > 2 else "outer") for g in gaps]
        self.pillars, self.pw = list(pillars), pillar_w
        self.clip, self.ends, self.name = clip, ends, name
        self.phase = None

    # geometry (vectorised)
    def footprint(self, wx, wz):
        s, t = self.path.project(wx, wz)
        ins = (np.abs(t) <= self.w / 2.0) & (s >= 0.0) & (s <= self.path.length)
        if self.clip is not None:
            ins = ins & self.clip(wx, wz)
        return s, t, ins

    def t_out(self, t):
        """distance from the outer parapet (0) to the inner curb (w)"""
        return self.w / 2.0 + t if self.outer == "right" else self.w / 2.0 - t

    def bottom(self, top, s=None):
        if self.support != "wall":
            return top - self.thick
        b = np.zeros_like(top)
        if self.slab and s is not None:
            on = np.zeros(np.shape(top), dtype=bool)
            for s0, s1 in self.slab:
                on = on | ((s >= s0) & (s <= s1))
            b = np.where(on, top - self.thick, b)
        return b

    def gap_at(self, s):
        """-> set of sides ("outer", "inner") open at arc length s"""
        out = set()
        for s0, s1, side in self.gaps:
            if s0 <= s <= s1:
                out |= {"outer", "inner"} if side == "both" else {side}
        return out

    def is_slab(self, s):
        return self.support != "wall" or any(s0 <= s <= s1 for s0, s1 in self.slab)

    def max_height(self):
        ss = np.linspace(0.0, self.path.length, 64)
        return float(np.max(self.h(ss)))

    # frames along the deck
    def frame_at(self, s):
        """-> (point, direction, outer normal) at arc length s"""
        p, d = self.path.at(float(s))
        left = (-d[1], d[0])
        n = (-left[0], -left[1]) if self.outer == "right" else left
        return p, d, n

    def along(self, s):
        """world along-coordinate for the dashes: arc length + the start's projection on the start direction (so a
        straight axis deck uses the world x or z, as lanelines.py and the stock frames do)"""
        if self.phase is None:
            p, d = self.path.at(0.0)
            self.phase = p[0] * d[0] + p[1] * d[1]
        return self.phase + s


def highway(path, height=H, **kw):
    """the two carriageways either side of `path` (each 1 cell, outer parapets outward). Traffic keeps right (stock
    73.0 drives +z with its outer parapet on +x): the right-hand deck runs along `path`, the left-hand one along
    path.reversed(), each with its outer parapet on its own right. `height` (and `slab` spans) are given along `path`;
    the left deck reads them mirrored (s -> length - s)."""
    L = path.length
    hf = _hfun(height)
    kw_l = dict(kw)
    if kw.get("slab"):
        kw_l["slab"] = [(L - b, L - a) for a, b in kw["slab"]]
    if kw.get("gaps"):
        kw_l["gaps"] = [(L - g[1], L - g[0]) + tuple(g[2:]) for g in kw["gaps"]]
    return [Deck(path.offset(-0.5), 1.0, "hw", "right", height, name="hw_right", **kw),
            Deck(path.offset(0.5).reversed(), 1.0, "hw", "right", lambda s: hf(L - np.asarray(s, dtype=float)),
                 name="hw_left", **kw_l)]


def highway_diag(path, height=H, **kw):
    """highway() for a 45-degree `path` on a stock band median (x - z or x + z an integer): two carriageways W_DIAG
    wide, as stock 11223 / 11224 (x - z) or 15052 / 15106 (x + z), so a painted cell meets a stock band cell"""
    L = path.length
    hf = _hfun(height)
    kw_l = dict(kw)
    if kw.get("slab"):
        kw_l["slab"] = [(L - b, L - a) for a, b in kw["slab"]]
    if kw.get("gaps"):
        kw_l["gaps"] = [(L - g[1], L - g[0]) + tuple(g[2:]) for g in kw["gaps"]]
    h = W_DIAG / 2.0
    return [Deck(path.offset(-h), W_DIAG, "hw", "right", height, name="hwd_right", **kw),
            Deck(path.offset(h).reversed(), W_DIAG, "hw", "right", lambda s: hf(L - np.asarray(s, dtype=float)),
                 name="hwd_left", **kw_l)]


def ramp_deck(path, outer="right", **kw):
    kw.setdefault("width", RAMP_W)
    return Deck(path, profile="ramp", outer=outer, **kw)


# ------------------------------------------------------------------------------------------------ materials

def _nearest_axis(n):
    return max(AXES, key=lambda a: a[0] * n[0] + a[1] * n[1])


def _frac256(v):
    return (v % 1.0) * 256.0


def _view_dir(r):
    """world direction toward the viewer in view r (screen down = +d = v - u in the slot frame)"""
    u, v = 0.5, 0.5
    u1, v1 = NA.rot_uv(u - 0.01, v + 0.01, -r % 4)
    u0, v0 = NA.rot_uv(u, v, -r % 4)
    # lane: x = (1 - u) * 256, z = v * 256 -> world deltas
    dx, dz = -(u1 - u0), (v1 - v0)
    m = math.hypot(dx, dz)
    return dx / m, dz / m


VIEW = [_view_dir(r) for r in range(4)]


def _stretch_e(e, top, band=7.0):
    """height on a wall of a deck whose top is `top` -> height on the stock wall (top H): the top band (parapet) kept
    at its distance from the top, the rest stretched"""
    if top <= 0.5:
        return 0.5
    if top - e <= band or top <= band:
        return min(H - 0.01, max(0.01, H - (top - e)))
    return max(0.01, e * (H - band) / (top - band))


def wall_sample(kind, N, z, r, wx, wz, es, outer=None):
    """stock face of `kind` ('outer', 'inner', 'end') whose normal is the axis N, at the world point's along-face
    coordinate, stock height es. An end face is read from the stock piece with the deck's outer axis `outer` when
    that piece runs along N (its end faces show the same cross-section), else from the state-0 piece running along N."""
    ax = (int(N[0]), int(N[1]))
    if kind == "outer":
        pid, st = AXES[ax]
    elif kind == "inner":
        pid, st = AXES[(-ax[0], -ax[1])]
    elif outer is not None and outer[0] * ax[0] + outer[1] * ax[1] == 0:
        pid, st = AXES[outer]
    else:                                               # end face: a stock piece running along N
        pid, st = (73, 0) if ax[0] == 0 else (15051, 0)
    if ax[0] != 0:                                      # face normal along x: the face is a plane lx = const
        lx = 255.9 if ax[0] > 0 else 0.1
        lz = _frac256(wz)
    else:
        lz = 255.9 if ax[1] > 0 else 0.1
        lx = _frac256(wx)
    return STOCK(pid, st, z, r, lx, lz, es)


def _band_d_a(fam, wx, wz):
    """(across, along) coordinates of a diagonal band family: across = x - z (xmz) or x + z (xpz)"""
    return (wx - wz, wx + wz) if fam == "xmz" else (wx + wz, wx - wz)


def _band_pt(fam, d, a):
    return ((a + d) / 2.0, (a - d) / 2.0) if fam == "xmz" else ((d + a) / 2.0, (d - a) / 2.0)


def band_colour(fam, m, wx, wz, z, r, e=None):
    """the stock diagonal band whose median is m, at world point (wx, wz), height e (default the deck H)"""
    X, Z = math.floor(wx), math.floor(wz)
    role = (X - Z - m) if fam == "xmz" else (X + Z + 1 - m)
    pc = DIAG_PIECES[fam].get(role)
    if pc is None:
        return CLEAR
    return STOCK(pc[0], pc[1], z, r, (wx - X) * 256.0, (wz - Z) * 256.0, H if e is None else e)


def diag_wall_sample(nd, z, r, wx, wz, es):
    """the stock band's outer wall facing the diagonal nd (unscaled (+-1, +-1)), at the world point's along-band
    coordinate, stock height es"""
    fam, sg = DIAGS[nd]
    d, a = _band_d_a(fam, wx, wz)
    off = sg * W_DIAG * SQ2 * 0.996
    m = round(d - off)
    qx, qz = _band_pt(fam, m + off, a)
    return band_colour(fam, m, qx, qz, z, r, es)


def _dir_weights(n, diag=True, visible=None):
    """-> [(w, key)] of the stock directions nearest the unit normal n: the four axes (AXES keys) and, with diag, the
    four diagonals (DIAGS keys); w falls to 0 at 45 degrees, so an axis or diagonal heading reads its own piece alone"""
    out = []
    keys = list(AXES) + (list(DIAGS) if diag else [])
    for k in keys:
        L = math.hypot(k[0], k[1])
        if visible is not None and (k[0] * visible[0] + k[1] * visible[1]) <= 0:
            continue
        c = (k[0] * n[0] + k[1] * n[1]) / L
        if c > C45 + 1e-9:
            out.append((((c - C45) / (1.0 - C45)) ** 2, k))
    return sorted(out, reverse=True)[:2]


def face_colour(kind, n, z, r, wx, wz, es, outer=None):
    """a vertical face with outward normal n (unit, any heading): the visible axis faces blended by angle (the stock
    faces carry the scene's lighting: in view 0 a face toward +x reads about 150 grey-beige, one toward +z about 80)"""
    V = VIEW[r]
    acc, wsum = [0.0, 0.0, 0.0], 0.0
    if kind == "outer":                                  # an outer wall: the stock axis or diagonal face nearest it
        for w, k in _dir_weights(n, True, V):
            c = diag_wall_sample(k, z, r, wx, wz, es) if k in DIAGS else wall_sample(kind, k, z, r, wx, wz, es, outer)
            if c[3]:
                acc = [acc[i] + w * c[i] for i in range(3)]
                wsum += w
        if wsum > 0:
            return (int(acc[0] / wsum + 0.5), int(acc[1] / wsum + 0.5), int(acc[2] / wsum + 0.5), 255)
        acc, wsum = [0.0, 0.0, 0.0], 0.0
    for ax in AXES:
        if ax[0] * V[0] + ax[1] * V[1] <= 0:
            continue                                     # that stock face is turned away in this view
        w = max(0.0, ax[0] * n[0] + ax[1] * n[1]) ** 2
        if w <= 1e-6:
            continue
        c = wall_sample(kind, ax, z, r, wx, wz, es, outer)
        if not c[3]:
            continue
        acc = [acc[i] + w * c[i] for i in range(3)]
        wsum += w
    if wsum <= 0:
        return None
    return (int(acc[0] / wsum + 0.5), int(acc[1] / wsum + 0.5), int(acc[2] / wsum + 0.5), 255)


def dash_on(along):
    """the stock deck's dash pattern: lanelines.py's period and centring, DASH_ON long (the avenue lines are shorter)"""
    return abs((along / LL.DASH_PERIOD) % 1.0 - 0.5) < DASH_ON / 2.0


def _profile_th(deck, to, prof, s=None):
    """distance from the outer parapet (cells) -> share th of the stock carriageway's width it samples. The ramp's
    split (outer parapet + edge line | lane | inner curb) is the zoom-4 profile of 73 (the same world widths at every
    zoom), squeezed when the deck is too narrow for it; a parapet gap at s turns the edge into lane"""
    if deck.profile == "ramp":
        lane = deck_profile(4, (1, 0))["lane"]
        a, b = lane[0], 1.0 - lane[1]                    # outer part and inner part widths, from the stock profile
        if a + b > 0.8 * deck.w:
            k = 0.8 * deck.w / (a + b)
            a, b = a * k, b * k
        if to <= a:
            th = to
        elif to >= deck.w - b:
            th = 1.0 - (deck.w - to)
        else:                                            # the one lane: the stock lane span squeezed into it
            f = (to - a) / max(1e-6, deck.w - a - b)
            th = lane[0] + f * (lane[1] - lane[0])
    else:
        th = to / deck.w
    if s is not None and deck.gaps:
        open_ = deck.gap_at(s)
        if "outer" in open_ and th < GAP_OUT:
            th = GAP_OUT + (GAP_OUT - th) * 0.6
        if "inner" in open_ and th > GAP_IN:
            th = GAP_IN - (th - GAP_IN) * 0.6
    return min(0.999, max(0.001, th))


_XPROF = {}


def cross_profile(ax, z, r):
    """median colour across the stock deck AXES[ax] (128 bins of th, 32 samples along each) in view r, and whether
    each bin is a painted line (median light): a curve reads its lines here, so they stay continuous instead of
    aliasing into dots where the stock frame's 1-2 px lines are sampled at a slant"""
    k = (ax, z, r)
    if k in _XPROF:
        return _XPROF[k]
    pid, st = AXES[ax]
    cols, line = [], []
    for i in range(128):
        acr = _across(ax, (i + 0.5) / 128.0)
        cs = []
        for j in range(32):
            al = (j + 0.5) * 8.0
            c = STOCK(pid, st, z, r, acr, al, H) if ax[0] != 0 else STOCK(pid, st, z, r, al, acr, H)
            if c[3]:
                cs.append(c)
        if not cs:
            cols.append(CLEAR)
            line.append(False)
            continue
        cs.sort(key=lambda c: sum(c[:3]))
        m = cs[len(cs) // 2]
        cols.append(m)
        line.append(min(m[:3]) >= 125)
    dash = deck_profile(z, ax)["dash"]
    if dash is not None:                                 # the dash band is lane: dashes are drawn from the arc length
        for i in range(128):
            if dash[0] - 1.0 / 128 <= (i + 0.5) / 128.0 <= dash[1] + 1.0 / 128:
                line[i] = False
    _XPROF[k] = (cols, line)
    return _XPROF[k]


def _diag_colour(nd, deck, to, z, r, wx, wz, s=None):
    """the stock diagonal band (DIAGS[nd]) at the point: the band carriageway on the deck's outer side, at the same
    share th across and the same along-band coordinate, so a deck on a stock band position reads the band unchanged
    (its dashes included)"""
    fam, sg = DIAGS[nd]
    th = _profile_th(deck, to, None, s)
    d, a = _band_d_a(fam, wx, wz)
    for k in range(6):
        t2 = min(0.995, max(0.005, th + (0.0 if k == 0 else (0.012 * k if th < 0.5 else -0.012 * k))))
        off = sg * (1.0 - t2) * W_DIAG * SQ2
        m = round(d - off)
        qx, qz = _band_pt(fam, m + off, a)
        c = band_colour(fam, m, qx, qz, z, r)
        if c[3]:
            return c
    return CLEAR


def _axis_colour(ax, deck, to, z, r, wx, wz, smooth=False, s=None):
    """the stock deck AXES[ax] at the point: -> (colour, th, on_dash_band); a pixel on the stock dash band comes back
    as the lane asphalt beside it (reflected about the band edge), the caller draws the dashes"""
    pid, st = AXES[ax]
    prof = deck_profile(z, ax)
    th = _profile_th(deck, to, prof, s)
    along = _frac256(wz) if ax[0] != 0 else _frac256(wx)

    def sample(th2):
        acr = _across(ax, th2)
        return STOCK(pid, st, z, r, acr, along, H) if ax[0] != 0 else STOCK(pid, st, z, r, along, acr, H)

    c = sample(th)
    if smooth:
        cols, line = cross_profile(ax, z, r)
        i = min(127, int(th * 128.0))
        if line[i] and cols[i][3]:
            return cols[i], th, False
        if c[3] and min(c[:3]) >= 125:                   # a line pixel of the frame beside a non-line bin
            for j in range(1, 12):                       # the nearest asphalt across, same along
                for i2 in (i - j, i + j):
                    if 0 <= i2 < 128 and not line[i2]:
                        c2 = sample((i2 + 0.5) / 128.0)
                        if c2[3] and min(c2[:3]) < 125:
                            return c2, th, False
    dash = prof["dash"]
    band = dash is not None and dash[0] <= th <= dash[1]
    if band and not (c[3] and min(c[:3]) < 120):
        m = dash[0] - (th - dash[0]) - 0.01 if th - dash[0] < dash[1] - th else dash[1] + (dash[1] - th) + 0.01
        f = sample(m)
        c = f if f[3] else c
    if not c[3]:                                         # a frame-border pixel: step inward
        c = sample(min(0.99, max(0.01, th + (0.02 if th < 0.5 else -0.02))))
    return c, th, band


def deck_top_colour(deck, z, r, wx, wz, s, t):
    """deck surface: the two stock decks running nearest the deck's heading, blended by angle (one alone on an axis
    deck, so 73 / 15051 come back unchanged); dashes from the world arc length on the hw profile"""
    p, d, n = deck.frame_at(s)
    to = deck.t_out(t)
    ws = _dir_weights(n)                                 # the axis / diagonal stock decks nearest the heading
    ax0 = ws[0][1]
    smooth = ws[0][0] < 0.9997                           # off its stock direction by over about 1 degree: a curve
    if deck.profile == "hw" and z >= LL.MIN_ZOOM and ax0 in AXES:
        c0, th0, band0 = _axis_colour(ax0, deck, to, z, r, wx, wz, s=s)
        if band0 and dash_on(deck.along(s)):
            pid, st = AXES[ax0]
            acr = _across(ax0, th0)
            al = _frac256(wz) if ax0[0] != 0 else _frac256(wx)
            own = STOCK(pid, st, z, r, acr, al, H) if ax0[0] != 0 else STOCK(pid, st, z, r, al, acr, H)
            return own if own[3] and min(own[:3]) >= 120 else LL.white(z, wx, wz)
    acc, wsum = [0.0, 0.0, 0.0], 0.0
    for w, a in ws:
        if a in DIAGS:
            c = _diag_colour(a, deck, to, z, r, wx, wz, s)
        else:
            c, _, _ = _axis_colour(a, deck, to, z, r, wx, wz, smooth, s)
        if not c[3]:
            continue
        acc = [acc[i] + w * c[i] for i in range(3)]
        wsum += w
    if wsum <= 0:
        return CLEAR
    return (int(acc[0] / wsum + 0.5), int(acc[1] / wsum + 0.5), int(acc[2] / wsum + 0.5), 255)


# ------------------------------------------------------------------------------------------------ scene + ray march

class Scene:
    """decks; cut_faces=False leaves out the faces where a deck is cut by the cell's own boundary (always covered by
    the neighbour cell in game; 73 / 15051 draw them, the curved stock pieces 15127 / 15055 do not)"""

    def __init__(self, decks, cut_faces=True):
        self.decks = list(decks)
        self.cut_faces = cut_faces

    def max_height(self):
        return max(d.max_height() for d in self.decks) if self.decks else H

    def solid(self, wx, wz, e):
        """-> index array: the deck (or pillar: 1000 + deck) solid at each point, -1 none; later decks win"""
        out = np.full(np.shape(wx), -1, dtype=int)
        for i, d in enumerate(self.decks):
            s, t, ins = d.footprint(wx, wz)
            top = d.h(np.clip(s, 0.0, d.path.length))
            hit = ins & (e <= top) & (e >= d.bottom(top, s))
            out = np.where(hit, i, out)
            for (px, pz) in d.pillars:
                ps, _ = d.path.project(np.array([px]), np.array([pz]))
                ptop = float(d.h(np.clip(ps, 0.0, d.path.length))[0]) - d.thick
                ph = (np.abs(wx - px) <= d.pw / 2.0) & (np.abs(wz - pz) <= d.pw / 2.0) & (e <= ptop) & (e >= 0.0)
                out = np.where(ph & (out < 0), 1000 + i, out)
        return out

    def covered_above_v(self, wx, wz, e):
        """covered_above over arrays"""
        cov = np.zeros(np.shape(wx), dtype=bool)
        for d in self.decks:
            s, t, ins = d.footprint(wx, wz)
            top = d.h(np.clip(s, 0.0, d.path.length))
            cov = cov | (ins & (d.bottom(top, s) > e + 1.0))
        return cov

    def covered_above(self, wx, wz, e):
        """True where some deck's slab is above height e + 1 at (wx, wz)"""
        cov = False
        for d in self.decks:
            s, t, ins = d.footprint(np.array([wx]), np.array([wz]))
            if not ins[0]:
                continue
            top = float(d.h(np.clip(s, 0.0, d.path.length))[0])
            if d.bottom(np.array([top]), np.array([float(s[0])]))[0] > e + 1.0:
                cov = True
        return cov


SHADE = 0.58              # surface under another deck (the stock underpass interior is about this dark)


def _rays(z, r, X, Z, w, h, L, T):
    """per pixel: world (x, z) at e = 0 and its change per unit e, for the canvas of a state-0 cell"""
    W = NA.TILE_W[z]
    xx, yy = np.meshgrid(np.arange(w) + 0.5 - L, np.arange(h) + 0.5 - T)
    sp = 2.0 * xx / W
    d0 = 4.0 * yy / W
    out = []
    for de in (0.0, 1.0):
        d = d0 + de / 16.0
        u, v = (sp - d) / 2.0, (sp + d) / 2.0
        for _ in range((-r) % 4):
            u, v = v, 1.0 - u
        out.append((X + (1.0 - u), Z + v))
    (x0, z0), (x1, z1) = out
    return x0, z0, x1 - x0, z1 - z0


def render_cell(scene, cell, z, r, canvas=None, mask_only=False):
    """-> (RGBA image, (L, T)) of cell `cell` at zoom z, view r (mask_only: -> (bool array of hit pixels, (L, T)))"""
    X, Z = cell
    W = NA.TILE_W[z]
    emax = scene.max_height() + 1.0
    if canvas is not None:
        cpid, cst = canvas
        im0, (L, T) = NA.stock_frames(cpid)[(z, (cst + r) & 3)]
        w, h = im0.size
    else:
        w, L = W, 0
        T = int(math.ceil(W / 4.0 + emax * W / 64.0)) + 1
        h = T + W // 4 + 2
    x0, z0, dx, dz = _rays(z, r, X, Z, w, h, L, T)
    # the e interval where the ray is inside the cell column: X <= x0 + e dx < X + 1 (same for z)
    lo = np.zeros_like(x0)
    hi = np.full_like(x0, emax)
    for p0, dp, a in ((x0, dx, X), (z0, dz, Z)):
        with np.errstate(divide="ignore", invalid="ignore"):
            e1 = (a - p0) / dp
            e2 = (a + 1 - p0) / dp
        el = np.where(dp != 0, np.minimum(e1, e2), np.where((p0 >= a) & (p0 < a + 1), -np.inf, np.inf))
        eh = np.where(dp != 0, np.maximum(e1, e2), np.where((p0 >= a) & (p0 < a + 1), np.inf, -np.inf))
        lo = np.maximum(lo, el)
        hi = np.minimum(hi, eh)
    live = hi > lo
    de = 0.25 * (2 ** (4 - z)) / 2.0
    hit_e = np.full(x0.shape, np.nan)
    hit_i = np.full(x0.shape, -1, dtype=int)
    ys, xs = np.nonzero(live)
    X0, Z0, DX, DZ, LO = x0[ys, xs], z0[ys, xs], dx[ys, xs], dz[ys, xs], lo[ys, xs]
    E = hi[ys, xs].copy()
    act = np.arange(len(ys))
    while len(act):
        ee = E[act]
        idx = scene.solid(X0[act] + ee * DX[act], Z0[act] + ee * DZ[act], ee)
        got = idx >= 0
        g = act[got]
        hit_e[ys[g], xs[g]] = ee[got]
        hit_i[ys[g], xs[g]] = idx[got]
        act = act[~got]
        last = E[act] <= LO[act] + 1e-9
        E[act] = np.maximum(E[act] - de, LO[act])
        act = act[~last]
    if mask_only:
        return hit_i >= 0, (L, T)
    # refine each hit between e_hit and e_hit + de (bisection, 7 steps): the first solid height from above
    ys, xs = np.nonzero(hit_i >= 0)
    a = hit_e[ys, xs]                                    # solid
    b = a + de                                           # free: above the hit, or outside the column
    for _ in range(7):
        m = (a + b) / 2.0
        mx, mz = x0[ys, xs] + m * dx[ys, xs], z0[ys, xs] + m * dz[ys, xs]
        sid = scene.solid(mx, mz, m)
        sol = (sid >= 0) & (mx >= X) & (mx <= X + 1) & (mz >= Z) & (mz <= Z + 1)    # inside this cell's column
        a = np.where(sol, m, a)
        b = np.where(sol, b, m)
    out = np.zeros((h, w, 4), dtype=np.uint8)
    if not len(ys):
        return Image.fromarray(out, "RGBA"), (L, T)
    WX, WZ = x0[ys, xs] + a * dx[ys, xs], z0[ys, xs] + a * dz[ys, xs]
    PX, PZ = x0[ys, xs] + b * dx[ys, xs], z0[ys, xs] + b * dz[ys, xs]
    IDX = scene.solid(WX, WZ, a)
    n = len(ys)
    S, Tt, TOP = np.zeros(n), np.zeros(n), np.zeros(n)
    PS, PT, PTOP = np.zeros(n), np.zeros(n), np.zeros(n)
    PINS = np.zeros(n, dtype=bool)
    for i, d in enumerate(scene.decks):
        m = IDX == i
        if not m.any():
            continue
        s1, t1, _ = d.footprint(WX[m], WZ[m])
        s2, t2, in2 = d.footprint(PX[m], PZ[m])
        S[m], Tt[m], TOP[m] = s1, t1, d.h(np.clip(s1, 0.0, d.path.length))
        PS[m], PT[m], PINS[m], PTOP[m] = s2, t2, in2, d.h(np.clip(s2, 0.0, d.path.length))
    COV = scene.covered_above_v(WX, WZ, a)
    for k in range(n):
        rec = (int(IDX[k]), float(WX[k]), float(WZ[k]), float(a[k]), float(PX[k]), float(PZ[k]), float(b[k]),
               float(S[k]), float(Tt[k]), float(TOP[k]), float(PS[k]), float(PT[k]), bool(PINS[k]), float(PTOP[k]))
        c = colour_hit(scene, rec, z, r, X, Z)
        if c is None or not c[3]:
            continue
        if COV[k] and IDX[k] < 1000:                     # a pillar holds its own deck up: no shade
            c = (int(c[0] * SHADE), int(c[1] * SHADE), int(c[2] * SHADE), c[3])
        out[ys[k], xs[k]] = c
    return Image.fromarray(out, "RGBA"), (L, T)


def colour_hit(scene, rec, z, r, X, Z):
    """colour of the solid point (wx, wz, e) of deck i, entered from the free point (px, pz, ep) just above / in front;
    s, t, top = the deck's frame at the point, ps, pt, pins, ptop = at the free point (rec, from render_cell)"""
    i, wx, wz, e, px, pz, ep, s, t, top, ps, pt, pins, ptop = rec
    if i < 0:
        return None
    if i >= 1000:                                        # pillar: a box face, inner-wall texture
        d = scene.decks[i - 1000]
        best = min(d.pillars, key=lambda q: (q[0] - wx) ** 2 + (q[1] - wz) ** 2)
        ox, oz = px - best[0], pz - best[1]
        n = (1.0 if ox > 0 else -1.0, 0.0) if abs(ox) >= abs(oz) else (0.0, 1.0 if oz > 0 else -1.0)
        return face_colour("inner", n, z, r, wx, wz, max(0.5, min(H - 8.0, e)))
    d = scene.decks[i]
    in_cell = X <= px < X + 1 and Z <= pz < Z + 1
    if not in_cell and pins:
        # the deck goes on past the cell's boundary: a cut, drawn as the stock end face of a piece running across it
        # (the neighbour cell's art covers it in game)
        if px < X:
            n = (-1.0, 0.0)
        elif px >= X + 1:
            n = (1.0, 0.0)
        elif pz < Z:
            n = (0.0, -1.0)
        else:
            n = (0.0, 1.0)
        if top - e < 0.6 or ep > ptop:
            return deck_top_colour(d, z, r, wx, wz, s, t)
        if not scene.cut_faces:
            return None
        nd = d.frame_at(s)[2]
        wd = _dir_weights(nd)
        if wd and wd[0][1] in DIAGS:                     # a diagonal deck: the stock band's own cell-edge face
            fam, sg = DIAGS[wd[0][1]]
            th = _profile_th(d, d.t_out(t), None)
            dd, aa = _band_d_a(fam, wx, wz)
            off = sg * (1.0 - th) * W_DIAG * SQ2
            m = round(dd - off)
            qx, qz = _band_pt(fam, m + off, aa)
            qx, qz = qx - 0.002 * n[0], qz - 0.002 * n[1]     # into the cell the face belongs to
            c = band_colour(fam, m, qx, qz, z, r, _stretch_e(e, top))
            if c[3]:
                return c
        oax = _nearest_axis(nd)
        c = wall_sample("end", n, z, r, wx, wz, _stretch_e(e, top), oax)
        if not c[3]:
            c = face_colour("end", n, z, r, wx, wz, _stretch_e(e, top), oax)
        return c
    if pins and ep >= ptop - 1e-6:
        return deck_top_colour(d, z, r, wx, wz, s, t)
    if abs(pt) > d.w / 2.0 and 0.0 <= ps <= d.path.length:
        side_left = pt > 0
        _, dd, _ = d.frame_at(s)
        left = (-dd[1], dd[0])
        n = left if side_left else (-left[0], -left[1])
        outer = (side_left and d.outer == "left") or (not side_left and d.outer == "right")
        kind = d.fascia if d.is_slab(s) else ("outer" if outer else "inner")
        return face_colour(kind, n, z, r, wx, wz, _stretch_e(e, top), _nearest_axis(d.frame_at(s)[2]))
    # a deck end, an abutment under a slab, or a clip edge: the stock end face facing the free point
    _, dd, _ = d.frame_at(s)
    n = (-dd[0], -dd[1]) if ps < s else dd
    return face_colour("end", n, z, r, wx, wz, _stretch_e(e, top), _nearest_axis(d.frame_at(s)[2]))


def _shade(scene, c, wx, wz, e):
    if c is None or not c[3]:
        return c
    if scene.covered_above(wx, wz, e):
        return (int(c[0] * SHADE), int(c[1] * SHADE), int(c[2] * SHADE), c[3])
    return c


# ------------------------------------------------------------------------------------------------ output

def _crop(im, LT):
    bb = im.getbbox()
    if not bb:
        return im.crop((0, 0, 1, 1)), LT
    return im.crop(bb), (LT[0] - bb[0], LT[1] - bb[1])


def paint_cell(scene, cell, out_dir, zooms=range(NA.ZOOMS), canvas=None, crop=True):
    """frames z{z}_r{r}.png of world cell `cell` + anchors.json (registration point = the cell's left ground vertex)"""
    os.makedirs(out_dir, exist_ok=True)
    anchors = {}
    for z in zooms:
        for r in range(NA.ROTS):
            im, LT = render_cell(scene, cell, z, r, canvas)
            if crop and canvas is None:
                im, LT = _crop(im, LT)
            name = NA.frame_name(z, r)
            im.save(os.path.join(out_dir, name))
            anchors[name] = [int(LT[0]), int(LT[1])]
    with open(os.path.join(out_dir, "anchors.json"), "w", encoding="utf-8") as f:
        json.dump(anchors, f, indent=1)
    return anchors


def paint_cells(scene, cells, root, zooms=range(NA.ZOOMS)):
    out = {}
    for c in cells:
        d = os.path.join(root, "%d_%d" % c)
        paint_cell(scene, c, d, zooms)
        out[tuple(c)] = d
    return out


def scene_cells(scene, margin=0.0):
    """cells any deck touches (sampled every 1/16 cell along each deck, across its width)"""
    cells = set()
    for d in scene.decks:
        n = max(2, int(d.path.length * 16) + 1)
        for k in range(n):
            s = d.path.length * k / (n - 1)
            p, dd = d.path.at(s)
            left = (-dd[1], dd[0])
            for j in range(9):
                o = (j / 8.0 - 0.5) * (d.w + 2 * margin)
                cells.add((int(math.floor(p[0] + o * left[0])), int(math.floor(p[1] + o * left[1]))))
    return sorted(cells)


def preview_cells(scene, cells, zoom, rot, root, extra=(), paint=True):
    """paint `cells` at one zoom into root/<X>_<Z>/ (paint=False: reuse what is there) and assemble them (plus stock
    `extra` cells, e.g. {"at": [-X, Z], "piece": 73, "slot": 2}) with netart.preview"""
    layout = []
    for c in cells:
        d = os.path.join(root, "%d_%d" % c)
        if paint:
            paint_cell(scene, c, d, zooms=[zoom])
        layout.append({"at": [-c[0], c[1]], "dir": d, "slot": 0})
    layout += list(extra)
    return NA.preview({"cells": layout}, None, zooms=[zoom], rots=[rot])[(zoom, rot)]


# ------------------------------------------------------------------------------------------------ checks

def compare(a, b, tol=24):
    """pixel match of two same-size RGBA frames: share of pixels opaque in either that are opaque in both and within
    `tol` per channel, plus the share exactly equal"""
    A, B = np.asarray(a.convert("RGBA")).astype(int), np.asarray(b.convert("RGBA")).astype(int)
    oa, ob = A[..., 3] > 0, B[..., 3] > 0
    anyo = oa | ob
    both = oa & ob
    near = both & (np.abs(A[..., :3] - B[..., :3]).max(axis=2) <= tol)
    exact = both & (np.abs(A[..., :3] - B[..., :3]).max(axis=2) == 0)
    n = max(1, int(anyo.sum()))
    return {"px": n, "near": near.sum() / n, "exact": exact.sum() / n, "silhouette": both.sum() / n}


def _side_by_side(pairs, scale=1):
    W = sum(max(a.width, b.width) + 8 for a, b in pairs)
    Hh = max(a.height + b.height + 12 for a, b in pairs)
    sheet = Image.new("RGBA", (W, Hh), (54, 88, 54, 255))
    x = 0
    for a, b in pairs:
        sheet.alpha_composite(a, (x, 0))
        sheet.alpha_composite(b, (x, a.height + 6))
        x += max(a.width, b.width) + 8
    if scale != 1:
        sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    return sheet


def proof_scenes():
    """name -> (scene, cell, stock piece, state): stock pieces rebuilt from scratch"""
    out = {
        "73.0": (Scene([Deck(Path.line((0.5, -2.0), (0.5, 3.0)), 1.0, "hw", "right")]), (0, 0), 73, 0),
        "73.2": (Scene([Deck(Path.line((0.5, -2.0), (0.5, 3.0)), 1.0, "hw", "left")]), (0, 0), 73, 2),
        "15051.0": (Scene([Deck(Path.line((-2.0, 0.5), (3.0, 0.5)), 1.0, "hw", "left")]), (0, 0), 15051, 0),
        "15051.2": (Scene([Deck(Path.line((-2.0, 0.5), (3.0, 0.5)), 1.0, "hw", "right")]), (0, 0), 15051, 2),
    }
    # stock curve 15127 (the On-ramp tool's corner piece): a one-lane slab deck on a tight arc round a point just
    # past the cell's front corner. Geometry FITTED to its frames (zoom 3, all views, colour match; `proof` reports
    # the result): centre (1.375, 1.375), radius 1.136, width 0.64, deck at e 31.9, slab 10.25 thick, parapet on the
    # concave side.
    arc = Path.arc((1.375, 1.375), 1.136, -195.0, 120.0)
    # stock diagonal bands, repainted with highway_diag on their medians (x - z = 0; x + z = 1)
    bx = highway_diag(Path.line((-3.0, -3.0), (4.0, 4.0)))
    bp = highway_diag(Path.line((4.5, -3.5), (-3.5, 4.5)))
    out["11224.0"] = (Scene(bx), (0, 0), 11224, 0)
    out["11223.0"] = (Scene(bx), (1, 0), 11223, 0)
    out["11223.2"] = (Scene(bx), (0, 1), 11223, 2)
    out["15106.0"] = (Scene(bp), (0, 0), 15106, 0)
    out["15052.0"] = (Scene(bp), (1, 0), 15052, 0)
    out["15052.2"] = (Scene(bp), (-1, 0), 15052, 2)
    out["15127.0"] = (Scene([ramp_deck(arc, outer="left", width=0.64, height=31.875, support="slab", thick=10.25)],
                            cut_faces=False), (0, 0), 15127, 0)
    return out


def cmd_profile(a):
    for z in range(NA.ZOOMS):
        for ax in AXES:
            print("zoom", z, "piece %d.%d" % AXES[ax], deck_profile(z, ax))
    for pid in (73, 15051, 15107, 15150, 15113):
        fr = NA.stock_frames(pid)
        for r in range(4):
            im, (L, T) = fr[(4, r)]
            print("piece %d slot %d: frame %s anchor %s -> top %.1f zoom-4 px above the top vertex = e %.2f"
                  % (pid, r, im.size, (L, T), T - 32, (T - 32) / 2.0))


def cmd_proof(a):
    os.makedirs(a.out, exist_ok=True)
    rep = {}
    pairs = {z: [] for z in (3, 4)}
    curve, diag = [], []
    for name, (sc, cell, pid, st) in proof_scenes().items():
        for z in range(NA.ZOOMS):
            for r in range(4):
                im, LT = render_cell(sc, cell, z, r, canvas=(pid, st))
                ref, _ = NA.stock_frames(pid)[(z, (st + r) & 3)]
                m = compare(im, ref)
                rep["%s z%d r%d" % (name, z, r)] = m
                if z in pairs and name[:2] in ("73", "15") and name[:5] not in ("15127", "15106", "15052"):
                    pairs[z].append((ref, im))
                if z == 4 and name == "15127.0":
                    curve.append((ref, im))
                if z == 4 and name[:5] in ("11224", "11223", "15106", "15052"):
                    diag.append((ref, im))
        print(name, "near %.3f exact %.3f (z4 mean)" % (
            np.mean([rep["%s z4 r%d" % (name, r)]["near"] for r in range(4)]),
            np.mean([rep["%s z4 r%d" % (name, r)]["exact"] for r in range(4)])))
    for z in pairs:
        _side_by_side(pairs[z], 2 if z == 3 else 1).save(os.path.join(a.out, "proof_straight_z%d.png" % z))
    _side_by_side(curve, 2).save(os.path.join(a.out, "proof_curve15127_z4.png"))
    _side_by_side(diag, 1).save(os.path.join(a.out, "proof_diagonal_z4.png"))
    with open(os.path.join(a.out, "proof.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)


def core_scenes():
    """hwcore's proof pieces (examples/highway_core): one carriageway descending from H to the ground across the cell
    toward +z at state 0; 21100 has the outer parapet on +x (as 73.0), 21101 on -x (as 73.2)"""
    line = Path.line((0.5, -1.0), (0.5, 2.0))
    h = ramp(H, 0.0, 1.0, 2.0)
    return {21100: Scene([Deck(line, 1.0, "hw", "right", height=h)]),
            21101: Scene([Deck(line, 1.0, "hw", "left", height=h)])}


def cmd_core(a):
    for pid, sc in core_scenes().items():
        d = os.path.join(a.pkg, "art", str(pid))
        paint_cell(sc, (0, 0), d)
        print(pid, "->", d)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("profile")
    p = sub.add_parser("proof")
    p.add_argument("out")
    p = sub.add_parser("demo")
    p.add_argument("out")
    p = sub.add_parser("core")
    p.add_argument("pkg")
    a = ap.parse_args(argv)
    {"profile": cmd_profile, "proof": cmd_proof, "demo": lambda a: cmd_demo(a), "core": lambda a: cmd_core(a)}[a.cmd](a)


def demo_scenes():
    """name -> (scene, stock extra cells): the shapes the shape streams need, built only from this module's API"""
    out = {}
    # a highway along x at stock height, a second one along z rising over it on a slab bridge (stock X heights)
    low = highway(Path.line((-4.0, 0.0), (5.0, 0.0)))
    up_h = lambda s: np.minimum(ramp(H, H_HIGH, 1.0, 3.5)(s), ramp(H_HIGH, H, 6.5, 9.0)(s))   # noqa: E731
    up = highway(Path.line((0.0, -5.0), (0.0, 5.0)), height=up_h, slab=[(3.7, 6.3)])
    out["bridge"] = Scene(low + up)
    # a one-lane loop ramp: 270 degrees, radius 1.5, slab on pillars, rising from the stock X's lower deck to H
    loop = Path.arc((0.0, 0.0), 1.5, 90.0, 270.0)
    piers = []
    for k in range(5):
        pt, _ = loop.at(loop.length * (k + 0.5) / 5.0)
        piers.append(pt)
    out["loop"] = Scene([ramp_deck(loop, outer="right", height=ramp(H_LOW, H, 0.0, loop.length), support="slab",
                                   pillars=piers)])
    # a one-lane ramp rising from the ground onto deck height beside a straight carriageway, walls down to the ground
    out["ramp"] = Scene([Deck(Path.line((-1.5, -4.0), (-1.5, 4.0)), 1.0, "hw", "right"),
                         ramp_deck(Path.line((-0.69, 4.0), (-0.69, -4.0)), outer="left",
                                   height=ramp(0.0, H, 0.0, 4.0))])
    return out


def cmd_demo(a):
    os.makedirs(a.out, exist_ok=True)
    shots = []
    for name, sc in demo_scenes().items():
        cells = scene_cells(sc)
        done = set()
        for z, r in ((3, 0), (3, 1), (4, 2)):
            im = preview_cells(sc, cells, z, r, os.path.join(a.out, name), paint=z not in done)
            done.add(z)
            im.save(os.path.join(a.out, "demo_%s_z%d_r%d.png" % (name, z, r)))
            shots.append(im)
        print(name, len(cells), "cells")
    W = sum(i.width for i in shots[:3])
    rows = [shots[i:i + 3] for i in range(0, len(shots), 3)]
    Hh = sum(max(i.height for i in row) for row in rows)
    sheet = Image.new("RGBA", (max(sum(i.width for i in row) for row in rows), Hh), (20, 20, 20, 255))
    y = 0
    for row in rows:
        x = 0
        for im in row:
            sheet.paste(im, (x, y))
            x += im.width
        y += max(i.height for i in row)
    sheet.save(os.path.join(a.out, "demo_sheet.png"))
    print(os.path.join(a.out, "demo_sheet.png"), sheet.size)


if __name__ == "__main__":
    main()
