#!/usr/bin/env python3
r"""avends_build.py - the avenue_ends package (task avends, 2026-11-09): pieces for the avenue ends AVL used to leave
two-way (round brief ROUND_2026-11-09_avends.md, groups B / E / A). Lanes / art by avjunc_build.py's own functions
(the same box-cell lane model and box painter as avenue_junctions / avenue_diamond).

  py -3.12 -m netmod.avends_build build PACK [--no-art]    lane specs, curves (shapes 26500..), art, manifest.json
  py -3.12 -m netmod.avends_build lines PACK               the table lines the manifest declares

PACK/avends_pieces.json (kept by hand, ids are stable: saved cities hold them):
  "ct":  corner + T cells (sc3netmod_avl.c `avlt`): {"id", "outline", "modes", "base", "why"}
  "box": AVX box cells (`avxm` + `avlj` on the avenue edges): {"id", "outline", "modes", "base", "why"}
Ids 22000..22099 (the brief's 20900..20999 is taken by boulevard_junctions / diagonal_boulevard in the installed tables).
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from netmod import avjunc_build as AB   # noqa: E402

IDS = range(22000, 22100)
SHAPE0, SHAPE_MAX = 26500, 26999
JUNC = os.path.join(HERE, "examples", "avenue_junctions")


def table_lines(T):
    out = []
    for r in T.get("box", []):
        out.append("avxm %d %s %s" % (r["id"], r["outline"], r["modes"]))
    for r in T.get("ct", []):
        out.append("avlt %d %s %s" % (r["id"], r["outline"], r["modes"]))
    for r in T.get("nt", []):                     # task avends F3: sc3netmod_bv.c `bvn`, avlj on the avenue side
        for pid, lj in sorted(r.get("avlj", {}).items()):
            out.append("avlj %s %s" % (pid, lj))
    for r in T.get("box", []):
        lj = "".join(m if (o == "A" and m in "IO" and e not in r.get("road_edges", [])) else "."
                     for e, (o, m) in enumerate(zip(r["outline"], r["modes"])))
        if lj != "....":
            out.append("avlj %d %s" % (r["id"], lj))
    return out


def cmd_lines(a):
    for ln in table_lines(json.load(open(os.path.join(a.pack, "avends_pieces.json")))):
        print(ln)


def cmd_build(a):
    from netmod import lanekit as LK
    from netmod import avlanes as AL
    T = json.load(open(os.path.join(a.pack, "avends_pieces.json")))
    for r in T.get("box", []) + T.get("ct", []):
        if r["id"] not in IDS:
            raise SystemExit("piece %d outside 22000..22099" % r["id"])
    AB.SHAPE0, AB.SHAPE_MAX = SHAPE0, SHAPE_MAX
    game = LK.Game()
    plan = AB.CurvePlan(game)
    peds = {b: AL._stock_ped(game, b) for b in (43, 39, 11203, 29)}
    variants, lanes_entries, outlines, nlanes = [], [], {}, 0
    for kind, rows in (("box", T.get("box", [])), ("ct", T.get("ct", []))):
        for r in rows:
            spec, ln = AB.box_spec(r["id"], r["outline"], r["modes"], r["base"], game, plan, peds[r["base"]])
            spec["_"] = ("avends_build.py: %s cell, outline %s modes %s (N E S W, state 0), saved as %d. %s" % (
                "AVX box" if kind == "box" else "avenue corner + T", r["outline"], r["modes"], r["base"], r.get("why", "")))
            nlanes += len(ln)
            fn = "%s_%d.lanes.json" % (kind, r["id"])
            json.dump(spec, open(os.path.join(a.pack, fn), "w", newline="\n"), indent=1)
            lanes_entries.append({"piece": r["id"], "spec": fn})
            variants.append({"id": r["id"], "base": r["base"], "network": "ROAD",
                             "name": {"*": "Avenue junction", "ENGLISH": "Cruce de avenida"},
                             "art": {"from": 43, "png_dir": "art/%d" % r["id"]}, "trblkatt": "copy_base"})
            outlines.setdefault(r["outline"], []).append(r["id"])
    for r in T.get("nt", []):                     # task avends F3: specs and art by avends_fbuild.py
        for pid in r["ids"]:
            fn = "bvn_%d.lanes.json" % pid
            if not os.path.exists(os.path.join(a.pack, fn)):
                raise SystemExit("%s missing: run avends_fbuild build first" % fn)
            lanes_entries.append({"piece": pid, "spec": fn})
            variants.append({"id": pid, "base": 43, "network": "ROAD",
                             "name": {"*": "Boulevard to avenue junction", "ENGLISH": "Cruce de bulevar a avenida"},
                             "art": {"from": 43, "png_dir": "art/%d" % pid}, "trblkatt": "copy_base"})
    if plan.shapes:
        first = os.path.join(a.pack, lanes_entries[0]["spec"])
        sp = json.load(open(first))
        sp["curves"] = [{"shape": s, "pts": p} for s, p in sorted(plan.shapes.items())]
        json.dump(sp, open(first, "w", newline="\n"), indent=1)
    junc = json.load(open(os.path.join(JUNC, "manifest.json")))
    lines = table_lines(T)
    man = {
        "netpack": 1, "name": "avenue_ends", "version": "0.1.0", "author": "netmod (task avends)",
        "description": (
            "Avenue ends that used to stay two-way (task avends, 2026-11-09): pieces sc3netmod's AVL / AVX blocks write "
            "where the stock tiler left an irregular end (a corner + T whose linked half is a plain road, ...). "
            "Saved as their stock base, so a game without the mod loads the stock pieces. Needs avenue_lanes and "
            "avenue_junctions. Build: `py -3.12 -m netmod.avends_build build .` in re/tools (art from the game's frames, "
            "not shipped)."),
        "game": junc["game"],
        "variants": sorted(variants, key=lambda v: v["id"]),
        "lanes": lanes_entries,
        "avenue_junction_lines": [ln for ln in lines if ln.startswith("avx")],
        "avenue_lines": [ln for ln in lines if ln.startswith(("avlj", "avlt"))],
        "boulevard_slope_lines": ["bvn %d %s" % (r["keep"], " ".join(str(i) for i in r["ids"])) for r in T.get("nt", [])],
    }
    json.dump(man, open(os.path.join(a.pack, "manifest.json"), "w", newline="\n"), indent=1)
    print("specs: %d pieces (%d lanes); new curve shapes %s" % (len(variants), nlanes, sorted(plan.shapes)))
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


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "lines"])
    ap.add_argument("pack")
    ap.add_argument("--no-art", action="store_true")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "lines": cmd_lines}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
