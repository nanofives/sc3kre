# PRE: zoom and rotate keep the map-area centre tile (`SC3RESIZE_ZOOMCENTER`)

Written 2026-10-12, committed before the formal arms. Owner design call (via the orchestrator): zoom centres on the
same map-area centre the LCENTER click uses (left of the side panel, above the bottom bar), not the whole window.

## Mechanism (static)

Zoom (numpad +/-, hotkey cmds 41/42) and rotate (PageDown/PageUp, cmds 43/44, identified by the exploratory run below)
go through the iso view's `SIMSPR FUN_1001d1d9(zoom, rot, flag)`. It passes the stored centre tile `+0xb0/+0xb4` to
camera vt+0x38 = `FUN_10006752` (zoom) or vt+0x48 = `FUN_10006a55` (rotate). Both set the origin to
tile->world - (camera rect `+0x64..+0x70`) / 2 `[CONFIRMED @ SIMSPR 0x1000688d, 0x10006b0f]`. `+0xb0/+0xb4` is written
only by CenterOnTile and Translate.

## Exploratory run (before this file, `SC3RESIZE_ZOOMCENTER=0`, build with LCENTER on)

`re/harness/inst_leftclick/zoomExplore` (MAIN). Instrument `re/tools/zoomcenter_run_arm.py`: per camera zoom/rotate
call, the game's own pick (`FUN_1000902f`, mode 0 then 1) at the map-area centre before and after, and where the
passed tile landed on screen.
- Camera rect `+0x64..+0x70` is the whole client: 800x600 at 800x600, 1680x979 maximized.
- 800x600 (map-area centre (352,272)): every zoom and rotate landed the tile at **(400,300)**. The centre tile changed
  each time (149,127 -> 150,127 -> 151,127, rotate 151,127 -> 149,129).
- Maximized (centre (792,461)): landed (840,489) or (840,490). Centre tile changed each time.
- After restore to 800x600: the stored tile was stale (passed 143,127 while the centre showed 157,128).

## Choice at 800x600

ZOOMCENTER applies at 800x600 too (default `=1`). The stock 48x28 offset comes from the camera centring on its own
rect, the whole window, while every other centre in the view (CenterOnTile, Translate's pick, the stored size) is the
map area's (352,272). Measured above, it makes the centre tile move on every stock zoom at 800x600, the same defect the
owner sees maximized. `SC3RESIZE_ZOOMCENTER=2` keeps the stock numbers at exactly 800x600, `=0` everywhere.

## Change

`ZOOMCENTER` block in `sc3resize.c`: the two half-rect sites (24 bytes each at `SIMSPR 0x1000688d` and `0x10006b0f`)
subtract half the map area (`rz_lcenter_area`, the same rule as LCENTER, taken from the client and HUD window rects,
not screen metrics); on entry to `FUN_1001d1d9` (7 bytes) the stored tile is refreshed with the game's pick at the
map-area centre (kept when the pick misses, i.e. the centre is past the map edge).

## Run

Same machine and instance as `PRE.md`. Sequence per arm (driver `zoomcenter_run_arm.py`): 800x600 click (200,200),
zoom in, zoom out, PageDown, PageUp, right-drag, zoom in, zoom out; maximize; click (1400,800), the same 4 keys,
right-drag, zoom in, zoom out; restore; zoom in, zoom out. 10 camera calls at 800x600 / restored, 6 maximized.

Arms: Z1 `ZOOMCENTER` unset (MAIN); Z0 `SC3RESIZE_ZOOMCENTER=0` (MAIN, control); Z2 `=2` (MAIN); ZS Z1's DLL on the
stock tree `Simcity_stock_leftclick`.

| # | observable | Z1 / ZS predicted | Z0 predicted | Z2 predicted |
|---|---|---|---|---|
| 1 | install line | `zoomcenter=1` | `disabled` | `zoomcenter=2 ... stock at 800x600` |
| 2 | every call: landed vs map-area centre | (352,272) / (792,461) +-1 px | (400,300) / (840,489..490) | 800x600: (400,300); maximized: (792,461) +-1 |
| 3 | every call: pick at the centre after == before | all equal | not all equal | equal for the maximized calls |
| 4 | restored zoom: tile passed == centre pick before | yes | no (stale tile) | n/a (stock at 800x600) |
| 5 | game alive to the end, no `VEH FAULT` past the startup `0xC0000096` | yes | yes | yes |

PASS: Z1 and ZS rows 1-5 as predicted, Z0 reproduces rows 2-3, Z2 row 2. VOID: no zoom/rotate calls recorded, a modal
up, or `zoomcenter` not read back. Frames: display asleep at writing, recorded as pending.
