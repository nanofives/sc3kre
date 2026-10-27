"""slopeend.py -- rounded road ends on sloped cells (task slopeend, 2026-10-26).

Stock: a ROAD cell on a legal slope never sees the rules. The retile pass FUN_1001547b moves every non-flat legal-slope
cell to the slope list and FUN_1001a2c0 gives it the ROAD slope table entry (SIMNTWRK 0x1003195C) for its corner
pattern, whatever its neighbours hold: 11202 (slope along x) / 11201 (along z) at magnitude 1, 32 / 31 at magnitude 2,
state 0 or 2 by the downhill side. So a road that ends on a slope ends with the straight piece's square cut.

This tool:
    py -3.12 re/tools/netmod/slopeend.py survey [city.sc3 ...]     # how the shipped cities use the slope pieces
    py -3.12 re/tools/netmod/slopeend.py classify city.sc3          # the rule (sc3netmod_sle.c) on a save, offline
    py -3.12 re/tools/netmod/slopeend.py lab IN.sc3 OUT.sc3         # lab terrain: two plateaus on Roadless Paradise
"""
import argparse
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

# ROAD slope table, SIMNTWRK 0x1003195C, read by tiler.slope_lookup: row -> (piece, state).
# Rows (FUN_1001a1f3 corners [0, c1-c0, c2-c0, c3-c0]): 0 [0,-1,-1,0] downhill +x, 1 [0,0,-1,-1] +z,
# 2 [0,1,1,0] -x, 3 [0,0,1,1] -z; 4..7 the same at magnitude 2.
SLOPE_PIECES = {11202: "x", 11201: "z", 32: "x", 31: "z"}
DOWNHILL = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}       # row % 4 -> world step to the downhill neighbour


def _road_ids(tiling):
    import re
    return {int(t) for t in re.findall(r"\d+", open(os.path.join(tiling, "ROAD_GRND_Set.txt"), encoding="latin-1").read())}


def load_city(path):
    from netmod import tiler, netrules
    opts = tiler.Options()
    return tiler, netrules.prepared(tiler.City.load(path), opts)


def slope_row(tiler_mod, city, x, z):
    """FUN_1001a1f3 + the pattern table: -> row 0..7 or None"""
    T = tiler_mod
    h0 = city.h(x, z)
    c = [0, city.h(x + 1, z) - h0, city.h(x + 1, z + 1) - h0, city.h(x, z + 1) - h0]
    rows = [[0, -1, -1, 0], [0, 0, -1, -1], [0, 1, 1, 0], [0, 0, 1, 1],
            [0, -2, -2, 0], [0, 0, -2, -2], [0, 2, 2, 0], [0, 0, 2, 2]]
    return rows.index(c) if c in rows else None


def flat(city, x, z):
    h = city.h(x, z)
    return h == city.h(x + 1, z) == city.h(x + 1, z + 1) == city.h(x, z + 1)


def classify_cell(lay, is_road, x, z, row):
    """-> (up, down, side): road in the uphill / downhill axis neighbour, road in a side neighbour"""
    dx, dz = DOWNHILL[row % 4]
    up = is_road(lay.get((x - dx, z - dz)))
    down = is_road(lay.get((x + dx, z + dz)))
    side = is_road(lay.get((x + dz, z + dx))) or is_road(lay.get((x - dz, z - dx)))
    return up, down, side


def cmd_survey(paths):
    from netmod import paths as P
    g = P.Game()
    road = _road_ids(g.tiling)
    tot = {}
    for p in paths:
        tiler_mod, city = load_city(p)
        lay = city.layers["surface"]

        def is_road(pc):
            return pc is not None and (pc.id & 0xffff) in road
        n = {}
        for (x, z), pc in lay.items():
            if not is_road(pc):
                continue
            row = slope_row(tiler_mod, city, x, z)
            if pc.id in SLOPE_PIECES:
                if row is None:
                    k = "slope piece on a non-slope cell"
                else:
                    up, down, side = classify_cell(lay, is_road, x, z, row)
                    k = "%s mag%d %s%s" % (SLOPE_PIECES[pc.id], 1 + row // 4,
                                           {(1, 1): "run (both)", (0, 1): "END going up (road below only)",
                                            (1, 0): "END going down (road above only)", (0, 0): "isolated"}[(up, down)],
                                           " +side road" if side else "")
            elif not flat(city, x, z):
                k = "other road piece %d on a non-flat cell (row %s)" % (pc.id, row)
            else:
                continue
            n[k] = n.get(k, 0) + 1
            tot[k] = tot.get(k, 0) + 1
        print("%-28s %s" % (os.path.basename(p)[:28], ", ".join("%s %d" % kv for kv in sorted(n.items()))))
    print("\nALL:")
    for k, v in sorted(tot.items()):
        print("  %6d  %s" % (v, k))


# Lab (Roadless Paradise, N 192, flat 82 on x 42..74 / z 12..44): plateau P1 one unit up, P2 two units up. Their
# edge cells are legal slopes in all four directions (P1 rows 0..3, P2 rows 4..7), their corner cells have one corner
# raised (not a legal slope).
LAB_PLATEAUS = [((50, 56, 18, 24), 1), ((62, 68, 18, 24), 2)]      # vertex box X0, X1, Z0, Z1 (inclusive), raise


def cmd_lab(src, dst):
    import city_write
    c = city_write.City.load(src)
    n = c.n
    m = (n + 1) ** 2
    sec = [s for s in c.sections if s.group == 0x21737DE5 and s.instance == 0][0]
    for (X0, X1, Z0, Z1), up in LAB_PLATEAUS:
        for X in range(X0, X1 + 1):
            for Z in range(Z0, Z1 + 1):
                sec.data[12 + (n - X) * (n + 1) + Z] += up
    c.save(dst)
    print("lab", dst, "plateaus", LAB_PLATEAUS)


def cmd_classify(path):
    """the SLE rule on a save (variants put back from the netvariant section): what a game WITH the mod should show"""
    from netmod import hwave_twin
    g, tiler_mod, netrules, opts, city = hwave_twin.load(path)
    road = _road_ids(g.tiling)
    fam = {11202: 27000, 11201: 27006, 32: 27012, 31: 27018}     # road_slope_ends 1.1.0: up/down/both at state 0, 2
    of = {b: b for b in fam}
    for b, v0 in fam.items():
        for k in range(6):
            of[v0 + k] = b
    lay = city.layers["surface"]

    def is_road(pc):
        return pc is not None and ((pc.id & 0xffff) in road or (pc.id & 0xffff) in of)
    bad = 0
    n = 0
    for (x, z), pc in sorted(lay.items()):
        if pc.id not in of:
            continue
        b = of[pc.id]
        st = pc.state
        dx, dz = ((-1 if st else 1), 0) if b in (11202, 32) else (0, (-1 if st else 1))
        up = is_road(lay.get((x - dx, z - dz)))
        dn = is_road(lay.get((x + dx, z + dz)))
        side = is_road(lay.get((x + dz, z + dx))) or is_road(lay.get((x - dz, z - dx)))
        v0 = fam[b] + (3 if st == 2 else 0)
        want = b if (side or (up and dn)) else (v0 if dn else (v0 + 1 if up else v0 + 2))
        n += 1
        if want != pc.id:
            bad += 1
        if want != b or pc.id != b:
            print("(%d,%d) %d/%d up %d down %d beside %d -> want %d %s" % (x, z, pc.id, st, up, dn, side, want,
                                                                         "ok" if want == pc.id else "DIFFERS"))
    print("%d slope cells, %d differ from the rule" % (n, bad))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("survey")
    s.add_argument("cities", nargs="*")
    s = sp.add_parser("lab")
    s.add_argument("src")
    s.add_argument("dst")
    s = sp.add_parser("classify")
    s.add_argument("city")
    a = ap.parse_args(argv)
    if a.cmd == "lab":
        return cmd_lab(a.src, a.dst)
    if a.cmd == "classify":
        return cmd_classify(a.city)
    if a.cmd == "survey":
        from netmod import paths as P
        cities = a.cities or sorted(glob.glob(os.path.join(P.Game().root, "Cities", "*.sc3")))
        cmd_survey(cities)


if __name__ == "__main__":
    main()
