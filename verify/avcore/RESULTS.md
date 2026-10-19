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

## In game (lab, own PIDs 46296, 58144, 32000, 58080, 23804, 34960, 71188, 69260; slope rows: hill copy)

| step | result |
|---|---|
| two parallel road drags x 50 / 51, z 20..36 | `avl: edit: band along z from (50,21) rows 0..14 -> one-way (ends: U-turn / U-turn)`, 34 cells: 21700.1 / 21700.3, ends 21701.3 / 21701.0 and 21701.2 / 21701.1 |
| save | `save: 34 variant tile(s) written as base`; read back: 11203.3 / 11203.0, 11204.1 / 11204.3, 11203.2 / 11203.1 |
| reload | `load: all 34 variant tiles restored`, the load pass finds the band |
| game without sc3netmod (only sc3resize) | the avenue loads as stock 11203 / 11204, same states |
| rail line across the avenue first, then the avenue | the band converts through the crossing: (50,30) 21711.1 runs N, (51,30) 21710.1 runs S |
| a road meeting the x 50 half (a stock T 39) | the band is refused and every cell goes back to stock: 11204, the four 11203, and the rail crossing 69 |
| slope (Roadless Paradise copy, own PIDs 9240, 41756; build 4c7e510 with the post-AVL hook slots empty) | two parallel roads x 96 / 97, z 18..46 over a hill. The game lays the avenue with slope pieces 31 (z 33, z 39) and 11201 (z 40, 41) on both halves. `avl: edit: band along z ... rows -14..12 -> one-way (ends: U-turn / U-turn)`, 58 cells: x 96 (runs N) 21719.0, 21718.2, 21723.0; x 97 (runs S) 21718.0, 21719.2, 21722.0, as the table's sides require |
| slope save / reload / revert | save: 58 tiles written as base; reload: `all 58 variant tiles restored`, the load pass finds the band (rows 0..26); a side road at (98,36) makes a T and the band goes back to stock, slopes included (31, 11201 at their states) |
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

## U-turn deadlock detour (2026-10-19: built, then RETRACTED and REVERTED the same day)

**Retraction (avjunc):** the game does not hang without a Frida probe. Every hang had hooks installed while paused and
the probe's `--start` unpausing it, with a one-way piece on screen at zoom 4. Without a probe: the ring view 7 min, the
U-turn end at Seoul (51, 62..63) 5 min, 3.3 M routing evaluations, no hang; attaching hwtraffic_probe to a running game
was fine for 2 months. The "curve" bisect was noise (single control runs).

**Reverted (orchestrator decision):** 21701 is back to two lanes (outer stock 1024, inner 23602); 21702 / 21703, the
`avlm` / `avlp` lines and the U-row rule are gone (package, AVL block, netpack, schema back to ed5465d). Kept:
`hwlanes.extra_for` (stock-matching sort id: flat 0, deck 2) and `avlanes tightleft` as a report tool. The record of
what was built and measured during the detour follows (committed in 3559939).

avjunc measured a hang (4/4, Seoul, zoom 4, sim running) with a car on 23602, the U-turn's inner lane (radius-80 left
turn). An inner lane cannot be widened inside the U-turn cell (it gains only 80 while turning 90 degrees). So now:

| part | change |
|---|---|
| 21701 U-turn | one lane, the outer (stock 1024, r 175); 23602 retired |
| 21702 merge / 21703 split (base 11204) | the band row next to a U end: the half running into the end merges inner into outer (S-curve 23608, r about 195), the half leaving it splits (23609) |
| AVL block | `avlm` / `avlp` lines; `avl_half_piece` picks merge / split by travel side; a band whose U row is a crossing / slope, or with two U ends and one row, stays stock |
| check | `avlanes tightleft <pack dirs>` (left bends r <= 80 by geometry, both languages); selftest runs it on avcore's pieces |

- Offline: selftest PASSED in ENGLISH and English-UK (straight -> merge -> U -> U -> split -> straight at all four end patterns, every crossing / slope, no tight left). netpack validate OK.
- Lab (hill copy, own PID 524): 58-cell band, row 19 x 96 21702.1 / x 97 21703.3 (N end), row 45 x 96 21703.1 / x 97 21702.3 (S end), slopes as before; save 58 as base.
- Scan over main's examples + avenue_lanes (`data/tightleft_main.txt`): 94 hits. Ground hits all on STOCK curves (English-UK shape 3 = 768..771 in avenue_junctions, big_roundabout, boulevard_junctions, roundabout, example_lanes_t_exit_only; English shapes 41 / 296 r 48 in diagonal_avenue). New-curve hits all on the deck (y 1024): highway_avenue, highway_dd_cloverleaf, highway_diagonal_cloverleaf, hwt_trumpet, hwx_cloverleaf. avenue_lanes 0.
- Stock baseline: stock pieces drive ground left bends of r 42..65 in English (11225, 1999, 18004, 15045) and every road corner as an r-80 left in English-UK. So geometry alone does not hang stock.
- Sort id: the curve record's trailing u32 is the path sort id (STRTSIM 0x1001e673 -> +0x34; Linux SortId; sent to the anim occupant manager on a change, 0x1001b030). Stock: 192/192 flat ground curves 0, 408/408 deck curves 2. hwlanes writes 2 on every new curve. Whether this is the hang's cause is [UNCERTAIN]; test proposed to avjunc / orchestrator.
- Sort id fix (orchestrator-approved, hwcore closed): `hwlanes.extra_for` writes 0 when every point is at y 0, else 2; curve_set / curve_records / inject agree (`netmod.hwlanes selftest` PASSED, also in avlanes selftest). Installed in my tree: 20 new flat curves 0, 16 new curves with height 2, stock untouched. The deciding A/B (sort id 2 vs 0 on the same tight-left ring lanes) is avjunc's.
- Not yet: the Seoul in-game check with cars on a U-turn (needs avjunc's junction package in my tree).

## Not done / open

- **No car has driven a converted avenue yet.** Before avjunc's junction pieces exist, no converted band connects to
  any road, so no trip or stock car reaches one. Cars come with the first sibling build.
- **English-UK routing [UNCERTAIN]** (AVENUE_LANES.md 2): lanekit says the matrix's high half serves English-UK's
  lanes, and the high half is the transpose here (needed for the tiler's arms). Not testable without an English-UK
  install.
- Slope variants 21718/21719 (base 31) and 21722/21723 (base 11201) passed in game. 21720/21721 (base 32) and 21724/21725 (base 11202) are offline only: the game did not lay 32 or 11202 under this avenue. The slope cells keep the base art (stock yellow centre line), as the rail crossing does.
- Stock cities: only 9 clean U-turn ends exist in the 15 shipped cities. Their avenues convert once avjunc declares its
  junction pieces (`avlj`).
