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

---

# RUNS 2 & 3 — the v3 crash does NOT reproduce under ANY tested condition. Routine is robust.
# PRE amendments git `55909f8`, and the run-3 amendment. Both clean, zero `FAULT CAUGHT`.

| run | timing | zoom | target | result |
|---|---|---|---|---|
| 1 | t+42s (settled) | 0 (forced) | 2048x1152 | all 9 steps, no fault |
| 2 | **t+5.3s (during load**, bridge at t+3.85s) | 0 (forced) | 2048x1152 | all 9 steps, no fault |
| 3 | t+42s (settled) | **3 (load zoom, no force)** | 2048x1152 | all 9 steps, no fault |
| + | run 1's window settle | 0 | 2048x1081 | all 9 steps, no fault |

**Five conditions now exclude the v3 crash:** size 2048x1152 and 2048x1081, zoom 0 and zoom 3, timing
t+5s (during load) and t+42s (settled). `FUN_10018cdf` returned 1 every time. The SEH catcher never
fired — **no exception occurred in `rz_do_resize` in any run.**

## Conclusion: the v3 crash is NOT REPRODUCIBLE with this build
- ⛔ My "isolate timing" framing (run 2) was itself confounded — runs 1 and 2 both forced zoom 0 while
  v3 was zoom 3. Run 3 corrected it (zoom 3, no force) and **still did not crash.** So neither timing
  nor zoom is the trigger.
- The routine completes cleanly at 2048x1152 across both zooms and both timings. **The earlier
  "resize during load is the cause" `[UNCERTAIN]` is now also unsupported** — run 2 resized during load
  and was clean.
- The v3 crash (`0xC000041D`, one occurrence) is most consistent with a **transient tied to the exact
  auto-maximize-during-load sequence** that these five controlled reproductions did not recreate, OR a
  consequential fault outside `rz_do_resize` that the SEH around the routine would not have caught
  anyway. `[UNCERTAIN]` — and, correctly, NOT asserted.

## Net effect on the workstream
The "hard size ceiling" / "it crashes at 2048" narrative is reduced to **a single non-reproducing
incident.** The mod's resize routine is now demonstrated robust at 2048x1152 across zoom and timing on
a dense city. What is genuinely open is smaller than it looked: (a) a load-readiness gate on the poll
is still good hygiene (cheap, do it); (b) the on-screen correctness at large sizes is unverified
(the screenshot is `D-004`-ambiguous) and needs a real display or a census-in-mod; (c) downward resize
`U-069` untested.

## Honest scorecard (final for the crash arc)
Three asserted causes, three refutations: DirectDraw primary (refuted by leaf-blit trace), int[16384]
overflow (refuted by census + this), resize-during-load timing (refuted by run 2). Plus one
self-inflicted confound (minzoom on during the "timing" test). **The SEH catcher — built last — is what
turned the question from repeated wrong guesses into "not reproducible under 5 controlled conditions."
Build the catcher first next time.**

## State
No fault, no orphan, owner build verified `f5b9f1d9` / `acefadf0`, mod patches nothing on disk, lease +
claim released.
