# avmisc results (2026-10-19): big roundabout avenue arms + hwave straight transition on one-way avenue halves

Branch child/avmisc on avcore's published conventions (`re/analysis/AVENUE_LANES.md`, 9cd3f76). Pictures:
`MAIN\verify\avmisc\owner_shots\avmisc_plan.png` (plan), `avmisc_roundabout_game.png` (in game).

## What was built
| part | files |
|---|---|
| rbt9 one-way set: sides 20605..20608, corners 20620..20628, lanes on shapes 23900..23913 | `re/tools/netmod/bigrbt.py` (`OW_*`, `lane_spec`, `_fix_curves`), `avmisc_edges.py`, package `examples/big_roundabout` (manifest keys `side_oneway` / `corner_oneway`), `netpack.py` + `netpack.schema.json` (marked `task avmisc`), `sc3netmod_rbt9.c` |
| hwave straight ground row 21850 / 21851, curves 23950..23953 | `re/tools/netmod/hwave_build.py` (`slanes`, `scheck`, `sart`), package `examples/highway_avenue`, `sc3netmod_hwave.c`, `sc3netmod_rbt.c` (`hwavs` dispatch) |
| avcore hook (superseded, see the last section) | `re/harness/src/sc3netmod_avm.c` (deleted): `avm_dir(x,z)`, `avm_band_ok(x,z)` through two function pointers avcore's block sets; unset = no band converts = today's two-way pieces |
| English-UK | avcore's rule (published 9624081): lane specs carry NO path keys; curves are found by end points per language, and every curve also gets a reverse shape whose UK copy is the forward lane (rbt9: stock lanes 23904..23909, new lanes 23900..23903 + reverses 23910..23913; hwave: forward 23950..23953, reverse 23954..23957). My earlier `hwlanes.py` NOMIRROR change is dropped (it would have un-reversed avcore's own UK shapes) |
| checks | `re/tools/netmod/avmisc_plan.py check` (direction rule vs piece frames), `avmisc_sheet.py plan` (the plan picture) |

## Rules
- RBT9: a block takes the one-way set when EVERY avenue arm of it has `avm_band_ok(arm cell)`; else the two-way set as
  before. Every piece of the block changes (ring-only ones included): an unmirrored UK lane set must not meet mirrored
  neighbours inside one ring. An arm cell that holds a converted avcore piece (`avm_dir >= 0`) is not rewritten to 11204.
  Blocks with avenue arms are remembered; every later RBT9 pass re-asks and re-runs a block whose answer changed
  (`r9_resync`), so a band avcore turns back to stock flips the block back on the next road pass anywhere.
- HWAVE: the ground row takes 21850 / 21851 when `avm_band_ok(first avenue cell)`; a built transition switches set on
  the next pass; recognise / check / revert accept both sets.
- Directions (16 of 16 placements agree): side 20605 and a corner's z- arm = IN, side 20606 and a corner's x+ arm = OUT.

## Checked
| check | result |
|---|---|
| lanekit compile of the new specs, every language | no warnings except the "N curves fit, took K" ambiguity notices avcore's own specs also give |
| `avmisc_edges.py` (avlanes.check against avcore 21700, 10 edges: 20605, 20606, corners 20622 / 20625 / 20626 / 20627 / 20628, hwave 21850 / 21851) | 0 problems, ENGLISH and English-UK |
| netpack install big_roundabout in `Simcity_stock_avmisc` | ok, 10 new curve shapes, 40 records per file |
| netpack validate highway_avenue | ok (21850 / 21851 only carry the same "tiler never builds it" notice as 21600..21609) |
| DLL builds (VC build_mod.ps1) | ok |
| in game (lab, `SC3NETMOD_AVM_FORCE=1` standing in for avcore) | drags: block + E avenue arm (2 rows) -> `rbt9: edit: (106,96) -> 3x3 roundabout, 2 avenue arm cell(s), 9 cell(s) written: 20620.3 20607.3 20622.0 / 20607.2 20600.0 20605.0 / 20620.2 20607.1 20620.1`, arm cells 11204.2 / 11204.0; save: `9 variant tile(s) written as base`; reload: same 9 cells restored by the load pass |

## Not done / open
- **avcore's block is not in the tree yet**: no band was converted, so no trip or car was seen on the new lanes. The
  in-game check above forces `avm_band_ok` (test env var only; without avcore and without the var the stub answers 0 =
  two-way pieces, not run in game). Cars were not watched (lab has no population).
- **hwave in game not run** (needs the four highway packages built and installed); lanes compile, package validates.
- Needs from avcore: set `g_avm_dir_fn` / `g_avm_ok_fn` (see `sc3netmod_avm.c`), export `avl_band_ok` semantics as the header
  says (same answer whichever of my sets stands at the near end), merge the `avenue_lines` netpack key and add my
  `avlj` lines (listed in the package READMEs).
- English-UK: the one-way sets are right-hand there (owner decision). A single-road arm of such a block meets stock road
  29 whose UK lanes are mirrored, and the transition's cap row / the highway behind it are mirrored too: those edges do
  not line up in English-UK. Owner call whether UK should keep left-hand roads / highways around one-way avenues.

## Known limitation: English-UK edges (owner decision 2026-10-19, relayed by the orchestrator)
Owner chose right-hand everywhere, English-UK included, so avenue, roundabout and transition pieces stay right-hand in UK.
Stock single roads and highways keep what the game ships (left-hand in UK). In an English-UK install the lanes of our
pieces therefore do not line up with a stock road arm of a one-way roundabout block, nor with the highway behind the
hwave transition. Known, not fixed here (stock roads are not touched).

## Milestone 2 on avcore's block (child/avcore d5dddf1 + my hooks), in game 2026-10-19
Test tree `Simcity_stock_avmisc`, packages avenue_markings, avenue_lanes, big_roundabout; no force variable.
| step | result |
|---|---|
| 3 drags (3x3) then two avenue drags east (rows z 96 / 97, x 109..113) | block first two-way (20603 / 20612), then `rbt9: resync` -> the one-way set (20620.3 20607.3 20622.0 / 20607.2 20600.0 20605.0 / 20620.2 20607.1 20620.1), `avl: band along x from (109,96) rows 0..3 -> one-way (ends: join or edge / U-turn)`: arm cells 21700.2 / 21700.0, end U-turn 21701.0 / 21701.1 |
| demolish a band cell (112,97) | the band is no longer valid, avl reverts to stock 11204, rbt9 flips the whole block back to the two-way set (20603 / 20612 / 20610 ...) on the same pass |
| redrag the avenue | converts again (same cells as above) |
| save | `19 variant tile(s) written as base` |
| reload | `load: all 19 variant tiles restored`, rbt9 load pass 1 qualifies / 0 written, avl load pass converts the band, same 19 cells. (First attempt reverted the block: the arm cells hold 21700 during rbt9's load pass, before avl's map exists; fixed by `avm_own` = avcore's piece ids) |
Picture: `MAIN\verify\avmisc\owner_shots\avmisc_roundabout_game.png`. No cars in the lab: trips / cars on the new lanes not watched.

Hooks added to avcore's block (marked `task avmisc` in `sc3netmod_avl.c`): `avl_line` sets `g_avm_dir_fn / g_avm_ok_fn / g_avm_own_fn`;
`avl_band_ok(mgr, x, z)` = `avl_band` run dry (`g_avl_dry`: no writes, no map) where a band end made of two of the callers'
pieces (`avm_reg_mine`) counts as a valid join; `avl_end` has the one dry-run line for that. `netpack.py`: `avlj` accepts HWAY
pieces (hwave's ground row) as well as ROAD. Package `avenue_lines`: `avlj` lines for 20605, 20606, 20622, 20625..20628 and 21850 / 21851.
Not run: hwave in game (needs the highway packages built); cars / trips on the one-way arms.

## hwave straight transition in game (2026-10-19, avcore's block on, packages avenue_markings, avenue_lanes, big_roundabout, highway_avenue)
| step | result |
|---|---|
| with `SC3NETMOD_AVL=0`, avenue then highway | crossover set 21600..21603 as before (band_ok answers 0) |
| avl on, avenue x 46/47 z 30..42 dragged first | avl converts it at once (U-turn / U-turn ends, 21700 / 21701) |
| then highway (47,14) -> (47,29) | first run: nothing, hwave refused silently (its checks wanted stock 11203 / 11204 in the U-turn and avenue rows). Fixed: `hwave_isb` accepts avcore's variants of them. Then `hwave: edit: highway end at (46,29) turn 0 -> transition to the avenue, 4 cell(s) written`: z 29 = 21601.0 / 21600.0, z 30 = **21851.0 / 21850.0** (straight set), z 31.. = 21700.1 / 21700.3; `avl: edit: band along z from (46,31) rows 0..10 -> one-way (ends: join or edge / U-turn)` |
| save | `28 variant tile(s) written as base` |
| reload | `load: all 28 variant tiles restored`, same cells, avl load pass converts the band again |
Picture: `MAIN\verify\avmisc\owner_shots\avmisc_transition_game.png`. Highway-first order (avenue dragged afterwards) not rerun with avl on; cars on the lanes not watched (no population in the lab).

Highway-first order with avl on (rerun): highway (47,14) -> (47,29), then avenue columns x 46 and x 47 (z 42 -> 30): after the first column `hwave: road: ... refused (no avenue U-turn row past the cap)` (a single road), after the second `hwave: road: highway end at (46,29) turn 0 -> transition to the avenue, 4 cell(s) written` (z 30 = 21851.0 / 21850.0, z 31.. = 21700) and `avl: edit: band along z from (46,31) rows 0..10 -> one-way (ends: join or edge / U-turn)`. The transition picture was retaken from a reloaded save (no tool hover).
Note: the `sc3netmod_avl.c` hunks and the netpack `avlj`-HWAY change are avcore's now (orchestrator patch avmisc_for_avcore.diff); once avcore publishes them, sc3netmod_avm.c switches from the g_avm_*_fn pointers to avcore's functions and my avl.c / avlj netpack hunks drop.

## Final: on avcore's base update (child/avcore 4c7e510), 2026-10-19
- `sc3netmod_avm.c` deleted. `sc3netmod_rbt9.c` / `sc3netmod_hwave.c` forward-declare avcore's plain functions and call them:
  `avl_dir`, `avl_own` (an arm cell holding an avcore piece, or one inside a converted band, is avcore's: never rewritten,
  accepted by the rule), `avl_band_ok(x, z, away)`: rbt9 passes each avenue arm cell and the arm's outward side (block
  side x- W, z- N, x+ E, z+ S); hwave passes the first avenue cell past the ground row and the highway -> avenue side. 0 =
  the pre-rework (two-way) pieces. My earlier `sc3netmod_avl.c` hunks and the netpack `avlj`-HWAY hunk were dropped in
  the merge (avcore's versions kept).
- In game (one game, lab copy `lab7.sc3`, packages avenue_markings, avenue_lanes, big_roundabout, highway_avenue):
  roundabout + E avenue arm -> `rbt9: edit: ... 2 avenue arm cell(s) ...: 20620.3 20607.3 20622.0 / 20607.2 20600.0 20605.0 /
  20620.2 20607.1 20620.1` in one pass (no two-way step any more), `avl: edit: band along x from (109,96) rows 0..3 ->
  one-way (ends: join or edge / U-turn)`; highway first, then avenue: first column refused (single road), second column
  `hwave: road: highway end at (46,29) turn 0 -> transition to the avenue, 4 cell(s) written` (z 30 = 21851.0 / 21850.0),
  `avl: edit: band along z from (46,31) rows 0..10 -> one-way (ends: join or edge / U-turn)`. Save: `47 variant tile(s)
  written as base`. Reload: same cells at both places, rbt9 load pass 1 qualifies / 0 written, avl load pass converts
  both bands, 0 written / 0 reverted.
- Not done: cars / trips on the new lanes (the lab has no population); English-UK edges (known limitation above).
