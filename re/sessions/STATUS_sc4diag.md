# STATUS sc4diag (round 2026-11-19c)

## goal
SC4 conversion (sc4conv.py + sc4web.js) writes 45-degree (diagonal) houses disabled with a note, enables a
non-diagonal colour of the design instead, Python and page byte-identical, page install in Sacramento grows no
diagonal house.

## verdict
Cause found (data): SC4 lot objects turn a building in quarter turns only (word 2 = 0-3), and the corner flag
0x4A4A88F0 (9 / 12) is also on straight houses, so no lot field says "45 degrees". The building's FOUNDATION
model does: exemplar 0x88FCD877 -> type 0x11 exemplar (group 0x361CF9D5) -> S3D mesh, real geometry. Share of
its horizontal outline at 26.6-63.4 degrees: 1.00 on Acorn, Allegheny, Empire, Fleetwood, Four Seasons, Homestar
(36 buildings, every colour), 0.00-0.06 on the other 12 designs (74). Check sheet: owner_shots/00_check_sheet.jpg.
DONE. Python + page byte-identical, run_all.sh 13 of 13 steps (sc4_golden 130 of 130, pagetest sc4 18 of 18).
Page install in Sacramento (bld_lab page1, 10 game-run minutes): 0 diagonal houses in all 5 saves, 62-80 converted
lots of the 12 straight designs (previous round's saves: 22-34 diagonal lots). verify/sc4diag/RESULTS.md.

## built
- views.py foundation_diagonal / outline_share_45, sc4conv.py pick_colours / diag_note / --diagonal
- sc4web.js transcription + 'diagonal' card badge (MutationObserver on #grid, no classifier.html edit)

## proven game-side vs static only
static: 110 of 110 classified, check sheet by eye on every design and colour; byte identity in run_all.sh.
game: Sacramento saves counted (count_saves.py), owner_shots/01 + 02. First launch crashed at SIMCITY.DLL+0x1783
(NULL read, 13.5 s, during city load, before unpause; runs/page1_fault1), retry clean. Cause not read.

## blocked on
-

## files owned (worktree dev\sc4diag\wt)
- re/tools/sc4conv/views.py, re/tools/sc4conv/sc4conv.py
- re/tools/bldimport/sc4web.js, docs/buildings/importer/sc4web.js (sync_css.py --publish)
- re/tools/bldimport/webtest/sc4_golden.mjs, golden_setup.py, pagetest.mjs, pagetest.js
- docs/buildings/index.html (SC4 section: diagonal line + limit)
In MAIN (gitignored, local): verify/bldpack/work/guide_template.html (same guide lines), verify/sc4diag/*

## game-harness need
Used: dev\sc4diag\tree (page install applied there). Game stopped, harness released. MAIN\verify\sc4diag\runs\page1.

## asks of other sessions
- classifier.html owner (sc3ui3): the SC4 note says "One colour of each design is on"; with diagonal designs off
  it could say "of each straight design". Not edited here (rule of this round).
