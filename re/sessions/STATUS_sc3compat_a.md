# STATUS sc3compat-a (round 2026-11-19e): 1999 .bld + player-side BA render tool

## goal
1999 .bld support (bldfile.py + bldweb.js + page), does the SC3U BA render them, player-side render tool (bawinonly
batch mode, BaappW made on the player's PC by a script, render_bld.ps1), importer reads the side IXF. Proof on 17 + 19.

## verdict + deciding RVA
Done (results: verify/sc3compat_a/RESULTS.md).
- 1999 .bld = model v7 (Baapp FUN_00413e1a v7 branch), info record without owner string / id (FUN_004063c8 ->
  FUN_00409142 random id), part record v7 without kind, image 0x0AF1. 36 of 36 samples read identically (Python,
  bldweb.js, classifier.html block).
- SC3U BA renders all 19 (72 s Frida, 43 s player route).
- Player route: render_bld.ps1 -> baappw_patch.ps1 -> BaappW + bawinonly batch mode (PeekMessageA import slot 0x4802b0,
  FUN_0040446b). Frames = Frida route 576 of 576, 0 mode changes, fail-closed checks pass, Jotti 0/13.
- Importer + page read bld_frames.ixf as "bat" art (golden bldside, pagetest bldside, run_all 33 of 33 twice).
- In game: page-installed 1999 Licks 849, Royal Arms Deluxe 112, Whitley Manufacturing 83 lots after 10 min in
  Sacramento; Maxis Plaza (3x3, class 6300) 0, its stock base 179 also 0 in this city (3x3 path unchecked in game).

## built
dev/sc3compat-a/inst/bldkit (the player kit: 2 ps1 + cmd + bawinonly.dll f6b985f9...), tree/Apps/BaappW.exe +
bawinonly.dll (dev tree only).

## proven game-side vs static only
Game-side: renders (4 launches + 2 fail-closed), page install into the dev tree, growth run (see RESULTS).
Static only: meaning of the v7 per-name u32 and FUN_0040f398; v7 part kind byte.

## blocked on
none

## files owned (dev/sc3compat-a/wt, branch child/sc3compat-a = main 9a9c7f7 + uncommitted changes)
Modified: re/analysis/BLD_FORMAT.md (sections 6, 7), re/harness/src/bawinonly.c (tracked), re/scripts/build_mod.ps1,
re/tools/bldbat/ba_patch.py, re/tools/bldimport/{bldfile.py, bldimport.py, bldweb.js, bld_js_check.mjs,
classifier.html}, re/tools/bldimport/webtest/{golden_setup.py, pagetest.js, pagetest.mjs, run_all.sh},
docs/buildings/importer/{index.html, bldweb.js} (sync_css.py --publish).
New (git add -f, /re/tools/* is ignored): re/tools/bldbat/ba_compare.py, re/tools/bldbat/ba_batch_check.py,
re/tools/bldbat/player/{baappw_patch.ps1, render_bld.ps1, render_bld.cmd, README.md}.
MAIN: verify/sc3compat_a/RESULTS.md, verify/sc3compat_a/classifier_1999.patch (reference), re/sessions/STATUS_sc3compat_a.md.
Not to commit: verify/sc3compat_a/runs/, owner_shots/ (game art), any Baapp/BaappW/sample file.

## game-harness need
BaappW in dev/sc3compat-a/tree only, windowed (bawinonly guards + external watcher).

## asks of other sessions
- Release (owner OK): ship the kit (bawinonly.dll + baappw_patch.ps1 + render_bld.ps1 + render_bld.cmd + README.md),
  never Baapp.exe / BaappW.exe.
- run_all.sh in a dev worktree needs SC3PACK_PACKS=<MAIN>\stage\st_packs (its default resolves to dev\stage).
