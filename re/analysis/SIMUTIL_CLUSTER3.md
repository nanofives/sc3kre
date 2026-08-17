## 1. Classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1000ae59,serialization,C2,sc3_serialize_write_triple,"[CONFIRMED @ 0x1000ae59] guard call FUN_10007dfe(this,arg,param_3); then 3x indirect call via (*param_3+0x84)(key,value): key 0xa352179a=*(this+0x58), 0xa352179b=*(this+0x5c), 0xa352179c=*(this+0x60); short-circuits on char!=0. Passes VALUE => write/serialize-out side. Read counterpart is FUN_1000adf3 (slot 0x80, passes field ADDRESS)"
0x1000b577,serialization,C2,sc3_serialize_write_triple_thunk28,"[CONFIRMED @ 0x1000b577] identical body to 0x1000ae59 with this adjusted -0x28: guard FUN_10007dfe(param_1-0x28); writes keys 0xa352179a/b/c from *(param_1+0x30/0x34/0x38) via (*param_3+0x84). param_1+0x30 == (param_1-0x28)+0x58 => same fields, secondary-subobject (MI adjustor) entry"
0x1000b5bf,serialization,C2,sc3_serialize_write_triple_thunk30,"[CONFIRMED @ 0x1000b5bf] identical body with this adjusted -0x30: guard FUN_10007dfe(param_1-0x30); writes 0xa352179a/b/c from *(param_1+0x28/0x2c/0x30) via (*param_3+0x84). param_1+0x28 == (param_1-0x30)+0x58 => same fields, second MI adjustor entry"
0x100033c0,serialization,C2,sc3_persist_get_typeid_e0afdf68,"[CONFIRMED @ 0x100033c0] body is `return 0xe0afdf68;` only. [CONFIRMED @ 0x10003f95] the constant 0xe0afdf68 is stored as local_48 next to local_4c=0x206c6e7c to build a 2-dword persist key passed to FUN_1001c5aa/FUN_1001c940. 0x206c6e7c = GZIID_cISC3CityLayer (per repo/commit 2c3a96d)"
0x1000c825,serialization,C2,sc3_persist_get_typeid_02bf0033,"[CONFIRMED @ 0x1000c825] body is `return 0x2bf0033;` only. [CONFIRMED @ 0x1000d9ec:60-62] the constant 0x2bf0033 is stored as local_24 next to local_28=0x206c6e7c (and local_20=0) to build a 3-dword persist key passed to FUN_10004714/FUN_1001c940. Same group id 0x206c6e7c = GZIID_cISC3CityLayer"
```

## 2. Notable findings

**Save-side serialiser + its load twin (highest value).** `0x1000ae59` is a **serialize-WRITE** of three consecutive dwords. It first calls the base/chained serialiser `FUN_10007dfe` (which itself calls `FUN_100189a9(this+0x28)` then `FUN_1000785c` — a base-class serialise guard), and on success writes three fields through vtable slot `+0x84`:

| property key | source field |
|---|---|
| `0xa352179a` | `*(this+0x58)` |
| `0xa352179b` | `*(this+0x5c)` |
| `0xa352179c` | `*(this+0x60)` |

The matching **LOAD side is `FUN_1000adf3`** [CONFIRMED @ 0x1000adf3]: same three keys, same offsets, but via vtable slot `+0x80` passing the field **address** (`this+0x58`, not `*`) — i.e. deserialize-in. So slot `+0x80` = read-field, slot `+0x84` = write-field on the same IGZSerializable-style stream interface (`param_3`). The three keys `0xa352179a..0xa352179c` are consecutive field tags of one 3-component record.

**Two adjustor-thunk aliases of the write.** `0x1000b577` and `0x1000b5bf` are byte-for-byte the same serialise-write reached through a different subobject `this` (multiple inheritance): `-0x28` and `-0x30` respectively. Confirmed by arithmetic — `param_1+0x30 == (param_1-0x28)+0x58` and `param_1+0x28 == (param_1-0x30)+0x58`, so all three functions touch identical object fields and identical keys.

**Two persist resource-key id accessors tied to GZIID_cISC3CityLayer.** `0x100033c0`→`0xe0afdf68` and `0x1000c825`→`0x2bf0033` are one-instruction constant returns. Both constants are used verbatim as the second component of a GZPersistResourceKey whose **group is `0x206c6e7c` = GZIID_cISC3CityLayer** (already established in the repo). Call sites:
- `0xe0afdf68` at `FUN_10003f4d:26-27` — builds `{0x206c6e7c, 0xe0afdf68}`, then serialises arrays (`this+0x29c`, blocks of 10 dwords, `this+0x2a0`…) via a stream object from `FUN_1001c940`, slot `+0x48`.
- `0x2bf0033` at `FUN_1000d9ec:60-62` — builds `{0x206c6e7c, 0x2bf0033, 0}`, then serialises a run-length region of `*(this+0x68)` (a dword array sized `(width*width)/0x20`) plus fields at `this+0xb0/0xb8/0xd8/0xc8/0xc4/0xc0/0xa4/0xc` via slots `+0x84`/`+0x88`.

Together these five are the write half and key-id half of the **cISC3CityLayer save/load path** the task flagged as highest value.

## 3. Not determined

- **Semantic meaning of the three fields at `+0x58/+0x5c/+0x60`** (keys `0xa352179a/b/c`): the decomp shows only three raw dwords written/read as one record. Missing evidence: a caller that assigns those offsets from named data (e.g. width/height/depth or x/y/z), or the iOS field names for this class. Not guessing.
- **Which concrete class** owns `0x1000ae59` and which secondary bases the `-0x28`/`-0x30` thunks belong to: no direct textual caller in the SIMUTIL export (they are vtable entries invoked indirectly). Missing evidence: the vtable/RTTI table listing these RVAs.
- **Human name of the resource ids `0xe0afdf68` and `0x2bf0033`**: confirmed they are persist-key components under group GZIID_cISC3CityLayer, but the specific segment each denotes is not decidable from these bodies. Missing evidence: an iOS `[iOS-HINT]` symbol for the matching `GetPersistResourceKey`, or a game-side `.dat`/save round-trip.

All five are serialization-subsystem, rated **C2** (bodies read, callees identified, mechanically described, named). None can honestly go above C2 without runtime or a second witness.
