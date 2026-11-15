#!/usr/bin/env python3
r"""bvdiag_build.py - the boulevard_diagonal package (task orthfix, 2026-11-15, xsect 39; owner "Yes, all three" for the
mockups in verify/orthfix/owner_shots/mockdiag_options.png): the OPENING box where a diagonal avenue leaves a straight
boulevard through one side while the boulevard runs on. sc3netmod_bv.c places it (table line `bvo`).

The box = the avenue band's 9 cells in the boulevard's three rows. Art and lanes come from one world scene per
orientation, the mockup's (diagave_paint.Crossing of the diagonal avenue and the boulevard, the avenue stopped at the
boulevard's far edge):

  A  boulevard along x on rows 0..2, the avenue (axis 0, p = x - z, cells p 0..2) leaving south going +x+z;
     box cell (k, j) = row k, j-th band cell from the west: (k + j, k).                     ids 22470..22478 (k*3 + j)
  B  the mirror: the avenue (axis 1, q = x + z, cells q 6..8) leaving south going -x+z; box cell (k, j) = (6 - k + j,
     k).                                                                                      ids 22479..22487
Every other orientation is one of these turned (sc3netmod_bv.c: a box on the boulevard's -w side is the +w box turned
half a circle, cell (k, j) -> (2 - k, 2 - j)).

Lanes (right-hand, as bvlanes / avdiag): the boulevard's 3 + 3 lanes straight on (rows at 80 / 175 and the middle row's
14 / 241); the avenue's 2 + 2 lanes (the lines DAV's 20500 / 20505 draw: 80 / 175 on every border they cross); turns by
box_lanes' rule: a boulevard direction turns into the avenue from its two inner (left turn) or two outer (right turn)
lanes, the avenue's two lanes turn both ways (it has no straight on). A turn is a straight line, a circular fillet that
stays inside the box, a straight line. Every lane is cut per box cell (bvlanes.clip_cell); curves new to the game get
shapes 29000..29119 (orchestrator grant 2026-11-15).

  py -3.12 -m netmod.bvdiag_build build PACK [--no-art] [--zooms 0,1,2,3,4]
  py -3.12 -m netmod.bvdiag_build sheet OUT.png          top-down lanes of both boxes (check picture)
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from netmod import bvlanes as BL          # noqa: E402
from netmod import boulevard_paint as BP  # noqa: E402
from netmod import diagave_paint as D     # noqa: E402

U = 255.0
IDS = {"A": list(range(22470, 22479)), "B": list(range(22479, 22488))}
SHAPE0, SHAPE1 = 29000, 29119
C = {"A": 0, "B": 7}                      # band offset of the avenue element (A: p in [0, 2); B: q in [7, 9))
S2 = math.sqrt(2.0)


class BoulevardEl:
    """The boulevard as a diagave_paint.Crossing element: rows m, m + 1, m + 2 along x (as verify/orthfix/mockdiag.py)."""

    kind = "boulevard"
    width = 3.0
    direction = (1.0, 0.0)
    normal = (0.0, 1.0)

    def __init__(self, m=0):
        self.m = m
        self.bv = BP.Boulevard()

    def across(self, wx, wz):
        return wz - self.m

    def colour(self, z, r, wx, wz):
        t = wz - self.m
        if not (0.0 <= t < 3.0):
            return D.CLEAR
        return self.bv.carriageway(z, r, (wx % 1.0) * 256.0, wx, t * 256.0)

    own = colour

    def median(self, z, r, wx, wz):
        t = (wz - self.m) * 256.0
        if not (256.0 <= t < 512.0):
            return None
        c = self.colour(z, r, wx, wz)
        return c if D._grassy(c) else None

    def fill(self, z, r, wx, wz):
        return BP.s29(z, r, (wx % 1.0) * 256.0, BP.fold((wz - self.m) * 256.0, BP.LANE_S))

    def sidewalk(self, z, r):
        return BP.CURB / 256.0, BP.CURB / 256.0

    def cells(self):
        return lambda X, Z: Z in (self.m, self.m + 1, self.m + 2)


def scene(ch):
    da = D.Placed(D.DiagEl(C[ch]), 0 if ch == "A" else 1)
    return D.Crossing([da, D.Placed(BoulevardEl(0))], stem=(0, 0))   # the avenue stops at the boulevard's N edge


def box_cells(ch):
    """[(X, Z)] in piece order k * 3 + j"""
    if ch == "A":
        return [(k + j, k) for k in range(3) for j in range(3)]
    return [(6 - k + j, k) for k in range(3) for j in range(3)]


def in_box(ch, x, z, eps=1e-6):
    X, Z = math.floor(x), math.floor(z)
    return (X, Z) in set(box_cells(ch)) and eps <= z <= 3 - eps


# ------------------------------------------------------------------------------------------------ lanes
class Line:
    def __init__(self, p, d):
        n = math.hypot(*d)
        self.p, self.d = p, (d[0] / n, d[1] / n)


def bv_lines():
    """{'E': [outer..inner], 'W': [...]}: eastbound lanes leave by the box's E side, westbound by its W side"""
    return {"E": [Line((0.0, z), (1, 0)) for z in BL.PX], "W": [Line((0.0, z), (-1, 0)) for z in BL.MX]}


def da_lines(ch):
    """('out' leaving the box south, 'in' coming from the south), each [outer, inner]"""
    c = C[ch]
    o, i = 175.0 / U, 80.0 / U
    if ch == "A":       # p = x - z; at z = 0 the line passes x = p
        return {"out": [Line((c + 1 + o, 0.0), (1, 1)), Line((c + 1 + i, 0.0), (1, 1))],
                "in": [Line((c + i, 0.0), (-1, -1)), Line((c + o, 0.0), (-1, -1))]}
    return {"out": [Line((c + 1 + o, 0.0), (-1, 1)), Line((c + 1 + i, 0.0), (-1, 1))],      # q = x + z
            "in": [Line((c + i, 0.0), (1, -1)), Line((c + o, 0.0), (1, -1))]}


def meet(a, b):
    """intersection of two lines"""
    (x1, z1), (dx1, dz1), (x2, z2), (dx2, dz2) = a.p, a.d, b.p, b.d
    den = dx1 * dz2 - dz1 * dx2
    t = ((x2 - x1) * dz2 - (z2 - z1) * dx2) / den
    return (x1 + dx1 * t, z1 + dz1 * t)


def turn_side(h, o):
    """+1 right, -1 left (bvlanes: right_of(h) = (h_z, -h_x))"""
    r = (h[1], -h[0])
    return 1 if r[0] * o[0] + r[1] * o[1] > 0 else -1


def fillets(ch, a, b, far=12.0):
    """[(polyline, r)] along line a (arriving), a circular fillet, along line b (leaving), every radius (largest
    first) whose arc and tangent points stay inside the box"""
    I = meet(a, b)
    out = []
    cosang = max(-1.0, min(1.0, a.d[0] * b.d[0] + a.d[1] * b.d[1]))
    th = math.acos(cosang)                               # the turn angle
    side = turn_side(a.d, b.d)
    n1 = (a.d[1], -a.d[0]) if side > 0 else (-a.d[1], a.d[0])   # toward the turn's centre
    for r in [x / 100.0 for x in range(160, 9, -5)]:
        t = r * math.tan(th / 2.0)
        T1 = (I[0] - a.d[0] * t, I[1] - a.d[1] * t)
        T2 = (I[0] + b.d[0] * t, I[1] + b.d[1] * t)
        Cc = (T1[0] + n1[0] * r, T1[1] + n1[1] * r)
        a0 = math.atan2(T1[1] - Cc[1], T1[0] - Cc[0])
        a1 = math.atan2(T2[1] - Cc[1], T2[0] - Cc[0])
        da = a1 - a0
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        arc = BL.arc(Cc, r, a0, a0 + da)
        if all(in_box(ch, *p) for p in [T1, T2] + arc):
            S = (I[0] - a.d[0] * far, I[1] - a.d[1] * far)
            E = (I[0] + b.d[0] * far, I[1] + b.d[1] * far)
            out.append((BL.join(BL.seg(S, T1), arc, BL.seg(T2, E)), r))
    if not out:
        raise ValueError("%s: no fillet fits the box for a turn %s -> %s" % (ch, a.d, b.d))
    return out


def _cell_keys(ch, pts):
    """{(cell, a, b): geometry} of a polyline's cuts in the box cells (int lane units, as the spec will hold them)"""
    out = {}
    for cell in box_cells(ch):
        for lu in BL.clip_cell(pts, *cell):
            q = BL._int_cut(lu)
            out[(cell, (q[0][0], q[0][2]), (q[-1][0], q[-1][2]))] = q
    return out


def _clash(have, new):
    """two cuts of one cell with the same end points but another path (lanekit picks a curve by its end points)"""
    for k, q in new.items():
        if k in have and not BL.same_geom([list(v) for v in have[k]], [list(v) for v in q]):
            return True
    return False


def lanes(ch):
    """[(polyline, label)]; each turn takes the largest fillet with no end-point clash in a box cell"""
    B, A = bv_lines(), da_lines(ch)
    out = []
    have = {}

    def fillet(a, b):
        for pts, r in fillets(ch, a, b):
            ks = _cell_keys(ch, pts)
            if not _clash(have, ks):
                have.update(ks)
                return pts, r
        raise ValueError("%s: every fillet of a turn %s -> %s clashes with another lane" % (ch, a.d, b.d))
    for key in ("E", "W"):                                # straight on
        for ln in B[key]:
            pts = BL.seg((ln.p[0] - 12.0 * ln.d[0], ln.p[1]), (ln.p[0] + 12.0 * ln.d[0], ln.p[1]))
            have.update(_cell_keys(ch, pts))
            out.append((pts, "bv" + key))
    # the boulevard into the avenue: inner lanes on a left turn, outer on a right turn, 2 of 3 (box_lanes)
    for key in ("E", "W"):
        src = B[key]
        side = turn_side(src[0].d, A["out"][0].d)
        srcs = src[:2] if side > 0 else src[::-1][:2]
        tgts = A["out"] if side > 0 else A["out"][::-1]
        for k, s in enumerate(srcs):
            pts, r = fillet(s, tgts[min(k, len(tgts) - 1)])
            out.append((pts, "bv%s>da r%.2f" % (key, r)))
    # the avenue out of the south into the boulevard: both lanes both ways (no straight on)
    for key in ("E", "W"):
        tgt = B[key]
        side = turn_side(A["in"][0].d, tgt[0].d)
        srcs = A["in"] if side > 0 else A["in"][::-1]
        outs = tgt if side > 0 else tgt[::-1]
        for k, s in enumerate(srcs):
            pts, r = fillet(s, outs[min(k, len(outs) - 1)])
            out.append((pts, "da>bv%s r%.2f" % (key, r)))
    # the avenue's own lanes beside the turns: none go straight on (its N side is closed)
    return out


NUDGE = 12.0                              # lane units: how far a clashing node moves along its border


def cell_cuts(ch):
    """{piece: [lane-unit cuts in the piece's state-0 frame]}. Two lanes of different headings that cross one INTERNAL
    border of the box at the same point would share one node there (lanekit merges equal positions, so a car could
    step from one onto the other): the turning / diagonal lane's point moves NUDGE units along the border, in both
    cells alike (as DAV's own junction cells do, avd_21817: 75 / 92 beside 80)."""
    cells = box_cells(ch)
    cset = set(cells)
    ls = lanes(ch)
    cuts = []                                             # [cell, lane index, lu]
    for li, (pts, _lab) in enumerate(ls):
        for cell in cells:
            for lu in BL.clip_cell(pts, *cell):
                cuts.append([cell, li, [list(v) for v in lu]])

    def wpt(cell, v):
        return (round(cell[0] * U + v[0]), round(cell[1] * U + v[1]))

    def heading(lu, end):
        a, b = (lu[-2], lu[-1]) if end else (lu[0], lu[1])
        return math.atan2(b[1] - a[1], b[0] - a[0])

    def internal(cell, v):
        X, Z = cell
        nb = []
        if v[0] <= 0.5:
            nb.append((X - 1, Z))
        if v[0] >= U - 0.5:
            nb.append((X + 1, Z))
        if v[1] <= 0.5:
            nb.append((X, Z - 1))
        if v[1] >= U - 0.5:
            nb.append((X, Z + 1))
        return len(nb) == 1 and nb[0] in cset
    groups = {}
    for ci, (cell, li, lu) in enumerate(cuts):
        for end in (0, 1):
            v = lu[-1] if end else lu[0]
            if internal(cell, v):
                groups.setdefault(wpt(cell, v), []).append((ci, end, li, heading(lu, end)))
    moved = {}
    for key, mem in groups.items():
        lanes_here = {}
        for ci, end, li, h in mem:
            lanes_here.setdefault(li, h)
        hs = list(lanes_here.items())
        keep = [li for li, h in hs if not ("<" in ls[li][1] or ">" in ls[li][1])] or [hs[0][0]]
        h0 = lanes_here[keep[0]]
        k = 1
        for li, h in hs:
            d = abs((h - h0 + math.pi) % (2 * math.pi) - math.pi)
            if li in keep or d < math.radians(20):
                continue
            moved[(key, li)] = NUDGE * k
            k = -k if k > 0 else -k + 1
    for ci, (cell, li, lu) in enumerate(cuts):
        for end in (0, 1):
            v = lu[-1] if end else lu[0]
            key = wpt(cell, v)
            if (key, li) not in moved:
                continue
            dlt = moved[(key, li)]
            if v[0] <= 0.5 or v[0] >= U - 0.5:            # on a vertical border: move along z
                v[1] = min(U - BL.CORNER, max(BL.CORNER, v[1] + dlt))
            else:
                v[0] = min(U - BL.CORNER, max(BL.CORNER, v[0] + dlt))
    out = {pid: [] for pid in IDS[ch]}
    for cell, li, lu in cuts:
        out[IDS[ch][cells.index(cell)]].append([tuple(v) for v in lu])
    return out


def _pick(cv, lang, a, b, own):
    """the curve lanekit.compile_spec takes for a lane a -> b: the spec's own state-0 shapes first, then their turned
    copies, then the game's (and other packages') -> (key, pts) or None"""
    mine = cv.lang_curves(lang, own)
    ownk = {x * 256 + r for x in own for r in range(4)}
    hits = []
    for k, c in cv.lib[lang].items():
        if (c["pts"][0][0], c["pts"][0][2]) == a and (c["pts"][-1][0], c["pts"][-1][2]) == b and k not in mine:
            hits.append((k, [list(v) for v in c["pts"]]))
    for k, (pts, _is_own) in mine.items():
        if (pts[0][0], pts[0][2]) == a and (pts[-1][0], pts[-1][2]) == b:
            hits.append((k, pts))
    hits.sort(key=lambda h: (h[0] not in ownk or h[0] % 256 != 0, h[0] not in ownk, h[0]))
    return hits[0] if hits else None


def _new_shape(cv, pts):
    """a fresh shape at state 0 for exactly these points (not a turned copy of another one)"""
    if cv.next > SHAPE1:
        raise ValueError("bvdiag: out of curve shapes (%d..%d)" % (SHAPE0, SHAPE1))
    x = cv.next
    cv.next += 1
    cv.new[x] = [list(v) for v in pts]
    return x


def specs(root=None):
    from netmod.diagave import _describe
    BL.SHAPE0, BL.SHAPE1 = SHAPE0, SHAPE1
    cv = BL.Curves(root)
    peds = _describe(43, 0)["pedestrian"]
    out, rep = {}, []
    for ch in ("A", "B"):
        for pid, cuts in sorted(cell_cuts(ch).items()):
            plan = []
            seen = set()
            for lu in cuts:
                pts = [list(v) for v in BL._int_cut(lu)]
                a, b = (pts[0][0], pts[0][2]), (pts[-1][0], pts[-1][2])
                key = (a, b, tuple(tuple(v) for v in pts))
                if key in seen:
                    continue
                seen.add(key)
                plan.append((pts, a, b))
            own = set()
            for _round in range(6):
                bad = 0
                for pts, a, b in plan:
                    for lang in ("en", "uk"):
                        h = _pick(cv, lang, a, b, own)
                        if h and BL.same_geom(h[1], pts):
                            continue
                        bad += 1
                        own.add(_new_shape(cv, pts if lang == "en" else pts[::-1]))
                if not bad:
                    break
            else:
                raise ValueError("piece %d: curve picks do not settle" % pid)
            used = set(own)                                  # + the non-stock shapes the picks land on (avcore's)
            for pts, a, b in plan:
                for lang in ("en", "uk"):
                    h = _pick(cv, lang, a, b, own)
                    if h and h[0] // 256 in cv.new:
                        used.add(h[0] // 256)
            own = used
            lanes_, exits = [], set()
            for pts, a, b in plan:
                ln = {"from": [a[0], a[1]], "to": [b[0], b[1]]}
                if b in exits:
                    ln["exit"] = False
                exits.add(b)
                lanes_.append(ln)
            out[pid] = {"piece": pid, "states": [0, 1, 2, 3], "flag": 1, "mirror_uk": False,
                        "vehicle": {"class": "car", "speed": 64000, "lanes": lanes_},
                        "pedestrian": json.loads(json.dumps(peds)),
                        "connects": {"road": BL._turns(plan)},
                        "curves": [{"shape": s, "pts": cv.new[s]} for s in sorted(own)],
                        "_": "bvdiag_build.py: opening box %s cell %d (row %d, band cell %d), lanes cut from the world "
                             "scene, right-hand, no path keys" % (ch, IDS[ch].index(pid), IDS[ch].index(pid) // 3,
                                                                  IDS[ch].index(pid) % 3)}
            rep.append("%d (%s %d): %d lanes, %d own curve(s)" % (pid, ch, IDS[ch].index(pid), len(lanes_), len(own)))
    return out, cv, rep


def table_lines():
    return ["bvo %d %s" % (k, " ".join(str(p) for p in IDS[ch])) for k, ch in enumerate(("A", "B"))]


def cmd_build(a):
    pack = a.pack
    os.makedirs(pack, exist_ok=True)
    sp, cv, rep = specs(a.root)
    print("\n".join(rep))
    used = sorted(s for s in cv.new if SHAPE0 <= s <= SHAPE1)
    print("curve shapes %d (%s..%s)" % (len(used), used[0] if used else "-", used[-1] if used else "-"))
    variants, lanes_ = [], []
    for pid in sorted(sp):
        fn = "bvo_%d.lanes.json" % pid
        json.dump(sp[pid], open(os.path.join(pack, fn), "w", newline="\n"), indent=1)
        lanes_.append({"piece": pid, "spec": fn})
        variants.append({"id": pid, "base": 43, "network": "ROAD",
                         "name": {"*": "Boulevard junction", "ENGLISH": "Cruce de bulevar"},
                         "art": {"from": 43, "png_dir": "art/%d" % pid}, "trblkatt": "none"})
    bvman = json.load(open(os.path.join(HERE, "examples", "boulevard", "manifest.json")))
    man = {"netpack": 1, "name": "boulevard_diagonal", "version": "0.1.0", "author": "netmod (task orthfix)",
           "description": "Boulevard x diagonal avenue OPENING box (task orthfix, xsect 39): where a diagonal avenue leaves "
                          "a boulevard through one side and the boulevard runs on, sc3netmod's BV block writes the "
                          "avenue band's nine cells in the boulevard's rows as one paved box (crosswalks where the "
                          "avenue leaves and across the boulevard on both sides, the boulevard's far kerb runs on). "
                          "22470..22478 the avenue going +x+z from the boulevard's +w side, 22479..22487 the mirror. "
                          "Saved as 43. Needs boulevard, diagonal_avenue. Build: `py -3.12 -m netmod.bvdiag_build build "
                          ".` in re/tools (art from the game's frames, not shipped).",
           "game": bvman["game"], "variants": variants, "lanes": lanes_,
           "boulevard_slope_lines": table_lines()}
    json.dump(man, open(os.path.join(pack, "manifest.json"), "w", newline="\n"), indent=1)
    print("manifest: %d variants, lines %s" % (len(variants), table_lines()))
    if a.no_art:
        return 0
    from netmod import netart as NA
    zooms = [int(v) for v in a.zooms.split(",")] if a.zooms else list(range(NA.ZOOMS))
    for ch in ("A", "B"):
        sc = scene(ch)
        for pid, cell in zip(IDS[ch], box_cells(ch)):
            d = os.path.join(pack, "art", str(pid))
            anc = D.paint_cell(sc, cell, d, zooms=zooms)
            anc["_"] = "bvdiag_build.py: opening box %s, cell %s" % (ch, cell)
            json.dump(anc, open(os.path.join(d, "anchors.json"), "w"), indent=1)
            print("art %d (%s %s)" % (pid, ch, cell), flush=True)
    return 0


def cmd_sheet(a):
    from PIL import Image, ImageDraw
    px, W = 70, 2
    img = Image.new("RGB", (2 * 11 * px, 11 * px), (250, 250, 250))
    d = ImageDraw.Draw(img)
    for n, ch in enumerate(("A", "B")):
        ox, oz = n * 11 * px + 2 * px, 3 * px
        for X in range(-2, 9):
            for Z in range(-2, 8):
                col = (255, 230, 180) if (X, Z) in box_cells(ch) else (235, 235, 235)
                d.rectangle([ox + X * px, oz + Z * px, ox + (X + 1) * px - 1, oz + (Z + 1) * px - 1], fill=col,
                            outline=(200, 200, 200))
        for pts, lab in lanes(ch):
            q = [(ox + x * px, oz + z * px) for x, z in pts]
            colr = (30, 30, 200) if lab.startswith("bv") and ">" not in lab else (200, 30, 30)
            d.line(q, fill=colr, width=W)
            d.ellipse([q[-1][0] - 3, q[-1][1] - 3, q[-1][0] + 3, q[-1][1] + 3], fill=colr)
        d.text((ox, 5), "box %s (cells orange; dot = lane end)" % ch, fill=(0, 0, 0))
    img.save(a.out)
    print(a.out)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("build")
    s.add_argument("pack")
    s.add_argument("--no-art", action="store_true")
    s.add_argument("--zooms")
    s.add_argument("--root")
    s = sub.add_parser("sheet")
    s.add_argument("out")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "sheet": cmd_sheet}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
