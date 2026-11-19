# STATUS sc3compat-b (round 2026-11-19e): the pack reader

## goal
re/tools/bldimport/sc3pack.js + sc3pack.py twin: open a pack (zip, folder, nested zip), sort its files, per-.bld
dependency report, install parts into Apps\BACustom with backups and Remove. Golden tests Python vs page.

## verdict + deciding RVA
Done, hook included (main 308f450 merged in, fast-forward). Results: verify/sc3compat_b/RESULTS.md.
No RVA: file formats only. 1999 .bld: model record byte 0 = 7 (v8 layout otherwise), part record 0xE3F87B0D v7 has
no kind u32 (measured on the 19 patch files). bldfile.custom_textures crashes on v7 (told the orchestrator).

## built
- sc3pack.py / sc3pack.js: same JSON byte for byte on 6 packs; agrees with bldfile.parts on 1,827 names (17 shipped).
- 3 test packs in MAIN\stage\st_packs\testpacks\ (local, EA content).
- Tests: sc3pack_golden.mjs 21/21, sc3pack_pagetest.mjs 11/11 (Chrome, + the hook in classifier.html), run_all.sh 24/24 with all six arguments.

## proven game-side vs static only
Static + file tests only. No game or BA launch (BACustom is read by Baapp at start-up; the renderer rules are bldbat's).

## blocked on
none

## files owned (dev/sc3compat-b/wt, changes against main 308f450)
re/tools/bldimport/classifier.html (modified: the hook)
re/tools/bldimport/sync_css.py (modified: publishes sc3pack.js)
re/tools/bldimport/webtest/sc3pack_pagetest.mjs (modified: + the hook in classifier.html)
docs/buildings/importer/index.html, docs/buildings/importer/sc4web.js (modified by sync_css.py --publish)
docs/buildings/importer/sc3pack.js (new, sync_css.py --publish)
Already on main from the first merge: sc3pack.js/.py, webtest sc3pack_*.py/.mjs/.html, run_all.sh (your hand merge, not touched since).
MAIN: verify/sc3compat_b/RESULTS.md, verify/sc3compat_b/run_all.log, verify/sc3compat_b/owner_shots/*.png (page screenshots), this file

## game-harness need
none

## asks of other sessions
- sc3compat-a: bldfile.custom_textures on 1999 v7 part records (no kind u32).
