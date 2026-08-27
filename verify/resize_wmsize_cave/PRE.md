# PRE-REGISTRATION — `wmsize_setrect` cave witness (committed BEFORE the lease)

**Claim under test.** The `wmsize_setrect` cave (GZGraphicD, recipe committed `c49dbb0`) makes a real
`WM_SIZE` publish the **real** client size, by calling the window's own SetRect `FUN_10018691` with
`lParam`'s LOWORD/HIWORD before the stock handler `FUN_100185f5` runs.

## This is an A/B, and arm A is ALREADY BANKED
Arm A (unpatched) is `verify/resize_wmsize_poll/RESULTS.md`, committed `7f578da` **before** this cave
existed. Same instrument (`-rectpoll`), same city (Europolis), same target (1280x1024), same three
sample points. Arm B changes exactly one thing: `wmsize_setrect` is staged.

| field at **MID** (real WM_SIZE done, before harness repair) | arm A measured | arm B predicted |
|---|---|---|
| `win+0x38..0x44` stored | 800x600 | **1280x1024** |
| `B+0x70..0x7C` window rect -> live | 800x600 | **1280x1024** |
| `B+0x1C..0x28` device surface | 800x600 | **800x600 (unchanged)** |
| `R+0x1C..0x28` render target | 800x600 | **800x600 (unchanged)** |

**The last two rows are predictions of NO CHANGE and they matter.** The cave fixes the stored rect
only. It does **not** re-create the render target or the device surface — that is the SIMSPR per-frame
routine, which is not built. If those move, something other than my cave is acting and the reading
needs explaining before it is believed.

## Outcomes, declared now

| # | reading | verdict |
|---|---|---|
| 1 | stored **and** window rect both 1280x1024 at MID; device + RT unchanged | ⭐ **PASS.** The cave works and does exactly what it claims, no more |
| 2 | stored moves, window rect does NOT | **PARTIAL.** SetRect landed but `FUN_100185f5` did not republish. Report as partial, do not call it a pass |
| 3 | neither moves | **FAIL — the cave did not execute.** Verify it is staged and the hook is reached before blaming the design |
| 4 | game crashes / fails to reach a city | **FAIL, cave faults.** Restore immediately; a WndProc cave is the highest-risk place to be wrong |
| 5 | device surface or RT moves too | **UNEXPECTED.** Do not report as success. Something beyond the cave is acting; explain it first |

## What this run does NOT test, stated before the result
- **The WM_MOVE(3) regression is NOT exercised.** The auto-resize uses `SWP_NOMOVE`, so no `WM_MOVE`
  is generated. The `cmp ebx,5` gate is verified by disassembly ONLY. **Do not claim WM_MOVE safety
  from this run** — it needs a move, which the headless harness does not currently drive.
- **No rendering claim.** The stored rect being true does not make the view redraw; the render target
  and device surface are untouched by design. A black or clipped viewport is EXPECTED here and is not
  a failure of this cave.
- Upward only (`U-069` untouched). Headless, so nothing about the DirectDraw primary (`D-004`).

## Install and restore
Staged for this run: `GZGraphicD.dll` = shipped + `resizable_frame` + `close_button_quit` +
`wmsize_setrect`, one invocation from `.shipped`, gate **109 bytes / 16 runs**. `SIMSPR.DLL` untouched
(owner's four-recipe `f5b9f1d9`).

⚠️ **LAST ACTION OF THE SESSION: restore the owner's two-recipe GZGraphicD (`acefadf0`) and verify it**,
per the standing rule in `BOARD.md`. `wmsize_setrect` is staged for this witness only; it does not join
the owner's standing build until the bridge is complete.
