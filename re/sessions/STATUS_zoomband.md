# STATUS zoomband (child of "SC3: owner bugs", 2026-10-26)

State: FIXED. Worktree `Simcity_wt_zoomband`, branch `child/zoomband` from main 742fe1f. Nothing committed (claude2
policy).

Cause: the game's full repaint (SIMSPR FUN_1000b4b3, iso vt+0x14c, run on every zoom change and layout pass) tiles the
view 8 x 8 with W/8 x H/8 integer division, so at 1351 rows it never redraws rows 1344..1350 (at 2561 wide also column
2560). Each scroll copy carries that stale 7-row stripe up above the HUD bar. It happens at x1 (any stock zoom level);
x2 / x3 were already safe through ALIGN8. Detail: `verify/zoomband/RESULTS.md`.

Fix: block REPAINT8 in `sc3resize.c` (after DIRTCLIP / CELLFIX, outside the dialog code): a C copy of the function with
the last tile of each row and column reaching the view edge. Identical to the game when both sizes are multiples of 8.
Off switch `SC3RESIZE_REPAINT8=0`. New diag `SC3RESIZE_FRAMEDUMP_VIEW=1` (each frame dump also writes the render target).

Tests: 2560x1351 unfixed 26 of 44 view dumps banded, fixed 0 of 42; 2561x1351 unfixed 5 of 5, fixed 0 of 44; 2560x1350
fixed 0 of 47; maximized (3840x1984 on this PC) fixed 0 of 42. Every x1 zoom step plus x1 -> x2 -> x1, scrolls in all 4
directions. hook_audit: REPAINT8 hook ok, 0 MISMATCH. No fps loss (no per-frame code).

ALIGN8: REPAINT8 alone also removes the x3 band ALIGN8 was added for (3840x1984 x3, ALIGN8 off: 3 of 9 dumps
banded without REPAINT8, 0 of 9 with it). ALIGN8 kept on by default. New test switch `SC3RESIZE_CITYZOOM_ALIGN8=0`.

## Files to commit (from the worktree)
- `re/harness/src/sc3resize.c` (REPAINT8 block + install, FRAMEDUMP_VIEW diag, CITYZOOM_ALIGN8 test switch)
- `verify/zoomband/RESULTS.md`
- `re/tools/zoomband_run.py`, `re/tools/zoomband_check.py`
- this file (`MAIN\re\sessions\STATUS_zoomband.md`)

Local only (gitignored): `MAIN\verify\zoomband\owner_shots\02..05_*.png`, `MAIN\verify\zoomband\runs\` (logs, check.txt
per run, the owner-pair BMPs).

Needs owner check: mouse-wheel zoom and right-drag scrolling (same code path, not driven by these tests).
