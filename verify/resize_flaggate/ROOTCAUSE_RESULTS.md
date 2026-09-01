# ⭐⭐⭐ ROOT CAUSE — the HUD's PARENT container was never resized

**2026-09-01. `route3.json`, state-gated to the router branch (`cap28=0x0 foc30=0x0`).**

## The finding

The router's traversal starts at the root (`self=0x53fd38`, rect `[0 0 800 600]`, `parent=0x0`) and
its child list is **exactly 15 windows**:

| count | rect | flags |
|---:|---|---|
| 1 | `[774 574 800 600]` | `0x4903` |
| 12 | `[0 0 96 442]` | `0x14902` |
| **1** | **`[0 0 800 600]`** | `0x4103` |
| 1 | `[0 0 0 0]` | `0x4902` |

**None of them is a relocated HUD window.** The bar `[1248 1025 1847 1081]`, the side panel
`[1952 481 2048 923]` and the minimap `[1888 917 2048 1081]` are **not children of the root the
router walks.** Only one traversal occurs, and it never recurses.

## The mechanism, end to end

`FUN_1001ec22` recurses into a child **only if that child passes `vt+0xe4`, a point-in-its-own-rect
test** `[CONFIRMED @ GZWIND 0x1001ec22]`:

```c
if ((*child->vt[0x100])() && (*child->vt[0xe4])(ev[1], ev[2]))
    return (*child->vt[0x130])(ev);        /* recurse only on a geometric hit */
```

The HUD windows are children of the container at **`[0 0 800 600]`** — still the *pre-resize* size.
A click at (1547,1053) is **outside** that rect, so the container fails `vt+0xe4`, the recursion
never starts, and **its children can never be reached no matter how correct their own geometry is.**

The mod moved the HUD **leaves** to the corner and never resized their **parent**.

## Why this reconciles every earlier result

This is what makes it a root cause rather than another candidate — it explains the contradiction
that has run through the whole investigation:

- **`FUN_1001e748` (the `vt+0x8c` walk) found the bar correctly** (`HITTEST_RESULTS.md`,
  `gate.json`). That walk gates children **only on `vt+0xf0(1)`** and recurses regardless of the
  parent's geometry `[CONFIRMED @ GZWIND 0x1001e748]`. **No parent rect test** — so it reaches the
  HUD.
- **`FUN_1001ec22` (the router) cannot**, because it *does* test the parent's rect first.

Two functions, same child tree, different gating. The HUD is reachable through one and unreachable
through the other, and normal clicks take the one that fails.

- It also explains `ROUTE2_RESULTS.md`'s anomaly exactly. In that run's **viewport** batch the HUD
  windows *were* gated (`vt+0x100 = 1`) — because (400,300) **is inside** `[0 0 800 600]`, so the
  container passed, the recursion ran, and its HUD children got tested. For the bar and minimap
  points, outside that rect, they were touched **0 times**. Same run, same process, opposite
  outcomes, one rule. That earlier data now serves as an independent control for this conclusion.

## Every previously excluded candidate stays excluded

`vt+0xf0(0x80000)`, the shown bit, the `+0x80..0x8c` write (never executed), walk reachability,
coordinate delivery, and gate 1 `vt+0x100`. All were correct findings about the wrong link. The
defect was never in a window's own state — it is in **an ancestor's rect**.

## The fix (designed, NOT built, NOT tested)

Resize the HUD container to the client size, using the method already proven on the bar and side
panel: **`vt+0xc8` SetRect**, live-vtable dispatch, expect-or-refuse.

- Identify the container as the child of the root whose rect equals the pre-resize client size and
  whose subtree contains the HUD windows.
- Set it to `[0 0 clientW clientH]` on resize, before/alongside the existing cluster moves.

**`[UNCERTAIN]`, and it is one cheap read to close:** the parent link has not been read *directly*.
The conclusion rests on (a) the root's 15 children containing no HUD window, and (b) HUD children
being gated exactly when the point falls inside `[0 0 800 600]` and never when it falls outside.
That is two independent observations agreeing, but **the next run should read `bar+0x3c` and confirm
it points at the `[0 0 800 600]` container** — parent is `this+0x3c`, byte-proven
(`vt+0x2c` = `mov eax,[ecx+0x3c]; ret`) `[CONFIRMED @ GZWIND 0x1001e210]`. One line, and it turns
this from inference-with-two-witnesses into a direct read.

**Do not skip that check.** The standing board rule is that a confirmed code path is not a confirmed
cause, and this session has already refuted three confident conclusions that were each built on
something not directly measured.

## Also worth carrying

The container at `[0 0 800 600]` being stale is very likely the **same defect** behind the
long-standing board note that *"navigation works only in the top-left 800x600"*. That symptom and
this one are the same rect.
