#!/usr/bin/env python3
r"""hwt_build.py - builds the connecting highway T package (stream hwt, 2026-10-18) from hwt_paint's scene.

  py -3.12 hwt_build.py table                        cell table -> re/tools/netmod/hwt_cells.py (ids, frame cells, kind,
                                                     base, turn matrices; the rule twin and the C block read it)
  py -3.12 hwt_build.py art PKG [--jobs 8] [--reuse DIR]   paint every table cell at every zoom into PKG/art/<id>/
                                                     (--reuse: take zoom 3 / 4 frames from a mockup's cells_z3 / cells_z4)
  py -3.12 hwt_build.py pad PKG                      grow every frame to its full cell diamond (after art; see cmd_pad)
  py -3.12 hwt_build.py lanes PKG                    PKG/hwt_<id>.lanes.json (hwlanes, curve shapes 22800..22999)
  py -3.12 hwt_build.py manifest PKG                 PKG/manifest.json (variants, lanes, highway_lines)
  py -3.12 hwt_build.py preview PKG OUT [--rio]      the package's art + plain stock highway as the game draws it

Cells and ids. The full T (trumpet, loop R 1.25) has one piece per cell whose art or lanes differ from plain stock
highway; the right-in / right-out fallback (rio) reuses every full-T cell whose decks are the same and adds its own for
the rest (the stem cells where the bridge ramps would start). All art is painted at state 0 in the stem frame; a T
turned r quarter turns uses state r (world = anchor + R^r(dx, dz), R(x, z) = (-z, x)). Kinds: "new" = a cell the T
claims (land piece, base 15099: Protected highway slope piece, as hwcore's), "highway" = a highway cell it rewrites
(base 15051 for the through highway, 73 for the stem, so a retile re-places them as plain highway).
Lanes and turn matrices: hwcore's hwlanes (lanes cut per cell from the scene's lane decks, one new curve per cut in
hwt's shape range 22800..22999, turn matrix "auto" = derived from the lanes); they equal hwt_paint.routes() on every
cell (checked when built). A cell with no lane gets an empty turn matrix.

Task hwcap2 (owner 2026-10-18, "never extend"): 3 CAPPED twins 21254..21256 of the T's end cells 21215 (through
highway, dx -2), 21227 (dx 7) and 21200 (stem, dz -4): where the player's drag ends ON that row, the stock caps are
there and the block writes the twin (`hwtc` line) instead of the cell's piece, at the same state r. Art: the T scene
with the through highway cut at x -2 / 8 and the stem at z -4, painted at the cell, the end face from the stock cap
(hwcap_art.compose_straight). Turn matrix: the cell's turns with the outward side replaced by the side toward the row's
other lane (the stock caps' U-turn), no animated lanes. Saves (hwys): the stock cap of that end at each turn.
  py -3.12 hwt_build.py capart PKG                   paint the capped twins (after `art`; before `pad`)
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

ID0, ID_END = 21200, 21259
LAND_ART_FROM = 15127       # frame table of the land pieces: stock 15127 (the On-ramp corner, an open slab on pillars)
                            # sits in all four states with ground showing; 73 only ever sits at states 0 / 2
SIDES = ["x-", "z-", "x+", "z+"]
LAND_BASE = 15099                     # Protected highway slope piece, as hwcore's (15110 tested 2026-10-18: same ground under open decks)
WINDOW = (-4, 7, -5, 7)
CAP_TWINS = {21215: 21254, 21227: 21255, 21200: 21256}      # task hwcap2: T end cell -> its capped twin
CAP_EXTENT = (-2.0, 8.0, -4.0, 8.0)                        # the capped scene: highways cut on those end cells
SIDE_V = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}
V_SIDE = {v: k for k, v in SIDE_V.items()}


def _rot(v, r):
    x, z = v
    for _ in range(r % 4):
        x, z = -z, x
    return (x, z)


def cap_out(dx, dz):
    """frame step out of the T along the highway a T highway cell lies on (sc3netmod_hwt.c hwt_out)"""
    return ((-1 if dx < 0 else 1), 0) if dz in (0, 1) else (0, -1)


def cap_partner(dx, dz):
    """frame step toward the other lane of the cell's row (hwt_cap_stock)"""
    if dz in (0, 1):
        return (0, 1 if dz == 0 else -1)
    return (1 if dx == 0 else -1, 0)


def cap_stock(dx, dz, r):
    """the stock end cap (id, state) of T highway cell (dx, dz) at turn r"""
    import hwcap
    p = _rot(cap_partner(dx, dz), r)
    return hwcap.cap_of(_rot(cap_out(dx, dz), r), p[0] + p[1] > 0)


def capped():
    """task hwcap2: [dict(id, of, dx, dz, base, base_st, connects)] the capped twins (state-0 turns, sides 0..3)"""
    import hwt_cells
    rows = {c["id"]: c for c in hwt_cells.CELLS}
    out = []
    for jid, cid in sorted(CAP_TWINS.items()):
        c = rows[jid]
        o, p = V_SIDE[cap_out(c["dx"], c["dz"])], V_SIDE[cap_partner(c["dx"], c["dz"])]
        conn = sorted({(p if e == o else e, p if l_ == o else l_) for e, l_ in c["connects"]})
        base, bst = cap_stock(c["dx"], c["dz"], 0)
        out.append(dict(id=cid, of=jid, dx=c["dx"], dz=c["dz"], base=base, base_st=bst,
                        connects=[list(t) for t in conn if t[0] != t[1]]))
    return out


def build_table():
    import hwt_paint as T
    out = []
    sets = {}
    for name, rio in (("full", False), ("rio", True)):
        sc, C = T.scene(rio=rio)
        fp = T.footprint(sc, WINDOW)
        if rio:                                   # the stock caps stay at z -1 (their ramp sliver is cut)
            fp = {c: v for c, v in fp.items() if c not in ((0, -1), (1, -1))}
        sets[name] = fp
    full, rio = sets["full"], sets["rio"]
    nid = ID0
    cells = {}
    for c in sorted(full, key=lambda c: (c[1], c[0])):
        v = full[c]
        same = c in rio and rio[c]["decks"] == v["decks"] and rio[c]["connects"] == v["connects"]
        cells[("full", c)] = dict(id=nid, dx=c[0], dz=c[1], kind=v["kind"], decks=v["decks"],
                                  connects=v["connects"], sets=3 if same else 1)
        nid += 1
    for c in sorted(rio, key=lambda c: (c[1], c[0])):
        if cells.get(("full", c), {}).get("sets") == 3:
            continue
        v = rio[c]
        cells[("rio", c)] = dict(id=nid, dx=c[0], dz=c[1], kind=v["kind"], decks=v["decks"],
                                 connects=v["connects"], sets=2)
        nid += 1
    if nid - 1 > ID_END:
        raise SystemExit("%d ids needed, the range ends at %d" % (nid - ID0, ID_END))
    rows = []
    for (scn, c), v in sorted(cells.items(), key=lambda kv: kv[1]["id"]):
        if v["kind"] == "new":
            base = LAND_BASE
        else:
            base = 15051 if v["dz"] in (0, 1) else 73
        rows.append(dict(v, scene=scn, base=base))
    return rows


def write_table(rows):
    p = os.path.join(HERE, "hwt_cells.py")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write('"""hwt_cells.py - GENERATED by hwt_build.py table (do not edit): the connecting highway T\'s cells in the\n'
                'stem frame. sets: 1 full T, 2 right-in / right-out fallback, 3 both. kind: new (claimed land cell) /\n'
                'highway (a through-highway or stem cell it rewrites). connects: [enter side, leave side], sides 0 x-,\n'
                '1 z-, 2 x+, 3 z+ (state 0)."""\n\n')
        f.write("CELLS = [\n")
        for r in rows:
            f.write("    dict(id=%d, dx=%d, dz=%d, kind=%r, sets=%d, base=%d, scene=%r, connects=%r, decks=%r),\n"
                    % (r["id"], r["dx"], r["dz"], r["kind"], r["sets"], r["base"], r["scene"], r["connects"],
                       r["decks"]))
        f.write("]\n")
    print("wrote", p, len(rows), "cells, ids %d..%d" % (rows[0]["id"], rows[-1]["id"]))


def cmd_table():
    rows = build_table()
    write_table(rows)
    for s, name in ((1, "full"), (2, "rio")):
        sel = [r for r in rows if r["sets"] & s]
        print("%s: %d cells (%d new, %d highway)" % (name, len(sel), sum(r["kind"] == "new" for r in sel),
                                                    sum(r["kind"] == "highway" for r in sel)))


def cmd_art(pkg, jobs, reuse):
    import hwt_cells
    todo = [r for r in hwt_cells.CELLS]
    procs = []
    for i in range(jobs):
        cmd = [sys.executable, os.path.abspath(__file__), "_paint", pkg, "%d/%d" % (i, jobs)]
        if reuse:
            cmd += ["--reuse", reuse]
        procs.append(subprocess.Popen(cmd))
    rc = [p.wait() for p in procs]
    print("art:", len(todo), "cells, shard exit codes", rc)
    return 0 if not any(rc) else 1


def cmd_paint_shard(pkg, shard, reuse):
    import shutil
    import hwpaint as HP
    import hwt_cells
    import hwt_paint as T
    from netmod import netart as NA
    i, n = map(int, shard.split("/"))
    scenes = {"full": T.scene()[0], "rio": T.scene(rio=True)[0]}
    for r in hwt_cells.CELLS[i::n]:
        sc = scenes[r["scene"]]
        c = (r["dx"], r["dz"])
        d = os.path.join(pkg, "art", str(r["id"]))
        os.makedirs(d, exist_ok=True)
        anchors = {}
        zooms = list(range(NA.ZOOMS))
        if reuse and r["scene"] == "full":
            for z in (3, 4):
                src = os.path.join(reuse, "cells_z%d" % z, "%d_%d" % c)
                if os.path.isfile(os.path.join(src, "anchors.json")):
                    a = json.load(open(os.path.join(src, "anchors.json")))
                    for name, lt in a.items():
                        shutil.copyfile(os.path.join(src, name), os.path.join(d, name))
                        anchors[name] = lt
                    zooms.remove(z)
        if zooms:
            tmp = os.path.join(d, "_tmp")
            a = HP.paint_cell(sc, c, tmp, zooms=zooms)
            for name, lt in a.items():
                shutil.move(os.path.join(tmp, name), os.path.join(d, name))
                anchors[name] = lt
            shutil.rmtree(tmp, ignore_errors=True)
        json.dump(dict(sorted(anchors.items())), open(os.path.join(d, "anchors.json"), "w"), indent=1)
        print("cell", c, "->", r["id"], len(anchors), "frames", flush=True)


SHAPE0, SHAPE_END = 22800, 22999     # hwt's lane curve shape range (protocol section 5)


def cmd_capart(pkg):
    """task hwcap2: paint the capped twins from the cut scene, then their end face from the stock cap"""
    import shutil
    import hwpaint as HP
    import hwt_paint as T
    from netmod import hwcap_art as CA
    sc = T.scene(extent=CAP_EXTENT)[0]
    for cp in capped():
        d = os.path.join(pkg, "art", str(cp["id"]))
        keep = os.path.join(pkg, "art_painted", str(cp["id"]))
        for p in (d, keep):
            if os.path.isdir(p):
                shutil.rmtree(p)
        HP.paint_cell(sc, (cp["dx"], cp["dz"]), d)
        CA.compose_straight(d, keep, cp["base"], cp["base_st"])
        print("capped twin %d of %d at (%d,%d): end face from stock %d.%d" % (cp["id"], cp["of"], cp["dx"], cp["dz"],
                                                                             cp["base"], cp["base_st"]), flush=True)


def cmd_lanes(pkg):
    """hwlanes specs for every table cell (lanes cut per cell from the scene's lane decks, one new curve per cut, turn
    matrix auto), written as PKG/hwt_<id>.lanes.json; cells without a lane get an empty turn matrix in the manifest"""
    import hwlanes as HL
    import hwt_cells
    import hwt_paint as T
    shape, n = SHAPE0, 0
    os.makedirs(pkg, exist_ok=True)
    for scn in ("full", "rio"):
        rows = [r for r in hwt_cells.CELLS if r["scene"] == scn]
        T.scene(rio=scn == "rio")
        cells = [(r["dx"], r["dz"]) for r in rows]
        specs, shape = HL.build_cells(list(T.LANE_DECKS), cells, shape, {(r["dx"], r["dz"]): r["id"] for r in rows},
                                      states=(0, 1, 2, 3))
        for c, spec in specs.items():
            json.dump(spec, open(os.path.join(pkg, "hwt_%d.lanes.json" % spec["piece"]), "w", encoding="utf-8"),
                      indent=1)
            n += 1
    for cp in capped():                                       # task hwcap2: turn matrix only, no animated lane
        low = [[SIDES[e], SIDES[l_]] for e, l_ in cp["connects"]]
        spec = {"piece": cp["id"], "states": [0, 1, 2, 3], "flag": 0, "vehicle": {"class": "car", "lanes": []},
                "connects": {"road": {"low": low, "high": [[l_, e] for e, l_ in low]}}}
        json.dump(spec, open(os.path.join(pkg, "hwt_%d.lanes.json" % cp["id"]), "w", encoding="utf-8"), indent=1)
        n += 1
    if shape - 1 > SHAPE_END:
        raise SystemExit("lane curves need shapes up to %d, hwt's range ends at %d" % (shape - 1, SHAPE_END))
    print("lanes: %d specs, curve shapes %d..%d" % (n, SHAPE0, shape - 1))


def cmd_pad(pkg):
    """grow every frame to cover its whole cell diamond (transparent padding, anchors moved): with ground_under the
    engine draws the terrain only under the frame's rectangle, so a frame cropped to its art leaves the rest of the
    diamond undrawn (stale pixels; measured 2026-10-18 on the far-side cells of a turned T)"""
    from PIL import Image
    from netmod import netart as NA
    n = 0
    for d in sorted(os.listdir(os.path.join(pkg, "art"))):
        ad = os.path.join(pkg, "art", d)
        a = json.load(open(os.path.join(ad, "anchors.json")))
        for name, (L, T) in list(a.items()):
            z = int(name[1])
            W = NA.TILE_W[z]
            im = Image.open(os.path.join(ad, name)).convert("RGBA")
            ox = max(0, -L)                                   # new left vertex at x = L + ox >= 0
            L2 = L + ox
            q = W // 4 + 1
            oy = max(0, q - T)                                # room above the vertex for the diamond's top
            T2 = T + oy
            w2 = max(ox + im.width, L2 + W + 1)
            h2 = max(oy + im.height, T2 + q)
            if (w2, h2) == im.size and (ox, oy) == (0, 0):
                continue
            out = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
            out.alpha_composite(im, (ox, oy))
            out.save(os.path.join(ad, name))
            a[name] = [L2, T2]
            n += 1
        json.dump(dict(sorted(a.items())), open(os.path.join(ad, "anchors.json"), "w"), indent=1)
    print("pad: %d frames grown to their full cell diamond" % n)


STOCK_STRAIGHT = {(1, 0): (15051, 2), (-1, 0): (15051, 0), (0, 1): (73, 0), (0, -1): (73, 2)}


def save_table(r):
    """hwys line of a rewritten highway cell: at each state s it saves as the stock straight highway for its heading
    turned s quarter turns ((x, z) -> (-z, x)), so a game without the mod loads plain highway running the right way.
    Heading at state 0 (stem frame): through row 0 +x, row 1 -x, stem column 0 -z, column 1 +z."""
    if r["dz"] == 0:
        h = (1, 0)
    elif r["dz"] == 1:
        h = (-1, 0)
    else:
        h = (0, -1) if r["dx"] == 0 else (0, 1)
    out = []
    for s in range(4):
        out += list(STOCK_STRAIGHT[h])
        h = (-h[1], h[0])
    return "hwys %d %s" % (r["id"], " ".join(str(v) for v in out))


def cmd_manifest(pkg):
    import hwt_cells
    variants, connects, lines, lanes = [], [], [], []
    for r in hwt_cells.CELLS:
        nm = "Highway T (%s %+d,%+d)" % ("ramp" if r["kind"] == "new" else "junction", r["dx"], r["dz"])
        variants.append({"id": r["id"], "base": r["base"], "network": "HWAY",
                         "name": {"*": nm, "ENGLISH": "Highway Interchange"},
                         "art": {"from": LAND_ART_FROM if r["kind"] == "new" else 73, "png_dir": "art/%d" % r["id"],
                                 "ground_under": True},
                         "trblkatt": "copy_base"})
        if os.path.isfile(os.path.join(pkg, "hwt_%d.lanes.json" % r["id"])):
            lanes.append({"piece": r["id"], "spec": "hwt_%d.lanes.json" % r["id"]})      # turn matrix: auto
        else:
            connects.append({"piece": r["id"], "road": {"low": [], "high": []}})          # no lane: no turn
        lines.append("hwyp %d %d" % (r["id"], 1 if r["kind"] == "new" else 0))
        if r["kind"] != "new":
            lines.append(save_table(r))
    for cp in capped():                                       # task hwcap2: the capped twins
        variants.append({"id": cp["id"], "base": cp["base"], "network": "HWAY",
                         "name": {"*": "Highway T (junction, highway end %+d,%+d)" % (cp["dx"], cp["dz"]),
                                  "ENGLISH": "Highway Interchange"},
                         "art": {"from": 73, "png_dir": "art/%d" % cp["id"], "ground_under": True},
                         "trblkatt": "copy_base"})
        lanes.append({"piece": cp["id"], "spec": "hwt_%d.lanes.json" % cp["id"]})
        lines.append("hwyp %d 0" % cp["id"])
        lines.append("hwys %d %s" % (cp["id"], " ".join("%d %d" % cap_stock(cp["dx"], cp["dz"], s) for s in range(4))))
    for r in hwt_cells.CELLS:
        lines.append("hwt %d %d %d %d %d" % (r["id"], r["dx"], r["dz"], 1 if r["kind"] == "new" else 0, r["sets"]))
    for cp in capped():
        lines.append("hwtc %d %d %d" % (cp["id"], cp["dx"], cp["dz"]))
    man = {
        "netpack": 1, "name": "hwt_trumpet", "version": "1.0.0", "author": "sc3kre",
        "description": "Task hwt: a highway T that connects every movement (a trumpet). A stem that ends beside a "
                       "straight highway, or the stock stub X, becomes ramps: the stem's two lanes bridge over both "
                       "carriageways, a loop and an outer ramp on the far side, two right-turn ramps on the stem side. "
                       "Right-in / right-out when the far side is built up.",
        "game": {"Apps/SIMNTWRK.DLL": "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"},
        "variants": variants, "lanes": lanes, "connects": connects, "highway_lines": lines,
    }
    os.makedirs(pkg, exist_ok=True)
    json.dump(man, open(os.path.join(pkg, "manifest.json"), "w", encoding="utf-8"), indent=1)
    print("manifest:", len(variants), "variants,", len(lanes), "lane specs,", len(connects), "empty turn matrices,",
          len(lines), "highway lines")


def cmd_preview(pkg, out, sets=1):
    """the package as the game would draw it: every table cell of the set from PKG/art plus plain stock highway
    around it, zoom 4 and 3, views 0 and 1 -> OUT/hwt_pkg_z<z>_r<r>.png"""
    import hwt_cells
    from netmod import netart as NA
    os.makedirs(out, exist_ok=True)
    cells = {(r["dx"], r["dz"]): r for r in hwt_cells.CELLS if r["sets"] & sets}
    lay = [{"at": [-x, z], "dir": os.path.join(pkg, "art", str(r["id"])), "slot": 0} for (x, z), r in cells.items()]
    for x in range(-6, 10):
        for z, (pid, st) in ((0, (15051, 2)), (1, (15051, 0))):
            if (x, z) not in cells:
                lay.append({"at": [-x, z], "piece": pid, "slot": st})
    for z in range(-8, 0):
        for x, (pid, st) in ((0, (73, 2)), (1, (73, 0))):
            if (x, z) not in cells:
                if z == -1 and sets == 2:
                    pid = 11235 if x == 0 else 11237
                    st = 0
                lay.append({"at": [-x, z], "piece": pid, "slot": st})
    shots = NA.preview({"cells": lay}, None, zooms=[3, 4], rots=[0, 1])
    for (z, r), im in shots.items():
        f = os.path.join(out, "hwt_pkg%s_z%d_r%d.png" % ("" if sets == 1 else "_rio", z, r))
        im.save(f)
        print(f, im.size)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    reuse = argv[argv.index("--reuse") + 1] if "--reuse" in argv else None
    if argv[1] == "table":
        cmd_table()
    elif argv[1] == "art":
        return cmd_art(argv[2], int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 8, reuse)
    elif argv[1] == "_paint":
        cmd_paint_shard(argv[2], argv[3], reuse)
    elif argv[1] == "capart":
        cmd_capart(argv[2])
    elif argv[1] == "preview":
        cmd_preview(argv[2], argv[3], 2 if "--rio" in argv else 1)
    elif argv[1] == "lanes":
        cmd_lanes(argv[2])
    elif argv[1] == "pad":
        cmd_pad(argv[2])
    elif argv[1] == "manifest":
        cmd_manifest(argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
