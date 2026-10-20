"""avjunc scan: every non-straight segment of every straight avenue band in the shipped cities, and whether AVX boxes it"""
import collections, glob, json, os, sys
sys.path.insert(0, os.getcwd())
from netmod import tiler, avx
E = avx._env()
IDS = E["ids"]
out = {"cities": {}, "segments": []}
tot = collections.Counter(); unc = collections.Counter(); cov = collections.Counter()
for path in sorted(glob.glob(os.path.join(E["g"], "Cities", "*.sc3"))):
    city = os.path.basename(path)[:-4]
    s = tiler.City.load(path).layers["surface"]
    R = {c for c, p in s.items() if p.id in IDS and p.flags is None}
    js, _ = avx.find(R, {c: s[c].id for c in R})
    boxcells = {}
    for j in js:
        for c in j["want"]:
            boxcells[c] = j["kind"]
    road = lambda c: c in R
    segs = {}
    for (x, z), p in s.items():
        if p.id != 11204 or (p.state & 3) not in (1, 2):
            continue
        st = p.state & 3
        o = (x + 1, z) if st == 1 else (x, z + 1)
        q = s.get(o)
        if q is None or q.id != 11204:
            continue
        step = (0, 1) if st == 1 else (1, 0)
        for sg in (1, -1):
            cells, sig, k = [], [], 1
            while True:
                a = (x + sg * step[0] * k, z + sg * step[1] * k)
                b = (o[0] + sg * step[0] * k, o[1] + sg * step[1] * k)
                pa, pb = s.get(a), s.get(b)
                if not (road(a) and road(b)):
                    term = "end"; break
                if pa.id == 11204 and pb.id == 11204:
                    term = "band"; break
                cells += [a, b]; sig.append("%d|%d" % (pa.id, pb.id)); k += 1
                if k > 8:
                    term = "long"; break
            if not cells:
                continue
            key = frozenset(cells)
            if key in segs:
                continue
            if sg < 0:
                sig = sig[::-1]
            covered = all(c in boxcells for c in cells)
            kinds = sorted({boxcells[c] for c in cells if c in boxcells})
            segs[key] = dict(city=city, axis="z" if st == 1 else "x", sig=" ".join(sig), term=term, n=len(sig),
                             covered=covered, kinds=kinds, at=sorted(cells)[0])
    for v in segs.values():
        lab = ("%s [%s]" % (v["sig"], v["term"]))
        tot[lab] += 1
        (cov if v["covered"] else unc)[lab] += 1
        out["segments"].append({k: (list(v[k]) if k == "at" else v[k]) for k in v})
    out["cities"][city] = {"segments": len(segs), "covered": sum(v["covered"] for v in segs.values()),
                           "avx_junctions": collections.Counter(j["kind"] for j in js)}
    print("%-24s segments %5d  covered by AVX %5d  avx %s" % (city, len(segs), out["cities"][city]["covered"],
          dict(out["cities"][city]["avx_junctions"])), flush=True)
print("\nCOVERED by AVX (top):")
for k, n in cov.most_common(25): print("  %5d  %s" % (n, k))
print("\nNOT covered (top 60):")
for k, n in unc.most_common(60): print("  %5d  %s" % (n, k))
json.dump(out, open(sys.argv[1], "w"), indent=0)
