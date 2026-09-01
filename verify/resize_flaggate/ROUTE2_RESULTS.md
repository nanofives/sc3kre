# ROUTE2_RESULTS.md — gate 1 is EXONERATED; the traversal itself is the anomaly

Scored against `ROUTE_PRE.md`. Tool: `re/tools/frida_route2.py`. Raw: `route2.json`.

## Both v1 defects are fixed, and the fixes worked

- **State gate held.** `state()` was polled before posting and reported `foc: 0x0`. All nine
  dispatches logged `branch=ROUTER vt+0x130` with `cap28=0x0 foc30=0x0` — **the run measured the
  branch normal play actually takes**, not the modal branch that confounded the earlier runs.
- **The trace opened on the branch under test.** Opening at `FUN_10020818` entry produced
  96 / 170 / 112 `vt+0x100` calls and 18 / 40 / 21 `vt+0xe4` calls across the three points. v1's
  meaningless zero is gone; this instrument is demonstrably able to log non-zero **on this branch**,
  which is the standard `ROUTE_RESULTS.md` set after being burned twice.

151 windows walked, hooks installed on 4 `vt+0x130`, 4 `vt+0x100`, 7 `vt+0xe4` live targets.

## ⭐ Gate 1 is NOT the blocker — G1-REJECT is falsified

In the `viewport` batch the relocated HUD windows **are** visited and **pass** gate 1:

| window | rect | `vt+0x100` | `vt+0xe4` |
|---|---|---|---|
| bar | `[1248 1025 1847 1081]` | **1 (pass)** | 0 |
| side panel | `[1952 481 2048 923]` | **1 (pass)** | 0 |
| minimap | `[1888 917 2048 1081]` | **1 (pass)** | 0 |

`vt+0xe4` returning 0 there is **correct** — those events were at points outside those rects. What
matters is that `vt+0x100` returns **1**: the relocated windows are enabled, they are on the routed
subtree, and they do receive geometry tests. **`G1-REJECT` is falsified and `NOT-VISITED` is
falsified as a general claim.**

Gate 1 *does* reject 13 other children per traversal, all with rect `[0 0 96 442]` — unrelocated
side-panel children in parent-relative coordinates. They are skipped before geometry.

## ⛔ The anomaly: the click that lands ON the bar never tests the bar

For `bar_bg` at (1547,1053) and `mini` at (1968,999):

```
windows with right > 800 seen at ANY gate: 0
bar   [1248 1025 1847 1081] : touched by gates 0 times
side  [1952  481 2048  923] : touched by gates 0 times
mini  [1888  917 2048 1081] : touched by gates 0 times
```

Only **three** windows are geometry-tested per traversal, all carrying stale 800x600-era rects
(`[774 574 800 600]` twice, `[0 0 800 600]`), and all correctly return 0 for the point.

**So on the traversal that handles a click inside the relocated bar, the bar is never tested — while
on other traversals in the same run it is tested and passes gate 1.** The windows are reachable; the
traversal that should reach them does not.

## `[UNCERTAIN]` — the mechanism, stated plainly

**I cannot explain the inconsistency from this run and will not invent a reason.** Per traversal the
counts are stable (~16 `vt+0x100`, 3 `vt+0xe4`), so the router walks a **~16-child list of which
only 3 pass gate 1** — and in the `bar_bg`/`mini` traversals the HUD windows are not in the tested
set at all, while in the `viewport` batch windows with `right > 800` are gated 16 times.

Two candidate explanations, **neither tested**:

1. The HUD windows are children of a **different parent**, reached only when recursion descends into
   that parent — and for the bar click no earlier child passes both gates, so the recursion that
   would reach them never starts.
2. The `viewport` batch's HUD gate calls came from **nested `vt+0x130` recursion** on a different
   `this`, i.e. a different subtree than the one the bar click traverses.

Distinguishing them needs the **parent chain and the `this` of each traversal** logged, which this
run did not capture.

## Cumulative position

| candidate | status |
|---|---|
| `vt+0xf0(0x80000)` | refuted (static) |
| `vt+0xf0(1)` shown bit | excluded |
| `+0x80..0x8c` write | never executes |
| walk `vt+0x8c` reachability | excluded — returns the bar correctly |
| coordinates reaching the dispatcher | correct and unclamped |
| **`vt+0x100` gate 1 on HUD windows** | **excluded — returns 1** |
| **which subtree the router traverses for a HUD-area click** | **OPEN, and now the whole question** |

## Next run

Log, per `vt+0x130` invocation: the `this` pointer, its rect, its **parent**, and the full ordered
child list with each child's gate results. That turns "the traversal did not reach them" into
"the traversal went *here* instead", which is the last unmeasured link.

## Method

Three runs, three instrument iterations, each fixing a gap the previous one exposed: hard-coded slot
addresses (`HITTEST_RESULTS.md`), a trace window that could not open on the branch under test
(`ROUTE_RESULTS.md`), and now missing traversal identity. Each iteration was cheap and each produced
a real exclusion. The rule that has held all session: **a zero is evidence only after the instrument
has produced a non-zero on that exact path** — applied here, it converted a would-be `NOT-VISITED`
verdict into a much more precise, and much more useful, anomaly.
