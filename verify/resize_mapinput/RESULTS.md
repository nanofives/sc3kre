# RESULTS — map input past the native 800x600 (`SC3RESIZE_VIEWFIX`)

Run 2026-10-05. Pre-registration `PRE.md` (`c96ce0e`). Build `sc3resize.dll` 195,072 B. Single
1680x1050 display at 100%, `SC3RESIZE_CLUSTER=1`, spans on, edge scroll off. Client 1680x979
maximized. Both arms read their flag back from `FLAGS>` (`viewfix=1` / `viewfix=0`). No modal up in
either arm. Logs and JSON: `T/`, `C/`.

## Verdict: PASS. Every row as predicted in both arms, and the control reproduces the defect.

| # | observable | arm T (`VIEWFIX=1`) | arm C (`VIEWFIX=0`) |
|---|---|---|---|
| 1 | view local / hit at maximized | `[0 0 1680 979]` / `[0 0 1680 979]` | `[0 0 800 600]` / `[0 0 800 600]` |
| 2 | moves at (1300,300) and (480,880) reach the city view | 3 / 3 calls | **0 / 0** |
| 3 | control move at (400,300) | 3 | 3 |
| 4 | right-drag (1300,400) -> (1000,300) | panned (dx -271, peak 0.02 = moved past overlap; frames show a different district) | **did not move** (0, 0, peak 0.98) |
| 5 | city renders full-window after the write | yes (`T/pan_pair.png`) | yes |
| 6 | after restore to 800x600 | local = hit = `[0 0 800 600]` | n/a |

The `VIEW>` write fired twice in arm T, once per size change. The engine never reset the local rect
in between, so the 250 ms re-assert is a safety net, not a fight.

## What it means

The cause pre-registered from `verify/resize_edgescroll` is confirmed. The city view's LOCAL rect was
the load-bearing field, because the cascade derives the hit rect from it. With both rects at the
client size, mouse moves and drags anywhere on the map reach the view. This also settles the
2026-09-07 "view does not pan after a resize" item (`verify/offscreen/MAP_INPUT.md`, local): those
drags started at x=900, outside the old hit rect.

## Not covered

- Zoning or building placement past 800x600 was not driven. Those go through the same view hit test,
  but nothing here clicked a tool onto the map. Owner hand test.
- The right-drag pan distance was large (it left the measurement overlap). That is the pan speed
  tuning, not this fix.
