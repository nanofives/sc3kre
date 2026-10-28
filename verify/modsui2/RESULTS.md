# modsui2: mods page buttons, layout + click-through (2026-10-28)

Code: `sc3resize.c` (MODSPAGE block: `MP_BX`, `MP_BH`, `mp_btn_y`, `mp_show`, `g_mp_lastlp` in the wndproc). Hover fix off switch: `SC3RESIZE_MPHOVER=0`.

| owner point | result |
|---|---|
| 1. buttons on the tick's top and bottom, left edge on the panel frames | DONE. "Opciones de mods..." and "Volver": x 6, h 32, bottom = bottom of the OK rect [432 434 474 466] (top 434). Both pages in owner_shots. |
| 2. Volver needs the mouse to leave and re-enter | FIXED, both directions. |

## Cause (game-side, reproduced)
Posted clicks at one point with no move between them (raw down/up): the first click switched to the mods page, every later click at the
same point logged `MODSPAGE> mods page` again, i.e. the HIDDEN "Opciones de mods" button kept receiving them. The dialog holds the
child under the mouse until a mouse move leaves it. A move inside the button or to the same point changes nothing (tried: +3 px and the
same point, still the old button). A move out of the button and back fixes it (tried by hand in the test: out to (300,300), back, click
= "game page").

## Fix
`mp_show` posts two WM_MOUSEMOVE to the game window after the switch: 80 px above the last click point, then the click point itself
(the point comes from the last WM_LBUTTONUP seen in the wndproc). The dialog re-resolves the child under the mouse, so the new button is it.
Did not move one button away from the other. Side effect: for a frame the hover highlight passes over whatever is 80 px above.

## Check (posted input only, FRAMEDUMP, windowed)
click Opciones de mods (240,514) -> raw click at the same point x3, no move: mods, game, mods, game page in the log. Both directions work with
one click each.

Pictures (not for git): MAIN\verify\modsui2\owner_shots\game_page.png, mods_page.png.
Note: a csrss "SC3U.exe - Error del sistema" box from another process sat over the game area, so desktop grabs were refused. FRAMEDUMP was used.
