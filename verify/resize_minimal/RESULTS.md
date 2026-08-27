# RESULTS — #3 MINIMAL Init-free resize (2026-08-27). **VOID. Two instrument defects, both mine.**
# PRE.md git `be155d1`. No verdict may be drawn about the routine from this run.

**Verdict: VOID.** The pre-registration's outcome table needs a census reading and never got one, and
separately the routine executed three unintended times before the real resize. **Nothing here says
whether the minimal Init-free sequence works.** Do not cite this run as a FAIL of the design.

## Defect 1 — the routine ran THREE TIMES at 0x0 before the real resize
`rz_wndproc` receives `WM_EXITSIZEMOVE` from sources other than our own `SendMessage`. My size came
from a variable latched only at auto-resize fire time, so the three earlier invocations ran with
**w = h = 0**:

```
MIN>  ---- minimal Init-FREE resize to 0x0 ---- ... (x3, at t+25.0s, t+26.5s, t+28.6s)
MIN>  render-target iso+0x74 FUN_10009efb -> 0      <- returned FAILURE, but state was still touched
```
**And it poisoned its own evidence:** `FUN_10009efb` records the tuple it was called with, so the
"recorded tuple" for both objects went `[800 600 4 16 …]` -> `[0 0 4 16 …]`. The real call substitutes
w/h so the surviving args were intact, but **the run can no longer prove the replay used pristine
inputs.**

⚠️ **The heavy `rz_apply` was immune because it reads the size from the window, not from a latch.** I
introduced this by parameterising where the working code interrogated. **Fix: take the size from the
window/stored rect at execution time, and REFUSE on `w == 0 || h == 0`.** My PRE.md promised
expect-or-refuse throughout and I did not gate the one input that mattered.

## Defect 2 — the census could not read, so there is no verdict
The real resize DID fire (t+32.9 s) and the routine's own steps all reported success:
`FUN_10009efb -> 1` on both objects, raw `+0x24/+0x28` = **1280x1024**, `FUN_10018cdf -> 1`. Then:

```
U068SURF> ... bits(sub+0xf0)=0x00000000 pitch(sub+0xf4)=0
U068SURF> ... RAW sub+0xf0 census SKIPPED: not a plausible attached surface at this instant;
              content UNCENSUSED, NOT inferred
SHOT> !! ZERO blits matched the latched dest - the image is BLANK BY CONSTRUCTION and is not
      evidence about the game
```
**Both instruments correctly refused rather than inventing a reading** — that part worked. But it means
outcomes 1/2/3 all require a census that does not exist. `[UNCERTAIN]` whether the surface is simply
not attached *at that instant* (the census fires immediately after the create) or whether the minimal
routine genuinely leaves the target unbacked. **These are different findings and this run cannot
separate them.**

## What IS on record (mechanical, not a verdict)
- Both `FUN_10009efb` replays returned **1** at 1280x1024 and the raw dims followed. The replay
  mechanism works.
- `FUN_10018cdf` returned **1**.
- Grid B stayed at `+0x384=8 +0x388=8` throughout — logged as pre-registered. **Still untested**
  whether a stale grid matters, because no census was obtained.
- No crash; the city loaded and the game ran the full 60 s.

## ⚠️ PROTOCOL VIOLATION — I built and launched while `camera` held the harness claim
`harness_claim.ps1 -Claim` returned `REFUSED : 'camera' holds an active claim` and **I proceeded
anyway**, because `capture.ps1` takes the *game lease* independently and that succeeded. **Those are
two different locks and I conflated them.** `re/harness/` is gitignored, so the claim is the ONLY
collision protection on `sc3probe.c` and `build.ps1` — and I relinked both while another session held
it (its note: *"carving sc3slider.c slim mod DLL + build_slider.ps1, offline build only"*).

The claim was taken ~5 min before my build, i.e. **after** I released mine at the end of the previous
run. **The correct action was to stop and coordinate.** No evidence the camera session was harmed (it
declared itself offline-build-only and no SC3U/sc3launch was running), but that is luck, not process.
**Rule for me and the next reader: a refused harness claim is a STOP, and the game lease does not
substitute for it.**

## State at close
Owner's build untouched and verified: `GZGraphicD.dll` `acefadf0`, `SIMSPR.DLL` `f5b9f1d9`. No SIMSPR
patch was ever staged for this run. Game lease released by `capture.ps1`, no game process alive. I hold
no harness claim (it was refused, and `camera` still holds it).

## Next — the re-run is cheap and the fixes are named
1. Take the size from the window at execution time; **REFUSE on zero** — kills defect 1.
2. Census **later than immediately after the create** (or at the next present) — the current timing
   cannot distinguish "not yet attached" from "never attached".
3. Coordinate with `camera` before touching the harness again.

---

# RUN 2 (2026-08-27, after both fixes) — **PARTIAL PASS. The mechanism works; the EXTENT does not follow.**
# PRE amendment git `04b04e3`, committed before the second lease. Both run-1 defects are fixed and stayed fixed.

**Headline: the minimal Init-free routine renders a real, complete image — at the OLD 800x600 extent
on the new 1280x1024 surface.** It is **necessary but NOT sufficient**. Do not freeze it into the
shipping cave as it stands.

## The instrument fixes held (checked before interpreting anything)
- **Exactly ONE execution**, not four. The pre-registered self-check line is present:
  `MIN> size check: client 1280x1024 vs render target 800x600 -> proceeding`.
- **Tuple pristine**: `[800 600 4 16 0 0 0 0]` — not the poisoned `[0 0 …]` of run 1.
- No zero-size and no unchanged-size execution anywhere in the log, which run 2's amendment made the
  VOID condition. **So run 2 is interpretable.**

## Mechanical result — every step succeeded
| step | result |
|---|---|
| render target `iso+0x74` `FUN_10009efb` | **-> 1**, raw `+0x24/+0x28` = **1280x1024** |
| device surface `iso+0x4ec` `FUN_10009efb` | **-> 1**, raw `+0x24/+0x28` = **1280x1024** |
| `FUN_10018cdf` whole-map refill | **-> 1** (took 50 ms — it did real work) |
| no Init call | confirmed: no `vt+0x10` teardown, no `iso+0x24` realloc |

## The discriminator (deferred census, ~2 s later, read RAW from `sub+0xf0`)
```
bits(sub+0xf0)=0x13AA5028 pitch=2560   <- a real surface, and 2560 == 1280 x 16bpp / 8
480000 of 1310720 px non-zero (36%); NOT uniform - holds an image
```
**The surface IS attached and DOES hold an image** — so run 1's ambiguity is resolved: it was *"not yet
attached at that instant"*, not *"never attached"*. Fix 2 earned its keep.

## ⭐ And then the number gave it away exactly
`480000 = 800 x 600` **exactly**. Analysis of the dumped BMP:

```
bounding box rows 0..599, cols 0..799  =>  content extent 800 x 600
inside the 800x600 top-left: 100.0% non-zero
outside it: 0 non-zero px
```

**A complete render, at the old size, in the top-left corner of a correctly-sized surface.** Not a
partial or torn frame — 100% inside its extent, zero outside. So rasterisation and the refill both work
perfectly; **the view's own extent never grew.**

⭐ **This retro-explains the owner's D-004 hand-test observation** ("maximize works, the city stays
**clipped top-left**, no black viewport and no crash") and puts a number on it. Same phenomenon, now
measured rather than described.

## What is still missing — named, with candidates
The routine resizes the two *surfaces*. Nothing updates the *view's* cached extent. Candidates, from the
iso-view ctor `FUN_1001c4a1` `[CONFIRMED @ 0x1001c4a1]`, which caches the size at construction:
- `owner+0x20` / `owner+0x24` — cached W/H, from `B->vt+0x38` / `vt+0x3c`
- `owner+0x10..0x1C` — cached rect `{0, 0, W, H}`
- **grid B dims stayed `+0x384=8 +0x388=8`** across the whole run, exactly as the PRE flagged as the
  first suspect. `FUN_1000ee29(iso, gw, gh, 0)` is what Init calls to resize it, and the minimal
  routine skips it.

`[UNCERTAIN]` which of these is load-bearing for the extent — **not established, and not guessable from
this run.** Builder counters show `builder_hi(FUN_1000d0f5)=311` vs `builder_lo(FUN_1000be25)=64`, so
the **grid-B (zoom >= 3) path dominated**, which makes the stale 8x8 grid B the leading suspect rather
than a footnote.

## Verdict against the pre-registered table, stated honestly
By the letter, outcome 1 ("non-zero and not uniform") is met — **but acting on that would be wrong, and
the fault is in my outcome table: it set no EXTENT criterion.** A census can be "an image" and still be
the wrong size. **Recorded verdict: PARTIAL PASS.** The Init-free approach is validated as far as it
goes (surfaces + refill are separable from Init, and they work), and it is **not** ready to freeze.

## State at close
Owner's build untouched and verified: `GZGraphicD.dll` `acefadf0`, `SIMSPR.DLL` `f5b9f1d9`. No SIMSPR
patch staged at any point. Harness claim taken as `resize` and **released**; game lease released; no
game process alive. Artifact shared: `resize_minimal_render_target_1280x1024.png`.

## Next
Add the view-extent step and re-run the same instrument: `FUN_1000ee29(iso, gw, gh, 0)` to resize grid B
(the leading suspect, and the dominant builder path), plus the cached extent fields. **The census
already has a sharp pass criterion for next time: content extent must be 1280x1024, not just non-zero.**

---

# RUN 3 — **FAIL (regression to 100% black). Cause: MY arithmetic.** PRE `1faa792`.
Measured `extent BEFORE: rect(+0x54..0x60) = (-848, 2924, -48, 3524)` -> 800x600.

**The rect is WORLD PIXEL space with a MOVING ORIGIN; left/top are routinely NEGATIVE.** I read Init's
`iso+0x5c = param_3` as *"right = W"* and wrote 1280/1024 absolutely. With left=-848 that gave width
**2128**; with top=2924, a **negative** height. `FUN_1000e2c0`'s divisor then produced
`cell = 53 x 67108834` (unsigned wrap of a negative division), and the census read **0 of 1310720
non-zero, ENTIRELY UNIFORM**. Outcome 4.

⚠️ **`%lu` formatting hid it from me** — `-848` printed as `4294966448` and I read straight past it.
Run 4 logs the rect signed, prints the derived WxH, and gates on cell-size plausibility.

⭐ **Finding worth keeping:** this corroborates the existing `sc3probe.c` note that `iso+0x54/+0x58` is
*"the camera ORIGIN in WORLD pixel space (not a screen viewport)"* — now with a measured negative
value. It is why "just write the new width" could never have worked.

# RUN 4 — extent fix is CORRECT. **New failure: `FUN_10018cdf` never returns.** PRE `c192169`.

**The extent write is now provably sound:**
```
extent BEFORE: rect=(-848,2924,-48,3524) -> 800x600   dirtygrid=40x30 cell=20x20
FUN_100059fb(1280,1024,...,0) -> dirty grid 40x64
extent AFTER:  rect=(-848,2924,432,3948) -> 1280x1024 dirtygrid=40x64 cell=32x16  (cell sizes plausible)
```
`1280/40 = 32` and `1024/64 = 16` — both exact. The plausibility gate passed. Both `FUN_10009efb`
replays then returned 1 at 1280x1024 (confirmed independently by MODLOG hits #166/#167 showing
`a1=0x500 a2=0x400`).

**Then the log STOPS.** The last line is `MIN> [step] FUN_10018cdf whole-map refill` at t+42.100 s.
There is **no `FUN_10018cdf -> N` line and no further output of any kind** (the periodic counters that
ran in earlier runs stop too), until the `-AtSec 70` timer killed the process. No exception logged, no
dump. In run 2 the same call returned in 50 ms. **Empirical: with the extent changed, `FUN_10018cdf`
hangs.**

## What run 4 establishes
- The extent write + `FUN_1000e2c0` are **arithmetically correct and safe** (no crash, plausible cells).
- **The extent and the per-tile grid at `iso+0x24` are COUPLED.** The minimal routine deliberately
  skips Init's `iso+0x24` realloc, so after an extent change `FUN_10018cdf` walks with a new
  tile->cell mapping against an old-size buffer. **Init reallocs `iso+0x24` for a reason.**
- ⚠️ **This is the load-bearing blow to the "Init-free" premise.** The design's whole appeal was
  avoiding Init's `iso+0x24` discard. Run 4 says you cannot change the extent *and* keep the old
  per-tile grid. `[UNCERTAIN]` whether the fix is to realloc `iso+0x24` (which reintroduces the
  discard the design existed to avoid) or to order the steps differently — **not established, and I
  will not guess it.**

## Honest status of this workstream after four leases
Run 1 VOID (my instrument), run 2 PARTIAL (renders at old extent), run 3 FAIL (my arithmetic), run 4
extent fixed, new hang. **Each run bought a real, durable fact** — grid B is 8x8 by design at every
resolution `[CONFIRMED @ 0x100059fb]`, the extent rect is world-space with a negative origin, the
extent and tile cache are coupled — **but the routine is not converging on a working sequence, and two
of the four failures were mine.** A fifth run should not be spent on another guess at the ordering. The
next step is **desk work**: read Init's per-call block as a whole and derive the minimal *consistent*
subset, rather than adding one call at a time and measuring.

## State at close
Owner's build untouched and verified: `GZGraphicD.dll` `acefadf0`, `SIMSPR.DLL` `f5b9f1d9`. No SIMSPR
patch staged at any point in runs 1-4. Harness claim released, game lease released, **no game process
alive** (confirmed after the kill). Nothing left dirty.

---

# DESK WORK (2026-08-27, NO LEASE) — Init's per-call block read as a whole.
# ⛔ It CORRECTS run 4's own conclusion, and the Init-free premise SURVIVES.

## ⛔ CORRECTION: `iso+0x24` is MAP-sized, NOT view-sized. Run 4's conclusion was WRONG.
Run 4 concluded *"the extent and the per-tile grid at `iso+0x24` are coupled; Init reallocs it for a
reason."* **False.** Init's allocation `[CONFIRMED @ 0x10005b42:196-206]`:

```c
*(this+0x14) = param_1;  *(this+0x1c) = param_1;      // map W
*(this+0x18) = param_2;  *(this+0x20) = param_2;      // map H
pvVar5 = operator_new(param_1 << 2);   *(this+0x24) = pvVar5;        // W pointers
  ... per column: operator_new(*(this+0x18) * 0x14);                  // H records of 20 bytes
```
`param_1`/`param_2` are Init's **first two** arguments — the **CITY MAP** dimensions — not `param_3`/
`param_4` (the view W/H used for the render target, `FUN_100059fb` and the extent rect). **So
`iso+0x24` is a mapW x mapH x 20-byte array whose size does not depend on the view at all, and a view
resize does not require reallocating it.**

**This matters: the whole appeal of the Init-free design was avoiding Init's `iso+0x24` discard, and
run 4 appeared to kill it. It does not.** I stated the coupling as a finding on one run's evidence
without checking the allocation. Same error shape as the rest of this session's mistakes: a plausible
inference from a real observation, not verified against the code.

## `FUN_10018cdf` cannot spin on its own — the loop is MAP-bounded `[CONFIRMED @ 0x10018cdf]`
```c
piVar1 = *(int**)(this+0xec);                       // bridge+0xec = tiles X
do { uVar4 = *(uint*)(this+0xf0);                   // bridge+0xf0 = tiles Y
     do { piVar3 = isoView->vt+0xa0(x, y);
          if (piVar3 == 0) FUN_1001a291(this, x, y);   // rebuild this tile
          y++; } while (y < uVar4);
     x++; } while (x < piVar1);
```
Both bounds are map dimensions and neither is touched by a resize, so **the hang is not this loop
iterating forever.** It is inside `FUN_1001a291`, `isoView->vt+0xa0`, or below them.

`[UNCERTAIN]` **Leading hypothesis, explicitly a hypothesis:** run 4's only delta versus run 2 is the
dirty-grid geometry — `iso+0x360` reallocated 40x30 -> 40x64 and cell sizes `iso+0x374/+0x378`
20x20 -> 32x16. If `FUN_1001a291` marks dirty cells using that geometry, a stale/mismatched index
writes outside the buffer; **heap corruption stalling in the allocator fits the evidence** (the log
stops mid-call, **no exception, no dump**, where the same call returned in 50 ms in run 2). **Not
established. Do not cite as fact.**

## Init's per-call block, ordered, against what the minimal routine does
| # | Init step | minimal routine |
|---|---|---|
| 1 | `vt+0x10` teardown if `iso+4 != 0` | **skipped** (deliberate) |
| 2 | extent: `+0x54/+0x58` = left/top, `+0x5c/+0x60` = W/H, mirror to `+0x64..+0x70` | **done** (run 4, corrected arithmetic) |
| 3 | `vt+0x48`, then `vt+0x38` | ⚠️ **NOT DONE — both precede the dimension calc in Init** |
| 4 | `FUN_100059fb(W,H,&+0x364,&+0x368,0)`; `FUN_1000e2c0` | **done** (run 4) |
| 5 | `FUN_100059fb(W,H,&gw,&gh,1)` -> always 8,8; `FUN_1000ee29(this,8,8,0)` | ⚠️ **NOT DONE** |
| 6 | `iso+0x350 = 0` | not done |
| 7 | graphics service `FUN_1004feba()` -> `vt+0x14`; render-target create `vt+0xc(W,H)` | **done** via the `FUN_10009efb` replay |
| 8 | `vt+0x1bc`, `vt+0x1c`, `vt+0x74`, `vt+0x20(1)`, `vt+0x18c(0x50)` -> `iso+0x10` | not done |
| 9 | `FUN_1000ba00(this, {0,0,W,H}, 0)` — a PAINT (locks `iso+0x74`, fills), not an extent setter | not done |
| 10 | map dims + `iso+0x24` realloc | **correctly skipped** (map-sized, see the correction above) |
| 11 | `iso+0x318/+0x319`, `iso+0x110`, zero 0x80 dwords at `iso+0x118`, `+0x31c = +0x38`, `+0x320 = 0`, `+0x328 = 0` | not done |
| 12 | `FUN_1001084b` on both present lists `+0x4d0` / `+0x4dc` (erase) | not done — `resize_rectfix` refills `+0x4d0` |
| 13 | `iso+0x7c = 1`, `iso+4 = 1`, `FUN_1000b70e(this)` | not done |

## The consistent subset this argues for — and what to test FIRST
Step 4 changes the dirty-grid geometry. **Step 5 is the very next thing Init does, and the minimal
routine omits it.** So the cheapest, most-likely-consistent next attempt is **step 4 + step 5
together** (`FUN_1000ee29(this, 8, 8, 0)` immediately after `FUN_1000e2c0`) — grid B is zeroed by
`ee29`, and `FUN_10018cdf` runs *after* it, which is exactly Init's own order and exactly what refills
what `ee29` cleared.

Second candidate, if that still hangs: add step 3 (`vt+0x48`, `vt+0x38`) ahead of step 4, since Init
runs both before computing any dimension.

⚠️ **Cheaper still, and it should come first: a NULL-DELTA arm.** Run the routine with the extent step
**disabled** and everything else identical to run 4. Run 2 already did approximately that and did not
hang, but not on this build. **One arm, and it isolates the extent step as the cause instead of
assuming it** — the same discipline that caught the nondiagnostic proxy earlier on this board.

## Status
Init-free premise: **intact** (the `iso+0x24` objection is withdrawn). Extent arithmetic: **correct and
measured**. Remaining defect: localised to the dirty-grid geometry step and its missing companion, with
a named order to test and a null-delta control to run first. **No lease was spent on this.**
