# STATUS sc4pass2 (round 2026-11-19f) - DONE

## goal
Global Office Center tower converted (Python + page, byte identity), grown next to stock towers; lot-only packs
(DiegoDL, I-M) reported plainly with tests; BSC dependencies pack read, lot-prop feasibility report.

## verdict
- Cause of "0 buildings" on all three packs: text exemplars (EQZT1###) not read (GOC, DiegoDL), one-value
  properties stored as one-element lists (I-M), the tower's zoom-5 views are 12 / 14 tiles of one 256-px screen grid
  (one-mesh reader refused them). All three fixed in sc4conv and sc4web.js.
- Tower: class 6700 (commercial dense, high wealth: SC4 $ -> low, $$ / $$$ -> high, density by jobs), lot 4x4 (SC4
  4x3), 251 m, night textures ignored (instance + 0x8000), ploppable + landmark lots named in x_sc4.versions.
  **Grew in Berlin by the first autosave** (churn anarchy_res + anarchy_com 5000), frame 8% taller than the tallest
  stock commercial (4031). Sacramento (no dense commercial) and Europolis (no demand, even with fresh zoned land)
  gave no lot.
- DiegoDL / I-M: nothing converted, report names the 23 buildings + readme's 20 links / the blank model + 6 lots,
  sc4conv exits 3 and writes nothing, the page shows no card and keeps Install / Save off.
- BSC pack: props are the same S3D format; converting lot props is feasible (resolve ids, convert each prop as a
  building, bake into the building's OBJ at its lot position); 61 of 97 I-M prop ids and 0 of 9 tower ids are in BSC;
  the page would need a streaming jar reader (1.64 GB). Report only.
- JMyers output unchanged (661 of 661 files byte-identical to main's converter).

## built
- run_all.sh **18 of 18 steps** (pristine stage\release, JMyers zip + folder, stage\st_packs\sc4).
- sc4_packs.mjs 33 of 33; pagetest sc4empty DiegoDL 4/4, I-M 4/4.

## proven game-side vs static only
- Game: the tower grows and draws in Berlin (verify/sc4pass2/runs/tower4 saves, tower8 dumps).
- Static only: the ploppable / landmark identification, the lot-prop feasibility.

## blocked on
nothing

## files owned (no git add / commit; orchestrator commits by path)
Worktree dev\sc4pass2\wt (branch child/sc4pass2):
- re/tools/sc4conv/exemplar.py, catalog.py, views.py, sc4conv.py
- re/tools/bldimport/sc4web.js
- re/tools/bldimport/webtest/sc4_packs_setup.py (NEW, needs git add -f), sc4_packs.mjs (NEW, needs git add -f)
- re/tools/bldimport/webtest/pagetest.js, pagetest.mjs, run_all.sh
- re/analysis/SC4_FORMATS.md (section 8)
MAIN (local, not repo files unless the orchestrator wants them): verify/sc4pass2/RESULTS.md, verify/sc4pass2/work/*.py,
verify/sc4pass2/owner_shots/ (pack art: local only), re/sessions/STATUS_sc4pass2.md.

## game-harness need
done; harness claim released. dev\sc4pass2\tree has the tower installed (bldimport build) plus test cities
"Europolis tower.sc3" and "Berlin tower.sc3" in its Cities: not pristine any more.

## asks of other sessions
- classifier.html owner: a proper branch for "no building converted" (sc4web.js rewrites #sc4Note and #status today,
  matching the page's current sentence; if that sentence changes, EMPTY_TAIL in sc4web.js must follow).
- Whoever runs sync_css.py --publish: republish docs/buildings/importer/sc4web.js (and the sample pack zip,
  make_zip.py) so players get the new reader.
