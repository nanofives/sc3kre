#!/usr/bin/env python3
r"""avends_dbvdiff.py - offline check for task avends F2a (2026-11-09): DBV's twin (diagbv.bands) with the bend-z-tee
end off and on, over the shipped cities and extra saves. Lists every band whose end kinds, verdict or written cells
change; any change that is not an end turning "ragged" -> "bend-z-tee" is printed as OUTSIDE.

  py -3.12 -m netmod.avends_dbvdiff [extra.sc3 ...] [--only]
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from netmod import avx, diagbv as DB      # noqa: E402


def run(road, stamps, on):
    DB.BENDT = on
    out = {}
    for b in DB.bands(road, stamps):
        key = (b["axis"], tuple(b["rows"][0]))
        out[key] = (b["ok"], b.get("why", ""), dict(b.get("ends", {})), b["want"])
    return out


def main(argv):
    E = avx._env()
    extra = [a for a in argv if not a.startswith("-")]
    saves = ([] if "--only" in argv else sorted(glob.glob(os.path.join(E["g"], "Cities", "*.sc3")))) + extra
    stamps = DB.load_stamps(DB.PACK)
    tot_in = tot_out = 0
    for path in saves:
        road = DB.road_of_save(path)
        a, b = run(road, stamps, False), run(road, stamps, True)
        ch = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
        n_in = n_out = 0
        for k in ch:
            x, y = a.get(k), b.get(k)
            ends_x, ends_y = (x or (0, 0, {}, {}))[2], (y or (0, 0, {}, {}))[2]
            diff = {e for e in (0, 1) if ends_x.get(e) != ends_y.get(e)}
            good = x and y and diff and all(ends_x.get(e) == "ragged" and ends_y.get(e) == "bend-z-tee" for e in diff)
            if good:
                n_in += 1
                print("   %s band axis %d first row %s: ends %s -> %s, ok %s -> %s, cells %d -> %d" % (
                    os.path.basename(path), k[0], k[1], ends_x, ends_y, x[0], y[0], len(x[3]), len(y[3])))
            else:
                n_out += 1
                print("   ### OUTSIDE %s band axis %d first row %s: %s -> %s" % (os.path.basename(path), k[0], k[1],
                      x and (x[0], x[1], x[2]), y and (y[0], y[1], y[2])))
        tot_in += n_in
        tot_out += n_out
        print("%-28s bands %3d, changed %d (bend-z-tee %d, other %d)" % (os.path.basename(path), len(b), len(ch), n_in, n_out))
    print("total: ends ragged -> bend-z-tee %d, other changes %d" % (tot_in, tot_out))
    return 1 if tot_out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
