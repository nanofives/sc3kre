# STATUS plop2 (round 2026-11-19i, stream plop2: landmark follow-ups)

## goal
Landmark Description field in the importer page; SC4 landmark / ploppable lot versions as kind landmark (sc4conv.py +
sc4web.js, byte identity) and one placed in game; whether the orange-brown lot a removed landmark leaves can be built
on; guide sections "Landmarks" and "Maxis landmark packs"; run_all.sh passing with the new steps.

## verdict
- Description: a panel box shown for landmark cards, written to models.json `description` only when set. Page install
  = bldimport.py byte for byte (pagetest landmarkdesc 9 of 9).
- SC4: the Global Office Center's "Landmark" lot -> landmark entry on (4x4, stats of stock 9510), "Jobs" lot -> landmark
  entry off. JS = Python (sc4_packs.mjs 37 of 37). In game: in the landmark dialog with "From SimCity 4", placed at
  (176, 213), price 120, saved as {0x207EDC0E, 0xB1D10002, 38002} type 18000.
- Orange lot = zone byte 22 (kPloppedBuilding) cells with no occupant. Buildable: a stock landmark placed on it, zoning
  over it works. The bulldozer does nothing on an empty orange cell; bulldozing a building clears only its footprint.

## built / proven
run_all.sh 30 of 30 steps (dev\plop2\work\runall.log). Detail: verify/plop2/RESULTS.md.

## blocked on
- nothing

## files owned (worktree dev\plop2\wt, uncommitted)
- re/tools/bldimport/classifier.html (Description box, entryOf, cp1252 warning)
- re/tools/sc4conv/sc4conv.py (landmark entries, versions carry exemplar + building_tgi, notes text)
- re/tools/bldimport/sc4web.js (same in JS)
- re/tools/bldimport/webtest/golden_setup.py (case landmarkdesc, in the default list)
- re/tools/bldimport/webtest/pagetest.js, pagetest.mjs (--edit-desc)
- re/tools/bldimport/webtest/sc4_packs.mjs, sc4_packs_setup.py (landmark entries, rerun keeps a landmark's description)
- re/tools/bldimport/webtest/run_all.sh (step pagetest landmarkdesc, 21 base steps)
- docs/buildings/index.html (make_docs.py), docs/buildings/importer/index.html + sc4web.js (sync_css.py --publish)
- MAIN (local): verify/bldpack/work/guide_template.html (Landmarks + Maxis landmark packs sections, 4 stale lines),
  verify/plop2/RESULTS.md, verify/plop2/owner_shots/*.jpg (SC4 art: local only), verify/plop2/work/lab.py, saves/

## game-harness need
- none now (both games stopped by PID: 9532, 19480)

## asks of other sessions
- none
