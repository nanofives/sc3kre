#!/usr/bin/env bash
# run_all.sh - task bldweb (2026-11-18d): every check of the page's importer against bldimport.py.
# Task sc4web (2026-11-19): plus the SC4 conversion (sc4web.js) against sc4conv.py + bldimport.py, when an SC4
# download is given, and the page's own checks (models.json round trip, sc3ui.css copy in sync).
# sc3ui3 (2026-11-19b): plus sc3font_check.py, the game's own fonts built in the page from <pristine game tree>.
# gamefont (2026-11-19d): sc3font_check.py also checks the published web fonts; plus build_fonts.mjs --check and
# fonts_inline.mjs (the importer's inline fonts, no Theme button, light look under OS dark mode).
#
#   test-slot bash re/tools/bldimport/webtest/run_all.sh <work dir> <pristine game tree> <stage\kits> [<SC4 .zip> <the same SC4 download unpacked> [<folder with more SC4 zips>]]
#
# sc4pass2 (2026-11-19f): the 6th argument (stage\st_packs\sc4: Global Office Center, DiegoDL, I-M zips) adds the
# tower and the lot-only packs: sc4_packs_setup.py + sc4_packs.mjs, and the page on a lot-only zip.
#
# <pristine game tree>: a game folder with the road mod and no bldimport install (read only; install_golden.mjs
# hard-links copies of it). Steps print "[N/M] name PASS|FAIL"; the tests' own lines follow each step.
# The SC4 download stays on this PC (its licence): nothing of it is written outside <work dir>.
# sc3compat-b (2026-11-19e): plus the pack reader (sc3pack.js vs sc3pack.py: 3 test packs built from the game's files +
# the Maxis 1999 .bld patch, the Maxis add-on installers and the game's Buildings; install / remove; the view in
# Chrome). Samples: SC3PACK_PACKS=<MAIN\stage\st_packs> (default: the stage folder of the repo this script is in), with
# maxis_batpatch_1999\ and maxis_addons_2000\ in it; the test packs are written to its testpacks\ (EA files: local only).
# sc3compat-a (2026-11-19e): plus the importer's .bld reader (bldweb.js) on the game's Buildings. BLD1999=<folder of 1999
# .bld files> adds the 1999 reader checks (bldweb.js and the classifier page block, Python vs JS) and golden case
# bld1999; BLDSIDE=<folder of .bld + bld_frames.ixf from render_bld.ps1> adds golden case bldside and the page installing
# it (the player's own Building Architect render as the art). Both stay local (EA / third-party files).
set -u
here="$(cd "$(dirname "$0")" && pwd)"
work="$1"; game="$2"; kits="$3"; sc4zip="${4:-}"; sc4dir="${5:-}"; sc4packs="${6:-}"
py="${PY:-$HOME/bin/py -3.12}"
packs="${SC3PACK_PACKS:-$here/../../../../stage/st_packs}"
steps=18; [ -n "$sc4zip" ] && steps=$((steps + 3)); [ -n "$sc4packs" ] && steps=$((steps + 4))
[ -n "${BLD1999:-}" ] && steps=$((steps + 5))
[ -n "${BLDSIDE:-}" ] && steps=$((steps + 3))
n=0; bad=0
step() { n=$((n + 1)); local name="$1"; shift; if "$@"; then echo "[$n/$steps] $name PASS"; else echo "[$n/$steps] $name FAIL"; bad=$((bad + 1)); fi; }
step "golden_setup (bldimport.py pack, 4 cases)" $py "$here/golden_setup.py" --game "$game" --kits "$kits" --out "$work"
step "golden.mjs (bldweb.js vs pack, every file + frame)" node "$here/golden.mjs" --golden "$work" --game "$game" --cases testmodels,bld,kenney,styles --frames
step "install_golden.mjs (install, re-install, restore)" node "$here/install_golden.mjs" --golden "$work" --game "$game" --case kenney
step "zip_golden.mjs (.zip route)" node "$here/zip_golden.mjs" --golden "$work" --game "$game" --case kenney
for c in kenney bld styles; do
  step "pagetest.mjs $c (the page in headless Chrome)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case "$c"
done
step "bld_js_check.mjs (.bld reader, game's Buildings)" bash -c "$py '$here/../bldfile.py' js-expect --out '$work/bldexp.json' '$game/Buildings' >/dev/null && node '$here/../bld_js_check.mjs' '$work/bldexp.json' '$game'/Buildings/*.bld"
step "bld_js_check.mjs --reader bldweb (.bld reader of the importer, game's Buildings)" node "$here/../bld_js_check.mjs" --reader bldweb "$work/bldexp.json" "$game"/Buildings/*.bld
if [ -n "${BLD1999:-}" ]; then
  step "js-expect 1999 .bld" bash -c "$py '$here/../bldfile.py' js-expect --out '$work/bldexp1999.json' '$BLD1999' >/dev/null"
  step "bld_js_check.mjs --reader bldweb (1999 .bld)" node "$here/../bld_js_check.mjs" --reader bldweb "$work/bldexp1999.json" "$BLD1999"/*.bld
  step "bld_js_check.mjs --reader page (1999 .bld, classifier.html)" node "$here/../bld_js_check.mjs" --reader page "$work/bldexp1999.json" "$BLD1999"/*.bld
  step "golden_setup bld1999" $py "$here/golden_setup.py" --game "$game" --kits "$kits" --out "$work" --cases bld1999 --bld1999 "$BLD1999"
  step "golden.mjs bld1999" node "$here/golden.mjs" --golden "$work" --game "$game" --cases bld1999 --frames
fi
if [ -n "${BLDSIDE:-}" ]; then
  step "golden_setup bldside" $py "$here/golden_setup.py" --game "$game" --kits "$kits" --out "$work" --cases bldside --bldside "$BLDSIDE"
  step "golden.mjs bldside" node "$here/golden.mjs" --golden "$work" --game "$game" --cases bldside --frames
  step "pagetest.mjs bldside (the page installs .bld files with bld_frames.ixf art)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case bldside
fi
step "check_roundtrip.py (models.json round trip in the page)" $py "$here/../check_roundtrip.py"
step "sync_css.py --check (sc3ui.css copy in classifier.html)" $py "$here/../sync_css.py" --check
step "sc3font_check.py (game fonts built in the page + published web fonts, pixel for pixel)" $py "$here/sc3font_check.py" --game "$game" --out "$work/sc3font"
step "build_fonts.mjs --check (docs/assets/fonts = a fresh build from the game's FBF files)" node "$here/../../sc3ui/build_fonts.mjs" --game "$game" --check
step "fonts_inline.mjs (importer: inline game fonts, light look under OS dark mode)" node "$here/fonts_inline.mjs"
tp="$packs/testpacks"
step "sc3pack_testpacks.py (3 local test packs)" $py "$here/sc3pack_testpacks.py" --game "$game" --batpatch "$packs/maxis_batpatch_1999" --addons "$packs/maxis_addons_2000" --out "$tp"
step "sc3pack_golden.py (sc3pack.py reports, install, remove)" $py "$here/sc3pack_golden.py" --game "$game" --out "$work/sc3pack" --install-pack "$tp/bld_parts.zip" "$tp/plain_bld.zip" "$tp/bld_parts.zip" "$tp/nested.zip" "$packs/maxis_addons_2000" "$packs/maxis_batpatch_1999" "$game/Buildings"
step "sc3pack_golden.mjs (sc3pack.js vs sc3pack.py: reports, install on a file list + a real folder)" node "$here/sc3pack_golden.mjs" --golden "$work/sc3pack" --game "$game"
step "sc3pack_pagetest.mjs (the pack reader in headless Chrome)" node "$here/sc3pack_pagetest.mjs" --golden "$work/sc3pack" --game "$game"
if [ -n "$sc4zip" ]; then
  step "golden_setup sc4 (sc4conv.py, rerun, bldimport.py pack)" $py "$here/golden_setup.py" --game "$game" --kits "$kits" --out "$work" --cases sc4 --sc4 "$sc4dir"
  step "sc4_golden.mjs (sc4web.js: .zip + folder convert, rerun, pack, frames)" node "$here/sc4_golden.mjs" --golden "$work" --game "$game" --zip "$sc4zip" --folder "$sc4dir" --frames
  step "pagetest.mjs sc4 (the page opens the .zip, converts, installs)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case sc4 --sc4zip "$sc4zip"
fi
if [ -n "$sc4packs" ]; then
  step "sc4_packs_setup.py (sc4conv.py on the tower + 2 lot-only packs, bldimport.py pack)" $py "$here/sc4_packs_setup.py" --packs "$sc4packs" --game "$game" --out "$work/sc4packs"
  step "sc4_packs.mjs (sc4web.js: text exemplars, tiled tower, lot-only reports, pack, frames)" node "$here/sc4_packs.mjs" --golden "$work/sc4packs" --packs "$sc4packs" --game "$game" --frames
  step "pagetest.mjs sc4empty diego (the page on a lot-only zip)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case sc4empty --action open --no-compare --sc4zip "$sc4packs/DiegoDLGrowablePack2019_Vanilla_DN.zip" --expect-empty "555 California Street,Willoughby Tower,Salesforce Tower,https://community.simtropolis.com/files/file/32961-salesforce-tower/"
  step "pagetest.mjs sc4empty im (the page on a blank-model zip)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case sc4empty --action open --no-compare --sc4zip "$sc4packs/I-M manufacturers lots.zip" --expect-empty "a blank placeholder building,1542-hanjin,1542-uniglory"
fi
echo "$((n - bad)) of $n steps passed"
exit $bad
