# RESULTS — zoom-crash fix (guard rows + churn fix), 2026-08-30

**VERDICT: PASS. The in-city viewport is complete end-to-end.** Owner-confirmed: after a resize, zoom
in/out renders correctly (no black), and there is no crash.

## The two changes

1. **Guard rows (`RZ_SURFACE_SLACK = 8`)** in `rz_recreate_raster` — allocate the render target / device
   surface `ht+8` rows tall. Fixes the `FUN_1000239d` zoom-blit overrun (companion write one scanline
   past the buffer). No more `GZGraphicD FUN_1000239d+0x1a1` fault.
2. **Poll settle-check tolerance** in `rz_poll` — treat width-equal AND height in `[ht, ht+SLACK]` as
   settled. Fix v1 (guard rows alone) had made `R+0x28 == ht` a permanent mismatch, re-resizing every
   frame; that churn caused black zoom + a zoom-out race crash (`FUN_10014fb4+0x1f9`, null read). With
   the tolerance, one resize per real size change.

## Evidence (final run)

- **One** `done (all 11 steps)` per size change (was dozens) — churn gone.
- **No `*** VEH FAULT ***`** on zoom (only the benign startup `0xC0000096` probe the game handles).
- ~42 s of gameplay: maximize to 2048x1081, zoom in/out, pan, clean shrink to 800x600 at exit.
- Owner: "zoom in/out renders correctly - no black, no crash."
- Install unchanged (`SIMSPR f5b9f1d9`, `GZGraphicD acefadf0`); no on-disk change.

## The zoom-out crash was churn-induced

`FUN_10014fb4+0x1f9` null-deref did NOT recur once the churn was gone — it was a resize racing a
mid-flight zoom-out, not an independent bug. The VEH logger (retained) would re-capture it if it were.

## Status — the in-city view is DONE

- `D-004` (window fills monitor) ✅
- Render after resize, no toggle ✅ (step 11)
- Zoom in/out stable, renders, no crash ✅
- Crash fix engine-wide (grid-B clamps) + zoom-blit guard rows ✅

Remaining (separate workstream, always the "row 5" gap): the **HUD/UI does not reflow** — it keeps the
1024x768 layout with margins. New feature request from the owner 2026-08-30; scoped separately.
