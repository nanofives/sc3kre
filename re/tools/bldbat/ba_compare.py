#!/usr/bin/env python3
r"""ba_compare.py - task sc3compat-a (2026-11-19e): check BA-rendered IXF files against .bld files and each other.

  py -3.12 re/tools/bldbat/ba_compare.py preview <ixf> <folder|.bld...> [--sheet out.png]
      every .bld's frames in the IXF (any group, matched as bldfile.side_match does) against its own preview:
      slot 0 at zooms 0-3 (mask IoU, colour RMS), and a contact sheet (zoom 2, four views per building)
  py -3.12 re/tools/bldbat/ba_compare.py frames <a.ixf> <b.ixf> <folder|.bld...>
      the same buildings in two renders (e.g. the Frida route and bawinonly's batch mode): frame size, anchor and
      pixels per (zoom, view), 16 frames per building
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bldimport"))
import bldfile as BF   # noqa: E402


def _frames_for(ixf, blds):
    with open(ixf, "rb") as fh:
        data = fh.read()
    return {b["path"]: (BF.bat_frames(m) if m is not None else None) for b, m in BF.side_match(data, blds)}


def cmd_preview(a):
    import numpy as np
    from PIL import Image
    blds = [BF.read_bld(p) for p in BF._bld_paths(a.paths)]
    fr = _frames_for(a.ixf, blds)
    rows, bad = [], 0
    for b in blds:
        f = fr[b["path"]]
        if f is None:
            print("%-30s NOT IN THE IXF" % b["file"])
            bad += 1
            continue
        pf = BF.preview_frames(b)
        cells = []
        for z in range(4):
            iou, rms = BF._cmp(pf[(z, 0)][0], f[(z, 0)][0])
            cells.append("z%d IoU %.3f RMS %4.1f" % (z, iou, rms))
        print("%-30s %s" % (b["file"], " | ".join(cells)))
        rows.append((b, f))
    if a.sheet and rows:
        cw = max(sum(f[(2, r)][0].width for r in range(4)) + 50 for _b, f in rows)
        hs = [max(f[(2, r)][0].height for r in range(4)) + 10 for _b, f in rows]
        cols = 3
        nrow = (len(rows) + cols - 1) // cols
        rh = [max(hs[i * cols:(i + 1) * cols]) for i in range(nrow)]
        sheet = Image.new("RGB", (cw * cols, sum(rh)), (58, 92, 58))
        y = 0
        for ri in range(nrow):
            for ci in range(cols):
                k = ri * cols + ci
                if k >= len(rows):
                    break
                _b, f = rows[k]
                x = ci * cw + 10
                for r in range(4):
                    im = f[(2, r)][0]
                    sheet.paste(im, (x, y + rh[ri] - im.height - 5), im)
                    x += im.width + 10
            y += rh[ri]
        sheet.save(a.sheet)
        print("wrote %s" % a.sheet)
    return 1 if bad else 0


def cmd_frames(a):
    import numpy as np
    blds = [BF.read_bld(p) for p in BF._bld_paths(a.paths)]
    fa, fb = _frames_for(a.a, blds), _frames_for(a.b, blds)
    tot = same = 0
    worst = []
    for b in blds:
        A, B = fa[b["path"]], fb[b["path"]]
        if A is None or B is None:
            print("%-30s missing in %s" % (b["file"], "a" if A is None else "b"))
            continue
        eq = 0
        for z in range(4):
            for r in range(4):
                (ia, la), (ib, lb) = A[(z, r)], B[(z, r)]
                tot += 1
                xa, xb = np.asarray(ia), np.asarray(ib)
                if la == lb and xa.shape == xb.shape and (xa == xb).all():
                    eq += 1
                    same += 1
                else:
                    diff = 1.0 if xa.shape != xb.shape else float((xa != xb).any(-1).mean())
                    worst.append((diff, b["file"], z, r, la, lb, xa.shape, xb.shape))
        print("%-30s %2d of 16 frames identical" % (b["file"], eq))
    print("total: %d of %d frames identical (size, anchor and every pixel)" % (same, tot))
    for w in sorted(worst, reverse=True)[:10]:
        print("  differs: %s z%d r%d share of pixels %.4f anchor %s/%s shape %s/%s" % (w[1], w[2], w[3], w[0], w[4], w[5],
                                                                                    w[6], w[7]))
    return 0 if same == tot else 1


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("preview")
    s.add_argument("ixf")
    s.add_argument("paths", nargs="+")
    s.add_argument("--sheet")
    s = sub.add_parser("frames")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("paths", nargs="+")
    a = ap.parse_args(argv)
    return {"preview": cmd_preview, "frames": cmd_frames}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
