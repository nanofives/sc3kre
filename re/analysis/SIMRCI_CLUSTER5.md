## SIMRCI.DLL — toolkit-necessary C0 slice (25 functions), classified

A single coherent picture emerged: this slice is dominated by (a) the **RCI demand-graph variable machinery** (register/create/fetch simulator variables into a shared data service), (b) **stream serializers**, (c) **GZCOM QueryInterface dispatch tables**, and (d) **network/zone adjacency probes**. All 25 were body-read; every one has its callees and constants identified, so all are rated **C2**.

### 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100159a5,rci-demand,C2,sc3_ind_register_demandvars,"[CONFIRMED @ 0x100159a5] QueryService(0x80f1e6d3)->QI(0x40a42f1c) into this+8; CreateVar(8000,0xf1ec30)->this+0x10 SetMax(2000)/SetMin(0xfffff830=-2000); CreateVar(0x1f41=8001)->this+0x14 SetMax(0x7fffffff)/SetMin(0x80000000) SetValue(DAT_10057674=IndLayer tuning)"
0x1000e842,rci-demand,C2,sc3_com_register_demandvars,"[CONFIRMED @ 0x1000e842] same shape as 0x100159a5; CreateVar(5000)->this+0xc range[-2000,2000]; CreateVar(0x1389=5001)->this+0x10 range[INT_MIN,INT_MAX] SetValue(DAT_100574f8=ComLayer tuning)"
0x10017b34,rci-demand,C2,sc3_ind_update_demandvar,"[CONFIRMED @ 0x10017b34] gated on this+0xc; QueryService(0x80f1e6d3)->QI(0x40a42f1c); GetVar(8000,0xf1ec30,this+0xac); if this+0xca==0 calls svc vtbl+0x1e4 then FUN_10018843(this,count)"
0x1000fa89,rci-demand,C2,sc3_com_fetch_demandvar,"[CONFIRMED @ 0x1000fa89] QueryService(0x80f1e6d3)->QI(0x40a42f1c); GetVar(5000,0xf1ec30,param+0x7c); Release"
0x10004669,rci-demand,C2,sc3_com_fetch_demandvar2,"[CONFIRMED @ 0x10004669] GetVar(0x1389=5001,0xf1ec30,param+0x44) via 0x80f1e6d3/0x40a42f1c"
0x10028c49,rci-demand,C2,sc3_res_fetch_demandvar,"[CONFIRMED @ 0x10028c49] GetVar(3000,0xf1ec30,param+0x7c) via 0x80f1e6d3/0x40a42f1c; service handle read from param_1[0x18]"
0x1002c941,rci-demand,C2,sc3_ind_fetch_demandvar2,"[CONFIRMED @ 0x1002c941] GetVar(0x1f41=8001,0xf1ec30,param+0x44) via 0x80f1e6d3/0x40a42f1c; service from param_1[0xe]"
0x10032479,gzcom-interface,C2,sc3_layer_query_interface,"[CONFIRMED @ 0x10032479] GUID->subobject map: 0x215b29c5->+0x38, 0x5e4->+0x3c, 0x6c6f42->+0x34, 0x206c6e7c/0x58d->+0x14, 0x80902c70->+0x10, 0x81c0cb7c->+0x14, 0xc171b663->FUN_10043106(+0x18,-0x3e8e499d); default FUN_1002e9ab; AddRef via vtbl+4"
0x1001d748,gzcom-interface,C2,sc3_layer_query_interface_b,"[CONFIRMED @ 0x1001d748] GUID->subobject: 0x5e4->+0x28, 0x215b29c5->+0x24, 0x6098556b->+0x1c, 0x81c0cb7c(-0x7e3f3484)/0x58d/0x206c6e7c->+0x20; default FUN_1002e9ab; AddRef vtbl+4"
0x1000ebca,serial,C2,sc3_rci_serialize_pair_20ec9849,"[CONFIRMED @ 0x1000ebca] EH-guarded; builds key{tag=0x206c6e7c, clsid=0x20ec9849, 0} via FUN_1000ecb4; FUN_1003fd8f/FUN_1003ff09 open stream; writes subobjects this+0xc & this+0x10 (vtbl+0x20 fetch, +0x1c serialize) gated on stream vtbl+0x88"
0x10015c80,serial,C2,sc3_rci_serialize_pair_a106cf3d,"[CONFIRMED @ 0x10015c80] byte-identical to 0x1000ebca except clsid=0xa106cf3d and members this+0x10 & this+0x14"
0x1004361d,serial,C2,sc3_serial_write_shortvec_record,"[CONFIRMED @ 0x1004361d] stream=param_2; writes this+4(vtbl+0x70 byte), this+8(+0x88), this+0xc(+0x68 bool), this+0x10/0x18/0x14/0x1c/0x20(+0x98); then std::vector<short> at this+0x24..this+0x28 (count=(end-begin)>>1) each via +0x78; then this+0x30/0x34/0x38(+0x98)"
0x10042cf8,serial,C2,sc3_serial_write_record,"[CONFIRMED @ 0x10042cf8] writes this+0xc/0x10/0x14/0x18(+0x88 int32), this+0x34/0x38(+0x90), this+0x3c(+0x68 byte), this+0x2c(+0x88), this+0x1c/0x20(+0x98) via stream param_2, short-circuit on each"
0x100421f9,serial,C2,sc3_serial_write_arrays3,"[CONFIRMED @ 0x100421f9] writes 3 arrays via FUN_100424b0 indexer: this+0x78[12], this+0xa0[10], this+0xc8[10] each element via stream vtbl+0x38, then this+0x60; cleanup branches on this+0x64 (vtbl+0x48 vs FUN_10041bee(this-8))"
0x100422c4,serial,C2,sc3_serial_write_arrays3_b,"[CONFIRMED @ 0x100422c4] same 12/10/10 arrays + this+0x60, written via stream vtbl+0x88 (dereferences *(*piVar2)); no trailing cleanup branch"
0x1003d43c,serial,C2,sc3_agent_write_descriptor,"[CONFIRMED @ 0x1003d43c] writer param_2 typed setters: +0x28(subobj this+4 vtbl+0x14), +0x2c(this vtbl+0x88); +0x30 unpacks packed coord this+0x10 as (x=&0x7ff, y=>>0xb&0x7ff, z=>>0x16&0xff); +0x34(vtbl+0xd4), +0x38(this+0x10>>0x1e = top 2 bits), +0x3c(this+0xc bit24/bit25 flags)"
0x1001cd8f,serial,C2,sc3_grid_load_rescale,"[CONFIRMED @ 0x1001cd8f] reader param_2 vtbl+0x14(0x100) opens tagged grid, +0x24(0x100) returns dim; nested loop reads cells via +0x18(0x100,i,j,&b); rescales b = raw*1000/0x9c4(2500), clamps 0->1; writes doubled grid via (this-0x20) vtbl+0x38(i*2,j*2,...); error path (this-0x20)+0x30"
0x10003b30,zone-network,C2,sc3_net_check_neighbor,"[CONFIRMED @ 0x10003b30] bounds-check current (this+0x48 vtbl+0x4c/0x50); neighbor by dir param_3 (0=x-1,1=y+1,2=x+1,3=y-1); this+0x3c vtbl+0x6c in-bounds/+0x7c getcell; QI(0xe0faadc7)->vtbl+0x60->QI(0x22002d06)->vtbl+0xc4; returns 1 iff ==2"
0x10003c30,zone-network,C2,sc3_net_classify_neighbor,"[CONFIRMED @ 0x10003c30] like 0x10003b30 but 3-state: same dir table, same QI chain 0xe0faadc7/0x22002d06, vtbl+0xc4==2->2, ==1->1, else 0"
0x1002b225,zone-scoring,C2,sc3_zone_score_region,"[CONFIRMED @ 0x1002b225] FUN_1002bb88 builds region from param_2 rect; this+0x3c vtbl+0x84(region,10,buf,&count,0) queries <=10 objects; per obj: type=vtbl+0x88, val=vtbl+0xd4&0xff; if type==param_3 *acc+=val*2 else *acc-=val; then rect scan this+0x44 vtbl+0x34(x,y,&b), +1 per tile b==0x0e"
0x100200eb,valve-grid,C2,sc3_valve_query_cell,"[CONFIRMED @ 0x100200eb] gated on this+0x40; this+0x40 vtbl+0x34(x,y,&b) reads cell; if b!=0 this+0x3c vtbl+0x34(x,y,&b2); this vtbl+0x1c()->obj; obj vtbl+0x14(param_3 float) ftol() obj vtbl+0x1c(result)"
0x1003f48e,layer-init,C2,sc3_layer_init_view,"[CONFIRMED @ 0x1003f48e] this+4=FUN_10039bdb(); this+8=param_1(AddRef); QI via +0x94->this+0xc, +0x8c->this+0x10; FUN_1003cf3b singleton dims vtbl+0xd0/+0xcc -> this+0x28=(h-1)*0x100, this+0x24=w*0x100-0x100 (0x100=tile subpixel); +0x15c->this+0x14; QI(0x22b66d3d)->register via this+8 vtbl+0x58; this+0x10 vtbl+0x38(0,0x23); this vtbl+0x34; this+8 vtbl+0x5c"
0x10025d41,layer-init,C2,sc3_layer_init_services,"[CONFIRMED @ 0x10025d41] FUN_10042ad8 base init; QueryService(0x80f1e6d3)->QI(0x40a42f1c)->this+0x44; QueryService(0xc106c4f5)->QI(0x4106c508)->this+0x48; FUN_10042b19 cleanup on fail"
0x1002ac8a,layer-init,C2,sc3_layer_connect_model,"[CONFIRMED @ 0x1002ac8a] from city root param_1: vtbl+0x11c->this+0x34, +0x138->this+0x38, +0x14c->this+0x3c; QueryService(0x1fd7a8c)->QI(0xc1fd7a96)->this+0x40; returns this+0x40!=0"
0x1003bfb2,io-util,C2,sc3_io_rename_file,"[CONFIRMED @ 0x1003bfb2] lazy GetProcAddress(""MoveFileExA"") from KERNEL32.DLL cached in DAT_10058830/34; MoveFileExA(src,dst,2=MOVEFILE_COPY_ALLOWED) with fallback to MoveFileA; src/dst from param vtbl+0x14 (path getters)"
```

### 2. Notable findings

**A. The RCI demand-graph variable table (highest value).** Seven functions in this slice operate one shared subsystem: a **simulator-variable / graph service** reached by `QueryService(0x80f1e6d3)` then `QueryInterface(0x40a42f1c)`. On that interface, **vtbl+0x10 = CreateVar(id, subtype, &out)**, **vtbl+0x14 = GetVar(id, subtype, &out)**, and on a returned variable **+0x50 = SetMax, +0x54 = SetMin, +0x58 = SetValue**. The subtype constant is always `0xf1ec30`. The variable-id assignment falls out cleanly and maps to the three RCI sub-layers:

| RCI layer | var ids | range | init value | register fn | fetch fn(s) |
|---|---|---|---|---|---|
| Res | 3000 | — | — | (not in slice) | 0x10028c49 |
| Com | 5000 / 5001 (0x1389) | [-2000,2000] / [INT_MIN,INT_MAX] | `DAT_100574f8` (ComLayer tuning) | 0x1000e842 | 0x1000fa89 / 0x10004669 |
| Ind | 8000 / 8001 (0x1f41) | [-2000,2000] / [INT_MIN,INT_MAX] | `DAT_10057674` (IndLayer tuning) | 0x100159a5 | 0x10017b34 / 0x1002c941 |

The `DAT_100574f8` / `DAT_10057674` seeds are exactly the ComLayer/IndLayer tuning globals recorded in `SIMRCI.md`. So the "-2000..+2000" variable is the **RCI demand value** and the INT_MIN..INT_MAX variable is an uncapped accumulator, both seeded from `.ini` tunables. `[iOS-HINT]` these are the R/C/I demand graph series (`goValveLayer` demand), but the id→layer binding above is confirmed SC3-side by the tuning-global cross-link, not the iOS names. This is the concrete bridge from the demand indicator UI to the tunables map — a P2 modding deliverable.

**B. Two GZCOM QueryInterface dispatch tables** — `0x10032479` and `0x1001d748`. Both are hand-written `GetInterface` switches mapping interface GUIDs to embedded subobject offsets, falling back to `FUN_1002e9ab` (base QI). Shared GUIDs recur across both and across the serializers: **`0x206c6e7c`, `0x81c0cb7c`, `0x215b29c5`, `0x5e4`, `0x58d`**. These are SIMRCI-internal interface IDs and belong in `GZCOM_INTERFACE_CATALOGUE.md`. `0x206c6e7c` also appears as the persist-key tag in the serializers (finding C), so it doubles as a class/type tag.

**C. Save/load serialization cluster.** `0x1000ebca` and `0x10015c80` are a matched pair that build a 3-word persist key `{tag=0x206c6e7c, GZCLSID, 0}` (via `FUN_1000ecb4`), open a stream (`FUN_1003fd8f`/`FUN_1003ff09`), and serialize two member subobjects. The embedded GZCLSIDs **`0x20ec9849`** and **`0xa106cf3d`** are two of the 37 registered factory class-ids from `SIMRCI.md` (→ `FUN_1003669e` and `FUN_100366d0`) — this pins two more of the previously-unbound layer class-ids to concrete serialized types. `0x1004361d` / `0x10042cf8` / `0x100421f9` / `0x100422c4` / `0x1003d43c` are the field-level writers; `0x1004361d` notably serializes a `std::vector<short>` (`this+0x24..0x28`, count `(end-begin)>>1`).

**D. `sc3_grid_load_rescale` (0x1001cd8f)** reads a data grid tagged `0x100`, **rescales every cell by `raw*1000/2500` (×0.4) with a 0→1 clamp**, and writes into a **2×-resolution** grid (`i*2, j*2`). This is a confirmed data-map load-and-upscale — a format-relevant transform (the 2500 divisor and doubling are exact).

**E. Zone/network adjacency probes** `0x10003b30` / `0x10003c30` share a direction table (**0=x−1, 1=y+1, 2=x+1, 3=y−1**) and a QI chain `0xe0faadc7 → (vtbl+0x60) → 0x22002d06 → (vtbl+0xc4)` that classifies the neighbor cell's occupant (returns 1 or 2). `0x1002b225` (`sc3_zone_score_region`) is a region desirability score: matching-type objects weight `+2×val`, others `−val`, plus `+1` per tile of type `0x0e`.

### 3. Not determined

- **No function in the slice was left unclassified.** All 25 are C2.
- **Owning class per function is partial.** The demand-var fetch/register functions are bound to Res/Com/Ind by variable-id + tuning-global evidence, but the serializers (`0x1004361d`, `0x10042cf8`, `0x100421f9`, `0x100422c4`, `0x1003d43c`) are named by mechanics only — I cannot prove which layer/agent struct each `this` is without the vtable→ctor data xref (same live-Ghidra gap flagged in `SIMRCI.md` for the valve class). Missing evidence: a data xref from each function to the vtable that installs it.
- **The recurring interface GUIDs** (`0x206c6e7c`, `0x81c0cb7c`, `0x215b29c5`, `0x5e4`, `0x58d`, `0x6098556b`, `0x80902c70`, `0x6c6f42`) are confirmed as interface/type ids by their use in the two QI dispatchers, but their **named semantics are undetermined** — resolving them needs the GZCOM interface catalogue or an iOS-side GUID match (not attempted here). Reported as raw hex per NO-GUESSING.
- **`FUN_10017b34`'s cadence** (per-tick vs on-demand) is not determined; it is gated on `this+0xc`/`this+0xca` flags and calls `FUN_10018843`, but no caller edge in the export proves it is the Simulate entry. Missing evidence: a caller from a tick/EndOfMonth dispatch.

No per-tick `Simulate` entry point and no message-id dispatch table appear in this particular 25-function slice; the closest structural finds are the demand-var updater (0x10017b34) and the two QueryInterface tables.
