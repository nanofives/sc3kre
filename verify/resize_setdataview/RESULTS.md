# RESULTS — restore base view with forced refresh (step 11), 2026-08-30

**VERDICT: the RENDER FIX WORKS. Defects A and B are FIXED.** Owner, after maximizing with NO manual
layer toggle: **"the whole city renders now."** Terrain, zones, buildings and roads all draw after a
resize. This closes the render half of the resizable-window mod.

**NEW, SEPARATE DEFECT found the same run: zooming in after a resize CRASHES the game** (owner: "it
closed itself when i zoomed in"). See below.

Pre-registration: `PRE.md` (`7db49d1`), pre-registered PASS = "whole city renders with no toggle."

## What fixed it

Step 11 = SetDataView(0)'s core with force: `FUN_10018cdf(bridge, *(bridge+0x2c) base layer,
*(bridge+0x80) base renderer, same, 0, force=1)`. Log:
```
[step 11] FUN_10018cdf(bridge, base layer 0x0DC5ED30, base rend 0x0EFFB8D0, force=1) ...
[step 11] returned - active layer bridge+0x28 = 0x0DC5ED30
---- done (all 11 steps) ----
```
The active layer `bridge+0x28`, which step 7 had nulled (`FUN_10018cdf(..., layer=0, force=0)`), is
restored to the valid base layer, and force=1 runs the full-grid refresh. That is the operative repair
the data-view toggle performs. Confirms the root cause: **the resize left the active layer NULL with no
forced refresh; nothing downstream (drawable re-register, repaint, device batch) could draw because the
active layer was null.** Five earlier hypotheses failed because none restored the active layer.

Install unchanged (`SIMSPR f5b9f1d9`, `GZGraphicD acefadf0`); no on-disk change; no `FAULT CAUGHT` in the
resize routine.

## The new defect — zoom-after-resize crash

- One resize cycle completed cleanly (all 11 steps, city rendered). The owner then **zoomed in and the
  game closed itself.**
- **No `FAULT CAUGHT`** (our SEH wraps only the resize routine, not the game's zoom path) and **no
  Windows Error Report** (SC3U's own top-level handler swallowed the fault and exited cleanly - the
  launcher saw `game exited`). So the crash is **uninstrumented**; its address is unknown.
- The zoom path is `FUN_10006752` (SIMSPR) -> `FUN_100071a3` + `FUN_1000c9bd` + the grid-B walkers
  (`FUN_1000cedb`/`FUN_1000ef50`/`FUN_1000d0f5`/`FUN_1000be25`, all grid-B-clamped). The original crash
  (§4) was an OOB grid-B index on resize; this is plausibly the **same class on the zoom path at the
  resized (2048x1081) window size**, in a structure/path the current clamps do not cover.
- `[UNCERTAIN]` — not localized. It only surfaced now because before step 11 the view never rendered, so
  the owner never zoomed around a resized view.

## Next

Add a **process-wide vectored exception handler (VEH)** to the mod that logs any AV with the faulting
`MODULE+RVA` + access address (the §4 methodology, "build the fault-catcher first") - the game swallows
the fault so only our own logger can capture it. Re-run, zoom to reproduce, read the address, then fix
(likely another grid-B clamp or a grid resize on the zoom path). `verify/resize_zoomcrash/`.

## Status

- `D-004` CONFIRMED; **defects A + B FIXED** (render complete end-to-end, no toggle needed).
- NEW: zoom-after-resize crash, uninstrumented, blocks shipping. Instrument next.
