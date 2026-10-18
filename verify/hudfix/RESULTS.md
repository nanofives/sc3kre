# RESULTS: hudfix A/B (task hudfix, 2026-10-11)

Pre-registration: `PRE.md` (committed in `ca51982` before the arms ran). Evidence (gitignored, MAIN `verify/hudfix/`):
`armA/`, `armB/`, `armB2/`, `armB3/`, `armN/`, `dlg1/`, `smoke/`, per arm `scroll/` (reference + frames during the
scroll), `score.txt`, `heat_hud.png` (red = a pixel inside the enlarged HUD that changed in 3+ frames, yellow = 1 to 2),
`frame_before/after_1200x900.raw` (in-process dump, RGB565), `sc3resize.log`.

Arms: A = `SC3RESIZE_HUDFIX=0` (control). B = first HUDFIX build (`ca51982`). B2 = B + minimap tent blur (slow).
B3 = B2 + speed-ups, the build that ships on the branch. N = B3 with smoothing off.

## Prediction by prediction

| # | Prediction | Result |
|---|---|---|
| 1 | A reproduces: U(P) >= 50 or U(R) >= 50 | **PASS.** A: U(P) = 3553, U(R) = 1797, U(L) = 6. `armA/heat_hud.png`: specks along the side-panel button outlines, in the RCI columns, around the minimap buttons and the layer button. |
| 2 | B: U(P), U(R), U(L) <= 5 | **P and L PASS, R FAIL as written, criterion wrong.** B3: U(P) = 0, U(L) = 10, U(R) = 311. The R rect I chose includes the RCI window's transparent top overhang, where the city legitimately shows and moves: all 311 (B3) and 313 (B) pixels are above the bar top (y < 1022), 0 inside the bar and RCI, against 1385 inside them in A. The 10 L pixels in B3 are x 0..2, y 1117..1122, the bar art's own transparent bottom-left corner, which shows the moving city (B2 had 0 there). N with R moved below the bar: U = 0 in all three. |
| 3 | camera moved, >= 30 frames | **PASS.** A 78, B 86, B2 78, B3 80, N 88 frames with > 30% city change against the previous frame. |
| 4 | B cost <= A + 3 ms (logged pre-present ms per frame) | **PASS for B3**, with a caveat on the A figure. A logs 2.55 to 3.10 ms, but that is per PASS: A runs the pass twice per frame (also on the city -> composite Blt, 164 passes/s at ~82 fps), so about 5.6 ms per frame. B3 runs once per frame: 3.9 to 4.1 ms at 1200x900, 5.0 ms maximized (2048x1081), ~82 fps like A. B (6.3 ms) and B2 (7.4 to 8.3 ms, fps down to 61 to 74) were slower; B3 fixed that (stage timers: minimap 2x 1.5 -> 0.02 ms with the cache, resample ~5 -> ~3.4 ms). |
| 5 | minimap smoother in B, frame/buttons the same | **PASS by eye (mine, owner to judge).** `minimap_A_vs_B3_x2.png` (in-process dumps, same view): octagon diagonals soft in B3, stair steps in A. Buttons and frame the same. Filter choice: `minimap_filters_x2.png` (offline, five filters on the dumped native minimap). |
| 6 | regressions | **PASS.** No ini: log `smooth 1`, Suavizado checked (`dlg1/02_prefs.png`). 125% + OK: `HUDOPT> OK: scale 125, smooth 1, saved` and the HUD grows (`03`). Reopen from the enlarged flyout, 200%, Esc: `kept scale 125 smooth 1` (`04`, `05`). Restart: `scale 125 smooth 1`. ini `smooth=0`: `smooth 0`, filter nearest. `SC3RESIZE_HUDSCALE_FILTER=0`: `smooth 0 (... from SC3RESIZE_HUDSCALE_FILTER)`. `SC3RESIZE_HUDOPT=0`: 0 HUDOPT lines, no HUDSCALE. |

Extra, not pre-registered: maximized (2560x1351 physical, 2048x1081 virtual, 150%) scroll with B3: 78 frames, 41
moving, U = 0 in the panel and in the bar's lower row (`armB3/heat_max_corner_x2.png`).

Deviations from PRE: arm A's first scroll grab failed (window partly off screen, then the NVIDIA overlay was on top for
one grab). The window was moved to (100,20) on the same monitor and the grab rerun on the same instance; the arm script
does that move before the resize for every later arm. Every arm logged one `VEH FAULT ... SC3U.exe+0x84122` at ~350 ms
of startup, before any resize; the owner's own `inst_hudopt` log and my r1 run have the same line.

## Follow-up: the owner's frame (orchestrator, `.happy-uploads/image-1791760014062.png`)

The owner's crop shows (a) city above the bar left of the globe/news button, near "?", and (b) black/white blocks in
the R, C and I columns.

- **(b) is the defect fixed here.** Arm A (HUDFIX=0) reproduces it during a scroll: city pieces inside the RCI columns,
  plus a speck right of "?" (`owner_repro_rci_crop.png`, A frame f93 next to B3 frame f98 and the native HUD). Mechanism
  (code, not a per-pixel trace of that frame): the old test drew a HUD pixel as see-through whenever it equalled the
  city-layer pixel at the same spot; the RCI is a keyed Blt straight into the composite, and with the recorded coverage
  its non-key pixels are HUD whatever their colour. B3: none in 150 frames.
- **Self-updating widgets, sim running** (not pre-registered, added for this report): `runA` / `runB`, ini scale 150,
  P to unpause, 4 for the top speed (log `PAUSEKEY> ... resume`, `SPEEDKEYS> speed 4`), same scroll. Changed pixels in
  the panel 4296 (A) vs 0 (B). Bar heat map (`runA/heat_bar.png`, `runB/heat_bar.png`): in B only the ticker, the date
  field and the minimap view box change, which the game itself updates. In A there are also specks in the RCI columns,
  on the globe button, around "?" and on the minimap buttons. Frame strip: `runAB_rci_frames.png`.
- **(a)** The city to the left of the globe button above the bar is in the native, unscaled HUD as well
  (`owner_repro_rci_crop.png`, left panel): the globe/RCI corner sits higher than the bar, so the view shows there in
  the stock layout too. If the owner meant a garbage line there, see the next item.
- **Not HUD scale: a black line scrolling through the city.** During the running-sim scroll a 4-px black row moves up
  with the map (y 1000 -> 990 -> 980 in f59..f61 of `runB`). It shows in A (81 frames), B (86) and with HUD scale
  OFF (`runOff`, 78 frames, `runOff/blackline_f104.png`), so it is an existing render artifact during scrolls,
  independent of this work. Its cause is `[UNCERTAIN]` (not investigated here).
