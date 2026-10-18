# hwdd: diagonal highway x diagonal highway cloverleaf, build and in-game check (2026-10-18)

Owner sheet: `MAIN\verify\hwdd\owner_shots\hwdd_sheet.png` (in game, both parities, zoom 3 and 4, views 0 and 1).
Plan and stock aftermath: `RESULTS_plan.md`. Mockup: `owner_shots\hwdd_mockup.png`.

## What was built

| part | file |
|---|---|
| block (on hwcore's `sc3netmod_hwy.c`) | `re/harness/src/sc3netmod_hwdd.c`, tables `sc3netmod_hwdd_tab.h` (generated: `hwdd.py ctab`) |
| shared files, 5 lines marked `/* task hwdd */` | `sc3netmod.c` (#include), `sc3netmod_rbt.c` (2 prototypes, `hwdd_run(hp)` in `rb_hwy`, `hwdd_stats()`) |
| geometry, ids, router flows, offline twin | `re/tools/netmod/hwdd.py` (`plan`, `cells`, `flows`, `ctab`, `check`) |
| scenes, mockup, package builder | `re/tools/netmod/hwdd_paint.py` (`mockup`, `build`) |
| package | `re/tools/netmod/examples/highway_dd_cloverleaf/` (manifest, README, `hwdd_<id>.lanes.json`; `art/` not committed) |

- 90 pieces, 21360..21449: cloverleaf centre 21360..21394 / corner 21395..21432, flyover centre 21433..21441 /
  corner 21442..21449. Ramp-only cells share an id over the four quarter turns, cells on the highway over the half
  turn. Every piece's representative cell sits at state 0 (cells on the highway: the stock state of the cell), so art
  and lanes are painted / cut in world frame. State convention = the game's (R: (x, z) -> (-z, x), hwy_rot).
- Bases: a piece on the player's highway has the stock piece the cell held as base, at that state (bands
  11223 / 11224 / 15052 / 15106, stub 73 / 15051 / 15149); a piece written into a free cell has 15099 (Protected,
  hwcore's land base). Art: `"from": 15127, "ground_under": true` on every piece (hwcore's ground rule).
- Lanes: hwlanes cuts of the painted decks (102 curve shapes, 23000..23101; diagonal carriageways at the stock
  lane offsets after hwcore's fix d5e1554). Turn matrices: hwdd's router flows, not "auto" (below).

## Proven offline

- `hwdd.py flows c|h`: per-cell (entry, exit) sides of the 4 carriageways and 8 ramps. In the corner parity the true
  staircases of A and B share entry sides in the 2x2 under O (the router would switch highways there without a
  ramp): B's two directions take other staircases through the crossing (`CORE_H`, found by search, A unchanged).
  Result, both parities: no clash (two flows sharing an entry but leaving by different sides, other than one
  carriageway with its own ramps), all 16 from -> to pairs reachable (4 through, 8 turns, 4 U-turns over two loops).
- `hwdd.py check` (twin of the C rule on the measured stock aftermath): fresh -> cloverleaf (97 / 108 cells), second
  pass keeps it with 0 writes, every cell saves as the stock piece it held, bulldozed ramp -> flyover with 0 ramp
  pieces left (out-of-box drop), building on a ramp cell -> flyover, end cap on an arm cell -> flyover, arm only 4
  cells past O -> stock.
- `netpack.py validate`: no errors (warnings: the tiler never places the pieces itself; two Collapse groups full,
  covered by INHERIT; matrix sides differ from the drawn lanes in the corner core by design, as in hwdx).

## Proven in game (Simcity_stock_hwdd, inst_hwdd, lab city)

| check | result | log / shot |
|---|---|---|
| corner parity drags (x - z = 30 x x + z = 86) | `built cloverleaf at frame (58,28) h`, 108 written, 0 reverted | g1_cells.txt, fin_h_* |
| centre parity drags (x - z = 118 x x + z = 149) | `built cloverleaf at frame (133,15) c`, 97 written, 0 reverted | g2_cells.txt, fin_c_* |
| save + reload with the mod | load pass: both `kept cloverleaf`, 0 written, 0 reverted | sc3netmod_run2.log |
| ground under the ramps | slate back-buffer patches with 73's frame table; grass in every shot after `"from": 15127` | g2_z3_r0 vs fin_c_z3_r0 |
| arm cut 12 cells out (stock retile reaches the interchange corner) | first DLL: whole interchange reverted (tests too strict: the tiler re-places band cells next to the 15099 ramps); fixed DLL: kept, 7 band cells written back | sc3netmod_run3.log |
| out-of-box drop (hwcore d8617ac) | 8 ramp cells outside the pass box `dropped by a block (outside the box)` | sc3netmod_run2.log |
| bulldozed ramp cell (57,22) | `no cloverleaf: 58 of 64 ramp cells hold their piece`, `built flyover`; then hwy_end's revert retiles re-placed the flyover cells with the stock stub (hwcore bug, fix pending merge) | sc3netmod.log run 3 |
| saved city loaded WITHOUT the mod | highway cells = the stock stub and bands; ramp cells = 15099 blocks (ramp-down decks on the ground) | nomod_h_z3_r0.png |

Logs and shots: `Simcity_stock_hwdd\re\harness\inst_hwdd\` and `inst_hwdd_nomod\` (game art, not committed).

## Open

- Bulldoze -> flyover in game: hwcore's hwy_end re-put of kept cells (re-placed by a revert's 3x3 retile) is
  written, not merged; re-test then. Until then a bulldozed ramp leaves the stock stub and the next pass rebuilds the
  cloverleaf.
- Saves without the mod: ramp cells show as 15099 ramp-down blocks (asked the program whether land pieces can save as
  no occupant). `hwys` saved states (hwcore, pending merge): the builder emits them when the base carries them; only
  the symmetric middle twins (11224 / 15106 / 15149 at state 2) change.
- Animated cars were not watched (the lab city has no population); routing is checked offline (turn matrices).
- Small wall fragments remain at some ramp joins (painter).
