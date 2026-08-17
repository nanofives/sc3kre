## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1002a296,disaster-persistence,C2,sc3_dstr_move_file,"one-time GetProcAddress MoveFileExA from KERNEL32.DLL (cached DAT_1003acf8/DAT_1003acfc); MoveFileExA(src,dst,2=MOVEFILE_COPY_ALLOWED) else MoveFileA fallback; src=param_1 vtable+0x14 path, dst=param_2 vtable+0x14 path [CONFIRMED @ 0x1002a296]"
0x1001ce14,disaster-class,C2,sc3_dstr_cls_deactivate_a,"guarded flag this+0xc; deregisters callback FUN_1001cec9 from layer this+0x60 (vtable[0x24]+0xf0); FUN_1000f3bf lock-dec; releases this+0x64; sends msg id 0xe5 (layer+0x44 slot+0x14, mode 2); msg-server(FUN_10022eeb) UNSUBSCRIBE +0x18 ids 0x6491d942,0x6491d943,0x6491d944,0x6491d945 [CONFIRMED @ 0x1001ce14]"
0x10019887,disaster-class,C2,sc3_dstr_cls_deactivate_b,"guarded flag this+0xc; FUN_1001820a lock-dec on layer this+0x10; releases this+0x14 (vtable+0x40); sends tag 0x4a twice (modes 5,4) to layer[0x64]+0x14; msg-server UNSUBSCRIBE +0x18 ids 0x3092d3c,0x33092d3c,0x43092d3c,0x53092d3c,0x625ec00b [CONFIRMED @ 0x10019887]"
0x1002df4d,disaster-serialize,C2,sc3_dstr_cls_write_state,"__thiscall(this,_,writer); writer setter slots +0x28/+0x2c/+0x30/+0x34/+0x38/+0x3c; packs this+0x10 word as x=&0x7ff, y=(>>0xb)&0x7ff, z=(>>0x16)&0xff, hi=(>>0x1e); flags from this+0xc bits 0x18/0x19; returns this[4]!=0 [CONFIRMED @ 0x1002df4d]"
0x10008c42,disaster-class,C2,sc3_dstr_spawn_effect,"__thiscall; queries service via this+0x7c(vtable+0x1c) with GUID 0xe0faadc7; instantiates class 0xc14f8955 (local_8 vtable[0]); inits new obj (vtable+0xf0)(param_1,param_2), (+0xa0)()->(+0x24)(param_3); releases; this+0x7c vtable+0x58 finalize [CONFIRMED @ 0x10008c42]"
0x100116a0,disaster-class,C2,sc3_dstr_cls_deactivate_c,"guarded flag this+0xc (cleared first); FUN_1000f3bf lock-dec layer this+0x60; releases this+0x64; sends msg id 0xed (layer+0x44 slot+0x14, mode 2) if flag this+0x2c; msg-server UNSUBSCRIBE +0x18 ids 0x625ec00b,0x425ec00b,0x525ec00b [CONFIRMED @ 0x100116a0]"
0x1001b3a9,disaster-ufo,C2,sc3_dstr_ufo_select_target,"__thiscall visitor; hit-test layer this+0x10(vtable[0x40]+0x7c)(param_1,param_2,&param_2); classifies bldg via FUN_10019c66 (P7PFUFO_Swarm table); if class==0 AND this+0x6c<DAT_10039ecc: inc this+0x6c, create class 0x621cda33 (layer[0x20]+0x34), FUN_10005e59 add-node [CONFIRMED @ 0x1001b3a9]"
0x10012133,disaster-class,C2,sc3_dstr_add_target_at_tile,"__thiscall visitor; hit-test layer this+0x60(vtable[0x38]+0x7c)(param_1,param_2,&param_2); create class 0x621cda33 (layer[0x1c]+0x34); FUN_10005e59 add-node; inc counter this+0x70 on success [CONFIRMED @ 0x10012133]"
0x10017114,disaster-class,C2,sc3_dstr_cls_subscribe_msgs,"guarded flag this+0x5d; sets flag; msg-server(FUN_10022eeb) SUBSCRIBE +0x14 ids 0x247e319d,0xc2a4e25b,0x620effde; target = this+8-or-NULL idiom [CONFIRMED @ 0x10017114]"
0x1001763f,disaster-class,C2,sc3_dstr_cls_unsubscribe_msgs,"inverse of 0x10017114; guarded flag this+0x5d; clears flag; msg-server UNSUBSCRIBE +0x18 same ids 0x620effde,0x247e319d,0xc2a4e25b [CONFIRMED @ 0x1001763f]"
```

---

## 2. Notable findings (structural)

**Message-subscription registrar found — `FUN_10022eeb`.** A cached singleton (`DAT_1003ac7c`) [CONFIRMED @ 0x10022eeb]. Its vtable `+0x14` = subscribe-to-message-id, `+0x18` = unsubscribe. The `target` argument is always the `-(uint)(this!=0) & (this+8)` idiom (the object's message-sink sub-interface at `this+8`). This is the highest-value structural find in the slice: a concrete message-id dispatch/subscription table for the disaster classes.

**A matched subscribe/unsubscribe pair for one disaster class** [CONFIRMED @ 0x10017114, 0x1001763f]: both keyed on flag `this+0x5d`, both touching the same three message ids `0x247e319d`, `0xc2a4e25b`, `0x620effde`. This is the enable/disable ("hook into the sim" / "unhook") pair for one class's event notifications.

**Message ids each disaster class listens for** (from the four teardown/deactivate methods — the ids it unsubscribes are the ids it had subscribed) [CONFIRMED]:
- `sc3_dstr_cls_deactivate_a` @0x1001ce14 → `0x6491d942`, `0x6491d943`, `0x6491d944`, `0x6491d945` (contiguous block of 4).
- `sc3_dstr_cls_deactivate_b` @0x10019887 → `0x3092d3c`, `0x33092d3c`, `0x43092d3c`, `0x53092d3c`, `0x625ec00b`.
- `sc3_dstr_cls_deactivate_c` @0x100116a0 → `0x625ec00b`, `0x425ec00b`, `0x525ec00b`.
- Subscribe pair @0x10017114/0x1001763f → `0x247e319d`, `0xc2a4e25b`, `0x620effde`.

**Save/serialize method — `FUN_1002df4d`** [CONFIRMED @ 0x1002df4d]. Writes a disaster instance's state to a stream (`writer` = `param_2`, sequential setter slots `+0x28…+0x3c`). Reveals the **packed position word at `this+0x10`**: `x = word & 0x7ff` (11 bits), `y = (word >> 0xb) & 0x7ff` (11 bits), `z = (word >> 0x16) & 0xff` (8 bits), `hi = word >> 0x1e` (top 2 bits). Two boolean flags come from `this+0xc` bits `0x18`/`0x19` (byte at `this+0xf`). This is the per-instance record layout for the disaster save format.

**Disaster-instance node class id `0x621cda33`** [CONFIRMED @ 0x1001b3a9, 0x10012133]. Two per-tile visitor callbacks both instantiate this class (via a layer sub-interface `+0x34`) and insert it into a collection at `this+0x6c`/`this+0x70` through `FUN_10005e59` (which `operator_new(0x40)` + `FUN_1000653a` builds a 0x40-byte node, `[CONFIRMED @ 0x10005e59]`). `0x621cda33` is the "spawn one disaster instance at this tile" class.

**Spawn/factory method — `FUN_10008c42`** [CONFIRMED @ 0x10008c42]. Two GUIDs: acquires a service `0xe0faadc7` (via ordinance/sim layer `this+0x7c`, vtable `+0x1c`), then instantiates class `0xc14f8955`, initialises it `(vtable+0xf0)(param_1, param_2)` and `(+0xa0)()→(+0x24)(param_3)`. A create-and-configure of an effect object.

**Two class families by layer offset** [CONFIRMED]: one keeps its owning layer pointer at `this+0x60` (`0x1001ce14`, `0x100116a0`, `0x10012133`) and one at `this+0x10` (`0x10019887`, `0x1001b3a9`). The `+0x60` family and `+0x10` family are distinct disaster classes.

**UFO tie via `FUN_10019c66`** [CONFIRMED @ 0x1001b3a9→0x10019c66]: the target-selection visitor classifies buildings against tables anchored at `DAT_10039efc/f08/f0c` and the string `P7PFUFO_Swarm` (`s_P7PFUFO_Swarm_10039f10`), returning categories 1–4, gated by max-count tunable `DAT_10039ecc`. This makes `0x1001b3a9` a UFO-attack target picker. The subsystem tag `disaster-ufo` for `0x1001b3a9` rests on this string/table linkage.

**File-move persistence util — `FUN_1002a296`** [CONFIRMED @ 0x1002a296]. Runtime-resolves `MoveFileExA` from `KERNEL32.DLL` (cached in `DAT_1003acfc`, one-shot guard `DAT_1003acf8`); uses flag `2` (`MOVEFILE_COPY_ALLOWED`) and falls back to `MoveFileA` if the export is absent (and permanently downgrades: on a successful `MoveFileA` fallback it nulls `DAT_1003acfc`). This is the atomic save-file replace primitive.

---

## 3. Not determined

- **No per-tick / `Simulate` entry point is present in this slice.** The 10 functions are subscribe/unsubscribe, teardown, serialize, spawn, and two tile-visitors — no periodic-update method. Missing evidence: the class vtables' update slot (would need the `PTR_LAB_*` vtable dumps from §2 of `SIMDSTR.md`, not in this read set).
- **Which concrete disaster maps to each of these classes.** The `+0x60`-family vs `+0x10`-family split is confirmed, and `0x1001b3a9` is UFO by string linkage, but `0x1001ce14`/`0x10019887`/`0x100116a0`/`0x10017114`/`0x1001763f`/`0x10012133`/`0x1002df4d`/`0x10008c42` carry no disaster-name string. Missing: the loader→vtable→`DAT_*`-global read chain (same open item as `SIMDSTR.md` §7).
- **Semantic meaning of the message ids** (`0x6491d942…945`, `0x3092d3c` family, `0x247e319d`, `0xc2a4e25b`, `0x620effde`, and outbound tags `0xe5`/`0xed`/`0x4a`). Confirmed only as opaque 32-bit ids passed to the registrar/layer; their message-type meaning is not decodable from this module. Missing: the sender/handler on the other side (another GZCOM module's message table).
- **`FUN_10022eeb` vtable identity.** Slots `+0x14`/`+0x18` are structurally subscribe/unsubscribe, but the interface's GZCOM name is `[iOS-HINT]` only. Missing: SC3U-side class-name string or IID for the singleton (built inside `FUN_10022fc7`, not read here).
