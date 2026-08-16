# SIMDSTR.DLL — C0 cluster (25 largest) + the eight save-section serialisers

Building on `SIMDSTR.md`, `SIMDSTR_CLUSTER1.md`, `SIMDSTR_PASS2.md`. All addresses are Ghidra VAs in `re/ghidra_export_simdstr/`. Every function below was body-read, mechanically described, callees identified, named → **C2**. No C3/C4 claimed.

## 0. The serialisation primitives (confirmed this pass)

- **`FUN_1002a9ae` = open-section-for-READ** [CONFIRMED @ 0x1002a9ae, slice member]. Constructs a reader (vtable `PTR_FUN_10033f74`), allocates two sub-streams (`operator_new(0x14)`+`FUN_1002ae2c`), validates a `0xdeadbeef` magic at `+8`. Its result is fetched by `FUN_1002ad44` and consumed with **read** slots.
- **`FUN_1002abca` = open-section-for-WRITE** (paired with `FUN_10004136(buf,&tag)` which packs the `{typeTag, groupId, 0}` triple). Result fetched by `FUN_1002ad44`, consumed with **write** slots.
- **`FUN_1002ad44(rec)`** returns the live stream object; **`FUN_1002ad05(rec)`** closes it.
- **Save vs load is decided purely by which opener is called.** LOAD → `FUN_1002a9ae`; SAVE → `FUN_1002abca`.

**Stream vtable slot map** — proven by the symmetric LOAD/SAVE pair on group `0xc4c90997` (`0x1001f7e9` reads exactly what `0x1002027f` writes, field-for-field):

| Value kind | WRITE slot | READ slot |
|---|---|---|
| 32-bit int | vt+0x88 | vt+0x38 |
| bool/byte | vt+0x68 | vt+0x18 |
| wide value (i64/float/blob) | vt+0x98 | vt+0x48 |
| string | vt+0x88 (after vt+0x34/0x30 fetch) | vt+0x34 |
| extra scalar | vt+0x90 | vt+0x14 |
| raw fixed block (ptr,size) | vt+0xac | (record accessor) |

Type-tag prefix in the section key is per-group, **not** save/load: `0x206c6e7c` for group `0x21f6abca`; `0xe1f6abe2` for all the others.

## 1. THE EIGHT SAVE-SECTION LAYOUTS (highest-value deliverable)

The `SC3DisasterLayer` manager (class #1, CLSID `0x61f6abf5`) owns a GZ persistent-object collection reached through its enumerator `manager+0x10` (`vt+0x18` = get-iterator, iter `+4` = next, `+0` = reset, `+0x20` = per-node type-id, `+0x10/+0x14/+0x1c/+0x30/+0x34` = field accessors). Every **list** section walks that collection, keeps only nodes whose type-id equals a per-record tag, and streams them; the **fixed-array** sections stream an in-place `std::vector`.

### Group `0x21f6abca` — the manager's own master record  (tag `0x206c6e7c`)
- **LOAD `0x100089c3`**, **SAVE `0x10008de8`**.
- Both first iterate the **global registry `DAT_1003a7b8`** delegating to each child (`load` via child `vt+0xc`, `save` via child `vt+0x18`), then stream the manager's own scalar/flag fields.
- SAVE order: `u32 this+0xb0` (vt+0x98), `u32 this+0xa4` (vt+0x88), `bool this+0xa0` (vt+0x88), `u32 this+0xb4` (vt+0x88), `bool this+0x54` (vt+0x88).
- LOAD order: `this+0xb0`, `this+0xa4`, `bool this+0xd0`, `this+0xd4`, `bool this+0x54` (all vt+0x38). (Save writes `+0xa0/+0xb4`; load restores into `+0xd0/+0xd4` — reported as-is.)

### Group `0x4296380e` — a variable list  (SAVE `0x1000d777`)
count (vt+0x88) then per node (type-id `0x4296380e`): `u32 idLo`+`u32 idHi` from node `vt+0x10` (vt+0x88, vt+0x88), `u32 node[0xf]`(=off 0x3c) (vt+0x98), `strA` from node `vt+0x34` (vt+0x88), `strB` from node `vt+0x30` (vt+0x88).

### Group `0x621cda33` — a variable list  (SAVE `0x10005917`)
count (vt+0x88) then per node (type-id `0x621cda33`): `u32 idLo`+`u32 idHi` from `vt+0x10` (vt+0x88 ×2), `u32 node[7]`(=off 0x1c) (vt+0x98). (This is the group `FUN_1000414f` references at `+0x1c vt+0x34` when spawning fire tiles → these are burning-tile / effect records.)

### Group `0xc336f77c` (+companion `0xe300c976`) — fixed vector of 36-byte records  (SAVE `0x10001dea`)
- Part A (`0xc336f77c`): `count = min(50000, (this+0x68 − this+0x64)/0x24)`; write count (vt+0x88); per element copy **9 dwords (0x24=36 bytes)** and write raw block (vt+0xac).
- Part B (`0xe300c976`, only if `this+0x5c != 0`): `count = min(50000, this+0x5c)` (vt+0x88); enumerate nodes type-id `0x42963812`; per node `node[1] vt+0x1c` → 36-byte record, write block (vt+0xac).

### Group `0x22963800` — a variable list  (SAVE `0x10015403`, slice)
count (vt+0x88); per node (type-id `0x22963800`): `idLo`,`idHi` from `vt+0x10` (vt+0x88 ×2), `u32 node[0x19]`(=off 0x64) (vt+0x98), then **3 dwords** from sub-object `node[1] vt+0x10` (vt+0x90 ×3), `strA`(node vt+0x34, vt+0x88), `strB`(node vt+0x30, vt+0x88).

### Group `0x24889f78` (+companion `0x24889f79`) — fixed vector of 24-byte records  (SAVE `0x10011158`)
- Part A: `count = min(50000, (this+0x68 − this+0x64)/0x18)`; write count (vt+0x88); per element copy **6 dwords (0x18=24 bytes)**, write block (vt+0xac).
- Part B (`0x24889f79`, if `this+0x5c != 0`): count `min(50000,this+0x5c)` (vt+0x88); enumerate type-id `0x13873256`; per node `node[1] vt+0x14` → 24-byte record, write block (vt+0xac).

### Group `0x45326359` (+companion `0x8532635c`) — fixed vector of 24-byte records  (SAVE `0x1000b4ed`, slice)
- Part A: `count = min(50000, (this+0x6c − this+0x68)/0x18)`; write count (vt+0x98); per element copy **6 dwords (24 bytes)**, write block (vt+0xac). *(Note this vector lives at `this+0x68..0x6c`, not `+0x64..0x68`.)*
- Part B (`0x8532635c`, if `this+0x4c != 0`): count/flag (vt+0x98); enumerate via a **second** collection `this+0x14` (not `+0x10`), type-id `0x13873255`; per node `node[1] vt+0x14` → 24-byte record, write block (vt+0xac).

### Group `0xc4c90997` — a single versioned scalar record  (LOAD `0x1001f7e9`, SAVE `0x1002027f`)
The one full save/load pair — SAVE order (LOAD reads the identical sequence):
1. `u32 this+0x70` (vt+0x88 / read vt+0x38)
2. `bool (this+0x4c>0)`, also stored to `this+0x7d` (vt+0x68 / read vt+0x18 into `this+0x7d`)
3. `u32 this+0x5c` (vt+0x88 / vt+0x38)
4. `u32 this+0x74` (vt+0x88 / vt+0x38)
5. `u32 this+0x78` (vt+0x88 / vt+0x38)
6. `bool this+0x7c` (vt+0x68 / vt+0x18)
7–10. **wide** `this+0x60`, `this+0x64`, `this+0x68`, `this+0x6c` (vt+0x98 / vt+0x48)
11. `this+0x80` (vt+0x98 / read vt+0x38) — **guarded on section version `>1`** on load (`if (1 < local_30)`), i.e. this field was added in a later save-format revision.

**Ninth section found in the slice:** group **`0x02963821`** SAVE = **`0x1001335d`** — same list shape as `0x22963800` but richer per-record: count (vt+0x88); per node (type-id `0x2963821`): `idLo`,`idHi` (vt+0x88 ×2), 3 dwords from `node[1] vt+0x14` (vt+0x90 ×3), `bool` from `node[1] vt+0x18` (**vt+0x70**), `float` from `node[1] vt+0x1c` (vt+0x90), `strA`(vt+0x34→vt+0x88), `strB`(vt+0x30→vt+0x88).

## 2. Per-tick / init disaster machines (second-highest value)

- **`0x10017400` `sc3_dstr_toxic_tick_fsm`** — the **Toxic-Cloud / acid-rain Simulate FSM**. State `this+0x30` (0→1→2→3→4→5), tick `this+0x34`; stage gates `DAT_1003aa94 / DAT_10039b30 / DAT_10039b34 / DAT_10039b38`. Stage 3→4 spawns clouds (`FUN_10016a9e`+`FUN_10016ebd`), sets rain-start (`DAT_10039b6c/b70`) and cloud duration `this+0x60` (`DAT_10039b44/b48`). Stage 4 is the rain loop: begins/ends rain over the cloud list `this+0x68` with `DAT_10039b74/b78` (rain duration) and `_DAT_10039b7c` (inter-rain gap), firing notifications `FUN_10015019/1503d/1505d/14ef2/14f16`. Ties directly to the toxic tunables catalogued in `SIMDSTR.md §4`.
- **`0x10016a9e` `sc3_dstr_toxic_spawn_clouds`** — instances toxic clouds over an area iterator (`FUN_10005b17/b42/ba5`); cap `= (DAT_10039b24−DAT_10039b20)*(this+0x64+1)/5 + DAT_10039b20`; cloud class `0x92a34b4f/0x82a34b4f`; height `DAT_10039b3c/b40`; radius-per-level `DAT_10039b80/b84`; appends to cloud list `this+0x68` (`FUN_100176af`), count `this+0xa8`, bbox `this+0x8c/90/94/98`.
- **`0x10014ac1` `sc3_dstr_toxic_find_spawn_site`** — best-cell finder for a cloud (4-direction growth scoring, threshold `0x4f`), map dims `this+0x5c/0x60`.
- **`0x10002411` `sc3_dstr_track_disaster_init`** — seeds the **`0x100029fe` swath-FSM** (documented in `SIMDSTR_CLUSTER1.md`): stores 3 coord triples → `this+0x48..0x68`, direction bool `this+0x6c=|dz|<|dx|`, phase durations `DAT_1003a6b0/DAT_1003958c/590/594` → `this+0x10..1c`, sets `this+0x28b0 = 1` (or 4 if `!param_6`), builds effect object class `0xa223be6c/0x22a34686` at `this+0x2890`, subscribes `0x925ec00b`, seeds speed via `FUN_10002846(v*_DAT_10032280)`. **This resolves the `SIMDSTR_CLUSTER1.md §3` open item** "which ctor installs the `0x100029fe` FSM / where its `DAT_10039520` block is consumed."
- **`0x10003776` `sc3_dstr_track_build_path`** — the swath path generator for that disaster: line-rasterises `FUN_100266e0` (max `0x501`=1281 points) into `this+0x74` (stride 8), per-point jitter (`FUN_10022c1c(-1,2)`) clamped to map dims, widened by `(this+0x3d − 1)` perpendicular to orientation `this+0x6c`.
- **`0x1001d156` `sc3_dstr_effect_tick_fsm`** + **`0x1001cb20` `sc3_dstr_effect_disaster_init`** + **`0x1001d589` `sc3_dstr_effect_damage_area`** + **`0x1001d7c8` `sc3_dstr_effect_build_path`** + **`0x1001c110` (tunable loader)** — a **complete, self-contained fourth disaster** distinct from the swath one: state `this+0x80` (1..6), durations `this+0x10..1c` from `DAT_1003ab64/DAT_1003a23c/a240/a244`; effect classes `0x3123be6c`/`0x44bec831` with sprite anim `DAT_1003a24c`; radius `DAT_1003a238`; subscribes `0x6491d942..945`; instance class `0x9223be6c/0x8223be6c`. This is the disaster that `SIMDSTR_CLUSTER1.md` left open as "who owns `0x1001da8f render_path_effects`" — **answer: this cluster** (shared `DAT_1003a2xx` block, all loaded by `0x1001c110`).
- **`0x1001ab55` `sc3_dstr_ufo_execute_attack`** — UFO attack executor: dispatches `FUN_1001a560`(open sites)+`FUN_10019cf6`(target buildings), caps `DAT_10039eb0/eb4`, issues destroy/crop/abduct commands via layer `this+0x14` (vt+0x48/0x4c/0x54/0x5c), mode `this+0x58`.
- **`0x1000677c` `sc3_dstr_fire_instance_tick`** — per-instance fire FSM (`param_1[7]` 0..3), spread cadence `param_1[9]/[10]`, escalation `param_1[8]`, effect class `0xf2a34505/0xe2a34505`, rand `FUN_10022ba1`.

## 3. Layer lifecycle, damage, config

- **`0x10008f42` `sc3_dstr_layer_shutdown_city`** — exact teardown mirror of `FUN_1000857d` (init): unsubscribes the same 7 broadcast ids, drains lists `+0x1c/+0x10`, iterates `DAT_1003a7b8` (`vt+0x14`), releases 18 held service pointers. Closes the init/shutdown pair.
- **`0x1001dfed` / `0x1000414f`** — track-disaster tile destruction / per-tile effect application (fire `0xf2a34505`, secondary `0x92b5a0da`; group `0x621cda33` records; tally into `FUN_10003e56`).
- **`0x10007bb3` `sc3_dstr_classify_apply_building`** — per-building damage classifier (query id `0xe0faadc7`, region test `this+0x80 vt+0x58`, appliers `FUN_10008b8b/FUN_10008c42`).
- **`0x1000c3dd` `sc3_dstr_spawn_capped_instance`** — creates a persistent instance (`operator_new(0x2c)`, id record `{0x207edc0e,0x57e,0x3faf}`), caps the `this+0x64` list at 2, posts message `(1,0xf6,0,0,0)` via `FUN_1002a88a`.
- **`0x1002c9e8` `sc3_dstr_ini_locate_section`** — INI group-offset locator/cacher (caches to `this+0xc0`, sets mode `this+0xb4`), extending the INI-primitive family from `SIMDSTR_CLUSTER1.md`.
- **`0x10006e31` `sc3_dstr_rbtree_erase_rebalance`** — a `std::_Rb_tree` node erase+rebalance (the map used by those INI caches). Library-shaped but unmatched by FidDb; mechanical only.
- **`0x1000f4bd` / `0x10010d2f` / `0x1001c110`** — three Pattern-A (`FUN_1002a8d6` property-id) tunable loaders writing contiguous global blocks `DAT_10039a40..a7c`, `DAT_10039a88..ac4` (incl. fire-spread `DAT_10039ab4/ab8` consumed by `FUN_10011e52`), and `DAT_1003a220..a25c` (the effect-FSM block above).

## 4. Classification table (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x10017400,disaster-toxiccloud,C2,sc3_dstr_toxic_tick_fsm,"per-tick FSM state this+0x30(0..5)/tick this+0x34; gates DAT_1003aa94/DAT_10039b30/b34/b38; stg3->4 spawn FUN_10016a9e+16ebd rain DAT_10039b6c/b70 dur DAT_10039b44/b48; stg4 rain loop DAT_10039b74/b78 gap _DAT_10039b7c; notify FUN_10015019/1503d/1505d/14ef2/14f16"
0x10002411,disaster-sim,C2,sc3_dstr_track_disaster_init,"seeds FSM 0x100029fe; 3 coord triples ->this+0x48..0x68; dir this+0x6c=|dz|<|dx|; dur DAT_1003a6b0/1003958c/590/594->this+0x10..1c; state this+0x28b0=1(4 if !param_6); effect 0xa223be6c/0x22a34686->this+0x2890; subscribe 0x925ec00b; speed FUN_10002846(v*_DAT_10032280)"
0x10003776,disaster-spread,C2,sc3_dstr_track_build_path,"line raster FUN_100266e0 (max 0x501 pts) into this+0x74 stride8; per-pt jitter FUN_10022c1c(-1,2) clamped to map dims (+0x288c vt+0xcc/0xd0); widen (this+0x3d-1) perp to orient this+0x6c; count this+0x2880/287c"
0x10016a9e,disaster-toxiccloud,C2,sc3_dstr_toxic_spawn_clouds,"area iter FUN_10005b17/b42/ba5; cap=(DAT_10039b24-DAT_10039b20)*(this+0x64+1)/5+DAT_10039b20; cloud class 0x92a34b4f/0x82a34b4f; height DAT_10039b3c/b40; radius DAT_10039b80/b84; list this+0x68(FUN_100176af) count this+0xa8 bbox +0x8c/90/94/98"
0x10014ac1,disaster-toxiccloud,C2,sc3_dstr_toxic_find_spawn_site,"area iter FUN_10005b17/b42/ba5; seed FUN_10022c8d(this+0x30); cell score FUN_1001534d; 4-dir growth (local_5c dir table) score vs 0x4f; dims this+0x5c/0x60; best (x,y)->param_1/param_2"
0x1001ab55,disaster-ufo,C2,sc3_dstr_ufo_execute_attack,"mode this+0x58(2/4/5); FUN_1001a560 open-sites + FUN_10019cf6 target-bldgs; caps DAT_10039eb0/eb4; cmds via layer this+0x14 vt+0x10/1c/24/54/48/4c/5c; query FUN_10024e7b id 0xa2cc6284; writes this+0x50/54"
0x1000677c,disaster-fire,C2,sc3_dstr_fire_instance_tick,"per-instance FSM param_1[7](0..3); bldg layer param_1[2] vt+0x34/64/68/30/1c; cadence param_1[9]/[10] escalate param_1[8]; effect 0xf2a34505/0xe2a34505; rand FUN_10022ba1; ftol; FUN_100069e7/10006004/10005372; msg param_1[6] vt+0xc"
0x1001cb20,disaster-sim,C2,sc3_dstr_effect_disaster_init,"init effect FSM 0x1001d156; layer this+0x60 dims +0x58/5c; origin param_3->this+0x48/4c/50; dur DAT_1003ab64/1003a23c/a240/a244->this+0x10..1c; state this+0x80=1(4); subscribe 0x6491d942..945; instance 0x9223be6c/0x8223be6c->this+0x64; cb FUN_1001cec9 via +0x24 vt+0xf0"
0x1001d156,disaster-sim,C2,sc3_dstr_effect_tick_fsm,"state this+0x80(1..6) tick this+0x84; dur this+0x10/14/18/1c; stg4->5 msg 0xe5 x2 via +0x44, spawn this+0x64 vt+0xc/10/14/18 DAT_1003a250/254/258/25c, cam FUN_10024067+layer+0x34 vt+0x200; stg6 cleanup FUN_1001d348/FUN_1001c06d"
0x1001d589,disaster-spread,C2,sc3_dstr_effect_damage_area,"square area +/-DAT_1003a238 around (param_1,param_2); bldg query this+0x60+0x38 vt+0x7c; test FUN_1001c7f0; destroy FUN_1001dfed; msg (1,0xf0,x,y,0) via +0x44; effect 0x3123be6c + sprite 0x44bec831 anim DAT_1003a24c"
0x1001d7c8,disaster-spread,C2,sc3_dstr_effect_build_path,"cell path into param_3 vector stride8; probe FUN_1001d766 +/-x/+/-y from seed; extend chosen axis; append FUN_1001e5c1; reverse first half; layer this+0x60+0x38"
0x1001dfed,disaster-damage,C2,sc3_dstr_track_destroy_tile,"destroy/tally tiles across 3 sublayers this+0x60/+0x38/3c/40 (vt+0x7c active,+0x60,+0x58); geom FUN_10004341/1000411d/10004136/1000435a; accum this+0x70 count +0x74 cost; param_3 mode param_4 finalize->layer +0x28 vt+0x34"
0x1000414f,disaster-damage,C2,sc3_dstr_track_apply_tile_effect,"tile effect at (param_1,param_2); bldg layer this+0x288c+0x38 vt+0x7c; flags &0x400/0x800/0x400000; rand FUN_10022ba1(0x32)/(0xf); effect 0xf2a34505/0xe2a34505 or 0x92b5a0da/0x82b5a0da; grp 0x621cda33 via +0x1c vt+0x34->FUN_10005e59; tally FUN_10003e56"
0x10007bb3,disaster-target,C2,sc3_dstr_classify_apply_building,"bldg damage classifier; query this+0x2c vt+0x24 tags 0x3232/0x2f53/300; bldg id 0xe0faadc7 + 0x253e6ac; buckets 2/8/0x10/0x20; apply FUN_10008b8b/FUN_10008c42; region this+0x80 vt+0x58; geom FUN_10004341"
0x1000c3dd,disaster-sim,C2,sc3_dstr_spawn_capped_instance,"new(0x2c) vtables PTR_FUN_10032b0c/LAB_10032adc/LAB_10032994; id {0x207edc0e,0x57e,0x3faf}; cap list this+0x64 to 2 (FUN_1000c89c); svc FUN_1002a807 vt+0xcc/0x164/0x128/0x13c; post msg (1,0xf6,0,0,0) FUN_1002a88a vt+0x14"
0x10008f42,disaster-layer,C2,sc3_dstr_layer_shutdown_city,"teardown mirror of FUN_1000857d; unsub 7 ids 0x220fbd5b/6373d4e2/373d622/4373d6a0/45356db9/8373d754/373d8ce (FUN_10022eeb vt+0x18); drain lists +0x1c/+0x10 (FUN_10009c80); iter DAT_1003a7b8 vt+0x14; release 18 svc ptrs +0xc0/b8/68/80/7c/74/78/6c/70/ac/60/30/28/5c/98/94/58"
0x1002c9e8,disaster-ini,C2,sc3_dstr_ini_locate_section,"locate+cache INI group offset; mode this+0xb4(->1/2); stream this+0x64/+0x78 vt+0x38; tokenizers FUN_1002ef13/ef96/efad, FUN_10006a9a/10004acb; compare FUN_100223ac; cache this+0xc0=line, this+0xb4=2"
0x1000f4bd,disaster-tunables,C2,sc3_dstr_load_tunables_2486_a40,"property provider FUN_1002a8d6 vt+0x14; ids 0x24860901..0911 -> DAT_10039a40..a7c + DAT_1003a960; scope FUN_100231cb/FUN_10023664"
0x10010d2f,disaster-fire,C2,sc3_dstr_fire_load_spread_tunables,"property provider; ids 0x44860901..0918 -> DAT_10039a88..ac4 + DAT_1003a9c4; DAT_10039ab4/ab8 consumed by fire spread FUN_10011e52"
0x1001c110,disaster-tunables,C2,sc3_dstr_load_effect_tunables_a220,"property provider; ids 0x24860901..0917 -> DAT_1003a220..a25c + DAT_1003ab64; DAT_1003a24c/a238/a250/254/258/25c consumed by effect FSM 0x1001d156/1001d589/1001cb20"
0x10006e31,disaster-infra,C2,sc3_dstr_rbtree_erase_rebalance,"std::_Rb_tree node erase+rebalance (color node+0, links +4/8/0xc); param_2 root param_3 leftmost param_4 rightmost; rotations FUN_1000705f/1000709f"
0x1002a9ae,disaster-serialize,C2,sc3_dstr_open_read_section,"open section for READ; reader ctor vtable PTR_FUN_10033f74; 2 substreams new(0x14)+FUN_1002ae2c; magic 0xdeadbeef at +8; result consumed by LOAD serialisers via FUN_1002ad44 (read vt+0x14/18/34/38/48)"
0x100089c3,disaster-serialize,C2,sc3_dstr_load_section_21f6abca,"LOAD grp 0x21f6abca tag 0x206c6e7c (FUN_1002a9ae); delegate DAT_1003a7b8 child vt+0xc; read this+0xb0,+0xa4,bool+0xd0,+0xd4,bool+0x54 (vt+0x38)"
0x10008de8,disaster-serialize,C2,sc3_dstr_save_section_21f6abca,"SAVE grp 0x21f6abca (FUN_1002abca); delegate DAT_1003a7b8 child vt+0x18; write u32+0xb0(vt+0x98),u32+0xa4,bool+0xa0,u32+0xb4,bool+0x54(vt+0x88)"
0x1000d777,disaster-serialize,C2,sc3_dstr_save_section_4296380e,"SAVE grp 0x4296380e list; count(vt+0x88); per node type 0x4296380e: idLo/idHi(vt+0x10;vt+0x88x2), u32 node[0xf](vt+0x98), strA(vt+0x34;vt+0x88), strB(vt+0x30;vt+0x88)"
0x10005917,disaster-serialize,C2,sc3_dstr_save_section_621cda33,"SAVE grp 0x621cda33 list; count(vt+0x88); per node type 0x621cda33: idLo/idHi(vt+0x88x2), u32 node[7]=off0x1c(vt+0x98)"
0x10001dea,disaster-serialize,C2,sc3_dstr_save_section_c336f77c,"SAVE grp 0xc336f77c: vector[this+0x64..0x68] of 0x24-byte recs, count=min(50000,n)(vt+0x88), block write(vt+0xac); companion grp 0xe300c976 if this+0x5c!=0: enum type 0x42963812 node[1] vt+0x1c -> 0x24 block"
0x10015403,disaster-serialize,C2,sc3_dstr_save_section_22963800,"SAVE grp 0x22963800 list; count(vt+0x88); per node type 0x22963800: idLo/idHi(vt+0x88x2), u32 node[0x19]=off0x64(vt+0x98), 3 dw from node[1] vt+0x10(vt+0x90x3), strA(vt+0x34;vt+0x88), strB(vt+0x30;vt+0x88)"
0x10011158,disaster-serialize,C2,sc3_dstr_save_section_24889f78,"SAVE grp 0x24889f78: vector[this+0x64..0x68] of 0x18-byte recs, count=min(50000,n)(vt+0x88), block(vt+0xac); companion grp 0x24889f79 if this+0x5c!=0: enum type 0x13873256 node[1] vt+0x14 -> 0x18 block"
0x1000b4ed,disaster-serialize,C2,sc3_dstr_save_section_45326359,"SAVE grp 0x45326359: vector[this+0x68..0x6c] of 0x18-byte recs, count(vt+0x98), block(vt+0xac); companion grp 0x8532635c if this+0x4c!=0: 2nd collection this+0x14 enum type 0x13873255 node[1] vt+0x14 -> 0x18 block"
0x1001f7e9,disaster-serialize,C2,sc3_dstr_load_section_c4c90997,"LOAD grp 0xc4c90997 (FUN_1002a9ae); read this+0x70(vt+0x38),+0x7d(vt+0x18),+0x5c/74/78(vt+0x38),+0x7c(vt+0x18),+0x60/64/68/6c(vt+0x48); if section-version local_30>1: +0x80(vt+0x38)"
0x1002027f,disaster-serialize,C2,sc3_dstr_save_section_c4c90997,"SAVE grp 0xc4c90997 (FUN_1002abca); write +0x70(vt+0x88),bool(this+0x4c>0)->+0x7d(vt+0x68),+0x5c/74/78(vt+0x88),bool+0x7c(vt+0x68),+0x60/64/68/6c/80(vt+0x98); symmetric to LOAD 0x1001f7e9"
0x1001335d,disaster-serialize,C2,sc3_dstr_save_section_2963821,"SAVE grp 0x02963821 list; count(vt+0x88); per node type 0x2963821: idLo/idHi(vt+0x88x2), 3 dw node[1] vt+0x14(vt+0x90x3), bool node[1] vt+0x18(vt+0x70), float node[1] vt+0x1c(vt+0x90), strA(vt+0x34;vt+0x88), strB(vt+0x30;vt+0x88)"
```

## 5. Not determined / uncertain

- **Which disaster class owns each save section.** Group `0x21f6abca` is definitively the **`SC3DisasterLayer` manager's** own record (scalar fields + delegation to registry `DAT_1003a7b8`) [CONFIRMED @ 0x10008de8/0x100089c3]. The list/vector sections stream child collections keyed by per-record type-ids (`0x4296380e`, `0x621cda33`, `0x22963800`, `0x02963821`, `0x13873255`, `0x13873256`, `0x42963812`) but the serialisers carry **no disaster-name string** and the type-id → disaster-type binding is not shown in these bodies. `0xc4c90997` is a single versioned per-instance record; its field layout is fully mapped but its owning class is **[UNCERTAIN]** — missing: the class vtable slot whose method calls each serialiser (same `.rdata` barrier documented in `SIMDSTR_PASS2.md §2a/§2b`; a `VtableDump.java`/`pe_read.py` pass over the 12 class vtables scanning for these serialiser addresses would bind them).
- **LOAD halves of the six SAVE-only groups.** Only `0x21f6abca` and `0xc4c90997` had both halves in scope. The load counterparts for `0x4296380e / 0x621cda33 / 0xc336f77c / 0x22963800 / 0x24889f78 / 0x45326359 / 0x02963821` exist (each uses `FUN_1002a9ae` + read slots) but are outside this slice — **not read**.
- **Named type of the two path/swath FSM disasters** (`0x100029fe`-cluster via init `0x10002411`, and `0x1001d156`-cluster via init `0x1001cb20`). Both are fully mechanically mapped (init + tick FSM + path builder + damage pass + tunable block) but neither reads a disaster-group *string* (their tunables load by 32-bit property id), so the type label is **[UNCERTAIN]**. A moving severity-scaled swath (`0x100029fe`) is consistent with Tornado `[iOS-HINT]`; the sprite-effect path disaster (`0x1001d156`, effect classes `0x3123be6c/0x44bec831`) is a distinct second one — missing: the INI group literal for property prefixes `0x*4237*` and `0x2486090*`.
- **Field semantics inside the fixed-block records** (`0x24`/`0x18`-byte elements written via `vt+0xac`). The serialisers copy raw dwords; individual field meanings require reading the producing/consuming code for vectors `this+0x64..0x68` / `this+0x68..0x6c` (not in this slice).
- **Shipped numeric tunable defaults** for the three new loader blocks (`DAT_10039a40+`, `DAT_10039a88+`, `DAT_1003a220+`) live in `SC3DisasterLayer.INI` inside `SYS.PAK` — data extraction, not decompilation (unchanged from `SIMDSTR.md §7`).
