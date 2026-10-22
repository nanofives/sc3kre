# RESULTS: zoom steps x2 / x3 past the closest zoom (task cityzoom, 2026-10-22)

Owner go 2026-10-22: route A, steps x2 and x3, Auto default, filter follows the HUD smooth setting. Design and code
map: worktree `Simcity_wt_cityzoom` (branch child/cityzoom) `re/analysis/CITY_ZOOM.md`. Light testing (owner rule).

Setup: tree `Simcity_stock_hwlight`, instance `re\harness\inst_cityzoom`, all 8 mods built from the worktree,
`euro.sc3` (copy of Europolis), 3840x1984 maximized on the 3840x2160 TV, HUD scale Auto (3.307x), smooth on unless
noted, sim paused unless noted. Frames are sc3resize FRAMEDUMP of the presented frame (`owner_shots/`).

| # | check | result | frame |
|---|---|---|---|
| 1 | stock zoom 4 at x1 with the new code | unchanged picture, 60 fps shown | `01` |
| 2 | + at zoom 4 | x2: view 1920x992, frame stays 3840x1984, HUD intact, centre kept | `02` |
| 3 | + again / + at x3 | x3: view 1280x662; a third + does nothing (stock at the last step) | `03` |
| 4 | - from x3, x2, x1 | x2, x1, then the game's zoom 3; the same world point stays at the map-area centre each step | `10` |
| 5 | minimap view box | shrinks to 1/2 and 1/3; the minimap's see-through corner shows the stretched city | `11` |
| 6 | left click in the city at x2 (2600,500) | mapped to view (1300,250); LCENTER centres that tile on the map area 1761x899 | `12` |
| 7 | road tool drag at x2 | drag preview follows the cursor; cost label (HUD factor) below the pointer at the cursor | `07`, `13` |
| 8 | HUD scale Normal (env), x2, road drag | the game's own label at the cursor (anchor scaled in TIPCURSOR); native HUD button click not remapped, flyout opens | `06` |
| 9 | Preferencias | "Zoom extra" box right of "Suavizado", ticked; untick + OK writes `[view] zoomextra=0`, + stops at zoom 4 | `08`, `14` |
| 10 | restore the window at x2 | 800x600 drops to x1; maximize again stays x1 | - |
| 11 | rotate (PageDown) at x2 | rotated view renders, ZOOMCENTER keeps tile (147,127) on the 1761x899 map area | `09` |
| 12 | sim running, nearest, x2 then x3, 30 s each | 59 to 60 presents/s (cap), dates advance, 0 faults past the startup `0xC0000096` | `04`, `05` |

Cost per frame (10-s log lines):

| arm | presents/s | stretch | HUD pass |
|---|---|---|---|
| stock zoom 4 (plan run, two other games on the PC) | 16 to 25 | game Blt 9.2 to 15.2 ms | 9.8 to 17.9 ms |
| x2 smooth, 1 thread (first build) | 27 to 29 | 9.9 to 10.6 ms | 7.6 to 8.2 ms |
| x2 smooth, 4 threads | 45 to 54 | 3.3 to 4.4 ms | 5.8 to 7.1 ms |
| x2 nearest, sim running | 59 to 60 | 2.3 ms | 3.6 ms |
| x3 nearest, sim running | 60 | 2.2 ms | 3.6 to 3.8 ms |

Builds that did not count:
- run2 (first): the stretch went into the render target -> device surface Blt and the frame (iso+0x4ec) was view-sized:
  black frames. Cause: iso+0x4ec is the frame composite; fixed by keeping it client-sized (`rz_do_resize` step 6).
- run3 / run4: one stretch per frame too many (the RCI repaint's nested Blt inherited the flag). Fixed: the flag is
  consumed by the first Blt from the render target. run5 on: stretches = rewritten Blts = frames.

Not run: save / load while magnified (a new city starts at x1 by design), terrain editor, a second monitor, the
GZWIND GetCursorPos reader (`FUN_10020260`, not mapped; nothing followed the wrong point in these checks).
