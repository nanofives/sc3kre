## SIMMISC.DLL — C0 cluster (toolkit-necessary set, 25 functions)

Building on `re/analysis/SIMMISC.md`. Stream serialization vtable, confirmed self-consistent across the load/save pairs below:

| stream slot | operation | proof |
|---|---|---|
| `+0x18` | read byte (into `&dest`) | load side of 10036f36/10037058 pair |
| `+0x38` | read uint32 (into `&dest`) | ″ |
| `+0x28` | read specialised (into `&dest`) | 100360de |
| `+0x40`,`+0x48` | read specialised | 10036f36 |
| `+0x68` | write byte (by value) | save side |
| `+0x88` | write uint32 (by value) | ″ |
| `+0x90`,`+0x98` | write specialised | 10037058 |
| `+0x20`/`+0x30`/`+0x24` | QueryInterface / release on the stream's GZ persist record | 10002784, 100028f1 |

The load↔save offset sets match exactly for two pairs (`10036f36`↔`10037058`; `10002784`↔`100028f1`; `10019c53`↔`10019d5a`), which is what fixes the slot meanings `[CONFIRMED @0x10037058, @0x10036f36]`.

### 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100278b0,S1-world,C2,sc3_world_tick_econphase_timeline,"per-tick: reads date via this+8 vtbl +0x1e4 -> (a,b,year); floors year>=0x76c(1900) @100278f2; index = date - 0x5911 + year*0xc @10027992; walks per-entry ushort schedule this+0xb4..0xb8 (stride 0x1c) advancing frame counter entry+8 and remainder entry+10 (else 65000); QI keys 0xf1ec30 per-entry and 3000/5000/8000 into this+0x18/0x20/0x1c; posts via FUN_10032100 +0x1d8 -> +0x28"
0x10020cc9,S14-ui,C2,sc3_ui_dispatch_menu_command,"command dispatch on param_2: 0x32/0x33/0x34/0x35/0x36 then range [0x64 .. this+0x50*+0x64]; posts notification descriptors {0x724a82e1},{0x724a82de,0x628d0c45,0xbbc=3004},{...0xbbe=3006},{0x724a82dd} via FUN_1002d87b +0xc; case0x34 new(0x3c)+FUN_10024367; case0x33 QI(0x630288e9,0x6856f7); sets busy cursor via FUN_100320b1 +0x34->+0x14(1,0xc..); this+0x5c array stride 0x28 indexed by param_2-0x19; tail FUN_10020f19"
0x1001e836,S14-ui,C2,sc3_ui_dispatch_mode_toggle,"dispatch on param_2 0x20..0x23; 0x20 sets help cursor(0x15) + FUN_1002d8d3 +0x44(0xd,...); 0x21 DAT_10049f1c=0 toggles this+0x60/+0x68 vtbl+0xf4 and this+0x5c +0x28 / this+0x58 +0x2c; 0x22 DAT_10049f1c=1 opposite; 0x23 posts {0x724a82da,0x628d0c45} via FUN_1002d87b +0xc; mutually-exclusive two-layer view toggle keyed by global DAT_10049f1c"
0x1001370c,S12-aura,C2,sc3_aura_propagate_tile_value,"reentrancy guard this+0x3c; radius this+8 +0xd4/+0xd8 (&0xff); city sim FUN_10032100 +0x11c layer, map w/h +0xcc/+0xd0; center this+8 +0xbc; bbox = center +/- 2*radius clamped to map; inner tiles -> FUN_1000cb4e/+0x48(param_1); outer tiles query +0x7c, if +0x88==id(this+4 +0x18) QI(0xe0faadc7) then +0x4c getter/+0x48 setter(param_1); IDENTICAL to 0x10012040 and 0x10013e71"
0x10012040,S12-aura,C2,sc3_aura_propagate_tile_value_b,"byte-identical duplicate of 0x1001370c (three-copy inlining across sibling layers)"
0x10013e71,S12-aura,C2,sc3_aura_propagate_tile_value_c,"byte-identical duplicate of 0x1001370c"
0x10002784,S12-aura,C2,sc3_aura_load_state,"LOAD: QI GZCLSID 0xc259c02d via param_2+0x20 (key 0x206c6e7c), record key 0x199627; reads via local_c +0x18(byte)/+0x38(dword) into this+0x90(byte clamp<=0xf @10002819),+0x94(clamp),+0x98(clamp),+0x80,+0x7c,+0x84; sets this+0x11=1; forwards to this+0x88 vtbl +0x84"
0x100028f1,S12-aura,C2,sc3_aura_save_state,"SAVE: QI GZCLSID 0xc259c02d via param_2+0x30 (key 0x206c6e7c/0x199627); writes this+0x90 via +0x68(byte), this+0x94/0x98/0x80/0x7c via +0x88(dword), this+0x84 via +0x68; forwards to this+0x88 vtbl +0x88; save counterpart of 0x10002784"
0x10019c53,S14-ordinance,C2,sc3_ordinance_load_flags,"LOAD: QI GZCLSID 0x41193c3a/0xe1193c2a (key 0x199627); reads count then loops: id(local_1c),byte,byte via +0x38/+0x18; FUN_10009d86 looks up record; writes record+0x14 -> +4 (enabled bool), +5 (leaf bool)"
0x10019d5a,S14-ordinance,C2,sc3_ordinance_save_flags,"SAVE: QI 0x41193c3a/0xe1193c2a (key 0x199627); writes this+0x28 count via +0x88; iterates list this+0x24 (node stride via FUN_10003354), each node+0x10 id via +0x88 and node+0x14 record +4/+5 bytes via +0x68; save counterpart of 0x10019c53"
0x100218d2,S14-ordinance,C2,sc3_ordinance_view_ctor,"ctor: vtbls PTR_LAB_1004121c / this+4=PTR_FUN_10041268 (FUN_1002d805) / PTR_LAB_10041254; stores param_1->+0x14,param_2->+0x10,param_3->+0x20,param_4->+0x24,param_6->+0x28; QI(0xe1193c2a)->(0x41193c3a,this+0x18) via FUN_100320b1 +0x18/+0x1b8; formatter FUN_1002d8ff +0x94->+0x1c; copies param_5[0..3]->this+0x2c/0x30/0x34/0x38 (rect bounds)"
0x10021a06,S14-ordinance,C2,sc3_ordinance_view_open_window,"opens GZ window: FUN_1002fe8d QI(0xa2a79fd0,0xa2a79fd1); flag bits via +0x18 (1,2,0x10000,0x100,0x40,0x1000,0x8000,4); sets callback this via +0x38; create +0xc; window id 0x82e00e34 via +0xec; rect +0xc8(0,0, this+0x34-0x2c, this+0x38-0x30) from ctor bounds"
0x1001ea54,S14-ordinance,C2,sc3_ordinance_view_open_window_alt,"identical to 0x10021a06 except window id 0x42dddc93 via +0xec (alternate skin/panel)"
0x1001bc3d,S14-ui,C2,sc3_ui_open_centered_window,"opens GZ window (FUN_1002fe8d QI 0xa2a79fd0/0xa2a79fd1); flags via +0x18; window id 0x42dd813a via +0xec, +0xf4(0x10000,1); fixed rect 500x0x1e0(480) via +0xc8; caches/centers position in DAT_10049f20/DAT_10049f24 with valid-flag DAT_10049f1d; center math = ((extent>>16 - x>>16)-500)/2 clamped>=0 @1001bda1; posts {0x624a8240} via FUN_1002d87b +0xc; applies pos via +0xcc"
0x10007a59,S14-ordinance,C2,sc3_layer_activate_slots,"activate: iterate this+0x5c list applying +0x20 flag; QI service 0x80f1e6d3->0x40a42f1c; this+0x4dc = FUN_100320b1 +0x1b0 service; FUN_10008865; fill 3 slots (base this+0x80, stride 0x88): +0x84 record, float via +0x6c(FUN(this-4)+0x50); after 3 subscribe msgs 0x62e8630b,0x23b4418f (FUN_100320b1 +0x2c +0x14) and 0x6569de54 (FUN_1002d87b +0x14); post {0x229a8a90} via FUN_1002d87b +0x10"
0x10007bb9,S14-ordinance,C2,sc3_layer_deactivate_slots,"deactivate/free: unsubscribe 0x62e8630b,0x23b4418f (FUN_100320b1 +0x2c +0x10), 0x6569de54 implied; loop3 free this+0x84 slot array (stride 0x88); release this+0x10/0x14/0x18/0x1c/0x20/0x24/0x2c/0x4dc/0x54c(FUN_10037583)/0x44; this+0xc=0; shutdown counterpart of 0x10007a59"
0x10036277,serialize,C2,sc3_object_save_state,"SAVE: QI(0x80199683) sub-object -> writes sub +0x14/+0x1c/+0x24 via param_2+0x88; writes this getters +0x88,+0x54,+0x60,+0xd4,+0xd8,+0xdc,+0x58,+0xf8,+0x30,+0x6c,+0x74 via stream +0x88/+0x68; this+0xb8 -> 3 coords (>>8) via +0x88; this+0xb0 -> 3 via +0x78; [UNCERTAIN] owning class"
0x100360de,serialize,C2,sc3_object_load_state,"LOAD: reads 3 handles via +0x38 -> this+0x18; bytes via +0x18 -> this+0x104,+0xfc(bool),+0x34,+0x70(bool),+0x78(bool); reads 3 coords via +0x38, <<8, -> this+0xec (SetPosition); reads 3 via +0x28 -> this+0x108; [UNCERTAIN] owning class (map/view object with fixed-point position)"
0x10036f36,serialize,C2,sc3_record_load_with_rate,"LOAD: this+0xc/0x10/0x14/0x18 via +0x38; this+0x34/0x38 via +0x40; this+0x3c byte via +0x18; this+0x1c/0x20 via +0x48; this+0x30=0; rate = this+0x2c<0 ? *-1000/this+0x28 : *1000/this+0x24 @10036fed; posts {0x426840a0} via FUN_1002d87b +0x10; load counterpart of 0x10037058"
0x10037058,serialize,C2,sc3_record_save,"SAVE: this+0xc/0x10/0x14/0x18 via +0x88; this+0x34/0x38 via +0x90; this+0x3c byte via +0x68; this+0x2c via +0x88; this+0x1c/0x20 via +0x98; identical offset set to 0x10036f36 (proves stream slot map)"
0x10036802,serialize,C2,sc3_record_deserialize_ctor,"ctor+deserialize: vtbl PTR_FUN_100420a8; reads 3 dwords via param_1 +0x260 -> this+0x14/0x18/0x1c; new(0x14)+FUN_10036c90(param_2) sub-reader x2; validates magic this+8 == -0x21524111 (0xDEADBEEF) @10368e0; on fail writes sentinel 0xdeadbeef and rebuilds; sets bit flags this+6/+7 from a byte"
0x10033e90,serialize,C2,sc3_layer_serialize_arrays,"three fixed arrays via FUN_10034147 accessor + stream +0x38 (uint32 primitive): this+0x78 x12, this+0xa0 x10, this+0xc8(200) x10, then this+0x60 once; tail: this+0x64==0 ? this vtbl +0x48 : FUN_10033885(this-8); [UNCERTAIN] load-vs-save (+0x38 is the read slot but element passed by value)"
0x100194bf,serialize,C2,sc3_object_copy_fields,"field-copy/clone: read string src param_1 +0xc/+0x10 (FUN_10003ae8 GZString, vtbl PTR_LAB_1003c434) -> this +0x38/+0x3c; getters param_1 +0x14..+0x30 -> setters this +0x40..+0x5c (8 dwords); one more +0x34->+0x60 via FUN_1002e254/FUN_1002e348 temp"
0x10008439,S14-ui,C2,sc3_ui_populate_money_list,"populate 3-entry list: for each of param_1+0x48 getters +0x24/+0x30/+0x3c reads int, value = int*1000 - 100000 @1000847e via FUN_1002d8ff +0x94 formatter +0x3c; label via param_1+0x4c +0x14; FUN_1002b2cf builds GZString; set into param_1+0x48 +8 vtbl +0x50 at indices 0,1,2; GZString vtbl PTR_LAB_1003c434"
0x1002cc3b,util-io,C2,sc3_io_read_text_line,"readline: reads 0x28-byte chunks from this+0x28 vtbl +0x38; scans for CR(0x0d)/LF(0x0a); on newline truncates and seeks (+0x30/+0x2c(-1)); appends to GZString local_30 via FUN_10003996; commits to param_1+4 via FUN_1002b360/FUN_10003c6a; returns bool found"
```

### 2. Notable findings (structural)

- **Per-tick timeline entry `0x100278b0`** — the highest-value find. It reads the current date from a sub-object (`this+8` vtable `+0x1e4`), **floors the year to ≥ `0x76c` = 1900** `[CONFIRMED @0x100278f2]`, computes a schedule index `date - 0x5911(22801) + year*0xc(12)` `[CONFIRMED @0x10027992]`, then walks a per-entry `ushort` duration schedule (`this+0xb4..0xb8`, entry stride `0x1c`), advancing a per-entry frame counter (`entry+8`) and storing a remainder or the sentinel `65000` (`entry+10`). This is a date-driven timeline/animation stepper feeding the world/econ-phase layer (`EconomicPhases`, `SIMMISC.md §S1`). The `year*12 + month` math is the standard SC3 month index.

- **Two message-command dispatch tables**: `0x10020cc9` (menu commands `0x32`–`0x36` plus an indexed range `[0x64, this+0x50·0x64)` over a `0x28`-stride array) and `0x1001e836` (mode toggle `0x20`–`0x23`, two mutually-exclusive view layers gated by global `DAT_10049f1c`). Both fan out to the notification service `FUN_1002d87b +0xc` with `0x724a82xx`-family message descriptors (`0x724a82e1`, `0x724a82de`+`0x628d0c45`+`0xbbc/0xbbe`, `0x724a82dd`, `0x724a82da`).

- **Three confirmed save/load serialiser pairs**:
  - Aura layer (S12, GZCLSID `0xc259c02d`, key `0x199627`): `0x10002784` load / `0x100028f1` save. Load clamps `this+0x90 ≤ 0xf` and two fields to service-provided maxima `[CONFIRMED @0x10002819]`.
  - Ordinance flags (S14, GZCLSID `0x41193c3a`/`0xe1193c2a`): `0x10019c53` load / `0x10019d5a` save — persists per-ordinance record `+0x14 → +4` (enabled) and `+5` (leaf) bytes, matching the 40-byte record in `SIMMISC.md §S14`.
  - Generic record (`0x10036f36` load / `0x10037058` save) — identical offset set `{0xc,0x10,0x14,0x18,0x34,0x38,0x3c,0x2c,0x1c,0x20}`, which is what pins down the stream vtable slot map above.

- **Aura tile-propagation, inlined three times byte-identically**: `0x1001370c` = `0x10012040` = `0x10013e71`. Flood-fills a value (`param_1`) across a `2×radius` tile box (radius from `this+8 +0xd4/+0xd8`, `&0xff`), clamped to map bounds, using tile-object QI `0xe0faadc7` and getter/setter `+0x4c`/`+0x48`. Re-entrancy guarded by `this+0x3c`. This is the aura/zone-effect spread mechanic (S12).

- **Ordinance UI view** ctor+windows: `0x100218d2` ctor (subscribes ordinance interface `0xe1193c2a`/`0x41193c3a`, stores rect bounds `+0x2c..+0x38`), opened by `0x10021a06` (window id `0x82e00e34`) and `0x1001ea54` (id `0x42dddc93`) via the GZ window factory `0xa2a79fd0`/`0xa2a79fd1`. `0x1001bc3d` is a sibling fixed-size (500×480) centered window (id `0x42dd813a`, position cached in `DAT_10049f20/24`, valid-flag `DAT_10049f1d`).

- **Serialisation sentinel**: `0x10036802` validates a record magic `this+8 == 0xDEADBEEF` (`-0x21524111`) and writes `0xdeadbeef` on rebuild — a corruption/version guard on a two-part `FUN_10036c90` sub-record.

- **Message-id constants worth registering** (all posted/subscribed in this slice): subscribe/unsubscribe `0x62e8630b`, `0x23b4418f`, `0x6569de54` (paired in `0x10007a59`/`0x10007bb9`); posted `0x724a82e1/de/dd/da`, `0x628d0c45` (channel), `0xbbc`=3004 / `0xbbe`=3006, `0x229a8a90`, `0x624a8240`, `0x426840a0`; service QI ids `0x80f1e6d3→0x40a42f1c`, `0x80199683`, `0x630288e9`/`0x6856f7`.

### 3. Not determined

- **Owning class of the generic serialisers** `0x10036277` (save), `0x100360de` (load), `0x10036802` (ctor), `0x10033e90` (arrays) — no string anchor and no GZCLSID inside the body. `0x100360de`/`0x10036277` touch different `this` offsets from each other, so they are **not** a matched pair; each needs its vtable (`PTR_FUN_100420a8`) resolved via live-Ghidra `.rdata` xref to name the class. Marked `serialize` subsystem provisionally.
- **`0x10033e90` serialisation direction** — it drives the `+0x38` primitive (the *read* uint32 slot) but passes each array element by value, which is the *write* calling form. Deciding load-vs-save requires the resolved type of `FUN_10034147`'s return (pointer-to-value vs pointer-to-pointer). Array sizes 12/10/10 resemble the S10 `BuildingPlacementCosts` block (`SIMMISC.md §S10`), but that link is unconfirmed.
- **`0x100278b0` owning layer** — the per-tick timeline is confidently mechanical, but which layer object hosts it (`this+8` date source, `this+0xb4..0xb8` schedule vector) is not pinned to a named class from the body alone; the `3000/5000/8000` QI keys (`0xf1ec30` group) would need a data-file/string cross-check.
- **`0x10008439` dialog identity** — confirmed it formats three `value*1000 - 100000` money strings into a 3-slot list, but which dialog/panel owns `param_1+0x48`/`+0x4c` is not determined (no anchor in body).

All 25 functions in the slice were read and classified **C2**. No function in the slice was left at C1.
