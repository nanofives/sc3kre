#!/usr/bin/env python3
r"""hwcars_tracks_an.py - read hwcars_tracks.py output against a piece grid (hwcars_grid.py): what each car did.

  py -3.12 hwcars_tracks_an.py TRACKS.json GRID.json [--pieces 21100-21699] [--cars 20] [--out REPORT.json]

Per car: the pieces it drove (consecutive cells collapsed, id.state), and flags:
  JUMP   two samples < 150 ms apart more than 0.6 cell apart
  STOP   3 s or more moving under 0.05 cell
  UTURN  heading reverses (dot < -0.8) within 1.5 cells of travel
  GONE   removed (Shutdown) more than 2 cells inside the box (not at its edge)
  NEW    first seen more than 2 cells inside the box after the first second
Per cell census: travel directions seen (E = +x, W = -x, S = +z, N = -z), so a carriageway cell with both E and W
cars has a car driving against its lanes.
"""
import argparse, json, math, collections

ap = argparse.ArgumentParser()
ap.add_argument("tracks"); ap.add_argument("grid")
ap.add_argument("--pieces", default="21100-21699"); ap.add_argument("--cars", type=int, default=30)
ap.add_argument("--out")
a = ap.parse_args()
T = json.load(open(a.tracks)); G = json.load(open(a.grid))
lo, hi = map(int, a.pieces.split("-"))
x0, z0, x1, z1 = T["box"]


def piece(cx, cz):
    p = G.get("%d,%d" % (cx, cz))
    return "%d.%d" % tuple(p) if p else "-"


def inner(x, z, m=2):
    return x0 + m <= x / 256.0 <= x1 + 1 - m and z0 + m <= z / 256.0 <= z1 + 1 - m


census = collections.defaultdict(collections.Counter)
rep = []
for k, s in T["cars"].items():
    if s[0][4] != 0:
        continue
    flags = []
    cells = []
    for (t, x, y, z, c, v) in s:
        cc = (x >> 8, z >> 8)
        if not cells or cells[-1][0] != cc:
            cells.append([cc, t])
    for i in range(1, len(s)):
        dt = s[i][0] - s[i - 1][0]
        d = math.hypot(s[i][1] - s[i - 1][1], s[i][3] - s[i - 1][3]) / 256.0
        if dt < 150 and d > 0.6:
            flags.append(("JUMP", s[i - 1][0], (s[i - 1][1] >> 8, s[i - 1][3] >> 8), (s[i][1] >> 8, s[i][3] >> 8), round(d, 2)))
    # stops
    j = 0
    for i in range(len(s)):
        while s[i][0] - s[j][0] > 3000:
            j += 1
        if s[i][0] - s[j][0] >= 2900:
            d = math.hypot(s[i][1] - s[j][1], s[i][3] - s[j][3]) / 256.0
            if d < 0.05:
                flags.append(("STOP", s[j][0], (s[j][1] >> 8, s[j][3] >> 8)))
                j = i
    # headings every 0.3 cell of travel
    pts = [s[0]]
    for p in s[1:]:
        if math.hypot(p[1] - pts[-1][1], p[3] - pts[-1][3]) >= 77:
            pts.append(p)
    hd = []
    for i in range(1, len(pts)):
        dx, dz = pts[i][1] - pts[i - 1][1], pts[i][3] - pts[i - 1][3]
        n = math.hypot(dx, dz)
        hd.append((dx / n, dz / n, pts[i]))
        cc = (pts[i][1] >> 8, pts[i][3] >> 8)
        if abs(dx) > abs(dz) * 2:
            census[cc]["E" if dx > 0 else "W"] += 1
        elif abs(dz) > abs(dx) * 2:
            census[cc]["S" if dz > 0 else "N"] += 1
    for i in range(len(hd)):
        for j2 in range(i + 1, min(i + 6, len(hd))):
            if hd[i][0] * hd[j2][0] + hd[i][1] * hd[j2][1] < -0.8:
                flags.append(("UTURN", hd[j2][2][0], (hd[j2][2][1] >> 8, hd[j2][2][3] >> 8)))
                break
    # dedupe UTURN runs
    seen = set(); f2 = []
    for f in flags:
        key = (f[0], f[2])
        if key in seen:
            continue
        seen.add(key); f2.append(f)
    flags = f2
    last = s[-1]
    if k in T["ends"] and inner(last[1], last[3]):
        flags.append(("GONE", T["ends"][k], (last[1] >> 8, last[3] >> 8), piece(last[1] >> 8, last[3] >> 8)))
    if s[0][0] > 1000 and inner(s[0][1], s[0][3]):
        flags.append(("NEW", s[0][0], (s[0][1] >> 8, s[0][3] >> 8), piece(s[0][1] >> 8, s[0][3] >> 8)))
    path = []
    for cc, t in cells:
        p = piece(*cc)
        if not path or path[-1][0] != p:
            path.append([p, cc, t])
    new = any(lo <= int(p[0].split(".")[0]) <= hi for p in path if p[0] != "-")
    rep.append({"car": k, "t": [s[0][0], s[-1][0]], "new_pieces": new, "path": path, "flags": flags})

rep.sort(key=lambda r: (not r["new_pieces"], r["t"][0]))
print("cars", len(rep), "on new pieces", sum(r["new_pieces"] for r in rep))
fl = collections.Counter(f[0] for r in rep for f in r["flags"])
print("flags", dict(fl))
for r in rep[:a.cars]:
    print("--- car %s t %d..%d ms new=%s" % (r["car"], r["t"][0], r["t"][1], r["new_pieces"]))
    print("    path:", " > ".join("%s@%d,%d" % (p[0], p[1][0], p[1][1]) for p in r["path"]))
    for f in r["flags"]:
        print("    ", f)
both = {c: v for c, v in census.items() if (v["E"] and v["W"]) or (v["N"] and v["S"])}
print("cells with opposite directions:", len(both))
for c, v in sorted(both.items()):
    print("   ", c, piece(*c), dict(v))
if a.out:
    json.dump({"cars": rep, "census": {"%d,%d" % c: dict(v) for c, v in census.items()}}, open(a.out, "w"), indent=1)
