# hwcars: animated cars on the new highway pieces in a populated city (2026-10-19)

Owner request 2026-10-19: "Watch traffic on the new pieces in a populated city." Branch child/hwcars from main 73b1381.
Test tree `Simcity_stock_highways` (all highway packages, highway_ask, highway_avenue, avenue_markings,
diagonal_avenue), instance `re\harness\inst_hwcars` with its own builds of sc3netmod, sc3cartrips, sc3simrun and
sc3resize from main 73b1381 source. City: copies of shipped Seoul (pop 498,577), never the original.
Owner pictures: `MAIN\verify\hwcars\owner_shots\hwcars_sheet.png` and 8 GIFs `hwcars_*.gif` (zoom 4, 1.3..4.5 MB).

## Verdict, piece by piece

| piece | cars seen | result |
|---|---|---|
| cloverleaf X (hwx_cloverleaf) outer ramps | real trips (route cars) and stock cars | **OK.** Cars drive the ramp deck and merge through the opened parapet. A queue of 4..6 cars forms at the merge (21134.0 -> 21151.0) when the lane is full, 5..8 s over the last 3 cells. |
| cloverleaf bridge / underpass | route cars, stock cars | **OK.** Through traffic on the deck and in the underpass. |
| cloverleaf loops | stock cars only | **Driven, but no real trip uses them** (see "Loops"). Stock cars complete the east -> south and south -> west loops. 12 of 25 stock cars that entered a loop were removed on it by the stock density despawn. |
| highway <-> avenue transition, straight (highway_avenue) | real trips both ways | **OK.** Highway -> avenue on one half, avenue -> highway on the other, no car removed on the 4 transition cells. |
| diagonal x straight (highway_diagonal_cloverleaf) | stock cars (the diagonal carries no trips) | **PROBLEM: cars vanish at 4 lane hand-offs** (table below). The other ramps and the diagonal core are driven. |
| RAMPFIRST | real trips | **OK.** Town trips take the new avenue -> transition -> highway in both cities' builds (deposits below). |
| T trumpet (hwt_trumpet), diagonal x diagonal (hwdd), diagonal transition | none | **Not tested** (see "Not covered"). |
| sc3cartrips filler mode | | **The game hung twice** (deadlock, see "Hang"). Replace mode (about 30 and 18 min in two games) and stock cars (about 10 and 15 min in two games) did not hang. |

Car tracks, all windows: **0 jumps** (two samples < 150 ms apart more than 0.6 cell apart), **0 cars against a
carriageway** on any highway, ramp, junction or transition cell (per-cell direction census).

## Build (Seoul copy)

The N-S highway x 244/245 z 94..125 crosses Seoul's east highway (rows 108/109, to the east map edge, the hwtraffic site)
-> `hwask: edit: yes: X cloverleaf at (245,109)`, `hwx: edit: cloverleaf at (245,109): 96 cells written`.
North end: avenue x 244/245 z 79..91 -> `hwave: road: highway end at (245,93) turn 2 -> transition to the avenue, 4
cell(s) written`; roads z 85 (x 209..243), x 209 (z 78..85), z 78 (x 201..209) to the town road x 201.
South end: avenue z 127..131 -> `hwave: road: highway end at (244,125) turn 0 -> transition`; roads z 128 and x 238 to
the amusement-park road (238,120). Saves `inst_hwcars\seoul3_built.sc3` (north only) and `seoul6_built2.sc3` (both
ends): `save: 104 variant tile(s)`, reload `load: all 104 variant tiles restored`.
Second copy: Highway (238,102) -> (251,115) -> `hwdx: edit: new crossing O (245,109) case A r 0, quadrants A1 A2 O1 O2`,
154 cells, save `seoul_dx1_built.sc3`.

## Real trips use the new chain (density deposits, `hwcars_deposits.py`, `data/dep_seoul_a.json`, `dep_seoul_c.json`)

90 s at speed 3 after the north build: 21 deposits on each cell of the town link and the avenue, then the north arm (x 245
southbound 34, x 244 northbound 13), the NE outer ramp onto the eastbound highway to the map edge (row 108 x 250..255:
66), and the eastbound highway -> NW outer ramp -> north arm (x 244) -> avenue. The transition cells get no deposit
(ramp cells never do, HIGHWAY_TRIPS.md).
150 s after the south build: park road (238,121..128) -> z 128 -> avenue -> south transition -> south arm north (12) ->
SW outer ramp -> westbound highway; 2 trips straight across the bridge to the south arm.

## Car tracks (`hwcars_tracks.py`, `hwcars_tracks_an.py`)

The probe hooks STRTSIM car Tick FUN_1001d2c0 (x +0x0c, z +0x14) and Shutdown FUN_1001c9e0; a removal probe
(`hwcars_removals.py`) labels each Shutdown by the last of NeedVehicleDisappear true (density despawn), SelectNextPath /
SelectPathFromConnectingNodeOnNextCell 0 (no path) within 2 s.

| window | cars | on new pieces | movements |
|---|---|---|---|
| cloverleaf, route cars 60 s | 115 | 99 | N arm -> NE outer ramp -> eastbound (20); eastbound -> NW exit -> N arm (9 + 17 through); through both ways |
| transition, route cars 60 s | 26 | 25 | highway -> 21600.2 -> 21602.2 -> avenue (most); one car avenue -> 21602.2 -> 21603.2 -> 21601.2 -> deck |
| NE quadrant, filler 40 s | 215 | 169 | the same plus the merge queue |
| loop test, stock cars 45 s + 40 s | 301, ... | 174 | loops east -> south and south -> west driven end to end |
| hwdx, stock cars 45 s x 3 views | 111..138 | 55.. | ramps up to the diagonal arms, through the diagonal core, a U-turn at the diagonal's stock end cap 14999.0 (237,101) |

Removals on the cloverleaf (stock cars, 40 s, both probes at once, `data/rm_stock2.json`): the 43 drawn cars that ended
on new pieces match the 43 density despawns cell for cell. The 36 "other" removals there were never drawn (failed
placements). 1 no-path removal on a new piece, no drawn car with it. So on the cloverleaf a car disappears only by the
stock quiet-street rule (CAR_TRIPS.md 1.3), not at a piece border.

## Problem: hwdx lane hand-offs where cars vanish (`data/rm_dx.json`, `rm_dx3.json`, clip `hwcars_diag_ramp_vanish.gif`)

Stock cars are removed with "no path" at fixed positions, the same in two camera views (so not the car-area edge):

| position (cells) | piece there | arriving from | next cell | moving cars removed |
|---|---|---|---|---|
| (251.31, 107.99) | 21350.3 (251,107) | 21349.0 (250,107) | 21293.2 (251,108), eastbound | 10 in 40 s, on screen, filmed |
| (243.26, 105.99) | 21333.0 (243,105) | 21325.1 (243,104) | 21286.0 (243,106), diagonal core | 5 |
| (241.0, 114.42) | 21320.2 (241,114) | 21319.2 (242,114) | 21321.1 (240,114) | 5 |
| (242.0, 106.21) | 21285.0 (242,106) | 21260.2 (242,107) | 11223.2 (241,106), diagonal band | 3 |

Clip: an RV and a scooter drive down ramp 21341 -> 21349 -> 21350 and are gone at the ramp foot instead of joining the
eastbound carriageway. What fails is the car's step into the next cell (no arrival node or no outgoing edge there,
FUN_1001c750 / FUN_1001c440); which of the two was not traced `[UNCERTAIN]`. The router's turn matrices on these cells
were proven by hwdx; the car lane graph is a separate thing and is where this fails. Route cars would hit it too if a
trip used these ramps (none did: the diagonal has no on-ramp).
Also seen: cars heading for the capped join 21532.2 (251,115) are removed on 21278.0 (251,114) (5). Capped pieces carry
no car lanes (hwcap2, known).

## Loops

No real trip took a cloverleaf loop in any window, and this follows from the router: at a highway node the trip keeps
the LAST allowed neighbour in the order z-1, x-1, z+1, x+1 below TrafficAnnoyanceLevel 165 (HIGHWAY_TRIPS.md,
`[CONFIRMED @ SimTransit 0x10007881]`), with no destination or density ranking. In this layout every trip movement was a
right turn or straight on. A test that held the highway traffic byte of (248,108), the straight-on cell after the NE
loop exit 21150.0, at 200 for 150 s (`hwcars_block.py`, value restored to 134 afterwards) did NOT divert eastbound trips
onto the loop: 21 route cars still went straight through. Why is not known `[UNCERTAIN]` (the router may read another
grid for the highway check). Stock random cars do drive the loops (clip `hwcars_clover_ne_stockcars.gif`); a loop has no
trip traffic, so the stock density despawn removes many of them on it (15 of the loop removals in 60 s were density).

## Hang (sc3cartrips filler mode)

Two games hung (PIDs 25084 and 68184): about 5 min and about 2 s after switching cartrips to filler mode (export
`sc3cartrips_mode(3)`), each time with the sim running; frames stopped, trips and car decisions frozen. Stacks
(`data/hang2_stacks.txt`, Frida thread snapshot, return addresses found on the stack, not an unwind):
- main thread: car Tick STRTSIM 0x1001d3b5 -> 0x10019adf -> MoveNStages 0x1001b95b / 0x1001b8cc -> path build
  0x10018768 -> SC3U.exe+0xc3e64 -> SIMSPR -> SIMCITY FUN_1000d310 = EnterCriticalSection on CS 0x1029d7b8; it owns CS
  0x103fcee8 (recursion 2);
- thread 23676 (SIMCITY+0x114dc -> SIMRCI -> SIMGEOM -> SIMSPR -> SIMDIRT+0x16ba2) owns CS 0x1029d7b8 and waits on
  0x103fcee8.
A lock-order deadlock between the car animation (main thread) and an RCI / terrain thread. Replace mode ran about 30 and
18 min in two games and stock cars (`mode=capture` / mode 1) about 10 and 15 min in two games without a hang. Whether filler mode causes it or only makes it likelier is not known
`[UNCERTAIN]` (2 hangs, both in filler). sc3simrun (animate while scrolling) was loaded in every game.

## Not covered

- T trumpet: its loop is on the far side of the through highway, and south of Seoul's east highway at x 229..237 is the
  park road (z 111), so hwt would refuse it there ("far side not free"). Not built.
- Diagonal x diagonal (hwdd) and the diagonal transition: a diagonal carries no trips unless a diagonal avenue joined to
  town feeds it, and DAV hands a band to the stock tiler when a road meets the avenue's rows (hwave RESULTS 6). Not built.
- Sacramento: not used (Seoul's east highway already carried the trips needed).
- Route cars (replace mode) are sparse on quiet pieces: the south transition got 12..14 trips per 150 s, so its clip
  shows few cars.

## Traps met (for the next traffic run)

- `rb_lab cam` failed ("system error" on the zoom call) and a road drag landed on other cells (a stray diagonal avenue):
  `hwcars_drag.py` retries the camera and refuses off-screen pixels.
- rb_lab.pix is the cell centre only when `alt` is the cell's own height: 73 for a 75 cell put drags one cell off.
  `hwcars_drag.py` reads each end's height from the save.
- Long road drags (20+ cells) were dropped; 7-cell pieces worked.
- After `hwcars_uicam.py` (minimap + zoom buttons) the car producer stopped spawning at zoom 4 until one more
  zoom-out + zoom-in click; the script now ends with that pair.
- The desktop grab returned white frames; sc3resize FRAMEDUMP (`SC3RESIZE_FRAMEDUMP`, set before launch) works. The
  sc3resize.dll in inst_highways predates FRAMEDUMP: build it from main.
- A grid read with `np_drive.py cells` over a big box times out silently (empty); `hwcars_grid.py` reads row by row.
- A non-road agent (straight line at constant speed across unbuilt cells) shows up in car tracks as class 0; ignore
  straight-line tracks over cells without a network.

## Tools (worktree, `re/tools/netmod/`)

hwcars_map.py (top-down map of a save), hwcars_drag.py, hwcars_uicam.py, hwcars_rec.py (FRAMEDUMP -> GIF, deletes the
BMPs, refuses below 3 GB free), hwcars_strip.py, hwcars_deposits.py, hwcars_tracks.py, hwcars_tracks_an.py,
hwcars_grid.py, hwcars_removals.py, hwcars_mode.py (sc3cartrips live mode), hwcars_block.py (test lever),
hwcars_stacks.py (thread snapshot for a hang). No mod source was changed.
