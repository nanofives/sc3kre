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

## Rebuild on hwcore 6ff62ab (ground rule + per-state save table, 2026-10-18; `sc3netmod.log` of x2.sc3)

- Every piece's art takes its frame table from stock 15127 (`"from": 15127`, `ground_under`, padded frames): the
  HWY_BASE.md ground rule (73's table can lose the terrain under the piece and its empty neighbours). Pixels and
  anchors unchanged.
- `hwys` lines for the 14 on-highway pieces: a junction saves as the stock straight highway of its cell's heading
  turned by its state, a core piece as its stock X piece at the same state (checked for all 28 placements per X).
- In game, on a copy of the first save: `load: all 204 variant tiles restored`, load pass 0 written / 0 reverted;
  shots in views 2 and 3 clean; save `204 variant tile(s) written as base`. Read back offline from that save: at both
  cloverleafs the 28 on-highway cells hold exactly the stock X pieces and plain straight highway in the stock states
  (28 / 28), the 68 ramp cells hold 15099. A game without the mod was not run.

## Without the mod (`x3_nomod.sc3` = a copy of the hwys save, sc3netmod.dll moved aside; only sc3resize injected)

The city loads. Live grid of the cloverleaf at (57,27): the 12 core cells are the stock X (15107 / 15108 / 15113 /
15114 / 15150 / 15153 in the stock states) and every arm and junction cell is plain stock 15051 / 73 in the stock
states, so the two highways and their crossing are exactly the stock X (`hwys` works). The 68 ramp cells load as
stock 15099 (a highway slope piece) at states 0..3 and draw as slope blocks on flat land around the X (shot
`inst_hwx
_c1_z3r0.png`). The sim was not run in that game. Better land save ids (the nearest stock one-lane
ramp piece per cell, HWY_BASE.md) would only change how those 68 cells look without the mod; not done.

## Not measured / open

- Highway trips through the cloverleaf and animated cars (the lab city has no population); only the turn matrices
  and lane specs were checked.
- Without the mod the 68 ramp cells show as 15099 slope blocks (section above); land save ids not done.
- Bulldozing in game (twin only): a bulldozed ramp cell is rebuilt; cutting the X or an arm removes the ramps.
- hwcore's frame rule for ground under open decks (pending): applied as `ground_under` + padding for now.
- The X on a slope (stock 15149) is not handled (ids 21170..21189 reserved).
