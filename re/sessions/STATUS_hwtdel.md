# STATUS hwtdel (child of owner hand-test bugs 2026-10-21): DONE (fixed, uncommitted)

## goal
Owner report (LAN 4f780c5): deleting highway pieces next to a built hwt T leaves 15149 "Highway Construction" marks and
cuts the T (img15_t_broken_after_delete.png). Orchestrator scope (2026-10-22): fix it as shared helpers in hwy.c and
run the same repro against hwt, hwx, hwdx, hwdd, hwave, fixing every block that shows the class.

## design
Cause: a pass whose box grazes an interchange did not recognise / keep it, hwy_end reverted the cells it saw, and the
stock revert retile re-tiled the run and left 15149 (and, for hwave, reset the avenue's lanes). Plain cells an
interchange leaves stock were never kept. Shared fix in sc3netmod_hwy.c: hwy_rd, hwy_put keeps (never writes) past
the box, hwy_keep_far, the 15149 net in hwy_end, hwy_unput, hwy_gap_cap. Block code: hwt (footprint vote, band, no RIO
re-read of a failed full T, caps), hwx (footprint ramps, re-tiled arm cells accepted, band, unput past the box, caps),
hwdx (dropped quadrant past the box), hwdd (no write past the box), hwave (scan from 1 cell in, hwy_rd).
Detail + per-block table: Simcity_wt_hwtdel/verify/hwtdel/RESULTS.md.

## built (files, uncommitted)
Simcity_wt_hwtdel: re/harness/src/sc3netmod_hwy.c, sc3netmod_hwt.c, sc3netmod_hwx.c, sc3netmod_hwdx.c,
sc3netmod_hwdd.c, sc3netmod_hwave.c, sc3netmod_hwcap.c (all tracked), verify/hwtdel/RESULTS.md (new).
main moved to 7fe2f7e meanwhile, none of these files changed there (checked).

## proven in game vs offline only
In game, final build: grazing drag per block (old build broke hwt and hwave, new build clean for all five), bulldoze
next to each (clean), undo / redo byte-identical for all five, save + reload 0 written / 0 reverted / 0 cells 15149,
no-mod load of each save. T-only checks on the earlier build: owner-like case, through cut inside the T, damaged save
repair. Offline: nothing.

## blocked on
nothing

## files owned
- Simcity_wt_hwtdel: the 7 source files above, verify/hwtdel/RESULTS.md
- MAIN: re/sessions/STATUS_hwtdel.md, verify/hwtdel/owner_shots/hwtdel_blocks_sheet.png, hwtdel_sheet.png,
  hwtdel_blk_*.png, hwtdel_*.png (game shots)

## instance (folder, last PID)
Simcity_stock_hwlight\re\harness\inst_hwtdel (all 8 mods from the worktree, final sc3netmod.dll; old-build DLL in my
scratchpad). Saves: scene_all.sc3 (T, cloverleaf, hwdx, hwdd, hwave), after_w*_*.sc3 (bulldozed). Lab scripts there:
group.sh, undo_group.sh/.py, reload.sh, sweep.py, drag.py, up.sh. No game of mine running.

## needs owner
- hwtdel_blocks_sheet.png, hwtdel_sheet.png

## asks of other streams
- none (hwx / hwdx / hwdd / hwave changes made here at the orchestrator's request, marked task hwtdel)
