# STATUS objprops (round 2026-11-24c): DONE

## goal
The game's own small props on the free part of an OBJ building's lot, Python and page byte for byte, post pictures.

## verdict
Done. Props + ground paints from the player's Building Architect library (`Apps\Res\BA\PROPS`, `PAINTS\GROUND`),
drawn as billboards (bldrender kind 3). Full detail: verify/objprops/RESULTS.md, re/analysis/BUILDING_ART.md 8.

## proven game-side vs static only
- suite 41 of 41 (dev\objprops\work\runall3.log); Python = page 80 of 80 frames in the scratch compare too
- Berlin: 4 pack ids grew, our frames found in the game's dumps (0.60-0.88 pixel match), start-up fault only

## blocked on
nothing

## files owned (dev\objprops\wt)
re/tools/bldimport/bldprops.py (NEW, `git add -f`), bldrender.py, bldimport.py, bldweb.js, classifier.html,
docs/buildings/importer/index.html + bldweb.js, docs/buildings/index.html (+ a baked_sharp line from another round's
template edit), re/analysis/BUILDING_ART.md. Not mine: re/tools/netmod/__pycache__/* (suite run).
MAIN gitignored: verify/bldpack/work/guide_template.html, verify/bldpack/owner_shots/{00,13,13b}*, verify/objprops/.

## game-harness need
none. Claim released, no game running.

## asks of other sessions
none
