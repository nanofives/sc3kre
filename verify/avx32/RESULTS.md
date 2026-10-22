# avx32: boulevard / avenue crossings from the owner hand test 2026-10-21 (img6, img7, img8)

Owner reports on the LAN build of main 664a685: "3 road avenue intersecting with 2 road avenue is not working" (img6)
and "asymmetrical intersection is not working for 3 lanes and 2 lanes" (img7, img8). Read from the screenshots:
img6 = boulevard x avenue, centred; img7 = boulevard through, the crossing road a boulevard on one side and an avenue
on the other; img8 = avenue through, the crossing road an avenue on one side and a single road on the other.
Light test (owner rule): one lab game per case, pictures, save and reload. Sheet:
`MAIN\verify\avx32\owner_shots\avx32_sheet.png` (before / after per case, both drag orders, regression, no-mod load).
Lane plan of the new boxes: `MAIN\verify\avx32\owner_shots\avx32_plan.png` (built before the owner saw it; open for
owner corrections).

Setup: worktree `Simcity_wt_avx32` (child/avx32 from main 664a685), test tree `Simcity_stock_avx32` (hard-linked copy of
`Simcity_release`), instance `re\harness\inst_avx32`, all 8 mod binaries built from the worktree.

## Causes (in game, sc3netmod.log)

| case | log | cause |
|---|---|---|
| img6 | `bv: run axis 0 from (50,27), 17 column(s) left to the stock tiler: an avenue arm that would stay two-way` | AVX runs before BV in the edit pass. It read the stock 11204 / 29 / 11204 boulevard as three single roads crossing the avenue (avjunc's box run goes up to 4) and wrote its box and one-way nose 20800 into the avenue arm. BVX's `avl_band_ok` on the arm cell 2 past the box then found AVX's 20800 (not a band row: `no band row at the cell (80015140)`) and refused the whole boulevard. Result: stock boulevard + AVX road box = img6 |
| img7 | axis 0 `road beside the boulevard is not a straight single road`, axis 1 `a junction inside an end region` | BVX had no box for a 3-column span whose side holds an avenue on 2 of its 3 columns (it fell to BV's per-column rule), and the crossing boulevard's run read the box columns as an avenue narrowing. Stock 3x3 of 43 = img7 |
| img8 | `avx: edit run: 1 junction box(es)` (a 1-position road x avenue box) | The stock tiler caps the crossing avenue's left half at the through avenue (11203 at (57,26)) and joins the right half with a T 39, because only the right column goes on as a road. AVX then sees a road crossing on that column only, and the crossing avenue stays stock two-way, cut off from the box |

## Changes

1. **AVX leaves boulevard junctions to BV** (`sc3netmod_avx.c` `avx_bv_box`, twin `avjunc_rule.bv_box`): a box run of
   3 positions that BV's own run rule takes. New `bv_takes(mgr, x, z)` in `sc3netmod_bv.c` runs `bv_run1` as a dry run
   on the cells as they stand with the AVL band checks taken as passed (`g_bv_dry`, macro `BV_BAND_OK` at the three
   band checks), so AVX and BV share one definition of a boulevard and leftover AVX pieces in an arm cannot flip the
   answer. Twin: `boulevard.runs()` (band_ok None). Orchestrator ruling 2026-10-21 (no separate heuristic).
2. **BVX asymmetric boxes** (`sc3netmod_bvx.c`, `sc3netmod_bv.c`, twin `bvx.py` / `boulevard.py`): a 3-column span may
   hold a 2-column avenue arm at one end of a side; a BV run may end in a box with an avenue going on past it (end
   type 6). The box side letter is `L` / `H` (the arm at the low / high end of the side in real coordinates) in the
   `bvxc` lines. Covers img7 (both alignments) and, with the same pieces, an avenue crossing a boulevard one column
   offset (both ways). Package `boulevard_junctions`: 25 new box pieces (20933..20949, 21920..21927), 108 new bvxc lines
   (213), lanes from `bvlanes.py` (new scenes `box_scene_asym`, the new pieces' curves allocated after all others:
   24818..24877), art from `bvx.py build`. Every one of the 245 existing lane specs is byte-identical after the rebuild.
   Schema: the bvxc pattern accepts `L` / `H`.
3. **AVX cap links** (`sc3netmod_avx.c` `avx_caps`, twin `avjunc_rule.cap_links`): the stock pattern "straight pair of
   the crossing avenue, then {11203, 39}, then the through avenue's two rows, then road in the T's column only" is
   re-read for the pass as a link row plus an arm into the box. The box forms as an avenue x avenue with the going-on
   road a two-way arm. No new pieces: all 21 patterns (every one-way / two-way arm combination, 8 drawings) are already
   declared in avenue_junctions.

## Offline

| check | result |
|---|---|
| `bvx.py check` (9 kinds x 4 rotations through `boulevard.runs()`) | 36 / 36 OK, rotation-invariant, 0 clashes; the old 20 unchanged; boulevard round-2 layout 39 cells |
| art edge pattern vs placement, every box cell of every scene | 72 cells, 0 mismatches |
| `netpack.py validate examples/boulevard_junctions` | exit 0 |
| `avjunc_rule.py check`, 15 shipped cities, edge check | before: 48,540 edges meet, 125 do not; after: 49,346 meet, 125 do not (same 125) |
| boxes the boulevard refusal changes in shipped cities | 0 (a first heuristic version removed 9 short 3-road stubs in Berlin / London; replaced by BV's own rule) |
| cap links in shipped cities | 32 road-x-avenue boxes become full 2x2 avenue junctions, 3 new boxes, 0 boxes lost (a first version also matched an avenue ending on an avenue in London (141,170); restricted to "road on the T's column only") |
| patterns the shipped cities need | 57, all declared |

## In game (Simcity_stock_avx32, lab city copies)

| case | result |
|---|---|
| img6, boulevard drawn first | BVX box 20900 / 20902 / 20901, noses 20910 / 20911, both avenue arms one-way 21700 with U-turns 21701 |
| img6, avenue drawn first | the same grid |
| img7 | 3x3 box (20933..20940, 20926), both boulevard runs, avenue one-way; save `100 variant tile(s) written as base`, reload `all restored`, load passes write 0, grid identical |
| boulevard x avenue one column offset | 3x3 box (20949, 21920..21922, 20905), both avenue arms one-way |
| img8, road on the high column | 2x2 box 20807 / 20808 / 20820, link noses 21772 / 21773, nose 20800, crossing avenue one-way; save 54 tiles, reload identical |
| img8, road on the low column, road drawn first | 2x2 box 20807 / 20825 / 20809, the same noses |
| DLL before bv_takes: img6 + img8 in one game | as above; save `133 variant tile(s) written as base`; the saved file read offline holds stock ids only (max 18002); reload `all 133 variant tiles restored`, every load pass 0 written, both grids identical |

| final DLL (bv_takes): img6, avenue drawn first | BVX box, noses, avenue one-way (AVX boxed it while 2 roads were drawn, BV took over with the 3rd) |
| final DLL: plain road x avenue (regression) | AVX road box 20805 + noses, as before |
| final DLL: img6 boulevard first + img7, save, reload | save `179 variant tile(s) written as base`; reload `all 179 variant tiles restored`, load passes 0 written, grids identical |
| the same save in a game WITHOUT sc3netmod (inst_avx32_nomod: mods_launch + sc3resize) | stock pieces only (11204 / 29 / 43), a sane stock layout (`nomod_img6_z3_r0.png`, `nomod_img7_z3_r0.png`) |
| before shot of the offset crossing | release code (HEAD sources built into inst_avx32_old): `road beside the boulevard is not a straight single road`, stock patch |

Traps met: the Frida camera call failed twice in one game and the game then went Not Responding (killed, one game per
case after that, the camera state file deleted before each camera call so a failed call cannot leave a stale one).
One relaunch crashed 0xC0000005 at 438 ms, before the city load; the next launch of the same city was fine.

## Not done / open

- Traffic not traced through the new boxes (lanes come from the same generators as bvlanes / avjunc; the lab city has
  no population).
- Asymmetric boxes not covered: a through avenue whose crossing road is a boulevard on one side and an avenue on the
  other (a 3x2 box), and a boulevard whose crossing is a boulevard and a single road. Both stay as today.
- Tree prep for package installs: the release ships no netpack ledger, so `Simcity_stock_avint`'s `ledger.json` and
  `packs\` were copied into the test tree before reinstalling boulevard_junctions. A republish needs the same
  reinstall in the staging tree (avint) with this package.

# img10 (owner report 2026-10-21, LAN build of main 67bd9ea): boulevard x avenue T, the avenue going into a highway

Owner: "why is this 3 lane intersection like this?" (`MAIN\verify\ownerbugs_1021\owner_shots\img10_bv_avenue_T.png`): a
boulevard with an avenue ending on its side, the avenue a few cells long and going up a highway ramp (hwave
transition). The T is a 3x3 of plain stock crossings. Owner log `MAIN\verify\handtest_2026-10-21b\sc3netmod.log`, undo
log beside it. Sheet: `MAIN\verify\avx32\owner_shots\img10_sheet.png`.

## What the owner did (the two logs)
576 s the T box DID build (`bv: ... 29 cell(s)` = 27 + the 2 avenue noses). 579 s a 4th parallel road beside the
boulevard (`road more than 3 wide`). 586 s / 588 s demolishes: `an avenue arm that would stay two-way` from then on.
594 s a demolish converted the boulevard again, and the 595 s undo reverted that, which left the grid in img10.

## Cause (reproduced in game, lab shifted one cell: highway cap x=52, avenue x=53..56, boulevard x=57..59)
Two "would this band convert if my end counted" queries (`avl_band_ok`) face each other on the short avenue:
- BVX builds the box only if the avenue arm's band converts. The band's far end is hwave's ground row, and AVL takes
  only the one-way row 21850 / 21851 (`avlj`) as a join, not the two-way T2 pair 21602 / 21603.
- hwave writes the one-way row only if the band converts from its side. That band's far end is the box side, which
  is a join only once BVX has built its noses.
The 4th road made BV refuse, so the arm went stock, AVL reverted the band and hwave put T2 back. After the demolish,
each side waits on the other and nothing converts. Same lines as the owner's log, frame `img10_repro_stuck.png`.

## Fix (`sc3netmod_avl.c`, avl_end + avl_band, marked task avx32)
A highway transition's ground row at a band end is the band's to choose. Either pair is read as the one-way pair
(T2 exit 21602 -> 21850, T2 entry 21603 -> 21851, same state) when the end is checked, and it reports end kind 4.
`avl_band` then writes 21850 / 21851 when the band converts and 21602 / 21603 when it does not, which is what
`hwave_build` writes for the same answer. So the queries no longer deadlock, and the band and its ground row always
agree, also when the edit is outside hwave's pass box (about 11 cells round the edit). No new ids, no table change.

## In game (final DLL, tree Simcity_stock_avx32)
| case | result |
|---|---|
| owner's sequence: highway, avenue, 3 roads, 4th road, demolish it | box 20910..20914 / 20903..20905, ground row 21850 / 21851, band one-way (`img10_final_owner_sequence.png`) |
| the stuck save (made with the old code) loaded | load pass builds the box (29 written), hwave puts the one-way row back, band one-way |
| other drag order: boulevard, highway, then the avenue, last cell at the boulevard | box + noses 20910 / 20911, 21850 / 21851; at that drag the transition was two-way, which the old check refused |
| long avenue (16 band rows), break with a 4th road and demolish | break: band two-way and AVL writes 21602 / 21603 at the far transition (17 cells from the edit). Demolish: box, band one-way, 21850 / 21851 again |
| save + reload | final build: 69 variant tiles restored (long avenue). Query-only build: 45 and 122 (both short Ts). Every load pass 0 written, grids identical |
| the 122-tile save (query-only build, the same saved piece kinds) in a game without sc3netmod | stock ids only (11204 / 29 / 43, caps 15053 / 15054 and 11237 / 11235, U-turn rows 11203) |
| first build of the query-only version, both T layouts | built, superseded by the final change above (the query-only version left a mismatch for long avenues) |

## Behaviour changes beyond img10 (not reported by the owner, needed by the fix)
- Any `avl_band_ok` caller (BV / BVX, DAV diagonal joins, RBT9 roundabout arms, hwave) now gets "converts" for a
  band whose other end is a highway transition in its two-way state. Not tried in game for DAV / RBT9.
- An avenue between two highway transitions can now convert (both ends read as the one-way row). Not tried in game.
- AVL writes the two hwave ground row cells at the end of a band it decides. Before, only hwave did, so a band
  decided outside hwave's pass box could keep the ground row of the other kind. Seen once in game with the old code:
  one-way ground row next to a reverted two-way band.

## Guard (orchestrator 2026-10-21): only a transition hwave would accept
`sc3netmod_hwave.c` `hwave_row_ok` (new, marked task avx32): runs `hwave_check` (the conditions hwave uses to keep or
build a transition) on a 7 x 7 window round the transition's anchor. It reads its own window because `avl_band_ok`
can be called from inside a highway pass (`hwave_build`), where `hwy_begin`'s static pass must not be touched. Claims
are not asked: after a ROAD pass the claim table still holds the cells hwave kept for this very transition, and
inside a highway pass hwave has just run the same check with them. `avl_end` reads the ground row as the one-way pair
(and takes it as the band's, end kind 4) only when both cells pass. Otherwise it keeps the old reading, so the band,
and a box that asks about it, stay stock.

In game (guard build, one lab game `labG`, then reload and no-mod load):
| case | result |
|---|---|
| A: highway, avenue (4 cells), 3 boulevard roads | box + noses, ground row 21850 / 21851, band one-way |
| A: undo of the 3rd boulevard road (drawn paused, sc3undo `UNDO> entry 1 (road): 127 op(s), 0 failed`) | grid identical to the 2-road grid before it (AVX road T, one-way avenue) |
| A: owner's sequence, 3rd road again, 4th road (stock, T2 two-way), demolish it paused (box back), undo (`173 op(s), 0 failed`) | grid identical to the 4-road grid: stock roads and T2 two-way, nothing mixed |
| A: demolish the 4th road again (not paused) | box + noses, 21850 / 21851, band one-way (`img10_guard_A_owner_sequence_z2.png`) |
| B: 2-cell avenue (U-turn row + 1 cell) between highway cap and boulevard | hwave refuses (`no straight avenue past the U-turn row`), BV refuses (`an avenue arm that would stay two-way`): stock caps 15053 / 15054, stock 11203 row, stock 3-road block, no one-way piece |
| C: other drag order: boulevard, highway, avenue | box + noses, 21850 / 21851, band one-way (`img10_guard_B_refused_C_order2.png`, bottom) |
| save (78 variant tiles) + reload | all 78 restored, every load pass 0 written, A / B / C grids identical |
| the same save without sc3netmod | stock ids only (11203, 11204, 15051, 15053, 15054, 29, 39, 43) |
Undo note: sc3undo records only actions made while paused (unpausing clears the history), and a Frida attach while
paused hangs the game. So the paused drags were posted mouse input with the tool picked before pausing, and the undo
the sc3undo window message (WM_APP + 0x5d0, wParam 1).

# img12 (owner report 2026-10-21, LAN build of main a89ecef): the boulevard's end on a crossing road

Owner: "roads at the end of the avenue are broken for three lanes" (`MAIN\verify\ownerbugs_1021\owner_shots\
img12_bv_end_broken.png`), log `MAIN\verify\handtest_2026-10-21c\sc3netmod.log`: `bv: edit: run axis 1 from (55,24), 15
column(s) left to the stock tiler: a junction inside an end region`, then every boulevard piece of the run (the middle
BVX box 20910..20914 at z 30..31 included) `no longer in a run -> stock retile`.

## Cause (offline twin reproduces the log line)
The crossing road runs through the run's LAST column, nothing beyond: bv_run1 reads that end as a cap (end region = that
column) and the column as a single-road junction. A junction inside a cap / taper / narrowing region is refused (their
pieces have no side openings), and BV refused the WHOLE run, so the good middle box went stock too. Same family: any
crossing exactly one column before the end ("a junction next to an end region").

| shape (boulevard.runs, before) | result |
|---|---|
| T: boulevard ends on a road | refused: a junction inside an end region |
| T: ends on an avenue / a boulevard | converts |
| X road / avenue / boulevard, 1 column past | refused: a junction next to an end region |
| X, 2+ columns past | converts |
| corner (road on one side only at the end) | refused: a junction inside an end region |

## Fix (plan `MAIN verify\avx32\owner_shots\img12_plan.png`, owner approved 2026-10-21)
1. Ends ON a single road: the last column is a 1-column BVX box (end type 4, width 1), pieces 21928 ACIA / 21929 ICIA /
   21930 ICAA (base 43), 12 `bvxc` lines (1x3 and 3x1, 4 turns). Lanes (bvlanes `end_scene` BrT): the boulevard turns
   right from its outer + middle lanes and left from its inner + middle lanes, merging into the road's lane (`box_lanes`:
   a 3-lane stem into a 1-lane road turns 2 lanes each way); the road goes through, right into the outer lane, left into
   the inner lane.
2. A road or an avenue crossing one column before the end: allowed, existing pieces, then the cap (scenes BxR1, BxA1
   prove the same lane sets). A boulevard there stays refused by the cap rule (the other boulevard reads the stub as an
   arm shorter than 2).
3. Ragged-end fallback (orchestrator 2026-10-21, picture `MAIN verify\avx32\owner_shots\img12_ragged.png`): a refusal
   about ONE end (corner, unknown continuation, junction in / next to an end region, missing end pieces) no longer takes
   the run stock. That end's columns stay with the stock tiler (cut 1, 2, ... up to 12 from that end until the run
   converts, the new end a plain column with the median in a nose, end type 7), the rest converts, middle boxes
   included; log `bv: ...: ragged end(s), N column(s) at +s and M at -s left to the stock tiler: <reason>`. Still
   whole-run refusals: road touching the run, a bad arm, road 4+ wide, and the AVL program rule (an avenue that would
   stay two-way). C `bv_run_fb` (`bv_pass` and `bv_takes`), twin `boulevard.runs()`.
   A ragged end meets the stock roads with one-way carriageways (the lanes running the other way end at that edge),
   as diagbv's ragged ends (avrbtfix).

## Offline
| check | result |
|---|---|
| twin matrix after: T on a road, X road / avenue 1 past | convert (box / existing pieces + cap) |
| twin: corner + a mid crossing; boulevard X 1 past; road crossing right before a taper; rows 0 and 2 going on | ragged end (1 / 4 / 2 / 1 column(s) stock), the rest converts; the crossing boulevard of "X 1 past" still refused (arm shorter than 2) |
| `bvx.py check --tiler` (new shapes BrT, BxR1, BxA1, every turn) | 0 failures |
| bvlanes rebuild vs the package | 245 existing specs byte-identical, + bvl_21928..21930, bvlanes_boxes.json additions only (3 pieces, 12 lines), no new curve shapes |
| `netpack.py validate boulevard_junctions` | exit 0 |
| 16 shipped cities, old vs new rule | 0 runs change |
| C build (`build_mod.ps1 -Mod sc3netmod`) | no warnings |
| C: read-border guard (`bv_pass`) | a ragged run whose full extent reaches the pass's read border is left to the whole-map pass (the window, not the run's end, may have cut it); found in game, below |

## In game (tree Simcity_stock_avx32, noinject loader from main d7d114b, lab copies of lab.sc3)
Sheet `MAIN verify\avx32\owner_shots\img12_sheet.png` (frames `img12_*.png` beside it).

| case | result |
|---|---|
| A1 img12 layout: boulevard x 53..55 first, then the road across its last column (z 36 / 38) | 1-column box 21930.1 / 21929.1 / 21928.1, median nose 20702 before it, cap at the other end (`45 written`, then `18 written` when the road came) |
| A2 the other drag order, at the run's -s end (road z 42 first, then the boulevard) | box 21928.3 / 21929.3 / 21930.3 |
| B road crossing one column before the end (boulevard along x) | BV crossing 20710 / 20711 at x 46, cap 20704..20706 at x 47 |
| C avenue crossing one column before the end | BVX box 20900 / 20901 / 20902, noses 20910 / 20911, cap at x 66, avenue one-way 21700 with U-turns 21701 |
| D corner end (road on one side only) + a mid road crossing | `ragged end(s), 1 column(s) at +s ... : a junction inside an end region`: the corner column stock (39 / 11204 / 11203), the rest converts with its mid crossing and the nose 20702 at the new end |
| fallback, incidental: a stray 2-row stub past a run's end (failed drags) | `ragged end(s) ... 1 at -s: an end where the roads going on are not one road or an avenue`, rest converts |
| incidental: a run whose third row was drawn short | narrowing into the avenue 20760..20768, the avenue one-way (existing rule) |
| road dragged over a boulevard column | the stock tiler retiles it, BV rewrites it (`36 written`) |
| undo: a road drawn across D's other end while paused (T box, `15 written`), sc3undo message | `UNDO> entry 1 (road): 99 op(s), 0 failed, $80 refunded`; the cap back, 15-row grid identical to before the drag |
| save (final DLL) | `213 variant tile(s) written as base` |
| reload | `all 213 variant tiles restored`, every BV / AVL / RBT / HWY load pass 0 written (AVX load post 4, its own box), 279 road cells identical |
| the same save without sc3netmod (inst_avx32_nomod: sc3resize only) | stock ids only: 29 / 39 / 43 / 11202 / 11203 / 11204 / 11225, roads joined (`img12_N1_nomod_A1.png`) |

Seen, not changed (existing behaviour on a89ecef, not from this round): an edit whose pass window cuts another
boulevard first reverts that boulevard's cells inside the window (its run is skipped as cut, so not kept), then the
whole-map pass writes them back, about 36 retiles + 36 writes per such edit. The end state is right. A fix would skip
the revert loop when the pass found a cut run.
Seen once, not reproduced: in the first lab game a mis-landed drag (wrong camera altitude) left case A's cells 31..36
stock with no BV write and reverted 37 / 38. Dragging a road over a boulevard column on purpose rebuilt it.
Traps: camera calls (rb_lab cam) failed once with `system error` on zoom and the game went Not Responding (killed, my
PID); drags whose endpoints fall off the view or on the toolbar place partial roads (checked with a pixel pre-check
after that); the shoreline area has another ground height.
