"""avjunc: distinct box-cell pieces (art pattern x lane-mode pattern, modulo rotation) the generic rule needs over the
shipped cities, all bands one-way / all two-way / mixed. Sizing only.

Edge art: I (another box cell), A (an arm: road, avenue half, or the band's next cell), C (closed).
Edge mode: N (2 lanes in), O (2 lanes out), T (two-way: 1 in + 1 out, stock slots), C (closed).
Dirs: SIMNTWRK index 0 x-, 1 z-, 2 x+, 3 z+ (rotation order)."""
import collections, glob, json, os, sys
sys.path.insert(0, os.getcwd())
from netmod import tiler, avx

E = avx._env()
IDS = E["ids"]
EX = E["netrules"].exemplars(E["game"])
D = [(-1, 0), (0, -1), (1, 0), (0, 1)]
JUNC_OK = {29, 39, 43, 11203, 11204}
AVCORE = {69, 67, 11258, 15098, 31, 32, 11201, 11202}


def opp(d):
    return (d + 2) % 4


def arms(p):
    m = EX.mask(p.id, 0)
    if m is None:
        return set()
    st = p.state & 3
    return {w for w in range(4) if (m >> (4 * ((w - st) % 4))) & 0xF or (m >> (16 + 4 * ((w - st) % 4))) & 0xF}


def canon(t):
    return min(tuple(t[(i - k) % 4] for i in range(4)) for k in range(4))


def segments(s, R):
    def straight(a, b, axis):
        pa, pb = s.get(a), s.get(b)
        return bool(pa and pb and pa.id == 11204 and pb.id == 11204 and
                    (pa.state & 3, pb.state & 3) == ((1, 3) if axis == "z" else (2, 0)))
    segs = {}
    for (x, z), p in s.items():
        if p.id != 11204 or (p.state & 3) not in (1, 2):
            continue
        axis = "z" if (p.state & 3) == 1 else "x"
        o = (x + 1, z) if axis == "z" else (x, z + 1)
        if not straight((x, z), o, axis):
            continue
        step = (0, 1) if axis == "z" else (1, 0)
        for sg in (1, -1):
            pos, k = [], 1
            while True:
                a = (x + sg * step[0] * k, z + sg * step[1] * k)
                b = (o[0] + sg * step[0] * k, o[1] + sg * step[1] * k)
                if not (a in R and b in R) or straight(a, b, axis) or k > 9:
                    break
                pos.append((a, b))
                k += 1
            if not pos:
                continue
            if sg < 0:
                pos = pos[::-1]
            key = frozenset(c for pr in pos for c in pr)
            if key not in segs:
                segs[key] = dict(axis=axis, pos=pos)
    return list(segs.values())


def main():
    pieces = {"oneway": collections.Counter(), "twoway": collections.Counter(), "mixed": collections.Counter()}
    artpat = collections.Counter()
    examples = {}
    nbox = ncell = 0
    kinds = collections.Counter()
    for path in sorted(glob.glob(os.path.join(E["g"], "Cities", "*.sc3"))):
        city = os.path.basename(path)[:-4]
        s = tiler.City.load(path).layers["surface"]
        R = {c for c, p in s.items() if p.id in IDS and p.flags is None}
        for sgm in segments(s, R):
            axis, pos = sgm["axis"], sgm["pos"]
            if axis == "x":
                alm, alp, outa, outb, da, pfirst = 0, 2, 1, 3, 2, 1
            else:
                alm, alp, outa, outb, da, pfirst = 1, 3, 0, 2, 1, 2
            if any(i not in JUNC_OK and i not in AVCORE for a, b in pos for i in (s[a].id, s[b].id)):
                kinds["segment with a rare piece"] += 1
                continue
            feat = []
            for a, b in pos:
                A, B = arms(s[a]), arms(s[b])
                f = []
                for c, side, arm in ((a, outa, A), (b, outb, B)):
                    cc = (c[0] + D[side][0], c[1] + D[side][1])
                    if side in arm and cc in R:
                        nx = (cc[0] + D[side][0], cc[1] + D[side][1])
                        f.append("av" if s[cc].id == 11204 or (nx in s and s[nx].id == 11204) else "rd")
                    else:
                        f.append(None)
                feat.append(tuple(f))
            armpos = [i for i, f in enumerate(feat) if f[0] or f[1]]
            if not armpos:
                continue
            runs, cur = [], [armpos[0]]
            for i in armpos[1:]:
                if i == cur[-1] + 1:
                    cur.append(i)
                else:
                    runs.append(cur)
                    cur = [i]
            runs.append(cur)
            for r in runs:
                if len(r) > 4:
                    kinds["run longer than 4"] += 1
                    continue
                nbox += 1
                perp = {}
                for side in (0, 1):
                    av = [i for i in r if feat[i][side] == "av"]
                    j = 0
                    while j < len(av) - 1:
                        if av[j + 1] == av[j] + 1:
                            perp.setdefault(av[j], {})[side] = 0
                            perp.setdefault(av[j + 1], {})[side] = 1
                            j += 2
                        else:
                            j += 1
                boxset = {c for i in r for c in pos[i]}
                for combo in ("oneway", "twoway", "mixedA", "mixedB"):
                    band_ow = combo in ("oneway", "mixedA")
                    perp_ow = combo in ("oneway", "mixedB")
                    if combo.startswith("mixed") and not perp:
                        continue
                    bucket = "mixed" if combo.startswith("mixed") else combo
                    for i in r:
                        ps = None
                        for hh in (0, 1):
                            if i in perp and hh in perp[i]:
                                ps = perp[i][hh]
                        for h, c in enumerate(pos[i]):
                            d_half = da if h == 0 else opp(da)
                            out_d = outa if h == 0 else outb
                            art, mode = [None] * 4, [None] * 4
                            for e in range(4):
                                nb = (c[0] + D[e][0], c[1] + D[e][1])
                                if e in (alm, alp):
                                    art[e] = "I" if nb in boxset else ("A" if nb in R else "C")
                                    mode[e] = "C" if art[e] == "C" else (
                                        ("O" if e == d_half else "N") if band_ow else "T")
                                elif e == out_d:
                                    f = feat[i][h]
                                    if not f:
                                        art[e] = mode[e] = "C"
                                    else:
                                        art[e] = "A"
                                        if f == "rd" or not perp_ow or ps is None:
                                            mode[e] = "T"
                                        else:
                                            pdh = pfirst if ps == 0 else opp(pfirst)
                                            mode[e] = "O" if e == pdh else ("N" if e == opp(pdh) else "?")
                                else:
                                    art[e] = "I"
                                    if ps is not None and perp_ow:
                                        pdh = pfirst if ps == 0 else opp(pfirst)
                                        mode[e] = "O" if e == pdh else ("N" if e == opp(pdh) else "?")
                                    else:
                                        mode[e] = "T"
                            key = canon(tuple(x + y for x, y in zip(art, mode)))
                            pieces[bucket][key] += 1
                            if combo == "oneway":
                                artpat[canon(tuple(art))] += 1
                                ncell += 1
                            examples.setdefault(key, (city, c))
    print("boxes", nbox, "box cells", ncell, dict(kinds))
    for b in ("oneway", "twoway", "mixed"):
        tot = sum(pieces[b].values())
        print("\n== %s: %d distinct pieces, %d cells" % (b, len(pieces[b]), tot))
        acc = 0
        for k, n in pieces[b].most_common():
            acc += n
            print("  %5d  %5.1f%%  %s  %s" % (n, 100.0 * acc / tot, " ".join(k), examples[k]))
    allp = set(pieces["oneway"]) | set(pieces["twoway"]) | set(pieces["mixed"])
    print("\nall distinct pieces:", len(allp))
    print("art patterns:", len(artpat), sorted(artpat.items(), key=lambda t: -t[1]))
    json.dump({b: {" ".join(k): n for k, n in pieces[b].items()} for b in pieces}, open(sys.argv[1], "w"), indent=0)


main()
