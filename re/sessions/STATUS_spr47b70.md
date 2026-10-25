# STATUS spr47b70 (2026-10-25)

State: **fixed** (milestone 2, round 2 checks done). Results: `verify/spr47b70/RESULTS.md`.

Cause: stock bug. The SIMSPR city view init (`FUN_10044471`) loads `anchor point cursor.BMP` into `this+0x1fc`
without a check. GZResourceD opens files with dwShareMode 0, so the load fails while any other process has that file
open, and 52 trees (MAIN included) hard-link it. Stock reproduces it 1 of 1 with the file held.

Fixes:
- sc3resize `SHAREREAD` (`SC3RESIZE_SHAREREAD=0` = stock): read-only GZResourceD opens share reads, the sprite load is
  retried and null-guarded, and the marker draw is null-guarded.
- sc3netmod `OVPIN` (`SC3NETMOD_OVPIN=0` = old walk): the overlay's import-table walk holds a reference on each
  module, taken and released outside `g_ovlock`.

Checks on the final build: held exclusively, fix on: 7 of 7 alive. Held exclusively with `=0`: crash 2 of 2. Held with
shared read: loads first try. Paired games from two hard-linked trees: 3 of 3 rounds alive. Save, save-on-quit, prefs
write and reload all work, with 0 failed opens.

## Files to commit

Worktree `Simcity_wt_spr47b70` (branch `child/spr47b70`, from main 8587f2c):
- `re/harness/src/sc3resize.c`
- `re/harness/src/sc3netmod.c`
- `re/tools/spr47b70_probe.py`
- `re/tools/spr47b70_markerdraw.py`
- `re/tools/spr47b70_filetrace.py`
- `functions.csv` (2 GZResourceD rows)

MAIN:
- `verify/spr47b70/RESULTS.md`, `run_arm.ps1`, `loop.ps1`, `pair.ps1`, `hold_file.py`, `who_holds.py`
- `verify/spr47b70/logs/*`
- `verify/spr47b70/*.png`
- `re/sessions/STATUS_spr47b70.md`

## Notes for the orchestrator

- My test tree's `anchor point cursor.bmp` is no longer linked to the other 51 trees. It is shared only with
  `Simcity_stock_spr47b70b` (a hard-linked twin of my tree, made for the paired check). Both trees can be deleted
  when this stream closes.
- Needs owner check: a real right-drag in a game where the sprite failed to load (the marker should just be absent).
- Until this build ships, two games from hard-linked trees (the owner's MAIN game included) can kill each other when
  one opens the BMP while the other builds its city view.
