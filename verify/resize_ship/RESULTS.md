# RESULTS — `sc3resize` slim mod DLL, validation run (2026-08-28)
# **WIRING VALIDATED end to end. Pixels still clipped — and the cause is a flaw in MY sequence.**
# PRE + amendments: git `4fc0988`, `b296bd8`, `f0f741b` (all committed before the lease).

Install verified correct before launching: `SIMSPR.DLL` `f5b9f1d9` (owner's four-recipe),
`GZGraphicD.dll` `acefadf0`, SIMDIRT/SIMUI back to shipped. The previous attempt was **refused** on a
contaminated install (`f0f741b`); this one ran on the right one.

## Wiring — every pre-registered failure mode is EXCLUDED
| pre-registered outcome | result |
|---|---|
| 2 — injects but no bridge captured | **excluded** — bridge captured |
| 3 — bridge captured but poll never fires | **excluded** — poll fired and detected the change |
| 5 — crash or hang | **excluded** — game exited **code 0**; `FUN_10018cdf` returned in **50 ms** |

```
### RESIZE: SIMSPR base 0x03320000 (relocated: YES)  GZGraphicD base 0x02F90000 (YES)
### RESIZE: armed - bridge capture at SIMSPR+0x16EBA, per-frame poll at GZGraphicD+0x18C58
### RESIZE: window 0x003B0D22 subclassed (old proc 0x73F32D00)
RZ   size change: client 1280x1024 vs render target 800x600
RZ   extent BEFORE: (-535,1946,265,2546) -> 800x600  dirtygrid=40x30 cell=20x20
RZ   extent AFTER:  (-535,1946,745,2970) -> 1280x1024 dirtygrid=40x64 cell=32x16 (cell sizes plausible)
RZ   render-target  FUN_10009efb -> 1 | now +0x24=1280 +0x28=1024
RZ   device-surface FUN_10009efb -> 1 | now +0x24=1280 +0x28=1024
RZ   FUN_10018cdf -> 1
```
⭐ **Both modules were RELOCATED** (`0x03320000`, `0x02F90000`) — position independence exercised
live, not assumed. The extent again read a **negative** left (`-535`), confirming world space.
The **external** `SetWindowPos` drove a genuine `WM_SIZE` from outside the process, which is a
stricter test than the harness posting its own message.

## The screenshot — instrument GOOD, result CLIPPED
The new instrument is **not** a silent failure: 1280x1024, **8,019 distinct colours**, 255 grey
levels. It captured a real, rich image. But:

```
bbox rows 0..599, cols 0..799  =>  content extent 800x600   (36.1% of the surface)
```

**The presented frame is still clipped to the OLD 800x600, in the top-left.** This is run 2's exact
signature — on screen, where run 6 had proved the *render target* holds a full 1280x1024 image.

## ⛔ THE CAUSE IS A FLAW IN MY OWN SEQUENCE, and it was written down in this repo already
Step 9 of the documented sequence says *"present rect — already ships as `resize_rectfix`"*.
**That is wrong.** `BOARD.md:668` states plainly: **"`resize_rectfix` is inert unless the iso Init
runs."** The cave hooks **Init** and replays the ctor's `push_back {0,0,w,h}`.

**The minimal routine's whole design is that it NEVER calls Init.** So `resize_rectfix` never fires,
the present-rect list keeps its old `{0,0,800,600}`, and the per-frame present `FUN_1000e058`
iterates that stale rect — presenting an 800x600 window onto a correctly-rendered 1280x1024 target.

**Init-free and `resize_rectfix` are mutually exclusive, and I documented them as complementary.**
The two facts sat one file apart and I never put them together. Every previous run censused the
render target directly, which is *upstream of the present*, so nothing before this run could have
caught it.

**Fix, and it is small:** the DLL must push the present rect itself — replay `FUN_10010586` into
`iso+0x4d0` with `{0,0,w,h}`, in C, as step 9. `resize_rectfix` is then irrelevant to this mod
(and stays useful only to an Init-driven path).

## Two other defects found, both mine, neither fatal
1. ⚠️ **`FUN_1000fa36` (step 8) is UNLOGGED** — I gave it no `logf`, so this run carries **no
   evidence it ran**. The sequence log jumps from `FUN_10018cdf` to `done`. Not a failure, but step 8
   is **unwitnessed here** and must not be reported as confirmed. Add the log line.
2. ⚠️ **The `+0x0c` `[UNCERTAIN]` from the costing is now MEASURED, and it is real.** The tuple
   reconstructed from the object's own fields reads `p3 = 7`; the harness's *recorded* create tuple
   for the render target was `p3 = 4`. So **field read-back does NOT reproduce the recorded tuple.**
   `FUN_10009efb` returned 1 and the dims followed, and the visible region is a rich correct image,
   so it is **not** obviously harmful — but the costing's assumption that reconstruction is
   equivalent is **not** supported. Left open, and the mod should keep a recording hook or this
   should be understood before ship.
3. Cosmetic: `bridge captured ... iso view = bridge+0x18 = 0x00000000` — the iso view is NULL at
   capture time. Harmless (the poll re-reads `bridge+0x18` every frame, which is why the resize found
   `iso=0x0E220BF0`), but the log line reads like a failure. Log it at poll time instead.

## Verdict
**WIRING VALIDATED — pixel verdict still owed, exactly as the amendment predicted the ceiling would
be.** The delivery vehicle, injection, both hooks, the subclass, the poll, the trigger and 7 of the
8 executed steps all work on a relocated, real-`WM_SIZE` path. The remaining clip is a **named,
localised, one-call gap**, not a mystery.

## State at close
Owner's build untouched and verified: `SIMSPR.DLL` `f5b9f1d9`, `GZGraphicD.dll` `acefadf0`. The mod
patches nothing on disk. Lease and harness claim released; no game process alive (exit code 0).
Artifact: `sc3resize_validation_clipped_800x600.png`.
