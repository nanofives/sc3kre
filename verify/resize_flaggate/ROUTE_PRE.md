# ROUTE_PRE.md — instrument `FUN_1001ec22`, the router clicks actually take (2026-09-01)

**Committed before the run. Score against this file only.** Tool: `re/tools/frida_eventroute.py`.

## Why

`CLICKPATH_RESULTS.md` measured `sink+0x28 == 0` **and** `sink+0x30 == 0` in normal play, so
`FUN_10020818` early-returns through `(sink+0x38)->vt[0x130]` and the `vt+0x8c` walk never runs
(walk entries = 0 across 7 posted clicks in two runs). The router is
**`GZWIND FUN_1001ec22`** `[CONFIRMED @ GZWIND 0x1001ec22, 0x10020818]`:

```c
for (child in this+0x34) {
    if ((*child->vt[0x100])()            != 0 &&   /* gate 1: NO arguments */
        (*child->vt[0xe4])(ev[1], ev[2]) != 0) {   /* gate 2: point-in-window */
        ...
        return (*child->vt[0x130])(ev);            /* recurse */
    }
}
```

A relocated HUD window can be lost in exactly two places, and they need different fixes.

## What the instrument does

At setup it walks the window tree read-only from `root = *(*(*(GZGraphicD+0x6cdb8)+0x30)+0x38)`,
collects **every distinct** `vt+0x100` / `vt+0xe4` / `vt+0x130` target from the **live** vtables, and
hooks all of them. Then it posts a real click and logs each gate call with the caller's rect and
flags.

Hooking every live copy is the correction from `HITTEST_RESULTS.md`, where three hard-coded SIMUI
addresses never fired and the resulting `flagCalls=0` was nearly misread as "no flags queried".
Classes override these slots; one address is not the function.

Trace is opened only inside an outermost event of type 7/8/9 (button), so the mouse-move flood
(type `0xb`) stays out of the log.

## Probe points

| name | point | in |
|---|---|---|
| `bar_bg` | (1547,1053) | relocated bar `[1248 1025 1847 1081]` |
| `viewport` | (400,300) | open city view (**control**) |
| `native_bar` | (299,572) | where the bar used to be `[0 544 599 600]` |

## Pre-registered outcomes

| # | observation | verdict |
|---|---|---|
| **G1-REJECT** | a relocated HUD window's `vt+0x100` returns **0** | **Gate 1 is the blocker.** Skipped before geometry is consulted; the fix is about that flag/state, and no amount of rect correctness helps. |
| **G2-REJECT** | `vt+0x100` returns 1 and `vt+0xe4` returns **0** for a relocated window whose rect **contains** the point | **Gate 2 is the blocker** — a geometry test failing on correct geometry, meaning `vt+0xe4` reads something other than `+0x14..0x20` on that class. |
| **NOT-VISITED** | neither gate is ever called for any relocated HUD window | The window is **not a child on the routed subtree**. A parenting defect, and the third distinct answer. |
| **ROUTED-OK** | the relocated window passes both gates and is recursed into | **The router delivers the click.** The defect is then inside the widget's own handler, downstream of routing entirely. |
| **VOID** | no type-7 event traced, zero hooks installed, `viewport` (control) produces no gate calls, or a fault fires | Do not interpret. Fix and re-run. |

**`viewport` is the instrument control.** A click over the open city view must produce gate traffic.
If it does not, the router is not being observed and nothing else in the run may be read. This is
the check skipped three times by the surface-census work.

## Stated in advance

- **ROUTED-OK would refute the whole "input is broken" framing** and move the defect into widget
  handlers. It is a real possible outcome.
- `native_bar` distinguishes "the router uses stale native geometry" from "the router is fine": if a
  HUD window passes `vt+0xe4` for the *old* position, something on this path is still native.
- **No fix is designed from this run.** Two sessions of fixes were built on a path normal clicks do
  not take; the cost of one more read-only run is far below the cost of a fourth wrong fix.
- Posted `WM_*` messages are not hardware input (`D-002`). If a hand test ever disagrees, the hand
  test wins.

## Verdict

*(filled in after the run)*
