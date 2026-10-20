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

## Seoul, two-lane U-turn end with avjunc's junctions (2026-10-19, own PIDs 58616, 71560)

Build: avjunc's uncommitted Simcity_wt_avjunc (sc3netmod src with sc3netmod_avx.c, avenue_junctions built by
avjunc_build into a scratch copy, their netpack) plus avcore's 0b189f8 hwlanes.py / avlanes.py / avenue_lanes; avjunc's
tree left untouched. Stock Seoul copy: avx load run 150 junction boxes / 1,015 cells, AVL load pass 124 bands / 1,482
cells, 5 U-turn ends (incl. (51, 62..63)).

| run | sequence | result |
|---|---|---|
| 1 (trap) | paused: rb_lab cam (Frida attach, camera hook, DETACH) to (51,63) zoom 4; then P + 2 by keys, nothing attached | deadlock within 30 s: IsHungAppWindow 18/18 over 9 min, CPU time flat; main thread STRTSIM+0x18768 -> SC3U+0x24c75 -> SIMSPR+0x19ea9 -> SIMCITY+0xd31d (EnterCriticalSection), two SIMSPR threads on locks (`data/seoul_uturn_trap_stacks.txt`) |
| 2 (clean) | P + 2 by keys first, sim running 20 s; then rb_lab cam (attach, detach) to (51,63) zoom 4; watched with no key and nothing attached | no hang: 18/18 samples responsive over 9 min, routing evaluations 380,166 -> 1,272,467, game date 1/3/1999 -> 9/23/1999 (over 6 months); cars on the U-turn curve in the frames (`owner_shots/avcore_seoul_uturn.png`) |

So the two-lane U-turn (inner 23602, r 80) runs clean. The trap is wider than avjunc's wording: a Frida attach that is
already DETACHED before the unpause still deadlocks when it happened while paused. Cars' lane direction on the band was
not tracked (the track tools attach Frida); visually the frames show cars on the curve only.

## Seoul, two-lane U-turn on the branch build with car tracks (2026-10-19, own PID 7376)

Build: child/avcore d3cd8f8 (avjunc 1152e03 merged) + the slope sort id change below; avenue_junctions built by
avjunc_build. Sequence: P + 2 by keys first, then rb_lab cam (51,63) zoom 4 and hwcars_tracks attached to the RUNNING
game (box 44,56..62,70, 180 s), then 6 min with nothing attached.

| check | result |
|---|---|
| hang | none: responsive throughout (20 s + 3 min tracked + 12/12 samples over 6 min), routing evaluations 0.94 M -> 1.50 M, game date 1/3/1999 -> 12/8/1999 |
| direction | every car visit to an avcore cell runs the half's direction: (52,63) 21700.0 W 27, (51,63) 21701.2 W 25 + N 1 (inside the curve), (51,62) 21701.3 E 24, (52,62) 21700.2 E 23, (56/57,62) E 105, (56/57,63) W 15, (60,59) N 14, (61,59) S 24; none the wrong way |
| U-turns | 17 cars drove the whole U: 52,63 > 51,63 > 51,62 > 52,62 (8 of them on to 56,62 > 57,62) |
| lanes | both lanes used: lateral samples at z ~80 and ~175 in (52,63), (52,62), (56,62), (57,62) |

Cells with opposite directions in the box (18) are all stock two-way roads (29, unconverted 11204) or avjunc's junction
pieces (20805 / 20810 / 20811 / 20819). Data: `data/seoul_uturn_tracks_an.json`, `seoul_uturn_grid.json`,
`seoul_uturn_watch_tracks.txt`.

Slope sort id (orchestrator item): stock's own slope lanes carry 2 on 31 / 32 (y -512..0) and 0 on 11201 / 11202
(y -256..0), so no height rule. Spec curves may now carry `"sort_id"` (hwlanes CurvePts / sort_id_of; selftest
row added) and avcore's slope curves copy their stock source's: 23604 / 23605 = 2, 23606 / 23607 = 0.

## Avenue corners (2026-10-19, own PIDs 26372, 46112, 29228)

Scope (`py -3.12 -m netmod.avcorner_scan --groups`, 15 shipped cities, crossings / slopes counted as band rows):

| item | count |
|---|---|
| band ends | junction 4,126, corner whose outer cell is a T 39 / X 43 214, clean corner 169, other 96, half-bend 37, corner without a band beside 19, U-turn 9, map edge 2 |
| clean corner ends per city | London 74, Frankfurt 44, Berlin 16, Madrid 10, Liverpool 6, Moscow 4, Sacramento 4, Craterville 2, Madison 2, Seoul 2 |
| groups of bands joined by clean corners | 43 whose other ends are all junctions (1,188 cells: convert where avjunc's boxes declare those ends), 24 that also have another blocker (724 cells) |

The stock corner: inner and outer 11203 at one state, diagonal, plus two 11204 (8 patterns, `AVL_CST`). Pieces: inner
bend -> new 21726 (one id; no new curve, no new art: lanes on 23601 / stock 768 in English, stock 1024 / 23602's copies
in English-UK), outer bend -> 21701 (the U-turn quarter is the same left turn), halves -> 21700. Block: `avlk` line;
`avl_end` accepts a corner when the band beyond converts (recursive decide, that band's corner end assumed, a loop of
bands closes on itself, depth <= 64); the band beyond is processed in the same run, even outside the pass box.

| check | result |
|---|---|
| offline | selftest PASSED in ENGLISH and English-UK: every adjacent cell pair of all 8 measured patterns (band row, block, other band's row). A negative control (corner lanes reversed) gives 64 problems |
| lab: build | Roadless Paradise copy, two L-shaped roads: the game laid a stock corner at (96..97, 52..53) (11203.2 inner / outer, pattern along z forward, inner on B). Both bands converted in one run: `band along z from (96,35) rows 0..16 (ends: U-turn / corner)`, `band along x from (98,52) rows 0..11 (ends: corner / U-turn)`; block 21700.1 / 21726.2 / 21701.2 / 21700.0; the x band lay outside the edit box |
| lab: save | 66 variant tiles written as base (34 + 2 + 4 + 24 + 2) |
| lab: junction | a side road on the x band: avjunc's block made a junction box there and the group stayed one-way (a declared join); demolishing the far U-turn cell then reverted only the cells past the junction |
| lab: revert through the corner | demolishing a cell of the north U-turn: `0 written, 48 reverted` in a pass box of (94,32)-(99,41): the z band, the corner block (back to 11203.2 / 11204) and the x band up to the junction |
| lab: reload | `load: all 66 variant tiles restored`; the load pass finds both bands through the corner, 0 rewritten |
| London (stock city, with avjunc) | load: 8 corners converted (21726 x 8, their outer bends 21701 x 8), 1,270 avcore cells |

Sheet: `MAIN\verify\avcore\owner_shots\avcore_corner_sheet.png` (`netmod.avcorner_sheet`: lanes of one pattern as
compiled, plus the lab shot). Not done: cars driving a corner (no traffic in the lab; London not watched); corners whose
outer cell is a T / X (214 ends) need a corner-junction piece.

## Cars through a corner (London, 2026-10-19, own PID 54788)

Branch 25ae1b3 build, both packages. P + 2 by keys first; then rb_lab cam and hwcars_tracks attached to the running
game, 240 s per box. Analysis: `py -3.12 -m netmod.avl_tracks_an TRACKS GRID` (new: per avcore cell the car visits'
direction, lateral positions, paths; WRONG = a visit against a straight half's travel side).

| corner | result |
|---|---|
| (157..158, 157..158): z band x 157 / 158 z 152..156 + x band z 157 / 158 x 159..160, junction boxes at both far ends | 0 wrong-way visits. Inner bend 21726.2: southbound cars turn east (paths 158,152 > ... > 158,157 > 159,157 > 160,157), both lanes in and out (lateral samples ~80 and ~175 in (158,152..156) and (159,157), (160,157)). Outer bend 21701.2: westbound cars turn north (160,158 > 159,158 > 158,158 > 157,158 > 157,157 > ... 157,153). On that side only the median lane carried traffic past the bend: (158,158) all at z ~80; the one curb-lane car seen at (159,158) ended its trip there (Shutdown) |
| (109..110, 157..158), 11-row x band | no car entered the group in 240 s (62 cars in the box, all on other roads) |

So: direction through both bends PASS; both lanes through the inner bend PASS; both lanes through the outer bend not
observed (no curb-lane car reached it). Data: `data/london_corner_tracks_an.txt`, `london_corner_grid.json`,
`london_corner2_tracks_an.txt`; shot `owner_shots/avcore_london_corner.png`. No hang (sim running throughout).

## Scope: corners whose outer cell is a T 39 / X 43 (not built)

Same scan, with those corners also joining bands (15 shipped cities; ok = every other end is a U-turn, the map edge
or a junction; a junction end converts only when avjunc's box declares it, so ok is an upper bound):

| | groups ok | cells | groups blocked otherwise | cells |
|---|---|---|---|---|
| clean corners only (built) | 43 | 1,188 | 24 | 724 |
| clean + T / X corners | 124 | 3,666 | 25 | 890 |

Calibration: in London the clean-corner bound is 25 corners in 20 groups; the load converted 8 corners (about 1 in 3).
If T / X corners realise the same share, handling them adds about 800 cells of the 2,478-cell bound [estimate].
The 214 ends: London 84, Frankfurt 37, Berlin 34, Liverpool 31, Moscow 10, Madrid 8, Sacramento 7, Seoul 3. What touches
the outer cell's outside: T 39 + one road 29: 110; X 43 + two roads: 30; T next to another T: 28; T + 11203: 12; T +
35: 6; others 28.

What it takes: the outer cell is a junction (the avenue turns through it, a road leaves it), so it is avjunc's box
machinery: a box piece per arm pattern with one-way avenue lanes in and out plus the road's two-way lanes, declared
with `avlj` so the AVL block can end the band there. avcore's side is small: `avl_corner_at` accepts an outer cell
that is an avlj-declared piece whose letters fit the turn (both bands then join through it as today). Ids: avjunc's
range, one per outer pattern and lane mode (the two largest patterns, T + road and X + 2 roads, cover 140 of 214).
Art: whatever avjunc's box pieces use (its build makes the nose art from stock frames); not measured here.
Owner: avjunc (box lanes, art, avx rule), avcore for the corner-block change.

## Corner outer cell declared by avlj (2026-10-19, avcore's side of the T / X corners)

Orchestrator decision: build T + one road (110 ends) and X (30 ends); avjunc makes the box pieces. avcore's side:
`avl_corner_at` accepts an outer cell holding an avlj-declared piece whose letters fit the turn (`avl_outer_join`: I on
the side the incoming half flows in from, O on the outgoing side, from the halves' travel); such a cell is not written,
not claimed, its avl_free guard skipped (it is the declaring stream's). New `avl_corner_ok(x, z)` for avjunc: the dry
run with (x, z) taken as a fitting piece. `avlanes corner-letters` prints the requirement per pattern (always W = I,
S = O in the outer's own frame at the corner's 11203 state).

| check | result |
|---|---|
| build | sc3netmod.dll compiles (347,648 bytes) |
| offline | avlanes selftest PASSED in both languages, with a new row: a fake avlj outer piece carrying 21701's own turn ("..OI") fits all 8 patterns at their outer state, the swapped letters ("..IO") fit none. This tests the Python mirror of the rule (`outer_fits`), not the C itself |
| in game | not run: needs avjunc's declared pieces |



- **No car has driven a converted avenue yet.** Before avjunc's junction pieces exist, no converted band connects to
  any road, so no trip or stock car reaches one. Cars come with the first sibling build.
- **English-UK routing [UNCERTAIN]** (AVENUE_LANES.md 2): lanekit says the matrix's high half serves English-UK's
  lanes, and the high half is the transpose here (needed for the tiler's arms). Not testable without an English-UK
  install.
- Slope variants 21718/21719 (base 31) and 21722/21723 (base 11201) passed in game. 21720/21721 (base 32) and 21724/21725 (base 11202) are offline only: the game did not lay 32 or 11202 under this avenue. The slope cells keep the base art (stock yellow centre line), as the rail crossing does.
- Stock cities: only 9 clean U-turn ends exist in the 15 shipped cities. Their avenues convert once avjunc declares its
  junction pieces (`avlj`).
