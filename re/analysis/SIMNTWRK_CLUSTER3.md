## SIMNTWRK.DLL — C0 slice (15 functions, toolkit-necessary set)

All addresses are SIMNTWRK.DLL VAs (image base `0x10000000`). Builds on `re/analysis/SIMNTWRK.md`; the director/registration table there is not re-derived.

### 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1001396b,gzcom-query,C2,sc3_ntwrk_query_interface,"IID dispatch: returns this for IIDs 1/0x58d/0x4147c2fb/0x206c6e7c/0x81c0cb7c, this+4 for 0x5e4, this+8 for 0x6182ea06, this+0xc for 0x81c0cb7b; else *param_2=0/false; AddRef via this[+4]() [CONFIRMED @ 0x1001396b]"
0x1000d84f,serialize,C2,sc3_ntwrk_piece_load,"calls base FUN_10024e10(this,param_1); reads 4 keyed props via stream[+0x38](key,dest,0) into this+0x130/+0x124/+0x128/+0x12c; zeroes field on read-fail; keys DAT_1002bc18/20/28/30 [CONFIRMED @ 0x1000d84f]; save-side sibling FUN_1000d8f1 uses same keys via [+0x58]"
0x10013589,gzcom-lifecycle,C2,sc3_ntwrk_register_notifications,"FUN_1001ef65 svc; [+0x14](param_1,id) x8 with ids 0x826cb9b6,0x426cb9b3,0xc2bdf178,0xd2bdf178,0x2bdf19f,0x12bdf19f,0x637c0dab,0x37c0dbd; then this+0x2c vtable [0x11c]/[0x120]/[0x124] -> [+0x34](param_1) [CONFIRMED @ 0x10013589]"
0x10013497,gzcom-lifecycle,C2,sc3_ntwrk_unregister_notifications,"FUN_1001ef65 svc; [+0x18](param_1,id) x8 (SAME 8 ids as 0x10013589); releases 8 sub-objs via [+8]() at param_1+0x3c/0x40/0x44/0x30/0x34/0x38/0x48/0x2c, nulling each [CONFIRMED @ 0x10013497]"
0x10025825,network-tool,C2,sc3_ntwrk_tool_ctor_attach,"stores FUN_1001efbd()@this+4, param_1@this+8 (AddRef [+4]); sub-objs param_1[0x94]->this+0xc, [0x8c]->this+0x10, [0x15c]->this+0x14; FUN_10021b24 layer dims [0xd0]/[0xcc] -> this+0x28=(w-1)*0x100, this+0x24=h*0x100-0x100; self[0](0x22b66d3d,&obj) QI; param_1[0x58]/[0x38](0,0x23)/[0x5c] [CONFIRMED @ 0x10025825]"
0x10006321,gzcom,C2,sc3_ntwrk_create_configure_service,"FUN_1001e4d8 svc; [+0xc](clsid=0xa2a79fd0,iid=0xa2a79fd1,&out) create; on ok out[+0x18](1,1)/(2,0)/(0x10,0)/(0x10000,1) config, out[+0x38](param_1); FUN_1001efbd[+0x9c](0,cmd) & [+0x28](cmd); release [+8] [CONFIRMED @ 0x10006321]"
0x10020a52,file-io,C2,sc3_ntwrk_move_file,"one-time LoadLibraryA(KERNEL32.DLL)+GetProcAddress(MoveFileExA)@DAT_100324d4, guard DAT_100324d0; if present MoveFileExA(src,dst,flag 2) with MoveFileA fallback; else MoveFileA(src,dst); paths via obj[+0x14]() [CONFIRMED @ 0x10020a52]"
0x10014807,network-tool,C2,sc3_ntwrk_tool_reset_query,"switch(param_2) 1->ECX[0x78],2->0x80,3->0x8c,4->0x7c,5->0x88,6->0x84,8->0x90; fills 1280 triples with 0x7fffffff sentinel; this[+0x14](); this[+0xc](buf,0x500,...) [CONFIRMED @ 0x10014807]"
0x1000e72a,network-build,C2,sc3_ntwrk_buildop_slot94,"FUN_1000aa2e coord + 0x7fffffff sentinel; if !this[0x38]&&!this[0x39]: this[0x110][+0x94](param_1,&f,coord,&sent), on ok result=0xe; elif this[0x39]: result=0x20; else result=0x1e; then FUN_1000104a[+0x7c] obj id 0xfa2, inner[+0x14](1,result,0,0,0) [CONFIRMED @ 0x1000e72a]"
0x1000ebe9,network-build,C2,sc3_ntwrk_buildop_slot98,"clone of 0x1000e72a; layer vtable slot +0x98; success result=0xe; flag paths 0x20/0x1e [CONFIRMED @ 0x1000ebe9]"
0x1000f041,network-build,C2,sc3_ntwrk_buildop_slot9c,"clone; layer slot +0x9c; success result=0x33; flag paths 0x20/0x1e [CONFIRMED @ 0x1000f041]"
0x1000f4ae,network-build,C2,sc3_ntwrk_buildop_slota0,"clone; layer slot +0xa0; success result=0x35; flag paths 0x20/0x1e [CONFIRMED @ 0x1000f4ae]"
0x100102a3,network-build,C2,sc3_ntwrk_buildop_slota4,"clone; layer slot +0xa4; success result=0x32; flag paths 0x20/0x1e [CONFIRMED @ 0x100102a3]"
0x1000fe36,network-build,C2,sc3_ntwrk_buildop_slota8,"clone; layer slot +0xa8; success result=0x10; flag paths 0x20/0x1e [CONFIRMED @ 0x1000fe36]"
0x1000f9b7,network-build,C2,sc3_ntwrk_buildop_slotac,"clone; layer slot +0xac; success result=0xe; flag paths 0x20/0x1e [CONFIRMED @ 0x1000f9b7]"
```

15 of 15 read, all C2 (bodies read, callees identified, mechanically described, named). None claimed above C2.

---

### 2. Notable findings (structural)

**A. GZCOM `QueryInterface` — `FUN_1001396b` [CONFIRMED @ 0x1001396b].** A textbook GZCOM interface-cast: dispatches on the requested IID (`param_1`) and hands back a pointer to a sub-object embedded in `this`, then `AddRef`s via `this[+4]()`. The IID→offset map:

| IID | returns | note |
|---|---|---|
| `0x00000001`, `0x0000058d`, `0x4147c2fb`, `0x206c6e7c`, `0x81c0cb7c` | `this` (self) | `1` = GZCOM `cIGZUnknown` |
| `0x000005e4` | `this+4` | |
| `0x6182ea06` | `this+8` | |
| `0x81c0cb7b` | `this+0xc` | |
| any other | `*param_2=0`, returns false | |

Multi-interface object with three composed sub-interfaces at `+4/+8/+0xc`. These IIDs are high-value keys for identifying this class against SIMNTWRK's two registered GZCLSIDs.

**B. Save/Load serialization pair — `FUN_1000d84f` (load, in slice) + `FUN_1000d8f1` (save, sibling).** Confirmed pair persisting the SAME 4 keyed dword properties (keys `DAT_1002bc18/20/28/30`, held in `.rdata`, not ASCII in `strings.csv`) to/from object fields `this+0x130, +0x124, +0x128, +0x12c`:
- Load: `base FUN_10024e10(this,param_1)` then `stream[+0x38](key, dest, 0)`; missing key → field zeroed [CONFIRMED @ 0x1000d84f].
- Save: `base FUN_100251aa(this,param_1)` then `stream[+0x58](key, src, 0)`, short-circuit chained [CONFIRMED @ 0x1000d8f1].

So `[+0x38]` = read-keyed-property, `[+0x58]` = write-keyed-property on the GZCOM property-stream. This is the persistence interface for one network-piece class.

**C. Notification subscribe/unsubscribe pair with an 8-entry message table — `FUN_10013589` (register) / `FUN_10013497` (unregister).** Both drive the `FUN_1001ef65` service; register uses vtable `[+0x14]`, unregister uses `[+0x18]`, over an identical fixed list of 8 message ids:

```
0x826cb9b6  0x426cb9b3  0xc2bdf178  0xd2bdf178
0x2bdf19f   0x12bdf19f  0x637c0dab  0x37c0dbd
```

This is the module's runtime message-subscription table (the notifications SIMNTWRK's director/tool listens to). Register additionally spins up 3 child services (`this+0x2c` vtable slots `[0x11c]/[0x120]/[0x124]` → `[+0x34](param_1)`); unregister releases 8 sub-objects (`param_1+0x3c/0x40/0x44/0x30/0x34/0x38/0x48/0x2c`). Highest-value find in the slice — a dispatch/subscription table with a clean paired teardown.

**D. Network-build op family — 7 clones (`FUN_1000e72a` … `FUN_100102a3`).** One handler per operation, each targeting a distinct consecutive vtable slot on the network-layer object at `this+0x110`:

| function | layer slot | success result | blocked results |
|---|---|---|---|
| `1000e72a` | `+0x94` | `0x0e` | `0x20` / `0x1e` |
| `1000ebe9` | `+0x98` | `0x0e` | `0x20` / `0x1e` |
| `1000f041` | `+0x9c` | `0x33` | `0x20` / `0x1e` |
| `1000f4ae` | `+0xa0` | `0x35` | `0x20` / `0x1e` |
| `100102a3` | `+0xa4` | `0x32` | `0x20` / `0x1e` |
| `1000fe36` | `+0xa8` | `0x10` | `0x20` / `0x1e` |
| `1000f9b7` | `+0xac` | `0x0e` | `0x20` / `0x1e` |

Each builds a coordinate record (`FUN_1000aa2e` + the `0x7fffffff` triple sentinel = "no coordinate"), and — when neither guard flag `this+0x38`/`this+0x39` is set — calls the layer slot `(param_1, &flag, coord, &sentinel)`. On success it fetches service `FUN_1000104a()[+0x7c]`, instantiates object id **`0xfa2`** (4002), and posts the result code via inner `[+0x14](1, result, 0, 0, 0)`. Guard flags short-circuit to shared status codes `0x1e`/`0x20`. The seven `+0x94..+0xac` slots and per-op result codes form a compact action→result-code table (the 6 line networks + diagonal, matching the module's 7 network families). `0x1e`/`0x20` are the shared "blocked/disabled" codes; `0xe/0x10/0x32/0x33/0x35` are per-op success codes.

**E. Tile→world coordinate scale `0x100` — `FUN_10025825` [CONFIRMED @ 0x10025825].** A network-tool constructor computes bounds from layer dimensions (`FUN_10021b24` layer, `[+0xd0]`=w, `[+0xcc]`=h): `this+0x28 = (w-1)*0x100`, `this+0x24 = h*0x100 - 0x100`. **256 world-units per tile.** It also Queries IID `0x22b66d3d` (`self[0](0x22b66d3d,&out)`) and reuses layer slots `[0x94]/[0x8c]` (same slots as the build family and `FUN_10014807` — same layer type at `this+0x110`).

**F. Coordinate/cost query buffer — `FUN_10014807`.** Dispatches on `param_2` (1-6, 8) to one of 7 layer vtable slots (`0x78/0x80/0x8c/0x7c/0x88/0x84/0x90`), then initializes a **1280-entry (`0x500`) array of `(x,y,z)`/`(x,y,cost)` triples to `0x7fffffff`** (same INT_MAX sentinel as the build family) and dispatches via `this[+0xc](buf, 0x500, …)`. A batched network-tool query over a fixed 1280-slot buffer.

**G. Atomic file move — `FUN_10020a52` [CONFIRMED @ 0x10020a52].** Lazily resolves `MoveFileExA` from `KERNEL32.DLL` (one-time, guarded by `DAT_100324d0`, cached at `DAT_100324d4`) and calls it with flag `2` (`MOVEFILE_COPY_ALLOWED`), falling back to `MoveFileA`. A save-file rename/commit helper — pairs with the tiling-file I/O already mapped in SIMNTWRK.md §3.6.

**H. Dynamic GZCOM create+configure — `FUN_10006321`.** Creates an object via `FUN_1001e4d8()[+0xc](clsid 0xa2a79fd0, iid 0xa2a79fd1, &out)`, configures it with four `[+0x18](key,val)` calls (`(1,1) (2,0) (0x10,0) (0x10000,1)`), binds `param_1` via `[+0x38]`, drives `FUN_1001efbd()[+0x9c](0,cmd)` / `[+0x28](cmd)`, then releases. `0xa2a79fd0`/`0xa2a79fd1` are a new CLSID/IID pair for this module's catalogue.

---

### 3. Not determined (missing evidence)

- **Meaning of the 8 notification ids** (`0x826cb9b6` … `0x37c0dbd`) in findings **C**. Confirmed as a subscription table, but the semantic of each id needs the GZCOM message-id registry (not in this module's export) or a producer that posts them.
- **Object id `0xfa2` (4002)** instantiated by the build family (findings **D**) — the class/service behind `FUN_1000104a()[+0x7c](0xfa2,…)` is not resolvable from the slice; needs the GZ factory/message catalogue.
- **The result codes `0x0e/0x10/0x1e/0x20/0x32/0x33/0x35`** (findings **D**) are posted via `[+0x14](1, code, …)` but the consumer (UI-cursor state, sound cue, or status string id) is outside the slice. Mechanically confirmed as literals; meaning undetermined.
- **The 4 serialization property keys** `DAT_1002bc18/20/28/30` (finding **B**) are dword keys in `.rdata`, absent from `strings.csv`; their raw values need a live data-section read of `0x1002bc18`.
- **CLSID/IID pairs** `0x22b66d3d` (finding **E**), `0xa2a79fd0`/`0xa2a79fd1` (finding **H**), and the QueryInterface IIDs (finding **A**) are confirmed as literals but map to unnamed classes — resolution needs the GZCLSID→name table (`SYS.PAK`/`.ini`) or an `[iOS-HINT]` cross-check not performed here.
- **`this+0x110` layer type**: the same object is used by findings **D**, **E**, **F** (slots `0x78`–`0xac`), but its class identity (one of the module's 2 GZCLSIDs, or an external layer) is not determined from the slice.

No function in the slice was left unclassified.
