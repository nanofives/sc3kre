"""zoomband_check.py - count stale bands in SC3RESIZE_FRAMEDUMP_VIEW dumps (task zoomband, 2026-10-26).

    py re/tools/zoomband_check.py <dir> [--client WxH] [--glob "*_view.bmp"]

A dump of the city render target (<tag>_view.bmp, slack rows included) is checked for full-width SEAMS: a row
(column) where more than 90% of the pixels change from the row (column) before. Live city art changes on about half
the columns from one row to the next; the stale stripe left by the full repaint starts and ends with a seam of
0.96..0.99 (measured on the unfixed build). Rows / columns at or past the client size (the slack) are not counted:
the view is client-sized at x1, client / f rounded up to 8 at x2 / x3 (ALIGN8), so only rows below the client's
view height are judged. Prints one "[N/M] file PASS|FAIL" line per dump and the seams found.
"""
import argparse
import glob
import os
import re
import sys

import numpy as np
from PIL import Image


def seams(a, lim):
    """bands: two seams (lim % 8) +- 1 apart (the stale stripe carried by a scroll; zoom 4 scrolls by even steps, so a
    7-row stripe can lose a row), or one seam at 8 * (lim / 8) (the stripe not moved yet). Nothing when lim is a
    multiple of 8. A lone seam elsewhere, or a pair at another distance, is a straight edge of the art (skyscraper
    sides at zoom 4 reach 0.92) and is not counted."""
    rem = lim % 8
    if not rem:
        return []
    d = np.abs(a[1:].astype(np.int32) - a[:-1].astype(np.int32)).sum(axis=2)
    fr = (d > 24).mean(axis=1)
    s = [y + 1 for y in range(len(fr)) if fr[y] > 0.9 and y + 1 < lim]
    out = []
    for k, y in enumerate(s):
        if k + 1 < len(s) and rem - 1 <= s[k + 1] - y <= rem + 1:
            out.append((y, s[k + 1]))
        elif y == 8 * (lim // 8):
            out.append((y, lim))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--client", default="2560x1351")
    ap.add_argument("--glob", default="*_view.bmp")
    ap.add_argument("--from-dump", action="store_true",
                    help="take the view size from the dump (render target = view + RZ_SURFACE_SLACK 8 rows), for runs "
                         "with SC3RESIZE_CITYZOOM_ALIGN8=0")
    ap.add_argument("--log", help="sc3resize.log of the run: the view size per dump comes from its CITYZOOM lines")
    a = ap.parse_args()
    cw, ch = map(int, a.client.lower().split("x"))
    fs = sorted(glob.glob(os.path.join(a.dir, a.glob)), key=os.path.getmtime)
    bad = 0
    for i, f in enumerate(fs, 1):
        im = np.asarray(Image.open(f).convert("RGB"))
        h, w, _ = im.shape
        # the view's live size: x1 = the client; with a factor the view is narrower than the client
        f_ = max(1, round(cw / w)) if w < cw * 0.9 else 1
        vw, vh = (cw, ch) if f_ == 1 else (((cw + f_ - 1) // f_ + 7) & ~7, ((ch + f_ - 1) // f_ + 7) & ~7)   # ALIGN8
        if a.from_dump:
            vw, vh = w, h - 8
        rows = seams(im, vh)
        cols = seams(np.transpose(im, (1, 0, 2)), vw)
        ok = not rows and not cols
        bad += not ok
        print(f"[{i}/{len(fs)}] {os.path.basename(f)} {'PASS' if ok else 'FAIL'} view {vw}x{vh}" + ("" if a.from_dump else f" (x{f_})")
              + (f" row seams {rows[:6]}" if rows else "") + (f" column seams {cols[:6]}" if cols else ""), flush=True)
    print(f"{len(fs) - bad} of {len(fs)} dumps without a band", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
