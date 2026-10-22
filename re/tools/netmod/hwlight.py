#!/usr/bin/env python3
r"""hwlight.py - LIT TWINS of highway-program pieces (task hwlight, owner bug img11, 2026-10-21).

Why. Stock wall shading follows the wall's WORLD axis: an outer wall toward +-x (73) reads about 135 grey in every
view, toward +-z (15051) about 78 (`hwpaint.py lit`). A piece's frame is shared by (state + view), so art painted at
state 0 is lit right at states 0 / 2 only; at 1 / 3 its walls keep the other axis' shade. The blocks write one painted
set at all four states (hwave, hwt, the hwx / hwdx ramps, hwdd), hence light ramp walls beside dark stock walls.

Fix. Every such piece P gets a twin T: same base, lanes, turn matrix and NETRAMP class, art painted from the scene
turned one state (hwpaint.paint_twin). sc3netmod writes T where a block writes P at an odd state and every reader sees
P (`hwyl P T`, sc3netmod_hwy.c / sc3netmod_rbt.c hwlt_*); saves use P's own hwyp / hwys entry.

The twins of a package are listed in <package>/lit_twins.json: {"pieces": {"<P>": <T>, ...}}. This tool keeps the
package manifest in step with it (idempotent: previous twin entries are replaced):
  variants    a copy of P's entry with id T, png_dir art/<T>
  lanes       {"piece": T, "spec": P's spec}       (netpack accepts a curve shape defined twice when identical)
  connects    a copy of P's entry with piece T
  highway_lines   "hwrc T" where P has one; "hwyl P T" (after every hwyp line)
  avenue_lines    "avlj T ..." where P has one

  py -3.12 hwlight.py twart <package_dir> [--jobs N]   paint the twins' art (after the package's own art; then its
                                                   pad step if it has one): highway_avenue (hwave_build twart),
                                                   hwt_trumpet, hwx_cloverleaf, highway_diagonal_cloverleaf,
                                                   highway_dd_cloverleaf
  py -3.12 hwlight.py manifest <package_dir>       write the twin entries into <package_dir>/manifest.json
  py -3.12 hwlight.py check <package_dir>          every twin's art shows its piece's geometry (hwpaint.twin_check)
  py -3.12 hwlight.py ids                          the twin ids of every package (range 26000..26399)
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

ID0, ID1 = 26000, 26399          # task hwlight twin ids (free in every worktree on 2026-10-21)


def twins(pkg):
    p = os.path.join(pkg, "lit_twins.json")
    if not os.path.isfile(p):
        return {}
    return {int(k): int(v) for k, v in json.load(open(p, encoding="utf-8"))["pieces"].items()}


def _first(line):
    t = line.split()
    return int(t[1]) if len(t) > 1 and t[1].isdigit() else None


def cmd_manifest(a):
    tw = twins(a.pkg)
    if not tw:
        raise SystemExit("%s: no lit_twins.json" % a.pkg)
    tset = set(tw.values())
    if not all(ID0 <= t <= ID1 for t in tset) or len(tset) != len(tw):
        raise SystemExit("twin ids must be distinct and in %d..%d" % (ID0, ID1))
    mp = os.path.join(a.pkg, "manifest.json")
    raw = open(mp, "rb").read()
    man = json.loads(raw.decode("utf-8"))
    crlf = b"\r\n" in raw
    # drop the previous twin entries
    man["variants"] = [v for v in man["variants"] if v["id"] not in tset]
    for k in ("lanes", "connects"):
        if k in man:
            man[k] = [e for e in man[k] if e.get("piece") not in tset]
    for k in ("highway_lines", "avenue_lines"):
        if k in man:
            man[k] = [ln for ln in man[k] if not (ln.startswith("hwyl ") or _first(ln) in tset)]
    byid = {v["id"]: v for v in man["variants"]}
    missing = sorted(p for p in tw if p not in byid)
    if missing:
        raise SystemExit("pieces without a variant entry: %s" % missing)
    for p, t in sorted(tw.items()):
        v = json.loads(json.dumps(byid[p]))
        v["id"] = t
        if isinstance(v.get("art"), dict) and "png_dir" in v["art"]:
            v["art"]["png_dir"] = "art/%d" % t
        nm = v.get("name")
        if isinstance(nm, dict) and "*" in nm:
            nm["*"] = nm["*"] + " (lit twin of %d)" % p
        man["variants"].append(v)
    for k in ("lanes", "connects"):
        if k not in man:
            continue
        add = []
        for e in man[k]:
            if e.get("piece") in tw:
                c = json.loads(json.dumps(e))
                c["piece"] = tw[e["piece"]]
                add.append(c)
        man[k] += add
    hl = man.get("highway_lines", [])
    hl += ["hwrc %d" % tw[_first(ln)] for ln in list(hl) if ln.startswith("hwrc ") and _first(ln) in tw]
    hl += ["hwyl %d %d" % (p, t) for p, t in sorted(tw.items())]
    man["highway_lines"] = hl
    if "avenue_lines" in man:
        al = man["avenue_lines"]
        al += [" ".join(["avlj", str(tw[_first(ln)])] + ln.split()[2:]) for ln in list(al)
               if ln.startswith("avlj ") and _first(ln) in tw]
    out = json.dumps(man, indent=1, ensure_ascii=False) + "\n"
    if crlf:
        out = out.replace("\n", "\r\n")
    open(mp, "wb").write(out.encode("utf-8"))
    print("%s: %d twins -> %d variants, %d highway lines" % (mp, len(tw), len(man["variants"]), len(hl)))
    return 0


# the stock end caps turned one state (as 73 <-> 15051, TURN1 in hwpaint: same lane, the outward step turned)
CAPTURN = {(11235, 0): (15053, 0), (11235, 2): (15053, 2), (11237, 0): (15054, 0), (11237, 2): (15054, 2),
           (15053, 0): (11235, 2), (15053, 2): (11235, 0), (15054, 0): (11237, 2), (15054, 2): (11237, 0),
           (14999, 0): (15059, 0), (14999, 2): (15059, 2), (15059, 0): (14999, 2), (15059, 2): (14999, 0)}


def twin_art(scene, cell, dst, cap=None, render=None):
    """the twin's art of world cell `cell` of `scene` into dst. cap = (stock cap, state) whose end face a capped piece
    composes over its painted frames (hwcap_art.compose_straight): the twin composes the cap turned with it"""
    import shutil
    from netmod import hwpaint as HP
    if not cap:
        return HP.paint_twin(scene, cell, dst, render=render)
    from netmod import hwcap_art as CA
    from netmod import netart as NA
    tmp, keep = dst + "_turned", dst + "_turned_painted"
    for d in (tmp, keep, dst):
        if os.path.isdir(d):
            shutil.rmtree(d)
    HP.paint_cell(HP.turn_scene(scene, 1), HP.turn_cell(cell, 1), tmp)       # the turned world, views as painted
    CA.compose_straight(tmp, keep, *CAPTURN[tuple(cap)])
    os.makedirs(dst)
    a = json.load(open(os.path.join(tmp, "anchors.json")))
    out = {}
    for z in range(NA.ZOOMS):
        for g in range(NA.ROTS):
            src, name = NA.frame_name(z, g), NA.frame_name(z, (g + 1) % NA.ROTS)
            shutil.copyfile(os.path.join(tmp, src), os.path.join(dst, name))
            out[name] = a[src]
    json.dump(out, open(os.path.join(dst, "anchors.json"), "w"), indent=1)
    shutil.rmtree(tmp)
    shutil.rmtree(keep)


def _done(d):
    p = os.path.join(d, "anchors.json")
    return os.path.isfile(p) and len(json.load(open(p))) == 20


def _jobs(a, items, fn, dst=None):
    """run fn(item) for items, sharded over a.jobs processes (each re-runs this tool on its shard); dst(item) = the
    item's art folder: finished ones (all 20 frames) are skipped, so a failed run resumes"""
    import subprocess
    import traceback
    if dst:
        items = [it for it in items if not _done(dst(it))]
    if a.shard:
        i, n = map(int, a.shard.split("/"))
        bad = 0
        for it in items[i::n]:
            try:
                fn(it)
            except Exception:
                traceback.print_exc()
                bad += 1
        return 1 if bad else 0
    procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), "twart", a.pkg, "--shard", "%d/%d" % (i, a.jobs)])
             for i in range(a.jobs)]
    rc = [p.wait() for p in procs]
    print("twart: %d items, shard exit codes %s" % (len(items), rc))
    return 1 if any(rc) else 0


def cmd_twart(a):
    name = os.path.basename(os.path.normpath(a.pkg))
    tw = twins(a.pkg)
    art = lambda pid: os.path.join(a.pkg, "art", str(tw[pid]))     # noqa: E731
    sys.path.insert(0, HERE)
    if name == "highway_avenue":
        import hwave_build
        return hwave_build.cmd_twart(a)
    if name == "hwt_trumpet":
        import hwt_build as B
        import hwt_cells
        import hwt_paint as T
        items = [("cell", r) for r in hwt_cells.CELLS if r["id"] in tw] + [("cap", c) for c in B.capped() if c["id"] in tw]
        scenes = {}

        def one(it):
            kind, r = it
            if kind == "cell":
                if r["scene"] not in scenes:
                    scenes[r["scene"]] = T.scene(rio=r["scene"] == "rio")[0]
                twin_art(scenes[r["scene"]], (r["dx"], r["dz"]), art(r["id"]))
            else:
                if "cap" not in scenes:
                    scenes["cap"] = T.scene(extent=B.CAP_EXTENT)[0]
                twin_art(scenes["cap"], (r["dx"], r["dz"]), art(r["id"]), cap=(r["base"], r["base_st"]))
            print("twin", tw[r["id"]], "of", r["id"], flush=True)
        return _jobs(a, items, one, lambda it: art(it[1]["id"]))
    if name == "hwx_cloverleaf":
        import hwx
        import hwx_build as B
        items = [(pid, p) for pid, p in sorted(B.pieces().items()) if pid in tw]
        st = {}

        def one(it):
            pid, p = it
            if not st:
                st["sc"] = hwx.scene()
                st["boxes"] = [hwx._deck_box(dk) for dk in st["sc"].decks]
            if p["cls"] == "capped":
                raise SystemExit("hwx capped piece %d sits at the cap's state (0 / 2): it needs no twin" % pid)
            twin_art(B._near(st["sc"], st["boxes"], p["ref"]), p["ref"], art(pid))
            print("twin", tw[pid], "of", pid, flush=True)
        return _jobs(a, items, one, lambda it: art(it[0]))
    if name == "highway_diagonal_cloverleaf":
        from netmod import hwdx as H
        from netmod import hwdx_paint as D
        items = [p for p in H.pieces_list() if p["id"] in tw]
        cache = {}

        def one(p):
            if p.get("capped"):
                raise SystemExit("hwdx capped join %d has a flavour per parity: it needs no twin" % p["id"])
            case, c = p["rep"]
            key = (case, p["r"])
            if key not in cache:
                cache[key] = D.scene(case, p["r"], False)
            twin_art(cache[key], H.to_world((0, 0), p["r"], c), art(p["id"]))
            print("twin", tw[p["id"]], "of", p["id"], flush=True)
        return _jobs(a, items, one, lambda p: art(p["id"]))
    if name == "highway_dd_cloverleaf":
        import hwdd
        import hwdd_paint as DD
        items = [p for p in DD.pieces() if p[0] in tw]
        scenes = {}

        def one(p):
            pid, par, fly, rep, states, base, land = p
            if (par, fly) not in scenes:
                scenes[(par, fly)] = DD.scene(hwdd.Geo(par), flyover=fly)
            twin_art(DD.local(scenes[(par, fly)], rep), rep, art(pid))
            print("twin", tw[pid], "of", pid, flush=True)
        return _jobs(a, items, one, lambda p: art(p[0]))
    raise SystemExit("twart: no twin painter for package %s" % name)


def cmd_check(a):
    from netmod import hwpaint as HP
    bad = 0
    for p, t in sorted(twins(a.pkg).items()):
        pd, td = os.path.join(a.pkg, "art", str(p)), os.path.join(a.pkg, "art", str(t))
        if not os.path.isdir(td):
            print("%d -> %d: NO ART" % (p, t))
            bad += 1
            continue
        out, b = HP.twin_check(pd, td)
        worst = max(out.values()) if out else 1.0
        print("%d -> %d: %d frames, worst coverage mismatch %.4f%s" % (p, t, len(out), worst, "  BAD %s" % sorted(b) if b else ""))
        bad += bool(b) or not out
    return 1 if bad else 0


def cmd_ids(a):
    seen = {}
    for f in sorted(glob.glob(os.path.join(HERE, "examples", "*", "lit_twins.json"))):
        pkg = os.path.dirname(f)
        tw = twins(pkg)
        print("%-34s %3d twins  %s" % (os.path.basename(pkg), len(tw),
                                       "%d..%d" % (min(tw.values()), max(tw.values())) if tw else ""))
        for t in tw.values():
            if t in seen:
                print("  ### id %d also in %s" % (t, seen[t]))
            seen[t] = os.path.basename(pkg)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hwlight.py")
    ap.add_argument("cmd", choices=("twart", "manifest", "check", "ids"))
    ap.add_argument("pkg", nargs="?")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--shard")
    a = ap.parse_args(argv)
    return {"twart": cmd_twart, "manifest": cmd_manifest, "check": cmd_check, "ids": cmd_ids}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
