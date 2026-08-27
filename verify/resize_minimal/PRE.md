# PRE-REGISTRATION — #3 MINIMAL Init-free resize routine (committed BEFORE the lease)

**What is being tested.** The routine the SIMSPR shipping cave is meant to freeze, prototyped in C so
the sequence is proven before anything is hand-assembled. **No SIMSPR patch is staged for this run** —
this is a harness prototype, deliberately, because freezing an unproven sequence into a cave is the
expensive mistake here.

## The routine (`-resizemin`), and where each step comes from
1. **render target** `iso+0x74` -> `FUN_10009efb` replay at the new w/h (recorded 8-arg tuple, `+0x08`
   guard cleared first — a 2-arg call writes stack garbage).
2. **device surface** `iso+0x4ec` -> same replay. **MEASURED NECESSARY** 2026-08-27
   (`verify/resize_wmsize_poll`): the engine does not re-Init this itself.
3. **`FUN_10018cdf`** whole-map refill — **the render lever**, established by
   `verify/resize_tilecache_test`: suppressing it blacks the view regardless of everything else. It is
   **not** `FUN_1000fa36` and **not** the tile cache; both were tried and refuted.
4. present rect — already ships as `resize_rectfix`, left to it.

**It does NOT call Init (`FUN_10005b42`)**, which is the whole point: Init's `vt+0x10` teardown and its
`iso+0x24` per-tile realloc/zero are the known stale-state sources. `rz_apply` (the heavy path) is
**replaced**, not supplemented — running both would make the resulting frame unattributable.

## Outcomes, declared now

| # | reading | verdict |
|---|---|---|
| 1 | render-target raw census **non-zero and not uniform** (a real image) at 1280x1024 | ⭐ **PASS.** The Init-free sequence is sufficient. Freeze it into the SIMSPR cave |
| 2 | census **0% / black** | **FAIL — sequence insufficient.** Report which step refused, then suspect the stale grid B (see below). Do NOT ship the cave |
| 3 | census non-zero but **uniform** | **FAIL, and a different one** — a fill, not a scene. Distinguish before interpreting |
| 4 | any step logs `REFUSE` (missing tuple, bad vtable, no bridge) | **VOID for that step**, logged as a refusal, not a crash. A refused step invalidates the PASS |
| 5 | crash / no city reached | **FAIL.** Restore and report |

## The named risk, recorded before the run
⚠️ **Grid B (`iso+0x380`) is NOT resized by this routine.** Init normally calls
`FUN_1000ee29(iso, gw, gh, 0)` to resize and zero it; the minimal routine skips Init entirely, so grid B
keeps its **old dimensions**. The corrected #3 design (after the tile-cache refutation) lists only
RT + refill + present, but that correction was derived at one zoom and **never tested Init-free**.
**If outcome 2 fires, a stale grid B is the first suspect, not the last.** The routine logs
`iso+0x384/+0x388` before it runs so the reading is on record either way.

`[UNCERTAIN]` The zoom at which this runs decides which builder walks: `FUN_1000be25` (zoom < 3, tile
cache) vs `FUN_1000d0f5` (zoom >= 3, grid B). **Not pinned in this run.** A PASS at one zoom is not a
PASS at both, and the result must say which zoom it got.

## Scope limits
Upward only (`U-069` untouched). Headless, so no claim about the DirectDraw primary (`D-004`). No
WM_MOVE exercise. Prototype only — **a PASS licenses building the cave, it does not ship one.**

## Install state
Owner's standing build stays live and untouched: `SIMSPR.DLL` `f5b9f1d9`, `GZGraphicD.dll` `acefadf0`.
`wmsize_setrect` is NOT staged (this run drives the resize through the harness, which does its own
SetRect). Nothing to restore beyond releasing the lease and the harness claim.

---

# AMENDMENT — run 2, after the VOID (committed BEFORE the second lease, 2026-08-27)

Run 1 was VOID on two instrument defects of mine (`RESULTS.md`). **The outcome table above is
unchanged** — the question and the declared verdicts stand. Only the instrument changed:

1. **Size is interrogated from the WINDOW at execution time** (`GetClientRect` on the game HWND),
   never from a latched variable. **Zero is a REFUSAL.** Additionally, "render target already at the
   client size" is an explicit **SKIP**, so stray `WM_EXITSIZEMOVE` events cannot churn the target.
   This kills defect 1 at its root: the routine can no longer execute at `0x0`, and cannot execute
   at all when there is nothing to do.
2. **Two censuses instead of one.** The immediate one (right after the create) is **data only, never
   the discriminator** — same rule the heartbeat dump already carries. A **deferred** census ~2 s
   later, after real frames have run, is **the discriminator**, plus a grid-B census at the same
   point. The pair is what separates *"not yet attached at that instant"* from *"never attached"*,
   which run 1 could not do.

**Additional pre-registered read for run 2:** the routine must log a `size check` line proving it saw
a genuine mismatch before acting. **If run 2 shows any `MIN>` execution at a zero or unchanged size,
the fix failed and the run is VOID again** — do not interpret its census.

Harness claim: taken as `resize` before this build (`camera` had released it and its process was
gone — **not stolen**). Run 1's protocol violation is recorded in `RESULTS.md` and is not repeated.

---

# AMENDMENT — run 3: the EXTENT step (committed BEFORE the third lease, 2026-08-27)

Run 2 was a PARTIAL PASS: a **complete** render at exactly **800x600** (480000 px = 800x600, bbox
0..799 x 0..599, **zero** px outside) on a correctly-sized 1280x1024 surface. Surfaces right, extent
wrong. Run 3 adds the extent step.

## ⛔ FIRST: the PRE's leading suspect is REFUTED, statically, with no run spent
The run-1/2 PRE named **stale grid B (8x8)** as the first suspect. **Wrong.** Init reaches grid B via
`FUN_100059fb(w, h, &gw, &gh, 1)`, and that helper's first branch is
`if (param_5 == 1) { *param_3 = 8; *param_4 = 8; return; }` `[CONFIRMED @ 0x100059fb]`.
**Grid B is 8x8 at EVERY resolution.** The 8x8 I logged as "stale" was correct all along, and the
builder-counter argument that promoted it was irrelevant. Recorded because the suspect was named in a
committed pre-registration and must be retired in one.

## What run 3 adds, and where every value comes from
The resolution-dependent pair is the *other* `FUN_100059fb` call (mode **0**), whose table gives
40x30 at 800x600 and 40x64 at 1280x1024. It feeds `FUN_1000e2c0`, which reallocs a `gw*gh`
dirty-region buffer at `iso+0x360` and recomputes per-cell sizes at `iso+0x374/+0x378` as
`(iso+0x5c - iso+0x54)/gw` and `(iso+0x60 - iso+0x58)/gh` `[CONFIRMED @ 0x1000e2c0]`.
That divisor **is** the extent: Init writes `iso+0x54/0x58` = left/top, `iso+0x5c/0x60` = W/H, then
mirrors all four into `iso+0x64..0x70` `[CONFIRMED @ 0x10005b42:80-94]`.

Added steps, in order, before the surface replays:
1. `FUN_100059fb(w, ht, &gw, &gh, 0)` — **the game's own helper. No invented constants.**
   Refuse if it returns a zero dimension.
2. `iso+0x5c = w`, `iso+0x60 = ht` (absolute, as Init does); left/top **preserved**; mirror to
   `iso+0x64..0x70`.
3. `FUN_1000e2c0(iso, gw, gh)`.
Grid B is deliberately **not** touched (it is already correct), and `FUN_1000ee29` is deliberately
**not** called — it would zero grid B for no reason.

## Outcome table for run 3 — now with the EXTENT criterion my run-2 table lacked
| # | deferred census content extent | verdict |
|---|---|---|
| 1 | **1280x1024** (bbox fills the surface), not uniform | ⭐ **PASS.** The Init-free routine is complete. Licenses building the cave |
| 2 | still **800x600** | **FAIL.** The extent lives somewhere else; `iso+0x54..0x60` + `e2c0` are not sufficient. Report the remaining candidates |
| 3 | some **third** size | **INFORMATIVE, not a pass.** Report the number; it localises the divisor |
| 4 | 0% / black | **REGRESSION** — the extent write broke a working render. Say so plainly |
| 5 | zero/unchanged-size execution, or any `REFUSE` | **VOID**, as in run 2's amendment |

**The bar is the extent, not merely "an image".** Run 2 would have passed a non-zero test while being
demonstrably incomplete; that loophole is closed here.

Harness claim taken as `resize` before this build.

---

# AMENDMENT — run 4, after run 3's REGRESSION (committed BEFORE the fourth lease, 2026-08-27)

**Run 3 FAILED at outcome 4 (regression to 100% black) and the cause is my arithmetic, not the
engine.** Measured `extent BEFORE: rect(+0x54..0x60) = (-848, 2924, -48, 3524)` -> 800x600.

**The rect is in WORLD PIXEL space with a MOVING ORIGIN — left/top are routinely NEGATIVE.** I had
read Init's `iso+0x5c = param_3` as *"right = W"* and wrote 1280/1024 absolutely, which with
left=-848 gave width **2128** and with top=2924 gave a **negative** height. `FUN_1000e2c0`'s divisor
then produced `cell = 53 x 67108834` (an unsigned wrap of a negative division) and the frame went
**0% non-zero, entirely uniform**.

⚠️ **`%lu` formatting is what hid it from me** — `(-848)` printed as `4294966448` and I read past it.
Run 4 logs this rect **signed**, prints the derived WxH, and carries an explicit plausibility gate on
the resulting cell sizes that names run 3 by name.

**The correction:** Init is called with a consistent quadruple, so the only sound read is
`right = left + w`, `bottom = top + h`. That is run 4's change, and it is the whole change.

**Outcome table is UNCHANGED from run 3's amendment** (the extent criterion stands: content extent
must be 1280x1024). Added VOID condition: **if the `cell sizes plausible` gate reports IMPLAUSIBLE,
the run is VOID for the same reason run 3 was** — the arithmetic is wrong again and the census must
not be interpreted.

⭐ **Kept as a finding in its own right:** `iso+0x54/+0x58` is the camera origin in **world pixel
space**, not a screen viewport at (0,0). That corroborates the earlier `sc3probe.c` note ("the camera
ORIGIN in WORLD pixel space (not a screen viewport)") with a measured negative value, and it is why
"just write the new width" was never going to work.

---

# AMENDMENT — run 5: `FUN_1000ee29` added in Init's order (committed BEFORE the fifth lease)

Run 4 fixed the extent arithmetic (`rect -> 1280x1024`, `cell 32x16`, gate passed) and then
`FUN_10018cdf` **never returned**. Desk work (`RESULTS.md`) established that its loop is MAP-bounded so
it cannot spin on its own, and that **Init's very next step after `FUN_1000e2c0` is
`FUN_1000ee29(this, 8, 8, 0)`** — which runs 1-4 all omitted.

**Change: exactly one call added**, immediately after `FUN_1000e2c0`, reproducing Init's order.
`8, 8` is not a guess — `FUN_100059fb` mode 1 unconditionally returns `8, 8`, so it is the only value
Init ever passes `[CONFIRMED @ 0x100059fb]`.

⚠️ **Owner chose this over the null-delta arm I recommended first.** Recording the tradeoff: if run 5
hangs again, we still will not know whether the extent step is the cause, because no arm has isolated
it on this build. **That control remains owed either way.**

## Outcomes for run 5
| # | reading | verdict |
|---|---|---|
| 1 | census extent **1280x1024**, not uniform | ⭐ **PASS.** `e2c0`+`ee29` is the missing pair. Licenses the cave |
| 2 | census **0% / uniform black** | **INFORMATIVE FAIL, and the predicted risk:** `ee29` zeroes grid B and `FUN_10018cdf` did not refill it — that is the original U-068 mechanism. Distinguishes "hang" from "empty grid" and is progress even so |
| 3 | `FUN_10018cdf` **never returns again** (log stops mid-call) | **FAIL.** `ee29` is not the missing companion. Stop adding calls; run the null-delta arm next |
| 4 | census still **800x600** | **FAIL, extent not applied** — contradicts run 4's measured rect; re-read before interpreting |
| 5 | zero/unchanged size, `REFUSE`, or implausible cell sizes | **VOID**, per the run-2/run-4 conditions |

**Pre-registered reads regardless of outcome:** the `gridB dims/ptr BEFORE/AFTER` pair around `ee29`
(does it reallocate, and to what), and whether `FUN_10018cdf` returns and in how long (50 ms in run 2,
116 ms in run 3, never in run 4 — the timing is itself a discriminator).

Harness claim taken as `resize` before this build. Owner's build untouched; no SIMSPR patch staged.
