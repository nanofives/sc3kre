#!/usr/bin/env python3
r"""nr_predict.py - the simulator's per-cell prediction for one in-game rectangle retile, and the comparison with a
live read-back (2026-10-13, netrules in-game check).

  py -3 -m netmod.nr_predict predict <rules dir> <save> X0,Z0,X1,Z1 [--mask 1] [--margin 3] > pred.json
  py -3 -m netmod.nr_predict compare pred.json live.jsonl     # live.jsonl = `nr_drive.py cells` output

The prediction runs tiler.Tiler.retile_rect (FUN_100151f1 -> FUN_10016a25 -> FUN_1001547b) on the save, exactly the
retile GZ message 0x637c0dab {mask, x0<<16|z0, x1<<16|z1} triggers, and lists every surface cell of the window
(rectangle + margin) with the saved and the predicted piece.
"""
import argparse
import json
import sys

from . import netrules, paths, tiler


def predict(a):
    g = paths.Game()
    rules = tiler.Rules(a.rules)
    pe = tiler.load_pe(g)
    ex = netrules.exemplars(g)
    city = tiler.City.load(a.save)
    x0, z0, x1, z1 = (int(v) for v in a.rect.split(","))
    opts = tiler.Options()
    c2 = netrules.prepared(city, opts)
    T = tiler.Tiler(rules, c2, opts, pe, ex)
    T.retile_rect(a.mask, x0, z0, x1, z1)
    m = a.margin
    lay0, lay1 = city.layers["surface"], T.layer(1)
    cells = []
    for x in range(max(x0 - m, 0), min(x1 + m, city.n - 1) + 1):
        for z in range(max(z0 - m, 0), min(z1 + m, city.n - 1) + 1):
            s, p = lay0.get((x, z)), lay1.get((x, z))
            cells.append({"x": x, "z": z,
                          "saved": [s.id, s.state] if s is not None else None,
                          "pred": [p.id, p.state] if p is not None and p.flags is None else None})
    json.dump({"rules": a.rules, "save": a.save, "rect": [x0, z0, x1, z1], "mask": a.mask, "cells": cells},
              sys.stdout, indent=0)


def compare(a):
    with open(a.pred) as fh:
        pred = json.load(fh)
    live = {}
    with open(a.live) as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            r = json.loads(line)
            if "piece" in r:
                live[(r["x"], r["y"])] = [r["piece"], r["state"]]
            else:
                live.setdefault((r["x"], r["y"]), "other:" + r.get("cls", "?"))
    n = agree = changed = changed_ok = 0
    bad = []
    for c in pred["cells"]:
        k = (c["x"], c["z"])
        if c["saved"] is None and c["pred"] is None:
            continue
        got = live.get(k)
        got = got if isinstance(got, list) else None
        n += 1
        if c["pred"] != c["saved"]:
            changed += 1
        if got == c["pred"]:
            agree += 1
            if c["pred"] != c["saved"]:
                changed_ok += 1
        else:
            bad.append((k, c["saved"], c["pred"], got))
    print("%d network cells in the window: %d live == predicted; predicted changes %d, of which happened %d"
          % (n, agree, changed, changed_ok))
    for k, s, p, g in bad:
        print("  x=%d z=%d saved %s predicted %s live %s" % (k[0], k[1], s, p, g))
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nr_predict")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("predict")
    p.add_argument("rules")
    p.add_argument("save")
    p.add_argument("rect")
    p.add_argument("--mask", type=lambda s: int(s, 0), default=1)
    p.add_argument("--margin", type=int, default=3)
    c = sub.add_parser("compare")
    c.add_argument("pred")
    c.add_argument("live")
    a = ap.parse_args(argv)
    return {"predict": predict, "compare": compare}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
