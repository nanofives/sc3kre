"""Score frames saved by hudfix_scrollgrab.py: per frame, the share of pixels inside each rect that differ from
ref.png, plus the frames' city shift against the previous frame (to prove the camera moved).

    python re/tools/hudfix_score.py verify/hudfix/<run> --rect x0,y0,x1,y1 [--rect ...] [--top 8]
"""

from __future__ import annotations

import argparse
import pathlib

import numpy as np
from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--rect", action="append", default=[])
    ap.add_argument("--city", default=None, help="x0,y0,x1,y1 city region to measure motion")
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    ref = np.asarray(Image.open(d / "ref.png").convert("RGB")).astype(np.int16)
    rects = [tuple(int(v) for v in r.split(",")) for r in a.rect]
    frames = sorted(d.glob("f*.png"))
    rows = []
    moved = 0
    prev = None
    for f in frames:
        arr = np.asarray(Image.open(f).convert("RGB")).astype(np.int16)
        sc = []
        for (x0, y0, x1, y1) in rects:
            sc.append(float((np.abs(arr[y0:y1, x0:x1] - ref[y0:y1, x0:x1]).sum(axis=2) > 24).mean()))
        if a.city and prev is not None:
            x0, y0, x1, y1 = (int(v) for v in a.city.split(","))
            if (np.abs(arr[y0:y1, x0:x1] - prev[y0:y1, x0:x1]).sum(axis=2) > 24).mean() > 0.3:
                moved += 1
        prev = arr
        rows.append((f.name, sc))
    print(f"{len(frames)} frames; city changed >30% vs previous frame in {moved}")
    for i in range(len(rects)):
        vals = [r[1][i] for r in rows]
        top = sorted(rows, key=lambda r: -r[1][i])[: a.top]
        print(f"rect {rects[i]}: median {np.median(vals) * 100:.2f}% max {max(vals) * 100:.2f}%  top: "
              + ", ".join(f"{n} {s[i] * 100:.1f}%" for n, s in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
