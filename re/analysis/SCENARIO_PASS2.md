# SCENARIO.DLL — Second pass

All RVAs are Ghidra virtual addresses in `re\ghidra_export_scenario\` (image base `0x10000000`). Every claim below is from a `.c` body actually read this pass.

## Cross-cutting facts established this pass (used throughout)

**Result-var resolvers** (both `[CONFIRMED]`): `FUN_10007206(this,node,&out)` resolves **arg0** as the destination variable index (`<0x200`) — the single-output helper. `FUN_1000792f(this,node,i,&out)` `[CONFIRMED @ 0x1000792f]` resolves **arg i** as a destination var index (`<0x200`) — the multi-output variant used by opcodes that write several vars.

**Value-producing opcode skeleton** (nearly every `cmdGet*`/math opcode): `if (exec_arg==0) return 1;` (dry/condition mode does nothing) `→ FUN_10007206` for dest slot `→` compute `→ store at this+0x70+dst*4`. This is the mechanical shape confirmed across all of them.

**New object-layout offsets** (SC3ScenarioLayer, extends the doc's §3 table), each from the handler cited:

| offset | meaning | evidence |
|---|---|---|
| `+0x20` | crime service (vtbl `+0x44` = get) | `0x10006fa8` |
| `+0x28` | land-value service (vtbl `+0x44`) | `0x10007356` |
| `+0x2c` | water service (vtbl `+0x50` = 5-out supply/demand query) | `0x1000656a`,`0x1000775a` |
| `+0x30` | pollution service (vtbl `+0x78`/`+0x7c`/`+0x80` selected by arg1) | `0x10007455` |
| `+0x34` | power service (vtbl `+0x58` supply, `+0x5c` demand, `+0x60` unpowered count) | `0x10006528`,`0x10007704` |
| `+0x3c` | budget/finance (vtbl `+0x10` funds, `+0x60` debt, `+0x4c(i)` RCI tax) | `0x10007807`,`0x1000789f` |
| `+0x40` | traffic service (vtbl `+0x5c` density query) | `0x10007849` |
| `+0x44` | aura/desirability service (vtbl `+0x44`, sign-extends a byte) | `0x10006f63` |
| `+0x5c/+0x60/+0x68/+0x6c` | date fields (months = `(0x6c-0x60)*12 - 0x5c + 0x68`) | `0x10008807` |
| `+0x8f8` | RNG object (`FUN_10010b68(this+0x8f8, lo, hi+1)`) | `0x10006eeb` |
| `+0x964` | GZCOM resource-enumeration service (vtbl `+0x18` open, `+0x20` get, `+0x24`/`+0x28` release) | `0x10009ffb` |
| `+0x980`/`+0x981` | popup-message byte flags | `0x10008c5d` |
| `+0x984` | **lock object** guarding goal/rank maps (vtbl `+0x04` acquire, `+0x08` release) | `0x100058d0`,`0x10005a84`,`0x10008662` |
| `+0x8bc` | referenced by resource serializer; nonzero → +4 bytes for resource type `0x2026960b` | `0x10009ffb` |
| `+0x8a0`/`+0x8a4` | child-node cursor pair walked by `FUN_1000741f` (next child node) | `0x1000741f` |

**Framework (`this+0x14`) vtbl slots seen this pass:** `+0x11c`/`+0x120`/`+0x124` = three building-layer catalogs; `+0x18c` = neighbor service; `+0x1e4` = date service (3 outputs).

---

## 1. Promoted rows (C1 → C2)

All 37 bodies were readable and reach C2 (body read, mechanics described, callees identified, name kept/confirmed). None had to stay C1.

```csv
rva,subsystem,confidence,new_name,evidence
0x100058d0,scenario-goals,C2,sc3_scenario_cmd_addgoal,"lock this+0x984; evals arg0=goalid arg1 arg2; FUN_1000e667 find/insert into goal map this+0x8c0; builds goal descriptor via FUN_10005791(ctor)+FUN_100057f9(init arg1,arg2); stores 16B value via FUN_1000cccd; status low-byte cleared"
0x10005a1a,scenario-goals,C2,sc3_scenario_cmd_allgoalsmet,"iterates goal map this+0x8c0 (header node; next at +8; FUN_10005a53 advance); returns 0 if any node status byte entry+0x18==0 else 1; condition op, no result var"
0x10005a84,scenario-flow,C2,sc3_scenario_cmd_addrankinfo,"lock this+0x984; evals arg0=key arg1 arg2; FUN_1000e667/FUN_1000cdcc insert into map this+0x8cc keyed by arg0; stores 8B value {arg1,arg2}"
0x10005c57,scenario-vm-control,C2,sc3_scenario_cmd_andcondition,"looks up cmdEndAnd id in DAT_1001eb78; FUN_1000741f walks child nodes until that terminator; dispatches each (FUN_10008d1a); if any returns 0 => result 0 and forces rest eval-only; AND with short-circuit"
0x10005cf8,scenario-vm-control,C2,sc3_scenario_cmd_assign,"FUN_10007206 dest=arg0; FUN_1000741f next child; FUN_10008d1a(child); if exec_arg==1 store child return into var[dst]; var[dst]=eval(child node)"
0x10005d47,scenario-vm-control,C2,sc3_scenario_cmd_beginblock,"looks up cmdEndBlock id; walks children to terminator; dispatches each with exec arg; returns last child result; sequential block"
0x10006528,scenario-query,C2,sc3_scenario_cmd_countunpoweredbuildings,"dest=arg0; var[dst]=power svc this+0x34 vtbl+0x60()"
0x1000656a,scenario-query,C2,sc3_scenario_cmd_countunwateredbuildings,"dest=arg0; water svc this+0x2c vtbl+0x50(5 out-params); var[dst]=first out"
0x10005e77,scenario-vm-math,C2,sc3_scenario_cmd_computepercentage,"dest=arg0; var[dst]=(eval(arg1)*100)/eval(arg2); arg2==0 => -1; const 100"
0x10006194,scenario-query,C2,sc3_scenario_cmd_countstructures,"dest=arg0; arg1=type; query obj new(0x10) FUN_100012d5(type); zero var; iterate framework+0x14 vtbl+0x11c/+0x120/+0x124 layers (iter +0x74/+0x14/+0x1c) counting matches; short-circuits per layer"
0x10005ee7,scenario-query,C2,sc3_scenario_cmd_countstructuresnearlocation,"dest=arg0; arg1=type arg2=x-1 arg3=y-1 arg4=radius; clamp x/y to this+0x18/0x1c; region via FUN_100060f9/FUN_10006149; same 3-layer count"
0x100063ef,scenario-query,C2,sc3_scenario_cmd_countstructureswithappearanceincity,"dest=arg0; args1-3=appearance triple; extent=max(this+0x18,0x1c)+1; FUN_10006314 counts buildings whose appearance 3-dwords (bldg vtbl+0x80 then +0x14) match, whole city"
0x10006474,scenario-query,C2,sc3_scenario_cmd_countstructureswithappearancenearlocation,"dest=arg0; args1-3=appearance triple, arg4=x-1 arg5=y-1 arg6=radius; clamp x/y; FUN_10006314 region-limited appearance match count"
0x100068e8,scenario-vm-math,C2,sc3_scenario_cmd_decrement,"dest=arg0; var[dst]-=1"
0x10006c4b,scenario-vm-math,C2,sc3_scenario_cmd_divide,"dest=arg0; var[dst]=eval(arg1)/eval(arg2); arg2==0 => -1"
0x10006eeb,scenario-vm-math,C2,sc3_scenario_cmd_generaterandomnum,"dest=arg0; lo=eval(arg1) hi=eval(arg2); equal=>that; else order and var=FUN_10010b68(this+0x8f8,lo,hi+1) inclusive range"
0x10006f63,scenario-query,C2,sc3_scenario_cmd_getaura,"dest=arg0; var[dst]=(signed char)aura svc this+0x44 vtbl+0x44()"
0x10006fa8,scenario-query,C2,sc3_scenario_cmd_getcrimevalue,"dest=arg0; var[dst]=crime svc this+0x20 vtbl+0x44() & 0xff"
0x10006fed,scenario-query,C2,sc3_scenario_cmd_getcurrentdate,"resolves 3 dests (FUN_1000792f args0/1/2); framework+0x14 vtbl+0x1e4(&d,&m,&y); stores y->var[arg0] d->var[arg1] m->var[arg2]"
0x10007455,scenario-query,C2,sc3_scenario_cmd_getpollutionvalue,"dest=arg0; arg1 selects 0/1/2 => pollution svc this+0x30 vtbl+0x78/+0x7c/+0x80(); arg1>2 fails"
0x10007356,scenario-query,C2,sc3_scenario_cmd_getlandvalue,"dest=arg0; var[dst]=landvalue svc this+0x28 vtbl+0x44()"
0x10007704,scenario-query,C2,sc3_scenario_cmd_getsurpluspower,"dest=arg0; var[dst]=power svc this+0x34 (vtbl+0x58 - vtbl+0x5c); clamped >=0"
0x1000775a,scenario-query,C2,sc3_scenario_cmd_getsurpluswater,"dest=arg0; water svc this+0x2c vtbl+0x50(5 outs); var[dst]=out[1]-out[2]"
0x10007807,scenario-query,C2,sc3_scenario_cmd_gettotaldebt,"dest=arg0; var[dst]=budget svc this+0x3c vtbl+0x60()"
0x10007849,scenario-query,C2,sc3_scenario_cmd_gettrafficdensity,"dest=arg0; traffic svc this+0x40 vtbl+0x5c(0,0,maxX,maxY,&buf+3,3); var[dst]=result>>0x18 (top byte)"
0x1000789f,scenario-query,C2,sc3_scenario_cmd_getrcitaxes,"resolves 3 dests (args0/1/2); budget svc this+0x3c vtbl+0x4c(0/1/2)&0xff => R/C/I tax rates into 3 vars"
0x10007ace,scenario-vm-control,C2,sc3_scenario_cmd_ifelse,"nodes [cond][then][else]; dispatch cond; if true: dispatch then(exec), skip else(arg0); if false: skip then(arg0), dispatch else(exec)"
0x10007b97,scenario-vm-math,C2,sc3_scenario_cmd_increment,"dest=arg0; var[dst]+=1"
0x10008462,scenario-neighbor,C2,sc3_scenario_cmd_isneighborconnection,"eval arg0,arg1 (&0xff); neighbor svc framework+0x14 vtbl+0x18c then vtbl+0x60(arg0,arg1)->bool; if arg2!=1 negate; condition op"
0x100084d3,scenario-neighbor,C2,sc3_scenario_cmd_isneighbordealpresent,"eval arg0(&0xff),arg1,arg2; new(0x28) dealbuf; neighbor svc vtbl+0x8c(arg0,dealbuf)->bool; true if found && buf+0x10==arg1 && buf+0x11==arg0; free; if arg2!=1 negate"
0x10008662,scenario-goals,C2,sc3_scenario_cmd_markgoalstatus,"lock this+0x984; eval arg0=goalid arg1=status; FUN_1000e667 find in map this+0x8c0; set *(node value ptr)+0x18 = (arg1!=0); returns found"
0x10008721,scenario-ui,C2,sc3_scenario_cmd_movecamera,"eval x,y (bounds this+0x18/0x1c), zoom(arg2, >4=>2); svc FUN_1001518f vtbl+0x5c; posts msg 0x435ee5c0, cond msg 0x635ee3c3, then msg 0x44a42474 {x,y,zoom} via FUN_100108a2"
0x1000881a,scenario-vm-math,C2,sc3_scenario_cmd_multiply,"dest=arg0; var[dst]=eval(arg1)*eval(arg2)"
0x100089e4,scenario-vm-control,C2,sc3_scenario_cmd_orcondition,"looks up cmdEndOr id; walks children to terminator; dispatches each; if any nonzero => result 1 and forces rest eval-only; OR with short-circuit"
0x10008c5d,scenario-ui,C2,sc3_scenario_cmd_popupmsg,"FUN_10006926(this); new(0x18) msg struct [0]=a0 [1]=a1 [+8b]=(a2==1) [3]=a3 [5]=a4 [4]=a5; if this+0x981 set this+0x980=1; posts msg 0xa44fab08 via FUN_100108a2"
0x100073de,scenario-query,C2,sc3_scenario_cmd_getmonthselapsed,"dest=arg0; var[dst]=FUN_10008807=(this+0x6c - this+0x60)*12 - this+0x5c + this+0x68"
0x1000c7d0,scenario-vm-math,C2,sc3_scenario_cmd_subtract,"dest=arg0; var[dst]=eval(arg1)-eval(arg2)"
```

---

## 2. OPEN-list resolutions

**① Which GZCLSID is the public SC3ScenarioLayer — STILL OPEN.**
No new binding is in the export. `SC3ScenarioLayer` appears in `strings.csv` only as the INI path `\Sys\SC3ScenarioLayer.INI` `[0x1001e820]`; no ASCII string is xref'd to `0x03de4ce4` or `0x03dfae27`. Cross-RE is negative: neither GZCLSID occurs anywhere in `re\ghidra_export_ios\`, and the iOS engine's scenario code is a different implementation (`LoadScript`, `_NewScenarioWindow` — script/JS driven, not a GZCLSID-registered layer), so the id does not transfer. **Blocker:** the ASCII-name→GZCLSID map lives in `SYS.PAK`/`CitySim.ini`, not in either binary export. Tool: unpack `SYS.PAK` (or `pe_read.py` on a config resource); alternatively `VtableDump.java` on the layer vtbl `PTR_FUN_1001a64c` to recover its interface IID.

**② Earthquake tunable floats `_DAT_1001a6d4/d8/dc` — STILL OPEN.**
Confirmed absent from `globals.csv` (grep of both `.csv` files: no match for `1001a6d4/d8/dc`). The refs exist only as operands in `FUN_1000aa2f`; the constants are raw `.rdata` float bytes that the function export does not carry. **Blocker:** need a raw section read. Tool: `pe_read.py` (or Ghidra `getFloat`) at RVAs `0x1001a6d4`, `0x1001a6d8`, `0x1001a6dc`.

**③ The 8 dword-pairs in `DAT_1001eb68` — RESOLVED.**
Consumer found: **`FUN_10009ffb`** `[CONFIRMED @ 0x10009ffb]`. It enumerates GZCOM resources through service `this+0x964` (vtbl `+0x18` open, `+0x20` get) and, for each enumerated resource key triple `{type,group,instance}` (read via `FUN_100148bc`), scans `DAT_1001eb68 … DAT_1001eb6c` two dwords at a time: `if (pair[0]==type && pair[1]==group)`. On match it QueryInterface's the resource for **IID `0x00199627`** (`(**local_28)(0x199627,&local_24)`), reads its serialized size (source vtbl `+0x10`), `operator_new`s a buffer, copies via source vtbl `+0x5c` → destination `param_1` vtbl `+0xac`. Special case at line 76: `if (type==0x2026960b && this+0x8bc != 0) size += 4`. `FUN_10005897` `[0x10005897]` is the static-dtor freeing the vector (`FUN_1000ca9e(&DAT_1001eb68)`); `DAT_1001eb6c` is its end pointer.
So `DAT_1001eb68` is a **`{resourceType-GZCLSID, groupID}` filter table** identifying which GZCOM resources belong to a scenario, and `FUN_10009ffb` is the **scenario-resource serializer/copier** (packs the matching resources into a target object). Note `0x23dfae5f` (a pair type) is the same GZCLSID used by `cmdSubRoutine`/`cmdRepeatRegular`, and `0x2026960b`/`0x62b9da24`/`0x26e732e0` share group `0x19a6cea1`.

**④ Disaster target layer identity — STILL OPEN (out of module).**
GZCLSIDs `0x621cda33`/`0x42963812`/`0xe2963828` are consumed as operands here; the module that registers them is not in this export. **Blocker:** `SIMDSTR.DLL`'s own director GZCLSID→factory table. Tool: export `SIMDSTR.DLL` with `ghidra_headless.ps1` and read its director ctor / `register_class` sites (same recipe as `FUN_100010b1`/`FUN_1000fd11` here).

**⑤ `LAB_*`-only handlers (cmdEqual, cmdGreaterThan, cmdLessThan, cmdMakeDialogText, cmdOfferBusinessDeal, cmdPlaySound, cmdIsOrdinanceEnacted, …) — STILL OPEN (not exported).**
Confirmed: glob for `{10006eb1,10007965,1000857a,1000860c,100088f5,10008bf3,100083fa}_*.c` returns **no files**. Ghidra never promoted these dispatch-table targets to functions, so no body exists to read. **Blocker:** the addresses are real code reached only via `DAT_1001eb10`. Tool: a headless script that `createFunction()` at each `LAB_*` RVA (from the §6 map) then re-`-Export`, after which their `.c` bodies become greppable.

**⑥ `Ole32`/`CoCreateInstance` usage — RESOLVED (not a scenario opcode).**
The only call site is **`FUN_100143e9`** `[CONFIRMED @ 0x100143e9]`: it takes a path, `strrchr('.')`, compares the extension to `DAT_1001e910` via `lstrcmpiA`, and on match `LoadLibraryA("Ole32.dll")` (`s_Ole32_dll_1001e904`) → `GetProcAddress` of `CoInitialize`/`CoUninitialize`/`CoCreateInstance` → creates a COM object (CLSID `&DAT_1001ad50`, IID `&DAT_1001ad40`), `IPersistFile::Load` (vtbl `+0x14`) the `MultiByteToWideChar`'d path, then `Resolve` (vtbl `+0x4c`) and `GetPath` (vtbl `+0xc`) into `local_124` — the **standard `IShellLink` Windows-shortcut resolver**. Its sole caller is `FUN_10013d36` (a path-normalization helper reading `this+8`). No `cmd*` opcode handler calls it. So `CoCreateInstance` in SCENARIO.DLL is generic filesystem/shortcut plumbing, unrelated to the scenario VM. (The extension string `DAT_1001e910` and the two 16-byte GUIDs `DAT_1001ad40`/`DAT_1001ad50` are raw `.rdata` and not in the export — `pe_read.py` would confirm they are `.lnk`, `CLSID_ShellLink`, `IID_IShellLinkA`, but the code shape already fixes the role.)

**⑦ `FUN_100011ab` 12-byte facet role — STILL OPEN (needs vtbl IIDs).**
Body read `[0x100011ab]`: sets **three** vtables on the 12-byte object — writes `PTR_LAB_1001a264` at `+0`, calls `FUN_10010100(obj+1)` (sub-object init), writes `PTR_LAB_1001a24c` at `+1`, then `PTR_LAB_1001a224` at `+0`. So it is a **triple-interface (multiple-inheritance) GZCOM facet**, and the layer director registers it as the second class (`0x03dfae27`). Which three interfaces it implements is not determinable from the export: the vtbl slots are `LAB_*` (unexported), and the identifying IID constants live in the QueryInterface method bodies / `.rdata`. **Blocker/tool:** `VtableDump.java` on `0x1001a224`, `0x1001a24c`, `0x1001a264`, then read (after force-defining) their QueryInterface handlers for the IID compares.

---

## 3. New findings (with RVAs)

- **New message ids posted via `FUN_100108a2`:** `cmdMoveCamera` posts `0x435ee5c0`, `0x635ee3c3` (conditional), and `0x44a42474` (payload `{x,y,zoom}`) `[CONFIRMED @ 0x10008721]`; `cmdPopUpMsg` posts `0x82…` no — posts **`0xa44fab08`** with an 18h-byte struct `[CONFIRMED @ 0x10008c5d]`.
- **Scenario-resource key table + serializer:** `DAT_1001eb68` is a `{type,group}` GZCLSID filter table consumed by `FUN_10009ffb`, which copies matching resources (QI IID `0x00199627`, size vtbl `+0x10`, read vtbl `+0x5c`, write dest vtbl `+0xac`) — a scenario-resource pack/serialize path `[CONFIRMED @ 0x10009ffb]`. End pointer `DAT_1001eb6c`; freed by `FUN_10005897`→`FUN_1000ca9e`.
- **Query-service map on the layer object** (offsets `+0x20`…`+0x44`, table in the "Cross-cutting facts" section) — nine distinct sim-query service pointers, each with the exact vtbl slot the opcodes call.
- **`this+0x984` is a lock/critical-section object** (acquire vtbl `+0x04`, release `+0x08`) taken around goal-map (`+0x8c0`) and rank-map (`+0x8cc`) mutation `[CONFIRMED @ 0x100058d0, 0x10005a84, 0x10008662]`.
- **`this+0x8f8` is an RNG object**; `cmdGenerateRandomNum` returns an **inclusive** `[lo,hi]` via `FUN_10010b68(this+0x8f8, lo, hi+1)` `[CONFIRMED @ 0x10006eeb]`.
- **Map value shapes:** goal map `this+0x8c0` value = 16 bytes with status byte at (value-ptr)`+0x18`; rank/end map `this+0x8cc` value = 8 bytes `{arg1,arg2}` `[CONFIRMED @ 0x100058d0, 0x10005a84]`. Note `cmdAddRankInfo` writes the **same map** `this+0x8cc` the doc labelled "end-scenario selection map" — that map is shared between rank-info and end-scenario selection.
- **`FUN_1000741f`** is the interpreter's **next-child-node cursor** over `this+0x8a0`/`+0x8a4` (node stride `0xc`, count at `node-4 +0x14`, base `+0x18`) `[CONFIRMED @ 0x1000741f]` — the mechanism behind every block/condition opcode's child walk.
- **`CoCreateInstance` = IShellLink `.lnk` resolver** (`FUN_100143e9`, caller `FUN_10013d36`), not scenario logic — see resolution ⑥.
- **Condition vs value opcodes distinguished:** `cmdAllGoalsMet`, `cmdIsNeighborConnection`, `cmdIsNeighborDealPresent`, `cmdMarkGoalStatus` return a boolean **directly** (no result-var write); the `cmd*` predicate family uses `arg2==1` as a "do-not-negate" flag (negates the test otherwise) `[CONFIRMED @ 0x10008462, 0x100084d3]`.

---

## 4. Revised OPEN (drop-in replacement for §9)

- **Which GZCLSID is the public SC3ScenarioLayer.** `0x03de4ce4` (2480-B object) vs `0x03dfae27` (12-B facet); no ASCII name binds either, and the ids do not appear in the iOS export. Needs the `SC3ScenarioLayer`→GZCLSID map in `SYS.PAK`/`CitySim.ini` (unpack `SYS.PAK`), or the layer vtbl interface IID (`VtableDump.java` on `PTR_FUN_1001a64c`).
- **Earthquake tunable floats `_DAT_1001a6d4/d8/dc`.** Confirmed not in `globals.csv`; raw `.rdata` floats. Needs `pe_read.py`/`getFloat` at those three RVAs.
- **Disaster target layer identity.** GZCLSIDs `0x621cda33`/`0x42963812`/`0xe2963828` consumed here but registered in `SIMDSTR.DLL`. Needs a SIMDSTR export + its director GZCLSID→factory table.
- **`LAB_*`-only opcode handlers** (`cmdEqual`, `cmdGreaterThan`, `cmdLessThan`, `cmdMakeDialogText`, `cmdOfferBusinessDeal`, `cmdPlaySound`, `cmdIsOrdinanceEnacted`, `cmdIsBusinessDealActive`, `cmdEnableDisableBusinessDeal`, `cmdEnable/DisableNewNeighborDeals`, `cmdEnableDisableDisasters`, `cmdSetResultsDlgText`). Not exported (glob returned none). Needs `createFunction()` at each §6 `LAB_*` RVA then re-`-Export`.
- **`FUN_100011ab` 12-byte triple-vtable facet.** Three interfaces (`1001a224`/`a24c`/`a264`); which IIDs is unknown. Needs `VtableDump.java` on those three vtables plus reading their QueryInterface IID compares.
- **`DAT_1001eb68` group id `0x19a6cea1` and per-type meanings.** The `{type,group}` table's role (scenario-resource pack) is resolved, but the semantic identity of each individual `type` GZCLSID (goals, deals, script blocks, etc.) beyond `0x23dfae5f`=subroutine is not pinned. Needs SIMUI/base-module registries, or `SYS.PAK` resource inspection.
- **`cmdMoveCamera`/`cmdPopUpMsg` message consumers.** New msg ids `0x435ee5c0`/`0x635ee3c3`/`0x44a42474`/`0xa44fab08` are posted here; their receivers (SIMUI/camera) are out of module. Needs an xref sweep for these ids across the other DLL exports.
(raw JSON: C:\Users\maria\AppData\Local\Temp\fleet-delegate-bcf0720ca8b041879d9ddbfe155e829d.json)
