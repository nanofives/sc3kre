# RESULTS: hudperf A/B (task hudperf, 2026-10-12)

Pre-registration: `PRE.md` (same folder). Build: `child/hudperf` 3eb048b (sc3resize), bench 7de7151. Run artifacts (logs,
`bench.json`, screenshots, frame dumps) are in MAIN `verify/hudperf/fin_*`, `band_*`, `rep*`, `specks_B` (gitignored).
Table produced by `re/tools/hudperf_summary.py`. Client 2560x1351 maximized on a 2560x1440 125% monitor, Europolis copy,
sim at speed 3 and running. The CPU was shared with unrelated work at 96 to 100% load during the runs.

## Cost (prediction 2, 3, 4)

Median of the 10-s windows of each 32-s phase, first window dropped. Cycles = thread cycles per frame, pass + restore.
Presents = composite -> screen Blts per 10 s (the frame rate the player sees is this / 10).

| scale | phase | A cycles M | B cycles M | B/A | A presents/10s | B presents/10s | A pass ms | B pass ms |
|---|---|---|---|---|---|---|---|---|
| 125 | static | 22.6 | 4.5 | 20% | 738 | 782 | 5.29 | 1.38 |
| 125 | scroll | 27.7 | 10.0 | 36% | 441 | 596 | 6.88 | 2.90 |
| 125 | hover | 24.3 | 5.4 | 22% | 525 | 309 | 6.27 | 3.41 |
| 125 | flyout | 27.2 | 5.9 | 22% | 343 | 175 | 11.42 | 16.89 |
| 150 | static | 22.7 | 3.9 | 17% | 816 | 810 | 5.30 | 1.10 |
| 150 | scroll | 25.5 | 8.4 | 33% | 571 | 610 | 6.10 | 2.25 |
| 150 | hover | 23.4 | 3.6 | 16% | 742 | 808 | 5.49 | 1.02 |
| 150 | flyout | 22.1 | 3.8 | 17% | 779 | 814 | 5.22 | 1.10 |
| 200 | static | 29.7 | 4.3 | 14% | 760 | 823 | 7.00 | 1.17 |
| 200 | scroll | 36.3 | 9.9 | 27% | 430 | 612 | 8.93 | 2.67 |
| 200 | hover | 40.6 | 4.5 | 11% | 393 | 800 | 11.32 | 1.19 |
| 200 | flyout | 41.4 | 4.0 | 10% | 223 | 825 | 15.81 | 1.06 |
| Fit | static | 37.1 | 4.4 | 12% | 570 | 797 | 8.73 | 1.19 |
| Fit | scroll | 43.4 | 11.8 | 27% | 366 | 590 | 10.30 | 3.27 |
| Fit | hover | 37.0 | 5.0 | 13% | 483 | 840 | 8.61 | 1.28 |
| Fit | flyout | 34.4 | 3.9 | 11% | 517 | 823 | 8.00 | 1.06 |

- **P2 met.** Static B/A 12% to 20% (limit 35%), scroll 27% to 36% (limit 50%).
- **P3 met.** Arm B static 4.4 M at Fit vs 4.5 M at 125 (ratio 0.98, limit 2.0). Arm A grows 22.6 -> 37.1 M.
- **P4 failed at one point.** B >= A in presents everywhere in static and scroll except 150 static: 810 vs 816 (-0.7%).
  Outside the predicted phases, 125 hover (309 vs 525) and 125 flyout (175 vs 343) are lower for B while B's cycles are
  22% of A's; in the same windows B's wall-clock pass reads 3.41 ms and 16.89 ms against 5.4 and 5.9 M cycles, so the
  pass thread was off the CPU for most of that time. The cause of those low windows is not established; the shared load
  is the measured candidate (`[UNCERTAIN]`).
- HUD scale off (`fin_normal`, Normal): sc3perf fps median 156 static, 157 scroll. sc3perf counts two Blts per frame
  (development: 93 shown vs 45 presents/s), so this is about 78 presents/s (derived from that ratio, not counted: the HUDSCALE line does not run with the HUD off).
- Restore right after the present (`SC3RESIZE_HUDPERF_LAZY=0`, Fit): 4.1 to 5.0 M cycles per frame for the restore alone,
  on top of the pass.

## Identity (prediction 1): met

`SC3RESIZE_HUDPERF_CHECK=1`, every frame both passes on the same frame:

| scale | frames compared | frames with a pixel difference | coverage frames / px different |
|---|---|---|---|
| 125 | 8,133 | 0 | 0 / 0 |
| 150 | 8,903 | 0 | 0 / 0 |
| 200 | 7,938 | 0 | 0 / 0 |
| Fit | 4,235 | 0 | 0 / 0 |

29,209 frames over static, scroll, hover and flyout, 0 differing pixels in the enlarged rects, 0 differing coverage bytes.

## Lazy restore (prediction 5): failed in one window

Every arm-B window at 125, 150, 200 and Fit static/scroll/flyout: `paid late 0 0 0 0 0, dropped 0`, every owed restore
cancelled by the game's full city-layer Blt. Fit hover, one window: 131 paid late, all of the kind "Blt onto the frame",
logged as dest `[0 0 800 599]` flags `0x01000000` (DDBLT_WAIT) at 112.5 s. The lazy path paid them before that Blt
reached the surface, which leaves the game the frame the eager restore would have left. What the game draws there is
not identified (`[UNCERTAIN]`).

## Hudfix defects (prediction 6): met for the predicted rects

Fit, arm B, sim paused, `hudfix_scrollgrab.py --dir right --taps 10 --frames 400` (139 frames captured, 62 with > 30%
of the city changed against the previous frame, so the camera moved): enlarged side panel `[2346 2 2558 993]` and bar
lower row `[2 1290 1650 1349]` 0.0% changed in all 139 frames. A third rect I added, `[2109 1173 2198 1349]`, peaks at
2.5%; the changed pixels are x 2109..2122, y 1173..1225, the city visible left of the RCI's raised globe tab, which
moves with the scroll (crop checked by eye).

## Opt-outs (prediction 7): met

`SC3RESIZE_HUDPERF=0`: `HUDPERF> off` and `rebuilt 0 px/frame` in every window of every A run.
`SC3RESIZE_HUDPERF_LAZY=0`: no `lazy restore on` line, restore 4.1 to 5.0 M cycles per frame.

## Screenshots, and one artifact not explained

Looked at by eye: `fin_s1_B` hover and flyout, the no-restore development grab, crops of the RCI corner: no specks, no
city inside opaque HUD, no stale HUD pixels. Every phase grab of the development, fin, rep and band runs was also scanned for long near-black
horizontal runs in the city area. In ONE arm-B run (`fin_s1_B`, Fit) a black horizontal line, 7 rows (y 1172..1178), x 0..about 2120, with
ends shaped like the bar's top outline, sat about 53 px above the enlarged bar in every grab from the first one after the
maximize until the end (static, scroll, hover, flyout). The arm-A run right after, at the same scale, did not have it.
Repeats on the same build at Fit: arm B 0 of 9 more launches (`rep1..3`, `band_B1..6`), arm A 0 of 6 (`band_A1..6`).
Totals: arm B 1 of 10, arm A 0 of 7. The lazy restore had not paid any restore before the line appeared (first late
restore at 112.5 s, the line is in the grab at about 26 s). Mechanism not established (`[UNCERTAIN]`): candidates are a
pre-existing resize-mod artifact (task hudfix logged a black 4-px line in the city with HUD scale off) or a read of the
composite through a path the lazy-restore hooks do not see (direct pixel access through a persistent mapping). Logged
in the status file as a hand-test watch item.
