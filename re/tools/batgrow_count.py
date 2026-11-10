#!/usr/bin/env python3
r"""batgrow_count.py - task batconvert (2026-11-10): count the buildings of a save by origin.

  py -3.12 re/tools/batgrow_count.py <city.sc3> [...]

Per save: occupants, stock buildings (key {0x207EDC0E, 0x57E, id < 36000}), growable tests (36001-36099), BAT slots
(36100-36999), converted BAT buildings (37000-37999, per id), European style copies (400000 + base) and Asian ones
(1500000 + base), read with occupant_layer.parse (the same reader batslots_lab.py save uses).
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import occupant_layer  # noqa: E402

BLD = (0x207EDC0E, 0x57E)


def count(path):
    c, s0, s1, cnt, ver, recs = occupant_layer.parse(path)
    ids = collections.Counter(x["key"][2] for x in recs if tuple(x["key"][:2]) == BLD)
    out = collections.OrderedDict()
    out["occupants"] = len(recs)
    out["stock"] = sum(v for k, v in ids.items() if k < 36000)
    out["growable tests 36001-36099"] = sum(v for k, v in ids.items() if 36001 <= k <= 36099)
    out["bat slots 36100-36999"] = sum(v for k, v in ids.items() if 36100 <= k <= 36999)
    out["converted BAT 37000-37999"] = sum(v for k, v in ids.items() if 37000 <= k <= 37999)
    out["european +400000"] = sum(v for k, v in ids.items() if 400000 <= k < 1500000)
    out["asian +1500000"] = sum(v for k, v in ids.items() if k >= 1500000)
    out["per converted id"] = {k: ids[k] for k in sorted(ids) if 37000 <= k <= 37999}
    return out


def main(argv):
    for p in argv:
        print("==", os.path.basename(p))
        for k, v in count(p).items():
            print("  %-28s %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) if len(sys.argv) > 1 else (print(__doc__) or 2))
