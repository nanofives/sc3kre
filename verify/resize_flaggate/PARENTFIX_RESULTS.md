# PARENTFIX_RESULTS.md — **P-PASS.** The router now reaches the relocated HUD.

Scored against `PARENTFIX_PRE.md` (committed `a28878c`, before the runs).
Raw: `route_armA.json`, `route_armB.json`, `parent.json`, logs `armA_fix.log` / `armB_ctrl.log`.
Both arms state-gated to the router branch (`cap28=0 foc30=0`).

## Verdict: P-PASS

### Arm B — control, `SC3RESIZE_NOPARENTFIX=1` (`PARENT> SKIPPED` in the log)

```
traversals: 4   -- all of them:
  self=0x5403f8  rect=[0, 0, 800, 600]  kids=15      <- the root, never recurses
bar [1248 1025 1847 1081] touched: 0
windows with right>800 seen at a gate: 0
```

The control reproduces the defect exactly: one level of traversal, no recursion, the HUD never
touched.

### Arm A — fix on

```
TRAVERSAL self=0xab0650   rect=[0, 0, 2048, 1081]      parent=0x0        kids=15
TRAVERSAL self=0x6455c0   rect=[0, 0, 2048, 1081]      parent=0xab0650   kids=5
TRAVERSAL self=0xe44ed30  rect=[1248, 1025, 1847, 1081] parent=0x6455c0  kids=5
```

and the gate results for the posted point (1547,1053):

| window | rect | `vt+0xe4` |
|---|---|---|
| container | `[0 0 2048 1081]` | **1** |
| **the bar** | **`[1248 1025 1847 1081]`** | **1** |
| bar's own children | `[1256 1031 1729 1045]`, `[1795 1036 1835 1075]`, … | 0 (correct — not on a button) |

**Three nested traversals where the control had one.** The container passes, recursion starts, the
bar passes, and the bar traverses its own five child widgets. The routing chain is repaired.

The fix log shows the write it made:

```
PARENT> win hop 0: 0x006455C0 [0 0 800 600] -> [0 0 2048 1081]
PARENT> win hop 1: 0x00AB0650 [0 0 800 600] -> [0 0 2048 1081]
PARENT> win hop 0: 0x006455C0 [0 0 2048 1081] already covers 2048x1081
```

Idempotent on repeat, as designed.

## ⛔ What this does NOT establish — stated in `PARENTFIX_PRE.md` before the run

**This measures ROUTING, not clickability.** Reaching the widget is necessary, not sufficient: the
widget's own handler still has to act on the event. **I am not entitled to say "the HUD is
clickable" and I am not saying it.** Only an owner hand-test on a real display can say that.

**The button test is INCONCLUSIVE, not passed.** A posted click at a real button centre
(1815,1055) took the **CAPTURE** branch — `cap28 = 0xf03b164`, non-null — so it was routed straight
to a captured window and never hit-tested. That capture was almost certainly left behind by my own
earlier posted clicks in the same process, i.e. **state contamination from the instrument**, not a
finding about the game. A clean button test needs a fresh process and `cap28 == 0` verified
immediately before posting.

**Side effects are unmeasured.** Widening a container's rect could affect painting, layout or
clipping in ways this trace cannot see. `[UNCERTAIN]` until someone looks at the screen.

## Why the fix is written the way it is

Direct write to `+0x14..0x20` rather than `vt+0xc8` SetRect: only those four fields gate routing
(`vt+0xe4` = `FUN_1001f8ef` compares exactly them), and SetRect on a *container* may relayout its
children and undo the cluster placement. Widen only, never shrink; refuse on non-positive extents;
stop at the root (`parent == NULL`), which is never geometry-tested because `FUN_10020818` calls
`root->vt[0x130]` directly.

Parent offset is byte-proven, not guessed: base `vt+0x2c` is `8b 41 3c c3` =
`mov eax,[ecx+0x3c]; ret` `[CONFIRMED @ GZWIND 0x1001e210]`, and the chain was then read directly
(`parent.json`): all 88 windows extending beyond the old box share the one container.

## Next

1. **Owner hand-test**: run with `SC3RESIZE_CLUSTER=1`, click HUD buttons, report whether they
   respond and whether anything looks wrong on screen.
2. Clean automated button test on a fresh process with `cap28 == 0` asserted before the post.
3. Check the standing board note *"navigation works only in the top-left 800x600"* — that is very
   likely this same stale rect and may now be fixed as a side effect.
