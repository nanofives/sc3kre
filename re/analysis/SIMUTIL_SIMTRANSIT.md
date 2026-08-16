# SIMUTIL.DLL + SimTransit.dll — power / water / traffic, first analysis

2026-08-14, companion to `SIMRCI.md`. Both confirm the GZCOM module recipe found there:
`GZDllGetGZCOMDirector` → guarded static director ctor → N × `register_class(GZCLSID, factory)`
→ factory `operator_new(size)` + ctor.

```
Apps\SIMUTIL.DLL      192,512 B  1,508 fns  SHA-256 AB99CC46…456DFC56  → re\ghidra_export_simutil\
Apps\SimTransit.dll   147,456 B  1,195 fns  SHA-256 B478DED4…19A6D3094  → re\ghidra_export_simtransit\
```

| module | director export | ctor | classes registered |
|---|---|---|---|
| SIMUTIL | `0x100170c0` | `0x1000c074` | **15** — 9 power plants, 4 water facilities, 2 big layer classes |
| SimTransit | `0x1000df14` | `0x100010d1` | **5** — TrafficLayer + 4 helpers |

Same correction as SIMRCI: `SC3PowerLayer` / `SC3WaterLayer` / `TrafficLayer` appear **only** as
INI paths (`\Sys\SC3PowerLayer.INI` `0x100283b4`, `\Sys\SC3WaterLayer.INI` `0x10028694`) and INI
section names (`MiscPowerLayerTunables` `0x1002835c`, `TrafficLayer` `0x1001f154`). They anchor
the **tunable loaders**, not the classes.

## S2 — the nine power plants `[CONFIRMED @0x1000c074 + factory bodies]`

This is the per-building-type class taxonomy that U-006 went looking for in the wrong place.
The real ids are a `0x?14a10??` cluster — nothing like CitySim.ini's `0x41F836xx`.

| GZCLSID | ctor | `new` size | plant | lifespan globals |
|---|---|---:|---|---|
| `0x814a0fbd` | `0x100081a0` | 0x54 | Coal | `0x100283d4/d8/dc` |
| `0x614a1014` | `0x100097aa` | 0x54 | Oil | `0x10028410/14/18` |
| `0xe14a102c` | `0x10008a03` | 0x54 | Gas | `0x100283ec/f0/f4` |
| `0xc14a1040` | `0x100091ff` | 0x54 | Nuclear | `0x10028404/08/0c` |
| `0xa14a106e` | `0x10009b49` | 0x54 | Solar | `0x1002841c/20/24` |
| `0x414a1097` | `0x10008da2` | 0x54 | Microwave | `0x100283f8/fc/00` |
| `0x214a10ae` | `0x1000865f` | 0x54 | Fusion | `0x100283e0/e4/e8` |
| `0x614a1057` | `0x1000aef0` | 0x54 | Wind | `0x10028438/3c/40` |
| `0x2302193a` | `0x10009f0e` | **0x64** | WasteToEnergy | `0x10028428/2c/30/34` |

Shared base ctor `sc3_powerplant_base_ctor` `0x10008232` installs a 3-vtable set
(`PTR_FUN_10020ea8` at `this`, `PTR_LAB_10020e78` at `+0x2c`, `PTR_LAB_10020cc8` at `+0x28`).
Each type ctor then lazily loads its own `[<PlantType>]` INI section (guard flags
`DAT_10028ae4`…`aec`) — `MaxLifeSpan` / `DeclineAge` / `PercentageVariationInLongevity` —
and calls `sc3_powerplant_set_lifespan` `0x10006ba6`.

### The power-plant object, fully mapped `[CONFIRMED]` (U-011)

| offset | dec | field | proven at |
|---|---:|---|---|
| `+0x00` | 0 | primary vtable (coal: `PTR_FUN_10020c48`) | `0x10006abe`, `0x10008232` |
| `+0x04` | 4 | 4-byte field, init 0, plain getter | `0x10006abe`, `0x10006b6b` |
| `+0x08` | 8 | **current derated OUTPUT** (per tick) | `0x10006c57` |
| `+0x0c` | 12 | **BASE CAPACITY** (derate input) | `0x10006c57`, `0x100069fb` |
| `+0x10` | 16 | u16 driving breakdown; exemplar key `0x2351faf8` | `0x10006c27`, `0x100077a6` |
| `+0x14` | 20 | construction-date sub-object (age source) | `0x10006abe`, `0x100120a1` |
| `+0x1c` | 28 | **MaxLifeSpan** (months); exemplar `0x2351faf9` | `0x10006ba6`, `0x100069fb` |
| `+0x20` | 32 | **DeclineAge** (months); exemplar `0x2351fafa` | `0x10006ba6`, `0x100069fb` |
| `+0x24` | 36 | 1-byte bool; exemplar `0x2351fafb` | `0x10006abe`, `0x100077a6` |
| `+0x28` | 40 | embedded sub-object (`PTR_LAB_10020cc8`, ctor `FUN_1001871b`) | `0x10008232` |
| `+0x2c` / `+0x30` | 44 / 48 | sub-object vtable slots | `0x10008232` |

**The capacity derate `[CONFIRMED @0x100069fb]`** — the actual SC3000 power output formula:

```
age = curYear*12 + curMonth - (builtYear*12 + builtMonth)      [0x100120a1]
if age >= MaxLifeSpan:  output = 0
else:                   output = cap - (age - DeclineAge) * cap / (MaxLifeSpan - DeclineAge)
```
i.e. full base capacity until `DeclineAge`, then linear falloff to zero at `MaxLifeSpan`.

**Breakdown `[CONFIRMED @0x10006c27]`** — `rand(MinOverworkMonths, MaxOverworkMonths) < u16 @+0x10`,
then `0x10006c67` posts message `0x434346e6`. Note this is *not* a per-plant failure float: it
combines one object field with the two `[MiscPowerPlantTunables]` globals.

Per-tick entry is `sc3_powerplant_tick` `0x10007afb` (vtable slot 18 / `+0x48`).

**Plant attributes come from EXEMPLAR keys** `0x2351faf8`…`fb` (`0x100077a6` load / `0x1000785c`
save) — a per-building data record system, distinct from the INI tunables. Worth a workstream.

`[UNCERTAIN]` — nothing in the plant cluster ever writes `+0xc` to a non-zero value; the write
that copies `[PowerPlantCapacities]` from the layer map into the plant is reached through a
vtable setter or layer-side code not yet read.

### ⚠ The iOS `goPowerPlant` field map is CONTRADICTED

`SIM_LAYERS_XREF.md` records the iOS field map as `+0x48 maxAge / +0x4c decayStart / +0x58 output
/ +0x5c baseCapacity / +0x60 failChance`. On the PC side `0x10006ba6` writes
**`MaxLifeSpan → this+0x1c` (28)** and **`DeclineAge → this+0x20` (32)**, and no SIMUTIL structure
read in this pass uses the `+0x48/+0x4c/+0x58/+0x5c/+0x60` cluster. The `[iOS-HINT]` is
**unconfirmed and actively contradicted for the life/decay fields**. Output / baseCapacity /
failChance offsets are `[UNCERTAIN]` — not yet located.

This is the first hard evidence of how far the iOS oracle diverges from the PC build. Treat iOS
struct layouts as leads only; the naming vocabulary survives, the offsets do not.

**Settled 2026-08-14 (U-011) — every iOS field maps to a different PC offset:**

| iOS field | iOS offset | PC offset | PC proof |
|---|---|---|---|
| maxAge | `+0x48` | **`+0x1c`** | `0x10006ba6`, `0x100069fb` |
| decayStart | `+0x4c` | **`+0x20`** | `0x10006ba6`, `0x100069fb` |
| output | `+0x58` | **`+0x08`** | `0x10006c57` |
| baseCapacity | `+0x5c` | **`+0x0c`** | `0x10006c57` |
| failChance | `+0x60` | **no equivalent** | `0x10006c27` uses u16 `+0x10` + 2 globals |

On the PC object the iOS range `+0x48…+0x60` falls *inside the embedded sub-object at `+0x28`*,
which has nothing to do with lifespan/capacity/output. The shared **concepts** all survive
(max lifespan, decline age, age-linear derate, INI-driven capacities, overwork breakdown); the
**layout** does not. Zero of five offsets transfer.

### Power layer class `[UNCERTAIN]`
`sc3_power_load_layer_tunables` `0x10004979` is the layer-level loader (`PowerPlantCapacities`
list + `MiscPowerLayerTunables` ordinance savings → `_DAT_100289ec` / `_DAT_100289e8`, each
`= (float)val * _DAT_10020790`). **It has no direct caller** — it is reached through a layer
vtable slot. The power layer is therefore one of the two big standalone classes:

- `0x82bf0042` → ctor `0x1000c645`, 0xe8 = 232 B, vtable `PTR_FUN_10022944`
- `0x20afdf44` → ctor `0x10003275`, 0x2fc = 764 B, vtables `PTR_FUN_10020748` / `PTR_FUN_10020608`

Which is Power and which is Water is **not resolvable from the text export**. Finding the vtable
slot that calls `0x10004979` settles it.

### Power grid raster — not found
No `Bit1_*`-style raster or `SelectionGrow` cap-600 flood-fill was encountered. The two layer
classes' internals were not walked (indirect dispatch). `[UNCERTAIN]`, open.

## S2 — water
`sc3_water_load_layer_tunables` `0x1000c8e2` reads `\Sys\SC3WaterLayer.INI` sections
`AgentIDModifiers` / `WaterFromPipe` / `TuningParameters`: `WaterPumpDistanceFactor`,
`WaterTowerCapa`, `WaterPumpCapa`, `DesaltPlantCapa`, `WaterConservationFactor`,
`WaterMeterFactor`, `DefaultConsumption`, `DefaultLeak`, `WaterTowerLife`, `WaterPumpLife`,
`DesaltPlantLife` → globals `0x10028568`…`0x10028594`.

Four water-facility classes: `0xa2fd2580` (0x54, ctor `0x10012d4a`), `0x02fd2c92` (0x54),
`0xc2fd2c98` (0x54), `0x62fd2c9f` (0x4c, ctor `0x10001082`). Which is pump / tower / desalt /
valve is `[UNCERTAIN]` — needs each ctor read.

## S6 — TrafficLayer `[CONFIRMED]`

**GZCLSID `0x029ca806`** → factory `0x1000116f` → `operator_new(0x110)` (272 B) → ctor
`sc3_traffic_layer_ctor` `0x100012bf`, vtables `PTR_FUN_1001a368` / `PTR_LAB_1001a350`. The ctor
copies loaded tunables straight into instance fields (`this+0xc4` = `TripThresholdPercent`,
`+0xc5/c6/c7` = `TripMaxDistanceToRoad*`, `+0xc9` = `UseMassTransitChance`).

`sc3_traffic_load_layer_tunables` `0x100015b1` (9,527 B) reads `\Sys\STTraffic.INI` — ~90 keys:
`TripCellCostBaseRoad` / `RoadBus` / `Highway` / `HighwayBus` / `BusStop` / `RailStation` /
`Subway`, `TripMaxDistanceToRoadRes/Com/Ind/Default`, `TripDensityAdder`, `TrafficMaxDensity`,
`TrafficUseMassTransitChance`, `TripChanceCountingBase/DensityMultiplier`; plus section
`TrafficTripDestinationThresholds` `FromResidential/Commercial/Industrial/MixedOrAll`, each
parsed `sscanf "%u %u %u"` → `DAT_1001fd60`…`6b` (defaults 10 / 40 / 100).

`sc3_traffic_layer_sim_begin` `0x10003ae8` builds **four per-zone-type trip-destination tables**
(`FUN_10009b78(type, index)` for type 0–3 = Res/Com/Ind/Mixed) into `DAT_1001fd74`…`0x1001fdb4`.

**The trip/cell-cost commute model is confirmed SC3-side** — per-mode cell costs, per-zone max
road distance, per-zone destination thresholds, four destination tables. This is consistent with
the iOS `StepTrip` / `EvaluateTripData` / `CalcTripDestinationBits` family, but no individual
SimTransit function has been matched to those names — they stay `[iOS-HINT]`.

Four helper classes: `0x82fe76aa` (0x40), `0x62fe76b6` (0x44), `0xc2fe76c1` (0x44),
`0xa2fe76cf` (0x40) — `[UNCERTAIN]`.

## Next probes
1. **Which big class is the power layer** — live-Ghidra walk of `PTR_FUN_10022944` /
   `PTR_FUN_10020748` for the slot calling `0x10004979`; then hunt its Simulate method for the
   grid flood-fill. Grep first: `query.ps1 -Xref FUN_10004979`.
2. **Plant field map beyond `+0x20`** — read `FUN_10006abe` (deeper base ctor) and a plant
   Simulate/capacity method for per-tick output and failure chance.
3. **Traffic per-tick core** — read `FUN_10009b78` and the `PTR_FUN_1001a368` method iterating
   `DAT_1001fd74`… to find the SC3 equivalent of `CalcTripDestinationBits`.
