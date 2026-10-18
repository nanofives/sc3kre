# HIGHWAY_TRIPS.md - why the game sends so few trips onto highways (task hwtrips, 2026-10-18)

Owner question: "Find out why the game sends so few trips onto highways." Addresses are Ghidra VAs of SimTransit.dll
(image base 0x10000000) unless another module is named. In-game check: `verify/hwtrips/RESULTS.md`, owner sheet
`MAIN\verify\hwtrips\owner_shots\hwtrips_sheet.png`, probe `re/tools/netmod/hwtrips_probe.py`.

## Verdict

Ranked by evidence. The first two were measured in game, the last two are read from the code.

1. **The router is not a shortest-path search, and costs do not steer it.** route_trip `FUN_100070d0` is a
   depth-first walk that stops at the first node that passes the arrival test `FUN_10008a94`. That test accepts any
   cell set in the destination-kind grid, or a neighbour-connection cell. Trip cell costs (STTraffic.ini
   `TripCellCostBase*`, `TrafficDensityTripCostDivisor*`) are only summed into the node cost `+0x18` and compared
   against the budget at the entry of `FUN_1000755e`. They never rank one neighbour over another
   `[CONFIRMED @ 0x100070d0, 0x1000755e]`. So the lower highway cost (2 against road 4) attracts no trips. Measured:
   highway cost 2 -> 0 inside one game gave 4.49..5.81% (A) against 5.40..6.02% (B), ranges overlap.
2. **Few trips ever pass an on-ramp, and a ramp loses the neighbour ranking when one is there.** Measured in
   Sacramento: only 6.6..7.6% of trips stand on a road cell next to a road-side ramp cell at any point of their search,
   and 33..36% of arrived trips end in under 4 nodes. At each road step the walk keeps the busiest candidate below
   `TrafficAnnoyanceLevel` (165). Ramp nodes (type 3) never receive density, because route_trip's deposit switch has
   no case for type 3, so ramp cells stay at 0 (149 of 150 in Sacramento). 85% of ramp offers had a busier rival and
   38% were taken, after the DFS had used up the busier branches. Giving the ramp cells density raised the highway
   share 1.4x (density 120) and 1.8x (164, a ramp then wins every time it is offered), and it stayed under 10%.
3. **Highways can only be entered through ramp cells.** A road node steps only onto cells with flag bit 1. A highway
   cell (bit 2) can be entered only from a ramp node (type 3) or from another highway node `[CONFIRMED @ 0x10007a63
   ring scan, 0x100086e7]`. A trip's first node is always a road (type 1) or a station `[CONFIRMED @ 0x1000755e,
   start-node branch]`. Sacramento has 50 on-ramp strips, which gives 50 road-side entry cells against 7,904 road cells.
4. **On the highway a trip cannot arrive, and its exits ignore the destination.** A highway node (type 2) arrives only
   on flag 0x800 `[CONFIRMED @ 0x10008a94]`. Live, the only 0x800 cells are the 12 highway cells on the map border
   (neighbour connections). Any other highway trip has to leave by a ramp. At each highway node the next cell is
   chosen from the piece's turn matrix in a fixed direction order (z-1, x-1, z+1, x+1), and the last allowed cell
   below the annoyance level wins `[CONFIRMED @ 0x10007881]`. Nothing in that choice looks at where the destination
   is.

hwtraffic's 0.6..3.7% understated the share. Its probe counted highway *deposits*, and those exist only for trips
routed with the deposit flag (38..41% of trips, CAR_TRIPS 3.1). Bus-highway nodes (0x42) deposit nothing at all. On
the final path of every arrived trip, Sacramento's stock share is 4.2..7.1% (A windows below). That is still low, for
the reasons above.

## 1. The search, decoded

### 1.1 route_trip `FUN_100070d0`

- Arguments (thiscall on the traffic layer, `ret 0x1c`): start node, destination kind `param_2` (0..3, `< 4`
  required), budget base `param_3`, deposit flag `param_4`, three mode flag bytes `param_5..7` (bus / rail /
  subway, by the station types they unlock in `FUN_1000755e`). Live in Sacramento, every call had budget base **256**,
  dest kind 0, 1 or 2, and mode flags (1,1,1), (1,0,0) or (0,0,0) (`hwtrips_probe.py` args histogram).
- Budget: `uVar9 = DAT_1001f0b0 * param_3` = TripCellCostBaseRoad (4) x 256 = 1,024 cost units
  `[CONFIRMED @ 0x100070d0]`.
- Loop: arrival test `FUN_10008a94(node, dest kind)`. If it passes, the loop stops (first hit wins). If not, the
  node is pushed, `FUN_1000755e` picks ONE next node, and when no next node is found the deque is popped back to the
  last node whose retry flag `+0x1d` is set, and `FUN_1000755e` runs again from there. When the deque empties, the
  trip fails (`layer[0x2d]` += 1). This is a depth-first search ordered by the neighbour rule in 1.2. It is not a
  best-first or shortest-path search.
- Deposit (on arrival, deposit flag set, while the final path is popped `0x100072d8..0x10007554`): type 1 -> mask
  0x15 (road grid `+0x6c`), 2 -> mask 2 (highway grid `+0x70`), 4 / 0x14 / 0x18 / 0x30 / 0x50 -> 0x15 and / or 8.
  **No case for type 3**, and types 0x41 / 0x42 only add to a float at `layer[0x40]` without depositing
  `[CONFIRMED @ 0x100070d0]`. Amount = rect area x `TripDensityAdder` (3), capped at `TrafficMaxDensity` (255) by
  `FUN_10006edd`.

### 1.2 select_next `FUN_1000755e`

- Entry: fails at once when the node's cost `+0x18` is over the budget `[CONFIRMED @ 0x1000755e]`. This is the only
  place cost is used.
- **Road / rail / station / bus nodes (ring scan `0x10007a63`)**: every cell of the node rect grown by one, corners
  excluded. A road candidate needs flags `& 1`, no `0x10`, and a visited byte without the node type's bits. It becomes
  type `((flags & 0x40) | 0x20) >> 5`: **1, or 3 when the cell carries 0x40**. Its score is the road density
  `+0x6c`. The keep rule at `0x10007db4`: a candidate below `TrafficAnnoyanceLevel` replaces the kept one unless its
  density is lower than the kept one's. A candidate at or above the level is kept only when nothing is kept yet.
  Result: **the busiest road below 165 wins, ties go to the later cell in scan order** (x-1, then z-1 / z / z+1 at x,
  then x+1). Measured: the game's pick matched this rule on **243,928 of 243,928** road steps checked (steps with a
  station neighbour excluded). LANE_DENSITY measured the same "most congested below the cap" result with another
  method.
- **Highway / ramp / highway-bus nodes (matrix branch `0x10007881`, types 2, 3, 0x42, 0x43)**: the occupant's turn
  matrix (`vt+0x4c(0, layer+0x54, entry side)`) gives four gates, and each gated neighbour goes through
  `FUN_100086e7` in the order z-1, x-1, z+1, x+1. A later candidate replaces the kept one when its density is below
  the level. No density ranking.
- `FUN_100086e7`: from type 2, a neighbour with `& 2` becomes 2, or 3 if it has 0x40, and is scored on `+0x70`. From
  type 3, a neighbour with `& 1` becomes 1 / 3 (scored on `+0x6c`), else one with `& 2` becomes 2 / 3 (scored on
  `+0x70`). 0x42 / 0x43 work the same way for bus nodes `[CONFIRMED @ 0x100086e7]`.
- Start node (type 0x80): cells within `TripMaxDistanceToRoad*` of the lot. A road cell gives type **1 even when it
  carries 0x40**, otherwise a station `[CONFIRMED @ 0x1000755e, 0x80 branch]`.
- Cost of a step (only summed): road `TripCellCostBaseRoad + d/TrafficDensityTripCostDivisorRoad` (4 + d/25),
  highway `2 + d/100`, type 3 uses the road pair. Flag 0x80 adds `DamagedCostAddToStep` (32) and flag 0x100 multiplies
  by 0.7 (`0x1000835d`).

### 1.3 Cell flags `FUN_10005983` (layer `+0x5c`, u16 per cell)

Occupant flag 0x8000 -> `| 1` (road). 0x10000 -> `| 2` (highway). 0x20000 -> `| 4` (rail). 0x40000 -> `| 8`
(subway). **0x200000 -> `| 0x40`**. A query on layer `+0xf4` (`vt+0x58(net, x, z)`, net 1 / 4 / 2 / 6) adds 0x400 /
0x800 / 0x1000 / 0x2000. Piece `vt+0x20` -> `0x100`, `vt+0x18` -> `0x80`, `vt+0x40` -> `0x4000`
`[CONFIRMED @ 0x10005983]`. What the `+0xf4` query tests is not decoded `[UNCERTAIN]`. Live, its bits sit only on
map-border cells, which matches neighbour connections.

Live census, Sacramento (`verify/hwtrips/data/sac_census.json`): 150 cells carry 0x40, exactly hwtraffic's on-ramp
cell count for Sacramento. 100 are `0x42` and 50 are `0x43`, so each 3-cell strip has one cell that is also a road
cell (the road-side end). Road density on them: 0 on 149, 3 on one. Highway density: 0 on all 150. Road cells: 7,904,
of which 5,758 carry density, median 21, 1,002 at or above 165. 0x800: 12 cells, all on x = 0 / 255 or z = 0 / 255.
0x400: 13, likewise.

## 2. STTraffic.ini: where it lives, what it holds

`FUN_100015b1` reads `Sys\STTraffic.INI` through the archive `Sys\SYS.PAK` (`FUN_100124e6`), section
`[TrafficLayer]`. SYS.PAK wins over loose files `[CONFIRMED @ SC3U 0x004872e8]`, so the file is not loose under
`Apps`. Shipped values (`Apps\Sys\SYS.PAK`, member `STTraffic.ini`): TripCellCostBaseRoad 4, RoadBus 3, Highway 2,
HighwayBus 1, BusStop 8, Rail 2, Subway 1, stations 6; TripMaxDistanceToRoad Res 4 / Com 3 / Ind 5; TripDensityAdder
3; MonthlyDensityDecrement 75; TrafficMaxDensity 255; **TrafficAnnoyanceLevel 165** (`DAT_1001f0c0`, read back
live as 165); divisors Road 25, Highway 100. Key -> global map: `DAT_1001f0b0..b9` costs, `c0` annoyance,
`c1..ca` divisors, `be` adder, `bf` max density, `f120` DamagedCostAddToStep.

A mod changes these with a netpack package `ini` entry (`set`, member STTraffic.ini, section TrafficLayer). netpack
then writes the overlay copy `mods\netmod\overlay\Apps\Sys\SYS.PAK` (NETPACK.md). Whether SimTransit's own open of
SYS.PAK goes through the overlay hook was not checked here `[UNCERTAIN]`: the tests below wrote the globals live.

## 3. Levers, and what a mod could change

| lever | what it does (code) | measured / expected |
|---|---|---|
| `TripCellCostBaseHighway` (INI) | only the budget | 2 -> 0: no clear change (ranges overlap) |
| other cost keys / divisors (INI) | only the budget (1,024 units, base 256 from the caller) | not tested; same mechanism |
| ramp-cell road density (Frida data write) | the ramp wins the ring-scan ranking more often | 120: pooled 5.93% -> 8.37%; 164: 4.93% -> 8.99% |
| `TrafficAnnoyanceLevel` (INI) | lowers the level a road must stay under to keep its rank; a ramp at 0 then beats every road at or above it | not tested. It changes all road routing (trips move to quiet roads), so it is a blunt lever |
| deposit on type-3 nodes (code patch) | add the missing case in route_trip's deposit switch (type 3 -> mask 0x15 / 2), so ramps gain density from their own use like roads | not built. Expected inside the measured 1.4x..1.8x, because ramps would compete by the game's own rule |
| prefer ramps outright in the ring scan (code patch, e.g. score 0x40 candidates like stations, 0xff) | a ramp is taken whenever it is offered | upper bound measured with density 164: 1.8x |
| more on-ramps (player / template) | more entry cells, so more searches pass one | not tested. hwtraffic: on-ramp count alone does not order cities |
| destination-aware routing (replace the DFS with a cost-ordered search to a chosen destination) | costs start to matter, and highways win on long trips | a rewrite of route_trip and its callers. Large experiment, not attempted |

What a mod can do cheaply: the deposit patch (one switch case) or the ramp preference, both inside SimTransit, both
bounded at about 1.8x the stock share. Getting most long trips onto highways needs a routing change (row 8), because
under the stock search a trip stops at the first destination it reaches and has no notion of a far, fast route.

## 4. Open

- What `layer+0xf4 vt+0x58` tests (live: map-border cells only) and what the destination-kind grids `+0x84/+0x88/+0x8c`
  hold `[UNCERTAIN]`.
- How often the budget check actually ends a search. It was not counted. The cost-0 control showed no clear effect.
- Whether a trip that dives onto a highway fails more often. Failed share in the density-120 game: A 0.57..0.73%,
  B 0.66..1.01%. In the density-164 game: A 0.54..0.91%, B 0.53..0.79%. Not settled.
