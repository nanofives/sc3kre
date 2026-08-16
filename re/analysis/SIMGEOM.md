# SIMGEOM.md — SIMGEOM.DLL, `SC3BuildingLayer` and the building occupant

```
Apps\SIMGEOM.DLL   221,184 bytes   image base 0x10000000   1,749 functions
export: re\ghidra_export_simgeom\
```

Director `GZDllGetGZCOMDirector` `0x10019596` → ctor `0x100128ab` → **14** registrations via
`0x1001991c`. All 14 factories have exported bodies — no label-only stubs in this module.

## The registered classes

| GZCLSID | factory | `new` | ctor | what it is |
|---|---|---:|---|---|
| **`0xe150e7bb`** | `0x100129e6` | 0xc4 (196) | `0x1000cdb0` | **SC3BuildingLayer** — the grid god-object |
| `0xc179c042` | `0x10012a1b` | 0x13c (316) | `0x10022364` | **base building occupant** (factory returns `+0x14`) |
| `0xffd30c03` | `0x10012afb` | 0x13c (316) | `0x1000b8f1` | occupant sibling |
| `0x207edc0e` | `0x10012b39` | 0x14c (332) | `0x100230f8` | occupant subclass **placed from Tiles.ini**; class tag `+0x140` = `0x62b9da80` |
| `0x220055e1` | `0x10012c4b` | 0x154 (340) | `0x10010d32` | most-derived occupant |
| `0x62b9da80` | `0x10012b7a` | 0x2c (44) | `0x10024065` | subcomponent |
| `0xa0ab8c20` | `0x10012c16` | 0x84 (132) | `0x10004bda` | 4-interface manager |
| `0x856cd19a`, `0xda0ac02e`, `0xab8c8b`, `0xe1fd7aa3`, `0x5a2`, `0xa1f53f57`, `0x631c8e77` | | | | `[UNCERTAIN]` |

**Proof that `0xe150e7bb` is the layer.** The two `SC3BuildingLayer.ini` openers
(`0x100042d5`, `0x10003eae`) have no static caller — vtable dispatch, as in SIMMISC — so identity
was pinned through shared object state instead: the ctor `0x1000cdb0` initialises guard bytes at
`+0xc`/`+0xd`, and the world-attach method `0x100023e8` uses `+0xc` as its single-shot init guard,
writing no further than `+0x7c` (inside the 196-byte allocation). Attach also reads the city grid
dims from the host (`vtable +0xcc`/`+0xd0`), stores `width>>1` → `+0x6c`, `height>>1` → `+0x70`,
and computes pixel extents `+0x48 = (width-1)·0x100`, `+0x4c = (height-1)·0x100`.

`[UNCERTAIN]` the config-load vtable slot index — needs a data xref on `PTR_LAB_10029e24` /
`PTR_LAB_10029ee4`.

## The building occupant

Two-witness field map: property **load** `0x1002286f` (GetProperty, vt `+0x38`/`+0x4c`/`+0x30`)
and **save** `0x10022c09` (SetProperty, vt `+0x58`/`+0x6c`/`+0x50`), over one key table.

### The property key table `[CONFIRMED]`
The table at `DAT_1002b4e8`…`DAT_1002b580` is `.rdata`, so it is absent from the text export.
Read directly out of the PE with **`re/tools/pe_read.py`** (new): entries are 8 bytes,
`{u32 propertyId, u32 descriptor}`, `descriptor = (count << 16) | typeCode`.

| propId | count | type | field | propId | count | type | field |
|---|--:|--:|---|---|--:|--:|---|
| `0x65` | 1 | 3 | `+0x04` primary id | `0x71` | 1 | 3 | `+0x120` |
| `0x66` | **3** | 3 | `+0x20/+0x28/+0x24` | `0x72` | 2 | 3 | `+0x114` |
| `0x67` | 1 | 8 | `+0x34` | `0x74` | 1 | 8 | `+0x84` |
| `0x6b` | 1 | 8 | `+0x48/+0x4c/+0x50` | `0x75` | 1 | 8 | `+0x94` |
| `0x6c` | 1 | 8 | `+0x54` | `0x76` | 1 | 8 | `+0xa4` |
| `0x6d` | 1 | 8 | `+0xf0/+0xf4/+0xf8` **resource key #1** | `0x77` | 1 | 8 | `+0xb4` |
| `0x6e` | 1 | **1** | `+0x60` (byte) | `0x78` | 1 | 8 | `+0xc4` |
| `0x6f` | 1 | 8 | `+0x64` | `0x79` | 1 | 8 | `+0xd4` |
| `0x70` | 1 | 8 | `+0x70` | `0x7a` | 1 | 8 | `+0xe4` |
| | | | | `0x7b` | 1 | 8 | `+0xfc` |
| | | | | `0x7c` | 1 | 8 | `+0x108/+0x10c/+0x110` **resource key #2** |

Ids run **consecutively `0x65`–`0x7c`** (`0x68`–`0x6a`, `0x73` unused here). The descriptor
decoding is corroborated twice by the decompilation: `0x66` has count 3 and the loader writes
three components; `0x6e` has type 1 and the loader treats it as a byte.

`[UNCERTAIN]` **type code 8.** It appears on the two fields proven to be 3-dword resource keys
(`0x6d`, `0x7c`) and on 13 others spaced 16 bytes apart (`+0x84`…`+0xe4`), which is consistent
with them all being resource keys — but only two are proven. Do not assume the rest.

> **Corrected 2026-08-15:** the `+0x84`..`+0xe4` block is **7** 16-byte slots (ids `0x74`-`0x7a`),
> not 13 — `(0xe4-0x84)/0x10 + 1 = 7`. Each is a lazy resource-key record resolved with registry
> type `0x6100`, selected by a purpose bitmask rather than a numeric index.
> **Semantic meanings for `0x65`-`0x7c` are now in `re/analysis/SIMGEOM_PROPERTIES.md`.**

`[UNCERTAIN]` the **semantic meaning** of each property id. Reading what each field drives is the
single highest-value follow-up in this module.

### Notable fields
- **Appearance**: two GZ resource keys of type `0x2026960b` at `+0xf0` and `+0x108`, defaults
  group `0xa1096a4f` / `0x62e69238` with instance `0xffffffff` (built via `sc3_geom_reskey_ctor`
  `0x1001fa0c`). Group `0x62e69238` is the **building catalog** string table identified in
  `SIMUI.md` — the same group id, from a different module.
- **Footprint**: the concrete size used at placement is the per-tile-code byte from `Tiles.ini`;
  `0x100048a1` computes `(dim.hi - dim.lo) + 1` from service `0xc14f8955`.
- **Growth/development stage**: **not present in the SIMGEOM occupant.** RCI development lives in
  SIMRCI's zone layer. A clean negative.

## INI loaders

**`DefaultBuildingData`** (`sys\SC3BuildingLayer.INI`, cb `0x100044e2`) — rows are **positional,
not `key=value`**: token0 int = building id (map `DAT_100308f0` + list `DAT_100308e0`), token1/2
ints, flag `F`/`f`, flag `G`/`g`, then repeated `(int,int)` pairs keyed via service `0x21183b00`.
`[UNCERTAIN]` the literal separator/marker characters (`DAT_100303ac/b0/b4` — too short for
`strings.csv`; the adjacent string is `%LANDMARK%`).

**`BUILDING_TRACKING_GROUPS`** (`Sys\SC3BuildingLayer.ini`, cb `0x10004127`) — a set of building
ids in map `DAT_10030910`, walked later by the layer attach. The richer record parser `0x10001250`
reads `LandUse: %d` → `+0x18`, `BuildingCount: %d` → `+0x1c`, and a `Key: %d,%d,%d,%d` loop →
list `+0x20` (4th int is an enable flag).

**`Sys\Tiles.ini [Tiles]`** (cb `0x10002bdc`) — a 256-entry table (`operator_new(0x800)`),
**8 bytes per record**, default `{+0: 0xffffffff, +4: 0xff}`; key `atoi` → index 0–255; value
`sscanf "%X %d"` → `{+0x00 uint resource id, +0x04 byte footprint size, clamped to 0 if > 3}`.
At placement (`0x1000271d`) each grid cell with tile code `c` instantiates GZCLSID `0x207edc0e`
(subtype `0x57e` = 1406) with `table[c].resId`, positions it via occupant `vt+0xf0`, inserts via
layer `vt+0x58`, and marks the `size × size` footprint occupied.

## Clean negatives `[CONFIRMED]`
- **No exemplar keys.** `0x2351faf8`–`0x2351fafb` (SIMUTIL's power-plant property keys) appear
  **nowhere** in SIMGEOM. This module uses the resource-key idiom (`type = 0x2026960b`) like
  SIMBABLD. Two distinct data-access idioms coexist in the engine.
- **`BuildingAnimationTunables` / `MaxAnimationsBase`** exist as `.rdata` strings but **no
  SIMGEOM function references them**. The animation model is not in this module.

## Next
1. Decode what property ids `0x65`–`0x7c` mean (highest value here).
2. Confirm or refute "type 8 = resource key" by reading one of the `+0x84`…`+0xe4` consumers.
3. Live-Ghidra: the config-load vtable slot index.
