# PORT_PICK: how airport and seaport zones pick a building, and how an imported one joins (airsea, 2026-11-19)

Round 2026-11-19g, stream airsea. Static reading of SIMRCI (`re/ghidra_export_simrci/functions/`), the stock
`Apps\Res\BUILDFAM.IXF`, `SC3ZoneLayer.ini` (SYS.PAK, `re/data/syspak/`) and the occupant exemplars. Background:
`BUILDING_PICK.md` (the RCI path, families, weights), `PORTS_AIRPORTS.md` (developers, UpdateCell gates, valves).
Runtime result: `verify/airsea/RESULTS.md`. Every claim carries an address or `[UNCERTAIN]`.

**Verdict: data only, no mod code.** A new building joins the airport zone as a 1x1 member of the airpark family
(family 3) and the seaport zone as a 1x1 or 2x2 member of the dockyard family (family 27), the same BUILDFAM line
the RCI growables use. Built into `bldimport.py` / `bldweb.js` as kinds `airport` and `seaport`.

## 1. Rows and families

`[ZoneDeveloperRules]` of `SC3ZoneLayer.ini`:

| zone | row | rule class | Apply | AddFamily | family |
|---|---|---|---|---|---|
| 14 Airport | `14,0x81ffc3ce` | runway, vtable `0x1004cdac` | `0x1002b04c` | `0x1002ad19` | 2 "Airport Runway building family", LandUse 12310 |
| 14 Airport | `14,0x2207d9ee` | airpark, vtable `0x1004b200` | `0x100032d1` | `0x10003022` | 3 "Airpark building family", LandUse 12310 |
| 15 Seaport | `15,0xc2d3fd7e` | pier, vtable `0x1004ce68` | `0x1002d27f` | `0x1002cf7d` | 26 "Seawall and Pier building family", LandUse 12330 |
| 15 Seaport | `15,0xe2d3fd92` | dockyard, vtable `0x1004cdec` | `0x1002c12a` | `0x1002bfec` | 27 "Seaport Yard building family", LandUse 12330 |

Vtables found from the Apply addresses in `.rdata` (slot `+0x1c` = Apply, `+0x14` = AddFamily, read from the PE).
[CONFIRMED, PE + data]

Family members (BUILDFAM.IXF; type 570447329 = `0x220055E1`, the airport/port occupant type, 545184782 =
`0x207EDC0E`, the ordinary building type):

| family | members (id, type, prop 0xCA, prop 0x1F4, footprint X) |
|---|---|
| 2 runway | 221, 222, 11010, 11011, 11012, 11015 (`0x220055E1` runway pieces); 11014 Tarmac, 11013 Airport Grass (`0x207EDC0E`, 0xCA `0x100`, 1x1) |
| 3 airpark | 225 Tower (`0x220055E1`, 0xCA 0, 1F4 4, 1); 227 Terminal (0xC00, 5, 1); 228 Storage Shed (0x100, 0, 1); 229 Grounds Control (0x400, 0, 1); 230 Walkway (0x100, 0, 1); 246 Hangar (0xC80, 6, 2); 11018 Terminal Connector (0, 0, 1); 231 Parked Airplane (`0x207EDC0E`, 0xD00, no 0x1F4, 1) |
| 26 pier | 223, 9276, 9277, 9278, 9279 (`0x220055E1`) |
| 27 dockyard | all `0x207EDC0E`: 224 Crane (0xCA 0, 1x1), 240 Loading Bay (0x280, 2x2), 242 Cargo Yard (0xF00, 2x2), 9042 Parking Lot (0xFF, 2x2), 9043 (0xD90, 1x1), 9044 (0xD00, 1x1) |

## 2. Airpark (family 3): fixed slots plus a filler list

AddFamily `0x10003022` reads, per member: `vt+0xbc` (attrib flags), `vt+0x40` (SizeInCellsX), and
`QueryInterface(0x22002d06)` then that interface's `+0xc4` (0 when the query fails). It sorts members into six lists
[CONFIRMED @ 0x10003022]:

| list (record offset) | condition |
|---|---|
| `+0x00` | size 1, piece type 4 (tower) |
| `+0x18` / `+0x0c` | flag 0x400 / 0x800, size 1, type 5 (terminal) |
| `+0x30` / `+0x24` | flag 0x400 / 0x800, size 2, type 6 (hangar) |
| `+0x3c` **filler** | (flag `0x100` set **or** type 0) **and** size 1 |

The record (stride `0x48`) is stored only when all six lists are non-empty. The loop reads only the attrib pointer of
each `{attrib, weight}` pair: **the Key weight is not used**, each line is pushed once. [CONFIRMED @ 0x10003022]

Data agrees member by member: prop `0x1F4` holds 4 / 5 / 6 on the tower, terminal and hangar and 0 on the rest, prop
`0xCA` carries `0x400|0x800` on the terminal and hangar, `0x100` on the shed and walkway. That prop `0x1F4` feeds
`+0xc4` and prop `0xCA` feeds `+0xbc` is [UNCERTAIN] by code (no loader read), consistent on all 8 members.
Stock filler list = 228, 229, 230, 231, 11018 (5 buildings); Sacramento's airport zones hold exactly those ids plus
the tower, terminals and hangar (`verify/airsea/RESULTS.md`).

Apply `0x100032d1` [CONFIRMED]: rect clamped to 10x10; `FUN_1000368a` (tower), else 55% `FUN_100037ea` (terminal
strip) / 45% `FUN_10003407` (hangar); when none placed, a random record, a random member of its `+0x3c` list and a
random cell of the rect, placed through ZoneLayer `vt+0x68` only if `this+0x40 vt+0x4c(cell)` is true (the runway
service test of `PORTS_AIRPORTS.md` 2.4). So **an imported airport building is a filler: 1x1 only, drawn uniformly
from the list**. A `0x207EDC0E` exemplar copied from Parked Airplane 231 is in that list on either branch (flag
0x100 set, and type 0 when the interface query fails or the prop is absent).

Weight: one Key line = one list entry, and the parser `SIMGEOM 0x10001250` keeps duplicate lines (no de-duplication,
each resolved line pushed `{attrib, weight}` into `+0x20`) [CONFIRMED], so N copies of the line give the building N
entries out of 5 + N.

## 3. Runway (family 2): not a target

AddFamily `0x1002ad19` keeps, per piece type 1-3 and flags, a single pointer (the last match), and pushes
`flag 0x100 && size 1` members into the list at `+0x28` [CONFIRMED]. The edge-row placer
`sc3_zonedev_place_edge_row_34` (`0x1002b2f0`) reads only the **first** entry of that list
(`**(record + 0x28)`) [CONFIRMED @ 0x1002b2f0:176, 267]. A line inserted first (as every importer does) would
replace Tarmac 11014 on every runway; a line appended would never be drawn. Left alone.

## 4. Dockyard (family 27): weighted, like the RCI rules

AddFamily `0x1002bfec`: per member, `vt+0xbc & 0x100` clear -> list `+4`, set -> list `+0x10`, each pushed
`weight` times (`piVar5[1]`) [CONFIRMED]. Record = `{LandUse, list +4, list +0x10}`, stride `0x1c`.

Apply `0x1002c12a` [CONFIRMED]:
- the record whose LandUse == the developer's argument; the seaport developer passes `0x302a` = 12330
  (`0x1002cc5b`, `rule vt+0x1c(cell, 0x302a, v, v)`) [CONFIRMED];
- rect at least `DAT_1005804c` x `DAT_10058050` and clamped to `DAT_10058054` x `DAT_10058058` (SC3Tune
  `0xe2d3fd92=1,7,5,35`, `PORTS_AIRPORTS.md` 2.2);
- a 10x10 mask of the cells where `this+0x3c vt+0x54(cell)` is true (the pier service of `PORTS_AIRPORTS.md` 2.4);
  nothing happens when no cell qualifies;
- per free, transport-reached cell (`ZoneLayer vt+0x6c(cell, this+0x30)`), `RandomUint32Uniform(100) <
  DAT_10058060` (35) draws from list `+4`, else from `+0x10`, uniformly over the weighted entries; the building is
  placed if `SizeInCellsX` fits the rect from that cell (both axes are tested with `vt+0x40`), through ZoneLayer
  `vt+0x68`, and its cells are marked used.

So an imported seaport building is an ordinary family-27 member: any square size that fits (stock 1x1 and 2x2,
the tool offers those two), weight honoured, list `+4` when its base has flag 0x100 clear. Stock list `+4` = 224,
240, 9042 (35% of draws), list `+0x10` = 242, 9043, 9044.

## 5. Pier (family 26): not a target

The pier rule builds the waterfront pieces (`0x220055E1` with piece-type interface, on water cells, zone 0 in the
raster; Sacramento's 29 pier occupants all stand on zone-0 cells). Its AddFamily `0x1002cf7d` / Apply `0x1002d27f`
were not read in detail [UNCERTAIN]; an ordinary building has no business there.

## 6. What a new building needs

| kind | exemplar | family line | lot | weight |
|---|---|---|---|---|
| airport | copy of 231 Parked Airplane (`0x207EDC0E`, prop 0x65 12310, 0xCA 0xD00) re-keyed, own art | family 3 | 1x1 | N identical lines of weight 1 (N <= 20 in the tool) |
| seaport | copy of 224 Crane (1x1) or 240 Loading Bay (2x2), flag 0x100 clear | family 27 | 1x1, 2x2 | the Key weight |

Same containers as every bldimport building (`OccupantAttribs_Korea.IXF`, `CSAttrib_Korea.IXF`,
`B1D10001_bldimport.DAT`, names, overlay BUILDFAM), so the same restore. The exemplar keeps the base's LandUse and
agent type, so the valve effects of `PORTS_AIRPORTS.md` 1.3 (airport cell +500 commercial capacity, seaport cell +250
industrial) apply to the new buildings too [CONFIRMED by data: prop 0x65 copied; valve code reads the agent type of the
occupant, `0x1002f5af`].

## 7. Open

- Prop `0x1F4` -> interface `+0xc4` and prop `0xCA` -> `+0xbc`: data-consistent, loader not read.
- Pier AddFamily / Apply detail.
- The airpark's tower / terminal / hangar placers (`0x1000368a`, `0x100037ea`, `0x10003407`): which list members
  they draw, not read; imports never enter those lists (they need piece type 4-6).
