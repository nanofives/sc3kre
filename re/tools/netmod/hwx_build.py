#!/usr/bin/env python3
r"""hwx_build.py - builds the cloverleaf package (task hwx, highway program 2026-10-18) from hwx.py's scene.

  py -3.12 hwx_build.py art PKG [--jobs 8] [--only ID,ID]   paint every piece (or those) at its ref cell, every zoom
                                                -> PKG/art/<id>/ (capped junctions: + the stock end face)
  py -3.12 hwx_build.py pad PKG                 grow every frame to its full cell diamond (ground_under draws the
                                                terrain only under the frame's rectangle: hwt measured it)
  py -3.12 hwx_build.py lanes PKG               PKG/hwx_<id>.lanes.json (hwlanes, curve shapes 22500..22799)
  py -3.12 hwx_build.py manifest PKG            PKG/manifest.json (variants, lanes, empty turn matrices, highway_lines)
  py -3.12 hwx_build.py ingame-sheet SHOTS_DIR OUT   the owner sheet from the in-game check's shots
  py -3.12 hwx_build.py preview PKG OUT [--fallback]   the package's art placed by the table (ids, states) with plain
                                                stock highway around it, zoom 4 / 3, views 0 / 1

Pieces (hwx.table(), verify/hwx/README.md): 17 land ids (ramps, base 15099, used in all four quadrants at state =
quadrant), 8 mainline ids (a carriageway cell with a ramp join, base 15051 / 73, states 0 / 2), 6 clean core ids (base
= the stock X piece, same states). Each id is painted and has its lanes cut at its ref cell, at state 0; any other cell
of the id is the ref cell turned `put` quarter turns about the X centre, so the scene's 4-fold symmetry (the ramps)
and 2-fold symmetry (the core) make the frames and lanes right there.
Table lines for the block (sc3netmod_hwx.c): `hwx <piece> <state> <dx> <dz> <cls>`, cls 0 main / 1 land / 2 core /
3 capped, (dx, dz) from the X centre cell (0, 0) = stock 15113.0.

Task hwcap2 (owner 2026-10-18, "never extend"): 4 CAPPED junctions 21166..21169, one per outer junction 21151 / 21153
/ 21155 / 21157 (the junctions on the last row of each arm, dx / dz 5 and -6). A drag that ends ON that row leaves the
stock end caps on both of its cells; the block writes the capped junction there instead of the junction. Base = the
stock cap, written at the cap's own state (each capped id has one cap id at both of its cells: checked), so a save
and the stock tiler see the stock end. Art: the scene with both highways ending on the box edge (hwx.scene(ext=6)),
painted at the cell where the cap is state 0, then the end face from the stock cap (hwcap_art.compose_straight).
Turn matrix: the junction's turns with the outward side replaced by the side toward the other lane of the row (the
stock cap's U-turn: 15054.0 x+ => z-), no animated lanes (as hwdx's capped joins).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

LAND_BASE = 15099            # Protected highway slope piece (hwcore's and hwt's land base)
ART_FROM = 15127             # frame table of EVERY piece: 15127's sprite class draws the terrain under the piece
                             # (HWY_BASE.md "ground under a piece": 73's table loses it in some views; ramps, joins
                             # and the core's underpass all leave ground visible)
SHAPE0, SHAPE_END = 22500, 22799
CLS = {"main": 0, "land": 1, "core": 2, "capped": 3}
CAP_IDS = {21151: 21166, 21153: 21167, 21155: 21168, 21157: 21169}     # task hwcap2: outer junction -> capped junction
CAP_EXT = 6                  # the capped scene: both highways end on the 12x12 box's edge (cells -6..5)
SIDE = {"x-": 0, "z-": 1, "x+": 2, "z+": 3}
SIDE_NAME = {v: k for k, v in SIDE.items()}


def cap_step(c):
    """outward step of the arm a carriageway cell lies on"""
    dx, dz = c
    return ((1 if dx > 0 else -1), 0) if dz in (-1, 0) else (0, (1 if dz > 0 else -1))


def cap_partner(c):
    """side (0..3) toward the other lane of the cell's row"""
    dx, dz = c
    if dz in (-1, 0):
        return 3 if dz == -1 else 1
    return 2 if dx == -1 else 0


def pieces(capped=True):
    """{id: dict(cls, ref, base, cells=[(cell, put)])} from hwx.table(); capped pieces (task hwcap2) also carry
    junction = the id they replace"""
    import hwx
    import hwcap
    out = {}
    for c, v in hwx.table().items():
        if not v["id"]:
            continue
        p = out.setdefault(v["id"], dict(cls=v["cls"], ref=v["ref"], base=None, cells=[]))
        if v["cls"] == "land":
            p["base"] = LAND_BASE
        else:
            p["base"] = v["base"][0]
        p["cells"].append((c, v["put"]))
    if capped:
        for jid, cid in sorted(CAP_IDS.items()):
            cells = []
            for c, put in out[jid]["cells"]:
                dx, dz = c
                lower = dz == -1 if dz in (-1, 0) else dx == -1
                cells.append((c, hwcap.cap_of(cap_step(c), lower)))
            bases = {cp[0] for c, cp in cells}
            if len(bases) != 1:
                raise SystemExit("capped junction %d: its cells end in different caps %s" % (cid, cells))
            ref = [c for c, cp in cells if cp[1] == 0][0]
            out[cid] = dict(cls="capped", ref=ref, base=bases.pop(), junction=jid,
                            cells=[(c, cp[1]) for c, cp in cells])
    return out


def capped_turns(pkg, cid, p):
    """task hwcap2: the capped junction's turns at state 0 (= at its ref cell, where the cap is state 0): the
    junction's turns there (its lanes, put state) with the outward side replaced by the side toward the row's other
    lane"""
    from netmod import lanekit as LK
    jid = p["junction"]
    put = dict(pieces(capped=False)[jid]["cells"])[p["ref"]]
    spec = json.load(open(os.path.join(pkg, "hwx_%d.lanes.json" % jid)))
    out_side = {(-1, 0): 0, (0, -1): 1, (1, 0): 2, (0, 1): 3}[cap_step(p["ref"])]
    part = cap_partner(p["ref"])
    turns = set()
    for ln in spec["vehicle"]["lanes"]:
        a, b = ln["from"], ln["to"]
        e = (min(LK.boundary_sides(a[0], a[2])) + put) % 4
        l_ = (min(LK.boundary_sides(b[0], b[2])) + put) % 4
        e = part if e == out_side else e
        l_ = part if l_ == out_side else l_
        if e != l_:
            turns.add((SIDE_NAME[e], SIDE_NAME[l_]))
    return sorted(turns)


HEAD_STOCK = {(1, 0): (15051, 2), (-1, 0): (15051, 0), (0, 1): (73, 0), (0, -1): (73, 2)}


def saved_as(p, k):
    """(id, state) an on-highway piece at state k saves as (hwys): a junction = the stock straight highway of its
    ref cell's heading turned k quarter turns; a core piece = its stock X piece at state k (the stock X's two copies
    of a piece are 180 degrees apart, as ours)"""
    import hwx
    if p["cls"] == "core":
        return p["base"], k
    pid, st = hwx.carriageway(p["ref"])[1]
    hx, hz = {(15051, 2): (1, 0), (15051, 0): (-1, 0), (73, 0): (0, 1), (73, 2): (0, -1)}[(pid, st)]
    for _ in range(k):
        hx, hz = -hz, hx
    return HEAD_STOCK[(hx, hz)]


def _near(sc, boxes, c):
    import hwpaint as HP
    return HP.Scene([dk for dk, bb in zip(sc.decks, boxes)
                     if bb[0] < c[0] + 1.5 and bb[2] > c[0] - 0.5 and bb[1] < c[1] + 1.5 and bb[3] > c[1] - 0.5])


def cmd_art(pkg, jobs, only=None):
    extra = [str(x) for x in sorted(only)] if only else []
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "_paint", pkg, "%d/%d" % (i, jobs)] + extra)
             for i in range(jobs)]
    rc = [p.wait() for p in procs]
    print("art: shard exit codes", rc)
    return 0 if not any(rc) else 1


def cmd_paint_shard(pkg, shard, only=None):
    import hwpaint as HP
    import hwx
    from netmod import hwcap_art as CA
    i, n = map(int, shard.split("/"))
    sc = hwx.scene()
    boxes = [hwx._deck_box(dk) for dk in sc.decks]
    scc = hwx.scene(ext=CAP_EXT)                                  # task hwcap2: both highways end on the box edge
    boxc = [hwx._deck_box(dk) for dk in scc.decks]
    for pid, p in [t for t in sorted(pieces().items()) if not only or t[0] in only][i::n]:
        d = os.path.join(pkg, "art", str(pid))
        if p["cls"] == "capped":
            keep = os.path.join(pkg, "art_painted", str(pid))
            if os.path.isdir(keep):
                import shutil
                shutil.rmtree(keep)
            HP.paint_cell(_near(scc, boxc, p["ref"]), p["ref"], d)
            CA.compose_straight(d, keep, p["base"])
            print("capped piece", pid, "ref", p["ref"], "end face from stock", p["base"], flush=True)
            continue
        HP.paint_cell(_near(sc, boxes, p["ref"]), p["ref"], d)
        print("piece", pid, "ref", p["ref"], flush=True)


def cmd_pad(pkg):
    """grow every frame to cover its whole cell diamond (transparent padding, anchor moved)"""
    from PIL import Image
    from netmod import netart as NA
    n = 0
    for dname in sorted(os.listdir(os.path.join(pkg, "art"))):
        ad = os.path.join(pkg, "art", dname)
        a = json.load(open(os.path.join(ad, "anchors.json")))
        for name, (L, T) in list(a.items()):
            W = NA.TILE_W[int(name[1])]
            im = Image.open(os.path.join(ad, name)).convert("RGBA")
            ox = max(0, -L)
            L2 = L + ox
            q = W // 4 + 1
            oy = max(0, q - T)
            T2 = T + oy
            w2, h2 = max(ox + im.width, L2 + W + 1), max(oy + im.height, T2 + q)
            if (w2, h2) == im.size and (ox, oy) == (0, 0):
                continue
            out = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
            out.alpha_composite(im, (ox, oy))
            out.save(os.path.join(ad, name))
            a[name] = [L2, T2]
            n += 1
        json.dump(dict(sorted(a.items())), open(os.path.join(ad, "anchors.json"), "w"), indent=1)
    print("pad: %d frames grown to their full cell diamond" % n)


def cmd_lanes(pkg):
    import hwlanes as HL
    import hwx
    sc = hwx.scene()
    ps = pieces()
    shape, n = SHAPE0, 0
    os.makedirs(pkg, exist_ok=True)
    for states, sel in (((0, 1, 2, 3), "land"), ((0, 2), "main"), ((0, 2), "core")):
        group = {p["ref"]: pid for pid, p in ps.items() if p["cls"] == sel}
        specs, shape = HL.build_cells(sc.decks, sorted(group), shape, group, states=states)
        for c, spec in specs.items():
            json.dump(spec, open(os.path.join(pkg, "hwx_%d.lanes.json" % spec["piece"]), "w", encoding="utf-8"),
                      indent=1)
            n += 1
    for cid, p in sorted(ps.items()):                         # task hwcap2: capped junctions, turn matrix only
        if p["cls"] != "capped":
            continue
        low = [list(t) for t in capped_turns(pkg, cid, p)]
        spec = {"piece": cid, "states": sorted({st for c, st in p["cells"]}), "flag": 0,
                "vehicle": {"class": "car", "lanes": []},
                "connects": {"road": {"low": low, "high": [[l_, e] for e, l_ in low]}}}
        json.dump(spec, open(os.path.join(pkg, "hwx_%d.lanes.json" % cid), "w", encoding="utf-8"), indent=1)
        n += 1
    if shape - 1 > SHAPE_END:
        raise SystemExit("lane curves need shapes up to %d, hwx's range ends at %d" % (shape - 1, SHAPE_END))
    print("lanes: %d specs, curve shapes %d..%d" % (n, SHAPE0, shape - 1))


def cmd_manifest(pkg):
    variants, connects, lanes, lines = [], [], [], []
    ps = pieces()
    for pid, p in sorted(ps.items()):
        nm = {"land": "Cloverleaf ramp %+d,%+d", "main": "Cloverleaf junction %+d,%+d",
              "core": "Clean flyover %+d,%+d", "capped": "Cloverleaf junction, highway end %+d,%+d"}[p["cls"]] % p["ref"]
        variants.append({"id": pid, "base": p["base"], "network": "HWAY",
                         "name": {"*": nm, "ENGLISH": "Highway Interchange"},
                         "art": {"from": ART_FROM, "png_dir": "art/%d" % pid,
                                 "ground_under": True},
                         "trblkatt": "copy_base"})
        if os.path.isfile(os.path.join(pkg, "hwx_%d.lanes.json" % pid)):
            lanes.append({"piece": pid, "spec": "hwx_%d.lanes.json" % pid})          # turn matrix: auto
        else:
            connects.append({"piece": pid, "road": {"low": [], "high": []}})          # no lane: no turn
        lines.append("hwyp %d %d" % (pid, 1 if p["cls"] == "land" else 0))
    for pid, p in sorted(ps.items()):                         # save table: what a game without the mod reads
        if p["cls"] not in ("land", "capped"):                # capped: its base (the stock cap) at its state
            lines.append("hwys %d %s" % (pid, " ".join("%d %d" % saved_as(p, k) for k in range(4))))
    for pid, p in sorted(ps.items()):
        for (c, put) in sorted(p["cells"]):
            lines.append("hwx %d %d %d %d %d" % (pid, put, c[0], c[1], CLS[p["cls"]]))
    man = {
        "netpack": 1, "name": "hwx_cloverleaf", "version": "1.0.0", "author": "sc3kre",
        "description": "Task hwx: a cloverleaf at a straight highway X. When two straight highways cross on flat "
                       "ground with room around them, four loops (left turns) and four outer ramps (right turns) "
                       "connect every movement; the X itself becomes a clean flyover (straight full-width decks). "
                       "With a quadrant built up, only the clean flyover.",
        "game": {"Apps/SIMNTWRK.DLL": "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"},
        "variants": variants, "lanes": lanes, "connects": connects, "highway_lines": lines,
    }
    os.makedirs(pkg, exist_ok=True)
    json.dump(man, open(os.path.join(pkg, "manifest.json"), "w", encoding="utf-8"), indent=1)
    print("manifest:", len(variants), "variants,", len(lanes), "lane specs,", len(connects), "empty turn matrices,",
          len(lines), "highway lines")


def cmd_preview(pkg, out, fallback=False):
    import hwx
    from netmod import netart as NA
    os.makedirs(out, exist_ok=True)
    lay, done = [], set()
    for pid, p in pieces().items():
        if fallback and p["cls"] != "core":
            continue
        for c, put in p["cells"]:
            lay.append({"at": [-c[0], c[1]], "dir": os.path.join(pkg, "art", str(pid)), "slot": put})
            done.add(c)
    for k in range(-9, 9):
        for c in ((k, -1), (k, 0), (-1, k), (0, k)):
            if c not in done and c not in hwx.STOCK_CORE:
                pid, st = hwx.carriageway(c)[1]
                lay.append({"at": [-c[0], c[1]], "piece": pid, "slot": st})
                done.add(c)
    shots = NA.preview({"cells": lay}, None, zooms=[3, 4], rots=[0, 1])
    for (z, r), im in shots.items():
        f = os.path.join(out, "hwx_pkg%s_z%d_r%d.png" % ("_fallback" if fallback else "", z, r))
        im.save(f)
        print(f, im.size)


SHOTS = [("c1_z3r0.png", "cloverleaf, zoom 3, view 0 (x highway dragged first)"),
         ("c1_z3r1.png", "cloverleaf, zoom 3, view 1"),
         ("c1_z4r0.png", "cloverleaf, zoom 4, view 0"),
         ("c1_z4r1.png", "cloverleaf, zoom 4, view 1"),
         ("r_c1_z3r2.png", "after save + reload: zoom 3, view 2"),
         ("r_c1_z4r3.png", "after save + reload: zoom 4, view 3"),
         ("r_c2_z3r1.png", "second cloverleaf (z highway dragged first), after reload, view 1"),
         ("f1_z4r0.png", "fallback, a road in one quadrant: clean flyover, zoom 4, view 0"),
         ("r_f1_z3r0_c.png", "fallback after reload, zoom 3, view 0")]


def cmd_ingame_sheet(shots_dir, out):
    """the in-game owner sheet from the shots of the check (HUD cropped off)"""
    from PIL import Image, ImageDraw, ImageFont
    try:
        fh, fb = ImageFont.truetype("arialbd.ttf", 26), ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        fh = fb = ImageFont.load_default()
    W, H, cols = 700, 540, 3
    rows = (len(SHOTS) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * W + (cols + 1) * 10, 60 + rows * (H + 40)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    d.text((12, 14), "hwx: cloverleaf at a straight highway X, in game (sc3netmod + hwx_cloverleaf, lab city)",
           fill=(240, 240, 240), font=fh)
    for k, (f, t) in enumerate(SHOTS):
        x, y = 10 + (k % cols) * (W + 10), 60 + (k // cols) * (H + 40)
        d.text((x, y), t, fill=(240, 220, 150), font=fb)
        sheet.paste(Image.open(os.path.join(shots_dir, f)).convert("RGB").crop((0, 0, W, H)), (x, y + 28))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sheet.save(out)
    print(out, sheet.size)


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    if argv[1] == "art":
        only = {int(x) for x in argv[argv.index("--only") + 1].split(",")} if "--only" in argv else None
        return cmd_art(argv[2], int(argv[argv.index("--jobs") + 1]) if "--jobs" in argv else 8, only)
    if argv[1] == "_paint":
        return cmd_paint_shard(argv[2], argv[3], {int(x) for x in argv[4:]} or None)
    if argv[1] == "pad":
        return cmd_pad(argv[2])
    if argv[1] == "lanes":
        return cmd_lanes(argv[2])
    if argv[1] == "manifest":
        return cmd_manifest(argv[2])
    if argv[1] == "ingame-sheet":
        return cmd_ingame_sheet(argv[2], argv[3])
    if argv[1] == "preview":
        return cmd_preview(argv[2], argv[3], "--fallback" in argv)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
