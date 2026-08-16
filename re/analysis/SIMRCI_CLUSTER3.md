# SIMRCI.DLL — C0 cluster (25 largest, third pass), analyzed

Building on `SIMRCI.md`, `SIMRCI_CLUSTER1.md`, `SIMRCI_CLUSTER2.md`. All bodies read from `re/ghidra_export_simrci/functions/`. Every claim is from the decompilation; RVAs cited inline. All rated **C2** (body read, callees identified, mechanically described, named) — none C3/C4.

**Headline result:** this slice is almost entirely the **zone-developer density-variant lot machinery** — a family of *identical-shape* config ctors, each pairing 1:1 with a *identical-shape* block-lot-placer by proven `DAT_*` global overlap, all reading one modding-facing tunable table: `SC3Tune.INI [ZoneDeveloperRules]`, keyed by each developer's own GZCLSID (`0x%08X`). Plus the three shared **config-reader infrastructure** functions (`0x1003c580`/`0x1003c877`/`0x100388ec`) that every tuning loader in the module calls, and the zone-developer **class factory** (`0x1000bb73`).

---

## 1. Classification table (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x1000bb73,zonedev,C2,sc3_zonedev_factory_dispatch,"GetClassObject-style dispatch; switch over 13 GZCLSIDs (0x82e88c9c,0x2e88915,0x2e88949,0x2e88968,0x2e889aa,0x2e889c4,0x42e88586,0xa2e8893b,0xa2e8895a,0xa2e8899d,0xc2e8898f,0xc2e889b6,0xe2e889d4); each operator_new(300=0x12c)+FUN_1000ba68(this,subclsid,zoneTypeIdx 0..0x11,v5[0x15..0x23],v6[0x26/0x2c]); subclsids 0x42e434f7/0x16c4e26/0x82e4350c/0xc2e43505/0x22e43512/0x62e43531/0x62e4352b/0x2e43524/0xa16c4e2a/0xc16c4e30/0x42e43517/0x2e4351e/0x42e434ff; then vtable[0](param_2,out)=QI, on fail vtable+0x40(1)=Release; *param_3=0 on unknown clsid"
0x1002713c,zonedev-residential,C2,sc3_resdev_lotcfg_ctor,"config ctor; FUN_10036ee3 base; installs vtables *this=PTR_FUN_1004cd10/+2=PTR_FUN_1004ccf0/+3=PTR_LAB_1004cce4; list init FUN_10039a69(this+8,-1); one-shot guard DAT_100586c0; loads \Sys\SC3Tune.INI(0x10057228) from Sys\SYS.PAK(0x10057218) section [ZoneDeveloperRules] key=0x%08X(own clsid) via FUN_1003c580; FUN_10036fc1 tokenises value (delim DAT_100574c4) -> FUN_1003b5ce(atoi) -> DAT_10057ffc/58000(minDim), DAT_10058008(cap<=10)/58004, DAT_1005800c(densityThr), DAT_10058010(largeLotPct); pairs w/ placer 0x10027699"
0x1000bf24,zonedev-commercial,C2,sc3_comdev_lotcfg_ctor_v1,"same shape; guard DAT_100585e0; vtable PTR_FUN_1004c12c; writes DAT_100574ac/b0(minDim),DAT_100574b8(cap<=10)/b4,DAT_100574bc(densityThr),DAT_100574c0(largeLotPct); pairs w/ placer 0x1000c3eb"
0x1001375e,zonedev-industrial,C2,sc3_inddev_lotcfg_ctor_v1,"same shape; guard DAT_10058620; vtable PTR_FUN_1004c3c8; writes DAT_1005762c/30,DAT_10057638(cap<=10)/34,DAT_1005763c,DAT_10057640; pairs w/ placer 0x10013c66"
0x1000ca4c,zonedev-commercial,C2,sc3_comdev_lotcfg_ctor_v2,"same shape; guard DAT_100585ec; vtable PTR_FUN_1004c16c; writes DAT_100574c8/cc,DAT_100574d4(cap<=10)/d0,DAT_100574d8,DAT_100574dc; pairs w/ CLUSTER2 block placer 0x1000cf87 (reads 574c8/cc/d0/d4/d8)"
0x100142d7,zonedev-industrial,C2,sc3_inddev_lotcfg_ctor_v2,"same shape; guard DAT_1005862c; vtable PTR_FUN_1004c408; writes DAT_10057644/48,DAT_10057650(cap<=10)/4c,DAT_10057654,DAT_10057658; pairs w/ placer 0x10014794"
0x1002027b,zonedev-residential,C2,sc3_resdev_lotcfg_ctor_v2,"same shape; guard DAT_100586a0; vtable PTR_FUN_1004c8fc; writes DAT_10057bf4/f8,DAT_10057c00(cap<=10)/fc,DAT_10057c04,DAT_10057c08; pairs w/ placer 0x10020762; [UNCERTAIN] R vs C/I (see notes)"
0x1000d80c,zonedev-commercial,C2,sc3_comdev_lotcfg_ctor_v3,"same shape; guard DAT_100585f8; vtable PTR_FUN_1004c1ac; writes DAT_100574e0/e4,DAT_100574ec(cap<=10)/e8,DAT_100574f0,DAT_100574f4; pairs w/ CLUSTER1 placer 0x1000dd1a (reads 574e0/e4/e8/ec/f0/f4)"
0x10014de5,zonedev-industrial,C2,sc3_inddev_lotcfg_ctor_v3,"same shape; guard DAT_10058638; vtable PTR_FUN_1004c448; writes DAT_1005765c/60,DAT_10057668(cap<=10)/64,DAT_1005766c,DAT_10057670; pairs w/ placer 0x100152a2"
0x10026644,zonedev-residential,C2,sc3_resdev_lotcfg_ctor_v3,"same shape; guard DAT_100586b4; vtable PTR_FUN_1004ccd0; writes DAT_10057fe4/e8,DAT_10057ff0(cap<=10)/ec,DAT_10057ff4,DAT_10057ff8; pairs w/ placer 0x10026b01"
0x1002bbf3,zonedev-residential,C2,sc3_resdev_lotcfg_ctor_v4,"same shape, variant (extra field param_1[0x11]=0; +2 vtable=PTR_LAB_1004cdec not PTR_FUN; loads only 4 tokens via FUN_10002efe x2); guard DAT_100586e8; vtable PTR_FUN_1004ce0c; writes DAT_1005804c/50,DAT_10058058(cap<=10)/54,_DAT_1005805c,DAT_10058060; placer not in this slice"
0x100152a2,zonedev-industrial,C2,sc3_inddev_place_lots_block_v3,"__thiscall(this,&rect[4],zoneKey,num,den); density=num*100/den gated>=DAT_1005766c; table this+8 stride 0x1c find +0==zoneKey; rect dims>=DAT_1005765c/60; block caps DAT_10057664/68 (shrink rect by comparing this+0x38 vtbl+0x70 at both ends); clears 10x10 grid local_98[25]; per tile buildable this+0x38+0x6c; random FUN_10039a9a(this+0x18); variant pick prob DAT_10057670 -> record+0x10(small)/small-array vs large; size proto+0x40; place this+0x38+0x68(bldg,coords,4,0,1); marks grid 0x01010101"
0x10013c66,zonedev-industrial,C2,sc3_inddev_place_lots_block_v1,"identical block placer reading DAT_1005762c/30/34/38/3c(gate)/40; pairs ctor 0x1001375e"
0x10020762,zonedev-residential,C2,sc3_resdev_place_lots_block_v2,"identical block placer reading DAT_10057bf4/f8/fc/c00/c04(gate)/c08; pairs ctor 0x1002027b"
0x1000c3eb,zonedev-commercial,C2,sc3_comdev_place_lots_block_v1,"identical block placer reading DAT_100574ac/b0/b4/b8/bc(gate)/c0; pairs ctor 0x1000bf24"
0x10014794,zonedev-industrial,C2,sc3_inddev_place_lots_block_v2,"identical block placer reading DAT_10057644/48/4c/50/54(gate)/58; pairs ctor 0x100142d7"
0x10026b01,zonedev-residential,C2,sc3_resdev_place_lots_block_v3,"block placer variant (no per-tile buildable +0x6c gate, iterates full grid) reading DAT_10057fe4/e8/ec/f0/f4(gate)/f8; pairs ctor 0x10026644"
0x1003c580,config,C2,sc3_config_ini_read_key,"__thiscall INI single-key reader; dispatch *(this+0xb4): 0->ret0, 1->FUN_1003864f, 2->scan; builds section header '['+param_1+']' (DAT_100582d8/d4); positions stream this+0x78 vtbl+0x30/+0x38; scans lines FUN_1003cb4b, on section match tokenises each line by '=' (DAT_10058208), compares key vs param_2 (FUN_100303fd), returns matched value into param_3+4 (FUN_100062d1); returns 1 on hit. Reader used by all tuning loaders in this module"
0x1003c877,config,C2,sc3_config_ini_enum_section,"__thiscall INI section callback-enumerator; same *(this+0xb4) dispatch (1->FUN_100388ec backend, 2->inline scan); for each key=value line in section [param_1] invokes callback param_2(&entry,&line,param_3); stops at next '[' or on ';' comment; used to load multi-row tunable sections"
0x100388ec,config,C2,sc3_config_ini_enum_section_backend,"type-1 backend of 0x1003c877; guarded by this+0x18/0x19 flags and vtable+0x3c/+0xc; FUN_100393ea locates section in an in-memory map (this+0x1c); reads lines via this vtable+0x40, tokenises by '=' (DAT_10058208), builds a sorted {key,value} list stride 0x28 (FUN_10039161/FUN_10038bc7), then per entry calls param_2(entry+0,entry+0x14,param_3)"
0x100188d3,zonedev-industrial,C2,sc3_inddev_pick_building,"__thiscall(this,levelBound param_1,allowNew param_2,ignoreRoadFlag param_3) -> building id; queries 12 ordinance GZCLSIDs via this+0xc4 vtbl+0xc (0xa2bf1e43,0x62f6e7cf,0xa2f6e7da,0x2f6e7e2,0xe2f6e7ea,0x2f6e7ef,0x22f6e7f4,0xa2f6e7f9,0xe2f6e7fe,0xc2f6e804,0x62f6e808,0x62f6e82b); demand uVar8=DAT_100576f8 -/+ DAT_10057716/17; land value this+0xb8 vtbl+0x84 banded 0x55..0x96 -> pct clamped to this+0xc8/0xc9; ordinance deltas DAT_1005770c..DAT_10057715; grow/decline/keep branch -> building list this+0x1c/0x34/0x4c (iVar6 0/1/2); walks list matching bldg+1/+2 min/max level vs param_1 (FUN_100192aa), returns highest match. Called by sc3_inddev_evaluate_tile(0x10017fc0)"
0x1001a62f,zonedev,C2,sc3_zonedev_find_growable_neighbor,"__thiscall(this,&center,&out); occupancy bitmap this+0x60(+0x10 row-ptr array, bit test); buildable this+0x4c vtbl+0x104(x,y); demand FUN_1001a9e5(this,coords)>0; searches center then expanding rings (radius++ up to map dims this+0x48 vtbl+0xc/+0x10), 4 edges per ring; writes first satisfying tile to out, returns 1. Growth seed-finder for sc3_zonedev_grow_region(0x10019de1)"
0x10017cef,zonedev-industrial,C2,sc3_inddev_layer_shutdown,"__fastcall(this); this+0xc=0; Release (vtbl+8) + null the 14 resolved context interfaces this+0x90/94/98/9c/a0/a4/a8/ac/b0/bc/b4/c0/b8/c4 (same set sc3_inddev_evaluate_tile uses); swap-clears 7 map-accumulator subobjs this+0x10/1c/28/34/40/4c/58 (FUN_1002fb80/FUN_1002fa6d/FUN_1001093a/FUN_100108e0); drains list this+0x68..0x6c releasing each elem (vtbl+0x10 then +8). Detach/shutdown counterpart to an Init"
0x1002f5af,rci-demand,C2,sc3_valve_apply_building_effects,"__thiscall(this,ctx param_1); QI 0xc14f8955->local_c (reads dims +0xd8/+0xd4, rect +0xd0->local_40/3c/38/34, id +0x88->local_14); QI 0xe0faadc7->zone (check +0x4c==1); iterates list this+0x10, per node obj at +2 with packed vals +3/+4 (short/short); obj vtbl +0x40/+0x44(scaled writes)/+0x20(type code); for type 3000/5000/8000: paints grid region via this+8 +0x3c layer (vtbl+0x34 read/+0x3c write, clamp 0..0xff) and accumulates area*val into 3 counters this+8 +0x4c/+0x50/+0x54 gated by this+8 +0x34 vtbl+0x24(type,local_14); type 7000: grid paint only. A valve-range effect/apply pass"
0x1001aa11,zonedev,C2,sc3_zonedev_check_road_frontage,"__thiscall(this,&coords,&out); *out=0; buildable this+0x48 vtbl+0x6c(coords,10) else *out=0x10; reserve this+0x50 vtbl+0x50/+0x48; probes 4 orthogonal neighbors for tile-type high-byte==0x11 then buildable (flags local_6/7/5/8); then 4 diagonal corners requiring both adjacent orthogonals set; returns 1 if a valid road-adjacent corner found else *out=9. Placement-validity helper for the growth driver"
```

---

## 2. Notable findings (structural)

**A. The zone-developer density-variant set: 10 config ctors + 6 block placers, paired 1:1 by tunable-global overlap.** This is the dominant structure in the slice and the highest-value result. Every ctor is byte-shape-identical (base ctor `FUN_10036ee3`, three-slot vtable install, list member init `FUN_10039a69(this+8,-1)`, one-shot guard byte, then a load of `SC3Tune.INI [ZoneDeveloperRules]`). Every placer is byte-shape-identical (`num*100/den` density gate, `0x1c`-stride variant table at `this+8`, `10x10` occupancy grid `local_98[25]`, `FUN_10039a9a` RNG, place via `this+0x38` vtable `+0x68`). The pairing is *proven*, not guessed — each placer reads exactly the six `DAT_*` its ctor writes:

| ctor (RVA) | vtable / guard | tunable block | paired placer |
|---|---|---|---|
| `0x1000bf24` com | `c12c` / `585e0` | `DAT_100574ac..c0` | `0x1000c3eb` |
| `0x1000ca4c` com | `c16c` / `585ec` | `DAT_100574c8..dc` | `0x1000cf87` (CL2) |
| `0x1000d80c` com | `c1ac` / `585f8` | `DAT_100574e0..f4` | `0x1000dd1a` (CL1) |
| `0x1001375e` ind | `c3c8` / `58620` | `DAT_1005762c..40` | `0x10013c66` |
| `0x100142d7` ind | `c408` / `5862c` | `DAT_10057644..58` | `0x10014794` |
| `0x10014de5` ind | `c448` / `58638` | `DAT_1005765c..70` | `0x100152a2` |
| `0x1002027b` ?   | `c8fc` / `586a0` | `DAT_10057bf4..c08` | `0x10020762` |
| `0x10026644` res | `ccd0` / `586b4` | `DAT_10057fe4..f8` | `0x10026b01` |
| `0x1002713c` res | `cd10` / `586c0` | `DAT_10057ffc..58010` | `0x10027699` (CL1) |
| `0x1002bbf3` res | `ce0c` / `586e8` | `DAT_1005804c..60` | (not in slice) |

**B. New modding-facing tunable table — `SC3Tune.INI [ZoneDeveloperRules]`.** Confirmed at every ctor. One section, one line per developer keyed by the developer's own GZCLSID formatted `0x%08X` (`FUN_100374f5` @ `s_0x_08X_10057210`, key string `s_ZoneDeveloperRules_100571fc`). The value is tokenised (`FUN_10036fc1`, delimiter `DAT_100574c4`) into four ints written to the block: **`{minDim, maxBlockDim (clamped ≤10), densityThreshold, largeLotPct}`**. This complements CLUSTER2's `[…ZoneDeveloper]` sections — that table is per-density-*rule*; this one is per-density-*variant lot geometry*.

**C. The zone-developer class factory — `0x1000bb73` `[CONFIRMED @ 0x1000bb73]`.** A `GetClassObject`-style dispatch keyed on 13 GZCLSIDs, each `operator_new(300)` + `FUN_1000ba68(this, subClsid, zoneTypeIdx, v5, v6)` where `zoneTypeIdx` runs `0..0x11` (the module-wide zone-type enum from CLUSTER1's `FUN_10034716`). This is the registry that maps external class ids to zone-developer descriptor objects.

**D. Config-reader infrastructure trio — `0x1003c580` / `0x1003c877` / `0x100388ec`.** These are the primitives every tuning loader in the module funnels through (CLUSTER1/2's `sc3_*_load_tuning` all call `FUN_1003c580`). `0x1003c580` = single-key lookup returning a value string; `0x1003c877` = per-line callback enumerator; `0x100388ec` = its in-memory-map backend. All three share the `*(this+0xb4)` `{0,1,2}` backend dispatch and the `'='`/`'['`/`';'` INI tokenizer (`DAT_10058208`). **Not serializers** — INI text only.

**E. Industrial grow/decline decision — `0x100188d3` `sc3_inddev_pick_building`.** Reads 12 ordinance GZCLSIDs and the industrial ordinance-effect tunables `DAT_1005770c..DAT_10057717` (the block `FUN_10016290` loads per CLUSTER1), bands land value over `0x55..0x96`, and selects a building from one of three lists (grow/keep/decline). This is the sub-decision inside `sc3_inddev_evaluate_tile` (`0x10017fc0`).

**F. Growth-driver helpers now connected — `0x1001a62f` + `0x1001aa11`.** Both feed CLUSTER2's `sc3_zonedev_grow_region` (`0x10019de1`, which explicitly calls `FUN_1001aa11`): `0x1001a62f` is the expanding-ring search for the nearest growable, demand-positive tile (`FUN_1001a9e5`); `0x1001aa11` is the road-frontage/corner-adjacency validity gate (tile-type high byte `== 0x11`).

**G. A valve-layer apply pass — `0x1002f5af`.** In the valve address range (right after `sc3_valve_apply_agent` `0x1002f4ed`). Iterates a building list, and for building-type codes `3000/5000/8000` paints a 2D grid region (clamped `0..0xff`) and accumulates `area × value` into three counters at `this+8 +0x4c/+0x50/+0x54`; type `7000` paints only. QI ids `0xc14f8955` and `0xe0faadc7` (zone). Mechanically an effect/demand-map application over placed buildings.

**H. Industrial layer shutdown — `0x10017cef`.** Releases and nulls the 14 context interfaces at `this+0x90..0xc4` (the exact set `sc3_inddev_evaluate_tile` resolves) and clears the map accumulators — the detach/`Init(0)` counterpart for the industrial developer.

**I. No binary save/load serializer in this slice.** The RCI serializer pair is CLUSTER2's `0x10022169`/`0x10021cf3`. Nothing here writes the city-save stream.

---

## 3. Not determined

- **`0x1002027b` / `0x10020762` R-vs-C-vs-I ownership `[UNCERTAIN]`.** Its block `DAT_10057bf4..c08` sits between the land-value globals (`DAT_100579xx`) and the residential tunables (`DAT_10057c10+`), overlapping neither the confirmed commercial (`0x100574xx`) nor confirmed residential (`0x10057fxx`) ranges. I tag it residential by address adjacency only. **Missing:** the factory/clsid that installs vtable `PTR_FUN_1004c8fc`.

- **`0x1002f5af` building-type codes `3000/5000/8000/7000`.** Reported raw; whether these are R/C/I/other agent-type ids is not provable from the body. The three accumulators `this+8 +0x4c/+0x50/+0x54` and QI id `0xc14f8955` are unresolved. **Missing:** a reader of those counters, or the class behind `0xc14f8955`.

- **`0x1000bb73` constants `v5 (0x15..0x23)` and `v6 (0x26/0x2c)`.** Passed positionally to `FUN_1000ba68`; reported raw. The value `FUN_100374f5` formats into the `0x%08X` section/key (inferred to be each object's own registered clsid) is not visible in the ctor bodies. **Missing:** `FUN_1000ba68`'s body and the descriptor struct layout.

- **`0x1002bbf3` extra field `param_1[0x11]` and its distinct `+2` vtable (`PTR_LAB_1004cdec`).** It is a config-ctor of the same family but structurally divergent; its paired placer is outside this slice, so its density role is unconfirmed. **Missing:** the placer reading `DAT_1005804c..60`.

- **`[iOS-HINT]` not asserted.** `0x1002f5af` (effect-grid apply) and the ctor/placer family are shape-consistent with iOS `goValveLayer`/`goZoneDeveloper`, but per project rules struct offsets do not transfer and I did not cross-read the iOS export for this slice, so no iOS claim is made.
