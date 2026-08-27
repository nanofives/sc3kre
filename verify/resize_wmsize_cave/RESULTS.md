# RESULTS — `wmsize_setrect` cave witness (2026-08-27). **OUTCOME #1: PASS.**
# PRE.md git `c233790`, committed before the lease. Arm A banked separately at `7f578da`.

**Verdict: the cave does exactly what it claims, and nothing more.** A real `WM_SIZE` now publishes the
**real** client size into the window object and onward to the device rect at `B+0x70..0x7C`. Both
"no change" predictions also held, which is what rules out something other than the cave acting.

Staged: `GZGraphicD` = shipped + `resizable_frame` + `close_button_quit` + `wmsize_setrect`, gate
**109 bytes / 16 runs** verified before the launch. SIMSPR untouched. Europolis, `-rectpoll
-resizeto 1280x1024 -resizeat 30`. **No crash**, city reached, shot produced.

## The A/B at MID (real WM_SIZE processed, before any harness repair)

| field | arm A (no cave, `7f578da`) | **arm B (cave)** | predicted |
|---|---|---|---|
| `win+0x38..0x44` stored | 800x600 | **1280x1024** | 1280x1024 ✓ |
| `B+0x70..0x7C` -> live | 800x600 | **1280x1024** | 1280x1024 ✓ |
| `B+0x1C..0x28` device surface | 800x600 | **800x600** | unchanged ✓ |
| `R+0x1C..0x28` render target | 800x600 | **800x600** | unchanged ✓ |
| OS `GetClientRect` | 1280x1024 | 1280x1024 | — |

**All four predictions landed, including both no-change rows.** The cave moves the stored rect and the
device rect; it leaves the render target and the device surface alone, exactly as designed. Outcome #5
(something else acting) is positively excluded rather than assumed.

## ⭐ BONUS — this retro-explains arm A's open `[UNCERTAIN]`
Arm A recorded, unexplained: *at PRE the OS client was 2560x1351 while every engine field said
800x600.* **Arm B's PRE row reads `stored = 2560x1351`, matching `GetClientRect` exactly.**

So the startup mismatch was **the same defect, not a separate one**: the engine was out of sync from
the very first `WM_SIZE`, because `WM_SIZE` never propagated a real size. The cave fixes it from that
first message onward. **One defect explained two anomalies** — and the arm A `[UNCERTAIN]` is closed
without spending a run on it.

(`R` pointer PRE/MID `0x12335F08`, POST `0x12D40EE8` — the render target is re-created on the repair,
reproducing arm A's observation on a different base. Both modules relocated again: `0x0315E894`
vtable => GZGraphicD at `0x03140000`.)

## What this run does NOT show, as pre-registered
- ⚠️ **WM_MOVE(3) safety is NOT exercised.** `SWP_NOMOVE` means no `WM_MOVE` was generated. The
  `cmp ebx,5` gate is **disassembly-verified only**. This still needs a real move before the cave
  ships in a standing build.
- **No rendering claim.** The render target and device surface are untouched by design, so the view is
  not expected to redraw correctly yet. That is the SIMSPR per-frame routine, not built.
- Upward only (`U-069` untouched). Headless, so nothing about the DirectDraw primary (`D-004`).

## State at close
**Owner's build restored and verified**: `GZGraphicD.dll` `acefadf0` (two recipes, 65 bytes / 12 runs),
`SIMSPR.DLL` `f5b9f1d9`, and the hook site `0x10017f17` reads back the shipped `8b 06 8b ce ff 50 30`.
`wmsize_setrect` is **not** in the owner's standing build. Lease and harness claim released, no game
process alive.

## Next
The SIMSPR per-frame routine: re-create the render target (raster `vt+0x0c` = `FUN_10009efb`, clear the
`+0x08` created-guard) **and drive the device surface** (`B+0x1C..0x28` — proven in arm A that the
engine will not), refill grid B via `FUN_10018cdf`, present rect already ships as `resize_rectfix`.
Re-read `R` from `iso+0x74` every sample; it is a new object after each resize.
