#!/usr/bin/env python3
r"""diagave.py - diagonal avenues (task diagave, 2026-10-17): the band rule, its pieces, art and lanes, offline checks.

A diagonal avenue is two diagonal road drags JOINED side by side: the second drag one cell over, so the two
staircases share their middle diagonal. The stock tiler turns that into a ladder of 3 pieces per row (curve, 4-way,
curve: verify/diagave/RESULTS_phase1.md); sc3netmod's DAV block applies the rule below after every road retile
instead, and this file is its offline twin plus the builder of the pieces it places.

Why it works: stock diagonal 35 draws only HALF its diamond, the road strip (verify/diagave/RESULTS.md). In a band of
three cells per row the middle cell holds the inner half of BOTH roads, so it is road all over; the outer cells keep
the stock pieces. The middle cell becomes a variant whose art is the two stock halves on one tile and whose lanes are
both halves' lanes.

The rule (down-right axis; the other axis is the same with x mirrored):
  band row  z, left a: ROAD cells (a..a+2, z), no ROAD at (a-1, z) and (a+3, z)
  band      a chain of band rows, each the next row's left - 1, at least MIN_ROWS rows, plus the rows above
            (z_top-k, left a_top-k) and below (z_bot+k, left a_bot+k) while they hold ROAD at d 0..2 (the drags' ends)
  d         x - (row left). Staircase A = d 0,1 and staircase B = d 1,2 in band rows; in end rows d 0 is A, d 2 is B and
            d 1 is A, B or both, whichever keeps every cell of both staircases a lone-staircase mask (fewest "both")
  isolated  no ROAD cell outside the band touches a band cell (8 neighbours); else the band is left to the stock tiler
  piece     a cell of one staircase gets the piece the stock tiler gives a LONE staircase of 3+ steps, by its mask
            inside that staircase (LONE); a cell of both gets the MID variant of (A's piece, B's piece, state offset)

  py -3 diagave.py combos                     the MID combinations every drag footprint needs (ids are assigned here)
  py -3 diagave.py build PACK_DIR             art/<id>/ (z*_r*.png + anchors.json) and mid_<id>.lanes.json per MID variant
  py -3 diagave.py scan [SAVE ...]            bands per save (default: the shipped Cities) and whether they convert
  py -3 diagave.py plan SAVE                  bands + wanted pieces on a save (read-only)
  py -3 diagave.py preview OUT.png PACK_DIR [--rows 6] [--zoom 4] [--axis 0|1] [--rot 0..3] [--offset x|z]
"""
import argparse
import glob
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

MIN_ROWS = 3
DIRS = [(-1, 0), (0, -1), (1, 0), (0, 1), (-1, -1), (1, -1), (1, 1), (-1, 1)]   # mask bit k (tiler.py:41)
# lone staircase (3+ steps): own-footprint mask -> (piece, state); tiler.py on the stock rules, both axes, both phases
LONE = {17: (18004, 2), 18: (1999, 2), 22: (35, 2), 25: (35, 0), 34: (18004, 3), 35: (35, 1), 36: (1999, 3),
        44: (35, 3), 68: (18004, 0), 70: (35, 2), 72: (1999, 0), 73: (35, 0), 86: (35, 2), 89: (35, 0),
        129: (1999, 1), 131: (35, 1), 136: (18004, 1), 140: (35, 3), 163: (35, 1), 172: (35, 3)}
# MID variants: (A's piece, B's piece, (B state - A state) mod 4) -> id; the cell's state is A's. Filled from `combos`.
MID = {(35, 35, 2): 20500, (35, 18004, 0): 20501, (18004, 35, 0): 20502, (35, 1999, 2): 20503, (1999, 35, 2): 20504}


# ------------------------------------------------------------------------------------------------ the rule
def _mask(c, cells):
    return sum(1 << k for k, (dx, dz) in enumerate(DIRS) if (c[0] + dx, c[1] + dz) in cells)


def bands(road):
    """road: set of (x, z) ROAD cells. -> list of {axis, rows: [(z, a)], A: set, B: set, ok, why} (real coords)."""
    out = []
    for axis in (0, 1):
        R = road if axis == 0 else {(-x, z) for (x, z) in road}
        rows = {}
        for (x, z) in R:
            if (x - 1, z) not in R and all((x + k, z) in R for k in range(3)) and (x + 3, z) not in R:
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
                A, B, amb = set(), set(), []
                for (zz, aa) in chain:
                    A |= {(aa, zz), (aa + 1, zz)}
                    B |= {(aa + 1, zz), (aa + 2, zz)}
                for (z0, a0), step, pref in ((chain[0], -1, "A"), (chain[-1], 1, "B")):
                    k = 1
                    while True:
                        zr, ar = z0 + step * k, a0 + step * k
                        got = [d for d in range(3) if (ar + d, zr) in R]
                        if not got:
                            break
                        for d in got:
                            c = (ar + d, zr)
                            if d == 0:
                                A.add(c)
                            elif d == 2:
                                B.add(c)
                            else:
                                amb.append((c, pref))
                        k += 1
                cells = A | B | {c for c, _ in amb}
                why = ""
                for c in cells:
                    for dx, dz in DIRS:
                        q = (c[0] + dx, c[1] + dz)
                        if q in R and q not in cells:
                            why = "touches road at (%d,%d)" % ((-q[0] if axis else q[0]), q[1])
                    if why:
                        break
                pick = None
                if not why:
                    best = None                      # same order as sc3netmod_dav.c: cost 100 per both + 1 per other,
                    for combo in range(3 ** len(amb)):  # first lowest-cost combination (cell 0 = least digit)
                        choice = [("pref", "other", "both")[(combo // 3 ** i) % 3] for i in range(len(amb))]
                        cost = 100 * choice.count("both") + choice.count("other")
                        if best is not None and cost >= best[0]:
                            continue
                        a2, b2 = set(A), set(B)
                        for (c, pref), ch in zip(amb, choice):
                            side = pref if ch == "pref" else ("B" if pref == "A" else "A") if ch == "other" else "AB"
                            if "A" in side:
                                a2.add(c)
                            if "B" in side:
                                b2.add(c)
                        if all(_mask(c, a2) in LONE for c in a2) and all(_mask(c, b2) in LONE for c in b2):
                            best = (cost, a2, b2)
                    pick = best[1:] if best else None
                    if pick is None:
                        why = "no split into two lone staircases"
                A2, B2 = pick if pick else (A, B)
                if axis == 1:
                    A2, B2 = {(-x, z2) for x, z2 in A2}, {(-x, z2) for x, z2 in B2}
                    chain = [(zz, -aa) for (zz, aa) in chain]
                out.append({"axis": axis, "rows": chain, "A": A2, "B": B2, "ok": not why, "why": why})
    return out


def wanted(band, mids=None):
    """-> {(x, z): (piece id, state)} for one band, or None (not isolated / no valid split / a MID combo has no id)."""
    mids = MID if mids is None else mids
    if not band["ok"]:
        return None
    A, B = band["A"], band["B"]
    out = {}
    for c in A | B:
        pa = LONE.get(_mask(c, A)) if c in A else None
        pb = LONE.get(_mask(c, B)) if c in B else None
        if pa and pb:
            key = (pa[0], pb[0], (pb[1] - pa[1]) % 4)
            if key not in mids:
                band["why"] = "no MID piece for %s at %s" % (key, c)
                return None
            out[c] = (mids[key], pa[1])
        else:
            out[c] = pa or pb
    return out


def mid_combos(band):
    A, B = band["A"], band["B"]
    for c in A & B:
        pa, pb = LONE[_mask(c, A)], LONE[_mask(c, B)]
        yield (pa[0], pb[0], (pb[1] - pa[1]) % 4)


# ------------------------------------------------------------------------------------------------ footprints
def drag(x0, z0, n, sx, first):
    """The cells of a diagonal drag of n steps from (x0, z0): x by sx and z by +1, alternating, `first` first."""
    cells = [(x0, z0)]
    x, z = x0, z0
    for i in range(2 * n):
        if (i % 2 == 0) == (first == "x"):
            x += sx
        else:
            z += 1
        cells.append((x, z))
    return cells


def footprints():
    """Two joined drags in every way a player makes them: both axes, both step phases of each drag, the second drag
    one cell along x or one cell up, the same length or one step shorter / longer."""
    for sx in (1, -1):
        for fa, fb in itertools.product("xz", repeat=2):
            for ox, oz in ((sx, 0), (0, -1)):
                for m in (4, 5, 6):
                    yield (sx, fa, fb, ox, oz, m), set(drag(0, 0, 5, sx, fa)) | set(drag(ox, oz, m, sx, fb))


def cmd_combos(a):
    need, fails = {}, []
    for key, road in footprints():
        bs = bands(road)
        if not bs:
            fails.append((key, "no band"))
            continue
        for b in bs:
            if not b["ok"]:
                fails.append((key, b["why"]))
                continue
            for c in mid_combos(b):
                need[c] = need.get(c, 0) + 1
    for c, n in sorted(need.items(), key=lambda t: -t[1]):
        print("  %-22s %3d footprint(s)  id %s" % (c, n, MID.get(c, "MISSING")))
    print("footprints without a converting band: %d of %d" % (len(fails), len(list(footprints()))))
    for k, w in fails[:16]:
        print("  ", k, w)


# ------------------------------------------------------------------------------------------------ art + lanes
def mid_frame(pa, pb, delta, z, slot):
    """A's piece frame (slot) + B's piece frame (slot + delta) on one full tile. -> (RGBA, (L, T))"""
    from PIL import Image
    from netmod import netart
    W = netart.TILE_W[z]
    H = W // 2
    T = H // 2 - 1
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for pid, s in ((pa, slot), (pb, (slot + delta) % 4)):
        im, (L, Tt) = netart.stock_frames(pid)[(z, s)]
        canvas.alpha_composite(im, (0 - L, T - Tt))
    return canvas, (0, T)


def _side(p):
    return "x-" if p[0] == 0 else "x+" if p[0] == 255 else "z-" if p[1] == 0 else "z+"


def _describe(pid, state):
    import subprocess
    out = subprocess.run([sys.executable, "-m", "netmod.lanekit", "describe", str(pid), "--state", str(state)],
                         capture_output=True, text=True, cwd=os.path.dirname(HERE), check=True).stdout
    return json.loads(out)


def mid_spec(pa, pb, delta, vid):
    """Lane spec (lanekit authoring format) of a MID variant: A's piece at state 0 + B's piece at state delta, the
    state-0 record; lanekit makes states 1..3 by rotation."""
    sa, sb = _describe(pa, 0), _describe(pb, delta)
    spec = {"_": "diagave.py: lanes of %d (state 0) + %d (state %d), the two roads that share this cell" % (pa, pb, delta),
            "piece": vid, "states": [0, 1, 2, 3], "flag": sa.get("flag", 0), "alt": sa.get("alt", [0, 0, 0, 0])}
    veh = {"class": sa["vehicle"]["class"], "speed": sa["vehicle"]["speed"], "lanes": [], "exits": []}
    ped = {"walks": [], "exits": []}
    for s in (sa, sb):
        veh["lanes"] += s.get("vehicle", {}).get("lanes", [])
        veh["exits"] += [e for e in s.get("vehicle", {}).get("exits", []) if e not in veh["exits"]]
        ped["walks"] += s.get("pedestrian", {}).get("walks", [])
        ped["exits"] += [e for e in s.get("pedestrian", {}).get("exits", []) if e not in ped["exits"]]
    spec["vehicle"], spec["pedestrian"] = veh, ped
    pairs = []
    for ln in veh["lanes"]:
        p = [_side(ln["from"]), _side(ln["to"])]
        if p not in pairs:
            pairs.append(p)
    spec["connects"] = {"road": pairs}
    return spec


def cmd_build(a):
    from netmod import netart
    for (pa, pb, delta), vid in sorted(MID.items(), key=lambda t: t[1]):
        d = os.path.join(a.pack, "art", str(vid))
        os.makedirs(d, exist_ok=True)
        anchors = {"_": "diagave.py build: %d (slot) + %d (slot + %d) on one tile" % (pa, pb, delta)}
        for z in range(netart.ZOOMS):
            for s in range(netart.ROTS):
                im, anc = mid_frame(pa, pb, delta, z, s)
                im.save(os.path.join(d, netart.frame_name(z, s)))
                anchors[netart.frame_name(z, s)] = list(anc)
        json.dump(anchors, open(os.path.join(d, "anchors.json"), "w"), indent=1)
        spec = mid_spec(pa, pb, delta, vid)
        with open(os.path.join(a.pack, "mid_%d.lanes.json" % vid), "w", newline="\n") as fh:
            json.dump(spec, fh, indent=1)
        print("built %d: art %s, lanes mid_%d.lanes.json (%d vehicle lane(s), connects %s)"
              % (vid, d, vid, len(spec["vehicle"]["lanes"]), spec["connects"]["road"]))


# ------------------------------------------------------------------------------------------------ checks
def road_cells(save):
    import re
    from netmod import tiler, paths
    g = paths.game_root()
    ids = {int(v) for v in re.findall(r"\d+", open(os.path.join(g, "Apps", "Res", "TilingRules",
                                                                "ROAD_GRND_Set.txt")).read())} | set(MID.values())
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
        for c in sorted(b["A"] | b["B"], key=lambda c: (c[1], c[0])):
            p = lay.get(c)
            print("  (%d,%d) %-2s now %-8s want %s" % (c[0], c[1], ("A" if c in b["A"] else "") + ("B" if c in b["B"] else ""),
                                                      "%d.%d" % (p.id, p.state) if p else "-",
                                                      "%d.%d" % w[c] if w else "-"))


def cmd_preview(a):
    from netmod import netart
    sx = 1 if a.axis == 0 else -1
    road = set(drag(0, 0, a.rows, sx, "x")) | set(drag(sx, 0, a.rows, sx, "x") if a.offset == "x" else
                                                 drag(0, -1, a.rows, sx, "x"))
    cells = []
    for b in bands(road):
        w = wanted(b) or {}
        for c, (pid, s) in w.items():
            cell = {"at": [-c[0], c[1]], "slot": s}
            if pid in MID.values():
                cell["dir"] = os.path.join(a.pack, "art", str(pid))
            else:
                cell["piece"] = pid
            cells.append(cell)
        print("band axis %d rows %d: %s" % (b["axis"], len(b["rows"]), "converts" if w else b["why"]))
    shot = netart.preview({"cells": cells}, None, zooms=[a.zoom], rots=[a.rot])[(a.zoom, a.rot)]
    shot.convert("RGB").save(a.out)
    print(a.out, shot.size)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("combos")
    s = sub.add_parser("build")
    s.add_argument("pack")
    s = sub.add_parser("scan")
    s.add_argument("saves", nargs="*")
    s = sub.add_parser("plan")
    s.add_argument("save")
    s = sub.add_parser("preview")
    s.add_argument("out")
    s.add_argument("pack")
    s.add_argument("--rows", type=int, default=6)
    s.add_argument("--zoom", type=int, default=4)
    s.add_argument("--axis", type=int, default=0)
    s.add_argument("--rot", type=int, default=0)
    s.add_argument("--offset", default="x", choices=("x", "z"))
    a = ap.parse_args(argv)
    {"combos": cmd_combos, "build": cmd_build, "scan": cmd_scan, "plan": cmd_plan, "preview": cmd_preview}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
