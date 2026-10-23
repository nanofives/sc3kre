# STATUS minimap (child of "SC3: owner bugs 10-23"), 2026-10-23

Worktree `Simcity_wt_minimap` (child/minimap), test tree `Simcity_stock_minimap`. State: **fixed, checked in game**.

## Cause
The minimap's map is a SIMUI map-view child (factory `0x5a9`, vt `0x100a7e68`), 129x129, whose texture is quantised to
128 texels (`FUN_100436b4`). sc3resize HUD scale enlarged that reduced picture, hence the blur.

## Fix
MININAT block in `sc3resize.c` (own block, `SC3RESIZE_MINIMAP_NATIVE=0` = off): a game Clone of the map view sized to the
HUD factor with its own raster, drawn whenever the native one draws, copied 1:1 over the enlarged map where the native
pixel is the map's own. Freed on the minimap's drop/rebuild messages and shutdown. Detail: `verify/minimap/RESULTS.md`,
`re/analysis/HUD_SCALE.md` last section.

Checked: 1024 city, minimap click, 2.187x, maximized 3.307x, restore, rotate, two city loads, layers dialog, control run. Cost 0.14 ms/frame compose,
0.35 to 0.47 ms per twin draw.

Pictures in `MAIN/verify/minimap/owner_shots\`: `09_native_old_new_2187.png` (native | old | new), `03`, `04` (A/B),
`10..14` (1024 + click), `05..08` (maximized, view box, rotated, after loads).

Seen, not changed: one load logged 168 first-chance AVs in `IsBadReadPtr` from existing `rz_poll` / `rz_hs_city` reading the
old city's iso view through stale `g_bridge` (game continued, second load 0). For the reload1024 stream.

## Files to commit (worktree `Simcity_wt_minimap`, by path)
- `re/harness/src/sc3resize.c` (MININAT block + 4 hook-up lines: collect, pass call, env var, 10 s log)
- `re/analysis/HUD_SCALE.md` (new last section)
- `verify/minimap/RESULTS.md` (also in MAIN)
- owner shots stay local in `MAIN\verify\minimap\owner_shots\` (game art)
