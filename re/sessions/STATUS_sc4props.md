# STATUS sc4props (round 2026-11-19g)

## goal
Bake SC4 lot props (fences, trees, cars) into converted SC4 buildings: SC4Lot prop rows + BSC prop models from a
streaming, cached index of the dependency pack jar; reproject each found prop at its lot position into every view
and zoom; list missing ones; per-building switch `x_sc4.props`; JMyers houses with props grown in Sacramento next to
the no-props version; Python then page (sc4web.js) with byte identity; run_all.sh passing.

## verdict + deciding evidence
- Python + page done and byte-identical: `sc4_props.mjs` 130 of 130 (OBJ/MTL/PNG/models.json, --no-props, rerun
  switch, pack, frames). JMyers + BSC: 486 of 5,190 prop rows placed on 72 buildings, 3,454 rows name props in no
  pack given (54 ids, mostly `xxxx0000` ids, SC4's own props by the pattern [UNCERTAIN]).
- Streaming index of the 1.7 GB zip: 20 s Python and page, cached (Python on disk), fetch 4-5 s.
- Rotation sense [UNCERTAIN, partly resolved]: lot textures of the Four Seasons corner lot (SC4_FORMATS.md 9.3).
- In game: all 12 grew in Sacramento (101 lots at the first autosave).
- Branch fast-forwarded to main 7f41ebe (airsea), worktree changes on top, nothing committed.

- run_all.sh with all six args + SC3PACK_PACKS, after the merge of main 7f41ebe: **28 of 28** (verify/sc4props/work/run_all2.log).

## built
re/tools/sc4conv/deps.py, props.py (new); sc4conv.py (--deps, --deps-cache, --no-props, write_props, props_notes,
merge by exemplar); dbpf.py (DBPF from bytes); sc4web.js (same steps); webtest sc4_props_setup.py + sc4_props.mjs
(new); run_all.sh (+2 steps when the 6th arg folder holds the BSC zip); SC4_FORMATS.md section 9.

## proven game-side vs static only
static: offline renders owner_shots/01, 02. game: run2 Sacramento, all 12 ids (6 designs x props / no props) grew by the first autosave, 101 lots; shots 03-05.

## blocked on
nothing

## files owned
(worktree dev\sc4props\wt)
- re/tools/sc4conv/deps.py (new), re/tools/sc4conv/props.py (new), re/tools/sc4conv/sc4conv.py, re/tools/sc4conv/dbpf.py
- re/tools/bldimport/sc4web.js
- re/tools/bldimport/webtest/sc4_props_setup.py (new, git add -f), re/tools/bldimport/webtest/sc4_props.mjs (new, git add -f), re/tools/bldimport/webtest/run_all.sh (hand-merged with airsea's ports steps), re/tools/bldimport/webtest/pagetest.mjs + pagetest.js (--sc4deps)
- re/analysis/SC4_FORMATS.md
MAIN local: verify/sc4props/ (RESULTS.md, work/, runs/, owner_shots/), re/sessions/STATUS_sc4props.md

## game-harness need
dev\sc4props tree, bld_lab run in Sacramento (test slot)

## asks of other sessions
- classifier.html (airsea's this round): optional, a "Props" toggle per SC4 card writing x_sc4.props.on and switching
  `file` between <stem>.obj and <stem>_props.obj; a hint that the BSC zip can be picked with the download. Not needed for
  the feature: picking both zips in "Open SC4 .zip" already works through sc4web.js.
