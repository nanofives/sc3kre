# PRE-REGISTRATION — whole-view repaint (step 10), the render-pipeline fix for A+B

Committed **before** the hand-test. Owner is the instrument (real-display run).

## Why

Drawable re-registration is **falsified** (`verify/resize_gridreshow/`): 65536/65536 cells re-shown, no
visual change. The defect is **downstream** — the resize recreates the render target `iso+0x74` but never
marks the view dirty, so the per-frame composite `FUN_1000dc17` (which only processes incremental
dirty-rect lists, empty after a surface recreate) draws nothing into the fresh surface.

Cross-DLL read (`RESIZABLE_WINDOW.md` §9): the data-view toggle repairs the screen by running the
iso-view **whole-view repaint** `iso vtable+0x144`, bracketed by a device batch, at
`FUN_1001818c:53-55`. `bridge` is the cMapView, so `iso = bridge+0x18` (already used).

Verified from the PE: `iso vtable+0x144 (0x10062650) = FUN_1000db86`. Its body (SIMSPR 0x1000db86):
`FUN_1000e248` (clear draw lists + dirty grid) then tessellate the whole extent `iso+0x54..0x60` into 64
dirty rects via `+0x130` and set `iso+0x32c=1`. So the next composite redraws the entire view.

## The change (`re/harness/src/sc3resize.c`, new step 10)

After step 9, call `FUN_1000db86(iso)` — `__fastcall(ecx=iso)`, no args, called directly by RVA (the
slot->RVA is PE-verified). This marks the full extent dirty; the game composites every frame, so the
whole view (terrain, zones, **buildings, roads**, sprites) redraws into the resized surface on the next
frame. The device begin/end batch the toggle wraps it in is for a *synchronous* present; we do not need
it (the per-frame composite presents), and it is omitted to avoid dispatching unverified device vtable
slots. Under the SEH fault catcher (`g_rz_step = 10`). Steps 1-9 (incl. 8a/8b/8c) retained. No on-disk
change.

## Outcomes, committed in advance

| observation | verdict |
|---|---|
| Log `[step 10] FUN_1000db86 returned` + `done (all 10 steps)` AND after a resize **buildings, roads, terrain and zones all render with NO manual layer toggle** | **PASS — defects A and B fixed, resize mod complete end-to-end** |
| Step 10 runs but the view is still blank/partial until a toggle | **FAIL** — marking dirty is not sufficient; the device begin/end batch (or a synchronous present) is required. Next: add the `bridge+0x14` device `+0x240`/`+0x244` bracket around the repaint |
| `iso+0x32c` logs as 0 after the call (expected 1) | **diagnostic** — `FUN_1000db86` did not run its body as expected; re-check the RVA/convention |
| `FAULT CAUGHT` at step 10 (code + MODULE+RVA) | **FAIL** — `FUN_1000db86` faulted; the log localises it |
| View redraws but flickers / wrong for a frame then settles | **PASS with a note** — cosmetic, acceptable |
| Crash / hang | **FAIL** — restore, report the last `RZ` line |

**Decisive:** after a resize, with NO manual layer toggle, does the whole city render.

## Falsifiability

If step 10 runs clean (`iso+0x32c=1`, no fault) and the view is still blank without a toggle, then
marking dirty is insufficient and the **device batch bracket** (`bridge+0x14` `+0x240`/`+0x244`) is the
operative part — that is the next build, not another repaint variant.

## Protocol

Harness claimed `handtest`. Owner launches (`resize_launch.exe -- <city>`, `SC3RESIZE_LOG` set, no
`-kill`), resizes by hand, reports what renders **before** touching any layer control. Prior log
archived `re/harness/sc3resize_handtest.gridreshow.log`. Install (`SIMSPR f5b9f1d9`, `GZGraphicD
acefadf0`) verified before/after; no on-disk change.

## STATUS

Built + string-verified (`step 10] FUN_1000db86`, `done (all 10 steps)`, `10=fullrepaint` present;
steps 1-9 retained; PE32; install intact). iso vt+0x144 -> FUN_1000db86 confirmed from the PE.
Pre-registered. Awaiting the owner hand-test.
