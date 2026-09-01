# PARENTFIX_PRE.md — the ancestor-rect fix (2026-09-01)

**Committed before the run.**

## Fix

`rz_fix_hud_parents()` walks `win+0x3c` up from each relocated window and widens any ancestor
whose `+0x14..0x20` rect is smaller than the client, stopping at the root (`parent == NULL`,
never touched — `FUN_10020818` calls `root->vt[0x130]` directly with no geometry test).

Direct field write, not `vt+0xc8` SetRect: only `+0x14..0x20` gates routing (`vt+0xe4` =
`FUN_1001f8ef` compares exactly those), and SetRect on a container may relayout children and undo
the cluster placement. Widen only, never shrink, refuse on non-positive extents.

## Arms

| arm | env |
|---|---|
| **A** fix | `SC3RESIZE_CLUSTER=1` (fix is default-on) |
| **B** control | `SC3RESIZE_CLUSTER=1 SC3RESIZE_NOPARENTFIX=1` |

## Pre-registered outcomes

Measured with `frida_route3.py`, state-gated to the router branch, click posted at the relocated
bar centre (1547,1053).

| # | observation | verdict |
|---|---|---|
| **P-PASS** | arm A: the container passes `vt+0xe4` (ret=1), recursion occurs, and the **bar receives `vt+0xe4` with (1547,1053) returning 1**; arm B: bar touched 0 times | **Root cause confirmed and fixed at the routing level.** |
| **P-PARTIAL** | container passes and recursion occurs, but the bar still is not reached or returns 0 | The ancestor rect was **a** blocker, not the only one. Report as partial. |
| **P-FAIL** | arm A behaves like arm B (bar touched 0 times) | The fix does not do what it was designed to do. Root cause stands but the write is ineffective. |
| **VOID** | state gate not satisfied, `PARENT>` lines absent, or a fault fires | Do not interpret. |

## Stated in advance

- **This measures ROUTING, not clickability.** Reaching the widget is necessary, not sufficient —
  the widget's own handler still has to act. A P-PASS does **not** entitle me to say "the HUD is
  clickable"; only an owner hand-test does.
- Arm B must reproduce the old behaviour, or arm A proves nothing.
- Widening a container's rect could have side effects on painting or layout that this trace cannot
  see. `[UNCERTAIN]` until a hand-test looks at the screen.
