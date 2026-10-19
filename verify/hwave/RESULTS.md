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

## 6. Diagonal (phase 2, owner 2026-10-19 "Keep it automatic and build the diagonal version")

Owner pictures: `MAIN\verify\hwave\owner_shots\hwave_diag_plan.png`, `hwave_diag_mockup.png`, `hwave_diag_sheet.png`.
Test tree as above plus `diagonal_avenue` (art copied from `Simcity_wt_avenues`). j = cells along the band from the cap.

### Stock + DAV (in game, lab, before this block)

| case | highway end | avenue end (DAV) |
|---|---|---|
| x-z, highway (122,4) -> (130,12), roads (130,13) -> (138,21) and (131,13) -> (139,21) | (129,12) 11223.2, cap (130,12) 14999.2, (131,12) empty | (130,13) 18004.0, (131,13) 20501.0, (132,13) 20505.0 |
| x-z, roads dragged toward the end: (103,86) -> (97,80), (104,86) -> (98,80) | (no highway) | (97,80) 1999.0, (98,80) 1999.0, (96,80) empty |
| x+z, roads (66,33) -> (58,41), (66,34) -> (58,42), then highway (73,27) -> (68,32) | (67,31) 15052.2, cap (67,32) 15059.2, (68,32) 15052.0, (67,33) empty | (65,33) 18004.1, (66,33) 18004.1 |

The highway end is the same shape in both families (a quarter turn apart). The avenue end depends on its drag
direction. The plain 20500 starts at j+4 in all three. Bands one cell off the highway's middle line (two of my first
drags) are not connected and stay refused. The x-z avenue-first order was not measured stock (the drag fell outside the
flat window); it is case C below.

### Design

Six pieces, one set at four states (k odd = x+z): 21604 / 21605 j-1 (highway outer cells), 21606 the cap, 21607 / 21608
j+1 (the far one empty land), 21609 j+2 (the avenue's first middle cell, the only cell beside the avenue). Bases 15134
(kind 15) and 15138 (kind 14). DAV's plain 20505 is written at j+3 where DAV left an end cap. Deck H from the cap's start
to the ground at j+3 (eased, 2.1 cells). Offline tiler (`d1.sc3`, stock rules): the bases are kept and the band behind
stays plain in all 8 base x state tries.

Art: `hwave_paint.py` (deck = hwpaint highway_diag; past the landing, in the median nose and in a sidewalk shoulder at
the deck's height: the DAV pieces' own frames for the piece each cell would hold). Lanes: `hwave_build.py dlanes` (shapes
23420..23435), compile clean in every language; the two crossing lanes use different cells so no two border points share a
72-unit bucket, highway-side points match the stock band (111/195 vs 112/194).

Block (`sc3netmod_hwave.c`, `hwavd_*`): the set of cells the transitions hold (`hwave_claimed`, asked by `dbv_claimed`,
one marked line in `sc3netmod_dbv.c`) keeps DAV's writer and revert off them. In road passes HWAVE runs before DAV (claims
only: the stock road retile of that pass has just re-tiled DAV's cells) and after it (checks, builds, reverts); in the load
pass before DAV (claims) and in the highway pass with the other blocks.

### In game (PIDs 57276, 57388)

| case | log |
|---|---|
| A x-z, highway first, avenue from its end | the run before DAV waited (band still stock), then `diagonal highway end at (130,12) turn 0 -> transition ... 6 cell(s) written`, 8 cells held |
| B x+z, avenue first, highway drawn to it | `edit: diagonal highway end at (67,32) turn 1 -> transition ... 7 cell(s)` |
| C x-z, avenue dragged toward the end first (1999 end), highway drawn to it | `edit: diagonal highway end at (53,26) turn 0 -> transition ... 7 cell(s)` |
| D x+z, highway first, avenue from its end | refused while the avenue was one road, then `road: ... (107,86) turn 1 -> transition ... 7 cell(s)` |
| first DLL: a highway drag also runs a road pass; the stock road retile reset DAV's cells and the run before DAV reverted, the run after rebuilt (B, C) | fixed: the run before DAV only claims; a highway drag next to D afterwards logged nothing |
| router (live flags + matrices) | A and B before the save, C and D after the reload: highway band (2) -> 21604 -> 21606 -> 21607 -> 21609 (3) -> 20505 (1); from both avenue strips -> 21609 (3) -> 21607 or 21608 -> 21606 -> 21605 (3) -> band (2) (`dprobe_*.txt` in the instance) |
| save + reload | `save: 106 variant tile(s)`, `load: all 106 variant tiles restored`, DAV load pass `0 written` on the four bands; twin `dmatch e1_saved.sc3`: 4 transitions; `nomod`: 0 variant ids in the tile words |
| a road drawn against case A's avenue (my mistake) | DAV: `column road leaves the avenue's rows` -> band to the stock tiler; HWAVE: case A back to the stock ends (intended) |

Not covered: animated cars, `SC3NETMOD_HWAVE=0`, a game without sc3netmod (offline only), diagonal + straight bends next
to the transition, DAV merges / junctions near the end (refused by the rule, not tried).
