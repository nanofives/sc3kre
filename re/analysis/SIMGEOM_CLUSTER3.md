# SIMGEOM.DLL — C0 cluster 3 (25 largest remaining, 8,946 bytes)

All 25 read and classified **C2** (body read, callees identified, mechanically described). Builds on `SIMGEOM.md`, `SIMGEOM_CLUSTER1/2.md`, `SIMGEOM_PROPERTIES.md`. I did **not** re-derive the property schema, the `0x1001e516/0x1001e226` pair, the section groups, or `0x1001f360` — instead I found (a) the **destructor that proves the `0x74`–`0x7a` slots hold releasable COM resource objects**, and (b) the **layer-cache attach/init** that backs the placement/scan `this`.

## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10014489,simgeom-layer,C2,sc3_geom_tool_attach_world,"Attach/init. Reads host param_1 vt+0xcc(w)/vt+0xd0(h); this+0x14=(w*0x100)-0x100, this+0x18=(h*0x100)-0x100 pixel extents, this+0x2c=w<<8, this+0x30=h<<8; acquires (AddRef vt+4) 10 host layer objects: vt+0x15c->+0x38, vt+0x14c->+0x3c, vt+0x140->+0x40, vt+0x11c->+0x44, vt+0x120->+0x4c, vt+0x124->+0x48, vt+0x13c->+0x50, vt+0x148->+0x54, vt+0x138->+0x58, vt+0x18c->+0x5c; then this+0x60 = layer(+0x38) vt+0x58(7) = per-tile cost base [CONFIRMED @0x10014489]"
0x100224ed,simgeom-occupant,C2,sc3_geom_occupant_destroy,"Destructor. vtables PTR_FUN_1002b658 / PTR_LAB_1002b5a8(+0x14) / PTR_LAB_1002b58c(+0x18); frees GZString at +0x20; Releases (vt+8) COM objects at occupant-base offsets +0x120(0x71 delegate),+0x34(0x67),+0x44,+0x48(0x6b),+0x84(0x74),+0x94(0x75),+0xa4(0x76),+0xb4(0x77),+0xc4(0x78),+0xd4(0x79),+0xe4(0x7a); tail FUN_1001ba2d(base) [CONFIRMED @0x100224ed]"
0x10003adf,simgeom-layer,C2,sc3_geom_centroid_remove_building,"Building-removal centroid update. occ param_2 vt+0x3c(0x100) gate; QI 0xe0faadc7, vt+0x4c==1 -> FUN_10003d34; this+0x34 vt+0x1d8 layer, QI 0x6c6f42 svc vt+0x2c; if this+8: occ vt+0xd0(&rect), area=(w+1)*(h+1); this+0x78-=area (total), this+0x70-=cx*area, this+0x74-=cy*area; recompute centroid this+0x68=+0x70/+0x78, this+0x6c=+0x74/+0x78; if +0x78==0 reset to host vt+0xcc>>1 / vt+0xd0>>1 [CONFIRMED @0x10003adf]"
0x1000970f,simgeom-place,C2,sc3_geom_tool_op_slot24,"Interactive place-tool op (sibling of FUN_1000a62a). placement svc this+0x104 vt+0x24 feasibility(param_1,this+0x108,&res,&cost)->this+0x38 valid/this+0x34 cost; FUN_100214b8; if ok & this+0x39==0: vt+0x38 commit; sound svc class 0xfa2 (FUN_10008ce6 vt+0x7c): 0xca success (x>>8,y>>8), 0x1e/0x20 failure [CONFIRMED @0x1000970f]"
0x10009f7f,simgeom-place,C2,sc3_geom_tool_op_slot28,"Sibling of FUN_1000970f; placement svc vt+0x28 feasibility / vt+0x3c commit; sound ids 0xca/0x1e/0x20 [CONFIRMED @0x10009f7f]"
0x100099eb,simgeom-place,C2,sc3_geom_tool_op_slot2c,"Sibling; placement svc vt+0x2c feasibility / vt+0x40 commit; sound ids 0xca/0x1e/0x20 [CONFIRMED @0x100099eb]"
0x10009d3f,simgeom-place,C2,sc3_geom_tool_op_slot30,"Sibling; placement svc vt+0x30 feasibility / vt+0x44 commit; sound ids 0xca/0x1e/0x20 [CONFIRMED @0x10009d3f]"
0x10008ee8,simgeom-place,C2,sc3_geom_tool_op_grid_service,"Place-tool op on grid svc this+0x144: FUN_10008d25/FUN_100093f9 clamp rect local_24, vt+0x48(this+0x88,rect,0,1,&cost,res,&occ) feasibility, vt+0x58 commit; FUN_100214b8; sound class 0xfa2 ids 5 success / 0x1e / 0x20 [CONFIRMED @0x10008ee8]"
0x100131d7,simgeom-place,C2,sc3_geom_scan_region_cost_mode,"Multilayer region cost scan (sibling FUN_1001303b) with mode param_1 0/1/2/3 selecting which of layers this+0x44(main)/+0x4c/+0x48 to test; lock this+0x50 vt+0x148(1/0); per tile vt+0x144 valid, layer vt+0x7c get occ, vt+0x3c(0x400)+FUN_10013ddf filter -> cost += this+0x60; presence on +0x4c/+0x48 sets *param_4=0; out cost param_4 [CONFIRMED @0x100131d7]"
0x10013f33,simgeom-place,C2,sc3_geom_collect_building_type_cells,"Collect all footprint cells of one multi-tile building. occ param_3: type=vt+0x88, w=vt+0xd4,h=vt+0xd8, pos vt+0xb8; expand rect by (dim&0xff)*0x200, clamp FUN_10008cf2/FUN_10008d7e; FUN_10013ddf(param_1,occ) filter -> param_2 vt+0x48(occ) add; loop cells vt+0x7c(x,y,&occ2), if occ2 vt+0x88==type & filter -> add [CONFIRMED @0x10013f33]"
0x100134fb,simgeom-place,C2,sc3_geom_enum_region_bbox_notify,"Region enumerate+bbox+cost+notify (sibling FUN_1001392a/FUN_1001364f). FUN_10008d25 clamp param_2; param_1 vt+0x74(&enum,rect,param_3); loop vt+0x18/+0x1c; FUN_10013ddf(param_4) filter; this vt+0x6c(occ,param_4,&out,rect6,&cnt)=FUN_1001408d; merge bbox param_7 FUN_100149c4; *param_6+=out; if cnt!=0 post msg 0x637c0dab packed bbox via FUN_10018460 vt+0x10; if !param_5 this+0x38 vt+0x14(*param_6) [CONFIRMED @0x100134fb]"
0x1000a41c,simgeom-occupant,C2,sc3_geom_occupant_init_footprint_dims,"FUN_1001be03 svc vt+0x138 -> param_1+0xac (AddRef); FUN_1001bec0 mgr vt+0x24 resolves iid 0xe075ef51 at param_1+0xb0/+0xbc/+0xc8; sums sub vt+0x40->+0xe2 (w-1), vt+0x44->+0xe3 (h-1), vt+0x80->+0xe4, vt+0x78->+0xe8; posts msg 0x635ee3c3 via FUN_10018460 vt+0x10; tail FUN_10021325(param_1-0x58,FUN_1001be16) [CONFIRMED @0x1000a41c]"
0x10011a4f,simgeom-grid,C2,sc3_geom_grid_set_region_flag,"Set flag bit 0x1000000 across the union of two tile rects (param_1,param_2). this vt+0x44 pre-check; lock this+0x18 vt+4/+8; per cell this-0x1c vt+0x1c match, vt+0x34 read byte3, OR 0x1000000, vt+0x3c write; step 4 (tile) [CONFIRMED @0x10011a4f]"
0x10011dbe,simgeom-grid,C2,sc3_geom_grid_clear_region_flag,"Mirror of FUN_10011a4f: clears flag bit 0x1000000 (& 0xfeffffff) across union of two rects; this-0x1c vt+0x1c/+0x34/+0x3c; lock this+0x18 [CONFIRMED @0x10011dbe]"
0x10011c71,simgeom-grid,C2,sc3_geom_grid_bump_adjacency_counter,"Over a +/-8 tile window around (param_1,param_2): pass1 read this-0x1c vt+0x34 byte, mask &0x3c, if >0x3b (saturated) return 0; pass2 counter=(b&0x3c)+4 | b&0xc3, write vt+0x3c; FUN_1001be03 vt+0x13c layer vt+0x15c(x,y,1) notify; lock this+0x18 [CONFIRMED @0x10011c71]"
0x10017825,simgeom-ini,C2,sc3_geom_stream_read_line,"Read one text line from reader this+0x28. vt+0x18 tell, vt+0x1c end, vt+0x38 read up-to-0x28 block, scan for CR/LF, vt+0x30 seek back, vt+0x2c; accumulates into GZString then FUN_10001f63 to param_1+4; returns got-line flag [CONFIRMED @0x10017825]"
0x100176c0,simgeom-ini,C2,sc3_geom_ini_index_section_names,"Enumerate all [SECTION] headers of reader param_1[10] (vt+0x10 eof, vt+0x70 seek, vt+0x24, vt+0x18 tell); param_1 vt+0x44 open, vt+0x40 readline; on '['..']' extract name (FUN_10001f63), FUN_10017aac build, FUN_10017ccc insert into container param_1+7 (init FUN_10017bc2); sets param_1+0x19 done flag [CONFIRMED @0x100176c0]"
0x10020fde,simgeom-util,C2,sc3_geom_string_replace_range,"std::string/vector<byte> replace: splice [param_2,param_3) into position param_1, grow-or-in-place; FUN_100018c5 alloc, memmove/memcpy, FUN_1000161d free old [CONFIRMED @0x10020fde]"
0x10017e8d,simgeom-util,C2,sc3_geom_vector_insert_rec40,"std::vector<0x28-byte record> insert element param_2 at position param_1; doubling growth; FUN_10018350 range-copy, FUN_100180bd copy-ctor, FUN_100183c4 dtor, FUN_100018c5/FUN_10001636 alloc/free [CONFIRMED @0x10017e8d]"
0x1001ed6b,simgeom-util,C2,sc3_geom_vector_insert_pair,"std::vector<8-byte record> insert-at-position; doubling growth; FUN_1001f2ec range-copy, FUN_1001ef0a copy, FUN_1001e211 dtor [CONFIRMED @0x1001ed6b]"
0x10014834,simgeom-util,C2,sc3_geom_vector_insert_triple,"std::vector<0xc-byte (3-dword) record> insert-at-position; doubling growth; FUN_100257a6 range-copy; element copied as 3 dwords [CONFIRMED @0x10014834]"
0x10015efa,simgeom-util,C2,sc3_geom_deque_grow_map4,"std::deque map/block reallocation (element stride 4); rebases begin this+0x14 / end this+0x24, first block +0xc/+0x10, last block +0x1c/+0x20; block size via FUN_1001584d*4 [CONFIRMED @0x10015efa]"
0x10015d31,simgeom-util,C2,sc3_geom_deque_grow_map8,"Sibling of FUN_10015efa with element stride 8 (block size FUN_10015853*8); std::deque map reallocation [CONFIRMED @0x10015d31]"
0x1001d943,simgeom-query,C2,sc3_geom_query_add_category_row,"Query row builder. this vt+0x80->sub vt+0xa8 vt+0x28(&list); if list nonempty build resource key group 0x41f2625 instance 0x132 (FUN_1001fa0c/FUN_1001fa44), format 2 GZStrings (FUN_10004e36), param_2 vt+0x4c(&label,&val,-1,0) add row [CONFIRMED @0x1001d943]"
0x100242ff,simgeom-query,C2,sc3_geom_query_build_name_row,"Query descriptor. FUN_1001cd38(this+8) match; this vt+0x38 -> this+8 vt+0x7c(&name), this+0xc vt+0x3c(&cur), if differ (FUN_10017e5a) param_2 vt+0x54(&name); this vt+0x3c -> vt+0x40(&val), FUN_1001916f/FUN_10019167 split, param_2 vt+0x60(b,a); param_2 vt+0x6c(this+0x1c) [CONFIRMED @0x100242ff]"
```

## 2. Notable findings

### PRIORITY-1 ADVANCE — the destructor proves `0x74`–`0x7a` hold releasable resource objects `[CONFIRMED @0x100224ed]`
`SIMGEOM_PROPERTIES.md` left ids `0x76`–`0x7a` (`+0xa4`..`+0xe4`) with **no proven consumer** — only inferred layout. The occupant destructor `FUN_100224ed` is that consumer. It releases a COM object (`vt+8`) at every one of these occupant-base offsets (destructor indices are on the **full** object; occupant base = full+0x14, so `property offset = index*4 − 0x14`):

| dtor index | ×4 | −0x14 = base off | property | prior status |
|---|---|---|---|---|
| `[0x4d]` | 0x134 | **+0x120** | `0x71` delegate | confirmed (now: released here) |
| `[0x12]` | 0x48 | **+0x34** | `0x67` | slot proven |
| `[0x16]` | 0x58 | **+0x44** | (0x6b resolve key) | corroborates FUN_1002396f |
| `[0x17]` | 0x5c | **+0x48** | `0x6b` | now: holds COM object |
| `[0x26]` | 0x98 | **+0x84** | `0x74` | slot proven |
| `[0x2a]` | 0xa8 | **+0x94** | `0x75` | slot proven |
| `[0x2e]` | 0xb8 | **+0xa4** | **`0x76`** | **was: no consumer → now proven COM-object slot** |
| `[0x32]` | 0xc8 | **+0xb4** | **`0x77`** | **now proven** |
| `[0x36]` | 0xd8 | **+0xc4** | **`0x78`** | **now proven** |
| `[0x3a]` | 0xe8 | **+0xd4** | **`0x79`** | **now proven** |
| `[0x3e]` | 0xf8 | **+0xe4** | **`0x7a`** | **now proven** |

**What this closes:** the `+0x00` word of every resource-key slot `+0x34`/`+0x84`/`+0x94`/`+0xa4`/`+0xb4`/`+0xc4`/`+0xd4`/`+0xe4` (props `0x67`,`0x74`–`0x7a`) is a **refcounted COM interface pointer** (the resolved resource object), released via `vt+8` at teardown — not a plain cached id. All 7 `+0x84`..`+0xe4` slots are now proven the same kind, by a **reader** (the destructor), not just by layout. It also proves `+0x48` (`0x6b`) and `+0x120` (`0x71`) hold COM objects.
**What it does NOT close:** the *semantic variant* of each slot (which visual/model purpose `0x76`–`0x7a` select). `FUN_10022749` still only maps purpose bits 1/2/4 → `+0x34`/`+0x84`/`+0x94`; no code in this slice reads `+0xa4`..`+0xe4` by a purpose bit. Missing evidence unchanged: an external caller passing purpose bits ≥ 8.
Occupant vtable is **`PTR_FUN_1002b658`** (base sub-vtables `PTR_LAB_1002b5a8` at `+0x14`, `PTR_LAB_1002b58c` at `+0x18`).

### The placement/scan layer-cache attach `[CONFIRMED @0x10014489]`
`FUN_10014489` is the init that backs the `this` used across cluster1/2's placement and scan functions. It caches **10 host grid-layer objects** (all AddRef'd) and the per-tile cost:

| host vtable slot | stored at | used by |
|---|---|---|
| `vt+0x15c` | `this+0x38` | main layer; source of per-tile cost |
| `vt+0x14c` | `this+0x3c` | |
| `vt+0x140` | `this+0x40` | |
| `vt+0x11c` | `this+0x44` | scan-cost layer (FUN_100131d7/FUN_1001303b) |
| `vt+0x120` | `this+0x4c` | scan layer 2 |
| `vt+0x124` | `this+0x48` | scan layer 3 |
| `vt+0x13c` | `this+0x50` | lock layer (`vt+0x148`/`+0x144`) |
| `vt+0x148` | `this+0x54` | |
| `vt+0x138` | `this+0x58` | |
| `vt+0x18c` | `this+0x5c` | |

and computes **`this+0x60 = layer(+0x38) vt+0x58(7)` = per-tile cost base** — the exact `*(this+0x60)` multiplied by `w*h` in `FUN_10012e92`/`FUN_1001408d`/`FUN_10024a04` and accumulated in `FUN_100131d7`. Pixel extents `this+0x14=(w-1)*0x100`, `this+0x18=(h-1)*0x100` match `SIMGEOM.md`'s attach (`+0x48`/`+0x4c`). This is not a per-tick callback — it is one-shot attach/init.

### Placement tool-op family `[CONFIRMED]`
Five consecutive interactive place-tool operations, identical bodies differing **only** by the placement-service (`this+0x104`) vtable-slot pair (feasibility / commit), all using sound service class `0xfa2` with success sound `0xca`, failure `0x1e`/`0x20`:

| function | feasibility | commit |
|---|---|---|
| `FUN_1000970f` | `vt+0x24` | `vt+0x38` |
| `FUN_10009f7f` | `vt+0x28` | `vt+0x3c` |
| `FUN_100099eb` | `vt+0x2c` | `vt+0x40` |
| `FUN_10009d3f` | `vt+0x30` | `vt+0x44` |
| `FUN_1000a62a` (cluster2) | `vt+0x34` | `vt+0x48` |

`FUN_10008ee8` is a 6th variant that instead drives grid service `this+0x144` (`vt+0x48`/`vt+0x58`, using grid `this+0x88`) with success sound `5`.

### Lot-fitting / building geometry (priority 2)
- `FUN_10013f33` — enumerate every footprint cell of one multi-tile building, matched by type id (`vt+0x88`); footprint rect expanded by `(dim&0xff)*0x200`.
- `FUN_100134fb` — region enumerate → per-occupant `FUN_1001408d` layer distribute → bbox merge + cost sum → repaint notify `0x637c0dab`.
- `FUN_100131d7` — multilayer region cost scan with a **mode selector** (0/1/2/3) choosing which of layers `+0x44`/`+0x4c`/`+0x48` participate.
- `FUN_10003adf` — running **city-centroid** update on building removal (`+0x70`/`+0x74` weighted sums, `+0x78` total area, `+0x68`/`+0x6c` centroid; resets to host-dims/2 when empty).
- `FUN_10011a4f` / `FUN_10011dbe` — set / clear grid flag bit **`0x1000000`** over a two-rect union.
- `FUN_10011c71` — bump a saturating **adjacency counter** in flag bits `0x3c` (cap `0x3c`), then layer redraw `vt+0x15c(x,y,1)`.

### Message / resource ids new to this slice `[CONFIRMED]`
- **`0x635ee3c3`** posted by `FUN_1000a41c` (occupant footprint-dims init) via `FUN_10018460 vt+0x10`.
- iid **`0xe075ef51`** — the interface `FUN_1000a41c` resolves ×3 to sum footprint w/h (`vt+0x40`/`vt+0x44`).
- svc **`0x6c6f42`** queried in `FUN_10003adf` (layer `this+0x34 vt+0x1d8`).
- resource group **`0x41f2625`** instance **`0x132`** in `FUN_1001d943` (same building-category text group as cluster1's `FUN_100202a7`, different instance).

## 3. Not determined / missing evidence

- **Semantic variant of props `0x76`–`0x7a`**: the destructor now proves they are releasable resource-object slots (see §2), but *which appearance/model variant* each selects is still unproven. Missing: a reader that selects `+0xa4`..`+0xe4` by a purpose bit (`FUN_10022749` handles only bits 1/2/4 → `+0x34`/`+0x84`/`+0x94`); an external caller passing purpose bits ≥ 8. Not present in this slice.
- **Per-tick / Simulate callback into the SIMCITY bucket list (priority 3): not found.** `FUN_10014489` is one-shot attach/init (caches layers, AddRef), not tick registration; no function here reads a clock/tick counter or installs a periodic callback. Missing: an xref showing which SIMGEOM vtable slot SIMCITY's tick driver invokes — outside this module's text export.
- **Placement-tool-op semantics**: the 5 feasibility/commit vtable-slot pairs (`0x24/0x28/0x2c/0x30/0x34`) are distinct tool modes (build vs bulldoze vs query, etc.), but which is which needs the placement-service (`this+0x104`) vtable-construction site — not in this slice. Same for `FUN_100131d7`'s mode `0/1/2/3` → layer mapping.
- **`FUN_10003adf` svc `0x6c6f42` and `FUN_1000a41c` msg `0x635ee3c3` / iid `0xe075ef51`**: raw selectors; human meaning needs an external (SIMCITY/SIMUI) caller passing a named constant.
- **`FUN_10015efa`/`FUN_10015d31` block sizes** (`FUN_1001584d`/`FUN_10015853`): the deque block-element count is returned by those callees (outside this slice); the container's element type is not determinable from the reallocation alone.
- **iOS cross-check**: not used. Per `SIMGEOM_PROPERTIES.md` the named iOS `Occupant` symbols are the population/disaster occupant and struct offsets are proven non-transferable (0/5 for goPowerPlant). No `[iOS-HINT]` applied.

All 25 slice functions read and named/classified **C2**. None reach C3/C4 (needs runtime or a second witness not producible read-only).
