# PRE: left click on the map centres on the visible map area (`SC3RESIZE_LCENTER`)

Written 2026-10-12, committed before the fix run. Task `leftclick`, branch `child/leftclick`.

## Owner report

"arreglar el click izquierdo en el mapa para desplazarse, no se adapta a la ventana resizeable"
(the left click on the map that moves the view does not adapt to the resizable window).

## Inventory of the left-click camera paths (measured before this file, game PID 39536, Europolis 256)

Instrument: `re/tools/leftclick_trace.py` (read-only Frida). It hooks `CenterOnTile` and `Translate` and
reports, after each `CenterOnTile`, where the centred tile ended up on screen ("landed" = tile -> world through
`SIMSPR FUN_1000a513` minus the new camera origin).

| left-click action | camera call | caller (return address) |
|---|---|---|
| click on the map, default tool | `CenterOnTile` | `SIMSPR+0x435b0` (in `FUN_10043540`, outer view vt+0x20) |
| left-drag on the map, default tool | one `CenterOnTile` on the press, no pan | same |
| click on the minimap | `CenterOnTile` | `SIMUI+0x5090c` |

No left-click path calls `Translate`. So one function carries every left-click camera move.

## Cause (static + measured)

`SIMSPR FUN_1001d039` = `cISC3CityViewIso` vtable `0x10063390` slot `+0x54` (the pointer sits at
`0x100633e4`) = CenterOnTile(tx, ty, flag). It stores the tile in `+0xb0/+0xb4`, converts it to world
(`FUN_1000a513`), subtracts `+0x20 >> 1` and `+0x24 >> 1` (`0x1001d09c..0x1001d0b4`) and sets the origin
through camera vt+0x30 `[CONFIRMED @ SIMSPR 0x1001d09c]`. `+0x20/+0x24` is the view's stored size, 704x544
(800x600 minus the 96 px side panel and 56 px bar), never changed by the resize mod (read live: 704x544 at
800x600 and at 1680x979). So the tile always lands at view point (352, 272).

Measured at 800x600: clicking (352, 272) moved the origin (-16, -4), i.e. stock centres there.
Measured maximized at 1680x979 (map area `[0 0 1584 923]` from the live side panel `SIMUI+0xa9834` at
x 1584 and bar `SIMUI+0xa40ec` at y 923, centre (792, 461)): a click at (792, 461) moved the origin
(+448, +192) and the tile landed at (352, 272). A click at (1400, 800) moved it (+1056, +528), landed (352, 272).

## Change

`LCENTER` block in `sc3resize.c`: a 5-byte jump at `SIMSPR 0x1001d09c` (25 stolen bytes, checked against the
shipped bytes first, all-or-nothing) to a stub that subtracts HALF THE VISIBLE MAP AREA instead of half the
stored size. Visible map area: right edge = the live side panel's left edge when it is docked in the right half,
bottom = the live bar's top when it is in the bottom half; otherwise stored size + (client - 800x600), the rule
`sc3overscroll` true_center uses. With HUDSCALE active the docked HUD is drawn enlarged about the bottom-right
corner by `s`, so the edges become `cw - s*(cw - x)`, `ch - s*(ch - y)`. At 800x600 the area is 704x544, the
stock numbers. `SC3RESIZE_LCENTER=0` leaves the function untouched (control arm).

## Run

This machine, single 1680x1050 display at 100%. Instance `re/harness/inst_leftclick`, Europolis copy, all
mods from combo plus the rebuilt `sc3resize.dll`. Display asleep at writing time: visual rows run if the
display is awake, else are recorded "pending, display asleep" and do not decide the verdict.

Arm T: `LCENTER` unset (read back `lcenter=1` in `FLAGS>`/the install line). Arm C: `SC3RESIZE_LCENTER=0`.
Then arm S: arm T's DLL on the stock install `Simcity_stock` (stock SIMSPR, sha `eec71500…`).

| # | observable | instrument | T predicted | C predicted |
|---|---|---|---|---|
| 1 | install line | log | `LCENTER` installed at SIMSPR+0x1d09c | `LCENTER: disabled` |
| 2 | 800x600: click (352,272) and (200,200): landed | trace | (352, 272) +-1 both | (352, 272) +-1 both |
| 3 | maximized 1680x979: click (792,461): landed / origin shift | trace | landed (792, 461) +-1, shift within +-32 px each axis (tile snap) | landed (352, 272), shift ~(+440, +189) |
| 4 | maximized: click (1400,800): landed / shift | trace | landed (792, 461), shift ~(+608, +339) +-32 | landed (352, 272), shift ~(+1048, +528) |
| 5 | maximized: minimap click | trace | landed (792, 461) +-1 | landed (352, 272) |
| 6 | restored to 800x600 after maximize: click (352,272) | trace | landed (352, 272) +-1 | n/a |
| 7 | arm S (stock install, T DLL), maximized: rows 3 and 5 | trace | as T | n/a |
| 8 | frames (if display awake): the clicked spot is at the map-area centre after the click | grab, by eye | yes | no (up-left) |

PASS: rows 1-7 as predicted in T and S, and C rows 1-5 as predicted (the control reproduces the defect).
VOID: a modal dialog up, `lcenter` not read back, scaling not 100%.

## Not covered

Zoom and rotate (`FUN_1001d1d9`) re-centre on the stored centre tile `+0xb0/+0xb4` through camera vt+0x38/+0x48,
which centre on the camera's own rect `+0x64..+0x70` (the FULL client, 1680x979 read live), not on 704x544. That
is a separate mechanic (buttons and keys, not a click on the map). It is measured informatively in RESULTS, not
changed here.
