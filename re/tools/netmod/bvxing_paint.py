#!/usr/bin/env python3
r"""bvxing_paint.py - art for the boulevard's crossing twins (task orthfix round 2026-11-15b, xsect 67 / 71).

Owner 2026-11-15: 67 "the crossing is not following the 3 lane layout" (the twins drew three stock 2-lane level
crossings side by side), 71 "there shouldn't be 3 tunnels below the highway" (three stock underpasses side by side).

Canonical frame as boulevard_paint: the boulevard runs along world x, rows wz 0 (north carriageway, traffic +x), 1
(middle), 2 (south carriageway, traffic -x); T = wz * 256 (0 .. 768). The crossing column is cell x 0. The crossing
base at state 0 has its road along x (69: rails along z at lane x 52..82 / 136..166; 15098 / 11258 the same axis), so
twin A (north row, lanes toward x+), twin B (south row) and the middle twin all draw at state 0 of this scene.

RailXing: the boulevard's 3 + 3 lanes (white dashes at 29's centre line and the extra-lane divider, as the straight
boulevard) run across the crossing column; the median becomes paint (two solid yellow lines at the old curb lines,
asphalt between); each carriageway gets 69's stop bar on its approach side only; the rail band (rails, planks,
sleepers over the sidewalks) is 69's own pixels, read along the rails, so it runs unbroken across all three rows.

  py -3.12 re/tools/netmod/bvxing_paint.py mock OUT.png [--zoom 4] [--rot 0]   # case 67 offline, 4 rotations sheet
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from netmod import boulevard_paint as BP                     # noqa: E402
from netmod.diagave_paint import CLEAR, STOCK                # noqa: E402
from netmod import lanelines as LL                           # noqa: E402

RAIL_PID = 69
RAIL_X = (44.0, 176.0)       # lane x band of 69 (state 0) holding the planks, rails and sleepers
RAIL_MID = (70.0, 180.0)     # 69's lane band where the rail cross-section is uniform along the rails
SIDE = 56.0                  # 29's sidewalk + curb + gutter band (outer edges of the boulevard)
MED_LINES = (312.0, 456.0)   # the median's paint lines: the north / south inner curb lines of the straight boulevard
CENTRES = (128.0, 220.0, 548.0, 640.0)   # carriageway lane lines: 29's centre, divider (BP.DIVIDER), mirrored


def s69(z, r, x, zl):
    x = min(255.5, max(0.5, x))
    zl = min(255.5, max(0.5, zl))
    c = STOCK(RAIL_PID, 0, z, r, x, zl)
    k = 0
    while not c[3] and k < 8:
        k += 1
        c = STOCK(RAIL_PID, 0, z, r, x + (k if x < 128 else -k), zl + (k if zl < 128 else -k))
    return c


def white(c):
    return bool(c[3]) and min(c[:3]) >= 150 and max(c[:3]) - min(c[:3]) <= 30


# round 2026-11-15b, owner on 66 / 70: the avenue gets the same treatment (2 + 2 lanes, painted median, one underpass).
# The avenue's two rows: each half is stock 29's section with its inner sidewalk turned median (11204), so the paved
# section keeps 29's outer sidewalks, one white dashed line per half at 29's centre (128 / 384) and paints the median
# between the halves' inner curb lines (29's gutter 200..224 -> T 212 / 300).
AV_MED_LINES = (212.0, 300.0)
AV_CENTRES = (128.0, 384.0)


class Section:
    """the paved cross-section with lane lines and a painted median (no curbs inside); rows = 3 the boulevard, 2 the
    avenue"""

    def __init__(self, rows=3):
        self.rows = rows
        self.W = 256.0 * rows
        self.med = MED_LINES if rows == 3 else AV_MED_LINES
        self.centres = CENTRES if rows == 3 else AV_CENTRES

    def colour_at(self, z, r, x, s, T, lines=True):
        if T < SIDE:
            return BP.s29(z, r, x, T)
        if T >= self.W - SIDE:
            return BP.s29(z, r, x, T - (self.W - 256.0))
        cl = BP.centre_line(z, r)
        base = lambda: BP.s29(z, r, x, BP.fold(T, BP.LANE_S))        # noqa: E731
        if cl is not None:
            for m in self.med:                                    # solid yellow: 29's centre footprint moved here
                if abs(T - m) <= cl[1]:
                    c = BP.s29(z, r, x, cl[0] + (T - m))
                    return c if BP.yellowish(c) else base()
            if lines:
                for m in self.centres:
                    if abs(T - m) <= cl[1]:
                        return LL.dashed(z, s, T / 256.0, s, BP.yellow(BP.s29(z, r, x, cl[0] + (T - m))), base)
        return base()


class RailXing(Section):
    def colour(self, z, r, wx, wz):
        if wz < 0 or wz >= self.rows or wx < 0 or wx >= 1:
            return CLEAR
        x, s, T = (wx % 1.0) * 256.0, wx, wz * 256.0
        if RAIL_X[0] <= x <= RAIL_X[1]:
            if T < SIDE:
                return s69(z, r, x, T)
            if T >= self.W - SIDE:
                return s69(z, r, x, T - (self.W - 256.0))
            return s69(z, r, x, BP.fold(T - RAIL_MID[0], RAIL_MID))
        # stop bars: 69's white bar on the approach side of each carriageway (north row drives +x, south -x)
        approach = x < RAIL_X[0] if T < self.W / 2.0 else x > RAIL_X[1]
        if approach and SIDE + 8.0 <= T <= self.W - SIDE - 8.0 and not (self.med[0] - 8 <= T <= self.med[1] + 8):
            c = s69(z, r, x, 120.0)
            if white(c):
                return c
        return self.colour_at(z, r, x, s, T, lines=True)


# ------------------------------------------------------------------------------------------------ underpass

DECK = 32.0                  # highway deck top, zoom-3 px above ground (netart.ELEVATED_PIECE's measured rise)
EDGE = 16.0                  # deck units next to a removed wall re-read from further in (the stock's edge line, the edge band's cap)
FASCIA = 6.0                 # the deck edge band on the open faces (the parapet strip), zoom-3 px


FAR_DIM = float(os.environ.get("BVX_FAR_DIM", "0.55"))      # the far outer wall seen under the deck, in its shade


def dim(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f), c[3])


class Underpass:
    """One boulevard row of a road under a highway crossing piece (15098 / 11258), drawn from the stock frame by ray
    casting a box model fitted to it: deck top at DECK, the open faces (lx 0 / 256, the road's ends) carry a FASCIA-deep
    deck edge, the side walls run along the road at lz 0 and lz 256 (canonical: road along x). `keep` = the side walls
    that stay (the boulevard's outer edges): row 0 keeps lz 0, row 2 keeps lz 256, the middle row none. A pixel whose
    first hit was a removed wall shows what the ray meets next: the boulevard's ground under the deck (shaded as the
    stock ground in the opening) or, past the boulevard, the far outer wall's inner face (the stock's own inner-face
    pixels, looked up by position along the wall and height). Every ground pixel is repainted as the boulevard (its
    3 + 3 lanes and painted median, Section), so the stock 2-lane road and its yellow line are gone."""

    def __init__(self, pid, row, shift, rows=3):
        self.pid, self.row, self.shift = pid, row, shift     # canonical slot r = stock frame (r + shift) & 3
        self.keep = (0.0,) if row == 0 else (256.0,) if row == rows - 1 else ()
        self.sec = Section(rows)
        self._tex = {}
        self._shade = {}

    @staticmethod
    def _lane(z, r, X, Y, L, T, e):
        from netmod import netart as NA
        u, v = NA.unproject(z, X + 0.5 - L, Y + 0.5 - T, e)
        u, v = NA.rot_uv(u, v, -r % 4)
        return (1.0 - u) * 256.0, v * 256.0

    def hits(self, z, r, X, Y, L, T):
        """[(e, kind, lx, lz)] every surface of the stock box model the ray of pixel (X, Y) meets, highest first;
        kinds deck, f0 / f256 (fascia), w0 / w256 (side walls), g (ground in the cell). Also the ground point."""
        a = self._lane(z, r, X, Y, L, T, 0.0)
        b = self._lane(z, r, X, Y, L, T, 1.0)
        dx, dz = b[0] - a[0], b[1] - a[1]
        out = []
        gx, gz = a[0] + DECK * dx, a[1] + DECK * dz
        if 0 <= gx <= 256 and 0 <= gz <= 256:
            out.append((DECK, "deck", gx, gz))
        for c in (0.0, 256.0):
            if abs(dx) > 1e-9:
                e = (c - a[0]) / dx
                zz = a[1] + e * dz
                # the deck edge, from outside only (seen from under the deck it is not there)
                if DECK - FASCIA <= e <= DECK and 0 <= zz <= 256 and ((dx > 0) if c == 256.0 else (dx < 0)):
                    out.append((e, "f%d" % c, c, zz))
            if abs(dz) > 1e-9:
                e = (c - a[1]) / dz
                xx = a[0] + e * dx
                if 0 <= e <= DECK and 0 <= xx <= 256:
                    out.append((e, "w%d" % c, xx, c))
        if 0 <= a[0] <= 256 and 0 <= a[1] <= 256:
            out.append((0.0, "g", a[0], a[1]))
        out.sort(key=lambda h: -h[0])
        return out, a, (dx, dz)

    def deck_at(self, z, r, lx, lz, src, L, T, fallback, e=DECK):
        """the stock pixel showing the point (lx, lz) at height e (default the deck top)"""
        from netmod import netart as NA
        u, v = NA.rot_uv(1.0 - lx / 256.0, lz / 256.0, r)
        X, Y = NA.project(z, u, v, e)
        X, Y = int(X + L), int(Y + T)
        try:
            c = src[X, Y]
        except IndexError:
            return fallback
        return c if c[3] else fallback

    def frame(self, z, r):
        from netmod import netart as NA
        return NA.stock_frames(self.pid)[(z, (r + self.shift) & 3)]

    def tex(self, z, c, inner):
        """{(along bin, e bin): colour} of side wall lz = c seen from inside (inner) or outside, from every slot"""
        k = (z, c, inner)
        if k in self._tex:
            return self._tex[k]
        t = {}
        for r in range(4):
            im, (L, T) = self.frame(z, r)
            px = im.load()
            for Y in range(im.height):
                for X in range(im.width):
                    if px[X, Y][3] < 128:
                        continue
                    h, _a, (dx, dz) = self.hits(z, r, X, Y, L, T)
                    if not h or h[0][1] != "w%d" % c:
                        continue
                    toward = dz > 0 if c == 0.0 else dz < 0        # travel = -d/de: toward the wall from inside
                    if toward != inner:
                        continue
                    t[(int(h[0][2] // 8), int(h[0][0] // 2))] = px[X, Y]
        self._tex[k] = t
        return t

    def wall(self, z, c, inner, along, e):
        t = self.tex(z, c, inner) or self.tex(z, c, not inner)
        if not t:
            return (150, 140, 120, 255)
        kb, eb = along / 8.0, e / 2.0
        k = min(t, key=lambda q: (q[0] - kb) ** 2 + 4.0 * (q[1] - eb) ** 2)
        return t[k]

    def shade(self, z, r):
        """mean stock ground / plain 29 brightness inside the opening (the stock darkens nothing much; measured)"""
        k = (z, r)
        if k in self._shade:
            return self._shade[k]
        im, (L, T) = self.frame(z, r)
        px = im.load()
        a = b = 0.0
        for Y in range(im.height):
            for X in range(im.width):
                c = px[X, Y]
                if c[3] < 128:
                    continue
                h, _g, _d = self.hits(z, r, X, Y, L, T)
                if h and h[0][1] == "g":
                    s = BP.s29(z, r, h[0][2], h[0][3])
                    if s[3]:
                        a += sum(c[:3])
                        b += sum(s[:3])
        self._shade[k] = min(1.0, a / b) if b else 1.0
        return self._shade[k]

    def ground(self, z, r, lx, lz):
        T = self.row * 256.0 + lz
        c = self.sec.colour_at(z, r, min(255.5, max(0.5, lx)), lx / 256.0, T, lines=True)
        f = self.shade(z, r)
        return (int(c[0] * f), int(c[1] * f), int(c[2] * f), 255)

    def paint(self, z, r, dbg=None):
        """canonical slot r -> (layer 0, layer 1, anchor). Layer 1 is the deck (top + edge band) alone, as the stock's
        own layer 1: the game draws it after the vehicles and trees, so cars pass under it."""
        from PIL import Image
        im, (L, T) = self.frame(z, r)
        src = im.load()
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        top = Image.new("RGBA", im.size, (0, 0, 0, 0))
        dst, tp = out.load(), top.load()
        removed = {"w0", "w256"} - {"w%d" % c for c in self.keep}
        for Y in range(im.height):
            for X in range(im.width):
                h, g, (dx, dz) = self.hits(z, r, X, Y, L, T)
                s = src[X, Y]
                if not h:
                    dst[X, Y] = s
                    continue
                first = h[0]
                new = next((x for x in h if x[1] not in removed), None)
                if new is not None and new is first and new[1] == "deck":
                    # the stock draws the deck's edge line along every side wall's top: inside the boulevard the deck
                    # goes on, so read the deck a few units in from a removed wall (the highway runs along z here)
                    lz = new[3]
                    lo = 0.0 if "w0" not in removed else EDGE
                    hi = 256.0 if "w256" not in removed else 256.0 - EDGE
                    if lz < lo or lz > hi:
                        dst[X, Y] = self.deck_at(z, r, new[2], min(hi, max(lo, lz)), src, L, T, s)
                    else:
                        dst[X, Y] = s
                    tp[X, Y] = dst[X, Y]
                    continue
                if new is not None and new is first and new[1] != "g":
                    dst[X, Y] = s
                    if new[1][0] == "f":
                        # the deck edge band ends in a cap where the stock wall was: inside the span it goes on, so
                        # read it a few units in from a removed wall (70's nub on the highway's median line)
                        lz = new[3]
                        lo = 0.0 if "w0" not in removed else EDGE
                        hi = 256.0 if "w256" not in removed else 256.0 - EDGE
                        if lz < lo or lz > hi:
                            dst[X, Y] = self.deck_at(z, r, new[2], min(hi, max(lo, lz)), src, L, T, s, new[0])
                        tp[X, Y] = dst[X, Y]
                    continue
                if new is not None and new[1] not in ("g",):
                    c = float(new[1][1:])
                    dst[X, Y] = self.wall(z, c, (dz > 0) if c == 0.0 else (dz < 0), new[2], new[0])
                    continue
                if new is not None and new[1] == "g" and s[3] < 128 and first is new:
                    continue                                   # stock leaves it clear (the frame's own rim)
                # ground: in the cell or, through a removed wall, under the next row
                Tw = self.row * 256.0 + g[1]
                if Tw < 0.0 or Tw >= self.sec.W:                # past the boulevard: its outer wall from inside
                    cl = (0.0 if Tw < 0.0 else self.sec.W) - self.row * 256.0
                    e = min(DECK, max(0.0, (cl - g[1]) / dz)) if abs(dz) > 1e-9 else 0.0
                    dst[X, Y] = dim(self.wall(z, 0.0 if Tw < 0.0 else 256.0, True, g[0] + e * dx, e), FAR_DIM)
                    continue
                dst[X, Y] = self.ground(z, r, g[0], g[1])
        return out, top, (L, T)


# ------------------------------------------------------------------------------------------------ offline mock

def mock_cells(art_dir, bv_art, stock=False):
    """case 67 around the crossing column: boulevard x -3..3 (noses beside the crossing), rail along z"""
    from netmod import boulevard as B
    cells = []

    def put(x, z, d, state):
        cells.append({"x": x, "z": z, "dir": d, "state": state})

    def stock(x, z, pid, state):
        cells.append({"x": x, "z": z, "piece": pid, "state": state})

    for x in list(range(-4, 0)) + list(range(1, 5)):
        put(x, 0, os.path.join(bv_art, str(B.OUTER)), 2)
        put(x, 2, os.path.join(bv_art, str(B.OUTER)), 0)
        if x == -1:
            put(x, 1, os.path.join(bv_art, str(B.NOSE)), 0)
        elif x == 1:
            put(x, 1, os.path.join(bv_art, str(B.NOSE)), 2)
        else:
            put(x, 1, os.path.join(bv_art, str(B.MIDDLE)), 0)
    for row in range(3):
        if stock:
            stock(0, row, RAIL_PID, 0)
        else:
            put(0, row, os.path.join(art_dir, "row%d" % row), 0)
    for z in list(range(-4, 0)) + list(range(3, 7)):
        stock(0, z, 44, 1)
    return cells


def cmd_mock(a):
    from PIL import Image
    from netmod import boulevard as B
    from netmod.diagave_paint import paint_cell
    tmp = a.tmp
    import json
    for row in range(3):
        d = os.path.join(tmp, "row%d" % row)
        anc = paint_cell(RailXing(), (0, row), d, zooms=[a.zoom])
        json.dump(anc, open(os.path.join(d, "anchors.json"), "w"))
    cells = mock_cells(tmp, a.bv_art, a.stock)
    ims = [B.render(cells, a.zoom, r) for r in range(4)]
    for r, im in enumerate(ims):
        im.save(a.out[:-4] + "_r%d.png" % r)
    W = sum(i.width for i in ims) + 10 * 3
    H = max(i.height for i in ims)
    sheet = Image.new("RGBA", (W, H), (30, 30, 30, 255))
    x = 0
    for im in ims:
        sheet.paste(im, (x, 0))
        x += im.width + 10
    sheet.save(a.out)
    print("wrote", a.out)


# task orthfix BVXART: the art twins. base -> (twin A = north row 0, twin B = south row 2, middle row 1); A / B as the
# bvr twins' sides (69 / 11258: A lanes toward side 1 at state 0, B side 3; 15098: A side 2, B side 0). In the canonical
# frame the north row drives +x (bvl_20700 = the south row at state 0 drives -x); 15098's road runs along z at state 0,
# so its canonical frame is 15098 at state 3 (side - 1), which puts its side 2 twin on the north row too.
XART = {69: (30200, 30201, 30202), 15098: (30203, 30204, 30205), 11258: (30206, 30207, 30208)}
XART_SIDES = {69: (1, 3), 15098: (2, 0), 11258: (1, 3)}
# task orthfix AVXART (owner 2026-11-15b on 66 / 70): the avenue's art twins of avenue_lanes' avlc crossing twins
# (21710.. : A = lanes toward XART_SIDES[base][0] at state 0 = north row 0, B = row 1), table lines `avlq`
AVXART = {69: (30233, 30234), 15098: (30235, 30236), 11258: (30237, 30238)}
AVLC = {69: (21710, 21711), 15098: (21716, 21717), 11258: (21714, 21715)}


def build_art(pack, zooms, only=None):
    """art/<id>/ of every art twin (frames + anchors.json)"""
    from netmod import netart as NA
    from netmod.diagave_paint import paint_cell
    jobs = []
    for base, ids in sorted(XART.items()):
        jobs += [(base, ids[0], 0, 3), (base, ids[2], 1, 3), (base, ids[1], 2, 3)]
    for base, ids in sorted(AVXART.items()):
        jobs += [(base, ids[0], 0, 2), (base, ids[1], 1, 2)]
    for base, vid, row, nrows in jobs:
        if True:
            if only and vid not in only:
                continue
            d = os.path.join(pack, "art", str(vid))
            os.makedirs(d, exist_ok=True)
            if base == RAIL_PID:
                anc = paint_cell(RailXing(nrows), (0, row), d, zooms=zooms)
            else:
                shift = {15098: 3, 11258: 0}[base]
                u = Underpass(base, row, shift, nrows)
                anc = {}
                for z in zooms:
                    for r in range(NA.ROTS):
                        im, im1, a = u.paint(z, r)
                        for layer, img in ((0, im), (1, im1)):
                            n = NA.frame_name(z, (r + shift) & 3, layer)
                            img.save(os.path.join(d, n))
                            anc[n] = list(a)
            anc["_"] = "bvxing_paint.py (orthfix %s): %s twin over %d, row %d" % (
                "BVXART" if nrows == 3 else "AVXART", "level crossing" if base == RAIL_PID else "underpass", base, row)
            json.dump(anc, open(os.path.join(d, "anchors.json"), "w"), indent=1)
            print("built %d (base %d, row %d)" % (vid, base, row))


def underpass_set(pid, out_dir, zooms, shift=None):
    """twin art of the three rows over stock `pid` -> out_dir/row{0,1,2}/ in the base's own frame numbering"""
    import json
    from netmod import netart as NA
    shift = {15098: 3, 11258: 0}[pid] if shift is None else shift
    for row in range(3):
        u = Underpass(pid, row, shift)
        d = os.path.join(out_dir, "row%d" % row)
        os.makedirs(d, exist_ok=True)
        anc = {}
        for z in zooms:
            for r in range(4):
                im, im1, a = u.paint(z, r)
                for layer, img in ((0, im), (1, im1)):
                    n = NA.frame_name(z, (r + shift) & 3, layer)
                    img.save(os.path.join(d, n))
                    anc[n] = list(a)
        json.dump(anc, open(os.path.join(d, "anchors.json"), "w"))


def cmd_mock71(a):
    """case 71 as built in the game (verify/final1115 final cells), twins replaced by the new art"""
    from PIL import Image
    from netmod import boulevard as B
    underpass_set(15098, a.tmp, [a.zoom])
    cells = []
    twin = {20778: 0, 20780: 1, 20779: 2}
    bv = {B.OUTER, B.MIDDLE, B.NOSE}
    fin = json.load(open(a.cells))["71"]["final"]
    for k, (pid, st) in fin.items():
        x, z = map(int, k.split(","))
        if not (136 <= z <= 146 and 9 <= x <= 21):
            continue
        if pid in twin:
            d = os.path.join(a.tmp, "row%d" % twin[pid]) if not a.stock else None
            cells.append({"x": x, "z": z, "dir": d, "state": st} if d else {"x": x, "z": z, "piece": 15098, "state": st})
        elif pid in bv:
            cells.append({"x": x, "z": z, "dir": os.path.join(a.bv_art, str(pid)), "state": st})
        else:
            cells.append({"x": x, "z": z, "piece": pid, "state": st})
    ims = [B.render(cells, a.zoom, r) for r in range(4)]
    for r, im in enumerate(ims):
        im.save(a.out[:-4] + "_r%d.png" % r)
    W = sum(i.width for i in ims) + 10 * 3
    sheet = Image.new("RGBA", (W, max(i.height for i in ims)), (30, 30, 30, 255))
    x = 0
    for im in ims:
        sheet.paste(im, (x, 0))
        x += im.width + 10
    sheet.save(a.out)
    print("wrote", a.out)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("mock")
    m.add_argument("out")
    m.add_argument("--zoom", type=int, default=4)
    m.add_argument("--tmp", required=True)
    m.add_argument("--bv-art", required=True, help="the installed boulevard package's art folder")
    m.add_argument("--stock", action="store_true")
    m = sp.add_parser("mock71")
    m.add_argument("out")
    m.add_argument("--zoom", type=int, default=4)
    m.add_argument("--tmp", required=True)
    m.add_argument("--bv-art", required=True)
    m.add_argument("--cells", required=True, help="verify/final1115/f1/final_cells.json")
    m.add_argument("--stock", action="store_true", help="the stock twins (before)")
    a = ap.parse_args()
    {"mock": cmd_mock, "mock71": cmd_mock71}[a.cmd](a)


if __name__ == "__main__":
    main()
