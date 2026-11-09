#!/usr/bin/env python3
r"""avdiamond_diff.py - offline check for task avdiamond (2026-11-09): the AVX rule (avjunc_rule, the C block's twin)
with and without the AVDIAMOND change (ramp ground ends as arms, crossing rows split a segment touching a ramp), over
the shipped cities and any extra saves. A box / nose that differs must lie on a segment walk that touches a ramp
(P.ramp_cells: the walk's positions, its seed pair and the row that ended it), or touch a ramp cell (validation
used to read a ramp as an unknown piece and drop the box beside it); a nose must be beside such a box. Anything else is a change outside the
ramp cases.

  py -3.12 -m netmod.avdiamond_diff [extra.sc3 ...] [--only extra]
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from netmod import avx, avjunc_rule as R      # noqa: E402


def run(path, ids, on):
    R.DIAMOND = on
    L, roads = R.city_layer(path, ids)
    P = R.Pieces()
    res = R.find_c(L, P, roads)
    boxes = {}
    for bx in res["boxes"]:
        boxes[frozenset(bx["cells"])] = tuple(sorted(R.box_modes(bx).items()))
    noses = {n: (tuple(d["ends"]), d["state"]) for n, d in res["noses"].items()}
    return L, P, boxes, noses, res


def main(argv):
    E = avx._env()
    extra = [a for a in argv if not a.startswith("--")]
    saves = [] if "--only" in argv else sorted(glob.glob(os.path.join(E["g"], "Cities", "*.sc3")))
    saves += extra
    tot_out = tot_in = 0
    for path in saves:
        L0, _, b0, n0, _ = run(path, E["ids"], False)
        L1, P1, b1, n1, res1 = run(path, E["ids"], True)
        gone = [k for k in b0 if k not in b1 or b0[k] != b1[k]]
        new = [k for k in b1 if k not in b0 or b0.get(k) != b1[k]]
        ng = [k for k in n0 if n0[k] != n1.get(k)]
        nn = [k for k in n1 if n1[k] != n0.get(k)]
        rc = set(P1.ramp_cells)
        # a box beside a ramp cell: before, validation read the ramp as an unknown piece ('X') and dropped the box
        rc |= {(x + dx, z + dz) for (x, z), q in L1.items() if q[0] in R.RAMP_END
               for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))}
        rbox = [k for k in gone + new if set(k) & rc]
        out = [k for k in gone + new if k not in rbox]
        near = {(x + dx, z + dz) for k in rbox for (x, z) in k for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))}
        nout = [k for k in set(ng + nn) if k not in rc and k not in near]   # noses: beside a ramp-case box
        tot_out += len(out) + len(nout)
        tot_in += len(gone) + len(new) - len(out)
        print("%-28s boxes %4d -> %4d  changed %3d (ramp %3d, other %d)  noses changed %3d (other %d)" % (
            os.path.basename(path), len(b0), len(b1), len(gone) + len(new), len(gone) + len(new) - len(out), len(out),
            len(set(ng + nn)), len(nout)))
        if "-v" in argv:
            for k in new:
                print("   + box", sorted(k), dict(b1[k]))
            for k in gone:
                print("   - box", sorted(k))
        for k in out + nout:
            print("   ### OUTSIDE GROUP D:", sorted(k) if isinstance(k, frozenset) else k)
    print("total: changed boxes touching a ramp %d, changes outside the ramp cases %d" % (tot_in, tot_out))
    return 1 if tot_out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
