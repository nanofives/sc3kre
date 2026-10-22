# STATUS avx32 (owner bugs 10-21, items 5 + 6)

## goal
Boulevard (3-wide, BVX / bvlanes) x avenue (2-wide, AVX / avjunc) crossings, centred (img6) and "asymmetrical"
(img7, img8), build a proper junction with lanes per the avlanes rules.

## state
2026-10-21: DONE. img6, img7, img8 fixed in game (+ offset crossing), save / reload identical, game stopped. Results: worktree verify/avx32/RESULTS.md, sheet MAIN verify/avx32/owner_shots/avx32_sheet.png.
2026-10-21 (2nd round, owner img10, boulevard x avenue T with the avenue into a highway ramp): FIXED in game, game stopped. Results: worktree verify/avx32/RESULTS.md section img10, sheet MAIN verify/avx32/owner_shots/img10_sheet.png.

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

## img10 round (2026-10-21, LAN build of main 67bd9ea)
- cause: BVX's arm query and hwave's ground-row query (`avl_band_ok`) each need the other's one-way piece. After the
  owner's 4th parallel road (579 s) BV refused, AVL reverted the band, hwave put the two-way T2 21602 / 21603 back, and
  from then on neither converted (`an avenue arm that would stay two-way`). Reproduced in game.
- fix: `sc3netmod_avl.c` only (avl_end + avl_band, marked task avx32): a band end on hwave's ground row reads either
  pair as the one-way pair and AVL writes 21850 / 21851 (converted) or 21602 / 21603 (refused). No ids, no tables.
- in game: owner sequence, stuck save load, other drag order, long avenue (break + recover), 3 save / reloads, no-mod load.
- behaviour changes beyond img10: every avl_band_ok caller (BV, DAV, RBT9, hwave) sees a two-way transition end as
  converting; an avenue between two transitions can now convert; AVL writes the ground row cells. DAV / RBT9 / two
  transitions not tried in game.
- guard (orchestrator): new hwave_row_ok in sc3netmod_hwave.c, the ground row is read as one-way only when hwave_check
  accepts the transition. In game: owner sequence + undo (paused) consistent, refused transition all stock, both drag orders,
  save / reload, no-mod load.
- files to commit (worktree Simcity_wt_avx32): re/harness/src/sc3netmod_avl.c, re/harness/src/sc3netmod_hwave.c,
  verify/avx32/RESULTS.md.
  The worktree also holds main's 67bd9ea copies of sc3netmod_dbv.c, sc3netmod_hwt.c, sc3netmod_hwy.c, diagbv.py,
  highway_core/README.md, link_tree.py (synced so the build equals main): NOT mine, identical to main, do not commit.
- MAIN pictures (not committed): verify/avx32/owner_shots/img10_*.png.
- ids: none taken. 21928..21949 still unused, can be released.

## img12 round (2026-10-21, LAN build of main a89ecef): boulevard end on a crossing road
- state: 2026-10-21 DONE. Plan owner approved; fixed in game (all 3 cases + the ragged fallback, both drag orders,
  undo, save / reload, no-mod load); my games stopped. Results: worktree verify/avx32/RESULTS.md section img12, sheet
  MAIN verify/avx32/owner_shots/img12_sheet.png.
- cause: the crossing road runs through the run's LAST column (cap end, end region = that column) -> bv_run1 "a
  junction inside an end region", and BV refused the whole run incl. the middle BVX box. Same family: any crossing
  exactly 1 column before the end -> "a junction next to an end region".
- fix 1: end on a single road = 1-column BVX box (end type 4, teew 1), pieces 21928 ACIA / 21929 ICIA / 21930 ICAA,
  12 bvxc lines (1x3 / 3x1). fix 2: road / avenue crossing next to a cap allowed (existing pieces + cap).
- fix 3 (fallback): a refusal about ONE end leaves that end's columns to the stock tiler (cut 1..12 until the run
  converts, end type 7 ragged, median nose), rest converts. C bv_run_fb (bv_pass + bv_takes), twin runs(). Still
  whole-run: touching road, bad arm, road 4+ wide, AVL program rule (avenue would stay two-way).
- lanes: bvlanes end_scene (BrT / BxR1 / BxA1); box_lanes: a 3-lane stem into a 1-lane road turns 2 lanes each way.
- offline: bvx.py check --tiler 0 failures; bvlanes rebuild (with the fallback) = package byte-identical (245 old specs
  unchanged, +3); netpack validate exit 0; 16 shipped cities 0 runs change; C build no warnings.
  Pictures: MAIN verify/avx32/owner_shots/img12_plan.png, img12_ragged.png.
- ids: 21928..21930 used; 21931..21949 unused (can be released).
- files (worktree Simcity_wt_avx32, uncommitted): re/harness/src/sc3netmod_bv.c, sc3netmod_bvx.c;
  re/tools/netmod/boulevard.py, bvx.py, bvlanes.py; examples/boulevard_junctions/{README.md, manifest.json,
  bvlanes_boxes.json, bvl_21928..21930.lanes.json} (+ art/21928..21930, not tracked); verify/avx32/RESULTS.md.
- also: read-border guard in bv_pass (a ragged run reaching the pass window border goes to the whole-map pass).
- in game: A1 / A2 T box both orders, B road X-then-cap, C avenue X-then-cap, D corner ragged; undo 99 ops 0 failed,
  grid identical; save 213 tiles, reload all restored + 0 written + 279 cells identical; no-mod load stock ids only.
- seen, not changed: an edit whose window cuts another boulevard reverts + rewrites it (existing, a89ecef).
- instance: Simcity_stock_avx32\re\harness\inst_avx32 (labF2.sc3 = final save), inst_avx32_nomod; mods_launch rebuilt
  from main d7d114b in both; all my PIDs stopped (31140, 41688, 34420, 44532, 27156).

## img16 round (2026-10-22, LAN build of main 4f780c5): a short stub near one end refuses the whole boulevard
- state: 2026-10-22 FIXED in game (both drag orders, undo, save / reload, no-mod load); my games stopped (PIDs 28764,
  6172, 33404, 64208, 42864). Results: worktree verify/avx32/RESULTS.md section img16, sheet MAIN
  verify/avx32/owner_shots/img16_sheet.png (+ img16_*.png).
- cause: a 2x1 road stub beside the run 3 columns from its end reads as an avenue arm 1 cell long; bvx_spans refused
  "arm shorter than 2" without naming an end, so the ragged fallback never ran and the T box at the other end went too.
- fix: a bad 2- / 3-column arm (too short, road beside it) names the nearer end -> that end stays stock (cut up to 12),
  rest converts. bv_run_fb 4 rounds, cuts grow; ragged-end column test moved before the spans. Twin mirrored.
- still whole-run: 1x1 stub (1-column rule; making it end-only converts a London run over rail crossings 69), touching
  road, 4+ wide, AVL program rule, and any bad arm more than 12 columns from both ends (the middle question, asked).
- offline: 16 shipped cities 0 runs change; bvx.py check --tiler 0 failures; C build no warnings.
- in game, 2nd pass (orchestrator checklist): 1x1 stub at an end = whole run stock (by design); demolish -> full
  boulevard back; 2x1 stub next to the T end = that end (4 cols, crossing incl.) stock, rest converts. PID 37276 stopped.
- ids: none.
- files (worktree Simcity_wt_avx32, uncommitted): re/harness/src/sc3netmod_bv.c, sc3netmod_bvx.c;
  re/tools/netmod/boulevard.py, bvx.py; verify/avx32/RESULTS.md.
- instance: inst_avx32 / inst_avx32_nomod rebuilt (7 mods + mods_launch) from main 4f780c5 + this change; labH_saved.sc3.
- round 2 (owner call 2026-10-22 "add the rail-crossing guard and make the 1x1 stub end-only"): DONE in game.
  Protected guard bv_prot (FUN_1001a7f7(1, id): crossings, tunnel mouths, bridges never boulevard cells), 1x1 stub
  names its end, bv_pass reverts BEFORE writing (a revert's retile overwrote freshly written cells, seen with a rail).
  Checked: owner layout, 1x1 at the end, rail across (+ paused rail undo), paused 1x1 undo, save / reload, no-mod load.
  16 cities 0 converting runs change; bvx check 0 failures; build clean. Sheet MAIN verify/avx32/owner_shots/
  img16r2_sheet.png. Last PIDs 37744 / 45112 / 10572 / 10304 stopped.
- round 3 (owner YES 2026-10-22, middle split): DONE in game. bv_parts: a run the end cuts cannot save, refused for a
  bad arm, splits at the arm's columns into boulevards with ragged ends (each tried with the end-cut fallback, split
  again if needed, <= 16 pieces, sides < 4 columns stock). Twin runs() segs. bv_takes uses it too.
  In game (x 40..72, crossings at 46 / 66, 2x1 stub at 55..56): 41..54 + 57..70 with their own junctions; stub first /
  last identical; paused demolish + 2 undos identical; save / reload (88 tiles, 0 written) identical; no-mod stock ids.
  16 cities unchanged; bvx check 0 failures; build clean. Sheet MAIN verify/avx32/owner_shots/img16r3_sheet.png.
  My last PIDs (69848, 49092, 42784, 73088) stopped.
