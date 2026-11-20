# STATUS sc4ci (round 2026-11-20): SimCity 4 commercial and industrial buildings

goal: test and fix SC4 commercial and industrial buildings (class rule with numbers, long lots, in-game growth, fixes,
byte identity, suite, guide). Results: verify/sc4ci/RESULTS.md.

verdict: done. Class rule kept with numbers (SC3 jobs = SC3ValveLayer.ini valve 7000 per cell x lot; the tool's cuts put
117 of 219 SC4 shops / offices within x2 of their SC4 jobs, a per-cell rule 118; industry is lot-decided, SC3 gives 3-10x
SC4's jobs). Fixes: class without a base of the lot -> no class (was on, bldimport skipped it); dirty 4x4 -> 9100; flat
atlas pieces left out + ATLAS_FIT 2.5 (all 423 install buildings convert, was 410). Maxis' C and I growables behind
`sc4conv.py --growables` / page `?sc4growables`, every entry off (owner's call whether to offer them, costs in RESULTS 7).

built / proven game-side: 8 of 9 SC4 buildings grew (Berlin: shop, retail, low office, 55 m office by save 1; Madison:
refinery, high-tech, textile mill, 1x1 farm by 4.9 min). The 2x2 farm never grew: no 2x2 farm lot develops in Madison or
Farmsville (stock 2x2 farms hold 0 lots in every Madison save). Pictures verify/sc4ci/owner_shots 01-09.

blocked on: nothing.

files owned (worktree dev\sc4ci\wt, uncommitted):
- re/tools/sc4conv/sc4conv.py, re/tools/sc4conv/views.py
- re/tools/bldimport/sc4web.js, re/tools/bldimport/classifier.html
- re/tools/bldimport/webtest/sc4_install_setup.py, sc4_install.mjs, run_all.sh
- docs/buildings/importer/index.html, docs/buildings/importer/sc4web.js (sync_css --publish)
- docs/buildings/index.html (make_docs from the template)
- re/analysis/SC4_FORMATS.md (section 13)
MAIN gitignored: verify/bldpack/work/guide_template.html (backup .bak_sc4ci), verify/sc4ci/*.

game-harness need: own tree only (dev\sc4ci\tree), ids 38000-38008 installed there by bldimport build.
asks of other sessions: none.
