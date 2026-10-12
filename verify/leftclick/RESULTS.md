# RESULTS: left click on the map centres on the visible map area (`SC3RESIZE_LCENTER`)

Run 2026-10-12, task `leftclick`. Pre-registration `PRE.md` (`262960f`). Build: `sc3resize.dll` 250,880 B from
`child/leftclick` (base `child/hudfix`), other mods from `re/harness/combo`. Single 1680x1050 display at 100%.
City: Europolis 256 (copy in the instance folder). Driver `re/tools/leftclick_run_arm.py`, instrument
`re/tools/leftclick_trace.py`. No modal up in any arm (`dismiss_tips`: "no modal up"). Evidence is local
(gitignored): `re/harness/inst_leftclick/armT`, `armC` in MAIN, and
`Simcity_stock_leftclick/re/harness/inst_leftclick/armS`.

## Verdict: PASS on rows 1-7 in T and S, and the control reproduces the defect. Row 8 (frames) pending: display asleep.

"landed" = where the centred tile sits on screen after the call (tile -> world through `SIMSPR FUN_1000a513`,
minus the new origin). "shift" = camera origin after minus before.

| # | observable | arm T (`lcenter=1`, MAIN) | arm C (`SC3RESIZE_LCENTER=0`, MAIN) | arm S (T's DLL, stock tree) |
|---|---|---|---|---|
| 1 | install line | `--- LCENTER: lcenter=1 ... (SIMSPR+0x1d09c)` | `--- LCENTER: disabled` | as T |
| 2 | 800x600, click (352,272) / (200,200) | landed (352,272) / (352,272), shift (-16,-4) / (-160,-80) | identical numbers | identical to T |
| 3 | maximized 1680x979, click (792,461) | landed **(792,461)**, shift (+8,+3) | landed (352,272), shift **(+448,+192)** | as T |
| 4 | maximized, click (1400,800) | landed (792,461), shift (+608,+336) | landed (352,272), shift (+1056,+528) | as T |
| 5 | maximized, minimap click (1600,897) (caller `SIMUI+0x5090c`) | landed (792,461) | landed (352,272) | as T |
| 6 | restored to 800x600, click (352,272) | landed (352,272), shift (-8,-3) | n/a (landed (352,272)) | as T |
| 7 | stock SIMSPR (sha `eec71500…`) + stock GZGraphicD (`48201f47…`) | n/a | n/a | rows 1-6 as T |
| 8 | frames by eye | pending: display asleep (taskbar clock 14:04 at 14:14) | pending | pending |

Map area read from the live tree in every arm at maximized: side panel `SIMUI+0xa9834` `[1584 0 1680 821]`,
bar `SIMUI+0xa40ec` `[0 923 1680 979]`, minimap `SIMUI+0xaa180` `[1520 815 1680 979]` -> area 1584x923, centre
(792,461). The hook's own log agrees: `LCENTER> ... centred on the map area 1584x923 (stored 704x544, client 1680x979)`
at maximized and `704x544 (stored 704x544, client 800x600)` at 800x600.

Two calls at city load used a stored size of 800x600 (`LCENTER> #1/#2 ... stored 800x600, client 800x600`): the view
centres the city before its size is set to 704x544. At the native client the hook leaves the stock numbers alone.

## Stock-install note

The first arm S attempt ran from `Simcity_stock\re\harness\inst_leftclick` and the game died at 390 ms, before SIMSPR
loaded (no LCENTER line). That is the protocol section 10 crash (release mod DLLs in `Simcity_stock\Apps` loaded and
freed as a second copy), not this change. The passing run used `Simcity_stock_leftclick`, a hard-linked copy of the
stock tree with the mod files removed from `Apps` (hashes above checked after the copy).

## Not covered

- Frames: the display was asleep for the whole session, so no grab shows the result. Owner hand test.
- Zoom and rotate (`SIMSPR FUN_1001d1d9`, static read only): they pass the stored centre tile `+0xb0/+0xb4` to camera
  vt+0x38 (`FUN_10006752`) / vt+0x48 (`FUN_10006a55`), which put it at the centre of the camera rect `+0x64..+0x70`.
  That rect read 1680x979 live (the full client), so zoom centres on (840,489), 48x28 px off the map-area centre, the
  same offset the stock game has at 800x600 (400,300 vs 352,272). After an LCENTER click `+0xb0/+0xb4` is the tile at
  the map-area centre. Not measured in this run.
- DPI: the fix reads only game-space numbers (client rect, window rects), so it does not depend on DPI. The owner's
  laptop was not tested.
- HUDSCALE on: the code maps the docked HUD edges through the enlargement (`cw - s*(cw - x)`), not run here.
