# PRE — panel buttons at native vs maximized, plus edge scrolling OFF in windowed mode

Written 2026-10-05, committed before the run. Owner request the same day: "screenshot the buttons on
all panels without resized window and with it and recheck, i remember last time we did not port fully
that", and "i don't want edge scrolling feature when on windowed mode".

## Build

`sc3resize.dll` 193,024 B. New since `b00dc6f`: `SC3RESIZE_EDGESCROLL` (default 0). `rz_edge_off`
widens the band test's inner rect `outer+0x178..+0x184` to cover every coordinate, re-asserted every
250 ms from `rz_poll` and right after the EDGEFIX rebuild. `FUN_10043a38` then always takes its
"inside inner, clear all flags" branch `[CONFIRMED @ SIMSPR 0x10043a38]`. The drag branch of that
function does not read these fields, and arrow keys read the keyboard, not the bands.

## Procedure

Game on the 100% monitor, `Cities\Europolis.sc3`, `SC3RESIZE_CLUSTER=1`, all other flags default.
`re/tools/panel_shots.py --state native`, then maximize, then `--state max`, then `--compare`.
Per state: full frame, then every side-panel category button clicked by its live rect, one grab per
open flyout, and the list of windows that became visible with each click. Bar and minimap buttons
are cropped from the full frames, not clicked (they open modal dialogs).

## What is scored

| # | check | pass |
|---|---|---|
| 1 | same number of category buttons found in both states | equal |
| 2 | per category, same number of newly visible windows (the flyout's buttons) in both states | equal |
| 3 | at maximized, no newly visible window outside the client | 0 outside |
| 4 | visually, per category: every flyout icon is drawn, beside its own button, in the same layout as native | by eye on `compare/catNN.png` |
| 5 | bar and minimap buttons all drawn at maximized, same set as native | by eye on `compare/bottom_*.png` |
| 6 | edge-off: log shows `EDGE> edge scrolling OFF`, and the band test never sets a flag | `edge_probe.py`-style hook, flags all 0 at band points |

Any row failing is a porting gap to list in RESULTS with the category and the window class.
Visual rows are my read of the images, and the owner's eye is the final word.
