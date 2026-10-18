# hwtraffic: does the highway program change trips? Berlin and Seoul before/after (2026-10-18)

Owner question: "will this change make improvements on the traffic trips?" Test chosen by the owner: before/after in
Berlin. Build: main cbefbc7 (all four highway packages + the seam fix), test tree `Simcity_stock_highways`, instance
`re\harness\inst_highways\hwtraffic\`. Sheets: `MAIN\verify\hwtraffic\owner_shots\hwtraffic_sheet.png` (Berlin) and
`hwtraffic_sheet_seoul.png` (Seoul). Seoul is the second pair the orchestrator asked for after Berlin's highways turned
out to carry under 1% of trips.

## Verdict

- **On a shipped city you just load, nothing changes.** The blocks build only on an edit pass. Berlin and Seoul both
  logged `hwy: load pass over (0,0)-(255,255): 0 written, 0 reverted`. No Berlin crossing is a shape this wave
  handles. Every stock X in Berlin, Frankfurt, Moscow, Sacramento and Seoul has the stock corner-ramp ring, which hwx
  refuses. Berlin's 10 cells of 15149 sit in 5 diagonal-stub T merges at (144,49), (171,69), (215,89), (215,143),
  (230,143), out of this wave.
- **Where a player draws a diagonal across a highway, the mod keeps trips flowing and stock does not.** Same edit in
  both games, one pair per city, 17 sim months per game:

  | city | stock (BEFORE) | mod (AFTER) |
  |---|---|---|
  | Berlin, west trunk to the map edge | 4 cells of 15149, 0 trips crossed | flyover + 2 quadrants, 32 trips crossed (0..5 per month) |
  | Seoul, east highway to the map edge | 4 cells of 15149, 0 trips crossed | flyover + 3 quadrants, 122 trips crossed (5..10 per month) |

- **Turning trips were not observed.** 0 trips used a ramp in any of the 4 games, because the new diagonal has no
  traffic of its own: it has no on-ramp and ends in empty land.
- **City-level: small or no measurable change.** Highways carry few SimTransit trips in every city surveyed: 0.6%
  to 3.7% of trips routed. In Berlin the failed-trip ratio ranges overlap (0.43..1.20% stock, 0.41..0.97% mod). In
  Seoul the mod game failed fewer trips: 79.9 per month (56..101) against 93.1 (78..105), ratio 1.52..2.58% against
  2.11..3.00%. The ranges overlap and it is one game per arm, so this is not a measured improvement.

## Site and edit (identical in both games)

Berlin's west trunk is the straight highway along x, rows 12/13 for x 36..70, running from the map edge at x 0. In the
shipped save's highway snapshot it is the busiest stretch. It has flat, unbuilt land (trees) to the south, a power
line on row 10 and a lake past row 7 to the north. The edit is `re/tools/netmod/hwtraffic_edit.py`:

1. Wires (menu 0x10005001): (43,8)->(47,8), (43,10)->(43,8), (47,10)->(47,8). This detours the power line around the
   diagonal's north end while the line still runs, so power stays connected.
2. Demolish (44,10), (45,10), (46,10), the wire cells under the diagonal. This step is needed because the Highway tool
   will not drag a diagonal over the wires. Measured: a first drag from (43,8) stopped at (45,9) and left a 15149, and
   that game was discarded.
3. Highway (45,10)->(58,23): one diagonal (hwdx case A), crossing at O = (48,13). Cost about §7,250 (HUD §117,006 ->
   §109,756).

Offline twin first (`re/tools/netmod/hwtraffic_twin.py`, hwdx's detect / place over the Berlin save): fresh crossing
at (48,13) case A, quadrants A1 + O1 built. A2 is refused because its joining cell (42,7) holds no highway, and O2
because its ramp cell (49,7) is not flat. 51 ramp + 19 joining + 16 core cells. In game:

| | cells after the edit (rb_lab cells) | log |
|---|---|---|
| BEFORE `SC3NETMOD_HWY=0` | 15149 at (45,12), (46,12), (49,13), (50,13), as the twin predicted cell for cell | `hwy: off (SC3NETMOD_HWY=0)` |
| AFTER (default) | 21260..21350 pieces over the trunk and on the south land | `hwdx: edit: new crossing O (48,13) case A r 0, quadrants A1 O1`, `hwy: edit pass over (31,1)-(66,31): 86 written, 0 reverted` |

## Method

`re/tools/netmod/hwtraffic_probe.py` (Frida, read-only) on SimTransit:
- `FUN_100070d0` (route one trip) counts every call in layer +0xb0 and every failure in +0xb4. Its return's low byte
  is 1 on arrival [CONFIRMED @ SimTransit 0x100070d0]. Density is deposited inside that call, only along an arrived
  trip's final path, through `FUN_10006edd(x, z, amount, mask)`, with mask 2 = highway node. So per trip the probe
  knows which highway cells were used.
- Cell groups: `west` = trunk x 0..40, `core` = x 45..50 rows 11..14, `east` = x 56..68, `joins` / `ramps` = the 19 /
  51 cells the block writes, `diag_s` / `diag_n` = the diagonal's arms outside the interchange.
- `FUN_100093e9` (monthly publish): the game's month counters +0xb0 / +0xb4, its failed ratio +0xb8 (float, failed /
  routed), the published average +0xc0, and the highway snapshot grid +0x64 per group.
- Each game: 7 months with a site box, then 12 months city-wide, at speed 4 (7 months take about 37 s). Each pass's
  first month is partial and dropped, leaving 17 full months per arm.

The arms are two separate games. The between-game noise note is about ms per trip (perf), not routing. The key result
here is structural (0 every month vs > 0 in 13 of 17 months), so it does not depend on that noise.

## Numbers (17 sim months per arm, mean and min..max per month; data in `data/summary.json`)

| | BEFORE (stock) | AFTER (mod) |
|---|---|---|
| trips crossing the site (`core`; `west` and `east` give the same counts, so these are through trips) | 0 total, 0 every month | 32 total, 0..5 per month (0 in 4 of 17 months) |
| trips using a ramp | 0 | 0 |
| trips using the new diagonal | 0 | 0 |
| arrived trips using any highway | 15.9 (5..26) | 21.9 (12..33) |
| all trips routed (city) | 3,507 (3,069..3,800) | 3,477 (3,081..3,811) |
| failed trips, game ratio +0xb8 | 0.43%..1.20% | 0.41%..0.97% |
| published traffic average +0xc0 | 40.6 (39..44) | 42.1 (39..44) |
| highway snapshot +0x64, city total | 15,795 (11,623..18,978) | 30,407 (20,387..42,060) |
| highway snapshot, west trunk group | 206 (0..1,134), decaying from the save to 0 | 2,421 (1,198..3,984) |

BEFORE, city-wide: over 12 months the deposits landed on 845 highway cells, all on the central trunk and the NE spur
(blocks around x 144..240, z 48..80), none west of the cut.

## Second pair: Seoul (orchestrator request after the Berlin note)

**Survey** (each city loaded unedited with the mod on, 3 full sim months, `hwtraffic_probe.py`, data `data/survey/`):

| city | arrived trips using a highway, per month | share of arrived trips | trips routed per month |
|---|---|---|---|
| Frankfurt | 59..97 (mean 74.3) | 2.1..3.7% | 1,601..3,162 |
| Moscow | 70..91 (mean 81.3) | 1.2..1.4% | 5,507..6,924 |
| Sacramento | 38..71 (mean 52.0) | 0.9..1.6% | 4,337..4,409 |
| Seoul | 24..46 (mean 33.7) | 0.6..1.2% | 3,307..3,762 |
| Berlin (AFTER arm, trunk passable) | 12..33 (mean 21.9) | about 0.6% | 3,081..3,811 |

**Site choice.** Frankfurt and Moscow carry the most highway trips, but no site fits there. A scan of every straight
highway point with trips and 21 straight cells around it found that a diagonal of 6 cells each way always crosses buildings,
roads or slopes in Frankfurt (14 or more blocked cells at each of its 21 such points). Moscow has no point with 21
used straight cells in a row (its used highway is broken up by ramps and bends). Sacramento and Seoul each
have sites with a fully free, flat diagonal and all 102 ramp cells free. Seoul's carried more highway use (deposit
sum 2,961 vs 1,323 over 4 months), so it was used.

**Site and edit.** Seoul's highway on rows 108/109 runs to the east map edge (x 255, a neighbour connection). It has
on-ramps at x 222..230 and empty, flat land with trees on both sides from x 231 to the edge. Trips use row 108. The
edit is one drag, `hwtraffic_edit.py --site seoul`: Highway (238,102) -> (251,115). The south arm stops at row 115
because water starts at (253,116).
- Twin: fresh crossing at (245,109) case A, all 4 quadrants, 154 cells, 12 of 12 movements.
- Game, BEFORE: 15149 at (242,108), (243,108), (246,109), (247,109), the cells the twin predicted.
- Game, AFTER: `hwdx: edit: new crossing O (245,109) case A r 0, quadrants A2 O1 O2`, 131 cells written. Quadrant A1
  was refused in game although the twin builds it. The log gives no reason and it was not traced `[UNCERTAIN]`. Its
  ramp cells reach x 254, next to the map edge.

**Numbers** (17 sim months per arm, `data/seoul/summary.json`):

| | BEFORE (stock) | AFTER (mod) |
|---|---|---|
| trips crossing the site (`west` = `core` counts, through trips to the edge) | 0 total, 0 every month | 122 total, 5..10 per month |
| trips using a ramp / the new diagonal | 0 / 0 | 0 / 0 |
| arrived trips using any highway | 25.1 (13..33) | 32.2 (23..45) |
| all trips routed (city) | 3,687 (3,262..4,114) | 3,640 (3,249..4,210) |
| failed trips per month, game counter +0xb4 | 93.1 (78..105) | 79.9 (56..101) |
| failed ratio +0xb8 | 2.11%..3.00% | 1.52%..2.58% |
| highway snapshot +0x64, city total | 13,021 (9,398..19,387) | 21,887 (18,677..24,228) |

In BEFORE the trips that used this highway to reach the east edge disappear entirely, from the on-ramp stretch
(`west`, x 222..234) too, not only past the cut.

## Why Berlin's highways get so few trips

Not determined `[UNCERTAIN]`. Measured facts:
- The share is low in every city surveyed (0.6..3.7%), so it is not a Berlin-only effect.
- On-ramp cell counts (pieces 15130..15141) do not order the cities by highway trips: Berlin 234, Frankfurt 327,
  Moscow 543, Sacramento 150, Seoul 225. Sacramento has the fewest on-ramps but 2 to 3 times Berlin's highway trips.
- Berlin's own 15149 merges do not isolate its southern network. In the BEFORE game 291 of the 462 highway cells of
  the south trunk and X (x 195..240, z 92..220) carried trips. The saved snapshot showing 0 there is an old state.
- The west trunk has no on-ramp between the map edge (x 0) and x 69. Its trips are edge <-> city trips, the only kind
  the AFTER games show crossing the new interchange in both cities.
What would settle it: which trips the router lets onto highway nodes (the mode argument of FUN_100070d0, `param_2 <
4`) and the per-mode costs in `STTraffic.INI` `[TrafficLayer]` (NETWORK_TYPES.md), neither read here.

## What it means for the owner's question

- In a city you load, the mod changes no trips until you build. Shipped cities' broken junctions (Berlin's 15149
  merges) are a shape the mod does not repair yet.
- When you draw a crossing that stock would leave as "Highway Construction", stock cuts both highways and trips stop
  using them. Measured in both cities: the highway to the map edge lost all its trips. The mod keeps the crossing
  passable, and trips keep using it (Berlin 32, Seoul 122 in 17 months).
- The extra movements (ramps) only matter when both highways carry trips. This test does not show them in use,
  because the new diagonal had no traffic source in either city. The turns exist: `hwdx check` routes 12 of 12
  movements with four quadrants, and the twin over the Berlin build (2 quadrants) routes 8, the 4 through movements
  and 4 turns. But no trip was seen taking a turn.
- Highways carry 0.6% to 3.7% of the trips SimTransit routes in the five cities measured, so one junction moves the
  city-level numbers little. Berlin: no measurable change. Seoul: fewer failed trips in the mod game, but the ranges
  overlap and it is one game per arm.

## Limits

- Two sites, one shape (diagonal x straight; 2 quadrants in Berlin, 3 in Seoul). The straight X (hwx) and the T (hwt)
  were not traffic tested. Their changes are turns only (a stock X already passes straight through, and a stock T
  stem dead-ends), so they need a highway with its own traffic on both legs, a bigger edit. The dead-end highway
  stubs in Frankfurt and Moscow carry 0 or close to 0 trips (they lead nowhere), so a T built on one would not be fed either.
- Turning trips need a fed second highway, for example the diagonal bent into a straight with an on-ramp to the road
  at x 63 (a larger edit, not done).
- One game per arm per city. The highway-trip and failed-trip differences have overlapping ranges. Only the
  crossing counts (0 vs 32, 0 vs 122) are clear differences.
- The traffic data map was not opened. The city-level numbers are the game's own SimTransit monthly counters (+0xb0,
  +0xb4, +0xb8, +0xc0), read live, and `[UNCERTAIN]` which of them the UI shows.
- Save coordinates: the save file's SimTransit grids are stored with x mirrored relative to network_layer's x (index
  `(n-1-x)*n + z` puts 86% of the saved highway grid on highway cells, `x*n+z` 2%). `transit_layer.py`'s note that
  saves are the transpose is also wrong for Berlin. The live grid and the deposit arguments use the game's cell
  coordinates (checked: deposits land on the trunk rows 12/13 and the jog rows 14/15).

## Files

`re/tools/netmod/hwtraffic_probe.py`, `hwtraffic_edit.py`, `hwtraffic_twin.py`, `hwtraffic_sheet.py`,
`verify/hwtraffic/RESULTS.md`, `verify/hwtraffic/data/` (Berlin at the top level, plus `seoul/` and `survey/`). Shots and
saves stay in the test tree (`inst_highways\hwtraffic\` and `inst_highways\hwtraffic\seoul\`, b2 / a2 each).

## Open item: Seoul quadrant A1 refused in game (twin builds it)

Crossing O (245,109) case A r 0. Quadrant A1 is the south-east quadrant, nearest the east map edge. Its own cells,
those that belong to no other quadrant (23, from `hwdx.case_table('A')` turned to the world), are:
- 12 ramp cells, all empty, flat and dry in the save: (249,110), (250,110), (250,112), (251,110), (251,111),
  (251,112), (251,113), (252,110), (252,111), (252,112), (252,113), (253,110).
- 11 joining cells, which must hold the plain stock highway: (249,109), (250,108), (250,109), (253,109), (254,109) on
  the straight, and (248,112), (249,112), (250,113), (250,114), (251,114), (251,115) on the diagonal's south arm.

Likely cause, from the code and the live cell read, not tested by a re-run: `hwdx_quad` (sc3netmod_hwdx.c) refuses
a quadrant when a joining cell does not hold exactly its base piece (11223 / 11224 at the right state). The drag
ends at (251,115), and the game put the diagonal's end cap there: the cells read after the edit show `14999.2` at
(251,115) in both games. The offline tiler places no end caps (its drag ends come out as 15149 / 15051), so the twin
saw a band cell there and built A1. If this is the cause, a drag one row longer would give A1, but (253,116) is water
here. All 23 cells lie inside the pass's read box (226,93)-(255,123), and they reach x 254 at most.
Open: confirm with one drag that ends past the joining cells, and have the twin model the end cap (check that every
joining cell is at least one cell inside the drag).
