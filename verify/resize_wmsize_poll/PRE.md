# PRE-REGISTRATION — WM_SIZE rect-poll witness (committed BEFORE the lease)

**Question.** Does the window client rect at `B+0x70..0x7C` — where `B` = `*(iso+0x4ec)`, the object
SIMSPR already holds — **change across a real resize**? If it does, a SIMSPR-only per-frame poll can
self-trigger and no GZGraphicD cave is needed. If it does not, the cave is required and its job is to
make the stored rect true.

**Prediction (from the 2026-08-27 static correction, `BOARD.md` / `STATUS_resize.md`).**
`B+0x78-B+0x70` will **NOT** change across the real `WM_SIZE`, because `FUN_100185f5` republishes the
window object's **STORED** size (`vt+0x68` = `FUN_10017c1e` = `*(win+0x40)-*(win+0x38)`), and nothing
updates `win+0x38..0x44` on a stock resize `[CONFIRMED @ 0x100185f5, 0x10017c1e, 0x10018691]`.

## Instrument — three sample points, and the third is the CONTROL

The harness's auto-resize does `SetWindowPos` (real `WM_SIZE`) and *then* `SendMessage(WM_EXITSIZEMOVE)`,
which runs `rz_apply` — and `rz_apply` performs its own `FUN_10018691 SetRect(0,0,w,h)` repair
(`sc3probe.c:6362-6387`). So the samples must straddle that:

| point | when | what it shows |
|---|---|---|
| **A: PRE** | before `SetWindowPos` | baseline |
| **B: MID** | in `rz_wndproc` on `WM_EXITSIZEMOVE`, **before** `rz_apply` | ⭐ the discriminator: real WM_SIZE has fired, harness repair has NOT |
| **C: POST** | same handler, **after** `rz_apply` | ⭐ the CONTROL |

**Point C is what makes a null result meaningful.** `rz_apply` is known to drive the SetRect that
should move `B+0x70..0x7C`. If C shows the field moving while B does not, the instrument provably CAN
see this field change, and "no change at B" is a fact about the game. **If C also shows no change, the
instrument is blind and the whole run is VOID** — no conclusion may be drawn about the stock path. This
is the defence against the silent-failure class already on this board twice.

## Fields read at each point
- gate: `B` vtable == `GZGraphicD+0x1F328` (refuse and log if not — never dereference on a mismatch)
- `B+0x70/0x74/0x78/0x7C` → `live_w`, `live_h` (window client rect, screen coords)
- `B+0x1C/0x20/0x24/0x28` → device surface rect (**a DIFFERENT field**, re-Init only)
- `R` = `*(iso+0x74)`, gate vtable == `GZGraphicD+0x1E894`; `R+0x24/+0x28` → `rt_w`, `rt_h`
- `win+0x38..0x44` (stored rect) and `win+0x34` (HWND)
- `GetClientRect(HWND)` — OS ground truth; the harness may call user32 freely

## Outcomes, declared now

| # | reading | verdict |
|---|---|---|
| 1 | C moves, **B does not** | ⭐ **PREDICTION CONFIRMED.** Poll alone cannot work; the WM_SIZE cave is required. Proceed to build it |
| 2 | **B moves** at MID | ⛔ **PREDICTION REFUTED.** The 2026-08-27 correction is wrong, the simpler poll-only design returns. Say so plainly |
| 3 | neither B nor C moves | **VOID — instrument blind.** No claim about the stock path. Debug the instrument, do not interpret |
| 4 | `B` or `R` vtable gate refuses | **VOID for that point**, logged as a refusal, not a crash |

Secondary, same run, no extra lease — settles the open `[UNCERTAIN]`: does `B+0x1C..+0x28` (device
surface) change across the resize, i.e. does GZGraphicD re-Init its own surface, or must our cave?
**This is observational only.** It is NOT gated by the outcomes above and no design decision rests on
it in this run.

## Scope limits, stated before the result
- Upward resize only (1024x768 -> 1280x1024). `U-069` (downward) stays untested.
- Headless harness. Per **D-004** the device/DirectDraw layer cannot be judged here; this run makes
  **no** claim about the primary surface.
- Observe-only. **No patch is staged for this run** beyond the owner's standing build; nothing is wired
  behind the poll until this returns.

## Install state for the run
Owner's standing build stays live (four-recipe `SIMSPR` `f5b9f1d9`, `GZGraphicD` `acefadf0`). The
instrument is harness-side only. **Last action of the session: verify the owner's build is still live**
and release the lease + harness claim.
