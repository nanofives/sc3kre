## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x100016e6,gzcom-persist,C2,sc3_gzcompersist_write_fields,"__thiscall(this,stream,param_2). Guards on FUN_100189a9 (base-record writer) then calls stream vtable+0x84 (Write-by-property-id) 4x with property ids 0x351d624/625/626/627 and fields this+0x34(4b),this+0x40(4b),this+0x44(4b),this+0x48(1b). Read-counterpart is FUN_1000165f (vtable+0x80). [CONFIRMED @ 0x100016e6]"
0x100044dd,gzcom,C2,sc3_gzcom_query_interface_sub,"__thiscall QueryInterface. riid switch: 0x58d & 0x206c6e7c & 0x81c0cb7c -> this+0x10; 0x5e4 -> this+0x18; 0xa0afdf5d -> this+0x14; else tail-calls base QI FUN_10003391. Sets *param_2, AddRef=vtable+4, returns true. [CONFIRMED @ 0x100044dd]"
0x1000df51,gzcom-msg,C2,sc3_gzmsg_add_notifications,"__fastcall(target). Fetches singleton FUN_10016dad(); if non-null calls its vtable+0x14 4x with msg ids 0xc2bdf178,0xd2bdf178,0x826cb9b6,0x426cb9b3. Then calls (target+0x1c)->vt+0x34 and (target+0x20)->vt+0x34. Returns true. [CONFIRMED @ 0x1000df51]"
0x1000dfab,gzcom-msg,C2,sc3_gzmsg_remove_notifications,"__fastcall(target). Fetches singleton FUN_10016dad(); if non-null calls its vtable+0x18 4x with the SAME 4 msg ids as 0x1000df51. Returns last result (true). Mirror-unsubscribe of 0x1000df51. [CONFIRMED @ 0x1000dfab]"
0x1000c82b,gzcom,C2,sc3_gzcom_query_interface_self,"__thiscall QueryInterface. riid in {1,0x58d,0x206c6e7c,0x81c0cb7c,0xc2bf0039} -> *param_2=this, AddRef=vtable+4, return true; else return riid&0xffffff00 (false). [CONFIRMED @ 0x1000c82b]"
```

## 2. Notable findings

**Persistence read/write pair — the highest-value find (0x100016e6).**
`FUN_100016e6` is a **serializer (Write)** and its **matching deserializer (Read) is `FUN_1000165f`** (found via the shared property-id constants):

- Write (`0x100016e6`) calls the segment's `vtable+0x84` with `(propertyId, value)`.
- Read (`0x1000165f`) calls `vtable+0x80` with `(propertyId, &value)`.
- Identical four-field record, keyed by sequential property IDs:

| Property ID | Object field | Width | [CONFIRMED] |
|---|---|---|---|
| `0x351d624` | `this+0x34` | 4 bytes | `@0x100016e6:10`, `@0x1000165f:15` |
| `0x351d625` | `this+0x40` | 4 bytes | `@0x100016e6:12`, `@0x1000165f:18` |
| `0x351d626` | `this+0x44` | 4 bytes | `@0x100016e6:14`, `@0x1000165f:21` |
| `0x351d627` | `this+0x48` | 1 byte (bool) | `@0x100016e6:16`; read stores `field!=0` at `@0x1000165f:29` |

The guard `FUN_100189a9` (334 bytes, `EH_prolog`) is the **base-record writer**: it recurses into a sub-object at `this+8` via `FUN_10019958`, calls stream `vtable+0x54/0x60/0x6c`, and writes a trailing value from `this+0x1c`. Its read-side twin is `FUN_1001888f`. This is a GZCOM `IGZPersist`-style property-record format.

**Message subscribe/unsubscribe pair (0x1000df51 / 0x1000dfab).**
Both resolve a lazily-cached singleton via `FUN_10016dad` (guards global `DAT_10028e7c`, inits once via `FUN_10016e31`/`FUN_10016e52`). They call `vtable+0x14` (subscribe) vs `vtable+0x18` (unsubscribe) with the **same four message IDs**:
`0xc2bdf178`, `0xd2bdf178`, `0x826cb9b6`, `0x426cb9b3` — a fixed notification set this director registers/tears down as a unit. Note `0xc2bdf178` and `0xd2bdf178` differ only in the top nibble (paired variant IDs).

**Two QueryInterface implementations + a shared base (dispatch by IID).**
Both `0x100044dd` and `0x1000c82b` are GZCOM `QueryInterface` (constant-list dispatch → `*ppv`, `AddRef` at `vtable+4`, return `bool`). `0x100044dd` tail-chains to base QI `FUN_10003391` (IIDs `1`=cIGZUnknown, `0x80ace12f`, `0x817ab319`). IID `0x206c6e7c` and `0x81c0cb7c` appear in **both** QIs, so these two objects expose an overlapping interface set. Full IID inventory:

- `0x100044dd`: `0x58d`, `0x5e4`, `0x206c6e7c`, `0x81c0cb7c`, `0xa0afdf5d`
- `0x1000c82b`: `0x00000001`, `0x58d`, `0x206c6e7c`, `0x81c0cb7c`, `0xc2bf0039`

These IIDs should be reconciled against `re/analysis/GZCOM_INTERFACE_CATALOGUE.md`.

## 3. Not determined

- **Semantic names of the IIDs / property IDs / message IDs.** The decompilation gives only the raw 32-bit constants (listed above). Mapping `0x206c6e7c`, `0x81c0cb7c`, the `0x351d624`–`0x351d627` property keys, and the four message IDs to named GZ interfaces/properties/messages requires the GZCOM catalogue or a second witness; not derivable from these 5 bodies alone.
- **Concrete class identity of each object.** `0x100016e6`/`0x1000165f` operate on a `this` with fields at `+0x34/0x40/0x44/0x48` (three 4-byte + one bool); the two QIs identify distinct classes, but which SimUtil class each is (`cSC3…`) is not shown — needs cross-check against the iOS unstripped export or vtable-layout matching. No [iOS-HINT] asserted; struct offsets are proven non-transferable.
- **What `vtable+0x34` on the two sub-objects does in `0x1000df51`** (`target+0x1c` and `target+0x20`): called with `(target)` and return ignored except the last. Purpose beyond "invokes slot 0x34 on two owned sub-objects" is not shown.

All five are **C2** (body read, callees identified, mechanically described, named). None claimed C3/C4 — no runtime or independent second witness was used.
