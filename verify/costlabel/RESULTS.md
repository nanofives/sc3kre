# costlabel: cost label offset during a highway drag (owner img14, 2026-10-22)

Verdict: sc3resize HUDSCALE bug, fixed in `re/harness/src/sc3resize.c` (branch `child/costlabel`). Not stock, not TIPCURSOR, not sc3overscroll.

Cause: HUDSCALE enlarged every small floating window inside the native HUD box about the bottom-right corner. The city cost
label (vt exe+0xd3bcc) is one of them, so a drag that ended in the lower right of the city drew the label s times larger at
`C + s * (p - C)`. Owner log `verify/handtest_2026-10-22a/resize.log` line 510: `[3678 1522 3742 1538] -> [3304 456 3516 509]`,
374 px left and 1066 px up at 3.307x.

Fix: a floating window is enlarged only when (1) the game's cursor was on the enlarged HUD (last queued mouse message
mapped) and (2) its rect touches a native HUD window (8 px margin). Latched per window and rect.
`SC3RESIZE_HUDSCALE_FLOATALL=1` = old rule.

Class check asked by the orchestrator: not possible. `exe+0xd3bcc` is also the window behind every HUD tooltip (Emergencia,
the top side-panel button, Pregunta, Pausa, Ampliar zoom: all logged `000D3BCC`, the same window moved). Test (2) is the
guard against a misread cursor instead. Measured: with the real mouse parked on the panel of the maximized window, the
cursor flag alone read "HUD" for the label at the start of a city drag (`[2428 1178 2448 1194]`); (2) refuses it.

Test: instance `Simcity_stock_hwlight\re\harness\inst_costlabel`, all mods from the worktree, lab.sc3, client 1584x851 on a
dpi 240 monitor, HUD scale fit (1.418x, native HUD box [468 251 1584 851]). Highway tool drags by posted input, held, grab.

| shot (`owner_shots/`) | case | result |
|---|---|---|
| `before_A_label_in_hud_box.png` | old build, drag end (1200,600) inside the box | "$600" enlarged, drawn up-left of the drag end (log `[1222 678 1254 694] -> [1071 606 1116 628]`) |
| `before_B_label_topleft_control.png` | old build, drag end top-left | native label at the cursor (`not scaled (floating)`) |
| `after_A_label_in_hud_box.png` | fixed, drag inside the box | "$2,700" native, below-right of the drag end (`COSTLABEL> ... cursor in the city -> native`) |
| `after_B_label_topleft_control.png` | fixed, top-left | unchanged |
| `after_C_drag_ends_outside_window.png` | fixed, last move at (1700,950), outside the client | "$7,950" clamped into the client corner by the game, native |
| `after_D_hud_tooltip_still_enlarged.png` | fixed, hover on the Emergencia button | tooltip still enlarged beside the enlarged button |

Second round (cursor + HUD-touch rule):

| shot | case | result |
|---|---|---|
| `after_max_A_label_in_hud_box_3307.png` | client 3760x1984 at 3.307x (owner's factor), drag end (3000,1550) in the box | "$2,850" native just below-right of the drag end; every label rect logged `cursor in the city, clear of a HUD window -> native` |
| `after_max_B_topleft_3307.png` | same, top-left | native at the cursor |
| `after_max_hud_tooltips_3307.png` | hover on Emergencia, Pregunta, Pausa, Ampliar zoom | all four enlarged beside their enlarged buttons |
| `after_off_hudscale_off_control.png` | `SC3RESIZE_HUDSCALE=0`, 1584x851, same drag as after_A | label at the same spot as after_A (1237,685), no COSTLABEL lines: no change with HUDSCALE off |

3760 instead of 3840 wide: maximized, the real mouse (parked at screen x 3838 on the side panel) sent moves between the
posted ones and the label flipped to it. Narrowing the client by 80 px put that cursor outside without moving it. The
factor is height-bound (1984 / 600 = 3.307), so it is the owner's. A maximized run showed the same decisions for the posted
points (log), but its frames caught the real cursor.

Not tested by hand: with the real mouse, both tests read the same cursor, so they agree. Save/reload not relevant (no game state touched).
