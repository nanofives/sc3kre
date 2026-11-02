# Land value: per-building modifiers (`SC3LandValue.ini [AgentIDModifiers]`)

2026-11-02. Module `SIMRCI.DLL` (the land value layer, iOS `goLandValueLayer`). Question answered: do
plopped buildings (police, fire, schools, parks, landmarks...) raise land value, how far, and does
size matter. A per-building workbook (`sc3_building_effects.xlsx`, shared with the owner, not in git) was
generated from `re/data/syspak/*.ini` plus the shipped `Cities/*.sc3` saves (section 6).

## 1. Short answer

- Yes. Every agent type with a row in `[AgentIDModifiers]` (or an ancestor with one) changes land value.
- The row is a **percentage of the cell's base land value**, one signed value each for R, C, I and A.
- It is added **once per footprint cell**: a 3x3 building stamps 9x the row, a 5x5 one 25x.
- The reach comes only from smoothing: about 2 blocks of 4 cells (8 cells) around the building.
- The 45 real-world landmarks (types 18001..18045, parent 18000) have **no row and no ancestor row**:
  no land value effect.
- Only standing buildings count (occupancy state 1); rubble/defunct (state 8) does not.

## 2. Loading the table

`0x1001b54d` `sc3_landvalue_load_tuning` reads `\Sys\SC3LandValue.INI` and registers
`0x1001c532` as the `[AgentIDModifiers]` entry callback `[CONFIRMED @ 0x1001b54d]`.

`0x1001c532` `sc3_landvalue_parse_agent_modifier` `[CONFIRMED @ 0x1001c532]`:
- key = agent type id (the `CitySim.ini [AgentTypes]` id, also the save occupant record `+8`);
- value tokens `<n>:<class>`, class letter `R/C/I/A` (lower case accepted), `n` clamped to -127..127;
- result = 4 signed bytes R (+0), C (+1), I (+2), A (+3), stored in map `DAT_10058688` only if one is non-zero.

## 3. Applying a building: `0x1001d840` (iOS `occupantChanged`)

Called with `0` = add, `1` = subtract `[CONFIRMED @ 0x1001d840]`:

| Caller | When |
|---|---|
| `0x1001dae7` | `OccupantInserted`, slot 3 of `0x1004c5b4` = the layer's `cISC3CityChangeReceiver` at `layer+0x24` |
| `0x1001daf8` | `OccupantRemoved`, slot 4, same vtable (passes 1) |
| `0x1001d3f1` | full rebuild, for every occupant |

The receiver is registered by `0x1001d25c` (`SimulationBegin` shape): occupant manager from city `vt+0x11c`,
then manager `vt+0x28(layer+0x24)` `[CONFIRMED @ 0x1001d25c]`. Interface identity by slot arity, same rule as
`GZCOM_INTERFACE_CATALOGUE.md` (`OccupantInserted(uint32, cISC3Occupant*)`).

Steps inside `0x1001d840`:

1. **Gate.** If the occupant answers QI `0xe0faadc7` and its `vt+0x4c` is not 1, return without stamping.
   iOS: the test is `goBuilding +0x3c` (OccupancyState) `== 1`; `goBuildingLayer::PlaceBuilding` sets 1,
   `BecomeDefunctDueToAge` / `GetCorrespondingBuildingRubble` set 8 `[iOS-HINT]`. Same QI/`+0x4c` gate as the
   valve code (`PORTS_AIRPORTS.md`, `0x1002f5af`).
2. **Lookup.** Exact type id (`vt+0x88`) in `DAT_10058688`. If absent, walk the map and take the first row for which
   `IsAncestor(rowId, typeId)` is true, then cache that result (zeros included) under the type id. No agent type
   has two ancestor rows, so the walk order never matters. Identity of the call (2026-11-02, section 8):
   - the object is `layer+0x4c`, filled at init by `FUN_1003d02d` = `FUN_1003ceec()` (the app singleton) `vt+0x40`
     `[CONFIRMED @ 0x1001c854]`; `this` of the stamp is the layer base (`0x1001dae7` does `ecx -= 0x24`);
   - SDK `cISC3App` slot 16 (`+0x40`) = `GetAppAgentTypeTree`, slot 20 (`+0x50`) = `GetAppDataDirectory`, which
     is what every SIMRCI ini loader uses `+0x50` for;
   - `cISC3AgentTypeTree`: slots 11/12 are the `IsAncestor` overload pair; with the project's overload-reversal
     rule (`GZCOM_INTERFACE_CATALOGUE.md` 12a) `+0x24` = `IsAncestor(uint, uint)`, `+0x20` = `IsAncestor(uint,
     uint, uint&)`. The call pushes 2 arguments, matching `+0x24`;
   - argument order: other modules call the same slot as `(3000, type)`, `(5000, type)`, `(18000, type)`,
     `(12005, type)` (SIMRCI `0x1002f5af`, SIMGEOM `0x10008599`, SIMECO `0x100095e7`), so it is
     `IsAncestor(ancestor, descendant)`. The land value call passes `(rowId, typeId)`;
   - Linux `libSimInit.so` names the class `cSC3AgentTypeTree`, with `IsAncestor(uint,uint)`,
     `AddISARelationBetweenAgentTypes` and `cSC3App::AgentTypeTree()`;
   - the tree is built from `CitySim.ini [AgentTypeHierarchy]` (`SC3U.exe 0x0040cc08`).
   So a Small Park (14311, parent 14310) gets the 14310 Park row `[CONFIRMED by call topology + SDK slot map]`.
3. **Stamp.** For every cell of the occupant's bounding rect (`vt+0xd0`), read-add-write the 4 values into
   `+0x50` = A, `+0x6c` = R, `+0x88` = C, `+0xa4` = I.

## 4. The modifier maps and smoothing

- The 4 maps are int16 cell maps (vtable `0x1004c6b4`) with shift 2 (ctor `0x1001b2b9`): **one value per 4x4
  cells**. Get/set `0x1001edc1` / `0x1001ee43` index `rows[x>>2][y>>2]` `[CONFIRMED]`. Every footprint cell adds
  its row again to the block it lies in, so the total stamped = row x cell count.
- `0x1001d3f1` (iOS `recalcModMaps`): zero the 4 maps, stamp every occupant, then **2 passes** that replace each
  block by the average of its 3x3 block neighbourhood (in bounds only, in place, C integer division)
  `[CONFIRMED @ 0x1001d3f1]`.
- It runs at `SimulationBegin` and from `0x1001d616` each time the 16-step block cursor of the compute wraps.
  Between rebuilds, a newly placed building's stamp sits unsmoothed in its blocks (inserted -> step 3 only).

## 5. The land value formula (`0x1001deca`)

Per 2x2 cells, per cell `[CONFIRMED @ 0x1001deca]`:

- modifier = map value clamped to -150..+150, times 0.01 (`DAT_1004b29c`);
- R map for zone types 1-3, C for 5-7 / 0xe / 0x16, I for 9-0xb / 0xf, A for everything else;
- base = the Res/Com/Ind city-centre curve value (from `0x1001d2fa`) by distance; non-R/C/I cells use base 1, so A
  is nearly invisible;
- value = base x (1 + modifier + pollution/crime/traffic terms + water and hill bonus + homeless ordinance), stored
  as 1..255.

Correction: the earlier `0x1001deca` tracker note called `+0x50..+0xa4` pollution/crime/traffic grids. They are the
four modifier maps.

## 6. Size, measured by replay

Replaying the stamp + two smoothing passes for the Park row (`R = +50`), interior map, values = percent of base R:

| Setup | Stamped | Peak | Note |
|---|---:|---:|---|
| 1x1 park | 50 | +3 | gone after 1 block |
| 3x3 park, one block | 450 | +38 | +15..33 one block out |
| 3x3 park, across 4 blocks | 450 | +32 | flatter |
| nine 1x1 parks, one per block | 450 | +24 | wider |

Shipped footprints (16 `Cities/*.sc3` saves, occupant record flags bits 0-11): Police Station 13130 3x3, Fire
Station 3x3, School 13010 3x3, Hospital 3x3, City College 3x3, University 5x5, Library 2x2, Museum 3x3, Small Park
1x1, Big Park 3x3, Ball Park 4x4, Playground 2x2, Fountain 1x1, Statue 1x1, Mayor's House 2x2, City Hall 3x3.

Every landmark record in those saves has type 18000..18044 (Big Ben, Notre Dame, Statue of Liberty...). None
resolves to a row.

Types with no row and no ancestor row include: SmallPoliceStation 13120 (parent 13001), FreeClinic 13320,
PostOffice 13008, HistoricBuilding 14160, Church 14910, Arcology 1001, Dam 12510, Parking 12260, clean industry
8700/8900/9100, Agriculture 9300, the holiday buildings 20000..20002. Only 13130 Police Station carries the police row.

## 7. Open

- The `IsAncestor` body itself was not read (SC3U `SIMINIT` side); the reading rests on the slot map, the constant
  call sites and the Linux names (section 3).
- Who calls `0x1001d25c` (the layer vtable slot) not traced.
- The pollution special routine `SIMECO 0x1000a032` (recycling, incinerator, waste-to-energy, water treatment) not read.

## 8. The other three per-building tables

All three use the same gate (QI `0xe0faadc7`, `vt+0x4c == 1`), the same add/subtract mode, and fall back to an
ancestor row when the type has none. No type has two ancestor rows in any of the four tables.

| Table | Row format | Parse | Stamp | Fallback |
|---|---|---|---|---|
| `SC3Aura.ini` | `radius,amount` | SIMMISC `0x100020a3`: first token -> byte `+2` (radius), rest -> signed char in short `+0` (amount); **row dropped if amount == 0** (only `12101=0,0`) | SIMMISC `0x1000314a`: amount added flat to every cell of the occupant rect grown by radius, map `this+0x5c` | first row with `IsAncestor(row, type)` (`this+0x38` = `App vt+0x40` via `FUN_1003216b`) |
| `SC3Crime.ini` | `radius,amount` | SIMSERV `0x1000689e`: first token -> byte `+1` (radius), rest -> `atol` clamped -127..127, byte `+0` (amount) | SIMSERV `0x10007d35`: amount added flat over rect grown by radius | row with smallest ancestor distance via `vt+0x20` = `IsAncestor(a, b, &dist)` |
| `SC3Pollution.ini` | `air:r,water:r,garbage` | SIMECO `0x1000564a` | SIMECO `0x100095e7`: footprint + linear falloff (`PORTS_AIRPORTS.md` 3.1) | walk parents (`GetNode` `vt+0x1c`, parent `vt+0x28`) until a row or type 50 |

Field order: both loaders split with the same 470-byte routine (SIMMISC `0x1002ad9b` = SIMSERV `0x10010741`, identical
after normalising names) that returns the text before the first `,` and removes it plus the comma from the source.
So the **first number is the radius, the second the signed amount** `[CONFIRMED @ 0x100020a3, 0x1000689e]`. This fits
the data: every first field is >= 0 and every second field is signed.

Pollution: recycling 12851, incinerator 12852, waste-to-energy 12853 and water treatment 12820 (and descendants)
first go through `0x1000a032`, then still get the normal table stamp `[CONFIRMED @ SIMECO 0x1000969b]`.

Readings from the resolved tables (workbook "All effects by building"):
- Police Station 13130 has **no crime row**. Police act on crime through coverage (`SC3Police.ini`), not this table.
  City Hall (-20, radius 20), Courthouse (-30, radius 30) and Quigley Castle (-80, radius 40) are the crime reducers.
- Parks: every park type gets the 14310 rows for land value (+50 R), aura (radius 8, +2) and crime (radius 3, +6),
  but has its own pollution row (Small Park -5 air, Big Park -20 air...).
- Schools, police, fire stations and hospitals add a little pollution (air 50-60, radius 10) and garbage.
