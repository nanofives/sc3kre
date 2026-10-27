"""avslope.py -- avenues and boulevards on slopes (task avslope, 2026-10-26).

Stock: a ROAD cell on a legal slope gets the ROAD slope table piece by its corner pattern alone (11202 / 11201, steep
32 / 31, FUN_1001a2c0, SIMNTWRK 0x1003195C; verify/slopeend/RESULTS.md 1), so an avenue (two parallel roads, flat
cells 11204) or a boulevard (three, 11204 / 29 / 11204) that runs up or down a slope is two or three plain sloped roads
on those cells.

    py -3.12 re/tools/netmod/avslope.py survey [city.sc3 ...]     # sloped avenue / boulevard rows in the shipped cities
    py -3.12 re/tools/netmod/avslope.py lab IN.sc3 OUT.sc3          # lab terrain: plateaus on Roadless Paradise
"""
import argparse
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

SLOPE_AXIS = {11202: "x", 32: "x", 11201: "z", 31: "z"}
D = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}            # N E S W


def load_city(path):
    from netmod import tiler, netrules
    return netrules.prepared(tiler.City.load(path), tiler.Options())


def flat(city, x, z):
    h = city.h(x, z)
    return h == city.h(x + 1, z) == city.h(x + 1, z + 1) == city.h(x, z + 1)


def survey(paths):
    tot = {}
    for p in paths:
        city = load_city(p)
        lay = city.layers["surface"]

        def pid(x, z):
            pc = lay.get((x, z))
            return None if pc is None else (pc.id & 0xffff, pc.state)
        n = {}

        def add(k):
            n[k] = n.get(k, 0) + 1
            tot[k] = tot.get(k, 0) + 1
        for (x, z), pc in lay.items():
            i, st = pc.id & 0xffff, pc.state
            if i in SLOPE_AXIS:
                ax = SLOPE_AXIS[i]
                ac = [(0, -1), (0, 1)] if ax == "x" else [(-1, 0), (1, 0)]     # across neighbours
                same = [pid(x + dx, z + dz) == (i, st) for dx, dz in ac]
                k = sum(same)
                if k:
                    add("slope cell with %d same-slope neighbour(s) across (%s, mag %d)" % (k, ax, 2 if i < 100 else 1))
                # avenue run onto the slope: a flat 11204 next along the axis?
                al = [(1, 0), (-1, 0)] if ax == "x" else [(0, 1), (0, -1)]
                if any((pid(x + dx, z + dz) or (0,))[0] == 11204 for dx, dz in al):
                    add("slope cell continuing an 11204 band along its axis")
            elif i == 11204:
                q = pid(x + D[st][0], z + D[st][1])
                if not flat(city, x, z):
                    add("11204 on a non-flat cell")
                if q is None or q[0] != 11204:
                    add("11204 whose median-side partner is %s" % ("empty" if q is None else
                                                                     ("slope %d" % q[0] if q[0] in SLOPE_AXIS else
                                                                      "piece %d" % q[0])))
                elif city.h(x, z) != city.h(x + D[st][0], z + D[st][1]) or not flat(city, x + D[st][0], z + D[st][1]):
                    add("11204 pair at different heights")
        print("%-26s %s" % (os.path.basename(p)[:26], "; ".join("%s %d" % kv for kv in sorted(n.items()))), flush=True)
    print("\nALL:")
    for k, v in sorted(tot.items()):
        print("  %6d  %s" % (v, k))


# Lab (Roadless Paradise, flat 82 on x 42..74 / z 12..44, x 94..116 / z 78..100, x 120..142 / z 2..46): vertex boxes
# X0, X1, Z0, Z1 (inclusive) raised by `up`. Edge cells are legal slopes (mag = up), corner cells are not.
LAB_PLATEAUS = [
    ((48, 58, 14, 23), 1),       # PA: avenue + boulevard along x, slope cells x 47 (W) / 58 (E)
    ((48, 58, 28, 38), 2),       # PB: avenue + boulevard along z, steep, slope cells z 27 (N) / 38 (S)
    ((124, 138, 8, 18), 1),      # PC: avenue + boulevard along z, slope cells z 7 / 18
    ((126, 136, 25, 40), 2),     # PD: avenue + boulevard along x, steep, slope cells x 125 / 136
    ((98, 112, 84, 94), 1),      # PE: avenues ALONG the plateau's edges (halves at different heights), rows 83 / 94
]


def cmd_lab(src, dst):
    import city_write
    c = city_write.City.load(src)
    n = c.n
    sec = [s for s in c.sections if s.group == 0x21737DE5 and s.instance == 0][0]
    for (X0, X1, Z0, Z1), up in LAB_PLATEAUS:
        for X in range(X0, X1 + 1):
            for Z in range(Z0, Z1 + 1):
                sec.data[12 + (n - X) * (n + 1) + Z] += up
    c.save(dst)
    print("lab", dst, "n", n, "plateaus", LAB_PLATEAUS)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("survey")
    s.add_argument("cities", nargs="*")
    s = sp.add_parser("lab")
    s.add_argument("src")
    s.add_argument("dst")
    a = ap.parse_args(argv)
    if a.cmd == "lab":
        return cmd_lab(a.src, a.dst)
    if a.cmd == "survey":
        from netmod import paths as P
        survey(a.cities or sorted(glob.glob(os.path.join(P.Game().root, "Cities", "*.sc3"))))


if __name__ == "__main__":
    main()
