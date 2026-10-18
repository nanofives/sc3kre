# hwtrips: in-game check of why few trips use highways (2026-10-18)

Mechanism and code: `re/analysis/HIGHWAY_TRIPS.md`. Sheet: `MAIN\verify\hwtrips\owner_shots\hwtrips_sheet.png`.

## Setup

- Build: main 3255edc, test tree `Simcity_stock_highways` (four highway packages, sc3resize + sc3netmod, no sc3perf).
  City: copy of shipped Sacramento (`inst_highways\hwtrips\sac1.sc3`, from hwtraffic's survey copy). One game, PID
  74384, speed 4, nothing built or edited. Load pass: `hwy: ... 0 written, 0 reverted`.
- Probe: `re/tools/netmod/hwtrips_probe.py` (Frida). Metric: an arrived trip "uses a highway" when its final path,
  read from route_trip's pop loop (`FUN_10009e8e` called from `0x100072d8..0x100072f3`), holds a type-2 or 0x42 node.
  This counts every arrived trip, including those routed without the deposit flag (hwtraffic counted deposits only).
- Levers were written live into SimTransit's globals / grids, never into shipped files or mods. They were alternated
  ABBA ABBA in windows of 20 s real time (88..97 sim days each) in fast mode (`--nostep`), and reset at the end.
  Arm A = stock, B = lever.

## Census (read-only, `data/sac_census.json`)

| what | value |
|---|---|
| cells with ramp flag 0x40 | 150 (100 `0x42` highway, 50 `0x43` road + highway = road-side ends of 50 strips) |
| road density on those 150 | 0 on 149, 3 on 1 |
| road cells / with density / median / at or above 165 | 7,904 / 5,758 / 21 / 1,002 |
| 0x800 (highway arrival) cells | 12, all on the map border |
| live TrafficAnnoyanceLevel / TripCellCostBaseHighway / Road | 165 / 2 / 4 |

## Search behaviour (per-step hook, 6 windows, `data/sac_base0.json`, `sac_base1.json`, `sac_offer.json`)

- Decoded ring-scan rule vs the game's own pick: 243,928 match, 0 differ.
- Road steps that had a ramp cell among the candidates: 5,784 of 1,133,161 (0.51%). In 85.0% of them a busier road
  was also a candidate. The ramp was taken in 38.0%, and in 12.7% it was the only candidate.
- Trips that were ever offered a ramp from a road node: 316 of 4,768 and 321 of 4,218 (6.6%, 7.6%). 32..38% of
  those used a highway. That is 121 of 231 and 104 of 204 highway trips. The rest were never offered a ramp from a road
  (type 1) node. The only other road-side entry in the code is a bus node (0x41 -> 0x43), but that path was not
  counted directly `[UNCERTAIN]`.
- Final path length of arrived trips: under 4 nodes 33..36%, 32..127 nodes 33%, 128+ 8..11%. Mean 41..45 nodes.
- Every route_trip call: budget base 256. Dest kind 0 / 1 / 2. Deposit flag on 29..39% of arrived trips.
- The per-step hook slows the game (6..44 sim days per 15..20 s), so those windows are not used for shares.

## Lever test (fast mode, 4 windows per arm, about 370 sim days per arm)

| lever (B) | A share per window | B share per window | pooled A -> B | failed trips A / B |
|---|---|---|---|---|
| TripCellCostBaseHighway 2 -> 0 (`data/sac_hwcost0.json`) | 4.49..5.81% | 5.40..6.02% | 5.28% -> 5.79% | 0.50..0.76% / 0.69..0.89% |
| ramp-cell road density 0 -> 120 (`data/sac_rampd120.json`) | 5.43..7.10% | 7.31..9.22% | 5.93% -> 8.37% | 0.57..0.73% / 0.66..1.01% |
| ramp-cell road density 0 -> 164 (`data/sac_rampd164.json`) | 4.24..6.25% | 8.51..9.38% | 4.93% -> 8.99% | 0.54..0.91% / 0.53..0.79% |

Trips routed per arm: 4,087..4,332 per 30 sim days. Trips with a ramp node in the final path rose with density 164
from 326..527 to 729..1,002 per window.

Reading:
- Cost 0: ranges overlap. One B window (5.40%) sits below two A windows. There is no clear effect, which matches the
  code (cost only feeds the budget check).
- Ramp density: every B window is above every A window in both games, a 1.4x (120) and 1.8x (164) rise. 164 is the
  upper bound of any "prefer ramps" change, since a ramp then wins every time it is offered, and it still leaves
  over 90% of trips off the highway. The remaining limit is how rarely a trip's search passes a ramp at all.
- Spread between A windows of one game is 1.3..2.0 points, so differences under that are noise.

## Limits

- One city, one game. Seoul was not run.
- The ramp-density lever is a data write every 0.5 s. It also makes the traffic map show density on ramp cells, and it
  raises the ramp step cost to 4 + d/25 (budget only). It is a test of the mechanism, not a mod.
- The INI path (netpack `ini` entry -> overlay SYS.PAK) was not exercised. The globals were written live.
- Shipped mods unchanged. Game stopped (own PID only).

## Files

`re/tools/netmod/hwtrips_probe.py`, `re/tools/netmod/hwtrips_sheet.py`, `verify/hwtrips/RESULTS.md`,
`verify/hwtrips/data/*.json`, `re/analysis/HIGHWAY_TRIPS.md`. Save copy and logs:
`Simcity_stock_highways\re\harness\inst_highways\hwtrips\`.
