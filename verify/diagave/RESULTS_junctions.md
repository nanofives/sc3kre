# diagave: junctions (2026-10-17)

Owner: "after that work on junctions". Built: junction-aware band rule (diagave.py `bands`, sc3netmod_dav.c
`dav_pass`), 10 junction pieces 20510..20519 (art + lanes generated), netpack `auto_diagonal_avenues[].junction`
(`davj` table lines). Owner sheet `MAIN\verify\diagave\owner_shots\diagave_junctions.png` (untracked).

## The rule

- Avenue rows are rows whose three footprint cells hold ROAD, whatever is beside them; a chain of them is an avenue
  when at least 3 of its rows have nothing beside them (clean rows, not necessarily consecutive).
- A road beside a row must be a straight arm: along the row (W / E, two cells, nothing above or below them) or along a
  column (N: up from the row's d3 cell, S: down from its d-1 cell). Anything else leaves the avenue to the stock tiler.
- Junction cells: a row arm on one side -> that side's edge cell (T); on both sides -> all three cells (crossing); both
  sides on the chain's first / last row -> a stem (the avenue ends on the road: the road's far curb is kept). A column
  arm from above enters at the d2 cell, from below at the d0 cell; both on one column -> the three cells it crosses.
- Arm cells (two per arm) become straight road 29 so they meet the junction cleanly.
- Junction descriptor = (35 half states in the cell, road 29 orientation, far curb or none), turned by states into one
  of 10 canonical pieces (the C block tries rotations 0..3 against the `davj` table, smallest first, as diagave.py).
- Art: road 29 with the avenue's 35 halves over it as asphalt (29's or 35's own asphalt pixel kept, sidewalks and lane
  lines inside the overlap filled from 29's asphalt), a stem keeps 29's light pixels within 0.22 tile of its far curb.
  Lanes: 29's plus the halves' (straight through on both roads, no turns). Base 43 (saves as a 4-way).

## Offline (diagave.py combos)

32 junction drawings (8 kinds x 2 axes x 2 second-drag offsets): 28 convert. The 4 that do not are stems where the
second drag (offset one cell up) pokes one cell past the road. Shipped cities: 0 tiles change (their double diagonals
meet two-wide avenues, which are not single straight arms).

## Game (Simcity_stock_diagave, inst_dav)

| Step | Result |
|---|---|
| Road row (100..114, 92), then the avenue drags starting on it | `8 row(s), 26 cell(s), 3 junction cell(s), 4 arm cell(s)`: stem row 20515.2 20518.0 20514.0 |
| Road row (100..115, 97) across it | `6 junction cell(s), 8 arm cell(s), 30 written`: crossing row 20510.2 20512.0 20510.0 |
| Other axis avenue, column road x = 18 across it | `3 junction cell(s), 4 arm cell(s)`: 20510.3 20512.1 20510.1 |
| Save, reload with the mod | `all 44 variant tiles restored`; load pass `0 written` on both avenues |
| Road from the east ending at row 95 (T), between the stem and the crossing | `7 junction cell(s), 10 arm cell(s)`: 20510.0 on the edge cell; the avenue still converts (clean rows 5 of 8) |
| Pictures | zoom 3 and 4, rotations 0 to 2: paved crossings, the median ends at junction rows, the stem keeps the road's far curb |

Logs: 0 sc3netmod exceptions; sc3resize only its usual startup entry.

## Open

- Stems where one drag pokes past the road; an avenue ending on a column road at a band end that is not a full
  crossing; avenue x avenue; joining the straight avenue 11204; T or crossing with turning lanes (lanes go straight).
- Bulldozing a junction or arm cell is not re-tested (same revert path as before).
