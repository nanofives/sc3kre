# RESULTS — WM_SIZE rect-poll witness (2026-08-27). **OUTCOME #1: PREDICTION CONFIRMED.**
# PRE.md committed before the lease at git `49ea7bd`. One lease, one launch, no retries.

**Verdict: the pre-registered top row landed.** `B+0x70..0x7C` does **NOT** move on a real `WM_SIZE`,
while the OS window demonstrably did resize — and the control proves the instrument could see it move.
**The `WM_SIZE` cave is required. The 2026-08-27 correction holds.**

Run: Europolis, `-rectpoll -resizeto 1280x1024 -resizeat 30`, owner's standing build live, 60 s cap.
**Both modules RELOCATED** (SIMSPR `0x03440000`, GZGraphicD `0x02830000`) — the readings are
position-independent in fact, not just in design.

## The measurement (`RPOLL>` lines, `capture.log:757-767, 1063-1067`)

| point | `B+0x70..0x7C` -> live | `B+0x1C..0x28` dev | `R` rect | `win+0x38..0x44` stored | `GetClientRect` (OS) |
|---|---|---|---|---|---|
| **PRE** | `(0,29,800,629)` -> **800x600** | 800x600 | 800x600 | 800x600 | 2560x1351 |
| **MID** (real WM_SIZE done, before repair) | `(0,29,800,629)` -> **800x600** | 800x600 | 800x600 | 800x600 | **1280x1024** |
| **POST** (after `rz_apply`) **[CONTROL]** | `(0,29,1280,1053)` -> **1280x1024** | **1280x1024** | **1280x1024** | **1280x1024** | 1280x1024 |

**The discriminator is MID.** The OS client went 2560x1351 -> 1280x1024, so a real `WM_SIZE` provably
fired and was processed — and **every engine-side field stayed at 800x600**, byte-identical to PRE.

**The control is what makes that meaningful.** At POST the same instrument, reading the same field on
the same object (`B` = `0x0054C540` at all three points), reports 1280x1024. So the probe can see this
field change; a still reading at MID is a fact about the game, not a blind instrument. Outcome #3
(VOID) is positively excluded rather than assumed away.

## Secondary question ANSWERED in the same run — `[UNCERTAIN]` closed
**Does GZGraphicD re-Init its own device surface on a resize?** **NO.** `B+0x1C..+0x28` stayed
`800x600` at MID and only moved at POST, under our own repair. **A resize fix must drive the device
surface itself** — the engine will not do it. (Observational, as pre-registered; no design decision in
this run rested on it.)

## Two findings the run produced that were NOT pre-registered
Recorded as observations, not as claims the pre-registration earns:

1. ⭐ **The render target is a NEW OBJECT after the repair** — `R` = `0x12329750` at PRE/MID,
   `0x12A7EFC0` at POST. So the resize path re-creates the raster rather than resizing it in place.
   **Consequence for the poll design: re-read `R` from `iso+0x74` on every sample.** A cached `R` would
   read a freed object. The instrument already did this, by luck of how it was written, not by design.
2. `[UNCERTAIN]` **The engine was ALREADY out of sync with the OS before any resize** — at PRE the OS
   client was **2560x1351** while every engine field said 800x600. Not investigated, not needed for
   this result (the test is whether the field *moves*, and the PRE/MID pair is internally consistent),
   but it means `-fitclient` did not produce the client size the engine believed in. **Do not cite the
   PRE row as evidence that the engine and OS agree at startup.** Worth its own look before any claim
   that depends on startup geometry.

## Scope limits, as pre-registered
Upward only (`U-069` untouched). Headless, so **no claim about the DirectDraw primary** (`D-004`).
Observe-only: nothing was staged, nothing wired.

## State at close
Owner's standing build verified live and byte-checked: `SIMSPR.DLL` `f5b9f1d9` (scroll `8.0` x5, dead
zone `2.0`), `GZGraphicD.dll` `acefadf0` (`0x10018570` = `cd`). Lease released, harness claim released,
no game process alive.

## Next
Build the **GZGraphicD `WM_SIZE` cave**: at `FUN_10017e2f`'s `param_2 == 5` branch call
`this->vt[0x1c]` (`FUN_10018691`) with `(0, 0, LOWORD(lParam), HIWORD(lParam))` before letting
`vt+0x30` run. ⚠️ Gate on `param_2 == 5` ONLY — `WM_MOVE(3)` shares that branch and its `lParam`
carries x/y. Then the SIMSPR per-frame poll becomes sound, and it must also drive the device surface
(finding above), not only the render target.
