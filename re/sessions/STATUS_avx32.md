# STATUS avx32 (owner bugs 10-21, items 5 + 6)

## goal
Boulevard (3-wide, BVX / bvlanes) x avenue (2-wide, AVX / avjunc) crossings, centred (img6) and "asymmetrical"
(img7, img8), build a proper junction with lanes per the avlanes rules.

## state
2026-10-21: DONE. img6, img7, img8 fixed in game (+ offset crossing), save / reload identical, game stopped. Results: worktree verify/avx32/RESULTS.md, sheet MAIN verify/avx32/owner_shots/avx32_sheet.png.

## cause (milestone 1, sent)
- img6 (boulevard x avenue, centred): AVX runs before BV in the edit pass and saw the stock 11204 / 29 / 11204
  boulevard as 3 single roads crossing the avenue (avjunc box run up to 4). It wrote its box + one-way nose 20800
  into the avenue arm, so BVX's `avl_band_ok` on the arm cell 2 past the box found no band row there ->
  "an avenue arm that would stay two-way" -> whole boulevard left stock + AVX box = img6.
- img7 (boulevard through, the crossing road a boulevard on one side, an avenue on the other): BVX had no such
  box: axis-0 run "road beside the boulevard is not a straight single road" (2 of 3 columns = staggered), axis-1 run
  "a junction inside an end region" (the box columns taken as an avenue narrowing). Stock 3x3 of 43 = img7.
- img8 (avenue through, the crossing road an avenue on one side, a single road on the other): the stock tiler caps
  the crossing avenue's other half (11203) and joins the going-on half with a T 39, so AVX built a 1-column road box
  and the avenue stayed two-way.

## design / built
1. AVX (`sc3netmod_avx.c` `avx_bv_box`, twin `avjunc_rule.bv_box`): a box run of 3 positions that BV's own run rule
   takes is left to BV. `bv_takes()` in `sc3netmod_bv.c` = bv_run1 dry run, geometry only (`g_bv_dry`, `BV_BAND_OK`).
2. BVX: a 3-column span may hold a 2-column avenue arm at one end of a side (box side letter `L` / `H` = the arm at
   the low / high end in real coordinates); a BV run may end in a box with an avenue going on past it (end type 6).
   Covers img7 (boulevard N + avenue S, both alignments) and the avenue crossing one column offset (both ways).
   C: `sc3netmod_bvx.c` (bvx_spans, bvx_letter, bvx_boxes), `sc3netmod_bv.c` (end type 6, 5 lines marked avx32).
   Twin: `bvx.py` (spans, partial_letter, box_want, shapes BxBAh / BxBAl / BxAlh / BxAhl), `boulevard.py` (boxav end).
   Lanes: `bvlanes.py` (box_scene_asym, L/H in box_config and _rot_cfg, new pieces' curves allocated last).
3. Package `examples/boulevard_junctions`: 25 new box pieces, 108 new `bvxc` lines (213 total), lanes + art built;
   all 245 existing lane specs byte-identical after the rebuild. Schema: bvxc pattern allows `L` / `H`.
4. AVX cap links (`sc3netmod_avx.c` avx_caps, twin `avjunc_rule.cap_links`): img8's stock pattern re-read as a link
   row + an arm into the box; existing avenue_junctions pieces cover it (no new ids). Shipped cities: 32 road boxes
   become 2x2 junctions, 0 lost, edge mismatches unchanged (125).
   BV-based refusal: 0 shipped-city boxes changed.

## ids taken
FINAL (the orchestrator records 21920..21949 as mine):
- box pieces used: 20933..20949 + 21920..21927. Granted but unused: 21928..21949 (can be released).
- curve shapes used: 24818..24877 (bvlanes grant 24000..24999).
- img8: no new ids (avenue_junctions' existing pieces); avjunc's 21779..21799 not used.
Grepped every worktree on 2026-10-21: none used by another stream.

## proven in game vs offline only
- in game (tree Simcity_stock_avx32): img6 drag both orders -> BVX box 20900/20902/20901, noses 20910/20911, avenue
  one-way 21700 + U-turns; img7 drag -> 3x3 box (20933.., 20926), both BV runs, avenue one-way; save (100 variant
  tiles as base), reload: everything restored, load passes write 0, grid identical.
- offline: bvx.py check 36/36 kind x rotation OK (old 20 unchanged), boulevard round-2 layout 39 cells.
- in game: offset crossing, img8 both alignments / drag orders, final DLL img6 + img8 save (stock ids only) + reload
  identical. Not in game: AvT / BvT regressions (twin only), traffic through the boxes.

## blocked on
(none)

## files owned (worktree Simcity_wt_avx32, uncommitted)
- re/harness/src/sc3netmod_avx.c, sc3netmod_bvx.c, sc3netmod_bv.c
- re/tools/netmod/avjunc_rule.py, boulevard.py, bvx.py, bvlanes.py, netpack.schema.json
- verify/avx32/RESULTS.md
- re/tools/netmod/examples/boulevard_junctions/: manifest.json, bvlanes_boxes.json, bvl_20933..20949.lanes.json,
  bvl_21920..21927.lanes.json
- MAIN: re/sessions/STATUS_avx32.md; verify/avx32/owner_shots/*.png (pictures, not committed: avx32_sheet.png,
  avx32_plan.png, before_* / after_* / final_* / nomod_* frames)

## instance
C:\Users\maria\Desktop\Proyectos\Simcity_stock_avx32\re\harness\inst_avx32\ , last PIDs 43080 / 62104 / 16720 / 42988 (mine, all stopped).
Extra instance folders (mine): inst_avx32_nomod (mods_launch + sc3resize only), inst_avx32_old (release-code netmod).
Tree prep: copied Simcity_stock_avint's mods\netmod\ledger.json + packs\ in (the release ships without them), then
netpack uninstall / install boulevard_junctions from the worktree.
Traps hit: a Frida camera call failing twice then the game going Not Responding (killed, restarted per case); one
startup crash 0xC0000005 at 438 ms before the city load on a relaunch (next launch fine).

## needs owner
- img7 / img8 read as "the crossing road changes width at the junction" (asked the orchestrator, no answer yet).
- plan avx32_plan.png: OWNER APPROVED 2026-10-21 ("Plan looks right, go ahead"), via the orchestrator.
- look of the boxes in game: sheet avx32_sheet.png.

## asks of other streams
(none)
