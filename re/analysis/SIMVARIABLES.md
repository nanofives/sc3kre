# SIMVARIABLES.DLL — GZCOM director analysis

**Module:** `Apps\simvariables.dll` (image base `0x10000000`)
**SHA-256:** `24c6f6b56b8af2b39a93cae1f48d829e262556d9469c4a6c23b0c6cf26d4e7ad`
**Export dir:** `re/ghidra_export_simvariables/` (541 functions, decomp ok=541 fail=0)
**Anchor note:** all RVAs below are `simvariables.dll` module-relative (`0x1000xxxx`), NOT SC3U.exe.

---

## 1. Purpose

`simvariables.dll` is a small GZCOM director module (only ~40 KB of real game code; the
rest is MSVC CRT/STL, RTTI, and a large SEH unwind-thunk table). It registers **two GZCOM
classes** and, per its strings, provides:

- A **keyed name/value variable store** loaded from configuration. It reads
  `\Sys\SYS.PAK` section `Tunables` `[CONFIRMED @ 0x1000e0e8, 0x1000e0dc]` and
  `\Sys\SimTune.INI` section `tuneup` `[CONFIRMED @ 0x1000e0c0, 0x1000e0d4]`, converts each
  entry's name-string into a 32-bit numeric id, and stores id→value pairs in a vector on the
  object. INI-style writeback format strings `"\n[%s]\n"`, `"%s = %s\n"`, `"[%s]\n"` are
  present `[CONFIRMED @ 0x1000e258, 0x1000e264, 0x1000e270]`.
- A set of **text-substitution macro tokens** — 8 global `std::string` constants
  `%MAYOR% %YOURNAME% %CITYNAME% %YOURCITY% %POPULATION% %YEAR% %PARADENAME% %ANYNEIGHBOR%`
  `[CONFIRMED @ 0x1000e330..0x1000e384]` — i.e. named placeholders substituted from city state.

The two registered classes are publicly named **`sysser`** and **`cogamecmd`**
`[CONFIRMED @ 0x1000e1e4, 0x1000e1ec]` (see §2). "sysser" (system-service) is the
variable/tunable store; "cogamecmd" (co-game-command) is a command object holding a
sub-object vector.

---

## 2. Director + registrations

**Chain (the GZCOM recipe holds exactly):**

| Step | RVA | What |
|---|---|---|
| PE export | `GZDllGetGZCOMDirector` @ `0x10006a2d` | guarded one-time ctor of static director at `&DAT_1000e490`, guard `DAT_1000e478 & 1` `[CONFIRMED @ 0x10006a2d]` |
| director ctor | `FUN_10002ab2` @ `0x10002ab2` | calls base ctor, sets vtables `PTR_FUN_1000b714` / `PTR_LAB_1000b6e8`, then 2× `register_class` `[CONFIRMED @ 0x10002ab2]` |
| base ctor | `FUN_10006a32` @ `0x10006a32` | vtables `PTR_LAB_1000b98c`/`b960` → `PTR_FUN_1000b918`/`b8ec`; zeroes members; builds two string members (`FUN_10006e94`); inits container at `+0x2c` (`FUN_10001147`) `[CONFIRMED @ 0x10006a32]` |
| register_class | `FUN_10006db3` @ `0x10006db3` | inserts `(clsid, factory, 0)` into the map at **director+0x14** via `FUN_1000705a` `[CONFIRMED @ 0x10006db3]` |
| map insert | `FUN_1000705a` @ `0x1000705a` | red-black-tree insert keyed on node dwords `[4],[5]` `[CONFIRMED @ 0x1000705a]` |

**Registered classes (GZCLSID → factory):** `[CONFIRMED @ 0x10002ab2 L20–21]`

| GZCLSID | Public name | Factory RVA | `operator_new` size | Object ctor | Vtable(s) |
|---|---|---|---|---|---|
| `0xa4232f1e` | **sysser** | `FUN_100010a0` (via `thunk_FUN_100010a0`) | **0x40 (64)** `[CONFIRMED @ 0x100010a0 L17]` | `FUN_100010d2` | `PTR_LAB_1000b240`, `b230`, `b264`, `b218` |
| `0x24242600` | **cogamecmd** | `FUN_10002b1c` | **0x14 (20)** `[CONFIRMED @ 0x10002b1c L18]` | `FUN_100071a4` | `PTR_FUN_1000b9c8` (base), `PTR_FUN_1000b75c` (derived) `[CONFIRMED @ 0x10002b1c L23]` |

**Name→classid alias registration** (`FUN_10002b81` @ `0x10002b81`): builds `std::string`
pairs and registers, via a service's vtable slot `+0x18`, the alias `"sysser"` → `"0xa4232f1e"`
and `"cogamecmd"` → `"0x24242600"` `[CONFIRMED @ 0x10002b81 L33,47,51,65]`. This is what ties
the human names to the GZCLSIDs.

**No `*Layer` INI-path strings and no `SC3…Layer` class names appear in this module** — it is
not a sim layer; it is the shared variable/tunable service.

---

## 3. Key subsystems

**Variable store (write path).** `FUN_100017cb` @ `0x100017cb` — `store_variable(this, id, value)`:
linear-scans the record vector between `this+0x20` (begin) and `this+0x24` (end), stride
`0xc` dwords (48-byte records), record `[0]` = id. If `record[0]==id` it overwrites the value
(`FUN_10003f5f`); otherwise it appends a new record (`FUN_100018ae`) and, if a listener service
`FUN_10006955()` exists, posts a message: payload `{ [0]=0xa42396c5, [1]=id, 0, 0 }` via the
listener's vtable `+0x10` `[CONFIRMED @ 0x100017cb L35–37]`. **`0xa42396c5` is the "variable
added" broadcast message id.**

**Tunable id parsing.** `FUN_10007722` @ `0x10007722` — `parse_id(text)`: `"0x"`/`"0X"` prefix →
`strtoul(base 16)`; else if any `a–f`/`A–F` digit present → base 16; else base 10
`[CONFIRMED @ 0x10007722]`. **Variable/tunable keys are 32-bit ids written as text** (e.g.
`"0xa42483b1"`).

**Tunable load callback.** `FUN_1000176c` @ `0x1000176c`: for each `[Tunables]` entry, reads
name via source vtable `+0x14`, `parse_id`, `FUN_10003ee0(...,3)`, reads value string, then
`store_variable`. `[CONFIRMED @ 0x1000176c]`

**Load from SYS.PAK.** `FUN_100015e9` @ `0x100015e9`: opens `\Sys\SYS.PAK`
`[CONFIRMED @ 0x100015e9 L39]`, gets the resource service from singleton `FUN_10008875()`
(vtable `+0x50`), iterates section `"Tunables"` calling `FUN_10008cb3(..., FUN_1000176c, this)`
`[CONFIRMED @ 0x100015e9 L42–44]`. Populates the store on `this`.

**Load from SimTune.INI.** `FUN_100013de` @ `0x100013de`: when `FUN_10008875()` returns non-null,
resolves the tunable collection `0xa42483b1` (service `+0x2c` → `+0xc`/`+0x14`) with section
`"tuneup"`, then opens `\Sys\SimTune.INI` and loads it via object `(param_1-8)` vtable `+0x18`
`[CONFIRMED @ 0x100013de L26,30,36,41–43]`.

**Tunable get/set by id.** `FUN_1000154d` @ `0x1000154d`: `service = FUN_10008875()->+0x2c`;
`service->+0x18(sizeArg, 0xa42483b1)` then `service->+0x10(0xa42483b1)` — set-then-get of the
tunable collection `0xa42483b1` `[CONFIRMED @ 0x1000154d L11,14]`.

**sysser replace/re-init.** `FUN_10002d63` @ `0x10002d63`: via a service `+0x30` releases any
existing instance of class `0xa4232f1e` (size **`0x6c`=108**) `[CONFIRMED @ 0x10002d63 L24]`,
then `operator_new(0x14)`, `FUN_100071a4`, sets vtable `PTR_FUN_1000b75c`, `QueryInterface`
`0x20685aa3`, and registers the new object `[CONFIRMED @ 0x10002d63 L31,40,45]`.

**Singleton service accessor.** `FUN_10008875` @ `0x10008875`: guarded one-time init
(`DAT_1000e629&1`) → `FUN_100088a0`, returns `DAT_1000e630`. `FUN_100088a0` @ `0x100088a0`:
`FUN_10002a63()->+0x7c` object, then `vtable[0](0xfa2, &DAT_1000e630)` — fetches service slot
**`0xfa2` (4002)** into the singleton `[CONFIRMED @ 0x100088a0 L11]`.

**Framework director accessor.** `FUN_10002a63` @ `0x10002a63` → `FUN_10002a87()`, calls `+0x2c`
(the GZCOM director service getter) `[CONFIRMED @ 0x10002a63]`.

**cogamecmd dtor.** `FUN_100071d7` @ `0x100071d7`: sets base vtable `PTR_FUN_1000b9c8`, walks the
sub-object vector `[param_1[2], param_1[3])`, calling each element's vtable `+8` (release) and
nulling it `[CONFIRMED @ 0x100071d7 L20–23]`. cogamecmd object layout: `[0]`=vtable,
`[1]`=?, `[2..4]`=vector begin/end/cap (`FUN_100071a4` zeroes `[1..4]`) `[CONFIRMED @ 0x100071a4]`.

**Embedded id-holder sub-object.** `FUN_1000330a` @ `0x1000330a`: ctor storing `param_1` at
`this+0xc`, `param_2` at `this+0x10`, byte flag `this+0x14=0`, vtables `PTR_FUN_1000b824`/`b858`/`b870`.
In the sysser ctor it is constructed with `(0xc425a194, 0)` `[CONFIRMED @ 0x100010d2 L18]`.

---

## 4. Data / tunables / magic constants

| Constant | Meaning (mechanical) | Evidence |
|---|---|---|
| `0xa4232f1e` | GZCLSID of class **sysser** (variable store) | `[CONFIRMED @ 0x10002ab2, 0x1000e208]` |
| `0x24242600` | GZCLSID of class **cogamecmd** | `[CONFIRMED @ 0x10002ab2, 0x1000e1f8]` |
| `0xa42483b1` | id of the **tunable collection** ("tuneup"/"Tunables") | `[CONFIRMED @ 0x100013de, 0x1000154d]` |
| `0xa42396c5` | **message id** broadcast on new-variable insert | `[CONFIRMED @ 0x100017cb L35]` |
| `0xc425a194` | id stored in sysser's embedded sub-object (`this+0xc`) | `[CONFIRMED @ 0x100010d2, 0x1000330a]` |
| `0x20685aa3` | IID QueryInterface'd from a cogamecmd object | `[CONFIRMED @ 0x10002d63 L45]` |
| `0xfa2` (4002) | framework service slot holding the singleton | `[CONFIRMED @ 0x100088a0 L11]` |
| `0x6c` (108) | size arg used when releasing class `0xa4232f1e` | `[CONFIRMED @ 0x10002d63 L24]` |
| `0x40` (64) | `operator_new` size of the sysser object | `[CONFIRMED @ 0x100010a0]` |
| `0x14` (20) | `operator_new` size of the cogamecmd object | `[CONFIRMED @ 0x10002b1c]` |
| record stride `0xc` dwords (48 B) | variable-table record size; `record[0]`=id | `[CONFIRMED @ 0x100017cb L50]` |
| store vector at `this+0x20`/`+0x24` | begin/end of variable table | `[CONFIRMED @ 0x100017cb L22–24]` |

**Config keys / paths:** `\Sys\SYS.PAK` `[0x1000e0e8]`, `\Sys\SimTune.INI` `[0x1000e0c0]`,
section `Tunables` `[0x1000e0dc]`, section `tuneup` `[0x1000e0d4]`.

**Substitution token table** — 8 global `std::string`s, stride `0x18` (24 B), ascending address:

| Global | Token | Init fn |
|---|---|---|
| `DAT_1000e640` | `%ANYNEIGHBOR%` | `FUN_100093c5` |
| `DAT_1000e658` | `%PARADENAME%` | `FUN_10009395` |
| `DAT_1000e670` | `%YEAR%` | `FUN_10009365` |
| `DAT_1000e688` | `%POPULATION%` | `FUN_10009335` |
| `DAT_1000e6a0` | `%YOURCITY%` | `FUN_10009305` |
| `DAT_1000e6b8` | `%CITYNAME%` | `FUN_100092d5` |
| `DAT_1000e6d0` | `%YOURNAME%` | `FUN_100092a5` |
| `DAT_1000e6e8` | `%MAYOR%` | `FUN_10009275` |

`[CONFIRMED @ each init fn]`. Within this module these globals are **written only** (by their
initializers); no in-module reader was found by grep — the consumers are in other modules.

---

## 5. Cross-module edges

- Reaches the **GZCOM framework director** via `FUN_10002a63`/`FUN_10002a87` (`+0x2c`)
  `[CONFIRMED @ 0x10002a63]`.
- Obtains a **framework service** (slot `0xfa2`) that supplies file/resource I/O
  (`+0x7c` object; the returned singleton is used for SYS.PAK/INI access) `[CONFIRMED @ 0x100088a0, 0x100015e9]`.
- Depends on tunable collection id **`0xa42483b1`** resolved through that service
  `[CONFIRMED @ 0x100013de, 0x1000154d]`.
- Broadcasts message **`0xa42396c5`** to a listener service `FUN_10006955()` on variable insert
  `[CONFIRMED @ 0x100017cb]`.
- Consumers of the `%…%` tokens and of GZCLSID `0xa4232f1e`/`0x24242600` live in other modules
  (obtained by name `sysser`/`cogamecmd` or by classid) `[CONFIRMED @ 0x10002b81]`.
- Uses `MSVCP60.dll` `std::string`/`std::exception`, `MSVCIRT.dll`, `MSVCRT.dll`, `Ole32.dll`
  (`CoCreateInstance`/`CoInitialize`), `WINMM.dll` (`timeGetTime`) `[CONFIRMED @ strings.csv]`.

---

## 6. Classification table (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x10006a2d,gzcom,C2,sc3_simvar_get_director,"PE export; guarded ctor of static director &DAT_1000e490, guard DAT_1000e478&1 [@0x10006a2d]"
0x10002ab2,gzcom,C2,sc3_simvar_director_ctor,"sets director vtables; register_class(0xa4232f1e,fac),(0x24242600,fac) [@0x10002ab2 L20-21]"
0x10006a32,gzcom,C2,sc3_simvar_director_base_ctor,"vtables 1000b98c/b960->b918/b8ec; builds string members; inits container +0x2c [@0x10006a32]"
0x10006db3,gzcom,C2,sc3_simvar_register_class,"packs (clsid,factory,0), inserts into map at director+0x14 via FUN_1000705a [@0x10006db3]"
0x1000705a,gzcom,C2,sc3_simvar_map_insert,"red-black tree insert keyed on node dwords [4],[5]; calls FUN_100070f9 [@0x1000705a]"
0x100010a0,gzcom,C2,sc3_simvar_factory_sysser,"operator_new(0x40) then ctor FUN_100010d2 for class 0xa4232f1e [@0x100010a0]"
0x100010d2,simvar,C2,sc3_simvar_sysser_ctor,"class 0xa4232f1e ctor; sub-obj(0xc425a194) at +8; vector@0x20; container@0x2c; vtables 1000b240/b230/b264/b218 [@0x100010d2]"
0x10002b1c,gzcom,C2,sc3_simvar_factory_cogamecmd,"operator_new(0x14), FUN_100071a4, vtable PTR_FUN_1000b75c; class 0x24242600 [@0x10002b1c]"
0x100071a4,cogamecmd,C2,sc3_cogamecmd_ctor,"zeroes [1..4] (vector begin/end/cap), sets base vtable PTR_FUN_1000b9c8 [@0x100071a4]"
0x100071d7,cogamecmd,C2,sc3_cogamecmd_dtor,"sets base vtable; walks sub-object vector [2]..[3], releases each via +8, nulls [@0x100071d7]"
0x10002b81,gzcom,C2,sc3_simvar_register_names,"registers alias sysser->'0xa4232f1e', cogamecmd->'0x24242600' via service +0x18 [@0x10002b81 L33,47,51,65]"
0x100013de,tune,C2,sc3_tune_load_simtune_ini,"resolves tunable 0xa42483b1 section 'tuneup'; opens \Sys\SimTune.INI, loads via +0x18 [@0x100013de]"
0x100015e9,tune,C2,sc3_tune_load_syspak,"opens \Sys\SYS.PAK; iterates section 'Tunables' with callback FUN_1000176c(this) [@0x100015e9]"
0x1000176c,tune,C2,sc3_tune_store_entry_cb,"per-entry: parse_id(name), parse_id(value?), store into table via FUN_100017cb [@0x1000176c]"
0x100017cb,simvar,C2,sc3_simvar_store_variable,"scan vector this+0x20..+0x24 stride 0xc, rec[0]=id; overwrite or append; post msg 0xa42396c5{id} [@0x100017cb]"
0x10007722,tune,C2,sc3_tune_parse_id,"0x-prefix->strtoul16; hex-digit->base16; else base10 [@0x10007722]"
0x1000154d,tune,C2,sc3_tune_get_set_tunable,"singleton+0x2c service; +0x18 set then +0x10 get on collection 0xa42483b1 [@0x1000154d]"
0x10002d63,simvar,C2,sc3_simvar_reinit_sysser,"releases class 0xa4232f1e size 0x6c; new 0x14 obj; QI 0x20685aa3; re-register [@0x10002d63]"
0x1000330a,simvar,C2,sc3_simvar_idholder_ctor,"stores param1@+0xc, param2@+0x10, flag@+0x14; vtables 1000b824/b858/b870 [@0x1000330a]"
0x10008875,gzcom,C2,sc3_simvar_get_service_singleton,"guarded (DAT_1000e629&1) init via FUN_100088a0; returns DAT_1000e630 [@0x10008875]"
0x100088a0,gzcom,C2,sc3_simvar_init_service_singleton,"FUN_10002a63()->+0x7c; vtable[0](0xfa2,&DAT_1000e630) [@0x100088a0]"
0x10002a63,gzcom,C2,sc3_simvar_get_framework_director,"FUN_10002a87()->+0x2c (GZCOM director service getter) [@0x10002a63]"
0x10008747,util,C2,sc3_util_init_perf_timer,"QueryPerformanceFrequency; fills _DAT_1000e5d8.._1000e620 timing scalars [@0x10008747]"
0x10009275,token,C2,sc3_token_init_mayor,"DAT_1000e6e8 = '%MAYOR%' [@0x10009275]"
0x100092a5,token,C2,sc3_token_init_yourname,"DAT_1000e6d0 = '%YOURNAME%' [@0x100092a5]"
0x100092d5,token,C2,sc3_token_init_cityname,"DAT_1000e6b8 = '%CITYNAME%' [@0x100092d5]"
0x10009305,token,C2,sc3_token_init_yourcity,"DAT_1000e6a0 = '%YOURCITY%' [@0x10009305]"
0x10009335,token,C2,sc3_token_init_population,"DAT_1000e688 = '%POPULATION%' [@0x10009335]"
0x10009365,token,C2,sc3_token_init_year,"DAT_1000e670 = '%YEAR%' [@0x10009365]"
0x10009395,token,C2,sc3_token_init_paradename,"DAT_1000e658 = '%PARADENAME%' [@0x10009395]"
0x100093c5,token,C2,sc3_token_init_anyneighbor,"DAT_1000e640 = '%ANYNEIGHBOR%' [@0x100093c5]"
```

---

## 7. OPEN

- **Value type of stored variables** — `FUN_100017cb` stores an object copied by `FUN_10003f5f`
  into record slot `+2`; whether the value is a `std::string`, a numeric, or a variant is not
  determined. *Missing:* decompilation of `FUN_10003f5f`/`FUN_10003aac` and the record struct.
- **Full sysser vtable semantics** — the public get/set/query methods in `PTR_LAB_1000b240`/
  `b230`/`b264`/`b218` were not individually resolved (vtables are DATA; Ghidra left slots as
  `LAB_*`). *Missing:* the vtable dword arrays behind those PTR_ labels.
- **Meaning of ids `0xc425a194` and `0x20685aa3`** — one is embedded in the sysser object, the
  other is QueryInterface'd from cogamecmd; their interface/class semantics are unknown here.
  *Missing:* cross-module lookup (which module defines/consumes them).
- **cogamecmd behavior** — confirmed as a command object owning a sub-object vector, but its
  Execute/dispatch method and relation to game commands is not read. *Missing:* the methods in
  vtables `PTR_FUN_1000b75c` / `PTR_FUN_1000b9c8`.
- **Token consumers** — the 8 `%…%` tokens are only written in this module; the substitution
  engine that reads them (news/message text expansion using city state) lives elsewhere.
  *Missing:* grep for these token globals' addresses across the other module exports.
- **Message `0xa42396c5` subscribers** — broadcast on insert; recipients are external.
- **`iOS cross-ref`** — not consulted for this pass; the `sysser`/tunable store may correspond to
  a named `cSC3…` singleton in `re/ghidra_export_ios/`. Marked `[iOS-HINT]` opportunity, not done.

---

Note: I could not verify anything at C3+ (needs runtime or a second witness). All rows above are
static-decompilation reads only.
