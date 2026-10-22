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

# img16 (owner report 2026-10-22, LAN build of main 4f780c5): a short stub near one end refuses the whole boulevard

Owner: "why is this intersection not triggering the 3 road wide avenue" (`MAIN\verify\ownerbugs_1021\owner_shots\
img16_boulevard_not_converted.png`), log `MAIN\verify\handtest_2026-10-22a\sc3netmod.log`: `bv: edit: run axis 0 from
(51,37), 13 column(s) left to the stock tiler: avenue / boulevard arm shorter than 2`, then every piece of the run (the
1-column T box 21928..21930 at x 63 included) `no longer in a run -> stock retile`.

## Cause (twin reproduces the log)
The stub is a 2x1 road (x 54..55, z 36) beside the boulevard x 51..63 z 37..39, 3 columns in from the x 51 end. Stock
draws it as the U. bvx_spans reads the 2 columns as an avenue arm 1 cell long and refused with "arm shorter than 2"
without naming an end, so the ragged-end fallback (img12) never tried that end and the whole run went stock. The log
agrees: while the owner's stub was 2 deep the run converted (`41 cell(s)`), at 1 deep it was refused. Twin: 2x1 stub
refused, 2x2 converts with 41 cells.

## Fix
1. A BAD ARM of a 2- / 3-column span (shorter than 2, or road beside it) names the run end nearer to the span
   (`bvx_spans(..., bad_e)`, twin `bvx.spans()` third value), so `bv_run_fb` cuts that end: its columns, the stub's
   included, stay stock (up to BV_RAG_MAX = 12 columns), the run ends on a plain column with the median nose, the rest
   converts. Log: `ragged end(s), 0 column(s) at +s and 5 at -s left to the stock tiler: avenue / boulevard arm shorter
   than 2`.
2. `bv_run_fb`: up to 4 rounds, each cut starting from the current cut (was 2 rounds from 1). Needed when both ends
   have a stub.
3. `bv_run1`: a ragged end on a column with road beside it is refused before the spans (same test as before, earlier),
   so a span further in is not read as the other end's refusal first.
Still whole-run: road touching the run, road 4+ wide, the AVL program rule (an avenue arm that would stay two-way).
The 1x1 stub was whole-run in the first pass of this round; owner call 2026-10-22 made it end-only too, with the
Protected guard below.
Middle: a bad arm more than 12 columns from both ends cannot be cut off; round 3 (owner yes, 2026-10-22) splits the
run there.

## Offline
| check | result |
|---|---|
| twin: 2x1 stub 3 in (either side), 2x1 stub near the +s end, 2-wide arm with road beside it | ragged, 5 / 5 / 4 / 5 columns stock, rest converts |
| twin: stubs near both ends | ragged both ends (4 + 5), 4 columns convert |
| twin: 2x1 stub 11+ columns from both ends, run of 8 with a stub 3 in, 1x1 stub | whole run refused (as designed) |
| twin: 2x2 stub (a real avenue arm) | converts, 41 cells (unchanged) |
| 16 shipped cities, before vs after (boulevard.runs) | 0 runs change |
| `bvx.py check --tiler` | 0 failures |
| C build (`build_mod.ps1`, all 7 mods + mods_launch from main 4f780c5 + this change) | no warnings |

## In game (tree Simcity_stock_avx32, inst_avx32, lab copies of lab.sc3)
Sheet `MAIN verify\avx32\owner_shots\img16_sheet.png` (frames `img16_*.png` beside it).

| case | result |
|---|---|
| A owner order: stub, crossing road, the three rows | `ragged end(s) ... 5 at -s: avenue / boulevard arm shorter than 2`, columns 57..64 written (24 cells): nose 20702 at 57, T box 21928 / 21929 / 21930 at 64; 52..56 stock with the U (11203 at (55,38) / (56,38)) |
| B other order: crossing, rows (full boulevard 53..64, 36 written), stub last | same grid as A |
| undo: stub drawn while paused, then sc3undo | `UNDO> entry 1 (road): 82 op(s), 0 failed`, grid 49..66 x 36..45 identical to before the stub |
| save (sc3undo TEST save = the game's Save) | `28 variant tile(s) written as base` |
| reload | `all 28 variant tiles restored`, BV load pass decides the same ragged run, 0 written; grid identical |
| the same save without sc3netmod (inst_avx32_nomod) | stock ids only (11204 / 29 / 43 / 39 / 11203 / 11225), roads joined |
| 1x1 stub 3 columns from the -s end (labJ) | whole run stock: `road beside the boulevard is not a straight single road` (kept whole-run on purpose, see Fix), T box gone too (`img16_C1_1x1_stub_whole_run.png`) |
| demolish that stub | full boulevard back, T box 21928..21930 at 64, `36 written` |
| 2x1 stub next to the T end (x 61..62, z 38) | `ragged end(s), 4 column(s) at +s ...: arm shorter than 2`: 61..64 stock with the crossing (stock T 39 / 43), 53..60 convert (`img16_D1_2x1_stub_at_T_end.png`) |

In my drags the middle row overshoots one cell past x 52 (a 1-cell stub at (51,40)), so case B's full boulevard already
had a 1-column ragged -s end (existing img12 fallback). Traps: the camera zoom call returned `system error` twice (once
after a rotation, once on a save that loads at zoom 2); the first hung the game (my PID, killed). Note for reading
frames: stock 11204 / 29 / 11204 also draws a tree median, so a stock stretch is told from a boulevard by its junction
paving and missing nose, not by trees.

## img16 round 2 (owner call 2026-10-22): Protected guard, 1x1 stub end-only, revert before write
1. **Protected guard** (`bv_prot`, twin `runs(protected=...)`): a cell whose ROAD piece is Protected
   (`FUN_1001a7f7(1, id)`: ROAD_GRND_Protected.txt = level crossings 67 / 69, road x highway 11258, tunnel mouths 63 / 64,
   bridges 81..88 / 11265.., plus netpack variants of those and template pieces) is never a boulevard cell. A rail line
   across a boulevard splits it into two runs, each with a 1-column ragged end beside the crossing; the crossing stays.
   Without it, the first pass of this round converted a London run over crossings 69 (x 104..109 z 224..226).
2. **1x1 stub end-only**: the 1-column "not a straight single road" refusal names the nearer end (like the 2x1).
3. **Revert before write** (`bv_pass` = `bv_decide` keep-only, reverts, re-read, `bv_decide` write). Found in game: a
   rail across the run, then a road edit: BV wrote 53..58, then reverted 59 / 61..64 with single-cell rect retiles, and a
   read 2 s later had 55..58 back as stock 11204 / 29 until the next edit rewrote them (`12 written`). With the new order
   the same edit leaves 53..58 converted at once; the re-read after the reverts found all 18 of those cells changed
   (`18 written`), so the revert retiles do reach the run's own cells.

| check | result |
|---|---|
| twin: 1x1 stub 3 in | ragged, 4 columns stock, rest converts |
| twin: rail crossing at column 55 of 40..69 / at column 41 | two boulevards 41..53 + 57..69 / one 43..69, crossing cells never written |
| 16 shipped cities with their Protected cells | 0 converting runs before and after (refused-run lists shorter in Berlin, Frankfurt, London, Moscow: columns over Protected pieces are no longer runs) |
| `bvx.py check --tiler` | 0 failures |
| C build | no warnings |

In game (final DLL unless noted):

| case | result |
|---|---|
| 1x1 stub at (55,38), full run 52..64 (guard DLL) | `ragged ... 4 at -s: road beside the boulevard is not a straight single road`, 56..64 convert with the T box |
| final DLL: owner layout (2x1 first) | 57..64 convert, T box kept (as round 1) |
| final DLL: 1x1 at (56,38) after demolishing the 2x1 | 57..64 convert (5 cut), then 1x1 at (55,38): 56..64 |
| rail across the boulevard at x 60 (rail tool, no road pass) | game places level crossings 69 at (60,39..41) over the BV pieces |
| then a road edit nearby | BV: 59 + 61..64 reverted, 53..58 converted with the nose 20702 at 58, crossing 69 intact |
| rail drawn while paused, then undo | `UNDO> entry 1 (rail): 14 op(s), 0 failed`, grid identical |
| 1x1 stub drawn while paused on the 8-column run, then undo | whole run stock (cutting 4 leaves 3 < 4), undo 51 ops 0 failed, grid identical |
| save, reload | 22 variant tiles saved / restored, BV load pass same decision, 0 written, grid identical |
| the same save without sc3netmod | stock pieces, crossings 69 intact |

A rail drawn over a boulevard does not fire a ROAD retile pass, so BV re-decides at the next road edit near it; until
then the crossing cells are the game's 69 between unchanged boulevard pieces (no nose).

## img16 round 3 (owner yes 2026-10-22): a bad arm in the middle splits the run
Rule (`bv_parts`, twin `runs()` segs): a run the end cuts cannot save, whose first refusal is a bad arm (2x1 / wider
span too short or with road beside it, or a 1x1 side road), is split at the arm's columns. Each side is a run of its own
(its base cut = the columns from the arm on, so the split ends are ragged with a median nose), tried with the end-cut
fallback the same way, and split again if it has its own bad arm (at most 16 pieces per run). Sides shorter than 4
columns stay stock. The arm's own columns always stay stock. The bad arm's columns come from `bv_run1` (`p->bja / bjb`).
`bv_takes` (AVX's view of what BV builds) uses the same `bv_parts`.

| check | result |
|---|---|
| twin: 2x1 stub mid of 45..70 | 45..55 + 58..70 convert, 56..57 stock |
| twin: 2x1 / 1x1 stub mid of 40..75 with a crossing road at 48 | 40..55 (junction at 48) + 58..75 / 40..56 + 58..75 |
| twin: two stubs in 40..95 | three boulevards |
| twin: stubs 12 / 14 columns in on 51..90 (were whole-run) | split, both sides convert |
| twin: all end-cut cases of rounds 1 / 2 | unchanged |
| 16 shipped cities (with Protected cells) | run lists identical to round 2, 0 converting runs |
| `bvx.py check --tiler` | 0 failures |
| C build | no warnings |

In game (zoom 2, `--alt 84` places drags on the exact cells; boulevard x 40..72 z 39..41, crossing roads at x 46 and
x 66, 2x1 stub at x 55..56 z 38):

| case | result |
|---|---|
| stub drawn first, then crossings, then the three rows | `split at a bad arm, columns 41..54 convert` + `columns 57..70 convert`: junction 20710 / 20711 at 46 and at 66, noses 20702 at 54 and 57, 55..56 stock with the U |
| paused: demolish the stub cell by cell, then undo twice | after one cell (a 1x1 left at 56): split 41..55 + 57..70; after both: one boulevard 41..70 (90 cells); two undos 149 ops each, 0 failed, grid identical to the split state |
| running: demolish the stub, then draw it again (stub last) | full boulevard 41..70, then the same split; grid identical to the stub-first grid |
| save, reload | 88 variant tiles saved / restored, the load pass makes the same split, 0 written, grid identical |
| the same save without sc3netmod | stock ids only (29 / 39 / 43 / 11203 / 11204 / 11225) |
| final DLL, owner layout of round 1 (zoom 3) | unchanged: 57..64 convert with the T box |
