# RESULTS — whole-view repaint (step 10), 2026-08-30

**VERDICT: FAIL as pre-registered — marking dirty is not enough; the DEVICE BATCH is the operative
part.** Step 10 ran clean and did not fix the screen; two new owner observations localize the fix
precisely.

Pre-registration: `PRE.md` (`f3cafeb`). Matched outcome: "Step 10 runs but the view is still
blank/partial until a toggle → FAIL — marking dirty is not sufficient; the device begin/end batch is
required. Next: add the `bridge+0x14` device `+0x240`/`+0x244` bracket."

## Log

```
[step 10] FUN_1000db86 returned - iso+0x32c=1 (full-redraw pending)
---- done (all 10 steps) ----
```
`FUN_1000db86` (iso vt+0x144, PE-verified) executed, the full-redraw flag is set, no fault. Still "same
as before" on screen. Install unchanged (`SIMSPR f5b9f1d9`, `GZGraphicD acefadf0`).

## Two decisive new observations

1. **Rotating the view does NOTHING.** Rotation runs `FUN_10006a55` -> `FUN_100071a3` (the full
   hide/show transition) plus the repaint work, and it does **not** fix the render. This **refutes the
   rotate/zoom-transition idea outright** (the earlier "Option B") and confirms the fix is **not** in
   the iso-view transition/repaint path.
2. **Only switching to a DATA/UTILITY overlay (underground, water) and back fixes it.** The distinctive
   thing that path does, which rotation does not, is the **device begin/end batch** around the
   base-view repaint: `FUN_1001818c:53-55` / `FUN_10018cdf:154-156` run
   `(*(cMapView+0x14)+0x240)()` [device begin] ; `(*(cMapView+0x18)+0x144)()` [iso repaint] ;
   `(*(cMapView+0x14)+0x244)()` [device end/present].

## Conclusion

The missing step is the **device batch** (`bridge+0x14`, slots `+0x240` begin / `+0x244` end) that binds
and presents the recreated surface. Step 10 called the iso repaint (`+0x144`) **without** that bracket,
so the view was marked dirty and composited into `iso+0x74` but never presented on the recreated device
surface. Rotation redraws but also never runs the device batch, which is why it fails too.
`[CONFIRMED behavior @ SIMSPR 0x1001818c:53-55]`. The batch slot targets are on the GZGraphicD device
vtable (called through the live pointer, as the engine does).

## Next build

Wrap step 10's repaint in the device batch, exactly as `FUN_1001818c:53-55`:
`device+0x240` (begin) -> `FUN_1000db86` (repaint) -> `device+0x244` (end), with `device =
*(bridge+0x14)`, called through the live device vtable, IsBadReadPtr-guarded, under the SEH catcher.
`verify/resize_present/`.

## Status

- `D-004` remains CONFIRMED.
- Defects A+B open; the fix is now localized to the **device present batch**, not the drawable or
  repaint layers (both falsified: 8a/8b, 8c, and step-10-alone).
- Rotation as a repair is **refuted**.

## What was NOT done

No on-disk change. No further iso-view repaint/registration variants (that whole layer is falsified).
