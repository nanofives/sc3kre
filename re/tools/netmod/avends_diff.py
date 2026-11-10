#!/usr/bin/env python3
r"""avends_diff.py - offline check for task avends (2026-11-09): the AVX twin (avjunc_rule, the C block's twin) with one
of the avends switches off and on, over the shipped cities and extra saves. Every save is read as a RELOAD sees it: the
saved tiles plus the save's variant list (section 0x4E56), with the installed tables' piece classes
(avjunc_rule.city_layer_saved). Shipped cities hold no variant list, so for them this is the stock grid.

A changed box / nose inside an --expect window is the group's case; anything else is printed as OUTSIDE.

  py -3.12 -m netmod.avends_diff --switch AVTEE [--expect x0,z0,x1,z1 ...] [--tables DIR] [-v] [extra.sc3 ...] [--only]
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from netmod import avx, avjunc_rule as R      # noqa: E402

TABLES = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "tree", "mods", "netmod", "tables"))


def run(path, ids, tdir, switch, on):
    setattr(R, switch, on)
    L, roads, P = R.city_layer_saved(path, ids, tdir)
    res = R.find_c(L, P, roads)
    boxes = {frozenset(bx["cells"]): tuple(sorted(R.box_modes(bx).items())) for bx in res["boxes"]}
    noses = {n: (tuple(d["ends"]), d["state"]) for n, d in res["noses"].items()}
    return boxes, noses


def main(argv):
    E = avx._env()
    a = list(argv)
    def opt(name, many=False):
        out = []
        while name in a:
            i = a.index(name)
            out.append(a[i + 1])
            del a[i:i + 2]
        return out if many else (out[0] if out else None)
    switch = opt("--switch") or "AVTEE"
    tdir = opt("--tables") or TABLES
    wins = [tuple(map(int, w.split(","))) for w in opt("--expect", True)]
    verbose = "-v" in a
    only = "--only" in a
    extra = [x for x in a if not x.startswith("-")]
    saves = [] if only else sorted(glob.glob(os.path.join(E["g"], "Cities", "*.sc3")))
    saves += extra
    def inside(c):
        return any(x0 <= c[0] <= x1 and z0 <= c[1] <= z1 for x0, z0, x1, z1 in wins)
    tot_in = tot_out = 0
    print("switch %s, tables %s" % (switch, tdir))
    for path in saves:
        b0, n0 = run(path, E["ids"], tdir, switch, False)
        b1, n1 = run(path, E["ids"], tdir, switch, True)
        chb = [k for k in set(b0) | set(b1) if b0.get(k) != b1.get(k)]
        chn = [k for k in set(n0) | set(n1) if n0.get(k) != n1.get(k)]
        out = [k for k in chb if not all(inside(c) for c in k)] + [k for k in chn if not inside(k)]
        tot_out += len(out)
        tot_in += len(chb) + len(chn) - len(out)
        print("%-28s boxes %4d -> %4d  changed boxes %3d, noses %3d, outside the expected windows %d" % (
            os.path.basename(path), len(b0), len(b1), len(chb), len(chn), len(out)))
        if verbose:
            for k in chb:
                print("   %s box %s %s" % ("+" if k in b1 else "-", sorted(k), dict(b1.get(k) or b0.get(k))))
            for k in chn:
                print("   nose %s %s -> %s" % (k, n0.get(k), n1.get(k)))
        for k in out:
            print("   ### OUTSIDE:", sorted(k) if isinstance(k, frozenset) else k)
    print("total: changes in the expected windows %d, outside %d" % (tot_in, tot_out))
    return 1 if tot_out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
