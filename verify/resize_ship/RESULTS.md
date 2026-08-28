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

---

# RUN 2 (`sc3resize` v2, 2026-08-28) — **FAIL, outcome 4: the game died before the resize.**
# PRE amendment git `8d8a796`. **And the failure isolates cleanly to ONE of the three fixes.**

The game process was **gone before the 40 s mark**; the mod log stops at **t+9.56 s**, immediately
after `bridge captured`. The external resize at ~t+42 s found a `0x0` client rect because there was no
window left. No screenshot (correctly — the instrument refused rather than saving a blank).

```
### RESIZE: SIMSPR base 0x03310000 (relocated: YES)  GZGraphicD base 0x02690000 (YES)
### RESIZE: armed - bridge capture at SIMSPR+0x16EBA, create recorder at GZGraphicD+0x9EFB,
            per-frame poll at GZGraphicD+0x18C58
### RESIZE: window 0x00FC072C subclassed
RZ   WM_SIZE 2048x1152 - poll will pick it up on the next frame
### RESIZE: bridge captured 0x0E64BCD0 (iso view = bridge+0x18 = 0x00000000)
                                                     <- log ends here, t+9.56 s
```

## ⭐ The failure isolates to the create recorder — by construction, not by suspicion
v2 changed **three** things, but two of them **cannot have run**:

| fix | active before the resize? |
|---|---|
| step 9 present-rect erase+push | **NO** — only runs inside `rz_do_resize`, and no resize ever happened |
| step 8 `FUN_1000fa36` logging | **NO** — same, and it is a log line either way |
| **`FUN_10009efb` create-recorder hook** | **YES** — installed at startup, fires on every raster create |

**So the only v2 code that executed before the death is the recorder hook**, which is exactly what the
pre-registration named as outcome 4's prime suspect (*"the new `FUN_10009efb` hook is the prime
suspect (it is a hot function)"*). Called out before the run, confirmed by the run.

`[UNCERTAIN]` **the mechanism.** No exception was logged and no dump was produced, so *why* it dies is
not established. Two candidates, neither verified: (a) `FUN_10009efb` is called on more than one
thread and the recorder's `g_rc[n]`-write-then-`InterlockedIncrement` is not actually safe — the slot
index is read non-atomically; (b) detouring a function this hot, inside device bring-up, is not
survivable the way the two cold hooks are. **Do not report either as the cause.**

## What run 2 did NOT invalidate
Run 1's result stands untouched: injection, both original hooks, the subclass, the poll, the trigger,
and the executed steps all worked, with the game exiting **code 0**. **The v1 hook set is known-good.**
The step 9 and step 8 fixes are **untested, not refuted** — they never ran.

## Correct next move — one variable, not three
**Drop the create recorder; keep the step 9 and step 8 fixes.** That returns to the known-good two-hook
set and tests the fix that actually addresses the clipped frame. The tuple question then reverts to
the honest position: field read-back is used, it is **measurably not identical** to the recorded create
(`p3` 7 vs 4), and the replay **logs which path it took** — a recorded caveat rather than a silent
assumption. If the frame comes back correct at 1280x1024 with field read-back, the discrepancy is
demonstrably benign for this purpose and the recorder was never needed.

⚠️ **I changed three things at once after a run that had already told me what to fix.** Run 1's clipped
frame pointed at exactly one defect. Bundling two more in cost a lease and told us nothing about the
one that mattered.

## State at close
**No orphan processes** (checked: zero `SC3U`/`resize_launch` alive). Owner's build untouched and
verified: `SIMSPR.DLL` `f5b9f1d9`, `GZGraphicD.dll` `acefadf0`. The mod patches nothing on disk. Lease
and harness claim released.

---

# ⛔⛔ CORRECTION — BOTH DLL RUNS ARE CONFOUNDED. I never controlled the DISPLAY MODE.
# Raised by the owner, 2026-08-28: *"were you launching fullscreen?"* The honest answer is
# **I don't know, because I never set it** — and that undermines the conclusions above.

**The six runs that validated the routine all used**
`-nocom -windowed -origin -fix16 -fitclient -nointro -quiet` (`capture.ps1:24`).

Those are not cosmetic. `-windowed` is a **live patch**: `patch_windowed` pokes
**`GZGraphicD+0x6cdac = 1`** plus a nop at `0x117D6` so Init yields windowed
`[CONFIRMED @ sc3probe.c:7311, 7336]`. `-fix16` patches the surface format. `-fitclient` sizes the
client.

**`sc3resize.dll` implements NONE of them — measured: zero occurrences of any display-mode handling
in the file.** `resize_launch.exe` passes no switches either; it only injects and forwards the city
path. **So both DLL runs launched the game in its DEFAULT display configuration, which is not the
configuration anything in this workstream was validated under.**

Corroborating oddity I logged and did not question: the window's client read **2048x1152** at
detection and **800x600** at resize time in run 1, and run 2 logged `WM_SIZE 2048x1152`. I recorded
those numbers and moved on.

## What this does to the conclusions above
| claim | status now |
|---|---|
| run 1 "WIRING VALIDATED" | **weakened.** Injection, hooks, subclass, poll and trigger did demonstrably work — but under an **uncontrolled display mode**, not the validated one |
| run 1 "the clip is caused by the missing present rect" | **still well-grounded** (`resize_rectfix` is Init-gated and the routine is Init-free — a static fact), **but I asserted it as THE cause without controlling for mode.** It may not be the only contributor |
| run 2 "isolates to the create recorder" | **the isolation logic holds** (steps 8/9 provably never ran), **but the mechanism is even less settled**: hooking `FUN_10009efb` during DirectDraw bring-up in an unknown display mode is a different proposition from doing it in the harness's patched windowed mode |

## The real defect in my method
The DLL was carved to reproduce a routine validated under six specific patches, and **I carried over
the routine but none of its preconditions.** Worse, I never asked what mode it was launching in — the
2048x1152/800x600 mismatch was in my own log twice.

**Before any further DLL run:** decide and CONTROL the display mode explicitly — either replicate
`-windowed` (`GZGraphicD+0x6cdac`) and `-fix16` inside the mod, or run the mod under the harness
launcher with those switches so the only variable is the mod itself. **Until then, neither DLL run
should be cited as evidence about the routine.**

---

# RUN 3 (`sc3resize` v3, 2026-08-28) — CONFOUND FIXED. Real windowed resize TRIGGERED.
# New crash inside FUN_10018cdf. PRE amendment git `e1b2716`.

**The display-mode fix worked and it changed everything about how the run behaved.**

```
--- WINDOWED: GZGraphicD+0x6cdac = 0 -> 1
--- WINDOWED: GZGraphicD+0x117D6 'mov [ebx+0x48],1' -> nop x4
--- FIX16: 16bpp branch injected at 0x19349 -> cave 0x03530000 (5-6-5)
### RESIZE: armed ... (create recorder DROPPED after v2 crash)
### RESIZE: window 0x00200CF0 subclassed
### RESIZE: bridge captured 0x0D3295F0
RZ   WM_SIZE 2048x1081 - poll will pick it up on the next frame
RZ   size change: client 2048x1081 vs render target 800x600
RZ   extent AFTER: (-848,2924,1200,4005) -> 2048x1081  dirtygrid=16x8 cell=128x135 (cell sizes plausible)
RZ   render-target  iso+0x74  FUN_10009efb -> 1 | now +0x24=2048 +0x28=1081
RZ   device-surface iso+0x4ec FUN_10009efb -> 1 | now +0x24=2048 +0x28=1081
                                                  <- log ends here, t+11597 ms
```

## What this run PROVED (all new, all under the correct display mode)
- ⭐ **`patch_windowed` took: the window is now a real 800x600 titled window** (`'SimCity 3000'`,
  client 800x600) — v1/v2 launched at **2048x1152** (fullscreen desktop). The confound is gone.
- ⭐ **`patch_surfacefmt` (fix16) installed cleanly**, no crash from the cave.
- ⭐ **The recorder drop fixed the v2 startup crash** — the game reached a city and ran to t+11.6s.
- ⭐ **The routine triggered on a REAL, game-driven resize**, not a synthetic one: windowed mode
  auto-maximized the window to **2048x1081** at t+11.6s and the per-frame poll caught it. Extent math,
  cell-size gate, and both `FUN_10009efb` replays all succeeded at that size.

## The crash — localized, but a NEW problem
Exit code **`0xC000041D` = STATUS_FATAL_USER_CALLBACK_EXCEPTION** (an exception inside a Win32
callback). The log stops **after** the device-surface replay returned 1 and **before** the
`FUN_10018cdf` line, and that logf calls `FUN_10018cdf` first — **so the crash is inside
`FUN_10018cdf`** (the tile-cache refill/repaint, step 7), surfacing as a callback exception because the
poll runs inside the `FUN_10018c58` paint hook.

`[UNCERTAIN]` **why FUN_10018cdf faulted here when it returned in 47-50 ms across six harness runs.**
Three differences from those runs, none yet isolated:
1. **Size**: 2048x1081 (odd height) vs the validated 1280x1024. `gw/gh` = 16x8 here vs 40x64 there.
2. **Timing**: this resize hit at **t+11.6 s, ~5 s after bridge capture** (city just loaded); the
   harness resized at ~t+42 s, long after load.
3. **The trigger**: a windowed **auto-maximize** to the full desktop, not a chosen 1280x1024.
4. **fix16 + our surface replay together at a new size** — the two were both present in the harness
   runs, but not at 2048x1081. **Do not assert any of these as the cause.**

⚠️ **My intended clean 1280x1024 test never ran** — the window auto-maximized to 2048x1081 first and
crashed there. The screenshot is stale (0% — taken after the crash) and carries no verdict.

## Where this leaves the mod
The delivery, injection, display-mode control, both hooks, subclass, poll, trigger, extent, grid and
BOTH surface replays are now demonstrated **under the validated display mode**. The failure is a single
localized fault in step 7 on a large/early/auto-maximize resize. Steps 8 and 9 **still have never
executed** — the crash is upstream of them.

**Recommended next, and it should be ONE change:** stop the window auto-maximizing so the poll fires at
a controlled size after load — either open the window at a fixed size, or gate the poll to ignore the
first N seconds / require the size to be stable for two polls. That isolates "does the routine work at
1280x1024 as a DLL" from "does FUN_10018cdf survive a 2048x1081 auto-maximize 5 s after load", which
are two different questions I have been accidentally testing at once.

## State at close
No orphan processes. Owner's build untouched and verified: `SIMSPR.DLL` `f5b9f1d9`, `GZGraphicD.dll`
`acefadf0`. The mod patches nothing on disk. Lease and harness claim released.
