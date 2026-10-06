# RESULTS — panel buttons at native vs resized, and edge scrolling OFF

Run 2026-10-05. Pre-registration `PRE.md` (`17aa1bb`). Final build `sc3resize.dll` 194,048 B
(`5803fa0` plus the view-identity fix committed with this file). `SC3RESIZE_CLUSTER=1`, all other
flags default. Screenshots are local only (game imagery): `native/`, `max/`, `compare/`.

## Deviations, and why the first pass was thrown away

1. **First pass invalid.** The first version of `panel_shots.py` matched sub-tool buttons as well as
   category buttons. Clicking one opened the modal "Escoge estructura hidrológica", and the game then
   discarded every later click. Fixed (categories = `SIMUI+0xa8f60` only), dialog closed, both states
   rerun from scratch.
2. **Resized state is 1600x700, not maximized.** An always-on-top VM control window covers the bottom
   of the screen, over the game's bar when maximized. A 1600x700 client at the top of the screen
   avoids it and runs the same resize path. The desktop was one 1680x1050 display at 100% by then.
3. Only the first 6 categories were clicked (landscape, zoning, transport, utilities, civic,
   emergency). Advisors, query and options open modal dialogs. They are scored from the full frames.

## Scored rows

| # | check | native 800x600 | resized 1600x700 | verdict |
|---|---|---|---|---|
| 1 | category buttons | 9 | 9 | PASS |
| 2 | flyout buttons per category | 6, 8, 7, 6, 7, 6 | 6, 8, 7, 6, 7, 6 | PASS |
| 2b | each flyout button's offset from its category button | — | identical in all 6 | PASS |
| 3 | flyout buttons outside the client | 0 | 0 | PASS |
| 4 | icons drawn, on their own hit rects, same layout (by eye, `compare/cat00..05.png`) | — | yes, all 6 | PASS |
| 5 | bar + minimap buttons (by eye, `compare/bottom_*.png`) | full set | full set | PASS, see the gap below |
| 6 | edge scrolling off | `EDGE> edge scrolling OFF` on every rebuild, live inner rect `[-32767 -32767 32767 32767]` | same | PASS |

Row 4 note: the flyout window list is not a reliable source on its own. The game draws flyout icons
from its own anchor (09-05 note in `sc3resize.c`). The screenshots are the evidence, and they show
each icon on its green hit-rect outline at both sizes.

## ⛔ The porting gap: in the DEFAULT launch the HUD moves, it does not extend

At 1600x700 the side panel is still **96x442**, moved to `[1504 100 1600 542]` and docked on the
minimap. Above it (y 0..100) is city. The bottom bar is still **600 wide**, moved right beside the
minimap (x ~800..1400). City shows to its left. Every button is there and works. But the panel does
not span the height and the bar does not span the width.

That is how the defaults are wired: cluster mode translates the native-size HUD.
`SC3RESIZE_SIDESPAN` (full-height panel) and `SC3RESIZE_BARSPAN` (full-width bar) both default to 0.
`RESIZABLE_WINDOW.md` §6 said "bar spans the full width, side panel spans the full height" without
that qualifier. Corrected in this commit. This is very likely the "did not port fully" the owner
remembers.

## Also found this session

- **The view search could pick the wrong object.** `rz_find_view` matched on `vt+0xe4` alone. With
  the water-structure picker open it returned an object whose outer vtable was `0x94003A00`, likely the
  dialog's building preview. The band rebuild was refused, but the bounds and hit-rect writes had
  already landed on that object. Fixed: the search now also requires the city view outer vtable
  `SIMSPR+0x67894` at `cw-4`. Verified over 4 resize cycles: found every time, 0 refusals.
- **Native-size frames were white earlier in the session** on the multi-monitor layout, at every
  restored size, while maximized captured fine. On the later single-display layout, native captured
  normally. Cause not established. It matters only for capture.
