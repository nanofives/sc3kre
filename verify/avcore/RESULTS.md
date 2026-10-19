# avcore: one-way avenue halves, the base (2026-10-19)

Stream `avcore` of the avenue lane rework (protocol `re/sessions/CHILD_PROTOCOL_2026-10-19_avlanes.md`, plan
`verify/avlanes/PLAN.md`). Branch child/avcore from main d25828f. Test tree `Simcity_stock_avlanes` (own hard-linked
tree), instance `re\harness\inst_avlanes` (sc3netmod built from this worktree), lab copies of the highway program's
`lab.sc3` and a Seoul copy. Owner sheet `MAIN\verify\avcore\owner_shots\avcore_sheet.png`.

## What was built

| part | file |
|---|---|
| the contract for the sibling streams | `re/analysis/AVENUE_LANES.md` (published in three pieces) |
| conventions as code, lane spec generator, edge checks | `re/tools/netmod/avlanes.py` (`build`, `check`, `selftest`) |
| the band rule block | `re/harness/src/sc3netmod_avl.c` (+2 marked lines in `sc3netmod.c`, +14 in `sc3netmod_rbt.c`) |
| per-trip refused list | `sc3netmod_lanes.c`: LD_TRIPMAX 32 -> 128 |
| netpack key `avenue_lines` | `netpack.py` (+10), `netpack.schema.json` (+5) |
| lanekit per-lane `uk_keep` | `lanekit.py` (+2: `mirror_spec` leaves such a lane as written) |
| package | `re/tools/netmod/examples/avenue_lanes/` (manifest, README, 18 lane specs; art = avenue_markings' white dashes, built by `avenue_markings.py build .`, not shipped) |
| Rail drags in the lab helper | `re/tools/netmod/hwcars_drag.py` (`rail` = menu 0x10004101) |

Pieces: 21700 straight one-way half (base 11204), 21701 end U-turn quarter (base 11203), 21710..21725 one-way rail /
power line / highway crossings and road slopes on a half (bases 69, 67, 11258, 15098, 31, 32, 11201, 11202, two per
base). New curves 23600..23607.

## Offline

- `py -3.12 -m netmod.avlanes selftest`: PASSED in ENGLISH and English-UK. It covers the straight run in every state,
  the four measured end patterns (straight -> U-turn -> U-turn -> straight), and every crossing / slope variant in every
  state between two one-way halves, both sides.
- `netpack.py validate`: OK in every language. The only warnings are the expected "no rule RESULT places it" (the block
  places these pieces, not the tiler).
- English-UK holds every curve reversed under the same key (lanekit MIRROR_LANGS). The specs therefore carry no curve
  keys (curves are found by end points per language), and two curves (23601, 23603) exist only to give English-UK
  forward copies.

## In game (lab, own PIDs 46296, 58144, 32000, 58080, 23804, 34960, 71188, 69260)

| step | result |
|---|---|
| two parallel road drags x 50 / 51, z 20..36 | `avl: edit: band along z from (50,21) rows 0..14 -> one-way (ends: U-turn / U-turn)`, 34 cells: 21700.1 / 21700.3, ends 21701.3 / 21701.0 and 21701.2 / 21701.1 |
| save | `save: 34 variant tile(s) written as base`; read back: 11203.3 / 11203.0, 11204.1 / 11204.3, 11203.2 / 11203.1 |
| reload | `load: all 34 variant tiles restored`, the load pass finds the band |
| game without sc3netmod (only sc3resize) | the avenue loads as stock 11203 / 11204, same states |
| rail line across the avenue first, then the avenue | the band converts through the crossing: (50,30) 21711.1 runs N, (51,30) 21710.1 runs S |
| a road meeting the x 50 half (a stock T 39) | the band is refused and every cell goes back to stock: 11204, the four 11203, and the rail crossing 69 |
| look | white dashed lane lines on the straight and the U-turn (avenue_markings' frames); the rail crossing keeps stock 69's art |

Two bugs found in the lab and fixed: a rect retile does not revert a Protected base (rail crossing 69 stayed the
variant), so a revert now writes the base at the same state. And a refused band's U-turn cells were not given back when
its other end failed first (short-circuit), so both ends are now always evaluated.

## Routing speed (Seoul copy, one game, sc3perf 8 workers batch mode, `ld_alt.py` ABBA)

`SC3NETMOD_LANEDENSITY=all` plus the M1 test package (stock 11204 one-way in routing: every avenue half in the city
one-way), LANEDENSITY toggled off / on in one game, windows of 25 s:

| | off | on |
|---|---|---|
| ms per trip, pooled | 0.05151 | 0.05189 (+0.7%) |
| per ABBA block on / off | 0.987, 1.106, 0.927 (median 0.987) | |

This is an upper bound: every stock piece's matrix is honoured as well. The shipped build honours only variants. The
fourth block saw no trips because the year-end budget window paused the sim. Per-trip refused list (LD_TRIPMAX 128):
188 overflows over the game (302,802 wrong-way fails, 470,934 refused-transition closes). At 32, M1 had 26,224
overflows. Different games, so this is not a paired comparison.

The M1 test package was uninstalled afterwards and must never ship.

## Not done / open

- **No car has driven a converted avenue yet.** Before avjunc's junction pieces exist, no converted band connects to
  any road, so no trip or stock car reaches one. Cars come with the first sibling build.
- **English-UK routing [UNCERTAIN]** (AVENUE_LANES.md 2): lanekit says the matrix's high half serves English-UK's
  lanes, and the high half is the transpose here (needed for the tiler's arms). Not testable without an English-UK
  install.
- The slope variants were checked offline only (the lab is flat).
- Stock cities: only 9 clean U-turn ends exist in the 15 shipped cities. Their avenues convert once avjunc declares its
  junction pieces (`avlj`).
