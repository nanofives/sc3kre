# PRE-REGISTRATION: CLOSEX (window X / Alt+F4 opens the game's own quit) - closex child, 2026-10-12

Written before any game run of the new build.

## Owner report
"no funcionó la X para cerrar" on the laptop: stock install + release sc3mods-2026-10-12. The X-to-quit behaviour lives
only in MAIN's on-disk GZGraphicD recipe `close_button_quit`, so every release player has a dead X.

## Static facts this test rests on
- Stock Gonzo WndProc `GZGraphicD FUN_10017e2f` returns 0 on msg 0x10 (WM_CLOSE) without calling DefWindowProc
  [CONFIRMED @ GZGraphicD 0x10017e2f, the `je` at 0x10017eab]. So the X, the system-menu Close and the taskbar
  "Cerrar ventana" (all end in WM_CLOSE) do nothing on stock.
- msg 0x104 (WM_SYSKEYDOWN) goes to the game's key path (LAB_1001805b), never to DefWindowProc
  [CONFIRMED @ GZGraphicD 0x10017e2f], so Alt+F4 never becomes SC_CLOSE on stock.
- SC3U's raw-message listener `FUN_00442c39` (registered for 0x5a4fc3d5 by `FUN_0043dc11`) handles only IME
  messages (1, 0x10d..0x10f, 0x281..0x284), not WM_CLOSE [CONFIRMED @ SC3U 0x00442c39].
- The menu "Quit" item is command 0x10009005, COMM to class 0xA10438E9 (`MenuItem.INI`, `re/tools/menuitem_parse.py`).
  SC3U's class factory `FUN_00411523` builds a 0xac-byte object for 0xa10438e9 (`FUN_004119d2`) [CONFIRMED @ 0x00411523].
- A button click fires its command by posting GZ message {0x025F0A91, cmdID, 0, 0} through the message service
  [CONFIRMED @ SIMUI 0x1004c209]. sc3resize already posts through that service (`rz_city_post`, PAUSEKEY / SPEEDKEYS).
- The app's own quit is `SC3U FUN_004613d8` = app vtable 0x4d6a8c slot 0x1a8: PostQuitMessage(code), or deferred when
  app+0x70 is set [CONFIRMED @ SC3U 0x004613d8; slot read from the PE .rdata at 0x4d6c34].

## The change (UX decision)
X / Alt+F4 / system-menu Close post the game's own Quit command {0x025F0A91, 0x10009005}, the same message a click on
the menu's "Salir" posts. The game then shows its own quit dialog, so an unsaved city is not lost on a stray click.
Immediate quit (PostQuitMessage, what the on-disk recipe does) only as a fallback when the message service is not up.
`SC3RESIZE_CLOSEX=0` = old behaviour (WM_CLOSE passes to the game's WndProc; on MAIN's patched GZGraphicD the cave quits).

## Arms and expected outcomes (committed in advance)

| # | install | state | input | expected | if not |
|---|---|---|---|---|---|
| C1 control | stock | main menu | WM_CLOSE, `SC3RESIZE_CLOSEX=0` | nothing happens, process alive 10 s later | if it quits, the static read of 0x10017eab is wrong |
| C2 control | stock | main menu | Alt+F4, `CLOSEX=0` | nothing happens | if it quits, Alt+F4 has a stock path |
| S1 | stock | main menu | WM_CLOSE | the game's "Salir" dialog on screen; then its accept -> process exits, exit code read | no dialog: the command is not handled at the menu (record which state works) |
| S2 | stock | city loaded | WM_CLOSE | same "Salir" dialog; Cancel -> city keeps running; second X + accept -> exits | |
| S3 | stock | city loaded | Alt+F4 | same dialog | |
| S4 | stock | city, X twice | WM_CLOSE x2 | one dialog, no crash | two stacked dialogs or a fault |
| M1 | MAIN (cave GZGraphicD) | city | WM_CLOSE | dialog (CLOSEX takes it first; the cave does not run, process alive) | immediate exit = the cave ran = double action |
| M2 | MAIN | city | WM_CLOSE, `CLOSEX=0` | immediate exit via the cave (control proving M1's dialog is CLOSEX) | |
| E | any | each exit | - | exit code 0, no new crash in sc3perf log beyond the known-benign VEH entries SC3U+0x84122 and KERNEL32+0x2CC02 | |

Every visual result is a screenshot that is looked at. "Process exited" is checked by PID, never by name.
A run where the display is asleep (stale taskbar clock) is VOID for visuals, logs still count.
