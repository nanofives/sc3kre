# RESULTS: zoom and rotate keep the map-area centre tile (`SC3RESIZE_ZOOMCENTER`)

Run 2026-10-12, task `leftclick`. Pre-registration `ZOOMCENTER_PRE.md` (`7e468ac`) and its addendum (`b4ec883`,
written after the first Z1 run, before the reruns). Driver and instrument `re/tools/zoomcenter_run_arm.py`. Europolis
256, all mods from combo, `sc3resize.dll` from `child/leftclick`. Single 1680x1050 display at 100%. Evidence local
(gitignored): `re/harness/inst_leftclick/armZ1, armZ1b, armZ0, armZ2` (MAIN) and
`Simcity_stock_leftclick/re/harness/inst_leftclick/armZS, armZS2, armZS3, armZS4` (stock tree).

## Verdict: PASS (Z1b, ZS4), the control Z0 reproduces the defect, Z2 as designed. Frames pending (display asleep).

Per arm, 30 camera zoom/rotate calls: 14 at 800x600 (keys and the four minimap buttons), 14 maximized at 1680x979,
2 after restoring. "landed" = where the passed tile sits on screen after the call. "kept" = the game's own pick at the
map-area centre returns the same tile after the call as before. "fresh" = the tile passed equals the centre pick before.

| arm | 800x600 landed / kept / fresh | maximized landed / kept / fresh | restored landed / kept / fresh |
|---|---|---|---|
| Z1b `ZOOMCENTER` unset (=1), MAIN | (352,272) / 14 of 14 / 14 of 14 | (792,461..462) / 14 of 14 / 14 of 14 | (352,272) / 2 of 2 / 2 of 2 |
| Z0 `=0` (control), MAIN | (400,300) / **0 of 14** / 2 of 14 | (840,489..490) / **0 of 14** / 2 of 14 | (400,300) / 0 of 2 / **0 of 2** |
| Z2 `=2`, MAIN | (400,300) / 0 of 14 / 2 of 14 (stock by design) | (792,461..462) / 14 of 14 / 14 of 14 | (400,300) / 0 of 2 / 0 of 2 |
| ZS4 Z1's DLL, stock tree (SIMSPR relocated to 0x03FD0000) | (352,272) / 14 of 14 / 14 of 14 | (792,461..462) / 14 of 14 / 14 of 14 | (352,272) / 2 of 2 / 2 of 2 |

The 462 is the camera's even-origin rounding at zoom 4 (`& 0xfffffffe` after the half-size, `FUN_10006752`).

| # | row | result |
|---|---|---|
| 1 | install line | Z1b/ZS4 `zoomcenter=1 ... iso vt+0x60/64/70/74`, Z0 `disabled`, Z2 `zoomcenter=2 ... stock at 800x600` |
| 2 | landed on the map-area centre +-1 | Z1b, ZS4: all 30. Z0: none (whole-window centre). Z2: maximized only |
| 3 | centre tile kept | Z1b, ZS4: 30 of 30. Z0: 0 of 30 |
| 4 / 7 | restored zoom uses the fresh tile | Z1b, ZS4: yes (passed 150,128 = centre pick). Z0: no |
| 5 | no fault past the startup `0xC0000096` | Z1b, Z0, Z2, ZS4: 1 VEH line each, the startup one |
| 6 | load position (tile of the first call, after the click at (200,200)) | Z1b 148,127, ZS4 148,127, Z0 149,127, Z2 149,127. The LCENTER arms gave 150,127 for both their arms with the same build, so +-1 tile is the run-to-run spread. No ZOOMCENTER log line at load |
| 8 | minimap buttons | button at local (100,120): rotate 3 -> 0, (34,120): rotate 0 -> 3, (120,100): zoom out, (14,100): zoom in. Same results as the keys in every arm |

## Runs that did not count

- **Z1 (first run, old design):** the refresh sat at `FUN_1001d1d9`. Keys never pass through it, and at city load
  it replaced the saved centre tile 143,127 with 142,114, so the city loaded about 13 rows away. Addendum to the PRE,
  design changed to the four vtable wrappers.
- **ZS (stock tree):** maximized, DirectDraw presents took 4.7 to 5.9 s each (sc3perf `present_ms`, saved as
  `armZS/sc3perf_ZS.log`), so the inputs ran about 15 to 60 s late, after the instrument had moved to the next phase.
  The 800x600 rows were already 14 of 14 as in Z1b. The MAIN arms and ZS4 had no present above 1 s. Cause not
  established. The display was asleep throughout, and in the PRE the frames are already treated as pending.
- **ZS2:** the game exited before SIMSPR loaded (`SIMSPR/GZGraphicD never loaded`), so no mod code ran.
- **ZS3:** `VEH FAULT` at `sc3bigcity.dll+0x5F59`, a WRITE to `SIMSPR+0xD06C` right after SIMSPR mapped (relocated to
  0x033F0000), and the game exited. That is bigcity's install code. LCENTER and ZOOMCENTER had installed cleanly first.
  Reported to the orchestrator, not investigated here.

## Choice at 800x600

`=1` changes stock at 800x600: stock zoom lands the tile on (400,300), the camera's whole-window centre, and the
centre tile changes on every zoom and rotate (Z0: 0 of 14 kept). The view's own centre everywhere else is (352,272).
`=2` keeps the stock numbers at exactly 800x600 for anyone who wants that.

## Not covered

- Frames: display asleep for the whole session.
- HUDSCALE on: the map area goes through the same `rz_lcenter_area` as LCENTER, not run.
- The mouse wheel: posted wheel messages do not zoom (memory note, sc3io), so wheel zoom was not driven. If the game
  zooms on the wheel it calls the same vt+0x60/+0x64 (not verified).
