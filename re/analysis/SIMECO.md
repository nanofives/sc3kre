# SIMECO.md — SimCity 3000 ecology / pollution director module

Module: `Apps\SIMECO.DLL` (151,552 bytes). Image base in this export = `0x10000000`.
All addresses below are Ghidra VAs in the SIMECO export. Facts drawn from
`re/ghidra_export_simeco/functions/` are marked `[CONFIRMED @ 0xADDR]`.

## 1. Purpose

SIMECO.DLL is the **ecology layer**: it owns air pollution, water pollution, and the
garbage/solid-waste subsystem. It is a GZCOM director that registers one large layer class
plus two small building-tuning models (Incinerator, Recycling Center). Grounding evidence:
its tuning loaders open `\Sys\SC3Pollution.INI` `[CONFIRMED @ 0x100046bb:56]` and read a
`[TuningParameters]` block of air/water/garbage pollution thresholds and 14 ordinance-effect
percentages `[CONFIRMED @ 0x100046bb]`; its per-tick method spreads pollution across the map
grid, applies those ordinance modifiers, and routes garbage to incinerators / recycling /
landfill / waste-to-energy `[CONFIRMED @ 0x10008249, 0x100094a2]`. The `SC3PowerLayer.ini`
string that `MODULE_MAP.md` flagged is a **cross-read**: `FUN_100046bb` opens it only to fetch
the `WasteToEnergyPowerPlant` garbage-cap `[CONFIRMED @ 0x100046bb:547]`, so it does not mean
SIMECO owns the power layer — this resolves the `[UNCERTAIN]` note at MODULE_MAP.md:55-57.

`[iOS-HINT]` The iOS sibling names the equivalent class `goPollutionLayer`
(`re/ghidra_export_ios/functions/002d58d4__goPollutionLayer.c`), with siblings
`GetOccupantPollutionGenerated`, `decay`, `findNewDumpPoint`. Algorithm shapes transfer;
struct offsets do not.

## 2. Director + registrations

Standard GZCOM recipe, fully recovered:

- **PE export** `GZDllGetGZCOMDirector` @ `0x1001234d` — guarded one-time init: sets bit 0 of
  `DAT_1002086c`, calls the director ctor on `&DAT_10020828`, registers an `_onexit` cleanup
  (`LAB_1000e698`), returns `&DAT_10020828` `[CONFIRMED @ 0x1001234d]`.
- **Director ctor** `FUN_1000e54e` @ `0x1000e54e` — calls base-director ctor `FUN_10012352`
  (which zero-inits the class map at `this+0x14` and installs vtables `PTR_FUN_1001c508` /
  `PTR_LAB_1001c4dc`), installs this director's vtables (`PTR_FUN_1001c14c`,
  `PTR_LAB_1001c120`), then registers **3** classes `[CONFIRMED @ 0x1000e54e]`.
- **register_class** `FUN_100126d3` @ `0x100126d3` — inserts `{GZCLSID, factory, 0}` into the
  map at `director+0x14` via `FUN_1001296e` `[CONFIRMED @ 0x100126d3]`.

| GZCLSID | factory RVA | `operator_new` size | object ctor | role |
|---|---|---|---|---|
| `0xc0a81498` | `0x1000e5c8` | `0x4d0` (1232) | `FUN_10004379` | main ecology/pollution+garbage layer (`goPollutionLayer`); factory returns `object + 0x1c` (the `puVar2 + 7` sub-interface) `[CONFIRMED @ 0x1000e5c8:25]` |
| `0x0345776c` | `0x1000e606` | `0x48` (72) | `FUN_10001020` | Incinerator building-tuning model `[CONFIRMED @ 0x1000e606, 0x10001020]` |
| `0xc34acd28` | `0x1000e638` | `0x44` (68) | `FUN_1000302b` | Recycling-Center building-tuning model `[CONFIRMED @ 0x1000e638, 0x1000302b]` |

No `SC3*Layer` *class-name* string is present in the module body; the only layer string is the
INI path `SC3PowerLayer.ini` (a cross-read), matching MODULE_MAP.md's corrected note that these
are config-loader anchors, not class names.

## 3. Key subsystems

**`FUN_10004379` @ 0x10004379 — main layer ctor (0x4d0 bytes).** Installs the object's primary
vtable `PTR_FUN_1001ba94` and six secondary vtables at `+0x1c…+0x30` (`PTR_LAB_1001b984 …
b8b8`). Allocates seven intrusive-list heads via `FUN_10002671` at object dwords `[0x2d..0x34]`
(each self-linked: `node->next = node->prev = node`) — these are the occupant lists later
walked by the tick. Constructs sub-vtable objects at `[0x4a]=PTR_FUN_1001bb38`,
`[0x51]=PTR_FUN_1001baf0`, `[0x16]/[0x1d]=PTR_FUN_1001bb80`, and a member at `[0x126]` via
`FUN_1000a3ba` (the map/grid helper) `[CONFIRMED @ 0x10004379]`.

**`FUN_100046bb` @ 0x100046bb — pollution tuning loader (3983 bytes).** Opens
`\Sys\SC3Pollution.INI` then overlays `\Sys\SYS.PAK` (via resource-manager singleton
`FUN_100162e9`, vtable+0x50), and reads, from section `[TuningParameters]`, the whole tunable
set into module globals (table in §4). It also parses the `[AgentIDModifiers]` section with a
per-entry callback `FUN_1000564a` `[CONFIRMED @ 0x100046bb:64-68]`, and cross-reads
`OptimalGarbageCap` from `[Incinerator]` in `SC3Tune.INI` (→`DAT_10020250 = value*0x1e`) and
from `[WasteToEnergyPowerPlant]` in `SC3PowerLayer.INI` (→`DAT_10020254 = value*0x1e`)
`[CONFIRMED @ 0x100046bb:528-564]`. The `*0x1e` (×30) scales a daily cap to a monthly one.

**`FUN_10005844` @ 0x10005844 — layer init / service wiring (2307 bytes).** Guarded by
`this+0x18`. Acquires the owning simulator (`param_1`) and caches sub-service pointers returned
by owner vtable slots `+0x14c, +0x17c, +0x18c, +0x158, +0x144, +0x1b8` into `this+0x24,0x2c,
0x30,0x20,0x28`; also grabs two globals via `FUN_100120e3` and `FUN_10016377`. Calls `Init`
(vtable+0x2c) on four sub-layers at `this+0x3c,0x58,0x10c,0x128`. Allocates a `0xf0`-byte
messaging/notifier object at `this+0xf4` and **subscribes to messages** `0xe3079ef9`
(vtable+0x54) and `0xe3079f00` (vtable+0x58) plus three prior `+0x50` subscriptions. Optionally
builds a `0x44`-byte object at `this+0x13c` (only if owner vtable+0x1b8 returns non-null and its
first method returns true), then computes `this+0x46c = (w*h) / (UpdatePeriod<<2)` using
`DAT_1002023c` `[CONFIRMED @ 0x10005844:314-315]` and initializes the grid bounds at
`this+0x488..0x494`. Text keys used: group `0x029541f4`, instances `0x167`, `0x1d9`.

**`FUN_10008249` @ 0x10008249 — pollution + garbage tick (2875 bytes).** The core per-period
update. Steps `[CONFIRMED @ 0x10008249]`:
1. Walks occupant lists `[0x2d]`,`[0x2e]`,`[0x2f]` summing production (method+0x34) and demand
   (method+0x38), counting active producers, into `param_1[0x35..0x36], [0x57], [0x58]`.
2. Queries 12 ordinances (see §5) into local flags, and pulls incinerator throughput via
   `param_1[0x13]` method+0x8c(5) `→ local_ac/0x1e`, adding it to accumulators `[0x112],[0x114]`.
3. Calls garbage router `FUN_100094a2`.
4. Main grid loop over `param_1[0x122]` cells: reads base air/land/water pollution from three
   sub-grids (`param_1[0x16]`,`[0x1d]`,`[0x4a]` method+0x34), applies ordinance % reductions,
   then a 2×2 sub-cell loop that reads tile type (method+0x34 on `[0x10]`), applies
   per-terrain-type ordinance effects, reads traffic (`[0x11]` method+0x60, scaled by
   `TrafficAirFactor`), accumulates into per-category totals `[0x3d]=air, [0x3e]=water,
   [0x3f]=garbage, [0x40..0x43]`, and writes back clamped values (0..0x7fff) into the pollution
   grids (method+0x98/0x9c), rate-limited per step by `MaxAir/WaterPolluteForUI` divisors
   (`DAT_1002025c>>3`, `DAT_10020260/0x78`, `/0xc`).
5. Final pass redistributes unserviced garbage back across the three occupant lists.

**`FUN_100094a2` @ 0x100094a2 — garbage disposal router (325 bytes).** Given an amount, drains
it in priority order: recycling reserve (`param_3`), incinerator reserve (`param_2`), a service
object at `this+0x158` (method+0x30/+0x40, the waste-to-energy plant), then a landfill object at
`this+0x4c` (method+0x8c(4)), then abduction/overflow capped by `GarbageAbductionAmount`
(`DAT_10020270 - this+0x480`) `[CONFIRMED @ 0x100094a2:92-98]`. Returns amount successfully
disposed.

**`FUN_1000c95c` @ 0x1000c95c — pollution advisor text builder (5952 bytes).** For a tile
(param_1,param_2) and a query category (param_5 = 0..4) produces a localized description string
(IXF group `0x82e0074c`). Category 0 = combined air+water land-value impact (bands on
`param_2/5, ×1, ×5, ×10, ×0x32`, text ids `0x29..0x2f`); category 3 = air (bands on
`DAT_1002025c>>3, >>2, >>1, <<2)/5`, ids `0x187..0x18d`); category 4 = water (bands on
`DAT_10020260`, ids `0x18e..0x194`). Sets `*param_6=1` on the worst band `[CONFIRMED @
0x1000c95c]`.

**`FUN_1000c763` @ 0x1000c763 — tile query dispatcher (505 bytes).** On a map-tool query
(`param_2`), reads tile coords (method+0x40), then calls `FUN_1000c95c` for the 5 categories,
pushing each returned string to the UI (method+0x4c) with a category flag: cat0→`0x4000`,
cat1→`0x20000`, cat2→`0x20000`, cat3→`0x2000`, cat4→`0x8000` `[CONFIRMED @ 0x1000c763]`.

**`FUN_1000564a` @ 0x1000564a — `[AgentIDModifiers]` entry parser (445 bytes).** Key→agent id
(`FUN_10012ad7`), value parsed with `sscanf` format `"%d %d %d %d %d"` (`s__d__d__d__d__d_100204fc`)
into 5 fields, clamped to signed-16 (`±0x7fff`, i.e. `0x8001..0x7fff`) and unsigned-8
(`0..0xff`), stored into the agent-id→modifier map `DAT_10020818` `[CONFIRMED @ 0x1000564a]`.

**Polluted-tile predicates (each 34 bytes):**
- `FUN_10008e67` @ 0x10008e67 — air: reads grid (vtable+0x58), returns `value >= AirPollutedThreshold` (`DAT_10020264`) `[CONFIRMED @ 0x10008e67]`.
- `FUN_10008e89` @ 0x10008e89 — water: (vtable+0x5c) vs `WaterPollutedThreshold` (`DAT_10020268`) `[CONFIRMED @ 0x10008e89]`.
- `FUN_10008eab` @ 0x10008eab — garbage: (vtable+0x60) vs `GarbagePollutedThreshold` (`DAT_1002026c`) `[CONFIRMED @ 0x10008eab]`.

**Incinerator model `FUN_10001020`** reads `[Incinerator]` keys `OptimalGarbageCap`,
`MaxLifespan`, `DeclineAge` from `SC3Tune.INI` → `DAT_100200a0/a4/a8`, with guards
`if(a4==0)a4=1` and `if(a4<a8)a8=a4>>1`; one-shot via `DAT_100207a8` `[CONFIRMED @ 0x10001020]`.
**Recycling model `FUN_1000302b`** reads `[RecyclingCenter]` keys `OptimalPctReduction`,
`OptimalPopServed`, `MaxLifespan`, `DeclineAge` → `DAT_100201f4/f8/fc, DAT_10020200`, same
guards; one-shot via `DAT_1002080c` `[CONFIRMED @ 0x1000302b]`.

## 4. Data / tunables

INI/resource keys (all in `[TuningParameters]` of `\Sys\SC3Pollution.INI` unless noted; values
read via `FUN_1001599c` and converted with `FUN_10012ad7`). All `[CONFIRMED @ 0x100046bb]`:

| Key (string RVA) | global | notes |
|---|---|---|
| `UpdatePeriod` (0x100204c0) | `DAT_1002023c` | forced `>=1`; divides grid work per tick |
| `CleanAirOrdEffect` (0x10020498) | `DAT_1002023e` | % |
| `LeafBurningBanOrdEffect` (0x10020480) | `DAT_1002023f` | % |
| `TrashPresortOrdEffect` (0x10020468) | `DAT_10020240` | % |
| `CarSmoggingOrdEffect` (0x10020450) | `DAT_10020241` | % |
| `ConservationCorpsOrdEffect` (0x10020434) | `DAT_10020242` | % |
| `IndPolluteFeeOrdEffect` (0x1002041c) | `DAT_10020243` | % |
| `LawnChemBanOrdEffect` (0x10020404) | `DAT_10020244` | % |
| `LandfillGasRecoveryOrdEffect` (0x100203e4) | `DAT_10020245` | % |
| `IndWasteDisposalOrdEffect` (0x100203c8) | `DAT_10020246` | % |
| `BackyardCompostingOrdEffect` (0x100203ac) | `DAT_10020247` | % |
| `PaperReductionOrdEffect` (0x10020394) | `DAT_10020248` | % |
| `TireRecyclingOrdEffect` (0x1002037c) | `DAT_10020249` | % |
| `TrafficAirFactor` (0x10020368) | `DAT_1002024c` | multiplies traffic byte per sub-cell |
| `MaxGarbagePolluteForUI` (0x10020350) | `DAT_10020258` | |
| `MaxWaterPolluteForUI` (0x10020338) | `DAT_10020260` | tick uses `/0x78`, `/0xc`, `>>1/2/3` bands |
| `MaxAirPolluteForUI` (0x10020324) | `DAT_1002025c` | tick uses `>>3`, and `<<2)/5` bands |
| `GarbagePollutedThreshold` (0x10020308) | `DAT_1002026c` | predicate cutoff |
| `WaterPollutedThreshold` (0x100202f0) | `DAT_10020268` | predicate cutoff |
| `AirPollutedThreshold` (0x100202d8) | `DAT_10020264` | predicate cutoff |
| `GarbageAbductionAmount` (0x100202c0) | `DAT_10020270` | landfill/abduction overflow cap |
| `GarbageScalingFactor` (0x100202a8) | `_DAT_10020274` | `= (float)value * _DAT_1001bdec` |
| `AgentIDModifiers` (0x100204d0) | `DAT_10020818` map | per-agent `%d %d %d %d %d` records |
| `OptimalGarbageCap` (0x100200e0) `[Incinerator]` in `SC3Tune.INI` | `DAT_10020250` | `= value*0x1e` |
| `OptimalGarbageCap` `[WasteToEnergyPowerPlant]` in `SC3PowerLayer.INI` | `DAT_10020254` | `= value*0x1e` |

Building models: `[Incinerator]`/`SC3Tune.INI` → `OptimalGarbageCap` `DAT_100200a0`,
`MaxLifespan` (0x100200c8) `DAT_100200a4`, `DeclineAge` (0x100200bc) `DAT_100200a8`.
`[RecyclingCenter]`/`SC3Tune.INI` → `OptimalPctReduction` (0x10020228) `DAT_100201f4`,
`OptimalPopServed` (0x10020204) `DAT_100201f8`, `MaxLifespan` `DAT_100201fc`, `DeclineAge`
`DAT_10020200`.

Fixed resource keys: `\Sys\SC3Pollution.INI` (0x100204e4), `\Sys\SC3Tune.INI` (0x10020104),
`\Sys\SYS.PAK` (0x100200f4), `\Sys\SC3PowerLayer.INI` (0x10020290). IXF text groups:
`0x82e0074c` (pollution advisor strings, instances `0x29..0x2f`, `0x10c..0x10f`, `0x187..0x194`,
`0x18f`/`0x190`), `0x029541f4` (init strings `0x167`, `0x1d9`).

`[UNCERTAIN]` The numeric values of float data constants `_DAT_1001bdec` (GarbageScalingFactor
multiplier), `_DAT_1001bdf0`, `_DAT_1001bdf8`, `_DAT_1001bf30`, `_DAT_1001bf38`, `_DAT_1001b5a8`
(a rounding bias, `+0.5`-style) are not readable from the C export — needs the `.rdata` bytes
at those RVAs.

## 5. Cross-module edges

- **Owning City Simulator** — SIMECO does not create the sim; `FUN_10005844` receives it and
  binds sub-services through its vtable (`+0x144, +0x158, +0x17c, +0x18c, +0x1b8`)
  `[CONFIRMED @ 0x10005844]`. `[UNCERTAIN]` the concrete GZCLSID of that simulator (obtained by
  the caller, not by SIMECO).
- **Ordinance service** — queried each tick via `param_1[0xf]` method+0xc with these ordinance
  ids `[CONFIRMED @ 0x10008249:127-138]`, each gating the matching tunable:
  `0x42bf1e18`→TrashPresort, `0x22bf1e35`→LeafBurningBan, `0xa2bf1e43`→CleanAir,
  `0xc2bf1e04`→CarSmogging, `0xa2f6e7da`→ConservationCorps, `0x02f6e7e2`→IndPolluteFee,
  `0x62f6e808`→LawnChemBan, `0x22f6e80c`→LandfillGasRecovery, `0xa2f917cf`→IndWasteDisposal,
  `0x22f6e814`→BackyardComposting, `0x22f6e81b`→PaperReduction, `0xc2f6e81f`→TireRecycling.
- **Message bus** — subscribes to `0xe3079ef9` and `0xe3079f00` via the notifier at `this+0xf4`
  `[CONFIRMED @ 0x10005844:186-189]`. `[UNCERTAIN]` message semantics (names live elsewhere).
- **Resource/INI manager** — singleton via `FUN_100162e9`, `.vftable+0x50` opens a resource by
  name; used by every tuning loader `[CONFIRMED @ 0x100046bb, 0x10001020, 0x1000302b]`.

## 6. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1001234d,gzcom-director,C2,sc3_eco_get_gzcom_director,"PE export; guarded ctor of &DAT_10020828, onexit LAB_1000e698 [CONFIRMED @ 0x1001234d]"
0x1000e54e,gzcom-director,C2,sc3_eco_director_ctor,"base ctor FUN_10012352 + 3x register_class; vtables PTR_FUN_1001c14c/1001c120 [CONFIRMED @ 0x1000e54e]"
0x10012352,gzcom-director,C2,sc3_eco_director_base_ctor,"zero-inits class map at this+0x14, installs PTR_FUN_1001c508 [CONFIRMED @ 0x10012352]"
0x100126d3,gzcom-director,C2,sc3_eco_register_class,"inserts {clsid,factory,0} into map this+0x14 via FUN_1001296e [CONFIRMED @ 0x100126d3]"
0x1000e5c8,gzcom-factory,C2,sc3_eco_factory_pollution_layer,"new(0x4d0)+FUN_10004379, returns object+0x1c; clsid 0xc0a81498 [CONFIRMED @ 0x1000e5c8]"
0x1000e606,gzcom-factory,C2,sc3_eco_factory_incinerator,"new(0x48)+FUN_10001020; clsid 0x0345776c [CONFIRMED @ 0x1000e606]"
0x1000e638,gzcom-factory,C2,sc3_eco_factory_recycling,"new(0x44)+FUN_1000302b; clsid 0xc34acd28 [CONFIRMED @ 0x1000e638]"
0x10004379,pollution-layer,C2,sc3_pollution_layer_ctor,"0x4d0 obj; vtable PTR_FUN_1001ba94; 7 self-linked lists at [0x2d..0x34] [CONFIRMED @ 0x10004379]"
0x10005844,pollution-layer,C2,sc3_pollution_layer_init,"binds owner sub-services, Init 4 sublayers, subscribes msg 0xe3079ef9/0xe3079f00, grid bounds [CONFIRMED @ 0x10005844]"
0x10008249,pollution-tick,C2,sc3_pollution_update_tick,"per-period grid spread; ordinance modifiers; garbage route; clamps 0..0x7fff [CONFIRMED @ 0x10008249]"
0x100094a2,garbage,C2,sc3_garbage_route_disposal,"drains to recycle/incin/W2E/landfill/abduction cap DAT_10020270 [CONFIRMED @ 0x100094a2]"
0x100046bb,tunables,C2,sc3_pollution_load_tuning,"opens SC3Pollution.INI+SYS.PAK; reads TuningParameters + AgentIDModifiers [CONFIRMED @ 0x100046bb]"
0x1000564a,tunables,C2,sc3_pollution_parse_agent_modifier,"key->agentid, sscanf '%d %d %d %d %d', clamp, store DAT_10020818 [CONFIRMED @ 0x1000564a]"
0x1000c95c,pollution-ui,C2,sc3_pollution_build_advisor_text,"tile+category -> IXF group 0x82e0074c banded strings; sets worst flag [CONFIRMED @ 0x1000c95c]"
0x1000c763,pollution-ui,C2,sc3_pollution_query_tile,"tool query -> 5x advisor text w/ UI flags 0x4000/0x20000/0x2000/0x8000 [CONFIRMED @ 0x1000c763]"
0x10008e67,pollution-ui,C2,sc3_pollution_is_air_polluted,"grid vtable+0x58 vs AirPollutedThreshold DAT_10020264 [CONFIRMED @ 0x10008e67]"
0x10008e89,pollution-ui,C2,sc3_pollution_is_water_polluted,"grid vtable+0x5c vs WaterPollutedThreshold DAT_10020268 [CONFIRMED @ 0x10008e89]"
0x10008eab,pollution-ui,C2,sc3_pollution_is_garbage_polluted,"grid vtable+0x60 vs GarbagePollutedThreshold DAT_1002026c [CONFIRMED @ 0x10008eab]"
0x10001020,building-model,C2,sc3_incinerator_ctor_load_tuning,"[Incinerator] OptimalGarbageCap/MaxLifespan/DeclineAge -> DAT_100200a0/a4/a8 [CONFIRMED @ 0x10001020]"
0x1000302b,building-model,C2,sc3_recycling_ctor_load_tuning,"[RecyclingCenter] OptimalPctReduction/OptimalPopServed/MaxLifespan/DeclineAge -> DAT_100201f4/f8/fc/0200 [CONFIRMED @ 0x1000302b]"
0x100162e9,resource-mgr,C1,sc3_eco_get_resource_mgr,"singleton; vtable+0x50 opens named resource; used by all loaders [CONFIRMED @ 0x100046bb:54]"
0x1001589f,ini,C1,sc3_eco_ini_ctor,"config object ctor before section reads [CONFIRMED @ 0x100046bb:518]"
0x1000f121,ini,C1,sc3_eco_ini_open_file,"attaches an INI path to config object [CONFIRMED @ 0x100046bb:58]"
0x10015981,ini,C1,sc3_eco_ini_overlay_pak,"overlays SYS.PAK onto config object [CONFIRMED @ 0x100046bb:63]"
0x1001599c,ini,C1,sc3_eco_ini_read_key,"reads section.key -> string, returns found flag [CONFIRMED @ 0x100046bb:81]"
0x10015c93,ini,C1,sc3_eco_ini_iter_section,"iterates section entries with callback (AgentIDModifiers) [CONFIRMED @ 0x100046bb:68]"
0x10012ad7,util,C1,sc3_eco_str_to_int,"string->int on INI values [CONFIRMED @ 0x100046bb:91]"
0x10016427,ixf-text,C1,sc3_eco_text_key_ctor,"builds IXF text key (instance,group) [CONFIRMED @ 0x1000c95c:234]"
0x1001645f,ixf-text,C1,sc3_eco_text_fetch,"fetches localized text for a key [CONFIRMED @ 0x1000c95c:236]"
0x1000a80b,util,C1,sc3_eco_agentmap_at,"indexes agent-modifier map DAT_10020818 [CONFIRMED @ 0x1000564a:99]"
```

## 7. OPEN

- **Float `.rdata` constants** `_DAT_1001bdec, _DAT_1001bdf0, _DAT_1001bdf8, _DAT_1001bf30,
  _DAT_1001bf38, _DAT_1001b5a8` — values not in the C export. Missing evidence: raw bytes at
  those RVAs (dump `.rdata`, or a globals.csv for the SIMECO project — none exists in
  `re/ghidra_export_simeco/`).
- **Owning simulator GZCLSID** and the meaning of message ids `0xe3079ef9` / `0xe3079f00` — not
  determinable inside SIMECO; needs the module that publishes them (SIMCITY.DLL / SIMMISC.DLL)
  or the ASCII clsid table in `SYS.PAK`/`CitySim.ini`.
- **Ordinance id → in-game ordinance name** — the 12 ids in §5 are confirmed as the query keys
  gating each `*OrdEffect`, but the human names come from the ordinance module / IXF, not read
  here.
- **Sub-layer object identities at `this+0x3c/0x58/0x10c/0x128/0xf4/0x13c`** — described
  mechanically (Init'd sublayers; notifier; optional 0x44 object). Missing evidence: their
  vtable RVAs' owning ctors and any name strings.
- **The 0x44-byte optional object (`this+0x13c`)** built only when owner vtable+0x1b8 yields a
  true condition — purpose (`GarbageAbductionAmount` is UFO garbage abduction in SC3, so this is
  plausibly the abduction/disaster hook) not confirmed; needs its ctor `FUN_1000a32e` and the
  method ids +0xc/+0x50/+0x54 it calls.
- **`FUN_1000c95c` categories 1 and 2** (both push with UI flag `0x20000`, text ids
  `0x2a..0x2c` region) — exact air-vs-water assignment for cats 1/2 not separated; the branch
  structure was read but the category-to-pollutant binding for those two is `[UNCERTAIN]`.

---

Note: `re/ghidra_export_simeco/` contains only the `functions/` tree in this export (no
`symbols.csv` / `globals.csv` / `EXPORT_INFO.txt`), which is why the float constant values in §4
and §7 could not be resolved read-only.
