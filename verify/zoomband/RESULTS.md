# RESULTS: stale band after a zoom change + scroll (task zoomband, 2026-10-26)

Owner report (MARIANO-PC, maximized client 2560x1351, HUD scale Auto, main c2276dd): "when scrolling down a bit after
changing zoom a line of wrong rendering appears, it goes away after moving around a little bit". Picture
`MAIN\verify\zoomband\owner_shots\img1_band_after_zoom_scroll.png`.

Worktree `Simcity_wt_zoomband` (branch `child/zoomband` from main 742fe1f). Test tree `Simcity_stock_zoomband`, all 7 mods
+ version.dll built from the worktree, Europolis, posted input and the key_state_spoof arrow hook only (no cursor,
keyboard or foreground). Raw dumps and logs: `MAIN\verify\zoomband\runs\` (local, not committed).

## Cause

1. The owner's stripe is exactly **7 rows** tall (picture rows 62..68: background 90,97,115 above and below, 82,89,107
   with terrain-coloured pixels inside). 1351 = 168 x 8 + **7**.
2. The game's full repaint, iso view vt+0x14c = SIMSPR `FUN_1000b4b3`, splits the view into 8 x 8 tiles of
   `(W) / 8` x `(H) / 8` pixels with integer division, hands each tile to vt+0x130 (dirty-rect intake) and draws with
   vt+0x148(1,1) [CONFIRMED @ SIMSPR 0x1000b4b3]. It covers `8 * (W / 8)` x `8 * (H / 8)`. At 2560x1351 that is
   2560 x 1344: **rows 1344..1350 are never redrawn** and keep whatever an earlier frame left there.
3. The full repaint runs on every zoom change and on the layout pass (and on a scroll too large for the copy). A normal
   scroll, `FUN_10006226`, copies the view onto itself by (dx, dy) (render target vt+0x120) and invalidates only the
   strip it exposes [CONFIRMED @ SIMSPR 0x10006226]. Scrolling down moves the picture up, so the stale rows travel up
   with it, while the newly exposed bottom strip is drawn correctly. The rows start under the HUD bar and show above it
   after about 130 px of scrolling. They go away when that area is redrawn for another reason (dirty cells, more
   scrolling), which is the owner's "goes away after moving around".
4. Measured with a new diag, `SC3RESIZE_FRAMEDUMP_VIEW=1`: each frame dump also writes the city render target iso+0x74
   itself, slack rows included, so the rows under the HUD bar can be seen. Unfixed, 2560x1351:
   - after the layout pass: view rows 1344..1350 flat (no row-to-row change), a 0.99 seam at 1344;
   - after an 8 px scroll down: the stripe at 1336..1342, rows 1344..1350 now drawn;
   - after each zoom step (zoom 3 -> 4, 4 -> 3, ...): the stripe back at 1344..1350.
5. It is a size issue, not a zoom-level one. It happens at x1, so at every stock zoom level, and `SC3RESIZE_CITYZOOM=0`
   does not change it. At x2 / x3 the CITYZOOM view is rounded up to a multiple of 8 (ALIGN8, rc_1023 row 9), and ALIGN8's
   6-row band at x3 (662 = 82 x 8 + 6) was this same function. The stock game never meets it: its window sizes are table
   sizes, all multiples of 8 (800x600 etc.). A width off a multiple of 8 (2561) loses its last column(s) the same way.

## Fix

`re/harness/src/sc3resize.c`, block **REPAINT8** (after DIRTCLIP / CELLFIX, installed next to `patch_dirtclip`): a
6-byte jump at SIMSPR+0xb4b3 (prologue and the call to FUN_1000e248 checked against the shipped bytes first) to
`rp8_full_repaint`, a C copy of the function: FUN_1000e248(iso), clear byte iso+0x32c, the same 8 x 8 tiles of W/8 x H/8,
except that the last tile of each row and column ends at the view edge, then vt+0x148(1,1). When both sizes are
multiples of 8 the tiles are identical to the game's. Calling conventions checked from the bytes: the original is
`__fastcall` with no stack arguments and ends `leave; ret` (c9 c3), vt+0x130 ends `ret 0xc` (3 args), vt+0x148 `ret 8`,
FUN_1000e248 `ret`. It logs `REPAINT8>` for the first 6 full repaints at a size off a multiple of 8.
Off switch: `SC3RESIZE_REPAINT8=0` (the game's function stays).

Also added: the `SC3RESIZE_FRAMEDUMP_VIEW=1` diag above (inside FRAMEDUMP, off by default) and the test switch
`SC3RESIZE_CITYZOOM_ALIGN8=0` (CITYZOOM block, default 1, see below).
Tools: `re/tools/zoomband_run.py` (zoomcrash_run.py plus arrow-key scrolling through key_state_spoof, `--keep`, `--pid`,
`--client max`), `re/tools/zoomband_check.py` (counts stale bands in the view dumps: two full-width seams, over 90% of
the columns changing, `H % 8` +- 1 rows apart, or one seam at `8 * (H / 8)`; a lone seam is a straight edge of the art).

## Tests

Script per size (`zoomband_run.py`): from zoom 3, out, out, in, in, in (zoom 4), in (x1 -> x2), out (x2 -> x1), out
(zoom 4 -> 3); after each step a dump, then 2 arrow taps down, right, up and left with a dump after each; then zoom in
and a long scroll down. Each dump = the presented frame + the view surface.

Bands counted by `zoomband_check.py` in the view dumps (the render target itself, so stripes still under the HUD bar
count too):

| client | build | dumps | with a stale band | where |
|---|---|---|---|---|
| 2560x1351 | unfixed (`SC3RESIZE_REPAINT8=0`) | 44 | **26** | after the layout and after every x1 step at zoom 3 / 4 (rows 1344..1350), then carried up by down / right / up / left scrolls (1336, 1328, 1312, 1304 ...). Zoom 1 / 2 and x2 dumps clean (x2 view 1280x680 is a multiple of 8) |
| 2560x1351 | fixed | 42 | 0 | same script |
| 2561x1351 | unfixed | 5 | **5** | rows 1344..1350 and column 2560 (2561 = 320 x 8 + 1) |
| 2561x1351 | fixed | 44 | 0 | `REPAINT8> ... 1 more column(s) / 7 more row(s)` |
| 2560x1350 | fixed | 47 | 0 | `REPAINT8> ... 0 more column(s) / 6 more row(s)` |
| maximized on this PC = 3840x1984 | fixed | 42 | 0 | a multiple of 8: REPAINT8 tiles identical to the game's (no REPAINT8 log line) |
| 2560x1351, owner pair (zoom 3 -> 4, 1 s scroll down = 232 px, zoom 4 -> 3, 1 s scroll down) | unfixed / fixed | 5 / 4 | **5** / 0 | unfixed: the stripe at rows 1120..1126 of the frame, above the bar, as in the owner's picture |

Pictures (`MAIN\verify\zoomband\owner_shots\`): `02_before_x1_zoom4_after_zoom_and_scroll_2560x1351.png` (the dark
7-row line across the city at y 1120), `03_after_...png` (same steps, fixed build, no line),
`04_closeup_rows1080-1170_before_top_after_bottom.png`, `05_before_x1_zoom3_after_zoom_out_and_scroll_2560x1351.png`.
The two pictures come from two games, so the city frame differs; the line is the difference to look at.

### ALIGN8 with REPAINT8 on (orchestrator request)

ALIGN8 (rc_1023 row 9) rounds the CITYZOOM view up to a multiple of 8 because of the 6-row band at x3 on 3840x1984
(view 1280x662). That band came from the same full repaint. To measure it, a test switch was added,
`SC3RESIZE_CITYZOOM_ALIGN8=0` (default 1 = unchanged). Maximized 3840x1984, zoom 3 -> 4 -> x2 -> x3, arrow scrolls in 4
directions, x3 -> x2 -> x3, view dumps checked with `zoomband_check.py --from-dump` (view size read from the dump):

| ALIGN8 | REPAINT8 | x3 view | dumps with a stale band |
|---|---|---|---|
| off | off | 1280x662 | **3 of 9** (rows 656..662 after each x3 step, carried to 640 by a scroll) |
| off | on | 1280x662 | 0 of 9 (`REPAINT8> full repaint of 1280x662: ... 6 more row(s)`) |

So REPAINT8 covers the band ALIGN8 was added for. ALIGN8 stays on by default: removing it changes the view size, and
so the stretch source and the slack-row Blts, at every x2 / x3 size, and only this one size was measured without it.
Removing it later needs the stretch and HUD checks at several sizes, not only this band count.

Frame rate: REPAINT8 has no per-frame code, it replaces the full repaint (4 calls in an 84-step run) with the same 64
tile calls. Median fps from sc3perf over the owner-pair script: unfixed 68.7, fixed 84.9. That gap is between-game
noise (memory project-perf-between-game-noise), not a gain, but it shows no loss.

`hook_audit.py` on a fixed game: the REPAINT8 jump at SIMSPR+0xb4b3 is `ours ret / original ret ok`, 0 MISMATCH over 323
install points.

Test-run traps hit on this PC (not caused by this change): with several children's games running, one start took
128 s to reach the 800x600 mode set, and sc3resize's wait for SIMSPR / GZGraphicD (600 tries x 100 ms, `rz_watcher`)
gave up first ("mod inactive"). That game never reached the city and the run was discarded. Stopping a backgrounded
`bash batch.sh | tee` stopped only the pipe, so a second batch ran at the same time and both wrote the instance folder's
sc3resize.log. Those runs were discarded and rerun one at a time.

## Not covered / needs owner check

- The mouse wheel and right-drag scrolling were not driven here. They reach the same scroll copy and the same full
  repaint, so the fix covers them, but this is unverified by test.
