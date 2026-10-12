# RESULTS: CLOSEX (verify/closex/PRE.md) - closex child, 2026-10-12

Build: sc3resize.dll 251,392 bytes, sha256 prefix e7f9f1f7467e9d31 (branch child/closex). Stock = hard-linked copy of
Simcity_stock without mod files in Apps (`Simcity_stock_closex`, protocol section 10), release 2026-10-12 DLLs beside
the launcher in the instance folder. MAIN = live install, GZGraphicD with the on-disk `close_button_quit` cave.
Driver: `re/tools/closex_drive.py` (launch / close = PostMessage WM_CLOSE / altf4 = posted WM_SYSKEYDOWN+UP VK_F4 with
the Alt context bit / syscls = posted WM_SYSCOMMAND SC_CLOSE / watch = holds a handle and records the exit code).
"quitdlgs" = visible root children `SIMUI+0xa4d64` with 7 children (`re/tools/uiwin_dump.py`); "depth" = GZWIND
sink+0x194 (`re/tools/dlg_text.py`). Each arm ran on the final build unless noted. Logs: `<instance>\runs\<arm>_<time>\`.

## Verdict
PASS on every pre-registered arm. The X, Alt+F4 and the system-menu Close open the game's own quit on stock and on
MAIN, a second X is ignored, Cancel returns, OK/No exits with code 0, "Sí" saves the city and then exits, and MAIN's
cave never runs while CLOSEX is on.

| PRE arm | result |
|---|---|
| C1 stock menu, CLOSEX=0, WM_CLOSE | alive, 0 dialogs (control_menu_143518, and c1_off on an earlier build) |
| C2 stock menu, CLOSEX=0, Alt+F4 (+ SC_CLOSE) | alive, 0 dialogs. Exit 0x1 = my own taskkill |
| S1 stock menu | X -> 1 dialog, depth 1 -> right = back to menu -> Alt+F4 -> 1 dialog -> left -> exit 0x0 (menu_14xxxx, final build 14:57:02) |
| S2 stock city | X -> question 1 (depth 1) -> right = cancel (depth 0, city runs) -> SC_CLOSE -> question 1 -> left -> question 2 -> right -> exit 0x0 (final build 14:59:38) |
| S3 stock city Alt+F4 | question 1 (same run) |
| S4 stock X twice | menu and city: second X logged "a modal dialog is open (depth 1) - ignored", 1 dialog |
| M1 MAIN city | same sequence as S2, exit 0x0 at 15:01:34, log says cave present, game asked both questions = cave did not fire |
| M2 MAIN city, CLOSEX=0 | X -> process gone within 3 s, exit 0x0 = the cave quit at once (control) |
| E exits | no fault other than the startup SC3U+0x84122 in any run, no SC3U_stkdmp.txt written in either tree |
| extra: intro | stock, X ~3 s after subclass while the intro screen (SC3U+0xd1784) is up -> exit 0x0 (14:54:31) |

## Visual check (display awake from ~15:03)
`Simcity_stock_closex\re\harness\inst_closex\runs\visual\`, each frame looked at:
- `city_q1.png`: dialog "Salir", text "Saliendo de Sim City 3000", buttons OK / Cancelar, centred on the city.
- `city_q2.png`: after OK, dialog "Salir", text "¿Quieres guardar el juego?", buttons Sí / No.
- After "Sí": the city file the game had loaded (the instance's `Europolis.sc3` copy) was rewritten at 15:03:57
  (761,860 -> 761,764 bytes) and the game exited 0x0 at 15:03:59. No save-as dialog: the city already had a file.
- `menu_q.png`: at the main menu, the same "Salir / Saliendo de Sim City 3000 / OK / Cancelar" dialog over the menu
  picture. OK -> exit 0x0 (15:06:01).

## Findings beyond the PRE
- The Quit command 0x10009005 does nothing at the main menu (posted, no dialog). The menu has its own Salir button
  (0x712BF5C4, SC3U FUN_0043b51d), so CLOSEX routes by screen.
- The main menu and the intro each run inside a GZWIND modal loop (depth 1). A second X during question 1 stacked a
  second question before the guard existed (depth 2, measured on MAIN).
- On stock the window never gets WS_THICKFRAME/WS_MAXIMIZEBOX from sc3resize: rz_make_resizable runs only inside the
  resize pass, which needs a city and a client size other than 800x600. Sent to `windowed`.

## Not covered
Real mouse click on the X glyph and a physical Alt+F4 (posted equivalents used). X during a city load or in the
terrain editor. Dialog placement when maximized.
