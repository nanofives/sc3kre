## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1001417a,config-ini,C2,sc3_ini_write_section,"builds two strings via FUN_10015615, opens config mgr this+0x28 vtable 0x44(1), scans lines for '[' section / ';' comment, writes fmt strings s___s__100286d0 and s__s____s_100286c4 via vtable 0x40; parses key names"
0x1000d262,pollution,C2,sc3_pollution_init_layer,"allocs 4 bitfield arrays sized dim*dim/0x20<<2 at this+0x68/0x70/0x6c/0x40 (dim=src vtable 0xcc), zeroes via FUN_1000b772, acquires 7 layer ifaces param_1 vtable 0x11c/0x120/0x150/0x16c/0x13c/0x15c/0x18c into this+0x1c..0x38, IID 0xe1193c2a/0x41193c3a, builds sim obj this+0x3c via FUN_1001b4c5 set interval 100 (vtable0x60), 4 msg strings FUN_1001b24d id 0x16c grp 0x29541f4, cfg 0x2bf0034/0x7e93d9"
0x10018cb0,ui-message,C2,sc3_msg_report_error,"tests (this-8) vtable 0x54 masks 0x100/2/4/8/0x10, builds localized msg FUN_1001b24d ids 0xc6/0xc5/0xc4/0xc7/199 grp 0x82e0074c, emits via param_2 vtable 0x34, final id 0x30, flag 0x200"
0x10001082,tunables,C2,sc3_tune_load_config,"ctor: sets vtables PTR_LAB_100203b0/10020380/10020238/100201f8; if DAT_10028978==0 reads Sys/SC3Tune.INI + Sys/SYS.PAK, keys OptimalPollutionCap->DAT_100281e0, MaxLifespan->DAT_100281e4, DeclineAge->DAT_100281e8 (clamped: e4>=1, e8=e4>>1 if e4<e8); WaterTreatment key; via FUN_1001a7d5/FUN_10017852"
0x1000f771,pollution,C2,sc3_pollution_tick_update,"per-tick: walks linked list **(this+0x74); per node reads coords piVar11[2], queries layer this+0x1c vtable0x78 -> obj IID 0x62fd2588; reads props vtable 0x44/0x4c/0x54/0x3c/0x5c/0x28/0x30/0x20/0x1c/0x10/0x18; area tests FUN_1000f57d; decline pct DAT_1002856c*/100; layer this+0x2c vtable0x5c/0x88; accumulates, average via __aulldiv -> this+0xa4"
0x100017da,render-effect,C2,sc3_effect_draw_sprite_a,"gets 3 mgrs FUN_1001b171 vtable0x138/0x11c/0x120; IID 0xc14f8955 then view IID 0xe0faadc7 at param_1[9]; pos vtable0xf0 (param[6]&0x7ff, >>0xb&0x7ff = 11-bit x/y); draw tags 0x637c0dab/0x43680ca9; 0x7fffffff bbox init"
0x100120f8,render-effect,C2,sc3_effect_draw_sprite_b,"byte-identical to 0x100017da except this-adjustor: param_1[-0xb]/[-2]/[-5] (multiple-inheritance base thunk variant)"
0x10011213,render-effect,C2,sc3_effect_draw_sprite_c,"byte-identical to 0x100017da/0x100120f8, third this-adjustor variant (param_1[-0xb]/[-2]/[-5])"
0x10009295,render-effect,C2,sc3_effect_draw_radius,"IID 0xe223be6c/0xd223be6c; center from param_1[0xc] vtable0xbc; DAT_10028ad8 lookup; draw center<<8; radius 0x14 (20) tiles; per-cell dist = dx*dx+dy*dy, sqrt + _DAT_10021cf0, threshold <0x15 with random FUN_10016fcc(&DAT_10028ac0,10); sets tiles vtable0x94; tags 0x434346e6; calls FUN_10006dec"
0x1000d9ec,pollution-persist,C2,sc3_pollution_save_state,"scans this+0x68 array bounds (dim*dim/0x20), opens writer FUN_1001c7c6/FUN_1001c940 tag 0x206c6e7c/0x2bf0033; writes low/high idx, array slice, param_1, this+0xb0(2),0xb8(2),0xd8(4),0xc8(4),0xc4,0xc0,0xa4,0xc via vtable0x88(scalar)/0x84(buffer)"
0x1000d86a,pollution-persist,C2,sc3_pollution_load_state,"counterpart to 0x1000d9ec: opens reader FUN_1001c5aa/FUN_1001c940 tag 0x206c6e7c/0x2bf0033; reads same fields via vtable0x38(scalar)/0x34(buffer); version gate (3 < local_38) guards this+0xa4/0xc"
0x1001c5aa,serialize,C2,sc3_stream_open_record,"record/chunk reader ctor; vtable PTR_FUN_10024118; reads 3 dwords via param_1 vtable0x260 into this+0x14/0x18/0x1c; creates reader FUN_1001ca28 (0x14 bytes); validates magic this+8 == 0xdeadbeef (-0x21524111); on mismatch resets, sets this+8=0xdeadbeef, retries once"
0x1001a231,persist,C2,sc3_object_save_props,"SAVE: IID 0x80199683 sub-obj; writes its vtable0x14/0x1c/0x24 then this vtable 0x88/0x54/0x60/0xd4/0xd8/0xdc/0x58/0xf8/0x30/0x6c/0x74 via param_2 vtable0x88(int)/0x68(float); bbox this vtable0xb8 -> param_2 0x88 (>>8); this vtable0xb0 -> param_2 0x78"
0x1001a098,persist,C2,sc3_object_load_props,"LOAD counterpart: reads via param_2 vtable0x38(int,ptr)/0x18(byte)/0x28; sets this vtable0x18/0x104/0xfc/0x34/0x70/0x78/0xec/0x108; coords local_14/18/1c <<8 into this vtable0xec"
0x10004340,tile-event,C2,sc3_tile_remove_object,"if this+8: FUN_1000472d then mgr FUN_1001b171 vtable0x234(begin)/0x238(end); coords param_2 vtable0xd0/0xbc; writes 0 into map this+0x2c0[(this+0xc)*y+x]; IID 0xe0faadc7 vtable0x5c -> dec this+0x2c4 (count, floor 0) and this+0x2d0 (sum) by that; IID 0xe14a51f0 branch iterates lists this+0x6c/this+4, FUN_10005488/FUN_10005429"
0x100041ce,tile-event,C2,sc3_tile_add_object,"counterpart to 0x10004340: FUN_1000472d, mgr begin/end 0x234/0x238; coords 0xbc, data 0xd0; IID 0xe0faadc7 vtable0x5c -> writes byte into map this+0x2c0[(this+0xc)*y+x], inc this+0x2c4 count & this+0x2d0 sum; IID 0xe14a51f0 branch: this+0x24 vtable0x38, FUN_100053fd; else FUN_1000366f + FUN_10005451"
0x100152da,io,C2,sc3_stream_read_line,"reads text lines from stream this+0x28 (vtable 0x18=tell,0x1c=size,0x38=read,0x30/0x2c=seek); buffers 0x28(40)-byte chunks into local_5c[44], scans for CR/LF, builds string FUN_10002bdd, returns via FUN_10002d2f; local_12 = read-any flag"
0x10010fb1,query,C2,sc3_tile_query_object,"mgr FUN_1001b171 vtable0x14c/0x11c; layer vtable0x7c lookup(x,y); IID 0xe0faadc7; coords <<8; net-node check local_14 vtable0x1c and [0xf] vtable0x4c; return via vtable0x1c(hit,param_3)"
0x1001bdfb,persist,C2,sc3_object_load_arrays,"iterates FUN_1001c0b2 element accessor over this+0x78 (12), this+0xa0 (10), this+0xc8 (10) then scalar this+0x60, via param_2 vtable0x38; cleanup: this+0x64 flag -> vtable0x48 or FUN_1001b7f0(this-8)"
0x10006593,query,C2,sc3_tile_query_flag,"this+0x3c layer vtable0x11c, vtable0x7c lookup(x,y); IID 0xe0faadc7 vtable0x5c -> bool; this+0x44 layer vtable0x34; this+0x40 layer vtable0x34; this vtable0x1c -> return(flag,param_3)"
0x10006dec,render-effect,C2,sc3_object_sync_position,"IID 0xc14f8955 -> coords vtable0xbc (local_14/local_10); IID 0xe0faadc7 -> id via vtable0x60; DAT_10028adc layer vtable0x1c lookup(id, 0xe0faadc7); IID 0xc14f8955 -> set pos vtable0xf0(x,y); returns obj"
0x100181d7,io,C2,sc3_file_move,"one-time LoadLibraryA(KERNEL32.DLL)+GetProcAddress(MoveFileExA) cached in DAT_10028edc/DAT_10028ed8; uses MoveFileExA(flag 2) with fallback MoveFileA; src/dst paths from param_1/param_2 vtable0x14"
0x10019958,persist,C2,sc3_effect_save_record,"if this+4: writes id (this+4 vtable0x14) via param_2 vtable0x28; this vtable0x88 -> 0x2c; packed pos this+0x10 (x&0x7ff, >>0xb&0x7ff, >>0x16&0xff = 11/11/8) -> vtable0x30; this vtable0xd4 -> 0x34; this+0x10>>0x1e (2-bit) -> 0x38; this+0xc bit24/25 -> 0x3c"
0x10011fbe,persist,C2,sc3_object_save_keyed,"FUN_100189a9 (base save) then keyed props via param_2 vtable0x84: id 0x8351fdf3=this+0x34, 0x8351fdf4=this+0x38, 0x8351fdf5=this+0x3c(ushort), 0x8351fdf6=this+0x50(byte)"
0x1001bec6,persist,C2,sc3_object_save_arrays,"same layout as 0x1001bdfb (this+0x78[12], 0xa0[10], 0xc8[10], scalar 0x60) via param_2 vtable0x88; FUN_1001c0b2 element accessor"
```

## 2. Notable findings

**Per-tick simulate entry — `FUN_1000f771` (0x1000f771).** Walks the intrusive linked list at `**(this+0x74)`; for each agent node it re-reads the tile occupant (layer `this+0x1c`, IID `0x62fd2588`), refreshes cached props into the node (offsets +0x1a,+7,+8,+6,+9), runs neighbourhood checks (`FUN_1000f57d` at radius 1/2/3), applies a **decline percentage tunable `DAT_1002856c` (`x*DAT/100`)** and writes the average back to `this+0xa4` via `__aulldiv`. This is the layer's Simulate. [CONFIRMED @ 0x1000f771]

**Tunable table loader — `FUN_10001082` (0x10001082).** Reads `Sys/SC3Tune.INI` (and `Sys/SYS.PAK`) once (guarded by `DAT_10028978`) and maps named keys to globals:
- `OptimalPollutionCap` → `DAT_100281e0`
- `MaxLifespan` → `DAT_100281e4` (forced `>=1`)
- `DeclineAge` → `DAT_100281e8` (clamped to `DAT_100281e4>>1` if larger)
- `WaterTreatment` key also read.

[CONFIRMED @ 0x10001082] — highest-value tunable find in this slice.

**Generic INI section writer — `FUN_1001417a` (0x1001417a).** Uses format strings `"%s"`/`"%s = %s"` (`s___s__100286d0`, `s__s____s_100286c4`) against the config manager at `this+0x28`, scanning for `[`-section headers and `;`-comments. Companion to the tunable loader above.

**Serialisation pairs (save/load).** Multiple confirmed persist pairs share matched offsets:
- Pollution layer: `FUN_1000d9ec` (save) / `FUN_1000d86a` (load), chunk tags `0x206c6e7c` + `0x2bf0033`, version gate `3 < ver`.
- Object props: `FUN_1001a231` (save, vtable 0x88/0x68/0x78) / `FUN_1001a098` (load, vtable 0x38/0x18/0x28).
- Array object (12/10/10 + scalar): `FUN_1001bec6` (vtable 0x88) / `FUN_1001bdfb` (vtable 0x38).
- Keyed-property save `FUN_10011fbe` uses **property IDs `0x8351fdf3`–`0x8351fdf6`**.
- Effect record save `FUN_10019958` uses **11/11/8-bit packed position** (`&0x7ff`, `>>0xb&0x7ff`, `>>0x16&0xff`) — same packing as the draw functions `FUN_100017da`/`FUN_100120f8`/`FUN_10011213`.

**Record-stream magic — `FUN_1001c5aa` (0x1001c5aa).** Chunk reader validates a header equal to `0xDEADBEEF` (`this+8 == -0x21524111`), retrying once on mismatch. [CONFIRMED @ 0x1001c5aa lines 79-87]

**Message/error dispatcher — `FUN_10018cb0` (0x10018cb0).** Flag-bit (`0x100/2/4/8/0x10`) to message-id (`0xc6/0xc5/0xc4/0xc7/199`, group `0x82e0074c`) mapping, emitted through `param_2` vtable 0x34.

**Interface IIDs observed (COM-like QueryInterface at vtable slot 0):** `0xc14f8955` (position/cell provider), `0xe0faadc7` (tile occupant/view), `0xe14a51f0` (network branch), `0x62fd2588` (pollution-source props), `0x80199683`, `0xe1193c2a`/`0x41193c3a`. Tile add/remove pair `FUN_100041ce`/`FUN_10004340` both maintain the same map buffer `this+0x2c0` indexed `(this+0xc)*y + x`, plus a count `this+0x2c4` and sum `this+0x2d0`.

## 3. Not determined / caveats

- **Save-vs-load direction of `FUN_1001bdfb` (0x1001bdfb) vs `FUN_1001bec6` (0x1001bec6)** — [UNCERTAIN]. Both iterate the identical layout (arrays at +0x78[12], +0xa0[10], +0xc8[10], scalar +0x60). I assigned `FUN_1001bec6` as save (stream vtable 0x88, which is the write slot confirmed in `FUN_1001a231`) and `FUN_1001bdfb` as load (slot 0x38, the read slot confirmed in `FUN_1001a098`). But `FUN_1001bdfb` passes `*piVar3` **by value** to slot 0x38, which is inconsistent with a pointer-taking read call. Missing evidence: the vtable layout of the stream class (decompilation of slot 0x38/0x88 targets, or the `FUN_1001c0b2` return-pointer level) to confirm which member is reader vs writer.
- **Concrete semantic meaning of the four bitfield arrays in `FUN_1000d262`** (offsets +0x68/+0x70/+0x6c/+0x40) — described mechanically only (each `dim²/32` bits). Missing evidence: reads of the accessor functions and the source-layer vtable slots (0xcc/0xa8/0xac) to name what each bitmap represents.
- **`sqrt` threshold constant `_DAT_10021cf0`** in `FUN_10009295` — reported as raw global; its float value is not in the decompiled body (data section not read).

All 25 functions in the slice were read; none left at C1.
