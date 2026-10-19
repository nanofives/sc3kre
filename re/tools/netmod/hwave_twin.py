#!/usr/bin/env python3
r"""hwave_twin.py - offline twin of the HWAVE block (re/harness/src/sc3netmod_hwave.c, task hwave 2026-10-19).

  py -3.12 hwave_twin.py match SAVE.sc3            every highway end beside a road: built / refused (why), as the DLL
  py -3.12 hwave_twin.py dmatch SAVE.sc3           the diagonal rule (phase 2): every diagonal end with road past it
  py -3.12 hwave_twin.py nomod SAVE.sc3            the same save as a game without sc3netmod reads it
  py -3.12 hwave_twin.py retile SAVE.sc3           build every match with the pieces' BASES, run the stock HWAY + ROAD
                                                   rect retile over each (tiler.py) and print the rows before / after
Same rule, turns and stock pieces as the C block (its header). Heights: the save's vertex grid (tiler City.h). Claims
by other highway blocks are not modelled (no interchange shapes are matched here).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

PIECES = (21600, 21601, 21602, 21603)            # T1 exit, T1 entry, T2 exit, T2 entry
BASES = {21600: 15137, 21601: 15136, 21602: 15141, 21603: 15140}
CAP_DIR = {(11235, 0): (0, 1), (11237, 0): (0, 1), (11235, 2): (0, -1), (11237, 2): (0, -1),
           (15053, 0): (-1, 0), (15054, 0): (-1, 0), (15053, 2): (1, 0), (15054, 2): (1, 0)}


def rot(k, v):
    x, z = v
    for _ in range(k):
        x, z = -z, x
    return x, z


def plain(k, c):
    return (15051 if k & 1 else 73), (0 if (k < 2) == (c == 1) else 2)


def cap(k, c):
    return ((15054 if c else 15053) if k & 1 else (11237 if c else 11235)), (0 if k < 2 else 2)


def uturn(k, c):
    return 11203, (k if c else (k + 3) & 3)


def ave(k, c):
    return 11204, ((k + 3) & 3 if c else (k + 1) & 3)


def cell(a, k, c, r):
    e, d = rot(k, (1, 0)), rot(k, (0, 1))
    return a[0] + c * e[0] + r * d[0], a[1] + c * e[1] + r * d[1]


def ident(p):
    return None if p is None else (p.id, p.state)


def check(lay, city, a, k):
    """-> None when the transition at anchor a, turn k qualifies, else why (the C block's hwave_check)"""
    for c in (0, 1):
        if ident(lay.get(cell(a, k, c, -1))) != plain(k, c):
            return "no plain highway behind the cap row"
        if ident(lay.get(cell(a, k, c, 0))) not in (cap(k, c), (PIECES[1 - c], k)):
            return "cap row"
        if ident(lay.get(cell(a, k, c, 1))) not in (uturn(k, c), (PIECES[3 - c], k)):
            return "no avenue U-turn row past the cap"
        if ident(lay.get(cell(a, k, c, 2))) != ave(k, c):
            return "no straight avenue past the U-turn row"
    n = city.n
    h0 = None
    for c in (0, 1):
        for r in (-1, 0, 1, 2):
            x, z = cell(a, k, c, r)
            if x < 1 or z < 1 or x >= n - 1 or z >= n - 1:
                return "map edge"
            hs = {city.h(x, z), city.h(x + 1, z), city.h(x, z + 1), city.h(x + 1, z + 1)}
            if len(hs) != 1:
                return "not flat"
            h = hs.pop()
            if h0 is None:
                h0 = h
            elif h != h0:
                return "height step"
    return None


def matches(lay, city):
    """-> [(anchor, turn, why or None)] for every entry-column cap with a road past it"""
    out = []
    for (x, z), p in sorted(lay.items()):
        d = CAP_DIR.get(ident(p))
        if d:
            k = [j for j in range(4) if rot(j, (0, 1)) == d][0]
            if ident(p) != cap(k, 0):
                continue
        elif p.id == PIECES[1]:                             # a built one: the entry column's T1 names the turn
            k = p.state
        else:
            continue
        past = lay.get(cell((x, z), k, 0, 1))
        if past is None or past.id not in (11203, 11204, 11225, 29, 39, 43) and past.flags is not None:
            continue
        if past is None:
            continue
        out.append(((x, z), k, check(lay, city, (x, z), k)))
    return out


def load(path, variants=True):
    """the save as the tiler reads it; variants=True puts back the variant ids sc3netmod saved in section 0x4E56
    (the tile words hold the stock-loadable ids; an entry's id carries the original state when bit 0x40000 is set,
    sc3netmod.c save_rec / load_rec), i.e. the city as a game WITH the mod shows it"""
    from netmod import tiler, netrules, paths
    g = paths.Game()
    opts = tiler.Options()
    city = netrules.prepared(tiler.City.load(path), opts)
    if variants:
        import city_write
        import netvariant
        ents = netvariant.section_entries(city_write.City.load(path)) or []
        lay = city.layers["surface"]
        for w0, w1, vid in ents:
            xy = netvariant.xy(w0)
            if xy in lay:
                st = (vid >> 16) & 3 if vid & 0x40000 else w0 >> 30
                lay[xy] = tiler.Piece(vid & 0xffff, st, lay[xy].z, lay[xy].props)
    return g, tiler, netrules, opts, city


def cmd_match(path):
    g, tiler, netrules, opts, city = load(path)
    lay = city.layers["surface"]
    res = matches(lay, city)
    for a, k, why in res:
        print("highway end at %s turn %d: %s" % (a, k, "transition" if why is None else "refused (%s)" % why))
    print("%d end(s) beside a road, %d transition(s)" % (len(res), sum(1 for r in res if r[2] is None)))
    return 0


def _rows(lay, a, k):
    out = []
    for r in (-1, 0, 1, 2):
        out.append("  ".join("%5d.%d" % ident(lay[cell(a, k, c, r)]) if cell(a, k, c, r) in lay else "    ." for c in (0, 1)))
    return out


def cmd_retile(path):
    g, tiler, netrules, opts, city = load(path)
    T = tiler.Tiler(tiler.Rules(g.tiling), city, opts, tiler.load_pe(g), netrules.exemplars(g))
    lay = T.layer(4)
    bad = 0
    for a, k, why in matches(lay, city):
        if why:
            continue
        before = _rows(lay, a, k)
        for c in (0, 1):
            for r in (0, 1):
                xz = cell(a, k, c, r)
                lay[xz] = tiler.Piece(BASES[PIECES[r * 2 + (1 - c)]], k, city.h(*xz))
        cs = [cell(a, k, c, r) for c in (0, 1) for r in (-1, 0, 1, 2)]
        x0, z0 = min(c[0] for c in cs), min(c[1] for c in cs)
        x1, z1 = max(c[0] for c in cs), max(c[1] for c in cs)
        T.retile_rect(3, x0 - 1, z0 - 1, x1 + 1, z1 + 1)
        after = _rows(lay, a, k)
        want = [plain(k, 0), plain(k, 1)], None, None, [ave(k, 0), ave(k, 1)]
        ok = all(ident(lay[cell(a, k, c, -1)]) == plain(k, c) and ident(lay[cell(a, k, c, 2)]) == ave(k, c) and
                 ident(lay[cell(a, k, c, r)]) == (BASES[PIECES[r * 2 + (1 - c)]], k) for c in (0, 1) for r in (0, 1))
        bad += not ok
        print("transition at %s turn %d: %s" % (a, k, "stable" if ok else "CHANGED by the stock retile"))
        for b, f in zip(before, after):
            print("   %-26s ->  %s" % (b, f))
    return 1 if bad else 0


# ------------------------------------------------------------------ diagonal (phase 2, sc3netmod_hwave.c hwavd_*)
DPIECES = (21604, 21605, 21606, 21607, 21608, 21609)   # j-1 high, j-1 low, j0, j+1 high, j+1 low, j+2
DBASES = {21604: 15134, 21605: 15134, 21606: 15134, 21607: 15134, 21608: 15134, 21609: 15138}
DOFF = ((0, -1), (-1, 0), (0, 0), (1, 0), (0, 1), (1, 1))
DAV_ROAD = {35, 18004, 1999} | set(range(20500, 20506))
DAV_OUTER, DAV_MIDDLE = 20505, 20500
DCAP = {(14999, 2): 0, (15059, 2): 1, (14999, 0): 2, (15059, 0): 3}   # cap -> turn k (outward step rot_k(1, 1))


def dcell(a, k, off):
    d = rot(k, off)
    return a[0] + d[0], a[1] + d[1]


def dplain(k, high):
    return (15052 if k & 1 else 11223), (0 if (k < 2) == bool(high) else 2)


def dcheck(lay, city, a, k):
    def at(off):
        return lay.get(dcell(a, k, off))
    if ident(at((-1, -1))) != ((15106 if k & 1 else 11224), 0):
        return "no plain highway band behind the cap"
    for side in (0, 1):
        if ident(at(DOFF[side])) not in (dplain(k, side == 0), (DPIECES[side], k)):
            return "no plain highway band beside the cap"
    if ident(at((0, 0))) not in (((15059 if k & 1 else 14999), 2 if k < 2 else 0), (DPIECES[2], k)):
        return "cap"
    p = at((1, 0))
    if p is not None and ident(p) != (DPIECES[3], k):
        return "the cell past the cap is taken"
    p = at((0, 1))
    if p is not None and p.id not in DAV_ROAD and ident(p) != (DPIECES[4], k):
        return "the avenue's end cell beside the cap is taken"
    p = at((1, 1))
    if p is None or (p.id not in DAV_ROAD and ident(p) != (DPIECES[5], k)):
        return "no avenue end past the cap"
    for off in ((2, 1), (1, 2)):
        p = at(off)
        if p is None or p.id not in DAV_ROAD:
            return "no avenue band two cells past the cap"
    p = at((2, 2))
    if p is None or p.id != DAV_MIDDLE:
        return "no plain avenue band (DAV middle piece) past the end"
    h0 = None
    for off in ((-1, -1), (0, -1), (-1, 0), (0, 0), (1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (2, 2)):
        x, z = dcell(a, k, off)
        hs = {city.h(x, z), city.h(x + 1, z), city.h(x, z + 1), city.h(x + 1, z + 1)}
        if len(hs) != 1:
            return "not flat"
        h = hs.pop()
        if h0 is not None and h != h0:
            return "height step"
        h0 = h
    return None


def dmatches(lay, city):
    out = []
    for xz, p in sorted(lay.items()):
        k = DCAP.get(ident(p))
        if k is None and p.id == DPIECES[2]:              # a built one: our j0 piece names the turn
            k = p.state
        if k is None or lay.get(dcell(xz, k, (1, 1))) is None:
            continue
        out.append((xz, k, dcheck(lay, city, xz, k)))
    return out


def cmd_dmatch(path, variants=True):
    g, tiler, netrules, opts, city = load(path, variants)
    lay = city.layers["surface"]
    res = dmatches(lay, city)
    for a, k, why in res:
        print("diagonal highway end at %s turn %d: %s" % (a, k, "transition" if why is None else "refused (%s)" % why))
    print("%d diagonal end(s) with road past them, %d transition(s)" % (len(res), sum(1 for r in res if r[2] is None)))
    return 0



def cmd_match_raw(path):
    g, tiler, netrules, opts, city = load(path, False)
    lay = city.layers["surface"]
    n = sum(1 for p in lay.values() if p.id in DPIECES or p.id in PIECES or p.id in range(20500, 20600))
    print("tile words holding a variant id (must be 0 for a stock-loadable save): %d" % n)
    return 0


def main(argv):
    if len(argv) == 3 and argv[1] == "match":
        return cmd_match(argv[2])
    if len(argv) == 3 and argv[1] == "dmatch":
        return cmd_dmatch(argv[2])
    if len(argv) == 3 and argv[1] == "nomod":                # what a game WITHOUT sc3netmod reads: the tile words
        return cmd_dmatch(argv[2], False) or cmd_match_raw(argv[2])
    if len(argv) == 3 and argv[1] == "retile":
        return cmd_retile(argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
