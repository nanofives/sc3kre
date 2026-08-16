# SIMADV.md — SimCity 3000 advisors + petitioners module (`SIMADV.DLL` / `SimAdv.dll`)

Module RE from the greppable decompilation export `re/ghidra_export_simadv/`. All addresses are Ghidra VAs in this module's image (base `0x10000000`). Facts marked `[CONFIRMED @ 0xADDR]` are read directly from the decompiled C or `strings.csv`.

## 1. Purpose

`SIMADV.DLL` is the GZCOM director module that implements SimCity 3000's **seven newspaper/advisor characters** plus the **petitioner manager** (the citizens/lobbyists who walk in to request ordinances and deals). It registers 8 GZCOM classes: one advisor per city-management domain — **Budget, City Planner, Demographics, Environment, Public Safety, Transportation, Utilities** — and one **Petitioner Manager**. The module name string is `"SimAdv.dll"` `[CONFIRMED @ 0x10036822]` with export `"GZDllGetGZCOMDirector"` `[CONFIRMED @ 0x1003682d]`.

Each advisor is a data-driven rule engine: at connect time it loads an `\Sys\Advisor-<Domain>.INI` tuning file (overlaid from `\Sys\SYS.PAK`), populates threshold/cutoff fields on its instance, subscribes to sim messages, and emits advice. The `strings.csv` carries the complete tunable vocabulary: tax/treasury thresholds, RCI demand cutoffs, pollution cutoffs, crime/fire funding tiers, transportation-advancement trigger years, reward-building population minimums, and the full ordinance-enablement year table. It also carries the seven advisor personalities' cheat handles (`"force Mortimer to say"`, `"force Moe to say"`, `"force Constance to say"`, `"force Maria to say"`, `"force Randall to say"`, `"force Gus to say"`, `"force Karen to say"`, plus `"force petitioners to say"` and `"stop forcing advice"`) `[CONFIRMED @ 0x10037eb8–0x10037f64]`.

## 2. Director + registrations

**Chain** (matches the GZCOM recipe exactly):

- `GZDllGetGZCOMDirector` `[CONFIRMED @ 0x10024817]` — guarded one-shot: sets bit 1 of `DAT_100386d4`, calls the director ctor `FUN_1000102b(&DAT_10038690)`, registers an `_onexit` teardown `LAB_1000130f`, returns `&DAT_10038690` (the static director instance).
- **Director ctor `FUN_1000102b`** `[CONFIRMED @ 0x1000102b]` — calls base ctor `FUN_1002481c`, installs director vtables (`*this = &PTR_FUN_10030154`, `this[1] = &PTR_LAB_10030128`), then makes **8 `register_class` calls** to `FUN_10024b9d(director, GZCLSID, factory, 0)` (the recipe's insert-into-map-at-director+0x14 helper).

**Registration table** `[CONFIRMED @ 0x1000102b:21–28]`. Each factory does `operator_new(size)` + ctor; factories 1–7 return `object+4` (a secondary interface vtable — classic MI layout), factory 8 returns the object base:

| # | GZCLSID | factory RVA | `new` size | ctor RVA | class (domain) |
|---|---|---|---|---|---|
| 1 | `0x828d0c49` | `0x100010fa` | `0x170` | `0x10003c1f` | **Budget advisor** |
| 2 | `0xe28d0b76` | `0x10001138` | `0x318` | `0x10006656` | **City Planner advisor** |
| 3 | `0x028d0f43` | `0x10001176` | `0x184` | `0x1000c8e1` | **Demographics advisor** |
| 4 | `0x828d04fb` | `0x100011b4` | `0x198` | `0x1000f0db` | **Environment advisor** |
| 5 | `0xc28d0a3a` | `0x100011f2` | `0x16c` | `0x10011be0` | **Public Safety advisor** |
| 6 | `0xa28d0fc9` | `0x10001230` | `0x180` | `0x10015365` | **Transportation advisor** |
| 7 | `0x422e28e8` | `0x1000126e` | `0x1f0` | `0x10017ba8` | **Utilities advisor** |
| 8 | `0x02619041` | `0x100012ac` | `0x150` | `0x1001e4aa` | **Petitioner Manager** |

**How the domain binding is established** `[CONFIRMED]`: the ctor addresses are strictly increasing, and each class's code region `[ctor, next-ctor)` contains **exactly one** INI-loader that reads that advisor's `\Sys\Advisor-<Domain>.INI`:

| class region | INI-loader | INI string |
|---|---|---|
| `[0x10003c1f, 0x10006656)` | `FUN_10004652` | `\Sys\Advisor-Budget.INI` `[@ 0x10037320]` |
| `[0x10006656, 0x1000c8e1)` | `FUN_10007989` | `\Sys\Advisor-CityPlanner.INI` `[@ 0x1003763c]` |
| `[0x1000c8e1, 0x1000f0db)` | `FUN_1000d44f` | `\Sys\Advisor-Demographics.INI` `[@ 0x100378d0]` |
| `[0x1000f0db, 0x10011be0)` | `FUN_1000fc90` | `\Sys\Advisor-Environment.INI` `[@ 0x100379ac]` |
| `[0x10011be0, 0x10015365)` | `FUN_100129ff` | `\Sys\Advisor-PublicSafety.INI` `[@ 0x10037ac0]` |
| `[0x10015365, 0x10017ba8)` | `FUN_10015f9c` | `\Sys\Advisor-Transportation.INI` `[@ 0x10037ce4]` |
| `[0x10017ba8, 0x1001e4aa)` | `FUN_10018a51` | `\Sys\Advisor-Utilities.INI` `[@ 0x10037e94]` |
| class 8 | `FUN_1001ecad` | `\Sys\PetitionerManager.INI` `[@ 0x100383a0]` |

There are **no C++ class-name strings** in the module (only INI paths), so the human-readable names (e.g. `cSC3BudgetAdvisor`) are `[UNCERTAIN]` — see OPEN.

## 3. Key subsystems

### 3.1 The advisor tuning-loader template (7 near-identical functions)

Every `\Sys\Advisor-*.INI` loader follows one mechanical shape (`FUN_10004652` Budget `[CONFIRMED @ 0x10004652]`, `FUN_1000fc90` Environment `[CONFIRMED @ 0x1000fc90]` read in full):

1. `FUN_10029434(parser)` — init an INI-parser object (a 49-dword stack struct).
2. `FUN_10029e7e()` → resource-manager, vtable+0x50 builds a path GZString; `FUN_10025a3f(parser, path)` attaches the `Advisor-*.INI` file, then again for `\Sys\SYS.PAK` via `FUN_10029516` (PAK overlays/overrides the loose INI).
3. Repeated key reads: `FUN_1000300d(buf,"KEY")` builds a key GZString, `FUN_10029531(parser,&section,&key,&out)` returns a success `char` and points `out` at the value string; the value is converted (`atoi`/`atol`/`atof`/`FUN_100285a3` = string→32-bit id) and stored at a fixed instance offset.
4. List-valued keys use `FUN_10029828(parser,&key,callback,this)` to iterate rows into a callback.

Confirmed Budget stores (offsets are byte offsets on the instance) `[CONFIRMED @ 0x10004652]`:
`TaxGrowthThreshold`→`float @+0x120` (× `_DAT_10030360`), `TaxDeclineThreshold`→`float @+0x124`, `TREASURY_LOW`/`TREASURY_NUMBERS`→`int64 @+0x110`, `LOSE_GAME_LEVEL`→`int64 @+0x118`, `MONTHS_TILL_BUSINESS_DEAL`→`byte @+0x100`, `BUSINESS_DEALS2` list → callback `LAB_10004ad4`.

Confirmed Environment stores `[CONFIRMED @ 0x1000fc90]`, all from section `POLLUTION_RATE_CUTOFFS`, `byte & 0xff`:
`WATER_POLLUTION_HIGH @+0xa8`, `WATER_POLLUTION_MEDIUM @+0xac`, `AIR_POLLUTION_HIGH @+0xb0`, `AIR_POLLUTION_MEDIUM @+0xb4`, `OVERALL_POLLUTION_HIGH @+0xb8`, `OVERALL_POLLUTION_MEDIUM @+0xbc`, `GARBAGE_BUILDINGS` list → callback `LAB_10010186`.

Confirmed City Planner reads (from section `ADVICE_TRIGGERS`) `[CONFIRMED @ 0x10007989]`:
`SMALL_SIZE_CITY`→`@+0xc0` (via `FUN_100285a3`), `MEDIUM_SIZE_CITY`→`@+0xc4`, then `NON_DEV_SENSITIVITY` and further keys (`PARK_RATIO`, `HI_TECH_JOB_RATIO`, reward-building population minimums, …) enumerated in `strings.csv` lines 104–163.

### 3.2 Advisor connect/init methods

Each advisor has a "connect to simulator" method reached at load, read in part for Demographics (`FUN_1000ce3b` `[CONFIRMED @ 0x1000ce3b]`) and Transportation (`FUN_1001588a` `[CONFIRMED @ 0x1001588a]`). Mechanically they:

- stash the sim pointer at `this+0x134`, walk its vtable (`+0x1b8` iterate, `+0x14c` get-layer) to bind sim layers, storing results at `this+0x158`, `this+0x168`, etc.;
- `operator_new(0x10)` two small notification-adapter objects (`FUN_1000f065`, `FUN_1000f02a`) stored at `this+0xf4`/`this+0xf8`, registered with a manager (`FUN_10029f48()`→vtable+0x1c, then +0x14) `[CONFIRMED @ 0x1000ce3b:130–160]`;
- call the domain INI-loader (`FUN_1000ce3b` calls `FUN_1000d44f` `[CONFIRMED @ 0x1000ce3b:129]`; `FUN_1001588a` calls `FUN_10015f9c` `[CONFIRMED @ 0x1001588a:150]`);
- register two message listeners on the message service (`FUN_10029e7e()`→vtable+0x2c): `(vtable+0xc)(0x83110c8b, &DAT_10038878)` then subscribe `(vtable+0x14)(this, 0x83110c8b)`, and `(vtable+0xc)(0x831109b4, &DAT_100388f0)` then subscribe `(vtable+0x14)(this, 0x831109b4)` `[CONFIRMED @ 0x1000ce3b:164–175]`. `0x831109b4` is the "stop forcing advice" cheat channel (§3.4).

### 3.3 Petitioner Manager

- **ctor `FUN_1001e4aa`** `[CONFIRMED @ 0x1001e4aa]`: installs 3 vtables, builds a self-linked circular list node via `FUN_100031c0(0xc)` at `this[0x2d]`, builds a table with `FUN_1002c51a(this+0x2f, 0xc, 0xb, &LAB_1001e636)`, and seeds ~24 message-string resource ids into `this[0x14..0x23]` (values `0x785`, `0x78b`, `0x78f`, `0x79d`, `0x7a0`, `0x7a1`, `0x7aa`, `0x7af`, `0x7b3`, `0x7b4`, `0x7be`, `0x7bb`, `0x7c0`, `0x7c4`, `0x799`, …) plus defaults `this[0x24]=this[0x25]=10000`, `this[0x11]=5000`, `byte this[0x26]=0x0a`, `this[0x12]=0x3c`.
- **config loader `FUN_1001ecad(this)`** `[CONFIRMED @ 0x1001ecad]`: reads `\Sys\PetitionerManager.INI` (+ SYS.PAK) and populates the **ordinance-enablement year table** from section `PETITIONER_ORDINANCE_TRIGGER_MAPPINGS`. Confirmed stores (byte offsets on `this`): `POPULATION_FOR_GAMBLING @+0x44`, `MAX_GAMBLING_AURA @+0x98` (byte), `PRO_READING_AURA @+0x99` (byte), `PRO_READING_POP @+0x94`, `LE_LEVEL_FOR_CLINIC @+0x48`, then the ordinance year fields: `PARKING_FINES_YEAR @+0x5c`, `POWER_CONSERVATION_YEAR @+0x4c`, `SHUTTLE_SERVICE_YEAR @+0x50`, `NUCLEAR_FREE_YEAR @+0x58`, `ELECTRONICS_JOB_FAIR_YEAR @+0x54`, `WATER_METERS_YEAR @+0x60`, `TIRE_RECYCLING_YEAR @+0x64`, `TOURIST_PROMOTION_YEAR @+0x68`, `CONSERVATION_CORPS_YEAR @+0x6c`, `PAPERWORK_REDUCTION_YEAR @+0x70`, `PUBLIC_ACCESS_TV_YEAR @+0x74`, `BACKYARD_COMPOST_YEAR @+0x78`, `IND_WASTE_DISPOSAL_YEAR @+0x7c`, `AEROSPACE_TAX_YEAR @+0x80`, `CLEAN_INDUSTRY_ASSOC_YEAR @+0x88`, `BIOTECH_TAX_INCENTIVE_YEAR @+0x84`, `STAIRWELL_LIGHTING_YEAR @+0x8c`, `HOMELESS_SHELTER_POPULATION @+0x90`.
- It then loads **11 petitioner UI string keys** via `FUN_10029828(parser,&key,FUN_1001fda8,this)`, iterating index `this[0x14c]=0..10` over: `PETITIONER_STRINGS_ADVICE, _BUTTON1, _BUTTON2, _HEADING, _MESSAGE, _NAME, _REACTION1, _REACTION2, _TICKER, _TICKER_X, _TICKER_Y` `[CONFIRMED @ 0x1001ecad:534–616]`, plus `PetitionerExtraInfo Filenames` via callback `LAB_1001fdd8`.
- **string dispatch `FUN_1001fda8(_,pair,this)`** `[CONFIRMED @ 0x1001fda8]`: converts the value (`FUN_100285a3`) and writes it into the array at `this + 0xbc + this[0x14c]*0xc` — i.e. an **11-entry, 12-byte-stride table at `this+0xbc`** keyed by the string-type index.

### 3.4 Advice-forcing cheat registration (9 static registrars)

Nine 16-byte functions at `0x1001cc1e`–`0x1001cd9e` (stride `0x30`) each call `FUN_10003b1d(&DAT_1003xxxx, "<cheat text>")` to seed a global GZString cheat handle `[CONFIRMED]`:

| func | global | cheat string |
|---|---|---|
| `FUN_1001cc1e` | `DAT_100388f0` | `"stop forcing advice"` `[@ 0x10037eb8]` |
| `FUN_1001cc4e` | `DAT_100388d8` | `"force Mortimer to say"` `[@ 0x10037ecc]` |
| `FUN_1001cd9e` | `DAT_10038830` | `"force petitioners to say"` `[@ 0x10037f64]` |
| (6 more, same pattern) | `DAT_10038…` | Moe / Constance / Maria / Randall / Gus / Karen |

`0x831109b4` is the message id these handles are registered under (advisors subscribe in §3.2). The seven names map to the seven advisor domains (Mortimer=finance, etc.), but the exact name→GZCLSID binding is `[UNCERTAIN]` from this module alone.

## 4. Data / tunables

- **INI files consumed** (`\Sys\` relative): `Advisor-Budget.INI`, `Advisor-CityPlanner.INI`, `Advisor-Demographics.INI`, `Advisor-Environment.INI`, `Advisor-PublicSafety.INI`, `Advisor-Transportation.INI`, `Advisor-Utilities.INI`, `PetitionerManager.INI`, `AdvisorMoods.INI` / `GoldAdvisorMoods.INI`, `Advisor-TopicGfxIDs.INI` / `GoldAdvisor-TopicGfxIds.ini`; all overlaid by `\Sys\SYS.PAK` `[CONFIRMED @ strings.csv 78–228]`.
- **Text-substitution tokens** `[CONFIRMED @ 0x100385c8–0x10038624]`: `%TOKEN% %MAYOR% %YOURNAME% %CITYNAME% %YOURCITY% %POPULATION% %YEAR% %PARADENAME% %ANYNEIGHBOR% %NEIGHBOR% %YEAROFDEAL%`.
- **Business-deal / secret-ordinance cheat phrases** `[CONFIRMED @ 0x10037f80–0x10037ff8]`: `"garbage in, garbage out"`, `"power to the masses"`, `"water in the desert"`, `"pay tribute to your king"`, `"zyxwvu"`, `"call cousin Vinnie"`, `"let's make a deal"`.
- **INI writeback formats** `[CONFIRMED @ 0x100383f4–0x1003840c]`: `"\n[%s]\n"`, `"%s = %s\n"`, `"[%s]\n"` (the module can serialize sections back out).
- **Resource-group ids** seen as args to `FUN_1002a207(buf, index, group)`: `0xc29a6083` and `0x29541f4` (Budget ctor) `[CONFIRMED @ 0x10003c1f:61,79,97,115]`; the "0x%08X" format `[@ 0x100370e0]` indicates hex id parsing elsewhere.
- **Budget ctor constants** `[CONFIRMED @ 0x10003c1f]`: `this[0x46]=100000`, `this[0x44]=5000`, `this[0x24]=299`, `byte this[0x40]=0x24`, `this[0x48]=0x3d4ccccd` (float), `this[0x49]=0xbdcccccd` (float).

## 5. Cross-module edges

All outward calls go through GZCOM service objects obtained locally (`FUN_10029e7e`, `FUN_10029f48`, `FUN_10027b11`, `FUN_10027b3d`) and invoked by vtable offset; the targets are other modules/services identified only by id `[CONFIRMED, raw]`:

- **Message/notification service** (`FUN_10029e7e`→vtable+0x2c): register-listener at vtable `+0xc`, subscribe at `+0x14`. Message ids: **`0x83110c8b`** (with `&DAT_10038878`), **`0x831109b4`** (advice-forcing cheat channel, with `&DAT_100388f0`), **`0xa2d1c5b9`** (subscribe target via `FUN_10027b11`) `[CONFIRMED @ 0x1000ce3b:163–175]`.
- **Resource/file service** (`FUN_10029e7e`→vtable+0x50): builds `\Sys\...` paths and opens `SYS.PAK` — the shared GZ resource system.
- **Simulator / layer access**: connect methods hold the sim at `this+0x134` and pull layers via its vtable (`+0x1b8`, `+0x14c`) `[CONFIRMED @ 0x1001588a:36–58]`. The specific layer GZCLSIDs are read at runtime; not resolvable in this module.
- **Query/cast** `FUN_1000c7be(obj, 0x42922a6c, &PTR_LAB_100301a8)` in Demographics connect `[CONFIRMED @ 0x1000ce3b:111]` — casts a sim object to interface id `0x42922a6c`.
- Imports (`strings.csv`): standard `KERNEL32`, `MSVCRT/MSVCP60/MSVCIRT`, `WINMM` (`timeGetTime`), `Ole32` (`CoCreateInstance`/`CoInitialize`) — no game-DLL static imports; everything cross-module is via GZCOM.

## 6. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10024817,advisor-director,C2,sc3_advisor_GZDllGetGZCOMDirector,"PE export; guarded ctor of &DAT_10038690, onexit LAB_1000130f [0x10024817]"
0x1000102b,advisor-director,C2,sc3_advisor_director_ctor,"base ctor FUN_1002481c + 8x register_class FUN_10024b9d(GZCLSID,factory,0) [0x1000102b:21-28]"
0x10024b9d,advisor-director,C1,sc3_advisor_director_register_class,"register_class helper: (director,GZCLSID,factory,0) inserting factory map per GZCOM recipe"
0x100010fa,advisor-budget,C2,sc3_advisor_factory_budget,"GZCLSID 0x828d0c49; operator_new(0x170)+FUN_10003c1f; returns obj+4"
0x10001138,advisor-cityplanner,C2,sc3_advisor_factory_cityplanner,"GZCLSID 0xe28d0b76; operator_new(0x318)+FUN_10006656; returns obj+4"
0x10001176,advisor-demographics,C2,sc3_advisor_factory_demographics,"GZCLSID 0x028d0f43; operator_new(0x184)+FUN_1000c8e1; returns obj+4"
0x100011b4,advisor-environment,C2,sc3_advisor_factory_environment,"GZCLSID 0x828d04fb; operator_new(0x198)+FUN_1000f0db; returns obj+4"
0x100011f2,advisor-publicsafety,C2,sc3_advisor_factory_publicsafety,"GZCLSID 0xc28d0a3a; operator_new(0x16c)+FUN_10011be0; returns obj+4"
0x10001230,advisor-transportation,C2,sc3_advisor_factory_transportation,"GZCLSID 0xa28d0fc9; operator_new(0x180)+FUN_10015365; returns obj+4"
0x1000126e,advisor-utilities,C2,sc3_advisor_factory_utilities,"GZCLSID 0x422e28e8; operator_new(0x1f0)+FUN_10017ba8; returns obj+4"
0x100012ac,petitioner,C2,sc3_petitioner_factory_manager,"GZCLSID 0x02619041; operator_new(0x150)+FUN_1001e4aa; returns obj base"
0x10003c1f,advisor-budget,C2,sc3_advisor_ctor_budget,"installs vtables PTR_LAB_10030310/278/244/1fc; resource ids 0xc29a6083/0x29541f4; consts this[0x46]=100000,this[0x44]=5000,float this[0x48]=0x3d4ccccd [0x10003c1f]"
0x1001e4aa,petitioner,C2,sc3_petitioner_ctor_manager,"3 vtables; circular list FUN_100031c0(0xc)@this[0x2d]; table FUN_1002c51a(this+0x2f,0xc,0xb); ~24 msg-string ids this[0x14..0x23]; defaults this[0x24/0x25]=10000 [0x1001e4aa]"
0x10006656,advisor-cityplanner,C1,sc3_advisor_ctor_cityplanner,"class-2 ctor; owns region containing CityPlanner INI loader FUN_10007989"
0x1000c8e1,advisor-demographics,C1,sc3_advisor_ctor_demographics,"class-3 ctor; owns region containing Demographics INI loader FUN_1000d44f"
0x1000f0db,advisor-environment,C1,sc3_advisor_ctor_environment,"class-4 ctor; owns region containing Environment INI loader FUN_1000fc90"
0x10011be0,advisor-publicsafety,C1,sc3_advisor_ctor_publicsafety,"class-5 ctor; owns region containing PublicSafety INI loader FUN_100129ff"
0x10015365,advisor-transportation,C1,sc3_advisor_ctor_transportation,"class-6 ctor; owns region containing Transportation INI loader FUN_10015f9c"
0x10017ba8,advisor-utilities,C1,sc3_advisor_ctor_utilities,"class-7 ctor; owns region containing Utilities INI loader FUN_10018a51"
0x10004652,advisor-budget,C2,sc3_advisor_load_budget_ini,"loads Advisor-Budget.INI+SYS.PAK; stores TaxGrowth/Decline float@+0x120/+0x124, TREASURY_LOW i64@+0x110, LOSE_GAME_LEVEL@+0x118, MONTHS_TILL_BUSINESS_DEAL byte@+0x100 [0x10004652]"
0x10007989,advisor-cityplanner,C2,sc3_advisor_load_cityplanner_ini,"loads Advisor-CityPlanner.INI+SYS.PAK; SMALL/MEDIUM_SIZE_CITY@+0xc0/+0xc4 from ADVICE_TRIGGERS; reads NON_DEV_SENSITIVITY etc [0x10007989]"
0x1000fc90,advisor-environment,C2,sc3_advisor_load_environment_ini,"loads Advisor-Environment.INI+SYS.PAK; POLLUTION_RATE_CUTOFFS -> bytes @+0xa8..+0xbc; GARBAGE_BUILDINGS list cb LAB_10010186 [0x1000fc90]"
0x1000d44f,advisor-demographics,C1,sc3_advisor_load_demographics_ini,"reads Advisor-Demographics.INI [strlen @0x1000d44f:47]; called by connect FUN_1000ce3b"
0x100129ff,advisor-publicsafety,C1,sc3_advisor_load_publicsafety_ini,"reads Advisor-PublicSafety.INI [FUN_100129ff:47]; called by connect FUN_1001215d"
0x10015f9c,advisor-transportation,C1,sc3_advisor_load_transportation_ini,"reads Advisor-Transportation.INI [0x10015f9c:48]; called by connect FUN_1001588a"
0x10018a51,advisor-utilities,C1,sc3_advisor_load_utilities_ini,"reads Advisor-Utilities.INI [0x10018a51:46]; called by connect FUN_1001816b"
0x1001ecad,petitioner,C2,sc3_petitioner_load_manager_ini,"loads PetitionerManager.INI; PETITIONER_ORDINANCE_TRIGGER_MAPPINGS year fields @+0x44..+0x90; 11 string keys@this+0xbc via FUN_1001fda8 [0x1001ecad]"
0x1001fda8,petitioner,C2,sc3_petitioner_store_string_key,"stores FUN_100285a3(value) into this+0xbc+this[0x14c]*0xc (11-entry,12-byte-stride table) [0x1001fda8]"
0x1000ce3b,advisor-demographics,C2,sc3_advisor_connect_demographics,"binds sim@this+0x134; new adapters@this+0xf4/0xf8; calls loader FUN_1000d44f; registers msg 0x83110c8b & 0x831109b4; cast 0x42922a6c [0x1000ce3b]"
0x1001588a,advisor-transportation,C2,sc3_advisor_connect_transportation,"binds sim@this+0x134 via vtable+0x1b8/+0x14c; calls loader FUN_10015f9c; registers 0x831109b4/&DAT_100388f0 [0x1001588a]"
0x1001215d,advisor-publicsafety,C1,sc3_advisor_connect_publicsafety,"calls loader FUN_100129ff [0x1001215d:157]; registers cheat 0x831109b4/&DAT_100388f0 [:211]"
0x1001816b,advisor-utilities,C1,sc3_advisor_connect_utilities,"calls loader FUN_10018a51 [0x1001816b:85]; registers cheat 0x831109b4/&DAT_100388f0 [:136]"
0x1001e6af,petitioner,C1,sc3_petitioner_connect_manager,"registers cheat 0x831109b4/&DAT_100388f0 [0x1001e6af:73]"
0x1001cc1e,advisor-cheat,C2,sc3_advisor_register_cheat_stopforcing,"FUN_10003b1d(&DAT_100388f0,'stop forcing advice') [0x1001cc1e]"
0x1001cc4e,advisor-cheat,C2,sc3_advisor_register_cheat_mortimer,"FUN_10003b1d(&DAT_100388d8,'force Mortimer to say') [0x1001cc4e]"
0x1001cd9e,petitioner-cheat,C2,sc3_petitioner_register_cheat_forcesay,"FUN_10003b1d(&DAT_10038830,'force petitioners to say') [0x1001cd9e]"
```

## 7. OPEN

- **Human-readable class names.** No C++ class-name strings exist in `SIMADV.DLL` (only INI paths). The names `cSC3BudgetAdvisor`/`goAdvisor*` are not confirmable here. *Missing evidence:* grep `re/ghidra_export_ios/functions` for `goAdvisor`/`Petition` to get `[iOS-HINT]` names, then confirm the GZCLSID↔name binding against `SYS.PAK`/`CitySim.ini` ASCII ids.
- **Cheat-name → advisor-domain binding.** The 9 cheat handles seed 9 distinct `DAT_10038xxx` globals, but which `DAT_` global each advisor's connect method subscribes to (i.e. Mortimer=which GZCLSID) is not shown; all connect methods I read register `DAT_100388f0` ("stop forcing advice"). *Missing evidence:* the remaining 6 cheat registrars (`0x1001cc7e`–`0x1001cd6e`) and the per-advisor subscribe arg — read those bodies.
- **Meaning of message ids `0x83110c8b`, `0x831109b4`, `0xa2d1c5b9`, `0x42922a6c`, `0x83110xxx` and resource groups `0xc29a6083`/`0x29541f4`.** Reported raw; the owning service/module is not in `SIMADV`. *Missing evidence:* cross-module id scan across the other `Apps\*.DLL` GZCOM directors.
- **6 advisor ctors not read line-by-line** (`0x10006656`, `0x1000c8e1`, `0x1000f0db`, `0x10011be0`, `0x10015365`, `0x10017ba8`): default field values and vtable layouts unknown (domain confirmed by region containment only). *Missing evidence:* read each ctor body.
- **`AdvisorMoods.INI` / `Advisor-TopicGfxIDs.INI` loaders** (Gold/BAT-edition mood + topic-graphic tables) are referenced by string but their loader functions were not located. *Missing evidence:* xref `0x100370d0`/`0x10037130` and the `AdvisorMoods` string consumers.
- **Advice-emission / trigger-evaluation path.** The loaders populate thresholds; the per-tick code that compares live sim values to those thresholds and posts advice/petitioner messages was not traced. *Missing evidence:* read the message-handler methods on each advisor vtable (the `DoMessage`-style entry the subscribe calls point at).
