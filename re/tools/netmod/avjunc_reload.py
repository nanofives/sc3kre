"""avjunc_reload.py (task avjunc): offline reload check: write the rule's own pieces into a shipped city, run the rule again, compare. py -3.12 netmod/avjunc_reload.py "London, England" (from re/tools)"""
import os, sys, json, glob
sys.path.insert(0, os.getcwd())
from netmod import avx, avjunc_rule as R

E = avx._env()
T = json.load(open("netmod/examples/avenue_junctions/avjunc_pieces.json"))
own = {b["id"]: {"outline": b["outline"], "kind": "box"} for b in T["box"]}
from netmod import avjunc_build as AB
for k, v in list(T["nose_oneway"].items()) + list(T["nose_twoway"].items()):
    own[v] = {"outline": "CACA", "kind": "nose"}
for k, v in list(AB.NOSE_OW_LINK.items()) + list(AB.NOSE_TW_LINK.items()):
    own[v] = {"outline": "CACA", "kind": "link"}
canon = {(b["outline"], b["modes"]): b["id"] for b in T["box"]}


def piece_of(o, m):
    for (co, cm), pid in canon.items():
        for k in range(4):
            if R.rot(co, k) == o and R.rot(cm, k) == m:
                return pid, k
    return None


def write(L, P, roads):
    res = R.find_c(L, P, roads)
    L2 = dict(L)
    for bi, bx in enumerate(res["boxes"]):
        dm = frozenset(a for a in R.box_arms(bx) if not res["arm_status"][(bi, a)])
        for c, (o, m) in R.box_modes(bx, dm).items():
            pc = piece_of(o, m)
            if pc:
                L2[c] = pc
    for n, d in res["noses"].items():
        ow = R.nose_oneway(L, P, res, res["bands"], n, d)
        ends = "".join(s for s in "NESW" if "NESW".index(s) in R.nose_kind(d))
        ends = {"": "", "E": "E", "W": "W", "EW": "EW"}.get(ends.replace("N", "").replace("S", ""), "")
        if d.get("link"):
            tab = AB.NOSE_OW_LINK if ow else AB.NOSE_TW_LINK
        else:
            tab = T["nose_oneway"] if ow else T["nose_twoway"]
        if ends in tab:
            L2[n] = (tab[ends], d["state"])
    return res, L2


city = sys.argv[1]
L, roads = R.city_layer(os.path.join(E["g"], "Cities", city + ".sc3"), E["ids"])
P = R.Pieces(own=own)
res1, L2 = write(L, P, roads)
res2, L3 = write(L2, P, roads | set(L2))
k1 = {frozenset(b["cells"]) for b in res1["boxes"]}
k2 = {frozenset(b["cells"]) for b in res2["boxes"]}
print("boxes first", len(k1), "after reload", len(k2), "lost", [sorted(k)[0] for k in k1 - k2][:10],
      "new", [sorted(k)[0] for k in k2 - k1][:10])
diff = [c for c in set(L2) | set(L3) if L2.get(c) != L3.get(c)]
print("cells that would change on the second pass:", len(diff), sorted(diff)[:12])
