# HUD scale-up for large windows (task hudscale, 2026-10-11)

Owner request 2026-08-30, second half: when the game window grows in both directions the HUD should get
BIGGER (buttons, bar, side panel, minimap), not only longer. Today sc3resize extends the bar to the full
width and the side panel to the full height (owner design calls, `project-resize-mod-shipped`), and every
widget stays at its 800x600 pixel size.

This note compares the ways to do it, with cost and risk, and records the recommendation that the
prototype (`SC3RESIZE_HUDSCALE`, off by default) implements.

## What the engine gives us (facts)

- **Widget size is fixed per layout group, and the 1024 group is not bigger.** SIMUI `FUN_100270e5` fills the
  bar field table from three hard-coded groups keyed on the root width (`0x280` -> 640 group, `800` -> 800
  group, `> 0x320` -> 1024 group). The field heights are identical in the 800 and 1024 groups (rows `0x1a..0x2c`
  in both); the 1024 group only moves the fields further right (`0x16e`, `0x1e0`, `0x276` vs `0x90`, `0x102`,
  `0x198`) `[CONFIRMED @ SIMUI 0x100270e5]`. The side panel table builder writes a `0x24` x `0x24` (36x36)
  button cell before it looks at the height at all `[CONFIRMED @ SIMUI 0x1004cdcd]`. Measured at a real
  1024x768 start (sc3startsize run, RESIZABLE_WINDOW.md): side panel `[928 0 1024 610]` = 96 wide, minimap
  `[864 604 1024 768]` = 160x164, RCI `[823 680 864 768]` = 41x88. At 800x600 the same windows are 96 wide,
  160x164 and 41x88. So the stock game never scales its HUD, it only spreads it.
- **Each window paints into its parent's surface, top-level windows into the frame.** `FUN_1006d2d0` repaints a
  dirty window (vt+0x144) and its children (vt+0x148), then blits its own surface `+0x58` (source rect `+0x24`,
  dest rect `+0x90`) into `parent->vt[0x158]()`, or into the global target when the parent has none
  `[CONFIRMED @ SIMUI 0x1006d2d0]`. The blit lands in GZGraphicD `FUN_10014894`, which forwards the two rects
  to the surface object's `vt+0x2c` `[CONFIRMED @ GZGraphicD 0x10014894]`. Whether that path stretches when the
  rects differ in size is `[UNCERTAIN]` (not read).
- **A window surface is dropped when its size changes** (`FUN_1006d56c` keeps a surface only on an exact size
  match, `project-simui-window-model`). Art is fixed-size bitmaps from the IXF archives.
- **Hit-testing reads the DERIVED rect `+0x14..+0x20`, rebuilt from the LOCAL rect** by the root cascade
  (vt+0x14c / vt+0x168). Input arrives through the game window's wndproc in client coordinates.
- **The mod already owns the final present.** `rz_blt_hook` sees every ddraw `Blt`; the final present is the one
  whose dest covers the client. MENUBG already rewrites the frame there (locks the source surface, edits pixels)
  and shifts mouse coordinates in `rz_wndproc` to match what it drew. RCIFIX already re-composites a HUD
  window at present time. Both shipped and were verified.

## Options

### A. Magnify the HUD at present time, map input back (RECOMMENDED)

Leave the game's layout exactly as sc3resize builds it today (full-width bar, full-height side panel, minimap
and RCI docked bottom-right). At the final present, take each HUD window's rect from the composed frame and
draw it again enlarged by a factor `s`, **scaled about the client's bottom-right corner C = (cw, ch)**:
`dest = C + s * (rect - C)`, clipped to the client. Mouse messages that land on an enlarged HUD rect are mapped
back with the inverse `p = C + (q - C) / s` before the game sees them, so the game hit-tests its own native
widget. Everything else (the city view) is untouched and keeps the full window resolution.

Why the bottom-right corner works with no layout change:
- every HUD window touches the right or bottom edge, or sits inside one that does. Such a region is closed
  under "move towards C", which means its enlarged copy always COVERS the native copy. No native-size widget
  is left visible beside its enlarged twin;
- the parts that scaling pushes off screen are exactly the stretched filler: the left part of the full-width
  bar and the top part of the full-height panel. The controls are already slid to the right end of the bar
  and the bottom of the panel, so they stay on screen;
- one affine map for all of it, so the relative layout (panel on the minimap, RCI beside the console) is
  preserved and the input map is a single formula.

Largest useful factor: `s_max = min(cw / 800, ch / 600)`. At `s_max` the HUD fills the window in the limiting
dimension exactly as it fills an 800x600 window, and the bar's controls (600-px art + RCI + minimap) still fit.
At the owner's maximized virtual client 2048x1081 that is 1.8 (bar 101 px tall, panel 173 wide, minimap
288x295).

Cost: one present-time pass, about 300 lines in sc3resize.c, no new hooks. Per frame: lock the composed
frame, snapshot it, resample the HUD rects into it, present, restore the touched rows (the game reuses the
frame, so it must get back exactly what it drew). Snapshot + restore at 2048x1081x2 bytes is ~4.4 MB each way.

Risks:
1. **Transparent HUD edges carry the city.** The composed frame holds HUD and city mixed. Where a HUD window
   is colour-keyed (for example around the RCI gauge), the enlarged copy shows an enlarged bit of the city
   from the corner instead of the city underneath. Mitigation if it shows: source the HUD from the window's
   own surface with the magenta key (option B's pixel source), or mask with the city-only target `iso+0x74`.
2. **Scaling filter.** Nearest-neighbour is crisp at integer factors and uneven at 1.5 or 1.8. Bilinear is
   even but soft. Owner call (needs owner).
3. **Dialogs and tooltips stay native size.** They are drawn into the same frame. The prototype redraws
   visible dialogs on top of the enlarged HUD so a dialog is never covered or copied into it. A dialog that
   sits ON a native HUD rect would also be copied enlarged (needs a player drag to the very edge). Tooltips
   from enlarged buttons show native size near the native button.
4. **The game might read the cursor itself** (GetCursorPos) for hover or drag instead of the message
   coordinates. Then hover over an enlarged widget is wrong while clicks are right. MENUBG only needed the
   message shift for clicks. To be checked in the prototype.
5. **Partial presents.** A present smaller than the client would draw native pixels over the enlarged HUD.
   None were seen in city mode in the PRESENTLOG runs (the logger only prints full presents, so this is
   `[UNCERTAIN]`); the prototype logs any partial present it sees while active.
6. Drags that start on the HUD (minimap pan) and leave it: the prototype keeps mapping from button-down to
   button-up so the drag does not jump between the two coordinate systems.

### B. Per-window enlarged composite

Same idea as A, but instead of resampling the composed frame, redo each top-level HUD window's final blit
(`FUN_1006d2d0`: surface `+0x58`, src `+0x24`, dest `+0x90`) with an enlarged dest rect and the colour key.
Clean transparency (no city in the HUD). Costs: needs either a stretching path in GZGraphicD (`[UNCERTAIN]`,
`vt+0x2c` not read) or a CPU resample from the raw raster bits (`+0x44` sub, `+0xf0` bits, `+0xf4` pitch, as the
surface dumper does); must suppress the game's own native-size blit of the same windows; input mapping is the
same as A. Best as a refinement of A's pixel source if risk 1 shows, not as a separate design.

### C. Pick the 1024 widget group at large sizes

Rejected. The 1024 group uses the same art at the same size and only spreads it (facts above). It gives a
wider bar layout, not a bigger HUD. It would also undo the BAR800 fix (800 fields on 1024 positions).

### D. True per-widget scaling (art, rects, fonts)

Rejected for now. Every widget surface is a fixed-size bitmap; scaling means resampling every HUD bitmap at load
(IXF decoders), multiplying every LOCAL rect (and the cascade, the flyout anchors, the side-panel item anchors
`+0xa917c`, the 36x36 cells in `FUN_1004cdcd`), rebuilding every surface at the new size (`FUN_1006d56c` drops
mismatches), and rendering text at a bigger font size through the game's own font code. Weeks to months, many
classes, and every mod fix keyed on native rects would need a scaled twin. The visual result would be no better
than A with bilinear filtering, because the art is the same 800x600-era bitmaps either way.

### E. Render the whole game smaller and stretch the whole frame

Cheapest of all (the menu used to do this before MENUBG): run the game at `cw/s x ch/s` and stretch every
present. The HUD gets bigger, but so does the city, so a big window shows no more map than a small one. That
defeats the point of the resize mod. Listed only as the fallback "zoom" behaviour if the owner prefers it.

## Recommendation

Option A behind `SC3RESIZE_HUDSCALE`, off by default:
- `SC3RESIZE_HUDSCALE=1`: factor = `s_max = min(cw/800, ch/600)`, so the HUD keeps its 800x600 proportion;
- `SC3RESIZE_HUDSCALE=<n>` with n >= 100: factor n/100, capped at `s_max` (for example 150);
- `SC3RESIZE_HUDSCALE_FILTER=0` nearest (default), `=1` bilinear;
- only in a city (not at the menu, MENUBG owns that), only when `s > 1.01`.

Risk 1 did show (city in the minimap's transparent corner) and is solved with the city-layer mask, so option B
is not needed for it. `SC3RESIZE_HUDSCALE_KEY=0` turns the mask off for an A/B.

## Needs owner (all answered, owner 2026-10-14)

**Decided.** (1) and (2) were answered by the hudopt and hudfix rounds: the scale is picked in Preferencias
(Off / Fit / 125% / 150% / 200%) and Smooth is on by default (`[hud] smooth` missing = 1). Owner calls 2026-10-14:
(3) dialogs stay native size, (4) the bar keeps the full width and the panel the full height, and a fresh install
starts at Off. All three are what the code already does, so no code change. The questions as first asked:

1. Size: HUD at the largest factor that fits (`min(cw/800, ch/600)`, 1.8 at a maximized 2048x1081), or a fixed
   percent (for example 150), or whole steps only (2x and up, crisp, but 1x until the window is 1600x1200)?
2. Filter: nearest (crisp, uneven pixel widths at 1.5x to 1.8x, cheaper) or bilinear (even, soft, about 4 ms
   per frame at 1600x960)?
3. Dialogs (budget, meeting, query): keep them native size as now, or enlarge them too?
4. The full-width bar and full-height panel stay, the enlarged copy just pushes their filler off screen. Keep
   that, or stop the bar and panel at the enlarged controls?

## Prototype (phase 2), 2026-10-11

Code: `re/harness/src/sc3resize.c`, the HUDSCALE block just before `rz_blt_hook`, two calls inside
`rz_blt_hook` (before and after the original Blt of a full-client present), and the mouse map at the top of
`rz_wndproc`. Env: `SC3RESIZE_HUDSCALE` (unset or 0 = off, the shipped behaviour), `_FILTER`, `_KEY`.

Per final present (dest covers the client, source rect 1:1 with the client, city view up, MENUBG not active):
1. collect visible root windows and children of the HUD container `SC3U+0xd32d0`, skipping the city view
   (`SIMSPR+0x676ac`), full-client layers, and dialogs (`SIMUI+0xa4d64` >= 120x80, kept native);
2. edge-touching windows are enlarged about C; small floating windows (tooltips) too, when their enlarged copy
   fits on screen, and their native copy is overwritten with the city layer;
3. lock the frame, snapshot the touched rects, write each dest pixel from source `C + (d - C) / s`, using the
   city-only target `iso+0x74` as the see-through mask (a source pixel equal to the city layer shows the city
   at the dest instead), redraw dialog pixels on top, unlock;
4. original Blt; then lock again and restore the snapshot so the game gets its frame back.
Mouse: a queue message on an enlarged rect (or between a press there and its release) gets the inverse map.
A mouse message the game sends to itself while handling one is passed through unmapped.

### Results (instance `inst_hudscale`, Europolis copy, display awake at 100%, 1680x1050)

Evidence in `verify/hudscale/` (MAIN, gitignored), logs `sc3resize_key.log` / `_v3.log` / `_bil.log` there.

| Check | Result |
|---|---|
| Default off | control run with `SC3RESIZE_HUDSCALE=0`: 0 HUDSCALE log lines. Code default `g_hudscale = 0`. |
| 1200x900, auto | factor 1.5. Bar `[0 844 1200 900]` -> `[0 816 1200 900]`, panel `[1104 0 1200 742]` -> `[1056 0 1200 663]`, minimap `[1040 736 1200 900]` -> `[960 654 1200 900]`, RCI `[999 820 1040 900]` -> `[898 780 960 900]` (`02_nearest_1200x900.png`) |
| 1600x960, auto | factor 1.6 (`03`, `05`) |
| See-through mask | without it a magnified chunk of city sat in the minimap's transparent corner (`01_unmasked...`). With the `iso+0x74` mask the corner shows the city under it (`02`). |
| Clicks | enlarged transport button `(1545,145)` -> native `(1565,450)` opened the transport flyout, drawn enlarged (`07`); first flyout item -> road tool active, red preview and cost label in the city (`08`); minimap "+" `(1385,877)` -> native `(1465,908)` zoomed the city (`11`); meeting button opened "Reunirse" (`10`); the dialog's own close box (not enlarged) closed it. |
| Hover / tooltips | hover highlights the enlarged flyout item; the "Reunirse" tooltip is enlarged next to its button (`09`). |
| Dialogs | native size, centred, drawn over the enlarged HUD (`10`). |
| Cost (pre-present pass, 10-s windows) | nearest 0.65 to 2.2 ms per frame at 1200x900 and 1600x960 (masked); bilinear 3.95 to 4.78 ms at 1600x960. The game stayed at its ~50 to 60 fps cap in both. |
| Filter | nearest is crisp with uneven pixel widths at 1.5x/1.6x; bilinear is even and soft (`06_nearest_vs_bilinear_crop.png`). |

One glitch seen and not explained: in the first build, 2 of 3 clicks on the first transport flyout item opened
the EMERGENCY flyout instead. The emergency button is exactly where that item's native point lands if mapped a
second time, so a guard now leaves game-sent nested mouse messages unmapped. After it: 0 of 5 item clicks
misfired, and the guard logged no nested message, so the cause is `[UNCERTAIN]` (the first build differed only
in that guard and in not handling tooltips). Logged in the status file for the owner's hand test.

**Update 2026-10-11 (task hudopt, `OPTIONS_DIALOG.md` section 5):** the second mapping was measured. A mouse move
comes back through the QUEUE (not nested) about 15 ms later carrying the native point the mod produced, with the
same message time, and was mapped again (`(1100,332) -> (1120,446) -> (1120,537)`, the enlarged "Preferencias"
flyout icon hovered and clicked as "Guardar como"). Fixed with the REPOST guard (`SC3RESIZE_HUDSCALE_REPOST=0` to
disable). Also found there and NOT fixed: an open flyout during a window resize with the HUD enlarged leaves a
stale enlarged side panel.

Not yet checked: drag on the minimap (pan) starting on it and leaving it, right-click on the HUD, the terrain
editor / New City while enlarged, Load City while enlarged, 1024 maps with sc3bigcity, maximized at the owner's
2048x1081 (factor 1.8), live resize drags with HUDSCALE on, the main menu (excluded by design, MENUBG owns it).

Also seen: blits onto the presented surface with client-coordinate dests right after a resize (the bar fields
redrawn, `src` = the bar's field surfaces). They happen in the frame after a size change only and did not show
in any grab. Where they go is `[UNCERTAIN]`.

## Defects after the owner's hand test (task hudfix, 2026-10-11)

Owner report on the hudopt build: (1) smoothing should be on by default, (2) the minimap looks pixelated with
Suavizado on, (3) while the camera moves, city shows over the bars and around buttons. Code: the HUDFIX block in
`sc3resize.c` (`rz_hs_record`, `rz_hs_coverage`, `rz_hs_resolve`, `rz_hs_epx`, the HUDFIX resample loop in
`rz_hs_pre`). `SC3RESIZE_HUDFIX=0` restores the hudopt behaviour. A/B: `verify/hudfix/PRE.md`, `RESULTS.md`.

**Frame structure (measured, HSSEQ Blt dump, 1200x900).** Per frame the game Blts the city layer (iso+0x74's surface)
into a composite surface with dest `[0 0 cw ch]`, then each HUD window into the composite (bar tiles, bar fields,
side panel opaque with `DDBLT_WAIT`; minimap, RCI, corner widget and ticker with `DDBLT_KEYSRCOVERRIDE`, flags
`0x01010000`), then the composite into the primary (caps `0x1000E200`) at screen coordinates. The camera scroll is a
Blt of the city layer onto itself (`[0 3 1200 900]`). The hudopt code treated every Blt with a client-sized dest as
the present, so the enlarge pass ran twice per frame, once on the city -> composite Blt (a no-op with the mask).
No present was skipped by the pass (HSDIAG census: 0 skips in every 1-s window).

**(3) mechanism.** The see-through test was `snapshot pixel == city-layer pixel at the same spot`. An opaque HUD pixel
that happens to equal the city pixel under it passed as see-through and showed the city at the dest instead. While
the camera moves the city under the HUD changes every frame, so those pixels flicker: specks along the side-panel
button outlines, in the RCI's white columns, around the minimap buttons (`verify/hudfix/armA/heat_hud.png`). Second
source: bilinear taps at the outer edge of an enlarged rect read the snapshot just outside the native rect, which is
city from a different spot of the map, and that moved too (a 1-px line along the bar top and the panel's left edge).
Fix: every Blt onto the composite after the frame's city Blt is recorded (dest, source rect, flags, colour key); a
pixel covered by an opaque Blt, or by a keyed Blt whose source pixel is outside the key range, is HUD regardless of
colour. The equality test is kept only for pixels no recorded Blt covers (HUD drawn some other way, if any). Each tap
that is not HUD takes the city at the DEST pixel, so edges are blended with the city they sit on. Result: changed HUD
pixels during a scroll 3553 -> 0 (panel), 1385 -> 0 (bar + RCI), also 0 maximized.

**(2) mechanism.** The minimap does go through the bilinear path (in-process dump: 88 interpolated colours in a 40x40
block of the enlarged map). Its native picture is plain pixel data with hard stair-step edges and 1-px dots
(`verify/hudfix/dump3/mini_before_x3.png`), while the rest of the HUD is pre-anti-aliased art. Bilinear cannot remove
steps that are in the source, so at 125% to 150% the map reads as pixelated next to soft buttons. Fix: in smooth mode
the minimap window's source (class `SIMUI+0xaa180`) is doubled with Scale2x (EPX), softened with one `[1 2 1]` tent in
2x space using only HUD neighbours, and the bilinear tap reads that buffer. Chosen from five filters compared offline
(`verify/hudfix/minimap_filters_x2.png`): Scale2x alone barely changes the shallow isometric diagonals, a plain blur
loses the dots. The 2x buffer is rebuilt only when the minimap's snapshot or coverage changes.
`SC3RESIZE_HUDSCALE_MINISMOOTH=0` turns it off.

**(1)** `[hud] smooth` now defaults to 1 when the key is missing (no ini). An explicit `smooth=0` or
`SC3RESIZE_HUDSCALE_FILTER=0` still wins. `g_hs_filter`'s static default stays 0, so `SC3RESIZE_HUDOPT=0` (no ini read)
is unchanged.

Cost (B3 build): 3.9 to 4.1 ms per frame at 1200x900, 5.0 ms maximized (2048x1081), one pass per frame, ~82 fps,
same as hudopt (2.6 to 3.1 ms per pass, two passes per frame).

Owner's frame (black/white junk in the RCI columns) is the same mechanism and is reproduced by the control arm; the
fixed build also stays clean with the sim running at speed 4 (`verify/hudfix/RESULTS.md`, follow-up section).
A black 4-px line that scrolls through the city during scrolls shows with HUD scale off too, so it is not this code.

Not addressed here, seen in the logs: while the sim is paused the cluster re-assert runs SRCRECT + SIDEKIDS every
~125 ms (the game resets the bar's source rect to 600 and the panel buttons to native, the mod pushes them back). The
owner's `inst_hudopt` log has 963 such passes in 2 minutes after a maximize. No frame in the scroll runs showed a
layout change from it. Why the game resets them is `[UNCERTAIN]`.

## Cost of the enlarged HUD (task hudperf, 2026-10-12)

Owner report: "hay bajones de FPS cuando aumento el escalado, es proporcional a la cantidad de escalado". Owner log at
2560x1351: 11.23 ms per frame in the pre-present pass at 200%, 12.5 to 14.6 ms at Fit. Code: the HUDPERF and
LAZYRESTORE blocks in `sc3resize.c`. A/B: `verify/hudperf/PRE.md`, `RESULTS.md`.

**Where the time went (measured, Fit 2.252x, 2560x1351, round/1012 build).** Stage times per frame: snapshot 0.6 to 1.4 ms,
coverage 0.4 to 1.2, resolve 0.3 to 0.85, minimap 2x 0.03 to 1.56, and the rest of the 12 to 22 ms in the per-pixel
resample of every enlarged dest pixel (about 690,000 at Fit). The restore after the present was not in that number:
1.7 to 4.3 ms more, with no lock wait (the copy itself), 4.1 to 5.0 M thread cycles per frame. Both scale with the dest
area, so with s^2.

**What changed (all bit-identical to the hudfix pass):**
1. Cached resample. Each dest pixel is decided by the coverage of its source taps: all taps HUD (value from the snapshot
   or the minimap 2x buffer only), no tap HUD (the city at the dest), or mixed (edges of see-through parts). The first
   kind is kept per window in a dest-sized cache keyed by the window's class and rects. Each window keeps a copy of its
   snapshot and coverage over its source rect + 1 px; per frame only the changed native rows are found, and only the
   dest pixels whose taps can reach them (+-4 native px) are recomputed. Per dest row a run list: cached runs and city
   runs are memcpy'd, mixed pixels recomputed with the same arithmetic (`rz_hp_px`). Typical rebuild with the sim
   running: 10,000 to 20,000 px per frame (the scrolling news ticker, date, funds, RCI); while scrolling 40,000 to
   78,000 (the minimap's view frame); mixed pixels 3,700 per frame.
2. Lazy restore. Every frame the game first Blts its city layer over the whole composite (one client-sized Blt onto it
   per present: 313 of 313, 543 of 543, 771 of 771 frames), which overwrites everything the restore puts back. The
   restore is now owed and paid only if something touches that surface first: any other Blt or BltFast onto or from
   it, a Lock or GetDC of it, the next present. Hooks for BltFast/GetDC/Lock go on the shared ddraw vtable on top of
   sc3perf's (sc3perf's FPS overlay calls its saved Lock directly and must not pay it every frame). Measured: all owed
   restores cancelled in every window except one Fit hover window, 131 paid before a Blt onto the frame with dest
   `[0 0 800 599]` (what the game draws there is `[UNCERTAIN]`).
3. Coverage: an opaque recorded Blt sets 2 on its intersection with each HUD rect (inside a HUD rect the old "nonzero"
   test is always true), keyed Blts read 1:1 without a divide per pixel, resolve skips to cov 1 with memchr. Same values
   inside every HUD rect + 1 px, the only part anything reads (CHECK compares it every frame).
4. Snapshot and restore copy a native rect + 1 px only when it is not inside its own enlarged rect.

**Result (thread cycles per frame, pass + restore, the CPU was shared so wall clock is secondary):** round/1012 22.6 M at
125% rising to 37.1 M at Fit (static), HUDPERF 3.9 to 4.5 M at every scale (static), 8.4 to 11.8 M while scrolling.
29,209 frames compared in CHECK with 0 differing pixels.

**Opt-outs and diagnostics:** `SC3RESIZE_HUDPERF=0` (the hudfix pass, restore right after the present),
`SC3RESIZE_HUDPERF_LAZY=0` (cached pass, restore right after the present), `SC3RESIZE_HUDPERF_CHECK=1` (both passes every
frame, differing pixels counted, the hudfix result shows). Every 10 s, with HUD scale on: `HUDPERF> thread cycles per
frame`, the resample/restore split, rebuilt and mixed px, and the lazy-restore counters next to the existing
`ms per frame in the pre-present pass` line.

**Not explained:** one arm-B launch of ten at Fit showed a 7-row black line in the city about 53 px above the enlarged
bar for the whole run; 0 of 7 arm-A launches, 0 of 9 further arm-B launches (`verify/hudperf/RESULTS.md`).

**Also measured, not changed:** sc3perf's fps counts every client-sized Blt as a frame, and there are two per frame
(city layer -> composite, composite -> screen), so its overlay reads about twice the presents (93 shown vs 45/s).

## Clicks while a dialog is up (task hudclick, 2026-10-15)

Question from menuscale: its first build mapped only depth-0 mouse messages, and "Preferencias" at the main menu runs its
modal loop inside the button handler, so its clicks came at depth 1 and missed. HUDSCALE has the same depth-0 rule.
Measured in a city (N / Fit / 200%, `verify/hudclick/RESULTS.md`): no miss.
- Dialogs opened from the HUD (Preferencias, Presupuesto, Ordenanzas, Mapa de vecinos, Reunirse, Guardar ciudad, the
  Load save question, Salir) get every message at depth 0: the HUD click returns before the dialog opens. Only the query
  dialog (opened by a city click with the query tool) nests at depth 1.
- Dialogs are drawn native, so their clicks need no mapping at any depth. All dialog-control clicks hit in all arms.
- The modal loop is GZWIND `FUN_10020971` (window-manager vtable `0x1002db80` slot `+0xa0`), closed by
  `vt+0x44(0xd, win, id)` = `FUN_10020f08` `[CONFIRMED @ GZWIND 0x10020971, 0x10020f08]`; while it runs, the mouse
  dispatcher `FUN_10020818` drops clicks outside the dialog `[CONFIRMED @ GZWIND 0x10020818]`. Reunirse is not modal for
  the HUD in the stock game: the side panel works with it open, and with HUDSCALE too.
- `g_hs_capture` is set by a mapped press and cleared only by a release that reaches `rz_hs_mouse` (or the HUDOPT OK). A
  HUD control that opened a nested modal on the press would leave it set after the dialog. None does: every opener's
  release was logged at depth 0 and mapped.
Diag added: `SC3RESIZE_FRAMEDUMP=<prefix>` writes the presented frame to `<prefix><tag>.bmp` when `<prefix>req` exists
(tag = its first line). Needed because background desktop grabs of this game are black/white.

## Dialogs enlarged too (task dlgscale, 2026-10-20)

Owner, 2026-10-20: "the Reunirse popup is not scaled, neither any other menu". Design call the same day: scale dialogs
with the HUD factor, capped to fit. This supersedes decision (3) of 2026-10-14 (dialogs native). Code: the DLGSCALE
block in `sc3resize.c` (`rz_hd_add`, `rz_hd_ready`, `rz_hd_draw`, `rz_hd_mouse`), `SC3RESIZE_DLGSCALE=0` turns it off.

- Which: every visible `SIMUI+0xa4d64` root child >= 120x80 (the set kept native before), fully inside the client.
- Size and place: `sd = min(HUD factor, cw / w, ch / h)`, below 1.01 the dialog stays native. Centred on the native
  dialog, shifted inside the client. Where a shift leaves native pixels outside the enlarged copy they get the city layer.
- Pixels: the native dialog is copied before the HUD pass, enlarged after it, on top of everything. Per dialog window a
  cache of the enlarged image; per frame only the dest box whose taps reach the source pixels that changed since the
  last frame is recomputed (`(b, b + 1)` taps, nearest or bilinear as the HUD). The cache is keyed by size and filter,
  not position, so a drag costs nothing. The dest is snapshotted with the HUD rects and restored with them.
- Mouse: inside an enlarged dialog, at any depth, `native = nat0 + (q - dst0 + 0.5) * w / dw`. A message equal to the
  last mapped point within 500 ms (a move, or a button at depth > 0) is left as is, the MENUSCALE rule. A press keeps
  the release on its dialog. Once the dialog's native origin changes during a press (a title-bar drag) the cursor maps
  1:1 from the press point: the game moves a dialog by the native distance from the press, so a proportional map moved
  it 118 px for a 300 px drag at 5 fps; 1:1 moved it exactly (300, 200) for (300, 200).

Measured 2026-10-20, Europolis, 3840x1984 maximized, Fit 3.307x (`verify/dlgscale/RESULTS.md`): Reunirse 383x354 ->
1266x1170 (3.305x), Preferencias 480x472 -> 1587x1560, Indagar 423x320 -> 1398x1058. Clicks hit at depth 0 (advisor,
close box, checkbox), inside the Discutir dropdown's own loop at depth 1, and in the query dialog at depth 1. Pass cost
with Reunirse open 9.9 to 10.6 ms per frame against 6.2 to 6.4 without.

**The Reunirse frame-rate drop is not this code.** With the dialog open the game's Blts per second drop about 3.5x at
every size and with HUD scale off: 4,883 -> 1,373 at native 800x600, 1,070 -> 277 at 4K scale off, 891 -> 265 at 4K Fit;
time inside Blt drops too (809 -> 135 ms/s native). With sc3perf (`sysmem=1`) there is no drop: 60 fps open and closed; the dialog adds ~3,300 surface Locks per second, cheap in system memory, slow in video memory (`verify/dlgscale/RESULTS.md`).

## City cost label pulled up-left (task costlabel, 2026-10-22)

Owner report on the LAN build of main `4f780c5`, window 3840x1984 at 3.307x: "after placing some highway outside the
screen the price marking is offset a lot" (`verify/ownerbugs_1021/owner_shots/img14_cost_label_offset.png`).

- Cause: `rz_hs_collect` enlarged every small floating window inside the native HUD box (the bottom-right
  `cw/s x ch/s` region) about the corner C, a rule meant for HUD tooltips. The road/highway cost label (vt
  `exe+0xd3bcc`) is a floating window the game puts next to the cursor in the city. In that region it went to
  `C + s * (p - C)`. The owner's `resize.log` line 510: `[3678 1522 3742 1538] -> [3304 456 3516 509] (floating: native
  copy erased)` = 374 px left of and 1066 px above where the game put it. The same label outside the box is logged
  `not scaled (floating): 004D3BCC[...]` and sits at the cursor. Not stock, not TIPCURSOR, not overscroll. A drag that
  leaves the window only clamps the label into the client corner (stock), where the old rule moved it little.
- Fix: a floating window is enlarged only if the last queued mouse message was mapped by `rz_hs_mouse`, i.e. the
  game's cursor was on the enlarged HUD, so the game placed it next to the native point. Decided per window and rect
  (latched), so a HUD tooltip keeps its place if the cursor leaves before it hides. Log: `COSTLABEL> floating ...`.
  `SC3RESIZE_HUDSCALE_FLOATALL=1` restores the old rule.
- No class check: `exe+0xd3bcc` is the game's one tooltip window. The side panel, bottom bar and minimap button
  tooltips are that same window, moved (logged with their vtable, 2026-10-22). Excluding the class would stop every
  HUD tooltip from enlarging. Second test instead: the floating rect must also touch a native HUD window (8 px
  margin, the previous pass's edge-anchored rects). Every HUD tooltip measured overlaps one. Reason: with the real
  mouse parked on the panel of a maximized window, Windows sends moves at its position between posted ones, and the
  flag read "HUD" at the start of a city drag (`[2428 1178 2448 1194]` at 3840x1984). The second test refuses that.
- Check (client 1584x851, 1.418x, `verify/costlabel/RESULTS.md`): highway drag held in the box, label native at the
  cursor (before: enlarged, pulled up-left); top-left control unchanged; HUD button tooltip still enlarged beside its
  button.

## Auto by default, cost label at the HUD scale (task uiscale, 2026-10-22)

Owner, on the LAN build of main `2564a08`: "auto-apply scaling according to the resolution of the computer, always leave
it by default auto adjust on the options" and "price tag is hiding under the cursor and it's not scaling with the rest of
the screen" (`verify/ownerbugs_1021/owner_shots/img17_price_tag_cursor.png`). This supersedes the 2026-10-14 call "a fresh
install starts at Off".

- Default: `[hud] scale` missing = 1, shown as "Auto" and listed first (the old Fit, same id and value, factor
  `min(cw/800, ch/600)` per present). An ini written before this build (no `ver` key) with `scale=0` is read as Auto once,
  since 0 was the old default and OK rewrote it unchanged. Saves write `ver=2`, so a later Normal persists.
- Cost label: when the COSTLABEL rule keeps the floating tooltip window (vt exe+0xd3bcc) native because the cursor is in
  the city, it is now drawn enlarged by the HUD factor in a DLGSCALE slot flagged `lbl` (no mouse mapping), placed from
  the cursor point that the TIPCURSOR stubs record at SIMSPR 0x1004a475 / 0x1004a4d5 (`g_tip_mx/my`): centred under the
  pointer box, top at `clearance + 2 + 2s` below the hotspot, clearance = max(pointer, CursorBaseSize x dpi / 96) in game
  px. It moves left of an enlarged HUD window it would cover, then above the hotspot. HUD tooltips are unchanged.
  `SC3RESIZE_COSTLABEL_SCALE=0` = native.
- Measured (`verify/uiscale/RESULTS.md`): 1.5x at 1600x900 and 3.307x at 3840x1984, at the centre, the bar, the side panel,
  the minimap corner and top-left: every decision logged `below the pointer` or `above the hotspot`.
- `[UNCERTAIN]` drawn pointer size at (base 32, dpi 240): `SM_CYCURSOR` reads 64, and the clearance uses 80.

## Minimap drawn by the game at the HUD factor (task minimap, 2026-10-23)

Owner report: the enlarged minimap looks pixelated and blurry. Code: the MININAT block in `sc3resize.c`,
`SC3RESIZE_MINIMAP_NATIVE=0` turns it off. Evidence and pictures: `verify/minimap/RESULTS.md`.

- The map is a SIMUI map-view child of the minimap (factory id `0x5a9`, ctor `FUN_10042866`, vt `0x100a7e68`), 129x129 at
  `(14,15)` `[CONFIRMED @ SIMUI 0x10050de2]`. Draw (vt+0x144 `FUN_10043937`) blits a square texture rotated into the
  diamond. Texture side = `width * 0.70710677` quantised to 32/64/128/256 `[CONFIRMED @ SIMUI 0x100436b4]`, so 128 natively.
- The map view renders at any size by itself: a new rect sets `+0xdd`, the next Draw rebuilds texture and corners. The game
  can clone it (iface vt+0x10 `FUN_10042aec`: layer list `+0xf0`, overlays `+0xf4` incl. the view box, rotation `+0xac`),
  and any GZ window can own a raster of its rect size (vt+0x170 `FUN_1006d56c`).
- So with s > 1 a clone sized `2*round(64 s)+1` with its own raster is drawn each time the native one draws, and the pass
  copies it 1:1 over the enlarged map where the frame's native pixel is still the map's own (buttons over the map keep
  the enlarged copy). Cost at 2.187x: 0.14 ms per frame compose, 0.35 to 0.47 ms per twin draw.
- The minimap survives a city load: it drops its map view on message `0x311fdae5` and rebuilds it on `0x511fdae5` /
  `0x45462fd2` (vt+0xc `FUN_100507ad`). The twin is freed there, before the old city's layers go.
- The stock minimap does not follow the city data view (Capas, Vista de capas: Crimen), with or without this change.

## UI audit fixes (task uiaudit, 2026-10-25)

Audit of every UI element with HUD scale Auto at 3840x1984 (3.307x) and 2560x1351 (2.252x): `verify/uiaudit/RESULTS.md`.
Owner picked four fixes, each a block in `sc3resize.c` with an off switch:

- **TIPDLG** (`SC3RESIZE_TIPDLG=0`): a tooltip of a dialog control (Reunirse advisor names) was drawn twice. A cursor on an
  enlarged dialog is mapped by DLGSCALE, not `rz_hs_mouse`, so COSTLABEL took the tooltip (vt `exe+0xd3bcc`, the cost
  label's class) for a city cost label and drew it at the stale TIPCURSOR point, while the dialog's own enlarged copy
  showed the native tooltip clipped at the dialog edge. Now the wndproc records that the last mouse message landed on an
  enlarged dialog (`g_hs_mouse_dlg`); such a tooltip is decided after the collect loop and enlarged with the dialog it
  overlaps most (dest = dialog dest + (r - dialog native) x dialog scale), in a `lbl` slot (drawn last, no mouse). Log
  `TIPDLG>`. A tooltip that overlaps no dialog keeps the COSTLABEL path.
- **MINIVIS** (`SC3RESIZE_MINIVIS=0`): with the UI hidden the MININAT twin stayed on the city. `rz_hs_collect` skips the
  hidden minimap before it records `g_mn_mini`, so `mn_compose` kept composing the twin against a snapshot rect no pass
  refreshed. The twin is now composed only when the minimap was collected visible in this pass (`g_mn_seen`).
- **DLGONLY** (`SC3RESIZE_DLGONLY=0`): in the terrain editor the only window is its 172x480 panel (a dialog), so the pass
  stopped at `n <= 0`: the panel stayed native although HSCENSUS logged "dialog enlarged", and `sc3resize_ui_scale()`
  returned 100, so sc3perf's FPS/profiler text was native. The pass now runs when a dialog is enlarged with no HUD window,
  and the export reports the factor while a dialog is enlarged. The panel is enlarged like any dialog (2560: `[2388 435
  2560 915] -> [2173 135 2560 1215]`); its clicks map (Aceptar este Terreno hit).
- **MSOPEN** (`SC3RESIZE_MENUSCALE_OPEN=0`): specks of `menu_bg.bmp` inside the scaled Load City list. A list pixel equal
  to the stock background at the same spot was classed background. MENUSCALE's compose now reads the 3x3 morphological
  opening of the mask (a pixel stays background only inside some all-background 3x3 square; outside the frame counts as
  background). Measured A/B at 2560: 81 client pixels differ between the arms, all in the dialog, 0 on the menu picture.

## Ver datos data maps drawn by the game at the dialog factor (task verdatos, 2026-10-25)

Owner request: the Ver datos maps (aura, crime, pollution...) drawn natively at the HUD scale, not upscaled, as the
minimap is. Code: the VERDATOS block in `sc3resize.c`, `SC3RESIZE_VERDATOS_NATIVE=0` turns it off. Evidence and pictures:
`verify/verdatos/RESULTS.md`.

- The dialog is the generic SIMUI+0xa4d64 class (container ctor `FUN_10044021`, 424x440). It holds one panel per data
  view (ids 0x5fa..0x603, made in `FUN_10044430`), each with its own map view (vt `0x100a7e68`, 379x379 at panel-local
  (2,6), made once in `FUN_10045df2`) `[CONFIRMED @ SIMUI 0x10044aa6]`: a view switch hides one panel and shows another, so
  the map view object that draws changes, and the deactivated one drops its texture (`FUN_10042ca4` -> `FUN_1004367e`).
  The layers come from the sim DLLs over the SIMDIRT base layer 0x2711. The map takes no clicks (view+0xd0 stays 0; a
  posted click moved nothing). It follows the city rotation (minimap rotate buttons); the compass only shows it.
- Unlike the minimap's, this view has no raster of its own: it draws into the client-sized UI composite (GZGraphicD
  raster vt +0x1f328) at client coordinates `[MEASURED live: rect [1060 473 1439 852] in dialog [1020 427 1444 867]]`, and
  the legend, compass and option boxes are sibling windows drawn after it. The legend box overlaps the diamond.
- Twin: the same Clone as MININAT, sized `2*round(189 x dialog factor)+1` with its own raster, drawn after the native
  view drew, but only when the native view's pixels (read back from the composite), its state or the factor changed. A
  still view redraws about 16 times a second with identical pixels, so the twin draws once per open, view switch,
  rotation or data refresh (about every 20 s with the sim running).
- The twin's texture goes past the game's 256 cap: the layers fill any texture per texel from their cell grid
  (`cx = W*tx/rectW`, inner layer +0x10/+0x14, reached through the wrapper vt 0x100a811c +8), so the side is the game's
  rule (smallest power of 2 at or above the diamond side) capped at twice the city's cells: 512 for a 256-cell city,
  1024 for a 1024-cell city. `SC3RESIZE_VERDATOS_TEX=<side>` caps it (256 = the game's cap). `this+0xe0` (texture scale)
  is a float `[CONFIRMED @ SIMUI 0x10043765 fstp]`.
- Paste: in DLGSCALE's draw loop right after `rz_hd_draw` for that dialog (dialogs in front and labels still cover it),
  where the twin drew and the frame's native pixel is still the view's own, as row runs in slot-local coordinates. The
  runs go into the slot's enlarged cache too, so a still or dragged dialog only pays one compare of the map rect
  (0.23 to 0.42 ms per frame measured); when the runs change, the slot is rebuilt from its native pixels the next frame.
- Lifetime: the dialog destroys its map views on close (measured: the view's vt+0x28 Shutdown runs), which frees the
  twin first; also freed on a view switch, a rotation, and after 1 s unused.
- It takes any map view inside an enlarged dialog, not only Ver datos. Only Ver datos was checked.
- Cost per texture side, Europolis 1024: twin draw 44 to 101 ms (256), 81 to 120 ms (512), 172 to 366 ms (1024); per frame
  0.27 to 0.72 ms whatever the side. 256 drops whole road rings on a 1024-cell city, 512 breaks them, 1024 keeps them.

## Dialog subclasses and dialogs in front of dialogs (child newcitydlg, 2026-10-26)

- "Is it a dialog" was `vt == SIMUI+0xa4d64`. That is the vt the dialog base ctor `FUN_1002c688` writes, and 16 SIMUI
  classes overwrite it after calling that ctor. Direct subclasses (ctor -> vt): `0x100305fe` -> `0x100a5120`,
  `0x10030b8c` -> `0x100a53ac`, `0x10031dde` -> `0x100a5604`, `0x100385c5` -> `0x100a6544`, `0x10039504` -> `0x100a67d0`,
  `0x1003a0c0` -> `0x100a6a68`, `0x1003c494` -> `0x100a6ce8`, `0x1003ccc0` -> `0x100a6f84`, `0x1003de05` -> `0x100a71f0`,
  `0x1003e042` -> `0x100a7468`, `0x1003eefa` -> `0x100a76fc`, `0x1003f6d0` -> `0x100a7988`, `0x1005b6f4` -> `0x100aa8e8`
  (the in-city New City options, 639x389). Under `0x10031dde`: `0x100359fe` -> `0x100a58b8`, `0x10036753` -> `0x100a5c5c`,
  `0x100379e0` -> `0x100a61d4` `[CONFIRMED @ each ctor]`. New City was therefore taken for a floating window and left
  native ("floating, NOT SCALED"), and the placement poll never centred it (it opened at [32 76]).
- The other 15 are the Internet Chat client (GZCOM factories registered in SIMUI `FUN_1006a964`; "Chat Settings",
  "Create a Room", "Send a Private Message", "Friends", "All Users", "Room Properties", "Receive Snapshot?", the
  transfer progress window, the room views, a text prompt). Nothing can open them: the entry is the "Internet chat"
  cheat, which calls the chat manager's vt (`SC3U 0x4d0a70`, ctor `FUN_004187ab`) slot +0x54 = `FUN_0041c988`, 3 bytes,
  `return 0` `[CONFIRMED @ 0x00418c71, 0x0041c988]`. Measured: the cheat box (`SC3U+0xd12d0`, Ctrl+Alt+Shift+C) takes the
  text and closes, no window. DLGCLASS (`rz_is_dlg_vt`, `SC3RESIZE_DLGCLASS=0` off) therefore adds New City only, in
  DLGSCALE, `rz_dialogs_poll` and the two HUD-translation exclusions. Per-class table: `verify/newcitydlg/RESULTS.md`.
- Each enlarged dialog is resampled from its native rect in the frame, and that rect also holds what the game drew in
  front of it. A dialog in front whose native rect overlaps it therefore showed up a second time, magnified inside the
  back dialog's box at the back dialog's factor and offset. That is the owner's "New City cropped to the map dialog" when
  New City stayed native, and it is a thin ghost strip when both are enlarged but their clamped dests do not line up.
  DLGOCC (`SC3RESIZE_DLGOCC=0` off): where an earlier dialog in the pass list (the root list is front-first) overlaps a
  dialog's native rect, that dialog's snapshot keeps its own pixels from the last frame. A dialog's first frame takes the
  frame as it is. A dialog kept native in front of enlarged ones (dragged partly off the client) is treated the same way:
  the enlarged dialogs behind freeze where it overlaps, its native pixels are saved before the enlarged pass and put
  back right after the last enlarged dialog behind it, and the mouse on it stays native (`g_hd_nfr` / `g_hd_nfz`).
- Preferencias is modal: a click on Ver datos' X while it is open does nothing, so that pair closes front first only.
- The cheat box (`SC3U+0xd12d0` 312x28 at [0 0]) stays native under the sc3perf FPS line. It does not open while Ver datos
  is up, and Ver datos does not open while it is up, so it never sits in front of an enlarged dialog.

## Scrolling with Ver datos open (child vdscroll, 2026-10-26)

Owner: "when trying to scroll the camera while the map details menu is open fps drop substantially". Detail and
numbers: `verify/vdscroll/RESULTS.md`.

- While the camera moves the game sets the data map view's dirty byte (view+0xdc) in bursts about 100 ms apart. With
  the camera still it sets it 0 to 2 times per 10 s. Many of those draws change 0 native pixels. VERDATOS redrew its
  twin on each one: 30 ms on a 256-cell city (texture 512), 230 to 420 ms on Europolis 1024 (texture 1024). Each new
  twin rebuilt the paste runs, and a rebuild dropped DLGSCALE's cache, so the whole 954x990 dialog was resampled the
  next frame.
- VDSCROLL (`SC3RESIZE_VDSCROLL=0` off) changes this:
  - The twin is redrawn only when the native view's pixels differ from the ones it was drawn over. The dirty byte alone
    does nothing, except once the twin is older than 20 s (`SC3RESIZE_VDSCROLL_MAXAGE`), for data changes finer than a
    native pixel on a 1024-cell city.
  - With the camera still, that redraw is immediate (the monthly data refresh).
  - While the iso view origin (`bridge+0x18` -> `+0x54/+0x58`) moved within the last 1 s (`SC3RESIZE_VDSCROLL_SETTLE`),
    the redraw waits for the camera to stop. Meanwhile the compose's equality mask shows the resampled native pixel
    wherever the data changed.
  - Open, view switch, rotation and factor changes redraw at once, as before.
  - A run rebuild from native pixels alone is pasted inside the box `rz_hd_draw` just resampled.
  - A new twin whose runs cover the old ones (`vd_runs_cover`) keeps the cache.
- Fixed cost per frame with one enlarged 424x440 dialog (new `DLGSCALE>` 10 s line): prep (dest snapshot for the
  restore, native copy) plus draw (diff, full cache copy to the frame). That is two to three 1.9 MB copies, 3.5 to
  6 ms per frame measured on a PC where a plain 1.9 MB memcpy took 1.3 ms (3 to 9 other games running). Not changed.
- `SC3RESIZE_DIAG_ARROWS=1` (test only): GZWIND's `GetAsyncKeyState` import reports the arrow named by a posted
  `WM_APP+0x5D0` as held, so benches scroll with posted keys and no Frida. `WM_APP+0x5D1` (wParam 0/1) sets VDSCROLL in
  game for A/B. Bench: `re/tools/vdscroll_bench.py`.
