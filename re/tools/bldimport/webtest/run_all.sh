#!/usr/bin/env bash
# run_all.sh - task bldweb (2026-11-18d): every check of the page's importer against bldimport.py.
#
#   test-slot bash re/tools/bldimport/webtest/run_all.sh <work dir> <pristine game tree> <stage\kits>
#
# <pristine game tree>: a game folder with the road mod and no bldimport install (read only; install_golden.mjs
# hard-links copies of it). Steps print "[N/M] name PASS|FAIL"; the tests' own lines follow each step.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
work="$1"; game="$2"; kits="$3"
py="${PY:-$HOME/bin/py -3.12}"
steps=8; n=0; bad=0
step() { n=$((n + 1)); local name="$1"; shift; if "$@"; then echo "[$n/$steps] $name PASS"; else echo "[$n/$steps] $name FAIL"; bad=$((bad + 1)); fi; }
step "golden_setup (bldimport.py pack, 4 cases)" $py "$here/golden_setup.py" --game "$game" --kits "$kits" --out "$work"
step "golden.mjs (bldweb.js vs pack, every file + frame)" node "$here/golden.mjs" --golden "$work" --game "$game" --cases testmodels,bld,kenney,styles --frames
step "install_golden.mjs (install, re-install, restore)" node "$here/install_golden.mjs" --golden "$work" --game "$game" --case kenney
step "zip_golden.mjs (.zip route)" node "$here/zip_golden.mjs" --golden "$work" --game "$game" --case kenney
for c in kenney bld styles; do
  step "pagetest.mjs $c (the page in headless Chrome)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case "$c"
done
step "bld_js_check.mjs (.bld reader, game's Buildings)" bash -c "$py '$here/../bldfile.py' js-expect --out '$work/bldexp.json' '$game/Buildings' >/dev/null && node '$here/../bld_js_check.mjs' '$work/bldexp.json' '$game'/Buildings/*.bld"
echo "$((n - bad)) of $n steps passed"
exit $bad
