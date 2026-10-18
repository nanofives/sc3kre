# hwx results: a cloverleaf at a straight highway X (2026-10-18)

Owner sheets (game art, not committed): `MAIN\verify\hwx\owner_shots\hwx_sheet.png` (in game), `hwx_mockup.png`
(offline mockup), `hwx_plan.png` / `hwx_plan_r175.png` (plan). Design: `README.md`.

## What was built

| part | file |
|---|---|
| geometry (one quadrant turned 4 times), cell / turn table, plan, hwpaint scene, mockup and sheet | `re/tools/netmod/hwx.py` |
| art (all zooms, 8 shards), frame padding, lanes (hwlanes), manifest, package preview, in-game sheet | `re/tools/netmod/hwx_build.py` |
| offline twin of the C rule + routing over the lane specs | `re/tools/netmod/hwx_twin.py` (`selftest` PASSED) |
| C block on hwcore's HWY base | `re/harness/src/sc3netmod_hwx.c` (+7 marked lines in `sc3netmod.c`, `sc3netmod_rbt.c`) |
| package | `re/tools/netmod/examples/hwx_cloverleaf` (31 variants, 29 lane specs `hwx_<id>.lanes.json`) |

Pieces: 17 ramp ids 21120..21136 (base 15099, art frame table from 15127, used in the four quadrants at state =
quadrant), 8 junction ids 21150..21157 (a carriageway cell with a ramp join, base 15051 / 73, states 0 / 2), 6 clean
core ids 21160..21165 (base = the stock X piece, same states). 96 cells per cloverleaf, 12 per clean flyover. Every
piece is painted and has its lanes cut at one ref cell at state 0; the scene's 4-fold symmetry (ramps) and 2-fold
symmetry (core) make the other cells right (checked: the package preview drawn by state equals the mockup). Lanes:
hwlanes, 56 new curves, shapes 22500..22555, turn matrices "auto"; all 29 specs compile in every language with 0
warnings. Every ramp starts and ends on a carriageway's outer lane at a cell border; parapets open at every join
(clamped to the join cell, so the core art is the same with and without ramps). Every art piece has
`"ground_under": true` and its frames padded to the full cell diamond (hwt's recipe).

## Offline (`hwx_twin.py selftest examples/hwx_cloverleaf lab.sc3`)

| check | result |
|---|---|
| routing over the placed pieces' lane turns (state-rotated) | from each of the 4 approaches every exit is reached: 4 through, 4 right, 4 left (U-turns too, by two loops) |
| two crossing drags on the lab city (tiler.py), x first and z first | stock 12-cell X both ways (z over x); rule: new cloverleaf, 96 cells, each holds its piece |
| a cell of quadrant Q0 not free | clean flyover |
| an arm cut right after the 4x4 (hwt's stub X) | refused (left to hwt) |
| a ramp cell bulldozed | rebuilt on the next pass, cloverleaf kept |
| an arm cell cut inside the box | ramps removed, junction cells back to plain highway, clean flyover kept |
| the city-load pass over a fresh stock X | left stock (a load never takes land) |

## In game (2026-10-18, `Simcity_stock_hwx\re\harness\inst_hwx`, sc3netmod.dll from the worktree + hwx_cloverleaf; logs `sc3netmod_run1.log`, `run2.log`)

| step | result |
|---|---|
| x highway 46,27 -> 70,27 then z highway 57,15 -> 57,39 (window 1) | `hwx: edit: cloverleaf at (57,27): 96 cells written`; live grid = the table, cell for cell |
| live turn matrices (`nr_drive.py conn` 51..62 x 21..32, prop 310 per piece + state) | routing over them: all 12 movements reach their exits |
| z highway first: 105,79 -> 105,99 then 95,89 -> 115,89 (window 2) | `cloverleaf at (105,89): 96 cells written` |
| a 3-cell road in a quadrant, then the X (window 3) | `clean flyover at (131,24) (a quadrant is not free): 12 cells written` |
| save (menu 0x10009002) | `save: 204 variant tile(s) written as base, section 0x4E56 written` (96 + 96 + 12) |
| restart on the saved city | `load: all 204 variant tiles restored`; load pass `0 written, 0 reverted`; `kept=3` |
| shots | views 0..3, zooms 3 / 4, before and after the reload: grass under the slab ramps, no stale patches seen on the cloverleaf. One fallback shot right after the reload caught a half-drawn frame (dark stepped terrain); the same view a few seconds later is clean |

## Not measured / open

- Highway trips through the cloverleaf and animated cars (the lab city has no population); only the turn matrices
  and lane specs were checked.
- A stock game (no mod) loading the save: pieces save as their bases (15099 for ramp cells, 15051 / 73 for junction
  cells, the stock X pieces for the core). hwt found that a piece's saved state is its own, not the stock one; for hwx
  the junction ids sit at states 0 / 2, the same as the plain highway they replace, and the core keeps the stock
  states, so only the 68 ramp cells (15099 in states 0..3) would show as stock slope pieces. Not run.
- Bulldozing in game (twin only): a bulldozed ramp cell is rebuilt; cutting the X or an arm removes the ramps.
- hwcore's frame rule for ground under open decks (pending): applied as `ground_under` + padding for now.
- The X on a slope (stock 15149) is not handled (ids 21170..21189 reserved).
