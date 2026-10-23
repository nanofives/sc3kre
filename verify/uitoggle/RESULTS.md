# uitoggle: hide / unhide UI freeze (owner 2026-10-23)

Owner report: "hiding / unhiding UI has a major delay / freeze on the game".

Test tree `Simcity_stock_uitoggle` (the LAN build), all 7 mods built from `child/uitoggle`, `Cities\Europolis.sc3`,
windowed and maximized on this PC: client 3840x1984, HUD scale Auto = 3.307x. The control is the game's hide-UI
button, the "_" at the minimap's bottom-right corner (native rect `[3814 1958 3840 1984]`). It hides the bar, the side
panel and the minimap, and a second press shows them again.

## Cause

| step | what the log shows (run 1, before the fix) |
|---|---|
| hide | nothing from sc3resize, max frame 33 ms |
| unhide | `RZ   city HUD became visible - layout will run again once ready` |
| | `RZ   DEFER: resize to 3840x1984 held - only 0 ms since bridge capture (< 3000)` |
| | `HOLD> presents held until the layout pass runs` |
| +3.0 s | full viewport routine (surfaces re-created, 44883-cell re-show, 18 ms), then the layout logs "already docked" for bar, side panel and HUD art |
| +3.09 s | `HOLD> released after 180 held present(s)` |

`rz_poll`'s "city HUD became visible" block (side panel `+0xa0` bit 0 going 0 -> 1, written 2026-10-07 for "accept
terrain") reset `g_bridge_fresh` and `g_bridge_ms`. That made every unhide look like a new city: the 3000 ms readiness
gate, with the present HOLD keeping the last frame on screen the whole time. The picture froze for 3 s.

Placing the cost, control run with `SC3RESIZE_HUDSCALE=0 SC3RESIZE_UITOGGLE=0`: `HOLD> released after 178 held
present(s)`, 3.1 s. So the cost does not come from HUD scale. The HOLD fires at any client size other than 800x600.

## Fix (`sc3resize.c`, block UITOGGLE, off switch `SC3RESIZE_UITOGGLE=0`)

After each layout pass, the block records the side panel's visibility, whether the pass was for a fresh city, the
bridge, the pass size and the client size. When the HUD becomes visible again:

- if the last pass ran on this bridge, at this client size, with the HUD visible, there is no re-layout. The windows
  kept their rects while they were hidden.
- if the last pass was a real resize done while the HUD was hidden, the layout runs on the next poll with no
  readiness wait.
- in every other case (accept terrain, where the fresh city's pass ran with the HUD hidden, or no pass recorded), the
  old path runs unchanged.

There was a second defect, found while testing the skip. On unhide the game resets the iso view's present list
`iso+0x4d0` to its map-area rect, `{0,0,3744,1928}` at 3840x1984 (read live with ReadProcessMemory). The city layer
then reached the composite through a Blt smaller than the client, so HUDFIX's record list never restarted, and after
that every frame used the equality fallback: 0 recorded Blts used, fps 60 -> 30 (run 2). For 1 s after a skipped
re-layout, the block puts back the pass's step-9 rect `{0,0,w,h}`. The full pass already did this as its step 9.

## Check (run 3, fixed build)

| case | log | frames |
|---|---|---|
| A: hide, unhide at the same size | `UITOGGLE> HUD shown again ... no re-layout`, then `present list ... [0 0 3744 1928] - erase then push {0,0,3840,1984}`. No HOLD | fps 59-61 after, max frame 34-74 ms. HUDFIX 0 fallback frames in the next 10 s windows |
| B: hide, restore to 800x600, maximize (two passes while hidden), unhide | `UITOGGLE> HUD shown ... layout runs now, no readiness wait`, pass 18.9 ms, `HOLD> released after 1 held present(s)` | fps 59-60 after, 0 fallback frames |

Pictures (frame dumps, `MAIN\verify\uitoggle\owner_shots\`):
- `1_hidden_3840x1984.png`: UI hidden, only the corner button left
- `2_unhidden_same_size_no_relayout.png`: case A, same layout as before the hide (compared with the pre-hide dump of run 1)
- `3_unhidden_after_resize_while_hidden.png`: case B

## Orchestrator's checks (runs 5 to 7, fixed build unless noted)

Timing method: `unhide_fd.py` clicks unhide, writes a FRAMEDUMP request 0.5 s later, and reports when the game served
it. While HOLD is on, nothing is presented, so a late serve means a frozen picture.

| check | log | result |
|---|---|---|
| before the fix (`SC3RESIZE_UITOGGLE=0`), Europolis maximized | `city HUD became visible`, `DEFER`, `HOLD> released after 88 held present(s)` | dump served at **+4.32 s** (88 presents held, because the PC was loaded by two other children's games) |
| after the fix, same city and size | `UITOGGLE> HUD shown again ... no re-layout`, present list put back. No HOLD | dump served at **+0.55 s**. 0 held presents |
| hide -> resize to 2133x1130 (owner size class, HUD 1.883x) -> unhide | `UITOGGLE> ... layout runs now, no readiness wait`, pass 2.8 ms, `HOLD> released after 1 held present(s)` | laid out correctly at once, served at +0.55 s |
| hide -> maximize, restore, maximize, restore, maximize (5 passes while hidden) -> unhide | same branch, pass 66 ms, 1 held present | laid out correctly, served at +1.52 s. The PC was overloaded at that moment: 2 to 25 fps from 300 s on, while the UI was still hidden, and the HUD resample (fixed CPU work) took 42 ms per frame instead of 3 to 5. Another child's game was using about 4 cores. HUDFIX 0 fallback frames |
| accept terrain (New City, Miniatura, maximized) | `city HUD became visible`, `DEFER ... (< 3000)`, `HOLD> released after 181 held present(s)`. No UITOGGLE line | old path unchanged with its gate. City HUD laid out correctly |

Pictures added to `MAIN\verify\uitoggle\owner_shots\`: `4_before_fix_unhide_served_at_4.32s.png`,
`5_after_fix_unhide_served_at_0.55s.png`, `6_accept_terrain_old_path_with_gate.png`,
`7_unhide_2133x1130_after_resize_while_hidden.png`, `8_unhide_max_after_max_restore_cycles.png`. Frames 4 and 5 look the
same, because a still picture cannot show a freeze. The serve times are the difference.

Not tested: city zoom x2 / x3 while toggling (the block records the pass size separately from the client size for that
case), and the owner's dpi 120 (here 2133x1130 is the same client size, at a different DPI).
