#!/usr/bin/env python3
r"""avjunc_build.py - the avenue_junctions package for one-way avenues (task avjunc, 2026-10-19): piece table, lane
specs, curves, art, manifest and sc3netmod table lines. Rule: avjunc_rule.py (twin of sc3netmod_avx.c); lane model:
avjunc.py; conventions: re/analysis/AVENUE_LANES.md.

  py -3.12 -m netmod.avjunc_build pieces PACK     scan the shipped cities with the rule (every arm one-way / two-way
                                                  combination of every box) -> PACK/avjunc_pieces.json (ids assigned)
  py -3.12 -m netmod.avjunc_build build PACK      lane specs, curves, art, manifest.json from avjunc_pieces.json
  py -3.12 -m netmod.avjunc_build check PACK      every spec compiles in ENGLISH and English-UK with y-0 curves,
                                                  every in-lane has an exit, noses meet avcore's 21700 (avlanes.check)

Pieces (all ROAD variants, all four states by rotation, saved as their base at the same state):
  box cells   base 43 / 39 / 11203 / 29 by the closed edges (avjunc_rule.canonical / save_base); lanes from the cell's
              edge modes (avjunc.cell_lanes); art = the AVX box painter for its outline (avx.Box)
  noses       base 11204: one-way (avcore's 21700 lanes) with the median nose at E, W, both or none; two-way (11204's
              own lanes) at E (20810), W (20811), both
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from netmod import avjunc as M          # noqa: E402
from netmod import avjunc_rule as R     # noqa: E402

BOX_IDS = list(range(20805, 20810)) + list(range(20812, 20850)) + list(range(21750, 21800))
NOSE_OW = {"": 20800, "E": 20801, "W": 20802, "EW": 20803}     # one-way half, median nose at those ends (state 0)
NOSE_TW = {"E": 20810, "W": 20811, "EW": 20804}                # two-way (stock 11204 lanes)
# link noses: the same, written on a LINK cell of a segment (a stock 39 / 43 joining the two halves). Own ids so a
# reloaded layout segments as the stock one: a nose on a straight pair stays a band row, a link nose stays a link
NOSE_OW_LINK = {"": 21771, "E": 21772, "W": 21773, "EW": 21774}
NOSE_TW_LINK = {"": 21778, "E": 21775, "W": 21776, "EW": 21777}


def all_noses(T):
    """-> [(ends, piece, oneway, link)]"""
    out = [(e, p, 1, 0) for e, p in sorted(T["nose_oneway"].items())]
    out += [(e, p, 0, 0) for e, p in sorted(T["nose_twoway"].items())]
    out += [(e, p, 1, 1) for e, p in sorted(NOSE_OW_LINK.items())]
    out += [(e, p, 0, 1) for e, p in sorted(NOSE_TW_LINK.items())]
    return out
SHAPE0 = 23700
FLAG = 1                                            # TrBlkAtt flag of box cells, as stock junctions (use UNKNOWN)
SHAPE_MAX = 23799
SIDE_NAMES = M.SIDES                                            # lanekit side names in SIMNTWRK order


def nesw_to_d(t):
    """per-side string N E S W -> SIMNTWRK order x- z- x+ z+ (W N E S); modes I -> N (avjunc.py letters)"""
    s = t[3] + t[0] + t[1] + t[2]
    return s.replace("I", "N")


# ------------------------------------------------------------------------------------------------ piece table

def cmd_pieces(a):
    import glob
    from netmod import avx
    E = avx._env()
    saves = sorted(glob.glob(os.path.join(E["g"], "Cities", "*.sc3")))
    need, stats, nose_need = R.scan(saves, E["ids"])
    keys = sorted(need, key=lambda k: (-need[k], k))
    if len(keys) > len(BOX_IDS):
        raise SystemExit("%d box pieces needed, %d ids" % (len(keys), len(BOX_IDS)))
    rows = []
    for pid, (o, m) in zip(BOX_IDS, keys):
        rows.append({"id": pid, "outline": o, "modes": m, "base": R.save_base(o), "cells_all_oneway": need[(o, m)]})
    out = {"_": "avjunc_build.py pieces: box cells by outline (I another box cell, A arm, C closed) and edge modes "
                "(I 2 lanes in, O 2 out, T two-way, C closed), N E S W at state 0; cells_all_oneway = cells in the 15 "
                "shipped cities with every avenue arm one-way (0: needed only when an arm stays two-way)",
           "box": rows,
           "nose_oneway": NOSE_OW, "nose_twoway": NOSE_TW,
           "scan": stats}
    p = os.path.join(a.pack, "avjunc_pieces.json")
    json.dump(out, open(p, "w", newline="\n"), indent=1)
    print("wrote %s: %d box pieces, %d one-way with every arm one-way" % (p, len(rows),
                                                                         sum(1 for r in rows if r["cells_all_oneway"])))


def table(pack):
    return json.load(open(os.path.join(pack, "avjunc_pieces.json")))


# ------------------------------------------------------------------------------------------------ lanes

# corner junctions (task avjunc corners): the outer cell of an avenue corner that is a T / X with roads (avjunc_rule
# corner_at). (id, outline, modes) at state 0, base = the stock piece (its art too: no new art)
CORNERS = [(21768, "ACAA", "ICTO", 39), (21769, "ACAA", "TCOI", 39), (21770, "AAAA", "ITTO", 43)]


def box_lanes(outline, modes, corner=False):
    """-> [(e, a, f, b, kind)] in SIMNTWRK sides, lanekit coords, state 0"""
    return M.cell_lanes(nesw_to_d(modes), corner)


def lane_pts(e, a, f, b):
    return M.bezier(a, M.opp(e), b, f, 9)


class CurvePlan:
    """new VPathAtt shapes for the lane geometries the stock libraries lack (per language, AVENUE_LANES.md 2: no path
    keys; a UK lane needs a curve that runs forward in English-UK's library = a new shape whose ENGLISH geometry is
    the lane reversed)"""

    def __init__(self, game):
        self.g = game
        self.en = game.paths("ENGLISH")
        self.uk = game.paths("English-UK")
        self.shapes = {}                    # shape -> pts (ENGLISH geometry, state 0)
        self.by_geom = {}                   # (a, b, "en"|"uk") -> shape
        self.next = SHAPE0

    @staticmethod
    def _good(lib, a, b):
        hits = lib.find("veh", a, b)
        if not hits:
            return None
        k = hits[0]
        return k if all(p[1] == 0 for p in lib.veh[k]["pts"]) else False

    def _rot_variants(self, a, b):
        out = []
        for k in range(4):
            out.append((M.rot_pt(a, k), M.rot_pt(b, k), k))
        return out

    def need(self, e, a, f, b):
        """make sure lane a -> b (state 0) finds a y-0 curve in both languages at every rotation"""
        pts = lane_pts(e, a, f, b)
        for lang, lib in (("en", self.en), ("uk", self.uk)):
            if (tuple(a), tuple(b), lang) in self.by_geom:
                continue
            ok = all(self._good(lib, ra, rb) for ra, rb, _ in self._rot_variants(a, b))
            if ok:
                continue
            bad = [self._good(lib, ra, rb) for ra, rb, _ in self._rot_variants(a, b)]
            if any(v is False for v in bad):
                raise SystemExit("lane %s -> %s: a curve with these end points exists in %s but leaves y 0; lanekit "
                                 "would take it (give the lane a via point)" % (a, b, lang))
            if self.next > SHAPE_MAX:
                raise SystemExit("out of curve shapes")
            s = self.next
            self.next += 1
            geom = pts if lang == "en" else [[p[0], p[1], p[2]] for p in pts[::-1]]
            self.shapes[s] = geom
            self.by_geom[(tuple(a), tuple(b), lang)] = s
            # register in this game's libraries so later lanes and the check see it (hwlanes rotations, UK reversed)
            from netmod import hwlanes as HL
            HL.inject(self.g, {"curves": [{"shape": s, "pts": geom}]})


def box_spec(pid, outline, modes, base, game, plan, ped, corner=False):
    lanes = box_lanes(outline, modes, corner)
    veh = []
    for e, a, f, b, kind in lanes:
        plan.need(e, a, f, b)
        veh.append({"from": list(a), "to": list(b)})
    mat = sorted({(e, f) for e, _, f, _, _ in lanes})
    spec = {
        "_": "avjunc_build.py: box cell outline %s modes %s (N E S W, state 0), saved as %d" % (outline, modes, base),
        "piece": pid, "states": [0, 1, 2, 3], "flag": FLAG, "mirror_uk": False,
        "vehicle": {"class": "car", "speed": M.SPEED, "lanes": veh},
        "pedestrian": ped,
        "connects": {"road": {"low": [[SIDE_NAMES[e], SIDE_NAMES[f]] for e, f in mat],
                              "high": [[SIDE_NAMES[f], SIDE_NAMES[e]] for e, f in mat]}},
    }
    return spec, lanes


def nose_spec(pid, oneway, game):
    from netmod import avlanes as AL
    if oneway:
        sp = json.loads(json.dumps(AL.specs(game)[AL.PIECE_STRAIGHT]))
        sp["piece"] = pid
        sp["_comment"] = "avjunc_build.py: one-way half with a median nose = avcore's 21700 lanes (AVENUE_LANES.md 2)"
        return sp
    return None                                     # two-way noses: trblkatt copy_base (stock 11204 lanes)


# ------------------------------------------------------------------------------------------------ art

def nose_frame(ends, z, r):
    """avx.arm_frame for any set of nose ends ('E', 'W'): 11204 (state 0) with the median grass within NOSE of each
    end repainted as road 29's sidewalk, the centre line as white dashes"""
    from netmod import netart as NA
    from netmod import diagave_paint as P
    from netmod import lanelines as LL
    from netmod import avx as X
    im, (L, T) = NA.stock_frames(11204)[(z, r)]
    out = im.copy()
    px = out.load()
    for y in range(out.height):
        for xx in range(out.width):
            c = px[xx, y]
            if c[3] < 128:
                continue
            line = X._yellowish(c)
            if not line and not X._median_grass(c):
                continue
            u, v = NA.unproject(z, xx + 0.5 - L, y + 0.5 - T)
            u, v = NA.rot_uv(u, v, -r % 4)
            lx, lz = (1.0 - u) * 256.0, v * 256.0
            if line:
                if -1.0 <= lx <= 257.0 and X.LINE_BAND_Z[0] <= lz <= X.LINE_BAND_Z[1]:
                    px[xx, y] = LL.dashed(z, lx / 256.0, lz / 256.0, lx / 256.0, True,
                                          lambda: X._asphalt_fill(z, r, min(255.5, max(0.5, lx)), lz))
                continue
            if not ends or not (-1.0 <= lx <= 257.0 and -1.0 <= lz <= X.MEDIAN):
                continue
            near = min([256.0 - lx] * ("E" in ends) + [lx] * ("W" in ends))
            if near < X.NOSE:
                s = P.STOCK(29, 0, z, r, min(255.5, max(0.5, lx)), max(0.5, lz))
                if s[3]:
                    px[xx, y] = (s[0], s[1], s[2], 255)
    return out, (L, T)


def paint_nose(d, ends):
    from netmod import netart as NA
    from netmod import diagave as D
    os.makedirs(d, exist_ok=True)
    anc = {}
    for z in range(NA.ZOOMS):
        for r in range(NA.ROTS):
            im, LT = nose_frame(ends, z, r)
            im.save(os.path.join(d, NA.frame_name(z, r)))
            anc[NA.frame_name(z, r)] = list(LT)
    D._write_anchors(d, anc, "avjunc_build.py: 11204 with the median nose at %s" % (ends or "no end"))


def paint_box(d, outline):
    from netmod import diagave_paint as P
    from netmod import diagave as D
    from netmod import avx as X
    anc = P.paint_cell(X.Box(outline), (0, 0), d)
    D._write_anchors(d, anc, "avjunc_build.py: box cell outline %s (avx.Box)" % outline)


# ------------------------------------------------------------------------------------------------ build

def table_lines(T):
    """sc3netmod table lines (sc3netmod_avx.c): avxm box pieces, avxn noses, avlj one-way avenue edges for avcore"""
    out = []
    for r in T["box"]:
        out.append("avxm %d %s %s" % (r["id"], r["outline"], r["modes"]))
    for ends, pid, ow, link in all_noses(T):
        out.append("avxn %d %s %d %d" % (pid, "".join("1" if s in ends else "0" for s in "NESW"), ow, link))
    for r in T["box"]:                                  # AVENUE_LANES.md 5: the avenue edges (I / O) of each piece
        lj = "".join(m if (o == "A" and m in "IO") else "." for o, m in zip(r["outline"], r["modes"]))
        if lj != "....":
            out.append("avlj %d %s" % (r["id"], lj))
    for ends, pid, ow, link in all_noses(T):            # state 0: traffic -x, enters across E, leaves across W
        if ow:
            out.append("avlj %d .I.O" % pid)
    for pid, o, m, base in CORNERS:                     # corner junctions
        out.append("avxk %d %s %s" % (pid, o, m))
        out.append("avlj %d %s" % (pid, "".join(c if c in "IO" else "." for c in m)))
    return out


def cmd_build(a):
    from netmod import lanekit as LK
    from netmod import avlanes as AL
    T = table(a.pack)
    game = LK.Game()
    plan = CurvePlan(game)
    peds = {b: AL._stock_ped(game, b) for b in (43, 39, 11203, 29)}
    variants, lanes_entries = [], []
    art_root = os.path.join(a.pack, "art")
    outlines = {}
    nlanes = 0
    for r in T["box"]:
        spec, ln = box_spec(r["id"], r["outline"], r["modes"], r["base"], game, plan, peds[r["base"]])
        nlanes += len(ln)
        fn = "box_%d.lanes.json" % r["id"]
        json.dump(spec, open(os.path.join(a.pack, fn), "w", newline="\n"), indent=1)
        lanes_entries.append({"piece": r["id"], "spec": fn})
        variants.append({"id": r["id"], "base": r["base"], "network": "ROAD",
                         "name": {"*": "Avenue crossing", "ENGLISH": "Cruce de avenidas"},
                         "art": {"from": 43, "png_dir": "art/%d" % r["id"]}, "trblkatt": "copy_base"})
        outlines.setdefault(r["outline"], []).append(r["id"])
    for pid, o, m, base in CORNERS:                     # corner junctions: stock art of the T / X
        spec, ln = box_spec(pid, o, m, base, game, plan, peds[base], corner=True)
        spec["_"] = "avjunc_build.py: avenue corner outer cell outline %s modes %s (N E S W, state 0), saved as %d" % (o, m, base)
        nlanes += len(ln)
        fn = "corner_%d.lanes.json" % pid
        json.dump(spec, open(os.path.join(a.pack, fn), "w", newline="\n"), indent=1)
        lanes_entries.append({"piece": pid, "spec": fn})
        variants.append({"id": pid, "base": base, "network": "ROAD",
                         "name": {"*": "Avenue corner junction", "ENGLISH": "Esquina de avenida"},
                         "art": {"from": base}, "trblkatt": "copy_base"})
    # curves: one spec carries every new shape (netpack_lanes collects curves from all specs)
    if plan.shapes:
        first = os.path.join(a.pack, lanes_entries[0]["spec"])
        sp = json.load(open(first))
        sp["curves"] = [{"shape": s, "pts": p} for s, p in sorted(plan.shapes.items())]
        json.dump(sp, open(first, "w", newline="\n"), indent=1)
    for ends, pid, ow, link in all_noses(T):
        if ow:
            sp = nose_spec(pid, True, game)
            fn = "nose_%d.lanes.json" % pid
            json.dump(sp, open(os.path.join(a.pack, fn), "w", newline="\n"), indent=1)
            lanes_entries.append({"piece": pid, "spec": fn})
            variants.append({"id": pid, "base": 11204, "network": "ROAD",
                             "name": {"*": "Avenue (one way)", "ENGLISH": "Avenida (un sentido)"},
                             "art": {"from": 11204, "png_dir": "art/%d" % pid}, "trblkatt": "copy_base"})
        else:
            variants.append({"id": pid, "base": 11204, "network": "ROAD", "name": {"*": "Avenue", "ENGLISH": "Avenida"},
                             "art": {"from": 11204, "png_dir": "art/%d" % pid}, "trblkatt": "copy_base"})
    variants.sort(key=lambda v: v["id"])
    man_p = os.path.join(a.pack, "manifest.json")
    man = json.load(open(man_p))
    man["version"] = "0.2.0"
    man["author"] = "netmod (task avx, task avjunc)"
    man["description"] = (
        "Avenue junctions as one paved box (task avx), reworked for one-way avenues (task avjunc, 2026-10-19: 2 lanes "
        "each way, right-hand traffic). sc3netmod's AVX block finds every junction on a straight avenue (road x avenue, "
        "road T, T's offset by a cell, avenue x avenue, avenue T, an avenue ending on a road), paves it across both "
        "halves (the median opening: every turn and U-turn works inside the box) and gives each box cell the lanes of its "
        "edges: two lanes in, two out, two-way or closed. Avenue x avenue boxes form a one-way ring. The halves beside "
        "a box carry the median nose (one-way, avcore's lanes). An arm whose avenue avcore leaves two-way gets two-way "
        "edges. Box cells save as 43 / 39 / 11203 / 29, noses as 11204, so a game without the mod loads stock junctions. "
        "Build: `py -3.12 -m netmod.avjunc_build build .` in re/tools (art from the game's frames, not shipped).")
    man["variants"] = variants
    man["lanes"] = lanes_entries
    man.pop("auto_avenue_junctions", None)
    lines = table_lines(T)
    man["avenue_junction_lines"] = [ln for ln in lines if ln.startswith("avx")]
    man["avenue_lines"] = [ln for ln in lines if ln.startswith("avlj")]           # avcore's key (AVENUE_LANES.md 5)
    json.dump(man, open(man_p, "w", newline="\n"), indent=1)
    for old in ("box_20800.lanes.json", "box_20801.lanes.json", "box_20802.lanes.json", "box_20803.lanes.json",
                "box_20804.lanes.json"):
        pth = os.path.join(a.pack, old)
        if os.path.exists(pth) and not any(e["spec"] == old for e in lanes_entries):
            os.remove(pth)
    print("specs: %d box pieces (%d lanes), %d one-way noses; new curve shapes %s" % (
        len(T["box"]), nlanes, len(T["nose_oneway"]), sorted(plan.shapes)))
    if a.no_art:
        return
    for outline, ids in sorted(outlines.items()):
        d0 = os.path.join(art_root, str(ids[0]))
        paint_box(d0, outline)
        for pid in ids[1:]:
            d = os.path.join(art_root, str(pid))
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(d0, d)
        print("art: outline %s -> %s" % (outline, ids))
    done = {}
    for ends, pid, ow, link in all_noses(T):
        d = os.path.join(art_root, str(pid))
        if ends in done:                                 # a link nose looks like the nose with the same ends
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(done[ends], d)
        else:
            paint_nose(d, ends)
            done[ends] = d
        print("art: nose %s -> %d" % (ends or "-", pid))


# ------------------------------------------------------------------------------------------------ check

def check_art(pack, T):
    """task avxroad (owner img3, 2026-10-26): every box id's art must be the paint of ITS outline. 28 of 61 ids carried
    the art of another outline (anchors.json named it: 21750 ACAI held AIII's), from an earlier id assignment, so the
    owner saw bare slabs with no crosswalk or curb. paint_box writes the outline into anchors.json; compare it. No art
    dir (not built here) is skipped. -> problems"""
    bad = 0
    for r in T["box"]:
        p = os.path.join(pack, "art", str(r["id"]), "anchors.json")
        if not os.path.isfile(p):
            continue
        note = json.load(open(p)).get("_", "")
        if "outline %s " % r["outline"] not in note:
            print("art %d: table outline %s, art painted for %r (rebuild: avjunc_build build)" % (r["id"], r["outline"], note))
            bad += 1
    return bad


def cmd_check(a):
    from netmod import lanekit as LK
    from netmod import avlanes as AL
    from netmod import hwlanes as HL
    T = table(a.pack)
    game = LK.Game()
    man = json.load(open(os.path.join(a.pack, "manifest.json")))
    specs = {e["piece"]: json.load(open(os.path.join(a.pack, e["spec"]))) for e in man["lanes"]}
    for sp in specs.values():
        if sp.get("curves"):
            HL.inject(game, sp)
    bad = 0
    for lang in ("ENGLISH", "English-UK"):
        P = game.paths(lang)
        for pid, sp in sorted(specs.items()):
            try:
                out = LK.compile_spec(sp, game, lang)
            except LK.LaneError as ex:
                print("%s %d: %s" % (lang, pid, ex))
                bad += 1
                continue
            rec = out["rec0"]
            for n in rec["veh"]:
                for ed in n["edges"]:
                    if ed["to"] is None:
                        continue
                    c = P.veh[ed["path"]]
                    m = rec["veh"][ed["to"]]
                    ends_ok = (c["pts"][0][0], c["pts"][0][2]) == (n["x"], n["z"]) and \
                              (c["pts"][-1][0], c["pts"][-1][2]) == (m["x"], m["z"])
                    if not ends_ok or any(p[1] != 0 for p in c["pts"]):
                        print("%s %d: lane (%d,%d)->(%d,%d) on curve %d %s" % (lang, pid, n["x"], n["z"], m["x"], m["z"],
                                                                            ed["path"], c["pts"][:2]))
                        bad += 1
            ins = [n for n in rec["veh"] if n["edges"] and all(e["to"] is not None for e in n["edges"])]
            for n in rec["veh"]:
                if not n["edges"]:
                    print("%s %d: node (%d,%d) has no edge" % (lang, pid, n["x"], n["z"]))
                    bad += 1
    # noses against avcore's straight half, both languages, every state, both along sides
    for ends, pid in list(T["nose_oneway"].items()) + list(NOSE_OW_LINK.items()):
        for lang in ("ENGLISH", "English-UK"):
            for s in range(4):
                d = "NESW"[AL.half_dir(s)]
                ob = {"N": "S", "S": "N", "E": "W", "W": "E"}[d]
                for pr in (AL.check(specs[pid], s, AL.specs(game)[AL.PIECE_STRAIGHT], s, d, game, lang),
                           AL.check(AL.specs(game)[AL.PIECE_STRAIGHT], s, specs[pid], s, d, game, lang)):
                    for p in pr:
                        print(lang, p)
                        bad += 1
    bad += check_art(a.pack, T)
    print("check:", "PASSED" if not bad else "%d problem(s)" % bad)
    return 0 if not bad else 1


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["pieces", "build", "check"])
    ap.add_argument("pack")
    ap.add_argument("--no-art", action="store_true")
    a = ap.parse_args(argv)
    return {"pieces": cmd_pieces, "build": cmd_build, "check": cmd_check}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
