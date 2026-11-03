# ghosttiles RESULTS (2026-11-03): ghost highlight cells while placing. FIXED

Owner report on sc3mods-2026-11-03b: "when placing a ploppable sometimes i see traces of the indicator on the map, like
ghost colored tiles" (shot `.happy-uploads\image-1793725647961.png`: red patches and light-blue squares away from the
cursor).

Build: `dev\ghosttiles\inst\sc3resize.dll` (main a895a3f + this stream), only sc3resize rebuilt. Berlin, 800x600
windowed, posted input only (hover moves, posted VK_SHIFT, Esc, menu commands), frame dumps. Pictures:
`verify\ghosttiles\owner_shots\`.

## Cause

The highlighter push vt+0x58 (SIMSPR `0x1004b779`) repaints the rect it is given, then **sets the dirty rect +0x50 to
that rect** (the copy at `LAB_1004b931`). The tools' clear `0x1004b653` wipes only the cells inside +0x50. It runs in the
preview fill `0x1004af93` on every mouse move and in the cancel `0x1004ae23` (Esc, tool change). So a push with a rect
that does not hold every live cell strands the rest on the map until the game restarts.

Two pushes did that:
1. **STATIONWARN's marker** (`sw_paint`, every 700 ms blink) pushed the flagged station's rect. +0x50 became that one
   station, so the tool's last footprint and halo were never cleared. It hits every tool, Shift or not, in any city with
   a flagged station (Berlin has 2). This is the owner's case.
2. **PLACEHINTS' halo push** (`ph_push`) passed only the halo's bounding box, which can leave the stock footprint
   outside +0x50 (same ghost, rarer).

## Fix (block GHOSTFIX, `sc3resize_stationwarn.c` `hl_push`, off switch `SC3RESIZE_GHOSTFIX=0`)

- STATIONWARN saves +0x50 before its push and puts it back after. The marker is drawn, blinks and is restored exactly as
  before. It only stops changing the tools' rect.
- PLACEHINTS pushes the union of its rect and +0x50 (when +0x25 says +0x50 holds live cells), so +0x50 never shrinks and
  the next stock clear covers every cell the hint set: move, Shift up, Esc, tool change, dialog open.

## Checks

| case | result | picture |
|---|---|---|
| before (main build): Big Park hovered at 6 spots 1.6 s apart, no Shift | 5 old red footprints left on the map | `A1_before_park_hovers_no_shift.png` |
| after: same 6 hovers | only the live footprint drawn | `A2_after_park_hovers_no_shift.png` |
| after with `SC3RESIZE_GHOSTFIX=0` (control) | the 5 ghosts again, same as A1. Log `GHOSTFIX> off` | `A3_ghostfix0_control.png` |
| Shift held, 5 moves (halo on) | one halo, the current one | `B1_after_shift_held_moves.png` |
| Shift up | halo gone, footprint only | `B2_after_shift_up.png` |
| Esc after a Shift hover | nothing left | `B3_after_esc.png` |
| Shift hover with the park, then the Road tool | only the road tool's own hover cell | `B4_after_tool_change_to_road.png` |
| flagged subway station (28,83), 2 frames 0.7 s apart | marker red in one, off in the other: blink unchanged | `C1_stationwarn_marker_blink_on_off.png` |

## Not covered / needs owner check

- Real mouse and the physical Shift key (posted messages only).
- Station plop preview (`ph_station`) and airport drag not shot. Both push through the same `ph_push`, so they get the
  same union.
- Dialog open while placing not tried. It goes through the same stock clear as Esc.
- Ghosts already on the map in a running game stay until the game restarts. They are not saved in the city file.
