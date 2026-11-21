# CIVIC_REWARD: how civic buildings and rewards reach the map, and what a new one needs (civrew, 2026-11-19)

Round 2026-11-19i, stream civrew. Research only. Static reading of SC3U.exe (`re/ghidra_export/`, CodeView names),
SIMGEOM, SIMUI, SIMSPR, SIMADV, SIMSERV and SIMINIT exports, PE disassembly of the stock DLLs (SIMGEOM sha256
`17a76e83...`, SIMADV `c1183ae8...`, identical in `Apps\` and `stage\release\Apps\`), the SYS.PAK inis
(`re/data/syspak/`) and `Apps\Res\Occupant\OccupantAttribs.IXF`. No game was run. Every claim carries an address, a
file check or `[UNCERTAIN]`. Follows `PLOPPABLES.md` (landmarks as data).

> **Built and measured (civmod, round 2026-11-19j): section 5.** Two claims below were wrong when run in game and are
> corrected there: the civic window `0x1000b19d` sees only 1 of the 17 cases (the hook is on the call at `0x1000b1a3`),
> and a reward of a type that is not in `CitySim.ini [AgentTypes]` faults the City Planner on placement and on load
> (`SIMADV 0x1000b392`), so the new types are declared at run time.

**Verdict.**

- **Civic.** Each civic button is one GZCOM command class id. A per-click lookup asks every registered command factory,
  and SIMGEOM's factory turns 17 of those ids into the plain building tool for ONE hard-coded exemplar key. The sim
  recognises a civic building by its type id (prop 0x65), not by its key. So a copy of the stock exemplar with its own
  key, own art and the same type IS a working police station, school and so on, and the stock tool places any key.
  What is missing is only the way to pick the copy: no menu, list or picker reads anything but the hard-coded key.
  Smallest change: one 5-byte detour in SIMGEOM at the shared tool-constructor call, which swaps the key for a
  registered variant. No menu edit, no SYS.PAK edit.
- **Rewards.** The list is `Advisor-CityPlanner.ini [REWARD_BUILDINGS]`, read by the City Planner advisor, keyed by
  type id. A row unlocks only through code: 7 type ids are unlocked directly when population and year are met, 12 more
  through a hard-coded petition-id table, and 11 have a hard-coded extra condition. A new type id passes the population
  and year test and then unlocks nothing. Smallest change: a 6-byte detour at SIMADV `0x1000a7fa` that adds our type
  ids to the direct-unlock set, plus the row itself (our own ini read by the game's own parser, or a SYS.PAK edit).

## 1. Civic: from the button to the building

| step | code / data | what it does |
|---|---|---|
| menu entry | `MenuItem.INI [SC3MenuItemInfo]`, e.g. `0x10006201=...,COMM,0x42ff052f,0,0,0,END ; Police Station` | kind COMM, a class id and 3 numeric args |
| click | SIMUI `FUN_10016329` (menu item vtable `0x100a317c` slot +0xc) | kind byte +0x45 == 1: `cRZSysServPtr<cIGZGameCommandFactory, 0x20685aa3, 0xa4b5e41f>`, then `GetCommand(item+0x48 class id, riid 0x6856f7, &cmd)` (vt+0xc), 3 x `cRZVariant(item+0x4c/+0x50/+0x54)` pushed with cmd vt+0xc, `cmd vt+0x2c` (Execute), Release. **A new command object per click** `[CONFIRMED @ SIMUI 0x10016329]` |
| hotkeys | SIMSPR `sc3spr_view_dispatch_command` `0x10049a80` (`cISC3WinCityView::DefOnHotKey`, CV) | the same call with the same class ids (hotkey 0x18 -> `0x42ff052f` police, 0x19 fire, 0x1a hospital, 0x1b school, 0x37 jail, 0x38 college, 0x39 / 0x3a small / big park), through `this+0x230` vt+0xc `[CONFIRMED @ 0x10049a80]` |
| the service | SC3U `cRZGameCommandFactory::GetCommand` `0x0047477b` | asks each registered factory's vt+0xc in vector order, first true wins. `AddCommandFactory` `0x004747bd` appends. Factories come from registry category `kGZCATNAME_GameCommandFactory` (`cSC3App::RegisterCommandFactoryCallback` `0x0040ca40`, `CreateCommandFactoryCallback` `0x0040c75f`: GZCOM create by class id, then AddCommandFactory) `[CONFIRMED, CV names]` |
| SIMGEOM factory | `sc3_geom_dispatch_command_handler` `0x1000a896`, vtable `0x10029200` slot +0xc | switch on the class id, builds the key `{0x207edc0e, 0x57e, instance}` and the tool, then QI with the caller's riid. Unknown id: `*out = 0`, false `[CONFIRMED @ 0x1000a896; vtable read from the PE]` |
| plain tool | `FUN_10009443(new 0x120, &key, 0, 0)` | all 17 plain civic ids meet at ONE call, `0x1000b1a3`, key at `[ebp-0x3c]` (`0x1000b19d push edi / 0x1000b19e push edi / 0x1000b19f lea eax,[ebp-0x3c] / 0x1000b1a2 push eax / 0x1000b1a3 call`) `[CONFIRMED, disassembly]` |
| other tools | `FUN_10009f1c` (`0x1000a9b2`: subway station, rail-to-subway), `FUN_1000a246` (`0x1000afc0`: marina), `FUN_1000a2a9` 4-key tool (`0x1000aad5`), `FUN_1000b1ec` (`0x1000a9dd`, class `0x0339da69`), `FUN_10009267` (`0x1000b0a1`: Demolish `0xe3166801`) | not the plain path |

The command -> exemplar table, read from `0x1000a896` and checked against `OccupantAttribs.IXF` (group `0x57e`, type
`0x207edc0e`, prop 0x65 = type id, prop 0x66 = lot x, height, z). 20 of 20 keys exist and their types match
`CitySim.ini [AgentTypes]`:

| command (MenuItem.INI name) | class id | instance | type | lot | tool |
|---|---|---|---|---|---|
| Police Station | `0x42ff052f` | `0xd2` (210) | 13130 PoliceStation | 3x3 | plain |
| Jail | `0x22ff053f` | `0x1f41` (8001) | 13881 Jail | 3x3 | plain |
| Fire | `0x22ff054c` | `0xd3` (211) | 13002 FireStation | 3x3 | plain |
| Hospital | `0xe2ff0555` | `0xd1` (209) | 13310 Hospitals | 3x3 | plain |
| School | `0xc2ff0563` | `0x1f94` (8084) | 13010 K2 School | 3x3 | plain |
| College | `0xc2ff0571` | `0xd6` (214) | 13873 Local College | 3x3 | plain |
| Library | `0xc2ff057a` | `0xf5` (245) | 14130 Library | 2x2 | plain |
| Museum | `0x62ff0585` | `0xd4` (212) | 14140 Museum | 3x3 | plain |
| Small Park | `0x02ff05aa` | `0xd` (13) | 14311 Small Park | 1x1 | plain |
| Big Park | `0x82ff05b7` | `0xd5` (213) | 14312 Big Park | 3x3 | plain |
| Zoo | `0x22ff05ca` | `0xda` (218) | 14450 Zoo | 4x4 | plain |
| Baseball Field | `0x62ff05d1` | `0xd7` (215) | 14313 Baseball | 4x4 | plain |
| Playground | `0xc2ff05e0` | `0x234b` (9035) | 14314 Playground | 2x2 | plain |
| Pond | `0x22ff05ea` | `0x234c` (9036) | 14315 Pond | 2x2 | plain |
| Fountain | `0x22ff05f3` | `0x234e` (9038) | 14316 Fountain | 1x1 | plain |
| Bus Stop | `0x02ff04fe` | `0x1f96` (8086) | 12210 BusStation | 1x1 | plain |
| Train Station | `0x22ff058f` | `0xed` (237) | 12230 RailStation | 2x2 | plain |
| Marina | `0x42ff05c2` | `0xf8` (248) | 14430 Marina | 3x3 | shore `FUN_1000a246` |
| Subway Station | `0x62ff059b` | `0xe9` (233) | 12360 | 1x1 | `FUN_10009f1c` |
| Rail To Subway | `0x22ff0521` | `0x3e8a` (16010) | 12361 | 1x1 | `FUN_10009f1c` |

The 4-key tool is not a variants picker. Its three class ids (`0x23004b76`, `0x23004b73`, `0x03004b6d`, none in
`MenuItem.INI`) hold the four lot pieces of three 2x2-piece rewards: `0x1f5d..0x1f60` type 14325 Theme Park,
`0x1f8b..0x1f8e` 11002 Military Base, `0x1f98..0x1f9b` 13871 Generic University. The random value (`& 3`) only rotates
which piece goes where `[CONFIRMED @ 0x1000a896, data]`. The same instances are the special cases of the key-driven
factory `sc3_geom_create_occupant_from_key` `0x10007e64` (tracker C2), which rewards and the pickers use.

**One type, several looks already exists in stock data.** Type 14311 (Small Park) has four exemplars, `0xd`, `0x2348`,
`0x2349`, `0x234d`, but the Small Park command builds `0xd` only `[data]`. Who places the other three was not read
`[UNCERTAIN]`.

### 1.1 The sim keys on the type id, not the key

- Police layer, on a building: `IsA(13130 PoliceStation, occupant vt+0x88 type)`, else `IsA(0x3639, type)`
  `[CONFIRMED @ SIMSERV sc3_serv_layer_on_building 0x1000f006:28-31]`.
- Fire layer `sc3_fire_layer_on_building` `0x1000b13e` tests 13002 the same way `[CONFIRMED: constant 0x32ca]`.
- First-of-a-kind news, SIMGEOM `sc3_geom_building_effect_by_id` `0x10008599`: switch on the type (0x32ca fire,
  0x32d2 school, 0x334a police, 0x33fe hospital, 0x362f university) and `this vt+0x60(type)` == 1 (the building count
  by type) `[CONFIRMED @ 0x10008599:62-100]`.
- Price: `SC3BudgetLayer.ini [BuildingPlacementCosts]` by type id (`13130=500 PoliceStation`, `13010=500 School`),
  charged through `budget vt+0x54(type id)` in the site check (`RELOCATE.md` 1).

So an exemplar with the stock police station's props and type 13130 under a new key draws its own art and is
counted, covered and priced as a police station. This was not run in game `[static only]`. bldimport's landmarks use
the same plugin route and were placed and saved in game (`verify/plop/RESULTS.md` 3).

### 1.2 Placing any key is already possible

The building layer (city vt+0x138, SIMGEOM vtable `0x100292c0`) builds the stock tool for any key: +0x70
`0x10007e64(key, oneShot, free, riid, out)`, +0x54 `DoPlaceBuildingTool(cGZResourceKey&, bool, bool)` `0x10007d5b`,
+0x50 `DoPlaceBuildingTool(cISC3OccupantAttrib*, bool, bool)` `0x10007d99` (tracker C3). sc3resize already calls +0x70 for
the picker (any plopped building, its own key) and for RELOCATE. Plugin exemplars are in the attrib cache: SIMINIT
`FUN_1000ccb2` registers the cache for registry category `sc3occattrib` (`0x1002fb40`), `FUN_1000c5b6` parses each
entry's name as `0x%x,0x%x,0x%x` and adds the key (`FUN_1000c428`). The plugin `.pin [OccupantKeys]` lines go to that
category (`PLOPPABLES.md` 1) `[CONFIRMED @ SIMINIT 0x1000ccb2, 0x1000c5b6]`.

### 1.3 A hidden "all buildings" catalog (stock, cheats only)

SIMUI `FUN_10011919` opens the catalog dialog (class `0xe3091435`, iid `0xa308d9ad`) for a mode. It keeps a 2-bit
history per call (power plants 1, rewards 2, garbage 3, landmarks 0). When cheat codes are enabled
(`cIGZCheatCodeManager::GetCheatCodesEnabled`, App vt+0x2c then vt+0x40, CV) and Landmarks is opened right after Power
Plants, Rewards, Garbage in that order (`history & 0x3f == 0x1b`), the mode becomes `0xa2f7d03a` and the game calls
`SetCheatHasBeenSet(0xe37fb7b8, 1)`. SIMUI `sc3_ui_catalog_build_picker` `0x10068603` then lists every attrib with
`IsA(100, type)` and attrib vt+0x30 == 1, and OK places it through building layer +0x50 with one-shot 0
`[CONFIRMED @ SIMUI 0x10011919, 0x10068603:95-131]`. Not tried in game. Not a proposal: it lists every building and
marks the city as cheated. It does show that the stock dialog can list and place any building.

### 1.4 What a new civic building needs

| piece | needed? | why |
|---|---|---|
| exemplar copy, own key, same type, own art and name | yes | data, the plugin route (`Apps\PlugIn\bldimport\`), as landmarks |
| `[OccupantKeys]` line | yes | puts the key in the attrib cache (1.2) |
| new MenuItem.INI entry + command id | no, for a variant of an existing button | a new button would need a SYS.PAK `MenuItem.INI` edit (3 sections: ItemInfo, BtnDefs, MenuDescs count), a button icon in the menu sprite groups (`0x225872FE` / `0x041F2625`) and a factory for the new class id |
| code | yes, small | nothing in stock picks a key other than the hard-coded one |

A new class id does not need a SIMGEOM patch: a mod can call `AddCommandFactory` with its own factory, which is asked
after the stock ones (SC3U `0x004747bd`, vector push_back), and return the tool from building layer +0x70. That is the
route for a separate button, if the owner ever wants one.

## 2. Rewards: the list, the unlock, the placement

### 2.1 The list

`Advisor-CityPlanner.ini` is read by SIMADV `sc3_advisor_load_cityplanner_ini` `0x10007989`, called from the City
Planner layer Init `0x10006c7f:108` (advisor class 2, ctor `0x10006656`, `SIMADV.md`). The file is `\Sys\Advisor-CityPlanner.INI`
with compressed path `\Sys\SYS.PAK` (`0x10007989:47-57`). SYS.PAK wins over a loose ini (`NETPACK.md`,
`cSC3CompressibleINIFile::InitFileType`, SC3U `0x004872e8`, SIMADV copy `0x10029ba7`).

`EnumEntries([REWARD_BUILDINGS], 0x100089bf, advisor)` and `EnumEntries([BUSINESS_DEAL_BUILDINGS], 0x100089d3,
advisor)` (`0x10007989:828-838`). The two callbacks are 20-byte stubs that call `FUN_100089e7(isDeal, key, value)` with
`ecx = advisor`: `push 0` for rewards, `push 1` for deals `[CONFIRMED, disassembly 0x100089bf..0x100089e6]`.

`FUN_100089e7`, per line `type=Name ;a;b;c;d`:

| column | stored in the item (vtable `0x10030614`, ctor `FUN_1000b6f0`, 0x60 bytes) | getter |
|---|---|---|
| key | the type id; map key in `advisor+0xb0` (`map<ulong,...>::operator[]`, so a repeated type replaces the earlier row) | |
| Name | not stored as text: the displayed name is the exemplar's (attrib vt+0x14 key, then its text) | |
| a | +0x40, compared with the population | vt+0x34 |
| b | +0x44, compared with the year | vt+0x38 |
| c | +0x48, the petition id | vt+0x3c |
| d | +0x4e, `d != 0`: use the type's own rule (2.2) | vt+0x48 |
| (section) | +0x4f, 1 for `[BUSINESS_DEAL_BUILDINGS]` | vt+0x4c |
| | +0x4c unlocked, +0x4d placed (both 0 at load) | vt+0x40, vt+0x44 |
| | +0x54 the exemplar key | vt+0x28 |

Item field offsets read from the vtable in the PE (`+0x34 lea eax,[ecx+0x40]` ... `+0x4c lea eax,[ecx+0x4f]`)
`[CONFIRMED]`. The exemplar comes from `cISC3App::GetAppOccupantAttribCache` (App vt+0x44, CV) vt+0x1c(type), SIMINIT
`FUN_1000cc22`: a linear search of the cache array (0x1c-byte entries, type at +0xc), **first entry with that type**
`[CONFIRMED @ SIMINIT 0x1000cc22]`. A row whose type has no exemplar is dropped (`if (cVar1 != 0)` around the item).
Consequence: a new reward needs its own type id. Under a stock reward type the lookup returns the stock exemplar.
The price text in the description: `advisor+0x2b8 vt+0x54(type)`, string 0x60 of group `0x29541f4`.

### 2.2 The unlock (`FUN_1000a324`, the City Planner tick `FUN_10009453:18`)

For every item not placed (+0x4d != 1) and not a deal (+0x4f == 0):

1. `d == 0`: unlocked when `a <= advisor+0x1f8` and `b <= advisor+0x204`.
2. `d == 1`: a switch on the type id. Each case also needs `a` and `b` as above (Lighthouse and National Park compare
   `a` with `advisor+0x1bc` instead), plus:

| type | reward | extra condition | ini threshold (store in `0x10007989`) |
|---|---|---|---|
| 13874 `0x3632` | Research and Development | `advisor+0x1fc > +0xd5` | `EQ_NEEDED_FOR_SCIENCE_CENTER` -> +0xd5 |
| 1002 `0x3ea` | Stock Exchange | int64 `+0x1f0 > +0xe0` | `FUNDS_NEEDED_FOR_STOCK_EXCHANGE` -> +0xe0/+0xe4 |
| 11001 `0x2af9` | Defense Contractor | the 11002 Military Base item is placed | |
| 12350 `0x303e` | Spaceport | `+0x21c > +0xd0` | `AIRPORT_NEEDED_FOR_SPACEPORT` -> +0xd0 |
| 13871 `0x362f` | Generic University | `+0x1fc > +0xd6` and byte `+0x1ac != 0` | `EQ_NEEDED_FOR_UNIVERSITY` -> +0xd6 |
| 13872 `0x3630` | Medical Research Institute | `+0x1fd > +0xd4` | `LE_NEEDED_FOR_MEDICAL_CENTER` -> +0xd4 |
| 14003 `0x36b3` | National Park | `+0x230 > +0xcc` | `PARKS_NEEDED_FOR_NATIONAL_PARK` -> +0xcc |
| 14325 `0x37f5` | Theme Park | `+0x21c > 5` and byte `+0x1aa != 0` | (`PORTS_AIRPORTS.md` 5.4: airports, Tourist Promotion) |
| 14550 `0x38d6` | Lighthouse | none | |
| 20001 `0x4e21` | Haunted House | city vt+0x40 == 1, prefs vt+0x7c not in {0x1e, 0x1f, 0x20, 0x22, 0x31}, month 7..9 | |
| 20002 `0x4e22` | Skating Rink | city vt+0x40 == 1, month 9..11, `+0x230 > 29` | |

The 11 rows with `d = 1` in the stock ini are exactly these 11 cases `[CONFIRMED, ini vs code]`. A type with `d = 1`
that is not a case never passes.

3. When the test passes (`LAB_1000a7fa`): the type is compared with **7 fixed ids** (1002, 10110 Mayor House, 10120
   City Hall, 13005 Judicial, 13871 Generic University, 14150 Statue Fountains, 14170 Performing Arts) by a `sub ecx`
   chain at `0x1000a7fa..0x1000a830`. For those, unlocked = 1 at `0x1000a83a`. Then, if not placed, the petition
   `c` is raised: `FUN_1001dcbd(advisor+4, c, 0)`, which returns at once for `c == 0` `[CONFIRMED @ 0x1001dcbd]`.
   When the test fails and the item is not unlocked, the pending petition `c` is withdrawn (`FUN_1001dd73` /
   `FUN_1001dd49`).
4. The other 12 rewards unlock only when their petition is answered yes: `sc3_petitionermgr_petitioner_button_pressed`
   `0x1002096a` -> `FUN_1000abb2(petition id, answer)`, answer 1, a fixed switch: 143 -> 11001, 132 -> 13874,
   136 -> 14003, 139 -> 14550, 140 -> 14370, 141 -> 14325, 142 -> 13872, 148 -> 14600, 150 -> 12350, 205 -> 11002,
   300 -> 20001, 303 -> 20002, then unlocked = 1 `[CONFIRMED @ 0x1000abb2]`. The 12 petition ids match column `c` of
   those 12 rows `[ini vs code]`.

So a new row `38500=X ;20000;0;0;0` is parsed, passes the population and year test, is not in the 7-id set, raises no
petition (c = 0) and is never unlocked. With any `c`, the answer handler has no case for it. **A new reward cannot
unlock from data alone** `[CONFIRMED @ 0x1000a7fa, 0x1000abb2]`.

The City Planner catalog list, `FUN_1000b1dd` (the 0x2dc6d7f query for mode `0x62e92553`, dispatched by
`FUN_1000b067`): an item is listed when placed == 0 and (unlocked == 1, or byte `advisor+0x30d != 0` and not a deal).
A scan of SIMADV `.text` finds only two references to `+0x30d`: the ctor's clear (`0x10006a80`) and this read
(`0x1000b264`), so in stock that second branch is dead `[CONFIRMED, disassembly scan]`. Deals appear only after
`sc3_advisor_cityplanning_add_business_deal_building_to_reward_list` `0x1000ad4d` sets unlocked.

### 2.3 Placement, "already built", saves

- OK in the catalog: SIMUI `FUN_10011919:60-68` calls building layer +0x50(attrib, one-shot 1 for the landmark and
  reward modes, else 0, free 0) `[CONFIRMED]`. So a reward is the plain tool for its exemplar (or the 4-piece tool for
  the three instances in 1), one per click.
- Placed flag: City Planner `FUN_1000b32a` (occupant inserted) looks the occupant's type up in the reward map and sets
  placed = 1, withdraws the petition, and for a deal (budget advisor `+0x2d8` vt+0x14 true) clears unlocked.
  `FUN_1000b458` (removed) sets placed = 0. Unlocked survives a demolish, so the reward is offered again
  `[CONFIRMED @ 0x1000b32a, 0x1000b458]`.
- Save: City Planner `cISC3CityLayer::Save` `0x100073b3`, record `{0x206c6e7c, 0xc28d0b6e, 0}`, one entry per item with
  unlocked or placed set: the exemplar key (3 dwords) + placed byte + unlocked byte. Load `0x100071ed` matches each
  saved key against the items and sets both bytes. A saved key with no item is skipped `[CONFIRMED @ 0x100071ed]`.
- Price: `[BuildingPlacementCosts]` by type. Mayor House, City Hall and most rewards have no row there (14003 Geyser
  Park 10000 and 14325 Theme Park 125000 have one) `[data]`. A new type id has no row, and the landmarks of type 18000
  (no row either) were placed for 0 plus clearing (`verify/plop/RESULTS.md`).

**Correction to `RELOCATE.md` 3.** It names the reward advisor as ctor `0x10017ba8` with items vtable `0x10031178`, and
says it "does not listen to occupant events". `0x10017ba8` is the Utilities advisor (`SIMADV.md` class 7). Vtable
`0x10031178` is used only by its functions `0x1001ca3d` / `0x1001ca9c`, and `0x100193dc`, `0x1001a3ec`, `0x1001a4ae`
set "available" on its power and water plant lists by year. The reward advisor is the City Planner (`0x10006656`,
items vtable `0x10030614`, map +0xb0), and it does track insert / remove (above). RELOCATE's conclusion still holds:
removing a reward clears only "placed", so a move cannot lose it.

### 2.4 What a new reward needs

| piece | needed? | why |
|---|---|---|
| exemplar copy with a NEW type id (unique), own art and name, `[OccupantKeys]` line | yes | the map is keyed by type, the lookup returns the first exemplar of a type |
| a `[REWARD_BUILDINGS]` row for that type, `d = 0`, `c = 0` | yes | the only source of reward items |
| an unlock | yes, code | 2.2: neither column unlocks a new type |
| `CitySim.ini [AgentTypes]` entry for the new type | **yes** (measured, section 5.2): the City Planner's occupant-inserted handler `0x1000b32a` reads the agent type object of the occupant (QI `0xe0faadc7`, vt+0x2c) and dereferences it; for an undeclared type it is NULL | the static reading above missed it |
| petition art / text | no | c = 0 raises none |

## 3. Proposal (not built)

### 3.1 Civic variants: same button, choose the look (smallest)

**Data (bldimport kind `civic`, `base` = one of the 17 plain commands in the table in section 1).** In the existing plugin
`Apps\PlugIn\bldimport\`: the exemplar = the stock base exemplar `{0x207edc0e, 0x57e, base instance}` with all its props
(type, coverage, budget class), only the key (`{0x207EDC0E, 0xB1D10002, id}`), the name (0x6D, 0x64), the
description (0x7C), the frame table (0x67) and the lot (0x66, square 1..4 as today) replaced, plus the `[OccupantKeys]`
line. The same writer as `landmark_table`, with the base chosen by command instead of by lot size. One more file in
the plugin folder, `bldimport_civic.ini`: `[Variants]` `0xd2=0x9480,0x9481` (base instance = variant ids in group
`0xB1D10002`, in the order the button cycles). The plugin scanner reads only `*.pin` and the sprite folder's `*.DAT`, so the extra file is
inert for the game.

**Code (a block in sc3resize, `SC3RESIZE_CIVVAR=0` off switch).**
- Detour at SIMGEOM `0x1000b19d` (5 bytes: `push edi; push edi; lea eax,[ebp-0x3c]`, all three re-issued by the
  cave). Key on the base instance at `[ebp-0x34]` (key + 8, e.g. `0x1000afdd mov [ebp-0x34], 0xd2` for police): each
  plain command has its own instance. Not on the class id: `[ebp+8]` is overwritten in the branches (`0x1000a958`,
  `0x1000a998`, ... `mov [ebp+8], ecx`). If the instance has variants, write the chosen variant id there (and the
  group `0xB1D10002` into `[ebp-0x38]`) before the stock call. Nothing else changes: the stock tool, site check,
  price and commit run.
- Choice: each press of the same button moves to the next look (stock, variant 1, ..., stock). The cost label that
  placehints already draws next to the pointer (`project-placehints`, sc3resize) gets the look's name, so the player
  sees which one is armed. A second press within the same tool is a new GetCommand call (1, per click).
- Follow-up if the owner wants a list instead of cycling: open the stock catalog dialog (`FUN_10011919`) with a mod
  mode and answer its 0x2dc6d7f query with the base + variants (the entry props `FUN_1000b0dd` writes: name
  0x2ebe76b, key 0xba64f91e / 0xfa64f93a / 0xfa64f957). The dialog's OK already places through building layer +0x50
  with one-shot 0. How the query reaches the layers (city vt+0x10 / vt+0x1d4 in SIMUI `FUN_1006950a`) was not read
  `[UNCERTAIN]`, so this is a second step.

**Why not a new button.** It needs a SYS.PAK `MenuItem.INI` edit in three sections, a button icon, a factory
(`AddCommandFactory` route, 1.4), and it changes the length of the Police / H&E / Parks flyouts. Those flyouts are
drawn from `[SC3MenuDescs]` counts with fixed art ids (`0x00496795`, `0x000018FF`), and their look with one more
entry at other UI scales was not read `[UNCERTAIN]`. The variant route touches no menu.

**Risks.**
- Saves: a placed variant is saved with its own key, like a landmark. Loaded without the plugin, its lot is empty
  orange-brown ground (measured for landmarks, `verify/plop/RESULTS.md` 3). For a civic building this also drops its
  coverage silently. Loaded without the mod DLL but with the plugin, placed variants keep working (data only) and the
  button builds the stock look.
- Other mods: placement still runs through the building layer slots sc3resize wraps (RELOCATE / PLOPOVER cave
  `0x100076b4`, commit `0x10007760`), so building over zoned lots works for variants too. The picker (Ctrl+F) picks a
  variant by its own key through layer +0x70 (`PICKER.md` 3, "any other building"), which is correct. sc3undo journals
  the Insert like any building. No mod hooks `0x1000a896` or `0x1000b19d` today (grep of `re/harness/src`).
- UI scales: no new window. The name rides the existing cost label, which is drawn at the HUD factor.
- Stats: the copy keeps the base's coverage and budget props. A different lot size than the base (for example a 2x2
  police station) keeps the base's coverage radius, which may look wrong to players. bldimport could limit the lot to
  the base's.
- Removing the import: `bldimport.py restore` removes the plugin and the variants list. Cities that hold variants then
  show empty lots (above).

### 3.2 New reward: one more row, one more unlock

**Data (bldimport kind `reward`).** Plugin exemplar like 3.1, base = a stock reward of the same lot (10110 Mayor House
is 1 lot piece), a NEW type id per reward from a block of our own (for example 38500 and up, clear of `CitySim.ini`
and of our landmark ids 38000+), name, description, `[OccupantKeys]`. The row
`38500=<name> ;<population>;<year>;0;0` (petition 0, own rule 0) goes into `Apps\PlugIn\bldimport\bldimport_rewards.ini`
under `[REWARD_BUILDINGS]`. Population and year come from the page (defaults e.g. 20000; 0).

**Code (a block in sc3simrun or sc3resize, off switch).**
- Load the row: after the stock loader (`0x10007989` returns into the layer Init at `0x10006c7f:108`), open our ini
  with the game's own `cSC3CompressibleINIFile` (SIMADV ctor `0x10029434`, `cRZIniFile::SetPath`, no compressed path)
  and call `EnumEntries` (`0x10029828`) for `[REWARD_BUILDINGS]` with the stock callback `0x100089bf` and the advisor as
  context. The stock parser then builds our items exactly like Maxis rows. Whether the class opens a loose file when
  no compressed path is set was not run `[UNCERTAIN]`. The fallback is netpack's `ini[]` edit of
  `Advisor-CityPlanner.ini` in the overlay SYS.PAK (`NETPACK.md`), which ties rewards to sc3netmod.
- Unlock: a detour at SIMADV `0x1000a7fa` (6 bytes: `mov eax,[ebp-0x10]; mov ecx,[eax+0x10]`): if `ecx` (the type) is
  one of ours, jump to `0x1000a832` (set unlocked), else continue at `0x1000a800`. This is reached only after the
  population and year test passed, so our rows follow the same rule as Mayor House.
- Moving: sc3resize's `rl_movable` (`sc3resize.c:10409`) is a hard-coded copy of the stock reward and deal type ids
  plus `18000 < t < 19000`. Add our reward type block there, so "Mover" appears and the picker refuses them ("solo uno
  por ciudad"), as for stock rewards. Side finding: bldimport's own landmarks have type 18000 itself, which that test
  leaves out, so they get no "Mover" button and the picker offers their tool `[CONFIRMED @ sc3resize.c:10411, not run]`.

**Risks.**
- Saves: the unlocked / placed bytes are saved under the exemplar key (2.3). Loaded without the mod, the record is
  skipped (no item matches), and a placed reward behaves like a removed landmark (empty lot) if the plugin is gone too.
  Loaded without the mod but with the plugin: the reward stays on the map as a building with an undeclared type, is not
  offered again, and "Mover" does not appear for it.
- Type id: an undeclared type passes every path read here (2.4) but the query dialog, the newscast and any `IsA` user
  were not read for it `[UNCERTAIN]`. Declaring it means a `CitySim.ini` SYS.PAK edit, so test the undeclared type first.
- Other mods: sc3resize RELOCATE and PICKER use the hard-coded type list (above). Deals are untouched (+0x4f == 0 only).
- UI: the reward appears in the stock Rewards catalog, which DLGSCALE already scales. No new window.
- Removing the import: delete the plugin and the rewards ini. Cities keep the record bytes, and the game ignores them.

### 3.3 Confidence

| claim | evidence | confidence |
|---|---|---|
| civic button -> class id -> SIMGEOM factory -> hard-coded key | `MenuItem.INI`, SIMUI `0x10016329`, SC3U `0x0047477b`, SIMGEOM `0x1000a896`, vtable `0x10029200` | high (static, 2 independent callers) |
| 20 command keys and their types | `OccupantAttribs.IXF` + `CitySim.ini`, 20 of 20 | high (data) |
| one shared plain-tool call at `0x1000b1a3` | disassembly | high |
| civic function follows the type id | SIMSERV `0x1000f006`, SIMGEOM `0x10008599`, budget ini | high for police / fire / news / price, not read for every service |
| a variant copy works as its base in game | static only | medium, not run |
| reward list, fields, unlock rules, petition table | SIMADV `0x100089e7`, `0x1000a324`, `0x1000abb2`, ini cross-check 11/11 and 12/12 | high |
| a new reward row never unlocks without code | `0x1000a7fa` chain + `0x1000abb2` switch | high |
| reward save / load by key, unknown keys skipped | `0x100073b3`, `0x100071ed` | high |
| loading our own ini with the game's ini class | not run | medium |
| hidden all-buildings catalog under cheats | SIMUI `0x10011919`, `0x10068603` | high (static), not run |

## 4. Open

- Who places the other three Small Park exemplars (`0x2348`, `0x2349`, `0x234d`).
- How the catalog's 0x2dc6d7f query reaches the advisors (SIMUI `FUN_1006950a`, city vt+0x10 / vt+0x1d4).
- Meaning of the advisor fields the unlock compares (`+0x1f8`, `+0x204`, `+0x1bc`, `+0x1fc`, `+0x1fd`, `+0x21c`,
  `+0x230`, `+0x1aa`, `+0x1ac`): only their ini thresholds are tied down here.
- `[OccupantKeys]` value text (`=38000 Test obelisk`): read as a key list only (`FUN_1000c5b6` parses the entry name).

## 5. Built (civmod, round 2026-11-19j)

Code: `re/harness/src/sc3resize_civic.c` (included by `sc3resize.c`), cost label line in `sc3resize_placehints.c`
`ph_label`, Mover list `rl_movable`, two rows on the "Activar mods" page. Data: `bldimport.py` kinds `civic` and `reward`.
Measurements: `verify/civmod/RESULTS.md`.

### 5.1 Civic looks (CIVVAR)

- **Correction.** Each of the 17 plain cases pushes its own args (`push edi; push edi; lea eax,[ebp-0x3c]`) and 16 of
  them `jmp 0x1000b1a2` (`push eax`); only the last falls through `0x1000b19d`. Jumps found by a scan of
  `0x1000a896..0x1000b1ec`: 16 `jmp 0x1000b1a2` plus the fall-through. The 5-byte window proposed in 3.1 is clean but sees
  one case: with it, the Police hotkey built the stock tool without passing the hook (measured). `[CONFIRMED @
  0x1000b1a3, disassembly + game]`
- **Hook.** The rel32 of `0x1000b1a3 call 0x10009443` points at `cv_call`, which runs `cv_pick(&key)` (`[esp+4]`) and
  jumps on to `0x10009443` with the stack untouched. A base listed in `bldimport_civic.ini` cycles per press: stock, then
  each variant, then stock. Installed only when the file lists a variant.
- **Label.** `ph_label` reads the city view's current tool (`+0x228`, a SIMGEOM building tool vtable), its key at
  `+0x108`, and prefixes "Aspecto i de n: <name>" whenever the key is a base with variants or one of its variants.
- **In game.** A copy of the police exemplar under `{0x207EDC0E, 0xB1D10002, 0x9470}` placed with the stock tool is
  type 13130, $500 like the stock one, drawn at zoom 3 and 4, and draws its own coverage circle on the criminality map
  when powered (section 2 of RESULTS). Unpowered, neither it nor a stock station draws one.
- **Without the plugin** a placed look comes back as the stock exemplar of the same type (`{0x207EDC0E, 0x57E, 0xd2}`),
  so it keeps working as a police station. Measured; same as growables (`verify/airsea` 4), unlike landmarks.

### 5.2 New rewards (NEWREWARD)

- **Rows.** The City Planner loader has one call site, `0x10006f80 call 0x10007989` (`ecx` = the advisor). Its rel32
  points at `rw_load_wrap`: the stock loader, then our `bldimport_rewards.ini` through SIMADV's own
  `cSC3CompressibleINIFile` with no compressed path. `InitFileType` `0x10029ba7` then takes the loose route (type 1,
  `cRZIniFile::EnumEntries` `0x100269f1`), which keeps the `;` columns in the value. Measured: `EnumEntries true`, both
  rows became items with the right population, year, petition 0, own rule 0. So the SYS.PAK fallback is not needed.
- **Unlock.** 6-byte jmp at `0x1000a7fa` to `rw_stub`: our types go to `0x1000a832`, all others to `0x1000a800`.
  Measured: unlocked at population 1000 in a city of ~150,000, the 100,000,000 row stayed locked; listed in
  Rewards and Opportunities with our name and description; gone from the list once placed, also after save + reload.
- **Correction: the type must be declared.** Placing type 38001 undeclared: the building is inserted and drawn, then
  `0x1000b32a` (City Planner occupant inserted) QIs the occupant for `0xe0faadc7`, calls vt+0x2c, gets NULL and reads
  address 0 at `0x1000b392`. The game's handler swallows the fault, the commit stops after the insert: "placed" never
  set, tool still armed (`verify/civmod/owner_shots/16`). Loading a city that holds such a building faults at the same
  address and the game exits (measured twice: rewards file removed, and the stock game with the plugin installed).
- **Declaration at run time.** The agent type tree (SIMINIT `sc3_agenttype_tree_init` `0x10002eb1`) is built from the
  GZ registry categories `sc3agenttype` / `sc3typehierarchy` (SC3U `0x004cffa0` / `0x004cffa4`). `cSC3App::LoadRegistry`
  `0x0040b761` fills them from `CitySim.ini` with `EnumEntries` at `0x0040bc80` (callback `RegisterAgentTypeCallback`
  `0x0040cb70`) and `0x0040bccb` (`RegisterAgentRelationCallback` `0x0040cc08`). Both rel32 point at our wrappers, which
  run the stock `EnumEntries` (`0x00486f55`) and then hand `bldimport_types.ini`'s rows to the same callback as exe
  `cRZString` (`0x00402a40` / `0x00402a96`). Patched from DllMain; LoadRegistry runs later. Measured: both types declared
  before the tree is built, the reward placed with no fault, saved, reloaded, moved.
- **Row format.** `[AgentTypes] 38001=bldimport38001:<the base reward type's text key>`, `[AgentTypeHierarchy]
  38001=<the base type's parent>` (Mayor's House 10110 -> 10001).
- **The loader declares (owner call 2026-11-19, round 2).** The two hooks and the row feed moved from sc3resize to
  `sc3mods.c` ("REWARD TYPES"), so they run whenever the patched exe maps the loader: all mods on, every mod off on the
  mods page, sc3resize not loaded, `SC3MODS_OFF=1`. sc3resize no longer declares; it asks the loader's new export
  `sc3mods_reward_types(out, cap)` and unlocks only the types listed there. The file moved with the rewards into
  their own plugin, `Apps\PlugIn\bldimport_rewards\bldimport_types.ini`.
- **The bare stock exe.** `sc3mods_patch.ps1 -Restore` / `.sh --restore` move `PlugIn\bldimport_rewards` to
  `Apps\sc3mods_off\PlugIn`, a patch run moves it back, so the unpatched exe never loads a reward exemplar. Measured
  before the move (round 1): the stock game with the plugin exited while loading a city holding a placed reward
  (PID 17576 gone within 10 s). After the move: the city loads, the reward lot empty orange-brown ground
  (`verify/civmod/RESULTS.md` 4).
- Rejected alternatives (round 1): a SYS.PAK `CitySim.ini` edit in the netmod overlay (ties rewards to sc3netmod), or
  the 24 building types `CitySim.ini` declares with no stock exemplar (1001 Arcology, 12260 Parking, 12510 Dam, ...),
  stock-safe but about eight rewards at most.

### 5.3 Mover

`rl_movable` now accepts `18000 <= t < 19000` (bldimport landmarks are 18000 itself) and the reward block
`38000..38999`. Measured: "Mover" in the "?" of a type 18000 landmark and of a type 38001 reward, both moved, one copy
left; the picker refuses both ("solo uno por ciudad"); a civic look is picked by its own key.


## 6. Built: the civic list window (civdlg, round 2026-11-19k)

Owner 2026-11-19: a civic button that has imported looks opens a small list window in the game's own look (the
original first, then the looks, each with name, price and picture); picking one arms the stock tool with that key;
Esc or close arms nothing; a button with no looks stays stock. Code: `cd_*` in `re/harness/src/sc3resize_civic.c`
(CIVDLG). Measurements: `verify/civdlg/RESULTS.md`.

### 6.1 Reuse the stock catalog dialog, not a new SIMUI window

The landmark / rewards / power plant / garbage lists are one GZCOM class, `0xe3091435` (iid `0xa308d9ad`, object
`0x68` bytes, ctor `0x10067397`), driven by a game command (SIMUI vtable `0x100a2b48`, Execute +0x2c -> +0x38 =
`0x10011919`) `[CONFIRMED @ SIMUI 0x10011919, disassembly]`:

| step | call | |
|---|---|---|
| pause | `cISC3City::SimHiddenPause` city vt+0x21c (Unpause +0x220 at the end) | CV names |
| create | GZCOM vt+0xc(`0xe3091435`, `0xa308d9ad`, &iface) | iface = object+0x18, vtable `0x100ab4f4` |
| mode | iface vt+0xc(mode) -> object+0x24 | stock modes `0x22e92581` landmarks, `0x62e92553` rewards, `0x62e925a2` power, `0xc2f291a9` garbage, `0xe2e92527` business deals, `0xa2f7d03a` all buildings (cheat) |
| init | iface vt+0x10 `0x1006749d`: creates the window (class `0xa2a79fd0`, `FUN_1002c647`), object+0x34 | |
| modal | `cIGZWinMgr::DoModalWin(GetMainWindow(), win)` wm vt+0x9c, wm vt+0xc | the window's create message builds the controls inside this call |
| result | iface vt+0x18 WasOK (object+0x28 OK pressed and +0x29 an entry selected), vt+0x1c GetSelected(&attrib) | |
| close | wm vt+0x28 DestroyWindow, Release window and object | |

Items: the object's own list (object vtable `0x100ab514`: +0x1c NewItem `0x1000c067`, +0x18 AddItem `0x1000c006`,
insertion order while the sort property +0x14 is 0). An item is a property holder (vtable `0x100a27c8`: +0x24
SetUint, +0x1c / +0x18 SetString, +0x30 GetUint, +0x28 GetString) with the key in `0xba64f91e` / `0xfa64f93a` /
`0xfa64f957`. The stock modes' items come from the advisors, which answer a city message {`0x2dc6d7f`, mode}
(`0x1006950a`); the cheat mode adds its own in `sc3_ui_catalog_build_picker` `0x10068603`. A mode nobody knows gets no
advisor items, so items added between SetMode and Init are exactly the list. On a selection `0x10069029` draws the
attrib's picture (object+0x38), its name (+0x4c, attrib GetName) and the item strings `0x2ebe7cb` -> +0x44 (left,
y 260), `0x22f291ae` -> +0x48 (right, y 260), `0x2ebe76b` -> +0x54 (description block), as the advisors' items use
them (SIMADV `0x1001c69c`, `0x10011590`). Esc (key `0x1b`), the close box (`0x42b7c353`), OK (`0xe2e80764`) and the
double click are the dialog's own (winproc `0x1006751b`).

Reuse wins on every point the owner named, with no SIMUI patch: the game's own look (it is the rewards window), the
picture (the dialog's own building preview: it drew the imported looks, measured), interface scale (the dialog is a
SIMUI dialog window, so DLGSCALE scales it: measured at 200%), Esc / close / OK / double click, and the remembered
window position. A new SIMUI window would need all of that rebuilt by hand, plus the building preview, which no mod
draws today.

Two traps, measured:

- **The controls do not exist before DoModalWin.** Init only creates the window object; the create message that runs
  `sc3_ui_build_catalog_picker_window` `0x10067620` arrives inside DoModalWin. A selection call before it faulted
  reading a NULL picture control (`SIMUI+0x690EF`). The builder selects an entry itself only from the saved catalog
  preferences, per stock mode. So CIVDLG selects the entry (and sets the title) from the frame heartbeat once
  object+0x3c / +0x38 / +0x64 exist.
- **The title.** The builder sets the caption from the mode (empty for an unknown one) in the same create message, so
  a caption set before DoModalWin is overwritten. Set from the heartbeat too.

### 6.2 Where the press is caught

SIMGEOM's command factory vtable is `0x100291f4`: +0xc `cRZGameCommandFactory::GetCommand` `0x10015560` asks its
sub-factories, then its own handler at +0x18, `sc3_geom_dispatch_command_handler` `0x1000a896` (the dword at
`0x1002920c`, the only reference to `0x1000a896` in the DLL). CIVDLG points that slot at `cd_getcmd`. For one of the
17 plain civic class ids (table in section 1) whose base has looks it runs the window first:

- **cancel** (Esc, close box, OK with no entry): `*out = 0`, return false. Both callers test the result: the menu
  item click SIMUI `0x10016329` and the hotkey path SIMSPR `0x10049a80` skip Execute, so no tool is armed.
- **a pick**: the stock handler runs with the pick set, and `cv_pick` on the shared constructor call `0x1000b1a3`
  (section 5.1) builds that key. The stock tool, site check, price and commit run unchanged.

The modal loop then runs inside GetCommand, one call before Execute in the same two callers: the stock lists run
theirs inside Execute, so the context is the same. Measured through the real menu button (posted clicks on the civic
flyout) and the hotkey path.

### 6.3 Not done

- **Press-to-cycle is not a mods page row.** The "Activar mods" page's two columns are full (both end where the notes
  start, MODTOGGLE in sc3resize.c), so a row means a new layout. The cycle stays only as the off-switch:
  `SC3RESIZE_CIVDLG=0` or `sc3resize.ini [buildings] civiclist=0` (measured: presses cycle as shipped).
- **The model's own description line** (bldimport writes it as exemplar prop 0x7C) is not shown: the window shows a
  fixed line per entry. The stock dialog takes that text from the advisor's records, not from the attrib.
- **Price** is `budget vt+0x54(type id)` (the site check's build price, RELOCATE.md 1), the same for the original and
  its looks (same type id). Clearing and levelling are added by the stock tool at the pointer, as always.

## 7. Built: civic looks from the game's own styles (civicstyle, round 2026-11-21)

Simtropolis 2026-11-21: "mix and match what schools/parks/hospitals/etc. appear in a city". Code: `cs_*` / `cv_looks`
in `re/harness/src/sc3resize_civic.c` (CIVSTYLE), data: netpack `style_mix` 1.2.0 (`"civic": true`,
`re/tools/netmod/netpack_stylesets.py`). Measurements: `verify/civicstyle/RESULTS.md`.

### 7.1 Which civic buildings have set art (offline, every claim a data read)

A building set holds TKB1 exemplars at the SAME keys as the base (BUILDING_PICK.md 0). Read of the two set archives
(`BuildingSets/e523f3fb/BST_0004.dat`, `6523f3d5/MBE_0015.dat`) against the 18 civic bases of section 1:

| base | European e523f3fb | Asian 6523f3d5 |
|---|---|---|
| Police 0xd2, Fire 0xd3, School 0x1f94, Museum 0xd4, Baseball 0xd7, Marina 0xf8 | yes | yes |
| Jail 0x1f41, Hospital 0xd1, College 0xd6, Library 0xf5, Small Park 0xd, Big Park 0xd5, Playground 0x234b, Pond 0x234c, Fountain 0x234e | no | yes |
| Zoo 0xda, Bus Stop 0x1f96, Train Station 0xed (and Subway 0xe9, Rail To Subway 0x3e8a) | no | no |

Every set exemplar differs from its base only in prop 0x66 middle value (height; x and z equal, so the same
footprint), 0x67 (its own frame table, groups 0x5432D60F / 0x547B7DF6), 0x6d (name key, group 0x453BBDE0, instance
already base + 400000 / + 1500000, a stock [DBSegments] string) and for some 0x6f. Type id 0x65 is the base's in all
21. The three other Small Park exemplars (0x2348, 0x2349, 0x234d) have Asian art too, but no button builds them
(section 4), so they are not offered.

### 7.2 Exemplars and art (style_mix 1.2.0)

`"civic": true` on a style set entry copies those set exemplars verbatim at base + offset with their frame tables
and pixels (the same writer as the growable copies, no family line, so nothing grows them), and checks type id and
footprint against the base. On the "00000000" entry it adds the stock exemplar of every civic base a civic entry
re-skins at base + 2600000: its 0x67 names the stock table `{0x6300, 0x6400, base}` in `CSATTRIB.IXF`, which no set
archive shadows (no 0x6300/0x6301 record of group 0x6400 in either set DAT), so it draws North American in a city
whose own set re-skins the base. Merge result in the 25-package tree: 6 + 15 + 15 civic copies. A manifest without
`"civic"` compiles byte-identically to before (1.1.0 checked).

### 7.3 The look list per press

`cv_looks(base)`: the original (base key), then the other two styles whose copy is in the attrib cache (asked once
per base, SIMUI `0x1008e985` vt+0x18), then the bldimport looks. The original's style is the city's skin (scheme
manager `[[0x4fa86c]+0x108]`, `+0x58` loaded, `+0x50` set, as sc3netmod's `sp_skin`): in a North American city
the list is North America / Europe / Asia; in a European city Europe (the base key) / North America (+2600000) /
Asia. The list window (section 6), the cycle (CIVDLG off) and the cost label all read that list. The rows are
renamed "<region>: <name>" after the dialog has built them, with `cIGZWinListBox::ModifyString` (vt+0x20, CodeView
`cv_vtables.tsv`), because the copies keep their set's name ("Comisaría" three times).

The Marina is not a plain case: its command builds `FUN_1000a246` (shore tool) at SIMGEOM `0x1000afc0` with the same
`(&key, 0, 0)` args. That call's rel32 now goes to `cv_call_m` (cv_pick, then `0x1000a246`). `0x1000a246` itself is
also called by `sc3_geom_create_occupant_from_key 0x10007e64` (picker, relocate), which is not hooked.

### 7.4 Trap: the lab's modal jobs

`civmod_lab.py hotkey` runs the city view's DefOnHotKey inside a Frida DispatchMessageA hook, and the list window's
modal loop runs inside that call. When the job returned and the Python side detached at once, the game faulted
once at a no-module address with the message loop on the stack (1 in 3 presses). A wrapper that keeps the session
attached 4 s after the job returned ran 19 presses over 5 runs with no fault (now in `civmod_lab.py`). Not a mod bug.
