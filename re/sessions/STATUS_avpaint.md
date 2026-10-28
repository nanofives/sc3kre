# STATUS avpaint (child of the SimCity 3000 RE orchestrator, 2026-10-28)

## goal
Owner report on LAN build sc3mods-2026-10-27f: avenue slope cells (img1) and a 2x2 avenue corner (img2) draw the plain
road with a yellow centre line. Tasks (owner approved 2026-10-28): 3 refusal-reason log in AVL, 2 accept the avenue
corner with a T attached, 1 a look-only paint fallback for avenue bands AVL leaves two-way.

## verdict
FIXED, all three tasks. Detail and log lines: `verify/avpaint/RESULTS.md`. Pictures: `verify/avpaint/owner_shots/`.
- Cause: a plain road at x 569 meets the x band's first row beside the corner (567..568, 31..32). The stock tiler makes
  that row T 39 / X 43 and links the inner bend and x half (both T 39). `avl_corner_at` (sc3netmod_avl.c) needed an
  11203 inner bend and AVX saw no box, so the 3-band chain stayed stock (corners are all or nothing).
- Fix: corner + T in AVL (`avlt`, SC3NETMOD_AVLCT=0 off); the owner's chain converts one-way (88 cells).
- Fallback: AVP block (`avlp`, SC3NETMOD_AVP=0 off) paints bends / U-turn ends / slope rows of a two-way band with the
  avenue look, stock lanes.

## built
- sc3netmod_avl.c: refusal reason per refused band; corner + T (avl_corner_at, avl_ct_side, avlt lines, end kinds 5..7).
- sc3netmod_avp.c (new): AVP block. sc3netmod.c: its #include. sc3netmod_rbt.c: rb_read / hwy_read return a twin's base.
- avenue_lanes 0.3.0: 21727..21735 look-only twins, 21736..21741 corner + T pieces; builder re/tools/netmod/avpaint_build.py.
- netpack.py: accepts avlt / avlp avenue lines.

## proven game-side vs static only
Game-side, owner save in dev\avpaint\tree (4 runs): refusal lines; corner + T converts (live grid read); save +
reload keeps it (stock ids in the file, 0 cells rewritten on reload); fallback paints exactly the 6 expected cells with
AVLCT=0; plain road curves and a plain road slope drawn beside the avenue stay stock. Not observed: traffic on the new
box, the road-on-inner-side T shape (pieces 21740 / 21741 declared, never seen in game).

## blocked on
nothing

## files owned (worktree dev\avpaint\wt, branch child/avpaint)
- re/harness/src/sc3netmod_avl.c (M)
- re/harness/src/sc3netmod_avp.c (NEW, ignored by `/re/*`: needs `git add -f` like the other sc3netmod_*.c)
- re/harness/src/sc3netmod_rbt.c (M)
- re/harness/src/sc3netmod.c (M, one #include line)
- re/tools/netmod/avpaint_build.py (NEW)
- re/tools/netmod/netpack.py (M)
- re/tools/netmod/examples/avenue_lanes/manifest.json (M), README.md (M), avl_21736..21741.lanes.json (NEW x6)
- re/analysis/AVENUE_LANES.md (M, section 4)
- in MAIN: re/sessions/STATUS_avpaint.md, verify/avpaint/RESULTS.md, verify/avpaint/owner_shots/avpaint_sheet_z4.png
  and owner_shots/frames/*.png
- not for commit (gitignored art): re/tools/netmod/examples/avenue_lanes/art/21727..21741 (copied from the recovered
  avenue_lanes / avenue_junctions art). The full installed package with its art is also in dev\avpaint\tree\mods\netmod\
  packs\avenue_lanes (that tree now has a netpack ledger, so `sc3dev remove` will refuse it until the art is moved to
  stage\src via netpack install).

## game-harness need
none (own tree, -multi). No game left running.

## asks of other sessions
- stage\release\Apps\SC3U.exe is the unpatched stock exe (49DD55E1...), so a tree linked from it loads no mods. I
  copied the patched exe (e5b6330c...) into my tree only. My tree also came with only Apps\sc3mods.dll in it; I
  re-linked it from stage\release.
- The release needs avenue_lanes re-installed (0.3.0) in stage\src and sc3netmod.dll rebuilt from this branch.
