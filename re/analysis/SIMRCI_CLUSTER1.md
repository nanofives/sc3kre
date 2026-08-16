# SIMRCI.DLL — C0 cluster (25 largest), analyzed

Building on `re/analysis/SIMRCI.md`. All bodies read from `re/ghidra_export_simrci/functions/`. Every claim below is from the decompilation; RVAs cited inline. All rated **C2** (body read, mechanically described, callees identified, named) — none C3/C4.

**The headline structural result:** this cluster resolves the **R/C/I zone-developer trinity** end to end. Three identical-shape config ctors, three identical-shape per-tile grow/decline evaluators, and multiple lot-layout placers, all tied together by shared tunable globals. The tie is *proven by global address overlap*, not guessed:

| Zone | ctor + `SC3Tune.INI` section | tunables written | per-tile evaluator (reads same tunables) |
|---|---|---|---|
| Industrial | `FUN_10016290` → `[IndustrialZoneDeveloper]` | `DAT_100576cc..717` | `FUN_10017fc0` (reads `DAT_100576cc/d0/d4/d8/dc/e0/e4/fc/700/704/708`) |
| Residential | `FUN_10028198` → `[ResidentialZoneDeveloper]` | `DAT_10058014..2c` | `FUN_10028f12` (reads `DAT_10058014/18/1c/20/24/28/2c`) |
| Commercial | `FUN_1000f022` → `[CommercialZoneDeveloper]` | `DAT_1005753c..54` | `FUN_1000fd53` (reads `DAT_1005753c/40/44/48/4c/50/54`) |

---

## 1. Classification table (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x10016290,zonedev-industrial,C2,sc3_inddev_ctor_load_config,"ctor sets vtable PTR_LAB_1004c528/PTR_FUN_1004c514; guard DAT_10058644; loads \Sys\SC3Tune.INI (0x10057228) from SYS.PAK, section [IndustrialZoneDeveloper] (0x10057918); ~40 keys via FUN_1003c580 -> FUN_1003b5ce(atoi) -> DAT_100576cc..DAT_10057717"
0x10024347,res-sim,C2,sc3_res_simulate_population,"per-tick sim over lists param_1[0x18d/0x18e/0x193/399/0x18]; 89-slot (0x59) age-cohort loop pfVar15[0xb4]; reads res tunables DAT_10057c**; ordinance queries via param_1[8]+0xc (0xc2bf1dc5,0xe0d07233,0x815b4cef,...); sends msgs 0x232f1e51/0x432f1e4b/0xe33070a4 via FUN_10039b57; tail FUN_100225c3"
0x1000a808,ui-query,C2,sc3_query_build_ind_panel,"builds query-panel rows: FUN_1003f052(buf,strID,0x82e0074c) string ids 0xb3-0xc0,0x86,0x87; sink (**param_2+0x4c)(...,flags 0x20000/0x800000/0x40000); singletons FUN_10039c33/FUN_1003cf3b; GZCLSID 0x259c03f/0x4259c018"
0x1001b54d,landvalue,C2,sc3_landvalue_load_tuning,"loads \Sys\SC3LandValue.INI (0x10057bd4) section TuningParameters via FUN_1003c877/FUN_1003c580; keys RadPolluteFactor/WaterPolluteFactor/AirPolluteFactor/GarbagePolluteFactor/CrimeFactor/Res|Com|Ind|AllModMapFactor/WaterEffect(Radius)/HillEffect/HomelessShelterOrdEffect/Res|Com|IndCityCenterEffect -> DAT_100579ac..DAT_100579fc; sscanf triple '%d %d %d'"
0x100055a3,ui-query,C2,sc3_query_build_panel_a,"query-panel populator; FUN_1003f052 str ids 0xc8-0xd3,0x86,0x87 grp 0x82e0074c; (**local_50+0x68/0x58/0x5c/0x44); sink (**param_2+0x4c)"
0x10006ccd,ui-query,C2,sc3_query_build_panel_b,"query-panel populator; str ids 0x86,0x87,0xa7-0xb2; (**local_4c+0x4c/0x48/0x60/0x3c)"
0x10007f76,ui-query,C2,sc3_query_build_panel_stats,"query-panel populator with math (__allmul/__alldiv percentages, jobs); str ids 0x86,0x87,0xd4-0xdd; reads local_54 vtable +0x84/+0x6c/+0x40/+0x78; DAT_10057428"
0x10034716,ui-query,C2,sc3_zonelabel_dispatch_query,"__thiscall message handler; param_6 == 0x45e5f4d5 / 0x45e5f4d6; switch on zone-type byte (cases 1-0x11) -> FUN_1003f052 str ids 0xf-0x1a,0x195; literals 'BUG: No military zones allowed'(0x100581dc),'BUG: No spaceport zones allowed'(0x100581b8); FUN_10035411(0x82e0074c,n,param_3); GZCLSID 0xe0faadc7"
0x100090d4,ui-query,C2,sc3_query_build_panel_c,"query-panel populator; str ids 0xde,0xdf,0xe0,0xe1,0xe4-0xe9,0x86,0x87; DAT_1005745c/10057468/10057428"
0x100015ab,zonedev,C2,sc3_zonedev_place_lots_34,"__thiscall(this,rect,zoneKey); scans 0x34-stride table this+8; tile queries via this+0x38 vtable(+0x34,+0xc,+0x10,+0x68,+0x6c) and this+0x3c(+0x58/+0x5c pollution); tunables DAT_100571d0/d4/d8/dc; 22x22 occupancy grid local_23c[484] stride 0x16; random FUN_10039a9a(this+0x18)"
0x10037ced,config,C2,sc3_config_rewrite_section,"__thiscall INI section reader/rewriter over stream this+0x28; fmt '%s'/'%s = %s' (0x10058224/0x10058218/0x1005820c); detects '[' section header and ';' comment; operator_new buffers; FUN_100393ea/FUN_100392f6 map lookups"
0x10017fc0,zonedev-industrial,C2,sc3_inddev_evaluate_tile,"__thiscall(this,&coords) grow/decline decision; layer subobjects this+0x90..0xc4 (landvalue/pollution/traffic/water grids); GZCLSID 0xa2bf1de5,0xe0faadc7,0x21183b00; industrial tunables DAT_100576cc/d0/d4/d8/dc/e0/e4/fc/700/704/708; calls FUN_100188d3/FUN_10018d18/FUN_10018e45/FUN_10018f66/FUN_100191fe; returns status 0..0x10"
0x1001deca,landvalue,C2,sc3_landvalue_compute_map,"__fastcall(layer); loops *(param_1+0x3c) tiles in 2x2 blocks; reads pollution/crime/traffic grids param_1+0x14 subobjs +0x50/+0x6c/+0x88/+0xa4 clamped +-0x96(150); tunables DAT_100579fc/f8/f9/fa,DAT_10058694-96,DAT_100579a8-aa (from sc3_landvalue_load_tuning); writes tile value via param_1+0x14 vtable+0x3c; DAT_10057a00/10057a04 step tables"
0x1002d27f,zonedev,C2,sc3_zonedev_place_road_lots,"__thiscall(this,rect); scans 4 rect edges for longest road-adjacent buildable run (>=5, cap 12) via this+0x38(+0x54,+0x150)/this+0x34(+0x7c); places random buildings from 0x48-stride table this+8 with rotation local_34 in {0,0x5a,0xb4,0x10e}; random FUN_10039a9a"
0x100214e0,ui-rci,C2,sc3_rci_init_demand_graph,"__fastcall(layer); creates 3 gauge objects operator_new(0xf0)+FUN_100418bf at param_1+0x690/0x694/0x698; configures via vtable+0x60/0x64/0x68/0x4c/0x50/0x54/0x58/0x5c; str ids grp 0x29541f4 (0x162,0x16d,0x16e,0x1d4,0x28e,0x28f); GZCLSIDs 0x303e40d/0xc303e41d,0x4303e4e7/0x303e4f0,0x6303e4f7/0x2303e4ff; colors 0x9000/0xaf6050/0x20c060; caps 0x59/0x96"
0x10027699,zonedev-residential,C2,sc3_resdev_place_lots,"__thiscall(this,rect,zoneKey,num,den); density (num*100/den) vs DAT_1005800c; 0x28-stride table this+8; 10x10 grid local_c8[100]; res tunables DAT_10057ffc/58000/58004/58008/58010; 4 orientations; random FUN_10039a9a(this+0x18)"
0x1000dd1a,zonedev-commercial,C2,sc3_comdev_place_lots,"__thiscall(this,rect,zoneKey,num,den); density vs DAT_100574f0; 0x28-stride table; 10x10 grid local_c4[100]; com tunables DAT_100574e0/e4/e8/ec/f4; 4 orientations"
0x1003591f,zone-tool,C2,sc3_zonetool_apply_area,"__thiscall(this,mode,rect,&out); iterates grid rect; layer getters this+0x34(+0x11c/+0x120/+0x124/+0x13c/+0x15c); per-tile via this-0x10 vtable +0x34/+0x3c and this+0x248+0x144; accumulates *param_3 = cost*local_38 + local_2c; final switch on mode (zone types 1-0x11); [UNCERTAIN] query vs mutate"
0x10028f12,zonedev-residential,C2,sc3_resdev_evaluate_tile,"__thiscall(this,&coords) grow/decline; subobjs this+0x70..0x90; GZCLSID 0xa2bf1de5/0xe0faadc7/0x21183b00; res tunables DAT_10058014/18/1c/20/24/28/2c; calls FUN_100295dc/FUN_1002971a/FUN_100298af/FUN_100297fb/FUN_10029a38/FUN_10029666; returns status 0..0x10"
0x1000fd53,zonedev-commercial,C2,sc3_comdev_evaluate_tile,"__thiscall(this,&coords) grow/decline; subobjs this+0x70..0x90; GZCLSID 0xa2bf1de5; com tunables DAT_1005753c/40/44/48/4c/50/54; calls FUN_10010414/FUN_10010561/FUN_100106f6/FUN_10010642/FUN_10029a38/FUN_1001049e"
0x10009eed,education,C2,sc3_school_ctor_load_config,"ctor vtables PTR_LAB_1004c024..; guard DAT_100585d4; loads SC3Tune.INI section [School] (0x100574a4); keys OptimalDeskCount/OptimalTeacherCount/MinAgeServed/MaxAgeServed/OptimalEQEffect/OptimalMonthlyUpkeep/MaxEfficiency/MysticalE -> DAT_10057474..1005748c; copies to param_1[0xe..0x11]"
0x10004c2a,education,C2,sc3_college_ctor_load_config,"same shape as school ctor; guard DAT_1005859c; section [College] (0x10057388); OptimalProfCount instead of teacher; -> DAT_100572f4..1005730c"
0x10011721,zonedev,C2,sc3_zonedev_place_lots_large,"__thiscall(this,rect,zoneKey,num,den); density num*10/den; 0xc4-stride table this+0xc (large multi-building lots); center via +0x94, 4 edges +4/+0x10/+0x1c/+0x28, mids +0x34/+0x4c/+0x40/+0x58, fill +0xa0/+0xac; places via FUN_100133ac; random FUN_10039a9a"
0x10028198,zonedev-residential,C2,sc3_resdev_ctor_load_config,"ctor vtables PTR_LAB_1004cd38/PTR_FUN_1004cd24; guard DAT_100586cc; section [ResidentialZoneDeveloper] (0x10058030); keys NoServicePercentage/MaxDistFromTransport/ConstructionTimeFactor/Higher|LowerLandValueRedevelopmentPct/HigherDensityRedevelopmentPct/AnarchyFactor -> DAT_10058014..2c"
0x1000f022,zonedev-commercial,C2,sc3_comdev_ctor_load_config,"ctor vtables PTR_LAB_1004c2f4/PTR_FUN_1004c2e0; guard DAT_10058604; section [CommercialZoneDeveloper] (0x100575f8); same 7 keys as residential -> DAT_1005753c..54"
```

---

## 2. Notable findings (structural)

**A. Per-tick / EndOfMonth simulation entry — `FUN_10024347` `[CONFIRMED @ 0x10024347]`.**
The single most valuable find. It walks the layer's building lists (`param_1[0x18d/0x18e/0x193/399]`), runs an **89-slot age-cohort loop** (`pfVar15[0xb4]`, index `0x59`=89 = human lifespan in years), applies education/health ordinance modifiers (queried by GZCLSID through `param_1[8]+0xc`), computes birth/death/migration, caps values, and **emits three message ids via `FUN_10039b57` → vtable+0x10**: `0x232f1e51`, `0x432f1e4b`, `0xe33070a4`. Reads the residential tunables `DAT_10057c**` documented in SIMRCI.md as `sc3_res_load_tuning`'s output. This is the residential population model's periodic update. The three message ids are the highest-value dispatch constants in the slice.

**B. The R/C/I zone-developer trinity resolved by tunable-global overlap** (table at top). Six functions — three ctors (`FUN_10028198` res, `FUN_1000f022` com, `FUN_10016290` ind) and three tile evaluators (`FUN_10028f12` res, `FUN_1000fd53` com, `FUN_10017fc0` ind) — are paired *mechanically*: each evaluator reads exactly the `DAT_*` block its ctor writes. All three evaluators share the same shape (query GZCLSID `0xa2bf1de5`/`0xe0faadc7`/`0x21183b00`, return a status code 0..0x10) and the same helper-call layout offset by module. This is a clean, verifiable subsystem map.

**C. Tunable tables now fully keyed (modding-facing).** Beyond SIMRCI.md's res block, this slice adds four more named `SC3Tune.INI`/`SC3LandValue.INI` sections with their exact global targets:
- `[IndustrialZoneDeveloper]` — ~30 ordinance-effect keys → `DAT_100576cc..DAT_10057717` (`FUN_10016290`).
- `[ResidentialZoneDeveloper]` / `[CommercialZoneDeveloper]` — 7 keys each → `DAT_10058014..2c` / `DAT_1005753c..54`.
- `[School]` / `[College]` — 8 education keys each → `DAT_10057474..8c` / `DAT_100572f4..30c` (`FUN_10009eed`/`FUN_10004c2a`).
- `SC3LandValue.INI [TuningParameters]` — pollution/crime/city-center weights → `DAT_100579ac..fc` (`FUN_1001b54d`), a **new layer** not in the SIMRCI.md table.

**D. Land-value map compute — `FUN_1001deca` `[CONFIRMED @ 0x1001deca]`.** The per-tile land-value engine that *consumes* `FUN_1001b54d`'s tunables. Reads pollution/crime/traffic grids (clamped ±150 = `0x96`), blends with distance-to-city-center and water/hill bonuses, writes each tile's value. Pairs with `FUN_1001b54d` the same way the R/C/I ctors pair with their evaluators.

**E. Zone-type → display-string dispatcher — `FUN_10034716` `[CONFIRMED @ 0x10034716]`.** A message handler keyed on `param_6 == 0x45e5f4d5 / 0x45e5f4d6`, switching over zone-type selector bytes 1..0x11 to fetch localized names (string group `0x82e0074c`). Contains two developer assert literals ("BUG: No military zones allowed", "BUG: No spaceport zones allowed") confirming the zone-type enumeration. The case set (1,2,3,5,6,7 / 9,10,0xb,0xe,0xf,0x11) recurs in `FUN_1003591f`'s final switch — that's the module-wide zone-type enum.

**F. RCI demand-graph UI init — `FUN_100214e0` `[CONFIRMED @ 0x100214e0]`.** Builds the three R/C/I demand gauges (`operator_new(0xf0)` each, stored at layer `+0x690/+0x694/+0x698`), with bar colors `0x9000`/`0x20c060`/`0xaf6050` and GZCLSID pairs per bar. Confirms three-channel RCI display, string group `0x29541f4`.

**G. No save/load serializer in this slice.** `FUN_10037ced` is the closest to serialization but it is an **INI text section reader/rewriter** (detects `[section]` / `;comment`, formats `%s = %s`), not city-save binary I/O. The binary RCI serialiser is not among these 25 functions.

---

## 3. Not determined

- **`FUN_1003591f` (`sc3_zonetool_apply_area`) — mutate vs. query is `[UNCERTAIN]`.** It iterates a rect, reads per-tile state, and accumulates a cost into `*param_3` (`cost*count + accumulator`), gated by `param_1` (a mode flag). The `param_1 != 0` branches call setters (`vtable+0x148`, `+0xb0`) that look like commits, but I cannot prove from the body alone whether `param_1==0` is a dry-run cost estimate and `param_1!=0` the apply, or vice-versa. **Missing evidence:** a caller passing a literal `param_1`, plus the meaning of vtable slots `+0x134/+0x148/+0xb0` on the object at `this+0x34`.

- **Lot-layout placer → zone mapping is only partial.** Confirmed by tunable overlap: `FUN_10027699` (res, `DAT_1005800c`) and `FUN_1000dd1a` (com, `DAT_100574f0`). Not tied down: `FUN_100015ab` (stride `0x34`, 22×22 grid, tunables `DAT_100571d0..dc`), `FUN_1002d27f` (stride `0x48`, road-frontage), and `FUN_10011721` (stride `0xc4`, large multi-building lots) — each uses a distinct table stride and its own `DAT_*` block that does not overlap the R/C/I evaluator tunables, so I cannot assert which developer (or shared tool) owns them. **Missing evidence:** the caller/vtable slot that invokes each placer, or a construction-table stride cross-referenced to a specific developer ctor.

- **`FUN_10009eed` / `FUN_10004c2a` subsystem edge.** Named education (School/College config) with confidence from the section strings and `EQEffect`/`AgeServed` keys, but whether these objects live in SIMRCI's own layer set or are proxies for an education module is not determinable from these bodies. Mechanically they are self-contained config ctors, so the C2 rating holds regardless.

- **`[iOS-HINT]` not asserted.** The R/C/I evaluator + `EndOfMonth`-style `FUN_10024347` shapes are consistent with iOS `goZoneDeveloper`/`goCitySimulator`, but per project rules struct offsets do not transfer and I did not cross-read the iOS export for this slice, so no iOS claim is made.
