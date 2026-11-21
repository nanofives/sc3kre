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
# suitespeed (2026-11-20): the steps live in suite.py now (this script only starts it, same arguments, same env). Modes:
#   (default)          the SC4 install steps use the fixed install set (sc4_install_set.json: 28 buildings chosen by the
#                      code they reach); every Python reference (golden_setup.py, sc4_*_setup.py, sc3pack_*.py) is
#                      reused while its key (the Python code and data it read, its inputs, its command line) is unchanged
#   SUITE_DEEP=1       releases: the whole install + the --sc4grow page step, every Python reference built fresh
#   SUITE_REBUILD=1    build every Python reference again
#   SUITE_CHANGED=<ref>  only the steps the files changed since <ref> (1 = main) can affect; the rest is listed as skipped
#   SUITE_JOBS=<n>     groups side by side in this one test slot (default 4, 1 = the old order one by one)
# Times (LIVING-PC, 2026-11-20, all six arguments + SC4INSTALL): verify/suitespeed/RESULTS.md.
# Memory: the groups share this run's test-slot cap; children used PROYECTOS_TEST_MEM_GB=6.
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
py="${PY:-$HOME/bin/py -3.12}"
exec $py "$here/suite.py" "$@"
