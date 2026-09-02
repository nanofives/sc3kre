# MAPCLICK_PRE.md — widen the city-view window rect, live (2026-09-01)

**Committed before the write.**

## Evidence this rests on

Owner hand-test, passive trace `maptrace2.json` (no synthetic input; every click is human):

| click | city-view `vt+0xe4` = `SIMSPR+0x4ecd3` on `0xf054214` | result |
|---|---|---|
| (713,335), (581,388) — inside 800x600 | **ret=1** | `vt+0x130` = `SIMSPR+0x4e020` entered, ret=1, zone placed (owner: works) |
| (1537,622), (1521,425) — outside | **ret=0** | `vt+0x130` never entered, event falls back to the root (owner: nothing happens) |

Mechanism `[CONFIRMED @ SIMSPR 0x1004ecd3]`: the hit test rejects the point when
`x < this+0x14 || y < this+0x18 || this+0x1c <= x || this+0x20 <= y`. Live read of `0xf054214`:
`rect+0x14 = [0 0 800 600]`, `ext+0x80 = [0 0 800 600]`, `dest+0x90 = [0 0 0 0]`.

The mod never touched this window **by design** — the window recorder skips anything covering most of
the native screen ("the main view is not a HUD element to move"). Excluded from being moved, and as a
side effect never widened.

## The intervention

Two `int` writes into the live game: `0xf054214+0x1c = 2048`, `+0x20 = 1081`. Only the fields the
confirmed reader actually reads. `+0x80..0x8c` deliberately left alone for now — if the hit passes
without touching it, that is a cleaner result and a smaller fix.

## Pre-registered outcomes

| # | observation | verdict |
|---|---|---|
| **M-PASS** | zoning works outside the old 800x600 box **and lands on the tile under the cursor** | Root cause confirmed; the fix is a field write on one more window. |
| **M-OFFSET** | the click now registers outside the box but the zone lands on the **wrong tile** | The hit test is fixed and a **second** stale source feeds screen→world picking. Real progress, not a failure — and it is the same question the bigger-cities workstream is blocked on. |
| **M-NULL** | still nothing happens outside the box | The rect is not the only gate. `vt+0xf0(0x80000)` and the `this+0x58` branch in `FUN_1004ecd3` are the next suspects. |
| **M-SIDE** | it works but something else breaks (rendering, scrolling, HUD) | The field has other readers. Record what broke. |

## Stated in advance

- `M-OFFSET` is a **likely** outcome and is not a failure. The hit test and the screen→world
  projection are different code; fixing one says nothing about the other.
- Other readers of `+0x14..+0x20` on the view window are **not enumerated**. Same open risk as the
  root-extent write, and stated before the write rather than after.
- Reversible: write `800`/`600` back.
