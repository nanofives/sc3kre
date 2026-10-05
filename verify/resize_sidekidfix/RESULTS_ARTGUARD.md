# RESULTS — the side panel does not paint: root cause found and fixed

2026-09-07, continuing from `RESULTS.md` (which fixed the child double-translate and **excluded** it
as the cause of this symptom). Build `sc3resize.dll` 191,488 B. `Cities\Europolis.sc3`,
`SC3RESIZE_CLUSTER=1`.

## Root cause

`rz_fix_hud_parents` (`sc3resize.c:1275`) walks up from every relocated window and widens each
ancestor to the live client size (`if (r[3] < ch) r[3] = ch;`). That is free for a layout
**container** and destructive for a window that **blits a fixed-size surface**: the blit
destination stops matching the source and the window paints nothing.

The side panel blits a **96x442** surface (`this+0x58`, the field `FUN_1006d2d0` blits
`[CONFIRMED @ SIMUI 0x1006d2d0]`). The cluster step places it correctly at `[1952 481 2048 923]`
— exactly 96x442. The parent walk then stretches it to `[1952 481 2048 1081]` = 96x**600**.

**Why a tool-button click was required first:** the panel only becomes an *ancestor* once its page
children exist, and those are created by clicking a tool button. Before that the panel is never on
this walk — which is precisely why maximizing on a fresh load looked fine and made the bug look
like a geometry problem.

## Evidence chain

**1. The mod logged its own defect.** `probe/run.log:83`:

```
PARENT> win hop 0: 0x0D34F698 ABS [1952 481 2048 923] LOCAL [1952 481 2048 923] -> 2048x1081
```

Correct rect in, client-height rect out.

**2. Causality proven by poking the live object.** In the broken maximized state, with nothing else
changed, `+0x24` (which I read as a relative rect at the time; the decompilation below shows it is
the blit SOURCE rect) was `[0, 0, 96, 600]` and `+0x14`/`+0x80`/`+0x90` were
`[1952, 481, 2048, 1081]`. Writing `+0x24 = [0,0,96,442]` and the other three to
`[1952,481,2048,923]` made the panel, its background art, its ten buttons **and** the open flyout
sub-tool column all reappear on the next repaint. `poke_fix_panel.png`.

**3. State diff isolates the field.** `side_paint_probe.py --diff s1 s2` (after-clicks →
after-maximize) is 34 changes, and the only non-positional one is `panel+0x30: 442 -> 600`. Every
child moved consistently and correctly (buttons `[1985 484 2041 516]` … `[1985 844 2041 876]`, all
inside a 442-tall band from y=481). So the children were never the problem.

**4. The discriminator is measured, not assumed.** Native subtree dump (`probe/s0.json`): the panel
had `surf=0xf6aaca8`; both layout ancestors `0x00640BA8` and `0x005A6040` had `surf=NULL`, and
`paint=[0,0,0,0]`. The panel is the only object in the tree that blits.

**5. Matched A/B, same build, one flag, identical click+maximize sequence:**

| arm | `PARENT>` on the panel | panel region | verdict |
|---|---|---|---|
| `SC3RESIZE_ARTGUARD=1` (default) | `SKIPPED - blits art (surface 0x0F4D93E8, the SIDE PANEL) … rect left [1952 481 2048 923]` | panel, art, 10 buttons, flyout | **present** (`ag_panel.png`) |
| `SC3RESIZE_ARTGUARD=0` (control) | `ABS [1952 481 2048 923] … -> 2048x1081` | pure city | **absent** (`agc_panel.png`) |

**6. No regression in what the parent walk exists for.** The walk was added so the router's
per-child `vt+0xe4` gate can pass (clickability). With the guard on, clicking a tool button at
maximized size still works: the panel region changes, bbox `(40,183)-(111,224)`, the flyout opens.
`ag_click_panel.png`. The guard **continues** up the chain rather than returning, so the containers
above are still widened.

## The change

`SC3RESIZE_ARTGUARD` (default **1**, verified by launching with it unset and reading
`artguard=1` back from the `FLAGS>` line). In `rz_fix_hud_parents`, an ancestor is skipped for the
widen — but still traversed — when it has a non-NULL surface at `+0x58`, or is one of the mod's own
managed HUD windows (`g_side_top`, `g_hud_top`, `g_mini`, named as belt-and-braces). `=0` restores
the old behaviour as the control arm.

This is consistent with a warning already in the source at `g_hud_dy`: *"HUD art is TOP-ANCHORED in
its rect, so a rect taller than the art paints the surplus black — do not implement this by growing
rects."* Same class of defect, different writer. Here the surplus paints nothing rather than black.

## Tooling added

`re/tools/side_paint_probe.py` — dumps the panel subtree (`+0x14` abs, `+0x80` local, `+0x90`
paint, `+0x58` surface, and every word `+0x24..+0x80`) to JSON and diffs two snapshots. The
`+0x30: 442 -> 600` line came straight out of it; that is what turned "the panel is missing" into a
one-field question.

## Decompilation corroboration (SIMUI, obtained after the fix; it agrees and goes further)

The empirical result above was reached from live measurement. The decompilation independently
confirms the mechanism and **closes the `+0x24` question**:

* **`+0x24..0x30` is the blit SOURCE rect, not a relative rect**, and `vt+0x164` =
  `FUN_1006d438` rebuilds it from the local rect as `(0, 0, w, h)`
  `[CONFIRMED @ SIMUI 0x1006d438]`. So the observed `+0x24 = [0,0,96,600]` was the source rect
  regenerated from the widened local rect — a request to blit a 96x**600** region out of a
  96x**442** surface. That is the whole failure, and it answers what wrote the 600.
  `+0x90` is the DEST rect; the blit is `dev->vt+0x118(surface, this+0x24, this+0x90, 0)`
  `[CONFIRMED @ SIMUI 0x1006d2d0]`.
* **Widening a surface-owning window is destructive by construction**, not just in this instance.
  `vt+0x170` = `FUN_1006d56c` keeps an existing surface **only on an exact match** to the local
  rect: `if (rect_w == surface->Width && rect_h == surface->Height) return 1;` else it frees the
  bits. And if the local rect is empty or inverted it releases the surface and sets `+0x58 = 0`,
  after which the paint routine's null check skips the blit **silently**
  `[CONFIRMED @ SIMUI 0x1006d56c]`. Base `SetRect` `FUN_1006db90` re-creates on any size change
  when flag `0x10000` is set `[CONFIRMED @ SIMUI 0x1006db90]`. So `ARTGUARD` is the correct shape
  of fix, not a workaround.
* **The paint gates are `+0xA0 & 1` (visible; hard stop, children not walked), the `+0x60` dirty
  byte, and `+0x58` null.** There is **no empty-rect test and no clip inside the paint routine**
  `[CONFIRMED @ SIMUI 0x1006d2d0]`.
* **The panel's own `SetRect` override discards the requested width.** `vt+0xc8` =
  `FUN_1004e20b` overwrites the width with the width of the raster at `+0xC0` and clamps the
  height *up* to the sum of three decoration rasters' heights `[CONFIRMED @ SIMUI 0x1004e20b]`.
  Consequence for the still-untested `SC3RESIZE_SIDESPAN`: the panel **cannot** be widened through
  SetRect while `+0xC0` holds the shipped 96-wide raster — the surface will keep being re-created
  at the raster's width. Same asymmetry `RESIZABLE_WINDOW.md` records for the horizontal case.

## ⚠️ A comment in the mod is wrong, and it is load-bearing

`sc3resize.c` says the parent walk exists "so the router's per-child `vt+0xe4` gate can pass **and
the recursion that reaches the HUD can start**". The second clause is false: `vt+0xe4` =
`FUN_1006de62` is a **hit-test** (`bool HitTest(int x, int y)` against the object's own
`+0x14..0x20`, with a per-pixel transparency refinement when flag `0x80000` is set)
`[CONFIRMED @ SIMUI 0x1006de62]`, and it is called only from the input walks `FUN_1006ccda` and
`FUN_1006d1af` `[CONFIRMED @ SIMUI 0x1006ccda, 0x1006d1af]`. The paint walk in `FUN_1006d2d0`
iterates `this+0x34` and calls every child's `vt+0x148` **unconditionally** — pre-counted
countdown, return value discarded, no gate, no early exit `[CONFIRMED @ SIMUI 0x1006d2d0]`.

**So a window outside its parent's rect still PAINTS but receives no MOUSE INPUT.** The parent
widen is an input fix only. Corrected in the source comment.

## Still open
* **A root window created while already maximized gets a resized-state rect cached as its
  "native".** Seen in `final/run.log`: `WINCAP> [7..11] … parent origin delta 1952,481`. Harmless
  for children (their relative rect is size-invariant, which is why those lines are correct) but a
  ROOT captured post-resize would be translated a second time on the next resize. Not yet observed
  to bite; no fix attempted.
* **`sc3io`'s DPI factor was wrong in one state.** `GetDpiForWindow` returned 96 (1.0x) while the
  game's own client was 800x600 against a physical 1000x750 — a true 1.25x. Clicks still landed, so
  it did not invalidate anything here, but the reported `scale` is not trustworthy for coordinate
  conversion in that state. Derive the factor from the game's own client rect instead.
