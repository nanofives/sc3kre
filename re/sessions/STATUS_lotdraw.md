# STATUS lotdraw (round 2026-11-20e)

## goal
Owner "True 2x3, patch drawing": non-square (X x Z) buildings draw whole in both orientations, every rotation and zoom,
behind a switch and a mods page row in an existing mod; square buildings unchanged; save records the true footprint.

## verdict + deciding RVAs
**Done** (verify/lotdraw/RESULTS.md, re/analysis/LOT_SHAPES.md section 8). sc3perf block LOTRECT
(`re/harness/src/sc3perf_lotrect.c`, `lot_rect=1` default, `SC3PERF_LOT_RECT=0` off, mods page C row
"Edificios no cuadrados"). 29 SIMSPR sites + the save filler in 9 DLLs.
- InsertCellAlignedSprite SIMSPR 0x10019341 reads X and Z; cell map Insert 0x10007b4d writes X x Z cells.
- Record flag 0x400 + side grid of Z (the cell record has no free byte: sc3bigcity ANCHOR16 uses +0x12/+0x13).
- Registration 0x1000c678 / 0x1000f6f4 (C copies, true left vertex), sort key 0x1000c14b / 0x1000d63f, depth boxes,
  widths, single-cell tests, picks.
- Save: the descriptor filler exists in 9 DLLs; landmarks save through SIMMISC's copy (0x100359f6), and the Z argument
  is the 0x1001cd9a call (LOT_SHAPES had SIMGEOM 0x1001cda8: corrected).

## built
dev\lotdraw\inst: sc3perf.dll, sc3resize.dll (+ sc3lang tables), build_mod.ps1, no warnings.

## proven game-side vs static only
Game-side (dev\lotdraw\tree): 2x3, 3x2, 1x3 whole in 4 rotations at zooms 2-4 with neighbours; highlight, tool
placement, Mover, bulldoze, 3x2 no ghost, save fields 1x3 / 2x3 / 3x2, reload, mods page row + switch round trip.
Square buildings: 20 of 20 Berlin views identical on vs off in one session outside animation (positive control on the
test city differs). Draw time: no measurable cost.
Static only: effect anchors (fire etc.) on non-square lots, 1024 maps, |X - Z| >= 2 sort ties (see RESULTS 6).

## blocked on
nothing

## files owned (commit by path)
- worktree child/lotdraw: re/harness/src/sc3perf_lotrect.c (NEW, ignored by `/re/*`: needs `git add -f`),
  re/harness/src/sc3perf.c, re/harness/src/sc3resize.c (k_mt_rows row + MT_FEAT_DY 16),
  re/harness/lang/{de,en,es,fr,it,nl,sv}.txt (resize.mt_lotrect), re/analysis/LOT_SHAPES.md,
  verify/lotdraw/RESULTS.md, re/sessions/STATUS_lotdraw.md (ignored by `/re/*`: `git add -f`)
- MAIN verify/lotdraw/owner_shots (01-17), MAIN verify/lotdraw/work (tools + results/*.txt). The worktree's
  verify/lotdraw/work holds the same tools (they run from there).

## game-harness need
none (own tree, own inst). SIMSPR / SIMGEOM / SIMMISC on disk untouched (patches in memory only; the tree's SIMSPR is
shipped, MAIN Apps\SIMSPR.DLL still the owner's staged build f5b9f1d9...).

## asks of other sessions
lotshape (importer): anchors for w != d = the TRUE lot's left vertex in every slot (L = 0), LOT_SHAPES 8.4; a
non-square exemplar needs SC3PERF_LOT_RECT on (with it off the art registers X x X: owner_shots/17).
