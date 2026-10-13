#!/usr/bin/env python3
r"""nb_map.py - print and compare live cell reads from nb_drive.py cells (2026-10-13, task netbridge).

  py nb_map.py show A.jsonl                 # grid of id.state per cell (rows = z)
  py nb_map.py diff A.jsonl B.jsonl [--base TABLE...]
      cells that differ between two reads; with --base (a netpack tables\*.txt "<variant> <base>" file, repeatable)
      a variant in B that matches its base in A counts as "variant of the same piece", reported apart
"""
import json
import sys


def load(path):
    g = {}
    for line in open(path, encoding="utf-8"):
        if line.startswith("{"):
            c = json.loads(line)
            if "piece" in c:
                g[(c["x"], c["y"])] = (c["piece"], c["state"])
    return g


def show(g):
    if not g:
        print("(no network pieces)")
        return
    xs = sorted({x for x, _ in g})
    zs = sorted({z for _, z in g})
    print("     " + " ".join("%8d" % x for x in range(xs[0], xs[-1] + 1)))
    for z in range(zs[0], zs[-1] + 1):
        row = [g.get((x, z)) for x in range(xs[0], xs[-1] + 1)]
        if any(row):
            print("%4d " % z + " ".join("%8s" % ("%d.%d" % v if v else "") for v in row))


def bases(paths):
    out = {}
    for p in paths:
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                v, b = line.split()[:2]
                out[int(v)] = int(b)
    return out


def main(argv):
    if len(argv) >= 3 and argv[1] == "show":
        show(load(argv[2]))
        return 0
    if len(argv) >= 4 and argv[1] == "diff":
        a, b = load(argv[2]), load(argv[3])
        tab = bases([argv[i + 1] for i, x in enumerate(argv) if x == "--base"])
        same, var, other = 0, [], []
        for k in sorted(set(a) | set(b)):
            va, vb = a.get(k), b.get(k)
            if va == vb:
                same += 1
            elif va and vb and vb[0] in tab and tab[vb[0]] == va[0] and va[1] == vb[1]:
                var.append((k, va, vb))
            else:
                other.append((k, va, vb))
        print("cells equal: %d, variant of the same piece: %d, other differences: %d" % (same, len(var), len(other)))
        for k, va, vb in var:
            print("  variant  x=%-4d z=%-4d %s -> %s" % (k[0], k[1], va, vb))
        for k, va, vb in other:
            print("  OTHER    x=%-4d z=%-4d %s -> %s" % (k[0], k[1], va, vb))
        return 0 if not other else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
