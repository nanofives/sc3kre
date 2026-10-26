# newcitydlg: New City options dialog not enlarged, and cropped over Ver datos (child/newcitydlg, 2026-10-26)

Owner report (MARIANO-PC, maximized 2560x1351, HUD scale Auto, sc3mods-2026-10-25d = main 9825dc4): "new city screen is
not scaled up, also, when opening it while having the map open it crops" (`owner_shots/img1_newcity_cropped_over_mapdlg.png`).

## Cause

1. **Not enlarged.** The in-city New City options dialog is not a `SIMUI+0xa4d64` window. Its ctor `SIMUI FUN_1005b6f4`
   calls the dialog base ctor `FUN_1002c688` (which writes vt `0x100a4d64`), then writes its own vt `0x100aa8e8`.
   DLGSCALE, the dialog placement poll and the HUD-translation exclusions all matched `0xa4d64` only. HSCENSUS before:
   `SIMUI+0xAA8E8 639x389 at [32 76 671 465]: floating, NOT SCALED`. So it stayed native at the top-left.
2. **Cropped.** DLGSCALE resamples each enlarged dialog from its native rect in the frame and draws it on top of
   everything. Ver datos' native rect also held the native New City pixels that overlapped it, so those came out
   enlarged inside Ver datos' box, and the rest of New City sat under the enlarged Ver datos. That is the owner's picture.
   It needs the two native rects to overlap, so it showed only once Ver datos was dragged to the top-left (native
   [320 241 744 681]). The same mechanism gives:
   - a ghost strip when two enlarged dialogs overlap natively and their clamped dests do not line up;
   - a hidden dialog when one kept native (dragged partly off the client) sits in front of an enlarged one. Measured:
     Ordenanzas at [-89 470 295 824] in front of Ver datos showed only as a magnified piece inside Ver datos' box.

## Fix (`re/harness/src/sc3resize.c`, two blocks, each with an off switch)

- **DLGCLASS** (`SC3RESIZE_DLGCLASS=0` = only `0xa4d64`, as before): `rz_is_dlg_vt()` counts `0xa4d64` and New City's
  `0xaa8e8` as dialogs in four places:
  - DLGSCALE collection (`rz_hs_collect`);
  - the placement poll (`rz_dialogs_poll`), so New City is centred in the map area like every other dialog;
  - the two "not a HUD piece" exclusions.

  The other 15 subclasses are left out. They are Internet Chat windows that cannot be opened (table below).
- **DLGOCC** (`SC3RESIZE_DLGOCC=0` = the old copy). For a dialog in front, meaning earlier in the root's front-first
  list, whether enlarged or kept native:
  - every enlarged dialog behind it keeps its own last-frame pixels where the front one overlaps its native rect;
  - a kept-native front dialog's pixels are saved before the enlarged pass and put back right after the last enlarged
    dialog behind it is drawn;
  - the mouse on such a native dialog keeps native coordinates, including its drag and release.

  A dialog's first frame takes the frame as it is. Log lines `DLGOCC>`.

## The 16 dialog subclasses of SIMUI `FUN_1002c688`

Identity is from the SIMUI and SC3U exports: strings in each class's init, the GZCOM factory registry in SIMUI
`FUN_1006a964`, and the SC3U chat manager (`FUN_00418a54` init, `FUN_00418c71` messages).
- 15 classes are the built-in **Internet Chat** IRC client (`irc://www.simcity.com:6667`, SC3U `FUN_00413d42`).
- Its only entry is the cheat word "Internet chat". `FUN_00418a54` registers it under id `0x53483962`. `FUN_00418c71` maps
  cheat message `0x230e27ac` with that id to the chat manager's vt slot +0x54.
- The chat manager vt is SC3U `0x4d0a70` (ctor `FUN_004187ab`). Its slot +0x54 is `FUN_0041c988`, 3 bytes `xor al,al; ret`
  `[CONFIRMED @ 0x0041c988, PE bytes 32 c0 c3]`.
- **Measured in game:**
  - Ctrl+Alt+Shift+C opened the cheat box (`SC3U+0xD12D0 312x28 at [0 0 312 28]`, kept native).
  - Typing "Internet chat" and Enter closed it, with no new window in HSCENSUS or on screen.
  - Input was posted: the modifier keys came from a 2 s Frida hook on the game's `GetKeyState`, because GZGraphicD
    `FUN_10017b50` reads them from there.
- **So none of the 15 can appear in this build.** DLGCLASS keeps them out on purpose.

| vt (SIMUI) | ctor | what it is | how a player opens it | after DLGCLASS |
|---|---|---|---|---|
| `0x100aa8e8` | `0x1005b6f4` | **New City options** ("Nuevas opciones de ciudad", 639x389) | in a city: options flyout > Nueva ciudad > "No" to the save prompt | **enlarged** 2.250x (2560) / 3.305x (3840), centred. Clicks checked, see below |
| `0x100a5120` | `0x100305fe` | chat text prompt ("Save Text" / "Add New Friend") | chat pane right-click, only inside the chat | not reachable: chat entry stubbed. Not in the list |
| `0x100a53ac` | `0x10030b8c` | chat "Chat Settings" (Server, Nickname, Password, Connect) | `/config` inside the chat `[UNCERTAIN]` | not reachable |
| `0x100a5604` | `0x10031dde` | chat view base class (abstract) | none | n/a |
| `0x100a58b8` | `0x100359fe` | chat main view, about the whole game screen (`parent_w - 0x9f` x `parent_h - 0x4d`) | first chat view `[UNCERTAIN]` | not reachable. If it ever were, it would be about client-sized, so DLGSCALE would enlarge it only about 1.06x. It should stay native, which is one more reason to leave the chat classes out |
| `0x100a5c5c` | `0x10036753` | chat in-room view, full panel | from the other chat views | not reachable. Same note |
| `0x100a61d4` | `0x100379e0` | chat room lobby ("All Rooms", "Members", 600x344) | from the room view | not reachable |
| `0x100a6544` | `0x100385c5` | chat "Create a Room" | chat right-click > Create new room | not reachable |
| `0x100a67d0` | `0x10039504` | chat "Send a Private Message" | chat right-click on a member | not reachable |
| `0x100a6a68` | `0x1003a0c0` | chat "Friends" list | `/view friends` `[UNCERTAIN]` | not reachable |
| `0x100a6ce8` | `0x1003c494` | chat "All Users" | `/view all` `[UNCERTAIN]` | not reachable |
| `0x100a6f84` | `0x1003ccc0` | chat "Room Properties" | `/view room properties` `[UNCERTAIN]` | not reachable |
| `0x100a71f0` | `0x1003de05` | chat class with no init or strings of its own `[UNCERTAIN]` | unknown | not reachable |
| `0x100a7468` | `0x1003e042` | chat window 500x400, no child widgets in its init `[UNCERTAIN]` | unknown | not reachable |
| `0x100a76fc` | `0x1003eefa` | chat "Receive Snapshot?" prompt | created by SC3U `FUN_0041e100` on an incoming DCC transfer (needs a live chat connection) | not reachable |
| `0x100a7988` | `0x1003f6d0` | chat transfer progress ("Sending..." / "Receiving...") | created by SC3U `FUN_0041dc7d` during a DCC transfer | not reachable |

## Check (Simcity_stock_newcitydlg, all 7 mods + version.dll from the worktree, Europolis, windowed)

Arms:
- A = main 7d3493b.
- B1 = the first build (16 classes, DLGOCC for enlarged dialogs only).
- B = this build.
- C = B1 with `SC3RESIZE_DLGOCC=0`.

Input was posted only: sc3io PostMessage, SetWindowPos with SWP_NOZORDER|SWP_NOACTIVATE, SetWindowPlacement for
maximize, and the GetKeyState hook above for the cheat box. Pictures come from `SC3RESIZE_FRAMEDUMP`, or from
`SC3RESIZE_MENUSCALE_DUMP` at the menu.

| case | result | picture (`owner_shots/`) |
|---|---|---|
| New City from the city, nothing else open, 2560x1351 | A: native at [32 76], `floating, NOT SCALED`. B: `dialog enlarged`, [912 453 1551 842] -> [513 210 1951 1085] 2.250x, centred | `fix1_newcity_in_city_2560_before_after.png` |
| New City over Ver datos (Ver datos dragged to native [320 241 744 681]) | A: New City cut to Ver datos' box (owner's picture). B: both enlarged, New City in front | `fix2_newcity_over_verdatos_2560_before_after.png` |
| New City dragged so its native rect is inside Ver datos' rows | C: magnified ghost of New City's bottom bar in Ver datos' box. B: Ver datos' own legend there | `fix2b_dlgocc_strip_2560_off_on.png` |
| maximized 3840x1984 (3.305x), New City over Ver datos | the centred New City overlaps Ver datos natively, DLGOCC logged, no ghost. Closing New City leaves Ver datos clean | `fix3_newcity_over_verdatos_3840_after.png` |
| New City from the main menu, 2560 | MENUSCALE scales it as before, no double scaling | `fix4_newcity_main_menu_2560_after.png` |
| Preferencias, Indagar, Presupuesto, Ordenanzas, Mapa de vecinos over Ver datos | each enlarged, in front of Ver datos | `fix5_other_dialogs_over_verdatos_2560_after.png` |
| **native dialog in front of an enlarged one**: Ordenanzas dragged to [-64 404 320 758] (kept native, off the client) in front of Ver datos (enlarged to [0 0 954 990]) | B1: only a magnified piece inside Ver datos' box, the real dialog hidden. B: drawn whole and native in front (`DLGOCC> native dialog [-64 404 320 758] put back in front of 1 enlarged dialog(s)`). A click on its ✓ at native (290,731) closed it, with no DLGSCALE remap. Ver datos clean after | `fix6_native_dialog_in_front_2560_before_after.png` |
| New City controls, 2560 (B) | all mapped through DLGSCALE and took effect: city name field (click, 14 backspaces, "Prueba" typed), Difícil, Enorme 512 radio (the sc3bigcity slider appeared), slider dragged to 896 (`sc3bigcity: slider 838 -> 896`, label "Enorme 896"), Panorama 1, Árboles 1, Edificios 3 (preview changed), Desastres checkbox. X cancelled. ✓ (first run) went on to `Cargando...` and the terrain editor, panel enlarged | `fix7_newcity_controls_2560.png` (frames `fd/q1..q4`, `fd/b18_after_accept.png`) |
| close order | New City or Preferencias first, then Ver datos: clean. Preferencias is modal (a click on Ver datos' X did nothing while it was open). The cheat box and Ver datos cannot be open together in either order | |
| the cheat box, the only other native window seen | `SC3U+0xD12D0` 312x28 at [0 0], drawn native under the sc3perf FPS line, so it is hidden when the FPS counter is on. It is not a dialog class and cannot sit in front of an enlarged dialog | (frames `fd/k5_typed.png`, `k7_typed.png`) |

The only VEH line in every arm is the startup `0xC0000096 at SC3U.exe+0x84122` that arm A logs too. Logs:
`logs/A_before_*`, `logs/B_city2560_*`, `logs/B_max3840_*`, `logs/B_menu2560_*`, `logs/C_dlgocc0_*`, `logs/D_*`
(cheat box, arm B1), `logs/E_*` (this build).

## Seen, not changed

- New City now opens centred in the map area (the placement poll owns it). Before, it opened at the stock [32 76]. Every
  other dialog follows the same rule.
- The cheat box is drawn under the FPS line (top-left, both native). Not part of this report, so not moved.
- "Seleccionar" (user-made buildings) in New City was not clicked. It may open a Windows file dialog, which would take
  the foreground.
- With the sim paused, the city view sometimes scrolled between frames during these runs. That was not traced.
