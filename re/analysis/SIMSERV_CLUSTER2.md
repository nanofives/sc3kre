# SIMSERV.DLL — toolkit-necessary C0 slice (25 functions)

## Headline finding: this slice is the module's **GZCOM persistence (save/load) family**

19 of the 25 functions are serialization. SIMSERV stores its fire/crime/police/flammability layer state through a GZCOM persist framework with a fixed record header and a matched reader/writer vtable convention. The whole family is now mechanically pinned:

**Persist record header** — every layer's save/load builds a 3-dword key `{0x206c6e7c, <GZCLSID>, 0}` and passes it to the persist provider:
- `0x206c6e7c` is both the header tag **and** the serializable-interface IID (it appears in every QueryInterface dispatcher, mapping to the object's serialize sub-pointer). `[CONFIRMED @ 0x100071d5:30, 0x10007a8d:23, 0x1000ca34:10, 0x1000b045:14]`
- second dword = the layer GZCLSID already in the map: crime `0x20a7ae7f`, fire `0xa0f42214`, police `0x00abf2ec`, flammability `0x61448030`. `[CONFIRMED @ 0x100071d5:31, 0x1000a619:28, 0x1000e581:28, 0x1000c7b3:29]`

**Provider handshake:** save path calls provider vtable **`+0x30`** to get an output object, load path calls **`+0x20`** to get an input object, then `QueryInterface(0x199627)` yields the actual stream, and vtable `+8`/`+0x24` release it. `[CONFIRMED @ 0x1000a619:31-33,89-92 / 0x1000a479:29-32,87-89]`

**Reader vs writer vtable slots** (consistent across all 8 layer methods + the generic record pair):

| op | writer slot | reader slot |
|---|---|---|
| int32 | `+0x88` | `+0x38` |
| byte/bool | `+0x68` | `+0x18` |
| short | `+0x78` | `+0x28` |
| block/struct | `+0x98` | `+0x48` |
| GUID/header | — | `+0x20` |

`[CONFIRMED @ 0x10017a42 (writer) vs 0x10017933 (reader), identical field offsets this+4/+8/+0xc/+0x10..+0x20/+0x24[]/+0x30..+0x38]`

**Reader open + integrity check:** `FUN_10018c2f` is the input-stream wrapper ctor. It reads 3 dwords from the source via vtable `+0x260`, allocates a `0x14`-byte helper (`FUN_100190bd`), and **validates a `0xDEADBEEF` signature** (`this+8 == -0x21524111`, i.e. `0x100000000 - 0x21524111 = 0xDEADBEEF`); on mismatch it writes `0xdeadbeef` back and tears down, retrying once. `[CONFIRMED @ 0x10018c2f:79,87]`

### The three save/load pairs (all reach their layer base by subtracting the factory offset)

| layer | SAVE | LOAD | base reached via | fields serialized |
|---|---|---|---|---|
| crime | `0x100073b0` | `0x100071d5` | `this-0x20` | scan pos `+0x2c/+0x30`, `+0x9c/+0xa0/+0xa4`, service `+0xa8`, then a global list `DAT_10024968`/count `DAT_1002496c` (node `[4]`,`[5]`,`+0x15`) `[CONFIRMED @ 0x100073b0:90-118]` |
| fire | `0x1000a619` | `0x1000a479` | scan obj `this+0x1c` | scan `+0x1c/+0x20/+0x24`, `this+0xa4`(bool)`/+0xa8..+0xbc` `[CONFIRMED @ 0x1000a479:49-77]` |
| police | `0x1000e581` | `0x1000e3e0` | scan obj `this+0x24` | scan `+0x3c/+0x40/+0x44`, `this+0x18`(bool)`/+0x1c/+0xbc..+0xcc` `[CONFIRMED @ 0x1000e3e0:50-78]` |
| flammability | `0x1000c8be` | `0x1000c7b3` | `this-0x14` | `this+0x2c/+0x30/+0x34/+0x38` (int) `+0x3c` (byte) `[CONFIRMED @ 0x1000c8be:45-64]` |

Both fire and police load paths **lazily construct the spread-scan object** if absent (`operator_new(0x48)`+`FUN_1000b565`+`FUN_1000b61d` for fire; `operator_new(0x58)`+`FUN_1000f829`+`FUN_1000f8d4` for police) — confirming `FUN_1000f829`/`FUN_1000f8d4` are the **police-side analogues** of the fire scan ctor/init already in the map. `[CONFIRMED @ 0x1000a479:36-47, 0x1000e3e0:37-48]`

### Version guard
`FUN_1000c7b3` (flammability load) rejects the record unless `local_30 < 2` — a **format version field checked against 2**. `[CONFIRMED @ 0x1000c7b3:36]`

### Coordinate bit-packing (save format detail)
`FUN_10014eb8` serializes a cell whose position is packed into one dword `this+0x10` as **x=bits[0:11], y=bits[11:22], z=bits[22:30], flags=bits[30:32]** (`&0x7ff, >>0xb&0x7ff, >>0x16&0xff, >>0x1e`). `[CONFIRMED @ 0x10014eb8:21,26]`

### Grid region 2× expansion (load)
`FUN_10007132` reads region id `0x200` cell-by-cell and blits each source cell into a **2×2 destination block** on the base grid (`this-0x20` vtable `+0x38`, dest coords `iVar1*2 / iVar1*2+1`). `[CONFIRMED @ 0x10007132:31-33]`

## Non-persistence finds

- **`FUN_1000f3bd` — jail inmate distribution / overcrowding (police).** Sums per-node capacity (`+0x14`→float) into `+0xc0` and population (`+0x18`) into `+0xc4`; `+0xc8 += +0xc4`; ratio = `+0xc8 / +0xc0` **clamped to `DAT_1002453c`**; redistributes inmates proportionally across the list (node vtable `+0x1c` setter). When there is **no capacity** it decays population by **95% (`*0x5f/100`)**. `[CONFIRMED @ 0x1000f3bd:20-33]` `DAT_1002453c` = an overcrowding-ratio ceiling (candidate `MaxJailOvercrowding`).
- **`FUN_1000ece1` — coverage grid repaint (police/crime).** Locks `this+0x7c`, sums station capacity (`this+0x18` list, node `+0x10`) into `this+0xb0`, then stamps two lists (`this+0x14` agents, `this+0x50` records) onto the base grid `this-0x1c` via `FUN_1000f557(base, &coord, byte, ushort, ushort)`. Second stamp uses tunables **`DAT_1002453a`(byte) + `DAT_1002453b`(ushort)**. `[CONFIRMED @ 0x1000ece1:46,59]` Parallel to the fire `0x1000adf5` recompute. `[UNCERTAIN]` whether police or crime — missing witness: an xref tying `this+0x7c/+0x50` to a named layer ctor.
- **`FUN_10007868` — format 3 numeric stats to localized display strings.** Gets a formatter service (`FUN_100132df` → vtable `+0x94`), reads three values from `param_1+0xc8` (getters `+0x24/+0x30/+0x3c`), formats each via `+0x40`, looks up a label string via `param_1+0xcc` `+0x14`, and stores into `param_1+0xc8` slots `+0x50(0..2)`. `[CONFIRMED @ 0x10007868:28-43]`
- **`FUN_100125cd` — readline over a byte stream.** Reads the stream at `this+0x28` in `0x28`(40)-byte chunks, scans for `\r`/`\n`, seeks back, and accumulates a std::string (`FUN_10002f32`). `[CONFIRMED @ 0x100125cd:47-90]`
- **`FUN_10014724` — atomic file rename.** One-shot `LoadLibraryA("KERNEL32.DLL")`+`GetProcAddress("MoveFileExA")` cached in `DAT_10024a74` (guard `DAT_10024a70`); calls `MoveFileExA(src, dst, flags=2)`, falling back to `MoveFileA`. Paths from param vtable `+0x14`. `[CONFIRMED @ 0x10014724:14-40]` This is the save-file commit (temp→final rename).

## QueryInterface dispatchers (three layers)
Each maps an IID to an interface sub-pointer at `this+offset`; common IIDs `0x206c6e7c` (serializable), `0x58d`, `0x5e4`, `0x6c6f42`, `0x81c0cb7b`/`0x81c0cb7c`. Layer-specific: crime adds `0x215b29c5`/`0x80a24318` `[CONFIRMED @ 0x10007a8d]`; flammability adds `0x2144802b`, returns fail on miss `[CONFIRMED @ 0x1000ca34]`; fire adds `0x215b29c5`/`0xa0f42240`/`0x81c0cb7b`/`0x81c0cb7c` `[CONFIRMED @ 0x1000b045]`. Miss falls through to base `FUN_10006251`.

---

## 1. Classification (CSV)

```csv
rva,subsystem,confidence,new_name,evidence
0x10018c2f,persistence,C2,sc3_persist_open_reader,"input-stream ctor: reads 3 dwords via src +0x260, alloc 0x14 helper FUN_100190bd, checks 0xDEADBEEF sig (this+8==-0x21524111) @0x10018c2f:37-87"
0x100073b0,crime-layer,C2,sc3_crime_save_layer,"persist {0x206c6e7c,0x20a7ae7f,0}; writer +0x88/+0x68/+0x98; writes +0x2c/+0x30/+0x9c/+0xa0/+0xa4, svc +0xa8, list DAT_10024968/DAT_1002496c @0x100073b0"
0x100071d5,crime-layer,C2,sc3_crime_load_layer,"persist {...,0x20a7ae7f}; reader via FUN_10018c2f; +0x18/+0x38/+0x48; base this-0x20; writes grid this+0x90 via FUN_10007f7e @0x100071d5"
0x1000a619,fire-layer,C2,sc3_fire_save_layer,"persist {0x206c6e7c,0xa0f42214,0}; provider +0x30, QI 0x199627; lazy scan obj (new 0x48/FUN_1000b565/FUN_1000b61d); writes scan +0x1c/+0x20/+0x24, this+0xa4..+0xbc @0x1000a619"
0x1000a479,fire-layer,C2,sc3_fire_load_layer,"persist {...,0xa0f42214}; provider +0x20, QI 0x199627; reader +0x18/+0x38; lazy scan obj; loads scan +0x1c/+0x20/+0x24, this+0xa4(bool)..+0xbc @0x1000a479"
0x1000e581,police-layer,C2,sc3_police_save_layer,"persist {0x206c6e7c,0xabf2ec,0}; lazy scan obj (new 0x58/FUN_1000f829/FUN_1000f8d4); writes scan +0x3c/+0x40/+0x44, this+0x18/+0x1c/+0xbc..+0xcc @0x1000e581"
0x1000e3e0,police-layer,C2,sc3_police_load_layer,"persist {...,0xabf2ec}; provider +0x20, QI 0x199627; reader +0x18/+0x38; lazy scan obj; loads scan +0x3c/+0x40/+0x44, this+0x18(bool)..+0xcc @0x1000e3e0"
0x1000c8be,flammability-layer,C2,sc3_flam_save_layer,"persist {0x206c6e7c,0x61448030,0}; writer via FUN_10018e4b; +0x88 x4 (this+0x2c/+0x30/+0x34/+0x38), +0x68 (this+0x3c) @0x1000c8be"
0x1000c7b3,flammability-layer,C2,sc3_flam_load_layer,"persist {...,0x61448030}; reader via FUN_10018c2f; version guard local_30<2; +0x38 x4 -> this+0x2c/+0x30/+0x34/+0x38, +0x18 -> this+0x3c @0x1000c7b3:36-61"
0x10015775,persistence,C2,sc3_persist_save_agent,"QI 0x80199683 for sub-obj (3 vals +0x14/+0x1c/+0x24); writes getters this+0x88/+0x54/+0x60/+0xd4../+0x74 via +0x88/+0x68; pos +0xb8 (>>8) via +0x88; +0xb0 3 floats via +0x78 @0x10015775"
0x100155dc,persistence,C2,sc3_persist_load_agent,"reader +0x38/+0x18/+0x28; sets this+0x104/+0xfc(bool)/+0x34/+0x70/+0x78; pos 3 ints<<8 -> this+0xec; 3 floats -> this+0x108 @0x100155dc"
0x10017a42,persistence,C2,sc3_persist_save_record,"writer +0x70(byte this+4)/+0x88(int +8)/+0x68(bool +0xc)/+0x98(+0x10/+0x18/+0x14/+0x1c/+0x20); count=(+0x28-+0x24)>>1, +0x78 ushort[]; +0x98 +0x30/+0x34/+0x38 @0x10017a42"
0x10017933,persistence,C2,sc3_persist_load_record,"reader +0x20(this+4)/+0x38(+8)/+0x18(bool +0xc)/+0x48(+0x10/+0x18/+0x14/+0x1c/+0x20); +0x38 count then +0x28 ushort[] this+0x24; +0x48 +0x30/+0x34/+0x38 @0x10017933"
0x1001854b,persistence,C2,sc3_persist_save_tables,"writer +0x88; three fixed arrays this+0x78[12], this+0xa0[10], this+0xc8[10] via FUN_10018737 accessor, then this+0x60 @0x1001854b"
0x10018480,persistence,C2,sc3_persist_load_tables,"reader +0x38; three arrays this+0x78[12]/+0xa0[10]/+0xc8[10] via FUN_10018737; this+0x60; on this+0x64!=0 calls FUN_10017e75(this-8) else vtable+0x48 @0x10018480"
0x10014eb8,persistence,C2,sc3_persist_save_cell,"writer typed slots +0x28/+0x2c/+0x30/+0x34/+0x38/+0x3c; packs this+0x10 as x(11)/y(11)/z(8)/flags(2); this+0xc bit flags via +0x3c @0x10014eb8:21-29"
0x10007132,persistence,C2,sc3_grid_load_region_2x,"reads region 0x200 (dims via +0x24, cells via +0x18) and 2x-expands each cell to a 2x2 block on base grid this-0x20 (+0x38) @0x10007132:22-38"
0x1000f3bd,police-jail,C2,sc3_police_distribute_inmates,"sum cap +0x14 -> +0xc0, pop +0x18 -> +0xc4; +0xc8+=+0xc4; ratio +0xc8/+0xc0 clamp DAT_1002453c; redistribute via node +0x1c; no-cap decay *0x5f/100 (95%) @0x1000f3bd:20-33"
0x1000ece1,police-crime-coverage,C2,sc3_svc_recompute_coverage,"lock this+0x7c; sum stations this+0x18 -> this+0xb0; stamp lists this+0x14 & this+0x50 onto base this-0x1c via FUN_1000f557 with DAT_1002453a/DAT_1002453b @0x1000ece1:46,59"
0x10007868,ui,C2,sc3_ui_format_stat_strings,"formatter svc FUN_100132df +0x94/+0x40; 3 getters param_1+0xc8 (+0x24/+0x30/+0x3c) -> labels param_1+0xcc +0x14 -> set +0x50(0..2) @0x10007868:28-43"
0x100125cd,io,C2,sc3_io_read_line,"reads stream this+0x28 in 0x28-byte chunks (+0x38), scans CR/LF, seeks (+0x30/+0x2c), builds std::string via FUN_10002f32 @0x100125cd:47-90"
0x10014724,io,C2,sc3_io_rename_file,"one-shot LoadLibrary KERNEL32 + GetProcAddress MoveFileExA (DAT_10024a74, guard DAT_10024a70); MoveFileExA(...,2) else MoveFileA @0x10014724:14-40"
0x10007a8d,gzcom,C2,sc3_crime_query_interface,"IID->sub-ptr: 0x215b29c5->+0x28,0x58d->+0x20,0x5e4->+0x30,0x6c6f42->+0x24,0x206c6e7c->+0x20,0x80a24318->+0x1c,0x81c0cb7b->+0x2c,0x81c0cb7c->+0x20; miss->FUN_10006251 @0x10007a8d"
0x1000b045,gzcom,C2,sc3_fire_query_interface,"IID->sub-ptr: 0x58d->+0x20,0x5e4->+0x2c,0x206c6e7c->+0x20,0x215b29c5->+0x24,0x81c0cb7b->+0x28,0x81c0cb7c->+0x20,0xa0f42240->+0x1c; miss->FUN_10006251 @0x1000b045"
0x1000ca34,gzcom,C2,sc3_flam_query_interface,"IID->sub-ptr: 0x206c6e7c/1/0x58d->+0x14,0x5e4->+0x1c,0x6c6f42->+0x18,0x2144802b->+0x10,0x81c0cb7b->+0x20,0x81c0cb7c->+0x14; miss->fail(0) @0x1000ca34"
```

## 2. Notable findings (with RVAs)

- **Full serialization framework**, keyed by the `{0x206c6e7c, GZCLSID, 0}` persist header and a reader/writer vtable convention (write-int `+0x88` / read-int `+0x38`, byte `+0x68`/`+0x18`, short `+0x78`/`+0x28`, block `+0x98`/`+0x48`). Three complete save/load pairs: crime `0x100073b0`/`0x100071d5`, fire `0x1000a619`/`0x1000a479`, police `0x1000e581`/`0x1000e3e0`, flammability `0x1000c8be`/`0x1000c7b3`.
- **`0xDEADBEEF` stream signature** validated on read at `0x10018c2f:79`.
- **Format version field, must be `< 2`**, at `0x1000c7b3:36`.
- **11/11/8/2 bit-packed cell coordinate** in the on-disk format at `0x10014eb8:21`.
- **Jail overcrowding model** at `0x1000f3bd`: ratio clamp `DAT_1002453c`, 95% (`*0x5f/100`) decay when capacity is zero.
- **New tunable globals not in the map:** `DAT_1002453c` (jail overcrowding ceiling, `0x1000f3bd:34`), `DAT_1002453a`+`DAT_1002453b` (coverage stamp params, `0x1000ece1:59`).
- **Atomic save-commit rename** via `MoveFileExA` at `0x10014724`.
- **QueryInterface tables** (`0x10007a8d`, `0x1000b045`, `0x1000ca34`) enumerate every interface each layer exposes; `0x206c6e7c` is the shared serializable IID, `0x199627` the stream IID used during save/load.

## 3. Not determined

- **`FUN_1000ece1` layer identity (police vs crime).** Body is fully described, but the offset set (`+0x7c` lock, `+0x14`/`+0x18`/`+0x50` lists, `-0x1c` base) is not uniquely tied to one layer ctor. Missing witness: an xref from a named layer ctor (`0x1000d7b8` police / `0x10005f9a` crime) writing these offsets. Classified C2 mechanically; layer left `[UNCERTAIN]`.
- **`FUN_10007868` owning subsystem.** Formats 3 stats from `param_1+0xc8`/`+0xcc` but the caller/object type is not identified in-slice. Missing: caller of `0x10007868` and the class holding fields `+0xc8`/`+0xcc`.
- **`FUN_10018480` direction (`+0x38` slot).** Slot `+0x38` is the established *read* slot, so it is classified as load of the 12/10/10 tables, but the argument is passed by value (`*piVar3`) rather than by address, which is atypical for a read. `[UNCERTAIN]` load-vs-save; the field/callee mechanics are confirmed either way.
- **`0x10015775` / `0x100155dc` object type.** Confirmed save/load pair for a positioned agent (get/set position `+0xb8`↔`+0xec`, 3-float vector `+0xb0`↔`+0x108`, extra IID `0x80199683`), but which registered class owns it is not established in-slice. Missing: caller/vtable owning `+0xb8`/`+0xec`.
- **Unlabeled IIDs** `0x58d`, `0x5e4`, `0x6c6f42`, `0x81c0cb7b/7c`, `0x80199683`, `0x199627`, `0x2144802b`, `0x80a24318`, `0xa0f42240` — reported as raw values; their named interfaces live in other GZCOM modules not in this export.

No iOS cross-reference was needed for these (all findings are SC3U-side decompilation); struct offsets above are SIMSERV-native and were not imported from the iOS tree.
