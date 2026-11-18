#!/usr/bin/env python3
r"""make_testmodels.py - task bldrender (2026-11-18): the test models for bldimport, written from code (no game art).

    py -3.12 re/tools/bldimport/make_testmodels.py <out folder>

Writes, in OBJ metres with Y up and the front facing +Z (bldrender.py axes):
  house_plain.obj/.mtl    1x1 cottage, flat colours only (walls, roof, door, windows, chimney)
  house_tex.obj/.mtl      1x1 brick house, textured (house_tex_wall.png, house_tex_front.png, house_tex_roof.png)
  block_2x2.obj/.mtl      2x2 three-storey block with a flat roof, rooftop box and two trees
  models.json             the classifier page's format (sc3models 1), classes 3300 / 3300 / 3900
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


def main(argv):
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
