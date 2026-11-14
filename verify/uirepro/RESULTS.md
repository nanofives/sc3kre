# uirepro: Simtropolis report (StevieKam84), 2026-11-14

Tree `dev\uirepro\tree` = LAN 2026-11-10d (release sc3mods-2026-11-10d), mods from `dev\uirepro\inst`, city
Roadless Paradise, display 3840x2160 (one monitor). Resize = `sc3io.resize_client` (WM_SIZING + SetWindowPos
SWP_NOACTIVATE). Alt+Enter = posted WM_SYSKEYDOWN/UP VK_RETURN with bit 29. Pictures = SC3RESIZE_FRAMEDUMP.

## (b) UI does not rescale on resize / Alt+Enter

| case | ini | 3440x1440 | Alt+Enter (3840x2160) | pictures |
|---|---|---|---|---|
| b1 Auto (no ini = default) | none | scales: `HUDSCALE> Auto: client 3440x1440 -> factor 2.400` | scales: `FULLSCREEN> on ...`, `HUDSCALE> Auto: client 3840x2160 -> factor 3.600` | `owner_shots/b1_auto_3440.png`, `b1_auto_altenter.png` |
| b2 saved Normal | `[hud] scale=0 smooth=1 ver=2` | NOT scaled, UI native in the corner. Log: `HUDOPT> on: scale 0 smooth 1 (sc3resize.ini [hud])`, no `HUDSCALE>` line | NOT scaled | `b2_normal_3440.png`, `b2_normal_altenter.png` |
| b3 Auto + GOG DDrawCompat (`original\gog_2.0.949\Apps\ddraw.dll` + `DDrawCompat.ini` copied into tree\Apps, module loaded from the tree, checked) | none | scales, factor 2.400 | scales, factor 3.600 | `b3_ddc_auto_3440.png`, `b3_ddc_auto_altenter.png` |

Verdict: does not reproduce on our 11-10d build with Auto, with or without DDrawCompat. The player's picture is exactly
case b2, the Normal pick in Preferencias (by design). Second candidate: the SC3KU Enhancement Package ships no
sc3resize.dll (memory `project-sc3ku-fork`: split into sc3native*), so on that package the HUD scaling is not ours.
GOG exe (2.0.949) itself not run: the frame path does not depend on the exe and DDrawCompat loaded with ours.

Ask the player: which package and date (ours sc3mods-2026-11-10d or SC3KU), the `[hud]` section of
`sc3resize.ini` next to the mods, Preferencias > HUD scale choice, Windows build and display scale %, and the
`HUDSCALE>` / `HUDOPT>` lines of `sc3resize.log`.

## (a) orthogonal avenue draws nothing

Same tree, Roadless Paradise, open land x 94..108 z 26..74. Roads laid with `re/tools/netmod/avdb_lab.py` (game-thread
calls to the network manager build, the same call the Road tool makes), camera with `rb_lab.py cam X,Z 3 0`, pictures with
`nb_drive.py shot` (in-process frame dump). Piece ids from `avdb_lab.py snap` (`snapAB.json`, `snapA.json`, `snapD.json`,
`snapC.json`).

| case | build | sc3netmod.log | pieces | picture |
|---|---|---|---|---|
| A z-axis avenue, 2 roads side by side | x=104 and x=105, z 40..56 | `avl: edit: band along z from (104,41) rows 0..14 -> one-way (ends: U-turn / U-turn)`, 34 written, 0 reverted | 21700 / 21701 ends | `owner_shots/a1_orth_avenues.png` (lower band) |
| A x-axis avenue | z=60 and z=61, x 96..108 | `avl: edit: band along x from (97,60) rows 0..10 -> one-way`, 26 written, 0 reverted | 21700 / 21701 | `a1_orth_avenues.png` (upper band) |
| B z-axis avenue + crossing road | x=100/101 z 28..44, road z=36 x 95..106 | `avx: edit run: 1 junction box(es) ... 6 cell(s) written, 0 reverted`, two `avl` bands one-way | 20801/20802/20805 box, 21718/21719 | `a2_orth_avenue_crossing.png` |
| C diagonal avenue | `avdb_lab.py avenue 96,65 8` | `dav: edit: band axis 0, 8 row(s) ... 24 written` | 20500/20505, 21803 ends | `a3_diag_avenue.png` |
| A+B+C again with the community mods | `tree\community\community_patch.ps1 -Game <my tree>` (3 community DLLs loaded, checked in the process map) | same lines, `stats: avl ... refused=0, reverted=0` | 102 of 102 cells identical to the run without them | `a4_community_orth.png`, `a5_community_diag.png` |

Verdict: does not reproduce. Every orthogonal and diagonal avenue draws, with and without the community mods, no
refusals or reverts in sc3netmod.log. The small blue rectangle in a1/a4 is the known lab highlight artefact
(memory `project-lab-build-highlight-artefact`), not art.

Side facts:
- The stage base already has the community SYS.PAK entries (the script said "SYS.PAK: already done" and
  "mods\netmod SYS.PAK: already done"), so the earlier runs already had them. The new part was the three community DLLs.
- The first two drags at x=90/91 drew nothing because that column is water: the game's own retile pass got an empty
  work box (`rbt: retile pass ROAD ... -> cells (0,0)-(0,0)`) and no cell was written. That is the game refusing a road
  on water, not a netmod effect.
- On screen a diagonal avenue looks vertical and a grid-aligned one looks slanted. The player's "orthogonal" may mean
  either, and both work here.

Open hypothesis, not tested: a converted avenue uses netmod's own piece ids (21700.., 20800..), whose art comes from
`mods\netmod\overlay`. An install whose overlay is missing or older than its sc3netmod.dll (DLL updated alone, or a
package that bundles the DLL from another build, like SC3KU's 11-02 netmod) could draw those cells as nothing.

Ask the player: which package and date; is there `mods\netmod\overlay\` next to the game; the first lines of
`sc3netmod.log` (`overlay: ..., N file(s)`) and the `avl:` / `avx:` lines after building the avenue; a screenshot;
whether the roads were built in one drag each or the second one next to an existing road.
