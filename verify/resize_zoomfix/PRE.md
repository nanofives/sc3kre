# PRE-REGISTRATION — zoom-crash fix: surface guard rows

Committed before the hand-test. Owner is the instrument.

## Why

Zoom-after-resize crash localized (`verify/resize_zoomcrash/`): `GZGraphicD FUN_1000239d+0x1a1`
(RVA 0x253E), a zoom-scaled 16bpp blitter with NO vertical clamp to the surface height. Its 2x/4x
branches issue companion writes one-to-~three scanlines BELOW the current row (vertical up-scaling);
when a bottom-edge tile at higher zoom reaches the surface's last row, the companion write spills one
page past the buffer -> `0xC0000005 WRITE at edx+pitch` (witnessed: addr = base+0x1000, pitch 0x1000 =
2048px). The surface is correctly WIDTH-resized (pitch witnessed); it is one row too SHORT.

## The change (`re/harness/src/sc3resize.c`, `rz_recreate_raster`)

Allocate **`RZ_SURFACE_SLACK = 8` guard rows** below the visible height: `ca[1] = ht + 8` in the
`FUN_10009efb` replay (was `ca[1] = ht`), for BOTH the render target `iso+0x74` and the device surface
`iso+0x4ec`. The companion writes of the last visible row then land in mapped guard space. Pitch is
width-based (unaffected); the present rect (step 9, `{0,0,w,ht}`) shows only the top `ht` rows, so guard
rows are never presented. One-value change to an existing, validated call. VEH crash logger retained so a
residual fault is captured, not blind. No on-disk change.

## Outcomes, committed in advance

| observation | verdict |
|---|---|
| Log `replay at WxH (+8 guard rows ...)` AND after a resize you can **zoom in/out freely with no crash** and the city renders | **PASS — zoom crash fixed, mod complete end-to-end** |
| Still crashes on zoom; log shows a NEW `*** VEH FAULT ***` at `GZGraphicD FUN_1000239d` with a LARGER `edx+N` (N > 0x1000) | **PARTIAL** — guard too small (a 4x/large-sprite spill exceeds 8 rows); raise `RZ_SURFACE_SLACK`. The new N sizes it |
| Crashes with a VEH FAULT at a DIFFERENT address | **FAIL, new site** — a second overrun elsewhere; localize from the new address |
| Renders wrong / 8 garbage rows visible at the bottom | **FAIL** — guard rows are being presented (present-rect assumption wrong); report |
| No crash but zoom looks visually off | **note it** — separate from the crash |

**Decisive:** resize, then zoom in and out repeatedly - does it stay up and render.

## Falsifiability

If it still crashes in `FUN_1000239d` with a bigger overrun delta, the guard-row count is just too small
(sizable/4x sprites) - the fix direction is right, the constant needs raising, and the new VEH delta
tells us to what. If it crashes elsewhere, guard rows were not the (only) cause.

## Protocol

Harness claimed `handtest`. Owner launches, resizes, then ZOOMS IN and OUT several times (and pans), and
reports. Prior log archived `re/harness/sc3resize_handtest.veh1.log`. Install (`SIMSPR f5b9f1d9`,
`GZGraphicD acefadf0`) verified before/after; no on-disk change.

## STATUS

Built + string-verified (`guard rows`, `zoom-blit overrun fix`, VEH logger + step 11 retained; PE32;
install intact). Pre-registered. Awaiting the owner hand-test.

---

## RESULT v1 (guard rows) + churn fix (2026-08-30)

**Guard rows STOPPED the original overrun** — no more `FUN_1000239d` fault. **But it caused a
regression I introduced:** padding the render target height to `ht+8` (1089) made the poll's settle
check (`R+0x28 == ht`) a permanent mismatch (1089 != 1081), so the resize routine **re-fired every
~130ms** (dozens of `done (all 11 steps)` in the log). That churn -> **zoom renders black** (never a
stable frame) and, deep in the churn, a **zoom-out crash**: a NEW, different fault
`GZGraphicD FUN_10014fb4+0x1f9` (RVA 0x151AD), `READ addr=0x00000000`, `ecx=0` — a null deref
consistent with a resize racing a mid-flight zoom-out (surface torn down under it).

**Churn fix:** the poll's settle check now tolerates the guard rows — width-equal AND height in
`[ht, ht+RZ_SURFACE_SLACK]` counts as settled (`rz_poll`). One resize per real size change again; no
per-frame churn. VEH logger retained: if the zoom-out null-deref is independent (not churn-induced), it
will be re-captured at `FUN_10014fb4` and localized then.

Expected on re-test: resize settles (one cycle), zoom in/out renders and does not crash. If black
persists with NO churn in the log, the guard-row height change itself breaks the composite (revisit).
If zoom-out still nulls at `FUN_10014fb4`, that is a real independent bug to fix next.
