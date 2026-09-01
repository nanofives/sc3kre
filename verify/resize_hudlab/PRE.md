# PRE-REGISTRATION — HUD lab: surface census + sampling profiler (2026-08-31)

**One lease, one build, two read-only instruments, one within-run control.**

## Why this run exists

Two claims closed the HUD workstream. Neither was measured.

1. **"The full-width HUD bar's FPS cost is intrinsic to per-frame compositing."**
   `verify/resize_hud/RESULTS.md` reaches this by elimination: three hypotheses falsified (device
   batch, iso overlap, per-tick invalidate) plus a read of `FUN_10026144` showing it is not an
   invalidator. **No one has ever measured where frame time goes.** This is the board's own recurring
   failure mode — asserting a cause from structure instead of building the instrument
   (see the crash-arc scorecard: three asserted causes, three refutations, settled only by the SEH
   catcher). This run builds the instrument.

2. **"The HUD children are a class our model does not cover."**
   The 2026-08-31 diagnostic found all 6 children `g_hud_top[0x2a..0x2f]` carry vtable
   `GZGraphicD+0x1E894` and read that as the model being wrong at a new layer. **`+0x1E894` is the
   raster surface base class this project already mapped** — `LAUNCH_CONTROL.md:4048` logs a device
   with that exact vtable, `RESIZE_DELIVERY_COST.md:47` names it "raster (`+0x1E894`)", and
   `rz_census_one()` in `sc3resize.c:338` already reads that family: dims `+0x24/+0x28`, bpp `+0x10`,
   sub `+0x44`, raw bits `sub+0xf0`, pitch `sub+0xf4`.

   Under that reading the two blockers are one fact: **the bar is composited from fixed-extent raster
   surfaces.** `vt+0xcc` being a flag getter (`FUN_10009ea2`) and `+0xe0` being garbage are then
   expected, not anomalies — a surface has no set-position.

## Hypothesis under test

**H:** the HUD bottom bar's children are raster surfaces of the `GZGraphicD+0x1E894` family whose
extent is fixed at construction, and the full-width FPS cost is the per-frame blit of a widened bar
region — attributable to a nameable function, not diffuse "compositing".

## Instruments (both READ-ONLY except the one SetRect already proven safe)

### I1 — HUD surface census
For each child `g_hud_top[0x2a..0x2f]`: vtable identity (is it `gz+0x1E894` / `gz+0x1F328`?), dims
`+0x24/+0x28`, bpp `+0x10`, sub `+0x44`, raw `sub+0xf0` bits and `sub+0xf4` pitch, plus a non-zero
pixel census. Reuses the validated raw-read discipline: **never call `vf1c` out of band** (standing
rule — the out-of-band lock tears the backing down).

Logged **twice**: before the SetRect widen and after it.

### I2 — EIP sampling profiler
A dedicated sampler thread suspends the game render thread, reads `Eip` via `GetThreadContext`,
resumes, and buckets by `eip >> 6` (64-byte granularity) in a lock-free open-addressed table.
Nothing is logged while the thread is suspended. Game thread id is captured in the existing
heartbeat hook (`fnlog_enter` idx 1), which already runs on the render thread. At dump time each
bucket resolves through `rz_modstr` to `MODULE+0xRVA`; top 30 by count.

## The within-run control — this is what makes the run decidable

Both phases run in **the same process, same city, same window size, same zoom**. The only variable
is the bar's width. The fixture supplies its own control, the pattern that made the `+0x140`
suspend-depth result clean.

| phase | bar state | duration | what is collected |
|---|---|---|---|
| A | **native 800-wide** (SetRect NOT yet applied) | 10 s | profile A + surface census (native) |
| B | **docked full-width** (SetRect applied) | 10 s | profile B + surface census (post-widen) |

Driven by a phase machine ticking in the per-frame poll (game thread), so the SetRect stays on the
thread that already performed it safely. Step 12 arms the machine; it does not widen inline.

## Pre-registered outcomes — scored as written, before the log is read

**On the FPS question (I2), diffing profile B against profile A:**

- **PASS / cause named:** the delta is concentrated — a small number of buckets (<= 5) account for
  the majority of the increase, resolving to nameable `MODULE+RVA` sites. The "intrinsic
  compositing" conclusion is then **refuted**: there is a specific hot site, and it is a fix target.
- **FAIL / conclusion upheld:** the increase is diffuse across many unrelated buckets with no
  concentration. "Intrinsic per-frame composite cost" then stands as **measured**, not merely
  inferred, and the HUD-scaling goal is correctly closed as engine-level work.
- **VOID:** total sample count in either phase < 200, or the sampler fails to attach, or the phases
  are not comparable (a resize/zoom/city change between them). **Do not interpret a VOID profile.**

**On the class question (I1):**

- **H supported:** children read as `+0x1E894`-family rasters with coherent dims/pitch (pitch
  consistent with `width * 2`, fix16), and their dims **do not change** across the SetRect. That
  identifies the fixed-extent surface as the thing a real reflow must resize, and points the fix at
  machinery steps 1-11 already own (`FUN_10009efb` create-replay).
- **H refuted:** children are not that family, or reads are incoherent (pitch/dims inconsistent, no
  readable backing). Then the raster reading is wrong and the "unknown class" write-up stands.
- **Partial:** family confirmed but dims **do** track the SetRect — the bar already re-extents itself,
  and the cost is elsewhere.

## Falsifiers, stated in advance

- If profile A and profile B are statistically indistinguishable **while the owner reports the FPS
  drop in phase B**, the sampler is not seeing the cost (wrong thread, or the cost is off-thread /
  in the driver). That is an **instrument failure, VOID** — not evidence of "no cost". The owner's
  perception is the ground truth the instrument must match.
- If the owner reports **no FPS drop at all** this run, the whole comparison is VOID (nothing to
  localize) and that itself is a finding worth recording.

## Safety

- Gated behind `SC3RESIZE_HUDLAB=1`. Unset, the mod is byte-for-byte the shipped viewport build
  with the HUD native. The default ship path is untouched.
- The only write is the HUD `vt+0xc8` SetRect, already run without crash or VEH fault (attempt 3).
- No teardown, no rebuild (that approach is falsified and stays disabled), no disk patching.
- VEH crash logger stays installed throughout.
- `SuspendThread` on the render thread is the one new risk. Mitigated: no logging or allocation
  while suspended, resume is unconditional on the same iteration, sampler exits on `g_prof_on == 0`.

## What this run does NOT claim

It does not attempt a reflow, does not resize any HUD surface, and does not produce a shippable HUD
change. It produces the two measurements that decide whether a reflow is reachable at all.

---

# RUN 2 PRE-REGISTRATION (2026-08-31) — FIX C in, HUD lab retried

Run 1 produced **no HUD data**: the resize faulted at step 7 and aborted before step 12 armed the
phase machine. Root cause found and fixed; everything above is unchanged and still the scoring
standard for the HUD question.

## What changed since run 1

**FIX C** — `FUN_1000efa1` (grid-B node REMOVE) dereferenced the NULL list terminator on its
"not found" and "empty bucket" paths, `[CONFIRMED @ SIMSPR 0x1000efa1]`. Two SIMSPR-internal,
base-invariant, fail-closed edits applied in memory (still nothing patched on disk):

1. cave at `0x615e0`, hooked at `0xefd6`, adding the missing `test eax,eax` before the unlink;
2. 2-byte in-place retarget of the empty-bucket branch at `0xefc2` to the function's `ret`.

Cave assembled and capstone-verified at its load address; hook bytes, cave slack (64 zero bytes) and
the `rel8` range all checked against the untouched `original\modules\SIMSPR.DLL`. Smoke run
confirmed both parts apply with their fail-closed checks passing.

## Pre-registered outcomes for run 2

**On FIX C (scored first — the HUD question is downstream of it):**

- **PASS:** the resize completes all of steps 1-11 at the maximized size with **no `FAULT CAUGHT`
  and no `*** VEH FAULT ***`** other than the known-benign startup `0xC0000096`, and the city
  renders. FIX C is then confirmed against the exact fault it targets.
- **FAIL, same site:** a fault at `SIMSPR+0xEFDB` or `+0xEFE3` again. The guard is then wrong or was
  not applied — check the `EFA1_GUARD` / `FUN_1000efa1` lines before interpreting anything else.
- **FAIL, new site:** a fault elsewhere. FIX C did its job and a *different* latent guard is next;
  record the address, do not re-litigate `efa1`.

**On the HUD question:** scored exactly against the run-1 criteria above (phase A vs phase B profile
concentration; child surface class/dims across the SetRect). Unchanged.

## Explicitly not claimed

FIX C is a null guard on a lookup that finds nothing. It stops the crash; it does **not** make the
stale-bucket lookup correct. Objects whose bucket changed under the new geometry are still looked up
in the wrong bucket — they simply fail to unlink instead of faulting. Whether that leaves a visible
artefact (a stale node lingering in an old bucket) is **`[UNCERTAIN]` and untested**. If the owner
reports ghost/stale sprites after a resize, that is the next thread, and it is a *different* defect
from the crash.

---

# RUN 4 PRE-REGISTRATION (2026-08-31) — HUDFIT: widen the bar's background surface

Run 2 named the blocker (a fixed 600x56 raster). Run 3 named the FPS mechanism (a GPU sync stall,
owner-confirmed). This run acts on both.

## What is new

`SC3RESIZE_HUDFIT=1` adds one step after the window SetRect: snapshot the bar background child
`[0x2a]`'s art RAW, widen the surface to the live client width via `rz_recreate_raster`
(`FUN_10009efb` through `vt+0x0c`, the same primitive the mod already runs on `iso+0x74` and
`iso+0x4ec` every resize, with its expect-or-refuse vtable gate), then tile the snapshot across the
new width. Tiling over stretching: no filtering, no new art.

## The prediction worth stating in advance

Run 3 measured the render thread blocking on `NtGdiDdDDIWaitForSynchronizationObject`, doubling when
the bar went full-width. **Until now the bar's WINDOW was 2048 wide while its backing SURFACE stayed
600 wide.** A hypothesis follows directly, and this run tests it without being designed to:

> **H-fps:** the sync stall is caused by that window/surface size MISMATCH — the engine is made to do
> something per-frame it would not do if the surface matched the window.

- **If H-fps is right:** widening the surface should REDUCE OR REMOVE the FPS drop. That would be a
  fix, not just a cosmetic improvement.
- **If H-fps is wrong:** the drop persists unchanged at full width with a correctly-sized surface.
  The stall is then about width itself, not the mismatch, and H-fps is dead.

Either result is informative and neither is assumed. **This is a prediction, not a claim** — nothing
in run 3 established the mismatch as the cause, and treating a plausible story as established is the
exact failure this board has logged repeatedly.

## Pre-registered outcomes

- **PASS:** the log shows `HUDFIT> ... widening to <liveW>x56`, `FUN_10009efb -> 1`, a tiled-pixel
  count, and `AFTER-setrect` reporting child `[0x2a]` at the live width with a COHERENT pitch — AND
  the owner sees a bar spanning the screen **with visible art**, no crash.
- **PARTIAL (blank bar):** the surface widens per the log but the owner sees a blank or garbage bar.
  Then the engine neither repaints nor preserves our tiled content, and the next question is who
  draws that surface. **A real possible outcome, flagged `[UNCERTAIN]` in the code comment** — a
  recreate discards pixels and the tiling is a mitigation, not a guarantee.
- **FAIL (refused):** `HUDFIT> recreate REFUSED` — the vtable gate rejected the object. The bar is
  left native and nothing is damaged. Read the refusal line before theorising.
- **FAIL (crash):** any `FAULT CAUGHT` or `*** VEH FAULT ***` beyond the benign startup
  `0xC0000096`. Record the address; do not retry blind.

**Scored separately and independently:** the FPS observation, per H-fps above.

## Safety

Gated behind `SC3RESIZE_HUDFIT=1` and additionally behind `SC3RESIZE_HUDLAB=1` (it runs inside the
phase machine). With either unset the mod is the shipped viewport build. The recreate goes through
the same expect-or-refuse gate that has never mispatched, and still patches nothing on disk.

---

# RUN 5 PRE-REGISTRATION (2026-08-31) — lock/tile route

Run 4's `bits=0` was diagnosed statically: `sub+0xf0`/`+0xf4` are written only by the LOCK, never by
create. So the tile step now takes a **balanced lock** around its write.

## What changed

After the recreate: expect-or-refuse the sub-object vtable against `GZGraphicD+0x1F0AC`, then
`sub->vt[0x0c]` (Lock) -> read `sub+0xf0`/`+0xf4` -> tile -> `sub->vt[0x10]` (Unlock). The unlock is
issued **only if our lock succeeded**, so we never drop the refcount below the level we took — the
precise hazard behind the standing out-of-band rule.

## Pre-registered outcomes

- **PASS:** log shows `lock ... -> 1 | depth=1 bits=0x... pitch=4096`, a tiled-pixel count of about
  `2048 x 56`, `unlock -> 1 | depth now 0`, no fault — AND the owner sees a full-width bar **with
  art**, not black.
- **PARTIAL (locks, tiles, still black):** the write lands but the engine overwrites or ignores the
  surface. Then the bar's pixels are not sourced from this surface at composite time, and the
  `[0x2a]`-is-the-background reading needs revisiting.
- **FAIL (refused):** `HUDFIT> REFUSE lock: sub vtable ...` — the sub-object is not the class the PE
  says. Nothing is written; read the refusal before theorising.
- **FAIL (lock returns 0):** `lock did not yield a usable backing`. The surface is not lockable at
  this moment on this thread — the `[UNCERTAIN]` called out in the code. No write, no unlock.
- **FAIL (crash):** any fault beyond the benign startup `0xC0000096`. Record the address.

## Also scored, independently: H-fps

Run 4 could not test it (2048 dims, no backing). If the lock succeeds this run, the bar surface is
**genuinely backed at 2048** for the first time, which is the condition H-fps needs.

- FPS drop **reduced/gone** -> the window/surface mismatch was the stall's cause.
- FPS drop **unchanged** -> H-fps is falsified, properly this time, and the stall is about width
  itself.

Only score H-fps **if the lock succeeded**. A refused or failed lock leaves it confounded again.

---

# RUN 6 PRE-REGISTRATION (2026-08-31) — HUDFIT promoted to the SHIP path

The dock+span now runs in step 12 unconditionally, on the render thread, with no lab and no phases.
`SC3RESIZE_HUDNATIVE=1` is the opt-out. `SC3RESIZE_HUDLAB=1` still routes through the A/B phase
machine for measurement.

## Two second-resize bugs fixed while promoting (neither could appear in runs 1-5, all single-resize)

1. **Bar height would grow 8 px per resize.** After a recreate the surface height reads
   `56 + RZ_SURFACE_SLACK = 64`, and the old code recreated at that read-back height — so every
   resize added another 8 px of guard rows permanently.
2. **Re-tiling already-tiled art.** Re-snapshotting after a widen would capture TILED content and
   re-tile it at the new width, compounding misaligned seams on every resize.

Both fixed by caching the **pristine native art once** (`g_hud_art`, 600x56, pitch 1200) and always
tiling from that cache at the cached NATIVE height. Also, the skip guard changed from
`liveW <= oldw` to `liveW == oldw`, so **shrinking** re-fits too instead of leaving the bar wider
than its window.

## Pre-registered outcomes — the point of this run is the SECOND and THIRD resize

Drive **at least three window size changes**, including a shrink: maximize -> restore -> maximize.

- **PASS:** every resize logs `HUDFIT> ... refitting to <liveW>x56` with the height **always 56**
  (never 64, 72, 80...), `art 600x56` every time, lock/unlock balanced (`depth 1 -> 0`), and the bar
  spans correctly at each size **with art and no seams growing**. No fault.
- **FAIL (height growth):** any `refitting to <w>x64` or larger. Bug 1 is not fixed.
- **FAIL (seams/degradation):** the bar art visibly degrades across successive resizes. Bug 2 is not
  fixed.
- **FAIL (shrink):** after restoring to a smaller window the bar is still wider than the window.
- **FAIL (crash/refusal):** any fault beyond the benign startup `0xC0000096`, or a `REFUSE` line.

## Shipping judgement, stated plainly

The full-width bar carries a **measured, unresolved GPU-sync FPS cost** (runs 3-5: mechanism
localized, two candidate causes eliminated, root cause still open). Shipping it ON is the owner's
explicit call. `SC3RESIZE_HUDNATIVE=1` exists so that cost is opt-out-able without a rebuild, and
this trade-off must stay documented wherever the mod is described to users.

---

# RUN 7 PRE-REGISTRATION (2026-08-31) — wait attribution (stack sampling)

Runs 3-5 established WHERE the render thread stalls
(`win32u!NtGdiDdDDIWaitForSynchronizationObject`, doubling with bar width) and eliminated two causes
(surface content, surface size). EIP cannot say WHO leads it there - every sample lands in the same
system stub whatever the caller.

## Instrument

At each sample, while the thread is suspended, copy `STK_BYTES` (1024) from `Esp`. **After** the
resume, scan that copy for the first address inside a game module (SIMSPR / GZGraphicD / SIMCITY /
SIMUI / GZWIN / SC3U) and bucket it on its EXACT address, so hits name precise call sites. Dumped per
phase alongside the EIP profile.

This is a stack **scan**, not a frame walk: /O2 omits frame pointers, so an `Ebp` chain would lie. A
scan can also pick up stale stack values, so a single hit means little. **What makes it decidable is
the same A/B differential that made the EIP profiler work** - a call site heavily present in phase B
and absent from phase A is attributable to bar width and nothing else.

## Pre-registered outcomes

- **PASS / caller named:** one or a few game-module addresses are strongly over-represented in
  `STK> B-fullwidth` versus `STK> A-native`. Those resolve to `MODULE+RVA` and become the read
  target - the engine-side code whose per-frame behaviour changes with bar width.
- **INCONCLUSIVE:** the B ranking is flat, or matches A's ranking closely. The scan is not
  separating caller from ambient stack content; a real frame walk or a targeted hook on the blit path
  would be needed instead.
- **VOID:** `no-game-frame` dominates (most samples find no game module on the stack), or either
  phase collects < 200 attributed samples. **Do not interpret a VOID ranking.**

## Explicitly NOT claimed in advance

A top-ranked call site is a **lead, not a proof**. Confirming it means reading that function and
showing a width-dependent per-frame behaviour - the standing rule that a confirmed code path is not
a confirmed cause applies with full force here, and this board has paid for ignoring it three times
in the crash arc.

## Conditions

`SC3RESIZE_HUDLAB=1` (phases). Bar docks and refits as on the ship path, so phase B measures the
final shipping configuration, not a half-state.

---

# RUN 8 PRE-REGISTRATION (2026-08-31) — wait attribution, with return-address validation

Run 7 was INCONCLUSIVE: the scan accepted any in-module value, and its ranking contained
`SC3U.exe+0x9` (DOS header) and page-aligned `+0x41000` / `+0x80000`.

## The fix

A candidate is now bucketed only if BOTH hold:

1. it lies in an **executable section** (parsed from each module's PE section table at init);
2. a **call instruction ends exactly at it** - `E8 rel32`, or the `FF /2` family across mod
   00/01/10/11 with and without SIB (lengths 2,3,4,6,7).

**Pre-flight, offline against `Apps\SC3U.exe`** - the new test re-scored run 7's own entries:

| address | verdict | why |
|---|---|---|
| `SC3U.exe+0x9` | **REJECT** | not in an executable section |
| `SC3U.exe+0x41000` | **REJECT** | no call ends here |
| `SC3U.exe+0x80000` | **REJECT** | no call ends here |
| `SC3U.exe+0x39237` | **REJECT** | no call ends here |
| `SC3U.exe+0x41237` | ACCEPT | `call rel32` |
| `SC3U.exe+0x25A9F` | ACCEPT | `call r/m32` (len 6) |
| `SC3U.exe+0x263B0` | ACCEPT | `call r/m32` (len 3) |

All three impossible entries are rejected; plausible ones are accepted with the encoding named.
Note `+0x41000` IS inside `.text`, so the section test alone would have passed it — **both filters
carry weight.** Validating the validator against the exact data that discredited the previous run,
before spending a lease.

## Pre-registered outcomes

- **PASS / caller named:** a small number of validated call sites are strongly over-represented in
  `STK> B-fullwidth` versus `A-native`. Those become the read target.
- **INCONCLUSIVE:** B's ranking is flat or mirrors A's. Attribution by stack scan is then exhausted
  and the next move is a targeted hook on the blit path, not a third scan variant.
- **VOID:** `no-game-frame` dominates, or either phase attributes < 200 samples. Validation will
  raise the miss count by design — rejecting junk means some samples now attribute to nothing. **A
  high miss count is expected and is NOT itself a failure**; only a miss count that starves the
  sample floor is.

## Unchanged from run 7, deliberately

A top-ranked call site remains a **lead, not a proof**. Validation removes impossible addresses; it
does not make a surviving address causal. Confirmation still means reading the function and showing
width-dependent per-frame behaviour.

---

# RUN 9 PRE-REGISTRATION (2026-08-31) — blit timing, direct measurement

Stack attribution failed twice: run 7 (contaminated by non-return-addresses), run 8 (validated, but
biased against the waiting samples). **Building a third scan variant would be chasing the instrument
instead of the bug.** Measure the thing directly instead.

## Instrument

`FUN_10018c58` is the engine's `IDirectDrawSurface::Blt` wrapper, and the mod ALREADY hooks it as its
per-frame heartbeat — so the measurement point costs nothing new and touches no new code path.

At each entry: take a QPC timestamp and attribute the interval since the PREVIOUS entry to the
PREVIOUS call's `this`. That interval is that blit's duration plus whatever ran before the next one,
which is exactly the quantity that grows when a blit blocks on the GPU. Bucketed per object, dumped
per phase with call count, total and average, plus the object's raster dims where its class is known
— so "the 2048x56 bar" is distinguishable from "the 2048x1081 iso view" by measurement, not by
assumption.

Intervals over 50 ms are counted separately and NOT averaged in: the heartbeat also drives
`rz_poll`, so a frame that ran the whole resize routine would otherwise swamp a bucket.

## Why this can succeed where the scans failed

Both scan attempts tried to infer *who* from stack contents. This measures *what*, directly, with no
inference: if a blit is the stall, it shows up as a specific object whose average interval rises
between phase A and phase B. There is nothing to misattribute.

## Pre-registered outcomes

- **PASS / blit named:** one object's average interval rises materially from A to B, and its dims
  identify it. If it is the ~2048x56 bar raster, the stall is the bar's own blit. If it is the iso
  view, the bar's width is slowing something else down — a different and more interesting result.
- **FAIL / not in the blits:** no object's average rises appreciably between phases while the owner
  still reports the drop. The cost is then NOT inside the Blt wrapper at all, and the next target is
  the present/flip path rather than any blit.
- **VOID:** fewer than 100 intervals in either phase, or outliers dominate (> 25% of samples).

## Scoring note carried forward from run 8

Run 8 passed its sample-count floor while being unusable. So this run is scored on **whether the A/B
comparison is structurally sound** (comparable interval counts in both phases, outliers not
dominating), not merely on collecting enough samples. A count threshold cannot detect a biased
population, and that lesson cost a lease.

---

# RUN 10 PRE-REGISTRATION (2026-08-31) — split "inside the blit" from "after the blit", + identity

Run 9 localized the regression to one object (`0x0F7AFC70`, avg interval x1.95, 97.1% of window,
throughput -37%) but left two things open: WHAT that object is, and WHETHER the cost is inside the
Blt or between blits.

## Two additions

**1. Identity.** `rz_blt_dump` now always reports each object's vtable resolved to `MODULE+RVA`
(plus dims where the class is known). Run 9's dominant object printed nothing precisely because it
is neither known raster class, which is what left it unidentified.

**2. Exact time inside `IDirectDrawSurface::Blt`,** by patching the COM vtable slot `+0x14`.

Chosen deliberately over prologue-wrapping `FUN_10018c58`: that function runs ~2000x/s on the render
thread, and entry+exit hooking it means stealing a prologue or patching return addresses — a real
crash risk for a measurement. A COM slot swap is a plain `__stdcall` C function with the documented
signature: no code generation, no stolen bytes, no rel32 relocation. It is also MORE precise,
timing the actual DirectDraw call, which is where a GPU synchronization wait lives.

The surface is reached exactly as the engine reaches it: a raster's sub-object holds
`IDirectDrawSurface*` at `sub+0x04` `[CONFIRMED @ GZGraphicD 0x10018a82]`. All DD surfaces share one
vtable, so one slot patch covers every blit. **Expect-or-refuse:** the existing slot target must lie
inside `ddraw.dll`, else the patch is refused and logged rather than forced.

## Pre-registered outcomes

- **INSIDE:** `INSIDE ddraw Blt` total roughly doubles A -> B and accounts for most of the window in
  B. The stall is then inside the DirectDraw blit — consistent with the GPU-sync EIP finding, and
  the two independent instruments would agree.
- **AFTER:** inside-Blt total stays roughly flat A -> B while the heartbeat interval still doubles.
  The cost is then NOT in the blit at all but between blits, and every blit-focused hypothesis dies
  at once. This would be a large, clean result.
- **VOID:** `NOT HOOKED` (refusal), or fewer than 100 ddraw calls in a phase.

Both instruments run in the same window, so they cannot disagree about conditions — the split is a
within-run comparison, not a cross-run one.

## Note

The identity line and the split are independent; either can succeed if the other fails.

---

# RUN 11 PRE-REGISTRATION (2026-08-31) — surface memory class and owner, both phases

Run 10 put the cost inside `IDirectDrawSurface::Blt` (x2.55 per call) on one object, identified as a
surface sub-object (`GZGraphicD+0x1F0AC`). Open: which surface, and why an unrelated wide bar makes
it 2.55x more expensive.

## What is added

For every blitting object of the sub-object class, the dump now also reports:

- **`sub+0xe8` = the OWNING raster** `[CONFIRMED @ GZGraphicD 0x100142a2:41]`, with its dims;
- **`sub+0x74` = `DDSCAPS.dwCaps`**, decoded (`VIDMEM` / `SYSMEM` / `PRIMARY` / `OFFSCR` /
  `NONLOCAL`). The `DDSURFACEDESC` is at `sub+0x0c` and `ddsCaps` at `DDSD+0x68`, which is exactly
  the field `FUN_10019273` writes when choosing video vs system memory - the fallback path at
  `0x1001943a` sets `DDSCAPS_SYSTEMMEMORY` (`0x800`) and clears `DDSCAPS_VIDEOMEMORY` (`0x4000`)
  `[CONFIRMED @ GZGraphicD 0x10019273]`.

Both are read in **both phases**, so a change is visible rather than inferred.

## Hypothesis being tested (H-mem)

> Widening the bar pushes the main scene surface out of video memory into system memory, turning a
> video->video blit into a system->video transfer. That is the classic shape of a ~2.5x cliff.

- **H-mem SUPPORTED:** the dominant object's caps show `VIDMEM` in phase A and `SYSMEM` in phase B
  (or gains `NONLOCAL`). The mechanism is then a memory-class demotion, and the fix direction is to
  stop the bar consuming the video memory the scene surface needs.
- **H-mem FALSIFIED:** caps are IDENTICAL across phases. The 2.55x then has nothing to do with
  surface residency, and the next candidate is the blit's own parameters (source rect, clipping,
  colour-key path) rather than where the memory lives.
- **VOID:** the dominant object is not of the sub-object class, or `owner`/`caps` read as garbage
  (owner dims implausible), meaning the offsets do not hold for this object.

**H-mem is a hypothesis with a named falsifier, not a finding.** It was written down before the run
precisely because it is the kind of tidy story that is easy to believe after the fact. If the caps
are identical, it dies, and that is a useful result too.

## Bonus the same line gives for free

`owner` + dims identifies WHICH surface the main blit belongs to - the iso view render target, the
device surface, or something else. That has been `[UNCERTAIN]` since run 9.

---

# RUN 12 PRE-REGISTRATION (2026-08-31) — Blt arguments

Run 11 excluded the destination: same surface (`iso+0x4ec`), same `VIDMEM` residency (caps byte-
identical `0x00006040`), same 2048x1089 dims — and still x2.2-2.55 per call. What remains on-path is
the CALL ITSELF.

## What is added

`rz_blt_hook` already receives every parameter and discarded them. Now aggregated per phase:

- **time bucketed by `dwFlags`** — colour-key, ROP, `DDBLT_WAIT` and async paths have very different
  costs, and a shift in the flag MIX would show here even if no single call got slower;
- **destination rect area** (count, average, largest w/h seen);
- **NULL dest rect** count (= whole surface) and **NULL source** count.

Cheap: a 32-entry linear scan at ~2600 calls/s.

## Pre-registered outcomes

- **PARAMETERS CHANGED:** the flag mix shifts A -> B, or the average/largest dest rect grows. The
  slowdown is then explained by what the engine is asking DirectDraw to do, and the fix direction
  is to stop it asking for that. A `DDBLT_WAIT` appearing, or a colour-keyed path taking over, would
  be the clearest form.
- **PARAMETERS IDENTICAL:** same flags in the same proportions, same rect sizes, same null counts —
  and the same calls still cost 2.2x more. Then **nothing on the call side changed**, and the cause
  is external: GPU contention induced by the wide bar elsewhere in the frame. That would leave the
  DirectDraw call as a victim rather than a culprit, and the investigation should move to what else
  the wide bar makes the driver do.
- **VOID:** hook refused, or fewer than 100 calls in a phase.

## Note on what "identical" would mean

**PARAMETERS IDENTICAL is the more likely outcome and is NOT a dead end.** Runs 9-11 have eliminated
the bar's own blit, surface residency, and now potentially the call parameters. Each elimination has
been by measurement, and the remaining space (external GPU contention from a wide system-memory
surface being composited by the desktop compositor) is both smaller and more specific than where
this started ("intrinsic to the engine's compositing, would require a compositor rewrite").

---

# RUN 13 PRE-REGISTRATION — bar width sweep (600 / 1024 / 1536 / 2048)

Runs 9-12 excluded the bar's own blit, surface residency, and pixel throughput. What is left is
per-call synchronization or external contention. **The SHAPE of cost-versus-width discriminates
between those**, and the A/B design cannot show a shape from two points.

## Design

`SC3RESIZE_SWEEP=1` replaces the A/B phases with four measurement windows of 8 s, at bar widths
600, 1024, 1536, 2048. Each step docks the bar AND refits its background surface to the same width,
so window and surface always agree — run 5 established that a widened window over a stale surface is
a third state that scores nothing.

**Tighter control than A/B:** the bar is DOCKED at every step including the 600 baseline, so docking
is held constant and the only variable across the four windows is width. The A/B design confounded
"docked" with "full-width"; this does not.

Same process, same city, same window size, same zoom throughout.

## Pre-registered outcomes

- **SMOOTH:** average inside-Blt rises roughly monotonically and proportionally with width
  (roughly linear in width, or in bar area). The cost is then per-pixel work in the driver/compositor
  — the wide surface genuinely costs more to composite every frame, and mitigation means drawing
  less of it (e.g. leaving the bar native and only repositioning it).
- **THRESHOLD:** cost is flat across two or three widths and then jumps at one step. That implies a
  RESOURCE LIMIT crossed at a specific size — a surface no longer fitting in a cache or video-memory
  budget. Mitigation would then be to stay under the threshold, which could make a full-width bar
  affordable at a slightly reduced width or by splitting it.
- **FLAT:** no material difference across all four widths. Then bar width is not the driver at all,
  and everything attributed to it across runs 3-12 needs re-examination — the confound would have to
  be the dock/refit action itself rather than the width.
- **VOID:** fewer than 100 inside-Blt calls in any window, a refused ddraw hook, or a fault.

## What this cannot decide

It measures cost versus width; it does not identify the mechanism. A THRESHOLD would name a size to
investigate, not a cause. Carried forward from every run in this file: a measured correlation is not
a mechanism, and this session has already killed four tidy stories that felt conclusive.

## Note on the ship path

Sweep is diagnostic only, behind two flags (`SC3RESIZE_HUDLAB=1 SC3RESIZE_SWEEP=1`). With either
unset the mod is the shipping build: viewport plus HUD dock/span at full width.
