"""snapdiff.py A.sc3 B.sc3 - compare two city saves at IXF-record and section level."""
import sys, os, hashlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ixf_parse, city_parse as CP

def load(p):
    recs, d = ixf_parse.parse(p)
    out = {}
    for i, r in enumerate(recs):
        body = d[r["offset"]:r["offset"] + r["size"]]
        key = (r["type"], r.get("group"), r.get("instance"))
        if CP.is_compressed_payload(body):
            dec, _ = CP.parse_payload(body)
            out[key] = ("pay", dec)
        else:
            out[key] = ("raw", body)
    return out

a, b = load(sys.argv[1]), load(sys.argv[2])
print("records A=%d B=%d" % (len(a), len(b)))
for k in sorted(set(a) | set(b), key=str):
    if k not in a or k not in b:
        print("ONLY IN", "A" if k in a else "B", k); continue
    ka, da = a[k]; kb, db = b[k]
    if da == db: continue
    print("REC DIFF type=0x%08x grp=%s inst=%s kind=%s size %d -> %d" % (k[0], k[1], k[2], ka, len(da), len(db)))
    if ka == "pay":
        _, ea = CP.parse_sections(da); _, eb = CP.parse_sections(db)
        sa = {(e["type"], e["group"], e["instance"]): da[e["abs"]:e["abs"] + e["size"]] for e in ea}
        sb = {(e["type"], e["group"], e["instance"]): db[e["abs"]:e["abs"] + e["size"]] for e in eb}
        same = 0
        for s in sorted(set(sa) | set(sb)):
            if s not in sa or s not in sb:
                print("   section ONLY IN", "A" if s in sa else "B", "%08x:%08x:%d" % s); continue
            if sa[s] == sb[s]: same += 1; continue
            x, y = sa[s], sb[s]
            nd = sum(1 for i in range(min(len(x), len(y))) if x[i] != y[i])
            first = next((i for i in range(min(len(x), len(y))) if x[i] != y[i]), None)
            print("   section %08x:%08x:%-3d %-16s size %d -> %d, %d bytes differ, first at +%s"
                  % (s + (CP.KNOWN_CLASS.get(s[1], ""), len(x), len(y), nd, first)))
        print("   %d sections identical" % same)
