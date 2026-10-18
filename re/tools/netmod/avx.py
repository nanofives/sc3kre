#!/usr/bin/env python3
r"""avx.py - straight avenue intersections (task avx, 2026-10-17): the junction rule, its pieces, art and lanes, offline
checks. Offline twin of sc3netmod's AVX block (re/harness/src/sc3netmod_avx.c); package examples/avenue_junctions.

Stock (offline tiler, verify/avx/RESULTS.md): two crossing avenues (11204, two parallel roads each) tile as a 2x2 of
43 with T 39 on the four arm cells beside it (four small crossings, medians stop one cell early); a road crossing an
avenue is a column of two 43 with the avenue's 11204 halves running up to it. This block re-pieces those shapes as ONE
paved box: crosswalks across every arm at the box edge, each avenue arm's median ending in a concrete nose on the cell
next to the box, curbs continuous where the box has no arm.

The rule (cells = ROAD cells, "road" below means a ROAD cell):
  box      a w x h rectangle of road, (w, h) = (2, 2), (1, 2) or (2, 1); its four diagonal corner cells hold no road
  side     the w (N / S) or h (W / E) cells just outside one box side: all road (an arm) or none (closed); else no box
  arm      clean and straight for ARM_LEN cells: the run of side cells goes on ARM_LEN cells away from the box, with no
           road flanking it on either side; 2 cells wide = avenue arm, 1 cell wide = road arm
  kinds    (2, 2): 4 avenue arms = avenue x avenue (AxA); 3 = an avenue ending on an avenue (AvT); fewer = left to stock
           (1, 2) and (2, 1): the avenue goes through (both avenue arms) and 2 road arms = road x avenue (RxA), 1 = a road
           ending on the avenue (RT)
  pieces   each box cell by its edge pattern N E S W, each edge I (another box cell), A (an arm cell) or C (closed):
           BOX holds the canonical patterns, a cell gets the one that turns into its pattern, at that turn as state.
           Each avenue arm's first cell (the one beside the box) gets the median-nose piece ARM[box side at state 0] in
           its stock 11204 state; road arm cells stay stock 29.
  refuses  the RBT 2x2 roundabout (its side exits hold one road each: not avenue arms), 3x3 blocks (a corner cell holds
           road), three parallel roads (an arm flank holds road), diagonal shapes (no clean straight arm), junctions
           closer than ARM_LEN cells, cells holding another block's piece (an id >= 20000 that is not ours).

  py -3.12 avx.py build PACK_DIR                art/<id>/ and box_<id>.lanes.json
  py -3.12 avx.py check                         every kind x rotation and the shapes it must refuse, on the offline tiler
  py -3.12 avx.py mockup OUT.png PACK_DIR       owner sheet: stock vs avx per kind, zoom 4 and 3, view 0 and 1
  py -3.12 avx.py scan [SAVE ...]               junctions per save (default: the shipped Cities)
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

EDGES = "NESW"
DIRV = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
ARM_LEN = 2
# canonical box cells (edge pattern N E S W at state 0) -> piece. The three with a closed edge have it on S, so their
# state is the state of the stock 11204 half that edge belongs to (they save as 11204: see SAVE_11204)
BOX = {"AIIA": 20800,       # avenue x avenue / avenue T near side: arms N and W
       "AAIA": 20801,       # road x avenue: road arm N, avenue halves W and E
       "IACA": 20802,       # road T: the avenue's far half, the road comes in from N
       "IACI": 20803,       # avenue T: the through avenue's far half, the other avenue's column on the W
       "IICA": 20804}       # avenue T: the same, the other avenue's column on the E
ARM = {1: 20810, 3: 20811}  # the 11204 half (state 0: median N, outer sidewalk S) with the box on its E / W end
SAVE_11204 = (20802, 20803, 20804)
LANES_OF = {"AIIA": (43, 0), "AAIA": (43, 0), "IACA": (39, 1), "IACI": (39, 1), "IICA": (39, 1)}
NAMES = {20800: "Avenue crossing", 20801: "Avenue crossing", 20802: "Avenue crossing", 20803: "Avenue crossing",
         20804: "Avenue crossing", 20810: "Avenue", 20811: "Avenue"}
OWN = set(BOX.values()) | set(ARM.values())


def rot(desc, k):
    """edge pattern turned k states (N -> E per state)"""
    out = [None] * 4
    for e in range(4):
        out[(e + k) % 4] = desc[e]
    return "".join(out)


def box_piece(desc):
    """-> (piece, state) whose canonical pattern turned by state is `desc`, smallest state first; None if undeclared"""
    for k in range(4):
        for canon, pid in BOX.items():
            if rot(canon, k) == desc:
                return pid, k
    return None


def half_state(e, first):
    """stock 11204 state of an avenue arm cell: arms W / E (e 3 / 1) run along x, row Z is state 2 and row Z+1 state 0;
    arms N / S run along z, column X is state 1 and column X+1 state 3 (offline tiler, verify/avx/RESULTS.md)"""
    if e in (1, 3):
        return 2 if first else 0
    return 1 if first else 3


def side_cells(X, Z, w, h, e):
    if e == 0:
        return [(X + i, Z - 1) for i in range(w)]
    if e == 2:
        return [(X + i, Z + h) for i in range(w)]
    if e == 1:
        return [(X + w, Z + k) for k in range(h)]
    return [(X - 1, Z + k) for k in range(h)]


def check(R, X, Z, w, h, ids=None):
    """box (X, Z, w, h) on road set R -> (junction dict, '') or (None, why)"""
    box = [(X + i, Z + k) for k in range(h) for i in range(w)]
    if not all(c in R for c in box):
        return None, "box not all road"
    for c in ((X - 1, Z - 1), (X + w, Z - 1), (X - 1, Z + h), (X + w, Z + h)):
        if c in R:
            return None, "corner %s holds road" % (c,)
    arms = {}
    for e in range(4):
        side = side_cells(X, Z, w, h, e)
        n = sum(c in R for c in side)
        if n == 0:
            arms[e] = None
            continue
        if n != len(side):
            return None, "side %s partly road" % EDGES[e]
        dx, dz = DIRV[e]
        pdx, pdz = abs(dz), abs(dx)
        for k in range(ARM_LEN):
            run = [(c[0] + dx * k, c[1] + dz * k) for c in side]
            if not all(c in R for c in run):
                return None, "arm %s shorter than %d" % (EDGES[e], ARM_LEN)
            if (run[0][0] - pdx, run[0][1] - pdz) in R or (run[-1][0] + pdx, run[-1][1] + pdz) in R:
                return None, "arm %s has road beside it" % EDGES[e]
        arms[e] = "avenue" if len(side) == 2 else "road"
    av = [e for e in range(4) if arms[e] == "avenue"]
    rd = [e for e in range(4) if arms[e] == "road"]
    if (w, h) == (2, 2):
        kind = {4: "AxA", 3: "AvT"}.get(len(av))
        if not kind:
            return None, "2x2 box with %d avenue arm(s)" % len(av)
    else:
        through = (1, 3) if (w, h) == (1, 2) else (0, 2)
        if any(arms[e] != "avenue" for e in through):
            return None, "the avenue does not go through"
        kind = {2: "RxA", 1: "RT"}.get(len(rd))
        if not kind:
            return None, "no road arm"
    first = {}
    for e in av + rd:
        for i, c in enumerate(side_cells(X, Z, w, h, e)):
            first[c] = (e, i == 0)
    want = {}
    for (cx, cz) in box:
        desc = ""
        for e in range(4):
            n = (cx + DIRV[e][0], cz + DIRV[e][1])
            desc += "I" if n in box else "A" if n in first else "C"
        bp = box_piece(desc)
        if not bp:
            return None, "no box piece for edge pattern %s" % desc
        want[(cx, cz)] = bp
    for c, (e, f) in first.items():
        if arms[e] != "avenue":
            continue
        s = half_state(e, f)
        d0 = ((e + 2) % 4 - s) % 4
        want[c] = (ARM[d0], s)
    if ids is not None:
        for c in want:
            i = ids.get(c, 0)
            if i >= 20000 and i not in OWN:
                return None, "cell %s holds another block's piece %d" % (c, i)
    return {"kind": kind, "box": (X, Z, w, h), "arms": {EDGES[e]: arms[e] for e in range(4) if arms[e]},
            "want": want}, ""


def find(R, ids=None):
    """-> (junctions, refusals): refusals list the boxes that have at least one avenue-wide side and fail, with why"""
    js, refused = [], []
    for (x, z) in sorted(R, key=lambda c: (c[1], c[0])):
        for w, h in ((2, 2), (1, 2), (2, 1)):
            j, why = check(R, x, z, w, h, ids)
            if j:
                js.append(j)
            elif why not in ("box not all road",) and not why.startswith("corner") and \
                    not why.startswith("the avenue does not") and not why.startswith("2x2 box with 0") and \
                    not why.startswith("2x2 box with 1") and not why.startswith("side"):
                refused.append(((x, z, w, h), why))
    return js, refused


# ------------------------------------------------------------------------------------------------ art

LINE_BAND = 40.0          # stock 43's two crosswalk lines lie within this many lane units of its edge (zoom 4 map)
CORNER = 40.0             # 43's corner sidewalk square and the line crossings beside it
LINE_LO, LINE_HI = 56.0, 196.0   # a line is sampled here along its edge: clear of the other edges' lines
CURB_BAND = 52.0          # road 29's sidewalk, curb and edge line from its edge
NOSE = 32.0               # median nose length on the arm cell, lane units from the box edge
MEDIAN = 34.0             # 11204 (state 0): median grass and its curb at lane z < this


def fold(t):
    """43's asphalt is sampled at a point mirrored into its marking-free middle; the same at every cell edge (t 0 and
    256 -> 72), so box cells meet with no seam whatever their states"""
    return 200.0 - abs(t - 128.0)


class Box:
    """A box cell in its own lane frame at state 0, edges `desc` (N E S W)."""

    def __init__(self, desc):
        self.d = desc

    def colour(self, z, r, wx, wz):
        from netmod import diagave_paint as P
        S = P.STOCK
        x, zl = (wx % 1.0) * 256.0, (wz % 1.0) * 256.0
        dist = (zl, 256.0 - x, 256.0 - zl, x)
        for e in range(4):                                   # closed side: road 29's sidewalk, curb and edge line
            if self.d[e] == "C" and dist[e] < CURB_BAND:
                return S(29, e % 2, z, r, x, zl)
        for e in range(4):                                   # outer corner between two arms: 43's corner as stock
            f = (e + 1) % 4
            if self.d[e] == "A" and self.d[f] == "A" and dist[e] < CORNER and dist[f] < CORNER:
                return S(43, 0, z, r, x, zl)
        for e in range(4):                                   # crosswalk across an arm: 43's own lines
            if self.d[e] == "A" and dist[e] < LINE_BAND:
                px, pz = (min(LINE_HI, max(LINE_LO, x)), zl) if e % 2 == 0 else (x, min(LINE_HI, max(LINE_LO, zl)))
                c = S(43, 0, z, r, px, pz)
                if P.light(c):
                    return c
        return S(43, 0, z, r, fold(x), fold(zl))


def _median_grass(c):
    """11204's median grass (not its trees: those are brighter, darker or bluer-free, measured at zoom 4)"""
    r, g, b = c[:3]
    return c[3] and 96 <= g <= 120 and b >= 62 and g > r + 4 and g > b + 4


LINE_BAND_Z = (108.0, 148.0)   # 11204 (state 0): its yellow centre line lies in this lane-z band (zoom 4 map: 120..136)


def _yellowish(c):
    """the stock centre line's pixels, anti-aliased edges included (not trees: green; not trunks: r - b < 40)"""
    r, g, b = c[:3]
    return c[3] and r - b >= 40 and g - b >= 25 and r >= 110


def _asphalt_fill(z, r, lx, lz):
    """11204's own lane asphalt beside the centre line: the point mirrored out of the line band (the nearer side
    first, then the other), skipping tree pixels; the plain asphalt palette if both are covered"""
    from netmod import diagave_paint as P
    lo, hi = LINE_BAND_Z
    for t in ((2 * lo - lz, 2 * hi - lz) if lz - lo < hi - lz else (2 * hi - lz, 2 * lo - lz)):
        c = P.STOCK(11204, 0, z, r, lx, min(255.5, max(0.5, t)))
        if P.asphaltish(c):
            return (c[0], c[1], c[2], 255)
    return P.pick("asphalt", z, lx, lz)


def arm_frame(d0, z, r):
    """11204 (state 0) frame at slot r with the median grass within NOSE of the box end (E: d0 1, W: d0 3) repainted as
    road 29's sidewalk at the same point: the median ends in a concrete nose. The yellow centre line becomes the
    owner's white dashed lane line (lanelines.py, 2026-10-17): its own pixels, white where a dash covers the world
    along-coordinate, lane asphalt between dashes. Period 0.25 divides a cell, so lane x / 256 gives the same phase as
    world x wherever the piece sits. Trees and everything else stay stock."""
    from netmod import netart as NA
    from netmod import diagave_paint as P
    from netmod import lanelines as LL
    im, (L, T) = NA.stock_frames(11204)[(z, r)]
    out = im.copy()
    px = out.load()
    for y in range(out.height):
        for xx in range(out.width):
            c = px[xx, y]
            if c[3] < 128:
                continue
            line = _yellowish(c)
            if not line and not _median_grass(c):
                continue
            u, v = NA.unproject(z, xx + 0.5 - L, y + 0.5 - T)
            u, v = NA.rot_uv(u, v, -r % 4)
            lx, lz = (1.0 - u) * 256.0, v * 256.0
            if line:
                if -1.0 <= lx <= 257.0 and LINE_BAND_Z[0] <= lz <= LINE_BAND_Z[1]:
                    px[xx, y] = LL.dashed(z, lx / 256.0, lz / 256.0, lx / 256.0, True,
                                          lambda: _asphalt_fill(z, r, min(255.5, max(0.5, lx)), lz))
                continue
            if not (-1.0 <= lx <= 257.0 and -1.0 <= lz <= MEDIAN):
                continue
            near = 256.0 - lx if d0 == 1 else lx
            if near < NOSE:
                s = P.STOCK(29, 0, z, r, min(255.5, max(0.5, lx)), max(0.5, lz))
                if s[3]:
                    px[xx, y] = (s[0], s[1], s[2], 255)
    return out, (L, T)


def cmd_build(a):
    from netmod import netart as NA
    from netmod import diagave_paint as P
    from netmod import diagave as D
    art = lambda vid: os.path.join(a.pack, "art", str(vid))                       # noqa: E731
    for desc, vid in sorted(BOX.items(), key=lambda t: t[1]):
        d = art(vid)
        anc = P.paint_cell(Box(desc), (0, 0), d)
        D._write_anchors(d, anc, "avx.py build: box cell %s" % desc)
        pid, st = LANES_OF[desc]
        spec = D.parts_spec([(pid, st)], vid, "avx box cell %s: lanes of %d state %d" % (desc, pid, st))
        json.dump(spec, open(os.path.join(a.pack, "box_%d.lanes.json" % vid), "w", newline="\n"), indent=1)
        print("built %d (box %s, lanes of %d.%d)" % (vid, desc, pid, st))
    for d0, vid in sorted(ARM.items(), key=lambda t: t[1]):
        d = art(vid)
        os.makedirs(d, exist_ok=True)
        anc = {}
        for z in range(NA.ZOOMS):
            for r in range(NA.ROTS):
                im, LT = arm_frame(d0, z, r)
                im.save(os.path.join(d, NA.frame_name(z, r)))
                anc[NA.frame_name(z, r)] = list(LT)
        D._write_anchors(d, anc, "avx.py build: 11204 with the median nose at the %s end" % EDGES[d0])
        print("built %d (arm, nose %s)" % (vid, EDGES[d0]))


# ------------------------------------------------------------------------------------------------ offline tiler

def _rot_cells(cells, k):
    out = set()
    for (x, z) in cells:
        for _ in range(k % 4):
            x, z = -z - 1, x
        out.add((x, z))
    return out


def shapes():
    """canonical drawings (avenue along x on rows 0 / 1) -> road cells; refusals: shapes another block owns"""
    av_x = {(x, z) for x in range(-7, 9) for z in (0, 1)}
    S = {
        "AxA": av_x | {(x, z) for x in (0, 1) for z in range(-7, 9)},
        "AvT": av_x | {(x, z) for x in (0, 1) for z in range(2, 9)},
        "RxA": av_x | {(0, z) for z in range(-7, 9)},
        "RT": av_x | {(0, z) for z in range(2, 9)},
    }
    must_refuse = {
        # RBT: 2x2 block, one road per side exit (the pinwheel the stock tiler builds)
        "rbt_2x2": {(0, 0), (1, 0), (0, 1), (1, 1)} | {(x, 0) for x in range(-6, 0)} | {(1, z) for z in range(-6, 0)} |
                   {(x, 1) for x in range(2, 8)} | {(0, z) for z in range(2, 8)},
        # bigrbt: 3x3 block with avenue arms
        "bigrbt_3x3": {(x, z) for x in range(3) for z in range(3)} | {(x, z) for x in range(-6, 0) for z in (0, 1)} |
                      {(x, z) for x in range(3, 9) for z in (1, 2)},
        # boulevard: three parallel roads crossed by a road and by an avenue
        "blvd_x_road": {(x, z) for x in range(-7, 9) for z in (0, 1, 2)} | {(0, z) for z in range(-7, 10)},
        "blvd_x_av": {(x, z) for x in range(-7, 9) for z in (0, 1, 2)} | {(x, z) for x in (0, 1) for z in range(-7, 10)},
        # diagonal avenue (two staircases one cell apart) crossing a straight avenue
        "diag_x_av": av_x | {(k + d, k) for k in range(-6, 7) for d in (0, 1, 2)},
        # a single diagonal road (staircase) crossing an avenue
        "diag_x_road": av_x | {(k + d, k) for k in range(-6, 7) for d in (0, 1)},
    }
    return S, must_refuse


_ENV = {}


def _env():
    if not _ENV:
        from netmod import tiler, netrules, paths
        g = paths.game_root()
        _ENV.update(g=g, game=paths.Game(), tiler=tiler, netrules=netrules,
                    ids={int(v) for v in __import__("re").findall(r"\d+", open(os.path.join(
                        g, "Apps", "Res", "TilingRules", "ROAD_GRND_Set.txt")).read())})
    return _ENV


def stock_grid(cells):
    """the stock tiler's pieces for road `cells` drawn on Roadless Paradise -> {(x, z): (id, state)} in shape coords"""
    E = _env()
    tiler, netrules = E["tiler"], E["netrules"]
    from netmod import diag_probe
    opts = tiler.Options()
    city = netrules.prepared(tiler.City.load(os.path.join(E["g"], "Cities", "Roadless Paradise.sc3")), opts)
    T = tiler.Tiler(tiler.Rules(os.path.join(E["g"], "Apps", "Res", "TilingRules")), city, opts,
                    tiler.load_pe(E["game"]), netrules.exemplars(E["game"]))
    xs, zs = [c[0] for c in cells], [c[1] for c in cells]
    X, Z = diag_probe.flat_patch(city, max(xs) - min(xs) + 3, max(zs) - min(zs) + 3)
    X, Z = X + 1 - min(xs), Z + 1 - min(zs)
    lay = T.layer(1)
    real = [(X + x, Z + z) for x, z in sorted(cells)]
    for c in real:
        lay[c] = tiler.Piece(29, 0, city.h(*c))
    T.retile(1, real)
    return {(x, z): (lay[(X + x, Z + z)].id, lay[(X + x, Z + z)].state) for (x, z) in cells
            if (X + x, Z + z) in lay and lay[(X + x, Z + z)].id in E["ids"]}


def grid_text(g, x0, z0, x1, z1):
    rows = ["%4d " % z + " ".join("%8s" % ("%d.%d" % g[(x, z)] if (x, z) in g else ".") for x in range(x0, x1 + 1))
            for z in range(z0, z1 + 1)]
    return "\n".join(rows + ["     " + " ".join("%8d" % x for x in range(x0, x1 + 1))])


def cmd_check(a):
    S, bad = shapes()
    fails = 0
    for name, cells in sorted(S.items()):
        for k in range(4):
            R = _rot_cells(cells, k)
            g = stock_grid(R) if a.tiler else {}
            js, _ = find(R, {c: v[0] for c, v in g.items()} if g else None)
            kinds = [j["kind"] for j in js]
            ok = kinds == [name]
            fails += not ok
            print("%-6s rot %d: %s %s" % (name, k, "OK  " if ok else "FAIL", kinds))
            if ok and k == 0 and a.verbose:
                w = js[0]["want"]
                print("  wanted: " + " ".join("(%d,%d)=%d.%d" % (c[0], c[1], p, s) for c, (p, s) in sorted(w.items())))
                if g:
                    print(grid_text(g, -3, -3, 4, 4))
    for name, cells in sorted(bad.items()):
        for k in range(4):
            R = _rot_cells(cells, k)
            js, ref = find(R)
            ok = not js
            fails += not ok
            print("%-11s rot %d (must refuse): %s %s" % (name, k, "OK  " if ok else "FAIL", [j["kind"] for j in js] or
                                                         sorted({w for _, w in ref})[:3]))
    # RBT's rule on our shapes: it must never convert our boxes
    from netmod import rb_auto
    for name, cells in sorted(S.items()):
        if not a.tiler:
            break
        g = stock_grid(cells)
        road = lambda x, z: g.get((x, z))                                         # noqa: E731
        hits = [(x, z) for (x, z) in cells if rb_auto.check(road, x, z)[0]]
        fails += bool(hits)
        print("RBT on %-4s: %s" % (name, "OK   no block qualifies" if not hits else "FAIL %s" % hits))
    print("%d failure(s)" % fails)
    return 1 if fails else 0


def cmd_scan(a):
    from netmod import tiler, paths
    saves = a.saves or sorted(glob.glob(os.path.join(paths.game_root(), "Cities", "*.sc3")))
    E = _env()
    for s in saves:
        lay = tiler.City.load(s).layers["surface"]
        R = {c for c, p in lay.items() if (p.id in E["ids"] or p.id in OWN) and p.flags is None}
        js, _ = find(R, {c: lay[c].id for c in R})
        n = {}
        for j in js:
            n[j["kind"]] = n.get(j["kind"], 0) + 1
        print("%-28s %s" % (os.path.basename(s), n or "-"))


# ------------------------------------------------------------------------------------------------ mockup

def layout(cells, pack, use_mod, window=None):
    g = stock_grid(cells)
    want = {}
    if use_mod:
        for j in find(set(cells), {c: v[0] for c, v in g.items()})[0]:
            want.update(j["want"])
    out = []
    for c, (pid, s) in g.items():
        if window and c not in window:
            continue
        if c in want:
            out.append({"at": [-c[0], c[1]], "dir": os.path.join(pack, "art", str(want[c][0])), "slot": want[c][1]})
        else:
            out.append({"at": [-c[0], c[1]], "piece": pid, "slot": s})
    return out


def cmd_mockup(a):
    from PIL import Image, ImageDraw
    from netmod import netart as NA
    S, _ = shapes()
    cols = [("stock", False, 4, 0), ("avx", True, 4, 0), ("avx", True, 4, 1), ("avx", True, 3, 0), ("avx", True, 3, 1)]
    rows = []
    for name in ("AxA", "AvT", "RxA", "RT"):
        win = {c for c in S[name] if -3 <= c[0] <= 4 and -3 <= c[1] <= 4}
        shots = []
        for label, mod, z, r in cols:
            lay = layout(S[name], os.path.abspath(a.pack), mod, win)
            sh = NA.preview({"cells": lay}, None, zooms=[z], rots=[r])[(z, r)]
            shots.append(("%s %s zoom %d view %d" % (name, label, z, r), sh))
        rows.append(shots)
    cw = max(im.width for row in rows for _, im in row)
    ch = max(im.height for row in rows for _, im in row) + 18
    sheet = Image.new("RGB", (cw * len(cols), ch * len(rows)), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for i, row in enumerate(rows):
        for j, (lab, im) in enumerate(row):
            sheet.paste(im.convert("RGB"), (j * cw + (cw - im.width) // 2, i * ch + 18 + (ch - 18 - im.height) // 2))
            dr.text((j * cw + 6, i * ch + 3), lab, fill=(230, 230, 230))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(a.out, sheet.size)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("build")
    s.add_argument("pack")
    s = sub.add_parser("check")
    s.add_argument("--tiler", action="store_true", help="also run the offline stock tiler (ids guard, RBT twin)")
    s.add_argument("-v", "--verbose", action="store_true")
    s = sub.add_parser("mockup")
    s.add_argument("out")
    s.add_argument("pack")
    s = sub.add_parser("scan")
    s.add_argument("saves", nargs="*")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "check": cmd_check, "mockup": cmd_mockup, "scan": cmd_scan}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
