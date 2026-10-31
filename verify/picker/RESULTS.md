# picker results (2026-10-30)

Owner request: "Add a picker tool (also Ctrl+F) to pick a selected building/road/entity that's selectable."
Spec: `re/analysis/PICKER.md`. Code: sc3resize block PICKER, off switch `SC3RESIZE_PICKER=0`.
Tree `dev/picker/tree` (base `stage/release`), all 8 mods from `dev/picker/inst`, Berlin, 800x600 windowed, posted
input only (sc3io), frames through SC3RESIZE_FRAMEDUMP. Pictures: `MAIN/verify/picker/owner_shots/`.
Runs and logs: `MAIN/verify/picker/runs/<tag>/` (final build: `final`, off switch: `off`).

Verification method: after every pick a test message logs the city view's current tool (view +0x228) as module+RVA,
plus its item: zone tools their zone byte (+0x124), building tools their key (+0x108).

## Verdicts

| # | check | result |
|---|---|---|
| 1 | button on the minimap, next to sc3undo's arrows | **PASS.** Bottom-left corner (10, 142), 18x20, tooltip "Cuentagotas (Ctrl+F)". Undo arrows unchanged. `01_minimap_button.png` |
| 2 | button starts the picker, message shown | **PASS.** Current tool = query tool SIMGEOM+0x2984C (ours). `02_picker_on_message.png` |
| 3 | grown building | **PASS.** Molino (type 9100, zone 11) -> Ind High `0x10003303`, tool SIMRCI+0x4C06C, zone byte 11. `03_...` |
| 4 | road | **PASS.** Carretera -> Roads, tool SIMNTWRK+0x2BEF8. `04_picked_road_tool.png` |
| 5 | nothing to pick: message, picker stays on | **PASS.** Empty cell (73, 99): "no hay nada para copiar aqui", current tool still the picker. `05_nothing_here_message.png` |
| 6 | zoned empty lot | **PASS.** Zoned Res Low with the sim paused (a house grew within 1 s while running, which then picked Res Low too): "zoned lot" -> `0x10003101`. `06_picked_zoned_lot.png` |
| 7 | Esc ends it | **PASS.** Current tool none, a click after it picks nothing and opens nothing |
| 8 | right-click ends it | **PASS.** "right-click: cancelled", current tool none |
| 9 | stock "?" untouched | **PASS.** Dialog opens (El Muro), no PICKER line. `07_stock_query_untouched.png` |
| 10 | Ctrl+F handler (test message) | **PASS** |
| 11 | Ctrl+F as a posted WM_KEYDOWN 'F', GetKeyState(VK_CONTROL) faked by Frida | **PASS.** "Ctrl+F: query tool ... active as picker" |
| 12 | 26 object classes, direct picks (`picker_batch.py`) | **26/26 PASS**, table below |
| 13 | a picked building tool places | **PASS.** Small Park picked (key 0x207EDC0E 0x0000057E 0x0000000D), clicked on empty land: park placed, funds 117,006 -> 116,906 ($100). `08_...png` |
| 14 | 1600x900, HUD 1.5x | **PASS.** Button and message scale with the HUD; a click on the enlarged button starts the picker. `09_1600x900_hud_1.5x.png` |
| 15 | underground: pipe and subway | **PASS.** Pipe (2, 17) -> Pipes, tool SIMNTWRK+0x2C328. Subway (2, 78) -> Subway, tool SIMNTWRK+0x2C0F0. `10_underground_pipe_picked.png` |
| 16 | off switch | **PASS.** `SC3RESIZE_PICKER=0`: log "PICKER> off", no button, Ctrl+F test message ignored |
| 17 | faults | none from this block. One `VEH FAULT 0xC0000096 at SC3U.exe+0x84122` at 24..920 ms is in every run, including the first one on the untouched DLL (t1) |

## Direct picks (final build, `runs/final/batch.txt`)

| object (cell) | picked as | active tool after |
|---|---|---|
| Jardines del Buen Corazon, 3900, zone 2 (103, 0) | Res Medium `0x10003102` | SIMRCI+0x4C06C, zone 2 |
| Emporio Veo y Quiero, 5700, zone 6 (118, 28) | Com Medium `0x10003202` | SIMRCI+0x4C06C, zone 6 |
| industrial 8700, zone 11 (118, 17) | Ind High `0x10003303` | SIMRCI+0x4C06C, zone 11 |
| road end (106, 0) | Roads | SIMNTWRK+0x2BEF8 |
| highway (34, 12) | Highway | SIMNTWRK+0x2BFA0 |
| rail 17002 (203, 16) | Rail | SIMNTWRK+0x2C048 |
| power line 12103 (9, 0) | Wires | SIMNTWRK+0x2C280 |
| level crossing 16014 (204, 24) | Roads | SIMNTWRK+0x2BEF8 |
| on-ramp 17202 (7, 13) | On-ramps | SIMNTWRK+0x2C1D8 |
| trees (6, 0) | Place Trees | SIMGEOM+0x298F4 |
| coal plant 12111 (51, 73) | building key 0xCF | SIMGEOM+0x29504, key 0xCF |
| water pump 12810 (133, 9) | building key 0xDC | SIMGEOM+0x295E4 (plumbing tool), key 0xDC |
| school 13010 (65, 16) | building key 0x1F94 | SIMGEOM+0x29504 |
| train station 12230 (201, 16) | building key 0xED | SIMGEOM+0x29504 |
| subway station 12360 (73, 20) | building key 0xE9 | SIMGEOM+0x2968C (subway tool) |
| fire station 13002 (207, 29) | building key 0xD3 | SIMGEOM+0x29504 |
| small park 14311 (117, 2) | building key 0x0D | SIMGEOM+0x29504 |
| seaport building 12330, zone 15 (122, 6) | Seaport zone `0x10003005` | SIMRCI+0x4C06C, zone 15 |
| airport hangar 12310, zone 14 (154, 34) | Airport zone `0x10003006` | SIMRCI+0x4C06C, zone 14 |
| prison 19004 (business deal) (29, 81) | refused, "solo uno por ciudad" | none |
| Rotes Rathaus 18010 (landmark) (214, 76) | refused, "solo uno por ciudad" | none |
| El Muro 1000, zone 22 (0, 42) | building key 0x2D36 | SIMGEOM+0x29504 |
| abandoned lot 15100 (1, 43) | refused, "esto no tiene herramienta" | picker stays |
| water (246, 8) | Place Water | |
| power line over water 17106 (155, 158) | Wires | SIMNTWRK+0x2C280 |
| empty land (33, 20) | refused, "no hay nada para copiar aqui" | picker stays |

Seen in passing: a netmod one-way avenue piece ("Avenida (un sentido)", type 16000) picked Roads.

## Needs owner check

- Real Ctrl+F on the keyboard.
- A real mouse click on the minimap button and on the city (all clicks here were posted).
- Owner calls taken as defaults (PICKER.md section 4): rewards / landmarks / deals refused; non-menu specials such as
  El Muro pickable; interchange templates pick plain Highway.
