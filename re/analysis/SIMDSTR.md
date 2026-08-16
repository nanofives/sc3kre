# SIMDSTR.DLL — SC3 Disaster / Special-Event module (S11)

GZCOM director module. Version resource: `SimCity 3000`, `FileVersion 2.0.949`,
`OriginalFilename SC3U.EXE`, `Copyright © 1999 Maxis, Inc.` [CONFIRMED @ 0x1003b1d4,
0x1003b24c, 0x1003b218, 0x1003b148]. Export name `SimDstr.dll` [CONFIRMED @ 0x10038a42].
All addresses below are Ghidra VAs in this module's export (`re/ghidra_export_simdstr/`).

## 1. Purpose

SIMDSTR.DLL implements the disaster and scripted-event subsystem of SimCity 3000. It is a
self-contained GZCOM plugin that registers **12 COM classes** through the standard director
recipe, and drives every catastrophe/event in the game: **Fire, Riot, Tornado, Toxic Cloud
(acid rain), UFO attack, Locust swarm, and the Parade special event** — each identified by a
tuning group string it loads from `\Sys\SC3DisasterLayer.INI` (inside `\Sys\SYS.PAK`)
[CONFIRMED @ 0x100396ec, 0x100396dc]. Grounding strings: `FireDisaster` [0x100396cc],
`RiotDisaster` [0x10039a30], `TornadoDisaster` [0x10039b0c], `ToxicCloudDisasterTunables`
[0x10039e5c], `UFODisasterTunables` [0x1003a1fc], `LocustDisasterTunables` [0x100399d0],
`ParadeEvent` [0x1003a3a4], `MiscDisasterTunables` [0x10039788], `DisasterDescriptions`
[0x100397b8]. Each disaster type is a class whose per-run tunables are read once from the
INI into module-global `DAT_*` slots, then consumed by that class's simulation methods. The
module also carries the parade macro-substitution tokens (`%MAYOR%`, `%CITYNAME%`,
`%PARADENAME%`, …) [CONFIRMED @ 0x1003a588–0x1003a5dc] and weekday names [0x1003a434–0x1003a470].

## 2. Director + registrations

### Entry chain
- `GZDllGetGZCOMDirector` (PE export) `[CONFIRMED @ 0x10024e87]` — guarded one-time init:
  sets bit0 of `DAT_1003ac34`, calls the director ctor `FUN_1002269e(&DAT_1003abf0)`, registers
  an `_onexit` destructor `LAB_10022acb`, and returns `&DAT_1003abf0` (the static director).
- **Director ctor `FUN_1002269e` `[CONFIRMED @ 0x1002269e]`** — installs the director vtables
  (`PTR_FUN_10033838`, `PTR_LAB_1003380c`) and makes **12 calls** to the class-registration
  helper.
- **Registration helper `FUN_1002520d(this, GZCLSID, factory, 0)` `[CONFIRMED @ 0x1002520d]`** —
  builds a `{GZCLSID, factory, 0}` triple and inserts it into the map at `director+0x14` via
  `FUN_1002547e` (matches the GZCOM recipe exactly).
- Each factory does `operator_new(size)` + ctor and returns `object + N` (the registered
  sub-interface), or NULL on failure (the `-(uint)(p!=0) & (uint)(p+N)` idiom) `[CONFIRMED]`.

### Registration table (all 12) `[CONFIRMED @ 0x1002269e]`

| # | GZCLSID | Factory RVA | operator_new size | Ctor RVA | Returns |
|---|---|---|---:|---|---|
| 1 | `0x61f6abf5` | `0x100227b5` | `0x108` (264) | `FUN_10007978` | obj+0x4 |
| 2 | `0x428fd431` | `0x100227f3` | `0x90` (144) | `FUN_100051e2` | obj+0xC |
| 3 | `0x62a34670` | `0x10022831` | `0x80` (128) | `FUN_10012de1` | obj+0xC |
| 4 | `0x22fe8d32` | `0x1002286f` | `0x88` (136) | `FUN_1000121c` | obj+0xC |
| 5 | `0xe2fe8d38` | `0x100228ad` | `0x88` (136) | `FUN_1000d0d1` | obj+0xC |
| 6 | `0x22fe8d3e` | `0x100228eb` | `0x88` (136) | `FUN_10017c9a` | obj+0xC |
| 7 | `0x84c92cbe` | `0x10022929` | `0x90` (144) | `FUN_1001eddd` | obj+0xC |
| 8 | `0xc2fe8d43` | `0x10022967` | `0x98` (152) | `FUN_10014d61` | obj+0xC |
| 9 | `0x52fe8d50` | `0x100229a5` | `0x88` (136) | `FUN_1001bd9d` | obj+0xC |
| 10 | `0x52fe8d51` | `0x100229e3` | `0x90` (144) | `FUN_1000a325` | obj+0xC |
| 11 | `0x52fe8d52` | `0x10022a21` | `0x88` (136) | `FUN_100106fe` | obj+0xC |
| 12 | `0x52fe8d53` | `0x10022a5f` | `0x88` (136) | `FUN_1000f036` | obj+0xC |

**Class #1 (`0x61f6abf5`) is the `SC3DisasterLayer` manager** `[CONFIRMED @ 0x10007978]`: its
ctor is the only one that is not the shared "sub-object" shape — it installs **four** vtables
(`PTR_LAB_10032668/…20/…0c/…f4`, later swapped to `…5a0/…558/…544/…52c`), builds two circular
linked lists (`FUN_1000454c(0x10)` nodes whose fwd/back both point to self, at `+0xA0` and
`+0xCC`), embeds two string members (`FUN_10006bb8` at `+0x14` and `+0x20`), and a large
sub-record via `FUN_100298cc(+0xE0)`. This is the layer that owns the disaster instances.

**Classes #2–#12 share one construction shape** `[CONFIRMED]`: each calls the base ctor
`FUN_1002a6ef` (zeroes `[1]/[2]`, sets `PTR_FUN_10033f38`), installs a common vtable trio at
`[3]=PTR_LAB_10032250`, `[4]=<class-specific>`, `[5]=PTR_LAB_10032228`, zeroes its fields,
initialises an id/handle member via `FUN_10022b70(obj+K, 0xffffffff)`, then overwrites `[0]` and
`[3..5]` with the final per-class vtables. The **class-specific vtable at `[4]`** is the unique
discriminator per class (e.g. `PTR_LAB_10033104` #3, `PTR_LAB_10032238` #4, `PTR_LAB_10032c4c`
#5, `PTR_LAB_10033480` #6, `PTR_LAB_10033774` #7, `PTR_LAB_10033288` #8, `PTR_LAB_100335f4` #9,
`PTR_LAB_100328cc` #10, `PTR_LAB_10032f4c` #11, `PTR_LAB_10032dd0` #12) `[CONFIRMED]`.

**Class-name string present:** only `SC3DisasterLayer` appears (as the INI path
`\Sys\SC3DisasterLayer.INI` [0x100396ec]); no per-disaster class-name string exists (the
disaster identities live as tuning-group strings, not class names — see §4). Mapping each of
classes #2–#12 to a specific disaster type is **[UNCERTAIN]** — see §7.

## 3. Key subsystems

Two tuning-load dispatch idioms are used across the module `[CONFIRMED]`:
- **Pattern A** (`FUN_1002c669` enumerate-group + `FUN_1002a8d6` property provider, then
  `(**(*prov+0x14))(propId, buf)` per key): reads typed values by a **32-bit property id**;
  used by Fire, Riot, Tornado.
- **Pattern B** (`FUN_1002c372(ini, &group, &key, &out)` returning a value string, then
  `FUN_10029a8e(str)` = string→int): reads values by **(group,key) name**; used by
  Misc/Descriptions, Locust, ToxicCloud, UFO, Parade.
Helpers: `FUN_10006b04` builds a `std::string` from a literal; `FUN_1002a7b8` returns the
resource-path/stream service (its vtable+0x50 stamps the `SC3DisasterLayer.INI` / `SYS.PAK`
path); `FUN_1002a8d6` returns the shared property-collection singleton (lazy, cached in
`DAT_1003ad1c`); `FUN_1002a6ef` is the base-object ctor `[CONFIRMED @ 0x1002a6ef, 0x1002a7b8,
0x1002a8d6]`.

1. **`FUN_1000613e` — Fire tunable loader** `[CONFIRMED @ 0x1000613e]`. Loads group
   `FireDisaster` (enumerated with callback `FUN_10005814`), then reads 13 fire properties by id
   `0x047df002`, `0x647df00f`, `0xc47df01a`, `0xa47df024`, `0x647df02b`, `0x647df032`,
   `0x247df038`, `0xa47df03e`, `0x047df044`, `0xe47df04a`, `0x047df051`, `0xa47df05a`,
   `0x047df061` into globals `DAT_1003967c/…80/…84/…88`, bytes `DAT_10039690/91`,
   `_DAT_1003a798/_DAT_10039694/_DAT_1003a79c/_DAT_10039698/_DAT_1003a7a0/_DAT_1003969c`,
   `DAT_100396ac`. Loops `FUN_100064ba(0..2)` (3 sub-levels) and calls `FUN_10006470`.
2. **`FUN_10005814` — Fire config-entry parse callback** `[CONFIRMED @ 0x10005814]`. For each
   `FireDisaster` group entry: reads the entry key via vtable+0x14, converts with `FUN_10029a8e`,
   resolves a sub-key against `DAT_100396c8` via `FUN_10025684`, and stores results in
   `DAT_1003a728` and `DAT_1003a72c`.
3. **`FUN_100092d6` — Misc/Descriptions loader** `[CONFIRMED @ 0x100092d6]`. Group
   `MiscDisasterTunables`; enumerates `DisasterDescriptions` (callback `FUN_10008d27`); reads
   `MaxEmergencyDuration`→`DAT_10039724`, `MinDisasterCostToGetRelief`→`DAT_1003a7ac`,
   `ReliefAsPercentageOfCostWithoutEW`→`DAT_1003a7a9`, `ReliefAsPercentageOfCostWithEW`→
   `DAT_1003a7a8`.
4. **`FUN_1000aa59` — Locust loader** `[CONFIRMED @ 0x1000aa59]`. Group `LocustDisasterTunables`;
   reads ~16 keys (`MaxLocustInstances`→`DAT_100397d0`, `Min/MaxMonthsBetweenLocustAttacks`,
   `PercentageChanceOfLocustAttackEachYearTimes100`, `SwarmSpeed`, three premonition timers,
   `Min/MaxLocustSwarmsPerInstance`, `SwarmToCropRatio`, `MaxLocustsPerInstanceCheatSwarm`,
   `YearOfFirstPossibleVisitationAppearance`→`DAT_10039804`, `MaxNumCropsToAttack`→`DAT_10039800`).
5. **`FUN_1000dc3a` — Riot loader** `[CONFIRMED @ 0x1000dc3a]`. Group `RiotDisaster` (callback
   `FUN_1000d680`); 12 properties by id `0x6484a25d`, `0x2484a264`, `0x6484a26a`, `0x4484a270`,
   `0x4484a278`, `0xe484a27d`, `0xa484a283`, `0x2484a289`, `0x2484a290`, `0x2484a29e`,
   `0x2484a2a5`, `0x4484a2ac` → `DAT_10039a08/…a04/…a00/…a10/…a18/…a1c/…a20/…a24` and
   `DAT_1003a898/…89c/…894/…900`. Calls `FUN_1000df36`.
6. **`FUN_1001367e` — Tornado loader** `[CONFIRMED @ 0x1001367e]`. Group `TornadoDisaster`
   (callback `FUN_1001325a`); 14 properties by id `0xe48381bc`, `0x048381c8`, `0xa48381d2`,
   `0x84838207`, `0x4483820f`, `0x84838216`, `0x8483821d`, `0x24838224`, `0x0483822a`,
   `0x44838230`, `0xc4838239`, `0x0483823f`, `0x6483824b`, `0xe4838253`. Two are cast to
   `float` (`_DAT_10039ad8`, `_DAT_10039adc`). Calls `FUN_100139c2`.
7. **`FUN_10015751` — Toxic Cloud / acid-rain loader** `[CONFIRMED @ 0x10015751]`. Largest loader
   (4443 bytes); group `ToxicCloudDisasterTunables`, ~30 keys. Applies **runtime clamps**:
   `MinCloudsPerInstance`≥1; cloud speeds `_DAT_10039b28/b2c = value * _DAT_10033114 *
   _DAT_10033118` (unit scaling); heights `DAT_10039b3c/b40 = value << 8`;
   `MinCloudDuration`(`DAT_10039b44`) defaulted to `10` if 0, `MaxCloudDuration` forced ≥ min+1;
   `ScorePerLevelIncrement` defaulted to `10` if <1; `MaxTimeForRainStart`≥`Min`+1;
   `MaxRainDuration`≥`Min`+1.
8. **`FUN_10018316` — UFO loader** `[CONFIRMED @ 0x10018316]`. Group `UFODisasterTunables`;
   `MaxUFOInstances`→`DAT_10039e90`, months-between/attack timers, and per-class building-
   destruction caps (see §4).
9. **`FUN_10020726` — Parade special-event loader** `[CONFIRMED @ 0x10020726]`. Group
   `ParadeEvent`/`ParadeEventTunables`; reads `RoadTilesRequired`→`DAT_1003a274`,
   `MaxParadeDuration`→`DAT_1003a270`, `ParadeCost`→`DAT_1003a280` (+`DAT_1003a284=0`),
   `MinPopulation`→`DAT_1003a288`, `MinCommercial`→`DAT_1003a28c`, `MinAura`→`DAT_1003a290`,
   `SpectatorDensity`→`DAT_1003a294`, `PetitionerTiming`→`DAT_1003a298`,
   `MinMonthsBetweenEvents`→`DAT_1003a278`, `EventProbability`→`DAT_1003a29c`; then enumerates
   `ParadeEventParadeBlocks` (callback `FUN_1001f9a3`) and `ParadeEventParadeConfigs` (callback
   `FUN_1001fa88`).
10. **`FUN_10014c98` — Toxic-cloud pollution score** `[CONFIRMED @ 0x10014c98]`. Computes
    `score = (WeightForPollution(DAT_10039b50) * pollutionSample) / normalizer`, then **subtracts
    ordinance weights** if the ordinance is active — querying an ordinance/simulator interface at
    `obj+0x7c` (vtable+0xC) with ids `0xe2f6e7ea`, `0x02f6e7e2`, `0xa2f917cf` (subtracting
    `_DAT_10039b54/b58/b5c`), then **adds** `WeightForEachToxicWastePlant(DAT_10039b60) *
    plantCount` (plantCount from `obj+0x80` vtable+0x60 with tag `0x4a39`). `obj+0x78` is the
    pollution-data layer.
11. **`FUN_10014fc8` — Toxic-cloud trigger test** `[CONFIRMED @ 0x10014fc8]`. Returns a float
    gate: fires only if `DAT_10039b1c > field+0x38`, sample `field+0x78 ≥ ftol(...)`, **and**
    `FUN_10014c98(...) > ThresholdScoreForToxicCloud(DAT_10039b64)`; otherwise returns
    `_DAT_1003248c`.
12. **`FUN_1001a26b` — disaster area/footprint builder** `[CONFIRMED @ 0x1001a26b]`. Fills a
    rectangular tile buffer `(x1..x2)×(y1..y2)` (fields `+0x0c/+0x10/+0x14/+0x18`), packing each
    tile as `(x&0xFF) | ((y&0xFF)<<8)` into the vector at `+0x20`; in the alternate branch it
    bins the area against thresholds `DAT_1003337e/…392/…3a6/…3ba/…3ce/…3e2/…3f6` to pick a
    step from table `DAT_1003336c`, then draws a random origin cell with `rand() %
    areaCount`. Calls `FUN_1001b95d` (uses `rand()`, `[CONFIRMED @ 0x1001b95d]`).

## 4. Data / tunables (raw)

All tuning is read from `\Sys\SC3DisasterLayer.INI` inside `\Sys\SYS.PAK`
[CONFIRMED @ 0x100396ec, 0x100396dc]. INI groups (section keys) present as strings:

| Group string | RVA | Disaster/event |
|---|---|---|
| `FireDisaster` | 0x100396cc | Fire |
| `MiscDisasterTunables` | 0x10039788 | shared relief/emergency |
| `DisasterDescriptions` | 0x100397b8 | text table |
| `LocustDisasterTunables` | 0x100399d0 | Locust swarm |
| `RiotDisaster` | 0x10039a30 | Riot |
| `TornadoDisaster` | 0x10039b0c | Tornado |
| `ToxicCloudDisasterTunables` | 0x10039e5c | Toxic cloud / acid rain |
| `UFODisasterTunables` | 0x1003a1fc | UFO attack |
| `ParadeEventTunables` / `ParadeEvent` | 0x1003a37c / 0x1003a3a4 | Parade event |

**Shared relief (Misc)** [CONFIRMED @ 0x100092d6]: `MaxEmergencyDuration`→`DAT_10039724`,
`MinDisasterCostToGetRelief`→`DAT_1003a7ac`, `ReliefAsPercentageOfCostWithoutEW`→`DAT_1003a7a9`,
`ReliefAsPercentageOfCostWithEW`→`DAT_1003a7a8`.

**Toxic cloud scoring inputs** [CONFIRMED @ 0x10014c98/0x10015751]: `WeightForPollution`
→`DAT_10039b50`; ordinance weights `WeightForCleanIndustryOrdinance`→`_DAT_10039b54`,
`WeightForIndPollutantFeeOrdinance`→`_DAT_10039b58`, `WeightForWasteDisposalOrdinance`
→`_DAT_10039b5c`; `WeightForEachToxicWastePlant`→`DAT_10039b60`;
`ThresholdScoreForToxicCloud`→`DAT_10039b64`; `ScorePerLevelIncrement`→`DAT_10039b68`
(default 10). Rain timing: `Min/MaxRainDuration`→`DAT_10039b74/b78`,
`Min/MaxTimeForRainStart`→`DAT_10039b6c/b70`, `MinGapBetweenRains`→`_DAT_10039b7c`,
`Abandon/DestructionRadiusIncrementPerLevel`→`DAT_10039b80/b84`,
`Destruction/AbandonLikelihood`→`DAT_10039b88/b8c`. Ordinance-active query ids (into ordinance
layer): `0xe2f6e7ea`, `0x02f6e7e2`, `0xa2f917cf`; toxic-waste-plant count tag `0x4a39`.

**UFO caps** (keys present) [CONFIRMED @ 0x10039f20–0x1003a210]:
`PercentageOfBuildingsCatchFireByUFOBombs`, `PercentageOfBuildingsDestroyedByUFOBombs`,
`Max{Power,HighTech,LowTech,Spaceport,Landmark}BuildingsDestroyedPerAttack`,
`MaxTotalBuildingsToDestroy`, `MaxCropCirclesMadePerAttack`, `MaxAbductionsMadePerAttack`,
`MaxUFOsPerInstance{,CheatSwarm}`, `Min/MaxMonthsBetweenUFOAttacks`, `TimeBeforeUFOAttack{,End}`,
`PercentageChanceOfUFOAttackEachMonthTimes100`, `PercentageChanceOfUFOExplosionOnExitTimes100`,
`YearOfFirstPossible{Attack,CropCircle,Abduction}Appearance`, `MaxUFOInstances`→`DAT_10039e90`.

**Fire property ids (32-bit)** [CONFIRMED @ 0x1000613e]: `0x047df002`, `0x647df00f`,
`0xc47df01a`, `0xa47df024`, `0x647df02b`, `0x647df032`, `0x247df038`, `0xa47df03e`, `0x047df044`,
`0xe47df04a`, `0x047df051`, `0xa47df05a`, `0x047df061`.
**Riot property ids** [CONFIRMED @ 0x1000dc3a]: `0x6484a25d …` (12, listed §3.5).
**Tornado property ids** [CONFIRMED @ 0x1001367e]: `0xe48381bc …` (14, listed §3.6).

**Toxic-area step table**: `DAT_1003336c` (array of `short`), thresholds `DAT_1003337e`,
`DAT_10033392`, `DAT_100333a6`, `DAT_100333ba`, `DAT_100333ce`, `DAT_100333e2`, `DAT_100333f6`;
step constants `0/10/0x14/0x1e/0x28/0x32/0x3c` [CONFIRMED @ 0x1001a26b].

**Parade macro tokens** [CONFIRMED @ 0x1003a588–0x1003a5dc]: `%MAYOR%`, `%YOURNAME%`,
`%CITYNAME%`, `%YOURCITY%`, `%POPULATION%`, `%YEAR%`, `%PARADENAME%`, `%ANYNEIGHBOR%`.

## 5. Cross-module edges

- **Resource / persistence service** — `FUN_1002a7b8` returns a singleton (cached in
  `DAT_1003ad10`); its vtable slot `+0x50` builds the `SC3DisasterLayer.INI` and `SYS.PAK`
  paths that are handed to the INI reader. `[CONFIRMED @ 0x1002a7b8]`
- **Property/INI provider** — `FUN_1002a8d6` returns a singleton (cached in `DAT_1003ad1c`);
  its vtable `+0x14` fetches a typed value by 32-bit property id. `[CONFIRMED @ 0x1002a8d6]`
- **Ordinance / simulator layer** — toxic-cloud scoring calls an interface at object `+0x7c`
  (`vtable+0xC`, ids `0xe2f6e7ea`/`0x02f6e7e2`/`0xa2f917cf`) to test active ordinances, a
  pollution-data layer at `+0x78` (`vtable+0x78`/`+0x84`), and a plant-count service at `+0x80`
  (`vtable+0x60`, tag `0x4a39`). These are held pointers to other GZCOM layers (the ordinance
  set is owned by SIMMISC per MODULE_MAP.md). `[CONFIRMED @ 0x10014c98]`
- **OLE / COM** — imports `CoCreateInstance`, `CoInitialize`, `CoUninitialize` from `Ole32.dll`
  [CONFIRMED @ 0x1003a540–0x1003a574]. Call sites not yet located → §7.
- Imports: `WINMM.dll` (`timeGetTime`), `MSVCP60`/`MSVCIRT`/`MSVCRT`, `KERNEL32`, `USER32`
  [CONFIRMED @ strings.csv]. `[iOS-HINT]` the iOS twin names this subsystem `goDisasterLayer`
  / `cSC3DisasterLayer`; not confirmed against SC3U-side evidence — treat as hypothesis.

## 6. Classification table (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x10024e87,disaster-director,C2,sc3_dstr_get_gzcom_director,"PE export; guarded init of DAT_1003abf0, calls ctor FUN_1002269e + onexit"
0x1002269e,disaster-director,C2,sc3_dstr_director_ctor,"installs director vtables; 12x FUN_1002520d(GZCLSID,factory,0)"
0x1002520d,disaster-director,C2,sc3_dstr_register_class,"builds {clsid,factory,0}; inserts into map at this+0x14 via FUN_1002547e"
0x10007978,disaster-layer,C2,sc3_dstr_layer_ctor,"class#1 0x61f6abf5; 4 vtables + 2 circular lists (FUN_1000454c 0x10) + FUN_100298cc"
0x100227b5,disaster-factory,C2,sc3_dstr_factory_layer,"new(0x108)+FUN_10007978, returns obj+4; factory for 0x61f6abf5"
0x100227f3,disaster-factory,C2,sc3_dstr_factory_cls2,"new(0x90)+FUN_100051e2, returns obj+0xC; 0x428fd431"
0x10022831,disaster-factory,C2,sc3_dstr_factory_cls3,"new(0x80)+FUN_10012de1; 0x62a34670"
0x1002286f,disaster-factory,C2,sc3_dstr_factory_cls4,"new(0x88)+FUN_1000121c; 0x22fe8d32"
0x100228ad,disaster-factory,C2,sc3_dstr_factory_cls5,"new(0x88)+FUN_1000d0d1; 0xe2fe8d38"
0x100228eb,disaster-factory,C2,sc3_dstr_factory_cls6,"new(0x88)+FUN_10017c9a; 0x22fe8d3e"
0x10022929,disaster-factory,C2,sc3_dstr_factory_cls7,"new(0x90)+FUN_1001eddd; 0x84c92cbe"
0x10022967,disaster-factory,C2,sc3_dstr_factory_cls8,"new(0x98)+FUN_10014d61; 0xc2fe8d43"
0x100229a5,disaster-factory,C2,sc3_dstr_factory_cls9,"new(0x88)+FUN_1001bd9d; 0x52fe8d50"
0x100229e3,disaster-factory,C2,sc3_dstr_factory_cls10,"new(0x90)+FUN_1000a325; 0x52fe8d51"
0x10022a21,disaster-factory,C2,sc3_dstr_factory_cls11,"new(0x88)+FUN_100106fe; 0x52fe8d52"
0x10022a5f,disaster-factory,C2,sc3_dstr_factory_cls12,"new(0x88)+FUN_1000f036; 0x52fe8d53"
0x100051e2,disaster-class,C2,sc3_dstr_cls2_ctor,"base FUN_1002a6ef; vtable[4]=PTR_LAB_10032450->100323d8; embeds string at +0x1b"
0x10012de1,disaster-class,C2,sc3_dstr_cls3_ctor,"base ctor; vtable[4]=PTR_LAB_10033104->10033090"
0x1000121c,disaster-class,C2,sc3_dstr_cls4_ctor,"base ctor; vtable[4]=PTR_LAB_10032238->100321ac"
0x1000d0d1,disaster-class,C2,sc3_dstr_cls5_ctor,"base ctor; vtable[4]=PTR_LAB_10032c4c->10032bd8; inits [0x1e]=10"
0x10017c9a,disaster-class,C2,sc3_dstr_cls6_ctor,"base ctor; vtable[4]=PTR_LAB_10033480->10033408; inits [7]=1"
0x1001eddd,disaster-class,C2,sc3_dstr_cls7_ctor,"base ctor; vtable[4]=PTR_LAB_10033774->100336f0; inits [0x1f]=1"
0x10014d61,disaster-toxiccloud,C2,sc3_dstr_toxic_ctor,"base ctor; vtable[4]=PTR_LAB_10033288; code-locality with toxic scoring 0x10014c98/0x10014fc8"
0x1001bd9d,disaster-class,C2,sc3_dstr_cls9_ctor,"base ctor; vtable[4]=PTR_LAB_100335f4->10033578"
0x1000a325,disaster-class,C2,sc3_dstr_cls10_ctor,"base ctor; vtable[4]=PTR_LAB_100328cc->10032850"
0x100106fe,disaster-class,C2,sc3_dstr_cls11_ctor,"base ctor; vtable[4]=PTR_LAB_10032f4c->10032ecc"
0x1000f036,disaster-class,C2,sc3_dstr_cls12_ctor,"base ctor; vtable[4]=PTR_LAB_10032dd0->10032d54"
0x1002a6ef,disaster-infra,C2,sc3_dstr_object_base_ctor,"zeros [1]/[2]; sets vtable PTR_FUN_10033f38"
0x1002a7b8,disaster-infra,C2,sc3_dstr_get_resource_service,"lazy singleton DAT_1003ad10; vtable+0x50 builds INI/PAK path"
0x1002a8d6,disaster-infra,C2,sc3_dstr_get_property_provider,"lazy singleton DAT_1003ad1c; vtable+0x14 fetch-by-propid"
0x1000613e,disaster-fire,C2,sc3_dstr_fire_load_tunables,"group FireDisaster; 13 prop ids 0x*47df*; writes DAT_1003967c..DAT_100396ac"
0x10005814,disaster-fire,C2,sc3_dstr_fire_parse_entry,"FireDisaster entry callback; FUN_10025684 vs DAT_100396c8; writes DAT_1003a728/72c"
0x100092d6,disaster-relief,C2,sc3_dstr_misc_load_tunables,"MiscDisasterTunables + DisasterDescriptions(FUN_10008d27); writes DAT_10039724/DAT_1003a7ac/a9/a8"
0x1000aa59,disaster-locust,C2,sc3_dstr_locust_load_tunables,"group LocustDisasterTunables; ~16 keys DAT_100397d0.."
0x1000dc3a,disaster-riot,C2,sc3_dstr_riot_load_tunables,"group RiotDisaster(FUN_1000d680); 12 prop ids 0x*484a2*; FUN_1000df36"
0x1001367e,disaster-tornado,C2,sc3_dstr_tornado_load_tunables,"group TornadoDisaster(FUN_1001325a); 14 prop ids 0x*4838*; 2 float casts; FUN_100139c2"
0x10015751,disaster-toxiccloud,C2,sc3_dstr_toxic_load_tunables,"group ToxicCloudDisasterTunables; ~30 keys w/ clamps; speed=val*DAT_10033114*DAT_10033118"
0x10018316,disaster-ufo,C2,sc3_dstr_ufo_load_tunables,"group UFODisasterTunables; MaxUFOInstances->DAT_10039e90 + building caps"
0x10020726,disaster-parade,C2,sc3_dstr_parade_load_tunables,"group ParadeEvent(FUN_1001f933)/ParadeEventTunables; blocks(FUN_1001f9a3)/configs(FUN_1001fa88)"
0x10014c98,disaster-toxiccloud,C2,sc3_dstr_toxic_compute_score,"WeightForPollution*sample/norm - ordinance weights + WeightForEachToxicWastePlant*count"
0x10014fc8,disaster-toxiccloud,C2,sc3_dstr_toxic_should_trigger,"gate vs DAT_10039b1c, ftol sample, score>ThresholdScoreForToxicCloud(DAT_10039b64)"
0x1001a26b,disaster-spread,C2,sc3_dstr_build_area_footprint,"packs (x&0xFF)|((y&0xFF)<<8) tiles; bins area vs DAT_1003337e..; rand() origin; calls FUN_1001b95d"
0x1001b95d,disaster-spread,C1,sc3_dstr_shuffle_area,"uses rand(); called by FUN_1001a26b to randomize the tile buffer"
```

## 7. OPEN (undetermined + missing evidence)

- **GZCLSID → disaster-type mapping for classes #2–#12.** The ctors carry no name string; the
  disaster identity lives only in the tuning-group strings, which are referenced by the *loader*
  functions, not the class ctors. Confirming e.g. "#8/`0xc2fe8d43` = Toxic Cloud" needs the tick/
  init method inside each class's vtable to be read and shown reading that disaster's `DAT_*`
  globals. The Toxic Cloud→#8 tie is a **code-locality inference only** (`FUN_10014d61` ctor sits
  in the same 0x10014xxx block as the toxic scorers `FUN_10014c98`/`FUN_10014fc8`) — **[UNCERTAIN]**.
  Missing: per-class vtable dump (`PTR_FUN_*`/`PTR_LAB_*` targets) and which loader each vtable
  method calls.
- **Who invokes the 8 tunable loaders.** A body-text grep for each loader name across the export
  returns only the loader's own file — no direct textual caller. They are reached indirectly
  (via a vtable slot or a data-referenced pointer). **[UNCERTAIN]** — missing: the DATA xref /
  vtable slot that holds each loader's address (needs `symbols.csv`/`globals.csv` or a live-Ghidra
  reference query).
- **Message ids sent to other layers.** No `PostMessage`/`SendMessage`/message-dispatch pattern
  was located; only inbound property/ordinance queries (§5) are confirmed. How a triggered
  disaster notifies the UI/news/finance layers is **not determined** — missing: the layer's
  update/tick method and any GZ message-broadcast call site.
- **`CoCreateInstance` usage.** Ole32 is imported but the call site and the CLSID passed are not
  yet located in the read set. **[UNCERTAIN]** — missing: xref to the `CoCreateInstance` thunk.
- **Numeric tunable defaults.** Values are read from `SC3DisasterLayer.INI` at runtime; only the
  in-code clamps/defaults are visible (e.g. ToxicCloud min-clouds≥1, ScorePerLevelIncrement=10).
  The shipped defaults themselves require reading the INI inside `SYS.PAK` (data-file extraction,
  not decompilation).
- **`SC3FireLayer`/`FlammabilityLayer`** (per MODULE_MAP.md) are **not** in this module — those
  strings live in SIMSERV.DLL. SIMDSTR's fire content is the `FireDisaster` *event*, distinct
  from the persistent fire/flammability layer.
