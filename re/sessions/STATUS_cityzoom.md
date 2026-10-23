# STATUS cityzoom (2026-10-23)

State: zoom steps committed on child/cityzoom (5f3221b); round 2+3 perf work and the right-drag fix built and
light-tested, NOT committed yet (owner testing).

- Feature: zoom in past the closest zoom adds x2 and x3 (as the window allows), view drawn at client / f and stretched
  into the frame; Preferencias "Zoom extra" (default on), sc3resize.ini [view] zoomextra.
- Round 2/3 (owner: FPS while moving): DEFER, x2 fast path, SKIP, MOVENEAREST, DEFER1, HUDPERF MT, incremental minimap
  2x, HUDPERF MASK; quit no longer saves an 800x600 window; surface create retried (CREATEFAIL). A/B in
  verify/cityzoom/RESULTS.md.
- Right-drag + zoom (owner 2026-10-23): cause = the drag anchor is in the press-time factor's view pixels; fix
  DRAGANCHOR (re/analysis/CITY_ZOOM.md last section). Built into inst_cityzoom2 (the owner's game holds inst_cityzoom's DLL).

Files to commit (worktree Simcity_wt_cityzoom): re/harness/src/sc3resize.c, re/analysis/CITY_ZOOM.md,
verify/cityzoom/RESULTS.md, re/sessions/STATUS_cityzoom.md (copy). MAIN: verify/cityzoom/owner_shots/* (local only).
