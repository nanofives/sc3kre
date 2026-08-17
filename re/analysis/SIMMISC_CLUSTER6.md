## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x10030fe5,util-fs,C2,sc3_util_move_file,"Loads KERNEL32.DLL + GetProcAddress(MoveFileExA) once (cached DAT_1004a078/DAT_1004a07c); calls MoveFileExA(src,dst,2=MOVEFILE_COPY_ALLOWED), MoveFileA fallback. src/dst from param_1/param_2 vtbl+0x14 string accessors [CONFIRMED @0x10030fe5]"
0x1003599a,serialize,C2,sc3_misc_write_record,"thiscall writer: param_2 vtbl slots 0x28/0x2c/0x30/0x34/0x38/0x3c fed from this+0x10 packed uint (x:11|y:11|z:8|top2) + this+0xc byte flags; guarded on this+0x4!=0 [CONFIRMED @0x1003599a]"
0x10033f5b,serialize,C2,sc3_misc_write_arrays,"thiscall writer: FUN_10034147 indexes 3 arrays this+0x78[0..11],this+0xa0[0..9],this+0xc8[0..9], each elem *piVar2 written via param_2 slot0x88; then scalar this+0x60; short-circuits on write-fail [CONFIRMED @0x10033f5b]"
0x10025dee,message-dispatch,C2,sc3_world_handle_command,"dispatch on param_2 msg id: 0x20/0x3a/0x3c. 0x20->FUN_100320b1()slot0x34()->slot0x14(0x15,0,0,0,0)+FUN_1002d8d3()slot0x44(0xd,...); 0x3a->this+0xc slot0x5c(this+0x24)+FUN_10025ed6; 0x3c->build GUID{0x724a82de,0x628d0c45,0xbbe,0}+FUN_1002d87b()slot0xc [CONFIRMED @0x10025dee]"
0x100290b4,config-load,C2,sc3_misc_load_properties,"fastcall: param_1[0x16] property-DB slot0x14(key,type=0xf1ec30,dest) for keys 3000,5000,8000 into this+0x17,+0x18,+0x19; on all-ok sets byte this+0x71=1, conditional this slot0x40(this+0x1b) gated by byte this+0x1c; releases (slot8) on failure [CONFIRMED @0x100290b4]"
0x10002c4f,S12-aura,C2,sc3_aura_query_interface,"GZCOM QueryInterface: IIDs 0x5e4->this+0x2c, 0x6c6f42->this+0x24, 0x215b29c5->this+0x28, 0x4259c018->this+0x1c, {0x58d,0x206c6e7c,0x81c0cb7c}->this+0x20, else FUN_100012dc (aura base QI); AddRef via slot4 [CONFIRMED @0x10002c4f]"
0x10004f40,S10-budget,C2,sc3_budget_scaled_lookup,"thiscall gated on byte this+0x3c; this+0x44 obj slot0x34(p1,p2,&b) then this slot0x1c()->obj; this+0x40 obj slot0x34(p1,p2,&b2); returns obj slot0x1c( (obj slot0x14(p3) * (0x7f - b2)) / 0x100 ) -- value scaled by (127-x)/256 [CONFIRMED @0x10004f40]"
0x10028fbb,init,C2,sc3_misc_init_layer,"calls base FUN_10036e38; acquires service 0x80f1e6d3 via this+0x40 slot0x1b8; queries key 0x40a42f1c into this+0x58 via ptr slot0; on ok inits this+0x48=0,0x4c=0,0x50=1,0x54=1,0x6c=0,byte0x71=0,ret1; else FUN_10036e79 [CONFIRMED @0x10028fbb]"
0x100283d1,gzcom-qi,C2,sc3_misc_query_interface_283d1,"QueryInterface: IID 1 & 0x811bdde9->this; {0x58d,0x206c6e7c,0x81c0cb7c}->this+4; 0x6c6f42->this+8; else fail; AddRef slot4 [CONFIRMED @0x100283d1]"
0x10029186,serialize,C2,sc3_misc_write_fields,"base FUN_10037058 then writes *(this+0x48),*(this+0x4c),*(this+0x50),*(this+0x54) via param_2 slot0x88 (write-dword), short-circuit on fail [CONFIRMED @0x10029186]"
0x10018c2a,gzcom-qi,C2,sc3_misc_query_interface_18c2a,"QueryInterface: {1,0x58d,0x206c6e7c,0x81c0cb7c,0xc2910e7d}->this; 0x6c6f42->this+4; else fail; AddRef slot4 [CONFIRMED @0x10018c2a]"
0x10029133,deserialize,C2,sc3_misc_read_fields,"base FUN_10036f36 then reads into this+0x48,+0x4c,+0x50,+0x54 via param_2 slot0x38 (read-dword, passed by address), short-circuit on fail [CONFIRMED @0x10029133]"
0x1001aee1,S14-ordinance,C2,sc3_ordinance_query_interface,"QueryInterface: 0x41193c3a->this; {1,0x58d,0x206c6e7c,0x81c0cb7c}->this+4; else fail; AddRef slot4. IID 0x41193c3a ties to ordinance CLSID 0x41193c4b (ctor 0x10019a2b) [CONFIRMED @0x1001aee1]"
0x1001b47a,S14-ordinance,C2,sc3_ordinance_query_interface_b47a,"QueryInterface: {1,0x58d,0x206c6e7c,0x81c0cb7c,0xd2ed2a04}->this else *param_2=0 fail; AddRef slot4 [CONFIRMED @0x1001b47a]"
0x10019acf,S14-ordinance,C2,sc3_ordinance_get_iid,"6-byte stub: return 0xe1193c2a (ordinance interface IID) [CONFIRMED @0x10019acf]"
0x100051e7,S10-budget,C2,sc3_budget_get_iid,"6-byte stub: return 0xa11bcc54 (budget interface IID; budget CLSID 0xc11bcc75) [CONFIRMED @0x100051e7]"
0x1001486e,gzcom-iid,C2,sc3_misc_get_iid_82937b60_deals,"6-byte stub: return 0x82937b60 (NeighborDeals island, ctor 0x10014759) [CONFIRMED @0x1001486e]"
0x100190e1,gzcom-iid,C2,sc3_misc_get_iid_82937b60_ord,"6-byte stub: return 0x82937b60 (ordinance island); same IID as 0x1001486e => shared service interface id [CONFIRMED @0x100190e1]"
```

## 2. Notable findings

**A coherent 4-method persistable layer at 0x10028-0x10029 (highest-value cluster).** Four functions in the slice operate on the *same object* with fields at 0x48/0x4c/0x50/0x54 (four dwords), 0x58 (resource ref), 0x6c, byte 0x71:
- **Init** `0x10028fbb` — acquires service GUID `0x80f1e6d3`, reads resource key `0x40a42f1c` into `this+0x58`, sets defaults `{0x48=0,0x4c=0,0x50=1,0x54=1}`.
- **Save** `0x10029186` — writes those four dwords out (writer slot `0x88`).
- **Load** `0x10029133` — reads those four dwords in (reader slot `0x38`).
- **Tuning-load** `0x100290b4` — loads property keys **3000 / 5000 / 8000** (type `0xf1ec30`) into `this+0x17..0x19`.

The `{0,0,1,1}` default pattern for a 4-dword group is consistent with an (x0,y0,x1,y1) rect / range default. `[UNCERTAIN]` which registered class this is — it sits past the World ctor (`0x1002653f`) and is not one of the 5 anchored classes in `SIMMISC.md`; no string anchor reached from these bodies.

**A message/command dispatcher `0x10025dee`** keyed on ids `0x20`, `0x3a`, `0x3c` — a per-command handler (not a per-tick Simulate). Id `0x3c` constructs an inline GZ GUID `{0x724a82de, 0x628d0c45, 0xbbe, 0}` and dispatches it via `FUN_1002d87b()` slot `0xc`. World-region address; classified S1 by proximity, `[UNCERTAIN]` on exact class.

**Two array/record serializers**, `0x1003599a` and `0x10033f5b`, both write through a stream interface (`FUN_10036e38`/`FUN_10036f36`/`FUN_10037058` are the base read/write/init helpers shared by the whole module). `0x10033f5b` serialises three arrays of sizes **12, 10, 10** at `this+0x78 / +0xa0 / +0xc8` plus a scalar at `this+0x60`. `0x1003599a` writes a **packed coordinate** at `this+0x10` unpacked as `x:11 | y:11 | z:8 | top-2` bits — a tile/cell coordinate serialisation.

**Interface-ID (IID) getter stubs** — five distinct GZCOM identity constants recovered:
- `0xa11bcc54` budget interface (`0x100051e7`)
- `0xe1193c2a` ordinance interface (`0x10019acf`)
- `0x82937b60` a **shared** service IID returned by two different classes (`0x1001486e` NeighborDeals + `0x100190e1` ordinance) — evidence of a common cross-layer service interface.

**QueryInterface family** — five GZCOM `QueryInterface` implementations (`0x10002c4f`, `0x100283d1`, `0x10018c2a`, `0x1001aee1`, `0x1001b47a`) share a base-IID set `{1, 0x58d, 0x206c6e7c, 0x81c0cb7c}` (the universal GZCOM base interfaces), each adding its own class IID and returning embedded sub-interface pointers at fixed offsets. `0x1001aee1` binds cleanly to the ordinance CLSID (`0x41193c4b`), confirming ordinance identity for that island.

**`0x10004f40` budget-island scaled lookup** — computes `value * (127 - x) / 256`, a coverage/effect attenuation formula (`0x7f - x` over `0x100`), gated by byte flag `this+0x3c`, pulling two sub-values through vtable `0x34` accessors. Mechanically a scaled effect query; `[UNCERTAIN]` exactly which budget/aura quantity (no string reached).

## 3. Not determined

- **Subsystem of the 0x10028-0x10029 persistable cluster** (`0x10028fbb`, `0x100290b4`, `0x10029133`, `0x10029186`): bodies are fully described (C2) but the owning registered class is unresolved. Missing: the `.rdata` vtable-to-factory xref, or a string/INI-section anchor reached from these offsets. None of the property keys (3000/5000/8000) or service GUID (`0x80f1e6d3`) resolve to a name in the text export.
- **Exact class for the two 0x1003xxx serializers** (`0x1003599a`, `0x10033f5b`): confirmed as writers with concrete field layouts, but which object owns the 12/10/10 arrays or the packed coordinate is not determined. Missing: caller/vtable-slot xref from live Ghidra.
- **Meaning of the numeric IIDs** `0x82937b60`, `0xd2ed2a04` (`0x1001b47a`), `0xc2910e7d` (`0x10018c2a`), `0x40a42f1c`/`0x80f1e6d3` (`0x10028fbb`): recovered as raw constants only — no symbol maps these to a named GZCOM interface. iOS export could name `0x82937b60` if it survives as a class-registration constant `[iOS-HINT, unverified]`; struct offsets here must not be transferred from iOS.
- **`0x10004f40` quantity**: formula confirmed, semantic label (which tax/coverage value) not determined — missing a string or a named caller.

All 18 functions in the slice were read and classified **C2** (bodies read, callees identified, mechanically described, named). No C3/C4 claimed.
