# PRE — dialogs follow the window, RCI stays under dialogs, no stale-window SetRect

Written 2026-10-05, committed before the run. Owner hand test the same day reported: (1) an open
window does not adjust when the game window is resized, (2) a dragged window draws over everything
except the RCI, (3) some windows (city data, Reunirse) do not open centered. The same test logged an
access violation in `GZWIND+0x1EF7A` with `rz_cluster_layout` on the stack
(`verify/handtest_1005/run.log:10597`).

## Measured before the change (`dialog_survey.py`, this folder)

| window | 800x600 | 1680x979 | parent |
|---|---|---|---|
| Reunirse | `[8 8 391 362]` | `[8 8 391 362]` | root |
| budget (city data 2) | not reached | `[102 32 602 512]` | root |
| city data 4 | not reached | `[8 8 392 362]` | root |
| city data 6 | not reached | `[40 34 464 474]` | root |
| snapshots (city data 0) | `[584 309 1096 669]`, buttons outside the client | `[584 309 1096 669]`, centered | HUD container `SC3U.exe+0xd32d0` |

All are `SIMUI+0xa4d64`, created once and re-used. The cached HUD window list (`g_wins`) captured
dialogs too, and kept their pointers after they were freed. `rz_cluster_layout` then called SetRect on
a freed object.

## Changes (build 198,144 B)

- `rz_dialogs_poll` (100 ms): at a non-native size, a dialog that becomes visible is centered in the
  map area (client minus the side panel and bar). On a resize, a dialog still at the spot we or the
  stock layout gave it is re-centered (stock rect at 800x600). A dialog the player dragged is only
  clamped inside the client. At 800x600 a dialog fully inside the client is left at its stock spot.
  `SC3RESIZE_DIALOGS=0` disables it.
- RCIFIX skips the re-draw when a visible dialog overlaps the RCI.
- `g_wins` no longer captures dialogs, and both SetRect loops drop any entry that is no longer in
  the live window tree (`rz_win_alive`).

## Run (`re/tools/dialog_test.py`), one launch, defaults

| # | step | pass |
|---|---|---|
| 1 | maximized: open Reunirse, budget, city data 0/4/6 | each centered in the map area, within 2 px |
| 2 | budget open, restore to 1280x700, then maximize | re-centered in each map area, within 2 px |
| 3 | Reunirse dragged by (-200,+100), then restore to 1280x700 | stays where dragged, clamped only if it would leave the client |
| 4 | Reunirse dragged over the RCI | the RCI's pixels are covered by the dialog (frame region differs from an RCI-only frame and matches the dialog) |
| 5 | 800x600: open Reunirse, then snapshots | Reunirse at stock `[8 8 391 362]`. Snapshots fully inside the client |
| 6 | the whole run | 0 access violations |
