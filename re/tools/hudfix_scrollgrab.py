"""Grab frames of the game WHILE the camera scrolls, to catch city pixels drawn over the enlarged HUD.

Task hudfix 2026-10-11. Drives one instance (SC3_PID), no cursor, no focus (sc3io). A thread holds the spoofed
arrow keys (sc3io.scroll) while the main thread blits the client area as fast as it can. Each frame is saved and
scored: for every enlarged HUD rect given with --rect (client coords, the HUDSCALE dest rects from the log), the
fraction of pixels that differ from a still reference frame of that region taken before the scroll. The HUD does
not move during a scroll, so any change inside those rects is something drawn over the HUD.

    SC3_PID=N python re/tools/hudfix_scrollgrab.py --out verify/hudfix/scrollA --dir right --taps 6 \
        --rect 0,816,1200,900 --rect 1056,0,1200,663

Note: the minimap legitimately changes (its view rectangle moves). Leave it out of --rect, or read it by eye.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import threading
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dir", default="right")
    ap.add_argument("--taps", type=int, default=6)
    ap.add_argument("--hold", type=float, default=0.25)
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--rect", action="append", default=[], help="x0,y0,x1,y1 client coords to score")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    hwnd = sc3io.game_hwnd()
    ref = sc3io.grab(hwnd, settle=0.5)
    ref.img.save(out / "ref.png")
    refa = np.asarray(ref.img.convert("RGB")).astype(np.int16)
    rects = [tuple(int(v) for v in r.split(",")) for r in a.rect]
    left, top, w, h = sc3io.client_rect_on_screen(hwnd)

    th = threading.Thread(target=sc3io.scroll, args=(hwnd, a.dir.split(","), a.taps, a.hold), daemon=True)
    th.start()
    time.sleep(0.05)
    shots = []
    t0 = time.time()
    while len(shots) < a.frames and (th.is_alive() or len(shots) < 3):
        shots.append((time.time() - t0, sc3io._blit(left, top, w, h)))
    th.join(timeout=10)
    sc3io.end_scroll()
    worst = 0.0
    for i, (t, img) in enumerate(shots):
        img.save(out / f"f{i:02d}.png")
        arr = np.asarray(img.convert("RGB")).astype(np.int16)
        if arr.shape != refa.shape:
            print(f"f{i:02d} size {img.size} differs from the reference {ref.img.size}: window moved, stop")
            return 2
        scores = []
        for (x0, y0, x1, y1) in rects:
            d = np.abs(arr[y0:y1, x0:x1] - refa[y0:y1, x0:x1]).sum(axis=2) > 24
            scores.append(float(d.mean()))
        worst = max([worst] + scores)
        print(f"f{i:02d} t={t:5.2f}s changed-in-HUD " + " ".join(f"{s * 100:5.1f}%" for s in scores))
    print(f"{len(shots)} frames, worst HUD-rect change {worst * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
