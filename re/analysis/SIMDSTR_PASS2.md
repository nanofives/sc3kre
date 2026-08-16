# SIMDSTR.DLL — Second-pass results

All addresses are Ghidra VAs in `re/ghidra_export_simdstr/`. Export filenames omit the `0x` prefix (`1001b95d_FUN_1001b95d.c`), which is why Glob-by-`0x…` returned nothing — the bodies are present and were read directly.

## 1. Promoted rows (C1 → C2)

**`0x1001b95d` — read in full** ([CONFIRMED @ 0x1001b95d], 60 bytes). Signature `void __cdecl(undefined2 *param_1, undefined2 *param_2)` over a half-open range `[param_1, param_2)` of **16-bit elements**. Body:

```
puVar3 = param_1;
while (++puVar3 != param_2) {
    j = rand() % ((((int)puVar3 - (int)param_1) >> 1) + 1);   // j in [0, i]
    swap(*puVar3, param_1[j]);                                // 2-byte swap
}
```

`(puVar3 - param_1) >> 1` is the element index `i` (2-byte stride), so each step draws `j = rand() % (i+1)` and swaps element `i` with element `j` — a textbook **Fisher–Yates / Durstenfeld shuffle**. Sole callee: `rand()`. No globals, no other calls. Called **only** by `FUN_1001a26b` (the area-footprint builder) at its line 50, when its `char param_1 != 0`, passing `*this_00` (= `this+0x20`, the packed-tile vector start) and `this+0x24` (vector end). It randomizes the order of the `(x&0xFF)|((y&0xFF)<<8)` packed tiles produced earlier in that function. Fully mechanical, callee identified, name assigned → **C2**.

```csv
rva,subsystem,confidence,new_name,evidence
0x1001b95d,disaster-spread,C2,sc3_dstr_shuffle_tile_buffer,"Fisher-Yates shuffle of 16-bit packed-tile array [param_1,param_2): for i=1..n-1, j=rand()%(i+1), swap elem[i]/elem[j] (2-byte). Sole callee rand(); zero globals. Called only by FUN_1001a26b(this,flag!=0) on the this+0x20 packed-tile vector"
```

## 2. OPEN-list resolutions

### 2a. GZCLSID → disaster mapping (#2–#12) — 7 of 11 RESOLVED (shared-global + locality), 4 STILL OPEN

Method: each disaster's tunable loader writes a distinct block of `DAT_*` globals; I grepped the *consumers* of those globals. Every disaster's `{loader + consumers}` set falls in one contiguous address block, and that block contains **exactly one** class ctor. MSVC emits a class's methods contiguously, so the ctor in a disaster's method block is that disaster's class. This is stronger than the first pass's single toxic observation — it is now shared-`DAT_` evidence, not bare locality — but it is still inference from emission order, **not** a vtable-slot proof.

| # | GZCLSID | Ctor | Disaster | Evidence (all [CONFIRMED @ addr] reads; mapping = clustering inference) |
|---|---|---|---|---|
| 2 | `0x428fd431` | 0x100051e2 | **Fire** | block 0x100051e2–0x100064f6: parse `0x10005814`, loader `0x1000613e`, consumers `0x100054d8`/`0x100064f6` all read `DAT_1003967c` |
| 3 | `0x62a34670` | 0x10012de1 | **Tornado** | consumers `0x10012c47`/`0x100139c2` + loader `0x1001367e` read `DAT_10039ad8` |
| 5 | `0xe2fe8d38` | 0x1000d0d1 | **Riot** | cb `0x1000d680`, loader `0x1000dc3a`, consumers `0x1000df36`/`0x1000dfc5`/`0x1000e853` read `DAT_10039a08` |
| 6 | `0x22fe8d3e` | 0x10017c9a | **UFO** | loader `0x10018316`, consumers `0x100180ca`/`0x1001959c` read `DAT_10039e90` |
| 7 | `0x84c92cbe` | 0x1001eddd | **Parade** | loader `0x10020726`, consumer `0x1001f239` read `DAT_1003a274` |
| 8 | `0xc2fe8d43` | 0x10014d61 | **Toxic Cloud** | scorers `0x10014c98`/`0x10014fc8` + loader `0x10015751` read toxic `DAT_10039b5x`; ctor sits inside that block |
| 10 | `0x52fe8d51` | 0x1000a325 | **Locust** | loader `0x1000aa59`, consumers `0x1000a781`/`0x1000b798` read `DAT_100397d0` |

**Class #1 (`0x61f6abf5`) = SC3DisasterLayer manager** — the Misc/relief + `DisasterDescriptions` loader `0x100092d6` clusters with the layer ctor `0x10007978` (both in the 0x10007–0x10009 block), consistent with the manager owning the shared relief/description tunables. [locality only]

**STILL OPEN — classes #4, #9, #11, #12.**

| # | GZCLSID | Ctor | State |
|---|---|---|---|
| 4 | `0x22fe8d32` | 0x1000121c | no disaster string, no disaster-specific `DAT_` cluster |
| 9 | `0x52fe8d50` | 0x1001bd9d | idem |
| 11 | `0x52fe8d52` | 0x100106fe | idem |
| 12 | `0x52fe8d53` | 0x1000f036 | idem |

These four ctors are structurally identical (same `0x88`-class layout, same field-zeroing, `FUN_10022b70(+0x14,-1)` handle init), differ only by vtable pointers, embed no name, and read no disaster-tagged global. Their GZCLSIDs `0x52fe8d50/52/53` form a contiguous CLSID block *around* Locust's `0x52fe8d51`, so they are sibling disaster classes, but which specific types is **not determined** from the text export. **Blocker:** identity lives in each class's vtable[4] tick/init method, whose target is a pointer value in `.rdata` not present in the decompiled bodies. **Tool that breaks it:** `VtableDump.java` on the per-class final vtables (`PTR_FUN_100321f4`/`PTR_LAB_100321ac` #4, `PTR_FUN_100335c0`/`PTR_LAB_10033578` #9, `PTR_FUN_10032f18`/`PTR_LAB_10032ecc` #11, `PTR_FUN_10032d9c`/`PTR_LAB_10032d54` #12) → read the referenced method → see which loader/`DAT_` it touches.

### 2b. Who invokes the 8 tunable loaders — STILL OPEN, cause now pinned

Confirmed: all 8 loaders take **no parameters** (`FUN_1000613e(void)`, `FUN_10015751(void)`, `FUN_10020726(void)`, …) [CONFIRMED @ each], so they are **not** `__thiscall` vtable methods. A body grep finds each loader only in its own file (zero textual callers), and `globals.csv` holds no named pointer to any loader address. Therefore each loader is invoked through a **code-pointer stored in `.rdata`/`.data`** (a vtable slot or dispatch-table entry) that the text export does not capture. **Blocker:** the DATA xref / pointer value. **Tool:** `VtableDump.java` over the class vtables, or `pe_read.py` scanning `.rdata`/`.data` for the 8 loader addresses (`0x1000613e 0x100092d6 0x1000aa59 0x1000dc3a 0x1001367e 0x10015751 0x10018316 0x10020726`) — the holding slot resolves both this item and 2a in one pass.

### 2c. `CoCreateInstance` usage — RESOLVED

Ole32 is loaded **dynamically** (`LoadLibraryA("Ole32.dll")` + `GetProcAddress`), which is why no static import thunk xref existed. The one call site is `FUN_1002a3a4` [CONFIRMED @ 0x1002a3a4] — a **Windows `.lnk` shortcut resolver**, mechanically:

1. `strrchr(path,'.')`, `lstrcmpiA(ext, DAT_1003a580)` (the extension literal is raw `.rdata` at `DAT_1003a580`, not a labeled string; behaviour proves it is the shortcut extension).
2. `CoInitialize`; `CoCreateInstance(rclsid=&DAT_10034410, NULL, CLSCTX=1, riid=&DAT_10034400, &pShellLink)` — `DAT_10034410`/`DAT_10034400` are 16-byte GUIDs in `.rdata` (not in `strings.csv`); the vtable usage identifies them as **CLSID_ShellLink** + **IShellLinkA**.
3. `QueryInterface` → `IPersistFile` (`local_c`); `MultiByteToWideChar` the path; `IPersistFile::Load` (vtable+0x14); `IShellLink::Resolve` (vtable+0x4c, hwnd=0/flags=1); `IShellLink::GetPath` (vtable+0xc, buf, `0x105`, WIN32_FIND_DATA, 0). Returns target-path length or `-1`.

Caller `FUN_10029ced` [CONFIRMED @ 0x10029ced] is a **file-open method**: it calls `FUN_1002a3a4(this+8, buf, 0x104)` and, if resolution succeeds, opens the resolved target with `CreateFileA` (disposition map: param_2 0→CREATE_NEW, 1→CREATE_ALWAYS, 2→OPEN_EXISTING, 3→OPEN_ALWAYS, 4→TRUNCATE_EXISTING). So `CoCreateInstance` is pure **persistence-layer infrastructure** (transparent shortcut dereference before opening a data file) — **not disaster logic**, not disaster-CLSID instantiation.

### 2d. Message ids to other layers — STILL OPEN

No `PostMessage`/`SendMessage`/broadcast/notify pattern in any body; the only `*Message` strings are the three Locust `TimeBefore{First,Second,Third}PremonitionMessage` **tunable keys** (`0x10039930`/`0x1003990c`/`0x100398e8`), i.e. warning-timer names, not a dispatch API. Outbound notification, if any, is a numeric-id GZCOM message-server vtable call. **Blocker:** the layer's tick/update method and its message-server pointer — same `.rdata` vtable barrier as 2a/2b. **Tool:** VtableDump the layer-manager (#1) vtable, then read its tick method for a `(**(code**)(*msgSrv+N))(msgSrv, id, …)` pattern.

### 2e. Numeric tunable defaults — STILL OPEN (unchanged, correctly scoped)

In-code clamps/defaults are all that is visible (ToxicCloud min-clouds≥1, `MinCloudDuration` default 10, `ScorePerLevelIncrement` default 10, various `Max ≥ Min+1`). Shipped values live in `SC3DisasterLayer.INI` inside `SYS.PAK`. **Tool:** PAK extraction, not decompilation.

### 2f. SC3FireLayer / FlammabilityLayer — RESOLVED (unchanged): those strings are in SIMSERV.DLL; SIMDSTR carries only the `FireDisaster` event.

## 3. New findings (with RVAs)

1. **`FUN_1002a3a4` = `.lnk` shortcut resolver** [CONFIRMED @ 0x1002a3a4]; **`FUN_10029ced` = shortcut-aware file-open** wrapping `CreateFileA` [CONFIRMED @ 0x10029ced]. Suggested names: `sc3_dstr_resolve_shell_link`, `sc3_dstr_file_open`. These belong to the persistence/file infrastructure (same family as `FUN_1002a7b8`), not the disaster subsystem.
2. **Loaders are parameterless global-init `void` functions** (not vtable methods), invoked via `.rdata` code-pointers — pins the "no textual caller" fact to a concrete cause.
3. **Disaster-consumer function inventory** (beyond loaders) newly attributed by shared-global reads — candidates for the next C1→C2 batch:
   - Fire: `FUN_100054d8`, `FUN_100064f6` (read `DAT_1003967c`)
   - Riot: `FUN_1000df36`, `FUN_1000dfc5`, `FUN_1000e853` (read `DAT_10039a08`)
   - Locust: `FUN_1000a781`, `FUN_1000b798` (read `DAT_100397d0`)
   - UFO: `FUN_100180ca`, `FUN_1001959c` (read `DAT_10039e90`)
   - Tornado: `FUN_10012c47`, `FUN_100139c2` (read `DAT_10039ad8`)
   - Parade: `FUN_1001f239` (read `DAT_1003a274`)
4. **GZCLSID block structure**: disaster CLSIDs cluster as a `?2fe8d3?` family (`0x22fe8d32` #4, `0xe2fe8d38` #5, `0x22fe8d3e` #6, `0xc2fe8d43` #8) and a contiguous `0x52fe8d50..0x52fe8d53` run (#9/#10/#11/#12), with #10 = Locust confirmed inside that run.

## 4. Revised OPEN section (drop-in replacement for §7)

```
## 7. OPEN (undetermined + missing evidence)

- **GZCLSID → disaster mapping: 7 of 11 resolved.** Classes #2/#3/#5/#6/#7/#8/#10 are tied to
  Fire/Tornado/Riot/UFO/Parade/Toxic Cloud/Locust by shared-DAT reads + method-emission
  clustering (each disaster's loader+consumers occupy one contiguous block containing exactly
  one class ctor). This is emission-order inference, not a vtable proof. STILL OPEN: classes
  **#4 (0x22fe8d32), #9 (0x52fe8d50), #11 (0x52fe8d52), #12 (0x52fe8d53)** — no name string,
  no disaster-specific DAT cluster; identity is behind the vtable[4] tick/init method whose
  target is an .rdata pointer absent from the text export. Break with VtableDump.java on the
  four ctors' final vtables (PTR_FUN_100321f4 #4, _100335c0 #9, _10032f18 #11, _10032d9c #12).

- **Who invokes the 8 loaders.** Confirmed the loaders are parameterless (void) global-init
  functions, not thiscall vtable methods; zero textual callers and no named global holds them,
  so each is called via an .rdata/.data code-pointer. Break with VtableDump.java (class vtables)
  or pe_read.py scanning .rdata/.data for the 8 loader addresses.

- **Message ids sent to other layers.** No dispatch pattern in any body; only inbound queries
  confirmed. The three *PremonitionMessage strings are Locust timer keys, not an API. Needs the
  layer-manager (#1) tick method + its message-server pointer (behind the .rdata vtable).

- **CoCreateInstance usage — RESOLVED.** FUN_1002a3a4 is a .lnk shortcut resolver
  (CLSID_ShellLink + IShellLinkA + IPersistFile; Load/Resolve/GetPath), Ole32 loaded via
  LoadLibrary+GetProcAddress. Called by file-open method FUN_10029ced to dereference shortcuts
  before CreateFileA. Persistence infrastructure, not disaster logic.

- **Numeric tunable defaults.** Only in-code clamps visible; shipped values are in
  SC3DisasterLayer.INI inside SYS.PAK (needs PAK extraction).

- **SC3FireLayer/FlammabilityLayer** are in SIMSERV.DLL, not here (unchanged).
```

**One tool run — `VtableDump.java` over the twelve class vtables (or `pe_read.py` scanning `.rdata`/`.data` for the 8 loader addresses) — closes 2a (the last 4 classes), 2b (loader invokers), and 2d (message dispatch) together.**
