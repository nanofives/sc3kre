# diagave phase 1: the straight diagonal avenue (2026-10-17)

Built: sc3netmod DAV block (`re/harness/src/sc3netmod_dav.c`, on RBT's retile-pass and city-load hooks), netpack key
`auto_diagonal_avenues` (one `dav <piece> <a> <b> <delta>` line per middle piece), package
`re/tools/netmod/examples/diagonal_avenue` (middle pieces 20500..20504), offline twin + art and lane builder
`re/tools/netmod/diagave.py`. Light test per owner rule: game runs with and without the mod, pictures. Owner sheets:
`MAIN\verify\diagave\owner_shots\diagave_joined.png` (current), `diagave_phase1.png` (round 1, superseded).

## Round 1 (superseded): two carriageways with a tree median, 4 cells per row

The first build treated a band of four cells per row (second drag two cells over) as the avenue: stock 35 on every
cell plus a tree on the terrain strip between the roads. Owner, 2026-10-17: "those two diagonal pieces are not joint,
the ladder should be 3 pieces, not 4". The avenue is the second drag ONE cell over; the stock tiler draws that as a
ladder of 3 pieces per row (11203 curve, 43 4-way, 11203 curve: `diag_probe.py band --shift 1`).

## Design (round 2, joined)

- Stock 35 draws only HALF its diamond (the road strip); the other half shows terrain (frame table 0xC0). In a band of
  three cells per row the middle cell holds the inner half of BOTH roads. Outer cells keep the stock pieces; the
  middle cell becomes a variant: the two stock halves on one tile (seams are stock pixels), and both halves' lane
  records merged into one spec (`lanekit describe` of each, lanes / exits / walks concatenated, connects from the lane
  end sides), rotated by lanekit for states 1..3. Where their sidewalks meet they read as a concrete median.
- Split of the band into staircase A (d 0,1) and B (d 1,2); in the end rows the d 1 cell can be A, B or both: the
  first choice with the fewest "both", then the fewest against the end's preference, that keeps every cell of both
  staircases a lone-staircase mask. Same order in C and Python.
- Middle combinations every drag footprint needs (`diagave.py combos`, 48 footprints: both axes, both step phases of
  each drag, second drag one cell along x or one cell up, lengths 4..6): (35,35,+2) in 92, (18004,35,+0) 4,
  (1999,35,+2) 4, (35,18004,+0) 3, (35,1999,+2) 3. The 24 footprints with no band are drags that land on top of each
  other (different step phases, same staircase), not avenues.
- Tiling-rule route rejected (round 1 measurement): band masks with no conditions changed 1,118 tiles in Berlin and
  773 in London; Simple-stage conditions only see 3x3 cells already placed this pass. The hook checks the exact shape.
- Saves: the middle pieces save as 4-way 43 (`rb_save_id`), not their base 35: a stock 35 there shows only one of
  the two roads (measured: a sawtooth carriageway without the mod), 43 keeps the road continuous.

## Shipped cities (offline, `diagave.py scan`)

37 three-cell diagonal bands (Berlin 16, Frankfurt 9, Madrid 5, Moscow 5, Liverpool 1, Seoul 1): Maxis's city
builders drew joined diagonals often, and the stock tiler shows them as the ladder. All 37 touch other roads, so none
converts and 0 tiles change. They are the case for the junction phase.

## Game runs (Simcity_stock_diagave = hard links of the stock tree, overlay install, inst_dav: sc3netmod + sc3resize)

| Step | Result |
|---|---|
| Load | 5 `dav: middle piece ...` lines, READY, load pass ran, 0 exceptions |
| Drags (102,92)-(110,100) and (103,92)-(111,100) | `band axis 0, 8 full row(s), 26 cell(s), 26 written`: rows 35.2 / 20500.0 / 35.0, top 18004.0 20501.0 35.0, ends 1999.2 1999.2 |
| Drags (22,45)-(14,53) and (22,44)-(14,52) (other axis, second drag one cell up) | `band axis 1, 7 full row(s), 26 cell(s), 26 written`; B ends half a step before A at one end (the split's cheaper choice) |
| Pictures | zoom 3 and 4, two view rotations: joined carriageways, seamless; pedestrians walk the median sidewalks |
| Save (menu 0x10009002) | `save: 15 variant tile(s) written as base, section 0x4E56 written` |
| Reload with the mod | `load: all 15 variant tiles restored`; load pass `0 written` on both bands |
| Save with the 43 override, open WITHOUT sc3netmod | loads; middle cells 43.x: a continuous road, the stock ladder look |

Logs: sc3resize carries only its usual startup entry (0xC0000096 at SC3U.exe+0x84122); sc3netmod logged no exception.
Bulldoze / rebuild was run on round 1 (same code path: a broken carriageway sends the band back to the stock ladder,
the rebuilt cell brings it back); not repeated on round 2.

## Round 3: the avenue median (owner: "it needs the trees of the regular 2 road avenues")

- 20500 takes avenue 11204's frame table (`art.from` 11204: two layers, the stock ground / tree split) and keeps base
  35. Layer 0: the two 35 halves, with the light sidewalk pixels within the seam's half-width of the diagonal repainted
  from 11204's median grass (curb pixel each side kept). Layer 1: 11204's two trees (its tree layer, slot 1, cut at the
  emptiest column), two per cell on the diagonal, back to front.
- The median strip runs past the middle cell's corners into the outer cells, whose stock 35 tips are sidewalk (a
  sawtooth of light triangles in the game, rotation 1). New piece 20505 = stock 35 frame (own size and anchor, so
  ground-under is stock) with those tip pixels as grass; DAV places it on a one-road 35 cell when the other road has a
  cell beside it in its row (`dav 20505 35 0 0`). It saves as its base 35; middle pieces still save as 43.
- Cap combinations (20501..20504) keep the concrete seam: the grass median ends in a concrete nose.
- Game (Simcity_stock_diagave, inst_dav): both avenues `26 cell(s), 26 written`; zoom 3 and 4, all four rotations:
  grass median with the tree row, no clipped tree tops; trees overlap the far carriageway in the two views where the
  avenue runs across the screen, as 11204's do. Save: `43 variant tile(s) written as base`, file holds 43 on middle
  cells and 35 on outer cells. 0 exceptions.

## Open (later phases)

- Junctions: a band that touches any other road is left to the stock tiler (crossings with roads, avenue x avenue,
  joining the straight avenue 11204). The Berlin / Moscow double diagonals are 4-cell bands with junctions.
- The two carriageways end half a step apart (the second drag is one cell over; a square end needs a half cell).
- A cut carriageway reverts the whole band to the ladder; splitting it into two shorter avenues is not done.
- Traffic: middle cells carry both roads' lanes (animated cars keep to their carriageway); trip routing steps between
  4-adjacent road cells and is not measured. The lab city has no population.
