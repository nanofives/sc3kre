# Picker / eyedropper tool (sc3resize PICKER, child picker 2026-10-30)

Owner request (2026-10-30): "Add a picker tool (also Ctrl+F) to pick a selected building/road/entity that's selectable."

What it does: the eyedropper button on the minimap panel (bottom-left corner) or Ctrl+F starts the picker. A click on
the city makes the build tool of the object under the cursor the active tool, with that exact item: the same tool and
item the menus would give. Objects with no build tool show a short message and the picker stays on. Esc or a
right-click ends it. While it is on, the mouse cursor is an eyedropper (round pickerui, section 6).

Code: `re/harness/src/sc3resize.c`, block `PICKER` right before `rz_wndproc`. Switches: `SC3RESIZE_PICKER=0` installs
nothing. `SC3RESIZE_PICKER_BUTTON=0`: no button (Ctrl+F only). `SC3RESIZE_PICKER_KEY=0`: no Ctrl+F.
`SC3RESIZE_PICKER_CURSOR=0`: the game's query cursor stays. Evidence: `verify/picker/RESULTS.md`,
`verify/pickerui/RESULTS.md`. Test tools: `re/tools/picker_lab.py` (`PICKER_RUNS=<dir>` moves its run folders),
`picker_batch.py`, `picker_screen.py`, `pickerui_check.py`.

## 1. The game's query tool, which the picker reuses

| piece | address | fact |
|---|---|---|
| "?" button handler | SIMUI `0x10026973` | bottom bar child notify, `__thiscall(bar, type, id)`, `ret 8`, `this` unused. For `(1, 0x52fb5feb)`: COM directory `FUN_10014b0d(&dir)` (fastcall), `dir vt+0xc(0x339da69, 0x6856f7, &tool)`, `FUN_10065c35(0xc)` (cdecl), `tool vt+0x2c()` select, `tool vt+8()` Release, `FUN_10014b2e(&dir)` `[CONFIRMED @ SIMUI 0x10026973, disassembly]` |
| query tool class | SIMGEOM ctor `0x1000b1ec` | object +0 vtable `0x1002984c`, +0x58 `0x100298a8`, +0x5c `0x10029838` `[CONFIRMED @ SIMGEOM 0x1000b1ec]`. The directory hands back the +0x58 interface (measured: iface = object + 0x58) |
| select | +0x58 iface vt+0x2c = `0x1000b68f` | -> `FUN_10021325(tool, view)`: view = `FUN_1001be16()` (app vt+0x74), `view vt+0x58(tool)` |
| Apply | slot +0x48 of `0x1002984c` = `0x1000b6b4` | `__thiscall(tool, LONG *coord)`, coord 8.8 fixed (cell = `>> 8`), `ret 4` `[CONFIRMED @ SIMGEOM 0x1000b6b4]`. Makes query command CLSID `0x816c8928` (SIMUI factory `0x10011f0b`, ctor `0x10010bb3`) and calls its vt+0x2c `0x10010c10` -> vt+0x38 `0x10010c39` |
| object lookup | SIMUI `0x10010c39` | `__thiscall(cmd, int cell[2], 0, 0)`, `ret 0xc`. Occupant manager = `FUN_1008e800()` vt+0x88 (the view's, so pipes and subway in the underground view), vt+0x6c(x, z) in-bounds, vt+0x7c(x, z, &occ) AddRef'd; with an occupant `occ vt+0x90(&dlg)` then `dlg vt+0x14(occ, 0)`, else a point dialog (0x57a) `[CONFIRMED @ SIMUI 0x10010c39]` |
| current tool | city view (SIMSPR vtable `+0x67894`) `+0x228` | our query tool while selected, gone after Esc or a menu click (measured, Frida read-only, 2026-10-30) |

Measured call chain (Frida backtrace, "?" then a map click on Berlin): `create clsid=0x339da69` from `SIMUI+0x269bb`;
map click -> `SIMGEOM+0xb6e7` creates `0x816c8928` -> `SIMGEOM+0xb820` calls `0x10010c10` -> `0x10010c39` cell
(84, 114).

Stock behaviour measured on the way: Esc deselects the query tool (a map click after it opens nothing). A right-click
does NOT end it (a click after it still opens a dialog), and in this game a right-click re-centres the camera. A
menu click also deselects it.

Trap: the tool object's +8 (the view, set by `FUN_10021325`) is NOT cleared on deselect. It read 0 in the first
measurement only because the stock tool had been freed and its memory reused. With our reference held it keeps the
view pointer, so "is the picker on" must read the view's +0x228.

## 2. What the mod does

1. Start (button, Ctrl+F): the same sequence as `0x10026973`, but the reference from the directory is kept. The three
   calls are anchored by their rel32 targets and the pushed CLSID inside `0x10026973` before install.
2. The Apply slot (`0x1002984c` +0x48) is wrapped. A call on OUR instance does the lookup `0x10010c39` does and opens
   no dialog. Every other query tool (the stock "?") goes to the original.
3. The picked tool is started 250 ms later from a thread timer (the RELOCATE trap: the same click's button-up must not
   reach the new tool), then our reference is released.
4. Esc is the game's own. A right-click (press and release within 5 px) while the picker is on is turned into the
   game's Esc (posted `WM_KEYDOWN` / `WM_KEYUP` VK_ESCAPE).
5. Messages (since pickerui only after a click that picks nothing, none at the start): a box drawn into the presented frame in the Blt hook, saved / drawn with GetDC / restored after the Blt
   (sc3perf's counter recipe), 2.5 s, at the HUD factor. FRAMEDUMP sees it.
6. Button: an 18x20 four-frame image (drawn by the mod, format from the rotate art `{0x2f78c6d, 0x22f96e30}`), added in
   the minimap panel's Init `FUN_1004faec` and answered in its child notify `FUN_1005093f` through entry detours (both
   start `mov eax, imm32`), so they chain with sc3undo's vtable wrap of the same two slots. Position (10, h - 22), the
   row of sc3undo's arrows, left of the anticlockwise rotate button. The click is posted to the window and run there.

## 3. Object -> tool

| object | test | tool |
|---|---|---|
| network piece | occupant vtable is one of the 22 SIMNTWRK piece classes (`qi_piece_vt2`) | GeomFlag bits: 0x200000 On-ramps `0x10004302`, 0x10000 Highway `0x10004301`, 0x8000 Roads `0x10004001`, 0x20000 Rail `0x10004101`, 0x400000 Wires `0x10005001`; else TilingRules set membership (ROAD/HWAY/RAIL/SUBW/PIPE/POWR); else type 17300 Pipes `0x10005003`, 17400 Subway `0x10004201` |
| tree | GeomFlag == 0x404 | Place Trees `0x10002001` |
| grown building (also abandoned) | GeomFlag 0x100, zone byte under its first cell 1..11 | that zone tool: Res `0x10003101..3`, Com `0x10003201..3`, Ind `0x10003301..3` |
| seaport / airport / landfill building | zone byte 15 / 14 / 17 | `0x10003005` / `0x10003006` / `0x10003004` |
| reward, business deal, landmark | `rl_movable` (`[REWARD_BUILDINGS]`, `[BUSINESS_DEAL_BUILDINGS]`, types 18001..18999) | none: "solo uno por ciudad" |
| abandoned lot | type 15100 | none: "esto no tiene herramienta de construccion" |
| any other building (plopped, zone 22 or 0) | GeomFlag 0x100 | building layer (city vt+0x138) +0x70(own key, oneShot 0, free 0, 0x6856f7, &tool), tool vt+0x2c. Own key = 3 dwords 0x10 before the occupant's first field target when its first two match the attrib key, else the attrib key |
| zoned lot, no occupant | zone byte 1..17 with a command | the zone tool |
| water, no occupant | DirtBag vt+0x54 | Place Water `0x10002002` |
| anything else | | none: "no hay nada para copiar aqui" / "esto no tiene herramienta de construccion" |

Why GeomFlag and not the type id for networks: one type id per network does not hold. The Berlin census
(`verify/relocate/census_berlin.json`) has road pieces with 16000 / 16003 / 16004 / 16011, rail 17000..17004,
highway 16001 / 17202..17204, power 12103 / 12104 / 17100 / 17105 / 17106, crossings 16014. The flag bits per class:
road `0xc804`, highway `0x14804`, highway over road `0x1c804`, on-ramps `0x214804` / `0x21c804`, rail `0x24804`,
road x rail `0x2c804`, highway over rail `0x34804`, power `0x400804`, power over road `0x40c804`; measured in game:
pipe `0x800804`, subway `0x44804`.

netmod pieces (avenues, boulevards, roundabouts, diagonals, junction variants) are road pieces made by road drags, so
they pick Roads (measured: "Avenida (un sentido)", type 16000, flags `0xc804`).

## 4. Owner calls taken as defaults

1. Rewards, landmarks and business deals pick nothing ("solo uno por ciudad"): their building tool would place a second
   copy the menus never offer.
2. Buildings that no menu offers (Berlin's "El Muro", type 1000, 1,241 pieces on zone 22) DO get their building tool.
   The owner asked for "anything selectable"; flip it by adding the type to the refusal rule.
3. Highway interchange templates (sc3netmod TMPL) pick the Highway tool, not template mode.

## 5. Not covered

- Real Ctrl+F from the keyboard (tests fake GetKeyState(VK_CONTROL) with Frida and post the key).
- A real cursor click on the button (posted clicks only). Hold-to-drag behaviour of the picked tools is the game's.
- Ctrl+F while a text field has focus is left to the field (`rz_text_focus`), not tested.
- Cities other than Berlin, 1024 cities, an English install (strings switch through `ho_spanish`).

## 6. Round pickerui (2026-10-31, owner feedback on the released picker)

| owner item | change | where |
|---|---|---|
| "remove the top banner with the eyedropper" | no message when the picker starts or is started again. The short messages after a click that picks nothing stay (2.5 s) | `pkr_start` |
| "a very similar icon in the same style as the cursor" | eyedropper cursor while the picker is the active tool | `pkr_cursor_install`, `pkr_setcursor` |
| "shading like the other buttons of the panel" | button art built from the minimap's own zoom-out button | `pkr_strip`, `pkr_from_minus` |
| "closes after picking the first element" | already the behaviour: a successful pick releases the picker (`pkr_drop("picked")`), measured again | `pkr_timer` |
| tooltip under the panel (picture) | RCIFIX re-blits only the RCI's overhang band | `rz_repaint_rci` |

**Cursor.** The game's tool cursors are monochrome `.cur` files under `Apps\Res\UI\Shared\Cursors\` (32x32, the arrow
top left with the hotspot at (0,0), a black / white picture beside it), loaded with `LoadCursorFromFileA` and set with
`SetCursor` `[CONFIRMED @ SC3U 0x0047cf0f, 0x0047d159]`. The query tool's is `QUERY CURSOR.cur`. The eyedropper is drawn
in that style (ASCII art `pkr_cur_art`), written once to `%TEMP%\sc3resize_picker_eyedropper.cur` and loaded with the
same call, so Windows gives it the size it gives the game's cursors. Measured on this PC: both load as 64x64 (masks
64x128), not 32x32. `SetCursor` is redirected in SC3U, SIMSPR, GZWIND, GZGraphicD, SIMUI and SIMCITY (3 import slots
found; PANCURSOR chains on top of it). While `pkr_active()`, a cursor whose masks equal `QUERY CURSOR.cur`'s becomes the
eyedropper. The stock "?" tool keeps its cursor.

**Button art.** `{0x2f78c6d, 0x22f96e2e}` is the zoom-out button, a 104x29 strip of four 26x29 frames: 0 greyed, 1
normal, 2 pressed, 3 hover (measured: the zoom and rotate buttons show frame 1, sc3undo's greyed arrows frame 0, the
hovered picker button frame 3). Its glyph is a bar at rows 10..12, columns 6..18. The bar is replaced by the face rows 9
and 13, the eyedropper glyph is laid over the face in the bar's colour (4x4 subsamples), and the strip is shrunk to
18x20 with sc3undo's box filter. The button is set enabled (`win vt+0xf4(2, 1)`), so it shows frame 1 like its
neighbours. Before this round it showed frame 0. The old drawn art stays as the fallback when the zoom-out art is not
that strip.

**Tooltip.** The game's tooltip (SC3U class `0x4d3bcc`, root child) is placed centred above the button, so for a button at
panel x 10 it reaches 41 px left of the panel, over the RCI gauge (`[599 520 640 608]` at 800x600). RCIFIX (sc3resize,
`rz_repaint_rci`) re-blitted the whole RCI at present time, after everything, which drew the gauge over the tooltip. Only
the band above the bar's top needs it (the city covers that band, RCIFIX's reason), so the re-blit is now limited to
that band (`SC3RESIZE_RCIFIX_BAND=0` brings back the whole re-blit). Below the bar's top the game's own order is right.
Any other tooltip over the lower RCI had the same problem.

