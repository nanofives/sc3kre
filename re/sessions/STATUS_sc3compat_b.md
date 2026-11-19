# STATUS sc3compat-b (round 2026-11-19e): the pack reader

## goal
re/tools/bldimport/sc3pack.js + sc3pack.py twin: open a pack (zip, folder, nested zip), sort its files, per-.bld
dependency report, install parts into Apps\BACustom with backups and Remove. Golden tests Python vs page.

## verdict + deciding RVA
Done except the classifier.html hook (waits for the orchestrator). Results: verify/sc3compat_b/RESULTS.md.
No RVA: file formats only. 1999 .bld: model record byte 0 = 7 (v8 layout otherwise), part record 0xE3F87B0D v7 has
no kind u32 (measured on the 19 patch files). bldfile.custom_textures crashes on v7 (told the orchestrator).

## built
- sc3pack.py / sc3pack.js: same JSON byte for byte on 6 packs; agrees with bldfile.parts on 1,827 names (17 shipped).
- 3 test packs in MAIN\stage\st_packs\testpacks\ (local, EA content).
- Tests: sc3pack_golden.mjs 21/21, sc3pack_pagetest.mjs 9/9 (Chrome), run_all.sh 18/18 (SC4 included, 4 new steps).

## proven game-side vs static only
Static + file tests only. No game or BA launch (BACustom is read by Baapp at start-up; the renderer rules are bldbat's).

## blocked on
none (the hook waits for the orchestrator's message)

## files owned (dev/sc3compat-b/wt)
The 7 new files are hidden by the deny-by-default .gitignore (/re/tools/*): commit them with `git add -f`.
re/tools/bldimport/sc3pack.js (new)
re/tools/bldimport/sc3pack.py (new)
re/tools/bldimport/webtest/sc3pack_testpacks.py (new)
re/tools/bldimport/webtest/sc3pack_golden.py (new)
re/tools/bldimport/webtest/sc3pack_golden.mjs (new)
re/tools/bldimport/webtest/sc3pack_pagetest.mjs (new)
re/tools/bldimport/webtest/sc3pack_view.html (new)
re/tools/bldimport/webtest/run_all.sh (4 steps added)
MAIN: verify/sc3compat_b/RESULTS.md, verify/sc3compat_b/run_all.log, verify/sc3compat_b/owner_shots/*.png (page screenshots, no EA art), this file

## game-harness need
none

## asks of other sessions
- orchestrator: the classifier.html hook (snippet in RESULTS.md); sync_css.py --publish should copy sc3pack.js.
- sc3compat-a: bldfile.custom_textures on 1999 v7 part records (no kind u32).
