# STATUS sc4trees (child of the 2026-11-20 round; worktree dev\sc4trees\wt, branch child/sc4trees, from main 0a4b357)

## goal

Owner (2026-11-20): "Fix the black patches on tree props". Converted SC4 buildings (Hagia Sofia, verify/lotshape
owner_shots/04) showed black patches on the edges of SC4 tree props.

## verdict

Cause found and fixed. It is in the frame renderer, not in the FSH reader or the alpha handling: bldrender / bldweb.js
peel through transparent texels at most 4 times (`PEEL_LAYERS = 4`). An SC4 lot stacks more see-through surfaces
than that (every prop is a view box whose front, back walls and floor are clear around the tree, and the trees
overlap): Hagia Sofia's zoom-3 frames need 15 to 19 rasterize passes. A sample still on a clear texel after the 4th
peel took that texel's colour, and the clear texels of the prop textures (FSH 0x60 DXT1, 1-bit alpha) are (0, 0, 0).
Fix: peel until no sample is open (cap 256), extra peels clipped to the open samples (same frames, about the old
render time). Details and numbers: verify/sc4trees/RESULTS.md.

## built

- bldrender.py + bldweb.js: peel loop to completion, `rasterize` box / open-sample skip, only refilled samples re-tested.
- No mod DLL changes. In game: two Hagia Sofia copies (old 4-peel frames, fixed frames) installed in dev\sc4trees\tree.

## proven game-side vs static only

- Game side: Madison, both copies placed (38000 old at (185, 203), 38001 fixed at (191, 203)), zoom 3 + 4, four
  rotations, frame dumps: black on the old copy, none on the fixed one (verify/sc4trees/owner_shots 01, 02).
- Static: frames byte for byte vs an unclipped peel loop; with SC3BLD_PEEL=4 the new code gives main's 1,000 sc4cmp
  frames exactly. run_all.sh: branch 41 of 42 (step 36 hung while the PC was loaded, 5 of 5 when re-run alone), main
  42 of 42. Python outputs file by file: 39,793 same, 661 differ, all SC4 frames + their .dat files + meta.json cache
  keys + path/timing text. No non-SC4 frame or game file changed.
- Survey, zoom 3: after 4 peels 76 of the install's 113 buildings and all 110 JMyers houses still had samples on a
  clear texel. Forum pictures rebuilt: the fix changes 11 of 17.

## blocked on

Nothing.

## files owned (commit by path, no git add done)

- re/tools/bldimport/bldrender.py
- re/tools/bldimport/bldweb.js
- re/analysis/SC4_FORMATS.md (section 9.5)
- re/sessions/STATUS_sc4trees.md
- docs/buildings/importer/bldweb.js (sync_css.py --publish copy)
- MAIN verify/sc4trees/RESULTS.md; local only: owner_shots/ (SC4 art), work/ (lab.py, shots.py, golden_diff.py/.txt)
- MAIN verify/sc4cmp/forum rebuilt (local, SC4 art), old set in verify/sc4cmp/forum_before_sc4trees
- dev\sc4trees\work (base/new suite folders, cmpconv copies, lab models): scratch, can go with the prune

## game-harness need

None left. Game PID 10564 (started by sc3dev run sc4trees) stopped by PID.

## asks of other sessions

None.
