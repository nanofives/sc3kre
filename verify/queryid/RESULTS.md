# queryid results (2026-10-12)

Pre-registration: `PRE.md`. Spec: `re/analysis/QUERY_ID.md`. Instance `re/harness/inst_queryid` (MAIN), city
`berlin_q.sc3` = `Cities\Berlin, Germany.sc3` (SHA-256 `99327775...`, loaded paused, nothing built or demolished, so
the loaded file is the saved state). Driving: posted input only (`sc3io`), camera moved with minimap clicks, the
clipboard read back with Win32 after each click. Block files: `verify/queryid/blocks*/` (MAIN, not committed).

Display: awake until about 19:40, asleep after (taskbar clock frozen at 19:40 at 19:55, game window white). Screenshots
exist for mode 2 dialogs only; the other modes were checked from the logged child rects. Clipboard and log checks do not
need the display.

## Verdicts

| # | prediction | result |
|---|------------|--------|
| P0 | button in every dialog, inside, not covering game controls | **PASS.** All four modes seen (0 network piece 308x280-class, 1 terrain/water 308x280, 2 building 308x395, 3 large building 423x320). Button local rects: modes 0/1 `[158 243 250 276]`, mode 2 `[158 358 250 391]`, mode 3 `[273 283 365 316]`. Game controls on that row: OK `[258 243 300 275]` / `[258 358 300 390]` / `[373 283 415 315]`, "Declarar historico" `[20 370 141 387]` (mode 2) and `[138 295 259 312]` (mode 3), "Sustituir" `[20 337 99 370]`. No overlap. Visual: `blocks_r1/bldg_parking.png` (mode 2, caption "Copiar ID" in the game's button style). Modes 0, 1, 3 visual check pending (display asleep). |
| P1 | one click = clipboard, dialog still usable | **PASS.** 52 clicks, 52 `QUERYID> copied`, clipboard text equal to the log every time; the driver closed every dialog with the game's OK afterwards; no fault, no crash over four launches. Click arrives as message 3 with p3 2 (press), 1 (click), 17; only p3 1 copies. |
| P2 | network words = save tile word0/word1 | **PARTIAL, prediction wrong for word1.** word0 equal on every piece (road 29, 11204, rail 44, crossing 69, highway 11223/15026/15098, power 10033/16063). word1: low 16 bits (piece id) equal, high half not (runtime 0, save `0x3000` on Berlin roads): the saver writes a layer-side record (`SIMNTWRK 0x1000d594`). The block keeps word0 and the piece id as confirmed and prints word1 raw. |
| P3 | sets: road ROAD only, crossing ROAD + RAIL | **PASS.** 29 ROAD, 11204 ROAD, 44 RAIL, 69 ROAD RAIL, 11223 and 15026 HWAY, 15098 ROAD HWAY, 10033 and 16063 POWR; each equals the `*_GRND_Set.txt` files read offline. |
| P4 | piece attrib key = `{0xe223741f, 0xa317745f, id}` | **PASS** (road 29 -> `...0000001D`, every piece). |
| P5 | building TypeId = save +8, attrib key = save +12 | **TypeId PASS** (12 buildings incl. pump 12810, coal plant 12111). **attrib key: 11 of 12, prediction wrong for abandoned buildings**: the abandoned Industrial Lab's attrib is `0xAD` "Abandoned Industrial Building", the save keeps `0xA4` "Industrial Lab". A read-only memory scan found the own key 0x10 before the pointer in the occupant's first field; printed as `object.key`, it equals the save key on all 12, the abandoned one included. `object.attrib_key` stays, as "the look in use". |
| P6 | building cell = save position | **PASS** (12/12), also size (footprint) and rotation 12/12. |
| P7 | zone = save zone at the cell | **PASS after an index correction.** With `city_write.zone_get(x, z)` only 3/12 matched; with byte `(N-1-x)*N + z` 12/12 (and 18/18 in the second pass). The live value also matched the dialog's own "Tipo de Zona" text. The save tool's frame, not the game value, was off. |
| P8 | water 1 / dry 0 | **PASS** (2 water cells 1, 26 dry 0). Corner heights: 112/112 dry corners equal the save terrain grid at row N-x, column z; on water `vt+0x48` reads the surface (30), `vt+0x4c` the ground (21 22 24 25 = grid). |
| P9 | `SC3RESIZE_QUERYID=0`: no button | **PASS** (log). No detour line, no QUERYID line, a click on the button's spot left a sentinel on the clipboard, game alive. The "off" log line was added after this run. |
| P10 | stock DLLs | **PASS.** Hard-linked stock tree without the release mods (`Simcity_stock_queryid`, protocol section 10), same build (SHA-256 `37224200...` before the last log-line change), same Berlin file. 8 of 8 targets (road, parking, abandoned lab, rail, crossing, coal plant, pump, water), all four dialog modes with the same button rects, 20 copies, `query_id_check.py` 32 PASS 0 FAIL (`check_stock.txt`). A tips dialog was modal at start; `dismiss_tips.py` closed it (and unticks "show tips at startup", a shared registry preference). |

`re/tools/query_id_check.py` on the second pass (final format, 18 objects): 72 PASS, 0 FAIL (`check_r2.txt`).

## Objects covered (second pass)

road 29 "Carretera", avenue piece 11204 "Avenida" (first pass), rail 44 "Via Ferroviaria", level crossing 69
"Paso a Nivel", highway 11223 / 15026 / 15098 "Autopista", power lines 10033 and 16063 (over water), coal plant 12111,
water pump 12810, zoned R 3900 and C 6100 lots, industrial 8100 / 8700 incl. one abandoned, landmark "El Muro" (1000),
flora "Cinco pinos negros" (not in the SIMGEOM occupant section, so not save-checked), open water, a dry slope.
Not covered: pipes and subway (need the underground view; the save shows they share cells with roads, the query on a
road cell returns the surface piece), a 1024 city.
