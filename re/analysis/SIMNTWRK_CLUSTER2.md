# SIMNTWRK.DLL — C0 cluster (second pass), 25 largest, analysis

All addresses are SIMNTWRK.DLL VAs (image base `0x10000000`). Every function below was read in full and is rated **C2** (body read, callees identified, mechanically described, named). Building on `SIMNTWRK.md` and `SIMNTWRK_CLUSTER1.md` — the three network sub-layer objects are `this+0x3c` / `this+0x40` / `this+0x44`, consistent with both prior docs.

## Headline finds

### 1. THE PERIODIC-UPDATE CALLBACK REGISTRATION — found (resolves CLUSTER1's open item on the tick) `[CONFIRMED]`

CLUSTER1 found no tick entry in its slice. This slice contains a **family of 7 near-identical layer-registration functions** that each subscribe the module's object to a single recurring notification message **`0x635ee3c3`**. Mechanically identical shape `[CONFIRMED @ 0x1000f79c, 0x1000e9e7, 0x1000e537, 0x1000ee4b, 0x1000fc45, 0x100100bc, 0x1000f2c7]`:

1. `operator_new(0x98)` + `FUN_10010be8` → handler object at `param_1+0xb0` (vtables `PTR_LAB_1002c1b0`/`PTR_LAB_1002c184`).
2. `FUN_10021b24()` (service registry) → pull 3 services via vcalls `+0x140`/`+0x11c`(or `+0x120`/`+0x124`)/`+0x13c` into `param_1+0xac`/`+0xc4`/`+0xb4`.
3. Acquire 3 sub-layer interfaces via `svc+0x54(dest, IID=0xa1c085db, index)` — the **index triple differs per function** (the per-network selector).
4. Get factory (`+0x15c`), create a simulator object by a **resource id** via `+0x54(id)`.
5. Register the update handler: `handler+0x10(flag, svc, svc, svc, svc, svc, 0, a, b, c, netType, simObj)` — last-but-one int is a **network type 1..6**.
6. Build a message record `{type=0x635ee3c3, …}`, register it via `FUN_1001ef65()+0x10`, then **subscribe** `param_1-0x64` to it via `FUN_10025825(obj, FUN_10021b37())` (message server).

| RVA | IID-index triple | factory resource id | netType (arg) | msg extra |
|---|---|---|---|---|
| `0x1000f79c` | `(2, 0, 0)` | `0x3e81` | 4 | flags\|4 |
| `0x1000e537` | `(0x1c, 0x10, 0x16)` | `0x3e80` (16000) | 1 | flags\|4 |
| `0x1000e9e7` | `(0x1d, 0x11, 0x17)` | `0x3e81` | 4 | flags\|4 |
| `0x1000ee4b` | `(0x1e, 0x12, 0x18)` | `0x4268` (17000) | 2 | flags\|4 |
| `0x1000f2c7` | `(0x1f, 0x13, 0x19)` | `0x43f8` | 6 | +8=`0xffffffff`,+0xc... |
| `0x100100bc` | `(0x20, 0x14, 0x1a)` | `0x4394` | 5 | +8=`0xffffffff`,+0xc=2 |
| `0x1000fc45` | `(0x21, 0x15, 0x1b)` | `0x42cc` | 3 | flags\|8 |

> **The network layers subscribe to periodic notification `0x635ee3c3` via `FUN_10025825` (add-subscriber into the message/notification server `FUN_10021b37`).** This is the callback-registration site CLUSTER1 could not locate. The 7 variants map to the 6 networks (netType 1..6) plus one duplicate netType-4 (`0x1000f79c` and `0x1000e9e7`, i.e. two road/highway variants). `[CONFIRMED @ 0x635ee3c3 literal in all 7 bodies]`

`[UNCERTAIN]` whether `0x635ee3c3` is specifically the SIMCITY sim *tick* vs a rebuild/notify message — the producer of that message id is in another module (SIMCITY). Missing evidence: the emitter of `0x635ee3c3` and the SIMCITY bucket-list registration. What IS confirmed is that this is the per-layer periodic-notification subscription.

### 2. Two new serialiser pairs (resolves task item 3) `[CONFIRMED]`

- **`FUN_10024412` @ 0x10024412 — object SAVE writer.** Queries a sub-object via `FUN_10022006(this)->(IID=0x80199683,&obj)`, writes its 3 header values (`+0x14/+0x1c/+0x24`) then ~11 of `this`'s own getters (`+0x88/+0x54/+0x60/+0xd4/+0xd8/+0xdc/+0x58/+0xf8/+0x30/+0x6c/+0x74`) plus a coord (`this+0xb8`, each `>>8`) and a triple (`this+0xb0`) to the stream (`param_2` vtable `+0x88` u32, `+0x68`, `+0x78`) `[CONFIRMED @ 0x10024412]`.
- **`FUN_10024279` @ 0x10024279 — object LOAD deserialiser** (mirror). Reads via stream `param_2` (`+0x38` u32, `+0x18` byte, `+0x28`) and applies to `this` setters `+0x18`(triple), `+0x104`, `+0xfc`(bool), `+0x34`, `+0x70`(bool), `+0x78`(bool), `+0xec`(coord `<<8`), `+0x108`(triple) `[CONFIRMED @ 0x10024279]`.
- **`FUN_10025f0d` @ 0x10025f0d — record-stream reader ctor.** Installs vtable `PTR_FUN_1002d244`, reads a 3-dword header via `param_1+0x260` into `this+0x14/+0x18/+0x1c`, opens a `0x14` sub-stream (`FUN_1002639b`), and validates a **magic sentinel `0xDEADBEEF`** at `this+8` (`-0x21524111`); on mismatch resets, stamps `0xDEADBEEF`, and retries with a second sub-stream `[CONFIRMED @ 0x10025f0d]`. This is the read-side counterpart CLUSTER1 saw invoked by the layer loader `FUN_100130e9`.

> **New raw constants: record-stream magic `0xDEADBEEF`; save sub-object IID `0x80199683`.**

### 3. Rule-file token parser + the rule-record binary format `[CONFIRMED]`

- **`FUN_10022676` @ 0x10022676 — Simple/Complex rules token parser (9-state machine).** Called per `strtok` token; `isdigit` gate then `switch(this+0x10)` states 0..8. State 0 reads a record-type selector (0..5 → next state 1/2/3/4/6/7). States 5 & 8 build a **6-byte neighbor record `{ id = atoi>>8 @+0, byte @+4 = dir/orient, byte @+5 = atoi&0xff }`** and push it via `FUN_100229e8`; when the second group's count (`this+0x28`) reaches `this+0x1c` the whole rule is finalized (`FUN_10022a56`/`FUN_10022a7e`) into a vector of **0x18-byte rule entries**. Default orient `0xff → 0x1f` remap `[CONFIRMED @ 0x10022676]`.

> This confirms the on-disk rules format: rule entry stride **`0x18`** bytes, containing two lists of **6-byte** `{id,dir,state}` sub-records — the same 6-byte record consumed by the commit path `FUN_100165d8` and neighbor collector `FUN_10019768` (CLUSTER1).

### 4. Rule-engine leaves (fill in FUN_1001547b's callees from CLUSTER1)

- **`FUN_10016a25` @ 0x10016a25 — region match collector.** Builds a box around a coord (`FUN_10016c99`/`FUN_1000aa9a` scale 1 or 2 by `param_3 & 0x10/&2`, transform via `this+0x50`), clips to map dims (`this+0x5c`,`this+0x60` `>>8`), iterates 4 sub-rectangles calling `layer+0x7c(x,y,&piece)` → `handler+0xc(piece)` → `piece+0xb8(&coord)` → `FUN_10004136(outlist,coord)`. Gathers all handler-matching tiles near a coord into `param_5` `[CONFIRMED @ 0x10016a25]`.
- **`FUN_100167d4` @ 0x100167d4 — rule-driven tile replace.** Matches handlers `param_3/param_4+0xc`, tile-id switch (`0x49→4, 0xe/0xf→3, 0x1d, 0x2c→2, 0x5c→3, 0x2bc4→1, 0x3acb→5`), indexes a **piece-selection matrix `DAT_100318ac`** at `(row + col*6)*4`, creates the oriented piece via GZCLSID **`0xc14f8955`** and replaces the tile (`layer+0x48` remove, `layer+0x3c` place) `[CONFIRMED @ 0x100167d4]`.
- **`FUN_100165d8` @ 0x100165d8 — commit tile-change records.** Iterates the 6-byte record list `param_3`, `FUN_1002205c` decodes the dir byte to `dx,dy`, computes target coord; `id==0` → remove existing piece, else create via `0xc14f8955` + set height (`this[0xc]+0x4c`) + coord (`+0xec`) + place (`+0x3c`); on failure re-checks existing piece against handlers `param_4/param_5` `[CONFIRMED @ 0x100165d8]`.
- **`FUN_100151f1` @ 0x100151f1 — reapply tiling rules over a region for selected networks.** `param_2` flag byte selects networks: bits 1|2 → handlers `DAT_100323c4`(net 4)+`DAT_100323c0`(net 1) on `this+0x3c`; `&4` → `DAT_100323c8`(net 2); `&0x20` → `DAT_100323d4`(net 3); `&8` → `DAT_100323d0`(net 5) on `this+0x40`; `&0x10` → `DAT_100323cc`(net 6) on `this+0x44`. Each pairs `FUN_10016a25`(collect) + `FUN_1001547b`(evaluate) `[CONFIRMED @ 0x100151f1]`.

### 5. Graph-connectivity primitives (partial answer to task item 2)

- **`FUN_100090f4` @ 0x100090f4 — connect a piece to adjacent tiles in up to 6 directions.** Reads the piece's adjacency flags (`piece+0x48`) and maps flag-bit → direction: `0x8000→1, 0x10000→4, 0x20000→2, 0x40000→6, 0x400000→3, 0x800000→5`. First **tests** each via the connection manager `this+0x48` vtable `+0x58(dir,coord)`, and if any succeed (gated by cost/permission id **`0x268`** via `this+0x140` when `param_3`), **commits** via `+0x54(dir,coord)` `[CONFIRMED @ 0x100090f4]`.
- **`FUN_1000986f` @ 0x1000986f — validate a network connection at a tile.** Over 4 neighbor directions and the 3 sub-layers (`this+0x3c/+0x40/+0x44`), fetches the piece (`+0x78`), queries the **net-connect interface `0x41658d28`** (`+0x30` value), and validates via `this+0x14c` (compat) + `FUN_1001a7f7`. Returns validity `[CONFIRMED @ 0x1000986f]`.

The net-connect interface `0x41658d28` and its `+0x30` accessor are the graph edges. **No path traversal / BFS / commute-cost walk was present in this slice** (see Not-determined).

## Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100151f1,net-tiling-eval,C2,sc3_ntwrk_reapply_region_rules,"param_2 flag byte selects nets; handlers DAT_100323c0/c4/c8/cc/d0/d4 on this+0x3c/+0x40/+0x44; FUN_10016a25 collect + FUN_1001547b eval per net [CONFIRMED @ 0x100151f1]"
0x1000938b,net-build,C2,sc3_ntwrk_decompose_run_segments,"walks node ring (local_14=*list), breaks poly-line into collinear runs via (short) delta compare, emits each segment via this+0x110(start,end,...,param_3); param_3==4 highway special; FUN_10016d69 per-node test; count->*param_5 [CONFIRMED @ 0x1000938b]"
0x1000986f,net-build,C2,sc3_ntwrk_validate_tile_placement,"4 neighbor dirs x 3 sub-layers (+0x3c/+0x40/+0x44 +0x78 get piece); iface 0x41658d28 (+0x30 value); compat this+0x14c + FUN_1001a7f7; returns validity char [CONFIRMED @ 0x1000986f]"
0x10016a25,net-tiling-eval,C2,sc3_ntwrk_collect_region_matches,"box around coord (FUN_10016c99/FUN_1000aa9a scale by param_3&0x10/&2, transform this+0x50); clip to this+0x5c/+0x60; 4 sub-rects; layer+0x7c get piece, handler+0xc match, piece+0xb8 coord, FUN_10004136 append to param_5 [CONFIRMED @ 0x10016a25]"
0x10009613,net-build,C2,sc3_ntwrk_place_tile_with_rebuild,"same validate loop as FUN_1000986f then if valid FUN_1001a581 place + 4-neighbor rebuild via this+0x34/+0x3c; piece state==5 test +0x74 -> +0x48 rebuild [CONFIRMED @ 0x10009613]"
0x100167d4,net-tiling-eval,C2,sc3_ntwrk_apply_rule_replace_tile,"rule-driven tile replace; handlers param_3/param_4 +0xc; tile-id switch 0x49/0xe/0xf/0x1d/0x2c/0x5c/0x2bc4/0x3acb; matrix DAT_100318ac at (r+c*6)*4; create piece GZCLSID 0xc14f8955; layer +0x48/+0x3c [CONFIRMED @ 0x100167d4]"
0x100086c8,net-build,C2,sc3_ntwrk_rebuild_rect_region,"rect between two pts (FUN_10016ccd validate); grid this[0xc] +0x100 lock/+0x120 commit; per-tile +0x144 test then 4 diag neighbors FUN_10008900 coord + FUN_10007d0d set-contains + this+0x114 action [CONFIRMED @ 0x100086c8]"
0x100251aa,config,C2,sc3_ntwrk_write_config,"property WRITER (mirror of FUN_10024e10 reader); keys DAT_1002cee0..DAT_1002cf78 via param_1 vtable +0x58/+0x6c/+0x50; reads this+0x04..0x114; skips defaults incl 0x57a at this+0x120 [CONFIRMED @ 0x100251aa]"
0x10006508,ui-panel,C2,sc3_ntwrk_hud_message_proc,"build-tool window msg proc; 0xa2bf8ace->FUN_10006727 build HUD, 0xa2bf8ad0->default size {0x80,0x60,0x180,0xfa}, 0xa2bf8ad1->layout child wins by id 0x12340000/1/10 via +0x78/+0xcc; this+0x2c==2 alt layout; color +0xc8(0x41,0x27,0xeb,0x72) [CONFIRMED @ 0x10006508]"
0x100165d8,net-tiling-eval,C2,sc3_ntwrk_commit_tile_changes,"iterates 6-byte records {id,dir,state}; FUN_1002205c decode dir->dx,dy; id==0 remove else create GZCLSID 0xc14f8955 + set height this[0xc]+0x4c + coord +0xec + place +0x3c; failure re-check handlers param_4/param_5 [CONFIRMED @ 0x100165d8]"
0x10025f0d,serialization,C2,sc3_ntwrk_record_reader_ctor,"stream-reader ctor vtable PTR_FUN_1002d244; header 3 dwords via param_1+0x260 -> this+0x14/+0x18/+0x1c; sub-stream FUN_1002639b(0x14); validates magic 0xDEADBEEF at this+8, retries on mismatch [CONFIRMED @ 0x10025f0d]"
0x1000f79c,init-registration,C2,sc3_ntwrk_register_layer_net4a,"IID 0xa1c085db triple (2,0,0); factory resource 0x3e81; handler+0x10(...,netType=4,...); subscribes obj to msg 0x635ee3c3 via FUN_10025825/FUN_10021b37 [CONFIRMED @ 0x1000f79c]"
0x10022676,tiling-parse,C2,sc3_ntwrk_parse_rule_token,"9-state per-token parser for Simple/Complex rules; builds 6-byte records {id>>8,dir,state} via FUN_100229e8; 0x18-byte rule entries via FUN_10022a7e; 0xff->0x1f default orient [CONFIRMED @ 0x10022676]"
0x1000e9e7,init-registration,C2,sc3_ntwrk_register_layer_net4b,"IID triple (0x1d,0x11,0x17); factory 0x3e81; netType=4; subscribes msg 0x635ee3c3 [CONFIRMED @ 0x1000e9e7]"
0x1000e537,init-registration,C2,sc3_ntwrk_register_layer_net1,"IID triple (0x1c,0x10,0x16); factory 0x3e80(16000); netType=1; subscribes msg 0x635ee3c3 [CONFIRMED @ 0x1000e537]"
0x1000ee4b,init-registration,C2,sc3_ntwrk_register_layer_net2,"IID triple (0x1e,0x12,0x18); factory 0x4268(17000); netType=2; subscribes msg 0x635ee3c3 [CONFIRMED @ 0x1000ee4b]"
0x10024412,serialization,C2,sc3_ntwrk_serialize_object_state,"SAVE writer; sub-obj via FUN_10022006 IID 0x80199683 (+0x14/+0x1c/+0x24); writes ~11 this getters + coord this+0xb8(>>8) + triple this+0xb0 to stream param_2 +0x88/+0x68/+0x78 [CONFIRMED @ 0x10024412]"
0x1000c86f,net-load,C2,sc3_ntwrk_load_piece_props,"reads exemplar props keys 0x6355941d/e/f/0x63559420/21/22 via param_2+0x80; packs coord into this+0x10 (11+11+8 bits) + flags into this+0xc/this+0x14; validate this[-1]+0x10 [CONFIRMED @ 0x1000c86f]"
0x1000fc45,init-registration,C2,sc3_ntwrk_register_layer_net3,"IID triple (0x21,0x15,0x1b); factory 0x42cc; netType=3; msg flags|8; subscribes msg 0x635ee3c3 [CONFIRMED @ 0x1000fc45]"
0x100100bc,init-registration,C2,sc3_ntwrk_register_layer_net5,"IID triple (0x20,0x14,0x1a); svc via +0x120; factory 0x4394; netType=5; msg +8=0xffffffff,+0xc=2; subscribes msg 0x635ee3c3 [CONFIRMED @ 0x100100bc]"
0x10025c93,ui-tool,C2,sc3_ntwrk_tool_drag_handler,"interactive build-tool click/drag; this+0xc+0x8c hit-test -> tile coord; FUN_10007d0d region-contains; 1st click stores this+0x40/44/48, 2nd builds via this+0x54(pt1,pt2,&out); wraps FUN_1002595f begin/FUN_1002596b commit [CONFIRMED @ 0x10025c93]"
0x1000f2c7,init-registration,C2,sc3_ntwrk_register_layer_net6,"IID triple (0x1f,0x13,0x19); svc via +0x124; factory 0x43f8; netType=6; msg +8=0xffffffff,+0xc=1; subscribes msg 0x635ee3c3 [CONFIRMED @ 0x1000f2c7]"
0x100090f4,net-graph,C2,sc3_ntwrk_connect_adjacent_dirs,"connect piece to neighbors; adjacency flags piece+0x48 -> dir map 0x8000=1/0x10000=4/0x20000=2/0x40000=6/0x400000=3/0x800000=5; test this+0x48+0x58, commit +0x54; cost/permit id 0x268 via this+0x140 [CONFIRMED @ 0x100090f4]"
0x10024279,serialization,C2,sc3_ntwrk_deserialize_object_state,"LOAD reader; stream param_2 +0x38 u32/+0x18 byte/+0x28; applies this setters +0x18/+0x104/+0xfc/+0x34/+0x70/+0x78/+0xec(coord<<8)/+0x108 [CONFIRMED @ 0x10024279]"
0x10012dff,serialization,C2,sc3_ntwrk_layer_save,"layer SAVE writer; save GROUP 0x2147c2dd, TYPE 0x206c6e7c, 4 instances (already CONFIRMED in SIMNTWRK_CLUSTER1 — not re-derived) [CONFIRMED @ 0x10012dff]"
```

## Notable data / constants surfaced (raw)

- **Periodic notification message id `0x635ee3c3`** — subscribed to by all 7 layer-registration functions `[CONFIRMED]`.
- **Sub-layer acquisition IID `0xa1c085db`** (with per-network index triples `(2,0,0)`,`(0x1c,0x10,0x16)`,`(0x1d,0x11,0x17)`,`(0x1e,0x12,0x18)`,`(0x1f,0x13,0x19)`,`(0x20,0x14,0x1a)`,`(0x21,0x15,0x1b)`) `[CONFIRMED]`.
- **Simulator factory resource ids**: `0x3e80`(16000), `0x3e81`, `0x4268`(17000), `0x42cc`, `0x4394`, `0x43f8` — one per layer registration `[CONFIRMED]`.
- **Record-stream magic `0xDEADBEEF`** and save sub-object IID **`0x80199683`** `[CONFIRMED @ 0x10025f0d, 0x10024412]`.
- **Net-connect interface `0x41658d28`** (matches CLUSTER1) — piece connectivity edges `[CONFIRMED @ 0x1000986f]`.
- **Piece-selection matrix `DAT_100318ac`** (row + col*6, 4-byte cells) used by the rule-replace path `[CONFIRMED @ 0x100167d4]`.
- **Network-piece exemplar property keys `0x6355941d`, `0x6355941e`, `0x6355941f`, `0x63559420`, `0x63559421`, `0x63559422`** `[CONFIRMED @ 0x1000c86f]`.
- **Piece-create GZCLSID `0xc14f8955`** (same as CLUSTER1 legacy importer/commit) `[CONFIRMED @ 0x100167d4, 0x100165d8]`.
- **HUD message ids** `0xa2bf8ace`(build HUD), `0xa2bf8ad0`(default size `{0x80,0x60,0x180,0xfa}` = 128,96,384,250), `0xa2bf8ad1`(layout); child-window ids `0x12340000`/`0x12340001`/`0x12340010`; button color `(0x41,0x27,0xeb,0x72)` `[CONFIRMED @ 0x10006508]`.
- **Cost/permission id `0x268`** for making connections `[CONFIRMED @ 0x100090f4]`.
- **Rule-file binary format**: `0x18`-byte rule entries, `6`-byte `{id,dir,state}` sub-records, default orientation `0x1f` `[CONFIRMED @ 0x10022676]`.
- **Packed piece coord** at `this+0x10`: x = 11 bits, y = 11 bits, z = 8 bits, top 2 bits flags `[CONFIRMED @ 0x1000c86f]`.

## Not determined (with the exact missing evidence)

- **Is `0x635ee3c3` the sim tick, or a rebuild/notify message?** The subscription is confirmed; the *producer* of `0x635ee3c3` is not in SIMNTWRK. *Needs:* grep for `0x635ee3c3` as an emitted message in SIMCITY / the sim-scheduler module, or the message-id → name table.
- **Network graph *traversal* for pathfinding / commute, and SimTransit consumption (task item 2): NOT in this slice.** This slice has the connectivity primitives (`FUN_100090f4` connect, `FUN_1000986f` validate, iface `0x41658d28`) but no BFS/Dijkstra/flood traversal and no SimTransit-facing export. *Needs:* an xref sweep on the net-connect iface `0x41658d28` consumers and on `SIMTRANS`/`SIMTRAFC` module boundaries; the large unread functions from `SIMNTWRK.md §7` (`FUN_10002693`, `FUN_1000488d`, `FUN_1000122a`, `FUN_1000abde`) are build-side, not traversal — the traversal likely lives in the transit module, not here.
- **Which physical network each `netType`/resource-id/IID-triple denotes** (roads vs rails vs highway vs subway vs power vs pipe). The 7 registrations give netType 1..6 (+ a duplicate 4), but the netType→name binding is not string-labelled in the module. *Needs:* the GZCLSID/resource-id → name table in `SYS.PAK`/exemplars, or an `[iOS-HINT]` match against `goRoadLayer`/`goRailLayer`/etc. in `re/ghidra_export_ios/`.
- **Raw bytes of `DAT_100318ac`** (piece-selection matrix) — outside the decompiled export. *Needs:* a data-section dump / live Ghidra read at `0x100318ac`.
- **Meaning of the resource ids `0x3e80/0x3e81/0x4268/0x42cc/0x4394/0x43f8`** passed to the simulator factory (`+0x54`). Confirmed as factory keys by usage; the id→object mapping is in the factory (`FUN_10021b24()+0x15c`), not in this slice. *Needs:* read the factory's dispatch.

---

## Orchestrator verification (2026-08-16) — `0x635ee3c3` is NOT the sim tick

CLUSTER2 correctly refused to call `0x635ee3c3` the tick and named the evidence needed: find its
producer. That sweep was run locally over all 30 module exports.

**Result: 23 sites across 9 modules — SCENARIO, SIMADV, SIMDIRT, SIMGEOM (6), SIMNTWRK (7),
SIMRCI, SIMSPR (4), SIMUI — and NONE in `SIMCITY.DLL`** `[CONFIRMED, full-export grep]`.

`SIMCITY.DLL` is the tick driver: it owns the clock (`0x10009b35`, 1,440 ticks/day) and the
bucket walk (`0x1000a915` / `0x1000a9b1` / `0x1000aa4d`). A per-tick message it never names
cannot be the tick. **The tick hypothesis is closed, negative.**

What it looks like instead — SIMUI `0x1004773c` `[CONFIRMED @0x1004773c]`:

```c
local_18 = 0x635ee3c3;   local_c = 1;   local_10 = uVar3;
piVar1 = (int *)FUN_1008500d();                       // the message server
iVar4 = (**(code **)(*piVar1 + 0x10))(&local_18, 0);  // 4-dword struct, led by the id
```

That is the shape of a **post**, not a subscription: a `{id, ?, payload, flag}` record handed to
the server. SIMSPR `0x10044471` instead calls `vt+0x14(obj, 0x635ee3c3)` — a different arity, so
the two are not the same operation.

`[UNCERTAIN]` which of `vt+0x10` / `vt+0x14` is post and which is subscribe, and therefore which
module is the true producer. Missing evidence: the message-server class itself (the object
`FUN_1008500d` returns) has not been read. Resolving it would name the direction for **every**
`0x635ee3c3` site at once, and the same server is used across all 9 modules — so it is worth one
targeted read rather than nine local guesses.
