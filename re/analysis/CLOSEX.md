# CLOSEX: the window X, Alt+F4 and the system-menu Close quit through the game's own path

Task `closex`, 2026-10-12. Owner report from the laptop (stock install, release sc3mods-2026-10-12): "no funcionó la X
para cerrar". Code: `sc3resize.c`, block `CLOSEX` (`g_closex`, `rz_closex`, `rz_closex_screen`), opt-out
`SC3RESIZE_CLOSEX=0`. Test: `verify/closex/PRE.md`, `verify/closex/RESULTS.md`.

## Why the X does nothing on a stock install

- `GZGraphicD FUN_10017e2f` (the Gonzo WndProc) returns 0 on msg 0x10 (WM_CLOSE) without calling DefWindowProc: the
  `je` at 0x10017eab goes to the shared return-0 epilogue [CONFIRMED @ GZGraphicD 0x10017e2f]. The X, the system-menu
  Close and the taskbar "Cerrar ventana" all end in WM_CLOSE (DefWindowProc turns WM_SYSCOMMAND/SC_CLOSE into it, and
  0x112 and 0xa1 do reach DefWindowProc in this WndProc).
- msg 0x104 (WM_SYSKEYDOWN) goes to the game's key path (LAB_1001805b), never to DefWindowProc, so Alt+F4 never
  becomes SC_CLOSE [CONFIRMED @ GZGraphicD 0x10017e2f].
- SC3U's raw-message listener `FUN_00442c39` (subscribed to 0x5a4fc3d5 by `FUN_0043dc11`; GZGraphicD broadcasts every
  window message to it from `FUN_10018871`) handles only IME messages [CONFIRMED @ SC3U 0x00442c39].
- Measured on the stock copy with `SC3RESIZE_CLOSEX=0`: X, posted Alt+F4 and SC_CLOSE at the main menu, game alive and
  no dialog after each (`verify/closex/RESULTS.md`, arm control_menu).

The only X-to-quit that ever existed is MAIN's on-disk `pe_patch.py` recipe `close_button_quit` (PostQuitMessage cave
at GZGraphicD 0x1001d80a, `je` rel32 at 0x10017ead redirected from 0x00000316 to 0x00005959). It quits at once, with no
question, and it never shipped to players.

## The game's own quit paths

| screen | what "Salir" does | evidence |
|---|---|---|
| intro (root child vtable `SC3U+0xd1784`, ~40 s at start) | no quit control | - |
| main menu (root child vtable `SC3U+0xd2c20`) | button 0x712BF5C4 (Exit) -> menu vt+0x1e0 = `FUN_0043b51d(1, id)` -> `FUN_0043b6c3` -> parent vt+0x44(0xd, menu, id). Shows a two-button dialog (`SIMUI+0xa4d64`, 288x139). Left button quits, right button goes back to the menu (measured). | [CONFIRMED @ SC3U 0x0043b51d], ids in `LAUNCH_CONTROL.md` section 31 |
| city | menu-bar item "Quit" = command 0x10009005, COMM to class 0xA10438E9 (`MenuItem.INI`). A click posts {0x025F0A91, cmd, 0, 0} through the message service [CONFIRMED @ SIMUI 0x1004c209]. The command object (`FUN_004119d2`, vtable 0x4d023c) calls the quit flow `FUN_004108f3(1, 1)` on the global at 0x4fae74 (vtable 0x4cf59c, slot 0x84) [CONFIRMED @ SC3U 0x00411a3b, slot resolved live]. | below |

`FUN_004108f3(confirm, askSave)` with a city [CONFIRMED @ SC3U 0x004108f3]: modal question 1 (text ids 0x55/0x225872fe
and 0xa3/0x209e6378, type 0x10001), result 0x5301814a continues. Modal question 2 (0x127/0x209e6378, type 0x10004):
0x5301814c opens the save dialog (class 0x410438DD), 0x53018149 skips the save, anything else cancels the quit. It
then quits through the framework (`thunk_FUN_0045d5ae()->vt+0x40(0)`). Measured: question 1 left button = continue,
right = cancel. Question 2 right button = quit without saving (exit code 0). The left button of question 2 (save) was
not pressed in these tests.

The Quit command does nothing at the main menu (measured: posted, no dialog, menu stays). That is why there are two
routes.

The app's own `PostQuitMessage` wrapper is `SC3U FUN_004613d8` = app vtable 0x4d6a8c slot 0x1a8 (deferred when
app+0x70 is set) [CONFIRMED @ SC3U 0x004613d8]. CLOSEX does not call it.

## What CLOSEX does

On WM_CLOSE (X, system menu, taskbar) and on WM_SYSKEYDOWN VK_F4 with the Alt context bit, before the game's WndProc:

1. If a modal loop is open beyond the screen's own, ignore it (logged). The modal loop is GZWIND `FUN_10020971`
   (vtable GZWIND+0x2db80 slot 0xa0); it counts depth in sink+0x194 (`FUN_1002174d` returns `!= 0`) and dispatches
   messages itself [CONFIRMED @ GZWIND 0x10020971]. Measured depth: city 0, main menu 1, intro 1, each open quit
   question +1 there. Without this guard a second X while question 1 was open stacked a second question (measured,
   depth 2). Allowed depth is 1 on the menu and the intro, 0 elsewhere.
2. Main menu visible: call its Salir button handler (route 1 above).
3. City loaded (`rz_city_post(0,0)`): post the Quit command (route 2 above).
4. Otherwise (the intro screen, or no menu and no city): `PostQuitMessage(0)`, like the recipe. Measured on the
   intro: exit code 0.

Because CLOSEX takes the message first and returns 0, a GZGraphicD that carries the recipe cave never reaches the cave
(measured on MAIN: the game asked, it did not quit). With `SC3RESIZE_CLOSEX=0` the message goes to the game as before,
so on MAIN the cave quits at once (measured, exit 0) and on stock nothing happens. At subclass time the log states
which GZGraphicD it is (`rel32 0x00005959` = cave present, `0x00000316` = stock).

UX decision: the X asks, it does not quit at once. On a city that is two questions (quit? then save?), the same as
the menu's "Salir". An unsaved city is not lost on a stray click. Quitting at once happens only on the intro screen,
where there is nothing to save.

## Open

- Visual check of the dialogs is pending: the display was asleep for the whole session (taskbar clock frozen at 13:04),
  so every result above is from the UI tree (`re/tools/uiwin_dump.py`), the modal depth (`re/tools/dlg_text.py`), the
  mod log and the process exit code. The dialog text was not read (it is rendered to a surface).
- Alt+F4 was sent as posted WM_SYSKEYDOWN/UP with the Alt context bit, not from a physical keyboard. A real key press
  goes through the same TranslateMessage/DispatchMessage in the game's loop to the same WndProc.
- The X button itself was not clicked with a real mouse. SC_CLOSE posted to the window was, and DefWindowProc turns
  that into WM_CLOSE. The owner's earlier real X clicks on MAIN reached the WM_CLOSE branch (the recipe cave fired).
- Not covered: X while a city is loading, in the terrain editor (New City), or with another modal dialog open (by
  rule 1 it is ignored there).
