# STATUS cityzoom (2026-10-22)

State: BUILT, light-tested in game, waiting for the orchestrator to commit and the owner's hand test.

- Feature: zoom in past the closest zoom adds x2 and x3 (as the window allows: x2 + x3 at 3840x1984, x2 at
  2560x1351 / 1600x1200, none at 1920x1080). The city view is drawn at client / f and stretched into the frame;
  smooth follows the HUD "Suavizado". Preferencias checkbox "Zoom extra" (default on). `sc3resize.ini [view]
  zoomextra` 0 / 1 / 2 (2 = at most x2), env `SC3RESIZE_CITYZOOM`.
- Results: `MAIN\verify\cityzoom\RESULTS.md` (12 checks, timings), frames `verify/cityzoom/owner_shots/01..14`.
  x2 smooth 45 to 54 presents/s at 4K vs 16 to 25 for stock zoom 4.
- Worktree is on main `a7b3195` content (uiscale's sc3resize.c / HUD_SCALE.md / stage_lan_release.py copied in from
  main, identical to it), my changes on top. No ids taken, no tables or packages changed.
- Instance `Simcity_stock_hwlight\re\harness\inst_cityzoom`: all 8 mods from the worktree, game closed.

Files to commit:
- worktree `Simcity_wt_cityzoom` (branch child/cityzoom): `re/harness/src/sc3resize.c`, `re/harness/src/sc3overscroll.c`,
  `re/analysis/CITY_ZOOM.md` (the other three modified files equal main a7b3195)
- MAIN: `re/sessions/STATUS_cityzoom.md`, `verify/cityzoom/RESULTS.md`, `verify/cityzoom/owner_shots/*.png` (14),
  `verify/cityzoom/*.png` mockups, `verify/cityzoom/stretch.c`, `verify/cityzoom/mock.py`
