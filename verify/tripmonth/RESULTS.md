# tripmonth RESULTS (2026-11-03)

Build: `dev\tripmonth\inst\sc3resize.dll` (main 3c92f97 + this stream). Berlin, 800x600 windowed, posted input only
(hover moves, posted VK_SHIFT key messages, rail drags in the unsaved test game), `SC3RESIZE_PLACEHINTS_LOG=1`, frame
dumps. Pictures: `verify\tripmonth\owner_shots\`. Detail and RVAs: `re/analysis/PLACEHINTS.md` F.

## 1. Trip months close from the city load

Before: TRIPCELLS / TRIPMODES closed a month only after the Graficas page had been opened once (`gn_month` gated on
the graph series). Now the budget month hook closes it from the load, with the month key from the same calendar call
the graphs use. The graphs path is the same code as before (the new branch runs only while the series do not exist).

| check | result |
|---|---|
| Berlin, Graficas never opened, sim at speed 4 | `TRIPMODES> month 24805` to `24823`, one per game month from the load, no `GRAPHNEW ... series made` line |
| station label after a few months | "14 viajes al mes" style figures, no longer "desde la carga" |

Not run in game: opening Graficas after some months closed this way (static: the first branch is untouched, and
TRIPCELLS keeps its own month key, so the two keep counting the same months).

## 2. Station preview upgrades

(a) **Somewhere to go.** A train / subway / rail-to-subway station touching a track that reaches no map edge and no
other station with lots in reach is drawn red, label "la vía no lleva a otra estación ni al borde: 0 viajes (rojo)".
Same rule as stationwarn (`sw_flood`), own copy (`ph_station_dest`), since stationwarn was not merged when built.

| case | result | picture |
|---|---|---|
| train station touching the long z=91 line | links 2, dest 1: stock blue footprint | `B1_train_on_connected_line_no_shift.png` |
| train station touching a 4-cell stub laid at (75..78, 99) | links 2, dest 0: footprint red | `B2_train_on_deadend_stub_red.png` |

(b) **Exact per-class reach.** With Shift the area is now the R / C / I lots whose own rect grown by their class
reach (Berlin live R 5, C 4, I 6), corners cut, holds a footprint cell: the trip start scan's test. Roads, civic
buildings and empty land are no longer drawn. Picture: `A1_station_perlot_area_label_before_fix.png` (area right,
the label in that shot is the first, broken, TIPLINES build) and the C shots below.

## 3. Shift label in 2 or 3 lines

Owner: "when pressing shift if the text is too long put it in two or 3 lines". The label is still the game's own
tooltip (same font, same placement below the pointer, same HUD scaling), made able to hold 3 lines. Split at the
"|" groups: 2 lines from 71 characters, 3 from 141, breaks chosen so the longest line is shortest.

| case | result | picture |
|---|---|---|
| train station, Spanish (longest) | 3 lines: cost + name + reach / trips a month / "no toca la vía" | `C1_station_3lines_es.png` |
| Big Park, Spanish | 2 lines | `C2_park_2lines_es.png` |
| airport drag, Spanish | 3 lines | `C3_airport_drag_lines_es.png` |
| train station, German (`SC3MODS_LANG=de`) | 2 lines (shorter than 141), umlauts right | `C4_station_3lines_de.png` |

Off switch `SC3RESIZE_PLACEHINTS_LINES=0` (one line as before), built, not launched.

Bug found and fixed on the way: es.txt on main has "no toca la v355a" (placehints4 used an octal escape that
`sc3lang.py extract` does not read). The source now uses `"v\xed" "a"`; es.txt reads "vía" again.

## Merge against main 41150db

Merged read-only with `git merge-file` per file (nothing written to the repo):
- `sc3resize_graphs.c`, `sc3resize_placehints.c`, `es.txt`, `en.txt`: clean.
- `fr/de/it/nl/sv.txt`: conflict at the end of the file only. Both sides appended a block (mine 3 placehints keys,
  stationwarn's 12 keys). Resolution: keep both. Resolved copies: `verify\tripmonth\lang_resolved_on_main_41150db\`
  (`sc3lang.py check` there: 306 keys = 303 + 3, 0 missing, the 12 "unknown" are stationwarn keys whose source is
  not in this tree). The JSON for my 3 keys is in the same folder (`tr2_<lang>.json`, for `sc3lang.py merge`).

## Not covered / needs owner check

- The physical Shift key (posted key messages only).
- Subway / rail-to-subway stations in game (same code path as the train station; the subway flood uses flag 8).
- `_LINES=0`, opening Graficas after months closed from the load, the full mod set (all mods loaded from this inst).
- HUD scale above 1: the label is the same game window, so COSTLABEL scales it as before; not shot at a scaled HUD.
