# STATUS civlot (round 2026-11-23b): SimCity 4 civic looks and parks on their own SC4 lot

Workspace `dev\civlot\{wt,tree,inst}`, branch child/civlot, fast-forwarded to main 991bea2 (bakedsharp merged), nothing
committed. Brief: `ROUND_2026-11-23b_forum_shots.md` + orchestrator add-on (baked_sharp default for all SC4 buildings).
Results: `verify/civlot/RESULTS.md`. **DONE.**

## Verdict

Holds, with one rule: X <= Z. A civic look's lot is its own exemplar's prop 0x66; tool, cell claim, bulldoze, Mover,
coverage (SIMSERV 0x1000f006 -> 0x1000f557, X x Z rect both ways), price (by type) and the LOTRECT save all take X x Z.
A saved look whose key is gone comes back as a SQUARE exemplar of its type with side = saved X (SIMGEOM 0x100038a8 ->
SIMINIT 0x1000cb3d), so a w > d civic lot is installed turned a quarter. CIVIC_REWARD.md section 8.

## Proven game-side (dev\civlot\tree, Madison)

SC4 Small Police Station from the Police list, 2x3, type 13130, $500 (+clearing), whole in 4 rotations, own coverage
circle (178 px gone on bulldoze, 0 new), save footprint 2x3, reload same, stock game opens it (2x2 sprite + bare
strip), plugin removed = empty 2x3 lot. baked_sharp copy among houses for the forum strip.

## Built

bldimport / page civic lots, the quarter turn, converter civic/park on SC4 lot, classifier, test models, compare_sheet
turn, baked_sharp default (sc4conv --style, sc4web opt.style), guide + importer copy, analysis. Suite 41 of 41;
non-SC4 goldens byte-identical to main except the civic / lotshape test models changed on purpose.

## Blocked on

nothing

## Files owned (no git add / commit; worktree dev\civlot\wt)

- re/tools/bldimport/bldimport.py, bldweb.js (plan / pack / render_one / renderJob only; renderFrame and styles untouched),
  classifier.html, sc4web.js, make_testmodels.py
- re/tools/sc4conv/sc4conv.py, compare_sheet.py (tracked, under the deny-by-default ignore: `git add -f` if needed)
- docs/buildings/index.html (make_docs.py, published sample-pack link kept), docs/buildings/importer/{index.html,
  bldweb.js, sc4web.js} (sync_css.py --publish)
- re/analysis/CIVIC_REWARD.md (section 8), re/analysis/LOT_SHAPES.md (section 10)
- MAIN (gitignored, local): verify/bldpack/work/guide_template.html (backup .pre_civlot), verify/civlot/RESULTS.md,
  verify/civlot/owner_shots/01-10, verify/civlot/work/{lab.py, match_town.py, ingame.json, logs},
  verify/sc4cmp/forum/01_small_police_station.jpg + 00_small_police_station_four_sides.jpg (old: *_pre_civlot.jpg)
- this STATUS file

## Game-harness need

none now; claim released. Tree holds the 2 SC4 looks (ids 38000 fire, 38001 police) and `Cities\civlot_saved.sc3`.

## Asks of other sessions

- forumshots: sheets 01 / 00 of the Small Police Station are re-made (2x3, baked_sharp); `sheet.json` in forum/ not touched.
- Orchestrator: `guide_template.html` is shared in MAIN; the bakedsharp guide line is folded into the new baked_sharp
  default line there, so a later make_docs run keeps it.
- Not read: whether a non-square LANDMARK with X > Z has the same stand-in risk (landmark type 18000 IsA scan).
