# POWER_GRID.md — how SimCity 3000 decides which tiles have power (U-012, RESOLVED)

Resolved 2026-08-14/15 in `SIMUTIL.DLL` (`re/ghidra_export_simutil/`, image base `0x10000000`).
`SC3PowerLayer` = GZCLSID `0x20afdf44`, ctor `0x10003275`, object **0x2fc = 764 bytes**,
primary vtable `PTR_LAB_100205c0`.

> **Base-offset warning.** The class uses several vtables, so `this` differs per method:
> `0x100047e1` and `0x10004e57` get `this` = **base**; `0x10003904` gets **base+0x10**;
> `0x10004c1f` gets **base+0x14**. Every offset below is normalised to the object base.
> (Two-witnessed: init allocates at `this+0x48/0x4c/0x2cc`, teardown frees the same buffers at
> `base+0x58/0x5c/0x2dc`.)

## The answer: a masked bitmap dilation flood-fill, capped at 600 `[CONFIRMED]`

Three rasters, all allocated in `sc3_power_layer_init` `0x10003904`:

| buffer | offset | allocation | role |
|---|---|---|---|
| region | `+0x58` | `operator_new((w*h>>5)<<2)` | 1 bit/tile — the region being grown |
| **mask** | `+0x5c` | `operator_new((w*h>>5)<<2)` | 1 bit/tile — the conductive/powerable tiles |
| demand | `+0x2dc` | `operator_new(w*h)` | **1 byte/tile** — per-tile power demand |

Per power source, `sc3_power_distribute_region` `0x10004e57`:

1. **Seed** `0x10004e93` — `sc3_bitraster_set_tile_bit(region, width, x, y)`:
   `idx = (width*y)/32 + x/32`, `bit = 1 << (x & 0x1f)`.
2. **Grow** `0x10004ec4` — `sc3_bitraster_grow_capped(region, mask, width, 0x258, &y_lo, &y_hi)`.
   Loops up to **600** iterations, stopping early when neither pass adds a bit:
   - horizontal `0x1000bce2`: `((next<<0x1e | self)<<1 | self>>1 | self) & mask ^ self` `@0x1000bd22`
   - vertical `0x1000be48`: `(self | rowAbove | rowBelow) & mask ^ self` (stride `width/0x20` dwords)

   `& mask` confines growth to conductive tiles; `^ self` isolates the new frontier. This is a
   4-neighbour flood-fill done 32 tiles at a time, **not** a per-cell work queue.
3. **Drain** `0x10005015`–`0x100050fa` — walk the grown region dword by dword (empty-dword fast
   path `@0x1000502b`), read the demand byte at `base+0x2dc + (width*y + x)` `@0x100050df`,
   subtract from the supply budget; when exhausted, `sc3_power_clear_region_rows` `0x10004579`
   wipes the remainder and returns. Per-tile powered state is emitted via layer `vtable+0x3c`.

### ⭐ The iOS cap of 600 is CONFIRMED on the PC side

`SIM_LAYERS_XREF.md` recorded `Bit1_SelectionGrow` with a cap of 600 from the iOS build as an
`[iOS-HINT]`. The literal **`0x258` = 600** appears at **`0x10004ee2`** in SIMUTIL. That is a
genuine cross-RE confirmation.

**Read together with U-011 this gives the calibrated rule for the oracle:** iOS **algorithms and
magic constants transfer**; iOS **struct layouts do not** (0 of 5 plant offsets matched).

## The raster kernel is generic infrastructure
`sc3_bitraster_{set_tile_bit, grow_capped, grow_horizontal, grow_vertical}`
(`0x1000b6c9` / `0x1000bbfc` / `0x1000bce2` / `0x1000be48`) are **not power-specific** — eight
other SIMUTIL functions reuse them (`FUN_1000e0b5`, `FUN_1000e366`, `FUN_1000e573`, `FUN_1000e675`,
`FUN_1000e8c4`, `FUN_1000dff3`, …). Expect the same kernel behind water and other coverage layers.

## SC3PowerLayer field map `[CONFIRMED]` (base-normalised)

| offset | dec | meaning | proven at |
|---|---:|---|---|
| `+0x20` | 32 | consumer/building list head | `0x10004c1f`, `0x10004e57` |
| `+0x24` | 36 | layer-active flag | `0x10003904`, `0x100047e1` |
| `+0x28` | 40 | grid **width** (source `vtable+0xcc`) | `0x10003904` |
| `+0x2c` | 44 | `width>>5` = dword stride per row | `0x10003904`, `0x100030e8` |
| `+0x30` / `+0x34` | 48 / 52 | `width-1` / `height-1` | `0x10003904` |
| `+0x38` | 56 | → source city-map object | `0x10003904` |
| `+0x3c`–`+0x54` | 60–84 | COM sub-objects (data/report/IO/dispatch) | `0x10003904` |
| `+0x58` / `+0x5c` | 88 / 92 | **region raster** / **mask raster** | `0x10003904` |
| `+0x68` | 104 | dword count `(w*h)>>5` | `0x10003904` |
| `+0x70` / `+0x74` | 112 / 116 | supply / served accumulators | `0x10004e57` |
| `+0x78` | 120 | unmet-demand % `= (0x70-0x74)*100/0x70` | `0x10004c1f` |
| `+0x7c` / `+0x7d` | 124 / 125 | PowerConservation / StairwellLighting ordinance flags | `0x10004c1f` |
| `+0x88` | 136 | secondary list head (network segments) | `0x10004c1f` |
| `+0x8c`–`+0xc8` | 140–200 | 4 × 8-byte per-sector accumulators | `0x1000406b` |
| `+0xcc` | 204 | monthly stats: 12 months × 10 categories × 4 B, row stride `0x28` | `0x10004132` |
| `+0x2ac` | 684 | month ring index (mod 12) | `0x10004c1f` |
| `+0x2b0` | 688 | 10-entry running totals | `0x10004c1f` |
| `+0x2d8` | 728 | message dispatcher | `0x10003904` |
| `+0x2dc` | 732 | **demand byte raster** | `0x10003904` |
| `+0x2e4` | 740 | tiles-with-demand actually served | `0x10004e57` |
| `+0x2f0` / `+0x2f4` | 752 / 756 | building count / count of category 5 | `0x10004c1f` |

## Ordinances feed the supply budget
The budget spent against demand is derived from the summed plant output and **reduced by**
`_DAT_100289ec` / `_DAT_100289e8` — the `SavingDueToPowerConservationOrdinance` and
`SavingDueToStairwellLightingOrdinance` tunables loaded by `sc3_power_load_layer_tunables`
`0x10004979` from `SC3PowerLayer.INI [MiscPowerLayerTunables]`. Code ↔ data chain closed.

## Still open `[UNCERTAIN]`
- **Who writes the mask raster `+0x5c`** (rasterising power lines / conductive tiles) and
  **who writes the demand bytes `+0x2dc`**. Both are only *read* in the functions examined and
  freed at teardown. Trace writers of `this+0x5c` / `this+0x2cc`–`0x2dc`; likely a pre-tick scan
  from `0x10004c1f` or via the primary vtable `PTR_FUN_10020608`.
- **Layer `vtable+0x3c` (slot 15)** — takes `(x, y, &flag)` and is the per-tile "mark powered"
  emitter; the target function has not been read.
