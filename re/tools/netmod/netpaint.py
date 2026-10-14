"""netpaint.py -- procedural ground art for new network pieces, drawn with the engine's own projection.

Task roundabout2 (2026-10-13), re/analysis/NET_ART.md section 11. A plan (JSON) describes a junction in the lane
frame of state 0 (x, z in 0..256, the frame of TrBlkAtt nodes, NET_LANES.md 2.2). Every output pixel of every
zoom x rotation slot is unprojected to that frame (netart.unproject, the inverse of the SIMSPR draw point,
NET_ART.md 2), classified, and coloured by SAMPLING A STOCK STRAIGHT ROAD'S FRAME of the same zoom at a mapped
point: a band is the stock road's cross profile (sidewalk, gutter, edge line, asphalt, centre line) bent along a
path. So the art uses the stock palette and dither at every zoom, and where a band is the straight road itself (an
arm) the pixels are the stock pixels, which makes the seam against a stock road cell exact by construction.
No game pixels are stored: the plan is JSON, the colours are read from the installed game at build time.

    py -3.12 re/tools/netmod/netpaint.py paint <plan.json> <out_dir>            # z{z}_r{r}.png (netpack png_dir)
    py -3.12 re/tools/netmod/netpaint.py seams <plan.json> <out_dir>            # arm seam vs the stock road

Lane frame <-> slot-0 tile coordinates (netart.py): u = 1 - x / 256, v = z / 256 (x- = NE edge, z- = NW edge,
x+ = SW, z+ = SE in view 0, NET_ART.md 2). The stock road's profile is read across x on its frame of slot
(r + 1) & 3, where it runs along z (29 slot k+2 == slot k, measured).

Only one plan kind exists so far: "pinwheel_roundabout", the 2x2 one-way mini roundabout of package roundabout
(one quarter cell, state 0; the other three cells are the same piece in states 3, 2, 1 round the block centre).
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from PIL import Image  # noqa: E402

from netmod import netart as NA  # noqa: E402

TAU = 2.0 * math.pi


# ------------------------------------------------------------------------------------------- stock sampler

class RoadSampler:
    """Colours of a stock straight road (default 29) addressed by (x', t): x' = position across the road in the
    lane frame of an arm running along z (0..256), t = position along it (wraps every 256)."""

    def __init__(self, piece=29):
        self.fr = NA.stock_frames(piece)
        self.px = {k: (im.load(), im.size, LT) for k, (im, LT) in self.fr.items()}

    def paint_white(self, z):
        """The brightest colour of the stock road's frames at this zoom (its edge line paint): road markings."""
        best = (0, 0, 0, 0)
        for (zz, _r), (px, (w, h), _LT) in self.px.items():
            if zz != z:
                continue
            for y in range(h):
                for x in range(w):
                    c = px[x, y]
                    if c[3] >= 128 and sum(c[:3]) > sum(best[:3]):
                        best = c
        return best

    def __call__(self, z, r, xp, t):
        px, (w, h), (L, T) = self.px[(z, (r + 1) & 3)]
        m = 4.0 / NA.TILE_W[z]                   # one pixel row, in tiles: the stock rim lies within it
        if not -256.0 * m <= t <= 256.0 * (1.0 + m):   # wrap, but keep the rim just outside the tile edges
            t %= 256.0
        u = min(1.0 + m, max(-m, 1.0 - xp / 256.0))
        v = min(1.0 + m, max(-m, t / 256.0))
        for k in range(8):                       # step towards the tile centre when the point hits the outer rim
            su, sv = NA.rot_uv(u, v, r)
            X, Y = NA.project(z, su, sv)
            X, Y = int(math.floor(X + L)), int(math.floor(Y + T))
            if 0 <= X < w and 0 <= Y < h and px[X, Y][3] >= 128:
                return px[X, Y]
            u, v = u + (0.5 - u) * 0.02, v + (0.5 - v) * 0.02
        return (0, 0, 0, 0)


# ------------------------------------------------------------------------------- pinwheel mini roundabout

class PinwheelRoundabout:
    """One quarter of a 2x2 one-way mini roundabout (state 0 of the piece; NET_LANES.md frame).

    Block coordinates P = (x, z - 256): the block centre O is the cell corner (x 0, z 256). Arm on side z-
    (the stock road comes in along z centred on the profile centre), side x+ closed, sides x- and z+ are the
    neighbouring quarters. Cars (quarter.lanes.json) drive: entry straight at x 175 from z- to z+ (tangent to the
    ring), ring = the circle of radius 175 about O, exit = a right turn of radius 80 about E = (0, -256)
    (the corner x-, z-). Painted as three bent copies of the stock road profile:
      entry band  x' = P.x                       (x' >= c0, the inbound half and its outer sidewalk)
      exit band   x' = |P - E| + adj * a / 90     (x' <= c0, the outbound half, a = angle from the arm edge)
      ring        x' = |P|                        (|P| < ring_out: the island edge line and the asphalt)
    c0 = the profile centre (the middle of the double centre line). adj = 2 c0 - 256 makes the exit band meet the
    next quarter's entry band (mirror profile) on the shared edge. Asphalt shade = the stock lane shade at the
    distance from the nearest lane centre line, so the bands join without a step."""

    def __init__(self, plan, sample):
        p = plan
        self.s = sample
        self.c0 = p.get("profile_centre", 129.5)
        self.lane_in = p.get("lane_in", 175.0)           # entry / ring lane (inbound half of the arm)
        self.lane_out = p.get("lane_out", 80.0)          # exit lane (outbound half)
        self.ring_out = p.get("ring_out", 212.0)         # outer limit of the ring asphalt (start of white line)
        self.asph_in = tuple(p.get("asphalt_in", [136.0, 211.0]))     # asphalt x' range, inbound half
        self.asph_out = tuple(p.get("asphalt_out", [48.0, 123.0]))    # asphalt x' range, outbound half
        self.edge_in = p.get("edge_in", 211.0)           # x' beyond which the entry band keeps its own paint
        self.edge_out = p.get("edge_out", 48.0)          # x' below which the exit band keeps its own paint
        self.yellow_w = p.get("yellow_width", 6.5)       # single yellow line on the island edge: x' c0 .. c0+w
        isl = p.get("island", {})
        self.gutter_x = isl.get("gutter_xp", 40.0)       # island edge sampled as the stock outer edge from here
        self.curb = isl.get("curb", 18.0)                # width of the island apron (stock sidewalk), units
        self.inner_curb = isl.get("inner_curb", 5.0)     # curb ring between the apron and the raised centre
        self.adj = 2.0 * self.c0 - 256.0
        self.arrows = p.get("arrows", [])
        self.dash = p.get("give_way", {})
        self.white = {}                                  # marking paint per zoom (RoadSampler.paint_white)
        yl = p.get("yellow_xp", [131.0, 136.0])         # the island edge line is the stock road's right yellow
        self.yellow_xp = tuple(yl)                       # line (x' 131..136) stretched over yellow_width
        self.stub = p.get("arm_stub", 12.0)              # depth of the arm edge strip drawn as the straight road

    # -- markings (zoom >= min_zoom): -> True when the point is white paint
    def marking(self, z, X, Zb, r_o, th):
        for a in self.arrows:
            if z < a.get("min_zoom", 3):
                continue
            th0 = math.radians(a["at_deg"])
            R = a.get("r", self.lane_in)
            d = (th - th0 + math.pi) % TAU - math.pi
            s = R * d                                     # along, CCW positive
            n = r_o - R
            L, H, ws, wh = a.get("length", 76), a.get("head", 28), a.get("shaft", 5.5), a.get("head_w", 17)
            if -L / 2 <= s < L / 2 - H and abs(n) < ws:
                return True
            if L / 2 - H <= s <= L / 2 and abs(n) < wh * (L / 2 - s) / H:
                return True
        g = self.dash
        if g and z >= g.get("min_zoom", 2):
            r0, r1 = g.get("r_z%d" % z, g.get("r", [self.ring_out, self.ring_out + 6.0]))   # per-zoom band
            if r0 <= r_o < r1 and X >= self.c0 + g.get("from_centre", 8.0) and X <= self.edge_in:
                per, on = g.get("period", 24.0), g.get("dash", 13.0)
                # arc length at the band's middle radius, from the dash run's start (X = c0 + from_centre). Not
                # r_o * th: with th near -1 rad mod 2 pi (~5.5) that phase moves ~38 units across a 7-unit band,
                # about one period, so every angle had an "on" pixel and the dashes merged into a thin ragged
                # line along the ring's edge (task roundabout3, NET_ART.md 11)
                rm = 0.5 * (r0 + r1)
                th0 = -math.acos(min(1.0, (self.c0 + g.get("from_centre", 8.0)) / rm))
                if (rm * (th - th0)) % per < on:
                    return True
        return False

    def colour(self, z, r, x, zl):
        X, Zb = x, zl - 256.0                            # block coords
        r_o = math.hypot(X, Zb)
        th = math.atan2(Zb, X)                           # -90 deg at the x- edge, 0 at the z+ edge
        r_e = math.hypot(X, zl)                          # distance from E (the x-, z- corner)
        a_e = math.atan2(zl, X)                          # 0 on the arm edge (z-), 90 deg on the x- edge
        xp_e, t_e = X, zl                                # entry band
        xp_x = r_e + self.adj * (a_e / (math.pi / 2))   # exit band
        w = a_e / (math.pi / 2)                          # arc length at the arm edge (= z there), one 256
        t_x = r_e * a_e * (1.0 - w) + 256.0 * w * w      # period at the x- edge (= the ring's t there)
        t_r = 256.0 * th / (math.pi / 2)                 # ring: one 256 period per quarter, 0 at the edges
        in_e = xp_e >= self.c0
        in_x = xp_x <= self.c0
        in_r = r_o < self.ring_out
        S = self.s
        # arm edge strip: the stock road itself, so the seam against a stock road cell is exact. At least one
        # pixel row deep: a row spans 1024 / W units across the edge (W = tile width in px at this zoom)
        if zl < max(self.stub, 1024.0 / NA.TILE_W[z]):
            return S(z, r, X, zl)
        if self.marking(z, X, Zb, r_o, th):
            if z not in self.white:
                self.white[z] = S.paint_white(z)
            return self.white[z]
        # outer edges of the arm halves (edge line, gutter, sidewalk) stay on top of the ring
        if in_e and xp_e > self.edge_in:
            return S(z, r, xp_e, t_e)
        if in_x and xp_x < self.edge_out:
            return S(z, r, xp_x, t_x)
        if in_r:
            if r_o < self.c0:                            # island: gutter + apron (stock outer edge profile),
                xp = r_o - self.c0 + self.gutter_x       # then a curb ring and a raised concrete centre. The
                if xp >= self.gutter_x - 4.0 - self.curb:     # engine draws no terrain under this piece (measured:
                    return S(z, r, xp, t_r)              # transparent pixels show the previous frame), so the
                r_in = self.c0 - 4.0 - self.curb         # whole island is painted
                if r_o >= r_in - self.inner_curb:
                    return S(z, r, self.gutter_x - 3.0, t_r)
                # the stock sidewalk band (x' 10..24) tiled straight across the centre: no radial streaks
                return S(z, r, 10.0 + (Zb % 14.0), X)
            if r_o < self.c0 + self.yellow_w:            # single yellow edge line round the island
                y0, y1 = self.yellow_xp
                return S(z, r, y0 + (y1 - y0) * (r_o - self.c0) / self.yellow_w, t_r)
            return self.asphalt(z, r, X, r_o, xp_x, t_e, t_x, t_r, r_e)
        if in_e:
            if self.asph_in[0] <= xp_e <= self.asph_in[1]:
                return self.asphalt(z, r, X, r_o, xp_x, t_e, t_x, t_r, r_e)
            return S(z, r, xp_e, t_e)
        if in_x:
            if self.asph_out[0] <= xp_x <= self.asph_out[1]:
                return self.asphalt(z, r, X, r_o, xp_x, t_e, t_x, t_r, r_e)
            return S(z, r, xp_x, t_x)
        # splitter island: the ring's outer profile (edge line at its nose, gutter, sidewalk)
        return S(z, r, r_o, t_r)

    def asphalt(self, z, r, X, r_o, xp_x, t_e, t_x, t_r, r_e):
        """Stock lane shade of the nearest lane centre line, read on that band's own profile."""
        c = [(abs(r_o - self.lane_in), r_o, t_r, self.asph_in),
             (abs(X - self.lane_in), X, t_e, self.asph_in),
             (abs(r_e - self.lane_out), xp_x, t_x, self.asph_out)]
        _, xp, t, (lo, hi) = min(c, key=lambda k: k[0])
        return self.s(z, r, min(hi, max(lo, xp)), t)


KINDS = {"pinwheel_roundabout": PinwheelRoundabout}


# ----------------------------------------------------------------------------------------------- painting

def paint(plan, out_dir, canvas=None, zooms=range(NA.ZOOMS)):
    """plan (dict or path) -> png_dir with z{z}_r{r}.png on the canvas piece's frames (default 39: the full flat
    diamond, every slot the same size)."""
    if isinstance(plan, str):
        plan = json.load(open(plan, encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    sample = RoadSampler(plan.get("source", 29))
    model = KINDS[plan["kind"]](plan, sample)
    cv = NA.stock_frames(canvas or plan.get("canvas", NA.FULL_TILE_PIECE))
    for z in zooms:
        for r in range(NA.ROTS):
            im0, (L, T) = cv[(z, r)]
            w, h = im0.size
            out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            mpx, opx = im0.load(), out.load()
            for y in range(h):
                for xx in range(w):
                    if mpx[xx, y][3] < 128:              # the canvas piece's own silhouette (diamond + rim)
                        continue
                    u, v = NA.unproject(z, xx + 0.5 - L, y + 0.5 - T)
                    u, v = NA.rot_uv(u, v, -r % 4)
                    # rim pixels (just outside the exact diamond) keep their unclamped position: the sampler
                    # reads the stock rim there; the model only needs to tolerate a few units outside 0..256
                    opx[xx, y] = model.colour(z, r, (1.0 - u) * 256.0, v * 256.0)
            out.save(os.path.join(out_dir, NA.frame_name(z, r)))
    return out_dir


def seams(plan, out_dir, piece=29):
    """Arm seam check: for every zoom x slot, the pixels of the painted frame that lie within one pixel row of the
    arm edge (z- side, the stock road's half) compared with the stock road frame that sits across that edge
    (same slot rule as the sampler). -> {"z{z}_r{r}": (equal, total)}."""
    if isinstance(plan, str):
        plan = json.load(open(plan, encoding="utf-8"))
    fr = NA.load_dir(out_dir)
    st = NA.stock_frames(piece)
    rep = {}
    for (z, r), (im, _a) in sorted(fr.items()):
        s_im, (L, T) = st[(z, (r + 1) & 3)]
        a, b = im.load(), s_im.load()
        eq = tot = 0
        for y in range(im.height):
            for x in range(im.width):
                if a[x, y][3] < 128:
                    continue
                u, v = NA.unproject(z, x + 0.5 - L, y + 0.5 - T)
                u, v = NA.rot_uv(u, v, -r % 4)
                if v > 4.0 / NA.TILE_W[z]:                   # farther than ~1 px from the z- edge
                    continue
                tot += 1
                eq += a[x, y][:3] == b[x, y][:3]
        rep["z%d_r%d" % (z, r)] = (eq, tot)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", help="game root to read stock frames from (default $SC3_GAME_ROOT)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("paint")
    p.add_argument("plan")
    p.add_argument("out")
    s = sub.add_parser("seams")
    s.add_argument("plan")
    s.add_argument("out")
    a = ap.parse_args(argv)
    if a.game or os.environ.get("SC3_GAME_ROOT"):
        NA.set_game(a.game or os.environ.get("SC3_GAME_ROOT"))
    if a.cmd == "paint":
        print(paint(a.plan, a.out))
    else:
        rep = seams(a.plan, a.out)
        for k, (e, t) in rep.items():
            print("%s %d/%d" % (k, e, t))
        print("total %d/%d" % (sum(e for e, _ in rep.values()), sum(t for _, t in rep.values())))


if __name__ == "__main__":
    main()
