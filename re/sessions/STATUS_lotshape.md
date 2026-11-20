# STATUS lotshape (round 2026-11-20e)

Worktree `dev\lotshape\wt` (branch child/lotshape, from main 96a80c3), nothing committed. Results:
`verify/lotshape/RESULTS.md`.

## goal

Owner calls 2026-11-20 "True 2x3, patch drawing" (merged as lotdraw) and "Allow 5x5": landmarks and rewards keep a
non-square lot [w, d] (1..5 each) in models.json, bldimport.py, the page and the frames; 5x5 for landmarks and rewards;
the SC4 converter keeps SC4's real lot for landmarks and rewards; page and guide say the mods page row "Non-square
buildings" is needed.

## verdict + deciding evidence

Done, see RESULTS. Suite 42 of 42 (main's code 41 of 41 on the same inputs). Goldens: 39,433 Python files the same;
the ones that differ are the render cache key (bldrender.py hashed), the 5x5 entry of cases landmarks / landmarkdesc,
and the SC4 install's landmarks and rewards (33 lots changed, 7 more on, install 113 cards, 82 on, was 73). Frames: slot extents (w, d), (d, w), (w, d), (d, w), anchor at the lot's left vertex = where
sc3perf LOTRECT registers the sprite (LOT_SHAPES 8.4); matched against `verify/lotdraw/work/make_lotrect.py` sizes and
anchors. In game (dev\lotshape\tree, Madison): SC4's Alamo 2x3 landmark, Mayor's House 2x3 reward, Hagia Sofia 5x5
landmark placed, whole in 4 rotations, save footprint 2x3 / 2x3 / 5x5 (occupant_layer.py), reloaded the same.

## built

See "files owned".

## proven game-side vs static only

- Game-side: the three buildings above, PIDs 5412 and 18280 started by `sc3dev.ps1 run lotshape`, stopped by PID.
- Static only: Mover and bulldoze of a converted non-square building (lotdraw tested them on its probe landmarks).

## blocked on

Nothing.

## files owned

- re/tools/bldimport/bldimport.py
- re/tools/bldimport/bldrender.py
- re/tools/bldimport/bldweb.js
- re/tools/bldimport/classifier.html
- re/tools/bldimport/sc4web.js
- re/tools/bldimport/make_testmodels.py
- re/tools/bldimport/webtest/golden_setup.py
- re/tools/bldimport/webtest/run_all.sh
- re/tools/sc4conv/sc4conv.py
- re/tools/sc4conv/props.py
- re/tools/sc4conv/lottex.py
- re/analysis/LOT_SHAPES.md (section 9)
- docs/buildings/index.html (from MAIN verify/bldpack/work/guide_template.html via make_docs.py)
- docs/buildings/importer/* (sync_css.py --publish)
- verify/lotshape/RESULTS.md (new)
- (worktree, gitignored like lotdraw's) verify/lotshape/work/lab.py, shots.py (lotdraw's, pointed at dev\lotshape),
  golden_diff.py, new.log, base.log, golden_diff.txt
- re/sessions/STATUS_lotshape.md
- (local, gitignored) MAIN verify/lotshape/owner_shots/*, MAIN verify/bldpack/work/guide_template.html (backup
  guide_template.html.bak_lotshape)

## game-harness need

None left: harness claim released, no game running.

## asks of other sessions

None.
