# Sim-layer cross-RE: power / zoning / traffic / demand (iOS models + SC3U anchoring status)

Goal: document the algorithm/vocabulary of the core sim layers from the iOS named oracle,
ready to anchor into the stripped SC3U binary. `[iOS-CONFIRMED]` = read from iOS decomp;
SC3U twins are `[iOS-HINT]` until anchored by SC3U-side evidence.

## Honest anchoring status (read this first)
- **SC3U has NO name anchors for the sim layers.** Confirmed: SC3U `strings.csv` contains no
  `cSC3…`/`go*Layer`/power/zone/traffic class strings (only `OccupantKeys` + `OccManAnim::`
  debug asserts). So the sim layers cannot be found by string xref.
- **Best available lead = the GZCOM AgentType registry.** The bootstrap hub
  `sc3_boot_register_all_factories` (`0x0040b761`) registers `AgentTypes` (magic `sc3agenttype`,
  factory `sc3_factory_agenttypes` `0x0040cb70`) and `AgentTypeHierarchy` (`sc3typehierarchy`,
  `0x0040cc08`). SC3's `go*Layer` objects are GZCOM **agents**; the agent-type table is where
  their class IDs/vtables are registered. Following what `0x0040cb70` reads (the agent-type
  records from `SYS.PAK`/`CitySim.ini`) is the concrete path to enumerating the sim layers by
  their 4CC/GZCLSID — a focused live-Ghidra xref session (the text export doesn't resolve the
  indirect vtable/data-table dispatch).
- Structural fallbacks: the shared **`Bit1_*` 1-bit raster flood-fill** (power/water/traffic
  reachability) and distinctive per-layer **constants** (below). No SC3U twin is committed to
  `functions.csv` yet — NO-GUESSING; these are documented leads.

## S2 — Power (`goPowerLayer` / `goPowerPlant`) `[iOS-CONFIRMED]`
Full model in `POWER_SUBSYSTEM.md`. Grid = `Bit1_*` bitmap flood-fill (`UpdatePowerGrid`
iOS 0x0025bff8, `Bit1_SelectionGrow` cap 600); plant = linear capacity derate with age
(field map `+0x48 maxAge / +0x4c decayStart / +0x58 output / +0x5c baseCapacity / +0x60 failChance`).

> **⚠ CONTRADICTED ON THE PC SIDE 2026-08-14** (`SIMUTIL_SIMTRANSIT.md`). SIMUTIL's
> `sc3_powerplant_set_lifespan` `0x10006ba6` writes `MaxLifeSpan → this+0x1c` (28) and
> `DeclineAge → this+0x20` (32); no SIMUTIL structure read uses the `+0x48/+0x4c/+0x58/+0x5c/+0x60`
> cluster. **The iOS plant field offsets do NOT transfer.** The PC build does have the same
> *concepts* (max lifespan, decline age, longevity variation, read from
> `SC3PowerLayer.INI [<PlantType>]`) — so the iOS oracle remains useful for vocabulary and
> algorithm shape, but its struct layouts must be treated as leads, never as evidence.
> The `Bit1_*` grid flood-fill was **not located** in SIMUTIL in the first pass.
>
> **⭐ UPDATE 2026-08-15 (U-012) — the flood-fill IS there, and the iOS cap of 600 is CONFIRMED
> SC3-side:** literal `0x258` at **`0x10004ee2`**, driving a masked bitmap dilation over a
> conductive-tile mask raster. Full model in `re/analysis/POWER_GRID.md`.
>
> **Calibrated rule for this oracle, from two hard results (U-011 negative, U-012 positive):**
> **iOS algorithms and magic constants transfer; iOS struct layouts do not.**
> Use iOS to predict *what the code does and which constants to look for* — never *where fields sit*.

## S4 — Zoning / development (`goZoneLayer` + `goZoneDeveloper`) `[iOS-CONFIRMED]`
Places zones and grows buildings on a cell grid. Key methods (iOS, size = complexity):
- `PlaceZone` (2732B @0x002671dc), `PlaceBuilding` (2080B @0x002652a0), `CanZone` (2128B
  @0x0026491c), `CanReZone` (1108B @0x002669bc), `testOldZoneForReZone`.
- **`IsNearTransport` (308B @0x0026516c)** — the transport-proximity gate that drives RCI
  development (a zone develops only if near road/rail); pairs with `GetRoadCount` (@0x0026678c).
- `GetUndevelopedTileCount`, `GetZoneCount`, `GetZoneColor`, `occupantChanged`, `checkEverything`,
  `SetValue`, `SimulationBegin` (1444B). Cadence via the layer contract (`onOccupant*`, `SimulationEnd`).

## S6 — Traffic (`goTrafficLayer`) `[iOS-CONFIRMED]`
**Trip-based commute simulation** (origin→destination), not a per-tile pressure field:
- `StepTrip` (7520B @0x00279f88) and `EvaluateTripData` (4856B @0x00276a14) — the cores.
- **`CalcTripDestinationBits` (2888B @0x00273588)** — a reachability **bitmap** of reachable
  destinations (same `Bit1`-style raster family as power → a structural anchor to hunt in SC3U).
- `SetTripSuccess`/`GetTripSuccess`, `GetTrafficDensity`, `GetTotalTrafficDensityInRect` (1200B),
  `GetDefaultTripLength`, `DamageRoads`, `ChanceOfStrike`/`EndStrike` (transit strikes).
- Network topology maintained in `onOccupantInserted` (2748B) / `onOccupantRemoved` (6088B) as
  roads/rails are added/removed. `goTransitLayer` handles the abstract network (`SameNet`, `convert`).

## S5 — RCI demand (`goValveLayer` / `goValve`) `[iOS-CONFIRMED]`
The demand engine as supply/demand **"valves"**:
- `AddToSupplyValue`, `AddToDemandValue`, `SetValveMax`/`SetValveMin`, `SetDemandCap`,
  `SetInitialSupplyValue`, `SetEconomyModifier`, `SetTaxModifier`, `QueryValveValue`, `GetDensity`.
- **`EndOfMonth` (580B)** — the periodic re-evaluation that updates RCI demand from
  economy/tax modifiers against caps. This is the SC3000 RCI regulator.

## Live-Ghidra xref result (2026-08-14) — the layers are DATA-DRIVEN
`XrefProbe.java` on the GZCOM bootstrap resolved the dispatch:
- `sc3_boot_register_all_factories` (`0x0040b761`) ← referenced from `.rdata` init-table
  `0x004cf668`, walked by `FUN_00402e74`/`FUN_00403019` (module static-init iterators; U-004 resolved).
- The AgentType factories `0x0040cb70`/`0x0040cc08` are referenced ONLY as DATA callbacks inside
  the hub — they are registration callbacks, not called directly.

**Consequence:** the `go*Layer` classes are **not a static function/vtable table in the exe** —
they are registered from **agent-type records the AgentTypes factory reads out of `SYS.PAK`
(and `CitySim.ini`) at runtime**. So the sim layers can't be fully enumerated from SC3U.exe
alone. The tractable routes are now: (a) parse the `SYS.PAK` agent-type records (a P2 data
task) to get the class list; (b) locate the shared `Bit1_*` raster by structure and walk to its
callers; (c) runtime observation. This is a genuine finding, not a dead end — it tells us WHERE
the layer registry lives (data, not code).

## Next step to pin any of these in SC3U
1. Live-Ghidra xref on `0x0040cb70` (`sc3_factory_agenttypes`) → the agent-type record layout →
   the registered layer class IDs/vtables → each `go*Layer` object and its `Simulate`/`SimulationBegin`.
2. Or locate the SC3U `Bit1_*` raster library by structure, then its callers = power/water/traffic.
3. Confirm a twin only when a constant/offset cluster or the layer-contract vtable order matches;
   then commit to `functions.csv` at C2 with `[CONFIRMED @ 0xADDR]`.
