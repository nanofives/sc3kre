#!/usr/bin/env python3
r"""make_testmodels.py - task bldrender (2026-11-18): the test models for bldimport, written from code (no game art).

    py -3.12 re/tools/bldimport/make_testmodels.py <out folder>

Writes, in OBJ metres with Y up and the front facing +Z (bldrender.py axes):
  house_plain.obj/.mtl    1x1 cottage, flat colours only (walls, roof, door, windows, chimney)
  house_tex.obj/.mtl      1x1 brick house, textured (house_tex_wall.png, house_tex_front.png, house_tex_roof.png)
  block_2x2.obj/.mtl      2x2 three-storey block with a flat roof, rooftop box and two trees
  models.json             the classifier page's format (sc3models 1), classes 3300 / 3300 / 3900

    py -3.12 re/tools/bldimport/make_testmodels.py --ports <out folder>      (task airsea, 2026-11-19)

Writes the airport / seaport test models instead (bldimport kinds airport / seaport):
  fuel_depot.obj/.mtl     1x1 airport: two white tanks with red bands on a concrete pad, a blue pump house
  container_stack.obj     1x1 seaport: stacked shipping containers (red, blue, yellow, green) on concrete
  warehouse_2x2.obj       2x2 seaport: a teal shed with a white roof stripe, a yellow gantry and containers
  models.json             kinds airport / seaport / seaport, plus two entries bldimport must refuse (airport_2x2.obj,
                          fuel_depot_25.obj: an airport 2x2 and an airport with weight 25)

    py -3.12 re/tools/bldimport/make_testmodels.py --landmarks <out folder>  (task plop, 2026-11-19)

Writes the landmark test models (bldimport kind landmark, a plugin in Apps\PlugIn\bldimport):
  obelisk_2x2.obj/.mtl    2x2 monument: a red and gold obelisk on a stepped white plaza with four lamp posts
  pavilion_3x3.obj/.mtl   3x3 pavilion: a teal dome on a round colonnade, a fountain basin in front
  models.json             kind landmark 2x2, 3x3 and 5x5 (landmark_5x5.obj, the pavilion on a 5x5 lot: refused
                          until task lotshape allowed 5x5), plus one entry bldimport must refuse (civic_1x1.obj: kind
                          ploppable, not imported)

    py -3.12 re/tools/bldimport/make_testmodels.py --civmod <out folder>   (task civmod, 2026-11-19)

Writes the civic look / reward test models (bldimport kinds civic and reward, plugin in Apps\PlugIn\bldimport):
  police_3x3.obj/.mtl     3x3 police station look: a navy two-storey block, white band, blue roof light, car park
  obelisk_2x2.obj         reward "Test reward obelisk", population 1000 (unlocks in any city past 1,000 people)
  reward_locked.obj       reward "Test locked reward", population 100,000,000 (stays locked)
  pavilion_3x3.obj        landmark "Test pavilion" (type 18000: the Mover fix)
  models.json             those four, a police look on a 2x2 lot (refused until task civlot, the base is 3x3), plus
                          entries bldimport must refuse: a civic look of an unknown base, a reward named with a ';'
    py -3.12 re/tools/bldimport/make_testmodels.py --civtest <out folder>   (task civtest, 2026-11-19)

Writes one civic look for every one of the 17 civic buttons (civic_<base>.obj: a block on the base's own lot, a colour
per base, a white band and a roof sign), three rewards (reward_1x1 / reward_3x3 / reward_4x4: a stepped plaza with a
gold spire, population 1000, so they unlock in any town) and a 3x3 growable plaza (plaza_3x3.obj, class 6300 = the
3x3 commercial base the 1999 Maxis Plaza copied), models.json for all of them.
    py -3.12 re/tools/bldimport/make_testmodels.py --civdlg <out folder>   (task civdlg, 2026-11-19)

Writes the civic list window test set: three police looks (police_blue, police_green, police_red), one fire look and
one school look. Every other civic button has none, so it must stay stock.
    py -3.12 re/tools/bldimport/make_testmodels.py --lotshape <out folder>   (task lotshape, 2026-11-20)
    py -3.12 re/tools/bldimport/make_testmodels.py --lotgrow <out folder>    (task lotgrowb, 2026-11-24: w x d growables)

Writes non-square landmarks and rewards (re/analysis/LOT_SHAPES.md 8, they need sc3perf LOTRECT in game): a hall on a
2x3 lot and one on a 3x2 lot (a long block, a tall tower at its +z end, a red -x wall), a 1x4 reward tower row, a 5x5
reward spire and a 5x4 landmark court, one 2x3 landmark wider than its lot (the overhang note), and entries bldimport must
refuse: a 2x3 growable, a 2x6 landmark, a 1x2 seaport. Task civlot (2026-11-23): a police look hall on a 3x2 lot
(installed turned a quarter as 2x3) and a Small Park look on a 2x3 lot (refused before civlot).
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw


class Obj:
    def __init__(self, name):
        self.name = name
        self.v, self.vt, self.f = [], [], []
        self.mats = {}
        self.cur = None

    def mat(self, name, kd=None, tex=None):
        self.mats.setdefault(name, {"kd": kd or (0.8, 0.8, 0.8), "tex": tex})
        self.cur = name

    def quad(self, p, uv=None):
        """p: 4 points counter-clockwise seen from outside."""
        base = len(self.v) + 1
        self.v += [tuple(map(float, q)) for q in p]
        if uv:
            tb = len(self.vt) + 1
            self.vt += [tuple(map(float, q)) for q in uv]
            self.f.append((self.cur, [(base + k, tb + k) for k in range(4)]))
        else:
            self.f.append((self.cur, [(base + k, None) for k in range(4)]))

    def tri(self, p, uv=None):
        base = len(self.v) + 1
        self.v += [tuple(map(float, q)) for q in p]
        if uv:
            tb = len(self.vt) + 1
            self.vt += [tuple(map(float, q)) for q in uv]
            self.f.append((self.cur, [(base + k, tb + k) for k in range(3)]))
        else:
            self.f.append((self.cur, [(base + k, None) for k in range(3)]))

    def box(self, x0, y0, z0, x1, y1, z1, mats=None, uvs=None):
        """Axis box. mats/uvs: dict per face name (px nx py ny pz nz) -> material / (u0, v0, u1, v1) texture rect."""
        P = lambda x, y, z: (x, y, z)  # noqa: E731
        faces = {
            "pz": [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)],
            "nz": [P(x1, y0, z0), P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0)],
            "px": [P(x1, y0, z1), P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1)],
            "nx": [P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1), P(x0, y1, z0)],
            "py": [P(x0, y1, z1), P(x1, y1, z1), P(x1, y1, z0), P(x0, y1, z0)],
            "ny": [P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)],
        }
        for k, p in faces.items():
            if mats and k in mats:
                if mats[k] is None:
                    continue
                self.cur = mats[k]
            uv = None
            if uvs and k in uvs:
                a, b, c, d = uvs[k]
                uv = [(a, b), (c, b), (c, d), (a, d)]
            self.quad(p, uv)

    def write(self, folder):
        mtl = self.name + ".mtl"
        with open(os.path.join(folder, self.name + ".obj"), "w", newline="\n") as fh:
            fh.write("# %s.obj - bldimport test model, metres, Y up, front = +Z\nmtllib %s\n" % (self.name, mtl))
            for q in self.v:
                fh.write("v %.4f %.4f %.4f\n" % q)
            for q in self.vt:
                fh.write("vt %.4f %.4f\n" % q)
            cur = None
            for m, idx in self.f:
                if m != cur:
                    fh.write("usemtl %s\n" % m)
                    cur = m
                fh.write("f " + " ".join(("%d/%d" % (a, b)) if b else str(a) for a, b in idx) + "\n")
        with open(os.path.join(folder, mtl), "w", newline="\n") as fh:
            for k, m in self.mats.items():
                fh.write("newmtl %s\nKd %.3f %.3f %.3f\n" % ((k,) + tuple(m["kd"])))
                if m["tex"]:
                    fh.write("map_Kd %s\n" % m["tex"])
                fh.write("\n")


def gable_roof(o, x0, x1, z0, z1, y0, y1, over, roof_mat, gable_mat, uv=False):
    """Ridge along X at height y1, eaves at y0, overhang `over` on every side."""
    xa, xb, za, zb, zm = x0 - over, x1 + over, z0 - over, z1 + over, (z0 + z1) / 2.0
    o.cur = roof_mat
    if uv:
        o.quad([(xa, y0, zb), (xb, y0, zb), (xb, y1, zm), (xa, y1, zm)], [(0, 0), (3, 0), (3, 1.5), (0, 1.5)])
        o.quad([(xb, y0, za), (xa, y0, za), (xa, y1, zm), (xb, y1, zm)], [(0, 0), (3, 0), (3, 1.5), (0, 1.5)])
    else:
        o.quad([(xa, y0, zb), (xb, y0, zb), (xb, y1, zm), (xa, y1, zm)])
        o.quad([(xb, y0, za), (xa, y0, za), (xa, y1, zm), (xb, y1, zm)])
    o.cur = gable_mat
    g0 = [(x1, y0, z1), (x1, y0, z0), (x1, y1, zm)]
    g1 = [(x0, y0, z0), (x0, y0, z1), (x0, y1, zm)]
    if uv:
        o.tri(g0, [(0, 0), (1, 0), (0.5, 0.6)])
        o.tri(g1, [(0, 0), (1, 0), (0.5, 0.6)])
    else:
        o.tri(g0)
        o.tri(g1)


def tree(o, x, z, h=7.0, r=2.6):
    o.mat("trunk", (0.36, 0.25, 0.15))
    o.box(x - 0.3, 0, z - 0.3, x + 0.3, h * 0.45, z + 0.3, mats={"py": None, "ny": None})
    o.mat("leaves", (0.22, 0.48, 0.16))
    # low-poly crown: an octahedron-ish blob of 8 triangles stretched
    c = (x, h * 0.62, z)
    pts = [(x + r, c[1], z), (x, c[1], z + r), (x - r, c[1], z), (x, c[1], z - r)]
    top, bot = (x, h, z), (x, h * 0.35, z)
    for k in range(4):
        a, b = pts[k], pts[(k + 1) % 4]
        o.tri([a, b, top])
        o.tri([b, a, bot])


def house_plain(folder):
    o = Obj("house_plain")
    o.mat("walls", (0.86, 0.80, 0.66))
    o.box(-5, 0, -4, 5, 4.6, 4, mats={"py": None, "ny": None})
    o.mat("door", (0.42, 0.22, 0.12))
    o.box(-0.7, 0, 4.0, 0.7, 2.3, 4.12, mats={"ny": None, "nz": None})                     # front door on +Z
    o.mat("window", (0.22, 0.30, 0.42))
    for x in (-3.4, 2.2):
        o.box(x, 1.4, 4.0, x + 1.2, 2.6, 4.08, mats={"ny": None, "nz": None})
        o.box(x, 1.4, -4.08, x + 1.2, 2.6, -4.0, mats={"ny": None, "pz": None})
    for z in (-2.0, 1.0):
        o.box(5.0, 1.4, z, 5.08, 2.6, z + 1.2, mats={"ny": None, "nx": None})
        o.box(-5.08, 1.4, z, -5.0, 2.6, z + 1.2, mats={"ny": None, "px": None})
    o.mat("roof", (0.62, 0.26, 0.18))
    o.mats.setdefault("gable", {"kd": (0.86, 0.80, 0.66), "tex": None})
    gable_roof(o, -5, 5, -4, 4, 4.6, 7.8, 0.5, "roof", "gable")
    o.mat("chimney", (0.55, 0.32, 0.26))
    o.box(2.4, 5.5, -2.6, 3.4, 8.9, -1.6, mats={"ny": None})
    o.mat("path", (0.62, 0.60, 0.56))
    o.box(-0.8, 0, 4.12, 0.8, 0.05, 7.6, mats={"ny": None})                                # path to the road
    o.write(folder)


def _wall_tex(path, w=256, h=128, door=False):
    im = Image.new("RGB", (w, h), (150, 66, 48))
    d = ImageDraw.Draw(im)
    for y in range(0, h, 6):                                    # brick courses
        d.line([(0, y), (w, y)], fill=(196, 180, 160))
        off = 0 if (y // 6) % 2 else 8
        for x in range(off, w, 16):
            d.line([(x, y), (x, y + 6)], fill=(196, 180, 160))
    for k in range(4):                                          # two rows of windows
        for row in (0, 1):
            x0 = 18 + k * 62
            if door and row == 0 and k in (1, 2):
                continue
            y0 = 20 + row * 56
            d.rectangle([x0, y0, x0 + 26, y0 + 34], fill=(236, 232, 220))
            d.rectangle([x0 + 3, y0 + 3, x0 + 23, y0 + 31], fill=(60, 84, 118))
            d.line([(x0 + 13, y0 + 3), (x0 + 13, y0 + 31)], fill=(236, 232, 220), width=2)
    if door:
        d.rectangle([104, 66, 152, 128], fill=(236, 232, 220))
        d.rectangle([109, 72, 147, 128], fill=(28, 70, 44))
        d.ellipse([139, 98, 143, 102], fill=(210, 180, 60))
    im.save(path)


def _roof_tex(path, w=128, h=64):
    im = Image.new("RGB", (w, h), (70, 74, 84))
    d = ImageDraw.Draw(im)
    for y in range(0, h, 8):
        d.line([(0, y), (w, y)], fill=(48, 50, 58), width=2)
        off = 0 if (y // 8) % 2 else 6
        for x in range(off, w, 12):
            d.line([(x, y), (x, y + 8)], fill=(58, 60, 68))
    im.save(path)


def house_tex(folder):
    _wall_tex(os.path.join(folder, "house_tex_wall.png"))
    _wall_tex(os.path.join(folder, "house_tex_front.png"), door=True)
    _roof_tex(os.path.join(folder, "house_tex_roof.png"))
    o = Obj("house_tex")
    o.mats["wall"] = {"kd": (0.6, 0.3, 0.2), "tex": "house_tex_wall.png"}
    o.mats["front"] = {"kd": (0.6, 0.3, 0.2), "tex": "house_tex_front.png"}
    o.mats["roof"] = {"kd": (0.3, 0.3, 0.35), "tex": "house_tex_roof.png"}
    o.box(-5.5, 0, -4.2, 5.5, 6.2, 4.2,
          mats={"pz": "front", "nz": "wall", "px": "wall", "nx": "wall", "py": None, "ny": None},
          uvs={"pz": (0, 0, 1, 1), "nz": (0, 0, 1, 1), "px": (0, 0, 0.76, 1), "nx": (0, 0, 0.76, 1)})
    gable_roof(o, -5.5, 5.5, -4.2, 4.2, 6.2, 9.4, 0.45, "roof", "wall", uv=True)
    o.mat("step", (0.70, 0.68, 0.64))
    o.box(-1.2, 0, 4.2, 1.2, 0.25, 5.2, mats={"ny": None})
    o.box(-0.8, 0, 5.2, 0.8, 0.05, 7.8, mats={"ny": None})
    o.write(folder)


def block_2x2(folder):
    o = Obj("block_2x2")
    o.mat("wall", (0.78, 0.74, 0.70))
    o.box(-11, 0, -6, 11, 10.5, 6, mats={"ny": None})
    o.mat("roof", (0.40, 0.40, 0.42))
    o.box(-11.3, 10.5, -6.3, 11.3, 11.1, 6.3, mats={"ny": None})
    o.mat("plant", (0.55, 0.55, 0.57))
    o.box(3, 11.1, -3, 7, 13.0, 1, mats={"ny": None})
    o.mat("window", (0.20, 0.28, 0.40))
    for fl in range(3):
        y0 = 1.2 + fl * 3.3
        for k in range(7):
            x = -9.6 + k * 2.9
            if fl == 0 and k == 3:
                continue
            o.box(x, y0, 6.0, x + 1.5, y0 + 1.6, 6.08, mats={"ny": None, "nz": None})
            o.box(x, y0, -6.08, x + 1.5, y0 + 1.6, -6.0, mats={"ny": None, "pz": None})
        for k in range(3):
            zz = -4.2 + k * 3.0
            o.box(11.0, y0, zz, 11.08, y0 + 1.6, zz + 1.5, mats={"ny": None, "nx": None})
            o.box(-11.08, y0, zz, -11.0, y0 + 1.6, zz + 1.5, mats={"ny": None, "px": None})
    o.mat("door", (0.30, 0.16, 0.10))
    o.box(-1.2, 0, 6.0, 1.2, 2.6, 6.15, mats={"ny": None, "nz": None})
    o.mat("awning", (0.70, 0.18, 0.16))
    o.box(-1.8, 2.7, 6.0, 1.8, 2.95, 7.2, mats={"nz": None})
    o.mat("path", (0.62, 0.60, 0.56))
    o.box(-1.4, 0, 6.15, 1.4, 0.05, 15.5, mats={"ny": None})
    tree(o, -8.5, 11.5)
    tree(o, 8.5, 11.0, h=6.0, r=2.2)
    o.write(folder)


def cylinder(o, x, z, r, y0, y1, sides=12, mat_side=None, mat_top=None):
    """Upright prism with `sides` faces (counter-clockwise from outside) and a flat top."""
    pts = [(x + r * math.cos(2 * math.pi * k / sides), z + r * math.sin(2 * math.pi * k / sides)) for k in range(sides)]
    if mat_side:
        o.cur = mat_side
    for k in range(sides):
        (ax, az), (bx, bz) = pts[k], pts[(k + 1) % sides]
        o.quad([(bx, y0, bz), (ax, y0, az), (ax, y1, az), (bx, y1, bz)])
    if mat_top:
        o.cur = mat_top
    for k in range(sides):
        (ax, az), (bx, bz) = pts[k], pts[(k + 1) % sides]
        o.tri([(bx, y1, bz), (ax, y1, az), (x, y1, z)])


def container(o, x, z, y, along_x, mat):
    """One 12 x 2.4 x 2.6 m shipping container, its long side along X or Z, bottom at y."""
    o.cur = mat
    hx, hz = (6.0, 1.2) if along_x else (1.2, 6.0)
    o.box(x - hx, y, z - hz, x + hx, y + 2.6, z + hz, mats={"ny": None})


def pad(o, half_x, half_z, kd=(0.58, 0.58, 0.56)):
    o.mat("pad", kd)
    o.box(-half_x, 0, -half_z, half_x, 0.08, half_z, mats={"ny": None})


def fuel_depot(folder, name="fuel_depot"):
    o = Obj(name)
    pad(o, 7.6, 7.6)
    o.mat("tank", (0.92, 0.92, 0.90))
    o.mat("band", (0.78, 0.14, 0.12))
    for x, z in ((-3.4, -2.6), (3.0, -2.8)):
        cylinder(o, x, z, 2.7, 0.08, 3.0, mat_side="tank", mat_top="tank")
        cylinder(o, x, z, 2.72, 3.0, 3.8, mat_side="band", mat_top="band")
        cylinder(o, x, z, 2.7, 3.8, 6.2, mat_side="tank", mat_top="tank")
    o.mat("pump", (0.18, 0.36, 0.70))
    o.box(-2.0, 0.08, 2.6, 2.6, 3.0, 6.2, mats={"ny": None})
    o.mat("pumproof", (0.86, 0.86, 0.84))
    o.box(-2.3, 3.0, 2.3, 2.9, 3.3, 6.5, mats={"ny": None})
    o.mat("pipe", (0.45, 0.45, 0.47))
    o.box(-3.6, 1.0, -0.2, 3.2, 1.5, 0.3, mats={"ny": None})
    o.write(folder)


def container_stack(folder):
    o = Obj("container_stack")
    pad(o, 7.8, 7.8)
    for name, kd in (("red", (0.74, 0.16, 0.12)), ("blue", (0.14, 0.30, 0.66)), ("yellow", (0.88, 0.70, 0.12)),
                     ("green", (0.16, 0.52, 0.28))):
        o.mat(name, kd)
    container(o, 0.0, -4.4, 0.08, True, "red")
    container(o, 0.0, -1.6, 0.08, True, "blue")
    container(o, 0.0, 1.2, 0.08, True, "yellow")
    container(o, 0.0, -3.0, 2.68, True, "green")
    container(o, 0.0, -0.2, 2.68, True, "red")
    container(o, 0.0, -1.6, 5.28, True, "blue")
    o.write(folder)


def warehouse_2x2(folder, name="warehouse_2x2"):
    o = Obj(name)
    pad(o, 15.6, 15.6)
    o.mat("shed", (0.16, 0.50, 0.52))
    o.box(-13.0, 0.08, -12.0, 13.0, 8.0, 2.0, mats={"ny": None, "py": None})
    o.mat("roof", (0.62, 0.64, 0.66))
    o.mats.setdefault("gable2", {"kd": (0.16, 0.50, 0.52), "tex": None})
    gable_roof(o, -13.0, 13.0, -12.0, 2.0, 8.0, 10.6, 0.4, "roof", "gable2")
    o.mat("stripe", (0.95, 0.95, 0.93))
    o.box(-13.2, 6.6, 2.0, 13.2, 7.4, 2.12, mats={"ny": None, "nz": None})
    o.mat("doors", (0.30, 0.32, 0.34))
    for x in (-9.0, -2.0, 5.0):
        o.box(x, 0.08, 2.0, x + 4.0, 5.2, 2.1, mats={"ny": None, "nz": None})
    o.mat("gantry", (0.92, 0.72, 0.10))
    for x in (-11.0, 11.0):
        o.box(x - 0.5, 0.08, 6.0, x + 0.5, 12.0, 7.0, mats={"ny": None})
        o.box(x - 0.5, 0.08, 13.0, x + 0.5, 12.0, 14.0, mats={"ny": None})
    o.box(-11.5, 12.0, 6.0, 11.5, 13.2, 14.0, mats={"ny": None})
    for name, kd in (("red", (0.74, 0.16, 0.12)), ("blue", (0.14, 0.30, 0.66)), ("green", (0.16, 0.52, 0.28))):
        o.mat(name, kd)
    container(o, -6.0, 8.4, 0.08, True, "red")
    container(o, 6.4, 8.4, 0.08, True, "blue")
    container(o, -6.0, 11.4, 0.08, True, "green")
    container(o, 6.4, 11.4, 0.08, True, "red")
    container(o, 0.2, 9.9, 2.68, True, "blue")
    o.write(folder)


def ports(out):
    """Task airsea: the airport / seaport test models + their models.json."""
    os.makedirs(out, exist_ok=True)
    fuel_depot(out)
    container_stack(out)
    warehouse_2x2(out)
    warehouse_2x2(out, "airport_2x2")
    fuel_depot(out, "fuel_depot_25")
    common = {"scale": 1.0, "rotate_deg": 0, "style": "any", "enabled": True}
    models = {"sc3models": 1, "generator": "make_testmodels.py --ports", "models": [
        dict(common, file="fuel_depot.obj", name="Test fuel depot", kind="airport", lot=[1, 1], weight=5,
             height_m=6.2, notes="airport 1x1: 5 copies in the airpark filler list (stock has 5 buildings there)"),
        dict(common, file="container_stack.obj", name="Test container stack", kind="seaport", lot=[1, 1],
             weight=10, height_m=7.9, notes="seaport 1x1, stats of Seaport Crane 224"),
        dict(common, file="warehouse_2x2.obj", name="Test harbour warehouse", kind="seaport", lot=[2, 2],
             weight=10, height_m=13.2, notes="seaport 2x2, stats of Seaport Loading Bay 240"),
        dict(common, file="airport_2x2.obj", name="Refused: airport 2x2", kind="airport", lot=[2, 2], weight=1,
             height_m=13.2, notes="the airpark grows only 1x1 fillers: bldimport skips this entry"),
        dict(common, file="fuel_depot_25.obj", name="Refused: airport weight 25", kind="airport", lot=[1, 1],
             weight=25, height_m=6.2, notes="more copies than PORT_MAX_COPIES: skipped")]}
    with open(os.path.join(out, "models.json"), "w", newline="\n") as fh:
        json.dump(models, fh, indent=2)
    print("wrote port test models to", out)
    return 0


def obelisk_2x2(folder, name="obelisk_2x2"):
    o = Obj(name)
    o.mat("plaza", (0.90, 0.89, 0.85))
    o.box(-15.6, 0, -15.6, 15.6, 0.3, 15.6, mats={"ny": None})
    o.box(-9.0, 0.3, -9.0, 9.0, 1.2, 9.0, mats={"ny": None})
    o.box(-5.5, 1.2, -5.5, 5.5, 2.2, 5.5, mats={"ny": None})
    o.mat("stone", (0.70, 0.18, 0.14))
    o.box(-2.4, 2.2, -2.4, 2.4, 24.0, 2.4, mats={"ny": None})
    o.mat("gold", (0.92, 0.74, 0.20))
    o.box(-2.6, 2.2, -2.6, 2.6, 4.0, 2.6, mats={"ny": None})
    o.tri([(-2.4, 24.0, 2.4), (2.4, 24.0, 2.4), (0, 28.5, 0)])
    o.tri([(2.4, 24.0, 2.4), (2.4, 24.0, -2.4), (0, 28.5, 0)])
    o.tri([(2.4, 24.0, -2.4), (-2.4, 24.0, -2.4), (0, 28.5, 0)])
    o.tri([(-2.4, 24.0, -2.4), (-2.4, 24.0, 2.4), (0, 28.5, 0)])
    o.mat("lamp", (0.20, 0.20, 0.22))
    for x, z in ((-12.0, -12.0), (12.0, -12.0), (-12.0, 12.0), (12.0, 12.0)):
        o.box(x - 0.3, 0.3, z - 0.3, x + 0.3, 5.0, z + 0.3, mats={"ny": None})
    o.mat("light", (0.98, 0.94, 0.70))
    for x, z in ((-12.0, -12.0), (12.0, -12.0), (-12.0, 12.0), (12.0, 12.0)):
        o.box(x - 0.7, 5.0, z - 0.7, x + 0.7, 6.0, z + 0.7, mats={"ny": None})
    o.write(folder)


def pavilion_3x3(folder, name="pavilion_3x3"):
    o = Obj(name)
    o.mat("plaza", (0.84, 0.82, 0.76))
    o.box(-23.6, 0, -23.6, 23.6, 0.3, 23.6, mats={"ny": None})
    o.mat("base", (0.94, 0.93, 0.90))
    cylinder(o, 0, -3.0, 15.0, 0.3, 1.5, sides=24, mat_side="base", mat_top="base")
    o.mat("column", (0.97, 0.96, 0.93))
    for k in range(12):
        a = 2 * math.pi * k / 12
        cylinder(o, 13.0 * math.cos(a), -3.0 + 13.0 * math.sin(a), 0.8, 1.5, 11.0, sides=8, mat_side="column")
    cylinder(o, 0, -3.0, 14.2, 11.0, 12.4, sides=24, mat_side="base", mat_top="base")
    o.mat("dome", (0.18, 0.56, 0.54))
    rings = 6
    for j in range(rings):
        a0, a1 = math.pi / 2 * j / rings, math.pi / 2 * (j + 1) / rings
        r0, r1 = 13.0 * math.cos(a0), 13.0 * math.cos(a1)
        y0, y1 = 12.4 + 10.0 * math.sin(a0), 12.4 + 10.0 * math.sin(a1)
        for k in range(24):
            b0, b1 = 2 * math.pi * k / 24, 2 * math.pi * (k + 1) / 24
            p00 = (r0 * math.cos(b0), y0, -3.0 + r0 * math.sin(b0))
            p01 = (r0 * math.cos(b1), y0, -3.0 + r0 * math.sin(b1))
            p10 = (r1 * math.cos(b0), y1, -3.0 + r1 * math.sin(b0))
            p11 = (r1 * math.cos(b1), y1, -3.0 + r1 * math.sin(b1))
            o.quad([p01, p00, p10, p11])
    o.mat("water", (0.30, 0.52, 0.80))
    cylinder(o, 0, 17.0, 4.5, 0.3, 0.9, sides=16, mat_side="base", mat_top="water")
    o.write(folder)


def landmarks(out):
    """Task plop: the landmark test models + their models.json."""
    os.makedirs(out, exist_ok=True)
    obelisk_2x2(out)
    pavilion_3x3(out)
    pavilion_3x3(out, "landmark_5x5")
    obelisk_2x2(out, "civic_1x1")
    common = {"scale": 1.0, "rotate_deg": 0, "style": "any", "enabled": True, "weight": 1}
    models = {"sc3models": 1, "generator": "make_testmodels.py --landmarks", "models": [
        dict(common, file="obelisk_2x2.obj", name="Test obelisk", kind="landmark", lot=[2, 2], height_m=28.5,
             notes="landmark 2x2, stats of Coit Tower 9507"),
        dict(common, file="pavilion_3x3.obj", name="Test pavilion", kind="landmark", lot=[3, 3], height_m=22.4,
             notes="landmark 3x3, stats of Arc de Triomphe 9528"),
        dict(common, file="landmark_5x5.obj", name="Test pavilion 5x5", kind="landmark", lot=[5, 5],
             height_m=22.4, notes="landmark 5x5, stats of Congresshalle 9552 (task lotshape; refused before)"),
        dict(common, file="civic_1x1.obj", name="Refused: ploppable", kind="ploppable", lot=[1, 1], height_m=28.5,
             notes="kind ploppable is not imported (civic looks are kind civic, task civmod): skipped")]}
    with open(os.path.join(out, "models.json"), "w", newline="\n") as fh:
        json.dump(models, fh, indent=2)
    print("wrote landmark test models to", out)
    return 0


def police_3x3(folder, name="police_3x3"):
    o = Obj(name)
    o.mat("lot", (0.45, 0.45, 0.47))
    o.box(-23.6, 0, -23.6, 23.6, 0.3, 23.6, mats={"ny": None})
    o.mat("walls", (0.14, 0.20, 0.42))
    o.box(-17.0, 0.3, -17.0, 17.0, 9.0, 6.0, mats={"ny": None})
    o.mat("band", (0.95, 0.95, 0.95))
    o.box(-17.2, 4.2, -17.2, 17.2, 5.0, 6.2, mats={"ny": None})
    o.mat("roof", (0.30, 0.30, 0.33))
    o.box(-17.4, 9.0, -17.4, 17.4, 9.6, 6.4, mats={"ny": None})
    o.mat("light", (0.10, 0.45, 0.95))
    o.box(-1.5, 9.6, -6.0, 1.5, 12.0, -3.0, mats={"ny": None})
    o.mat("car", (0.95, 0.95, 0.98))
    for x in (-12.0, -4.0, 4.0, 12.0):
        o.box(x - 1.5, 0.3, 12.0, x + 1.5, 1.8, 18.0, mats={"ny": None})
    o.write(folder)


def civmod(out):
    """Task civmod: a police look, two rewards, a landmark, and entries to refuse."""
    os.makedirs(out, exist_ok=True)
    police_3x3(out)
    police_3x3(out, "police_2x2")
    police_3x3(out, "civic_unknown")
    obelisk_2x2(out)
    obelisk_2x2(out, "reward_locked")
    obelisk_2x2(out, "reward_semicolon")
    pavilion_3x3(out)
    common = {"scale": 1.0, "rotate_deg": 0, "style": "any", "enabled": True, "weight": 1}
    models = {"sc3models": 1, "generator": "make_testmodels.py --civmod", "models": [
        dict(common, file="police_3x3.obj", name="Test police look", kind="civic", base="police", height_m=12.0,
             notes="look 2 of the Police Station button, stats of stock 0xD2 (type 13130)"),
        dict(common, file="obelisk_2x2.obj", name="Test reward obelisk", kind="reward", lot=[2, 2], population=1000,
             year=0, height_m=28.5, description="Test reward, bldimport", notes="unlocks past 1,000 people"),
        dict(common, file="reward_locked.obj", name="Test locked reward", kind="reward", lot=[2, 2],
             population=100000000, height_m=28.5, notes="stays locked"),
        dict(common, file="pavilion_3x3.obj", name="Test pavilion", kind="landmark", lot=[3, 3], height_m=22.4,
             notes="landmark, type 18000: Mover"),
        dict(common, file="police_2x2.obj", name="Test police look 2x2", kind="civic", base="police", lot=[2, 2],
             height_m=12.0, notes="task civlot: a police look on a 2x2 lot, stats of stock 0xD2 (refused before)"),
        dict(common, file="civic_unknown.obj", name="Refused: unknown base", kind="civic", base="castle",
             height_m=12.0, notes="no such civic button: skipped"),
        dict(common, file="reward_semicolon.obj", name="Refused; semicolon", kind="reward", lot=[2, 2],
             height_m=28.5, notes="the reward row cannot hold ';': skipped")]}
    with open(os.path.join(out, "models.json"), "w", newline="\n") as fh:
        json.dump(models, fh, indent=2)
    print("wrote civmod test models to", out)
    return 0


# task civtest (2026-11-19): base -> lot of the stock building (CIVIC_REWARD.md 5 / bldimport civic_table)
CIVTEST_BASES = [("police", 3), ("jail", 3), ("fire", 3), ("hospital", 3), ("school", 3), ("college", 3),
                 ("library", 2), ("museum", 3), ("small_park", 1), ("big_park", 3), ("zoo", 4), ("baseball", 4),
                 ("playground", 2), ("pond", 2), ("fountain", 1), ("bus_stop", 1), ("train_station", 2)]


def civic_block(folder, name, n, kd, height):
    """A block filling most of an n x n lot (cell = 16 m), colour kd, white band, a sign on the roof."""
    o = Obj(name)
    h = 8.0 * n - 0.4
    o.mat("lot", (0.45, 0.45, 0.47))
    o.box(-h, 0, -h, h, 0.3, h, mats={"ny": None})
    w = h * 0.72
    o.mat("walls", kd)
    o.box(-w, 0.3, -w, w, height * 0.75, w * 0.4, mats={"ny": None})
    o.mat("band", (0.97, 0.97, 0.97))
    o.box(-w - 0.2, height * 0.38, -w - 0.2, w + 0.2, height * 0.46, w * 0.4 + 0.2, mats={"ny": None})
    o.mat("roof", (0.25, 0.25, 0.27))
    o.box(-w - 0.3, height * 0.75, -w - 0.3, w + 0.3, height * 0.8, w * 0.4 + 0.3, mats={"ny": None})
    o.mat("sign", (0.98, 0.84, 0.10))
    o.box(-w * 0.5, height * 0.8, -1.0, w * 0.5, height, 1.0, mats={"ny": None})
    o.write(folder)


def spire(folder, name, n):
    """Reward: stepped plaza on an n x n lot, a gold spire."""
    o = Obj(name)
    h = 8.0 * n - 0.4
    o.mat("plaza", (0.90, 0.89, 0.85))
    o.box(-h, 0, -h, h, 0.3, h, mats={"ny": None})
    o.box(-h * 0.6, 0.3, -h * 0.6, h * 0.6, 1.4, h * 0.6, mats={"ny": None})
    o.mat("stone", (0.30, 0.20, 0.55))
    s = 1.2 + 0.8 * n
    top = 10.0 + 6.0 * n
    o.box(-s, 1.4, -s, s, top, s, mats={"ny": None})
    o.mat("gold", (0.92, 0.74, 0.20))
    for a, b in (((-s, top, s), (s, top, s)), ((s, top, s), (s, top, -s)), ((s, top, -s), (-s, top, -s)),
                 ((-s, top, -s), (-s, top, s))):
        o.tri([a, b, (0, top + 2.5 * s, 0)])
    o.write(folder)


def plaza_3x3(folder, name="plaza_3x3"):
    """Growable 3x3 commercial: a glass tower on a podium."""
    o = Obj(name)
    o.mat("lot", (0.55, 0.55, 0.56))
    o.box(-23.6, 0, -23.6, 23.6, 0.3, 23.6, mats={"ny": None})
    o.mat("podium", (0.80, 0.42, 0.20))
    o.box(-20.0, 0.3, -20.0, 20.0, 7.0, 14.0, mats={"ny": None})
    o.mat("glass", (0.25, 0.62, 0.70))
    o.box(-9.0, 7.0, -12.0, 9.0, 42.0, 4.0, mats={"ny": None})
    o.mat("roof", (0.92, 0.92, 0.92))
    o.box(-9.4, 42.0, -12.4, 9.4, 43.0, 4.4, mats={"ny": None})
    o.write(folder)


def civtest(out):
    """Task civtest: a look per civic button, rewards 1x1 / 3x3 / 4x4, a 3x3 growable."""
    os.makedirs(out, exist_ok=True)
    common = {"scale": 1.0, "rotate_deg": 0, "style": "any", "enabled": True, "weight": 1}
    models = []
    for k, (base, n) in enumerate(CIVTEST_BASES):
        hue = k / len(CIVTEST_BASES)
        import colorsys
        kd = colorsys.hsv_to_rgb(hue, 0.75, 0.80)
        civic_block(out, "civic_" + base, n, kd, 10.0 + 2.0 * n)
        models.append(dict(common, file="civic_%s.obj" % base, name="Test %s look" % base.replace("_", " "),
                           kind="civic", base=base, height_m=10.0 + 2.0 * n,
                           description="Test look, bldimport civtest", notes="look 2 of the %s button" % base))
    for n in (1, 3, 4):
        spire(out, "reward_%dx%d" % (n, n), n)
        models.append(dict(common, file="reward_%dx%d.obj" % (n, n), name="Test reward %dx%d" % (n, n),
                           kind="reward", lot=[n, n], population=1000, year=0,
                           height_m=round(10.0 + 6.0 * n + 2.5 * (1.2 + 0.8 * n), 1),
                           description="Test reward %dx%d, bldimport civtest" % (n, n), notes="unlocks past 1,000 people"))
    plaza_3x3(out)
    models.append(dict(common, file="plaza_3x3.obj", name="Test plaza 3x3", kind="growable", **{"class": 6300},
                       lot=[3, 3], height_m=43.0, notes="3x3 commercial growable", weight=20))
    with open(os.path.join(out, "models.json"), "w", newline="\n") as fh:
        json.dump({"sc3models": 1, "generator": "make_testmodels.py --civtest", "models": models}, fh, indent=2)
    print("wrote civtest test models to", out, len(models), "models")
    return 0


def civdlg(out):
    """Task civdlg: police with three looks (pick each in the list window), fire and school with one, every other
    civic button with none (stays stock: the hospital is the check)."""
    import colorsys
    os.makedirs(out, exist_ok=True)
    common = {"scale": 1.0, "rotate_deg": 0, "style": "any", "enabled": True, "weight": 1}
    police_3x3(out, "police_blue")
    civic_block(out, "police_green", 3, colorsys.hsv_to_rgb(0.33, 0.75, 0.80), 16.0)
    civic_block(out, "police_red", 3, colorsys.hsv_to_rgb(0.0, 0.75, 0.80), 16.0)
    civic_block(out, "fire_look", 3, colorsys.hsv_to_rgb(0.08, 0.85, 0.90), 16.0)
    civic_block(out, "school_look", 3, colorsys.hsv_to_rgb(0.60, 0.70, 0.85), 16.0)
    models = [
        dict(common, file="police_blue.obj", name="Police blue", kind="civic", base="police", height_m=12.0,
             description="Test look, bldimport civdlg", notes="police look 2"),
        dict(common, file="police_green.obj", name="Police green", kind="civic", base="police", height_m=16.0,
             description="Test look, bldimport civdlg", notes="police look 3"),
        dict(common, file="police_red.obj", name="Police red", kind="civic", base="police", height_m=16.0,
             description="Test look, bldimport civdlg", notes="police look 4"),
        dict(common, file="fire_look.obj", name="Fire orange", kind="civic", base="fire", height_m=16.0,
             description="Test look, bldimport civdlg", notes="fire look 2"),
        dict(common, file="school_look.obj", name="School blue", kind="civic", base="school", height_m=16.0,
             description="Test look, bldimport civdlg", notes="school look 2")]
    with open(os.path.join(out, "models.json"), "w", newline="\n") as fh:
        json.dump({"sc3models": 1, "generator": "make_testmodels.py --civdlg", "models": models}, fh, indent=2)
    print("wrote civdlg test models to", out, len(models), "models")
    return 0


def hall(folder, name, w, d, tower=True, over=0.0):
    """Task lotshape: a w x d cell lot (cell 16 m, model x = w, z = d): a pale plaza, a long block, a tall tower at the
    +z end, the -x wall red, a gold roof strip along z. over: metres the plaza reaches past the lot on every side."""
    o = Obj(name)
    hx, hz = 8.0 * w - 0.4 + over, 8.0 * d - 0.4 + over
    o.mat("plaza", (0.86, 0.84, 0.78))
    o.box(-hx, 0, -hz, hx, 0.3, hz, mats={"ny": None})
    bx, bz = 8.0 * w - 3.0, 8.0 * d - 3.0
    o.mat("walls", (0.62, 0.66, 0.74))
    o.mat("red", (0.80, 0.16, 0.12))
    o.box(-bx, 0.3, -bz, bx, 11.0, bz, mats={"pz": "walls", "nz": "walls", "px": "walls", "nx": "red", "py": "walls", "ny": None})
    o.mat("gold", (0.92, 0.74, 0.20))
    o.box(-1.2, 11.0, -bz + 1.0, 1.2, 12.0, bz - 1.0, mats={"ny": None})
    if tower:
        o.mat("tower", (0.20, 0.36, 0.62))
        t = min(bx, 6.0)
        o.box(-t, 11.0, bz - 2 * t, t, 11.0 + 8.0 * max(w, d), bz, mats={"ny": None})
    o.write(folder)


def lotshape(out):
    """Task lotshape: non-square landmarks and rewards, 5x5, and entries to refuse (civlot: two civic looks)."""
    os.makedirs(out, exist_ok=True)
    common = {"scale": 1.0, "rotate_deg": 0, "style": "any", "enabled": True, "weight": 1}
    hall(out, "hall_2x3", 2, 3)
    hall(out, "hall_3x2", 3, 2)
    hall(out, "towers_1x4", 1, 4)
    spire(out, "reward_5x5", 5)
    hall(out, "court_5x4", 5, 4, tower=False)
    hall(out, "wide_2x3", 2, 3, over=6.0)
    hall(out, "grow_2x3", 2, 3)
    hall(out, "landmark_2x6", 2, 6)
    hall(out, "police_3x2", 3, 2)
    hall(out, "park_2x3", 2, 3, tower=False)
    hall(out, "seaport_1x2", 1, 2)
    models = [
        dict(common, file="hall_2x3.obj", name="Test hall 2x3", kind="landmark", lot=[2, 3], height_m=35.0,
             description="Test hall 2x3, bldimport lotshape", notes="landmark 2x3, stats of a 3x3 landmark"),
        dict(common, file="hall_3x2.obj", name="Test hall 3x2", kind="landmark", lot=[3, 2], height_m=35.0,
             notes="landmark 3x2"),
        dict(common, file="towers_1x4.obj", name="Test towers 1x4", kind="reward", lot=[1, 4], population=1000, year=0,
             height_m=43.0, description="Test reward 1x4, bldimport lotshape", notes="reward 1x4, stats of a 4x4 reward"),
        dict(common, file="reward_5x5.obj", name="Test reward 5x5", kind="reward", lot=[5, 5], population=1000, year=0,
             height_m=52.0, notes="reward 5x5, stats of Country Club 8046"),
        dict(common, file="court_5x4.obj", name="Test court 5x4", kind="landmark", lot=[5, 4], height_m=12.0,
             notes="landmark 5x4, stats of a 5x5 landmark"),
        dict(common, file="wide_2x3.obj", name="Test wide hall 2x3", kind="landmark", lot=[2, 3], height_m=35.0,
             notes="12 m wider and deeper than its lot: the overhang note"),
        dict(common, file="grow_2x3.obj", name="Refused: growable 3x2", kind="growable", lot=[3, 2], height_m=35.0,
             notes="a non-square growable lists its short side first (task lotgrowb): skipped", **{"class": 3500}),
        dict(common, file="landmark_2x6.obj", name="Refused: landmark 2x6", kind="landmark", lot=[2, 6],
             height_m=35.0, notes="a side longer than 5: skipped"),
        dict(common, file="police_3x2.obj", name="Test police look 3x2", kind="civic", base="police", lot=[3, 2],
             height_m=35.0, notes="task civlot: installed turned a quarter as 2x3 (X <= Z), stats of stock 0xD2"),
        dict(common, file="park_2x3.obj", name="Test park look 2x3", kind="civic", base="small_park", lot=[2, 3],
             height_m=12.0, notes="task civlot: a Small Park look on a 2x3 lot (the stock one is 1x1)"),
        dict(common, file="seaport_1x2.obj", name="Refused: seaport 1x2", kind="seaport", lot=[1, 2], weight=1,
             height_m=35.0, notes="ports stay square: skipped")]
    with open(os.path.join(out, "models.json"), "w", newline="\n") as fh:
        json.dump({"sc3models": 1, "generator": "make_testmodels.py --lotshape", "models": models}, fh, indent=2)
    print("wrote lotshape test models to", out, len(models), "models")
    return 0


def lotgrow(out):
    """Task lotgrowb (round 2026-11-24d): growables on w x d lots (1x2, 2x3, 3x4, long side along z), the copy families of
    3500 and 3700 with their rule rows (overlay SYS.PAK), a square growable of the same class beside them, and entries
    to refuse."""
    os.makedirs(out, exist_ok=True)
    common = {"scale": 1.0, "rotate_deg": 0, "style": "any", "enabled": True, "weight": 5}
    for nm, w, d in (("shop_1x2", 1, 2), ("villa_1x2", 1, 2), ("flats_1x2", 1, 2), ("tower_3x4", 3, 4), ("office_2x3", 2, 3),
                     ("square_2x2", 2, 2), ("bad_3x2", 3, 2), ("bad_1x3", 1, 3), ("farm_1x2", 1, 2), ("nobase_2x3", 2, 3),
                     ("dock_1x2", 1, 2)):
        hall(out, nm, w, d)
    G = "growable"
    models = [
        dict(common, file="shop_1x2.obj", name="Test shop 1x2", kind=G, lot=[1, 2], height_m=10.0,
             notes="class 5700, family 8 (commercial corners rule), stats of the 2x2 base", **{"class": 5700}),
        dict(common, file="villa_1x2.obj", name="Test villa 1x2", kind=G, lot=[1, 2], height_m=12.0,
             notes="class 3500: family 31 + the copy 38100 of family 10 (rows 2,3 of 0xa22653c0)", **{"class": 3500}),
        dict(common, file="flats_1x2.obj", name="Test flats 1x2", kind=G, lot=[1, 2], height_m=14.0,
             notes="class 3700: the copy 38116 of family 16 (rows 2,3 of 0x222c9d00)", **{"class": 3700}),
        dict(common, file="tower_3x4.obj", name="Test tower 3x4", kind=G, lot=[3, 4], height_m=60.0,
             notes="class 4500: family 14 only (30 is an L-block family), stats of the 4x4 base", **{"class": 4500}),
        dict(common, file="office_2x3.obj", name="Test office 2x3", kind=G, lot=[2, 3], height_m=30.0,
             notes="class 6100, family 23", **{"class": 6100}),
        dict(common, file="square_2x2.obj", name="Test square villa 2x2", kind=G, lot=[2, 2], height_m=12.0,
             notes="square, class 3500: families 10 and 31 as before; its line is in the copy 38100 too", **{"class": 3500}),
        dict(common, file="bad_3x2.obj", name="Refused: growable 3x2", kind=G, lot=[3, 2], height_m=12.0,
             notes="short side first: skipped", **{"class": 3300}),
        dict(common, file="bad_1x3.obj", name="Refused: growable 1x3", kind=G, lot=[1, 3], height_m=12.0,
             notes="sides differ by 2: skipped", **{"class": 3300}),
        dict(common, file="farm_1x2.obj", name="Refused: farm 1x2", kind=G, lot=[1, 2], height_m=8.0,
             notes="class 9300 grows only from the farm rule's family 25: skipped", **{"class": 9300}),
        dict(common, file="nobase_2x3.obj", name="Refused: 2x3 without a 3x3 base", kind=G, lot=[2, 3], height_m=8.0,
             notes="class 3300 has no 3x3 base: skipped", **{"class": 3300}),
        dict(common, file="dock_1x2.obj", name="Refused: seaport 1x2", kind="seaport", lot=[1, 2], height_m=12.0,
             notes="ports stay square: skipped")]
    with open(os.path.join(out, "models.json"), "w", newline="\n") as fh:
        json.dump({"sc3models": 1, "generator": "make_testmodels.py --lotgrow", "models": models}, fh, indent=2)
    print("wrote lotgrow test models to", out, len(models), "models")
    return 0


def main(argv):
    if len(argv) == 2 and argv[0] == "--lotshape":
        return lotshape(argv[1])
    if len(argv) == 2 and argv[0] == "--lotgrow":
        return lotgrow(argv[1])
    if len(argv) == 2 and argv[0] == "--civdlg":
        return civdlg(argv[1])
    if len(argv) == 2 and argv[0] == "--civtest":
        return civtest(argv[1])
    if len(argv) == 2 and argv[0] == "--civmod":
        return civmod(argv[1])
    if len(argv) == 2 and argv[0] == "--ports":
        return ports(argv[1])
    if len(argv) == 2 and argv[0] == "--landmarks":
        return landmarks(argv[1])
    if len(argv) != 1:
        print(__doc__)
        return 2
    out = argv[0]
    os.makedirs(out, exist_ok=True)
    house_plain(out)
    house_tex(out)
    block_2x2(out)
    models = {"sc3models": 1, "generator": "make_testmodels.py", "models": [
        {"file": "house_plain.obj", "name": "Test cottage (plain)", "kind": "growable", "class": 3300, "lot": [1, 1],
         "weight": 20, "height_m": 8.9, "scale": 1.0, "rotate_deg": 0, "style": "any", "enabled": True,
         "notes": "untextured, flat colours"},
        {"file": "house_tex.obj", "name": "Test brick house (textured)", "kind": "growable", "class": 3300,
         "lot": [1, 1], "weight": 20, "height_m": 9.4, "scale": 1.0, "rotate_deg": 0, "style": "any",
         "enabled": True, "notes": "textured walls and roof"},
        {"file": "block_2x2.obj", "name": "Test block 2x2", "kind": "growable", "class": 3900, "lot": [2, 2],
         "weight": 20, "height_m": 13.0, "scale": 1.0, "rotate_deg": 0, "style": "any", "enabled": True,
         "notes": "three storeys, two trees"}]}
    with open(os.path.join(out, "models.json"), "w", newline="\n") as fh:
        json.dump(models, fh, indent=2)
    print("wrote test models to", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
