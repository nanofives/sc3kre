# PRE — map input past the native 800x600 (`SC3RESIZE_VIEWFIX`)

Written 2026-10-05, committed before the run.

## Cause (measured, causal)

`verify/resize_edgescroll/RESULTS.md` Finding 1. At 1920x1009 the city view's hit rect `+0x14` and
local rect `+0x80` both read `[0 0 800 600]`. Posted moves at (1792,336) and (480,929) reached the view
0 times, and 3 times after a live poke of the hit rect. The cascade (root `vt+0x14c`) rebuilds `+0x14`
from `+0x80` `[CONFIRMED @ SIMUI 0x1006c61b]`, and the mod only widened `+0x14`.

## Change

`rz_view_rect_assert`: write the view's local AND hit rects to `[0 0 cw ch]`, exact in both
directions. Called from `rz_input_geometry` and every 250 ms from `rz_poll`. Direct field writes, no
SetRect. Default `SC3RESIZE_VIEWFIX=1`, `=0` keeps the old widen-only hit write (control). City-view
lookup is shared with edge-off and checks both vtables.

## Run

Single 1680x1050 display at 100%. `SC3RESIZE_CLUSTER=1`, defaults otherwise (spans on, edge scroll
off). Two launches, one flag: arm T `VIEWFIX` unset (read back as `viewfix=1`), arm C
`SC3RESIZE_VIEWFIX=0`. Each arm maximized (client 1680x979). Points avoid the always-on-top VM window
(screen x 740..1135, y 775..965).

| # | observable | instrument | T predicted | C predicted |
|---|---|---|---|---|
| 1 | view local/hit rects at maximized | in-process read | `[0 0 1680 979]` both | local `[0 0 800 600]`, hit `[0 0 800 600]` |
| 2 | posted moves at (1300,300) and (480,880) reach the city view | hook on the band test `SIMSPR FUN_10043a38` (on the move path) | calls > 0 at both | 0 at both |
| 3 | posted move at (400,300), inside 800x600 (control point) | same hook | calls > 0 | calls > 0 |
| 4 | right-drag (1300,400) -> (1000,300) pans the view | phase correlation on the crop x 0..1480, y 0..740 | moved: `abs(dx)` >= 8 or peak < 0.1 | not moved: `abs(dx)`, `abs(dy)` <= 2 with peak >= 0.2 |
| 5 | the city still renders full-window after the write | frame by eye | yes | yes |
| 6 | after restore to 800x600 | in-process read | local = hit = `[0 0 800 600]` | n/a |

**PASS:** T rows 1-6 as predicted and C rows 1-3 as predicted. The control must reproduce the defect.
**VOID:** `viewfix` missing from `FLAGS>`, a modal dialog up (dismiss_tips reports one), scaling not
100%, or no hook calls at the control point in either arm.
Row 4 in arm C is informative only. A drag that starts outside the hit rect may still pan if another
path handles it, and that would be worth knowing, not a failure.
