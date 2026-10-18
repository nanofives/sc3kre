# avx: straight avenue intersections (2026-10-17)

Owner ask (via the avenue program orchestrator): avenue intersections with a paved box, crosswalks on every arm, medians
ending in a concrete nose, curbs continuous. Built: sc3netmod AVX block, package `examples/avenue_junctions`
(ids 20800..20804, 20810, 20811), offline twin `re/tools/netmod/avx.py`. Owner pictures (untracked):
`MAIN\verify\avx\owner_shots\avx_mockup.png` (offline, stock vs avx) and `avx_sheet.png` (game).

## Stock today (offline tiler, `avx.py check --tiler -v`)

| Shape | Stock pieces |
|---|---|
| avenue x avenue | 2x2 of 43, T 39 on the four arm cells beside it (four small crossings, medians stop one cell early) |
| avenue T | 39 39 on the near half, the through avenue's far half stays 11204 (median runs through) |
| road x avenue | a column of two 43, the avenue's 11204 halves run up to it |
| road T | 39.3 on the near half, 11204 on the far half |

## Design

Box cells by edge pattern (N E S W, each I / A / C): 5 canonical patterns cover all four kinds in all rotations
(20800 AIIA, 20801 AAIA, 20802 IACA, 20803 IACI, 20804 IICA). The three with a closed side have it on S at state 0,
so their state equals the 11204 state of that half and they save as 11204. Arm cells beside the box: 20810 / 20811,
11204 with the median grass within 32 lane units of the box end repainted as road 29's sidewalk at the same point
(trees and everything else stock). Box art per pixel: 29's curb band on a closed side; 43's corner block where two arms
meet; 43's own crosswalk pixels within 40 units of an arm edge (sampled clear of the other edges' lines); else 43's
asphalt mirrored about the cell middle (`fold`, the same value at every cell edge, so box cells meet whatever their
states). Lanes: 43's for 20800 / 20801, T 39 state 1 for the closed-side cells, 11204's for the nose cells.

## Offline

- `avx.py check --tiler`: 16 of 16 kind x rotation drawings convert to their kind; 24 of 24 shapes owned by others are
  refused (RBT 2x2 roundabout, bigrbt 3x3 with avenue arms, boulevard x road, boulevard x avenue, diagonal avenue x
  avenue, diagonal road x avenue, each in 4 rotations); RBT's rule twin (`rb_auto.check`) qualifies no block on any
  of the four kinds' stock tiles.
- `avx.py scan` (shipped cities, what a load pass would convert): Berlin 188 junctions, London 192, Liverpool 155,
  Madrid 153, Frankfurt 118, Moscow 100, Seoul 114, Sacramento 47, Madison 8, Craterville 8; the rest none.

## Game (Simcity_stock_avx, inst_avx, lab city copies)

| Step | Result |
|---|---|
| Run 1 (pid 57992): avenue x avenue drawn | bug: the junction writes 12 cells, the per-junction buffer held 8 (log showed garbage kind and wants, box cells left 43). Fixed (`AVX_MAX_W` 12), rebuilt |
| Run 2 (pid 42528): avenue (101..115, rows 97/98), avenue cols 103/104 | `avenue x avenue, box from (103,97), 12 written`: 20800.0 20800.1 / 20800.3 20800.2, noses on the 8 arm cells. Grid equals the twin |
| road x = 110 across it | `road x avenue, box from (110,97)`: 20801.0 / 20801.2 + noses |
| road x = 114 from z 99 down | not converted: the avenue ends one cell past it (11203 at 115), so the E arm is 1 cell. Correct per rule |
| road x = 107 from z 91 down to the avenue | `road T, box from (107,97)`: 20801.0 / 20802.0 (far half) + noses |
| patch 2: avenue rows 50/51, avenue cols 16/17 from z 52 | `avenue T, box from (16,50)`: 20803.2 20804.2 / 20800.3 20800.2 + 6 noses |
| Screenshots | zoom 4 views 0 and 1, zoom 3 views 0 and 2: paved boxes, crosswalks, noses, the T's far curb continuous; `avx_sheet.png` |
| Save | `34 variant tile(s) written as base`; offline read of the save: box cells 43, T far halves 11204, noses 11204 |
| Run 3 (pid 58216) reload of that save | `all 34 variant tiles restored`; AVX load pass `4 junction(s), 0 cell(s) written` |
| Bulldoze (107,95), the road T's arm | the T falls back to stock (39.1 + 11204), the same pass re-pieces the avenue x avenue and road x avenue that the stock retile reached |

Logs: no sc3netmod exceptions. All three runs stopped by PID.

## Owner change: white dashed lane lines (2026-10-17)

"On avenues instead of yellow lines they should be white striped lines for every lane" (via the orchestrator). The
nose cells 20810 / 20811 now carry the line as `lanelines.py` specifies (copied unchanged from the diagave worktree):
the 11204 centre line's own pixels (yellowish, lane z 108..148 at state 0) are white where a dash covers the
along-coordinate and 11204's lane asphalt (mirrored out of the band, trees skipped) between dashes; nothing at zoom 0-1.
Phase = lane x / 256, the same as world x for any cell because the 0.25 period divides a cell and dashes are centred.
Road arms (29) keep yellow; box cells have no lane lines. Game check (pid 23212, the saved lab3 reloaded with the
rebuilt art, 34/34 restored, load pass 0 written): dashes on the nose cells at zoom 4 views 0 and 1
(`game_dash_p1_z4_r0.png`, `game_dash_p2_z4_r1.png`). The stock 11204 cells beyond them stay yellow until the
orchestrator's avenue_markings package reskins 11204 / 11203.

## Open

- The median trees of the nose cells are 11204's own and stand up to the box end; at zoom 4 the front trees overhang
  the crosswalk in views where the median faces the camera. Owner call: keep, or drop the tree nearest the box.
- Box asphalt is 43's mirrored about the cell middle: a faint symmetric crease shows at zoom 4.
- Not handled (stay stock): an avenue ending on a single road, junctions closer than 2 cells along an avenue, an
  avenue whose arm is shorter than 2 cells (as the x = 114 T above).
- Lanes are 43's / 39's per box cell (straight and the turns stock offers); not traced with cars in game.
