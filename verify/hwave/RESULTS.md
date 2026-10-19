# hwave results: highway <-> avenue transition (2026-10-19)

Owner request 2026-10-19: "a way to turn highways into avenues, a transition that happens when dragging either one,
a piece that lowers the highway to the ground and seamlessly connects to road". Branch child/hwave from main 3e3bc0f.
Owner pictures: `MAIN\verify\hwave\owner_shots\hwave_plan.png`, `hwave_mockup.png`, `hwave_sheet.png`.
Test tree `Simcity_stock_highways` (four highway packages + highway_ask + avenue_markings + highway_avenue),
instance `re\harness\inst_hwave`, lab city copies.

## 1. Stock (in game, sc3netmod from main, before this block)

| case | result |
|---|---|
| avenue x 46/47 z 30..42, then highway (47,14) -> (47,29) | highway z 13..29, cap row z 29 = 11235.0 / 11237.0, avenue U-turn row z 30 = 11203.3 / 11203.0 |
| same, highway dragged to (53,30) (onto the avenue's first cell) | identical: the highway stops at z 29 |
| highway first, then roads dragged from z 42 to z 30 / z 29 (onto the cap) | identical: the road stops at z 30 |
| highway drag starting at the avenue end, (125,29) -> (125,14) | identical (cap ON the start cell z 29) |
| along x: avenue z 84/85 x 106..115, highway (95,85) -> (105,85); and the reverse order | cap row x 105 = 15054.2 / 15053.2, U-turn row x 106 = 11203.3 / 11203.2 |

Never connected. Neither tool builds onto the other network's cell. Save `inst_hwave\s1_stock.sc3`.

## 2. Design (plan sheet)

- Footprint: the two end rows only. Cap row -> 21600 / 21601 (deck H to H/2), U-turn row -> 21602 / 21603 (H/2 to the
  ground). The stock on-ramp drop (lane nodes 1024 -> 512 -> 0 over two cells, `lanekit show 15130 / 15134 / 15138`).
- Router: a road node steps only onto flag-1 cells; a highway cell (flag 2) is entered only from a ramp node (type 3)
  or a highway node; type 3 = cell flag 0x40 = occupant flag 0x200000 [CONFIRMED @ SimTransit 0x10007a63, 0x100086e7,
  FUN_10005983]. Only the on-ramp classes give 0x200000 (SIMNTWRK FUN_1001a5f2: ids 0x3b1a..0x3b25 = 15130..15141,
  kind 14 when also in the ROAD set = 15138..15141, else kind 15). So the ground pieces are variants of 15141 / 15140
  and the deck pieces of 15137 / 15136. sc3netmod's class mapping gets a new line kind `hwrc <variant>`.
- Offline tiler (`hwave_twin.py retile s1_stock.sc3`): with those bases in the end rows the stock HWAY + ROAD rect
  retile turns nothing back: 7 of 7 transitions stable (x and z).

## 3. Build

| file | what |
|---|---|
| `re/harness/src/sc3netmod_hwave.c` | HWAVE block: rule, build, revert, ROAD-pass entry (header = the rule) |
| `re/harness/src/sc3netmod.c` | +13 lines (task hwave): `hwrc` lines in NETRAMP's `ramp_file`, the #include |
| `re/harness/src/sc3netmod_rbt.c` | +9 lines (task hwave): prototypes, `hwave` / `hwrc` dispatch in `rb_file`, `hwave_run(hp)` in `rb_hwy`, `hwave_road` in the ROAD pass, stats |
| `re/tools/netmod/hwave_paint.py` | the art scene (hwpaint, unedited) + offline mockup |
| `re/tools/netmod/hwave_build.py` | package art + lanes + lane compile check |
| `re/tools/netmod/hwave_twin.py` | offline twin: `match` / `retile` on a save |
| `re/tools/netmod/hwave_probe.py` | live router inputs (occupant flag tests, turn matrices) + step walk |
| `re/tools/netmod/examples/highway_avenue/` | package: manifest, README, 4 lane specs |

Lane specs compile in every language with no warning (`hwave_build.py check`).

## 4. In game (one check, lab city, PIDs 66276 then 16656)

| step | log / cells |
|---|---|
| DLL start | `ramp: ... variant 21600..21603 classified as its base`, `hwave: ... transition pieces 21600 21601 21602 21603` |
| avenue first, then highway (47,14) -> (47,29) | `hwave: edit: highway end at (46,29) turn 0 -> transition to the avenue, 4 cell(s) written`; z 29 = 21601.0 / 21600.0, z 30 = 21603.0 / 21602.0, z 28 = 73, z 31 = 11204 |
| highway first, then roads (58,42) -> (58,30), (59,42) -> (59,30) | after the first road: `refused (no avenue U-turn row past the cap)` (a single road); after the second: `hwave: road: highway end at (58,29) turn 0 -> transition` |
| along x: avenue then highway (95,85) -> (105,85) | `highway end at (105,85) turn 3 -> transition`; x 105 = 21600.3 / 21601.3, x 106 = 21602.3 / 21603.3 |
| live occupants | cap row pieces on occupant vtable 0x10029E74 (15130's, kind 15), ground pieces on 0x1002A020 (15138's, kind 14) (`nr_drive.py conn`) |
| save | `save: 12 variant tile(s) written as base, section 0x4E56 written`; the saved tiles read back (tiler.City.load) as 11235/11237 (or 15053/15054) + 11203, the stock ends |
| reload (package rebuilt with the pruned matrices) | `load: all 12 variant tiles restored`, load pass 0 written 0 reverted |
| bulldoze an avenue cell beside the (58,29) transition (the click landed on (59,32), one cell off the (58,31) aimed at) | `hwave: road: transition at (58,29) turn 0 no straight avenue past the U-turn row -> 4 piece(s) back to the stock ends`; cap row 11235.0 / 11237.0, U-turn row 11203.3 / 11203.0 |

Router check (`hwave_probe.py`, after the reload; cell flags from the occupant tests FUN_10005983 makes, matrices
from the exemplar, the step rules of HIGHWAY_TRIPS.md 1.2):

```
(46,29) 21601.0 flags 0x42 matrix 0x00802000    (47,29) 21600.0 flags 0x42 matrix 0x20000080
(46,30) 21603.0 flags 0x43 matrix 0x00c02200    (47,30) 21602.0 flags 0x43 matrix 0x20081080
highway -> avenue: (47,26) type 2 ... (47,29) 21600.0 type 3 -> (47,30) 21602.0 type 3 -> (47,31) 11204.3 type 1
avenue -> highway: (46,31) 11204.1 type 1 -> (46,30) 21603.0 type 3 -> (46,29) 21601.0 type 3 -> (46,28) 73.2 type 2
other avenue cell: (47,31) 11204.3 type 1 -> (47,30) 21602.0 type 3 -> x- (46,30) 21603.0 type 3 -> (46,29) -> (46,28) 73.2 type 2
along x: the same three walks connect (probe_reload_x.txt in the instance folder)
```

Found and fixed during the check: with the matrices derived from the lanes ("auto"), the ground pieces also carried
the crossover lanes' U-turns (21602 z- -> x-, 21603 x+ -> z+). The router keeps the last gated exit in the order z-,
x-, z+, x+ [CONFIRMED @ SimTransit 0x10007881], so a trip entering 21602 from the avenue was sent back onto the avenue
through 21603 (first run's walk). The ground pieces now carry explicit matrices without those two turns.

## 5. Not covered / open

- Animated cars on the new lanes were not watched (the lab has no population); no trip was observed using the
  transition, the router check is the step rules on live flags and matrices.
- `SC3NETMOD_HWAVE=0` (revert-only path) and a load in a game without sc3netmod were not run; the no-mod load was
  checked offline (the saved tile records are the stock ends).
- The animated cars' crossover lanes lack the two pruned turns in the matrix; the street sim reads lanes, not the
  matrix (NET_LANES.md), so they should still drive; not watched.
- Diagonal version: assessed only (plan sheet). Single road, boulevard, avenue one column off, slopes: refused (stock).
- Owner call open: automatic (built that way) vs asking like the interchanges.
