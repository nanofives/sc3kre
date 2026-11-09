#!/usr/bin/env python3
r"""avdiamond_build.py - the avenue_diamond package (task avdiamond, 2026-11-09): AVX box cells whose outside edge
faces an off-ramp (mode I, both ramp lanes into the box). Rule: avjunc_rule.py (RAMP_END, split_ramp_segment), C block
AVDIAMOND in sc3netmod_avx.c; lanes / art by avjunc_build.py's own functions (same lane model, same box painter).

  py -3.12 -m netmod.avdiamond_build pieces PACK   the combos the ramp boxes need that avenue_junctions lacks (15
                                                   shipped cities + extra saves via --save) -> PACK/avdiamond_pieces.json
  py -3.12 -m netmod.avdiamond_build build PACK    lane specs, curves (shapes 25500..), art, manifest.json
  py -3.12 -m netmod.avdiamond_build check PACK    avjunc_build's check (both languages, every lane has its curve)

Every piece is a box cell like avjunc's (base 43 / 39 / 11203 / 29 by the closed edges, saved as its base), so a
game without the mod loads the stock junction. Its art is the avjunc box painter's for the same outline. Ids 20850..
20899 (round brief grant). avlj letters: the avenue edges only (the ramp edge is a road, not an avenue half).
"""
import glob
import itertools
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from netmod import avjunc_build as AB   # noqa: E402
from netmod import avjunc_rule as R     # noqa: E402

IDS = list(range(20850, 20900))
SHAPE0, SHAPE_MAX = 25500, 25999
JUNC = os.path.join(HERE, "examples", "avenue_junctions")
AVLC_SIDE = {21716: "2", 21717: "0"}                  # avenue_lanes: avlc 21716 15098 2, avlc 21717 15098 0


def have_combos():
    """(outline, modes) -> piece of the avenue_junctions package (its manifest's avxm lines)"""
    m = json.load(open(os.path.join(JUNC, "manifest.json")))
    out = {}
    for ln in m["avenue_junction_lines"]:
        t = ln.split()
        if t[0] == "avxm":
            out[(t[2], t[3])] = int(t[1])
    return out


def cmd_pieces(a):
    from netmod import avx
    E = avx._env()
    have = have_combos()
    saves = sorted(glob.glob(os.path.join(E["g"], "Cities", "*.sc3"))) + (a.save or [])
    need = {}
    R.DIAMOND = True
    for path in saves:
        L, roads = R.city_layer(path, E["ids"])
        res = R.find_c(L, R.Pieces(), roads)
        for bx in res["boxes"]:
            if not any(inf["edges"][e][1] == "ramp" for inf in bx["cell"].values() for e in range(4)):
                continue
            arms = R.box_arms(bx)
            for n in range(len(arms) + 1):
                for dm in itertools.combinations(arms, n):
                    for c, (o, m) in R.box_modes(bx, frozenset(dm)).items():
                        cz = R.canonical(o, m)
                        if cz is None:
                            raise SystemExit("no canonical orientation for %s %s at %s" % (o, m, c))
                        k = (cz[0], cz[1])
                        if k in have:
                            continue
                        need.setdefault(k, {"cells": 0, "oneway": 0, "example": "%s %s" % (os.path.basename(path), c)})
                        need[k]["cells"] += 1
                        need[k]["oneway"] += 0 if n else 1
    keys = sorted(need, key=lambda k: (-need[k]["oneway"], -need[k]["cells"], k))
    p = os.path.join(a.pack, "avdiamond_pieces.json")
    prev = json.load(open(p)) if os.path.exists(p) else {}
    old = prev.get("box", [])                                        # ids are stable: saved cities hold them
    rows, taken = [], set()
    for r in old:
        k = (r["outline"], r["modes"])
        rows.append({"id": r["id"], "outline": r["outline"], "modes": r["modes"], "base": r["base"],
                     **need.get(k, {"cells": 0, "oneway": 0, "example": "(no longer needed by the scan)"})})
        taken.add(k)
    free = [i for i in IDS if i not in {r["id"] for r in rows}]
    for k in keys:
        if k in taken:
            continue
        if not free:
            raise SystemExit("out of ids (20850..20899)")
        rows.append({"id": free.pop(0), "outline": k[0], "modes": k[1], "base": R.save_base(k[0]), **need[k]})
    out = {"_": "avdiamond_build.py pieces: box cells with an off-ramp edge (mode I on the outside edge) that "
                "avenue_junctions lacks; outline / modes N E S W at state 0 as avjunc_build",
           "box": rows, "ct": prev.get("ct", []), "hwtx": prev.get("hwtx")}   # kept by hand (D2, D4)
    os.makedirs(a.pack, exist_ok=True)
    json.dump(out, open(p, "w", newline="\n"), indent=1)
    print("wrote %s: %d pieces" % (p, len(rows)))
    for r in rows:
        print("  %d %s %s base %d  cells %d (all arms one-way %d)  e.g. %s" % (
            r["id"], r["outline"], r["modes"], r["base"], r["cells"], r["oneway"], r["example"]))


def ramp_edge(outline, modes):
    """the outside edge of a box cell at state 0: an A edge that is not along the band. In avjunc's canonical frame the
    band runs N-S on A/I edges N and S; for AAII the band arm is N (row S, median W), outside E; for AAAI outside E."""
    return 1


def table_lines(T):
    out = []
    for r in T["box"]:
        out.append("avxm %d %s %s" % (r["id"], r["outline"], r["modes"]))
    for r in T.get("ct", []):
        out.append("avlt %d %s %s" % (r["id"], r["outline"], r["modes"]))
    for r in T["box"]:
        e_ramp = ramp_edge(r["outline"], r["modes"])
        lj = "".join(m if (o == "A" and m in "IO" and e != e_ramp) else "."
                     for e, (o, m) in enumerate(zip(r["outline"], r["modes"])))
        if lj != "....":
            out.append("avlj %d %s" % (r["id"], lj))
    return out


def cmd_build(a):
    from netmod import lanekit as LK
    from netmod import avlanes as AL
    T = json.load(open(os.path.join(a.pack, "avdiamond_pieces.json")))
    for r in T["box"]:
        if r["modes"][1] != "I" or r["outline"][1] != "A":
            raise SystemExit("piece %d: E edge is not the off-ramp edge (%s %s)" % (r["id"], r["outline"], r["modes"]))
    AB.SHAPE0, AB.SHAPE_MAX = SHAPE0, SHAPE_MAX
    game = LK.Game()
    plan = AB.CurvePlan(game)
    peds = {b: AL._stock_ped(game, b) for b in (43, 39, 11203, 29)}
    variants, lanes_entries, outlines, nlanes = [], [], {}, 0
    for r in T["box"]:
        spec, ln = AB.box_spec(r["id"], r["outline"], r["modes"], r["base"], game, plan, peds[r["base"]])
        spec["_"] = ("avdiamond_build.py: box cell with an off-ramp edge (E), outline %s modes %s (N E S W, state 0), "
                     "saved as %d" % (r["outline"], r["modes"], r["base"]))
        nlanes += len(ln)
        fn = "box_%d.lanes.json" % r["id"]
        json.dump(spec, open(os.path.join(a.pack, fn), "w", newline="\n"), indent=1)
        lanes_entries.append({"piece": r["id"], "spec": fn})
        variants.append({"id": r["id"], "base": r["base"], "network": "ROAD",
                         "name": {"*": "Avenue ramp junction", "ENGLISH": "Cruce de avenida con rampa"},
                         "art": {"from": 43, "png_dir": "art/%d" % r["id"]}, "trblkatt": "copy_base"})
        outlines.setdefault(r["outline"], []).append(r["id"])
    for r in T.get("ct", []):                       # task avdiamond D2: corner + T cells (sc3netmod_avl.c `avlt`)
        spec, ln = AB.box_spec(r["id"], r["outline"], r["modes"], r["base"], game, plan, peds[r["base"]])
        spec["_"] = ("avdiamond_build.py: avenue corner + T cell, outline %s modes %s (N E S W, state 0), saved as %d"
                     % (r["outline"], r["modes"], r["base"]))
        nlanes += len(ln)
        fn = "ct_%d.lanes.json" % r["id"]
        json.dump(spec, open(os.path.join(a.pack, fn), "w", newline="\n"), indent=1)
        lanes_entries.append({"piece": r["id"], "spec": fn})
        variants.append({"id": r["id"], "base": r["base"], "network": "ROAD",
                         "name": {"*": "Avenue corner junction", "ENGLISH": "Esquina de avenida"},
                         "art": {"from": 43, "png_dir": "art/%d" % r["id"]}, "trblkatt": "copy_base"})
        outlines.setdefault(r["outline"], []).append(r["id"])
    hx = T.get("hwtx")                              # task avdiamond D4: crossing twins under a T cell
    hlines = []
    if hx:
        dx, dz = hx["cell"]
        variants.append({"id": hx["twin"], "base": 15098, "network": "ROAD", "trblkatt": "copy_base",
                         "name": {"*": "Highway T over a road", "ENGLISH": "Cruce de autopista sobre calle"}})
        hlines.append("hwtx %d %d %d" % (hx["twin"], dx, dz))
        for pid, src in hx["oneway"]:
            sp = json.load(open(os.path.join(HERE, "examples", "avenue_lanes", "avl_%d.lanes.json" % src)))
            sp["piece"] = pid
            sp["_comment"] = "avdiamond_build.py: avenue_lanes %d's lanes (one-way avenue half under a highway) on the T crossing twin" % src
            sp.pop("curves", None)
            fn = "hwtx_%d.lanes.json" % pid
            json.dump(sp, open(os.path.join(a.pack, fn), "w", newline="\n"), indent=1)
            lanes_entries.append({"piece": pid, "spec": fn})
            variants.append({"id": pid, "base": 15098, "network": "ROAD",
                             "name": {"*": "Avenue (one way), under a highway T", "ENGLISH": "Avenida (un sentido) bajo autopista"}})
            hlines.append("hwtx %d %d %d" % (pid, dx, dz))
    if plan.shapes:
        first = os.path.join(a.pack, lanes_entries[0]["spec"])
        sp = json.load(open(first))
        sp["curves"] = [{"shape": s, "pts": p} for s, p in sorted(plan.shapes.items())]
        json.dump(sp, open(first, "w", newline="\n"), indent=1)
    junc = json.load(open(os.path.join(JUNC, "manifest.json")))
    lines = table_lines(T)
    man = {
        "netpack": 1, "name": "avenue_diamond", "version": "0.1.0", "author": "netmod (task avdiamond)",
        "description": (
            "Avenue junctions beside a highway's diamond ramps (task avdiamond, 2026-11-09). sc3netmod's AVX block reads "
            "the stock on-ramp ground ends (15138..15141) as road arms and, on an avenue under an elevated highway, "
            "cuts the junction segment at the highway crossing, so each ramp junction becomes one paved box and the "
            "crossing between them a one-way band. These pieces are the box cells whose outside edge faces an "
            "off-ramp: both ramp lanes enter the box. Needs avenue_junctions (the other box cells). Saved as 43 / 39, "
            "so a game without the mod loads stock junctions. Build: `py -3.12 -m netmod.avdiamond_build build .` in "
            "re/tools (art from the game's frames, not shipped)."),
        "game": junc["game"],
        "variants": sorted(variants, key=lambda v: v["id"]),
        "lanes": lanes_entries,
        "avenue_junction_lines": [ln for ln in lines if ln.startswith("avx")],
        "avenue_lines": [ln for ln in lines if ln.startswith(("avlj", "avlt"))] + (
            ["avlc %d 15098 %s %d" % (pid, AVLC_SIDE[src], hx["twin"]) for pid, src in hx["oneway"]] if hx else []),
        "highway_lines": hlines,
    }
    json.dump(man, open(os.path.join(a.pack, "manifest.json"), "w", newline="\n"), indent=1)
    print("specs: %d box pieces (%d lanes); new curve shapes %s" % (len(T["box"]), nlanes, sorted(plan.shapes)))
    if a.no_art:
        return
    for outline, ids in sorted(outlines.items()):
        d0 = os.path.join(a.pack, "art", str(ids[0]))
        AB.paint_box(d0, outline)
        for pid in ids[1:]:
            d = os.path.join(a.pack, "art", str(pid))
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(d0, d)
        print("art: outline %s -> %s" % (outline, ids))


def cmd_check(a):
    T = json.load(open(os.path.join(a.pack, "avdiamond_pieces.json")))
    shim = os.path.join(a.pack, "avjunc_pieces.json")              # avjunc_build.check reads this name
    made = not os.path.exists(shim)
    if made:
        json.dump({"box": T["box"], "nose_oneway": {}, "nose_twoway": {}}, open(shim, "w", newline="\n"))
    link, AB.NOSE_OW_LINK = AB.NOSE_OW_LINK, {}                   # this package has no noses
    try:
        return AB.cmd_check(a)
    finally:
        AB.NOSE_OW_LINK = link
        if made:
            os.remove(shim)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["pieces", "build", "check"])
    ap.add_argument("pack")
    ap.add_argument("--save", action="append", help="extra city save (pieces)")
    ap.add_argument("--no-art", action="store_true")
    a = ap.parse_args(argv)
    return {"pieces": cmd_pieces, "build": cmd_build, "check": cmd_check}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
