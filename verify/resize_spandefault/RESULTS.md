# RESULTS — full-width bar and full-height side panel ON by default

Run 2026-10-05. Pre-registration `PRE.md` (`b68bdca`). Single 1680x1050 display at 100%,
`SC3RESIZE_CLUSTER=1`, spans by default. Three builds: the flip alone (run 1), then two fixes found
by run 1 (runs 2 and 3, final build 195,072 B). Screenshots are local only.

## Run 1 — the flip alone: bar PASS, side panel FAIL

| # | check | result |
|---|---|---|
| 1 | `FLAGS>` `barspan=1 sidespan=1` with neither set | PASS |
| 2 | bar full width at 1600x700 | PASS: filler across the left, fields, controls and RCI at the right |
| 2 | side panel full height | FAIL, see below |
| 3 | buttons as native | FAIL (side panel) |
| 4 | Blt rate does not blow up with width | PASS: 5,832/s native, 2,767/s maximized, ~0.8 s/s inside Blt in both |
| 5 | churn | PASS: 20 cycles, 0 AV, RCIFIX active for the first time |

**Side panel defects, three of them, each root-caused:**

1. **At native 800x600 the buttons sat under the minimap, plus a ghost column at the top.** SIDESPAN
   stretched the panel to 600 (buttons pushed +158), then shrank it to 436, and
   `rz_side_children_bottom` returned early on `dy <= 0`, so the buttons never came back. Same bug
   class as the bar's `dx <= 0` early return (`db1fd42`).
2. **With a category open, a duplicate button group appeared and covered a slot.** The group overlay
   (item `+0xe8` raster at `(+0xf0, +0xf4)`) is the whole highlighted group. On 09-05 it was anchored at
   the clicked item's own y, so the group was drawn again starting at that item
   (`v2/panel_triptych.png`).
3. **Flyout click targets were 94 px above their icons.** The sub-tool windows (`SIMUI+0xa917c`) stayed
   at native y while the icons followed the category button. Causal test (`v2/hit_test.txt`): a click
   on the drawn tree icon resolved to the 4th sub-tool. A live poke moved one sub-button window by
   +94 and its icon did not move (`v2/poke_pair.png`). So these windows are click targets only, and
   the icons are drawn from the category item's anchor.

## Fixes (all in `rz_side_children_bottom`)

1. `dy` clamped to 0 instead of returning, so every cached item goes back to native + 0.
2. Overlay y = cached native + `dy`, not the item's y. Absolute, so it cannot drift.
3. Sub-tool buttons placed at cached native y + `dy`, absolute, re-cached if the game recreates or
   moves one. `SC3RESIZE_SUBMOVE` now defaults to follow SIDESPAN. The 09-05 "drift toward the bottom"
   came from the old incremental `e[1] + dy` with an `e[1] < dy` guard.
4. Invalidate and rebuild at `dy == 0` only when a restore changed something, so there is no new
   per-frame repaint at native.

## Run 3 — final build

| check | native 800x600 | resized (1680x979) | after 10 resize cycles, back to 800x600 |
|---|---|---|---|
| category buttons | 9, stock positions (y 3..521 step 36 as stock) | 9, docked above the minimap | identical to native |
| flyout counts | 6/8/7/6/7/6 | 6/8/7/6/7/6 | 6/8/7/6/7/6 |
| sub-button offsets from category | — | identical to native in all 6 | identical, landscape re-opened at native y 21..201 |
| click on drawn tree icon | — | resolves to sub-tool #1 (`v3/hit_test.txt`) | — |
| visual | stock, no ghost | every icon inside its click target (`v3/landscape_hit.png`) | stock, no ghost |
| faults | — | 0 over 10 cycles | — |

Row 6 (ARTGUARD case, tool click then resize): the panel painted throughout, since tool categories
were clicked before every resize in the churn.

## Not covered

- The bar at maximized size was not re-checked visually in run 3, because the always-on-top VM
  window covers that part of the screen. It was checked at 1600x700 in run 1, and the bar code did not
  change after run 1.
- Owner hand test on this build.
