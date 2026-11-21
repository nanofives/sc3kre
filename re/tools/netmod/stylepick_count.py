r"""stylepick_count.py - task stylepick (2026-11-21): which style the NEW buildings of a save have, and whether the
standing ones kept theirs.

  py -3.12 stylepick_count.py <save.sc3>                 style counts + the saved scheme / stylepick records
  py -3.12 stylepick_count.py <before.sc3> <after.sc3>   the same for <after>, split into buildings that stand where
                                                         they stood in <before> with the same key ("kept") and the rest
                                                         ("new"), plus how many kept cells changed key ("changed")

Style of an occupant key {0x207EDC0E, 0x57E, id}: 400000.. European copy, 1500000.. Asian copy, 2600000.. North
American copy (style_mix 1.1.0), else base. "base, re-skinnable" = a base id one of the sets re-skins (it has a
copy): it draws in the city's own building set. Records: the stock scheme record {0x0525A6B9, 0x4525A6E2, 1}
(building set, flora, landscape) and sc3netmod STYLEPICK's {0x0525A6B9, 0x4525A6E2, 0x5354594C} (magic, set, mix).
"""
import collections
import os
import re
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import occupant_layer  # noqa: E402

SETS = {0: "North American", 0xE523F3FB: "European", 0x6523F3D5: "Asian"}


def style(i):
    if 2600000 <= i < 2665536:
        return "na_copy"
    if 1500000 <= i < 1565536:
        return "asian"
    if 400000 <= i < 465536:
        return "euro"
    return "base"


def record(raw, inst, n):
    pat = struct.pack("<II", 0x4525A6E2, inst)
    o = raw.find(pat)
    while o >= 0 and struct.unpack_from("<I", raw, o + 8)[0] != 0x0525A6B9:
        o = raw.find(pat, o + 1)
    if o < 0:
        return None
    off, size = struct.unpack_from("<II", raw, o + 12)
    if size < 4 * n:
        return ("size %d" % size,)
    return struct.unpack_from("<%dI" % n, raw, off)


def buildings(p):
    c, s0, s1, cnt, ver, recs = occupant_layer.parse(p)
    return [r for r in recs if r["key"][0] == 0x207EDC0E and r["key"][1] == 0x57E]


def counts(b, reskinnable):
    c = collections.Counter()
    for r in b:
        s = style(r["key"][2])
        if s == "base" and r["key"][2] in reskinnable:
            s = "base_reskinnable"
            c["  by_" + "+".join(sorted(reskinnable[r["key"][2]]))] += 1
        c[s] += 1
    return c


def fmt(c):
    keys = ("base", "base_reskinnable", "na_copy", "euro", "asian")
    by = sorted(k for k in c if k.startswith("  by_"))
    return ", ".join("%s %d" % (k, c[k]) for k in keys) + ("  (re-skinnable %s)" % ", ".join(
        "%s %d" % (k.strip()[3:], c[k]) for k in by) if by else "")


def main(argv):
    after = argv[-1]
    raw = open(after, "rb").read()
    sch, sp = record(raw, 1, 3), record(raw, 0x5354594C, 3)
    print("%s" % os.path.basename(after))
    if sch:
        print("  scheme record: building set %08x (%s), flora %08x, landscape %08x"
              % (sch[0], SETS.get(sch[0], "?"), sch[1], sch[2]))
    print("  stylepick record: %s" % ("none" if not sp else "magic %08x, style %08x (%s), mix %d"
                                      % (sp[0], sp[1], SETS.get(sp[1], "?"), sp[2]) if len(sp) == 3 else sp[0]))
    b = buildings(after)
    ids = {r["key"][2] for r in b}
    reskinnable = collections.defaultdict(set)    # base id -> the sets that re-skin it
    for i in ids:
        if style(i) in ("euro", "asian"):
            reskinnable[i - {"euro": 400000, "asian": 1500000}[style(i)]].add(style(i))
    fam = os.environ.get("SP_BUILDFAM", os.path.join(os.path.dirname(os.path.abspath(after)), "..", "mods", "netmod",
                                                     "overlay", "Apps", "Res", "BUILDFAM.IXF"))
    if os.path.exists(fam):                       # every base id a set re-skins, from the family lines
        off = {"euro": 400000, "asian": 1500000, "na_copy": 2600000}
        for m in re.finditer(rb"Key:\s*1406,545184782,(\d+),", open(fam, "rb").read()):
            i = int(m.group(1))
            if style(i) in ("euro", "asian"):
                reskinnable[i - off[style(i)]].add(style(i))
    if len(argv) == 1:
        print("  buildings %d: %s" % (len(b), fmt(counts(b, reskinnable))))
        return 0
    before = {}
    for r in buildings(argv[0]):
        before[(r["a"], r["b"])] = r["key"][2]
    kept, new, changed = [], [], 0
    for r in b:
        k = (r["a"], r["b"])
        if k in before and before[k] == r["key"][2]:
            kept.append(r)
        else:
            new.append(r)
            if k in before:
                changed += 1
    print("  buildings %d: kept %d, new or rebuilt %d (of them on a cell that held another building before %d)"
          % (len(b), len(kept), len(new), changed))
    print("  kept: %s" % fmt(counts(kept, reskinnable)))
    print("  new:  %s" % fmt(counts(new, reskinnable)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
