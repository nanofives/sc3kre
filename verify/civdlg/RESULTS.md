# civdlg results (round 2026-11-19k): the civic list window

Tree `dev\civdlg\tree`, mods of `dev\civdlg\inst` (main dca2fb0 + this branch), every mod on (sc3mods.log: 11 mod(s)
loaded each run), windowed, started by `pwsh re/scripts/sc3dev.ps1 run civdlg` (wrapper `dev\civdlg\work\launch.sh`).
Posted input only (sc3io via `re/tools/civmod_lab.py`: click, move, key), Frida only for reads (`tool`, `find`) and the
camera (`verify/showcase/cam.py`). Pictures by SC3RESIZE_FRAMEDUMP, PNG, no BMP left. City Madison, WI.

Test data: `make_testmodels.py --civdlg` (new) -> `bldimport.py build --game dev\civdlg\tree`: ids 38000-38004.
Police has three looks (Police blue 0x9470, Police green 0x9471, Police red 0x9472), fire one (0x9473), school one
(0x9474), every other civic button none.

**Verdict.**

- **Built and works through the real menu button.** Pressing Police or Fire in the civic flyout (posted clicks) opens
  "Elegir aspecto": the original first, then the looks, each with its name in the list, the picture, "Precio: §500"
  and "Aspecto i de n". OK arms the stock building tool with the picked key and closes the window. Esc and the close
  box close it with no tool. Hospital (no looks) arms the stock tool with no window.
- **Decision: the stock catalog window, not a new SIMUI window.** It is the rewards / landmarks list itself
  (class `0xe3091435`, driven as SIMUI `0x10011919` drives it), filled with our own items under a mode id no advisor
  answers. That gives the game's look, the building picture, Esc / close / OK and DLGSCALE scaling for free, with no
  SIMUI patch. Evidence and RVAs: `re/analysis/CIVIC_REWARD.md` section 6.
- **Press-to-cycle replaced.** The "Activar mods" page has no free row (both columns full), so the cycle is not a page
  option. It stays reachable only as the off-switch `SC3RESIZE_CIVDLG=0` / `sc3resize.ini [buildings] civiclist=0`
  (measured below). The "Civicos: varios aspectos" row is unchanged: off = stock buttons, no window.

## 1. The window

| check | result |
|---|---|
| install | `CIVVAR> on: 3 civic button(s) with 5 variant look(s) (SIMGEOM+0xb1a3)`, `CIVDLG> on: a civic button with looks opens the list window (stock catalog dialog, SIMGEOM+0x2920c)` |
| Police button (civic flyout, posted clicks) | `CIVDLG> entry 0..3: key 0x57E 0xD2 / 0xB1D10002 0x9470 / 0x9471 / 0x9472, type 13130, price 500`, `list window open, 4 entries, entry 0 selected`, `entry 0 selected (list ok)` |
| scale Normal (SC3RESIZE_HUDSCALE=0, 1600x1000) | native size 370x412, title "Elegir aspecto", "Comisaría" selected with the stock picture, "Precio: §500", "Aspecto 1 de 4", "El edificio original del juego." (owner_shots 01); Police red selected: its own picture, "Aspecto 4 de 4" (02) |
| scale 200% (SC3RESIZE_HUDSCALE=200, 1600x1000) | the same window at 2x (DLGSCALE), list rows and OK clicked at their scaled spots (04, 05) |
| 800x600, Auto | the same window; first run, before the title fix: title empty (11). Fixed: the builder writes the caption in its create message inside DoModalWin, so the caption is now set from the frame heartbeat |
| pictures | the stock police station, and each imported look's own art (blue, green, red) drawn by the dialog's preview (02, 05, 11) |
| Fire button | "Estación de bomberos", "Fire orange", "Aspecto 1 de 2", price §500 (03) |
| last pick | reopened after picking Police blue: `entry 1 selected` (the last pick is preselected) |
| frame time with the window open | 8-15 fps (67-168 ms/frame), the same range as the stock Rewards list (civmod owner_shots 06: 15 fps): the dialog's text redraw, known since DLGSCALE |

## 2. Pick and place, each entry of the police button

All at scale 200% except the first blue (800x600 Auto). After each OK: `CIVDLG> base 0xD2: picked entry k of 4 (<name>)`,
then `CIVVAR> button of base 0xD2: look k of 4, <name>, key ...`, and `civmod_lab.py tool` read the city view's tool.

| entry | tool after OK | label at the pointer | placed (`find 13130`) |
|---|---|---|---|
| 1 Comisaría (original) | SIMGEOM+0x29504, key `0x57E 0xD2`, oneshot 0 | (stock) | (207..209, 198..200), flags 0x104 |
| 2 Police blue | SIMGEOM+0x29504, key `0xB1D10002 0x9470`, oneshot 0 | "Aspecto 2 de 4: Police blue \| §500" | first run (191..193, 203..205), funds 109,073 -> 108,573; second run (207..209, 209..211) |
| 3 Police green | key `0xB1D10002 0x9471`, oneshot 0 | "Aspecto 3 de 4: Police green \| §500" (06) | (191..193, 204..206) |
| 4 Police red | key `0xB1D10002 0x9472`, oneshot 0 | - | (202..204, 198..200) |

All four type 13130. Picture of the four: owner_shots 07. The tool stays armed after a placement, as the stock civic
tool does (one-shot 0). One click on a site under power lines was refused by the stock site check (red footprint); the
next on open ground placed. Not a CIVDLG matter.

## 3. No tool, no window

| check | result |
|---|---|
| Esc (posted VK 0x1B) with the window open | `window closed without a pick (Esc / close): no tool`, tool read: null (09) |
| close box (posted click on the X) | the same line, tool null (Police, run 1 and Normal run) |
| Fire window, Esc | the same, tool null |
| Hospital button (no looks), real menu click | tool `0x57E 0xD1` stock, no CIVDLG line written (count 13 before and after) (10) |
| Hospital hotkey 0x1A (civmod_lab hotkey) | tool `0x57E 0xD1`, no CIVDLG line |

## 4. Save and reload

The 5-minute autosave after the four placements (`Madison, WI (auto 5 min).sc3`, copied to `tree\Cities\civdlg_saved.sc3`)
read with `re/tools/occupant_layer.py`: `207edc0e/b1d10002` x3 at (191,204) 0x9471, (202,198) 0x9472, (207,209) 0x9470,
and `0x57e/0xd2` at (207,198), all 3x3. Loaded in a new game (scale Normal): `find 13130` gives the same four keys
at the same cells, picture owner_shots 08. The window then opened as before (01-03).

## 5. Off-switch

`SC3RESIZE_CIVDLG=0`: `CIVDLG> off (...): presses cycle the looks`; three hotkey presses 0x18 logged `look 1 of 4, stock`,
`look 2 of 4, Police blue`, `look 3 of 4, Police green`: the shipped cycle.

## 6. Faults

Every run (PIDs 952, 8948, 6776, 20448, 17196, all started by this session and stopped by PID): the only VEH FAULT
after the fix is the start-up `0xC0000096 at SC3U.exe+0x84122`. Run 952 (the first build) also had
`0xC0000005 at SIMUI.DLL+0x690EF`: my selection call before DoModalWin (cause and fix in CIVIC_REWARD.md 6.1); caught
by CIVDLG's handler, logged `fault ... no tool`. Not seen after the fix.

## 7. Text

5 new keys (`resize.cd_title`, `cd_price`, `cd_lookn`, `cd_desc_stock`, `cd_desc_look`): `sc3lang.py extract` (es,
en), `merge` fr / de / it / nl / sv (machine translation, marked for review as the others), `check`: 357 keys in all 7
tables, 0 missing, 0 format mismatches, 0 outside cp1252. Only the Spanish text was seen in game.

## 8. Not run

- The window in the other 6 languages (tables checked, not seen).
- Placing fire and school looks (civtest placed them with the cycle; the pick path is the same `cv_pick` call).
- Double click on an entry (the dialog's own, as in Rewards).
- The cursor over the window with a real mouse (posted clicks only).

Lab scripts (not for commit): `dev\civdlg\work\launch.sh`, `camgo.py`, `pick_place.sh`, `lang\*.json`.
