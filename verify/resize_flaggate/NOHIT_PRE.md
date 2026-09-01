# PRE_NOHIT.md — arm A: disable the `+0x80..0x8c` write (2026-09-01)

**Written and committed before the build. Score the run against this file only.**

## The hypothesis

`rz_win_move_hit` translates the window's `+0x80..0x8c` rect, preserving its size, at three call
sites. Two facts from the decompilation, both read before this build:

1. **The write cannot help.** `FUN_1006ddbd` (vt+0x1a0) reads those four fields **only as a width and
   a height** — `param_1 >= [+0x88]-[+0x80]`, `param_2 >= [+0x8c]-[+0x84]`
   `[CONFIRMED @ SIMUI 0x1006ddbd]`. A size-preserving translation leaves both differences identical,
   so the verdict is unchanged **by construction**. And `FUN_1006ddbd` is not even the hit test on the
   path: `FUN_1001e748` calls `vt+0xe4` = `FUN_1006de62`, which compares the **window rect
   `+0x14..0x20`** `[CONFIRMED @ GZWIND 0x1001e748; SIMUI 0x1006de62]`.
2. **The write can hurt.** `+0x80`/`+0x84` are read by `vt+0x98`/`vt+0x9c` and **summed up the parent
   chain** by `vt+0xdc` = `FUN_1006dd44` to build the screen→local origin
   `[CONFIRMED @ SIMUI 0x1006dd44]`. The mod writes **absolute screen coordinates** into a link of a
   **parent-relative sum**. If the chain is not rooted at (0,0), the offset is double-counted and the
   transformed coordinate lands outside the target.

**So: the mod's own clickability "fix" may be the thing causing the miss.** `SC3RESIZE_NOHIT=1`
disables all three writes and leaves `+0x80..0x8c` exactly as the engine built it.

## Arms

| arm | env | expectation |
|---|---|---|
| **A** | `SC3RESIZE_CLUSTER=1 SC3RESIZE_INPUT=1 SC3RESIZE_NOHIT=1` | the HUD relocates and `+0x80..0x8c` is untouched |
| **B** (control) | `SC3RESIZE_CLUSTER=1 SC3RESIZE_INPUT=1` | current shipping behaviour, known not clickable |

B must be run too. Without it, "A is not clickable" cannot be separated from "this build broke
something", and "A is clickable" cannot be separated from a run-to-run difference.

## Pre-registered outcomes

A click only counts as evidence if the log shows `<<< CLICK IS INSIDE THIS WINDOW RECT` for the
window aimed at. Run 36's lesson: "nothing responded" is worthless unless the click is shown to have
landed on the target.

| # | observation | verdict |
|---|---|---|
| **A-PASS** | Arm A: a verified-inside click makes the HUD **respond**; arm B: it does not | **The `+0x80/+0x84` write was the blocker.** Remove it, keep the relocation. |
| **A-FAIL** | Arm A: verified-inside clicks still do nothing (B likewise) | The write is **not** the blocker. It is still a proven no-op for containment and should be removed as dead code, but the defect is elsewhere — next suspect is walk reachability from `sink+0x38`. |
| **A-REGRESS** | Arm A is clickable **and so is B** | Something other than this flag changed. **VOID** — do not credit the flag. |
| **VOID** | No click verified inside a logged rect, or the HUD does not relocate, or a fault fires | Do not interpret. Fix and re-run. |

## Stated in advance

- **A-FAIL does not rescue the flag hypothesis.** `vt+0xf0(0x80000)` is already refuted statically
  (`PRE.md`) and must not be revived by a null result here.
- **A-PASS is a cause, not a design.** It would show the write is harmful; the correct replacement
  (leave it alone vs. write a parent-relative value) is a separate question needing the parent chain,
  which this run does not measure.
- **I am not predicting the outcome.** Fact 1 says the write is useless; fact 2 says it *may* be
  harmful, and whether the parent chain is rooted at (0,0) is `[UNCERTAIN]` and unmeasured. If it is
  rooted at (0,0), absolute equals relative, the write is harmless, and A-FAIL is expected.

## What the run also banks regardless of verdict

A per-click `WINSTATE>` line per captured window, using only confirmed offsets: window rect
`+0x14..0x20` (what `FUN_1006de62` compares), extents `+0x80..0x8c`, and flags `+0xa0` with the
**shown** bit `0x1` broken out — which is the surviving live gate from `PRE.md`, since
`FUN_1001e748` skips any child whose `vt+0xf0(1)` is false.

## Verdict

*(filled in after the run — leave empty until then)*
