#!/usr/bin/env bash
# run_all.sh - task bldweb (2026-11-18d): every check of the page's importer against bldimport.py.
# Task sc4web (2026-11-19): plus the SC4 conversion (sc4web.js) against sc4conv.py + bldimport.py, when an SC4
# download is given, and the page's own checks (models.json round trip, sc3ui.css copy in sync).
# sc3ui3 (2026-11-19b): plus sc3font_check.py, the game's own fonts built in the page from <pristine game tree>.
# gamefont (2026-11-19d): sc3font_check.py also checks the published web fonts; plus build_fonts.mjs --check and
# fonts_inline.mjs (the importer's inline fonts, no Theme button, light look under OS dark mode).
#
#   test-slot bash re/tools/bldimport/webtest/run_all.sh <work dir> <pristine game tree> <stage\kits> [<SC4 .zip> <the same SC4 download unpacked>]
#
# <pristine game tree>: a game folder with the road mod and no bldimport install (read only; install_golden.mjs
# hard-links copies of it). Steps print "[N/M] name PASS|FAIL"; the tests' own lines follow each step.
# The SC4 download stays on this PC (its licence): nothing of it is written outside <work dir>.
# sc3compat-b (2026-11-19e): plus the pack reader (sc3pack.js vs sc3pack.py: 3 test packs built from the game's files +
# the Maxis 1999 .bld patch, the Maxis add-on installers and the game's Buildings; install / remove; the view in
# Chrome). Samples: SC3PACK_PACKS=<MAIN\stage\st_packs> (default: the stage folder of the repo this script is in), with
# maxis_batpatch_1999\ and maxis_addons_2000\ in it; the test packs are written to its testpacks\ (EA files: local only).
set -u
here="$(cd "$(dirname "$0")" && pwd)"
work="$1"; game="$2"; kits="$3"; sc4zip="${4:-}"; sc4dir="${5:-}"
py="${PY:-$HOME/bin/py -3.12}"
packs="${SC3PACK_PACKS:-$here/../../../../stage/st_packs}"
steps=17; [ -n "$sc4zip" ] && steps=$((steps + 3))
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
echo "$((n - bad)) of $n steps passed"
exit $bad
