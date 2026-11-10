r"""What a load without the style_mix package does to the style copies (task stylemix).
Compares a save made WITH the package against the game's save of that same city loaded WITHOUT it (taken while
the city was still paused, so no sim time passed). Per lot that held a copy (id >= 400000): same base id, another
id, or nothing.   py -3.12 stylemix_verify_nomod_diff.py <with_mod.sc3> <loaded_without_mod_paused.sc3>"""
import collections
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import occupant_layer


def load(p):
    c, s0, s1, cnt, ver, recs = occupant_layer.parse(p)
    return {(r["a"], r["b"]): (r["key"][2], r["t18"]) for r in recs if r["key"][0] == 0x207EDC0E}, len(recs)


B, nb = load(sys.argv[1])
D, nd = load(sys.argv[2])
copies = {p: v for p, v in B.items() if v[0] >= 400000}
print("occupants %d -> %d, copies before %d" % (nb, nd, len(copies)))
res, same_type = collections.Counter(), 0
for pos, (i, t) in copies.items():
    c = D.get(pos)
    base = i - 1500000 if i >= 1500000 else i - 400000
    if c is None:
        res["no building on that lot"] += 1
        continue
    res["same base id" if c[0] == base else "other id"] += 1
    same_type += c[1] == t
print(dict(res), "| same building type (t18):", same_type)
print("lots without a copy that changed:", sum(1 for p, v in B.items() if v[0] < 400000 and D.get(p) != v))
print("copies left after load:", sum(1 for v in D.values() if v[0] >= 400000))
