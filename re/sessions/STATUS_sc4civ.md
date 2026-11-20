# STATUS sc4civ (round 2026-11-19l, stream sc4civ)

## goal
SimCity 4's civic buildings, parks and rewards (from the player's own SC4 install) as SC3U civic looks / rewards /
landmarks, in the page and in sc4conv.py, byte-identical, tested in game.

## verdict + deciding evidence
- SC4 marks them in OccupantGroups 0xAA1DD396: 0x1005 civic (42), 0x1006 park (32), 0x150B reward (53), 0x150A landmark
  (39), service 0x1500..0x1507 + 0x1702. Reward conditions: 60 Lua records in SimCity_1.dat (type 0xCA63E2A3), keyed by
  building instance; 36 count the whole city and give the SC3 population, the rest get 20,000, year 0 always.
- 113 with a model, 112 convert, 73 on. Needed: FSH group 0x1ABE787D for SC4's S3D group 0xBADB57F1, cohort parents
  (63 of 113 hold their type only there), atlas views (316 of 452 views, 2,343 pieces, 738 transposed).
- Byte identity Python = page: sc4_install.mjs 18 of 18, pagetest sc4install 4 of 4; run_all.sh (six args + SC3PACK_PACKS + SC4INSTALL) 34 of 34.
- In game: police, fire, Gazebo looks via the list window; Mayor's House reward unlocked at 500 and placed; save +
  reload keep all 4; police coverage 180 cyan pixels gone when bulldozed. Detail: `verify/sc4civ/RESULTS.md`.

## built
sc4conv: rewards.py (new), catalog/views/props/dbpf/sc4conv. Page: sc4web.js, classifier.html (Open SC4 game, one card
per entry). Tests: sc4_install_setup.py, sc4_install.mjs (new), pagetest.mjs/.js, run_all.sh (SC4INSTALL=...).
Docs: SC4_FORMATS.md 10, docs/buildings/index.html + importer/, MAIN guide_template.html.

## proven game-side vs static only
Game-side: section 3 of RESULTS. Static: the Lua mapping for the other 59 rewards, the park button by name, landmarks
from the install (kind proven in plop/plop2).

## blocked on
Nothing.

## files owned (dev\sc4civ\wt, branch child/sc4civ; new files under re/tools need `git add -f`)
- re/tools/sc4conv/rewards.py (NEW), catalog.py, views.py, props.py, dbpf.py, sc4conv.py
- re/tools/bldimport/sc4web.js, classifier.html
- re/tools/bldimport/webtest/sc4_install_setup.py (NEW), sc4_install.mjs (NEW), pagetest.mjs, pagetest.js, run_all.sh
- docs/buildings/index.html, docs/buildings/importer/index.html, docs/buildings/importer/sc4web.js
- re/analysis/SC4_FORMATS.md
- verify/sc4civ/RESULTS.md (NEW; verify/ is deny-by-default: `git add -f`)
- MAIN (not in the worktree, gitignored): verify/bldpack/work/guide_template.html, verify/sc4civ/owner_shots/ (local only, EA art)

## game-harness need
None left. Tree dev\sc4civ\tree holds the 4-building test install and Cities\sc4civ_saved.sc3. Note: I deleted the
tree's 604 game .bmp files by mistake (a BMP-dump cleanup with a too-wide find) and restored them as copies from
stage\release (604 of 604 back, contents equal); the tree is disposable anyway.

## asks of other sessions
- Next stream sc4baseprops: the install is now readable as a source (catalog.install_files, sc4web installOf /
  readDbpfLazy); `1EDF0000` and `28330000` (the JMyers lots' two most used missing props) are SC4's own.
- To repeat the suite: `SC4INSTALL="C:/Program Files (x86)/Steam/steamapps/common/SimCity 4 Deluxe"` with run_all.sh and
  `PROYECTOS_TEST_HUB=off` (the install is on this PC only).
