# STATUS verdatos (child of "SC3: owner bugs 10-23"), 2026-10-25

Worktree `Simcity_wt_verdatos` (child/verdatos from main b93b77c), test tree `Simcity_stock_verdatos`. State: **fixed,
checked in game** (2560x1351 and maximized 3840x1984, Europolis, Seoul, Europolis 1024).

## Cause
Each Ver datos data view is its own panel with its own SIMUI map view (379x379, texture already at the game's 256 cap).
It draws into the UI composite, and DLGSCALE resampled the whole dialog 2.25x to 3.3x.

## Fix
VERDATOS block in `sc3resize.c` (`SC3RESIZE_VERDATOS_NATIVE=0` = off, `SC3RESIZE_VERDATOS_TEX=<side>` caps the texture):
- A game Clone of the view that draws inside an enlarged dialog, sized to the dialog factor, texture up to twice the
  city's cells (512 for 256 cities, 1024 for 1024 cities).
- Redrawn only when the native picture, state or factor changes.
- Pasted 1:1 right after DLGSCALE draws that dialog, where the native pixel is the view's own (the legend stays on top),
  as row runs also written into DLGSCALE's cache.
- Freed on the view's Shutdown (close), a view switch or rotation, and after 1 s unused.

Still dialog 0.23 to 0.41 ms/frame. Twin draw 29 to 324 ms, once per open, switch or rotation, or a data refresh
(about every 20 s with the sim running).

Stall on opening Ver datos: not reproduced (11 opens over 3 cities, 2 sizes, arms on and off). Worst was a single 1.6 to
2.1 s frame, the same with VERDATOS off.

## Texture follow-up
The orchestrator's rule (smallest of 256/512/1024 at or above the on-screen size) is the shipped rule, measured along
the texture axis, so a 1024-cell city gets 1024. Cost per side on Europolis 1024: 44 to 101 / 81 to 120 / 172 to 366 ms
per twin draw. Per frame 0.27 to 0.72 ms at any side. 1024 is not too slow there (one 222 ms redraw in about 50 s of
sim). Minimap: a 512 texture would add at most 1.17x detail at 3.3x, not worth it. Detail in RESULTS.md.

## Files to commit (worktree `Simcity_wt_verdatos`, by path)
- `re/harness/src/sc3resize.c`:
  - the VERDATOS block (after mn_compose)
  - 3 lines in mn_draw and the mn_install guards (the shared draw hook)
  - 2 lines in rz_hd_draw (`g_hd_rb`)
  - `vd_idle()` at the top of rz_hs_pre, `vd_compose()` in the DLGSCALE draw loop
  - the 10 s log line, 2 env vars, 1 FLAGS line
- `re/analysis/HUD_SCALE.md` (new last section)
- `verify/verdatos/RESULTS.md` (also in MAIN)
- owner shots stay local in `MAIN\verify\verdatos\owner_shots\` (game art). Raw frames `fd*/` and logs `logs/` are local too.
