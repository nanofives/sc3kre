#!/usr/bin/env python3
r"""diagave.py - diagonal avenues (task diagave phase 1, 2026-10-17): the band rule, its art, offline checks.

A diagonal avenue is two diagonal road drags laid side by side. The stock tiler turns that into a ladder of 4-ways
(verify/diagave/RESULTS.md 2); sc3netmod's DAV block applies the rule below after every road retile instead, and this
file is its offline twin plus the art builder.

The rule (down-right axis; the other axis is the same with x mirrored):
  band row  z, left a: ROAD cells (a..a+3, z), no ROAD at (a-1, z) and (a+4, z)
  linked    row z (left a) and row z+1 (left a+1) both band rows
  band      a maximal chain of linked rows, at least MIN_ROWS rows, plus its ends: the rows above (z_top-k, left
            a_top-k) and below (z_bot+k, left a_bot+k) while they hold ROAD at any of their d 0..3 cells
  d         x - (row left); staircase A = d 0,1, staircase B = d 2,3
  isolated  no ROAD cell outside the band touches a band cell (8 neighbours); else the band is left to the stock tiler
            (phase 1: junctions at the ends are later work)
  piece     each cell gets what the stock tiler gives a LONE staircase of 3+ steps, by the cell's mask inside its own
            staircase (LONE, measured with tiler.py, verify/diagave/RESULTS.md); a cell at d 1 or 2 whose row or a row
            next to it holds the other staircase takes the INNER variant of that piece (35 / 18004 / 1999): the half
            of the cell away from its road is the median.

  py -3 diagave.py art OUT_DIR [--ids 20500,20501,20502]      png dirs (z*_r*.png + anchors.json) of the 3 inner pieces
  py -3 diagave.py plan SAVE [--rect x0,z0,x1,z1]             bands + wanted pieces on a save (read-only)
  py -3 diagave.py scan [SAVE ...]                            bands per save (default: the shipped Cities)
  py -3 diagave.py preview OUT.png ART_DIR [--rows 6] [--zoom 4] [--axis 0|1] [--rot 0..3]
                                                              a seeded band (game drag footprint), tiled + converted
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

MIN_ROWS = 3
INNER = {35: 20500, 18004: 20501, 1999: 20502}          # stock piece -> its inner (median-side) variant
DIRS = [(-1, 0), (0, -1), (1, 0), (0, 1), (-1, -1), (1, -1), (1, 1), (-1, 1)]   # mask bit k (tiler.py:41)
# lone staircase (3+ steps): own-footprint mask -> (piece, state); tiler.py on the stock rules, both axes, both phases
LONE = {17: (18004, 2), 18: (1999, 2), 22: (35, 2), 25: (35, 0), 34: (18004, 3), 35: (35, 1), 36: (1999, 3),
        44: (35, 3), 68: (18004, 0), 70: (35, 2), 72: (1999, 0), 73: (35, 0), 86: (35, 2), 89: (35, 0),
        129: (1999, 1), 131: (35, 1), 136: (18004, 1), 140: (35, 3), 163: (35, 1), 172: (35, 3)}


# ------------------------------------------------------------------------------------------------ the rule
def bands(road):
    """road: set of (x, z) ROAD cells. -> list of bands {axis, rows: [(z, a)], cells: {(x, z): (staircase, d)},
    ok, why}. axis 0: rows x = a..a+3 shifting +1 per row (down-right); axis 1: the mirror (x -> -x)."""
    out = []
    for axis in (0, 1):
        R = road if axis == 0 else {(-x, z) for (x, z) in road}
        rows = {}
        for (x, z) in R:
            if (x - 1, z) not in R and all((x + k, z) in R for k in range(4)) and (x + 4, z) not in R:
                rows.setdefault(z, set()).add(x)
        seen = set()
        for z in sorted(rows):
            for a in sorted(rows[z]):
                if (z, a) in seen or a - 1 in rows.get(z - 1, ()):
                    continue
                chain = [(z, a)]
                while chain[-1][1] + 1 in rows.get(chain[-1][0] + 1, ()):
                    chain.append((chain[-1][0] + 1, chain[-1][1] + 1))
                seen.update(chain)
                if len(chain) < MIN_ROWS:
                    continue
                cells = {}
                for (zz, aa) in chain:
                    for d in range(4):
                        cells[(aa + d, zz)] = ("A" if d < 2 else "B", d)
                for (z0, a0), step in ((chain[0], -1), (chain[-1], 1)):
                    k = 1
                    while True:
                        got = [d for d in range(4) if (a0 + step * k + d, z0 + step * k) in R]
                        if not got:
                            break
                        for d in got:
                            cells[(a0 + step * k + d, z0 + step * k)] = ("A" if d < 2 else "B", d)
                        k += 1
                why = ""
                for (x, z2) in cells:
                    for dx, dz in DIRS:
                        q = (x + dx, z2 + dz)
                        if q in R and q not in cells:
                            why = "touches road at (%d,%d)" % ((-q[0] if axis else q[0]), q[1])
                            break
                    if why:
                        break
                if axis == 1:
                    cells = {(-x, z2): v for (x, z2), v in cells.items()}
                    chain = [(zz, -aa) for (zz, aa) in chain]
                out.append({"axis": axis, "rows": chain, "cells": cells, "ok": not why, "why": why})
    return out


def wanted(band):
    """-> {(x, z): (piece id, state)} for one isolated band, or None (not isolated, or a cell's own mask is not a
    lone-staircase mask)."""
    if not band["ok"]:
        return None
    own, rows_of = {}, {}
    for c, (st, d) in band["cells"].items():
        own.setdefault(st, set()).add(c)
        rows_of.setdefault(st, set()).add(c[1])
    out = {}
    for c, (st, d) in band["cells"].items():
        m = sum(1 << k for k, (dx, dz) in enumerate(DIRS) if (c[0] + dx, c[1] + dz) in own[st])
        if m not in LONE:
            band["why"] = "own mask %d at %s not a lone-staircase mask" % (m, c)
            return None
        pid, s = LONE[m]
        other = rows_of["B" if st == "A" else "A"]
        inner = d in (1, 2) and any(c[1] + k in other for k in (-1, 0, 1))
        out[c] = (INNER[pid] if inner else pid, s)
    return out


# ------------------------------------------------------------------------------------------------ art
def tree_sprites(z):
    """The two trees of avenue 11204 (slot 0) at zoom z, cut above the ground diamond's upper edges.
    -> [(RGBA image, (bx, by) = trunk base inside the image)]"""
    from PIL import Image
    from netmod import netart
    im, (L, T) = netart.stock_frames(11204)[(z, 0)]
    W = netart.TILE_W[z]
    px = im.load()
    keep = Image.new("RGBA", im.size, (0, 0, 0, 0))
    kp = keep.load()
    for y in range(im.height):
        for x in range(im.width):
            gx = x - (0 - L)            # ground x from the left vertex
            if gx < 0 or gx > W:
                continue
            top = T - (gx / 2.0 if gx <= W / 2 else (W - gx) / 2.0)
            if y < top and px[x, y][3] > 0:
                kp[x, y] = px[x, y]
    # 8-connected components of the kept pixels
    seen, comps = set(), []
    for y in range(im.height):
        for x in range(im.width):
            if kp[x, y][3] == 0 or (x, y) in seen:
                continue
            stack, comp = [(x, y)], []
            seen.add((x, y))
            while stack:
                p = stack.pop()
                comp.append(p)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        q = (p[0] + dx, p[1] + dy)
                        if 0 <= q[0] < im.width and 0 <= q[1] < im.height and q not in seen and kp[q][3]:
                            seen.add(q)
                            stack.append(q)
            if len(comp) >= max(3, 2 ** z):
                comps.append(comp)
    out = []
    for comp in sorted(comps, key=lambda c: min(p[0] for p in c)):
        xs = [p[0] for p in comp]
        ys = [p[1] for p in comp]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        spr = Image.new("RGBA", (x1 - x0 + 1, y1 - y0 + 1), (0, 0, 0, 0))
        sp = spr.load()
        for (x, y) in comp:
            sp[x - x0, y - y0] = px[x, y]
        base = max(comp, key=lambda p: (p[1], -abs(p[0] - (x0 + x1) / 2.0)))
        out.append((spr, (base[0] - x0, base[1] - y0 + 1)))
    return out


def inner_frames(pid, z, slot, trees, tree_pick):
    """Stock piece `pid`'s frame (road half / cap quarter) on a full-tile canvas, a tree on the other half's centre
    line. -> (RGBA image, (L, T))"""
    from PIL import Image
    from netmod import netart
    im, (L, T) = netart.stock_frames(pid)[(z, slot)]
    W = netart.TILE_W[z]
    H = W // 2
    up = max([t.height for t, _ in trees] + [0]) + 2
    Tc = up + H // 2 - 1
    canvas = Image.new("RGBA", (W, up + H), (0, 0, 0, 0))
    canvas.alpha_composite(im, (0 - L, Tc - T))
    a = canvas.getchannel("A").load()
    xs, ys = [], []
    for y in range(canvas.height):
        for x in range(W):
            if a[x, y]:
                xs.append(x)
                ys.append(y)
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    if slot % 2 == 0:                                   # strip vertical on screen: median = the other W/E half
        bx, by = (W // 4 if cx > W / 2 else 3 * W // 4), Tc
    else:                                               # strip horizontal: median = the other N/S half
        bx, by = W // 2, (Tc - H // 4 if cy > Tc else Tc + H // 4) + H // 8   # nearer the front edge: less of the far road hidden
    if tree_pick is not None and trees:
        spr, (tx, ty) = trees[tree_pick % len(trees)]
        canvas.alpha_composite(spr, (bx - tx, by - ty)) if bx - tx >= 0 and bx - tx + spr.width <= W else \
            _paste_clipped(canvas, spr, bx - tx, by - ty)
    return canvas, (0, Tc)


def _paste_clipped(canvas, spr, x, y):
    from PIL import Image
    tmp = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    tmp.paste(spr, (x, y))
    canvas.alpha_composite(tmp)


def cmd_art(a):
    from netmod import netart
    ids = [int(t) for t in a.ids.split(",")]
    for pid, vid in zip((35, 18004, 1999), ids):
        d = os.path.join(a.out, str(vid))
        os.makedirs(d, exist_ok=True)
        anchors = {"_": "diagave.py art: stock %d frame + a tree from 11204 on the median half" % pid}
        for z in range(netart.ZOOMS):
            trees = tree_sprites(z)
            for s in range(netart.ROTS):
                # one tree per piece: the 35 inner gets tree 0 on states 0/1 (the A side) and tree 1 on 2/3 (B side);
                # the caps get none (the median ends there)
                pick = (0 if s in (0, 1) else 1) if pid == 35 else None
                im, anc = inner_frames(pid, z, s, trees, pick)
                im.save(os.path.join(d, netart.frame_name(z, s)))
                anchors[netart.frame_name(z, s)] = list(anc)
        json.dump(anchors, open(os.path.join(d, "anchors.json"), "w"), indent=1)
        print("built", d)


# ------------------------------------------------------------------------------------------------ checks
def road_cells(save):
    from netmod import tiler
    import re
    from netmod import paths
    g = paths.game_root()
    ids = {int(v) for v in re.findall(r"\d+", open(os.path.join(g, "Apps", "Res", "TilingRules",
                                                                "ROAD_GRND_Set.txt")).read())} | set(INNER.values())
    lay = tiler.City.load(save).layers["surface"]
    return lay, {c for c, p in lay.items() if p.id in ids and p.flags is None}


def cmd_scan(a):
    from netmod import paths
    saves = a.saves or sorted(glob.glob(os.path.join(paths.game_root(), "Cities", "*.sc3")))
    for s in saves:
        _lay, road = road_cells(s)
        b = bands(road)
        print("%-26s bands %d %s" % (os.path.basename(s), len(b), [(x["axis"], x["rows"][0], len(x["rows"]),
                                                                       "converts" if wanted(x) else x["why"]) for x in b]))


def cmd_plan(a):
    lay, road = road_cells(a.save)
    for b in bands(road):
        w = wanted(b)
        print("band axis %d rows %d from %s: %s" % (b["axis"], len(b["rows"]), b["rows"][0], "converts" if w else b["why"]))
        for c in sorted(b["cells"], key=lambda c: (c[1], c[0])):
            p = lay.get(c)
            print("  (%d,%d) %s d%d  now %s  want %s" % (c[0], c[1], b["cells"][c][0], b["cells"][c][1],
                                                         "%d.%d" % (p.id, p.state) if p else "-",
                                                         "%d.%d" % w[c] if w else "NO LONE MASK"))


def seeded_band(rows, axis, square=False):
    """Two drags like the 2026-10-17 game run (A from (x0,z0), B two cells along x; square: B one cell along the
    other diagonal, so both ends are cut square to the avenue), as cell sets."""
    def drag(x0, z0, n):
        cells = [(x0, z0)]
        x, z = x0, z0
        for i in range(2 * n):
            if i % 2 == 0:
                x += 1
            else:
                z += 1
            cells.append((x, z))
        return cells
    A, B = drag(0, 0, rows), (drag(2, 0, rows) if not square else drag(1, -1, rows))
    if axis == 1:
        A, B = [(-x, z) for x, z in A], [(-x, z) for x, z in B]
    return A, B


def cmd_preview(a):
    from netmod import netart
    A, B = seeded_band(a.rows, a.axis, a.square)
    road = set(A) | set(B)
    bs = bands(road)
    want = {}
    for b in bs:
        w = wanted(b)
        if w:
            want.update(w)
    cells = []
    for c in sorted(road):
        pid, s = want.get(c, (None, None))
        if pid is None:
            print("not converted:", c)
            continue
        cell = {"at": [-c[0], c[1]], "slot": s}
        if pid in INNER.values():
            cell["dir"] = os.path.join(a.art, str(pid))
        else:
            cell["piece"] = pid
        cells.append(cell)
    print("bands", [(b["axis"], len(b["rows"])) for b in bs], "cells", len(cells))
    shot = netart.preview({"cells": cells}, None, zooms=[a.zoom], rots=[a.rot])[(a.zoom, a.rot)]
    shot.convert("RGB").save(a.out)
    print(a.out, shot.size)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("art")
    s.add_argument("out")
    s.add_argument("--ids", default="%d,%d,%d" % (INNER[35], INNER[18004], INNER[1999]))
    s = sub.add_parser("scan")
    s.add_argument("saves", nargs="*")
    s = sub.add_parser("plan")
    s.add_argument("save")
    s = sub.add_parser("preview")
    s.add_argument("out")
    s.add_argument("art")
    s.add_argument("--rows", type=int, default=6)
    s.add_argument("--zoom", type=int, default=4)
    s.add_argument("--axis", type=int, default=0)
    s.add_argument("--rot", type=int, default=0)
    s.add_argument("--square", action="store_true")
    a = ap.parse_args(argv)
    {"art": cmd_art, "scan": cmd_scan, "plan": cmd_plan, "preview": cmd_preview}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
