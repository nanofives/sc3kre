# City zoom that scales with the screen (task cityzoom, 2026-10-22) - BUILT (route A), owner hand test pending

Owner request on the LAN build of main `2564a08`: "as we scale up, can you also scale the zoom levels? because on 4K
screens the game looks too zoomed out on the highest zoom level."

## Facts (engine)

- Zoom is `iso+0x28` = 0..4. `FUN_10006752` (iso vt+0x38, set zoom) writes tile width `+0x30 = 8 << zoom`, height
  `+0x38 = 4 << zoom`, `+0x34 = 1 << zoom`. It has no range check `[CONFIRMED @ SIMSPR 0x10006752]`.
- The 0..4 clamp is only in the callers: controller vtable `0x10063390` slot +0x60 `FUN_1001d2d6` (zoom in, returns when
  zoom == 4), +0x64 `FUN_1001d365` (zoom out, returns when 0), and iso vt+0x3c `FUN_1000699f` / +0x40 `FUN_100069da`
  (`< 4` / `> 0`). ZOOMCENTER already wraps +0x60/+0x64 (`sc3resize.c` ZOOMCENTER block).
- **The stock closest zoom is already magnified art.** `FUN_1001f5b1` / `FUN_10020570` do `if (z < 4) z++` on the art
  request, so zoom 3 and zoom 4 load the same resource; for zoom > 3 `FUN_1001f718` / `FUN_100205fe` set the flag
  `this+0x1d+zoom`, and `FUN_1001fef9` then draws through the surface's scaled blit (vt+0x50) instead of +0x48. GZGraphicD
  `FUN_1000239d` picks its 2x or 4x branch from `dst width == 2 * src` or `4 * src` (no scale argument). What the
  player sees at zoom 4 is zoom-3 building art doubled by the engine.
- Zoom-indexed tables are 5 entries: `DAT_100624c8` {120,80,40,20,10} (recentre threshold, `FUN_10006226`),
  `DAT_100624dc` {32,20,16,8,4} (prefetch margin), `DAT_100624f0` {0x10..0x100} (per-zoom "art loaded" bit in the tile
  word +0x10, 13 users), `iso+0x42c[5]`. Sprite instance ids are `base + rot*5 + zoom` (`FUN_1002517a`, `FUN_1002147b`,
  `FUN_10029b6d`): a zoom 5 would collide with the next rotation's zoom 0.
- Picking: `FUN_1000902f` takes a client point, adds the view origin (`FUN_100090b7`, +0x54/+0x58) and walks tiles
  (`FUN_100090ef`: flat inverse `FUN_1000a33a`, then altitude and per-sprite hit tests). Callers: controller
  `FUN_1001d503` (+0x78), `FUN_1001d698` (+0x8c), `FUN_10010121`. It works on whatever size the view has.
- Cursor reads outside messages: GZWIND `FUN_10020260` (GetCursorPos + ScreenToClient, virtual, no direct caller) and
  GZGraphicD `FUN_100178a6` (WM_MOUSEWHEEL point through ScreenToClient). None in SC3U, SIMSPR, SIMUI. sc3overscroll's
  edge scroll reads GetCursorPos against the client rect.
- Readers of the view size `+0x5c - +0x54` / `+0x60 - +0x58`: `FUN_10006752`, `FUN_10006226` (scroll), `FUN_100061d1`,
  `FUN_10006167`, `FUN_1000b4b3` / `FUN_1000db86` (8x8 dirty split), `FUN_1000ec0b` (centre on object), `FUN_1000e2c0`,
  `FUN_1000ee29`. No minimap view-box reader in SIMSPR (where the minimap reads it is `[UNCERTAIN]`).
- The resize routine (`RESIZABLE_WINDOW.md` section 2) already sizes the view to any w x h without Init. The game Blts the
  whole city layer into the composite once per frame (HUD_SCALE.md "Frame structure"), and sc3resize already finds that
  Blt (HUDPERF counts it).

## Measured (instance `inst_cityzoom`, Europolis copy, 3840x1984 maximized on the 3840x2160 TV, HUD Fit 3.307x, smooth,
all 8 mods, two other games running on the PC at the time)

| | 3840x1984, zoom 4 | 1920x992, zoom 4 |
|---|---|---|
| presents per second (sc3perf shows double) | 16 to 25 | 28 to 30 (at the 60 Hz cap, ~400 ms/s waiting) |
| city layer -> composite Blt | 9.2 to 15.2 ms each | 3.1 to 3.4 ms each |
| HUD pass (pre-present) | 9.8 to 17.9 ms per frame | 4.2 to 5.0 ms per frame |

Offline stretch cost, 16bpp, to 3840x1984 (`stretch.c`, same compiler and flags as the mods, same loaded PC):
memcpy of the frame 13.4 ms | 2x nearest 9.1 ms | 2x smooth (exact 2x bilinear) 15.1 ms, 8.5 ms on 4 threads |
3x nearest 10.3 ms | 3x bilinear 48.5 ms, 18.6 ms on 4 threads | 1.5x bilinear 47.7 ms, 15.6 ms on 4 threads.
So an integer stretch costs about what the game's own 1:1 Blt costs today, and a non-integer bilinear costs more.

Mockups from a real frame dump (`MAIN\verify\cityzoom\`): `mock_1x_stock_4k_zoom4.png`, `mock_2x_*`, `mock_3x_*`,
`mock_fit3.3x_*` (nearest and smooth, HUD pasted from the real frame), `overview_stock_2x_3x_fit.png`,
`detail_1to1_stock_2xnear_2xsmooth_3xsmooth.png`. They are what route A draws: the internal view at cw/f x ch/f is the
same pixels as the centre crop of the full-size view.

## Options

### A. Extra zoom steps past the stock closest, drawn small and stretched (RECOMMENDED)

Stock zoom 0..4 unchanged, at full window resolution. Zoom in at zoom 4 adds steps "x2", "x3" (integer factors up to
`floor(min(cw/800, ch/600))`: 2 and 3 at 3840x1984, 2 at 2560x1351, none below 1600x1200). In a magnified step:
1. the resize routine sizes the view to `cw/f x ch/f` (render target, device surface, extent, grids), the city view
   window keeps the client size, the centre tile is kept (ZOOMCENTER);
2. the one city layer -> composite Blt becomes a stretch from `[0 0 cw/f ch/f]` to the client (nearest, or exact 2x/3x
   smooth on 4 threads when `[hud] smooth` is on);
3. city mouse messages (not on an enlarged HUD, dialog or native HUD window) get `q / f`, the wheel point too; GZWIND
   `FUN_10020260` hooked for the same map;
4. floating windows the game puts next to the cursor in the city (cost label, city tooltips) are moved from `p` to `f * p`
   at present time, native size;
5. HUDSCALE's see-through mask and "city at the dest pixel" read the stretched city instead of `iso+0x74` 1:1;
6. LCENTER / ZOOMCENTER map area in view pixels (`/ f`).

Cost: the city is drawn at a quarter (x2) or a ninth (x3) of the pixels, the stretch replaces the 1:1 Blt at about the
same cost, the HUD pass is unchanged. Expected frame rate in a magnified step: not below today's 4K zoom 4 (16 to 25
presents/s), probably above. This is an estimate from the table above, not a measurement.

Quality: identical to stock zoom 4 pixels, enlarged. Nearest is crisp blocks (the engine already doubles zoom-3 art at
zoom 4, so x2 nearest shows zoom-3 art at 4x). Smooth is even and soft (detail sheet).

What breaks or needs work: points 3 to 6 above. Free by construction: picking (the view is just smaller), dirty rects
(full-layer Blt every frame), the minimap view box (it follows the view extent; to check), scroll speed (same world
speed as stock zoom 4), overscroll (camera rect), edge scroll (real cursor against the client rect), query tool, undo
buttons (HUD), the tool preview and drag lines (drawn in the city layer).

Size: about 400 to 600 lines in `sc3resize.c`, city-view code only except point 5 (HUDSCALE code, uiscale stream).

### A'. Same mechanism, one "city scale" factor for every zoom level

What the request literally says. At 4K with factor 2 every zoom shows a quarter of the map, the stock far zooms lose the
point of a 4K window. Same code as A with the factor applied at zoom 0..4. Can be a second setting later.

### B. A native zoom 5 (engine draws 256x128 tiles)

Rejected. Needs a sixth entry in the 5-entry tables, a new art-loaded bit (0x200 is outside the table), and sprite
instance ids `base + rot*5 + zoom` collide with the next rotation. The art does not exist: the engine would draw zoom-3
art through its 4x branch, the same pixels A gets at x2, at full 4K cost.

### C. Render the whole game small and stretch the whole frame

Rejected (HUD_SCALE.md option E): the far zooms shrink too and the HUD is stretched twice.

## Owner choices (needed before the build)

1. Route A (extra steps past zoom 4) or A' (scale every zoom)?
2. Steps: integer factors up to the HUD Fit factor (x2, x3 at 4K), or only x2, or the Fit factor itself (3.3x, the
   800x600 look, non-integer, ~16 ms smooth on 4 threads)?
3. Option in Preferencias "Zoom extra: Off / Auto / x2", default Auto, on regardless of the HUD scale value? Proposed:
   default Auto, since nothing changes until the player zooms past the stock closest level.
4. Filter follows `[hud] smooth` (default smooth), or its own setting?

## Risks

1. A cursor read this plan has not found (hover, drag) would make hover wrong while clicks are right (HUD_SCALE.md risk 4).
2. A native dialog rect under a mapped city point catches a city click while DLGSCALE shows the dialog elsewhere.
3. Each step change is a view resize at 4K (the routine's cost at 4K not measured; SKIPREFRESH skips the tile refill).
4. Blts the game makes in client coordinates right after a size change (HUD_SCALE.md, `[UNCERTAIN]`).
5. Shared HUDSCALE code with the uiscale stream (point 5).
6. Timings above were taken with two other games on the PC; the A/B in the build phase must run alone.

## Built (2026-10-22, owner go: route A, x2 and x3, Auto default, filter follows smooth)

Code: the CITYZOOM block in `re/harness/src/sc3resize.c` (before `rz_hs_city`), plus marked `task cityzoom` hooks in
`rz_poll`, `rz_do_resize` step 6, `rz_blt_hook` / `rz_blt_hook_inner`, `rz_hs_city`, `rz_hs_pre`, `rz_hl_add`,
`tip_stub1`, `rz_zc_area`, `lcenter_sub`, the zoom wrappers `zc_wrap0/1`, `rz_wndproc`, the Preferences hooks, and the
export `sc3resize_view_factor` (read by `sc3overscroll.c` `visible_size`).

Fact found while building `[CONFIRMED @ runtime log 2026-10-22]`: per frame the game Blts the render target iso+0x74
`[0 0 vw vh]` into the device surface iso+0x4ec, draws the HUD into iso+0x4ec, and presents iso+0x4ec to the screen
(`[0 56 3840 2040]` on the primary). So iso+0x4ec IS HUDSCALE's composite. The resize routine sized both surfaces
with the view, which made the game stretch the whole frame, HUD included (first try). Now step 6 gives iso+0x4ec the
client size when a factor is on, and only iso+0x74 and the extent take the view size.

How it works:
- `cz_zoom` (zoom in/out wrappers, controller vt+0x60/+0x64): at zoom 4, + raises the step up to `cz_max` and - lowers
  it; the game's own method is skipped. `cz_max` = `min(cw / 800, ch / 600)` floored, at most 3 (2 with zoomextra=2).
- `rz_poll`: view = ceil(client / f). A new city, zoom away from 4, or a client too small for the step drops it. On a
  step change the world point under the map-area centre is kept: iso vt+0x30 (ScrollTo, `FUN_10006736`) after the
  resize.
- `rz_blt_hook`: the city Blt (src = iso+0x74's surface, covering the view) is rewritten to a client-sized Blt; the
  inner hook does it with `cz_stretch` (one flag, consumed by the first Blt from iso+0x74, so a nested Blt such as the
  RCI repaint is untouched). Everything after it (HUDFIX records, lazy restore, RCI fix) sees the usual city Blt.
- `cz_stretch`: dest pixel (x, y) = view pixel (x / f, y / f); smooth blends toward the next one by (x % f) / f per axis
  (same grid, so the mouse map is the same for both filters). Rows over 4 threads above 400,000 px.
- HUDSCALE reads "the city" through `rz_hs_city`: with a factor that is a client-sized buffer filled by `cz_fill_hs`
  only on the rects the pass reads (each window's source and dest, dialog native and dest, +-2 px).
- Mouse: a queued message on the city (not on an enlarged HUD rect, dialog, or visible UI window) gets `q / f`; a press
  keeps the map to its release; the game's repost of our point is left alone. Wheel point too. HUD scale Normal has
  its own block.
- Cost label: `tip_stub1` multiplies the view point by f before it builds the anchor box (the game then places its own
  label at the cursor); `rz_hl_add` multiplies `g_tip_mx/my` (view pixels) for the enlarged label.
- LCENTER / ZOOMCENTER map area and sc3overscroll's visible size are divided by f.
- Preferencias: checkbox "Zoom extra" / "Extra zoom" right of "Suavizado" (`[345 400 ...]`, id `0x02F95B4A`), OK writes
  `sc3resize.ini [view] zoomextra`.

Measured (3840x1984, Europolis copy, HUD Auto 3.307x, all 8 mods; `MAIN\verify\cityzoom\RESULTS.md`):

| | presents/s | stretch | HUD pass |
|---|---|---|---|
| stock zoom 4 (plan, other games running) | 16 to 25 | (game Blt 9 to 15 ms) | 9.8 to 17.9 ms |
| x2 smooth, 1 thread (first build) | 27 to 29 | 9.9 to 10.6 ms | 7.6 to 8.2 ms |
| x2 smooth, 4 threads | 45 to 54 | 3.3 to 4.4 ms | 5.8 to 7.1 ms |
| x2 nearest, sim running | 59 to 60 (cap) | 2.3 ms | 3.6 ms |
| x3 nearest, sim running | 60 (cap) | 2.2 ms | 3.6 to 3.8 ms |

Not covered / open:
- GZWIND `FUN_10020260` (GetCursorPos + ScreenToClient) is not mapped. Hover and drag previews followed the mapped
  messages in every check, so no reader of it was seen; if one shows, map it there.
- A city click whose q / f lands on a native window drawn elsewhere (risk 2) is logged (`(lands on a UI window)`), not
  prevented. Not seen at 3840x1984 (q / f stays in the top-left half, away from the native HUD box).
- Save / load while magnified: a new city starts at x1 (by design), not run. Terrain editor / New City, not run.
- The second monitor / a window drag between monitors while magnified, not run.

## FPS while moving (owner hand test 2026-10-22: "it looks perfect, but there's some minor FPS drop when moving around")

Measured with `SC3RESIZE_CITYZOOM_DIAG=1` (one `CZDIAG>` line per second: presents, camera moved or still, longest
interval, ms per frame in the stretch / HUD pass / present, and the DEFER counters), arrow-key scrolling through
`key_state_spoof.py`, sim running, 3840x1984, HUD Auto, smooth. Runs `inst_cityzoom\pan4` (before) and `pan5` (after).

Cause `[CONFIRMED @ HSSEQ Blt sequence, run seq1]`: while the camera moves the game Blts the view into the frame twice per
frame. The order is: present, scroll (view onto itself), RCI corner, full view, RCI corner, full view, the HUD, present.
The first full copy is overwritten by the second, but each one was a 4K stretch, so every moving frame paid two
(copied 2.9M HUD px per present instead of 1.7M). Stock zoom 4 does the same with two 1:1 4K copies (x1 moving 22
presents/s, still 30).

Changes (all in the CITYZOOM block):
- DEFER: a city Blt only marks the frame as owed; the next city Blt drops an owed one; any other access pays it first
  (a Blt from the frame, a Lock / GetDC / BltFast of it, a Blt onto it bigger than 20,000 px). Up to two small Blts
  onto it (the RCI corner) pass through and are replayed after a late stretch. Only while HUDPERF's Lock / GetDC /
  BltFast hooks are installed. `SC3RESIZE_CITYZOOM_DEFER=0` turns it off. Measured: dropped 37 to 42 stretches per
  second while moving, every owed stretch paid by the first HUD Blt (0 at the present, so sc3perf's overlay is safe).
- x2 smooth fast path: two pixels per DWORD with the bit-trick average, the same floor((a + b) / 2) the lane blend gives
  at weight 16 of 32 (bit-identical).
- HUD-city buffer: copied from the frame right after the stretch (last pass's rects) instead of stretched again; a
  native rect inside its enlarged rect is not filled twice.
- Worker threads stay at 4 (6 lost to the sim's 8 traffic workers); bands from 100,000 px.

| presents/s (median of 1-s lines) | before (pan4) | after (pan5) |
|---|---|---|
| x1 still / moving (stock zoom 4) | 30.1 / 22.2 | 30.0 / 22.0 |
| x2 still / moving | 52.0 / 36.3 | 59.0 / 49.2 |
| x3 still / moving | 50.2 / 36.8 | 57.5 / 51.7 |

Left while moving: the HUD pass grows from ~3.9 to ~7 ms per frame (HUDPERF rebuilds what the moving city under
see-through HUD parts and the minimap view box change), at x1 as well, so it is not cityzoom. The same DEFER rule would
also drop stock zoom 4's redundant 1:1 4K copy (about 10 ms per moving frame); not applied, the stock path is unchanged.

## Round 3 (owner: "performance is still not optimal"; go: skip HUD-covered pixels, nearest while moving, the HUD pass while moving, stock zoom's duplicate copy)

The owner's second session ran with other sessions' test jobs on the PC (3 `port.test.boot` workers, then `mashed_re`):
stretch 6.7 to 8.5 ms and HUD pass 8 to 10 ms per frame, about twice the quiet-PC numbers. So the comparison below is an
interleaved A/B with one binary: A = this round's features off by env, B = defaults, launched A, B, A, B under the same
load (23 to 57 %), x1 / x2 / x3, 8 s still + 12 s arrow-key scrolling each, sim running.

Changes (env switch to turn each off):
- SKIP (`SC3RESIZE_CITYZOOM_SKIP=0`): dest pixels the last HUD pass composed from HUD taps only (HUDPERF cached runs)
  are left out of the stretch and the HUD-city copy; native HUD rects never are. About 913,000 px per frame at 3840x1984.
- MOVENEAREST (`SC3RESIZE_CITYZOOM_MOVENEAREST=0`): nearest while the view origin moved in the last 120 ms.
- DEFER1 (`SC3RESIZE_CITYZOOM_DEFER1=0`): the same drop-the-overwritten-copy rule at x1. Measured there: the game copies
  the view into the map area only (`[0 0 3744 1928]`) and passes a DDBLTFX; 15 to 16 copies per second dropped while
  moving. No measurable fps change at x1 (its moving cost is elsewhere).
- HUDPERF MT (`SC3RESIZE_HUDPERF_MT=0`): a window's rebuilt dest pixels in row bands over the CITYZOOM workers.
- Minimap 2x incremental (`SC3RESIZE_HUDSCALE_EPXINC=0`): the changed native rows +-2 instead of the whole buffer.
- HUDPERF MASK (`SC3RESIZE_HUDPERF_MASK=0`): snapshot changes at pixels no cached value reads do not trigger a rebuild.
  Fired on only 2 to 9 rows per frame: the moving cost is the minimap's view box (HUD pixels), not the city behind.
- Output checks: `SC3RESIZE_HUDPERF_CHECK=1` 0 px differ over about 1,400 frames (MASK + MT); new
  `SC3RESIZE_HUDSCALE_EPXCHECK=1` 512 incremental minimap rebuilds, 0 readable px differ (pixels of see-through
  sources differ and are never read).

| moving, presents/s | A1 | B1 | A2 | B2 |
|---|---|---|---|---|
| x1 (stock zoom 4) | 20.6 | 20.1 | 21.3 | 21.1 |
| x2 | 28.5 | 33.2 | 33.8 | 37.7 |
| x3 | 29.8 | 37.5 | 34.2 | 41.2 |

Moving frame split (A2 vs B2): stretch 7.6 to 9.3 -> 3.4 ms; HUD pass 9.3 to 10.6 -> 8.0 to 8.2 ms (compose 6.4 to 7.7
-> 4.9 to 5.3, minimap 2x 1.2 to 1.3 -> 0.6 to 0.7). Still frames: within the run-to-run spread.

Left: the HUD pass floor (about 3 ms per frame copying the 1.5M px enlarged HUD even when nothing changed), the present
(2.6 ms quiet, 4 to 5 ms under load), the game's own scroll work (x1 moving 20 to 21 presents/s with or without this round).

Also fixed: at quit the game restores the window to 800x600 by itself (WM_SIZE SIZE_RESTORED 800x600 about 0.6 s after
the quit dialog), and WINMEM saved that, so every start after a quit came up small. A restore to exactly 800x600 now
saves only after a player window command (WM_SYSCOMMAND / title double-click) in the last 2 s. Checked: quit through
the dialogs, ini kept `maximized=1`.

Crash seen once in a test run (`inst_cityzoom\pan7`): at a x1 -> x2 step both surface creates returned 0
(`FUN_10009efb` -> vt+0x1dc failed), the render target was left with a NULL surface object (+0x44) and the next draw
read through it (GZGraphicD `FUN_10014649` Lock). The same NULL +0x44 the monitor-change crash leaves; no display event
was logged, and the cause is `[UNCERTAIN]` (a Frida key-state spoof had just detached in that run). Now: up to 6 create
retries with a growing sleep (logged `CREATEFAIL`), and no ScrollTo on a render target without a surface.

## Right-drag + zoom (owner 2026-10-23: "when I scroll holding right click and then I press '+' to zoom, the camera flies the other way I'm facing")

Build: this branch (the owner's game was `inst_cityzoom`, round 3), not the LAN 2564a08. Log `handtest_1023`: a right press at
x3 (mapped to view (723,407)), no release, then steps x3 -> x2 -> x1 with the button held; in the 1.1 s at x2 the kept
centre moved from (-8377,5209) to (-3336,9127), i.e. right and down.

Mechanism `[CONFIRMED @ SIMSPR 0x10043daf, 0x10042cfe]`: the right-drag scroll is a velocity. SetDragMode (city view vt
0x10067894 +0x3c, `FUN_10042cfe(x, y, on)`) stores the anchor at view+0x1ec/+0x1ee and the mode at +0x1e6; each tick
`FUN_10043daf` scrolls by the velocity at +0x1f4/+0x1f8 (floats, from mouse - anchor), all in view pixels. Measured with a
probe: press at client (1760,900) -> anchor (1760,900) at x1, (880,450) at x2, (586,300) at x3; a zoom (stock or a step)
turns the mode off (+0x1e6 = 0). The anchor is the press point as the game got it, so in the factor at the press; after a
step the moves arrive as q / f_new. The flight direction in the owner's log (positive velocity after x3 -> x2) is the old
anchor (q0 / 3) against new moves (q / 2). Stock zooms keep the mouse map 1:1, so the LAN build cannot do this.

Fix (DRAGANCHOR, `SC3RESIZE_CITYZOOM_DRAGANCHOR=0` turns it off): (1) a drag still active at a step has its anchor scaled
by f_old / f_new and its velocity cleared; (2) SetDragMode is wrapped: turned on with exactly the last right press point
the game was given, after the factor changed since that press, the point is put in the current factor. Any other anchor
passes as is. Left-drags (tools) map at the current factor, so a road drag across a step follows the cursor.

Not reproduced end to end: with posted input (and VK_RBUTTON reported held through the GZWIND key leaf, GetAsyncKeyState
and GetKeyState) the zoom ends the drag and it never restarts, so the owner's restart path (real mouse, likely another
input path) could not be driven here; both of its possible forms are covered by (1) and (2). Checked with the fix: the
hook installs, drags at x1 / x2 / x3 keep working, plain zoom steps and rotation keep the centre (tile (35,128) over three
rotations at x2). Overscroll edge with a held drag: not run (the synthetic drag ends at the step).
