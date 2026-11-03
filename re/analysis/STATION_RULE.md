# When a station can take passengers: the trip router's rule (child stationwarn, 2026-11-03)

Owner, 2026-11-03: "add an indicator when a station of any kind can't receive passengers because it's poorly
connected". Code: `re/harness/src/sc3resize_stationwarn.c` (block STATIONWARN in sc3resize). Results:
`verify/stationwarn/RESULTS.md`. Addresses are SimTransit.dll (image base 0x10000000) unless another module is named.
All reads are C2 (body read); the touch rule also has railgap's measurement behind it (`verify/railgap/RESULTS.md`).

## 1. What counts as a station

The cell flag builder `FUN_10005983` tags exactly four occupant type ids (occupant `vt+0x88`) as stations, over the
whole occupant rect `[CONFIRMED @ 0x10005983]`:

| type id | station | cell flags it ORs in |
|---|---|---|
| 0x2fb2 (12210) | bus stop | 0x11 = station 0x10 + road 1 |
| 0x2fc6 (12230) | rail station | 0x14 = station + rail 4 |
| 0x3048 (12360) | subway station | 0x18 = station + subway 8 |
| 0x3049 (12361) | rail-subway station | 0x3c = 0x20 + station + subway + rail |

Seaports, airports and ferries are not trip nodes: the router has no node type for them (`FUN_1000755e`,
`FUN_10008a94` handle types 1, 2, 3, 4, 8, 0x14, 0x18, 0x30, 0x41, 0x42, 0x43, 0x50, 0x80 only). They act on demand
through the valve layer (`PORTS_AIRPORTS.md`, `PLACEHINTS.md`). There is no elevated rail network (`PUBLIC_TRANSIT.md`).

## 2. The rule, step by step

The router `FUN_100070d0` is a depth-first walk that stops at the first node passing the arrival test
`FUN_10008a94` (`HIGHWAY_TRIPS.md` 1.1). `FUN_1000755e` picks the next node.

- **Neighbours.** Road, rail, subway, station and bus nodes look at the cells of their rect grown by one, the four
  corners excluded (ring scan `0x10007a63`). A station node's rect is the whole occupant rect: the chosen cell's
  occupant comes from the manager `*(T+0x94)` `vt+0x7c(x, z, &occ)` and its rect from `occ vt+0xcc`
  `[CONFIRMED @ 0x1000755e, 0x10007ec9..]`. So "touching" means sharing an edge with the station footprint.
- **In, from a road.** A road node (type 1, a road cell without 0x40) offers a neighbouring 0x10 cell as a bus stop
  (bus mode, cell has bit 1), else as 0x30 (bit 0x20), 0x14 (rail mode, bit 4) or 0x18 (subway mode). The station
  gets the score 0xff, so below `TrafficAnnoyanceLevel` it beats every road `[CONFIRMED @ 0x1000755e type 1 branch,
  keep rule 0x10007db4]`. A ramp road cell (0x40) is a type-3 node, matrix branch, and never offers a station.
- **In, from the lot.** The start node (0x80) scans the lot rect grown by `TripMaxDistanceToRoad` (T+0xc5 Res 4,
  +0xc6 Com 3, +0xc7 Ind 5, +0xc8 Default 5, picked by `FUN_100057f6` / `FUN_1000532c`) with the same offers, so a
  station that close to a lot wins over the roads `[CONFIRMED @ 0x1000755e 0x80 branch]`. The cells within that reach
  of R / C / I lots are the destination grids T+0x84 / +0x88 / +0x8c: `FUN_1000559e` sets them over the lot rect grown
  by +0xc5 / +0xc6 / +0xc7 for the classes `FUN_1000532c` maps to 0 (3000), 1 (5000, 10000, 0x3016, 0x303e, 18000)
  and 2 (8000, 0x302a); class 3 gets no grid `[CONFIRMED @ 0x1000559e, 0x1000532c]`. This settles the old
  `[UNCERTAIN]` on those grids (`PUBLIC_TRANSIT.md` 4, `CAR_TRIPS.md`): they are "within walking reach of an R / C / I
  lot", the cells a trip may arrive on.
- **Out, onto track.** A rail station (0x14) offers only a neighbour with bit 4 and no 0x10, a subway station (0x18)
  bit 8, a rail-subway (0x30) either by the trip's modes, and none of them when the node came from that track type
  (parent byte +0x15) `[CONFIRMED @ 0x10007f87, 0x10007fe9]`. From any station a trip can also take a neighbouring bus
  stop (bus mode). Nothing leads from a station back to a road (railgap measured 0 of 190,939).
- **Along the track.** Rail (4) and subway (8) nodes ring-scan for cells of their own bit (4-neighbour spread) and for
  station cells: from rail a 0x10 cell with bit 4 (rail station or rail-subway), from subway a 0x10 cell with 0x20, or
  with bit 8 and neither 1 nor 4 `[CONFIRMED @ 0x1000755e types 4 / 8]`.
- **Arrival.** A rail or subway node arrives only on a map-edge connection cell (0x1000 rail, 0x2000 subway, set by
  `FUN_10005983` from the neighbour query `T+0xf4 vt+0x58`). A station node arrives when its rect overlaps the
  destination grid of the trip's kind `[CONFIRMED @ 0x10008a94]`. So a track trip must reach another station that has
  lots in reach, or the map edge.
- **Bus stops.** Entered from a neighbouring road (bus mode) or a lot in reach; leave only to a neighbouring road cell
  (no 0x10, bit 1) as a bus-road node 0x41, which arrives like a road (0x400 edge cell or a destination grid)
  `[CONFIRMED @ 0x1000755e type 0x50, 0x10008a94]`. A bus stop only fails with no road next to it.
- **Not read by the router:** power, water, funding, strikes. The trip budget (256 x 4 = 1,024 cost units, rail 2 per
  cell) and which buildings may take transit (building bytes +0xc..+0xe, writer unknown) are not station properties.

## 3. What STATIONWARN flags

| flag | station kinds | test (cells of the ring = footprint grown by one, corners excluded) |
|---|---|---|
| no toca la via / el metro | rail, subway, rail-subway | no ring cell with its track bit (4 / 8) and no 0x10 |
| via sin otra estacion | rail, subway, rail-subway | the track components it touches (4-neighbour flood over the bit) reach no map-edge connection and no other station cell of a kind the track enters whose footprint lies in a destination grid |
| sin calle ni edificios | rail, subway, rail-subway | no ring cell that is road (bit 1, no 0x10, no 0x40), no ring cell that is a bus stop (0x11, the station hands trips to it, `0x10007fe9`) and no footprint cell in any destination grid |
| sin calle al lado | bus stop | no ring cell with bit 1 and no 0x10 |

Known gap: trips from class-3 buildings (`FUN_1000532c` kind 3, no grid) walk the Default distance (+0xc8) and are
not seen by the grid test.

## 4. Fields found on the way

- Station object (SimTransit vtables 0x1001af20 / +4 0x1001aef0 / +8 0x1001ada8, the occupant interface; subway
  ctor `0x1000d8e7`): +0x34 upkeep (10), +0x38 monthly funding cost (12 at the default 120%, the "Coste de
  financiacion" row, `0x1000cf4a`), +0x3c efficiency byte (120, "Calidad del servicio" thresholds above 0x27,
  `0x1000d064`). Measured on a Berlin subway station 2026-11-03.
- The stock per-cell rows `FUN_1000b2c2` (transit layer message handler) read the transit layer density getter
  `vt+0x60` = `FUN_10006d17(x, z, &byte, mask)`: for a station cell (0x10) it returns the surface density grid +0x60
  `[CONFIRMED @ 0x10006d17, call 0x1000b472]`.
- The city view window (outer, SIMSPR vt 0x67894) holds the cell highlighter at +0xc0 (SIMSPR `0x1004abc0`, Linux
  `cSC3WinCityView::GetCellCursorMap` +0xb8), visible flag +0xf8 (`0x1004abde`, hiding it runs highlighter vt+0x40(1)).
  The clear `FUN_1004b653` only wipes cells inside the dirty rect +0x50.
- The power outage icon is `cSC3PowerOuttageDisplay` (SIMSPR `0x1003db3d` update, `0x1003e486` add sprite, image key
  0xFFFE1600 + zoom, blink period `0x1003dadf`), power only, no kind field; names from the Linux demo [LINUX-HINT].
