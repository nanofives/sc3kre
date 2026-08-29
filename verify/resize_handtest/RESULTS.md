# RESULTS — D-004 owner hand-test on a real display, 2026-08-29

**VERDICT: `D-004` NOT CONFIRMED. Row 1 FAILS.** The resize routine runs to completion and the engine's
own surfaces report the new size, but **the enlarged view does not reach the screen** — the city stayed
drawn in the top-left at the pre-resize size while the window was maximized.

The resize mod is **NOT complete end-to-end**. It is complete up to `iso+0x4ec` and no further.

Pre-registration: `HANDTEST.md`, committed **before** the run as `2b7d6c9`, with its PASS/FAIL table.
(`PRE.md` in this folder is the **older** 2026-08-26 no-bridge hand-test and does not cover this run.)
Witness log reproduced verbatim in the appendix at the end of this file (`re/harness/` and `*.log` are
both gitignored, so this file is the only durable copy).

---

## Run

Owner-launched (`resize_launch.exe -- Cities\Europolis.sc3`, `SC3RESIZE_LOG` set, no `-kill`), owner
drove the window by hand on a physical display, owner reported the observation. No harness, no lease.
Display maximized client area = **2048x1081** (so a 2048x1152 monitor).

Install verified **before and after**, unchanged: `Apps/GZGraphicD.dll` = `acefadf0`,
`Apps/SIMSPR.DLL` = `f5b9f1d9`. The mod patches nothing on disk, as designed.

Build confirmed to be the all-4-clamp build before launch (`sc3resize.dll` contains
`all grid-B walkers` and `FUN_1000ef50`). Nothing was rebuilt or re-patched.

## PASS/FAIL against the pre-registered table

| # | observation | result | evidence |
|---|---|---|---|
| 1 | after growing, the city fills the whole window | **FAIL** | owner: did not fill; "still at the top left was the main rendering things" — the pre-registered FAIL signature verbatim |
| 2 | the enlarged view is a real image, not garbage | **N/A** | there is no enlarged view to judge; the drawn region was the un-enlarged one. `[UNCERTAIN]` whether the area outside it was black or stale — not reported |
| 3 | shrinking works | **NOT DETERMINED visually** | log shows the downward cycle completed (see below); the owner did not report on the shrunk frame separately |
| 4 | no crash across several resizes incl. maximize | **PASS** | 3 resize cycles incl. maximize/restore/maximize, zero `FAULT CAUGHT`, game stayed up |
| 5 | HUD reflow | not a blocker | not reported; known separate item |

**Row 1 is decisive and it failed.** Rows 2 and 3 cannot be scored positively from a run whose row 1
failed — there was no full-window image to assess.

Additional owner observation, not in the pre-registered table: **the cursor worked across the whole
window.** So window hit-testing and input mapping did follow the new client size; the failure is
confined to what is presented.

## What the log proves DID work

`sc3resize_handtest.log`, 66 lines, three complete cycles:

| # | t (ms) | direction | dirty grid | outcome |
|---|---|---|---|---|
| 1 | 12139 | 800x600 -> 2048x1081 | 40x30 cell 20x20 -> 16x8 cell 128x135 | `---- done (all 9 steps) ----` |
| 2 | 14427 | 2048x1081 -> 800x600 | 16x8 -> 40x30 cell 20x20 | `---- done (all 9 steps) ----` |
| 3 | 18703 | 800x600 -> 2048x1081 | 40x30 -> 16x8 cell 128x135 | `---- done (all 9 steps) ----` |

- **All four grid-B clamps installed** at 980 ms, rebased onto the relocated `SIMSPR` at `0x03310000`:
  `FUN_1000cedb` (hook `0xCFAB` -> cave `0x614E0`), `FUN_1000d0f5` (`0xD281` -> `0x61520`),
  `FUN_1000be25` (`0xC412` -> `0x61560`), `FUN_1000ef50` (`0xEF50` -> `0x615A0`), then
  `GRIDB_CLAMP: all grid-B walkers clamped`.
- **Readiness gate fired and held**: bridge captured 8142 ms, gate 3000 ms, first resize 12138 ms.
- **Zero `FAULT CAUGHT`** in the whole run. The crash fix holds on a real display under hand-driven
  maximize/restore churn — the first non-headless witness for Fix A.
- Both surfaces re-created and **report the new size**: render target `iso+0x74` and device surface
  `iso+0x4ec`, `FUN_10009efb -> 1`, `+0x24=2048 +0x28=1081` on each grow.
- Step 8 `FUN_1000fa36` re-registered drawables; step 9 pushed `{0,0,2048,1081}` into `iso+0x4d0`.
- Display patches applied: `WINDOWED` (`GZGraphicD+0x6cdac` 0->1, `+0x117D6` nop x4) and
  `FIX16` (cave at `+0x19349`).
- WndProc subclass installed at 3225 ms; **the `WM_SIZE` values in the log are the true client sizes**
  (`2048x1081`, `800x600`), so the stored-size defect is genuinely fixed.

The run ended with `WM_SIZE 800x600` at 45027 ms and no further entry; the process was gone afterwards.
`[UNCERTAIN]` why it ended — consistent with a window close, but not evidenced. Nothing was faulted.

## What this localizes — the remaining gap

Everything from `WM_SIZE` through `iso+0x4ec` is now **witnessed on a real display**: the size is
published correctly, the grids are rebuilt, both surfaces are re-created at 2048x1081, drawables are
re-registered, the present rect is pushed at full extent, and nothing faults. Yet the monitor shows the
old 800x600 image in the top-left.

**Therefore the defect is downstream of `iso+0x4ec`** — in whatever copies that surface to the
DirectDraw primary and flips it. That component was never touched by the 9-step routine and never
resized. `[UNCERTAIN]` — the specific object and call are **not identified**; this is a localization by
elimination, not a confirmed cause. Do not write a fix against a guess.

⛔ **The next reader's trap:** `PRE.md` (2026-08-26) pre-registered this exact visual — "city stays
top-left, new area black" — as meaning *"the render target is NOT resized and the blit is 1:1, the
expected no-bridge outcome"*. **That reading is now WRONG.** The log proves the render target **was**
resized to 2048x1081 on this run. The same pixels mean something different once the bridge is in: the
resize happened and did not reach the primary. Scoring this run against the old table would produce the
wrong conclusion.

## Method finding — the census was a nondiagnostic proxy

`verify/resize_census` censused `iso+0x74` and `iso+0x4ec` at ~100% fill / full bounding box at
2048x1152 and that was reported as "on-screen fill". **It was not.** Both of those surfaces were full
on this run too (the log shows them re-created at the new size) and the screen still showed 800x600 in
the corner. Measuring the last surface the harness can reach is not measuring the flip, and the
distance between them is exactly `D-004`.

This is the third instance of the failure class already on `BOARD.md` ("THE NONDIAGNOSTIC PROXY") and
the first where the proxy passed while the real thing failed.

## Status changes

- `D-004` — **still OPEN**, and now with a positive negative result rather than an unknown.
- Fix A (4 grid-B clamps) — **holds on a real display**, hand-driven, zero faults. Upgraded from
  headless-only evidence.
- Load-readiness gate — **fires correctly on a real load** (Europolis, 8.1 s bridge capture).
- `RESIZABLE_WINDOW.md` claim that the mod "renders a full-window frame at 2048x1152" must be read as
  *renders into its surfaces at that size*, not *displays at that size*.

## What was NOT done

No rebuild, no re-patch, no on-disk change, no tracker mutation. The owner ran the game; this record
interprets the log and the owner's observation only.

---

## Appendix — the witness log, verbatim

`re/harness/sc3resize_handtest.log`, 66 lines, reproduced here because `re/harness/` and `*.log`
are both gitignored and this file is the record.

```
[    0.379 ms][tid 62fc] ### sc3resize loaded - resizable-window mod (minimal Init-free routine, validated 2026-08-27 over 6 runs)
[  979.939 ms][tid 2f24] ### RESIZE: SIMSPR base 0x03310000 (relocated: YES)  GZGraphicD base 0x027C0000 (YES)
[  980.093 ms][tid 2f24] --- WINDOWED: GZGraphicD+0x6cdac = 0 -> 1
[  980.173 ms][tid 2f24] --- WINDOWED: GZGraphicD+0x117D6 'mov [ebx+0x48],1' -> nop x4
[  980.244 ms][tid 2f24] --- FIX16: 16bpp branch injected at 0x19349 -> cave 0x033C0000 (5-6-5)
[  980.322 ms][tid 2f24] --- GRIDB_CLAMP FUN_1000cedb: index clamped (hook 0xCFAB -> cave 0x614E0, base 0x03310000)
[  980.732 ms][tid 2f24] --- GRIDB_CLAMP FUN_1000d0f5: index clamped (hook 0xD281 -> cave 0x61520, base 0x03310000)
[  980.775 ms][tid 2f24] --- GRIDB_CLAMP FUN_1000be25: index clamped (hook 0xC412 -> cave 0x61560, base 0x03310000)
[  980.810 ms][tid 2f24] --- GRIDB_CLAMP FUN_1000ef50: index clamped (hook 0xEF50 -> cave 0x615A0, base 0x03310000)
[  980.826 ms][tid 2f24] --- GRIDB_CLAMP: all grid-B walkers clamped (OOB bucket-index AV fixed engine-wide)
[  980.876 ms][tid 2f24] ### RESIZE: armed - windowed+fix16 applied, bridge capture at SIMSPR+0x16EBA, per-frame poll at GZGraphicD+0x18C58 (create recorder DROPPED after v2 crash)
[ 3225.668 ms][tid 7944] ### RESIZE: window 0x006E0E72 subclassed (old proc 0x027D7E11) - WM_SIZE observed, resize performed on the render thread
[ 8142.517 ms][tid 7944] ### RESIZE: bridge captured 0x0D3549D8 (iso view = bridge+0x18 = 0x00000000); readiness gate = 3000 ms
[12138.146 ms][tid 7944] RZ   WM_SIZE 2048x1081 - poll will pick it up on the next frame
[12139.248 ms][tid 7944] RZ   size change: client 2048x1081 vs render target 800x600
[12139.307 ms][tid 7944] RZ   ---- resize to 2048x1081 ---- iso=0x0DB19270 R=0x0F034D90 B=0x0058B650 bridge=0x0D3549D8
[12139.326 ms][tid 7944] RZ   extent BEFORE: (-848,2924,-48,3524) -> 800x600  dirtygrid=40x30 cell=20x20
[12139.347 ms][tid 7944] RZ   extent AFTER: (-848,2924,1200,4005) -> 2048x1081  dirtygrid=16x8 cell=128x135  (cell sizes plausible)
[12139.364 ms][tid 7944] RZ   render-target iso+0x74 0x0F034D90 NO RECORDED CREATE (0 known) - FALLING BACK to field read-back [_ _ 7 16 0 0 0 0]. Field read-back is NOT proven equivalent: p3 measured 7 vs a recorded 4 on 2026-08-28.
[12139.378 ms][tid 7944] RZ   render-target iso+0x74 replay at 2048x1081
[12139.433 ms][tid 7944] RZ   render-target iso+0x74 FUN_10009efb -> 1 | now +0x24=2048 +0x28=1081
[12139.454 ms][tid 7944] RZ   device-surface iso+0x4ec 0x0058B650 NO RECORDED CREATE (0 known) - FALLING BACK to field read-back [_ _ 7 16 0 0 3 0]. Field read-back is NOT proven equivalent: p3 measured 7 vs a recorded 4 on 2026-08-28.
[12139.467 ms][tid 7944] RZ   device-surface iso+0x4ec replay at 2048x1081
[12142.488 ms][tid 7944] RZ   device-surface iso+0x4ec FUN_10009efb -> 1 | now +0x24=2048 +0x28=1081
[12198.450 ms][tid 7944] RZ   FUN_10018cdf -> 1
[12198.529 ms][tid 7944] RZ   [step 8] FUN_1000fa36(iso, recompute=1, purge=0) - re-register drawables from iso+0x3a4
[12198.700 ms][tid 7944] RZ   [step 8] FUN_1000fa36 returned
[12198.731 ms][tid 7944] RZ   [step 9] present list iso+0x4d0: begin=0x0DADB670 end=0x0DADB690 (2 rect(s)) - erase then push {0,0,2048,1081}
[12198.749 ms][tid 7944] RZ   [step 9] after: begin=0x0DADB670 end=0x0DADB680 (1 rect(s))
[12198.763 ms][tid 7944] RZ   ---- done (all 9 steps) ----
[14426.806 ms][tid 7944] RZ   WM_SIZE 800x600 - poll will pick it up on the next frame
[14427.910 ms][tid 7944] RZ   size change: client 800x600 vs render target 2048x1081
[14427.965 ms][tid 7944] RZ   ---- resize to 800x600 ---- iso=0x0DB19270 R=0x0F034D90 B=0x0058B650 bridge=0x0D3549D8
[14427.984 ms][tid 7944] RZ   extent BEFORE: (-848,2924,1200,4005) -> 2048x1081  dirtygrid=16x8 cell=128x135
[14428.017 ms][tid 7944] RZ   extent AFTER: (-848,2924,-48,3524) -> 800x600  dirtygrid=40x30 cell=20x20  (cell sizes plausible)
[14428.035 ms][tid 7944] RZ   render-target iso+0x74 0x0F034D90 NO RECORDED CREATE (0 known) - FALLING BACK to field read-back [_ _ 7 16 0 0 0 0]. Field read-back is NOT proven equivalent: p3 measured 7 vs a recorded 4 on 2026-08-28.
[14428.091 ms][tid 7944] RZ   render-target iso+0x74 replay at 800x600
[14428.149 ms][tid 7944] RZ   render-target iso+0x74 FUN_10009efb -> 1 | now +0x24=800 +0x28=600
[14428.171 ms][tid 7944] RZ   device-surface iso+0x4ec 0x0058B650 NO RECORDED CREATE (0 known) - FALLING BACK to field read-back [_ _ 7 16 0 0 3 0]. Field read-back is NOT proven equivalent: p3 measured 7 vs a recorded 4 on 2026-08-28.
[14428.185 ms][tid 7944] RZ   device-surface iso+0x4ec replay at 800x600
[14430.339 ms][tid 7944] RZ   device-surface iso+0x4ec FUN_10009efb -> 1 | now +0x24=800 +0x28=600
[14430.541 ms][tid 7944] RZ   FUN_10018cdf -> 1
[14430.561 ms][tid 7944] RZ   [step 8] FUN_1000fa36(iso, recompute=1, purge=0) - re-register drawables from iso+0x3a4
[14430.697 ms][tid 7944] RZ   [step 8] FUN_1000fa36 returned
[14430.713 ms][tid 7944] RZ   [step 9] present list iso+0x4d0: begin=0x0DADB670 end=0x0DADB680 (1 rect(s)) - erase then push {0,0,800,600}
[14430.728 ms][tid 7944] RZ   [step 9] after: begin=0x0DADB670 end=0x0DADB680 (1 rect(s))
[14430.741 ms][tid 7944] RZ   ---- done (all 9 steps) ----
[18701.838 ms][tid 7944] RZ   WM_SIZE 2048x1081 - poll will pick it up on the next frame
[18703.372 ms][tid 7944] RZ   size change: client 2048x1081 vs render target 800x600
[18703.435 ms][tid 7944] RZ   ---- resize to 2048x1081 ---- iso=0x0DB19270 R=0x0F034D90 B=0x0058B650 bridge=0x0D3549D8
[18703.456 ms][tid 7944] RZ   extent BEFORE: (-1437,2043,-637,2643) -> 800x600  dirtygrid=40x30 cell=20x20
[18703.482 ms][tid 7944] RZ   extent AFTER: (-1437,2043,611,3124) -> 2048x1081  dirtygrid=16x8 cell=128x135  (cell sizes plausible)
[18703.500 ms][tid 7944] RZ   render-target iso+0x74 0x0F034D90 NO RECORDED CREATE (0 known) - FALLING BACK to field read-back [_ _ 7 16 0 0 0 0]. Field read-back is NOT proven equivalent: p3 measured 7 vs a recorded 4 on 2026-08-28.
[18703.514 ms][tid 7944] RZ   render-target iso+0x74 replay at 2048x1081
[18703.599 ms][tid 7944] RZ   render-target iso+0x74 FUN_10009efb -> 1 | now +0x24=2048 +0x28=1081
[18703.622 ms][tid 7944] RZ   device-surface iso+0x4ec 0x0058B650 NO RECORDED CREATE (0 known) - FALLING BACK to field read-back [_ _ 7 16 0 0 3 0]. Field read-back is NOT proven equivalent: p3 measured 7 vs a recorded 4 on 2026-08-28.
[18703.640 ms][tid 7944] RZ   device-surface iso+0x4ec replay at 2048x1081
[18706.498 ms][tid 7944] RZ   device-surface iso+0x4ec FUN_10009efb -> 1 | now +0x24=2048 +0x28=1081
[18706.701 ms][tid 7944] RZ   FUN_10018cdf -> 1
[18706.724 ms][tid 7944] RZ   [step 8] FUN_1000fa36(iso, recompute=1, purge=0) - re-register drawables from iso+0x3a4
[18706.887 ms][tid 7944] RZ   [step 8] FUN_1000fa36 returned
[18706.904 ms][tid 7944] RZ   [step 9] present list iso+0x4d0: begin=0x0DADB670 end=0x0DADB680 (1 rect(s)) - erase then push {0,0,2048,1081}
[18706.918 ms][tid 7944] RZ   [step 9] after: begin=0x0DADB670 end=0x0DADB680 (1 rect(s))
[18706.931 ms][tid 7944] RZ   ---- done (all 9 steps) ----
[45027.353 ms][tid 7944] RZ   WM_SIZE 800x600 - poll will pick it up on the next frame
```
