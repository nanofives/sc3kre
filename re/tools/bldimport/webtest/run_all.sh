#!/usr/bin/env bash
# run_all.sh - task bldweb (2026-11-18d): every check of the page's importer against bldimport.py.
# Task sc4web (2026-11-19): plus the SC4 conversion (sc4web.js) against sc4conv.py + bldimport.py, when an SC4
# download is given, and the page's own checks (models.json round trip, sc3ui.css copy in sync).
# sc3ui3 (2026-11-19b): plus sc3font_check.py, the game's own fonts built in the page from <pristine game tree>.
#
#   test-slot bash re/tools/bldimport/webtest/run_all.sh <work dir> <pristine game tree> <stage\kits> [<SC4 .zip> <the same SC4 download unpacked> [<folder with more SC4 zips>]]
#
# sc4pass2 (2026-11-19f): the 6th argument (stage\st_packs\sc4: Global Office Center, DiegoDL, I-M zips) adds the
# tower and the lot-only packs: sc4_packs_setup.py + sc4_packs.mjs, and the page on a lot-only zip.
#
# <pristine game tree>: a game folder with the road mod and no bldimport install (read only; install_golden.mjs
# hard-links copies of it). Steps print "[N/M] name PASS|FAIL"; the tests' own lines follow each step.
# The SC4 download stays on this PC (its licence): nothing of it is written outside <work dir>.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
work="$1"; game="$2"; kits="$3"; sc4zip="${4:-}"; sc4dir="${5:-}"; sc4packs="${6:-}"
py="${PY:-$HOME/bin/py -3.12}"
steps=11; [ -n "$sc4zip" ] && steps=$((steps + 3)); [ -n "$sc4packs" ] && steps=$((steps + 4))
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
step "sc3font_check.py (game fonts built in the page, pixel for pixel)" $py "$here/sc3font_check.py" --game "$game" --out "$work/sc3font"
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
