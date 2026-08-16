# SCENARIO.DLL — SC3ScenarioLayer + scenario scripting VM

**Module:** `Apps\SCENARIO.DLL` (143,360 bytes) — GZCOM director module.
**Export anchor:** `re\ghidra_export_scenario\` — image_base `0x10000000`, 1210
functions (decomp ok=1210). SHA-256 `77a111cb04b817ddd3453a559e841c9e661d92fff4b282d30dcceb298b0fb801`.
All RVAs below are Ghidra virtual addresses in that export.

## 1. Purpose

SCENARIO.DLL implements the **scenario system** — the scripted, goal-driven
game mode. It is a small **bytecode/command interpreter** driven by an INI
config (`\Sys\SC3ScenarioLayer.INI`, read from `\Sys\SYS.PAK`) plus a fixed
built-in vocabulary of **~72 `cmd*` opcodes** (`cmdStartFire`, `cmdGetPopulation`,
`cmdAddGoal`, `cmdIf`, `cmdSetVariable`, `cmdOfferBusinessDeal`, …). The opcode
names are all confirmed as ASCII in `strings.csv` `[CONFIRMED @ 0x1001e200–0x1001e7f8]`.
A scenario script is a tree of command nodes; each node carries a 16-bit opcode id
and an argument array; the layer walks the tree, evaluating conditions and applying
effects (spawn a disaster, offer a deal, mark a goal met, end the scenario). It
holds a 512-slot integer **variable file** and a set of **goal/deal maps**, and it
reaches into the rest of the engine (sim queries, disaster layer, business-deal
service, UI newsticker) through the GZCOM framework pointer. Player-facing text is
templated with tokens such as `%CITYNAME%`, `%MAYOR%`, `%POPULATION%`, `%YEAR%`
`[CONFIRMED @ 0x1001e928–0x1001e984]`.

## 2. Director + registrations

**Entry chain** (`[CONFIRMED]`):

- `GZDllGetGZCOMDirector` `[0x1000f984]` — PE export. Guarded one-time init of the
  static director object `&DAT_1001e9e0` (guard bit `DAT_1001ea24 & 1`), registers
  an atexit dtor (`&LAB_100011f5`), returns `&DAT_1001e9e0`. Standard GZCOM recipe.
- Director ctor `[0x100010b1]` — sets vtables `PTR_FUN_1001a1dc` / `PTR_LAB_1001a1b0`
  and calls the class-registrar `FUN_1000fd11` **twice**. So this director registers
  **exactly 2 classes**.
- `FUN_1000fd11` `[0x1000fd11]` — register_class: inserts `{GZCLSID, factory, 0}`
  into the director's map at `this + 0x14` (via `FUN_1000ffb4`). Matches the module recipe.

**GZCLSID → factory table** `[CONFIRMED @ 0x100010b1]`:

| GZCLSID | factory RVA | alloc size | ctor | identity |
|---|---|---|---|---|
| `0x03de4ce4` | `0x10001116` | `0x9b0` (2480 B) | `0x100065dc` | **SC3ScenarioLayer** (the scenario engine object) |
| `0x03dfae27` | `0x1000114b` | `0x0c` (12 B) | `0x100011ab` | small helper/COM-facet object (3 vtables: `PTR_LAB_1001a224/…a24c/…a264`) |

- Factory `0x10001116`: `operator_new(0x9b0)` then ctor `FUN_100065dc`.
- Factory `0x1000114b`: `operator_new(0xc)` then ctor `FUN_100011ab`.

The class-name **path string** the module map keys on is
`\Sys\SC3ScenarioLayer.INI` `[CONFIRMED @ 0x1001e820]`; the class GZCLSIDs are the
two dwords above, not name strings. `[UNCERTAIN]` which GZCLSID is the public
`SC3ScenarioLayer` interface vs. the internal helper — inferred from allocation
size (the 2480-byte object is the engine, the 12-byte object is a COM facet); no
name-string binds either id.

## 3. The interpreter core (key subsystems)

### Command node layout `[CONFIRMED]`
From `FUN_10005c2b`, `FUN_10007206`, `FUN_1000a514`, a command node is:

| offset | field |
|---|---|
| `+0x04` | `int16` opcode id (dispatched against `DAT_1001eb10`) |
| `+0x06` | `byte` argument count |
| `+0x08` | pointer to argument array, **8 bytes per arg**: `[+0]` byte `isVariable`, `[+4]` int `value` |

### SC3ScenarioLayer object layout (partial, from `FUN_100065dc` + handlers) `[CONFIRMED]`

| offset | meaning | evidence |
|---|---|---|
| `+0x00`,`+0x04` | vtables (`PTR_FUN_1001a64c`, `PTR_LAB_1001a604` after ctor) | `0x100065dc` |
| `+0x09` | byte "execute" flag — when 0, dispatcher forces cmd arg to 0 (condition/dry mode) | `0x10008d1a` |
| `+0x14` | GZCOM framework/service pointer (disasters, deals, speed) | `0x1000aaf3`,`0x1000a448` |
| `+0x18` / `+0x1c` | city max X / max Y (coord clamp) | `0x1000aaf3` |
| `+0x38` | sim-query service (population source, vtbl `+0x78`) | `0x100074c5` |
| `+0x3c` | sim-query service (funds source, vtbl `+0x10`) | `0x10007236` |
| `+0x64` | int initialized to **1000** | `0x100065dc` (`param_1[0x19]=1000`) |
| `+0x70` | base of **512-entry int variable file** (`idx < 0x200`) | `0x10005c2b`,`0x10007206` |
| `+0x8c0` | goal-status map (`entry+0x18` = status byte) | `0x1000799f` |
| `+0x8cc`/`+0x8d8` | end-scenario selection map / selected index | `0x10006db8` |
| `+0x94c`/`+0x974` | newsticker map | `0x1000a514` |
| `+0x9a8`,`+0x9a9` | byte flags (0x9a9 = scenario-speed non-zero) | `0x10006db8`,`0x1000a448` |

Ctor also seeds `param_1[0x22c] = 0x022e288e`, `[0x22d]=3`, `[0x22e]=1` `[CONFIRMED @ 0x100065dc]` (raw; purpose not determined).

### Dispatcher `FUN_10008d1a` `[CONFIRMED]`
`sc3_scenario_dispatch_command(this, node, arg)`: reads `int16` id at `node+4`,
bounds-checks against `DAT_1001e1ec` (max registered id), fetches handler at
`DAT_1001eb10 + id*8`, calls `handler(node, arg)`. If `this+9 == 0` the `arg` is
forced to 0 before the call. `DAT_1001eb10` is the **opcode dispatch table**
(8 bytes/entry: handler ptr + aux), `DAT_1001e1ec` the max id.

### Argument evaluator `FUN_10005c2b` `[CONFIRMED]`
`sc3_scenario_eval_arg(this, node, i)`: if `i < node[+6]`, reads arg `i` from
`node[+8]`; when its `isVariable` byte is set, the value is a variable index and the
result is read from the variable file `this+0x70+idx*4`; otherwise it is an
immediate. Out-of-range → 0.

### Result-slot resolver `FUN_10007206` `[CONFIRMED]`
`sc3_scenario_resolve_result_var`: evaluates arg0 as a destination variable index,
requires `< 0x200`, else fails. This is the write-target for the value-producing
opcodes (`cmdGet*`, `cmdAdd`, …) which store into `this+0x70+idx*4`.

### Command-table builder `FUN_1000b1f9` `[CONFIRMED]`
Static initializer that (a) loads `\Sys\SC3ScenarioLayer.INI` from `\Sys\SYS.PAK`
via the resource service `FUN_1001511a` (vtbl `+0x50`), (b) parses the
`CommandNameToIdMapping` section `[CONFIRMED @ 0x1001e7f8]` assigning each `cmd*`
name a numeric id, (c) sizes the dispatch table `DAT_1001eb10` to
`DAT_1001e1ec + 1` and zero-fills it, (d) binds every built-in `cmd*` name to its
handler via `FUN_1000c6fe`. So **opcode ids are data-driven from the INI**, while
the name→handler binding is compiled in. Handler registrar `FUN_1000c6fe`
`[0x1000c6fe]`: looks the name up in map `DAT_1001eb78`, gets its id (`+0x24`), and
writes `{handler, aux}` into `DAT_1001eb10 + id*8`.

At its tail the builder pushes **8 dword pairs** into `DAT_1001eb68`
`[CONFIRMED @ 0x1000b1f9]` (raw, purpose not determined — likely GZCLSID/resource-key
pairs): `(0x04845cbe,0xc3de4d66)`, `(0xa4846144,0xa48461a3)`,
`(0x44eb6bc8,0x44eb6bc9)`, `(0x62b9da24,0x6504691d)`, `(0x23dfae5f,0x23dfae8c)`,
`(0x26e732e0,0x19a6cea1)`, `(0x2026960b,0x19a6cea1)`, `(0x62b9da24,0x19a6cea1)`.

## 4. Representative opcode handlers (mechanics + constants)

- **cmdStartFire** `FUN_1000aaf3`: eval arg0/arg1 as (x,y), subtract 1 (1-based→0-based),
  clamp to `[0, this+0x18]`×`[0, this+0x1c]`. Gets the disaster factory via
  framework `this+0x14` vtbl `+0x168` → query GZCLSID **`0x621cda33`** → create IID
  **`0x634fd3bc`** → call obj vtbl `+0x10 (x,y)`. `[CONFIRMED @ 0x1000aaf3]`
- **cmdStartEarthquake** `FUN_1000aa2f`: factory query GZCLSID **`0x42963812`**,
  create IID **`0xe3024e82`**. Magnitude = `arg0 * _DAT_1001a6dc`, then normalized:
  `< _DAT_1001a6d8 → 0.0`; `> _DAT_1001a6d4 → 1.0` `[CONFIRMED @ 0x1000aa2f]`
  (three float tunables in `.rdata`; exact values `[UNCERTAIN]` — not in globals.csv).
  Calls obj vtbl `+0x14 (magnitude, arg1!=0)`.
- **cmdStartUFOAttack** `FUN_1000b0bb`: factory query GZCLSID **`0xe2963828`**, create
  IID **`0x43024ded`**, obj vtbl `+0x10 (arg0!=0)`. `[CONFIRMED @ 0x1000b0bb]`
  (all `cmdStart*` disasters share this framework-`+0x168`→query→create→invoke shape.)
- **cmdGetPopulation** `FUN_100074c5`: `this+0x38` vtbl `+0x78` → store into result var. `[CONFIRMED]`
- **cmdGetFundsAvailable** `FUN_10007236`: `this+0x3c` vtbl `+0x10` → result var. `[CONFIRMED]`
- **cmdAdd** `FUN_10005bd3`: `var[dst] = eval(arg1) + eval(arg2)`. `[CONFIRMED]`
- **cmdSetVariable** `FUN_1000a4d9`: `var[dst] = eval(arg1)`. `[CONFIRMED]`
- **cmdIf** `FUN_10007b48`: pulls two sub-nodes via `FUN_1000741f`; dispatches the
  condition node, and on true dispatches the body, else dispatches body with arg 0
  (evaluate-only). `[CONFIRMED]`
- **cmdRepeatRegular** `FUN_10009a5d`: evals arg0/arg1/arg2, seeds a struct tagged
  `0x23dfae5f`, calls `FUN_10005b76` (timer/recurring registration). `[CONFIRMED]`
- **cmdSubRoutine** `FUN_1000c742`: evals arg0/arg1, uses resource manager
  `DAT_1001eb8c` (vtbl `+0x24`/`+0x14`) to fetch resource keyed `0x23dfae5f` /
  IID `0x80199683`, then re-enters the interpreter `FUN_10008d58`. `[CONFIRMED]`
- **cmdSetScenarioSpeed** `FUN_1000a448`: framework `+0x14` vtbl `+0x204(arg0)`,
  `+0x214`(query)/`+0x210`; posts message **`0x54e23ee9`** (data=arg1) via
  `FUN_100108a2`; sets `this+0x9a9 = (arg1!=0)`. `[CONFIRMED]`
- **cmdEndScenario** `FUN_10006db8`: records end selection in map `this+0x8cc`,
  posts/sends message **`0xba44eb51`**. `[CONFIRMED]`
- **cmdShowNewsticker** `FUN_1000a514`: allocates a `0x14`-byte request, builds a
  ticker item keyed class **`0x84628d9a`**, posts message **`0x82684130`** (or
  **`0xa460ed02`** when a target entry exists) via `FUN_100108a2`. `[CONFIRMED]`
- **cmdOfferRewardBuilding** `FUN_100088ad`: framework `+0x14` vtbl `+0x1a8` → service
  vtbl `+0x14 (arg0)`. `[CONFIRMED]`
- **cmdGoalStatusIs** `FUN_1000799f`: looks up goal id (arg0) in map `this+0x8c0`,
  compares status byte at `entry+0x18` against arg1. `[CONFIRMED]`

## 5. Data / tunables (raw)

- **Config:** `\Sys\SC3ScenarioLayer.INI` `[0x1001e820]`, read from `\Sys\SYS.PAK`
  `[0x1001e810]`; section `[CommandNameToIdMapping]` `[0x1001e7f8]` maps opcode
  name→id. INI write format strings `"\n[%s]\n"`, `"%s = %s\n"`, `"[%s]\n"`
  `[0x1001e840–0x1001e858]`.
- **Opcode vocabulary:** ~72 `cmd*` names `[0x1001e278–0x1001e7f8]` (full id map in §6).
  Note `cmdEndAnd` `[0x1001e214]`, `cmdEndBlock` `[0x1001e220]`, `cmdEndOr`
  `[0x1001e240]` are present as strings but are **not** bound in the handler loop —
  they read as parser block-terminator tokens, not dispatchable opcodes `[UNCERTAIN]`.
- **Text template tokens:** `%TOKEN%`, `%MAYOR%`, `%YOURNAME%`, `%CITYNAME%`,
  `%YOURCITY%`, `%POPULATION%`, `%YEAR%`, `%PARADENAME%`, `%ANYNEIGHBOR%`,
  `%SCNNAME%`, `%SCNV` `[0x1001e200–0x1001e984]`.
- **printf arg formats:** `"%d %d"`, `"%d %d %d"`, `"%d %d %d %d"`, `"%s %d"`
  `[0x1001e234–0x1001e26c]` (used to serialize/parse command args).
- **Earthquake magnitude tunables:** `_DAT_1001a6dc` (scale), `_DAT_1001a6d8` (floor),
  `_DAT_1001a6d4` (ceiling) `[CONFIRMED refs @ 0x1000aa2f]` — float values not recovered.
- **Ctor constants:** variable-file init size seeds; `this+0x64 = 1000`;
  `this+0x22c = 0x022e288e`, `+0x22d = 3`, `+0x22e = 1` `[0x100065dc]`.
- **Version:** FileVersion `2.0.949`, "SimCity 3000", Maxis, © 1999
  `[0x1001f232/0x1001f1d4/0x1001f118]`.

## 6. Full opcode → handler map `[CONFIRMED @ 0x1000b1f9]`

Ids are the sequential values assigned in the builder (`0x04`–`0x4b`); handlers left
as bare `LAB_*` were reached only through the DATA-driven table (no exported body).

`cmdAdd`→`FUN_10005bd3`(0x04) · `cmdAddGoal`→`FUN_100058d0`(0x05) ·
`cmdAllGoalsMet`→`FUN_10005a1a`(0x06) · `cmdAddRankInfo`→`FUN_10005a84`(0x07) ·
`cmdAndCondition`→`FUN_10005c57`(0x08) · `cmdAssign`→`FUN_10005cf8`(0x09) ·
`cmdBeginBlock`→`FUN_10005d47`(0x0a) · `cmdCountUnpoweredBuildings`→`FUN_10006528`(0x0b) ·
`cmdCountUnwateredBuildings`→`FUN_1000656a`(0x0c) · `cmdComputePercentage`→`FUN_10005e77`(0x0d) ·
`cmdCountStructures`→`FUN_10006194`(0x0e) · `cmdCountStructuresNearLocation`→`FUN_10005ee7`(0x0f) ·
`cmdCountStructuresWithAppearanceInCity`→`FUN_100063ef`(0x10) ·
`cmdCountStructuresWithAppearanceNearLocation`→`FUN_10006474`(0x11) ·
`cmdDecrement`→`FUN_100068e8`(0x12) · `cmdDisableNewNeighborDeals`→`LAB_10006938`(0x13) ·
`cmdDivide`→`FUN_10006c4b`(0x14) · `cmdEnableNewNeighborDeals`→`LAB_10006d6c`(0x15) ·
`cmdEnableDisableBusinessDeal`→`LAB_1000898a`(0x16) · `cmdEndScenario`→`FUN_10006db8`(0x17) ·
`cmdEqual`→`LAB_10006eb1`(0x18) · `cmdGenerateRandomNum`→`FUN_10006eeb`(0x19) ·
`cmdGetAura`→`FUN_10006f63`(0x1a) · `cmdGetCrimeValue`→`FUN_10006fa8`(0x1b) ·
`cmdGetCurrentDate`→`FUN_10006fed`(0x1c) · `cmdGetFundsAvailable`→`FUN_10007236`(0x1d) ·
`cmdGetPollutionValue`→`FUN_10007455`(0x1e) · `cmdGetLandValue`→`FUN_10007356`(0x1f) ·
`cmdGetPopulation`→`FUN_100074c5`(0x20) · `cmdGetSurplusPower`→`FUN_10007704`(0x21) ·
`cmdGetSurplusWater`→`FUN_1000775a`(0x22) · `cmdGetTotalDebt`→`FUN_10007807`(0x23) ·
`cmdGetTrafficDensity`→`FUN_10007849`(0x24) · `cmdGetRCItaxes`→`FUN_1000789f`(0x25) ·
`cmdGoalStatusIs`→`FUN_1000799f`(0x26) · `cmdGreaterThan`→`LAB_10007965`(0x27) ·
`cmdIf`→`FUN_10007b48`(0x28) · `cmdIfElse`→`FUN_10007ace`(0x29) ·
`cmdIncrement`→`FUN_10007b97`(0x2a) · `cmdIsOrdinanceEnacted`→`LAB_100083fa`(0x2b) ·
`cmdIsBusinessDealActive`→`LAB_1000892f`(0x2c) · `cmdIsNeighborConnection`→`FUN_10008462`(0x2d) ·
`cmdIsNeighborDealPresent`→`FUN_100084d3`(0x2e) · `cmdLessThan`→`LAB_1000857a`(0x2f) ·
`cmdMakeDialogText`→`LAB_1000860c`(0x30) · `cmdMarkGoalStatus`→`FUN_10008662`(0x31) ·
`cmdMoveCamera`→`FUN_10008721`(0x32) · `cmdMultiply`→`FUN_1000881a`(0x33) ·
`cmdNotEqual`→`LAB_10008873`(0x34) · `cmdOfferRewardBuilding`→`FUN_100088ad`(0x35) ·
`cmdOfferBusinessDeal`→`LAB_100088f5`(0x36) · `cmdOrCondition`→`FUN_100089e4`(0x37) ·
`cmdPlaySound`→`LAB_10008bf3`(0x38) · `cmdPopUpMsg`→`FUN_10008c5d`(0x39) ·
`cmdRepeatRegular`→`FUN_10009a5d`(0x3a) · `cmdEnableDisableDisasters`→`LAB_10006d29`(0x3b) ·
`cmdSetResultsDlgText`→`LAB_1000a320`(0x3c) · `cmdSetScenarioSpeed`→`FUN_1000a448`(0x3d) ·
`cmdSetVariable`→`FUN_1000a4d9`(0x3e) · `cmdShowNewsticker`→`FUN_1000a514`(0x3f) ·
`cmdStartEarthquake`→`FUN_1000aa2f`(0x40) · `cmdStartFire`→`FUN_1000aaf3`(0x41) ·
`cmdStartLocusts`→`FUN_1000ab97`(0x42) · `cmdStartRiot`→`FUN_1000ac11`(0x43) ·
`cmdStartSpaceJunk`→`FUN_1000ad3e`(0x44) · `cmdStartTornado`→`FUN_1000ae04`(0x45) ·
`cmdStartUFOAttack`→`FUN_1000b0bb`(0x46) · `cmdStartToxicCloud`→`FUN_1000afec`(0x47) ·
`cmdStartWhirlpool`→`FUN_1000b135`(0x48) · `cmdSubRoutine`→`FUN_1000c742`(0x49) ·
`cmdSubtract`→`FUN_1000c7d0`(0x4a) · `cmdGetMonthsElapsed`→`FUN_100073de`(0x4b).
(Id 0x03 = the `CommandNameToIdMapping` loader itself, handler `LAB_10006e7e`.)

## 7. Cross-module edges

All go through the framework pointer `this+0x14` (a GZCOM service/registry; vtbl
`+0x168` returns the class factory catalog) or the message service `FUN_100108a2`.
GZCLSID/IID values are `[CONFIRMED]` as the immediate operands in the handlers:

| Consumer opcode | GZCLSID (factory) | IID (interface) | likely target |
|---|---|---|---|
| cmdStartFire | `0x621cda33` | `0x634fd3bc` | disaster layer (SIMDSTR `SC3DisasterLayer`) `[iOS-HINT for the layer id, unconfirmed]` |
| cmdStartEarthquake | `0x42963812` | `0xe3024e82` | disaster layer |
| cmdStartUFOAttack | `0xe2963828` | `0x43024ded` | disaster layer |
| cmdGetPopulation | via `this+0x38` vtbl+0x78 | — | sim query service |
| cmdGetFundsAvailable | via `this+0x3c` vtbl+0x10 | — | budget/finance service |
| cmdOfferRewardBuilding | via `this+0x14` vtbl+0x1a8 | — | reward/building service |
| cmdSetScenarioSpeed | msg `0x54e23ee9`; framework vtbl+0x204/+0x214/+0x210 | — | sim clock |
| cmdEndScenario | msg `0xba44eb51` | — | game-flow/UI |
| cmdShowNewsticker | msg `0x82684130` / `0xa460ed02`; class `0x84628d9a` | — | newsticker UI (SIMUI) |
| cmdSubRoutine | resource `DAT_1001eb8c` query class `0x23dfae5f` IID `0x80199683` | — | scenario resource store |

Config/resource I/O uses the resource service `FUN_1001511a` → `DAT_1001ec64`
(vtbl+0x50 open) to read `SC3ScenarioLayer.INI` out of `SYS.PAK`. `Ole32`
(`CoCreateInstance`) `[0x1001e8d0]` is imported but not seen wired into any opcode
handler read here `[UNCERTAIN]`.

## 8. Classification table (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x1000f984,scenario-director,C2,sc3_scenario_get_gzcom_director,PE export; guarded ctor of DAT_1001e9e0 returns director
0x100010b1,scenario-director,C2,sc3_scenario_director_ctor,sets vtables + 2x register_class(0x03de4ce4/0x03dfae27)
0x1000fd11,scenario-director,C2,sc3_scenario_register_class,inserts {clsid,factory} into director map at this+0x14
0x10001116,scenario-director,C2,sc3_scenario_factory_layer,operator_new(0x9b0)+ctor 0x100065dc (SC3ScenarioLayer)
0x1000114b,scenario-director,C2,sc3_scenario_factory_helper,operator_new(0xc)+ctor 0x100011ab
0x100011ab,scenario-director,C2,sc3_scenario_helper_ctor,sets 3 vtables 1001a224/a24c/a264 on 12-byte object
0x100065dc,scenario-layer,C2,sc3_scenario_layer_ctor,inits 2480B object; var-file base +0x70; +0x64=1000; +0x22c=0x22e288e
0x1000b1f9,scenario-vm,C2,sc3_scenario_build_command_table,loads SC3ScenarioLayer.INI CommandNameToIdMapping; binds ~72 cmd handlers into DAT_1001eb10
0x1000c6fe,scenario-vm,C2,sc3_scenario_register_command,name->id via DAT_1001eb78 then writes handler to DAT_1001eb10+id*8
0x10008d1a,scenario-vm,C2,sc3_scenario_dispatch_command,int16 id@node+4; bounds vs DAT_1001e1ec; call DAT_1001eb10+id*8
0x10005c2b,scenario-vm,C2,sc3_scenario_eval_arg,reads arg i from node+8 (8B stride); resolves variable via this+0x70+idx*4
0x10007206,scenario-vm,C2,sc3_scenario_resolve_result_var,arg0 as dest var index; requires <0x200
0x100108a2,scenario-messaging,C2,sc3_scenario_get_message_service,lazy-init cached message service DAT_1001ebac
0x1001511a,scenario-config,C2,sc3_scenario_get_framework,guarded init returns resource/framework service DAT_1001ec64
0x10005bd3,scenario-vm-math,C2,sc3_scenario_cmd_add,var[dst]=eval(arg1)+eval(arg2)
0x1000a4d9,scenario-vm-math,C2,sc3_scenario_cmd_setvariable,var[dst]=eval(arg1)
0x10007b48,scenario-vm-control,C2,sc3_scenario_cmd_if,dispatch cond node then body; false=>body with arg0
0x10009a5d,scenario-vm-control,C2,sc3_scenario_cmd_repeatregular,evals 3 args; registers recurring via FUN_10005b76 tag 0x23dfae5f
0x1000c742,scenario-vm-control,C2,sc3_scenario_cmd_subroutine,fetch resource 0x23dfae5f/IID 0x80199683 then re-enter interpreter
0x100074c5,scenario-query,C2,sc3_scenario_cmd_getpopulation,this+0x38 vtbl+0x78 -> result var
0x10007236,scenario-query,C2,sc3_scenario_cmd_getfundsavailable,this+0x3c vtbl+0x10 -> result var
0x1000799f,scenario-goals,C2,sc3_scenario_cmd_goalstatusis,lookup goal id in map this+0x8c0; compare status byte entry+0x18
0x10006db8,scenario-flow,C2,sc3_scenario_cmd_endscenario,records end selection map this+0x8cc; posts msg 0xba44eb51
0x1000a448,scenario-flow,C2,sc3_scenario_cmd_setscenariospeed,framework vtbl+0x204/+0x214/+0x210; posts msg 0x54e23ee9; sets +0x9a9
0x1000a514,scenario-ui,C2,sc3_scenario_cmd_shownewsticker,builds ticker item class 0x84628d9a; posts msg 0x82684130/0xa460ed02
0x100088ad,scenario-deals,C2,sc3_scenario_cmd_offerrewardbuilding,framework vtbl+0x1a8 -> service vtbl+0x14(arg0)
0x1000aaf3,scenario-disaster,C2,sc3_scenario_cmd_startfire,clamp x/y to this+0x18/0x1c; clsid 0x621cda33 iid 0x634fd3bc vtbl+0x10
0x1000aa2f,scenario-disaster,C2,sc3_scenario_cmd_startearthquake,clsid 0x42963812 iid 0xe3024e82; mag=arg0*_DAT_1001a6dc clamped by _DAT_1001a6d8/_DAT_1001a6d4
0x1000b0bb,scenario-disaster,C2,sc3_scenario_cmd_startufoattack,clsid 0xe2963828 iid 0x43024ded vtbl+0x10(arg0!=0)
0x100058d0,scenario-goals,C1,sc3_scenario_cmd_addgoal,cmdAddGoal handler (registered id 0x05)
0x10005a1a,scenario-goals,C1,sc3_scenario_cmd_allgoalsmet,cmdAllGoalsMet handler (id 0x06)
0x10005a84,scenario-goals,C1,sc3_scenario_cmd_addrankinfo,cmdAddRankInfo handler (id 0x07)
0x10005c57,scenario-vm-control,C1,sc3_scenario_cmd_andcondition,cmdAndCondition handler (id 0x08)
0x10005cf8,scenario-vm-math,C1,sc3_scenario_cmd_assign,cmdAssign handler (id 0x09)
0x10005d47,scenario-vm-control,C1,sc3_scenario_cmd_beginblock,cmdBeginBlock handler (id 0x0a)
0x10006528,scenario-query,C1,sc3_scenario_cmd_countunpoweredbuildings,cmdCountUnpoweredBuildings (id 0x0b)
0x1000656a,scenario-query,C1,sc3_scenario_cmd_countunwateredbuildings,cmdCountUnwateredBuildings (id 0x0c)
0x10005e77,scenario-vm-math,C1,sc3_scenario_cmd_computepercentage,cmdComputePercentage (id 0x0d)
0x10006194,scenario-query,C1,sc3_scenario_cmd_countstructures,cmdCountStructures (id 0x0e)
0x10005ee7,scenario-query,C1,sc3_scenario_cmd_countstructuresnearlocation,cmdCountStructuresNearLocation (id 0x0f)
0x100063ef,scenario-query,C1,sc3_scenario_cmd_countstructureswithappearanceincity,cmdCountStructuresWithAppearanceInCity (id 0x10)
0x10006474,scenario-query,C1,sc3_scenario_cmd_countstructureswithappearancenearlocation,cmdCountStructuresWithAppearanceNearLocation (id 0x11)
0x100068e8,scenario-vm-math,C1,sc3_scenario_cmd_decrement,cmdDecrement (id 0x12)
0x10006c4b,scenario-vm-math,C1,sc3_scenario_cmd_divide,cmdDivide (id 0x14)
0x10006eeb,scenario-vm-math,C1,sc3_scenario_cmd_generaterandomnum,cmdGenerateRandomNum (id 0x19)
0x10006f63,scenario-query,C1,sc3_scenario_cmd_getaura,cmdGetAura (id 0x1a)
0x10006fa8,scenario-query,C1,sc3_scenario_cmd_getcrimevalue,cmdGetCrimeValue (id 0x1b)
0x10006fed,scenario-query,C1,sc3_scenario_cmd_getcurrentdate,cmdGetCurrentDate (id 0x1c)
0x10007455,scenario-query,C1,sc3_scenario_cmd_getpollutionvalue,cmdGetPollutionValue (id 0x1e)
0x10007356,scenario-query,C1,sc3_scenario_cmd_getlandvalue,cmdGetLandValue (id 0x1f)
0x10007704,scenario-query,C1,sc3_scenario_cmd_getsurpluspower,cmdGetSurplusPower (id 0x21)
0x1000775a,scenario-query,C1,sc3_scenario_cmd_getsurpluswater,cmdGetSurplusWater (id 0x22)
0x10007807,scenario-query,C1,sc3_scenario_cmd_gettotaldebt,cmdGetTotalDebt (id 0x23)
0x10007849,scenario-query,C1,sc3_scenario_cmd_gettrafficdensity,cmdGetTrafficDensity (id 0x24)
0x1000789f,scenario-query,C1,sc3_scenario_cmd_getrcitaxes,cmdGetRCItaxes (id 0x25)
0x10007ace,scenario-vm-control,C1,sc3_scenario_cmd_ifelse,cmdIfElse (id 0x29)
0x10007b97,scenario-vm-math,C1,sc3_scenario_cmd_increment,cmdIncrement (id 0x2a)
0x10008462,scenario-neighbor,C1,sc3_scenario_cmd_isneighborconnection,cmdIsNeighborConnection (id 0x2d)
0x100084d3,scenario-neighbor,C1,sc3_scenario_cmd_isneighbordealpresent,cmdIsNeighborDealPresent (id 0x2e)
0x10008662,scenario-goals,C1,sc3_scenario_cmd_markgoalstatus,cmdMarkGoalStatus (id 0x31)
0x10008721,scenario-ui,C1,sc3_scenario_cmd_movecamera,cmdMoveCamera (id 0x32)
0x1000881a,scenario-vm-math,C1,sc3_scenario_cmd_multiply,cmdMultiply (id 0x33)
0x100089e4,scenario-vm-control,C1,sc3_scenario_cmd_orcondition,cmdOrCondition (id 0x37)
0x10008c5d,scenario-ui,C1,sc3_scenario_cmd_popupmsg,cmdPopUpMsg (id 0x39)
0x100073de,scenario-query,C1,sc3_scenario_cmd_getmonthselapsed,cmdGetMonthsElapsed (id 0x4b)
0x1000c7d0,scenario-vm-math,C1,sc3_scenario_cmd_subtract,cmdSubtract (id 0x4a)
0x1000aa2f_disaster_group,scenario-disaster,C1,sc3_scenario_cmd_startlocusts,cmdStartLocusts=FUN_1000ab97 startriot=FUN_1000ac11 startspacejunk=FUN_1000ad3e starttornado=FUN_1000ae04 starttoxiccloud=FUN_1000afec startwhirlpool=FUN_1000b135 (ids 0x42-0x48)
```

## 9. OPEN

- **Which GZCLSID is the public SC3ScenarioLayer.** Only two ids register
  (`0x03de4ce4`, `0x03dfae27`); no name-string binds either. Missing evidence: the
  ASCII `SC3ScenarioLayer`→GZCLSID mapping in `SYS.PAK`/`CitySim.ini`, or the vtable
  interface-id, to confirm the 2480-byte object is the layer.
- **Earthquake tunable float values** (`_DAT_1001a6d4/d8/dc`): referenced but their
  constants are not in `globals.csv`. Missing: a read of the `.rdata` float bytes at
  those RVAs (needs the raw data dump, not the function export).
- **The 8 dword-pairs pushed to `DAT_1001eb68`** at `0x1000b1f9` tail: raw values
  captured; meaning not determined (candidate GZCLSID/resource-key ranges). Missing:
  a consumer of `DAT_1001eb68` (no reader was located in this pass).
- **Disaster target layer identity.** GZCLSID `0x621cda33`/`0x42963812`/`0x2963828`
  are consumed here but defined elsewhere; mapping them to `SIMDSTR.DLL`'s registered
  ids is unproven. Missing: SIMDSTR's own director GZCLSID→factory table.
- **`LAB_*`-only handlers** (e.g. `cmdEqual`, `cmdGreaterThan`, `cmdLessThan`,
  `cmdMakeDialogText`, `cmdOfferBusinessDeal`, `cmdPlaySound`, `cmdIsOrdinanceEnacted`):
  reached only via the DATA-driven dispatch table, so Ghidra left no exported `.c`
  body — bodies not read. Their ids/names are `[CONFIRMED]`; behavior is not.
- **`Ole32`/`CoCreateInstance` usage.** Imported `[0x1001e8d0]` but no opcode handler
  read here calls it. Missing: an xref sweep for the COM call site.
- **`FUN_100011ab` 12-byte facet role.** Three vtables set; purpose (event sink? COM
  aggregate?) not determined. Missing: identification of the vtable interface ids.
