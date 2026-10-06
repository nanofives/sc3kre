# RESULTS — the 2026-10-05 maximize crash

Pre-registration `PRE.md` (`5803fa0`). Build 194,048 B.

## Run

30 maximize/restore cycles through sc3io, restores alternating 800x600 / 1280x800 / 1600x900:
**0 access violations, window alive throughout** (`churn.txt`). A second build (view-identity fix)
ran 4 more cycles, also 0.

## Reading, per the pre-registered table

"No AV in 30 cycles: consistent with the guard, NOT proof." That stands. `RCIFIX>` never logged in
this run or in the crash run, so the RCI blit never completed in either. That leaves RCIFIX neither
cleared nor implicated: a crash on its first blit would also leave no log line.

## A competing explanation

The crash client was 1680x979, which is a 1680x1050 display maximized. By the time of this run the
desktop had gone from four displays to that one display. A display-topology change under a running
SC3U was measured on 2026-09-07 to kill it, and lost DirectDraw surfaces would leave exactly a
raster with `+0x44 = NULL`. If the monitors changed while the owner maximized, that is the more
likely cause. `[UNCERTAIN]`, owner to confirm.

## What is in place either way

- `rz_repaint_rci` refuses to blit when either raster's `+0x44` is NULL.
- The VEH logs `in_rci_repaint` and up to 14 module-resident stack words, so a repeat names its caller.

Decisive check: the owner's hand maximize on this build.
