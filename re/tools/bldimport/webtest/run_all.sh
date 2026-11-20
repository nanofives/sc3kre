#!/usr/bin/env bash
# run_all.sh - task bldweb (2026-11-18d): every check of the page's importer against bldimport.py.
# Task sc4web (2026-11-19): plus the SC4 conversion (sc4web.js) against sc4conv.py + bldimport.py, when an SC4
# download is given, and the page's own checks (models.json round trip, sc3ui.css copy in sync).
# sc3ui3 (2026-11-19b): plus sc3font_check.py, the game's own fonts built in the page from <pristine game tree>.
# gamefont (2026-11-19d): sc3font_check.py also checks the published web fonts; plus build_fonts.mjs --check and
# fonts_inline.mjs (the importer's inline fonts, no Theme button, light look under OS dark mode).
#
#   test-slot bash re/tools/bldimport/webtest/run_all.sh <work dir> <pristine game tree> <stage\kits> [<SC4 .zip> <the same SC4 download unpacked> [<folder with more SC4 zips>]]
#   (env SC4INSTALL=<SimCity 4 folder> adds the install steps, sc4civ 2026-11-19l)
#
# airsea (2026-11-19g): golden case ports (kinds airport / seaport: make_testmodels.py --ports + a .bld as a seaport) in
# golden_setup / golden.mjs, and the page installing it (pagetest.mjs ports).
# sc4pass2 (2026-11-19f): the 6th argument (stage\st_packs\sc4: Global Office Center, DiegoDL, I-M zips) adds the
# tower and the lot-only packs: sc4_packs_setup.py + sc4_packs.mjs, and the page on a lot-only zip.
#
# plop (2026-11-19h): golden case landmarks (kind landmark: the plugin Apps/PlugIn/bldimport, make_testmodels.py
# --landmarks + a .bld) and a landmark in case ports, the page installing case landmarks (pagetest.mjs landmarks), and
# the pack reader installing the Maxis landmark packs (sc3pack_golden --plugin-pack <maxis_addons_2000>: .pin + .dat
# into Apps/PlugIn, the 2000 art converted).
# civmod (2026-11-19j): golden case civic (kinds civic and reward: two plugins + the sc3resize ini files) and the page
# installing it (pagetest.mjs civic).
# lotshape (2026-11-20): golden case lotshape (non-square landmarks and rewards, 5x5; make_testmodels.py --lotshape) in
# golden_setup / golden.mjs and the page installing it (pagetest.mjs lotshape).
# plop2 (2026-11-19i): golden case landmarkdesc and the page's Description box (pagetest.mjs --edit-desc: blanked, typed
# in the panel, installed from the page's own models.json = bldimport.py); the SC4 tower's landmark / ploppable lots as
# kind landmark entries and a rerun that keeps their description (sc4_packs.mjs, in the 6th argument's steps).
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
# In a dev worktree (dev\<name>\wt) the default above is dev\<name>\wt\stage, which never exists: fall back to the main
# checkout's stage, found through git's common dir (MAIN\.git).
if [ -z "${SC3PACK_PACKS:-}" ] && [ ! -d "$packs" ]; then
    common="$(git -C "$here" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
    [ -n "$common" ] && [ -d "$(dirname "$common")/stage/st_packs" ] && packs="$(dirname "$common")/stage/st_packs"
fi
steps=23; [ -n "$sc4zip" ] && steps=$((steps + 3)); [ -n "$sc4packs" ] && steps=$((steps + 4))
# sc4props (2026-11-19g): SC4 lot props from the BSC Common Dependencies Pack, when the 6th argument's folder holds it
# (and the JMyers .zip + folder are given): sc4_props_setup.py (sc4conv.py --deps) + sc4_props.mjs (sc4web.js streams
# the 1.7 GB zip as the page does: slices and a stream, never read whole)
bsc=""; [ -n "$sc4packs" ] && [ -n "$sc4zip" ] && for f in "$sc4packs"/*Common\ Dependencies*.zip; do [ -f "$f" ] && bsc="$f"; done
[ -n "$bsc" ] && steps=$((steps + 2))
# sc4civ (2026-11-19l): SC4INSTALL=<the player's SimCity 4 folder, holding SimCity_1.dat> adds the install as a source:
# sc4_install_setup.py (sc4conv.py on the install, a rerun with edits, a 4-building subset packed) + sc4_install.mjs (sc4web.js
# reads the install by slices: every file byte / pixel identical, kinds, rerun, the subset's game files and frames).
# EA's files are read in place: nothing of them leaves <work dir>.
[ -n "${SC4INSTALL:-}" ] && steps=$((steps + 4))
# sc4baseprops (2026-11-19): SimCity 4's own props from the install for a download's lots, when SC4INSTALL, the JMyers
# .zip + folder and the BSC zip are all given: sc4_baseprops_setup.py (sc4conv.py --deps --sc4, and --sc4 alone, both
# packed) + sc4_baseprops.mjs (sc4web.js: the install picked with the download, read by slices, and remembered) + the
# page installing the install-alone case twice (the game's .dat files picked with the .zip; Open SC4 game first)
sc4base=""; [ -n "${SC4INSTALL:-}" ] && [ -n "$bsc" ] && sc4base=1 && steps=$((steps + 4))
# sc4lottex (2026-11-20): SC4 lot textures (driveways, paths, paving) on the ground under the building, with the same three
# sources: sc4_lottex_setup.py (sc4conv.py over the download alone, + BSC, + install, both; --no-textures; a rerun with the
# two switches; the rerun packed) + sc4_lottex.mjs (sc4web.js: report lines, every file of the both run, the switches,
# pack and frames of a building drawn with its ground art and no props)
[ -n "$sc4base" ] && steps=$((steps + 2))
[ -n "${BLD1999:-}" ] && steps=$((steps + 5))
[ -n "${BLDSIDE:-}" ] && steps=$((steps + 3))
n=0; bad=0
step() { n=$((n + 1)); local name="$1"; shift; if "$@"; then echo "[$n/$steps] $name PASS"; else echo "[$n/$steps] $name FAIL"; bad=$((bad + 1)); fi; }
step "golden_setup (bldimport.py pack, 9 cases)" $py "$here/golden_setup.py" --game "$game" --kits "$kits" --out "$work"
step "golden.mjs (bldweb.js vs pack, every file + frame)" node "$here/golden.mjs" --golden "$work" --game "$game" --cases testmodels,bld,kenney,styles,ports,landmarks,civic,lotshape --frames
step "install_golden.mjs (install, re-install, restore)" node "$here/install_golden.mjs" --golden "$work" --game "$game" --case kenney
step "zip_golden.mjs (.zip route)" node "$here/zip_golden.mjs" --golden "$work" --game "$game" --case kenney
for c in kenney bld styles ports landmarks civic lotshape; do
  step "pagetest.mjs $c (the page in headless Chrome)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case "$c"
done
step "pagetest.mjs landmarkdesc (the Description box typed in the page, installed = bldimport.py)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case landmarkdesc --edit-desc "obelisk_2x2.obj=Typed in the page, Córdoba"
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
step "sc3pack_golden.py (sc3pack.py reports, install, remove)" $py "$here/sc3pack_golden.py" --game "$game" --out "$work/sc3pack" --install-pack "$tp/bld_parts.zip" --plugin-pack "$packs/maxis_addons_2000" "$tp/plain_bld.zip" "$tp/bld_parts.zip" "$tp/nested.zip" "$packs/maxis_addons_2000" "$packs/maxis_batpatch_1999" "$game/Buildings"
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
if [ -n "$bsc" ]; then
  step "sc4_props_setup.py (sc4conv.py --deps: JMyers lot props from the BSC pack, rerun, --no-props, bldimport.py pack)" $py "$here/sc4_props_setup.py" --sc4 "$sc4dir" --deps "$bsc" --game "$game" --out "$work/sc4props"
  step "sc4_props.mjs (sc4web.js: the BSC zip streamed, props baked, rerun switch, --no-props, pack, frames)" node "$here/sc4_props.mjs" --golden "$work/sc4props" --game "$game" --zip "$sc4zip" --deps "$bsc" --frames
fi
if [ -n "${SC4INSTALL:-}" ]; then
  step "sc4_install_setup.py (sc4conv.py on the SC4 install: civic, parks, rewards, landmarks; rerun; subset packed)" $py "$here/sc4_install_setup.py" --install "$SC4INSTALL" --game "$game" --out "$work/sc4install"
  step "sc4_install.mjs (sc4web.js on the SC4 install by slices: files, kinds, rerun, subset pack, frames)" node "$here/sc4_install.mjs" --golden "$work/sc4install" --install "$SC4INSTALL" --game "$game" --frames
  # sc4ci (2026-11-20): 113 cards, the Large High School converts since flat atlas pieces are left out (off: 6x6)
  # lotshape (2026-11-20): 82 on (73 before): rewards and landmarks keep their SC4 lot up to 5x5, and 5x5 is allowed
  step "pagetest.mjs sc4install (the page opens the install's .dat files: 113 cards, 82 on, read only)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case sc4install --action open --sc4install "$SC4INSTALL" --expect-install 113,82
  # owner 2026-11-20: the page's "with shops, offices, industry and farms" box ticked: 310 more cards, all off
  step "pagetest.mjs sc4install --sc4grow (the box ticked: 423 cards, the 310 growables off, 82 on)" node "$here/pagetest.mjs" --golden "$work" --game "$game" --case sc4install --action open --sc4install "$SC4INSTALL" --expect-install 423,82 --sc4grow --expect-grow 310
fi
if [ -n "$sc4base" ]; then
  step "sc4_baseprops_setup.py (sc4conv.py --sc4: JMyers with SC4's own props, with and without the BSC pack, bldimport.py pack)" $py "$here/sc4_baseprops_setup.py" --sc4 "$sc4dir" --deps "$bsc" --install "$SC4INSTALL" --game "$game" --out "$work/sc4baseprops"
  step "sc4_baseprops.mjs (sc4web.js: the install picked with the download and remembered, by slices; files, pack, frames)" node "$here/sc4_baseprops.mjs" --golden "$work/sc4baseprops" --game "$game" --zip "$sc4zip" --deps "$bsc" --install "$SC4INSTALL" --frames
  step "pagetest.mjs sc4baseprops_inst --sc4with (the page: the game's .dat files picked with the .zip, installed)" node "$here/pagetest.mjs" --golden "$work/sc4baseprops" --game "$game" --case sc4baseprops_inst --sc4zip "$sc4zip" --sc4with "$SC4INSTALL"
  step "pagetest.mjs sc4baseprops_inst --sc4remember (the page: Open SC4 game first, then the .zip alone, installed)" node "$here/pagetest.mjs" --golden "$work/sc4baseprops" --game "$game" --case sc4baseprops_inst --sc4zip "$sc4zip" --sc4remember "$SC4INSTALL"
  step "sc4_lottex_setup.py (sc4conv.py: JMyers lot textures from the download, BSC, install, both; --no-textures; rerun switches; bldimport.py pack)" $py "$here/sc4_lottex_setup.py" --sc4 "$sc4dir" --deps "$bsc" --install "$SC4INSTALL" --game "$game" --out "$work/sc4lottex"
  step "sc4_lottex.mjs (sc4web.js: lot textures per source set, every file, --no-textures, rerun switches, pack, frames)" node "$here/sc4_lottex.mjs" --golden "$work/sc4lottex" --game "$game" --zip "$sc4zip" --deps "$bsc" --install "$SC4INSTALL" --frames
fi
echo "$((n - bad)) of $n steps passed"
exit $bad
