# ROOTRECT_PRE.md - widen the root window extent, live (2026-09-01)

**Committed before the write.** Target: the hover label clamp.

## Claim under test

The label placement clamps to `root+0x88` (right) / `root+0x8c` (bottom), read via `vt[0xa0]`/`vt[0xa4]`
`[CONFIRMED @ SC3U 0x00443331, 0x00441d3e, 0x00441d45]`. Live read: root `0x5a94a8` has
`rect+0x14 = [0 0 2048 1081]` (widened by the mod PARENT fix) but `ext+0x80 = [0 0 800 600]` (never
written by anything - the parent fix stops one hop short of the root by design).

## The intervention

Two `int` writes into the live game: `root+0x88 = 2048`, `root+0x8c = 1081`. Nothing else.
Reversible by writing `800`/`600` back.

## Pre-registered outcomes

| # | observation | verdict |
|---|---|---|
| **T-PASS** | after the write, the label follows the cursor across the full 2048x1081 client area; right edge exceeds 798 and top exceeds 582 | The clamp source is identified and the fix is a field write. Build it into the mod. |
| **T-NULL** | the label still pins at right 798 / top <= 582 | **The diagnosis is WRONG.** Report it as wrong; do not explain it away. Another bound is in play. |
| **T-SIDE** | the label moves correctly but something else misbehaves (layout, input, painting) | The field has other readers. Record what broke; the fix needs scoping. |
| **T-VOID** | the write is refused or the object is stale | Do not interpret. |

## Stated in advance

`+0x88/+0x8c` on the ROOT window may have readers beyond the tooltip clamp; they have not been
enumerated. `T-SIDE` exists precisely because that is unmeasured, and the owner was told before the
write, not after.
