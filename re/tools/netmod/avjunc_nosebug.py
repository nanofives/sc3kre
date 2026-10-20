import glob, os, sys, collections
sys.path.insert(0, os.getcwd())
from netmod import tiler, avx
E = avx._env()
n = collections.Counter(); ex = {}
for path in sorted(glob.glob(os.path.join(E["g"], "Cities", "*.sc3"))):
    s = tiler.City.load(path).layers["surface"]
    R = {c for c, p in s.items() if p.id in E["ids"] and p.flags is None}
    js, _ = avx.find(R, {c: s[c].id for c in R})
    for j in js:
        for c, (pid, st) in j["want"].items():
            if pid in avx.ARM.values() and s[c].id != 11204:
                n[s[c].id] += 1; ex.setdefault(s[c].id, (os.path.basename(path), c))
print("nose cells AVX would write over a non-11204 piece:", dict(n), ex)
