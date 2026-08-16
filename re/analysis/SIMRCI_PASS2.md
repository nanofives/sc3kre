# SIMRCI.DLL — second pass

Scope note: JOB 1 had no C1 rows (module is all-C2) and JOB 2 found no OPEN section. The live backlog is the doc's **"Next probes"** list (3 items). All three are addressed below. Every claim is from the text export; vtable-slot→function bindings that live in `.rdata` are called out as the one class of thing not resolvable here.

## 1. Promoted rows (newly raised to C2)

These are functions I read in full, described mechanically, whose callees I identified, and named. Confidence C2 only.

```csv
rva,subsystem,confidence,new_name,evidence
0x1002dede,S5-valve,C2,sc3_valve_ctor,"factory 0x100367a7 new(0x58)->this; installs vtables PTR_FUN_1004cee4(+0x00)/PTR_LAB_1004ce9c(+0x04) over transient PTR_LAB_1004cf20/PTR_LAB_1004c22c; zeroes +0x08..+0x14, ctor-inits subobjects at +0x18 and +0x28 via FUN_100109a1, zeroes +0x24 and +0x34..+0x54 — the exact fields FUN_1002efe8 reads/writes"
0x100367a7,S5-valve,C2,sc3_valve_factory,"GZCLSID 0x60a42f32 -> operator_new(0x58) -> ctor FUN_1002dede; returns this+0x10 on success (0 on alloc fail), standard SIMRCI factory shape"
0x10030c5b,S4-zone,C2,sc3_zone_parse_developer_desc,"ZoneDeveloperDescriptions row cb; atoi(field0) via FUN_1003b5ce; tokenizes field via FUN_10036fc1(&DAT_100574c4); GZCOM lookup GetClassObject(0x2108580c) via FUN_1003ae82; writes parsed int through target vtable slot +0x58 and layer vtable slot +0x14c"
0x10030d64,S4-zone,C2,sc3_zone_parse_developer_rules,"ZoneDeveloperRules row cb; parses developer index local_60=atoi(name); GATES on *(param_3 + local_60*8 + 0x19c)!=0 (the developer table); GetClassObject(0xa1f3e1db); loops rule fields via FUN_10036fc1(&DAT_100574c4/&DAT_10057624), atoi each (FUN_1003b5ce); registry FUN_1003cf77 lookup key 0xa1f592f9; on success stores via FUN_100310d3(param_3,(byte)local_60,obj)"
0x1002f4ed,S5-valve,C2,sc3_valve_apply_agent,"thiscall; caches this+0xc; walks the AgentValveEffects global list DAT_10058720 via FUN_10029c40; reads 20-byte effect record fields +0x08(agentType, piVar3[2]) +0x0c(short, piVar3[3]) +0x0e(short); tests sibling layer via *(this+8) vtable +0x14; inserts via FUN_1002fb8b(this+0x10)"
```

## 2. "Next probes" resolutions

### Probe #1 — Pin the ValveLayer class → **RESOLVED (class id + ctor + size + vtables); one residual needs VtableDump**

- **GZCLSID `0x60a42f32`** → factory `FUN_100367a7` `0x100367a7` → `operator_new(0x58)` (88 bytes) → ctor `sc3_valve_ctor` `0x1002dede`. [CONFIRMED @ 0x10036382:25, 0x100367a7:17-20, 0x1002dede]
- **Proof it is the valve object (not adjacency-only):** `sc3_valve_ctor` initializes exactly the field set the valve methods touch. `sc3_valve_apply_effects` `0x1002efe8` reads `this+0x10`/`+0x14` (sibling-layer vtable pointers), `this+0x18` (internal container), `this+0x38`/`+0x3c` (grid objects) and rotates accumulators `this+0x40=+0x4c, +0x44=+0x50, +0x48=+0x54, then zero +0x4c..+0x54` [CONFIRMED @ 0x1002efe8:138-143]. The ctor zeroes `+0x08..+0x14` and `+0x34..+0x54` and ctor-inits subobjects at `+0x18` and `+0x28`, all inside the 0x58 allocation [CONFIRMED @ 0x1002dede:19-36]. Field-set match + 0x58 size match + same GZCLSID → the pin holds without runtime.
- **Vtables installed:** primary `PTR_FUN_1004cee4` at `+0x00`, secondary interface `PTR_LAB_1004ce9c` at `+0x04` (over transient `PTR_LAB_1004cf20`/`PTR_LAB_1004c22c`). [CONFIRMED @ 0x1002dede:17-18,37-38]
- **Residual:** proving `0x1002efe8`/`0x1002f218`/`0x1002f4ed` are *slots* of `PTR_FUN_1004cee4` (i.e. their vtable index) needs the vtable array itself, which is in `.rdata` and not in the decompiled bodies. **Breaker: `VtableDump.java` on `PTR_FUN_1004cee4` (0x1004cee4) and `PTR_LAB_1004ce9c`.** The `goValveLayer::EndOfMonth` `[iOS-HINT]` is unchanged — still needs the slot index + a monthly-cadence caller.

### Probe #2 — Map the other 36 factories → **RESOLVED (full table below)**

Every factory is the same 3-step shape (`operator_new(size)` → `ctor(this)` → return). Full `(GZCLSID, factory, alloc size, ctor)` map, all [CONFIRMED @ 0x10036382 for the id→factory edge and at each factory body for size→ctor]:

| # | GZCLSID | factory | size | ctor |
|--|--|--|--|--|
| 1 | 0x409ff3ba | FUN_10036660 | 0x2d0 | FUN_100310f5 **(ZoneLayer, known)** |
| 2 | 0x20ec9849 | FUN_1003669e | 0x20 | FUN_1000e772 |
| 3 | 0xa106cf3d | FUN_100366d0 | 0x24 | FUN_100158d3 |
| 4 | 0x60a2966e | FUN_10036702 | 0xe0 | FUN_1001b2b9 |
| 5 | 0xa106c520 | FUN_10036740 | 0x6d8 | FUN_10020dfd **(ResLayer candidate)** |
| 6 | 0x60a42f32 | FUN_100367a7 | 0x58 | FUN_1002dede **(ValveLayer, now pinned)** |
| 7 | 0xc0f1ec40 | FUN_10036775 | 0x44 | FUN_10042a94 |
| 8 | 0x619ba64e | FUN_100367d9 | 0x98 | FUN_10028198 |
| 9 | 0x41a3adc1 | FUN_1003680e | 0x98 | FUN_1000f022 **(ComLayer candidate)** |
| 10 | 0xe1a53b30 | FUN_10036843 | 0xd0 | FUN_10016290 **(IndLayer candidate)** |
| 11 | 0x82d2d72b | FUN_10036878 | 0x70 | FUN_1002c73f |
| 12 | 0xc1f81e7e | FUN_100368aa | 0x70 | FUN_10004447 |
| 13 | 0x82348de5 | FUN_100368dc | 0x80 | FUN_100194cf |
| 14 | 0xa2c1eda3 | FUN_10036911 | 0x48 | FUN_10001020 |
| 15 | 0x61f44687 | FUN_1003694c | 0x40 | FUN_10029cd1 |
| 16 | 0xe22f4a83 | FUN_10036987 | 0x48 | FUN_10010f52 |
| 17 | 0x630ea608 | FUN_100369c2 | 0x48 | FUN_10012413 |
| 18 | 0xa22653c0 | FUN_100369fd | 0x48 | FUN_10026644 |
| 19 | 0x222c9d00 | FUN_10036a38 | 0x48 | FUN_1002713c |
| 20 | 0x822c9d13 | FUN_10036a73 | 0x48 | FUN_1002027b |
| 21 | 0x422b55f2 | FUN_10036aae | 0x48 | FUN_100142d7 |
| 22 | 0x822c9d24 | FUN_10036ae9 | 0x48 | FUN_10014de5 |
| 23 | 0xc22c9d34 | FUN_10036b24 | 0x48 | FUN_1001375e |
| 24 | 0x422c9d52 | FUN_10036b5f | 0x48 | FUN_1000ca4c |
| 25 | 0x622c9d42 | FUN_10036b9a | 0x48 | FUN_1000d80c |
| 26 | 0x822c9d62 | FUN_10036bd5 | 0x48 | FUN_1000bf24 |
| 27 | 0xc2d3fd7e | FUN_10036c10 | 0x50 | FUN_1002ce0e |
| 28 | 0xe2d3fd92 | FUN_10036c4b | 0x48 | FUN_1002bbf3 |
| 29 | 0x2207d9ee | FUN_10036c86 | 0x50 | FUN_10002f45 |
| 30 | 0x81ffc3ce | FUN_10036cc1 | 0x50 | FUN_1002abb7 |
| 31 | 0x42e88384 | FUN_10036cfc | 0x14 | FUN_1003a218 |
| 32 | 0x612a8f75 | FUN_10036d3a | 0x48 | FUN_10009eed |
| 33 | 0xe3319eb4 | FUN_10036d75 | 0x40 | FUN_1000793d |
| 34 | 0xa3319f62 | FUN_10036db0 | 0x3c | FUN_10008aae |
| 35 | 0xc2ec529c | FUN_10036deb | 0x48 | FUN_10004c2a |
| 36 | 0x2123cb83 | FUN_10036e26 | 0x4c | FUN_10006416 |
| 37 | 0x0356c518 | FUN_10036e61 | 0x2c | FUN_10009bf3 |

**Matching Res/Ind/Com loaders to their ctors — STILL OPEN (but narrowed).** The three loaders `sc3_res_load_tuning 0x10022ac6`, `sc3_ind_load_tuning 0x10015dc0`, `sc3_com_load_tuning 0x1000eccd` all take `void` and write **module globals**, not a `this` [CONFIRMED @ 0x1002dff3, and each loader's signature `FUN_xxxx(void)`]. Grep over all 3,263 bodies finds **no static caller** for any of the four load functions — they are reached only through a vtable slot or a message-dispatch table in `.rdata`. So the loader→owning-class edge cannot be drawn from the text export. Narrowed candidates by object weight + address neighborhood (these are **[UNCERTAIN]**, not asserted):
- ResLayer = ctor `FUN_10020dfd` / GZCLSID `0xa106c520` — the only 0x6d8-byte object, a full GZCOM layer (installs `PTR_LAB_1004ca40` + interface `PTR_LAB_1004c714`/`PTR_LAB_1004c22c`, builds linked-list node at `+0x60`, subobjects via `FUN_10036ee3`/`FUN_1003b6f0`/`FUN_10025ea8`) [CONFIRMED shape @ 0x10020dfd:18-40]; loader `0x10022ac6` sits ~0x1d00 past it.
- IndLayer = ctor `FUN_10016290` / GZCLSID `0xe1a53b30` (0xd0), loader `0x10015dc0` adjacent.
- ComLayer = ctor `FUN_1000f022` / GZCLSID `0x41a3adc1` (0x98), loader `0x1000eccd` adjacent.
- **Breaker:** `VtableDump.java` on each candidate ctor's installed vtable — the loader address will appear as one of the slots (or a data xref from the loader RVA back to a vtable/registration table resolves it directly).

### Probe #3 — Confirm the 23-slot `0x19c` table = zone developers → **CONFIRMED**

`sc3_zone_parse_developer_rules` `0x10030d64` parses a developer index and indexes the table by it: `if (*(int *)((int)param_3 + local_60 * 8 + 0x19c) != 0)` where `local_60 = FUN_1003b5ce(developer-name-field)` (atoi) [CONFIRMED @ 0x10030d64:65,71]. Stride 8, base byte `0x19c`, indexed by the parsed developer number — this is exactly the "23-slot table at 0x19c, stride 8" the ctor builds. On a matched rule it stores the built rule object back into the slot via `FUN_100310d3(param_3,(byte)local_60,local_14)` [CONFIRMED @ 0x10030d64:140]. The description callback `FUN_10030c5b` writes into the same layer through vtable slot `+0x14c` then the developer's `+0x58` [CONFIRMED @ 0x10030c5b:48-49]. The `goZoneDeveloper`/`goZoneLayer` structural match remains an `[iOS-HINT]`; the transport-proximity / road-count field it predicts is not visible in these two callbacks.

## 3. New findings

1. **Four new GZCLSIDs, resolved via `FUN_1003ae82` (GZCOM GetClassObject) in the zone parsers** [CONFIRMED]:
   - `0x2108580c` — zone developer **description** record class (`FUN_10030c5b:43`).
   - `0xa1f3e1db` — zone developer **rules** record class (`FUN_10030d64:73`).
   - `0xa1f592f9` — a rule sub-object, resolved through a second registry `FUN_1003cf77` (`FUN_10030d64:115`).
   - `0x61190076` — **not a class id**: a sentinel agent-type key compared in `sc3_valve_get_or_create` (`FUN_1002f218:33`); when the lookup key equals it, the method returns the cached object at `this+0x20` instead of allocating.
2. **Valve effect global tables — the three named INI sections and their record producers** [CONFIRMED @ 0x1002dff3]:
   - `AgentValveEffects` (`s_..._10058090`) → `DAT_10058720`, row cb `FUN_1002e4ad` (0x1002dff3:65-67).
   - `ConnectionValveEffects` (`s_..._10058078`) → `DAT_10058710`, row cb `FUN_1002e4ad` (0x1002dff3:71-73).
   - `OrdinanceEffects` (`s_..._10058064`) → global `0` slot, row cb `FUN_1002e217` (0x1002dff3:77-79).
   The loader also swaps/rotates the head/tail of `DAT_10058720` and `DAT_10058710` before reload (`FUN_1002fb80`/`FUN_1002fa6d`/`FUN_1002f9c4`, 0x1002dff3:39-54).
3. **20-byte valve effect record layout re-confirmed from a second witness** (`sc3_valve_apply_agent`): `+0x08` agentType key (int), `+0x0c` short, `+0x0e` short [CONFIRMED @ 0x1002f4ed:39-41], matching the prior doc's `[CONFIRMED @ 0x1002e4ad]`.
4. **`sc3_valve_apply_effects` demand-category vtable slots** on the sibling layer at `this+0x10`: category 0→slot `+0xdc`, 1→`+0xd8`, 2→`+0xec`, 3→`+0xf0`; ordinance pass drives `this+0x14` slot `+0xc`; grid pass drives `this+0x38` slots `+0xc/+0x10/+0x3c` and `this+0x3c` slots `+0x34/+0x40` [CONFIRMED @ 0x1002efe8:34-137]. These are the concrete vtable indices for whoever runs VtableDump next.
5. **Config field-name string globals** used by the zone tokenizer `FUN_10036fc1`: `DAT_100574c4` (developer desc/rule fields) and `DAT_10057624` (a rules-only field) [CONFIRMED @ 0x10030c5b:35, 0x10030d64:62,81,90,100]. Worth resolving to their literal key text (they are in `.rdata`; `pe_read.py` at those RVAs).

## 4. Revised OPEN list (replace the doc's "Next probes")

1. **Valve vtable slot indices** — run `VtableDump.java` on `PTR_FUN_1004cee4` (0x1004cee4) and `PTR_LAB_1004ce9c` to confirm `0x1002efe8`/`0x1002f218`/`0x1002f4ed`/`0x1002eee1`/`0x1002ef26` are its slots, closing the last valve residual and testing the `goValveLayer::EndOfMonth` `[iOS-HINT]`.
2. **Res/Ind/Com loader → owning class** — `VtableDump.java` on the three candidate ctors' vtables (`FUN_10020dfd`→`PTR_LAB_1004ca40`, `FUN_10016290`, `FUN_1000f022`); the loader RVA (`0x10022ac6`/`0x10015dc0`/`0x1000eccd`) will surface as a slot, or a data xref from the loader RVA resolves it. Only then can `0xa106c520`/`0xe1a53b30`/`0x41a3adc1` be asserted as Res/Ind/Com.
3. **The remaining 30 unclassified GZCLSIDs** (factories #2-4,7-8,11-37) — read each ctor's installed vtable + subobject init to classify (the `0x48`-byte cluster #14-35 with sequential `0x?22c9d??` ids looks like one record family; needs bodies read).
4. **Resolve the new class-id string text** for `0x2108580c` / `0xa1f3e1db` / `0xa1f592f9` and the field-name globals `DAT_100574c4` / `DAT_10057624` (`pe_read.py` over `.rdata`).
5. **Zone `goZoneDeveloper` `[iOS-HINT]`** — still unproven; needs the developer struct's field map (the `+0x58`/`+0x14c` slots written by `FUN_10030c5b`) read against the iOS `goZoneDeveloper` layout.
(raw JSON: C:\Users\maria\AppData\Local\Temp\fleet-delegate-8630cdeb1d8b4268b393824fe8450523.json)
