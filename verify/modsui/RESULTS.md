# modsui: mods page buttons + camera panel (2026-10-28)

Code: `sc3resize.c`, `mp_panel` + `mp_btn_y` (MODSUI block before `cs_add_controls`), `mp_build` placement. `SC3RESIZE_MODSUI=0` drops the panel.

| owner point | result |
|---|---|
| buttons bottom-left, same height as OK | DONE. "Opciones de mods..." and "Volver" at x 18, y centred on the measured OK rect [432 434 474 466] (button y 437, h 26). |
| camera sliders on one light-blue panel | DONE. Panel built as the game builds its frames (FUN_10058c80: class 0x4303E5B6/0xE303E5AE, colour 0x62E56A2B, style 0x22), 190x50 at (278,161), added before the sliders. |
| no blue rectangle behind the buttons | NOT SOLVED. The blue box is the game's own text-button draw: the stock OK tick shows the same box. |

## Blue box, what was tried (all in-game, mods page, posted clicks, FRAMEDUMP)
- Dropping `+0x24(4,1)`, `+0x24(0x20,0)` and vt+0xf4(2,1) (all three): pill art goes, box stays.
- `+0x24(4,0)`: box and caption both gone from the first page, but the page background there is the same blue, so it only hid it. On the mods page the box stays. Button then does not send message 3.
- `+0x24(0x20,1)`: pill shrinks, box stays (tight).
- vt+0xf4(0x800,0), (0x10000,1), (0x10000,0), `+0x24(0x40,0)`, `(2,0)`, `(1,1)`: box stays.
- Empty caption + transparent label on top: box stays; label swallows clicks unless its flag 2 is cleared. Dropped.
Box colour is about (120,144,248), the first page's blue. On the first page the button sits on the blue strip so it is invisible there. Ideas left: an owner-drawn button (own bitmap, hit-test in ho_prefs_msg), or a lavender panel behind it.

Pictures (not for git): MAIN\verify\modsui\owner_shots\prefs_game_page.png, prefs_mods_page.png.

## Round 2 (orchestrator follow-up)
- Camera panel colour: now `fac+0x80(0x62E56A2C, 0)`, the colour of the panel behind the three sound sliders (frame 0x02F95ADC, FUN_100564d9). Saturated blue, checked in game.
- Blue box, colour slots tried: window vt+0x178(colour from vt+0x184(212,216,248)) as GZWIND 0x100150aa sets on message-box buttons: no visible change. Button +0x84(): shrinks the button to ~54 px and darkens the caption, box stays. Box is not the button's fill. The image-button route (factory +0x30) has no caption path (QUERY_ID.md) and the stock OK, built that way, has the same box. Stopped, as briefed. Remaining options: owner-drawn button or lavender backing panel (owner call).
