# SIMADV.DLL — Second-pass RE results

All addresses are Ghidra VAs in the `SIMADV.DLL` image (base `0x10000000`). Every claim below was read directly from `re/ghidra_export_simadv/functions/`.

## JOB 1 — C1 → C2 promotions

### The register-class helper — `0x10024b9d` (44 bytes)
Forwards its 3 args as a key/value pair into the director's factory map. `__thiscall`, copies `param_1`(GZCLSID)→`local_18`, `param_2`(factory)→`local_10`, `param_3`(0)→`local_14`, then calls `FUN_10024e9a((this+0x14), &local_c, &local_18)` `[CONFIRMED @ 0x10024b9d:11-14]`. `this+0x14` is the director's class map (matches doc §2); `FUN_10024e9a` is the map-insert. Trivial one-call forwarder but mechanically complete → **C2**.

### The six advisor ctors — one shared template
All six are `__fastcall(param_1=instance)` and follow an identical shape `[CONFIRMED]`:
1. `*param_1 = &PTR_LAB_<primary vtable>`; call base subobject ctor `FUN_1001cf14(param_1+1)`; zero a block of fields.
2. Install the MI vtables at `param_1[0]`, `param_1[1]`, `param_1[2]`, `param_1[5]` (four distinct `PTR_LAB_1003xxxx`).
3. Build a local GZ list with `FUN_10003a5f`, then append **four topic/newspaper resource-id entries**: each entry is `FUN_1002a207(buf, <index>, <group>)` → `FUN_1002a267` → `FUN_100037e7` → `FUN_10003bd8`, inserted via `FUN_1001d453 / _1d724 / _1d632 / _1d741`.
4. Query game edition: `piVar = FUN_10027b3d(); uVar = (*(piVar+0x20))()`, then select a **topic-graphic resource key** = the triple `{0x62b9da24, 0x52db60a0, <instance>}` and store it via `FUN_1001d84d` + `FUN_1001d867`.
5. Write default tunable field values, and set `param_1[0x24]` to a per-class id.

Per-ctor specifics `[CONFIRMED]`:

| ctor RVA | domain | `FUN_1002a207` calls `(index, group)` | topic-gfx instance byte | `param_1[0x24]` | notable defaults |
|---|---|---|---|---|---|
| `0x10006656` | City Planner | `(0x57,0xc29a6083)`,`(0x2c5,0x29541f4)`,`(0x2be,0x29541f4)`,`(0x156,0x29541f4)` | `0x03` | `0x12d` | `[0x32]=10`,`[0x38]=50000`,`[0x30]=20000`,`[0x31]=100000`,byte`+0xd7=0x78`,`[0x24]=0x12d` |
| `0x1000c8e1` | Demographics | `(0x53,0xc29a6083)`,`(0x2c8,0x29541f4)`,`(0x2c1,0x29541f4)`,`(0x15c,0x29541f4)` | `0x07` | `0x12a` | `[0x30]=5000`,`[0x2c]=[0x2d]=2000`,`[0x2a]=15000`,`[0x2b]=50000`,`[0x32]=52000`,`[0x33]=80000` |
| `0x1000f0db` | Environment | `(0x54,0xc29a6083)`,`(0x2c6,0x29541f4)`,`(0x2bf,0x29541f4)`,`(0x158,0x29541f4)` | `0x04` | `0x129` | builds circ-list node `FUN_100031c0(0xc)@[0x29]`; `[0x2a]=[0x2c]=[0x2e]=0x42`,`[0x2b]=[0x2d]=[0x2f]=0x21` |
| `0x10011be0` | Public Safety | `(0x55,0xc29a6083)`,`(0x2c7,0x29541f4)`,`(0x2c0,0x29541f4)`,`(0x15a,0x29541f4)` | `0x05` | `0x12f` | `FUN_1000b9e2(+0x50)`; byte`+0xa5=0x5a`,`[0x2b]=500`,`[0x2c]=25000`,`[0x2d]=5000` |
| `0x10015365` | Transportation | `(0x56,0xc29a6083)`,`(0x2c4,0x29541f4)`,`(0x2bd,0x29541f4)`,`(0x15b,0x29541f4)` | `0x06` | `0x12e` | `[0x2b]=0x776`,`[0x2c]=0x780`,`[0x2d]=0x78a`,`[0x2e]=0x794`,`[0x31]=0x3e19999a`(f),`[0x33]=0x7c0`,`[0x35]=0x785` |
| `0x10017ba8` | Utilities | `(0x51,0xc29a6083)`,`(0x2c9,0x29541f4)`,`(0x2c2,0x29541f4)`,`(0x159,0x29541f4)` | `0x01` | `300` | two circ-list nodes `@[0x29]`,`@[0x2a]`; `[0x36]=10000`,`[0x37]=0x789`,`[0x38]=5000`,`[0x5b]=0x42c80000`(f); tail `FUN_10028120/100280d4(0x10038748)` |

The middle byte of the instance dword (`0x00`/`0x01`/`0x02`) is chosen by the edition code from `FUN_10027b3d()+0x20`: `∈{1,2}`→`0x00`, `∈{0xf,0x11,0x12,0x13}`→`0x02`, else→`0x01` `[CONFIRMED @ e.g. 0x10017ba8:159-190]`. All six read line-by-line → **C2**.

### The four INI loaders (Demographics, PublicSafety, Transportation, Utilities)
Same template as doc §3.1 (`FUN_10029434` parser init → attach `Advisor-<Domain>.INI` then `\Sys\SYS.PAK` → per-key `FUN_1000300d`+`FUN_10029531` → convert → store at instance offset). Full offset maps (`+0x..` = byte offset on instance; converter noted) `[CONFIRMED]`:

**Demographics `0x1000d44f`** — section `FUNDING_RATE_CUTOFFS`: `HEALTH_FUNDING_HIGH`→byte`+0xa4`, `HEALTH_FUNDING_MEDIUM`→byte`+0xa5`, `EDUCATION_FUNDING_HIGH`→byte`+0xa6`, `EDUCATION_FUNDING_MEDIUM`→byte`+0xa7`. Section `ADVICE_TRIGGERS`: `RESIDENTIAL_GROWTH_CAP`→int`+0xa8`, `STADIUM_GROWTH_CUTOFF`→int`+0xac`, `SCHOOL_POPULATION_MINIMUM`→int`+0xbc`, `COLLEGE_POPULATION_MINIMUM`→int`+0xc0`, `HOSPITAL_POPULATION_MINIMUM`→int`+0xb0`, `LIBRARY_POPULATION_MINIMUM`→int`+0xb4`, `MUSEUM_POPULATION_MINIMUM`→int`+0xb8`, `ZOO_POPULATION_MINIMUM`→int`+0xc8`, `MARINA_POPULATION_MINIMUM`→int`+0xcc`, `LE_AND_EQ_POPULATION_MINIMUM`→id`+0xd8`(`FUN_100285a3`), `LOW_EQ_CUTOFF`→byte`+0xdc`, `AVERAGE_EQ_CUTOFF`→byte`+0xdd`, `HIGH_EQ_CUTOFF`→byte`+0xde`, `LOW_LIFE_EXPECTANCY`→byte`+0xdf`, `HIGH_LIFE_EXPECTANCY`→byte`+0xe0`, `CITY_AURA_DREARY_POPULATION`→int`+0xc4`, `LOW_DREARY_RATING`→byte`+0xe1`, `HIGH_DREARY_RATING`→byte`+0xe2`, `CITY_AURA_LOW`→byte`+0xd4`, `CITY_AURA_HIGH`→byte`+0xd5`. Section `PETITIONER_GENERATION`: `HOSPITAL_RATIO`→int`+0xd0`.

**Public Safety `0x100129ff`** — `FUNDING_RATE_CUTOFFS`: `POLICE_FUNDING_HIGH`→byte`+0xa4`, `POLICE_FUNDING_MEDIUM`→byte`+0xa5`, `FIRE_FUNDING_HIGH`→byte`+0xa6`, `FIRE_FUNDING_MEDIUM`→byte`+0xa7`. `ADVICE_GENERATION`: `FIRE_COVERAGE_CUTOFF`→byte`+0xa8`, `FIRE_STATION_MIN_POP`→id`+0xac`, `JAIL_MIN_POP`→id`+0xb0`, `HIGH_CRIME_LEVEL`→byte`+0xaa`, `MED_CRIME_LEVEL`→byte`+0xa9`. `PETITIONER_GENERATION`: `POLICE_STATION_RATIO`→id`+0xb4` (read only if all prior keys succeeded; on any failure the whole load aborts and returns 0 `[CONFIRMED @ 0x100129ff:271-314]`).

**Transportation `0x10015f9c`** — `FUNDING_RATE_CUTOFFS`: `ROAD_FUNDING_HIGH/MEDIUM/LOW`→byte`+0xa4/+0xa5/+0xa6`, `RAIL_FUNDING_HIGH/MEDIUM`→byte`+0xa7/+0xa8`. `TRANSPORTATION_ADVANCEMENTS`: `SUBWAY/BUS_STATION/AIRPORT/HIGHWAY_AVAILABLE`→id`+0xac/+0xb0/+0xb4/+0xb8`. `TRANSPORTATION_CUTOFFS`: `ROAD_DAMAGE`→**float**`+0xc4` (`atof × _DAT_10030f1c`), `HIGH_ROAD_TRAFFIC`→id`+0xbc`, `MED_ROAD_TRAFFIC`→id`+0xc0`, `MED_RAIL_USAGE`→id`+0xe4`, `HIGH_RAIL_USAGE`→id`+0xe8`. `PETITIONER_GENERATION`: `CARPOOL_TRIGGER_LEVEL`→id`+0xc8`, `CARPOOL_TRIGGER_YEAR`→id`+0xcc`, `CROSSING_GUARD_TRIGGER_LEVEL/YEAR`→id`+0xd0/+0xd4`, `BUS_STOP_TRIGGER_LEVEL`→id`+0xe0`, `ALTERNATE_DAY_DRIVING_YEAR`→id`+0xdc`, `ALTERNATE_DAY_DRIVING_LEVEL`→id`+0xd8`.

**Utilities `0x10018a51`** — `FUNDING_RATE_CUTOFFS`: `POWER_FUNDING_HIGH/MEDIUM`→**double**`+0xb0/+0xb8`, `WATER_FUNDING_HIGH/MEDIUM`→**double**`+0xc0/+0xc8` (all `atof × _DAT_10031108`). `CONSUMPTION_RATE_CUTOFFS`: `POWER_CONSUMPTION_CRITICAL/HIGH/MEDIUM`→byte`+0xd0/+0xd1/+0xd2`, `WATER_CONSUMPTION_CRITICAL/HIGH/MEDIUM`→byte`+0xd3/+0xd4/+0xd5`. `NEIGHBOR_DEAL_CONSTANTS`: `LOW_TREASURY_LEVEL`→int`+0xd8`, `MINIMUM_DEAL_POPULATION`→id`+0xe0`. `PETITIONER_GENERATION`: `WATER_CONSERVATION_YEAR`→id`+0xdc`. List keys: `POWER_BUILDINGS`→`FUN_10029828(..,LAB_100193b4,inst)`, `WATER_BUILDINGS`→`..LAB_100193c8`. → **C2**.

### The three connect methods
**Public Safety connect `0x1001215d`** `[CONFIRMED]`: stores sim at `this+0xf4`; sim-status obj at `this+0x13c` (`sim vtable+0x23c`); walks `sim vtable+0x1b8` nine times (layer iterate); binds one layer via `+0x11c` into `this+0x11c`; builds two query objects — `FUN_10011abd(new 0x38, 0xa2963983)`→`this+0x150` and `FUN_1001194d(new 0x38, 0x62963928)`→`this+0x154`, using resource keys `FUN_1002a207(0x92,0x29541f4)` and `(0x94,0x29541f4)`; sets byte`+0x14c=100`, `+0x144=+0x148=0`; calls loader `FUN_100129ff`; builds two notification adapters `FUN_10014bbc`/`FUN_10014b8e`(new 0x10)→`this+0x120/+0x124`, registers them with `FUN_10029f48()+0x1c` then `+0x14`; **subscribes via `FUN_10027b11()+0x14`: `0xa2d1c5b9`, `0x62e5af45`, `0xc30177ca`, `0x3417e94`, `0x23417ec0`, `0x434346e6`**; registers cheats via `FUN_10029e7e()+0x2c` vtable: `(+0xc)(0x83110c8b, &DAT_10038890)`+subscribe, `(+0xc)(0x831109b4, &DAT_100388f0)`+subscribe; installs callback `FUN_100132a6` on adapter `this+0xf8 (+0x2c)`; tail-calls `FUN_1001d22b(this, sim)`. → **C2**.

**Utilities connect `0x1001816b`** `[CONFIRMED]`: sim at `this+0xd4`; pulls layers by GZCLSID via `sim vtable+0x1b8` with nested null-guards — `0xe0afdf68`→`(0xa0afdf5d, this+0xd8)`, `0x82937b60`→`(0xc2910e7d, this+0xec)`, `0xa11bcc54`→`(0xe11bcc69, this+0xe4)`, `0x2bf0033`→`(0xc2bf0039, this+0xdc)`, `0xaaa1bb`→`(0x80a814ac, this+0xe0)`, `0x80f1e6d3`→`(0x40a42f1c, this+0xe8)`, `0xc106c4f5`→`(0x4106c508, this+0xfc)`, `0xe1193c2a`→`(0x41193c3a, this+0xf4)`, `0xa0ab89f0`→`(0x20631788, this+0xf8)`; gets a value via `+0x1a4`→`this+0x100`; calls loader `FUN_10018a51`; builds adapters `FUN_1001c921`/`FUN_1001c8eb`→`this+0x10c/+0x110`, registers via `FUN_10029f48()+0x1c(0xc2505969)`; **subscribes via `FUN_10027b11`: `0xa2d1c5b9`, `0x434346e6`**; registers cheats: `(0xc2fa8e82,&DAT_10038800)`, `(0x42fa93fe,&DAT_100387e8)`, `(0xc310f7d4,&DAT_10038860)`, `(0x831109b4,&DAT_100388f0)`; tail-call `FUN_1001d22b`. → **C2**.

**Petitioner connect `0x1001e6af`** `[CONFIRMED]`: sim at `this+0x24`; builds notification adapter `FUN_10022eeb`(new 0x10)→`this+0x20`; byte`+0xa8=1`, `+0x28=0`; pulls sub-objects via `sim+0x1b8`: `0xa11bcc54`→`(0xe11bcc69,this+0x28)`, `0xe1193c2a`→`(0x41193c3a,this+0x34)`, `0xc106c4f5`→`(0x4106c508,this+0x2c)`, `0x259c03f`→`(0x4259c018,this+0x30)`, `0x82937b60`→`(0xc2910e7d,this+0x38)`; pulls 7 layer pointers via `sim+0x1b0/+0x1a8/+0x19c/+0x1a4/+0x1a0/+0x1ac/+0x198`→`this+4/+8/+0xc/+0x10/+0x14/+0x18/+0x1c`; calls loader `FUN_1001ecad`; registers cheats: `(0x31dce55,&DAT_10038830)`, `(0x831109b4,&DAT_100388f0)`, `(0xa3558fd6,&DAT_100387a0)`; subscribes `0xa4c68296` via `FUN_10027b11`. → **C2**.

### Promoted-rows CSV
```csv
rva,subsystem,confidence,new_name,evidence
0x10024b9d,advisor-director,C2,sc3_advisor_director_insert_factory,"forwards (GZCLSID,factory,0) to map-insert FUN_10024e9a on director+0x14 [0x10024b9d:11-14]"
0x10006656,advisor-cityplanner,C2,sc3_advisor_ctor_cityplanner,"4 vtables 10030154..; topic-ids grp 0xc29a6083 idx0x57 + grp0x29541f4 idx0x2c5/0x2be/0x156; topicgfx instance byte 0x03; this[0x24]=0x12d; defaults this[0x38]=50000,[0x30]=20000,[0x31]=100000 [0x10006656]"
0x1000c8e1,advisor-demographics,C2,sc3_advisor_ctor_demographics,"topic grp0xc29a6083 idx0x53 + 0x2c8/0x2c1/0x15c; gfx byte 0x07; this[0x24]=0x12a; defaults [0x30]=5000,[0x2a]=15000,[0x2b]=50000,[0x32]=52000,[0x33]=80000 [0x1000c8e1]"
0x1000f0db,advisor-environment,C2,sc3_advisor_ctor_environment,"circ-list FUN_100031c0(0xc)@[0x29]; topic grp0xc29a6083 idx0x54 + 0x2c6/0x2bf/0x158; gfx byte 0x04; this[0x24]=0x129; [0x2a/0x2c/0x2e]=0x42,[0x2b/0x2d/0x2f]=0x21 [0x1000f0db]"
0x10011be0,advisor-publicsafety,C2,sc3_advisor_ctor_publicsafety,"FUN_1000b9e2(+0x50); topic grp0xc29a6083 idx0x55 + 0x2c7/0x2c0/0x15a; gfx byte 0x05; this[0x24]=0x12f; [0x2b]=500,[0x2c]=25000,[0x2d]=5000 [0x10011be0]"
0x10015365,advisor-transportation,C2,sc3_advisor_ctor_transportation,"topic grp0xc29a6083 idx0x56 + 0x2c4/0x2bd/0x15b; gfx byte 0x06; this[0x24]=0x12e; [0x2b-0x2e]=0x776/0x780/0x78a/0x794,[0x31]=float 0x3e19999a [0x10015365]"
0x10017ba8,advisor-utilities,C2,sc3_advisor_ctor_utilities,"two circ-lists @[0x29]/[0x2a]; topic grp0xc29a6083 idx0x51 + 0x2c9/0x2c2/0x159; gfx byte 0x01; this[0x24]=300; [0x36]=10000,[0x37]=0x789,[0x38]=5000; tail FUN_10028120/280d4(0x10038748) [0x10017ba8]"
0x1000d44f,advisor-demographics,C2,sc3_advisor_load_demographics_ini,"Advisor-Demographics.INI+SYS.PAK; FUNDING_RATE_CUTOFFS->byte+0xa4..+0xa7; ADVICE_TRIGGERS->int+0xa8..+0xcc & EQ/aura bytes+0xd4..+0xe2; PETITIONER_GENERATION/HOSPITAL_RATIO int+0xd0 [0x1000d44f]"
0x100129ff,advisor-publicsafety,C2,sc3_advisor_load_publicsafety_ini,"Advisor-PublicSafety.INI; FUNDING_RATE_CUTOFFS byte+0xa4..+0xa7; ADVICE_GENERATION +0xa8..+0xb0 & crime bytes +0xa9/+0xaa; POLICE_STATION_RATIO id+0xb4; aborts on any missing key [0x100129ff]"
0x10015f9c,advisor-transportation,C2,sc3_advisor_load_transportation_ini,"Advisor-Transportation.INI; funding byte+0xa4..+0xa8; ADVANCEMENTS id+0xac..+0xb8; ROAD_DAMAGE float+0xc4(*_DAT_10030f1c); CUTOFFS/PETITIONER ids +0xbc..+0xe8 [0x10015f9c]"
0x10018a51,advisor-utilities,C2,sc3_advisor_load_utilities_ini,"Advisor-Utilities.INI; funding DOUBLE+0xb0/+0xb8/+0xc0/+0xc8(*_DAT_10031108); CONSUMPTION bytes+0xd0..+0xd5; NEIGHBOR_DEAL int+0xd8/id+0xe0; POWER/WATER_BUILDINGS lists cb LAB_100193b4/c8 [0x10018a51]"
0x1001215d,advisor-publicsafety,C2,sc3_advisor_connect_publicsafety,"sim@+0xf4; query objs FUN_10011abd(0xa2963983)@+0x150,FUN_1001194d(0x62963928)@+0x154; loader FUN_100129ff; subs 0xa2d1c5b9/0x62e5af45/0xc30177ca/0x3417e94/0x23417ec0/0x434346e6; cheat 0x83110c8b&DAT_10038890(Maria) [0x1001215d]"
0x1001816b,advisor-utilities,C2,sc3_advisor_connect_utilities,"sim@+0xd4; 9 layer-gets via +0x1b8; loader FUN_10018a51; subs 0xa2d1c5b9/0x434346e6; cheats 0xc2fa8e82&DAT_10038800,0x42fa93fe&DAT_100387e8,0xc310f7d4&DAT_10038860(Gus),0x831109b4&DAT_100388f0 [0x1001816b]"
0x1001e6af,petitioner,C2,sc3_petitioner_connect_manager,"sim@+0x24; adapter FUN_10022eeb@+0x20; 7 layers via +0x198..+0x1b0; loader FUN_1001ecad; cheats 0x31dce55&DAT_10038830,0x831109b4&DAT_100388f0,0xa3558fd6&DAT_100387a0; sub 0xa4c68296 [0x1001e6af]"
0x10002138,advisor-topicgfx,C2,sc3_advisor_load_topicgfx_ini,"reads Advisor-TopicGfxIDs.INI then GoldAdvisor-TopicGfxIds.ini +SYS.PAK; section AdvisorTopicGfxIDs key '0x%08X'; writes resource-key triple param2[0]=0x62b9da24,[1]/[2]=FUN_100285a3(values) [0x10002138]"
0x100018f9,advisor-moods,C2,sc3_advisor_load_moods_ini,"reads AdvisorMoods.INI then GoldAdvisorMoods.INI +SYS.PAK; key fmt '0x%08X'; base(local_18==0)/Gold(==1) two-pass [0x100018f9]"
```

## JOB 2 — OPEN-list resolutions

**1. Human-readable class names — STILL OPEN.** Unchanged: no C++ class-name strings in `SIMADV.DLL`. Blocker unchanged (needs iOS `re/ghidra_export_ios` grep for `cSC3…Advisor` + GZCLSID confirmation against `SYS.PAK`/`CitySim.ini`). *I did not run the iOS grep — no `[iOS-HINT]` claim is made here.*

**2. Cheat-name → advisor-domain binding — RESOLVED (5 of 8 direct; 3 by elimination).** Complete cheat-string global map `[CONFIRMED @ registrars 0x1001cc1e-0x1001cdfe]`: `DAT_100388f0`="stop forcing advice", `DAT_100388d8`=Mortimer, `DAT_100388c0`=Moe, `DAT_100388a8`=Constance, `DAT_10038890`=Maria, `DAT_10038878`=Randall, `DAT_10038860`=Gus, `DAT_10038848`=Karen, `DAT_10038830`="force petitioners to say", `DAT_10038818`="garbage in, garbage out", `DAT_10038800`="power to the masses", `DAT_100387e8`="water in the desert", `DAT_100387a0`="call cousin Vinnie". The connect methods bind (character, message-id):

| advisor | connect | character | cheat global | msg id |
|---|---|---|---|---|
| Demographics | `0x1000ce3b` | **Randall** | `DAT_10038878` | `0x83110c8b` |
| Public Safety | `0x1001215d` | **Maria** | `DAT_10038890` | `0x83110c8b` |
| Transportation | `0x1001588a` | **Moe** | `DAT_100388c0` | `0x43110c27` |
| Utilities | `0x1001816b` | **Gus** | `DAT_10038860` | `0xc310f7d4` |
| Petitioner Mgr | `0x1001e6af` | petitioners | `DAT_10038830` | `0x31dce55` |

The remaining three characters — **Mortimer (`DAT_100388d8`), Constance (`DAT_100388a8`), Karen (`DAT_10038848`)** — belong to **Budget, City Planner, Environment** (the only advisors left). *Which is which is `[UNCERTAIN]`:* a full-export grep shows those three globals' addresses are taken **only** in their own registrar functions — no connect method in the text export references them. The Budget/CityPlanner/Environment connect/register code is reached through a vtable slot (their loaders `FUN_10004652`/`_10007989`/`_1000fc90` also have zero direct callers in the export, confirming vtable dispatch). *Tool to break it:* `VtableDump.java` on the advisor primary vtables (`PTR_LAB_1003056c` Budget-region etc.) to find each connect method, then read its `(+0xc)(msgid,&DAT_globa l)` line.

**3. Message-id / resource-group meanings — PARTIALLY RESOLVED.**
- **`0xc29a6083` and `0x29541f4` = GZ resource *group* ids** passed to `FUN_1002a207(buf, index, group)`; each advisor ctor pulls one entry from group `0xc29a6083` (indices `0x51`–`0x57`, one per advisor) and three from group `0x29541f4` (indices `0x150`–`0x2c9`) as its newspaper/topic resource entries `[CONFIRMED, all 6 ctors]`.
- **`0x62b9da24` = resource *type* id, `0x52db60a0` = resource *group* id** of the advisor topic-graphic key. Proven by the TopicGfx loader `FUN_10002138`, which writes `param2[0]=0x62b9da24` as the key's type field `[CONFIRMED @ 0x10002138:75]`, matching the `{0x62b9da24,0x52db60a0,instance}` triples built in every ctor.
- **`0x83110c8b`** = the "force advice" cheat channel (Demographics + Public Safety register their character string under it); **`0x831109b4`** = "stop forcing advice" (every advisor + petitioner) `[CONFIRMED]`. **`0xa2d1c5b9`** = subscribed by every connect via `FUN_10027b11+0x14` — the common advisor event/heartbeat. **`0x434346e6`** subscribed by Public Safety + Utilities.
- **STILL OPEN:** the owning service/module for `0xa2d1c5b9`, `0x62e5af45`, `0xc30177ca`, `0x3417e94`, `0x23417ec0`, `0x434346e6`, `0xa4c68296`, and the layer-GZCLSIDs (`0xe0afdf68` etc.) is outside `SIMADV`. Needs a cross-module id scan over the other `Apps\*.DLL` GZCOM directors (not in this export).

**4. Six advisor ctors not read — RESOLVED.** All six read line-by-line (JOB 1 table above). Default fields and the four-vtable MI layout are captured; exact vtable *slot contents* remain in `.rdata` (see item 6).

**5. AdvisorMoods / TopicGfxIDs loaders — RESOLVED (located).**
- `FUN_10002138` = **Advisor-TopicGfxIDs loader** `[CONFIRMED @ 0x10002138]`: two-pass over `\Sys\Advisor-TopicGfxIDs.INI` (`local_18==0`) then `\Sys\GoldAdvisor-TopicGfxIds.ini` (`==1`), overlaid by `SYS.PAK`; section `AdvisorTopicGfxIDs`; key built with format `"0x%08X"` (`FUN_100255fa`); returns a 3-dword resource key `{0x62b9da24, FUN_100285a3(v1), FUN_100285a3(v2)}` in `param_2`.
- `FUN_100018f9` = **AdvisorMoods loader** `[CONFIRMED @ 0x100018f9]`: identical two-pass over `\Sys\AdvisorMoods.INI` then `\Sys\GoldAdvisorMoods.INI` + `SYS.PAK`, same `"0x%08X"` key format.

**6. Advice-emission / trigger-evaluation path — STILL OPEN (with concrete leads).** The subscribe calls make `this` a listener; the service dispatches to a fixed slot on the advisor's **primary vtable** (`*param_1 = &PTR_LAB_1003xxxx`), which lives in `.rdata` and is not in the decompiled bodies. One concrete callback was found: Public Safety installs `FUN_100132a6` on its `this+0xf8` adapter (`+0x2c`) `[CONFIRMED @ 0x1001215d:192]`. *Tool to break it:* `VtableDump.java` on each advisor primary vtable to resolve the `DoMessage`/notify slot, then read those bodies — that is where live sim values are compared against the loaded thresholds.

## New findings (with RVAs)

- **Business-deal / secret cheats are owned by specific advisors** `[CONFIRMED]`: Utilities connect registers `"power to the masses"` (`DAT_10038800` @msg `0xc2fa8e82`) and `"water in the desert"` (`DAT_100387e8` @msg `0x42fa93fe`) `[0x1001816b:118,124]`; Petitioner connect registers `"call cousin Vinnie"` (`DAT_100387a0` @msg `0xa3558fd6`) `[0x1001e6af:79]`. Registrars: `0x1001cdce`=`"garbage in, garbage out"`(`DAT_10038818`), `0x1001cdfe`=`"power to the masses"`, `0x1001ce2e`=`"water in the desert"`, `0x1001cebe`=`"call cousin Vinnie"`.
- **Topic-graphic resource key is edition-gated in code, not just INI** `[CONFIRMED, all 6 ctors]`: ctors hardcode the `{0x62b9da24,0x52db60a0,instance}` triple and pick the instance's edition byte from `FUN_10027b3d()+0x20` (`0x00` base / `0x01` / `0x02` Gold-BAT). Instance low byte = advisor id (Util `0x01`, CityPlanner `0x03`, Env `0x04`, PubSafety `0x05`, Transport `0x06`, Demo `0x07`; **Budget `0x02` not read but is the only unused value** — `[UNCERTAIN]`, verify by reading Budget ctor `0x10003c1f`).
- **`FUN_100076b1` is the City Planner disconnect/teardown** (not a connect) `[CONFIRMED]`: unsubscribes `0x831109b4`, `0x83110c50`, `0x631dc6ba`, `0x234da4d2` (via msg-service `+0x10`/`+0x18`) and `0xa2d1c5b9`, `0xc52e6bc9` (via `FUN_10027b11+0x18`), then nulls ~18 object pointers at `param_1+0x84..+0x2e8`. → City Planner's forced-advice channel is `0x83110c50` and it also uses `0x631dc6ba`, `0x234da4d2`.
- **Public Safety loader is fail-atomic** `[CONFIRMED @ 0x100129ff:271]`: if any required key is missing it skips `POLICE_STATION_RATIO`, tears down the parser and returns 0 (load failure) — the other three loaders instead set a "some-key-missing" flag but continue.
- **Two `_DAT` scaling constants**: `_DAT_10030f1c` (Transportation `ROAD_DAMAGE` float scale) and `_DAT_10031108` (Utilities funding double scale) `[CONFIRMED @ 0x10015f9c:297, 0x10018a51:79]`.

## Revised OPEN section (drop-in replacement for §7)

```
## 7. OPEN

- Human-readable class names. No C++ class-name strings in SIMADV.DLL. Unresolved.
  Missing: grep re/ghidra_export_ios for cSC3*Advisor / goAdvisor / Petition and
  confirm GZCLSID<->name against SYS.PAK / CitySim.ini.
- Budget / City Planner / Environment <-> Mortimer / Constance / Karen pairing.
  Character cheat globals DAT_100388d8 (Mortimer), DAT_100388a8 (Constance),
  DAT_10038848 (Karen) have their address taken ONLY in their registrars; the three
  advisors' connect/register + loader (FUN_10004652/_10007989/_1000fc90) have no direct
  callers -> dispatched via .rdata vtable slots. Missing: VtableDump.java on the Budget/
  CityPlanner/Environment primary vtables to locate the connect method, then read its
  (+0xc)(msgid,&DAT_global) line. (5 of 8 bindings CONFIRMED: Demo=Randall, PubSafety=
  Maria, Transport=Moe, Util=Gus, Petitioner=petitioners.)
- Owning module for cross-module message/layer ids: 0xa2d1c5b9, 0x62e5af45, 0xc30177ca,
  0x3417e94, 0x23417ec0, 0x434346e6, 0xa4c68296, 0x83110c50, 0x631dc6ba, 0x234da4d2, and
  the layer GZCLSIDs (0xe0afdf68, 0x82937b60, 0xa11bcc54, 0x2bf0033, 0xaaa1bb, 0x80f1e6d3,
  0xc106c4f5, 0xe1193c2a, 0xa0ab89f0, 0x259c03f). Not in SIMADV. Missing: cross-module id
  scan over the other Apps\*.DLL GZCOM directors.
- Advice-emission / trigger-evaluation path. Subscribers dispatch to a DoMessage-style
  slot on each advisor primary vtable (.rdata), not in the decompiled bodies. One callback
  found: FUN_100132a6 (PublicSafety adapter, 0x1001215d:192). Missing: VtableDump.java on
  the advisor vtables to resolve the notify slot, then read those bodies.
- Budget ctor 0x10003c1f topic-gfx edition byte (only unused advisor id 0x02) not yet
  confirmed by reading. Minor: read the FUN_1001d84d triple in 0x10003c1f.
```

RESOLVED and removed from OPEN: the six-ctors item, and the AdvisorMoods/TopicGfxIDs-loader item (loaders are `FUN_100018f9` and `FUN_10002138`).
(raw JSON: C:\Users\maria\AppData\Local\Temp\fleet-delegate-67ccf5102bb44dabaf7422577eda6899.json)
