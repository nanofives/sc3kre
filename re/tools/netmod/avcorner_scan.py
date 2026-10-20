#!/usr/bin/env python3
r"""avcorner_scan.py - avenue corners in the shipped cities: what ends the avenue bands (task avcore, 2026-10-19).

A band = the maximal run of rows of two stock 11204 halves side by side (along z: (x, z) state 1 and (x + 1, z) state 3;
along x: (x, z) state 2 and (x, z + 1) state 0), the AVL block's rule without crossings. For each band end this prints
the pieces on the end row (the two cells past the last row), as id.state, and counts them over every city.

  py -3.12 -m netmod.avcorner_scan [--examples N]        (run from re/tools)
"""
import collections, glob, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from netmod import tiler, paths  # noqa: E402

D = [(0, -1), (1, 0), (0, 1), (-1, 0)]          # N E S W
CROSS = {69, 67, 11258, 15098, 31, 32, 11201, 11202}   # avcore's crossing / slope bases (AVENUE_LANES.md 3)


def bands(s):
    """-> [(axis, x, z, k0, k1)]: first-half cell of row 0 and the row range; axis 0 along z, 1 along x"""
    out, seen = [], set()

    def row(axis, x, z):
        a = s.get((x, z))
        b = s.get((x + 1, z) if axis == 0 else (x, z + 1))
        if not a or not b:
            return False
        if a.id == b.id and a.id in CROSS:                # the AVL block converts through these (road along: unchecked)
            return True
        if a.id != 11204 or b.id != 11204:
            return False
        return (a.state & 3, b.state & 3) == ((1, 3) if axis == 0 else (2, 0))
    for (x, z), p in s.items():
        if p.id != 11204 or (x, z) in seen:           # seeds: plain halves only
            continue
        for axis in (0, 1):
            if not row(axis, x, z):
                continue
            dx, dz = (0, 1) if axis == 0 else (1, 0)
            k0 = 0
            while row(axis, x + dx * (k0 - 1), z + dz * (k0 - 1)):
                k0 -= 1
            k1 = 0
            while row(axis, x + dx * (k1 + 1), z + dz * (k1 + 1)):
                k1 += 1
            ax, az = x + dx * k0, z + dz * k0
            for k in range(0, k1 - k0 + 1):
                cx, cz = ax + dx * k, az + dz * k
                seen.add((cx, cz))
                seen.add((cx + 1, cz) if axis == 0 else (cx, cz + 1))
            out.append((axis, ax, az, 0, k1 - k0))
    return list(set(out))


def end_cells(axis, ax, az, k0, k1, end):
    dx, dz = (0, 1) if axis == 0 else (1, 0)
    k = k0 - 1 if end < 0 else k1 + 1
    a = (ax + dx * k, az + dz * k)
    b = (a[0] + 1, a[1]) if axis == 0 else (a[0], a[1] + 1)
    return a, b


USTATE = {(0, -1): (3, 0), (0, 1): (2, 1), (1, 1): (0, 1), (1, -1): (3, 2)}   # (axis, end) -> A / B 11203 states


def row_at(s, axis, x, z):
    a = s.get((x, z))
    b = s.get((x + 1, z) if axis == 0 else (x, z + 1))
    return bool(a and b and a.id == 11204 and b.id == 11204 and
                (a.state & 3, b.state & 3) == ((1, 3) if axis == 0 else (2, 0)))


def classify(s, b, end, W=256):
    """-> (kind, detail): U / edge / corner (clean: inner 11203 + outer 11203, the other axis's band beside the block) /
    corner-junction (the outer cell is not 11203) / junction (39 / 43 on the end row) / other"""
    axis, ax, az, k0, k1 = b
    a, c = end_cells(*b, end)
    if not (0 <= a[0] < W and 0 <= a[1] < W and 0 <= c[0] < W and 0 <= c[1] < W):
        return "edge", None
    pa, pc = s.get(a), s.get(c)
    if pa and pc and pa.id == 11203 and pc.id == 11203 and (pa.state & 3, pc.state & 3) == USTATE[(axis, end)]:
        return "U", None
    ids = (pa.id if pa else 0, pc.id if pc else 0)
    if sorted(ids) == [11203, 11204]:
        dx, dz = (0, 1) if axis == 0 else (1, 0)
        a2, c2 = (a[0] + dx * end, a[1] + dz * end), (c[0] + dx * end, c[1] + dz * end)
        inner_is_a = ids[0] == 11203
        under = s.get(a2 if inner_is_a else c2)
        outer = s.get(c2 if inner_is_a else a2)
        if under and under.id == 11204:
            # the other band: perpendicular axis, beside the block on the inner cell's side
            oaxis = 1 - axis
            side = -1 if inner_is_a else 1                    # a is the x- (along z) / z- (along x) column
            if axis == 0:
                cx = a[0] - 1 if inner_is_a else c[0] + 1
                zz = min(a[1], a2[1])
                other = (cx, zz) if row_at(s, 1, cx, zz) else None
            else:
                cz = a[1] - 1 if inner_is_a else c[1] + 1
                xx = min(a[0], a2[0])
                other = (xx, cz) if row_at(s, 0, xx, cz) else None
            if other is None:
                return "corner-nobeside", None
            if outer and outer.id == 11203:
                return "corner", (oaxis, other)
            return "corner-junction", (oaxis, other, outer.id if outer else 0)
        return "half-bend", None
    if any(i in (39, 43) for i in ids):
        return "junction", None
    return "other", ids


def groups(argv):
    g = paths.game_root()
    tot = collections.Counter()
    gk = collections.Counter()
    cells_k = collections.Counter()
    ex = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(g, "Cities", "*.sc3"))):
        city = os.path.basename(path)[:-4]
        s = tiler.City.load(path).layers["surface"]
        bl = bands(s)
        idx = {}
        for i, b in enumerate(bl):                    # band lookup by any of its first-half cells
            axis, ax, az, k0, k1 = b
            dx, dz = (0, 1) if axis == 0 else (1, 0)
            for k in range(k0, k1 + 1):
                idx[(axis, ax + dx * k, az + dz * k)] = i
        parent = list(range(len(bl)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        ends = {}
        ncorner = 0
        for i, b in enumerate(bl):
            for end in (-1, 1):
                k, d = classify(s, b, end)
                tot[k] += 1
                ends[(i, end)] = k
                if k == "corner":
                    j = idx.get((d[0],) + d[1])
                    if j is not None:
                        parent[find(i)] = find(j)
                        ncorner += 1
                    else:
                        ends[(i, end)] = "corner-unmatched"
        grp = collections.defaultdict(list)
        for i in range(len(bl)):
            grp[find(i)].append(i)
        for r, members in grp.items():
            ks = [ends[(i, e)] for i in members for e in (-1, 1)]
            if "corner" not in ks:
                continue
            rest = [k for k in ks if k != "corner"]
            cells = sum(2 * (bl[i][4] - bl[i][3] + 1) for i in members) + 4 * ks.count("corner") // 2
            if all(k in ("U", "edge") for k in rest):
                cls = "corner only (rest U / edge)"
            elif all(k in ("U", "edge", "junction") for k in rest):
                cls = "corner + junctions (avjunc decides)"
            else:
                cls = "corner + other blocker"
            gk[cls] += 1
            cells_k[cls] += cells
            if len(ex[cls]) < 4:
                b = bl[members[0]]
                ex[cls].append("%s (%d,%d) %d band(s)" % (city, b[1], b[2], len(members)))
    print("band ends by kind:", dict(tot.most_common()))
    for k in gk:
        print("groups %-36s %4d, cells %6d   e.g. %s" % (k, gk[k], cells_k[k], "; ".join(ex[k])))


def main(argv):
    if "--groups" in argv:
        return groups(argv) or 0
    nex = int(argv[argv.index("--examples") + 1]) if "--examples" in argv else 3
    g = paths.game_root()
    hist, ex, rows_by_kind = collections.Counter(), collections.defaultdict(list), collections.Counter()
    nb = 0
    for path in sorted(glob.glob(os.path.join(g, "Cities", "*.sc3"))):
        city = os.path.basename(path)[:-4]
        s = tiler.City.load(path).layers["surface"]
        for b in bands(s):
            nb += 1
            for end in (-1, 1):
                a, c = end_cells(*b, end)
                pa, pc = s.get(a), s.get(c)
                key = ("%d.%d" % (pa.id, pa.state & 3) if pa else "-", "%d.%d" % (pc.id, pc.state & 3) if pc else "-",
                       "along z" if b[0] == 0 else "along x", "back" if end < 0 else "fwd")
                hist[key] += 1
                rows_by_kind[key] += b[4] - b[3] + 1
                if len(ex[key]) < nex:
                    ex[key].append("%s (%d,%d)" % (city, a[0], a[1]))
    print("bands:", nb)
    for k, n in hist.most_common(60):
        print("%5d  %-9s %-9s %-8s %-4s  rows %5d  e.g. %s" % (n, k[0], k[1], k[2], k[3], rows_by_kind[k], "; ".join(ex[k])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
