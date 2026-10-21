"""cmp_saves.py DIR a b [a b ...] - compare test_<a>.sc3 / test_<b>.sc3 by section; known benign sections marked."""
import sys, os
S = os.path.dirname(os.path.abspath(__file__))
sys.argv, args = [sys.argv[0], os.path.join(S, "snapdiff.py")], sys.argv[1:]
exec(open(os.path.join(S, "snapdiff.py")).read().split("a, b = load")[0])
BENIGN = {0x20a7ae7f: "crime cache (module global)", 0xc0a81498: "pollution cache (module global)",
          0x61448030: "flammability (sim recomputes)"}
d = args[0]
pairs = args[1:]
for i in range(0, len(pairs), 2):
    a, b = pairs[i], pairs[i + 1]
    fa, fb = os.path.join(d, "test_%s.sc3" % a), os.path.join(d, "test_%s.sc3" % b)
    if not (os.path.exists(fa) and os.path.exists(fb)):
        print("S%s vs S%s: missing file" % (a, b)); continue
    if open(fa, "rb").read() == open(fb, "rb").read():
        print("S%s == S%s  byte-identical" % (a, b)); continue
    A, B = load(fa), load(fb)
    bad, benign = [], []
    for k in A:
        if A[k][0] != "pay" or A[k][1] == B.get(k, (None, None))[1]: continue
        _, ea = CP.parse_sections(A[k][1]); _, eb = CP.parse_sections(B[k][1])
        sa = {(e["type"], e["group"], e["instance"]): A[k][1][e["abs"]:e["abs"] + e["size"]] for e in ea}
        sb = {(e["type"], e["group"], e["instance"]): B[k][1][e["abs"]:e["abs"] + e["size"]] for e in eb}
        for s in set(sa) | set(sb):
            if sa.get(s) == sb.get(s): continue
            x, y = sa.get(s, b""), sb.get(s, b"")
            nd = sum(1 for j in range(min(len(x), len(y))) if x[j] != y[j]) + abs(len(x) - len(y))
            tag = "%08x %d B diff%s" % (s[1], nd, "" if len(x) == len(y) else " (size %d -> %d)" % (len(x), len(y)))
            (benign if s[1] in BENIGN else bad).append(tag + ("  [" + BENIGN[s[1]] + "]" if s[1] in BENIGN else ""))
    print("S%s vs S%s: %s%s" % (a, b, "EXACT except known benign" if not bad else "DIFFERS: " + "; ".join(bad),
                                "" if not benign else "  | benign: " + "; ".join(benign)))
