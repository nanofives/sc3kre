# SYS.PAK — SimCity 3000 Unlimited packed config archive + GZCOM AgentType registry

Target: `Apps/Sys/SYS.PAK` (272,507 bytes, GOG desktop install). Read-only reference.
Parser: `re/tools/syspak_parse.py`. Resolves tracker item **U-005** (enumerate the go*Layer sim layers).

## Summary / status

**PROVEN (C4 — parser round-trips; C3 — code↔data chain confirmed from decomp + strings):**

1. **SYS.PAK is an uncompressed length-prefixed archive of 51 `.ini` config files.** No magic, no
   compression, plain ASCII payloads. `re/tools/syspak_parse.py` extracts all 51 and re-frames to
   **EOF exactly** (0x428FB / 272507). Format fully specified below.
2. **The GZCOM agent-type registry is DATA, living in `CitySim.ini` (packed inside SYS.PAK).**
   `CitySim.ini` `[AgentTypes]` section = **273 agent-type registrations**, each
   `<typeId>=<Name>:0x2026960B,0x41F56C4C,0x<classGZCLSID>`. `[AgentTypeHierarchy]` = a
   `<typeId>=<parentTypeId>` inheritance tree. This is exactly the data the
   `sc3agenttype` / `sc3typehierarchy` factories consume — U-005 route (a) delivered.
3. **Code↔data chain CONFIRMED** (no guessing):
   - SC3U.exe strings: `"Sys\CitySim.ini"` [CONFIRMED @0x004f50a4], `"AgentTypes"` [@0x004f4fe8],
     `"AgentTypeHierarchy"` [@0x004f4fd4], `"sc3agenttype"` [@0x004f5124], `"Sys\SYS.PAK"` [@0x004f5074].
   - `FUN_0040b761` (`sc3_boot_register_all_factories`) **opens `Sys\CitySim.ini`** [@line 213,
     ref `PTR_s_Sys_CitySim_ini_004f4f30`], **selects `[AgentTypes]`** [line 222] and binds
     **`FUN_0040cb70`** as its section handler [line 226], then **selects `[AgentTypeHierarchy]`**
     [line 230] binding **`FUN_0040cc08`** [line 234]. So the two magic-named factories are the
     per-section callbacks that parse these two `CitySim.ini` sections.
4. **The go*Layer sim layers are enumerated** two ways, cross-referenced to iOS names + S1–S18:
   - 14 `SC3*Layer.ini` per-layer tuning files (keyed by filename → class), + 7 more `SC3*.ini`.
   - 4 layer **agents** registered in `[AgentTypes]` as `*LayerProxy` (Aura/World/Neighbors/
     Flammability), all class GZCLSID `0x41F83776` (= `LayersAsAgents`, typeId 20). Full table below.

**OPEN / [UNCERTAIN]:**
- The literal tokens `sc3typehierarchy`, `goPowerLayer`/`go*Layer`, and per-layer `GZCLSID`
  strings are **absent from SYS.PAK bytes** (searched). The 4CC/GZCLSID→class binding for layers
  that are *not* registered as `*LayerProxy` agents is not carried as a string in these `.ini`s;
  those layers are ticked directly by the city sim loop, not via the AgentType registry.
  [UNCERTAIN] the concrete class GZCLSID of goPowerLayer/goZoneLayer/goValveLayer/etc. — not in
  `[AgentTypes]` (only their occupant/proxy children are). Missing evidence: a live-Ghidra xref of
  the layer vtables or a GZCOM registration table keyed by class name.
- The three GZCLSID fields' precise GZCOM interface roles: field1 `0x2026960B` and field2
  `0x41F56C4C` are **constant across all 273 entries** (→ an interface id + an allocator/factory
  class); field3 `0x41F836xx…` **varies per type = the concrete C++ class GZCLSID**. Exact GZCOM
  interface names are [UNCERTAIN] (no name strings in SC3U).
- TOC `A[0]`=51 equals the file count; [UNCERTAIN] whether by design or an artifact of the
  offset-table layout (see Format spec). Does not affect parsing.

_Deliverables: `re/tools/syspak_parse.py` (validated) + this file. Candidate function
classifications for the parent to merge into `functions.csv` are in the CSV block at the end._

---

## Format spec (CONFIRMED — parser round-trips to EOF)

```
SYS.PAK
├─ TOC  (starts at 0x0, no header/magic/count word)
│    51 × entry:
│      +0x00  u32  A_i         ; record-offset table: A_i (i>=1) = ABS start of record[i-1];
│      │                          A_0 = 51 (== file count) [UNCERTAIN role]
│      +0x04  u32  nameLen
│      +0x08  nameLen bytes  ASCII filename (e.g. "SC3PowerLayer.ini"), no NUL, no path
│    TOC ends at 0x508 (1288) after the 51st entry.
├─ 0x508  u32  A_51 = 0x41B88 (269192)   ; ABS start of record[50] (last) — tail of the A[] table,
│                                           NOT a length (records still self-terminate by lineCount)
└─ 0x50C  content region (= A_1): 51 records, contiguous, SAME ORDER as the TOC:
     record:
       +0x00  u32  lineCount
       then lineCount × line:
         u32  lineLen
         lineLen bytes  ASCII (one ini physical line: section "[X]" or "key=value")
     => record[i] spans [A_{i+1}, A_{i+2});  record[50] spans [A_51, EOF)
```

- **Encoding**: ASCII, **uncompressed**. A "line" is one ini physical line WITHOUT its trailing
  newline (the length prefix replaces `\n`). Section headers `[NAME]` are their own line.
- **Canonical parse**: read the u32 at TOC end (= A_51), then walk 51 records sequentially by
  `lineCount`, pairing record[i] with TOC name[i]. Validated: record[50] ("Tiles.ini") ends at
  byte 272507 = EOF. The A[] offset table is redundant with the sequential walk but is consistent
  (`record[i].start == A[i+1]` for all i, verified).

## File inventory (51 entries — extracted & validated; size = record bytes)

| Bytes | Lines | File | Role |
|------:|------:|------|------|
| 394 | 15 | Advisor-Budget.ini | S14 advisor tuning |
| 1958 | 58 | Advisor-CityPlanner.ini | S14 advisor tuning |
| 842 | 30 | Advisor-Demographics.ini | S14 advisor tuning |
| 384 | 14 | Advisor-Environment.ini | S14 advisor tuning |
| 3567 | 223 | AdvisorMoods.ini | S14 advisor text |
| 364 | 15 | Advisor-PublicSafety.ini | S14 advisor tuning |
| 7973 | 223 | Advisor-TopicGfxIDs.ini | S14 advisor gfx ids |
| 711 | 27 | Advisor-Transportation.ini | S14 advisor tuning |
| 1016 | 36 | Advisor-Utilities.ini | S14 advisor tuning |
| **18853** | **551** | **CitySim.ini** | **GZCOM AgentType registry — [AgentTypes]+[AgentTypeHierarchy]** |
| 8580 | 158 | Default.ini | app defaults |
| 239 | 15 | GoldAdvisorMoods.ini | S14 (Gold add-on) |
| 485 | 15 | GoldAdvisor-TopicGfxIDs.ini | S14 (Gold add-on) |
| 4387 | 88 | GoldTickerData.ini | S14 ticker (Gold) |
| 108 | 6 | HolidaysPetitionerExtraInfo.ini | S14 petitioner |
| 20616 | 251 | MenuItem.INI | S15 UI menu |
| 577 | 26 | NeighborDeals.ini | S1/neighbors |
| 60856 | 1052 | Occupant.ini | S9 occupant/building master data |
| 1840 | 50 | Ordinances.ini | S14 ordinances |
| 3461 | 186 | PetitionerExtraInfo.ini | S14 petitioner |
| 4340 | 278 | PetitionerManager.ini | S14 petitioner mgr |
| 2157 | 78 | SC3Aura.ini | **S12** goAuraLayer (→ AuraLayerProxy) |
| 2688 | 96 | SC3BudgetLayer.ini | **S10** goBudgetLayer |
| 6949 | 159 | SC3BuildingLayer.ini | **S9** goBuildingLayer |
| 14017 | 360 | SC3CityScheme.ini | S1/S16 building color schemes |
| 162 | 7 | SC3ComLayer.ini | **S5** goCommercialLayer |
| 1781 | 56 | SC3Crime.ini | **S11** goCrimeLayer |
| 4311 | 141 | SC3DisasterLayer.ini | **S13** goDisasterLayer |
| 295 | 13 | SC3FireLayer.ini | **S11** goFireLayer (→ FlammabilityLayerProxy) |
| 811 | 18 | Sc3HolidaysTickerData.ini | S14 ticker |
| 236 | 9 | SC3IndLayer.ini | **S5** goIndustrialLayer |
| 3791 | 88 | SC3LandValue.ini | **S12** goLandValueLayer |
| 421 | 7 | SC3NetMap.ini | **S6** transit net map (goTransitLayer) |
| 141 | 6 | SC3Newscast.INI | S14 newscast |
| 381 | 17 | SC3Police.ini | **S11** goPoliceLayer |
| 3879 | 105 | SC3Pollution.ini | **S12** goPollutionLayer |
| **1304** | **56** | **SC3PowerLayer.ini** | **S2** goPowerLayer |
| 1163 | 42 | SC3ResLayer.ini | **S5** goResidentialLayer |
| 1898 | 81 | SC3ScenarioLayer.ini | **S14** scenario layer |
| 965 | 45 | SC3StrtSimLayer.ini | **S7** SSStrtSimLayer (street-sim/vehicles) |
| 59548 | 1158 | SC3TickerData.ini | S14 ticker strings |
| 3608 | 150 | SC3Tune.ini | global sim tunables |
| **3914** | **95** | **SC3ValveLayer.ini** | **S5** goValveLayer (RCI demand) |
| 2369 | 91 | SC3WaterLayer.ini | **S3** goPlumbingLayer (water) |
| 443 | 11 | SC3WorldLayer.ini | **S1** goWorldLayer (→ WorldLayerProxy) |
| **2945** | **49** | **SC3ZoneLayer.ini** | **S4** goZoneLayer |
| 1991 | 115 | SimTune.INI | global sim tunables |
| 2444 | 65 | STTraffic.ini | S6/S7 traffic tunables |
| 104 | 6 | Test.ini | test stub |
| 1633 | 36 | TestSettings.ini | test stub |
| 3315 | 148 | Tiles.ini | S8/S16 tile palette (index=0xNN table) |

## Agent-type / sim-layer registration (from `CitySim.ini`)

### Record format — `[AgentTypes]` (273 entries)
```
<typeId> = <Name> : <GZCLSID_iface>,<GZCLSID_factory>,<GZCLSID_class>
```
- **typeId** — decimal (`3000`) or hex (`0x0259c03f`). Occupant/building/vehicle types use
  small decimal ids; layer proxies, disaster ticks and advisor agents use 32-bit hex 4CCs.
- **GZCLSID_iface = `0x2026960B`** — constant across all 273 rows (the AgentType interface id).
- **GZCLSID_factory = `0x41F56C4C`** — constant across all rows (allocator/factory class).
- **GZCLSID_class = `0x41F836xx…`** — **varies per type = the concrete C++ class GZCLSID.**

### Record format — `[AgentTypeHierarchy]` (child→parent tree)
```
<typeId> = <parentTypeId>        ; parentTypeId 0 = root
```
Roots (`=0`): `20` LayersAsAgents, `50` Occupant, `51` Terrain, `52` Advisor, and the
DisasterManager tick types. Example chain:
`12111 CoalPlant → 12101 PowerPlant → 12000 InfrastructureUtilities → 100 Buildings → 50 Occupant`.

### The sim LAYERS registered as AGENTS (the only go*Layer entries in the registry)
All four are children of `20 LayersAsAgents` and share class GZCLSID **`0x41F83776`**:

| typeId (4CC) | Name | class GZCLSID | parent | Layer config file | iOS class | Subsystem |
|---|---|---|---|---|---|---|
| `20` | LayersAsAgents | 0x41F83776 | 0 (root) | — | (layer-agent base) | S1 |
| `0x0259c03f` | AuraLayerProxy | 0x41F83776 | 20 | SC3Aura.ini (name match) | goAuraLayer | S12 |
| `0x411bddda` | WorldLayerProxy | 0x41F83776 | 20 | SC3WorldLayer.ini (name match) | goWorldLayer | S1 |
| `0x82937b60` | NeighborsLayerProxy | 0x41F83776 | 20 | [UNCERTAIN] (NeighborDeals.ini?) | (neighbors) | S1 |
| `0xc144aca9` | FlammabilityLayerProxy | 0x41F83776 | 20 | [UNCERTAIN] (no SC3Flammability.ini) | goFlammabilityLayer | S11 |

`*LayerProxy → SC3*.ini` links marked "name match" are by filename↔classname convention only
(strong, not byte-proven); the two [UNCERTAIN] rows have no clean filename twin in the archive.

The remaining go*Layer classes (Power/Zone/Valve/Budget/Traffic/…) are **NOT** in `[AgentTypes]`
— they are ticked by the sim loop directly and configured only by their `SC3*Layer.ini` file
(keyed by filename → class). [UNCERTAIN] their individual class GZCLSIDs (see Summary/status).

### Advisor / manager AGENTS in `[AgentTypes]` (S14)
`0x413b4f54 PoliceAdvisorAgent`, `0xa1536206 BudgetAdvisorAgent`,
`0x6292587c CityPlanningAdvisorAgent`, `0x41576710 DemographicsAdvisorAgent`,
`0xc1576708 EnvironmentAdvisorAgent`, `0xe1eb6d9a PublicSafetyAdvisorAgent`,
`0x82925329 TransportationAdvisorAgent`, `0xc2505969 UtilityAdvisorAgent`,
`0x22618fcc PetitionerManagerAgent` (class GZCLSIDs 0x41F83777–0x41F8377A).

### Occupant / building / vehicle AGENTS in `[AgentTypes]` (S9/S5/S6/S7)
The bulk of the 273 entries are the RCI + infrastructure occupant taxonomy, mirroring
`Occupant.ini`. Representative ids (name : classGZCLSID):
- RCI roots: `3000 Residential:41F836E9`, `5000 Commercial:41F836F8`, `8000 Industrial:41F83702`
  (each a child of `100 Buildings`), with density/land-value variants `3100…4700`, `5100…6700`,
  `8100…9300` (matching the `SC3ValveLayer.ini [AgentValveEffects]` keys 1:1).
- Utilities: `12101 PowerPlant:41F83715` + subtypes `12111 CoalPlant … 12118 WindPlant`,
  `12853 Waste to Energy` — ids match `SC3PowerLayer.ini [PowerPlantCapacities]` 1:1.
- Transport: `12210 BusStation … 12361 Subway/Rail Station`; hydrology `12510 Dam`, `12810 WaterPump`.
- Vehicles (S7): `214 Cars … 223 Ships`, `211 Trailers` (class GZCLSIDs 0x41F837C2–0x41F837D2).

### iOS go*Layer class → SC3 subsystem (cross-RE map, `re/ghidra_export_ios/symbols.csv`)

| iOS class | SC3*.ini config | Subsystem | CitySim agent? |
|---|---|---|---|
| goPowerLayer | SC3PowerLayer.ini | S2 Power | no (sim-loop) |
| goPlumbingLayer | SC3WaterLayer.ini | S3 Water | no |
| goZoneLayer | SC3ZoneLayer.ini | S4 Zoning | no |
| goValveLayer | SC3ValveLayer.ini | S5 RCI demand | no |
| goResidentialLayer | SC3ResLayer.ini | S5 | no |
| goCommercialLayer | SC3ComLayer.ini | S5 | no |
| goIndustrialLayer | SC3IndLayer.ini | S5 | no |
| goTrafficLayer / goTransitLayer | SC3NetMap.ini / STTraffic.ini | S6 | no |
| SSStrtSimLayer | SC3StrtSimLayer.ini | S7 | no |
| goTerrainLayer / goFloraLayer | (Tiles.ini) | S8 | `51 Terrain` (root) |
| goBuildingLayer / goOccupant | SC3BuildingLayer.ini / Occupant.ini | S9 | `50 Occupant` (root) |
| goBudgetLayer | SC3BudgetLayer.ini | S10 | no |
| goPoliceLayer | SC3Police.ini | S11 | no |
| goFireLayer / goFlammabilityLayer | SC3FireLayer.ini | S11 | **FlammabilityLayerProxy** |
| goCrimeLayer | SC3Crime.ini | S11 | no |
| goPollutionLayer | SC3Pollution.ini | S12 | no |
| goLandValueLayer | SC3LandValue.ini | S12 | no |
| goAuraLayer | SC3Aura.ini | S12 | **AuraLayerProxy** |
| goDisasterLayer | SC3DisasterLayer.ini | S13 | `DisasterManager` 0x0288e4c8 |
| goOrdinanceLayer / goAdvisor / goPetitionerManager | Ordinances/Advisor-*/Petitioner*.ini | S14 | advisor agents (above) |
| goWorldLayer / goCityLayer | SC3WorldLayer.ini | S1 | **WorldLayerProxy** |
| (neighbors) | NeighborDeals.ini | S1 | **NeighborsLayerProxy** |
| (scenario) | SC3ScenarioLayer.ini | S14 | no |

## Candidate SC3U function classifications (parent merges into `functions.csv`)

Child worker does NOT write trackers. The following are the SC3U functions this workstream
confirmed against the CitySim.ini data + strings. Evidence is decompilation-literal.

```csv
rva,subsystem,confidence,evidence
0x0040b761,S18,C3,"sc3_boot_register_all_factories: opens PTR_s_Sys_CitySim_ini_004f4f30 (line213), selects s_AgentTypes_004f4f5c (line222) binding FUN_0040cb70 (line226), selects s_AgentTypeHierarchy_004f4f60 (line230) binding FUN_0040cc08 (line234). CitySim.ini is packed in SYS.PAK."
0x0040cb70,S18,C3,"sc3_factory_agenttypes: per-section handler for CitySim.ini [AgentTypes]; registers factory keyed on PTR_s_sc3agenttype_004cffa0. Parses 273 records <id>=<name>:<iface GZCLSID 0x2026960B>,<factory 0x41F56C4C>,<class 0x41F836xx>."
0x0040cc08,S18,C3,"sc3_factory_agenttypes_hierarchy: per-section handler for CitySim.ini [AgentTypeHierarchy]; registers factory keyed on PTR_s_sc3typehierarchy_004cffa4. Parses <typeId>=<parentTypeId> tree (0=root)."
```

- `0x0040b761` / `0x0040cb70` / `0x0040cc08` were previously known structurally (SIM_LAYERS_XREF,
  U-004); this workstream raises them to **C3** by matching them to the concrete `CitySim.ini`
  data they parse. No new `go*Layer` RVA is committed — those classes are not reachable from the
  registry (documented [UNCERTAIN], needs live-Ghidra vtable xref).
