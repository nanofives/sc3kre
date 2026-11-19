# STATUS civmod (round 2026-11-19j, round 2 after merge 289d3ce) - done, waiting for merge

## goal
Round 2 (owner calls): the loader declares the reward types; rewards out of PlugIn on -Restore; page side of kinds
civic / reward; guide sections; build + one start / load.

## verdict + deciding RVA
- sc3mods.dll "REWARD TYPES": SC3U 0x0040bc80 / 0x0040bccb rel32 -> at_types / at_hier (stock EnumEntries 0x00486f55,
  then bldimport_types.ini rows to the stock callbacks 0x0040cb70 / 0x0040cc08). Runs whenever the patched exe maps
  the loader. New export sc3mods_reward_types @5. sc3resize no longer declares.
- Rewards are their own plugin Apps\PlugIn\bldimport_rewards. sc3mods_patch.ps1 -Restore / .sh --restore move it to
  Apps\sc3mods_off\PlugIn, a patch run moves it back.

## built
sc3mods.dll 126,976 bytes (tree\Apps, copy in inst), VERSIONINFO kept. sc3resize.dll 748,544 bytes (inst).

## proven game-side vs static only
All in verify/civmod/RESULTS.md sections 4-6: runs 0 (all on), A (every mods-page row off), B (sc3resize off), C
(-Restore, the stock exe's view reproduced with SC3MODS_DECLARE=0) load the city holding a placed reward. The bare
unpatched exe itself was not started (fullscreen). run_all.sh 31 of 31. Golden + page case civic byte-identical.

## blocked on
nothing

## files owned (dev\civmod\wt)
- re/harness/src/sc3mods.c, sc3mods.def, sc3resize.c, sc3resize_civic.c
- re/scripts/sc3mods_patch.ps1, sc3mods_patch.sh
- re/tools/bldimport/bldimport.py, bldweb.js, classifier.html, make_testmodels.py
- re/tools/bldimport/webtest/golden_setup.py, run_all.sh, pagetest.js, pagetest.mjs
- docs/buildings/index.html (make_docs.py), docs/buildings/importer/bldweb.js + index.html (sync_css.py --publish)
- re/analysis/CIVIC_REWARD.md, verify/civmod/RESULTS.md
Outside git: MAIN verify/bldpack/work/guide_template.html (edited), stage/sample_pack/README.txt (rewritten, identical).

## game-harness need
none

## asks of other sessions
LAN / release: ship the new sc3mods.dll with sc3mods_patch.ps1 / .sh together (the scripts move the rewards plugin).
