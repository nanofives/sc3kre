# SIMRCI.md — SIMRCI.DLL (zoning + RCI demand), first analysis

First-ever look at a SimCity 3000 **simulation** module (2026-08-14). Until today the project
had only ever analysed `SC3U.exe`, which is the GZCOM shell (`MODULE_MAP.md`).

```
Apps\SIMRCI.DLL   393,216 bytes   image base 0x10000000   3,263 functions
SHA-256 = 41378D72F09F89980B19E210787225950E7F6F477928F62D960CE1F811395F53
export: re\ghidra_export_simrci\   anchored copy: original\modules\SIMRCI.DLL
```

Carries the layers **SC3ZoneLayer** (S4 zoning/development) and **SC3ValveLayer** (S5 RCI
demand), plus the three RCI sub-layers **SC3ResLayer / SC3ComLayer / SC3IndLayer**.

## How a GZCOM module is put together `[CONFIRMED]`

```
GZDllGetGZCOMDirector  0x1003ae8e   (real PE export, 5-byte body)
   → returns &DAT_10058780, one-shot: guard bit0 of DAT_100587c4
   → director ctor  FUN_10036382  0x10036382   + atexit dtor 0x10036ec1
        installs vtables PTR_FUN_1004d618 (GZCOM director) and PTR_LAB_1004d5ec
        then 37 × sc3_gzcom_register_class(this, GZCLSID, factory, 0)
                    0x1003b214 — inserts {GZCLSID, factory, 0} into the map at director+0x14
   → at runtime GetClassObject(GZCLSID) calls the stored factory,
        which operator_new()s the class and runs its ctor
        (proven end-to-end: 0x409ff3ba → FUN_10036660 → operator_new(0x2d0) → FUN_100310f5)
```

**This is the reusable recipe for all 29 modules.** It also supplies the *real* GZCLSIDs, which
CitySim.ini's `0x41F836xx` values are not (U-006).

### The 37 registered (GZCLSID → factory) pairs `[CONFIRMED @ 0x10036382]`

```
0x409ff3ba→FUN_10036660   0x20ec9849→FUN_1003669e   0xa106cf3d→FUN_100366d0
0x60a2966e→FUN_10036702   0xa106c520→FUN_10036740   0x60a42f32→FUN_100367a7
0xc0f1ec40→FUN_10036775   0x619ba64e→FUN_100367d9   0x41a3adc1→FUN_1003680e
0xe1a53b30→FUN_10036843   0x82d2d72b→FUN_10036878   0xc1f81e7e→FUN_100368aa
0x82348de5→FUN_100368dc   0xa2c1eda3→FUN_10036911   0x61f44687→FUN_1003694c
0xe22f4a83→FUN_10036987   0x630ea608→FUN_100369c2   0xa22653c0→FUN_100369fd
0x222c9d00→FUN_10036a38   0x822c9d13→FUN_10036a73   0x422b55f2→FUN_10036aae
0x822c9d24→FUN_10036ae9   0xc22c9d34→FUN_10036b24   0x422c9d52→FUN_10036b5f
0x622c9d42→FUN_10036b9a   0x822c9d62→FUN_10036bd5   0xc2d3fd7e→FUN_10036c10
0xe2d3fd92→FUN_10036c4b   0x2207d9ee→FUN_10036c86   0x81ffc3ce→FUN_10036cc1
0x42e88384→FUN_10036cfc   0x612a8f75→FUN_10036d3a   0xe3319eb4→FUN_10036d75
0xa3319f62→FUN_10036db0   0xc2ec529c→FUN_10036deb   0x2123cb83→FUN_10036e26
0x0356c518→FUN_10036e61
```

Only `0x409ff3ba` is bound to a layer so far. The valve/res/ind/com class ids are among the
other 36 but **cannot be pinned from the text export** — each layer's methods are reached only
through vtable/data slots, so there is no static caller edge.

## The `SC3*Layer` strings are INI paths, not class names `[CONFIRMED]`

All five resolve through one idiom: `FUN_1003ceec()` singleton → vtable `+0x50` string buffer →
`FUN_1000212c` builds the path → `FUN_1003793a` sets it as the config file → `FUN_1003c56a` sets
archive `Sys\SYS.PAK` @`0x10057218` → repeated `FUN_1003c580(cfg, section, key, &out)` reads keys
from section `TuningParameters` @`0x100574fc` → `FUN_1003b5ce` (atoi) → module globals.

| layer | INI path | loader | writes |
|---|---|---|---|
| SC3ZoneLayer | `\Sys\SC3ZoneLayer.INI` @`0x100580e4` | `sc3_zone_load_config` `0x1003250f` | 23-slot developer table |
| SC3ValveLayer | `Sys\SC3ValveLayer.ini` @`0x100580a4` | `sc3_valve_load_tuning` `0x1002dff3` | `DAT_10058720/10058710/10058700` |
| SC3ResLayer | `Sys\SC3ResLayer.ini` @`0x10057fd0` | `sc3_res_load_tuning` `0x10022ac6` | ~70 globals `DAT_10057c**` |
| SC3IndLayer | `Sys\SC3IndLayer.ini` @`0x100576b8` | `sc3_ind_load_tuning` `0x10015dc0` | `DAT_10057674/78/7c` |
| SC3ComLayer | `Sys\SC3ComLayer.ini` @`0x10057528` | `sc3_com_load_tuning` `0x1000eccd` | `DAT_100574f8` |

## S4 — the zone layer `[CONFIRMED]`

**GZCLSID `0x409ff3ba`** → factory `0x10036660` → `operator_new(0x2d0)` (720 bytes) → ctor
`sc3_zone_ctor` `0x100310f5`. The ctor installs a secondary interface vtable at byte `+0x10` and
builds a **23-slot table at byte `0x19c`**.

`sc3_zone_load_config` `0x1003250f` runs on that secondary interface (`this = base+0x10`, so
`this+0x18c == base+0x19c` — the same table), reads sections `ZoneDeveloperDescriptions`
(parse cb `FUN_10030c5b`) and `ZoneDeveloperRules` (cb `FUN_10030d64`), then walks the 23 entries
(stride 8) calling each element's vtable `+0x14`.

The 23 slots = the 23 zone-developer entries. Structurally this matches iOS
`goZoneDeveloper`/`goZoneLayer` — **`[iOS-HINT]`, not asserted.**

## S5 — the valve (RCI demand) layer

**Effect data is module-global, not per-instance** — `sc3_valve_load_tuning` `0x1002dff3` fills
three global tables from `AgentValveEffects` / `ConnectionValveEffects` / `OrdinanceEffects`.

Effect record, 20 bytes `[CONFIRMED @ 0x1002e4ad / 0x1002eee1 / 0x1002ef26]`:
```
+0x00  list-node pointers
+0x08  agentType key (int)
+0x0c  short
+0x0e  short
```

Members attributed by `this`-offset pattern (subobjects at `+0x08/+0x10/+0x14/+0x18/+0x24/
+0x38/+0x3c/+0x40..+0x54`): `sc3_valve_apply_effects` `0x1002efe8` (560 B — 4-category demand
loop over vtable `+0xd8/+0xdc/+0xec/+0xf0`, ordinance pass, 2D grid pass, rotates accumulators
`+0x40..+0x54`) · `sc3_valve_get_or_create` `0x1002f218` · `sc3_valve_apply_agent` `0x1002f4ed` ·
`sc3_valve_query_effect_lo/hi` `0x1002eee1`/`0x1002ef26` · `sc3_valve_clear_tables` `0x1002e7e6`.

`0x1002efe8` mechanically matches iOS `goValveLayer::EndOfMonth` (periodic supply/demand
re-evaluation from ordinance/economy modifiers) — **`[iOS-HINT]` only.** Confirmation needs the
vtable slot index plus a caller proving monthly cadence.

**`[UNCERTAIN]`: the valve class's ctor, vtable and GZCLSID.** Missing evidence = the
vtable→function mapping, which needs a live-Ghidra data xref on the layer vtables.

## Real sim tunables now in reach

`sc3_res_load_tuning` `0x10022ac6` (5,504 bytes) reads ~70 keys into `DAT_10057c10..DAT_10057c80`:
population cohorts, health, education and ordinance effects — `NewbornPopPct`, `EQDecay`,
`HospitalizationRate`, `PollutionFactor`, `AgeOfRebellion`, curfew/reading/sports/clinic ordinance
effects. These are the actual RCI simulation constants, and they are **data in `SYS.PAK`**, so a
modding-facing tunables map is now a tractable P2 deliverable.

## Next probes (ranked, from the worker)

1. **Pin the ValveLayer class** — live-Ghidra data xref on `0x1002efe8`/`0x1002f218`/`0x1002f4ed`
   → their vtable → the ctor installing it → the factory → its GZCLSID. Closes the biggest
   `[UNCERTAIN]` here and tests the `goValveLayer` `[iOS-HINT]`.
2. **Map the other 36 factories** — read `FUN_1003669e … FUN_10036e61` (each a 3-line
   `new(size)+ctor`), record `(GZCLSID, alloc size, ctor)`, then match the Res/Ind/Com loaders to
   the ctor whose vtable routes to them.
3. **Confirm the 23-slot table = zone developers** — read `FUN_10030c5b`, `FUN_10030d64` and the
   vtable `PTR_FUN_1004d274`; SC3-side confirmation of the `goZoneLayer` hint would be a
   transport-proximity read or a road-count field in the developer struct.
