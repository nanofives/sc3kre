## Summary

All three are C2. Two are the **write/serialize half of a network-piece "tile record" property protocol**, the third is a **GZCLSID accessor**. The property-id block and the writer/reader pairing are the high-value structural finds.

### 0x1000ca2c — `FUN_1000ca2c` (236 B) — tile-record serializer (write path)
`__thiscall(int param_1 /*this: piece*/, undefined4 param_2, int *param_3 /*writer/descriptor*/)`. Reads packed fields from the piece struct and pushes them into `param_3` via its vtable [CONFIRMED @ 0x1000ca2c]:

- **Keyed property setter** `(*param_3+0x84)(key, value)`:
  - `0x6355941d` ← `*(param_1+0x14) & 0xffff` (16-bit)
  - if `+0x14 & 0x10000`: `0x63559421` ← `+0x14 >>0x10 & 1`
  - if `+0x14 & 0x20000`: `0x6355941e` ← `>>0x11 & 1`; `0x63559420` ← `>>0x14 & 0xff`; `0x6355941f` ← `>>0x12 & 3`
- **Typed setters** on `param_3`:
  - `(+0x30)(x, y, z)` from `+0x10`: `x = &0x7ff`, `y = >>0xb & 0x7ff`, `z = >>0x16 & 0xff` (11/11/8-bit packed tile coordinate)
  - `(+0x38)(+0x10 >>0x1e)` — top 2 bits (rotation/orientation)
  - `(+0x3c)(+0xc >>0x19 & 1, +0xc >>0x18 & 1)` — two flag bits
- returns `1`.

This is the exact inverse of **`FUN_1000c86f`** (445 B) [CONFIRMED @ 0x1000c86f], which reads the same keys via `(*param_2+0x80)(key, &out)` (GET) and reassembles the identical bit layout back into `this+0xc/+0x10/+0x14`. `+0x84`=SET-by-value, `+0x80`=GET-by-pointer → **`FUN_1000ca2c` is the serialize/save direction, `FUN_1000c86f` the deserialize/load direction.** `FUN_1000d594` [CONFIRMED @ 0x1000d594] is the per-key getter dispatch for the same id block, confirming `0x6355941d..0x63559422` is a stable property enumeration.

### 0x10023b3a — `FUN_10023b3a` (177 B) — tile-record serializer, virtual-source sibling
`__thiscall(int *param_1 /*this: piece*/, undefined4 param_2, int *param_3 /*writer*/)`. Same `param_3` typed-setter layout as `FUN_1000ca2c`, but the source values come from **virtual getters** on the piece rather than raw struct reads [CONFIRMED @ 0x10023b3a]:

- guards on sub-object `piVar1 = param_1[1]`; returns `piVar1 != 0`
- `(+0x28)` ← `(*piVar1+0x14)()`
- `(+0x2c)` ← `(*param_1+0x88)()`
- `(+0x30)(x,y,z)` from `param_1[4]`: `&0x7ff`, `>>0xb & 0x7ff`, `>>0x16 & 0xff` (identical 11/11/8 packing)
- `(+0x34)` ← `(*param_1+0xd4)()` (called twice)
- `(+0x38)(param_1[4] >>0x1e)` — top 2 bits
- `(+0x3c)(param_1[3] >>0x18 & 1, param_1[3] >>0x19 & 1)` — two flags

Same six `param_3` typed setters (`+0x28,+0x2c,+0x30,+0x34,+0x38,+0x3c`) → `param_3` is the same "tile descriptor builder" object as in `FUN_1000ca2c`. This is a sibling emit for a different piece class that exposes its fields through virtuals.

### 0x10013965 — `FUN_10013965` (6 B) — GZCLSID accessor
`return 0x2147c2dd;` (`mov eax,0x2147c2dd; ret`) [CONFIRMED @ 0x10013965]. `0x2147c2dd` is used as a **GZCLSID** in `FUN_10012dff` [CONFIRMED @ 0x10012dff], where four `{type=0x2147c2dd, iid=0x206c6e7c, index=0..3}` triples are queried against three city-layer pointers (`this+0x3c/+0x40/+0x44`) via `FUN_10012fc3`. `0x206c6e7c` is already named `GZIID_cISC3CityLayer` in this project's prior work, so this accessor returns this class's own GZCLSID `0x2147c2dd`.

## Deliver — classification table

```csv
rva,subsystem,confidence,new_name,evidence
0x1000ca2c,piece-serialize,C2,sc3_ntwrk_tile_write_record,"emit path: (*param_3+0x84)(key,val) keys 0x6355941d/1e/1f/20/21 + typed setters +0x30(x11,y11,z8)/+0x38(rot2)/+0x3c(2 flags); exact inverse of reader FUN_1000c86f (+0x80 GET) [CONFIRMED @ 0x1000ca2c, 0x1000c86f, 0x1000d594]"
0x10023b3a,piece-serialize,C2,sc3_ntwrk_tile_write_record_virtual,"sibling emit: same param_3 setters +0x28/2c/30/34/38/3c, source via virtual getters (*param_1+0x14/+0x88/+0xd4); same 11/11/8 packing at param_1[4], flags at param_1[3] bit24/25 [CONFIRMED @ 0x10023b3a]"
0x10013965,gzcom,C2,sc3_ntwrk_get_clsid_2147c2dd,"returns const 0x2147c2dd; used as GZCLSID paired with IID 0x206c6e7c (GZIID_cISC3CityLayer) in FUN_10012dff layer queries [CONFIRMED @ 0x10013965, 0x10012dff]"
```

## Notable findings (structural)

- **Keyed property protocol / id enumeration** `0x6355941d, 0x6355941e, 0x6355941f, 0x63559420, 0x63559421, 0x63559422` — a contiguous GZ property-id block for a network-piece "tile record." Setter vtable slot `+0x84` (SET by value), getter slot `+0x80` (GET by pointer). Read/write pair fully mapped: writer `0x1000ca2c`, reader `0x1000c86f`, per-key getter dispatch `0x1000d594`. This is **serialization/persistence** infrastructure — the save/load of individual placed pieces.
- **Packed placement word** (same in both serializers): tile coordinate `x:11 | y:11 | z:8 | rotation:2` in one dword (`+0x10` / `param_1[4]`), plus two boolean flags at bits 24/25 of a second dword (`+0xc` / `param_1[3]`).
- **Two serializer variants for the same descriptor** (`param_3` with typed setters `+0x28..+0x3c`): `0x1000ca2c` reads raw struct fields, `0x10023b3a` reads through virtual getters — two piece classes emitting a uniform tile descriptor.
- **GZCLSID accessor** `0x2147c2dd` (`0x10013965`), confirmed a class id via its use with `GZIID_cISC3CityLayer` (`0x206c6e7c`) in `FUN_10012dff`.

## Not determined

- **None left unclassified** — all three functions in the slice were read and classified C2.
- Residual (does not block classification): the concrete object type of the writer/descriptor `param_3` (the object bearing setters `+0x28..+0x3c` and `+0x84`) is not named here — *needs* its vtable `PTR_*` identification or a GZCLSID→name table; and `+0x84`/`+0x80` are described mechanically as SET/GET by key, the exact GZCOM interface name is not proven in this module.
