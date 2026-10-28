#!/usr/bin/env python3
r"""avpaint_build.py - task avpaint (2026-10-28): adds to the avenue_lanes package
  1. the LOOK-ONLY twins (sc3netmod_avp.c, `avlp`): the art of AVL's U-turn / corner / slope pieces on the STOCK base
     with its stock two-way lanes, for avenue bands AVL leaves two-way (owner img1 / img2, 2026-10-27);
  2. the CORNER + T pieces (sc3netmod_avl.c, `avlt`): a plain road meeting the other band's first row beside an avenue
     corner (owner save "Big One" (567..569, 31..32)). Box-cell pieces with the AVX letters (avjunc_build.py): two new
     ones for the linked inner bend and half, four copies of avenue_junctions box cells for the T row (own ids, so
     AVX's revert never touches them).

  py -3.12 -m netmod.avpaint_build build PACK --art-from DIR --junctions JPACK [--junctions-art DIR]
      PACK      re/tools/netmod/examples/avenue_lanes
      DIR       a folder holding avenue_lanes' art/ (11203, 21718..21725); default PACK
      JPACK     re/tools/netmod/examples/avenue_junctions (box lane specs, its curves; art/<id> unless --junctions-art)
Ids 21727..21741 (avenue_lanes' free range 21727..21749). Curve shapes from 23708 (avenue_junctions uses 23700..23707).
"""
import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

# look-only twins: twin -> the AVL pieces it looks like (art dir of the first)
PAINT = [(21727, [21701, 21726], "11203")] + [(21728 + i, [21718 + i], str(21718 + i)) for i in range(8)]
# corner + T: (id, base, outline, modes at state 0, lanes from: None = generated (corner turn flag), else a box id)
CT_NEW = [(21736, 39, "ICAI", "CCIO", True), (21737, 39, "ICAI", "ICOC", False)]
CT_COPY = [(21738, 20817), (21739, 20815), (21740, 20814), (21741, 20816)]
CT_ART = {21736: 20817, 21737: 20817}           # ICAI box art (avjunc_build.paint_box paints by outline only)
SHAPE0 = 23708


def load(p):
    return json.load(open(p))


def save(p, d):
    json.dump(d, open(p, "w", newline="\n"), indent=1)


def copy_art(src, dst):
    if not os.path.isdir(src):
        raise SystemExit("art missing: %s" % src)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def cmd_build(a):
    from netmod import lanekit as LK
    from netmod import avlanes as AL
    from netmod import avjunc_build as JB
    from netmod import hwlanes as HL
    pack, jpack = a.pack, a.junctions
    man_p = os.path.join(pack, "manifest.json")
    man = load(man_p)
    jman = load(os.path.join(jpack, "manifest.json"))
    jbox = {r["id"]: r for r in load(os.path.join(jpack, "avjunc_pieces.json"))["box"]}
    jvar = {v["id"]: v for v in jman["variants"]}
    own = {pid for pid, _, _ in PAINT} | {r[0] for r in CT_NEW} | {r[0] for r in CT_COPY}
    man["variants"] = [v for v in man["variants"] if v["id"] not in own]
    man["lanes"] = [e for e in man["lanes"] if e["piece"] not in own]
    man["avenue_lines"] = [ln for ln in man["avenue_lines"] if not ln.startswith(("avlp ", "avlt "))]
    byid = {v["id"]: v for v in man["variants"]}
    art_src = os.path.join(a.art_from or pack, "art")
    art_dst = os.path.join(pack, "art")
    jart = os.path.join(a.junctions_art or jpack, "art")

    # 1. look-only twins: base and art spec of the piece they look like, no lanes (copy_base = stock lanes)
    for pid, of, art in PAINT:
        src = byid[of[0]]
        v = {"id": pid, "base": src["base"], "network": "ROAD",
             "name": {"*": "Avenue (two way)", "ENGLISH": "Avenida (doble sentido)"}, "trblkatt": "copy_base",
             "art": dict(src["art"], png_dir="art/%d" % pid)}
        man["variants"].append(v)
        for o in of:
            man["avenue_lines"].append("avlp %d %d" % (pid, o))
        copy_art(os.path.join(art_src, art), os.path.join(art_dst, str(pid)))

    # 2. corner + T: lane specs
    game = LK.Game()
    for sp in [os.path.join(pack, e["spec"]) for e in man["lanes"]] + \
              [os.path.join(jpack, e["spec"]) for e in jman["lanes"]]:
        cv = load(sp).get("curves")
        if cv:
            HL.inject(game, {"curves": cv})           # the packages' own shapes: found, never re-made
    plan = JB.CurvePlan(game)
    plan.next = SHAPE0
    ped39 = AL._stock_ped(game, 39)
    for pid, base, ol, md, corner in CT_NEW:
        spec, ln = JB.box_spec(pid, ol, md, base, game, plan, ped39, corner=corner)
        spec["_"] = ("avpaint_build.py: avenue corner + T cell outline %s modes %s (N E S W, state 0), saved as %d" %
                     (ol, md, base))
        fn = "avl_%d.lanes.json" % pid
        save(os.path.join(pack, fn), spec)
        man["lanes"].append({"piece": pid, "spec": fn})
        man["variants"].append({"id": pid, "base": base, "network": "ROAD",
                                "name": {"*": "Avenue corner junction", "ENGLISH": "Esquina de avenida"},
                                "art": {"from": 43, "png_dir": "art/%d" % pid}, "trblkatt": "copy_base"})
        man["avenue_lines"].append("avlt %d %s %s" % (pid, ol, md))
        copy_art(os.path.join(jart, str(CT_ART[pid])), os.path.join(art_dst, str(pid)))
        print("corner + T %d: %d lanes %s" % (pid, len(ln), [(e, f, k) for e, _, f, _, k in ln]))
    for pid, src in CT_COPY:
        r, v = jbox[src], jvar[src]
        spec = load(os.path.join(jpack, "box_%d.lanes.json" % src))
        spec.pop("curves", None)
        spec["piece"] = pid
        spec["_"] = "avpaint_build.py: copy of avenue_junctions %d (%s %s) for the T row of an avenue corner + T" % (
            src, r["outline"], r["modes"])
        fn = "avl_%d.lanes.json" % pid
        save(os.path.join(pack, fn), spec)
        man["lanes"].append({"piece": pid, "spec": fn})
        man["variants"].append({"id": pid, "base": v["base"], "network": "ROAD",
                                "name": {"*": "Avenue corner junction", "ENGLISH": "Esquina de avenida"},
                                "art": dict(v["art"], png_dir="art/%d" % pid), "trblkatt": "copy_base"})
        man["avenue_lines"].append("avlt %d %s %s" % (pid, r["outline"], r["modes"]))
        copy_art(os.path.join(jart, str(src)), os.path.join(art_dst, str(pid)))
    # curves: new shapes plus avenue_junctions' own (the box copies' lanes use them; netpack_lanes accepts a shape
    # defined by two packages when the points are the same), on the first new spec
    jcurves = {}
    for e in jman["lanes"]:
        for c in load(os.path.join(jpack, e["spec"])).get("curves", []):
            jcurves[c["shape"]] = c["pts"]
    jcurves.update(plan.shapes)
    fn = os.path.join(pack, "avl_%d.lanes.json" % CT_NEW[0][0])
    sp = load(fn)
    sp["curves"] = [{"shape": s, "pts": p} for s, p in sorted(jcurves.items())]
    save(fn, sp)
    man["variants"].sort(key=lambda v: v["id"])
    man["version"] = "0.3.0"
    if "task avpaint" not in man["description"]:
        man["description"] += (
            " Task avpaint (2026-10-28): 21727..21735 are LOOK-ONLY twins (sc3netmod's AVP block) of 21701 / 21726 and "
            "21718..21725 on the stock base with stock two-way lanes, written on the bends, U-turn ends and slopes of an "
            "avenue band AVL leaves two-way, so it still looks like the avenue. 21736..21741 are the corner + T pieces: "
            "an avenue corner with a plain road meeting the other band right beside it converts one-way as a paved box "
            "(21738..21741 are avenue_junctions box cells 20817 / 20815 / 20814 / 20816 under own ids). Needs "
            "avenue_junctions installed (its curves).")
    save(man_p, man)
    print("manifest: %d variants, %d lane specs, %d avenue lines; new curve shapes %s" % (
        len(man["variants"]), len(man["lanes"]), len(man["avenue_lines"]), sorted(plan.shapes)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("pack")
    b.add_argument("--art-from")
    b.add_argument("--junctions", required=True)
    b.add_argument("--junctions-art")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        cmd_build(a)


if __name__ == "__main__":
    main()
