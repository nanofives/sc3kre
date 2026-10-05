# PRE — side panel missing when maximized: the child double-translate

Pre-registered 2026-09-07, before the build. Owner-reported symptom: with `SC3RESIZE_CLUSTER=1`,
maximizing leaves the side tool panel absent from the frame.

## Root cause claimed

`+0x90` (the paint rect) is **parent-relative for a child window** and absolute for a root, while
`+0x14..0x20` (the window's own rect) is always absolute. `rz_cluster` cached only `+0x90` as the
native rect and translated **every** recorded painter window by the global `(dx,dy)`. For a child,
`vt+0xc8` SetRect then adds the parent's *new* origin on top — so the delta is applied twice and the
child leaves the client area, taking all visible side-panel content with it. The container itself
moves correctly, which is why the log looked healthy.

## Evidence it rests on (already measured, `verify/resize_clicklab/live_resizeio/run.log`)

At native (`:388-393`), origin delta between paint and window:

| item | paint | window | delta | reads as |
|---|---|---|---|---|
| `[1]` `0x0D3680B8` | `[704 0 800 442]` | `[704 0 800 442]` | `(0,0)` | root |
| `[4]` `0x0E2D6F80` | `[0 0 36 442]` | `[704 0 740 442]` | `(704,0)` | child of the side panel `[704 0 …]` |
| `[3]` `0x0D42D110` | `[138 72 147 87]` | `[778 508 787 523]` | `(640,436)` | child of the minimap `[640 436 800 600]` |

At maximize (`:284-289`), `dx,dy = (1120,409)`, side panel moved to `[1824 409 1920 851]`:

* `[4]` fed SetRect `[1120 409 1156 851]` → observed window `[2944 818 2980 1260]`.
  `1824+1120 = 2944` ✓ `409+409 = 818` ✓
* `[3]` fed `[1258 481 …]` → observed `[3018 1326 …]`. Minimap new origin `[1760 845]`:
  `1760+1258 = 3018` ✓ `845+481 = 1326` ✓

Both match to the pixel, in both directions. The double-translate is arithmetic, not a hypothesis
about intent.

## The change

1. Cache `natwin[4]` (`+0x14..0x20`) alongside `nat[4]`, once, at native capture.
2. `child = (natwin[0] != nat[0] || natwin[1] != nat[1])` — origins only; sizes may legitimately
   differ without implying parentage.
3. Cluster and anchor loops **skip children entirely** — no SetRect, no `+0x90` write, no hit move.
4. `SC3RESIZE_KIDFIX=0` restores the old behaviour as the A/B control arm; `kidfix` is echoed in
   the `FLAGS>` line (a flag absent from that line has silently failed to arm three times here).
5. The per-window log is uncapped (was the first 6 of 11 — the buttons were in the hidden tail).

## Predictions — what PASS and FAIL look like

**PASS, all four required:**

1. `WINCAP>` classifies `0x0E2D6F80`, `0x0F046008` and `0x0D42D110` as `CHILD`, and
   `0x0D3680B8` / `0x0D3681F0` / `0x0EE65158` as `root`.
2. After maximize, **no `<<< PAINT/WINDOW DIVERGE` line** remains, and every logged window rect
   lies inside the live client (`0 ≤ x < clientW`, `0 ≤ y < clientH`).
3. `CLUSTER> translated N painter windows … left K child window(s) to their parents` with `K ≥ 3`.
4. **The side panel with its tool buttons is visible in the maximized screenshot**, docked to the
   right edge — the owner-facing observable. Judged on the PNG, not the log.

**FAIL signatures, pre-committed so they cannot be reinterpreted afterwards:**

* Panel still absent while the log is clean → the child rects were never the reason the panel does
  not paint; the panel's own art/surface is the next suspect, not its geometry.
* Panel appears but buttons are stacked at the panel's top-left corner → the children's
  parent-relative rects are *not* preserved across the parent's move, i.e. skipping is too passive
  and they need an explicit relative re-write.
* Some *root* window stops moving (e.g. the RCI indicator returns to native `[599 520 640 608]`)
  → the origin comparison misclassified a root as a child. Re-run with `SC3RESIZE_KIDFIX=0` to
  confirm the classifier, not the skip, is at fault.
* A new fault in the `VEH` log at the cluster step → the `+0x14` read is out of bounds for some
  class; `IsBadReadPtr(w, 0xa0)` should already cover `0x20`, so this would falsify that assumption.

## Control

Same build, same city (`Cities\Europolis.sc3`), same recipe (`SC3RESIZE_CLUSTER=1`), run twice:
`SC3RESIZE_KIDFIX=1` (treatment) and `SC3RESIZE_KIDFIX=0` (control, must reproduce the off-screen
`2944`/`3018` numbers). Screenshots via `re/tools/sc3io_cli.py grab`, which refuses to save an
untrustworthy frame — so a "clean" shot cannot be an occluded desktop.
