# SIMNTWRK.DLL — C0 cluster (25 largest), analysis

All addresses are SIMNTWRK.DLL VAs (image base `0x10000000`). Every function below was read in full; all are rated **C2** (body read, callees identified, mechanically described, named). The three network sub-layer objects are consistently `this+0x3c` (networks 1–4), `this+0x40` (network 5), `this+0x44` (network 6) — matching the 3 save sub-sections found in the serialiser.

## Headline finds

### 1. Save-section GROUP identified — serialiser triad `[CONFIRMED]`

The literal `0x206c6e7c` grep hit **`FUN_10012dff`**, which builds four GZCOM TGI keys as `{type=0x206c6e7c, group=0x2147c2dd, instance=0,1,2,3}` `[CONFIRMED @ 0x10012dff lines 40-51]` and passes them to the record writer `FUN_10012fc3`. So per the task's rule (the u32 paired with `0x206c6e7c` is the save GROUP):

> **SIMNTWRK save-section GROUP = `0x2147c2dd`** (record TYPE `0x206c6e7c`, 4 instances). This names one of the previously-unnamed groups on the task list.

The triad (only `0x100130e9` is in the slice; the other three surfaced via the literal grep and are reported as bonus):
- **`FUN_10012dff` @ 0x10012dff — layer SAVE writer.** Guards on `this+0x3c/+0x40/+0x44` and `DAT_100323d8` (the stream/COM provider), writes the 3 sub-layers each with its TGI via `FUN_10012fc3`, wrapped in `FUN_10026129`/`FUN_100262a3` (open record) + vcall `+0x88` (commit) `[CONFIRMED @ 0x10012dff]`.
- **`FUN_10012fc3` @ 0x10012fc3 — per-layer element serialiser.** `param_2->+0x74` "has data?", enumerates elements (`local_14 +0x14/+0x1c`), serialises each via `+0x24` then `FUN_1000d688(elem, this+0x2c, stream)` with the TGI key `[CONFIRMED @ 0x10012fc3]`.
- **`FUN_100130e9` @ 0x100130e9 (IN SLICE) — layer LOADER.** Opens read stream (`FUN_10025f0d`/`FUN_100262a3`, vcall `+0x38`), reads three count fields (`local_18`,`local_1c`,`local_24`) and deserialises pieces via `FUN_1000d6b3` into sub-layer objects `this[0xf]`,`this[0x10]`,`this[0x11]`; the `(short)local_60 == 4` check confirms the 4-section framing `[CONFIRMED @ 0x100130e9]`.
- **`FUN_1001396b` @ 0x1001396b — QueryInterface.** Maps IIDs → sub-object pointers: `0x206c6e7c`→this, `0x6182ea06`→this+8, `0x81c0cb7b`→this+0xc, `0x5e4`→this+4, plus `0x4147c2fb`/`0x58d`/`0x81c0cb7c`→this `[CONFIRMED @ 0x1001396b]`. Confirms `0x206c6e7c` is the layer's own interface/type id.

### 2. Rule-evaluation engine (resolves module OPEN item #7)

- **`FUN_1001547b` @ 0x1001547b (3706 B)** — the core tiling-rule evaluator. `param_2` (1–6) selects the per-network rule containers `DAT_10032300..0x10032344` and handler objects `DAT_100323c0..` (mapping enumerated at lines 104-169). Builds a **32×32 adjacency bitmask** (`local_1e0`,`local_160`) using the direction-bit table **`DAT_10031380`**, runs a dilation/flood pass (neighbor OR), partitions tiles into simple/complex/final lists, and applies rules via `FUN_100167d4`, `FUN_1001a2c0`, `FUN_10016327`, `FUN_100165d8` `[CONFIRMED @ 0x1001547b]`. This is how the 18 rule stages combine at runtime.
- **`FUN_1001a2c0` @ 0x1001a2c0 (705 B)** — per-tile rule resolver. Picks a rule-string table by network (`DAT_1003195c`/`197c`/`199c`/`19bc`/`19dc`/`19fc`/`1a1c`/`1a3c`) and matches a 4-byte neighbor signature (`FUN_1001a1f3`) against 8 rows of **`DAT_1003193c`**, returning piece id+orientation `[CONFIRMED @ 0x1001a2c0]`.
- **`FUN_10016327` @ 0x10016327 (671 B)** — rule-stage applier (called 3× by `FUN_1001547b`); per node calls `FUN_10019768` then matches/validates/commits via `FUN_100228ff`/`FUN_100165d8` `[CONFIRMED]`.
- **`FUN_10014a23` @ 0x10014a23 (1998 B)** — node-set rule rebuild; uses tunable objects `DAT_100323b0/b4/b8/bc`, rule vcalls `+0x144/+0x148`, then `FUN_1001547b` `[CONFIRMED]`.

### 3. Tunable / conversion-table readers

- **`FUN_10024e10` @ 0x10024e10 (922 B)** — **config/exemplar reader**. Reads ~24 named properties from a property source (`param_1` vtable `+0x38` array / `+0x4c` value / `+0x30` bool) via key constants `DAT_1002cee0..0x1002cf78` into `this+0x04..this+0x114`, each with a hardcoded default (defaults include `0x57a`, `0xa1096a4f`, `0x2026960b`, `0x62e69238`, `0x5bee0`) `[CONFIRMED @ 0x10024e10]`.
- **`FUN_1001272e` @ 0x1001272e (1745 B)** — **legacy tile-map importer/converter**. Reads a 2-D tile array from `param_2` (prop key `0x10002f`, dims `+0x24`, cells `+0x18` planes 2 & 8) and remaps old tile ids into new pieces via four `(id-base)*stride` lookup tables: `DAT_100313c0` (plane 2), `DAT_100316d4`/`DAT_1003178c`/`DAT_10031844` (plane-8 sub-ranges). Instantiates pieces via GZCLSID `0xc14f8955` `[CONFIRMED @ 0x1001272e]`.

## Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10002693,net-build,C2,sc3_ntwrk_build_median_run,"dual-lane/median segment builder; terrain height FUN_1001a5b5, validate FUN_1000986f, place FUN_10009613/FUN_10008919, append FUN_10004172, commit vcall this+0x154; cost unit 0x3e84 via this+0x38[+0x54], funds [+0x10]; err msg 0x28b/0x2e0/0x285 [CONFIRMED @ 0x10002693]"
0x1000488d,net-build,C2,sc3_ntwrk_drag_build_line,"Bresenham drag-build (step local_28/local_2c, abs diffs), tile counter DAT_100322a4 capped 0x200; per-tile cost this[0x25]; commit; broadcasts msg 0x62c0838e on completion [CONFIRMED @ 0x1000488d]"
0x1000122a,net-build,C2,sc3_ntwrk_build_avenue_run,"param_3 net-type variant of 0x10002693; cost 0x3e82, msg 0x28b/0x2d2, err 0x285; tile-substitution table DAT_10031120/DAT_10031160; default piece ids 0x1d/0x2c/0x5c for net 1/2/3; calls FUN_1001a2c0 [CONFIRMED @ 0x1000122a]"
0x1000abde,net-tiling,C2,sc3_ntwrk_place_diagonal_piece,"diagonal/curve selector; reads existing tiles FUN_1000aaba; tile-id consts 0x2bfa/0x3acb/0x3afa/0x49/0x3b13..0x3b25; rule lookup FUN_10016a25(DAT_100323c0/c4)+FUN_1001547b; place FUN_10008919 [CONFIRMED @ 0x1000abde]"
0x1001547b,net-tiling-eval,C2,sc3_ntwrk_apply_tiling_rules,"core rule engine; param_2 1..6 selects DAT_10032300.. containers + DAT_100323c0.. handlers; 32x32 adjacency bitmask via DAT_10031380; dilation pass; applies via FUN_100167d4/FUN_1001a2c0/FUN_10016327/FUN_100165d8 [CONFIRMED @ 0x1001547b]"
0x10009d20,net-tiling,C2,sc3_ntwrk_autotile_crossing,"crossing/junction auto-tile with terrain slope; 5 dir x 2 orient; tile id FUN_10009bc7, height this+0x54[+0x4c]; piece ids 0x49/0x2bfa/0x3acb/0x3afa/0x3b07..0x3b0a; broadcasts 0x62c0838e [CONFIRMED @ 0x10009d20]"
0x1001ca1a,net-build,C2,sc3_ntwrk_build_highway_ramp,"highway (param_3==4) on-ramp/junction; slope thresholds (<7 reject); cost unit 0x3e86, msg 0x253, err 0x284; piece tables DAT_10031ff8/32008/32018/32028 by orientation; place FUN_10009613/FUN_10008919 [CONFIRMED @ 0x1001ca1a]"
0x1001c102,net-build,C2,sc3_ntwrk_build_slope_ramp,"road/rail (param_3 1/2) slope-ramp/embankment; piece tables DAT_10031fd8/10031fe8; cost 0x3e86, msg 0x253/0x284; place FUN_10009613/FUN_10008919 [CONFIRMED @ 0x1001c102]"
0x10019768,net-graph,C2,sc3_ntwrk_collect_neighbor_pieces,"builds neighbor piece-record list (operator_new(6) {u32 id,byte dir,byte state}); FUN_1002203e rel-dir, FUN_1001a056 record; param_9==0x18 subway path vs surface; GZCLSID 0x41658d28 net-connect iface; add via FUN_10022196 [CONFIRMED @ 0x10019768]"
0x1001da5f,net-tiling,C2,sc3_ntwrk_extend_diagonal_run,"trace/extend run along template id list DAT_100323ac; special ids 0x3acc/0x2bd7/0x2bd8/0x3b02; dir-bit table DAT_10031f34; tile id FUN_1001a93d; recurse vcall +0xfc, place +0xf4 [CONFIRMED @ 0x1001da5f]"
0x10006727,ui-panel,C2,sc3_ntwrk_build_tool_hud,"build-tool HUD; GZWin via GZCLSIDs 0xc2afa76e/0x42e55fd5+0x82b9b75b/0x82fe68c4+0xc12cea13/0x12340010; icon res 0x62e56a2c/0x62e56a2d/0x24e/0x24f/0x252; two layouts by this+0x2c mode [CONFIRMED @ 0x10006727]"
0x10014a23,net-tiling-eval,C2,sc3_ntwrk_rebuild_node_rules,"node-set rule rebuild; 0x23 connection markers; tunable objs DAT_100323b0/b4/b8/bc; rule vcalls +0x144/+0x148; FUN_1000bcf5+FUN_1001547b; highway path FUN_10016a25(DAT_100323c0) [CONFIRMED @ 0x10014a23]"
0x1001272e,net-load-legacy,C2,sc3_ntwrk_import_legacy_tilemap,"legacy tile-array importer; prop key 0x10002f, dims +0x24, cells +0x18 planes 2/8; remap tables DAT_100313c0/DAT_100316d4/DAT_1003178c/DAT_10031844 via (id-base)*stride; create piece GZCLSID 0xc14f8955 [CONFIRMED @ 0x1001272e]"
0x10008064,net-build,C2,sc3_ntwrk_build_straight_run,"2-tile-wide straight run point-to-point; coord+tile vector; commit vcall +0x150/+0x154; post-place flood cleanup (param_7 in {1,2,3,5,6}) up to 100 iters via +0x144/+0x14c [CONFIRMED @ 0x10008064]"
0x10008a4a,net-neighbor,C2,sc3_ntwrk_make_neighbor_connection,"map-edge/neighbor-city connection; edge via +0xb0/+0xb4, neighbor via this+0x48[+0x58/+0xa4]; funds this+0x38[+0x54/+0x10]/this+0x140; piece ids 0x24/0x25/0x2e/0x2d per net; opens dialog msg 0xfa2 via FUN_1000104a[+0x7c] [CONFIRMED @ 0x10008a4a]"
0x1000de17,net-decoration,C2,sc3_ntwrk_balance_decor_density,"map scan counts pieces w/ DAT_100323c0 & DAT_10032464 handlers; compares to ftol target; RNG DAT_10032468 (FUN_1001f232/FUN_1001f26f) adds/removes decor ids 0x3ac0/0x3ac1/0x3ac2/0x235b <-> base 0x1d/0x23 [CONFIRMED @ 0x1000de17]"
0x100077e7,net-build,C2,sc3_ntwrk_clear_region,"bulldoze validate+execute over rect param_3; per-tile rule +0x144, per-layer +0x78 on this+0x3c/+0x40/+0x44, compat FUN_1001a7f7; if param_7 remove via +0x48 + this+0x34[+0x3c] [CONFIRMED @ 0x100077e7]"
0x100130e9,serialization,C2,sc3_ntwrk_layer_load,"network layer LOADER; FUN_10025f0d/FUN_100262a3 read stream, vcall +0x38; 3 count fields; deserialise via FUN_1000d6b3 into sub-layers this[0xf]/[0x10]/[0x11]; 4-section framing (short==4) [CONFIRMED @ 0x100130e9]"
0x10024e10,config,C2,sc3_ntwrk_read_config,"reads ~24 named props (keys DAT_1002cee0..0x1002cf78) via param_1 vtable +0x38/+0x4c/+0x30 into this+0x04..0x114 w/ defaults 0x57a/0xa1096a4f/0x2026960b/0x62e69238/0x5bee0 [CONFIRMED @ 0x10024e10]"
0x10007d32,net-build,C2,sc3_ntwrk_clear_region_layer,"near-duplicate of 0x100077e7; region test this+0x30[+0x108], rule +0x144, per-layer +0x78, compat FUN_1001a7f7; removal pass via +0x128 [CONFIRMED @ 0x10007d32]"
0x10006018,ui-dialog,C2,sc3_ntwrk_confirm_dialog,"modal confirm dialog; script-msg keys 0x4372cf29/0xa372cf2d via FUN_1001ef65[+0xc]; string res 0x252 + param_1 title; returns OK(0x12340001) vs cancel(0x12340000) [CONFIRMED @ 0x10006018]"
0x1000cde8,net-render,C2,sc3_ntwrk_select_piece_sprite,"adjacency-flag sprite selector; tests flag bits 0x8000/0x20000/.../0x200000 -> variant 1..8; tile x/y this+0x10 (11+11 bits); edge-detect vs map dims; bitmap res 0x54 grp 0x82e0074c; chains FUN_10024749 [CONFIRMED @ 0x1000cde8]"
0x1001d761,net-tiling,C2,sc3_ntwrk_extend_diag_connection,"diagonal-connection extender; matches dir vs 6 tables DAT_10031fd8..DAT_10032028; computes mating dir; recurse vcall +0x104, place +0xf4; tile id FUN_1001a93d, orient +0xc0 [CONFIRMED @ 0x1001d761]"
0x1001a2c0,net-tiling-eval,C2,sc3_ntwrk_lookup_tile_rule,"per-tile rule resolver; net 1..6 selects rule-string table DAT_1003195c/197c/199c/19bc/19dc/19fc/1a1c/1a3c; matches 4-byte neighbor sig (FUN_1001a1f3) vs 8 rows DAT_1003193c; returns piece id+orient in *param_4/*param_5 [CONFIRMED @ 0x1001a2c0]"
0x10016327,net-tiling-eval,C2,sc3_ntwrk_apply_rule_stage,"rule-stage applier (3x from FUN_1001547b); per node FUN_10019768 collect, FUN_100228ff/FUN_1002217a match, validate (adjacency+FUN_1001a7f7), commit FUN_100165d8, output coords to param_3/param_4 [CONFIRMED @ 0x10016327]"
```

## Notable data tables surfaced (raw)

- **`DAT_10031380`** and **`DAT_10031f34`** — per-row direction-bit tables used to build the 32×32 adjacency bitmask in `FUN_1001547b` / `FUN_1001da5f` `[CONFIRMED]`. Raw bytes not in export.
- **`DAT_10031fd8`,`DAT_10031fe8`,`DAT_10031ff8`,`DAT_10032008`,`DAT_10032018`,`DAT_10032028`** — 6 parallel piece-id tables indexed by orientation (road/rail vs highway ramp/diagonal families) `[CONFIRMED @ 0x1001ca1a, 0x1001c102, 0x1001d761]`.
- **`DAT_1003193c` (+ `DAT_1003195c`…`DAT_10031a3c`)** — the tiling-rule signature table + 8 per-network rule-string tables `[CONFIRMED @ 0x1001a2c0]`.
- **`DAT_100313c0`,`DAT_100316d4`,`DAT_1003178c`,`DAT_10031844`** — legacy-tile→new-piece conversion tables (each a struct array with base/stride header) `[CONFIRMED @ 0x1001272e]`.
- **`DAT_1002cee0`…`DAT_1002cf78`** — ~24 property-key constants for the config reader `[CONFIRMED @ 0x10024e10]`.
- Broadcast message id **`0x62c0838e`** fired after network mutation (`FUN_1000488d`, `FUN_10009d20`) `[CONFIRMED]`.

## Not determined (with missing evidence)

- **No per-tick / `Simulate()` entry in this slice.** The registered SIMCITY bucket-list tick callback was not among these 25 (they are build-tool, tiling, serialisation, config and UI functions). `FUN_1000de17` (decor-density balancer) is the only candidate for a periodic maintenance pass, but its *trigger* (tick vs on-demand) is not shown in its body — *needs* an xref of its caller against a bucket/registration site.
- **Semantics of the raw tile-id constants** (`0x49`, `0x2bfa`, `0x3acb`, `0x3afa`, `0x3ac0-0x3ac2`, `0x3b02-0x3b25`, `0x24/0x25/0x2d/0x2e/0x5c/0x1d/0x2c`): confirmed as piece ids by usage, but the id→visual/piece-name mapping lives in the `TilingRules\*.txt` data, not in code — *needs* the data tables.
- **Raw bytes of the bit/rule/conversion `DAT_*` tables** above are outside the decompiled export — *needs* a data-section dump / live Ghidra read.
- **The second save tag `0xE223741F`/`0xA317745F` linkage** to this GROUP `0x2147c2dd`: `0x2147c2dd` is confirmed the network save group here; whether it equals the earlier §4 record tag is not shown in these functions — *needs* the consumer that reads the record header (`FUN_1000d688`/`FUN_1000d6b3` internals, outside slice).
