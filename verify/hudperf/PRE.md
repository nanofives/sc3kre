# PRE: hudperf A/B (task hudperf, 2026-10-12)

Written before the final A/B runs. Development runs before this file (named `base_*`, `check1_*`, `t2`..`t9`, `dev_*` in
MAIN `verify/hudperf/`) are exploration, not evidence for the predictions below.

## Setup

- Build: `child/hudperf` at the commit that adds this file (sc3resize source; a follow-up commit changes only the bench
  tool and this line: 32-s phases, per-phase cycles in its JSON). Instance `MAIN\re\harness\inst_hudperf` (all six binaries
  built from the worktree), Europolis copy in `inst_hudperf\city\`, `mods_launch -multi`, windowed.
- Driver: `re/tools/hudperf_bench.py`. It moves the window to the left monitor (2560x1440, 125%, the same model as the
  owner's), maximizes it (client 2560x1351, the owner's measured size), sets speed 3 and unpauses with P (date, funds, RCI
  and minimap tick), then runs 32-s phases (the first 10-s log window of each phase straddles the previous phase and is not used): `static`, `scroll` (spoofed arrows, left/right), `hover` (posted moves over
  the enlarged side-panel buttons: highlights and tooltips), `flyout` (one category open, hover over its items, closed).
- Scales: `SC3RESIZE_HUDSCALE=125`, `150`, `200`, `1` (Fit, 2.252x here), `SC3RESIZE_HUDSCALE_FILTER=1` (Suavizado on).
  Normal (HUD scale off) is one extra run of arm B with `SC3RESIZE_HUDSCALE=0` for the fps reference.
- Arms: **A** `SC3RESIZE_HUDPERF=0` (the hudfix pass and the restore right after the present, as shipped in round/1012),
  **B** default (HUDPERF on: cached enlarged HUD, lazy restore, cheaper coverage).
- The CPU is shared with unrelated work (96 to 100% load measured during development). So the primary cost metric is
  **thread cycles per frame** (QueryThreadCycleTime around the pre-present pass and around the restore, logged as
  `HUDPERF> thread cycles per frame`), which preemption does not inflate. Wall-clock `ms per frame in the pre-present
  pass` (the line the owner's log has) and presents per 10 s (`N enlarged frames in 10000 ms`) are reported too.
  sc3perf's fps column counts two client-sized Blts per frame (city layer -> composite, composite -> screen), so it reads
  about twice the presents (development: 93 vs 45/s); it is reported as is, labelled.

## Identity

`SC3RESIZE_HUDPERF_CHECK=1` runs the cached pass and then the hudfix pass on the same frame, every frame, and counts
pixels of the enlarged rects that differ (the hudfix result is what shows), plus the coverage map of the new coverage
code against the old one inside every HUD rect + 1 px.

## Predictions

1. Identity: in CHECK runs at 125, 150, 200 and Fit, all four phases, every 10-s window logs
   `0 with a difference, 0 px differ` and `coverage: 0 frames with a difference, 0 px`.
2. Cost, B vs A, thread cycles per frame (pass + restore, median of the 10-s windows of a phase):
   static B <= 35% of A, scroll B <= 50% of A, at every scale.
3. Scale dependence, arm B static: cycles per frame at Fit <= 2.0x the cycles per frame at 125.
   (Arm A grows with the dest area, about s^2.)
4. Presents per 10 s: B >= A in static and scroll at every scale (median of windows; noisy under the shared load).
5. Lazy restore: in every arm-B bench window `paid late 0 0 0 0 0` and `dropped 0`; every owed restore is cancelled by
   the game's own full city-layer Blt.
6. No regression of the hudfix defects: at Fit, arm B, `re/tools/hudfix_scrollgrab.py` during a scroll with the enlarged
   side panel and the bar's lower row as rects: changed-in-HUD <= 0.5% in every frame for those rects (hudfix measured 0).
   Screenshots of each phase are looked at for specks, see-through city in the HUD, stale HUD pixels.
7. Opt-outs: `SC3RESIZE_HUDPERF=0` logs `HUDPERF> off` and 0 rebuilt px; `SC3RESIZE_HUDPERF_LAZY=0` logs no
   `lazy restore on` line and a non-zero restore time.
