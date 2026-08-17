## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100039a8,geometry,C2,sc3_geom_layer_accumulate_centroid,"QI grid iface 0xe0faadc7; reads bbox via vt+0xd0; area=(w+1)*(h+1); accumulates weighted sums into this+0x70/+0x74, running count this+0x78, writes centroid this+0x68=+0x70/count, this+0x6c=+0x74/count"
0x1000b47d,building-layer,C2,sc3_geom_layer_postload_notify,"host this+0x104 vt+0x54 loads obj into this+0x34; guards +0x38/+0x39 select code 0x11/0x1e/0x20; QI 0xfa2; posts via vt+0x14(1,code,0,0,0)"
0x1000377e,geometry,C2,sc3_geom_create_positioned_object,"EH-wrapped; host vt+0xc; registry FUN_1001958a; resolves iface 0xe0faadc7; vt+0(param_2,param_3) create; vt+0x18 init; coords via this+0x3c vt+0x1e4; FUN_10018f81 packs; vt+0x44 sets position"
0x10021325,building-layer,C2,sc3_geom_view_init_attach,"init: +8=host(AddRef), +0xc=vt+0x94, +0x10=vt+0x8c, +4=FUN_100184b8, +0x14=grid vt+0x15c; grid FUN_1001be03 dims vt+0xd0/vt+0xcc -> +0x28=(d-1)*0x100, +0x24=d*0x100-0x100; QI self 0x22b66d3d, register host vt+0x58; vt+0x38(0,0x23); host vt+0x5c"
0x1000d830,building-layer,C2,sc3_geom_view_shutdown_detach,"guard +0xc; vt+0x58(1); registry FUN_10018460 unregisters 4 svc 0xc35ee786/0xa36cf3d1/0x920fbda8/0x231bbf91 (subject +0x8); releases +0x98,+0x9c,+0x20,+0x24; clears guard"
0x1000118f,serialization,C2,sc3_geom_load_keyed_list,"stream read via param_1 vt+0x38; count into this+0x1c; loop reads 4 ints; key lookup FUN_1001be55 vt+0x14(&rec,0x21183b00,&out); FUN_10001562 appends to list this+0x20"
0x1001b599,io-util,C2,sc3_geom_move_file,"lazy GetProcAddress MoveFileExA from KERNEL32.DLL (guard DAT_10030ab0, ptr DAT_10030ab4); MoveFileExA(dst,src,2) with MoveFileA fallback; paths via vt+0x14"
0x1001cd38,serialization,C2,sc3_geom_write_occupant_transform,"writer param_2: vt+0x28(this vt+0x14), vt+0x2c(this vt+0x88), vt+0x30 packed coords this+0x10 (x=&0x7ff,y=>>0xb&0x7ff,z=>>0x16&0xff), vt+0x34(this vt+0xd4), vt+0x38(this+0x10>>0x1e), vt+0x3c(this+0xc bits 0x18/0x19)"
0x1000bbaa,building-layer,C2,sc3_geom_scan_grid_place,"grid param_2 vt+0x14(2) init; vt+0x24(2) dims-1; nested loop; vt+0x18(2,x,y,&code) read cell; FUN_1000c60e lookup; place via this vt+0x6c(&px{x<<8,y<<8},obj)"
0x1001176e,dispatch,C2,sc3_geom_dispatch_cmd_28,"EH-wrapped; key 0x206c6e7c/0x1fd7a8c; FUN_10003529 + FUN_1001f57c(param_1,param_2); FUN_1001f6f6 run; if flag call (this-0x20) vt+0x28"
0x100116e9,dispatch,C2,sc3_geom_dispatch_cmd_24,"EH-wrapped; key 0x206c6e7c/0x1fd7a8c; FUN_1001f360(param_1,param_2); FUN_1001f6f6 run; if flag call (this-0x20) vt+0x24"
0x10013ddf,building-layer,C2,sc3_geom_query_draw_flag,"param_1==1?vt+0x74:vt+0x6c on param_2; if set, vt+0x48 bit 0x100; QI 0xe0faadc7; vt+0x54(0x200) clears result; returns char"
0x100121e1,geometry,C2,sc3_geom_get_grid_attribute,"QI param_1 0xe0faadc7 (grid); vt+0x60 sub-obj; QI 0x22002d06; return vt+0xc4; Release"
0x1001206a,occupant,C2,sc3_geom_occupant_queryinterface,"QI: {0x58d,0x206c6e7c,0x81c0cb7c}->this+0x20; 0xc1fd7a96->this+0x1c; else tail-call base FUN_10011525; AddRef vt+4"
0x10014676,occupant,C2,sc3_geom_occupant_queryinterface2,"QI: {1,0x58d,0x206c6e7c,0x231c8e63,0x81c0cb7c}->*param_2=this,AddRef vt+4,ret 1; else ret 0"
```

## 2. Notable findings

**A serialiser pair for the packed-coordinate occupant format — highest value.**
- **`0x1001cd38` `sc3_geom_write_occupant_transform`** proves the on-wire/on-disk layout of a geometry object. `this+0x10` is a single dword packing **x = bits 0-10 (0x7ff), y = bits 11-21 (0x7ff), z = bits 22-29 (0xff), and a 2-bit field bits 30-31** `[CONFIRMED @ 0x1001cd38:26]`. `this+0xc` holds two boolean flags at bit 0x18 and bit 0x19 `[CONFIRMED @ 0x1001cd38:27-29]`. It emits six fields through writer vtable slots `+0x28,+0x2c,+0x30,+0x34,+0x38,+0x3c`.
- **`0x1000118f` `sc3_geom_load_keyed_list`** is a **loader/deserialiser**: reads a count into `this+0x1c`, then loops reading 4 ints per record and resolving each via service **`0x21183b00`** (the same `DefaultBuildingData` key service documented in `SIMGEOM.md`) `[CONFIRMED @ 0x1000118f:36]`, appending survivors to the list at `this+0x20`.

**Two init/shutdown entry points for a view/sub-layer object (paired).**
- **`0x10021325` `sc3_geom_view_init_attach`** computes **pixel extents from grid dims**: `this+0x28 = (dimD0 - 1) * 0x100`, `this+0x24 = dimCC * 0x100 - 0x100` `[CONFIRMED @ 0x10021325:32-33]` — the same `·0x100` pixel-scale idiom as the `SC3BuildingLayer` attach, but on a distinct class (extents at `+0x24/+0x28`, self-IID `0x22b66d3d`). Registers itself via host `vt+0x58`/`vt+0x5c`.
- **`0x1000d830` `sc3_geom_view_shutdown_detach`** is its counterpart: **unregisters from four services** `0xc35ee786`, `0xa36cf3d1`, `0x920fbda8`, `0x231bbf91` `[CONFIRMED @ 0x1000d830:19,26,33,40]`, then releases four held pointers (`+0x20,+0x24,+0x98,+0x9c`).

**A grid-scan placement loop.** `0x1000bbaa` `sc3_geom_scan_grid_place` iterates the grid `[dim-1..0]²`, reads each cell code via `vt+0x18(2,x,y,&code)`, resolves it through `FUN_1000c60e`, and places the result at pixel coords `{x<<8, y<<8}` via `this vt+0x6c` `[CONFIRMED @ 0x1000bbaa:31-37]` — the same `<<8` tile→pixel convention as the `0x1000271d` placement path in the module map.

**QueryInterface / interface-id evidence (no single dispatch table, per-class QI chains).**
- Base QI **`0x10011525`**: IIDs `{1, 0x817ab319, 0xa0ace10a}`.
- `0x1001206a` and `0x10014676` are QI methods for a building-**occupant** class exposing embedded interface subobjects at `this+0x1c` (IID `0xc1fd7a96`) and `this+0x20` (IIDs `0x58d`, `0x206c6e7c`, `0x81c0cb7c`) `[CONFIRMED @ 0x1001206a:9-17]`.
- The two dispatch handlers `0x100116e9`/`0x1001176e` invoke a vtable slot on `(this - 0x20)` `[CONFIRMED @ 0x100116e9:35, 0x1001176e:41]` — i.e. they run *on* that `+0x20` subobject and call back into the parent. Consistent cross-link. Their shared key is `0x206c6e7c`/`0x1fd7a8c`.

**`0xe0faadc7` is the grid/world interface id.** Queried in `0x100039a8`, `0x1000377e`, `0x10013ddf`, `0x100121e1`, and the known placement fn `0x1000271d`; after resolving it, callers read grid dims via `vt+0xd0`/`vt+0xcc` — matching the grid-dims vtable slots in `SIMGEOM.md` `[CONFIRMED @ 0x100039a8:34,41; 0x100121e1:12]`.

**A centroid/center-of-mass accumulator.** `0x100039a8` maintains a running area-weighted sum (`this+0x70`, `this+0x74`), total area (`this+0x78`), and derived centroid (`this+0x68 = +0x70/total`, `this+0x6c = +0x74/total`) over grid bounding boxes `[CONFIRMED @ 0x100039a8:42-58]`. No tick/Simulate entry point was found in this slice.

## 3. Not determined

- **No per-tick / `Simulate` entry point** appears in these 15 functions. Missing evidence: none in this slice reads a tick counter or is called from a scheduler vtable; would need the module's tick-registration site (not in this set).
- **Semantic purpose of the dispatch key `0x206c6e7c` / `0x1fd7a8c`** in `0x100116e9`/`0x1001176e`: the two dwords are a paired constant of unknown meaning `[UNCERTAIN]`. The distinguishing vtable slots (`+0x24` vs `+0x28`) and the run helper `FUN_1001f6f6`/`FUN_1001f360`/`FUN_1001f57c` were not read; missing evidence = bodies of those three helpers and the class holding the `+0x20` subobject.
- **The four unregister service ids** in `0x1000d830` (`0xc35ee786`, `0xa36cf3d1`, `0x920fbda8`, `0x231bbf91`) and the register ids in `0x10021325` (self-IID `0x22b66d3d`) have no resolved names — raw hex reported. Missing evidence = a service-id → name table (none in `.text`; would need `.rdata`/iOS symbol match).
- **`0x100121e1`** interface `0x22002d06` and the `vt+0x60`/`vt+0xc4` slots return an unnamed value; purpose beyond "reads one attribute off a grid sub-interface" is `[UNCERTAIN]` (missing: the sub-interface's vtable layout).
- The `0x6c6f42` interface id queried at the tail of `0x100039a8` and the codes `0x11/0x1e/0x20` in `0x1000b47d` are reported as raw values; their semantic meaning is not determined from this slice.

All 15 functions were read and mechanically described → **C2** each. No C3/C4 claimed (no runtime/second witness). Struct offsets above are SC3U-native; no iOS offsets were transferred (none needed).
