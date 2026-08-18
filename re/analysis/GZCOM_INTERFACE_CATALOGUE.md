# GZCOM_INTERFACE_CATALOGUE.md — named C++ interfaces for SC3K, and the dword anchors they gave us

**Source:** [`0xC0000054/sc3k-gzcom-dll`](https://github.com/0xC0000054/sc3k-gzcom-dll) (LGPL-2.1-or-later,
Nicholas Hayes, 2025). A GZCOM plugin SDK for SimCity 3000. Its 111 headers were **derived from the
SimCity 3000 Unlimited _Linux_ build, which shipped with debug symbols enabled** — the author
un-decorated the GCC-mangled C++ method names into interface declarations.

**Why this matters for us:** a third oracle, and the strongest one yet.

| Oracle | Arch | Version relation to SC3U.exe | Names |
|---|---|---|---|
| `re/ghidra_export_ios/` (SimCity Deluxe 2011) | ARMv7 | partial re-engineer, 11 yrs later | `goZoneLayer`, `cSC3…` |
| **sc3k-gzcom-dll headers** | **x86** | **same product (SC3KU), same source tree, GCC vs MSVC** | **`cISC3ZoneLayer`, full signatures** |

Per the calibrated rule in `SIM_LAYERS_XREF.md` (iOS algorithms transfer, iOS struct layouts do not),
this oracle is held to the same bar: header names are `[GZ-HINT]` until an SC3U-side witness confirms
them. **The headers happen to carry witnesses**, which is the substance of this document.

> **License note.** The repo is LGPL-2.1-or-later and is NOT vendored into this tree (it was cloned to
> a scratchpad). What is recorded here are *facts read from it* (interface names, IID values) plus our
> own SC3U-side evidence. `sc3kre` stays free of third-party LGPL source.

---

## 1. The breakthrough: interface IDs DO exist as dwords in the shipped binaries

`MODULE_MAP.md` claim 3 stated: *"No `0x41F836xx` GZCLSID dword occurs in ANY shipped binary … Class ids
exist only as ASCII in `SYS.PAK` / `CitySim.ini` and are parsed at runtime."*

That finding is **correct but was over-generalised**. It tested *class* ids (GZCLSID) with an assumed
`0x41F836xx` prefix. The headers hand us the **interface** ids (GZIID) and **layer type** ids, and those
are present as immediates in `.text` in abundance.

Method: extracted all 25 `static const uint32_t` constants from the headers, byte-scanned all 36 shipped
binaries plus `original\SC3U.exe` for each as a little-endian dword, converted file offsets to RVAs via
each PE's section table, resolved the containing function from `functions.csv`, then **re-verified every
hit by grepping the constant literal out of that function's exported decompilation**.

```
853 raw dword hits across 36 binaries
611 in .text
260 high-entropy AND inside a function we already track
243 of those 260 confirmed present in the decompiled text   <-- the usable anchors
150 distinct functions
```

**Entropy caveat (important).** Four constants are small values and their hits are mostly arithmetic
noise, not IID references: `GZIID_cIGZSystemService=0x6c` (315 hits), `GZIID_cISC3App=0xfa2` (110),
`GZIID_cIGZMessageTarget=0x58d` (65), `GIID_cIGZWinMgr=0x5a4` (26), `GZIID_cIGZResourceKeyList=0x199656`,
`GZIID_cIS3DValve=0xf1ec30`, `GZIID_cISC3BaseAdvisor=0x13dee82`. Only hits `>= 0x01000000` were treated as
evidence. Small-value constants are only trusted when they appear *inside a confirmed QueryInterface
chain* (see §2), where the surrounding shape disambiguates them.

### The constant table (verbatim from the headers)

| Constant | Value | Hit modules (high-entropy only) |
|---|---|---|
| `GZIID_cISC3ValveLayer` | `0x40a42f1c` | SIMRCI, SIMMISC, SIMADV, SIMECO, SIMUI, SIMSPR, SimTransit, AUDIO |
| `LayerType_cISC3ValveLayer` | `0x80f1e6d3` | (same 8) |
| `GZIID_cISC3AuraLayer` | `0x4259c018` | SIMMISC, SIMRCI, SIMDSTR, SIMADV, SIMSERV, SIMSPR, SCENARIO, AUDIO |
| `LayerType_cISC3AuraLayer` | `0x0259c03f` | (same 8) |
| `GZIID_cISC3CityCellMapBase` | `0x817ab319` | SIMECO, SIMSERV, SIMRCI, SIMMISC, SIMGEOM, SIMSPR, SIMUTIL |
| `GZIID_cISC3CityCellMap_Sint8` | `0x40ace11f` | SIMMISC |
| `GZIID_cISC3CityCellMap_Sint16` | `0xa0ace0fb` | SIMECO, SIMMISC, SIMRCI, SIMSERV |
| `GZIID_cISC3CityCellMap_Sint32` | `0x40ace0d5` | SIMECO, SIMSERV |
| `GZIID_cISC3CityCellMap_Uint8` | `0xa0ace10a` | SIMGEOM, SIMRCI, SIMSERV, SIMSPR, AUDIO |
| `GZIID_cISC3CityChangeReceiver` | `0x215b29c5` | SIMECO, SIMGEOM, SIMMISC, SIMRCI, SIMSERV |
| `GZIID_cISC3OccManIterator` | `0x41bdf76b` | (no high-entropy in-function hit) |
| `GZIID_cISC3OccManIteratorTest` | `0xa1c085db` | SIMNTWRK, SIMSPR |
| `GZIID_cIGZWin` | `0x22ba0121` | GZWIND, SIMUI, SIMSPR, SIMBABLD, SIMINIT, SC3U.exe |
| `GZIID_cIGZDBSegment` | `0xc019963e` | GZResourceD, SC3U.exe, SIMBABLD, SIMSPR, SIMINIT |
| `GZIID_cIGZDBRecord` | `0x4019960a` | GZResourceD, SC3U.exe, SIMBABLD, SIMSPR |
| `GZSERVID_cIGZWinMgr` | `0xa417445e` | 17 modules |
| `GZCLSID_cIGZResourceKeyList` | `0x801ed267` | GZResourceD, SIMINIT, Baapp.exe |
| `kGZMessageWndProcHook` | `0x5a4fc3d5` | SC3U.exe, GZGraphicD, SIMBABLD |
| `GZIID_cIGZMessageTarget` | `0x58d` | low-entropy — trusted only inside QI chains |
| `GZIID_cIGZSystemService` | `0x6c` | low-entropy |
| `GZIID_cISC3App` | `0xfa2` | low-entropy |
| `GZIID_cISC3BaseAdvisor` | `0x13dee82` | low-entropy, but SIMADV + SIMCITY only, and one QI chain |
| `GZIID_cIS3DValve` | `0xf1ec30` | low-entropy |
| `GIID_cIGZWinMgr` | `0x5a4` | low-entropy |
| `GZIID_cIGZResourceKeyList` | `0x199656` | low-entropy |
| **GZIID_cISC3CityLayer** | **`0x206c6e7c`** | **NOT in the SDK headers — named by us in §12c** |
| ? unnamed | `0x81c0cb7c` | not in the headers; 16 implementors, 8 not city layers (U-044) |

---

## 2. Classes pinned by their QueryInterface — 23 functions, C3

A `QueryInterface` implementation enumerates exactly the interfaces its class implements, so a function
that tests a known GZIID *identifies the class*. 23 such functions were found and committed to
`functions.csv` at **C3** (two independent witnesses: the SDK header constant + the decompiled shape).

The witness pattern, `SIMECO.DLL` `0x1000462e` (47 bytes) `[CONFIRMED @ 0x1000462e]`:

```c
if (((param_1 == 1) || (param_1 == 0x40ace0d5)) || (param_1 == -0x7e854ce7)) {
    *param_2 = this;
    uVar2 = (**(code **)(*(int *)this + 4))();     /* AddRef */
    uVar1 = CONCAT31((int3)((uint)uVar2 >> 8),1);
}
```

`1` = `cIGZUnknown`, `0x40ace0d5` = `GZIID_cISC3CityCellMap_Sint32`, `-0x7e854ce7` = `0x817ab319` =
`GZIID_cISC3CityCellMapBase`. The accepted set is exactly the header's declared hierarchy
(`cISC3CityCellMap<T> : cISC3CityCellMapBase : cIGZUnknown`). This is `cISC3CityCellMap<int32_t>::QueryInterface`.

| Module | RVA | committed name | identifying IID |
|---|---|---|---|
| SIMECO | `0x1000462e` | `sc3_citycellmap_sint32_queryinterface` | `_Sint32` + Base |
| SIMECO | `0x1000465d` | `sc3_citycellmap_sint16_queryinterface` | `_Sint16` + Base |
| SIMECO | `0x1000468c` | `sc3_citycellmap_sint32_queryinterface` | `_Sint32` + Base |
| SIMGEOM | `0x10011525` | `sc3_citycellmap_uint8_queryinterface` | `_Uint8` + Base |
| SIMMISC | `0x100012dc` | `sc3_citycellmap_sint8_queryinterface` | `_Sint8` + Base |
| SIMMISC | `0x1000130b` | `sc3_citycellmap_sint16_queryinterface` | `_Sint16` + Base |
| SIMRCI | `0x1001b51e` | `sc3_citycellmap_sint16_queryinterface` | `_Sint16` + Base |
| SIMRCI | `0x1002e9ab` | `sc3_citycellmap_uint8_queryinterface` | `_Uint8` + Base |
| SIMSERV | `0x10006251` | `sc3_citycellmap_uint8_queryinterface` | `_Uint8` + Base |
| SIMSERV | `0x10006280` | `sc3_citycellmap_sint16_queryinterface` | `_Sint16` + Base |
| SIMSERV | `0x10009ca2` | `sc3_citycellmap_sint32_queryinterface` | `_Sint32` + Base |
| SIMSPR | `0x1004ba87` | `sc3_citycellmap_uint8_queryinterface` | `_Uint8` + Base |
| SIMUTIL | `0x10003391` | `sc3_citycellmapbase_queryinterface` | Base |
| **SIMRCI** | **`0x1002ef6b`** | **`sc3_valvelayer_queryinterface`** | **`GZIID_cISC3ValveLayer`** |
| SIMADV | `0x1001d401` | `sc3_baseadvisor_queryinterface` | `GZIID_cISC3BaseAdvisor` |
| GZResourceD | `0x1000b434` | `gz_dbsegment_queryinterface` | `GZIID_cIGZDBSegment` |
| GZResourceD | `0x1000b79b` | `gz_dbrecord_queryinterface` | `GZIID_cIGZDBRecord` |
| SC3U.exe | `0x004660d7` | `gz_dbsegment_queryinterface` | `GZIID_cIGZDBSegment` |
| SC3U.exe | `0x0046643e` | `gz_dbrecord_queryinterface` | `GZIID_cIGZDBRecord` |
| SIMBABLD | `0x120505e1` | `gz_dbsegment_queryinterface` | `GZIID_cIGZDBSegment` |
| SIMBABLD | `0x1205091e` | `gz_dbrecord_queryinterface` | `GZIID_cIGZDBRecord` |
| SIMSPR | `0x100594c8` | `gz_dbsegment_queryinterface` | `GZIID_cIGZDBSegment` |
| SIMSPR | `0x10059805` | `gz_dbrecord_queryinterface` | `GZIID_cIGZDBRecord` |

### The RCI demand engine class is now located

`SIMRCI.DLL` `0x1002ef6b` (77 bytes) `[CONFIRMED @ 0x1002ef6b]`:

```c
if (param_1 == 1) { *param_2 = (uint)this; }
else {
  if ((param_1 != 0x58d) && (param_1 != 0x206c6e7c)) {
    if (param_1 == 0x40a42f1c) { *param_2 = (uint)this; }        /* GZIID_cISC3ValveLayer */
    if (param_1 != -0x7e3f3484) { return param_1 & 0xffffff00; }
  }
  *param_2 = -(uint)(this != (void *)0x0) & (int)this + 4U;      /* second base at +4 */
}
```

Mechanical reading: the object answers to `cIGZUnknown` and `GZIID_cISC3ValveLayer` **at offset 0**, and to
`0x58d` (`GZIID_cIGZMessageTarget`), `0x206c6e7c` and `0x81c0cb7c` at **`this+4`**. So `cSC3ValveLayer`
multiply-inherits, with a message-target base subobject at `+4`. `0x58d` is low-entropy on its own but is
unambiguous here — it sits in a QI chain alongside a confirmed high-entropy IID.

This is the class behind `SC3ValveLayer` / `Sys\SC3ValveLayer.ini` and the `goValveLayer` the iOS oracle
models in `SIM_LAYERS_XREF.md` §S5. Its vtable is `*(int *)this` and the header gives the 11 declared
methods to walk it with: `EndOfMonth`, `CreateNewValve`, `GetValvePointer`, `AddValveToLayer`,
`GetAgentSupplyEffect`, `GetAgentDemandEffect`, `GetDensity`, `GetTaxableResidentialDensity`,
`GetTaxableCommercialDensity`, `GetTaxableIndustrialDensity`, `DebugSetValve`.

`0x206c6e7c` and `0x81c0cb7c` are **unknown IIDs** not present in the SDK headers → logged in
`UNCERTAINTIES.md`.

---

## 3. Layer acquisition sites — 127 functions annotated `[GZ-IID]`

The remaining 206 verified hits sit in 127 functions that *consume* a layer rather than implement it. The
recurring idiom is a `LayerType_X` immediate followed ~0x18 bytes later by the matching `GZIID_X`: fetch
the layer by its type id, then `QueryInterface` it for the typed pointer.

`functions.csv` notes for these rows now carry `[GZ-IID] literal interface ids present: <const>=<value> @<rva>`.
Confidence was **not** raised — knowing which layer a function acquires is not the same as knowing what it
does with it.

The distribution independently corroborates existing subsystem assignments:

| Evidence | Corroborates |
|---|---|
| `GZIID_cISC3BaseAdvisor` occurs in **SIMADV + SIMCITY only** | SIMADV = the advisor subsystem |
| all 7 `cISC3AdvisorFor*` advisors in SIMADV acquire ValveLayer + AuraLayer (`sc3_advisor_*` @ `0x1000ce3b`, `0x1001215d`, `0x1001588a`, `0x1001816b`) | advisors read RCI demand + aura, per `SIMADV.md` |
| `LayerType_cISC3AuraLayer` concentrated in SIMMISC's `sc3_query_bu*` cluster (7 sites) | `MODULE_MAP.md`: SIMMISC = S12 aura |
| `GZIID_cISC3ValveLayer` in `sc3_budget_l*` `0x100067c7` + `sc3_financeg*` `0x10026795` | S10 budget reads RCI demand |
| `GZIID_cISC3ValveLayer` in `SimTransit` `sc3_transit_*` `0x10003d93` | S6 traffic reads demand |
| `GZIID_cISC3ValveLayer` in SIMECO `sc3_pollutio*` `0x10005844` | S? pollution reads demand |
| `GZIID_cISC3OccManIteratorTest` ×18 across 6 `sc3_ntwrk_re*` registration functions in SIMNTWRK | occupant-iterator predicates registered at init |

---

## 4. Interface inventory — 65 SC3 interfaces, 1,379 virtual methods

Full signatures are in the upstream repo. Method counts are declared-virtuals per header (not
vtable slot counts, which include inherited entries).

**Layers** — cross-referenced to our module map and subsystem codes:

| Interface | methods | base | module (per `MODULE_MAP.md`) | our subsystem |
|---|---:|---|---|---|
| `cISC3PollutionLayer` | 51 | `cISC3CityCellMap<uint32_t>` | SIMECO | pollution-layer |
| `cISC3ResidentialLayer` | 38 | `cIGZUnknown` | SIMRCI | S4/S5 |
| `cISC3WeatherLayer` | 32 | `cIGZUnknown` | — `[UNMAPPED]` | — |
| `cISC3BuildingLayer` | 26 | `cIGZUnknown` | SIMGEOM | S3 |
| `cISC3BudgetLayer` | 25 | `cIGZUnknown` | SIMMISC | S10 |
| `cISC3ZoneLayer` | 20 | `cISC3CityCellMap<uint8_t>` | SIMRCI | S4 |
| `cISC3CityLayer` | 15 | `cIGZUnknown` | — (the layer contract) | — |
| `cISC3DisasterLayer` | 15 | `cIGZUnknown` | SIMDSTR | S11 |
| `cISC3PoliceLayer` | 14 | `cISC3CityCellMap<uint8_t>` | SIMSERV | S9 |
| `cISC3OrdinanceLayer` | 12 | `cIGZUnknown` | SIMMISC | S14 |
| `cISC3FireLayer` | 11 | `cISC3CityCellMap<uint8_t>` | SIMSERV | S9 |
| **`cISC3ValveLayer`** | **11** | `cIGZUnknown` | **SIMRCI (class @ `0x1002ef6b`)** | **S5** |
| `cISC3WorldLayer` | 5 | `cIGZUnknown` | SIMMISC | S1 |
| `cISC3LandValueLayer` | 1 | `cISC3CityCellMap<uint8_t>` | — `[UNMAPPED]` | — |
| `cISC3AuraLayer` | 1 | `cISC3CityCellMap<int8_t>` | SIMMISC | S12 |
| `cISC3CrimeLayer` | 1 | `cISC3CityCellMap<uint8_t>` | SIMSERV | S9 |
| `cISC3CommercialLayer` | 1 | `cIGZUnknown` | SIMRCI | S4/S5 |
| `cISC3IndustrialLayer` | 1 | `cIGZUnknown` | SIMRCI | S4/S5 |
| `cISCNScenarioLayer` | — | — | SCENARIO | scenario |
| `cISSStrtSimLayer` | — | — | STRTSIM | startup sim |

Note the layer classes are **cell maps**: `cISC3CityCellMap<T>` is the per-tile raster base, `T` being the
per-cell type (`uint8_t` zones/police/crime/landvalue, `int8_t` aura, `uint32_t` pollution). That is why the
`CityCellMap` QueryInterface functions turn up in seven different modules — each layer module instantiates
the template.

`SIM_LAYERS_XREF.md` lists no `cISC3PowerLayer` / `cISC3TrafficLayer` header, and none exists upstream —
those are `[UNMAPPED]` in the SDK. Power stays anchored the way `POWER_GRID.md` did it (the `0x258` cap).

**Non-layer interfaces of note:**

| Interface | methods | what it is |
|---|---:|---|
| `cISC3City` | **159** | the city god-object |
| `cISC3CitySpriteCellMap` | 104 | sprite grid |
| `cISC3DirtBag` | 88 | SIMDIRT — the "dirt" system |
| `cISC3Occupant` | 69 | the occupant base (S3) |
| `cISC3CitySchemeMgr` | 45 | colour/scheme manager |
| `cISC3OccupantManagerAnim` | 41 | matches the `OccManAnim::` asserts already seen in SC3U strings |
| `cISC3OccupantAttrib` | 41 | occupant attributes |
| `cISC3WinCityView` | 38 | main city window |
| `cISC3BaseAdvisor` | 35 | advisor base (SIMADV, QI @ `0x1001d401`) |
| `cISC3App` | 34 | app object |
| `cISC3AppPreferences` | 34 | preferences |
| `cISC3Valve` | 31 | a single supply/demand valve |
| `cISC3Internet` | 26 | in-game internet |
| `cISC3PetitionerManager` | 9 | petitioners (matches `sc3_petition*` @ `0x1001e6af`) |
| `cISC3DepartmentBudget` | 9 | per-department budget |
| `cISC3AgentTypeTree` | 9 | **the agent-type hierarchy** `SIM_LAYERS_XREF.md` identified as the layer registry |

Header file counts: **111 total** = 32 `cIGZ*` framework + 67 `cISC3*`/`cISCN*`/`cISS*` game (65 of which
parse to a class declaration with a method list) + 12 utility (`cRZBaseString`, `cRZCOMDllDirector`,
`GZServPtrs`, …).

The 32 `cIGZ*` framework headers (`cIGZCOM`, `cIGZMessageServer`, `cIGZDBSegment`, `cIGZFileSystem`,
`cIGZResourceManager`, `cIGZLanguageManager`, `cIGZCheatCodeManager`, …) confirm SC3K and SC4 share the GZ
framework, so SC4-community knowledge of GZCOM/DBPF partly transfers.

---

## 5. Reproducing this

Scripts used live in the session scratchpad, not the repo (they depend on a scratchpad clone). The
sequence:

1. `git clone --depth 1 https://github.com/0xC0000054/sc3k-gzcom-dll` into a scratchpad (do NOT vendor).
2. Regex the headers for `static const uint32_t (\w+) = (0x[0-9a-fA-F]+);`.
3. Byte-scan every `Apps\*.dll|exe` + `original\SC3U.exe` for each value as a little-endian dword.
4. Convert file offset → RVA via the PE section table (`ImageBase + VirtualAddress + (off - PointerToRawData)`).
5. Resolve the containing function against `functions.csv` (`rva <= X < rva+size`).
6. **Re-verify** by grepping the constant (both `0x…` and Ghidra's signed `-0x…` form) out of
   `re/ghidra_export_<module>/functions/<rva>_*.c`. A hit that fails this step is discarded.

Step 6 is what makes these `[CONFIRMED]` rather than `[GZ-HINT]`.

## 6. What this does not give us

- **No class ids (GZCLSID).** The headers carry interface ids, not the per-class factory ids. `MODULE_MAP.md`
  claim 3 stands for GZCLSID: those are still ASCII in `SYS.PAK` / `CitySim.ini`, parsed at runtime.
- ~~**No vtable slot order.**~~ **REFUTED 2026-08-17 — see §7.** Declaration order IS vtable order, proven
  on three classes across 29 slots with zero mismatches.
- **No struct field offsets.** Same rule as the iOS oracle: layouts do not transfer.
- **Incomplete coverage.** Upstream says only a small number of interfaces are decoded and the message
  system values are mostly unknown. 65 SC3 interfaces here vs. the full engine.

---

## 7. The cSC3ValveLayer vtable walk — declaration order IS vtable order (U-042 resolved)

`SIMRCI.DLL`. Two vtables, **29 slots, zero mismatches** against the SDK headers. This both resolves U-042
and opens the S5 RCI demand engine.

Finding them: scan `.rdata` for a dword-aligned pointer to the known `QueryInterface` `0x1002ef6b` → one hit
at `0x1004cee4`, which is therefore slot 0 of the primary vtable. The secondary vtable was found from
`0x1002df6a` (`mov eax,0x80f1e6d3; ret`, a function returning `LayerType_cISC3ValveLayer`), which the header
places at `cISC3CityLayer` slot 15, giving base `0x1004ced8 - 0x3c = 0x1004ce9c`. The two vtables are
adjacent: `0x1004ce9c + 18*4 = 0x1004cee4`.

### `cISC3ValveLayer` vtable @ `.rdata` `0x1004cee4`

| slot | RVA | size | header method | mechanical evidence |
|---:|---|---:|---|---|
| 0 | `0x1002ef6b` | 77 | `QueryInterface` | accepts `GZIID_cISC3ValveLayer` |
| 1 | `0x1004312b` | 23 | `AddRef` | increments `this+8` |
| 2 | `0x1002efb8` | 48 | `Release` | tests `this+8` |
| **3** | **`0x1002efe8`** | **560** | **`EndOfMonth(void)->bool`** | **the demand regulator, see below** |
| 4 | `0x1002edbe` | 138 | `CreateNewValve(u32,u32,void**)` | `QueryInterface(clsid 0xc0f1ec40, iid 0xf1ec30 = GZIID_cIS3DValve)` then `cISC3Valve+0xc` (`Init`) |
| 5 | `0x1002eeac` | 53 | `GetValvePointer(u32,u32,void**)` | 3 args, map lookup at `this+0x18` |
| 6 | `0x1002ee48` | 100 | `AddValveToLayer(cISC3Valve*)` | 1 ptr arg, keys on `cISC3Valve+0x20` (`GetId`), Releases old + AddRefs new |
| 7 | `0x1002eee1` | 69 | `GetAgentSupplyEffect(u32,u32)->i16` | returns `int16` at record `+0xc` |
| 8 | `0x1002ef26` | 69 | `GetAgentDemandEffect(u32,u32)->i16` | identical body, returns `int16` at record `+0xe` |
| 9 | `0x1002e9da` | — | `GetDensity(u32,u32,u8&)` | `ret 0xc` (3 args), forwards all three to `[this+0x38]` vtable `+0x34` |
| 10 | `0x1002df70` | 4 | `GetTaxableResidentialDensity(void)` | `mov eax,[ecx+0x40]; ret` |
| 11 | `0x1002df74` | 4 | `GetTaxableCommercialDensity(void)` | `mov eax,[ecx+0x44]; ret` |
| 12 | `0x1002df78` | 4 | `GetTaxableIndustrialDensity(void)` | `mov eax,[ecx+0x48]; ret` |
| 13 | `0x1002de20` | 3 | `DebugSetValve(str*,str*,str*)` | `ret 0xc` (3 args) — **stubbed out in retail** |
| 14 | `0x1002df7c` | 28 | *(scalar deleting dtor)* | not in the header, as expected |

Slots 15-28 are 14 copies of `0x10044c20` = `jmp [0x1004b120]` (an import thunk, `__purecall` shape) and
belong to a different, abstract vtable. Our vtable ends at slot 14.

### `cISC3CityLayer` vtable @ `.rdata` `0x1004ce9c` — the `this+4` base subobject

Slots 0-2 are **MSVC adjustor thunks** — `sub ecx, 4 ; jmp <primary>` — the compiler's signature for a
secondary base at object offset +4. That alone proves what `this+4` is.

| slot | RVA | header method | mechanical evidence |
|---:|---|---|---|
| 0-2 | `0x100308a6/ae/b6` | `QueryInterface`/`AddRef`/`Release` | `sub ecx,4 ; jmp` to each primary |
| 3 | `0x100312a2` | `DoMessage(cGZMessage&)` | `xor al,al; ret 4` → 1 arg, returns false |
| 4 | `0x100308be` | `DoQueryInfo(cGZMessage&,cIGZUnknown*)` | 2 args, dispatches on `*edx == 0x2dc6d7f` |
| 5 | `0x1002dff3` | `StaticInit(cISC3CityDefinition*)` | our `sc3_valve_load_tuning`, loads `Sys\SC3ValveLayer.ini` |
| 6 | `0x1002e7e6` | `StaticShutdown(void)` | our `sc3_valve_clear_tables` |
| 7 | `0x1002e9f6` | `Init(cISC3City*)` | 396 B |
| 8 | `0x1002e9f1` | `Init(cISC3City*,cISC2Importer*)` | `mov al,1; ret 8` → **2 args, stubbed**: no SC2 import for this layer |
| 9 | `0x1002e887` | `Init(cISC3City*,cIGZDBSegment*)` | 292 B — the **load** path |
| 10 | `0x1002eb82` | `Save(cISC3City*,cIGZDBSegment*)` | 263 B — the **save** path |
| 11 | `0x1002ec89` | `SimulationBegin(void)` | 51 B |
| 12 | `0x1000e7b3` | `SimulationEnd(void)` | `mov al,1; ret` → **0 args**, stubbed |
| 13 | `0x1002ecbc` | `Shutdown(void)` | 258 B |
| 14 | `0x1002f218` | `GetManipulator(...)` | our `sc3_valve_get_or_create` |
| 15 | `0x1002df6a` | `GetLayerType(void)->u32` | `mov eax,0x80f1e6d3; ret` = `LayerType_cISC3ValveLayer` |
| 16 | `0x1003d791` | `DebugClassTag(cIGZString&)` | `xor al,al; ret 4` → 1 arg, stubbed |
| 17 | `0x1003d791` | `DebugTypeTag(cIGZString&)` | same function, stubbed |

`Init(City*,DBSegment*)` at slot 9 and `Save` at slot 10 are the layer's **serialisation pair** — directly
relevant to the city-save writer, since these read and write the valve layer's section.

### Why this is proof, not coincidence

Each of these was predicted from a header *before* being looked up:

1. **Argument counts from `ret N`.** `ret 8` = 2 args at slot 8, `ret 0` = 0 args at slot 12, `ret 0xc` = 3
   args at slots 9 and 13, `ret 4` = 1 arg at slots 3/16/17. Five independent arity checks, all correct.
2. **A constant-returning slot.** Slot 15 returns exactly `LayerType_cISC3ValveLayer` `0x80f1e6d3`.
3. **Three consecutive getters, in R/C/I order.** Slots 10/11/12 read `[ecx+0x40]`, `[ecx+0x44]`, `[ecx+0x48]`,
   and `EndOfMonth`'s tail publishes `this+0x4c/0x50/0x54` into exactly those three fields then zeroes the
   accumulators. The R/C/I ordering is confirmed by the write side, not assumed from the header.
4. **`cISC3Valve`'s own header predicted five vtable offsets used from inside the layer, all correct:**
   `+0xc`=`Init`(slot 3), `+0x20`=`GetId`(8), `+0x2c`=`QueryDemandValue`(11),
   `+0x40`/`+0x44`=`AddToSupplyValue`/`AddToDemandValue`(16/17), `+0x78`=`EndOfMonth`(30).

Point 4 is the strongest: a **second** header (`cISC3Valve.h`, 31 methods) correctly predicted five offsets in
a **different** class's call sites. Two classes agreeing by chance is not credible.

**Scope of the claim:** proven for `cISC3ValveLayer`, `cISC3CityLayer` and `cISC3Valve`. NOT asserted for all
65 interfaces. Cheap per-class re-verification: arg counts from `ret N`, plus any constant-returning slot.

### `cISC3ValveLayer::EndOfMonth` — the RCI demand regulator `[CONFIRMED @ 0x1002efe8]`

560 bytes at `0x1002efe8`. Mechanically:

1. Loops `i = 0..3` (the four agent classes), pulling a per-class scalar from the city object
   `[this+0x10]` vtable at `+0xdc`, `+0xd8`, `+0xec`, `+0xf0`.
2. For each agent record in that class's list, multiplies the record's `int16` supply field (`+0xc`) and
   demand field (`+0xe`) by that scalar and calls `cISC3Valve+0x40` (`AddToSupplyValue`) and `+0x44`
   (`AddToDemandValue`) on the matching valve, found via the map at `this+0x18`.
   *These are the same two fields slots 7 and 8 expose as `GetAgentSupplyEffect` / `GetAgentDemandEffect`.*
3. Walks a second table (`DAT_10058700`), gated by `[this+0x14]` vtable `+0xc`, reading `cISC3Valve+0x2c`
   (`QueryDemandValue`), scaling by a float from `_DAT_1004b538`, sign-correcting on `value < 1`, and feeding
   the result back through `AddToDemandValue` — the **economy-modifier** pass.
4. Calls `cISC3Valve+0x78` (`EndOfMonth`) on **every** valve and ANDs the results into the return value.
5. Iterates the 2D cell grid (`[this+0x38]` vtable `+0xc`/`+0x10` = extents) calling `+0x34` then `+0x3c`
   per cell — the per-tile density writeback.
6. Publishes `this+0x4c/0x50/0x54` into `this+0x40/0x44/0x48` (taxable R/C/I densities) and zeroes the
   accumulators.

So SC3000's RCI demand is: **per-agent-class supply/demand deltas → per-valve accumulation → economy
modifier → per-valve `EndOfMonth` → monthly taxable-density snapshot.** This matches the iOS oracle's
`goValveLayer::EndOfMonth` (580 B) in `SIM_LAYERS_XREF.md` §S5, and the size agreement (560 vs 580 B, both the
largest method on the class) is a third witness.

### Committed

17 rows in `functions.csv` promoted to **C3** with `sc3_valvelayer_*` names (`endofmonth`, `createnewvalve`,
`getvalvepointer`, `addvalvetolayer`, `getagentsupplyeffect`, `getagentdemandeffect`, `staticinit`,
`staticshutdown`, `init_city`, `init_city_dbsegment`, `save`, `simulationbegin`, `shutdown`,
`getmanipulator`, `addref`, `release`, `scalar_deleting_dtor`). Project C3 count 43 → 60.

**Five slots Ghidra never carved into functions** (`0x1002e9da`, `0x1002df70/74/78`, `0x1002de20`) so they have
no `functions.csv` row. They are documented in the table above from hand disassembly. Worth a Ghidra
re-analysis pass that seeds function starts from vtable entries.

---

## 8. cSC3ZoneLayer — S4 zoning, and a limit on §7's result

`SIMRCI.DLL`. Expected layout from the header chain
`cISC3ZoneLayer : cISC3CityCellMap<uint8_t> : cISC3CityCellMapBase : cIGZUnknown`
= 3 + 8 + 6 + 20 = **37 slots**.

### Finding it without an IID

`cISC3ZoneLayer.h` declares **no** GZIID constant, so §1's dword-scan route does not apply. What worked
instead was a `GetLayerType` sweep, generalised from §7:

1. Scan `.text` for `b8 <imm32> c3` (`mov eax, imm32 ; ret`) — every `cISC3CityLayer::GetLayerType`
   implementation has this exact shape. SIMRCI yields 9 candidates with `imm >= 0x01000000`.
2. For each, find a dword-aligned `.rdata` pointer to it and assume it is **slot 15** (the header's
   position for `GetLayerType`), giving vtable base `ptr - 0x3c`.
3. Verify slots 0..17 are all `.text` pointers, then read slots 5/9/10 (`StaticInit`, `Init(City*,DBSegment*)`,
   `Save`) — those identify the layer.
4. The layer's own primary vtable is adjacent at `base + 18*4`.

This recovered the ValveLayer's `0x80f1e6d3` as a control (it matched §7 exactly) plus **five previously
unknown SIMRCI layer-type ids**:

| LayerType | `cISC3CityLayer` vtable | primary vtable | identified by |
|---|---|---|---|
| `0x80f1e6d3` | `0x1004ce9c` | `0x1004cee4` | `sc3_valvelayer_*` (§7) — control |
| **`0xc0ab8a56`** | **`0x1004d198`** | **`0x1004d1e0`** | **slot 9 = `sc3_zonelayer_init_attach`, slot 10 = `sc3_zonelayer_save`** |
| `0xc0ab8a88` | `0x1004c5dc` | `0x1004c624` | slot 5 = `sc3_landvalue_load_tuning`, slot 9 = `sc3_rci_init_history_graph` |
| `0xc106c4f5` | `0x1004c918` | `0x1004c960` | slot 9 = `sc3_rci_layer_init`, slot 10 = `sc3_rci_layer_serialize` |
| `0x4106cf1f` | `0x1004c45c` | `0x1004c4a4` | **SC3IndLayer** — StaticInit `0x1001599a` calls `sc3_ind_load_tuning` `0x10015dc0` |
| `0x60f1e6fb` | `0x1004c1c0` | `0x1004c208` | **SC3ComLayer** — StaticInit `0x1000e834` calls `sc3_com_load_tuning` `0x1000eccd` |

All six were attributed by the same rule: disassemble `cISC3CityLayer` slot 5 (`StaticInit`) and read its
direct callees — each calls exactly one of the `Sys\SC3*Layer.ini` tuning loaders we had already named from
its INI string, which names the layer without any inference. Refining the table above:
`0xc106c4f5` StaticInit `0x1002115a` → `sc3_res_load_tuning` `0x10022ac6` = **SC3ResLayer**;
`0xc0ab8a88` StaticInit **is** `sc3_landvalue_load_tuning` `0x1001b54d` = the **land-value** layer.

> **Correction to `MODULE_MAP.md`.** Its SIMRCI row lists five layers (`SC3ValveLayer`, `SC3ZoneLayer`,
> `SC3ResLayer`, `SC3ComLayer`, `SC3IndLayer`). There are **six** — SIMRCI also hosts the **land-value**
> layer (`cISC3LandValueLayer` is in the SDK, deriving from `cISC3CityCellMap<uint8_t>`). The INI-string scan
> that built that row missed it because its tuning loader does not reference an `SC3LandValueLayer.ini` path.

The zone layer was identified by **our own prior names landing in the header's predicted slots**, which is an
independent confirmation: nothing about `sc3_zonelayer_save` was derived from the SDK.

### The size ranking agrees with the iOS oracle

Before dumping, `SIM_LAYERS_XREF.md` §S4 gave iOS sizes: `PlaceZone` 2732 B > `CanZone` 2128 B >
`PlaceBuilding` 2080 B. The three biggest slots in the SC3U vtable are **34 > 33 > 26** — exactly the header
positions of `PlaceZone`, `CanZone`, `PlaceBuilding`. Ranking predicted, ranking observed.

### `cISC3ZoneLayer` vtable @ `.rdata` `0x1004d1e0`

Slots 0-16 (the inherited cell-map interface) are all **adjustor thunks** `sub ecx, 0x10 ; jmp <impl>`, so the
cell-map base subobject sits at **object offset +0x10**. Slots 17-36 (the zone-specific methods) are direct
implementations on the primary object.

| slot | RVA | size | header method | evidence |
|---:|---|---:|---|---|
| 0-16 | `0x100342ca`+8n | 8 | *(inherited cell-map)* | `sub ecx,0x10 ; jmp` adjustor thunks |
| 17 | `0x10032c44` | 23 | `GetZoneCount(u8)` | `cmp byte[esp+4],0x17; jb; xor eax,eax; movzx; mov eax,[ecx+eax*4+0x40]; ret 4` |
| 18 | `0x10032c5b` | 26 | `GetUndevelopedTileCount(u8)` ⚠ | same shape, array at `+0x9c`, `ret 4` = **1 arg** |
| 19 | `0x100312a7` | 7 | `GetUndevelopedTileCount(void)` ⚠ | `mov eax,[ecx+0x154]; ret` = **0 args** |
| 20 | `0x10032c75` | 52 | `GetDevelopmentFailureCount(u8,i32)` | position |
| 21 | `0x100312ae` | 7 | `GetAbandonedTileCount(void)` | `mov eax,[ecx+0x15c]; ret` — 0 args ✓ |
| 22 | `0x10032694` | 66 | `RegisterZoneDeveloper(u8,dev*,u32)` | `ret 0xc` = 3 args ✓ |
| 23 | `0x100326d6` | — | `UnregisterZoneDeveloper(u8)` | `ret 4` = 1 arg ✓ |
| 24 | `0x1003270a` | — | `GetZoneDeveloper(u8)` | `ret 4` = 1 arg ✓ |
| 25 | `0x1003306d` | 74 | `PlaceBuilding(attrib*,…)` ⚠ | `ret 0x14` = 5 args ✓ |
| 26 | `0x10032dfc` | 625 | `PlaceBuilding(reskey&,…)` ⚠ | iOS twin 2080 B |
| **27** | **`0x100330b7`** | **234** | **`IsNearTransport(pt&,u32)`** | **the RCI development gate**; iOS twin 308 B |
| 28 | `0x100331a1` | 323 | `GetRoadCount(pt&,pt&)` | pairs with slot 27 |
| 29 | `0x100332e4` | 132 | `FindBuildableRect(rect&,u32,u32,u32,u8,u32,bool)` | **`ret 0x1c` = 7 args** ✓ |
| 30 | `0x100336fc` | — | `GetFilledDemand(u32)` | `ret 4` ✓ |
| 31 | `0x10033711` | — | `AddToFilledDemand(u32,i32)` | `ret 8` ✓ |
| 32 | `0x1003547c` | 251 | `GetZoneColor(u32,u32,u8&,u16&)` | position |
| 33 | `0x1003559f` | 896 | `CanZone(i32,bounds&,i32&)` | iOS twin 2128 B |
| **34** | **`0x1003591f`** | **1742** | **`PlaceZone(i32,bounds&,i32&,bool)`** | **largest on the class**; iOS twin 2732 B, also largest |
| 35 | `0x100312b5` | 7 | `NerdsRule(void)->bool` | `mov al, byte[ecx+0x2bc]; ret` — returns a **byte** (bool), 0 args ✓ |
| 36 | `0x1003250f` | 389 | `ReadZoneDeveloperDescriptions(bool)` | `ret 4` = 1 arg ✓ |

**10 independent arity matches, 0 hard mismatches** across distinctly-named methods. `FindBuildableRect` at
`ret 0x1c` (7 arguments) and `NerdsRule` returning a byte from a bool field are the two that could not
plausibly be coincidence.

### Field map recovered `[CONFIRMED @ 0x10032c44, 0x10032c5b, 0x100312a7, 0x100312ae, 0x100312b5]`

| offset | type | meaning |
|---|---|---|
| `this+0x10` | subobject | the `cISC3CityCellMap<uint8_t>` base (per the adjustor thunks) |
| `this+0x40` | `u32[23]` | zone count per zone type |
| `this+0x9c` | `u32[23]` | undeveloped tile count per zone type |
| `this+0x154` | `u32` | total undeveloped tile count |
| `this+0x15c` | `u32` | abandoned tile count |
| `this+0x2bc` | `bool` | the `NerdsRule` flag |

**There are 23 (`0x17`) zone types.** Both array accessors bounds-check `zoneType < 0x17` and return 0 above
it. Internal consistency check: `0x40 + 23*4 = 0x9c` — the two arrays are exactly adjacent and exactly 23
entries each. That was not assumed; it falls out of two independently disassembled accessors.

### ⚠ Correction to §7: overload order is NOT preserved

Slots 18/19 are the `GetUndevelopedTileCount` overload pair. The header declares `(void)` first, then `(u8)`.
The binary has them **the other way round** — slot 18 takes an argument (`ret 4`, indexes the `+0x9c` array),
slot 19 takes none (`ret 0`, reads the `+0x154` scalar).

So §7's "declaration order is vtable order" holds **between distinctly-named methods** but **not between
overloads sharing a name**. That is exactly where reconstruction from mangled names is weakest: the mangled
names differ only in their parameter encoding, and nothing in them fixes the relative order.

Consequences, applied:
- Slots 18/19 are committed **swapped relative to the header**, per the disassembly.
- Slots **25/26** (`PlaceBuilding`) both take 5 arguments, so arity cannot separate them. Both rows carry
  `[UNCERTAIN]` on the overload assignment. Resolving it needs the *type* of the first argument
  (`cISC3BuildingAttrib*` vs `cGZResourceKey const&`) read out of the bodies.
- The inherited cell-map pairs `InBounds(2)/InBounds(4)` and `SetValue(3)/SetValue(5)` are subject to the same
  doubt and were not committed.
- Logged as U-045.

### Committed

11 rows to **C3** with `sc3_zonelayer_*` names (`getdevelopmentfailurecount`, `registerzonedeveloper`,
`placebuilding_attrib`, `placebuilding_reskey`, `isneartransport`, `getroadcount`, `findbuildablerect`,
`getzonecolor`, `canzone`, `placezone`, `readzonedeveloperdescriptions`). Project C3 count 60 → 71.

Nine of the 37 slots are uncarved by Ghidra (`0x100312a7/ae/b5`, `0x100326d6`, `0x1003270a`, `0x100336fc`,
`0x10033711`, `0x10032c44`, `0x10032c5b`) and so have no `functions.csv` row; they are documented in the table
above from hand disassembly. This is now the second class where vtable-derived function starts would pay for a
Ghidra re-analysis pass.

---

## 9. The zoning rules decoded — PlaceZone, IsNearTransport, and U-045 closed

### U-045 closed: the `PlaceBuilding` overloads are swapped, 2-for-2

**Slot 25** `0x1003306d` (74 B) is a **forwarder**, not an implementation `[CONFIRMED @ 0x1003306d]`:

```c
cVar1 = (**(code **)(*DAT_1005874c + 0x24))(param_1, 0x21183b00, &param_1);  /* resolve */
uVar2 = 0;
if (cVar1 != '\0') {
  uVar2 = (**(code **)(*(int *)this + 0x68))(param_1, param_2, param_3, param_4, param_5);
  (**(code **)(*param_1 + 8))();                                              /* Release */
}
```

`0x68 / 4 = 26`. It resolves its first argument through a global service (`DAT_1005874c` vtable `+0x24`, with
`0x21183b00` as the type/interface id) into a refcounted object, forwards to **slot 26**, then releases.

**Slot 26** `0x10032dfc` (625 B) dereferences its first argument as a vtable object `[CONFIRMED @ 0x10032dfc]`:

| call | meaning |
|---|---|
| `(**(code **)(*param_1 + 0x14))()` | returns a pointer to 3 dwords = a `{type, group, instance}` resource key |
| `(**(code **)(*param_1 + 0x40))()` | footprint **width** |
| `(**(code **)(*param_1 + 0x44))()` | footprint **depth** |

An object that *reports* a resource key and a footprint is a `cISC3BuildingAttrib*`. A `cGZResourceKey const&`
would be read as three dwords directly, with no vtable.

**Therefore: slot 25 = `PlaceBuilding(cGZResourceKey const&, …)`, slot 26 = `PlaceBuilding(cISC3BuildingAttrib*, …)`
— the reverse of the header.** Combined with the slot 18/19 `GetUndevelopedTileCount` pair, that is **two
overload pairs examined and two found reversed**. The pattern so far is consistent reversal, but with n=2 it
stays a caveat, not a rule: keep checking overload pairs individually.

Byproducts: the 5th argument is confirmed to be the `bool` (Ghidra types it `int*` but tests `(char)param_5`),
and `this+0x248` is a cell map with `+0xa8` = `CellCountX`, `+0xac` = `CellCountZ`, `+0x48` = `GetValue(x,z,&out)`.
When the bool is set, slot 26 runs a **footprint uniformity check**: sample the zone value at the anchor tile,
then walk the whole width × depth rect (clamped to the cell counts) and bail if any tile differs.

### `IsNearTransport` — the RCI development gate `[CONFIRMED @ 0x100330b7]`

`IsNearTransport(sIGZPointXZUint32 const& pt, uint32 radius) -> bool`, 234 B. `this+0x244` is the queryable
layer (`+0x14` extent X, `+0x18` extent Z, `+0x74` rect query).

1. Return **false** immediately if `pt.x >= extentX` or `pt.z >= extentZ`.
2. Build a square around the tile, clamped to the map:
   `x0 = max(0, x - radius - 1)`, `z0 = max(0, z - radius - 1)`,
   `x1 = min(extentX - 1, x + radius + 1)`, `z1 = min(extentZ - 1, z + radius + 1)`.
   Side length is therefore **2·radius + 3** cells — the radius is inflated by one on each side.
3. **Shift all four bounds left by 8.** Cell coordinates become 8.8 fixed point, `0x100` units per tile.
4. Call `this+0x244` vtable `+0x74` with `(&out, &rect, *(this+0x2b4))`, where `this+0x2b4` is a filter/predicate
   object the layer holds.
5. On success read `out->vtable[0x18]`, return `(result != 0)`, then `Release` via `out->vtable[8]`.

So an RCI zone develops only when a rect query over its neighbourhood, filtered by the transport predicate,
returns a non-zero result. This is the SC3U counterpart of the iOS `IsNearTransport` (308 B @ `0x0026516c`).

### `PlaceZone` — the zoning apply path `[CONFIRMED @ 0x1003591f]`

1742 B, the largest method on the class. `PlaceZone(int32 zoneType, cSC3CityBounds const&, int32& outCost, bool)`.

**Gate.** The first call is `this->vtable[0x84]`. `0x84 / 4 = 33` = **`CanZone`**. If it returns false,
`PlaceZone` returns 0 immediately. This cross-confirms slots 33 and 34 from the call graph, independently of
§8's arity and size arguments.

**Subsystems**, all fetched from the city object at `this+0x34`:

| city vtable | role |
|---|---|
| `+0x15c` | cost / tunables provider (`+0x58` = a per-tile cost, `+0x14` = a finaliser) |
| `+0x13c` | the zone cell map (`+0x4c` read, `+0x54` test, `+0x134`/`+0x148` batch begin/end) |
| `+0x11c`, `+0x120`, `+0x124` | three occupant queries (`+0x7c` = query at cell) |

**Bounds are 8.8 fixed point.** The max corner is bumped by `+0x100` (exactly one tile) and all four bounds are
then `>> 8` into cell coordinates. Same convention as `IsNearTransport`.

**Pass 1 — validation.** Per cell: query `+0x11c` `+0x7c`; if an occupant is present it must pass `+0x74` and a
chain of `+0x3c` predicates. Separately the `+0x120` and `+0x124` queries must **miss**. Any failure clears the
ok flag and aborts the sweep. Every queried occupant is released.

**Pass 2 — apply**, bracketed by cell-map `+0x134` … `+0x148` (batch begin/end). Per cell:

- sample the **four corner values** via `+0x4c` × 4; if they are not all equal, write through the cell map
  (`[this-0x10]` `+0x3c` — negative because these methods run with `this` = the cell-map subobject, matching
  §8's `sub ecx, 0x10` thunks);
- gate on `this+0x248` vtable `+0x144(x, z)` (buildability);
- on a hit, run the **demolition path**: occupant `+0x80` (attrib), `+0xb8`, `+0xa0` then `+0x1c`, and an
  indirect call at `local_44[0x2d]`, accumulating a demolished bounding box from a `0x7fffffff` sentinel via a
  rect-union; add the per-tile cost each time;
- count tiles actually zoned, and write the zone value through the cell map.

Afterwards, if anything was demolished, a global service (`+0x140` then `+0xb0`) is notified — a region
refresh.

**The cost formula.** *(⚠ SUPERSEDED by §11c — the whitelist reading below is wrong; the tail is a zoneType→cost-ID map and it also charges the player. Kept for the audit trail.)*

```
outCost = perTileCost * tilesZoned + accumulatedDemolitionCost
```

where `perTileCost = tunables->vtable[0x58]()` **only for**

```
zoneType ∈ {0, 1, 2, 3, 5, 6, 7, 9, 10, 11, 14, 15, 17}
```

and `0` for every other type. That is **13 chargeable types out of the 23** established in §8. The whitelist is
literal in the decompilation as two comparison chains (`zoneType < 8` handling `{0,1,2,3,5,6,7}`, else
`{9,10,11,14,15,17}`), so types `{4, 8, 12, 13, 16, 18…22}` are free.

**`[UNCERTAIN]`, logged as U-047:** the `zoneType == 0` semantics and the role of the 4th `bool`. Much of pass 2
is guarded by `zoneType != 0`, which reads like *0 = de-zone*, yet 0 is in the chargeable whitelist. Ghidra also
aliases a stack flag onto `param_2`'s high byte (`param_2 = CONCAT13(1, param_2._0_3_)`), which corrupts the
argument model. Re-read with a corrected 4-argument signature before trusting either point.

### Committed

5 rows enriched at C3, and **the two `PlaceBuilding` names swapped** to match the evidence:
`0x1003306d` → `sc3_zonelayer_placebuilding_reskey`, `0x10032dfc` → `sc3_zonelayer_placebuilding_attrib`.

---

## 10. cSC3ResidentialLayer — 38 methods, and a general method for finding a vtable

`SIMRCI.DLL`, LayerType `0xc106c4f5`. `cISC3ResidentialLayer : cIGZUnknown`, so 3 + 38 = **41 slots**.
This is the health/education/population half of the RCI model.

### §8's adjacency shortcut failed, and a fingerprint scan replaced it

For the valve and zone layers the class's own vtable sat at `cISC3CityLayer vtable + 18*4`. **That adjacency
is a layout coincidence, not a rule.** Applying it here gave `0x1004c960`, which scored 18 OK / 12 mismatch —
and had slots 5 and 9 pointing at the *same* function, which no valid vtable does. Rejected.

The replacement is general and worth reusing. `cISC3ResidentialLayer` has a distinctive **arity fingerprint**
across its 38 slots: mostly 0-argument, with `ret 0xc` at slots 9-11, `ret 8` at 32/34/36, and `ret 4` at
39/40. So:

1. Enumerate every dword-aligned `.text` pointer in every non-`.text` section.
2. For each as a candidate slot 0, require slots 3..40 all be `.text` pointers.
3. Read each slot's terminating `ret N` for its argument byte count, skipping any slot whose first
   control transfer is a `jmp` (unmeasurable).
4. Score matches against the header-predicted arities; require at least 22 measurable slots.

926 candidates qualified. The winner was unambiguous:

| score | vtable base |
|---|---|
| **100.0% (29/29)** | **`0x1004c99c`** |
| 86.2% (25/29) | `0x1004c994` |
| 85.2% (23/27) | `0x1004c9a4` |

The runners-up are the same vtable read off by one or two slots, which is the expected shape of a true hit.
A full dump at `0x1004c99c` gives **29 OK, 0 MISMATCH, 9 unmeasurable**.

> **Honesty check on that 100%.** 26 of the 29 matches are `ret 0`, the commonest value, so a run of trivial
> getters would score well by luck. The fingerprint alone is suggestive, not conclusive. What makes this
> class certain is the field and call-graph evidence below, all of which was predicted from the header
> before being looked up.

### Witness 1 — three consecutive strike flags, in declared order

Slots 9/10/11 are three 170-byte sibling functions, each gated on a different byte:

```
slot  9  0x1002555b   cmp byte ptr [esi + 0x650], 0     GetStrikingSchoolBuildings
slot 10  0x10025605   cmp byte ptr [esi + 0x651], 0     GetStrikingCollegeBuildings
slot 11  0x100256af   cmp byte ptr [esi + 0x652], 0     GetStrikingHealthBuildings
```

School, College, Health at `+0x650`, `+0x651`, `+0x652` — the header's order mapped onto three adjacent
bytes. The `Is*OnStrike` triple (slots 3/4/5) reads the same three bytes in the same order, and the
`End*Strike` triple (slots 12/13/14) takes their addresses and additionally touches a dword at `0x654 + 4i`:

```
slot 12  0x10024157   lea eax,[ecx+0x650] ; mov eax,[ecx+0x654]
slot 13  0x10024196   lea eax,[ecx+0x651] ; mov eax,[ecx+0x658]
slot 14  0x100241d5   lea eax,[ecx+0x652] ; mov eax,[ecx+0x65c]
```

So each of the three systems has a **byte flag at `0x650+i` and a dword at `0x654+4i`**. Four separate method
triples agree on the same School/College/Health ordering.

### Witness 2 — the workforce getters call the AgeCohort slots the header pairs them with

```
slot 31 GetWorkforcePopPct  0x100251a8   mov eax,[ecx]; push 0x41; push 0x14; call [eax+0x80]   -> slot 32
slot 33 GetWorkforceEQ      0x100251f6   mov eax,[ecx]; push 0x41; push 0x14; call [eax+0x88]   -> slot 34
slot 35 GetWorkforceLE      0x10025292   mov eax,[ecx]; push 0x41; push 0x14; call [eax+0x90]   -> slot 36
```

`0x80/4 = 32`, `0x88/4 = 34`, `0x90/4 = 36`. **Three vtable indices predicted from the header, three hits.**
Each `GetWorkforceX` is literally `GetAgeCohortX(0x14, 0x41)`.

**Game rule, confirmed:** the *workforce* is the age cohort **20 to 65** inclusive.

### Witness 3 — the age-cohort table `[CONFIRMED @ 0x100251b5]`

`GetAgeCohortPopPct(uint8 lo, uint8 hi)` reads two byte arguments, clamps `hi` to **`0x59` (89)**, returns
`0.0` if `lo > hi`, and otherwise sums `hi - lo + 1` floats starting at `[esi + lo*4 + 0x354]`.

So there is a **per-age float array at `this+0x354`, ages 0..89** (90 entries × 4 bytes = `0x168`, spanning
`+0x354`..`+0x4bb`). Maximum modelled age is 89.

### Field map `[CONFIRMED]` — from the trivial getters

| offset | type | accessor (slot) |
|---|---|---|
| `+0x354` | `float[90]` | per-age population pct, ages 0..89 |
| `+0x628` | `i32` | `GetTotalCityEducationUpkeep` (37) |
| `+0x640` | `i32` | `GetTotalCityHealthUpkeep` (38) |
| `+0x650/1/2` | `u8` ×3 | school / college / health strike flags (3,4,5 and 9,10,11) |
| `+0x654/8/c` | `i32` ×3 | per-system strike dword (12,13,14) |
| `+0x660` | `u8` | `GetSchoolSystemRating` (16) |
| `+0x661` | `u8` | `GetCollegeSystemRating` (17) |
| `+0x662` | `u8` | `GetHealthSystemRating` (15) |
| `+0x664` | `i32` | `GetPatientCount` (18) |
| `+0x668` | `i32` | `GetHealthSystemCapacity` (24) |
| `+0x66c` | `i32` | `GetSchoolStudentCount` (20) |
| `+0x670` | `i32` | `GetSchoolSystemCapacity` (25) |
| `+0x674` | `i32` | `GetCollegeStudentCount` (22) |
| `+0x678` | `i32` | `GetCollegeSystemCapacity` (26) |
| `+0x67c` | `i32` | `GetLibrarySystemCapacity` (27) |
| `+0x680` | `i32` | `GetMuseumSystemCapacity` (28) |
| `+0x684` | `i32` | `GetTeacherCount` (21) |
| `+0x688` | `i32` | `GetProfessorCount` (23) |
| `+0x68c` | `i32` | `GetDoctorCount` (19) |

Note the struct is laid out as **demand/capacity pairs per system** — patients `+0x664` / health capacity
`+0x668`, school students `+0x66c` / school capacity `+0x670`, college students `+0x674` / college capacity
`+0x678` — with the three staff counts grouped afterwards at `+0x684`/`+0x688`/`+0x68c`.

This is worth dwelling on as evidence. The header's *accessor* order (patient, doctor, school student,
teacher, college student, professor) is **not** the field order. The ratings are the same: the accessors run
Health, School, College (slots 15/16/17) while the fields run School `+0x660`, College `+0x661`, Health
`+0x662`. Two different orderings, each matching its own source. Had the slot assignment been wrong, the
accessors would not have landed on a coherent paired struct at all.

### A negative result: address order is NOT an ordering witness

The `ChanceOf*Strike` triple (slots 6/7/8) sits at `0x10024046`, `0x100240fc`, `0x100240a1` — slot 7 at a
*higher* address than slot 8, unlike every other sibling triple on this class, which ascend. That looked like
an overload-style reversal.

It is not. Disassembling each for the flag it tests:

```
0x10024046   cmp byte ptr [ecx + 0x650], 0    -> School  = slot 6
0x100240fc   cmp byte ptr [ecx + 0x651], 0    -> College = slot 7
0x100240a1   cmp byte ptr [ecx + 0x652], 0    -> Health  = slot 8
```

The header order is **correct**; the compiler simply emitted these three out of source order. Recorded because
the tempting move was to "fix" the slot assignment from address order, which would have introduced an error.
**Use field/call evidence, never address order.**

### Committed

10 rows to **C3** with `sc3_reslayer_*` names (`getstrikingschoolbuildings`, `getstrikingcollegebuildings`,
`getstrikinghealthbuildings`, `endschoolstrike`, `endcollegestrike`, `endhealthstrike`, `getagecohorteq`,
`getagecohortle`, `seteducationfundingpercentage`, `sethealthfundingpercentage`).

**28 of the 41 slots are uncarved by Ghidra** — this class is almost entirely 7-byte field getters that
auto-analysis never turned into functions, which is why so much of it lives only in the table above. Third
class running where vtable-seeded re-analysis would pay off; that job is now clearly worth doing before
walking any more classes.

---

## 11. Vtable-seeded re-analysis, U-047, and cSC3BudgetLayer

Three pieces of work that turned out to be one story: the Ghidra pass unblocked the rest, U-047's answer
corrected §9, and the correction pre-validated the budget layer before it was dumped.

### 11a. Vtable-seeded re-analysis — 1,170 new functions

Sections 7, 8 and 10 each ended with the same complaint: many vtable slots point at code Ghidra's
auto-analysis never turned into a function, so they have no `functions.csv` row and no decompilation. Most are
7-byte field getters, only ever reached through a virtual call, i.e. only through a **data** reference.

Fix, using the pre-existing `re/scripts/MakeFunctions.java` (which already accepts `@file` of addresses):

1. For each module, scan every non-`.text` section for dword-aligned pointers into `.text`.
2. Keep runs of **≥ 8 consecutive** such pointers (vtable-shaped).
3. Collect the distinct targets; subtract those already present in `functions.csv`.
4. Feed the remainder to `MakeFunctions.java` **without `-readOnly`**, then re-export.

| module | vtable runs | distinct targets | already functions | seeded | created | failed |
|---|---:|---:|---:|---:|---:|---:|
| `SIMRCI.DLL` | 22 | 1,161 | 479 | 682 | **681** | 0 |
| `SIMMISC.DLL` | 34 | 940 | 448 | 492 | **489** | 0 |

**1,170 functions created, zero failures.** Decompilation exports grew from 3,268 → **4,040** files (SIMRCI) and
2,603 → **3,132** (SIMMISC). The estimate going in was "~42 slots across three classes"; the real number was
28× that, because the same blind spot applies to every class in these modules, not just the three walked.

> **Tracker consistency warning** *(RESOLVED for the seeded set in §11e; the wider gap it exposed is open as U-048)*. These 1,170 functions exist in the Ghidra projects and in the text exports
> but have **no rows in `functions.csv`**, which `CLAUDE.md` designates the single source of truth for status.
> The tracker is now behind the analysis by ~1,170 C0 rows and needs a mechanical sync from the refreshed
> `symbols.csv`. Not done here: `functions.csv` has concurrent writers (another session is actively verifying
> rows), and a 1,170-row insert is exactly the kind of change that should not race.

Both Ghidra projects were **mutated** (function creation, plus the U-047 signature override). Reversible with
`ghidra_headless.ps1 -Module <NAME> -Import`, which re-imports and re-analyses from the anchored copy.

### 11b. U-047 resolved — and my premise was wrong

New tool: `re/scripts/ForceSignature.java`, which overrides a function's prototype and prints the resulting
decompilation.

```
analyzeHeadless <proj> SC3_SIMRCI -process SIMRCI.DLL -noanalysis \
  -scriptPath re\scripts -postScript ForceSignature.java 0x1003591f __thiscall bool int ptr ptr bool
```

Storage came out `this=ECX`, `a1=Stack[0x4]`, `a2=Stack[0x8]`, `a3=Stack[0xc]`, `a4=Stack[0x10]`.

**The 4th bool argument is dead.** Zero accesses to `ebp+0x14` across all 1742 bytes. The callee pops it
(`ret 0x10`) and never reads it.

**The `CONCAT13` was Ghidra being faithful, not broken.** U-047 was filed on the premise that Ghidra's
argument model was wrong. It wasn't. `ebp+0xf` is the high byte of the `a2` argument slot and is genuinely
reused as a local boolean — 16 accesses, first written at `0x10035ba1`, which is *after* `a2`'s last read at
`0x10035a0c`. Deliberate, safe MSVC argument-slot reuse. Forcing the signature did not remove the aliasing and
should not have. Recorded because the lesson generalises: **an ugly decompilation is not automatically a wrong
one.**

**`zoneType == 0`** skips the corner-sample / buildability / demolition-cost block but still reads, tests and
writes the cell — de-zone.

### 11c. ⚠ Correction to §9's cost formula

§9 claimed a "13-type chargeable whitelist at one per-tile cost". **That was wrong.** Raw disassembly of the
tail shows a **zoneType → development-cost-ID map**, not a whitelist:

```
0x10035f6c  mov  eax, [ebp+8]          ; zoneType
            ...comparison chain...
0x10035fae  push 6      0x10035fca  push 3      0x10035fce  push 5
0x10035fd2  push 4      0x10035fd6  push 2      0x10035fda  push 1
0x10035fde  xor  eax,eax               ; id 0
0x10035f8a  xor  eax,eax               ; unmatched -> multiplier 0
0x10035fe8  call [edx+0x58]            ; GetCost(costId)      <- budget slot 22
0x10035f8f  imul eax, [ebp-0x34]       ; * zoned tile count
0x10035f96  add  eax, ecx              ; + demolition cost
0x10035f9c  mov  [ecx], eax            ; *a3 = total
0x10035fa2  call [edx+0x14]            ; WithdrawFunds(total) <- budget slot 5
```

So the 13 types map onto **seven different cost IDs (0-6)**, each priced by `GetCost`; unmatched types get a
zero multiplier and pay only demolition. And `PlaceZone` does not merely *report* a cost — it **charges the
player** via `WithdrawFunds`.

That identifies the object from city vtable `+0x15c`: `+0x14` = slot 5 and `+0x58` = slot 22 are
`WithdrawFunds` and `GetCost` in `cISC3BudgetLayer.h`. **City vtable `+0x15c` returns the cISC3BudgetLayer** —
established from SIMRCI, before SIMMISC was even opened.

### 11d. cSC3BudgetLayer @ `.rdata` `0x1003c550` (SIMMISC) — 17/17, 0 mismatches

`cISC3BudgetLayer : cIGZUnknown`, 25 methods → 28 slots. Found by the §10 fingerprint method
(`[8,0,4,4,4,0,0,0,0,4,4,8,4,4,4,4,4,4,4,4,4,0,0,4,0]`); the winner scored **100% (17/17)** and the
runner-up 81%.

The decisive evidence is the 64-bit and flag pairs, all predicted before being looked up:

**Two independent 64-bit witnesses.** `int64` is the only type on this class that produces a distinctive
shape, and both ends match:

```
slot 3  SetTotalFunds(int64)   0x100051ed
        mov eax,[esp+4] ; mov edx,[esp+8]          ; a 64-bit ARG in two dwords
        mov [ecx+0x38],eax ; mov [ecx+0x40],eax
        mov [ecx+0x3c],edx ; mov [ecx+0x44],edx    ; written to TWO int64 fields
slot 4  GetTotalFunds(void)->int64   0x10005204
        mov eax,[ecx+0x38] ; mov edx,[ecx+0x3c] ; ret   ; 64-bit RETURN in EDX:EAX
```

`ret 8` on slot 3 (two dwords of argument) and a bare `ret` on slot 4 returning `EDX:EAX` from the same field
pair. Total funds live at `this+0x38` (int64), mirrored to `this+0x40`.

**A setter/getter pair on one flag, at the two predicted slots — and it is `MarxismIsOn`:**

```
slot 26  SetMarxism(bool)          0x1000522c   mov al,[esp+4] ; mov byte [ecx+0x11],al ; ret 4
slot 27  MarxismIsOn(void)->bool   0x10005236   mov al,[ecx+0x11] ; ret
```

**And the flag has teeth.** Slot 22, the `GetCost` that `PlaceZone` calls, opens by testing it:

```
slot 22  0x10008fa0   cmp byte [ecx+0x11], 0 ; je 0x10008faa ; xor eax,eax ; jmp 0x10008fbb
```

`je` is taken when the flag is clear (normal lookup at `0x10008faa`); when Marxism is **on**, `eax = 0`.
**Game rule, confirmed: with Marxism enabled, development costs are zero.**

| slot | RVA | size | header method | note |
|---:|---|---:|---|---|
| 0 | `0x10007d2b` | 77 | `QueryInterface` | |
| 3 | `0x100051ed` | — | `SetTotalFunds(int64)` | `ret 8`; writes `+0x38`/`+0x3c` and `+0x40`/`+0x44` |
| 4 | `0x10005204` | — | `GetTotalFunds(void)->int64` | returns `EDX:EAX` from `+0x38` |
| **5** | **`0x10008946`** | **98** | **`WithdrawFunds(u32)->bool`** | **the spend path; PlaceZone's `+0x14`** |
| 6 | `0x100089a8` | 69 | `DepositFunds(u32)` | |
| 7 | `0x100089ed` | 81 | `DepositDisasterReliefFunds(u32)` | |
| 8 | `0x10008a3e` | 73 | `GetYTDIncome(void)->int64` | sibling pair with slot 9 (both 73 B) |
| 9 | `0x10008ae1` | 73 | `GetEstIncome(void)->int64` | |
| 10 | `0x10008ced` | 51 | `GetYTDExpenses(void)->int64` | sibling pair with slot 11 (both 51 B) |
| 11 | `0x10008d92` | 51 | `GetEstExpenses(void)->int64` | |
| 12 | `0x10008630` | 113 | `AddDepartmentBudget(dept*)->bool` | |
| 13 | `0x100086a1` | 59 | `RemoveDepartmentBudget(dept*)` | |
| 14 | `0x100086dc` | 52 | `GetDepartmentBudget(u32, dept*&)->bool` | reads both stack args = 2 args ✓ |
| 15 | `0x100092b9` | 132 | `NeededFundingChanged(dept*)` | |
| 16 | `0x1000933d` | 150 | `FundingPercentageChanged(dept*)` | |
| 17 | `0x10008734` | 89 | `GetFunding(dept*)` ⚠ | overload pair, see below |
| 18 | `0x10008710` | 36 | `GetFunding(u32)` ⚠ | 36 B — forwarder-shaped |
| 19 | `0x1000520b` | — | `GetTaxRate(i32)->float` | `ret 4` ✓ |
| 20 | `0x1000892f` | — | `GetValveModifier(u8)->float` | `ret 4` ✓ |
| 21 | `0x10008fbe` | 233 | `GetCost` ⚠ | the substantive body |
| 22 | `0x10008fa0` | — | `GetCost` ⚠ | Marxism guard → lookup; **this is the one PlaceZone calls** |
| **23** | **`0x10009150`** | **346** | **`IssueBond(u32)->bool`** | **largest on the class** |
| 24 | `0x1000521f` | — | `GetTotalBorrowed(void)->int64` | |
| 25 | `0x100092aa` | — | `GetCurrentBorrowingLimit(void)->i32` | |
| 26 | `0x1000522c` | — | `SetMarxism(bool)` | writes `+0x11` |
| 27 | `0x10005236` | — | `MarxismIsOn(void)->bool` | reads `+0x11` |

**⚠ Two overload pairs left `[UNCERTAIN]`, deliberately.** `GetFunding` (17/18) and `GetCost` (21/22) are each
two 1-argument methods, so arity cannot separate them — and three of three overload pairs examined on this
project so far turned out reversed (U-042's caveat, U-045). For `GetCost` there is *direct* evidence that slot
22 receives a development-cost selector, which is what the header attributes to slot 21; but rather than
assert the reversal I have recorded what the code does and flagged the labelling. Slot 18's 36 bytes make it
forwarder-shaped, which is exactly the shape that resolved U-045 — that is the cheap next test.

### Committed

18 rows: 17 `sc3_budgetlayer_*` at C3, plus the corrected `sc3_zonelayer_placezone` note. Two new reusable
scripts in `re/scripts/`: `ForceSignature.java`, and the vtable-seeding recipe driving the existing
`MakeFunctions.java`.

### 11e. Tracker sync — and a coverage claim I got wrong

**Done:** the 1,174 seeded addresses now have `functions.csv` rows. Appended rather than rewritten, so every
pre-existing line is byte-identical (verified by `diff` against the pre-sync backup).

```
36,789 -> 37,963 rows   (+1,174:  1,020 kind=fun/C0,  154 kind=thunk)
SIMRCI.DLL   1,536 -> 2,218 rows
SIMMISC.DLL  1,200 -> 1,692 rows
duplicates introduced: 0     C3 rows preserved: 98
```

Each new row carries `[vtable-seeded 2026-08-17]` in `notes` for provenance. Conventions followed:
`fun`→`C0`, `thunk`→`thunk`, `lib`→`lib`, with `subsystem`/`new_name` empty. Note these are the **first
`thunk`-kind rows for any DLL module** — previously only `SC3U.exe` had them, and
`enumerate_functions.py` deliberately never adds them, so this is a mild convention deviation (harmless: the
"real backlog" metric excludes `confidence=thunk`).

### ⚠ RETRACTION — the "20,100 untracked functions / 65.4% coverage" claim was wrong

This section originally reported that the tracker covered only 65.4% of the analysed binary, with 20,100
genuine functions untracked across all 29 DLLs, and concluded that every phase-gate percentage was measured
against two thirds of the real inventory. **All of that was wrong.** The corrected picture:

| exported `.c` files | 58,063 |
|---|---:|
| **`FUN_*` — the actual backlog** | **33,118** |
| `Unwind_*` (MSVC exception-unwind fragments) | 22,495 |
| `Catch_*` handlers | 1,118 |
| `thunk_*` | 664 |
| named / library / PE-exported | 668 |

My scan treated every exported `.c` file as a candidate function and used `symbols.csv`'s `isThunk` /
`isLibrary` columns to filter. **Neither flag marks `Unwind_*` or `Catch_*` fragments** — they come through as
`isThunk=false, isLibrary=false`, so 23,613 exception-handling fragments were counted as untracked game code.
That is the entire "gap".

Worse, the project already had `re/scripts/enumerate_functions.py`, which does exactly this back-fill and whose
docstring documents this precise trap:

> *"Counting those as backlog inflates the total from 31,963 to 56,754 — a 78% overstatement."*

**I did not check `re/scripts/` for existing tooling before measuring.** Had I done so, I would have used its
definition and never produced the wrong number.

**True gap, `FUN_*` only: 129 rows** — 90 SIMRCI + 39 SIMMISC. And all 129 were **created by my own vtable
seeding**, not pre-existing: seeding a slot that points at a thunk makes Ghidra also create the body behind it
(`0x10001005` behind `thunk_FUN_10001005`), and those cascade targets were not in my seed list. **The other 27
modules had zero missing `FUN_*` rows.** The tracker was already complete by the project's own definition.

Retracted specifically: 65.4% coverage; 20,100 untracked functions; per-DLL coverage of 43-73%; and the
conclusion that the gate percentages are untrustworthy. Logged as U-048, status `retracted`.

The 129 were closed by a parallel session running `enumerate_functions.py` (37,963 → 38,092 rows), so the
`FUN_*` gap is now zero.

**Standing lessons.** Check `re/scripts/` for existing tooling before building a measurement. Count `FUN_*`
only — `Unwind_*` outnumbers real functions 2:3 in these exports and silently dominates any naive total.

### 11f. The seeding pass across all 30 binaries, and what it did to the P1 gate

§11a did SIMRCI and SIMMISC. This extends it to every remaining binary, then re-derives the gate honestly.

**Seeding.** Same recipe: scan non-`.text` sections for runs of ≥8 dword-aligned `.text` pointers, take the
distinct targets, subtract those already tracked, feed to `MakeFunctions.java` without `-readOnly`, re-export.

```
28 binaries   12,879 targets seeded
created 12,787    already existed 91    FAILED 1
```

The single failure is `SIMBABLD.DLL 0x12055fcd` — Ghidra could not create a function there (the address is
almost certainly mid-instruction or in data that a vtable slot points at spuriously). One in 12,879 is a fine
rate for a heuristic; it is recorded rather than chased.

**Enumeration.** `re/scripts/enumerate_functions.py` then added **12,529** `FUN_` rows:

| | |
|---|---:|
| SC3U.exe | +1,906 |
| SIMUI.DLL | +1,109 |
| SIMSPR.DLL | +981 |
| SIMDSTR.DLL | +795 |
| SIMGEOM.DLL | +712 |
| GZWinD.dll | +593 |
| STRTSIM.DLL | +563 |
| SIMBABLD.DLL | +559 |
| …20 more | +5,311 |

`functions.csv` 38,092 → **50,621 rows**; real backlog 33,011 → **45,669 (+38%)**. Verified strictly additive:
**0 rows lost, 0 pre-existing rows modified**, and C1/C2/C3/C4 unchanged at 4,014 / 1,668 / 98 / 11.
`--dry-run` now reports 0 rows to add, so **criterion 1 is re-closed**.

The excluded classes are worth restating, since they are what §11e got wrong: `unwind 22,495`,
`catch 1,118`, `thunk 2,475`, `named 724`. Note `thunk_*` nearly quadrupled (664 → 2,475) — seeding a vtable
slot that points at a thunk creates the thunk *and* the body behind it, which is also where §11a's 129 cascade
rows came from.

### ⚠ P1 criterion 2 has re-opened: 530/562

ROADMAP's own caveat on criterion 2 fired exactly as written:

> *"The set is derived from the export, and the export grew from 513 to 530 members while the reading was in
> progress. A re-export can add members, so re-run `scope_toolkit.py` rather than quoting 530."*

Re-running it against the refreshed export:

```
                 before        after
core-sim FUN_     9,575       14,671
toolkit set         530          562
  >= C2             530          530
  C0 left             0           32
```

**Nothing that was read got unread.** The 530 already at C2 are intact. The set is simply larger: 32 newly
visible bodies satisfy the toolkit criteria and start at C0. The gate went from 100% to **94.3%**.

Instrument still trustworthy — `--validate` recall against `find_section_producers.py`, an unrelated method, is
**50/50 = 100%** after the re-export.

The 32, by module and criterion (`S1` stream slots, `S2` section keys, `S3` class identity, `S4` INI):

| module | count | RVAs |
|---|---:|---|
| SIMGEOM | 13 | `0x10004c5e` `0x10004cb8` `0x100069fd` `0x10006a15` `0x10006a2d` `0x1000c17b` `0x1000c681` `0x1000ccbe` `0x1000d290` `0x1000d950` `0x1000fc80` `0x10010220` `0x10011561` |
| SIMDSTR | 10 | `0x10006576` `0x10007aed` `0x10008cd6` `0x1000a08a` `0x1000a0a2` `0x1000a0ba` `0x1000e266` `0x10013b42` `0x10016de3` `0x1002136e` |
| SIMUTIL | 5 | `0x100033c0` `0x1000ae59` `0x1000b577` `0x1000b5bf` `0x1000c825` |
| SIMNTWRK | 3 | `0x1000ca2c` `0x10013965` `0x10023b3a` |
| SimTransit | 1 | `0x100015a7` |

Four of them (`SIMGEOM 0x1000d290`, `0x10010220`, plus `0x1000d950`/`0x1000fc80`) are **S1 serialisers** —
functions making ≥3 calls to a pinned GZCOM stream slot. Those matter most for the city-save writer, because
S1 is the criterion that found the writer's own primitives.

Work list: `py -3.12 re/scripts/scope_toolkit.py --todo > list.txt` then `delegate_cluster.ps1 -RvaFile list.txt`.
Deliberately NOT checked in as a file: `re/analysis/` is Markdown-only by `.gitignore` policy, and a
frozen copy would rot the moment anything is read or re-exported. The table above is the snapshot; the
script is the source of truth.

### The honest summary of this pass

It **cost** a met gate: criterion 2 went 530/530 → 530/562. It **bought** 12,529 function bodies that were
invisible to every previous measurement, including 32 that the project's own toolkit definition says are
needed. A gate computed over a set that was missing 38% of the binary was measuring the wrong thing; 94.3% of
the right set is a better number than 100% of the wrong one.

---

## 12. Overload order becomes a rule, and `GZIID_cISC3CityLayer` is named

Two cheap follow-ups that each closed a marker, plus a correction to the SDK headers themselves.

### 12a. 4 of 4 overload pairs are reversed — promoted from caveat to working rule

§8 found one reversed pair and §9 a second. Two more on `cISC3BudgetLayer` complete the set.

**`GetFunding`, slots 17/18** `[CONFIRMED @ 0x10008710]`. Slot 18 (36 bytes) is a forwarder:

```c
if (param_1 == (int *)0x0) { uVar2 = 0; }
else {
  iVar1 = *(int *)this;
  uVar2 = (**(code **)(*param_1 + 0xc))();     /* pull an id out of the department object */
  uVar2 = (**(code **)(iVar1 + 0x44))(uVar2);  /* 0x44/4 = 17  -> forwards to slot 17 */
}
```

A forwarder that converts an *object* into an *id* has to be the object overload. So slot 18 takes the
`cISC3DepartmentBudget*` and slot 17 takes the `uint32` — the reverse of the header.

**`GetCost`, slots 21/22.** Slot 22 (30 bytes) is `cmp byte [ecx+0x11],0` then a direct table lookup
`FUN_10009847(&DAT_10049dc0, arg)`. Slot 21 (233 bytes) is a bounded nearest-match search with an initial
bound of 50000 and a per-key cache. A 30-byte table lookup is the small-enum overload, and SIMRCI's
`PlaceZone` passes exactly a 0..6 selector to slot 22 via `+0x58`. The header attributes the
`tDevelopmentCostID` parameter to slot 21. Reversed.

**The rule.** For a same-name overload pair, **invert the header order, then confirm by body shape** — the
forwarder / narrower / table-lookup member is the *later* slot. The mechanism is why: mangled names differ only
in parameter encoding, so nothing in them fixes intra-name order during reconstruction.

Honest scope: 4 pairs across 3 classes in one SDK. A strong prior, not a licence to skip the check.

### 12b. A correction *to* the SDK header

`cISC3BudgetLayer.h` declares `uint32_t GetFunding(...)` and the author appended
`// Verify that this is the correct return type.` That doubt is now resolved, and they were right to have it:
slot 17 returns a **64-bit** value. The body ends in an `__allmul` / `__alldiv` pair computing
`(pct & 0xff) * amount / 100` and returns it as `undefined8` in `EDX:EAX`.

So the oracle is not only reversible on overload order, it has at least one wrong return type — and it labels
its own weak spots. Worth trusting those labels.

### 12c. `0x206c6e7c` = `GZIID_cISC3CityLayer` `[CONFIRMED]`

U-044 had two unnamed IIDs accepted at `cSC3ValveLayer`'s `this+4` subobject, split 8/8/2 across the module's
QI functions and known to be independent interfaces.

**The probe.** A class has a `cISC3CityLayer` base subobject iff an adjustor thunk
`sub ecx, N ; jmp <that class's primary QueryInterface>` sits at slot 0 of a *second* vtable whose slot 15 is
`mov eax, imm32 ; ret` — i.e. `GetLayerType`. This is exactly the shape §7 found on `cSC3ValveLayer`, used here
as a test rather than an observation.

| class | group | `cISC3CityLayer` subobject? |
|---|---|---|
| SIMRCI `0x1002ef6b` (ValveLayer) | A+B+M — control | **yes**, vtable `0x1004ce9c`, LayerType `0x80f1e6d3` |
| SIMSERV `0x1000ef24` | A-only | **yes**, vtable `0x1001f424`, LayerType `0x80abf2be` |
| SCENARIO `0x10008e0b` | A-only | **yes**, vtable `0x1001a604`, LayerType `0xc3de4d66` |
| SIMRCI `0x1003d154` | B-without-A | no — 0 adjustor thunks |
| SIMECO `0x10014838` | B-without-A | no — 0 |
| SIMGEOM `0x1001ca50` | B-without-A | no — 0 |
| SIMUTIL `0x10019670` | B-without-A | no — 0 |

Accepting **A** correlates perfectly with being a city layer (3/3 yes, 4/4 no). Accepting **B** does not.
Therefore **`0x206c6e7c` = `GZIID_cISC3CityLayer`**, a constant the SDK headers do not carry.

Two new LayerType constants fell out for free: **`0x80abf2be`** (SIMSERV) and **`0xc3de4d66`** (SCENARIO,
presumably `cISCNScenarioLayer`). Also noted: SIMSERV `0x1000ef24` has **five** adjustor thunks
(`sub ecx` 0x1c/0x20/0x24/0x28/0x2c), so it is a five-base multiple-inheritance class — the richest seen so far.

**`0x81c0cb7c` is still unnamed**, and deliberately so. It is implemented by 16 classes, 8 of which are not city
layers, and is accepted at the same subobject as `GZIID_cIGZMessageTarget` `0x58d`, so it is a base that
`cISC3CityLayer` also inherits. U-044 stays `narrowed` with the next step recorded: the four B-implementing
classes share an identical primary slot-15 shape (`mov eax,[ecx] ; call [eax+0x48]`), so diffing the common
vtable prefix of two otherwise-unrelated ones should yield B's method count.

### A method note

The first version of the 12c probe was wrong and worth recording. It measured "consecutive code pointers from
the QI" as the vtable length and tested *that* vtable's slot 15. It reported 94 slots for the ValveLayer, whose
vtable is 15 — `.rdata` packs vtables adjacently, so a run-length walk sails straight through the boundary. And
the `cISC3CityLayer` vtable is a *secondary* vtable, never the one starting at the primary QI. The adjustor
thunk is the only reliable way in.

---

## 13. cSC3City — the god-object, 162 slots, found by fingerprint and validated from three other modules

`cISC3City` is the largest interface in the SDK (159 methods) and the object every layer reaches through.
It is also the best-anchored target available, because three earlier layer walks had already pinned real
city-vtable offsets **before** this class was looked at.

### 13a. Located: `SIMCITY.DLL` `.rdata` `0x10013260`

The arity fingerprint was generated *from the header* rather than by hand — parse each
`virtual R Name(params) = 0;`, sum 4 bytes per parameter and 8 for a by-value `int64_t`/`double`, and you
get a 159-entry expected `ret N` vector. Scanning every dword-aligned `.text` pointer in every data section
of all 30 binaries for a 159-slot window:

```
candidates (>=60 comparable, >=80% match): 1
   96.9%  126/130   SIMCITY.DLL  vtable 0x10013260
```

**One candidate, project-wide.** 130 measurable slots, 126 matching.

### 13b. Validated against offsets confirmed before this class was opened

These twelve came out of the ValveLayer, ZoneLayer and BudgetLayer walks (§7, §9, §11d), in other modules,
without any knowledge of `cISC3City`'s layout:

| offset seen earlier | slot | header method | implementation |
|---|---:|---|---|
| `+0xcc`, `+0xd0` — "map dimensions" | 51, 52 | `CellCountX`, `CellCountZ` | `mov eax,[ecx+0x3c]` / `[ecx+0x40]` |
| `+0x11c` — the query PlaceZone requires to HIT | 71 | `SurfaceOccupantManager` | `mov eax,[ecx+0x84]` |
| `+0x120`, `+0x124` — the two that must MISS | 72, 73 | Underground managers L1, L2 | `[ecx+0x88]`, `[ecx+0x8c]` |
| `+0x138` | 78 | `BuildingLayer` | `[ecx+0xa0]` |
| `+0x150` | 84 | `PowerLayer` | `[ecx+0xb8]` |
| **`+0x15c` — proven to return the budget layer** | **87** | **`BudgetLayer`** | `[ecx+0xc4]` |
| `+0x188` | 98 | `LandValueLayer` | `[ecx+0xf0]` |
| `+0x194` | 101 | `DemolitionLayer` | `[ecx+0xfc]` |
| `+0x1b8` | 110 | `GetSpecificLayer(uint32)` | not a getter ✓ takes an argument |

`+0x15c` is the strongest: §11c established from *SIMRCI* that the object at city vtable `+0x15c` is a
`cISC3BudgetLayer`, because `PlaceZone` calls `GetCost` and `WithdrawFunds` on it. `0x15c / 4 = 87`, and the
header's slot 87 is `BudgetLayer`. Two modules, two methods, one answer.

**A semantic upgrade this produced.** §9 called `+0x13c` "the zone cell map". Slot 79 is **`DirtBag`** — SC3's
terrain layer. So `PlaceZone` sampling four values through it and comparing them is a **corner-height / slope
check**, not a zone-value read. That reading is now recorded as the correction it is.

**A correction it forces.** §7 described `[this+0x10]` in `ValveLayer::EndOfMonth` as "the city object", with
`+0xdc/+0xd8/+0xec/+0xf0` as per-agent-class scalars. Those offsets are slots 55/54/59/60 =
`AnimCellCountZ`/`AnimCellCountX`/`CellSizeInAnimUnitsY`/`GetTileSize` — dimension getters, not agent scalars.
And `CreateNewValve` passes `this+0xc` as the city. **So `this+0x10` is not the city and §7's label was wrong.**
Logged as U-049; the mechanical description of EndOfMonth (which valve slots it calls, what it publishes) is
unaffected.

### 13c. The subsystem-pointer block — 28 slot-order confirmations at once

Slots 71–101 are trivial accessors, and their field offsets are perfectly linear:

```
field = 0x84 + (slot - 71) * 4        holds for all 28 getters, 0 exceptions
```

| slots | subsystem pointers |
|---|---|
| 71–74 | surface / underground L1 / underground L2 / anim occupant managers → `+0x84`…`+0x90` |
| 78–101 | Building, DirtBag, Transit, Traffic, Flora, Zone, Power, Plumbing, Ordinance, **Budget**, World, StrtSim, Disaster, Pollution, Crime, Police, Fire, Residential, Commercial, Industrial, LandValue, Neighbors, Weather, Demolition → `+0xa0`…`+0xfc` |

So the city holds a **contiguous array of 31 subsystem pointers at `+0x84`…`+0xfc`**, and the vtable exposes
them in declaration order. Slots 75/76/77 sit inside that run but are `CreateOccupant` ×2 and
`RemoveAllOccupants` instead of getters, so `+0x94`/`+0x98`/`+0x9c` are three pointers this interface does not
expose.

Twenty-eight getters landing on twenty-eight consecutive predicted offsets is the single strongest piece of
slot-order evidence in this document — no permutation of the declaration order could produce it.

### 13d. The advisor block is permuted — and that is a struct fact, not a slot error

Slots 102–109 break the linear formula. All eight still land inside a contiguous advisor block, but in a
different order:

| field | `+0x104` | `+0x108` | `+0x10c` | `+0x110` | `+0x114` | `+0x118` | `+0x11c` | `+0x120` |
|---|---|---|---|---|---|---|---|---|
| getter | Utility | **Budget** | CityPlanning | Environment | Demographics | PublicSafety | Transportation | Petitioner |
| slot | 102 | 108 | 106 | 105 | 103 | 104 | 107 | 109 |

Eight distinct fields, eight consecutive dwords, no duplicates. **This is not a slot-order failure** — each
named getter reads one field and the getters remain in header order. The *struct* simply stores advisors in a
different order than the interface declares them. Same lesson as §10's system ratings: accessor order and field
order are independent, and only the former is what the header claims.

### 13e. 6 of 6 — the overload rule now predicts

The **only 4 arity mismatches in 130 measurable slots** are two overload pairs, and both are reversed:

| slot | header says | actual `ret` | is really |
|---:|---|---|---|
| 121 | `GetDate(dayOfYear, year)` — 2 args | `0xc` | the **3-arg** `(month, day, year)` |
| 122 | `GetDate(month, day, year)` — 3 args | `0x8` | the **2-arg** `(dayOfYear, year)` |
| 123 | `SetDate(dayOfYear, year)` — 2 args | `0xc` | the **3-arg** form |
| 124 | `SetDate(month, day, year)` — 3 args | `0x8` | the **2-arg** form |

§12a promoted overload-reversal to a working rule at 4 of 4 pairs. This class was **not** used to derive it,
and it supplies two more — **6 of 6**. More usefully, the rule is now *predictive*: every mismatch on a
162-slot class was an overload pair, and inverting each pair resolved all four. Non-overload slots mismatched
zero times.

### Committed

32 rows at **C3**: the 28 `sc3_city_get_*` subsystem accessors plus the 4 date overloads under their corrected
signatures. `verify_worker_rows.py` on the batch: **0 of 32 flagged**. Project C3 count 99 → 131.

29 of the 159 slots are unmeasurable by arity (their first control transfer is a `jmp`), so they are confirmed
by position only. The header's own uncertainty markers remain worth heeding — §12b already found one wrong
return type where the author had flagged their own doubt.

---

## 14. cSC3DirtBag — the terrain layer, and PlaceZone's real preconditions

§13 identified city vtable slot 79 as `DirtBag`, which meant §9's reading of `PlaceZone` was wrong about what
it was talking to. Walking `cISC3DirtBag` settles it and turns four unlabelled offsets into game rules.

### 14a. Located: `SIMDIRT.DLL` `.rdata` `0x1002046c`, 91 slots

88 methods + 3 `cIGZUnknown`. Same method as §13 — arity fingerprint generated from the header, scanned across
every data-section code pointer in all 30 binaries. **One candidate project-wide: 67/73 = 91.8%.**

Structural note: **slots 3–17 are the `cISC3CityLayer` contract verbatim** (`DoMessage`, `DoQueryInfo`,
`StaticInit`, `StaticShutdown`, `Init` ×3, `Save`, `SimulationBegin`, `SimulationEnd`, `Shutdown`,
`GetManipulator`, `GetLayerType`, `DebugClassTag`, `DebugTypeTag`). So unlike `cSC3ValveLayer`, which carries
`cISC3CityLayer` as a secondary base with adjustor thunks (§7), `cISC3DirtBag` **flattens the layer contract
into its own vtable**. Both shapes occur; the adjustor-thunk probe from §12c only finds the first kind.

New LayerType constant, from slot 15: **`0x21737de5`** (`mov eax,0x21737de5 ; ret`).

### 14b. Five anchors, all derived before this class was opened

Every offset `PlaceZone` used on the object at city `+0x13c` was recorded in §9 with a guessed label. All five
now resolve, and **all five match their expected arity exactly**:

| offset | slot | header method | expected / actual `ret` | what §9 called it |
|---|---:|---|---|---|
| `+0x03c` | 15 | `GetLayerType` | `0` / `0` ✓ | — |
| `+0x04c` | 19 | `GetVertexAltitudeDirt(u32,u32,u8&)` | `0xc` / `0xc` ✓ | "cell-map value read" |
| `+0x054` | 21 | `IsWater(u32,u32)` | `0x8` / `0x8` ✓ | "a test" |
| `+0x134` | 77 | `SetupZone(bounds&,u32&,bool,bool)` | `0x10` / `0x10` ✓ | "batch begin" |
| `+0x148` | 82 | `LockUpdates(bool)` | `0x4` / `0x4` ✓ | "batch end" |

### 14c. What PlaceZone actually does — three corrections to §9

**The four-value read is a slope check.** `PlaceZone` calls `+0x4c` = `GetVertexAltitudeDirt` four times, at
`(x,z)`, `(x+1,z)`, `(x,z+1)`, `(x+1,z+1)`, into four **byte** locals, then tests them for equality. Those are
the four **corner vertex altitudes** of the tile. §9 called this "samples the four corner values via `+0x4c`"
without knowing what the values were; they are terrain heights, and unequal corners mean a sloped tile.

**A tile cannot be zoned on water.** `+0x54` is `IsWater(x,z)`, and `PlaceZone` clears its per-cell ok flag when
it returns true. §9 recorded this only as "`+0x54` (a test)".

**Zoning terraforms first.** `+0x134` is `SetupZone(bounds, &cost, bool, bool)`, called **once over the whole
rect before the per-cell loop** — not a "batch begin" as §9 assumed. The batch guard is the *other* call:
`+0x148` = `LockUpdates(bool)`, invoked with 1 before the apply loop and again at the end.

So the corrected precondition chain for zoning a tile is: `CanZone` (slot 33 of the zone layer) → `SetupZone`
terraform over the rect → `LockUpdates(true)` → per cell: corner-altitude slope check, `IsWater` rejection,
buildability gate, occupant/demolition handling → `LockUpdates(false)`.

### 14d. 10 of 10 — four more reversed pairs

All **six** arity mismatches on this class are **four overload pairs, every one reversed**:

| pair | header order | actual `ret` | verdict |
|---|---|---|---|
| `SetVertexAltitude` 32/33 | 3-arg point, 5-arg rect | `0x14`, `0xc` | reversed |
| `SetWaterTable` 34/35 | 4-arg, 5-arg rect | `0x14`, `0x10` | reversed |
| `InCellBounds` 51/52 | 2-arg point, 4-arg rect | `0x10`, `0x8` | reversed |
| `InVertexBounds` 53/54 | 2-arg point, 4-arg rect | `0x10`, `0x8` | reversed |

Running total across five classes: **10 of 10 overload pairs reversed**, and **zero non-overload slots have
ever mismatched**. In each pair the **rect / wider form is the earlier slot** and the point / narrower form the
later — consistent with §12a's "the narrower member is the later slot".

> **A method fix worth recording.** The first pass reported only 6 mismatches and missed that slots 33 and 35
> were also wrong, because the arity extractor bails with `'jmp'` when a function's first control transfer is a
> branch, and treats that slot as unmeasurable. Bounding the disassembly by each function's **tracked size**
> from `functions.csv` and collecting *all* `ret N` in the body gives an unambiguous answer — and confirmed the
> extractor was not overrunning, which was my first suspicion. Prefer size-bounded extraction over a fixed
> byte window.

### Committed

13 rows at **C3**: the 5 anchors plus all 8 members of the 4 reversed pairs, each named with its real form
(`_rect` / `_point`). `verify_worker_rows.py`: **0 of 13 flagged**. Project C3 count 131 → 144.

---

## 15. cSC3PollutionLayer — the cleanest walk yet, and a counterexample checked

`cISC3PollutionLayer : cISC3CityCellMap<uint32_t>`, so the expected chain is 3 (`cIGZUnknown`) + 8
(`cISC3CityCellMapBase`) + 6 (`cISC3CityCellMap<T>`) + 51 = **68 slots**.

### 15a. Located: `SIMECO.DLL` `.rdata` `0x1001b984` — 50/50, zero mismatches

**One candidate project-wide, 100.0%.** The best result of the six walks. The expected arity vector was
assembled from three headers chained in inheritance order, and the extractor used §14d's lesson: bound the
disassembly by each function's tracked size and collect *every* `ret N` in the body, accepting the slot only
when the set is a singleton.

### 15b. Two regular structures, each independently confirming slot order

**Seven int64 running totals as direct field reads, slots 46–52:**

```
field = 0x154 + (slot - 46) * 8          stride 8 = sizeof(int64), zero exceptions
mov eax,[ecx+0x154] ; mov edx,[ecx+0x158]     slot 46  GetTotalGarbageProduced
mov eax,[ecx+0x15c] ; mov edx,[ecx+0x160]     slot 47  GetTotalGarbageImported
... 0x164 Exported, 0x16c Recycled, 0x174 Incinerated, 0x17c ConvertedToEnergy, 0x184 Landfilled
```

Seven consecutive `int64` fields spanning `+0x154`…`+0x18b`, in exactly the header's declared order, each read
as an `EDX:EAX` pair.

**Seven computed "LastMonth" siblings, slots 53–59:** not field reads but real functions, at `0x100091a5`,
`0x100091ec`, `0x10009233`, `0x1000927a`, `0x100092c1`, `0x10009308`, `0x1000934f` — **identical 71-byte
bodies spaced exactly `0x47` apart**, in the same Produced/Imported/Exported/Recycled/Incinerated/
ConvertedToEnergy/Landfilled order as the running totals above.

Fourteen slots, two independent regularities, one ordering. That is the same class of evidence as §13c's
28-getter block.

### 15c. A potential counterexample, checked rather than assumed

Zero mismatches is a suspicious result when the inherited chain contains **two overload pairs** —
`cISC3CityCellMapBase::InBounds` (slots 6/7) and `cISC3CityCellMap<T>::SetValue` (slots 14/16). If either had
*matched* the header order, it would contradict §14d's 10-of-10 reversal rule.

Neither did, and neither refutes it. Size-bounded inspection shows **slots 5–16 are all 8-byte bodies with no
`ret` at all** — adjustor thunks (`sub ecx, N ; jmp`) into a cell-map subobject, the same shape as
`cSC3ZoneLayer`'s slots 0–16 in §8. They are unmeasurable by arity, which is precisely why the mismatch list
came back empty. Controls in the same pass (slot 20 `ret 8`, slot 22 `ret 0xc`, slot 60 `ret 4`) confirm the
extractor was working.

So the rule stands at 10 of 10 with **no counterexample**, and the reason this class produced none is
structural, not lucky.

**Incidental finding:** slots 5 and 13 point at the *same* function `0x1000c41e` —
`cISC3CityCellMapBase::GetValueSint32` and `cISC3CityCellMap<uint32_t>::GetValue` share one implementation,
which is correct when `T` is a 4-byte type: both are the same fetch.

### 15d. What the class says about the garbage model

The interface is far more about **garbage** than about air or water. Air and water get one value reader, one
predicate, one average and one maximum each; garbage gets the seven-way running-total ledger above, the
matching seven monthly deltas, landfill capacity (total and available), daily incinerator capacity, daily
waste-to-energy capacity, a recycling-centre effect, a per-building capacity query, an aging count for water
treatment / incinerators / recycling centres, a scaling factor, and per-cell active-landfill get/set.

Garbage in SC3000 is tracked as a **mass-balance ledger** — produced, imported, exported, recycled,
incinerated, converted to energy, landfilled — not as a per-tile pressure field like air and water pollution.

### Committed

24 rows at **C3**: the 14 garbage totals plus the two predicates, three value readers and five capacity
getters. `verify_worker_rows.py` over all 49 `sc3_pollution_*` rows in SIMECO: **0 of 49 flagged**. Project C3
count 144 → 168.

---

## 16. Two uncertainties closed, and a misread reframed

### 16a. U-049 resolved — `ValveLayer this+0x10` is the NEIGHBOURS layer, and §7 gets better for it

§13 showed that §7's label "the city object" for `[this+0x10]` in `ValveLayer::EndOfMonth` could not be right,
because the offsets it called (`+0xd8`/`+0xdc`/`+0xec`/`+0xf0`) are `cISC3City` dimension getters. The write is
in `sc3_valvelayer_init_city_dbsegment` `0x1002e887`:

```c
piVar1 = (**(code **)(**(int **)((int)this + 8) + 0x18c))();   /* city->vtable[0x18c] */
*(int **)((int)this + 0xc) = piVar1;                            /* = primary+0x10 */
piVar1 = (**(code **)(**(int **)((int)this + 8) + 0x158))();   /* city->vtable[0x158] */
*(int **)((int)this + 0x10) = piVar1;                           /* = primary+0x14 */
```

**The +4 thunk shift is what made this confusing.** That function is slot 9 of the *secondary*
`cISC3CityLayer` vtable, entered through `sub ecx, 4`, so its `this` is primary+4 and every offset inside it
reads 4 lower than the primary view. Under that correction:

| primary field | source | resolves to |
|---|---|---|
| `+0x0c` | `Init(cISC3City*)` writes `*(this+8)` | **the city** — and this is what `CreateNewValve` reads |
| `+0x10` | city vtable `+0x18c` → slot 99 | **`NeighborsLayer`** |
| `+0x14` | city vtable `+0x158` → slot 86 | **`OrdinanceLayer`** |

So `EndOfMonth`'s four per-agent-class scalars come from the **neighbours layer** — they are
**neighbour-city demand**, which is exactly why they were never going to be dimension getters. And
`[this+0x14]->vtable[0xc]` is `cISC3OrdinanceLayer::QueryOrdinanceOn(uint32)` (slot 3), gating the
economy-modifier pass: **ordinances modulate RCI demand**.

The corrected model of the RCI regulator is therefore: neighbour demand per agent class → per-valve
supply/demand accumulation → an ordinance-gated economy-modifier pass → per-valve `EndOfMonth` → monthly
taxable-density snapshot. §7's mechanical description (which valve slots are called, what is published where)
is unaffected and stands.

No SDK header exists for the neighbours layer — `cISC3City` declares it as untyped `intptr_t
NeighborsLayer(void)` — so those four offsets stay unnamed.

### 16b. U-044: my 8/8/2 split was the wrong model

The earlier probe found 8 QI functions accepting `0x81c0cb7c` without `0x206c6e7c`, and I read that as *eight
different classes implementing a shared interface B*. That model is wrong.

Comparing the six B-implementors' primary vtables slot by slot:

```
SIMRCI    0x1004d9d0    0x8 0x0 0x0 0x4 0x8 0x8 0x4 0x4 0x0 0x8 0x0 0x4 ...
SIMECO    0x1001c91c    0x8 0x0 0x0 0x4 0x8 0x8 0x4 0x4 0x0 0x8 0x0 0x4 ...
SIMGEOM   0x1002b058    (identical)
SIMUTIL   0x10023e38    (identical)
SIMDSTR   0x10034270    (identical)
SimTransit 0x1001b884   (identical)

common arity prefix: 82 slots; the "divergence" at slot 82 is 5 of 6 unmeasurable, not a difference
```

**Byte-for-byte identical for at least 82 slots across six modules.** That is not six classes sharing an
interface — it is **one class of ≥79 methods statically replicated into each sim module**. Which also explains
why "8 accept B without A" looked like a population: it was one class counted eight times.

It is definitely not a `cISC3CityLayer` — zero adjustor thunks and no constant-returning `GetLayerType` slot
(§12c's probe). And no SDK header describes a ≥79-method non-layer class, so `0x81c0cb7c` stays unnamed.

Recorded resolution path: point the §13/§15 fingerprint scanner at **all 65 headers in bulk** and match this
82-slot arity vector, rather than guessing. The scanner already does exactly this for one header at a time.

> **The lesson, since it is the fourth of its kind today.** "Eight classes accept B" was a count over QI
> functions that I treated as a count over *classes*. Identical replicated code inflates any per-module tally.
> Same family as the `Unwind_*` miscount (§11e), the `thunk_FUN_` miscount, and the `functions.csv`-vs-`symbols.csv`
> convergence miscount: **check whether the things you are counting are distinct before reporting how many there
> are.**

---

## 17. cISC3Occupant — the first interface with no unique implementor, and 12 of 12

`cISC3Occupant : cIGZUnknown`, 69 methods → **72 slots**. This is what `PlaceBuilding` places and what all
three occupant managers (city slots 71–73, §13) hand out.

### 17a. 156 candidates, not one — and that is the correct answer

Every previous walk produced exactly **one** vtable project-wide. This one produces **156 at ≥75%**, with
**6 in a 93.3% (56/60) top tier** spread across SimTransit (4 of them), STRTSIM and SIMUTIL.

That is not a failure of the method, it is the method reporting a different kind of class. `cISC3City`,
`cISC3DirtBag` and `cISC3PollutionLayer` are **singletons** — one city, one terrain layer, one pollution layer,
each implemented once. `cISC3Occupant` is an **interface implemented by every placeable thing in the game**:
roads and rails in SimTransit, flora, buildings, network pieces. Each concrete occupant class has its own
vtable with the same 72-slot layout.

**Consequence for the method, worth stating before it misleads someone:** a unique hit means "singleton
class"; a large candidate set means "widely implemented interface". Neither is evidence of a wrong
fingerprint. What generalises from this walk is the **slot map**, not any one address.

### 17b. Five anchors from PlaceZone, all resolved

§9 described `PlaceZone`'s occupant handling in terms of raw offsets. All five now have names, and four match
their expected arity directly:

| offset | slot | header method | §9's description |
|---|---:|---|---|
| `+0x3c` | 15 | `IsGeomFlag(uint32)` | "a chain of `+0x3c` predicate calls" |
| `+0x74` | 29 | **`CanUserRemove(void)`** | "must pass `+0x74`" |
| `+0x80` | 32 | `GetAttribData(void)` | "occupant `+0x80` (attrib)" — guessed right |
| `+0xa0` | 40 | `GetSpriteInst(void)` | "`+0xa0` then `+0x1c`" |
| `+0xb8` | 46 | **`GetLocation(cSC3CityCoord&)`** | "`+0xb8`" then a bounding-box union |

**The zoning rule this settles:** a tile can only be zoned over an existing occupant when
`CanUserRemove()` is true. Combined with §14c, `PlaceZone`'s per-cell gate is now fully named — corner-altitude
slope check, `IsWater` rejection, buildability, and `CanUserRemove` plus an `IsGeomFlag` mask chain on any
occupant present. `GetLocation` feeds the demolished-region bounding box.

`IsGeomFlag` is a nice miniature: `mov eax,[ecx] ; call [eax+0x48] ; and eax,[esp+4]` — it fetches the flag
word through its own vtable slot 18 (`GetGeomFlag`, `0x48/4 = 18`) and masks with the argument. A one-line
method that confirms two slots at once.

### 17c. 12 of 12, and this time the test is unambiguous

The **only 4 arity mismatches** are the class's two overload pairs, both reversed:

| slot | header says | actual `ret` | is really |
|---:|---|---|---|
| 38 | `GetSpriteAttrib(uint32)` | `0` | the **void** form |
| 39 | `GetSpriteAttrib(void)` | `4` | the **uint32** form |
| 40 | `GetSpriteInst(uint32)` | `0` | the **void** form |
| 41 | `GetSpriteInst(void)` | `4` | the **uint32** form |

Every earlier pair had **identical** arities on both members (`GetFunding`, `GetCost`, `PlaceBuilding`) or was
resolved by body shape. These two differ, `0` versus `4`, so arity alone decides them — no forwarder argument,
no table-lookup heuristic. **The cleanest confirmation of the rule so far**, taking it to **12 of 12 pairs
reversed across seven classes**, with zero non-overload slots ever mismatching.

It also retro-explains a §9 detail: that section recorded occupant `+0xa0` as called with **no visible
arguments**, which sat oddly against a header that says slot 40 takes a `uint32`. Under the reversal, slot 40
*is* the void form. The decompiler was right and the header ordering was the problem.

### Committed

8 rows at **C3** against one representative implementor (SimTransit `0x1001b6a0`), each note stating explicitly
that it describes one of many implementors and that the slot map is the transferable part.
`verify_worker_rows.py`: **0 of 8 flagged**. Project C3 count 168 → 176.

---

## 18. Bulk vtable location — 31 of 39 classes placed in one pass

The per-class walks (§7-§17) each cost a session slice. This generalises them: parse every header, build
each class's **full inheritance chain**, turn it into an expected `ret N` vector, and fingerprint-scan all 30
binaries for all classes at once.

`106 classes parsed; 39 with >=12 chained methods; 30 modules indexed`

### 18a. It re-found every hand walk, at the same address

The scan was not given any prior result. It independently reproduced all six:

| class | hand-walked in | bulk scan says | agree |
|---|---|---|---|
| `cISC3BudgetLayer` | §11d SIMMISC `0x1003c550` | SIMMISC `0x1003c550` | ✓ |
| `cISC3PollutionLayer` | §15 SIMECO `0x1001b984` | SIMECO `0x1001b984` | ✓ |
| `cISC3ResidentialLayer` | §10 SIMRCI `0x1004c99c` | SIMRCI `0x1004c99c` | ✓ |
| `cISC3City` | §13 SIMCITY `0x10013260` | SIMCITY `0x10013260` | ✓ |
| `cISC3ZoneLayer` | §8 SIMRCI `0x1004d1e0` | SIMRCI `0x1004d1e0` | ✓ |
| `cISC3Occupant` | §17 SimTransit `0x1001b6a0`, 156 cands | same, 156 cands | ✓ |

Six for six, including reproducing §17's large candidate set rather than collapsing it.

### 18b. Twenty classes at 100%, and the one §17 was waiting for

**`cISC3CitySpriteCellMap` → `SIMSPR.DLL` `0x1006250c`, 104 of 104 slots, single candidate.** A complete arity
match on the largest class after `cISC3City`, with no ambiguity.

Other 100% single- or few-candidate locations now available without further work:

| class | module | vtable | m/c |
|---|---|---|---|
| `cISC3AppPreferences` | SC3U.exe | `0x004cfdac` | 34/34 |
| `cISC3OccupantManagerAnim` | SC3U.exe | `0x004d1088` | 41/41 |
| `cISC3App` | SC3U.exe | `0x004cf59c` | 32/32 |
| `cISC3Internet` | SC3U.exe | `0x004d0974` | 25/25 |
| `cISC3OccupantManager` | SIMGEOM | `0x10029e24` | 32/32 |
| `cISC3Valve` | SIMRCI | `0x1004cc14` | 31/31 |
| `cISC3BaseAdvisor` | SIMADV | `0x10030e64` | 34/34 |
| `cISC3CityAgentType` | SIMCITY | `0x10013d8c` | 20/20 |
| `cISC3OrdinanceLayer` | SIMMISC | `0x10040f3c` | 12/12 |
| `cISC3DisasterLayer` | SIMDSTR | `0x100325a0` | 15/15 |
| `cISC3CitySpriteCellMap` | SIMSPR | `0x1006250c` | **104/104** |
| `cISC3CityView` / `cISC3CityViewIso` | SIMSPR | `0x10063390` | 31/31, 35/35 |
| `cISC3WinCityViewCellCursor` | SIMSPR | `0x10067a5c` | 19/19 |
| `cISC3CitySchemeMgr` | SIMINIT | `0x1002f528` | 43/45 |
| `cISC3WeatherLayer` | SIMMISC | `0x10041000` | 30/32 |
| `cISSStrtSimLayer` | STRTSIM | `0x1002c600` | 24/26 |

`cISC3Valve` at SIMRCI `0x1004cc14` is worth noting: §7 walked `cSC3ValveLayer` and inferred five `cISC3Valve`
vtable offsets from its call sites. That class's own vtable is now located, so those five inferences are
directly checkable.

`cISC3CityView` and `cISC3CityViewIso` resolving to the *same* address `0x10063390` is consistent — the Iso
view derives from `cISC3CityView`, so one concrete class satisfies both chains.

### 18c. Eight NOT FOUND, and the honest reason

`cISC3AuraLayer`, `cISC3BuildingLayer`, `cISC3CityCellMap`, `cISC3CitySpriteManager`, `cISC3CrimeLayer`,
`cISC3DirtBag`, `cISC3LandValueLayer`, `cISC3OccupantAttribCache` all returned **0 candidates with 0
comparable slots**.

For the cell-map-derived ones (`Aura`, `Crime`, `LandValue`, `CityCellMap` itself) the cause is diagnosed and is
the same as §15b: their inherited slots are **8-byte adjustor thunks with no `ret`**, so arity is unmeasurable,
and for a 15-method class most of the chain is thunked. There is nothing left to fingerprint.

**`cISC3DirtBag` is a genuine false negative and I am flagging it as one.** §14 located it by hand at
`SIMDIRT.DLL` `0x1002046c` with 67/73 = 91.8%, above this scan's 90% bar — yet the bulk pass reports 0/0
comparable for it. So the scanner has a failure mode I have not diagnosed, and `cISC3DirtBag` is the
known-answer test it fails. Treat 18b as a set of leads that each still want the §13/§15 validation
treatment, not as 20 finished results.

That is also the value of having done six walks by hand first: without ground truth, this scan would have
looked like an unqualified success.

### 18d. `0x81c0cb7c` still not named

The bulk scan was expected to name U-044's remaining IID by matching the ≥82-slot arity vector of the class
replicated across six modules (§16b). It did not: no target class produced a hit in those six vtables. Combined
with 18c's false-negative, that is weak evidence rather than a negative result, so U-044 stays `narrowed`.

---

## 19. Making T1 testable unattended — a spec, not a change

T1 (does the game load a file we wrote?) is currently blocked on needing a human click. This section supplies
the RVAs and the exact harness changes required, and deliberately stops short of making them: `re/harness/src/`
belongs to the windowed-mode session, and any edit there means rebuilding `re/harness/bin/sc3launch.exe`, a
binary all three sessions depend on. `re/harness/` is also gitignored (`.gitignore:45 /re/*`), so a trace table
dropped in it could not be committed anyway.

### 19a. Why the existing tables cannot do it

`sc3probe.c` rebases each table against a fixed module:

```
-fnlog   -> fnlog_load(path, GetModuleHandleA(NULL), 0x400000, "SC3U")   line 3395
-gzlog   -> GetModuleHandleA("GZGraphicD.dll")                            line 3268
```

The city-load path is in **SIMCITY.DLL**, so neither table can rebase it. That is the blocker, not a missing
address.

### 19b. Change 1 — one line, gives "was our file opened at all"

`-filetrace` already IAT-hooks `CreateFileA` **and** `GetFileAttributesA` on SC3U.exe. Its filter
(`sc3probe.c` line 414) is:

```c
return n && (ci_contains(n, "SC3Tune") || ci_contains(n, ".PAK") || ci_contains(n, "\Sys\\"));
```

Adding the city-save extensions makes every open of a city file visible, with the returned handle logged:

```c
return n && (ci_contains(n, "SC3Tune") || ci_contains(n, ".PAK") || ci_contains(n, "\Sys\\")
          || ci_contains(n, ".sc3") || ci_contains(n, ".sct")
          || ci_contains(n, ".snr") || ci_contains(n, ".st3"));
```

This alone is worth having: if the load dialog header-reads each city to display its name, then merely
*opening* the dialog exercises our file's container parse, and the trace shows whether the open succeeded.

### 19c. Change 2 — a per-module table, gives unattended accept/reject

Generalise the table loader to take a module name, e.g. `-modlog SIMCITY.DLL <table>` calling
`fnlog_load(path, GetModuleHandleA("SIMCITY.DLL"), 0x10000000, "SIMCITY")`. Then this table answers T1 without
any UI interaction, because a load either reaches these functions and returns true or it does not:

```
# cSC3City load/save path -- SIMCITY.DLL, image base 0x10000000
# vtable 0x10013260, slot numbers from GZCOM_INTERFACE_CATALOGUE.md section 13
0x10003b8b  city_init_dbsegment      # slot   7  Init(cIGZDBSegment*)  <-- THE LOAD ENTRY
0x1000429d  city_save_dbsegment      # slot   8  Save(cIGZDBSegment*)
0x10007b28  city_do_load_city        # slot  48  DoLoadCity(bool)      <-- user-initiated load
0x10007a6d  city_do_new_city         # slot  47  DoNewCity(bool)       # control: distinguishes load from new
0x1000ebe6  city_do_save_city        # slot  49  DoSaveCity(bool)
0x10004e30  city_shutdown            # slot   9  Shutdown
0x10008d90  city_can_city_save       # slot 148  CanCitySave
```

And the per-layer deserialisers, which is where a bad payload would actually be rejected. All named by this
session, so each already has a `functions.csv` row:

```
# SIMRCI.DLL   base 0x10000000
0x1002e887  valvelayer_init_dbsegment   # cISC3CityLayer slot 9 on cSC3ValveLayer (section 7)
0x100314f0  zonelayer_init_attach       # the zone layer's load path (section 8)
0x100320e7  zonelayer_save
# SIMDIRT.DLL  base 0x10000000
0x1002046c  <vtable>                    # cSC3DirtBag. CORRECTED in section 21: the DBSegment Init is
#                                       # slot 7 OR 8, NOT slot 9 -- slot 9 is the 1-arg Init(cISC3City*).
#                                       # Both 2-arg forms are ret 8 so arity cannot separate them; read
#                                       # the bodies before trusting either for a load trace.
```

**The read to make:** with the edited file loaded, `city_init_dbsegment` and every per-layer
`*_init_dbsegment` should hit once and the run should reach `SimulationBegin`. A file the loader rejects will
show `city_do_load_city` hit with `city_init_dbsegment` either absent or followed immediately by
`city_shutdown`.

### 19d. Do not repeat the mistake this session nearly made

Whoever runs this must use `harness_run.ps1` with `-Runs 3` or more. §T1 in `POST_P1.md` records a first run
that FAILED and a control that PASSED back to back, which reads as "the game rejects our file" and is **wrong**
— repeating gave 3/3 PASS and the FAIL was a U-032 transient. A single run is not evidence, and this is the
domain where that rule has already produced one false negative in one afternoon.

---

## 20. cSC3CitySpriteCellMap — 104 of 104, zero mismatches

`SIMSPR.DLL` `.rdata` **`0x1006250c`**, located by §18's bulk pass as a unique hit project-wide. Re-checked
here slot by slot with the size-bounded extractor: **104 of 104 arity-matched, 0 mismatches.** The largest
class after `cISC3City`, and the cleanest match in the catalogue.

This is the isometric city view's sprite grid — what turns the cell world into screen pixels.

### 20a. The two decisive slots

**Slot 3 `Init`, `ret 0x24` = nine arguments.** The header declares exactly nine
(`cellCountX, cellCountZ, screenWidth, screenHeight, u5, u6, zoom, rotation, u9`). A 9-argument arity match is
the single most distinctive slot in any class walked this session — there is no plausible way for a wrong
identification to land on it.

**A four-dword projection block.** Slots 17/21/22/23 are 4-byte field getters on consecutive dwords:

| slot | method | field |
|---:|---|---|
| 17 | `GetRotate` | `+0x2c` |
| 21 | `ScreenCellSizeX` | `+0x30` |
| 22 | `ScreenCellAdjustmentY` | `+0x34` |
| 23 | `ScreenCellSizeZ` | `+0x38` |

Slots 21-23 are the **isometric projection constants** — cell width, vertical adjustment, cell depth in screen
pixels. Those three plus the rotation at `+0x2c` are the whole screen-space parameterisation of the view.

> **Worth noting against a temptation.** Slot 23's implementation sits at `0x100550a1`, nowhere near its three
> siblings at `0x100056e7`/`eb`/`ef`. Address proximity did **not** identify these — slot position and the +4
> field stride did. §10's negative result (never use address order as an ordering witness) applies to
> *grouping* as well as ordering.

### 20b. The structure of the class

`RotateLeft` (19) and `RotateRight` (20) are identical 40-byte siblings, both opening `mov eax,[ecx+0x2c]`, and
both wrap slot 18 `SetRotate` (430 bytes) — the real implementation. `StartChangeSpriteBatch`/
`EndChangeSpriteBatch` (28/29) are the sprite-mutation batch guard, the same idiom as `DirtBag::LockUpdates`
in §14.

**`DoPick` (slot 32) is 2933 bytes, the largest method on the class** — screen-to-cell hit testing, i.e. what
turns a mouse position into a tile. For a modding toolkit that is the interesting one: it encodes the exact
inverse of the isometric projection the three constants above define.

### 20c. No overload pairs, so no rule test

Unlike every other class walked, `cISC3CitySpriteCellMap` has **no same-name overload pairs**, so it neither
confirms nor challenges the 12-of-12 reversal rule. Stated explicitly because "0 mismatches" could otherwise be
read as a thirteenth confirmation, and it is not one.

### Committed

14 rows at **C3**: `Init`, the four projection/rotation getters, `SetRotate` and both rotate wrappers,
`ZoomOut`, the batch-end guard, `ChangeSprite`, `GetCellsForViewCornersUnclipped`, `IsSpriteVisible`, and
`DoPick`. `verify_worker_rows.py`: **0 of 14 flagged**. Project C3 count 176 → 190.

**Scope, stated plainly:** all 104 slots are *validated* by arity, but only these 14 are *named*. The other 90
are identified by slot position and can be named mechanically from the header whenever they are needed — the
map is in this section, the work is not done.

### 20d. All 104 slots named — 14 read, 90 mechanical

The remaining 90 slots are now named from the header by slot position. **Confidence C1, not C2**, and the
distinction is deliberate: C2 in this project means the decompilation was read, and these bodies were not. Each
note says so explicitly (*"the slot is confirmed, the body has NOT been read"*). Marking 90 unread functions C2
would also have inflated the `>=C2` gate metric — SIMSPR is outside the eleven core-sim modules so the gate is
untouched here, but the principle is why C1 was chosen.

Audited before generating, because mechanical naming is exactly where a silent collision would hide:

```
duplicate METHOD NAMES in the header        : none
implementations shared by >1 slot           : 0
slots whose impl has no functions.csv row   : 0
duplicate generated names                   : none
resulting rows                              : 104 total, 104 unique names
```

**A convention fix on my own earlier work.** The 14 hand-named rows from §20 used compressed lowercase
(`sc3_spritecellmap_dopick`, `_getrotate`) while the mechanical pass produced snake_case (`_do_pick`,
`_get_rotate`). `CLAUDE.md` specifies `sc3_<subsystem>_<verb>_<noun>`, so the mechanical form is the correct one
and my hand-written 13 were not. Renamed, with the old name recorded in each note. 104 of 104 now match
`sc3_spritecellmap_[a-z0-9_]+`.

**The mechanical pass found more structure than the hand pass did.** The view-state field block is larger than
§20a reported:

| field | accessor |
|---|---|
| `+0x14` / `+0x18` | `GetActualGridSizeX` / `GetActualGridSizeZ` |
| `+0x1c` / `+0x20` | `GetDrawGridSizeX` / `GetDrawGridSizeZ` |
| `+0x28` | `GetZoom` |
| `+0x2c` | `GetRotate` |
| `+0x30` / `+0x34` / `+0x38` | `ScreenCellSizeX` / `ScreenCellAdjustmentY` / `ScreenCellSizeZ` |
| `+0x74` | `GetCityBufferPtr` |
| `+0x114` | `GetUnusedCellCount` |

So the class keeps **two grid sizes** — an *actual* grid and a *draw* grid — which is consistent with slot 41
`ActualGridToDrawGridMicroVirtual` converting between them. That pair was invisible until all 104 were named.

**One irregularity, logged as U-050 rather than smoothed over.** Two distinct slots return `+0x38`: slot 23
`ScreenCellSizeZ` (`ret`, 0 args) and slot 57 `GetLowestSpriteHeight` (`ret 4`, 1 arg — and it **ignores** the
argument). Both fit their slot's arity and the class scored 104/104, so the arity evidence cannot separate them.
Every other member of the block has exactly one accessor, which makes `+0x38` the sole anomaly.

### 20e. U-050 resolved — the shared `+0x38` is real, and the header is right

§20d flagged two slots returning the same field. Reading slot 57's callers was the recorded plan and it went
nowhere useful: the two `+0xe4` virtual call sites in SIMSPR both pass **two** arguments, while slot 57 is
`ret 4` = one, so those sites dispatch on a different class that happens to have something else at `+0xe4`.
`+0xe4` is a common offset and matching on it alone is the same loose-filter mistake as the rest of this
document. Slot 57 has **no** identified caller.

Three other checks settle it instead:

**1. The neighbourhood is saturated.** Slots 52-62 are eleven consecutive arity matches with no mismatch:

| slot | method | want | got |
|---:|---|---|---|
| 52 | `GetPixelSizeOfSprite` | `0x10` | `0x10` |
| 53 | `SpritePixelToMicroActualGrid` | `0x1c` | `0x1c` |
| 54 | `GetEntireCityBaseRect` | `0x8` | `0x8` |
| 55 | `GetLowestTerrainAltitude` | `0x4` | `0x4` |
| 56 | `GetHighestTerrainAltitude` | `0x4` | `0x4` |
| **57** | **`GetLowestSpriteHeight`** | `0x4` | `0x4` |
| 58 | `GetHighestSpriteHeight` | `0x4` | `0x4` |
| 59 | `GetHeightOfSprite` | `0xc` | `0xc` |
| 60 | `Position3DToWindowPixel` | `0x14` | `0x14` |
| 61 | `IsPointWithinCityOutline` | `0xc` | `0xc` |
| 62 | `GetUnusedCellCount` | `0x0` | `0x0` |

Slot 57 cannot be shifted without breaking ten other slots, including the highly distinctive `0x1c` and `0x14`.

**2. The block is coherent.** Slots 55/56 are an identical-shape 20-byte Lowest/Highest **terrain** pair, both
opening `cmp byte [esp+4],0 ; movzx eax, byte [ecx..]`. Slots 57/58 are the matching Lowest/Highest **sprite**
pair. That is a 2×2 Lowest/Highest × Terrain/Sprite block, and slot 57 sits exactly where it belongs in it.

**3. No sharing.** `0x1000b2a7` occupies exactly **one** data slot in the entire module — `0x100625f0`, which is
vtable base + 57×4. It is used only as slot 57 of this one vtable.

Note the asymmetry inside the pair: slot 57 is **6 bytes** (a stored constant) while slot 58
`GetHighestSpriteHeight` is **55 bytes** (computed). That is what you would expect if the *lowest* sprite height
is fixed while the *highest* must be searched for. Slot 57 ignoring its argument is then an implementation that
returns that constant regardless of which sprite is asked about.

So both names stand and `+0x38` is genuinely read by two accessors. **What is not established** is *why* the two
quantities coincide — whether a flat sprite's height equals the isometric cell depth for a semantic reason, or
whether this is an implementation shortcut. Neither name depends on the answer, so it is left unresolved rather
than guessed.

---

## 21. The §18 false negative diagnosed — a threshold, not a bug, and a correction it exposed

§18c flagged `cISC3DirtBag` as a genuine false negative: located by hand at `SIMDIRT.DLL` `0x1002046c` with
91.8%, yet reported 0/0 by the bulk pass. Diagnosed stage by stage against the known-good address.

### 21a. Root cause: the two passes used different arity extractors

| stage | result |
|---|---|
| header parse | 88 chained methods — correct |
| `functions.csv` rows for SIMDIRT | 789 — fine |
| window test (slots 3..90 all `.text` pointers) | **True** — the vtable was found |
| **arity, STRICT** (bulk.py, size-bounded, all `ret N` in body) | **75/85 = 88.2%** → below the 0.90 bar → **filtered out** |
| **arity, LOOSE** (dirt.py, first `ret` within 700 bytes) | 67/73 = 91.8% → above 0.90 → passed |

**Not a logic bug — a miscalibrated threshold.** The scanner located the vtable on every pass. The strict
extractor introduced in §14d correctly detects *more* mismatches, and a class carrying four reversed overload
pairs plus the `Init` triple below has enough of them to sink it under 0.90.

The irony is worth stating plainly: **the better measurement caused the miss.** §18c's "undiagnosed failure
mode" was a 0.90 bar inherited from an era when the extractor was looser and therefore flattered every class.

### 21b. Recalibrated to 0.80 — DirtBag returns as a *unique* hit

```
cISC3DirtBag              88   cands 1   88.2%   75/85   SIMDIRT.DLL 0x1002046c
```

Exactly the ground-truth address, single candidate. Two more classes also surfaced:

| class | module | vtable | m/c |
|---|---|---|---|
| `cISC3BuildingLayer` | SIMGEOM | `0x100292c0` | 22/26 = 84.6% |
| `cISC3OccupantAttribCache` | SIMINIT | `0x1002fb44` | 13/15 = 86.7% |

**The cost, stated so §18b is not over-trusted.** A lower bar inflates candidate counts on small classes:
`cISC3OccAttribOverRide` 61 → 420, `cISC3CityAgentType` 19 → 80, `cISC3WinMain` → 136. The usable rule:

> **Trust a location when the candidate count is small AND the method count is large.** Twelve classes now have
> a *unique* hit — CitySpriteCellMap, CityView, CityViewIso, DisasterLayer, PollutionLayer, ResidentialLayer,
> City, CitySchemeMgr, WinCityView, ZoneLayer, DirtBag, BuildingLayer. A row with 80+ candidates on a 12-20
> method class is noise, not a result.

Five classes remain NOT FOUND with 0/0 comparable — `AuraLayer`, `CityCellMap`, `CitySpriteManager`,
`CrimeLayer`, `LandValueLayer` — for the cause already diagnosed in §18c: their vtables are dominated by 8-byte
adjustor thunks with no `ret`. No threshold can help a class with nothing measurable.

### 21c. ⚠ It exposed an error of mine in §19's T1 spec

The strict extractor flagged slots **7 and 9**, which the loose one had marked unmeasurable. Those are
`cISC3DirtBag`'s three-way `Init`:

| slot | header says | actual | |
|---:|---|---|---|
| 7 | `Init(cISC3City*)` — 1 arg | `ret 8` = **2 args**, 901 B | mismatch |
| 8 | `Init(cISC3City*, cISC2Importer*)` — 2 args | `ret 8`, 1403 B | ok |
| 9 | `Init(cISC3City*, cIGZDBSegment*)` — 2 args | `ret 4` = **1 arg**, 1481 B | mismatch |

**So slot 9 is the 1-argument `Init(cISC3City*)`, not the DBSegment loader.** §19's trace table for T1 listed
"DirtBag `0x1002046c` slot 9 = `Init(City*,DBSegment*)`". That is **wrong**, and it is exactly the kind of error
that propagates, because another session was told to build a city-load trace from that table. §19 is corrected
in place. The DBSegment `Init` is at slot 7 or 8; both are `ret 8`, so arity cannot separate them and the bodies
must be read before either is used as a load-path trace point.

### 21d. The overload rule extends from pairs to groups

Twelve of twelve *pairs* were reversed (§14d, §17). This `Init` **triple** is the first group larger than two,
and it is permuted the same way: the narrower member (1 arg) sits at the **later** slot, the wider ones earlier.
U-042's rule statement is updated from "pair" to "group".

That also explains why §14 missed it: §14 used the loose extractor, which marked slots 7 and 9 unmeasurable, so
the triple never registered as a mismatch. §14 committed no rows for those slots, so **no tracker row is wrong**
— only the §19 prose was.

---

## 22. DirtBag slots 7 vs 8 — narrowed, not closed

§21c established that `cISC3DirtBag` slot 9 is the 1-argument `Init(cISC3City*)`, so §19's T1 trace table was
wrong to call slot 9 the DBSegment loader. The loader is slot 7 or slot 8, both `ret 8`. This section tried to
settle which and **did not fully succeed**; recorded here so the next attempt does not repeat the dead ends.

### 22a. Two discriminators that failed

**Vtable-call fingerprint against the known `Save`.** `Save` (slot 10) is a known `(City*, DBSegment*)` method
and calls `+0xcc`/`+0xd0` twice each; slot 7 does the same and slot 8 does not. That looked decisive and is
worthless: **slot 9 — the 1-argument `Init`, which receives no segment at all — calls that pair sixteen times.**
`+0xcc`/`+0xd0` is something ubiquitous on the receiver, not a DB-segment signature. Another filter that matched
more than it was asked to.

**Hard constants.** Neither candidate, nor `Save`, references `GZIID_cIGZDBSegment` `0xc019963e` or
`GZIID_cIGZDBRecord` `0x4019960a` — they take the segment as a parameter, so no `QueryInterface` is needed. And
SIMDIRT contains no `.sc2` or importer strings at all, so the SC2 side offers no anchor either.

### 22b. What the caller side gives

`cISC3City` has the same `Init` triple. Checking which DirtBag offset each city entry point calls
(slot 7 = `+0x1c`, slot 8 = `+0x20`):

| city method | calls `+0x1c` | calls `+0x20` |
|---|---:|---:|
| `cISC3City::Init(cIGZDBSegment*)` — SIMCITY `0x10003b8b` | 0 | 0 |
| `cISC3City::Init(cISC2Importer*)` — SIMCITY `0x10003178` | 0 | **1** |

The SC2-import entry point calls layer `+0x20` and the DB-segment entry point calls neither. Since
`cISC3CityLayer`'s contract places `Init(City*, Importer*)` at slot 8 = `+0x20`, and `cISC3DirtBag` flattens
that contract into its own vtable at the same slots (§14a), the reading is: **slot 8 is the Importer form,
therefore slot 7 is the DBSegment form.** That would make the permutation 7↔9 with slot 8 unmoved, which is
also consistent with §21d's "narrower member at the later slot".

### 22c. `[UNCERTAIN]` — why this is not called closed

The `+0x20` call site was **not verified to have a DirtBag as its receiver**. It is one call in a function that
touches many layers, and the argument that it must be a layer rests on the contract's slot numbering rather than
on the decompilation naming the object. One unverified receiver is not the standard the rest of this catalogue
has been held to.

**Net position for the T1 spec:** slot 9 is definitively excluded (`ret 4`, 1 argument). Between 7 and 8, slot 7
is the better-supported candidate. §19's table already carries the correction and the warning to read the bodies
before trusting either as a load-trace point; that warning stands. Anyone building the trace should simply
instrument **both** `0x10004a00` (slot 7) and `0x10004420` (slot 8) — the run itself will then say which one
fires on a city load, which is cheaper and more conclusive than any amount of static argument.

---

## 23. CityView / CityViewIso share a vtable — checked, and that is correct

§18b listed `cISC3CityView` and `cISC3CityViewIso` both resolving to `SIMSPR.DLL` `0x10063390`, which reads
like one identification must be wrong. It was worth checking rather than assuming either way. **Both are right,
and the shared address is what the inheritance requires.**

### 23a. Why one vtable satisfies both chains

```
class cISC3CityView    : public cIGZUnknown      34 methods -> slots 3..36  (37 total)
class cISC3CityViewIso : public cISC3CityView     4 methods -> slots 3..40  (41 total)
```

`cISC3CityViewIso` **derives from** `cISC3CityView`, so the CityView expected-arity vector is a strict **prefix**
of the Iso one. A concrete class implementing Iso necessarily satisfies the CityView fingerprint over its first
37 slots. The fingerprint method reporting both is correct behaviour, not a collision — and it is a different
situation from §20d's *shared implementation* case, which genuinely would be an error.

The vtable at `0x10063390` runs **92 consecutive code slots**, comfortably past the 41 the Iso chain needs.

### 23b. The Iso extension is present, and two of its slots confirm each other

| slot | header method | want | got | body |
|---:|---|---|---|---|
| 37 | `GetCitySpriteManager()` | `0` | `0` | `mov eax,[ecx+0x154] ; ret` |
| 38 | `GetCitySpriteCellMap()` | `0` | `0` | `mov eax,[ecx+0x158] ; ret` |
| 39 | `DoScreenShake(i32,i32,i32,i32,bool,i32)` | `0x18` | `0x18` | `cmp byte ptr [ecx+0xd0], 0` … |
| 40 | `IsScreenShaking()` | `0` | `0` | `mov al, byte ptr [ecx+0xd0] ; ret` |

`DoScreenShake` at **`ret 0x18` = six arguments** is the distinctive one; six is rare enough that no wrong
identification lands on it. And slots 39/40 form a pair on a single byte: `DoScreenShake` gates on
`byte [ecx+0xd0]` and `IsScreenShaking` returns it — the same actor/predicate idiom as
`cISC3BudgetLayer::SetMarxism` / `MarxismIsOn` (§11d).

Slots 37/38 are adjacent subsystem pointers at `+0x154` and `+0x158`. **Slot 38 is the isometric view's handle
on the class walked in §20** — `cSC3CitySpriteCellMap`, vtable `0x1006250c` — so the view and the sprite grid are
now linked in both directions: the cell map defines the projection constants (§20a) and the view holds the cell
map here.

### 23c. The labelling should be sharpened, though

§18b's phrasing is imprecise even though its addresses are right. The accurate statement:

> `0x10063390` is the vtable of a concrete class that implements **`cISC3CityViewIso`**. It satisfies
> `cISC3CityView` because Iso *is-a* CityView, not because there is a separate plain-CityView class.

And there is no separate one: the recalibrated scan gives **one candidate each** for both interfaces, both this
address. So in this build **every city view is an isometric view** — consistent with SC3000 having no other
projection.

### Committed

4 rows at **C3** (`sc3_cityviewiso_*`): the two subsystem getters, `DoScreenShake` and `IsScreenShaking`.
`verify_worker_rows.py`: **0 of 4 flagged**. Project C3 190 → 194.

**A note on the fingerprint method, since this is its first false-alarm-shaped result:** two classes resolving to
one address means *prefix inheritance* (correct) or *shared implementation* (an error). Distinguish them by
checking the header for a derivation. Only the second case needs fixing.
