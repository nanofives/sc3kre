r"""bldprops.py - task objprops (2026-11-24): the game's own small props on the free part of an OBJ building's lot.

Owner 2026-11-24 (sample pack overview): "skyscraper doesn't have anything on its floor?". An OBJ model was drawn on a
plain patch of lawn. This module adds, at render time, props and a lot ground taken from the PLAYER'S OWN game install:
the Building Architect's prop library (Apps\Res\BA\PROPS) and its ground paints (Apps\Res\BA\PAINTS\GROUND). Nothing of
EA's art is shipped: the files are read where the game keeps them, as bldimport already reads the game's IXF files.

The art (re/analysis/BUILDING_ART.md 8, measured on the GOG install):
  - a prop = four BMPs `<name> <view>.bmp` (24-bit, 32 / 64 / 128 / 256 px square, colour key 255,0,255) and lines
    in its folder's .met file `x,y,z:"<view 0>.bmp","<view 1>.bmp","<view 2>.bmp","<view 3>.bmp"`, one line per
    orientation of the prop (the BMP names rotate by one per line). x, y, z = the prop's box in BA grid units
    (8 per lot cell, BLD_FORMAT.md 2), x along SC3 tile u, y along v (semi1 9,3,3 lies along u in view 0).
  - BA view j = SC3 rotation slot j (the semi's cab turns counter-clockwise from view to view, as slot r + 1 turns
    the lot counter-clockwise, NET_ART.md 6).
  - scale: 32 px of screen width per grid unit (a 1x1 fence edge spans 16 px = half its 32 px diamond), i.e. 256 px
    per cell = 4 x zoom 3. The box centre is the image's centre column; its ground centre sits 8 px per z unit below
    the image's centre row (fitted on trunks and poles of 1x1 / 3x3 props, c = 1, 3, 5, 7, 9, 13; c = 2 props sit
    4 to 10 px higher, which the foot rule below absorbs).
A prop is drawn as a billboard: a vertical quad through the point under its lowest opaque row, facing the camera, the
BMP of that slot mapped one texel per 1/256 cell, so the picture lands on screen as the BA drew it, scaled to the zoom,
and the model's own z-buffer decides what is in front. Its pixels are used as they are: no light, shadow, tone or grain
(they come lit from Maxis' renderer), bldrender kind 3.

Placement (slot 0, deterministic, plain float64 / uint32 arithmetic that bldweb.js repeats in the same order):
  occupied = the BA grid cells (1/8 cell) under the (u, v) box of any model triangle; per class a list of props with
  counts, each tried at the free positions in an order hashed from the model file name (FNV-1a + a 32-bit mix), the
  first box whose cells are all free and inside the lot wins; "edge" props (cars, lamps) must touch the lot edge.
  Classes: houses 3100-3599, apartments 3600-4999, shops 5000-5999, offices 6000-6999, industry 8000-9299 (farms 9300 get none).

Per entry: `x_props: {"on": false}` in models.json turns it off (default on). Only growables of a class above, OBJ
models, square lots, not SC4 conversions (they bring their own lot props) and not .bld files (BA art has its own).
Without a game folder, or when a prop's files are missing from the install, that prop is left out (listed in info).
Off switch for a run: SC3BLD_PROPS=0.
"""
import os
import re

import numpy as np
from PIL import Image

PROP_ROOT = "Apps/Res/BA/PROPS"
GROUND_ROOT = "Apps/Res/BA/PAINTS/GROUND"
PX_PER_CELL = 256.0          # sprite scale: 32 px per BA grid unit, 8 units per cell
GRID = 8                     # BA grid units per lot cell
VSCALE = 0.6123724356957945  # bldrender.VSCALE = cos(30 deg) / sqrt(2)
KEY = (255, 0, 255)
ENABLED = os.environ.get("SC3BLD_PROPS", "1") != "0"

# name -> (folder under PROP_ROOT, .met file in it)
CATALOG = {
    "sm decid1": ("FLORA", "FLORA.MET"), "med decid1": ("FLORA", "FLORA.MET"), "sm decid2": ("FLORA", "FLORA.MET"),
    "lg evgn2": ("FLORA", "FLORA.MET"), "sm bfpine1": ("FLORA", "FLORA.MET"), "sm evgn1": ("FLORA", "FLORA.MET"),
    "lg evgn1": ("FLORA", "FLORA.MET"), "sm shrub1": ("FLORA", "FLORA.MET"), "sm shrub2": ("FLORA", "FLORA.MET"),
    "lg shrub2": ("FLORA", "FLORA.MET"), "floweringbush1": ("FLORA", "FLORA.MET"),
    "chevy1": ("VEHICLES", "VEHICLES.MET"), "cort": ("VEHICLES", "VEHICLES.MET"), "pickup1": ("VEHICLES", "VEHICLES.MET"),
    "van1": ("VEHICLES", "VEHICLES.MET"), "semi3": ("VEHICLES", "VEHICLES.MET"),
    "bench1": ("plaza and street", "plazaandstreet.met"), "lamp1": ("plaza and street", "plazaandstreet.met"),
    "lamp2": ("plaza and street", "plazaandstreet.met"), "lamp3": ("plaza and street", "plazaandstreet.met"),
    "planter1": ("plaza and street", "plazaandstreet.met"), "planter2": ("plaza and street", "plazaandstreet.met"),
    "fountain2": ("plaza and street", "plazaandstreet.met"), "waste1": ("plaza and street", "plazaandstreet.met"),
    "news1": ("plaza and street", "plazaandstreet.met"), "postbox1": ("plaza and street", "plazaandstreet.met"),
    "table and chairs1": ("plaza and street", "plazaandstreet.met"),
    "lawnfurn1": ("yard objects", "yard objects.met"), "clothesline1": ("yard objects", "yard objects.met"),
    "play1": ("yard objects", "yard objects.met"), "garden1": ("yard objects", "yard objects.met"),
    "pool1": ("yard objects", "yard objects.met"), "picnic1": ("yard objects", "yard objects.met"),
    "garbage": ("yard objects", "yard objects.met"),
    "barrels1": ("industrial", "industrial.met"), "barrels2": ("industrial", "industrial.met"),
    "pileoftires": ("industrial", "industrial.met"), "tank1": ("industrial", "industrial.met"),
}
CARS = ("chevy1", "cort", "pickup1")

# class sets: (lo, hi, ground paint or None = the lawn, [(prop or alternatives, count, edge)])
SETS = [
    ("house", 3100, 3599, None,
     [(CARS, 1, True), ("med decid1", 1, False), ("sm decid1", 2, False), ("sm bfpine1", 2, False),
      ("lg shrub2", 1, False), ("garden1", 1, False), ("pool1", 1, False), ("lawnfurn1", 1, False),
      ("clothesline1", 1, False), ("floweringbush1", 2, False), ("sm shrub1", 4, False)]),
    ("apartments", 3600, 4999, None,
     [(CARS, 2, True), ("med decid1", 1, False), ("sm decid1", 2, False), ("lg evgn2", 1, False),
      ("play1", 1, False), ("picnic1", 1, False), ("lamp1", 2, True), ("bench1", 2, False), ("planter1", 2, False),
      ("sm shrub1", 4, False)]),
    ("shop", 5000, 5999, "parking lot1.tga",
     [(CARS, 3, True), ("van1", 1, True), ("lamp2", 2, True), ("sm decid1", 1, False), ("bench1", 2, False),
      ("planter1", 2, False), ("news1", 1, False), ("waste1", 1, False), ("postbox1", 1, False)]),
    ("office", 6000, 6999, "skyscraper base1.tga",
     [("fountain2", 1, False), ("sm decid1", 4, False), ("lg evgn1", 2, False), ("sm evgn1", 3, False), (CARS, 1, True),
      ("lamp3", 4, True),
      ("planter2", 3, False), ("table and chairs1", 2, False), ("bench1", 3, False), ("planter1", 3, False),
      ("waste1", 1, False)]),
    ("industry", 8000, 9299, "concrete lot.tga",
     [("semi3", 1, True), ("van1", 1, True), ("pickup1", 1, True), ("tank1", 1, False), ("barrels1", 2, False),
      ("garbage", 1, False), ("barrels2", 2, False), ("pileoftires", 2, False)]),
]

MASK = 0xFFFFFFFF


def fnv1a(s):
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & MASK
    return h


def mix(a, b):
    x = ((a ^ b) * 0x9E3779B1) & MASK
    x ^= x >> 15
    x = (x * 0x85EBCA77) & MASK
    x ^= x >> 13
    return x


def set_of(m):
    """-> the class set of an entry, or None when it gets no props."""
    if not ENABLED:
        return None
    if (m.get("x_props") or {}).get("on", True) is False:
        return None
    if m.get("kind", "growable") != "growable" or "x_sc4" in m or not str(m.get("file", "")).lower().endswith(".obj"):
        return None
    c = m.get("class")
    if not isinstance(c, int) or isinstance(c, bool):
        return None
    for s in SETS:
        if s[1] <= c <= s[2]:
            return s
    return None


# ------------------------------------------------------------------------------------------------ the player's files

def parse_met(text):
    """-> [(x, y, z, [4 names])] in file order."""
    out = []
    for ln in text.splitlines():
        mm = re.match(r"\s*(\d+),(\d+),(\d+):(.*)", ln)
        if not mm:
            continue
        names = re.findall(r'"([^"]+)"', mm.group(4))
        if len(names) != 4:
            continue
        out.append((int(mm.group(1)), int(mm.group(2)), int(mm.group(3)), names))
    return out


def decode_bmp(data):
    """24- or 32-bit uncompressed BMP -> (h, w, 3) uint8 top row first; None for anything else."""
    if len(data) < 54 or data[:2] != b"BM":
        return None
    off = int.from_bytes(data[10:14], "little")
    w = int.from_bytes(data[18:22], "little", signed=True)
    h = int.from_bytes(data[22:26], "little", signed=True)
    bpp = int.from_bytes(data[28:30], "little")
    comp = int.from_bytes(data[30:34], "little")
    if comp != 0 or bpp not in (24, 32) or w <= 0 or h == 0:
        return None
    ah = abs(h)
    bp = bpp // 8
    stride = (w * bp + 3) & ~3
    if off + stride * ah > len(data):
        return None
    out = np.zeros((ah, w, 3), dtype=np.uint8)
    for y in range(ah):
        row = np.frombuffer(data, dtype=np.uint8, count=w * bp, offset=off + y * stride).reshape(w, bp)
        out[ah - 1 - y if h > 0 else y] = row[:, 2::-1][:, :3]
    return out


def decode_tga(data):
    """TGA types 2 / 10 (true colour, RLE), 24 / 32 bpp -> (h, w, 3) uint8 top row first; None for anything else."""
    if len(data) < 18:
        return None
    idl, cmt, typ = data[0], data[1], data[2]
    w = int.from_bytes(data[12:14], "little")
    h = int.from_bytes(data[14:16], "little")
    bpp, desc = data[16], data[17]
    if cmt != 0 or typ not in (2, 10) or bpp not in (24, 32) or w == 0 or h == 0:
        return None
    bp = bpp // 8
    n = w * h
    px = bytearray(n * bp)
    p = 18 + idl
    if typ == 2:
        if p + n * bp > len(data):
            return None
        px[:] = data[p:p + n * bp]
    else:
        q = 0
        while q < n:
            if p >= len(data):
                return None
            c = data[p]
            p += 1
            k = (c & 0x7F) + 1
            if q + k > n:
                return None
            if c & 0x80:
                v = data[p:p + bp]
                p += bp
                px[q * bp:(q + k) * bp] = v * k
            else:
                px[q * bp:(q + k) * bp] = data[p:p + k * bp]
                p += k * bp
            q += k
    a = np.frombuffer(bytes(px), dtype=np.uint8).reshape(h, w, bp)[:, :, 2::-1][:, :, :3]
    if not desc & 0x20:                     # bottom-left origin
        a = a[::-1]
    if desc & 0x10:                         # right-to-left
        a = a[:, ::-1]
    return np.ascontiguousarray(a)


class Library:
    """The props and ground paints of one game folder (batgrow.Game), read once."""

    def __init__(self, game):
        self.game = game
        self.mets = {}
        self.imgs = {}
        self.missing = set()

    def _read(self, rel):
        try:
            return self.game.read(rel) if self.game.exists(rel) else None
        except OSError:
            return None

    def orients(self, name):
        """-> [(x, y, z, [4 names])] of one prop, or [] when its .met or a BMP is missing."""
        folder, met = CATALOG[name]
        rel = PROP_ROOT + "/" + folder + "/" + met
        if rel not in self.mets:
            d = self._read(rel)
            self.mets[rel] = parse_met(d.decode("latin-1")) if d is not None else []
        out = [o for o in self.mets[rel] if all(nm.lower().startswith(name + " ") for nm in o[3])]
        for o in out:
            for nm in o[3]:
                if self.image(folder, nm) is None:
                    self.missing.add(name)
                    return []
        if not out:
            self.missing.add(name)
        return out

    def image(self, folder, nm):
        rel = PROP_ROOT + "/" + folder + "/" + nm
        if rel not in self.imgs:
            d = self._read(rel)
            self.imgs[rel] = decode_bmp(d) if d is not None else None
        return self.imgs[rel]

    def ground(self, nm):
        rel = GROUND_ROOT + "/" + nm
        if rel not in self.imgs:
            d = self._read(rel)
            self.imgs[rel] = decode_tga(d) if d is not None else None
        return self.imgs[rel]

    def key_files(self, s):
        """The relative paths whose bytes decide the props of class set s (for the render cache key)."""
        rels = []
        for item, _, _ in s[4]:
            for name in (item if isinstance(item, tuple) else (item,)):
                folder, met = CATALOG[name]
                rels.append(PROP_ROOT + "/" + folder + "/" + met)
                for o in self.orients(name):
                    rels.extend(PROP_ROOT + "/" + folder + "/" + nm for nm in o[3])
        if s[3]:
            rels.append(GROUND_ROOT + "/" + s[3])
        return sorted(set(rels))


# ------------------------------------------------------------------------------------------------ placement

def occupancy(tri, n):
    """(E, E) bool over the BA grid cells of an n x n lot: True under the (u, v) box of any model triangle."""
    E = n * GRID
    occ = np.zeros((E, E), dtype=bool)
    for k in range(tri.shape[0]):
        t = tri[k]
        u0 = min(t[0][0], t[1][0], t[2][0]) * GRID
        u1 = max(t[0][0], t[1][0], t[2][0]) * GRID
        v0 = min(t[0][1], t[1][1], t[2][1]) * GRID
        v1 = max(t[0][1], t[1][1], t[2][1]) * GRID
        i0 = max(int(np.floor(u0)), 0)
        i1 = min(max(int(np.ceil(u1)) - 1, int(np.floor(u0))), E - 1)
        j0 = max(int(np.floor(v0)), 0)
        j1 = min(max(int(np.ceil(v1)) - 1, int(np.floor(v0))), E - 1)
        if i0 > i1 or j0 > j1:
            continue
        occ[i0:i1 + 1, j0:j1 + 1] = True
    return occ


def plan(tri, n, m, lib, s):
    """-> placed props [(name, folder, orient (x, y, z, names), i, j)] in placement order, the cells used."""
    E = n * GRID
    used = occupancy(tri, n)
    seed = fnv1a(str(m.get("file", "")))
    out = []
    inst = 0
    for k, (item, count, edge) in enumerate(s[4]):
        for c in range(count):
            inst += 1
            names = item if isinstance(item, tuple) else (item,)
            name = names[mix(seed, inst * 977 + 13) % len(names)]
            ors = lib.orients(name)
            if not ors:
                break
            oorder = sorted(range(len(ors)), key=lambda o: (mix(seed, inst * 7919 + o), o))
            done = False
            for o in oorder:
                a, b = ors[o][0], ors[o][1]
                if a > E or b > E:
                    continue
                cand = []
                for i in range(E - a + 1):
                    for j in range(E - b + 1):
                        if edge and not (i == 0 or j == 0 or i + a == E or j + b == E):
                            continue
                        cand.append((mix(mix(seed, inst * 131 + o), i * 1024 + j), i, j))
                cand.sort()
                for _, i, j in cand:
                    if not used[i:i + a, j:j + b].any():
                        used[i:i + a, j:j + b] = True
                        out.append((name, CATALOG[name][0], ors[o], i, j))
                        done = True
                        break
                if done:
                    break
            if not done:
                break
    return out


def _rot(u, v, n, r):
    for _ in range(r % 4):
        u, v = v, n - u
    return u, v


def quads(placed, n, lib):
    """-> (tri (N,3,3), uv (N,3,2), mat index (N,), slot (N,), mats [dict]) of the billboards, materials sc3p_*."""
    tris, uvs, mids, slots, mats, mat_of = [], [], [], [], [], {}
    for name, folder, (a, b, c, names), i, j in placed:
        cu = (i + a / 2.0) / GRID
        cv = (j + b / 2.0) / GRID
        for r in range(4):
            nm = names[r]
            img = lib.image(folder, nm)
            S, Wd = img.shape[0], img.shape[1]
            key = (img[..., 0] == KEY[0]) & (img[..., 1] == KEY[1]) & (img[..., 2] == KEY[2])
            rows = np.where((~key).any(1))[0]
            cols = np.where((~key).any(0))[0]
            if not len(rows):
                continue
            y0, yl, x0, x1 = int(rows[0]), int(rows[-1]), int(cols[0]), int(cols[-1])
            if nm not in mat_of:
                c0, c1, r0, r1 = x0 - 1, x1 + 1, y0 - 1, yl + 1
                w, h = c1 - c0 + 1, r1 - r0 + 1
                rgb = np.zeros((h, w, 3), dtype=np.uint8)
                al = np.zeros((h, w), dtype=np.float32)
                sy0, sy1, sx0, sx1 = max(r0, 0), min(r1, S - 1), max(c0, 0), min(c1, Wd - 1)
                sub = img[sy0:sy1 + 1, sx0:sx1 + 1]
                rgb[sy0 - r0:sy1 - r0 + 1, sx0 - c0:sx1 - c0 + 1] = sub
                al[sy0 - r0:sy1 - r0 + 1, sx0 - c0:sx1 - c0 + 1] = (~key[sy0:sy1 + 1, sx0:sx1 + 1]).astype(np.float32)
                mat_of[nm] = len(mats)
                mats.append({"kd": (1.0, 1.0, 1.0), "tex": rgb.astype(np.float32) / 255.0, "alpha": al,
                             "name": "sc3p_" + nm[:-4].replace(" ", "_"), "tex_file": nm})
            gu, gv = _rot(cu, cv, n, r)
            yc = S / 2.0 + 8.0 * c                      # the box's ground centre row (edge coordinates)
            yf = yl + 1.0                               # the foot: the lower edge of the lowest opaque row
            dv = (yf - yc) / (PX_PER_CELL / 2.0)
            fu, fv = gu - dv, gv + dv                   # the ground point straight below the centre on screen
            X0, X1 = x0 - 1 + 0.5, x1 + 1 + 0.5         # texel centres of the padded crop
            Y0, Y1 = y0 - 1 + 0.5, yl + 1 + 0.5
            corner = []
            for X, Y in ((X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)):
                du = (X - S / 2.0) / PX_PER_CELL
                u, v = fu + du, fv + du
                hh = (yf - Y) / (PX_PER_CELL * VSCALE)
                u, v = _rot(u, v, n, (4 - r) % 4)       # back to slot 0: render_frame turns the lot by r
                corner.append([u, v, hh])
            tl, tr, br, bl = corner
            ut = [[0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]]
            for q in ((0, 1, 2), (0, 2, 3)):
                tris.append([corner[q[0]], corner[q[1]], corner[q[2]]])
                uvs.append([ut[q[0]], ut[q[1]], ut[q[2]]])
                mids.append(mat_of[nm])
                slots.append(r)
    return tris, uvs, mids, slots, mats


def add_props(mesh, n, m, game):
    """mesh: a placed model (tile coordinates, bldrender.place). -> (mesh with props and lot ground, info or None)."""
    s = set_of(m)
    if s is None or game is None or isinstance(n, (tuple, list)):
        return mesh, None
    lib = Library(game)
    placed = plan(mesh["tri"], n, m, lib, s)
    tris, uvs, mids, slots, mats = quads(placed, n, lib)
    out = dict(mesh)
    nm = len(mesh["tri"])
    if tris:
        base = len(mesh["mats"])
        out["tri"] = np.concatenate([mesh["tri"], np.array(tris, dtype=np.float64)])
        out["uv"] = np.concatenate([mesh["uv"], np.array(uvs, dtype=np.float64)])
        out["has_uv"] = np.concatenate([mesh["has_uv"], np.ones(len(tris), dtype=bool)])
        out["mat"] = np.concatenate([mesh["mat"], np.array(mids, dtype=np.int32) + base])
        out["mats"] = list(mesh["mats"]) + mats
        sl = mesh.get("slot")
        sl = sl if sl is not None else np.full(nm, -1, dtype=np.int8)
        out["slot"] = np.concatenate([sl, np.array(slots, dtype=np.int8)])
        gd = mesh.get("ground")
        gd = gd if gd is not None else np.zeros(nm, dtype=bool)
        out["ground"] = np.concatenate([gd, np.zeros(len(tris), dtype=bool)])
    pr = mesh.get("prop")
    pr = pr if pr is not None else np.zeros(nm, dtype=bool)
    out["prop"] = np.concatenate([pr, np.ones(len(tris), dtype=bool)])
    info = {"set": s[0], "placed": [[p[0], p[3], p[4], p[2][0], p[2][1]] for p in placed]}
    if s[3]:
        g = lib.ground(s[3])
        if g is not None:
            out["lot_tex"] = g.astype(np.float32) / 255.0
            info["ground"] = s[3]
        else:
            info["ground_missing"] = s[3]
    if lib.missing:
        info["missing"] = sorted(lib.missing)
    return out, info
