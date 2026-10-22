# hwlight: ramp / interchange wall shading (owner img11, 2026-10-21)

Owner report on the LAN build of main a89ecef: "lighting on the ramp is incorrect on the darker side of the
highway" (`MAIN\verify\ownerbugs_1021\owner_shots\img11_ramp_wall_light.png`). Branch child/hwlight from a89ecef.

## Cause

1. Stock wall shading follows the wall's WORLD axis, not the screen. Measured on the stock frames (`hwpaint.py lit`,
   zoom 3, mid-wall grey): an outer wall toward +-x (piece 73) reads 134..136 in every view it is visible in, toward
   +-z (15051) 78. Inner walls 156..158 / 80..83. That is why stock has one id per axis.
2. A piece's frame is shared by (state + view). Art painted at state 0 shows its x-facing walls light; written at
   state 1 or 3 those walls face z and keep the light shade. No single art set fits both parities: the same frame
   is shown for state 0 view 1 and state 1 view 0, which need opposite shades.
3. The highway blocks write one painted set at all four states:

| package | pieces written at odd states | where |
|---|---|---|
| highway_avenue (hwave) | 21600..21609, 21850, 21851 (all 12) | `sc3netmod_hwave.c`: turn k = 0..3 (img11) |
| hwt_trumpet | all 57 | `sc3netmod_hwt.c`: state = the T's turn r |
| hwx_cloverleaf | ramps 21120..21136 (17) | table lines: state = quadrant |
| highway_diagonal_cloverleaf | the 68 ramp-only classes | `hwdx_want`: one id for both crossing parities |
| highway_dd_cloverleaf | 30 land ramps | tables: states 0..3 |

The X core, junctions, capped joins and hwdx's flavoured classes are only written at 0 / 2 (already right).

## Fix

LIT TWINS. Each piece above gets a twin id: same base, lanes, turn matrix and hwrc class, art painted from the scene
turned one state (`hwpaint.turn_scene` / `paint_twin`, frames relabelled r -> r + 1; capped pieces compose the stock
cap turned with it). sc3netmod: table line `hwyl <piece> <twin>`; `rb_read` / `hwy_read` report a twin as its piece
(every block unchanged), `hwy_put`, the hwy_end re-place, `hwave_write` and AVL's writer put the twin where a piece
goes at an odd state (`hwlt_want`), a read value flagged `HWLT_LIT` (piece at an odd state, twin at an even one) is
re-put, so cities saved before the fix heal on their next load pass. Saves use the piece's own hwyp / hwys entry
(`hwy_piece` maps twin -> piece). Ids 26000..26399 (free in every worktree on 2026-10-21):
hwave 26000..26011, hwt 26020..26076, hwx 26080..26096, hwdx 26100..26167, hwdd 26180..26209.

Tool: `re/tools/netmod/hwlight.py` (`twart` per package, `manifest`, `check`, `ids`); twin lists in
`examples/<package>/lit_twins.json`.

Rebuild a package (after its own art, from its art folder): `py -3.12 re/tools/netmod/hwlight.py twart <pkg>`, the
package's pad step if it has one (hwt_build / hwx_build / hwdx_paint `pad`), `hwlight.py manifest <pkg>`,
`hwlight.py check <pkg>`, then netpack install.

## Checks

Offline:
- `hwpaint.py lit`: each stock straight repainted from the turned scene vs the stock piece the engine shows there
  (TURN1): near 0.975 for the twin, 0.325 for the state-0 art at state 1 (zoom 4, mean of 4 views).
- hwave repaint in this worktree = the shipped art, 240 / 240 frames identical.
- `hwlight.py check` (twin coverage = piece coverage, 1 px tolerance): worst frames 2..10 %, all a 1..3 px sliver of
  the cut face at the cell's corner (covered by the neighbour cell in game), on small frames.
- Sheets: `MAIN\verify\hwlight\owner_shots\hwlight_cause_hwave_turns.png` (cause), `hwlight_hwave_offline_before.png`
  / `_after.png` (4 turns x 4 views), `hwlight_hwt_offline.png` (T at turn 1, before / after).

In game (tree `Simcity_stock_hwlight` = the release plus the reinstalled packages, instance `inst_hwlight`, all 8 mods
built from this worktree, lab city):
- hwave along x (turn 3): twins 26000.3 / 26001.3 / 26010.3 / 26011.3 written; along z (turn 0): 21600 / 21601 /
  21850 / 21851 unchanged. All 4 views of each: ramp walls in the shade of the stock walls beside them.
  `hwlight_ingame_after_x.png`, `hwlight_ingame_after_z.png`.
- save: 40 variant tiles written as base; reload: 40 restored, hwy load pass 0 written 0 reverted (twins read back
  as their pieces).
- all five packages reinstalled with their twins (netpack, 94 overlay files, 184 `hwyl` lines, no `###` line at load).
- hwt T at turn 1 (through highway (131,14)-(131,29), stem (141,20)-(132,20), hwask "Si"): `full T at anchor (131,19)
  turn 1 ... 50 cells written`; 4 views: the T's walls follow the stock walls of each axis. Saved (54 variant tiles).
  `hwlight_ingame_after_hwt_turn1.png`; the moment before the T was built: `ingame_hwt_turn1_before_T_built.png`.
- hwx, hwdx, hwdd, hwave diagonals (2026-10-21, noinject loader from main d7d114b, mods_launch rebuilt from main,
  same tree + mods): the four streams' own saved labs, loaded in this tree. Each was saved before the fix, so the load
  pass is also the heal test. Live grid read after load (np_drive cells), then 4 views through the minimap turn
  button at zoom 3:
  - hwx (`x1_saved` -> lt_hwx.sc3): 204 variant tiles restored, hwy load pass 68 written (34 odd-quadrant ramps per
    cloverleaf x 2). Grid at (56,26): every 26080..26096 at state 1 / 3, every 21120..21165 at 0 / 2. Saved: 208
    variant tiles as base, no id >= 20000 in the file. Reloaded: 208 restored, hwy load pass 0 written 0 reverted,
    grid 34 twins at odd states / 62 pieces at even. `hwlight_ingame_hwx.png`, `hwlight_ingame_hwx_reload_v1.png`.
  - hwdx (`lab3` -> lt_hwdx.sc3, 3 crossings kept: A r0 (58,28), B r0 (131,24), B r1 (105,89)): load pass 162
    written; 60 + 52 + 50 twins, all at state 1, pieces all at 0. Case A 4 views, case B r1 2 views.
    `hwlight_ingame_hwdx_caseA.png`, `hwlight_ingame_hwdx_caseB_r1.png`.
  - hwdd (`lab3_saved` -> lt_hwdd.sc3, cloverleafs (58,28) h and (133,15) c kept): load pass 60 written; 32 + 28 twins
    at states 1 / 3, pieces at 0 / 2. 4 views of (58,28). `hwlight_ingame_hwdd.png`.
  - hwave diagonals (`e1_saved` -> lt_hwave.sc3): the two turn-1 transitions (67,32) and (107,86) re-put as twins
    26004..26009 at state 1 (load pass 12 written), the two turn-0 ones (53,26) and (130,12) keep 21604..21609 at
    state 0. 4 views of (53,26) + (67,32) together. `hwlight_ingame_hwave_diag.png`.
  In every view the ramp / transition walls take the shade of the stock walls with the same world facing. No wall
  shows the img11 pattern (one shade beside the opposite stock shade). Defender: 0 new detections over 6 launches.

Seen twice during the run, not caused by this change: the latent deadlock of memory `project-avenue-lanes` (main
thread STRTSIM -> SIMSPR -> wait SIMCITY.DLL+0xd31d, render thread wait SIMSPR+0x54f3d; Frida stacks) when the view was
rotated through Frida with the sim running. Workaround used: pause, rotate with the minimap button, grab with sc3io.
