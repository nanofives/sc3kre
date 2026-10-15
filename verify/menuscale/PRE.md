# PRE: menuscale (main menu frame scaled to the largest 4:3 rect), 2026-10-14

Owner request 2026-10-14: "the main menu has to scale on the viewable 4:3 area, despite textures not scaling".
Branch `child/menuscale` from `round/1012` (5eae8e6). Code: MENUSCALE block in `re/harness/src/sc3resize.c`
(`rz_ms_*`, called from `rz_mb_present`, mouse map in `rz_wndproc`). Switches: `SC3RESIZE_MENUSCALE=0` (today's 1:1
centred frame), `SC3RESIZE_MENUSCALE_FILTER=0` (nearest), `SC3RESIZE_MENUSCALE_DUMP=<prefix>` (in-process dump of the
composed client and the source frame on request).

Instance `MAIN\re\harness\inst_menuscale` (all six binaries built from this worktree, owner's `menu_bg.bmp`), live
game install, `mods_launch.exe -multi -- -intro:off`, only the PID it prints is driven or killed. Display 3840x2040.

## Rect predictions (largest 4:3, floor, centred)

| client | rect logged `[x0 y0 x1 y1]` |
|---|---|
| 3840x1984 (maximized, aspect 1.94) | `[597 0 3242 1984]` = 2645x1984 |
| 1680x1050 (16:10) | `[140 0 1540 1050]` = 1400x1050 |
| 1680x979 | `[187 0 1492 979]` = 1305x979 |
| 1000x900 (taller than 4:3) | `[0 75 1000 825]` = 1000x750 |
| 800x600 | no MENUSCALE rect line, the native path as before (swap log `stock ...`) |

## Arms

| arm | env | steps | predicted |
|---|---|---|---|
| A | - | 800x600 grab; maximize; dump + grab; click the drawn "Nueva Ciudad" (client point from the frame dump: rect origin + (frame point + 0.5) x scale), dump, Cancelar; same for "Cargar ciudad", "Preferencias" (if on the menu), "Salir" + its Cancelar; one widget inside the New City dialog (a radio / option) changes state; resize 1680x1050, 1680x979, 1000x900, dump each | rect lines as in the table; every click opens / closes the dialog drawn under it; the dump shows the frame scaled into the rect, picture sharp around and behind the buttons |
| B | `SC3RESIZE_MENUSCALE_FILTER=0` | maximize, dump | every rect pixel of the dump equals either the frame pixel at the nearest index or the picture pixel at that client point (checked offline from the two dump files) |
| C | `SC3RESIZE_MENUSCALE=0` | maximize, click "Nueva Ciudad" at its 1:1 spot (frame + `(1520,692)`) | log `first centred present ... [1520 692 2320 1292]`, no MENUSCALE rect line, dialog opens: today's behaviour |
| D | - | from the scaled menu: New City, accept, terrain / city view | log `menu over` or `not the menu, mapping off` once the city frame appears, city frames presented by the normal path, no crash, no menu frame in the first city grabs |

Performance: the log prints avg read / compose / blit ms and the worst present every 2 s. Reported for maximized
3840x1984 and 1680x979, static menu and with a dialog opening. No pass threshold is set; a static-menu average above
8 ms per present is flagged as a defect to fix.

## What counts as seen

The game window is never given focus (`sc3io`). The menucrop run saw a white frame while the window was not
foreground. Two views are recorded and kept apart in RESULTS: (1) the DLL dump = what MENUSCALE composed and sent to
the window, and the source frame it read; (2) the desktop grab = what the screen shows. If the source frame itself
is white, posting `WM_ACTIVATEAPP(1)` / `WM_ACTIVATE(WA_ACTIVE)` to the game window (no real focus change) is tried
as a diagnostic, and its effect is reported as such.

Pass: A, C, D as predicted, B exact. Any click that opens a different dialog than the one drawn under it is a fail.
