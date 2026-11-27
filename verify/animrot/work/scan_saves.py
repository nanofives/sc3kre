#!/usr/bin/env python3
"""animrot: list occupant records of given instance ids in every save of a Cities folder.

  py -3.12 scan_saves.py <Cities dir> <inst>[,<inst>...]
"""
import collections
import glob
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "re" / "tools"))
from occupant_layer import parse  # noqa: E402


def main(a):
    want = {int(x, 0) for x in a[1].split(",")}
    for f in sorted(glob.glob(os.path.join(a[0], "*.sc3"))):
        try:
            c, s0, s1, cnt, ver, recs = parse(f)
        except Exception as e:  # noqa: BLE001
            print(os.path.basename(f), "ERR", e)
            continue
        hits = [(hex(r["key"][0]), hex(r["key"][1]), r["key"][2], r["a"], r["b"], r["rot"], r.get("sa"), r.get("sb"))
                for r in recs if r["key"][2] in want]
        print(os.path.basename(f), len(recs), len(hits), hits[:8])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
