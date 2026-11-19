# STATUS plop (round 2026-11-19h, stream plop: new ploppable buildings, landmarks first)

## goal
How the game builds its landmark / reward / civic menus and places a ploppable; whether SC3U loads the 2000 `.pin` +
`.dat` landmark plugins natively; proof with one Maxis landmark pack, then one of our buildings as a new landmark;
kind `landmark` in bldimport.py + the page (byte identity, run_all.sh), pack reader offering to install plugins.

## verdict + deciding RVA
Landmarks are data only, no mod code.
- SC3U loads `.pin` plugins natively from `Apps\PlugIn\` (any depth): SIMINIT `0x1000583e` (Init with
  `PlugInDirectory() + "PlugIn\"`), `0x1000ea2a` (recursive `*.pin`), `0x1000e8d1` / `0x1000ec96` / `0x1000eeef`;
  root = SC3U.exe `0x00482532` (default the Apps folder). Measured in game.
- Landmark dialog = every exemplar whose type IsA 18000 (SIMADV `0x10008ef2`). Line 2 = prop 0x7C text.
- The 2000 art is LZO1X and SC3U dropped that decoder (SIMSPR `0x1001de49`, `0x1001e086` -> `0x1004efdd` return 0):
  blank lot. Converted to QFS (`sc3plugin.py`) it draws.
- Civic = one menu entry + command per building (mod code, not built); rewards = fixed list in
  Advisor-CityPlanner.ini + unlock rules ([UNCERTAIN], not built). Detail `re/analysis/PLOPPABLES.md` section 6.

## built
- `sc3plugin.py` (LZO1X decoder + 2000 -> SC3U record converter), kind `landmark` in bldimport.py / bldweb.js /
  classifier.html, plugin install in sc3pack.py / sc3pack.js, `make_testmodels.py --landmarks`, webtest case
  `landmarks`, landmark in case `ports`, `pagetest.mjs landmarks`, `sc3pack_golden --plugin-pack`.

## proven game-side vs static only
- Game-side: Maxis packs load, list, place, save; converted art draws; our 2 test landmarks list, place, draw (zoom 3/4,
  4 rotations), save, reload, own description; save loaded without the plugins: no crash, landmarks dropped, empty lots.
- JS vs Python: converted packs byte-identical; sc3pack goldens 21/21 incl. plugin install (quick run).
- run_all.sh full run (six arguments + SC3PACK_PACKS): 29 of 29 steps passed (dev\plop\work\runall2.log).
- Static only: civic / reward paths.

## blocked on
- nothing

## files owned (worktree dev\plop\wt, all uncommitted)
- re/tools/bldimport/bldimport.py
- re/tools/bldimport/bldweb.js
- re/tools/bldimport/classifier.html
- re/tools/bldimport/sc3pack.js
- re/tools/bldimport/sc3pack.py
- re/tools/bldimport/sc3plugin.py (new; ignored by `/re/tools/*` like the other bldimport files: needs `git add -f`)
- re/tools/bldimport/make_testmodels.py
- re/tools/bldimport/webtest/golden_setup.py
- re/tools/bldimport/webtest/run_all.sh
- re/tools/bldimport/webtest/sc3pack_golden.py
- re/tools/bldimport/webtest/sc3pack_golden.mjs
- re/tools/bldimport/webtest/pagetest.mjs (backup count: only the outputs the game already had)
- re/analysis/PLOPPABLES.md (new)
- MAIN (not the worktree): verify/plop/RESULTS.md, verify/plop/owner_shots/*.jpg, re/sessions/STATUS_plop.md

## game-harness need
- one windowed game in dev\plop\tree at a time (done; none running)

## asks of other sessions
- guide2 / the guide: a "landmarks" section can now point at kind landmark and the pack reader's plugin install.
- Never ship the Maxis packs (EA content): players install their own copies through the pack reader.
