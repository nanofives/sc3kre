#!/usr/bin/env python3
r"""avenue_markings.py - reskin art for the stock straight avenue: white dashed lane lines instead of the yellow centre
line (owner, 2026-10-17: "on avenues instead of yellow lines they should be white striped lines for every lane").

  py -3 avenue_markings.py build PACK_DIR      art/<piece>/z{z}_r{r}.png (layer 0) for 11204 (avenue) and 11203 (end)

Per stock frame (zoom z, frame slot k) every pixel is unprojected to the frame's lane coordinates (x, zl in 0..256).
The yellow pixels give the line: its direction (the lane axis they spread along) and its footprint (their spread across
it). A yellow pixel becomes a white dash where lanelines.dash_on(along) holds (period 0.25 cell, dash centred in it, so
the frame's own lane direction does not matter), else the lane asphalt reflected about the line's edge. Other pixels
stay stock. Layer 1 (11204's trees) is left alone: a reskin replaces only the frames it ships.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from netmod import netart as NA                                                    # noqa: E402
from netmod import lanelines as LL                                                 # noqa: E402

PIECES = (11204, 11203)


def strong_yellow(c):
    """the centre line's own paint (yellow and the olive middle of the double line), never foliage or trunks"""
    r, g, b, a = c
    return a >= 128 and r - b > 60 and 0.7 * r <= g <= r


def warm(c):
    """a line pixel or its anti-aliased edge: warmer than the bluish asphalt, not green"""
    r, g, b, a = c
    return a >= 128 and r - b > 15 and g <= r + 5


def lane_grey(c):
    return c[3] >= 128 and max(c[:3]) < 118 and max(c[:3]) - min(c[:3]) < 22


def fit_circle(pts):
    """least-squares circle (Kasa) -> (cx, cz, radius), or None when the points are (close to) a straight line"""
    n = float(len(pts))
    mx, mz = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    suu = svv = suv = suuu = svvv = suvv = svuu = 0.0
    for x, z in pts:
        u, v = x - mx, z - mz
        suu += u * u
        svv += v * v
        suv += u * v
        suuu += u ** 3
        svvv += v ** 3
        suvv += u * v * v
        svuu += v * u * u
    det = suu * svv - suv * suv
    if abs(det) < 1e-9:
        return None
    bu = 0.5 * (suuu + suvv)
    bv = 0.5 * (svvv + svuu)
    uc = (bu * svv - bv * suv) / det
    vc = (bv * suu - bu * suv) / det
    R = ((uc * uc + vc * vc + (suu + svv) / n)) ** 0.5
    if R > 2000.0:
        return None
    return mx + uc, mz + vc, R


def frame(pid, z, k):
    """-> (output RGBA image, anchor, converted pixel count) for one stock frame"""
    import math
    im, (L, T) = NA.stock_frames(pid)[(z, k)]
    src = im.load()
    out = im.copy()
    dst = out.load()
    W, H = im.size

    def lane(xx, y):
        u, v = NA.unproject(z, xx + 0.5 - L, y + 0.5 - T)
        return (1.0 - u) * 256.0, v * 256.0

    def at(x, zl):
        u, v = 1.0 - x / 256.0, zl / 256.0
        X, Y = NA.project(z, u, v)
        X, Y = int(X + L), int(Y + T)
        if 0 <= X < W and 0 <= Y < H:
            return src[X, Y]
        return (0, 0, 0, 0)

    def on_ground(q):                                      # tree sprites unproject off the cell
        return -6.0 <= q[0] <= 262.0 and -6.0 <= q[1] <= 262.0

    core = [q for q in (lane(xx, y) for y in range(H) for xx in range(W) if strong_yellow(src[xx, y])) if on_ground(q)]
    if len(core) < 2:
        # no visible line (zoom 0 / 1): warm specks on the carriageway become asphalt-neutral by leaving them
        return out, (L, T), 0
    # straight when the paint lies within a few lane units of its principal axis, else a circular arc
    n0 = float(len(core))
    mx, mz = sum(p[0] for p in core) / n0, sum(p[1] for p in core) / n0
    sxx = sum((p[0] - mx) ** 2 for p in core)
    szz = sum((p[1] - mz) ** 2 for p in core)
    sxz = sum((p[0] - mx) * (p[1] - mz) for p in core)
    ang = 0.5 * math.atan2(2.0 * sxz, sxx - szz)
    ux, uz = math.cos(ang), math.sin(ang)
    resid = max(abs(-(p[0] - mx) * uz + (p[1] - mz) * ux) for p in core)
    circ = fit_circle(core) if (resid > 12.0 and len(core) >= 8) else None
    if circ is None:                                       # straight: along / across the principal axis
        xs, zs = [p[0] for p in core], [p[1] for p in core]
        along_x = (max(xs) - min(xs)) >= (max(zs) - min(zs))
        geo = lambda lx, lz: ((lx, lz) if along_x else (lz, lx))                  # noqa: E731
        back = lambda a_, c_: ((a_, c_) if along_x else (c_, a_))                 # noqa: E731
    else:                                                  # an arc: along = arc length, cross = radius
        cx, cz, R = circ
        geo = lambda lx, lz: (R * math.atan2(lz - cz, lx - cx), math.hypot(lx - cx, lz - cz))   # noqa: E731
        back = lambda a_, c_: (cx + c_ * math.cos(a_ / R), cz + c_ * math.sin(a_ / R))         # noqa: E731
    crs = sorted(geo(*p)[1] for p in core)
    lo, hi = crs[0], crs[-1]
    c0 = crs[len(crs) // 2]
    margin = 3.0
    n = 0
    for y in range(H):
        for xx in range(W):
            c = src[xx, y]
            if not warm(c):
                continue
            lx, lz = lane(xx, y)
            if not on_ground((lx, lz)):
                continue
            along, cr = geo(lx, lz)
            if not (lo - margin <= cr <= hi + margin):
                continue
            n += 1
            if z >= LL.MIN_ZOOM and LL.dash_on(along / 256.0):
                dst[xx, y] = LL.white(z, lx / 256.0, lz / 256.0)
                continue
            edge, sign = (lo, -1.0) if cr <= c0 else (hi, 1.0)
            fill = None
            for extra in (2.0, 4.0, 6.0, 9.0, 13.0, 18.0):
                q = back(along, edge + sign * (abs(cr - edge) + extra))
                cc = at(*q)
                if lane_grey(cc):
                    fill = cc
                    break
            if fill is None:                               # the nearest lane pixel on the same screen row
                for dx in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6):
                    if 0 <= xx + dx < W and lane_grey(src[xx + dx, y]):
                        fill = src[xx + dx, y]
                        break
            dst[xx, y] = fill if fill is not None else c
    # line ends at the cell border that the footprint missed (a handful per frame): asphalt from the row
    for y in range(H):
        for xx in range(W):
            if strong_yellow(dst[xx, y]) and on_ground(lane(xx, y)):
                for dx in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6):
                    if 0 <= xx + dx < W and lane_grey(src[xx + dx, y]):
                        dst[xx, y] = src[xx + dx, y]
                        n += 1
                        break
    return out, (L, T), n


def cmd_build(a):
    report = {}
    for pid in PIECES:
        d = os.path.join(a.pack, "art", str(pid))
        os.makedirs(d, exist_ok=True)
        anchors, n = {}, 0
        for z in range(NA.ZOOMS):
            for k in range(NA.ROTS):
                im, anc, ny = frame(pid, z, k)
                name = NA.frame_name(z, k)
                im.save(os.path.join(d, name))
                anchors[name] = list(anc)
                n += ny
        anchors["_"] = "avenue_markings.py build: %d with white dashed lanes" % pid
        json.dump(anchors, open(os.path.join(d, "anchors.json"), "w"), indent=1)
        report[pid] = n
        print("built %d (%d yellow pixels converted)" % (pid, n))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("pack")
    a = ap.parse_args(argv)
    {"build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
