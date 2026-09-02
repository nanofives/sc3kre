# CASCADE_PRE.md — write the AUTHORITATIVE rect and let the framework derive the rest (2026-09-02)

**Committed before the build.** A refactor, not a patch: it changes how the mod moves every HUD
window.

## The defect, measured

A 20 ms sampler recorded each window's first observed rect in a live game
(`re/tools/_tmp_toast.py`, output in this session's log):

```
minimap   0xd3711a0  LOCAL [1888, 925, 2048, 1089]   ABS [640, 436, 2048, 1081]   <- ABS stale
its child 0xdb0e6a8  LOCAL [138, 72, 147, 87]        ABS [778, 508, 787, 523]     <- 640+138, 436+72
ancestor  0x642188   LOCAL [0, 0, 800, 600]          ABS [0, 0, 2048, 1081]       <- LOCAL stale
```

The framework's field model `[CONFIRMED @ SIMUI 0x1006db90, 0x1006c61b, 0x1006d438, 0x1006d8b4]`:

| field | role |
|---|---|
| `+0x80..+0x8c` | **authoritative LOCAL rect** — the only storage |
| `+0x14..+0x20` | DERIVED absolute rect = local + Σ ancestor origins, rebuilt by `vt+0x14c` |
| `+0x24..+0x30`, `+0x90..+0x9c` | DERIVED source and blit-dest rects, rebuilt by `vt+0x168` |

**The mod writes the derived fields.** `rz_fix_hud_parents` pokes `+0x14` on ancestors;
`rz_mini_dock` pokes `+0x90`. Both are recomputed from `+0x80` whenever the framework cascades, so
the HUD's absolute rects are inconsistent — and anything the engine positions from an absolute rect
inherits the inconsistency. The tool flyout's positioner reads the owning item's absolute rect
`[CONFIRMED @ SIMUI 0x1004ec95, 0x1004b8c5]`, which is why toasts and submenus land wrong and why a
periodic correction pass was needed at all.

## The change

1. `rz_fix_hud_parents` widens the ancestor's **LOCAL** rect `+0x80..+0x8c` (still widen-only,
   never shrink), keeping the `+0x14` write so nothing regresses if the cascade does not reach.
2. `rz_mini_dock` writes the minimap's **LOCAL** rect, not just `+0x90`.
3. After all HUD layout, call **`vt+0x14c`** once on the topmost changed window, which rebuilds
   `+0x14` for it and recurses into every descendant `[CONFIRMED @ SIMUI 0x1006c61b]`.

Direct local writes plus an explicit cascade, deliberately NOT `vt+0xc8` SetRect on ancestors —
SetRect relayouts children, and the current placement is owner-tuned and working.

## Pre-registered outcomes

| # | observation | verdict |
|---|---|---|
| **R-PASS** | minimap `ABS == LOCAL`, ancestor LOCAL widened, and toasts/submenus land correctly **with the periodic pass disabled** | The refactor is the real fix. Delete the correction pass, the band heuristic and the `+0x90`-only dock. |
| **R-PARTIAL** | rects consistent but toasts still land wrong | The anchor is not the ancestor chain. Keep the refactor (it is still correct) and RE the toast positioner. |
| **R-CLICK-FAIL** | clicking breaks | The `+0x14` poke was load-bearing in a way the cascade undoes — the GZWIND ancestor classes may not implement `vt+0x14c` as SIMUI does. Revert to the poke. |
| **R-LAYOUT-FAIL** | HUD placement scrambles | The cascade relayouts more than expected. Revert. |

## Stated in advance

- The ancestors are **GZWIND / SC3U.exe** classes, not SIMUI ones. `vt+0x14c` is verified as
  `FUN_1006c61b` **on the SIMUI window base**; that those classes implement the same slot the same
  way is `[UNCERTAIN]` and is exactly what `R-CLICK-FAIL` would reveal.
- Everything currently working (full-width bar, clickability, hover label, map clicks, camera pan,
  panel fill, button placement) is owner-confirmed and at risk from this change. The previous build
  is `99d851e` + the invalidate commit, and `verify/resize_clicklab/sc3resize.c.before` holds an
  earlier snapshot.
- Success is measured **with the periodic correction pass disabled**, or the test cannot
  distinguish the refactor from the hack it is meant to replace.
