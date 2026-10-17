# diagave phase 1: the straight diagonal avenue (2026-10-17)

Built: sc3netmod DAV block (`re/harness/src/sc3netmod_dav.c`, on RBT's retile-pass and city-load hooks), netpack key
`auto_diagonal_avenues` (writes `dav <inner35> <inner18004> <inner1999>`), package
`re/tools/netmod/examples/diagonal_avenue` (variants 20500 / 20501 / 20502), offline twin + art builder
`re/tools/netmod/diagave.py`. Light test per owner rule: one game run with the mod, one without, pictures. Owner sheet:
`MAIN\verify\diagave\owner_shots\diagave_phase1.png` (untracked).

## Design (from phase 0, RESULTS.md)

- Stock 35 draws only HALF its diamond (the road strip); the other half shows terrain (frame table 0xC0: first pass +
  ground under). Two touching diagonal drags therefore give two carriageways with a terrain strip between them, once
  each cell holds the piece a lone diagonal gets. The inner cells (beside that strip) take a variant: the same stock
  frame on a full-tile canvas plus one tree cut from avenue 11204 (slot 0, pixels above the ground diamond) on the
  strip's centre line. `first_pass` cleared (frames are taller than the tile), ground-under kept.
- Lone-staircase table (own-footprint mask -> piece.state), stock rules via tiler.py, staircases of 3+ steps, both
  axes and both step phases: 20 masks, one piece each. Two-step staircases get curves, so bands need 3+ rows.
- Tiling-rule route rejected: the band masks (118/127/223/217 and 236/239/191/179) with no conditions changed 1,118
  tiles in Berlin, 773 in London (16 cities, `netrules preview`); Simple-stage conditions only see 3x3 cells already
  placed this pass. The hook checks the exact band shape instead.

## Shipped cities (offline, `diagave.py scan`)

4 bands match the shape: Berlin 2, Moscow 2 (existing double diagonals drawn as the 4-way ladder). All 4 touch other
roads at their ends, so none converts: 0 tiles change in the 16 shipped cities.

## Game run (Simcity_stock_diagave = hard links of the stock tree, overlay install, inst_dav: sc3netmod + sc3resize)

| Step | Result |
|---|---|
| Load | `dav: ... inner pieces 20500 (35) 20501 (18004) 20502 (1999)`, hooks on, load pass ran, 0 faults |
| Two drags (102,92)-(110,100), (104,92)-(112,100) | `band axis 0, 8 full row(s), 34 cell(s), 34 written`; rows 35.2 / 20500.0 / 20500.2 / 35.0, top 18004.0 20500.0 20501.0 35.0, ends 1999.2 . 20502.2 |
| Two drags on the other axis, square ends (22,45)-(14,53), (23,46)-(15,54) | `band axis 1, 7 full row(s), 34 cell(s), 34 written` |
| Pictures | zoom 3 and 4, view rotations 0 to 3: median with terrain and trees, no holes. One frame after a camera jump near the map edge showed dark stale tiles; a one-cell camera move redrew them clean (harness artifact) |
| Bulldoze (106,96) | carriageway A broken: band no longer qualifies, the stock retile re-placed the ladder, `(112,100) inner piece 20502 no longer in a band -> stock retile` |
| Rebuild (106,96) | `band axis 0 ... 34 written`, the same 34 pieces as before |
| Save (menu 0x10009002) | `save: 34 variant tile(s) written as base, section 0x4E56 written`; the file's tile words read 35 / 18004 / 1999; `diagave.py plan` finds both bands again |
| Same save, game WITHOUT sc3netmod | loads; two plain diagonals per avenue (terrain between, no trees), no ladder |

Logs: sc3resize carries only its usual startup entry (0xC0000096 at SC3U.exe+0x84122); sc3netmod logged no exception.

## Open (later phases)

- Junctions: a band that touches any other road is left to the stock tiler (crossings with roads, avenue x avenue,
  joining the straight avenue 11204). The Berlin / Moscow ladders are the natural showcase.
- A cut carriageway reverts the whole band to the ladder; splitting it into two shorter avenues is not done.
- Traffic: inner cells keep 35's lane records (copy_base), so animated cars stay on their carriageway; trip routing
  steps between 4-adjacent road cells and can cross the median. Not measured.
- Trees in the views where the avenue runs across the screen overlap the far carriageway (stock 11204 trees do the
  same); smaller trees or one per row are options if the owner wants.
