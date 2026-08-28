# RESULTS — crash hunt at min zoom (2026-08-28). ⭐ **OUTCOME 2: NO CRASH. The v3 crash did NOT reproduce.**
# PRE git `a229a83`. This refutes BOTH the 16384-overflow story AND my step-7 localization.

Europolis, `-windowed -fix16`, `SC3RESIZE_MINZOOM=1`, external resize to 2048x1152 at t+42s (a
**settled** city). **Zero `FAULT CAUGHT` lines. Zero crash. Game exited clean.**

```
### sc3resize loaded ... [MINZOOM crash-hunt build]
RZ   size change: client 2048x1152 vs render target 800x600
RZ   MINZOOM: forcing zoom 3 -> 0 before resize
RZ   MINZOOM: zoom now 0
RZ   extent AFTER: (-848,2924,1200,4076) -> 2048x1152  dirtygrid=16x12 cell=128x96 (cell sizes plausible)
RZ   FUN_10018cdf -> 1
RZ   [step 8] FUN_1000fa36 returned
RZ   [step 9] present list ... erase then push {0,0,2048,1152} ... after: 1 rect
RZ   ---- done (all 9 steps) ----
   ... and AGAIN at t+75s when the window settled to 2048x1081, also all 9 steps, no fault.
```

**All 9 steps completed at 2048x1152 AND 2048x1081, at forced MIN zoom (0), twice.** `FUN_10018cdf`
(the step-7 function I had blamed for v3) returned **1 in ~62 ms** — exactly as in the safe harness runs.

## What this settles
1. ⛔ **The 16384-overflow root cause (`609e97a`) is FULLY REFUTED.** Min zoom (the hypothesized worst
   case) at 2048x1152 (larger than the v3 crash size) ran clean. No overflow, no fault.
2. ⛔ **My "crash is inside FUN_10018cdf / step 7" localization (v3 RESULTS) is REFUTED.** Step 7
   completes here at a larger size and min zoom.
3. **The SEH catcher proved it:** had any step faulted, `FAULT CAUGHT ... STEP n ... MODULE+RVA` would
   have logged. It did not fire — the routine genuinely did not fault.

## The real correlate of the v3 crash: TIMING, not size/zoom
The one salient difference left between v3 (crashed) and this run (clean):
- **v3**: the window auto-maximized and the poll fired the resize at **t+11.6 s — ~5 s after bridge
  capture, while the city/renderer was still initializing.**
- **this run**: the resize fired at **t+42 s on a fully settled city.**

Size (2048), zoom (min), and the routine are now all excluded. **The evidence points to a
resize-during-load race** as the v3 cause. `[UNCERTAIN]` — not proven; the direct test is to fire the
resize early (t+~11 s) on this SEH build and see if the fault returns and where. But the actionable fix
is already implied and cheap: **gate the poll until the city is fully initialized** (e.g. N seconds
after bridge capture, or on a readiness field), which the mod should do anyway.

## Screenshot — AMBIGUOUS, do not over-read
2048x1152, 2,319 colours, content bbox 808x608. At **min zoom** the Europolis diamond occupies only
part of a 2048-wide view, so an ~800px content region is **consistent with a correctly zoomed-out city
that simply does not fill the huge viewport** — OR with a clip. `PrintWindow` is also `D-004`-suspect
for a DirectDraw frame. **The log is the witness (no crash, present rect set to full size); the
screenshot decides nothing here.** Artifact: `sc3resize_2048x1152_minzoom_noCrash.png`.

## Honest scorecard for this workstream's crash diagnosis
I asserted a root cause twice from static/structural evidence without the load-bearing measurement, and
was wrong twice: first "un-resized DirectDraw primary" (refuted by the leaf-blit trace), then "fixed
int[16384] overflow" (refuted by the zoom-3 census AND now by this clean min-zoom run at 2048x1152).
The SEH catcher is the instrument I should have built first — it converts the crash from a guessing
game into a logged address.

## State
No fault, no orphan (0 processes). Owner build verified `f5b9f1d9` / `acefadf0`. Mod patches nothing on
disk. Lease + claim released.
