# PRE — full-width bar and full-height side panel ON by default

Written 2026-10-05, committed before the run. Owner decision the same day: "Turn on full-width bar
and full-height panel by default".

## Change

`SC3RESIZE_BARSPAN` and `SC3RESIZE_SIDESPAN` default to 1 (`=0` opts out). Both values are echoed
in `FLAGS>`. Both paths already existed and were exercised by the owner on 2026-09-02/03, but never
together with KIDFIX / ARTGUARD (2026-09-07). `RCIFIX` only runs with BARSPAN on, so it, and its new
null-surface guard, runs by default for the first time.

## Run

One launch, `SC3RESIZE_CLUSTER=1`, `SC3RESIZE_BLTBEAT=1` (log-only Blt counter), all else default.
Single 1680x1050 display at 100%.
1. `panel_shots.py --state native` at 800x600.
2. Resize to 1600x700 at the top of the screen (avoids the always-on-top VM window), `--state max`, then `--compare`.
3. Maximize, wait 20 s, read the `BLTBEAT` lines.
4. 20 maximize/restore cycles, restores 800x600 / 1280x700 / 1600x700.

## Predictions

| # | check | pass |
|---|---|---|
| 1 | `FLAGS>` shows `barspan=1 sidespan=1` with neither variable set | yes |
| 2 | at 1600x700 the bar spans the full client width, the side panel spans from the top of the client down to the minimap, and no bare city shows where native HUD art would be (by eye) | yes |
| 3 | every button present and aligned as in `verify/resize_panelshots`: 9 categories, flyouts 6/8/7/6/7/6, offsets identical to native | identical |
| 4 | blits per second at maximized within 2x of native | the FPS fix holds |
| 5 | 0 access violations over the churn, and `in_rci_repaint` never 1 in a VEH line | 0 |
| 6 | the side panel paints after a tool click plus a resize (the ARTGUARD case) | painted |

Failures are listed by row. Row 2 and row 6 are my read of the images, and the owner's hand test is final.
