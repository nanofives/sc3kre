# restoreui: results (child restoreui, round 2026-11-02 graphs/restoreui)

Owner asks (round brief, restoreui row) and what was done. Checked in game: dev/restoreui tree, stock "Berlin, Germany",
800x600 windowed, posted input only, frames from SC3RESIZE_FRAMEDUMP. Runs b1 (baseline, before) and t1..t7 under
`verify/restoreui/runs/`. Pictures for the owner: `verify/restoreui/owner_shots/` (local, gitignored).

## Verdict

| # | ask | done | checked in game |
|---|---|---|---|
| 1 | "Vida útil" an icon, as tall as the X | Image button cut from the close box's own art (24x25 frames, the X's size): the minimise frames with the bar replaced by an hourglass, all 4 state frames, tooltip "Vida útil". Placed 6 px left of the X, same top | icon shown (07, 08), its click opens the list (t4, t5, t6) |
| 2 | restore cheaper | `restore.ini [restore] cost_percent=50` beside sc3restore.dll, default 50 with no file, `SC3RESTORE_COSTPCT` overrides | coal plant 235 of 939 months, price 5000: cost §626 (was §1,251); restore charged 117,006 -> 116,386 = §620 at 233 months |
| 3 | list buttons narrower, light blue unbroken behind them and in the footer gaps | Row buttons 92 wide (were 132) reading "Restaurar", the price on the row's second line, "decae" on the first. Boxes butted: rows 33 apart, footer edge to edge from x 8 to w - 8 | 09, 10 (one blue column, one blue strip), compare 00_before_list_zoom |
| 4a | "Sustituir" same font as the other buttons | The template button is hidden and a factory text button (the "Copiar ID" recipe) takes its place: id 4, same rect, same enabled flag, same caption | 01, 03, 04, 06 |
| 4b | "Como nuevo" grey, not clickable | Disabled (window vt+0xf4(2, 0)) in the query dialog ("Como nuevo" and "Restaurado ($N)") and in the list ("Nuevo", "Como nuevo" did not fit 92 px) | 02, 11 |
| 5 | more data in the "?" dialog | rows below, the dialog grows to show them | 01, 03, 04; a zoned building gets none (06) |

## Query dialog rows (QROWS)

Added through the dialog's own row list (qo+0x100, QI 0x583, vt+0x4c FUN_100645bf, flags 0x20000), so they take the
game's layout and colours. Sources from `re/sessions/restoreui_query_rows_research.md` (read-only research of this
round).

| row (es / en) | shown for | value | source |
|---|---|---|---|
| Coste de obra / Build cost | every building with a build price | budget vt+0x54(type id) | city vt+0x15c budget, SIMGEOM 0x100072f6 (the building tool's price) `[CONFIRMED]` |
| Decae desde / Declines from | every building with a lifespan | DeclineAge, "(ya decae)" once age passes it | IBuildingMortal 0x43680ca9 vt+0x18, RESTORE.md `[CONFIRMED @ SIMUTIL 0x10006b63]` |
| Vida restante / Life left | same | MaxAge - age | vt+0x10, vt+0x1c `[CONFIRMED @ SIMUTIL 0x10006b6f, 0x100120a1]` |
| Rendimiento / Output | SIMUTIL power plants | output / base, percent | mortal vt+0x3c (+8) / vt+0x38 (+0xc), derated from DeclineAge `[CONFIRMED @ SIMUTIL 0x100069fb]` |
| Meses en sobrecarga / Months overworked | SIMUTIL power plants | u16 at mortal+0x10 | breakdown test `[CONFIRMED @ SIMUTIL 0x10006c27]` |
| Camas (este) / Beds (this one) | hospital, occupant vtable SIMRCI+0x4b548 | u32 occ+0x24 | `[CONFIRMED @ SIMRCI 0x1000790d, 0x10006c12]` |
| Médicos (este) / Doctors (this one) | hospital | u32 occ+0x28 | same |
| Profesores (esta) / Teachers (this one) | school, SIMRCI+0x4be08 | u32 occ+0x24 | `[CONFIRMED @ SIMRCI 0x1000b726]` |
| Profesores (esta) / Professors (this one) | college, SIMRCI+0x4b2a8 | u32 occ+0x24 | `[CONFIRMED @ SIMRCI 0x100063c6]` |

The game's own hospital and school rows are the systemwide totals (city vt+0x17c); these are the building's own. Measured:
coal plant 5 rows (5,000, 62a 7m, 58a 10m, 100%, 0), hospital 1500 beds / 115 doctors (systemwide 39,000 / 2,990),
college 173 professors (systemwide 1,038). The three occupant vtables were confirmed by a map scan (test message
WM_RZ_RESTORE 7): hospital at (201, 29), school at (65, 16), college at (117, 66).

The dialog does not grow for rows added after its build (measured: rows accepted, none drawn, the list ends under the
restore button). QROWS grows it: the row list window (SIMUI+0xAAF64) by 14 px a row, the children below it move down,
plus one button row when RESTORE or RELOCATE puts a button above the bottom row. Coal plant 308x395 -> 308x504.

Not added, kept for a later round (research section 3): commute result of a lot (A) and power drawn (B) need one live
check of the (x, z) argument order; raw land value / crime 0..255 (C) need the layer pointer compared once; fire/police
coverage (H) has the police layout from its ctor only. Not available per building at all: population or jobs of an
R/C/I building, age of an R/C/I building, per-building upkeep of plants.

## Off switches (all checked together in t7)

`SC3RESIZE_RSICON=0`, `SC3RESIZE_RSLAYOUT=0`, `SC3RESIZE_RSGREY=0`, `SC3RESIZE_SUSTFONT=0`, `SC3RESIZE_QROWS=0`: the
query dialog and the list come back exactly as on 11-02 (text "Vida util" button, "Restaurar $N" buttons, the game's
"Sustituir", no extra rows). The cost factor is sc3restore's: `SC3RESTORE_COSTPCT=100` or `cost_percent=100` gives the
11-02 price.

## Notes for the merge

- `restore.ini` is not shipped: with no file the cost is 50%. Ship one only if the owner wants the key visible.
- A dialog whose game rows already overflow (school, college: the game shows a scrollbar) grows by our rows only and
  still scrolls.
- The hourglass is drawn at 24x25 like the X; picture 08 is 4x.
- Never shown: "Sin fondos" captions (unchanged code path).

## Files

Changed: `re/harness/src/sc3restore.c` (COSTPCT), `re/harness/src/sc3resize_restore.c` (RSICON, RSLAYOUT, RSGREY,
SUSTFONT, QROWS, test message 7), `re/harness/src/sc3resize.c` (switch variables, two hook lines in qi_msg, the qi_install
condition, env parsing), `re/analysis/RESTORE.md` (cost factor, section 3b). New: this file,
`re/sessions/restoreui_query_rows_research.md`, `re/sessions/STATUS_restoreui.md`.
