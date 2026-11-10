r"""Count building styles in a city save (task stylemix). py -3.12 stylemix_verify_count.py <save.sc3> [...]
Style of an occupant key {0x207EDC0E, 0x57E, id}: id >= 1500000 -> set 6523f3d5 (Asian), 400000.. -> e523f3fb
(European), else base. 'mixable' = base ids that one of the sets re-skins (the ids that have style copies)."""
import collections, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import occupant_layer
def style(i):
    return "asian" if i >= 1500000 else "euro" if i >= 400000 else "base"
for p in sys.argv[1:]:
    c, s0, s1, cnt, ver, recs = occupant_layer.parse(p)
    b = [r for r in recs if r["key"][0] == 0x207EDC0E and r["key"][1] == 0x57E]
    ids = collections.Counter(r["key"][2] for r in b)
    mix = {i - 400000 for i in ids if 400000 <= i < 1500000} | {i - 1500000 for i in ids if i >= 1500000}
    st = collections.Counter(style(r["key"][2]) for r in b)
    mixable_base = sum(n for i, n in ids.items() if i in mix)
    print("%s: occupants %d, buildings %d, base %d (of them mixable ids %d), euro %d, asian %d, 36001 %d, distinct euro ids %d, asian ids %d"
          % (os.path.basename(p), len(recs), len(b), st["base"], mixable_base, st["euro"], st["asian"], ids[36001],
             len([i for i in ids if 400000 <= i < 1500000]), len([i for i in ids if i >= 1500000])))
    # densest 16x16 window holding all three styles of mixable buildings
    grid = collections.defaultdict(collections.Counter)
    for r in b:
        i = r["key"][2]; s = style(i)
        if s != "base" or i in mix:
            grid[(r["a"] // 16, r["b"] // 16)][s] += 1
    best = sorted(grid.items(), key=lambda kv: -min(kv[1]["base"], kv[1]["euro"], kv[1]["asian"]))[:5]
    print("  windows (16-cell) with all three:", [((k[0]*16, k[1]*16), dict(v)) for k, v in best])
