# PRE: menucrop (main-menu picture cropped, broken menu_bg.bmp falls back to stock), 2026-10-14

Owner calls 2026-10-14: crop the main-menu picture instead of stretching it, and a broken `menu_bg.bmp` uses the
stock picture instead of turning MENUBG off. Branch `child/menucrop` from `round/1012` (a270f4f).
Code: `rz_mb_use_stock`, `rz_mb_load`, `rz_mb_prepare` in `re/harness/src/sc3resize.c`, switch `SC3RESIZE_MENUBGFIT`
(1 cover + centre crop, default; 0 the old stretch).

Instance `re\harness\inst_menucrop` (MAIN): the 2026-10-11 `inst_menubg` mods plus the new `sc3resize.dll`, game =
the live install, `mods_launch.exe -multi`. Each arm: main menu, maximize (sc3io, no focus taken), grab, click the
drawn "Nueva Ciudad", grab, kill the PID started.

| arm | menu_bg.bmp | env | predicted |
|---|---|---|---|
| A | owner's 1448x1086 24-bit | - | log `cover source [x 0 x+w 1086]` with w = 1086 * cw / ch, picture undistorted (circles stay round), buttons native size, centred, "Nueva Ciudad" opens "Nuevas opciones de ciudad" |
| B | none | - | log `missing - using the stock background`, stock picture cropped, click as in A |
| C | a text file named menu_bg.bmp | - | log `not a BMP - using the stock background`, same picture as B, click as in A |
| D | the owner's picture saved as 32-bit BMP | - | log `not an uncompressed 24-bit BMP - using the stock background`, same picture as B, click as in A |
| E | owner's | `SC3RESIZE_MENUBGFIT=0` | log `stretch source [0 0 1448 1086]`, the 2026-10-11 stretched look (control) |

Pass: A to D all as predicted. Any arm with MENUBG off (whole frame stretched, click opens the wrong dialog) is a fail.
At 800x600 (not maximized) a 4:3 picture is not cropped (source = whole picture), checked from the A log at startup.
