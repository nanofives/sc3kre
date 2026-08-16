# Power subsystem — cross-RE demo (SC3U ↔ iOS)

Purpose: demonstrate the cross-RE method end-to-end on one subsystem. The iOS named
sibling gives the algorithm + names + struct field offsets; SC3U is the authority we
anchor back to. Evidence tags: `[iOS-CONFIRMED]` = read from the iOS decompilation;
`[iOS-HINT]` = iOS-derived hypothesis for SC3U, not yet SC3U-anchored.

## 1. The power model, from the iOS decompilation `[iOS-CONFIRMED]`

The SimCity 3000 engine models power as a **1-bit-per-cell raster flood-fill**, plus a
per-plant capacity/aging model. Two classes: `goPowerLayer` (grid) and `goPowerPlant`.

### 1a. Grid propagation — `goPowerLayer::UpdatePowerGrid` @ iOS `0x0025bff8`
- Uses a reusable **`Bit1_*` 1-bit raster library** (shared engine primitive — the water
  system reuses it: `goPlumbingLayer::...Bit1_SelectionGrowHorzwDrain` @ iOS `0x002f8514`).
  Family @ iOS `0x00261320`+: `Bit1_PixelSet/Clear/Test`, `Bit1_Count`, `Bit1_Xor`,
  `Bit1_Copy`, `Bit1_SelectionSet`, `Bit1_Grow{Horiz,Vert}`, `Bit1_SelectionGrow{,Horiz,Vert}`,
  `Bit1_GrowDeepWrite{Horiz,Vert}`.
- Power spreads from plants by flood-filling connected conductive cells:
  `Bit1_PixelSet(this+0xb8, this+0xa4, x, y)` then
  `Bit1_SelectionGrow(this+0xb8, this+0xbc, this+0xa4, 600, ...)` — grow capped at **600**.
- `goPowerLayer` field offsets seen: `+0xa4` grid stride/width; `+0xb8` powered/wire bitmap;
  `+0xbc` selection scratch bitmap.
- Cadence methods: `Simulate`, `SimulationBegin`, `SimulationEnd`, `UpdateLayer`,
  `UpdateUsageHistory` (196 B), `SetsWireBits`/`UpdateWireBit`, `onOccupantInserted/Removed`,
  `CellChanged`. Queries: `GetTotalPowerNeededByTheCity`, `GetNumberOfPowered/UnpoweredConsumers`,
  `GetPlantCapacity`, `GetPowerPlants`.

### 1b. Plant capacity + aging — `goPowerPlant::Update` @ iOS `0x0025dd64` `[iOS-CONFIRMED]`
Linear capacity derate between a decay-start age and a max age, with a random early-failure
roll. Struct `goPowerPlant` field map (byte offsets):
- `+0x40` embedded `IBuildingMortal` (has `GetAge()`).
- `+0x48` **maxAge** (defunct threshold).  `+0x4c` **decayStartAge**.
- `+0x58` **currentOutput** (written result).  `+0x5c` **baseCapacity**.
- `+0x60` u16 **earlyFailChance** (compared to `RandomSint32RangeUniform`).
- `+0x50` defunct flag.  vtable `+0x108` = failure handler.

Formula (verbatim):
```
output = baseCapacity
if age < maxAge && decayStartAge < age:
    output -= baseCapacity*(age - decayStartAge) / (maxAge - decayStartAge)
else if age >= maxAge: output = 0
this+0x58 = output
```
Other plant methods: `ActualCapacity`, `SetUsage`, `NeedsPower`, `IsAging`,
`BecomeDefunctDueToAge` @ `0x0025dc8c`, `Explode` @ `0x0025e118`, `GetCorrespondingBuildingRubble`.

## 2. Anchoring to SC3U (desktop) — method + first pass

**Key finding:** SC3U.exe is **string-poor** for sim internals (1,369 strings total; a grep
for power/consumer/plant/electric returns **nothing**). So the desktop power code cannot be
found by string xref — anchor by **shared constants, struct-offset signatures, and the
Bit1 flood-fill shape** instead.

First-pass probes `[iOS-HINT]`:
- The flood-fill cap **600** appears in only **6** SC3U functions (candidate set):
  `FUN_0040496d`, `FUN_00407bec`, `FUN_00408a23`, `FUN_00428801`, `FUN_00430e6b`, `FUN_00436a94`.
  (600 may be coincidental; treat as leads, confirm by the Bit1-grow structure below.)
- `__udivsi3` is correctly ABSENT in SC3U (ARM-only soft-divide helper; x86 uses inline
  `div`) — a reminder that iOS↔SC3U is semantic, not instruction-level.

**Next step to promote to `[CONFIRMED @ 0xADDR]`:** locate SC3U's `Bit1_*` 1-bit raster
library by its structure (nested row/col loops over a bitmask stride, bit-shift by width),
then find its caller that seeds from plant tiles + grows capped at 600 = `goPowerLayer::UpdatePowerGrid`
twin; and find the plant-derate function matching the `+0x58/+0x5c/+0x48/+0x4c` field math.
This is a focused P4 session, not a guess to commit now.

## 3. What this demo proves about the workflow
- The iOS binary hands over a full, named, citable model of an SC3 subsystem in minutes —
  including exact struct field offsets and the reusable `Bit1_`/`goPlumbingLayer` sharing.
- SC3U's string-poverty means the iOS oracle is not a luxury but the **primary lead
  source** for the desktop sim; constants + struct shape are the anchor currency.
- Honest scoping: iOS gives the map; SC3U confirmation is per-subsystem manual work. No
  SC3U power function is committed to `functions.csv` yet — only logged as candidates here.
