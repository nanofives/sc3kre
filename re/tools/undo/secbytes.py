"""secbytes.py DIR group a b c [...] - per-byte view of one save section across saves test_<a>.sc3, test_<b>.sc3, ...

Prints each differing offset with the byte in every save, and groups runs. With three saves (before, after, undo) it
tags each run: KEPT (undo == after, the action's change survived undo), NEW (undo differs from both), BACK (undo ==
before). Group = the section's group id in hex (e.g. 029ca804).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv, args = [sys.argv[0], "x", "y"], sys.argv[1:]
exec(open(os.path.join(HERE, "snapdiff.py")).read().split("a, b = load")[0])


def section(path, grp):
    out = {}
    for k, (kind, body) in load(path).items():
        if kind != "pay":
            continue
        _, es = CP.parse_sections(body)
        for e in es:
            if e["group"] == grp:
                out[(e["type"], e["instance"])] = body[e["abs"]:e["abs"] + e["size"]]
    return out


d, grp, names = args[0], int(args[1], 16), args[2:]
secs = [section(os.path.join(d, "test_%s.sc3" % n), grp) for n in names]
for key in secs[0]:
    bs = [s.get(key, b"") for s in secs]
    n = max(len(b) for b in bs)
    diff = [i for i in range(n) if len({b[i] if i < len(b) else None for b in bs}) > 1]
    print("section type=0x%08x inst=0x%08x sizes %s, %d differing offsets" % (key[0], key[1], [len(b) for b in bs], len(diff)))
    runs, cur = [], []
    for i in diff:
        if cur and i - cur[-1] > 4:
            runs.append(cur); cur = []
        cur.append(i)
    if cur:
        runs.append(cur)
    for r in runs:
        lo, hi = r[0], r[-1] + 1
        cells = [b[lo:hi].hex() for b in bs]
        tag = ""
        if len(bs) == 3:
            tag = "KEPT" if cells[2] == cells[1] else "BACK" if cells[2] == cells[0] else "NEW"
        print("  +%-7d %-4s %s" % (lo, tag, "  ".join(cells)))
