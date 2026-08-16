# SimCity 3000 — P1 Subsystem Surface Map

Read-only analysis over the two Ghidra text exports. iOS class names are the **named
oracle** `[iOS]`; SC3U desktop facts are `[SC3U]`. NO-GUESSING: nothing inferred beyond
what the CSVs literally show. (Built by a delegated read-only analysis pass, 2026-08-14.)

## 0. Ground truth / corpus state

| Fact | Value | Source |
|---|---|---|
| iOS symbol rows | 20,051 | `re/ghidra_export_ios/symbols.csv` |
| iOS classes with `s_initType` (~distinct type-registered classes) | 1,079 | grep `,s_initType,` |
| iOS `go*` / `SS*` method rows | 3,456 / 764 | grep counts |
| SC3U functions | 9,727 | `re/ghidra_export/symbols.csv` |
| SC3U functions with a class namespace | **0** — fully stripped (all `Global`) | sampled |
| SC3U string-table entries | 1,369 | `re/ghidra_export/strings.csv` |

**Two load-bearing consequences:**
1. SC3U is 100% stripped → the iOS sibling is the *only* source of subsystem vocabulary;
   classification flows iOS-name → SC3U-evidence.
2. The SC3U code segment is **almost devoid of gameplay vocabulary** — sim strings
   (power/zone/traffic/budget) live in external packed data (`SYS.PAK`, `*.IXF`, `Sys\*.INI`),
   NOT in `.rdata`. String-xref classification works for I/O-framework-UI subsystems but is
   weak for the core sim layers; those lean on iOS cross-ref + call topology.

Engine framework: Maxis **GZCOM / "Gonzo"** component system (SC3U strings
`GZDllGetGZCOMDirector`, `cGZFrameWorkW95`, `cGZDBSegmentIndexedFile`, `Gonzo`). Game state
is a stack of **`go*Layer`** god-objects over a cell grid; each is an agent implementing
`SimulationEnd / onOccupantInserted / onOccupantRemoved / CellChanged / onAllCellsChanged`
(pattern confirmed on `goPowerLayer`, iOS 0x00258cc4…0x0025b58c).

## 1. Subsystem taxonomy (from the iOS named binary)

Method counts are raw `grep ,<Class>$` row counts (incl ctor/dtor/thunks). Generic inner
class names (`Data/Info/Instance/Node/Layer/Command`) are ambiguous and NOT counted.

- **S1 Simulation Core & City loop** — `goCity`(47), `goCitySimulator`(16), `goCityChild`,
  `goCityLayer`, `goWorldLayer`, `goGraphInfo`; host `Game/GameContext/Context/GameData/GameMode_SimCity`;
  layer registry + tick driver (`Simulation_Update/Begin/InternalPause`).
- **S2 Power / Electricity** — `goPowerLayer`(37), `goPowerPlant`(25); plant subtypes
  `go{Coal,Oil,Gas,MicroWave,Nuclear,Fusion,Solar,Wind,Waste}PowerPlant`; wiring occupants
  `goPowerLineOccupant goPowerTower goPowerLine goPowerPole goPowerBridge`. See POWER_SUBSYSTEM.md.
- **S3 Water / Plumbing** — `goPlumbingLayer`(45), `goWaterPump goDesalinationPlant goWaterTower
  goWaterTreatmentBuilding goPlumbingBuilding goPipe`. (Reuses the `Bit1_*` raster like S2.)
- **S4 Zoning & RCI development** — `goZoneLayer`(63), `goZoneDeveloper`(12) +
  `go{Res,Com,Ind}ZoneDeveloper`; rule tree `goDeveloperRule` + `go{Res,Com,Ind}{LD,MD,HD}DeveloperRule`,
  `goRowHouseDeveloperRule goAgDeveloperRule`, `goZoneBuilding`; developer data tables
  `Residential/Commercial/Industrial` → density/land-value variants; `BuildingType/Family/Set`.
- **S5 RCI demand & population (Valves)** — `goValveLayer`(50), `goValve`,
  `goResidentialValve goWorkforceValve goGarbageValve`, `ValveEffect ClassValveData PhaseEffect`;
  density layers `goResidentialLayer`(66), `goCommercialLayer`, `goIndustrialLayer`.
  ("Valve" = the SC3000 supply/demand regulator objects.)
- **S6 Road / Rail transport network** — `goTrafficLayer`(42), `goTransitLayer`(66); occupants
  `goRoad goRoadBridge goDamagedRoad goRail goRailEndcap goRailBridge goPowerRoad goPowerRail
  goRoadRail`, base `goNetworkOccupant goTransitOccupant`; buildings `goTransitBuilding
  goRailStation goBusStop`.
- **S7 Vehicles / Street-Sim (`SS*`, 764 methods)** — `SSStrtSimLayer`, `SSVehicle`(100),
  `SSVehicleAttrib SSVehicleProducer SSVehiclePath*`; modal `SSAeroplane SSBoat SSHelicopter
  SSShip SSRailVehicle SSTrainProducer`, `SSAirTrafficManager`, `SSStrtSim{Occupant,Script,TrBlock}`,
  `SSOccupant{Manager,Inserted,Moved,Removed,Sort}`.
- **S8 Terrain & flora** — `goTerrainLayer`(79), `TerrainMap`(45), `TerrainGenerator`,
  `goFlora goFloraLayer`; support `OccupantSet PaletteTable`; `Event_Terrain_RefreshVisuals`.
- **S9 Buildings & occupants** — `goOccupant`(27), `goOccupantManager`, `goBuilding`,
  `goDynamicOccupant`, `IBuildingMortal`; reward/landmark buildings (museum, library, college,
  hospital, park family, stadium, casino, prison, megamall, cityhall, courthouse, spaceport,
  militarybase, landmark, rewardbuilding, businessdealbuilding, HQ/EQ buildings, …).
- **S10 Budget & finance** — `goBudgetLayer`(79), `goDepartmentBudget`, `goBuildingBudget`,
  `go{Road,Rail,Police,Fire,Education,Health}DeptBudget`; records `BusinessDealRecord
  SpecialBuildingRecord GarbageBuildingRecord UtilityBuildingRecord`.
- **S11 Public safety & civic** — `goPoliceLayer`(32)+`goPoliceStation goJail`,
  `goFireLayer`(31)+`goFireStation`, `goCrimeLayer`(29), `goFlammabilityLayer`; edu/health via buildings.
- **S12 Environment layers** — `goPollutionLayer`(54), `goLandValueLayer`(31), `goAuraLayer`;
  waste `goWasteBuilding goRecyclingCenterBuilding goIncineratorBuilding goLandfillDeveloper`.
- **S13 Disasters** — `goDisasterLayer`(43); per-disaster `{Simulator,DisasterManager,DisasterInstance}`
  for fire, earthquake, tornado, UFO, toxic cloud, explosion, meteor, blizzard, electrical storm,
  heat wave, insect plague.
- **S14 Governance: advisors / petitioners / ordinances / ticker** — `goOrdinanceLayer`(33)+`Ordinance`,
  `goAdvisor`(28)+`goAdvisorFor{Budget,Demographics,Environment,PublicSafety,Transportation}`,
  `goPetitionerManager`(53)+`Petitioner PetitionerQueue`, `Advice AdviceQueue`, `Ticker`.
  **The one core-sim cluster with strong SC3U string anchors** (§2).
- **S15 UI: windows / tools / HUD** — `CityWindow`(82), `CityTool`+`CityTool_{Atomic,Query,
  PlaceNetwork,PlaceZone,PlaceBuilding,DispatchCrew}`, buttons; feature windows (Budget, Bonds,
  Loan, Graph, MapData, Query, Ordinance, Advice, Petitioner, BuildingSelect, NewGame, Load,
  Settings, Options, Main, …); toolkit `Window Frame Dialog Menu Font RichEditControl WindowMgr`.
- **S16 Rendering / graphics / particles** — render targets (`City/Terrain/Color/Occupant/Data
  RenderTarget`); `Sprite SpriteList FastSprite Xform View Material Anim`; large
  `ParticleEmitterRules_*` family; 3D `Actor Scene Shape*`; codecs `{JPG,PNG,TGA,PVR}`.
  **⚠ engine-divergent**: OGL_ES/PVR are iOS-only; SC3U is GDI/DirectX (`GDI32.dll`, `sc3dbssprite`).
- **S17 Audio** — `MusicMgr Track Sound SoundFactory`; iOS drivers `Driver_OAL/FMOD`.
  **⚠ engine-divergent**: SC3U desktop audio is `UV.dll` (`uV_*`, `WINMM.dll`), not OpenAL/FMOD.
- **S18 Save/Load, assets & data (GZ DB)** — `AssetInfo AssetFactory`, `cGZDBSegmentIndexedFile`,
  `File Profile ProfileData`; SC3U anchors `systemloadsave.fbf`, `SYS.PAK`, `SC3StringsApp.IXF`.

**Host/shell (iOS-only or thin on desktop — map with caution):** framework
`Application StateMachine State Step Command GlobalEventManager NotificationMgr Module Device
Input Binding`; scripting `TutorialScript Scenario RCIZoneObjective ValueObjective DateObjective`;
networking `NetEvent_Session* Connection Transport Session Player*` (CityExchange/multiplayer);
mobile-only `HighscoreTable NotifyAchievement Profile_iPhone MoreGamesWindow EA`.

## 2. SC3U string evidence (desktop anchors, `[SC3U]`)

**Headline:** sim tokens return almost nothing — `power|consumer|plant|electric`→0,
`traffic|road|rail|transit`→0, `budget|tax|ordinance|bond`→0, `pollut|crime|police|fire|
landvalue|garbage`→0. Sim vocabulary is in external packed data, not the code segment. The
subsystems that DO have code-segment anchors (usable for string-xref classification):

- **S1 / framework:** `GZDllGetGZCOMDirector` @0x004f306b/@0x004f810c · `Gonzo` @0x004f4b1c ·
  `cGZFrameWorkW95::AbortiveQuit()` @0x004f7894 · `Sys\CitySim.ini` @0x004f50a4 ·
  `SimCity 3000 Mutex` @0x004f4b24 · `SIMCITY3000` @0x004f4b64
- **S9 Occupants:** `OccupantKeys` @0x004f4ff4 · `Sys\Occupant.ini` @0x004f50b4 ·
  `OccManAnim::InsertOccupant: Failed…` @0x004f7707 · `OccManAnim::MoveOccupant…` @0x004f7298 ·
  `OccManAnim::RefreshOccupant…` @0x004f7308 · `OccManAnim::IsOccupantVisible…` @0x004f7380
- **S1 command dispatch:** `GameCommandFactories` @0x004f5004 · `gamecmd` @0x004f7240 ·
  `cogamecmd` @0x004f5150/@0x004f7248
- **S14 governance/ticker (only sim-facing cluster with strings):** `ticker` @0x004f7140 ·
  `advisor` @0x004f7198 · `mayor` @0x004f716c · `%MAYOR%` @0x004f804c · `Sc3TickerData` @0x004f71cc ·
  `\Sys\SC3Newscast.INI` @0x004f720c · `TickerAdvertisements.html` @0x004f548c · `news://` @0x004f86fc
- **S15/S18 UI menus & config:** `SC3MenuBtnDefs` @0x004f4f7c · `SC3MenuDescs` @0x004f4f8c ·
  `SC3MenuSets` @0x004f4f9c · `SC3MenuItemInfo` @0x004f4fa8 · fourccs `SC3MBTNDEFS/SC3MSET/SC3MDESC/SC3MII` · `SC3.cfg` @0x004f4f20
- **S16 sprites (desktop):** `sc3dbssprite` @0x004f4c08 · `SpriteSegments` @0x004f4fc4 ·
  `DBSegmentDirectoryFiles` @0x004f503c · `Sys\Sprite.ini` @0x004f5094 · `Res\Sprites` @0x004f51f0 · `GDI32.dll` @0x004f21b8
- **S17 audio (desktop = UV.dll):** `UV.dll` @0x004f2142 · `uV_Open/Close/Stop/Pause/SetAudioVolume/
  is_Playing/Play_FromHandle` @0x004f20de… · `\Sys\SC3Tune.ini` @0x004f74a8 · `res\sound\radio\` @0x004f4ed4 · `WINMM.dll` @0x004f21d0
- **S18 save/load & archives:** `systemloadsave.fbf` @0x004f52c4 · `\Sys\SYS.PAK` @0x004f71dc ·
  `SC3StringsApp.IXF` @0x004f4bcc · `cGZDBSegmentIndexedFile::DoOpenRecord(): Record not found: %d` @0x004f7990
- **Host (S1):** cheat `simon says` @0x004f7158 · registry
  `HKLM\Software\Electronic Arts\Maxis\SimCity 3000 Unlimited\…` @0x004f4d58 · `%CITYNAME%`/`%YOURCITY%`
- **Networking/CityExchange:** `SC3Net.cfg` @0x004f5500 · `CityExchange` @0x004f553c ·
  `www.simcity.com` @0x004f54a8 · `irc://www.simcity.com:6667/Welcome` @0x004f5714
- **⚠ Copy protection (NOT game logic — do not mis-file):** SafeDisc
  `DRVMGT.DLL`@0x004f5164 `DPLAYERX.DLL`@0x004f5170 `CLCD32.DLL`@0x004f518c `CLCD16.DLL`@0x004f5198

## 3. Size map — 25 largest `FUN_*` (RE priority targets)

Only 82 `FUN_*` are ≥1000 bytes; the largest cluster in `0x0040_`–`0x004be_`.

| # | Address | Size | | # | Address | Size |
|---|---|---|---|---|---|---|
| 1 | `0x004a89f6` | **15,247** | | 14 | `0x0042f629` | 2,895 |
| 2 | `0x00436f31` | 9,411 | | 15 | `0x00428801` | 2,805 |
| 3 | `0x0041ae65` | 6,575 | | 16 | `0x004108f3` | 2,802 |
| 4 | `0x0040efd8` | 6,339 | | 17 | `0x00409e78` | 2,791 |
| 5 | `0x0049032d` | 3,874 | | 18 | `0x004093e3` | 2,709 |
| 6 | `0x0042affa` | 3,537 | | 19 | `0x004b98ea` | 2,685 |
| 7 | `0x00477b70` | 3,457 | | 20 | `0x0043a8b9` | 2,658 |
| 8 | `0x0040b761` | 3,415 | | 21 | `0x004b8c7a` | 2,603 |
| 9 | `0x004be941` | 3,197 | | 22 | `0x0042054f` | 2,590 |
| 10 | `0x00413d42` | 3,157 | | 23 | `0x00417c23` | 2,588 |
| 11 | `0x004856b2` | 3,119 | | 24 | `0x0049140b` | 2,519 |
| 12 | `0x00415aa2` | 3,033 | | 25 | `0x0041d2bc` | 2,394 |
| 13 | `0x0041674e` | 2,986 | | | | |

`0x004a89f6` (15 KB, 2.4× the next) is the single dominant RE target.

## 4. Methodology — classifying a `FUN_*` to a subsystem

SC3U has no symbols and few strings, so **call-topology + iOS-vtable shape carry most of the
weight; string-xref is a bonus that only fires for the §2 subsystems.**

**Step 0 — pick targets.** Work the §3 size list first, then follow call graphs. Record every
step in `functions.csv` (`subsystem/new_name/confidence/notes`).

**Step 1 — string xref (only S1/S9/S14/S15/S16/S17/S18).**
`query.ps1 -Xref FUN_<addr>` then `-Fn 0x<addr>`. A §2 anchor in the body nearly settles it:
`OccManAnim::`→S9, GZCOM director/`CitySim.ini`→S1, `SC3Newscast.INI`/`ticker`→S14, `uV_*`→S17,
`Sprite.ini`/`sc3dbssprite`→S16, `systemloadsave.fbf`/`SYS.PAK`→S18. Cite `[CONFIRMED @ 0xADDR]`.

**Step 2 — iOS named cross-ref (primary for sim layers).** No address map (ARM vs x86) — match
on *shape*: read the layer class in `ghidra_export_ios/`, transfer distinctive **numeric
constants**, **struct field offsets**, and **vtable method ordering** to the SC3U body. A
matching cluster promotes `[iOS-HINT]`→`[CONFIRMED @ 0xADDR]`. The shared layer contract
(`SimulationEnd/onOccupantInserted/onOccupantRemoved/CellChanged/onAllCellsChanged` in order)
fingerprints a `go*Layer`; disambiguate by constants + callees.

**Step 3 — call topology / clustering.** Each god-object layer owns a tight island of helpers;
label the island once the layer is identified (members inherit subsystem at `C1` until read).
Factory/registration hubs (`GameCommandFactories`, `OccupantKeys`) are good cluster roots.
Functions reached only via `WSOCK32`/`CityExchange`/registry/SafeDisc chains are host/shell.

**Step 4 — confidence & guards.** `C1`=single witness; `C2`=body read + callees + named
`sc3_<subsys>_<verb>_<noun>`; `C3`=second witness (constant + topology agree). Never claim `C3`
from an iOS name alone. Guard against: (a) ambiguous iOS inner classes; (b) iOS-only tech
(OpenAL/FMOD/PVR/OGL_ES, achievements) with no SC3U counterpart; (c) SafeDisc code posing as game logic.
