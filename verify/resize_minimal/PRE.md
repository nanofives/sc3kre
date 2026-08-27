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
