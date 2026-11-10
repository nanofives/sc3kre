# avends: the remaining two-way avenue ends on the owner's Big One (groups B, C, A, E, F; round 2026-11-09)

Brief: `re/sessions/ROUND_2026-11-09_avends.md`. Causes per group and the designs: `re/sessions/STATUS_avends.md`.
Orchestrator decisions (2026-11-09): order B1, B2, E, A1, A2; (584,108) back in scope as group F (owner: "a junction
that turns 3 into two"), after A2, design first; B2's piece on base 29 so the save keeps the 29; the twin reads the save's
variant list for every group's offline diff; E lists every stub-T box its rule makes in the shipped cities.

Ids: the brief's 20900..20999 is taken in the installed tables (boulevard_junctions 20900..20905 / 20910..20949,
diagonal_boulevard 20950..). Free and unreserved: **piece ids 22000..22099**. Curve shapes: **26500..26999** (26000..26209
are wall-lighting twin piece ids, avdiamond holds the 25500..25999 shape grant; 26500.. is free both as shape keys and as
ids in the installed tables).

Package `avenue_ends` (`re/tools/netmod/avends_build.py`, `examples/avenue_ends`, piece list `avends_pieces.json`).
Offline twin: `avjunc_rule.city_layer_saved` (new) reads a save as a reload sees it: saved tiles + the save's variant
list (section 0x4E56) with the installed tables' piece classes (avxm box, avxn nose / link, avxk corner, avl* family;
AVP twins read as their base). Diff: `py -3.12 -m netmod.avends_diff --switch <NAME> --expect x0,z0,x1,z1 [save ...]`
(15 shipped cities + extra saves; shipped cities hold no variant list, so for them it is the stock grid). Live seams:
`SC3_PID=<pid> py -3.12 -m netmod.avends_seams x0,z0,x1,z1` (avlanes.check on every join that touches a variant, tree
overlay lane data, ENGLISH + English-UK).

## Group C: nothing to build

The ramp T's beside 11258 at (555,64) / (558,64) already convert on this save with D1 (`(556,64) rows 0..1`,
`(560,64) rows 0..4 -> one-way`, live boxes 20831 / 20850 / 20806).

## B1: avenue T avenue next to a saved link row, (545..548,62..65) (AVX block AVTEE, off: `SC3NETMOD_AVTEE=0`)

Cause (debug line, `SC3NETMOD_AVXDBG=1`): `avx: dbg drop: box at (547,64) cell (547,64) side W mode T vs (546,64)
21775.2 mode O`. The owner's save holds AVX two-way link noses 21775 / 21776 at (546,64) / (546,65) (saved as 11204).
AVX makes the 2 x 2 T box from the stem's walk first (the through avenue's box of the same size loses the tie). The stem
box looks W for a crossing-avenue span: `avx_make` wants a straight pair within 3 cells, `avx_pair` skips link noses, then
box 545 and an empty cell: no span, so the W edge is a road arm (T) against the nose's one-way O, and validation drops
the box. With those saved variants removed (a lab copy) the box forms from existing pieces.

Change (`sc3netmod_avx.c` avt_link_row, twin `avjunc_rule.link_row`): the span test also accepts a row whose two cells
are our link noses. A version that also accepted two stock T 39 linked across the median changed 463 boxes / noses in
the shipped cities and was dropped. No new piece.

| check | result |
|---|---|
| offline diff, saved variants read, 15 shipped cities + owner save | shipped: 0 changes in every city; owner save: 1 box + 9 noses changed, all in 543..551 x 60..66; **0 outside** |
| owner save, load | `stats: avl bands converted=36, refused=14` with B1 alone; new `(547,61) rows 0..0 -> one-way`, `(550,64) rows 0..3 -> one-way` |
| live cells | box 20807.3 / 20807.0 / 20808.1 / 20809.1 at (547..548,64..65), link noses 21772.1 / 21773.3 on row 63 (one-way), 21774.2 / 21774.0 at 546 (one-way link noses, both ends), noses 20800 on row 62, 21700 beyond |
| seams, ENGLISH, 543..552 x 59..66 | 40 seams, 1 line: (547,64)S 20807.3 / 20808.1 "in at (80,255) has no out lane": an entry node of avjunc's existing box piece that the cell beside it does not feed (an unused entry; no exit without an entry). English-UK: 21, every one where a right-hand piece meets a stock / hwave two-way piece (accepted limitation) |

## B2: corner + T whose linked half is a plain road, (567..569,31..32) (AVL block AVCT29, off: `SC3NETMOD_AVCT29=0`)

Cause: avpaint's own corner + T (converted 2026-10-28). In the newest save the stock tiler left a 29.0 at (568,32)
where the linked half (a T 39) stood; the inner bend (568,31) 39.2 keeps its arm toward it, the 29 has none back.
`avl_corner_at` refused the block ("the cells beside the inner bend are not 11204 halves"), so (567,23), (570,31) and,
through the corner (581..582,31..32), (581,33) stayed two-way.

Change (`sc3netmod_avl.c` avl_corner_at): with a linked inner bend, a 29 in the linked-half position whose arms are the
half's own (no arm back) is read as the linked half. Piece **22000** (avlt `IICA CICO`, base 29, lanes by avjunc's
box-cell model = the one-way half, art by avjunc's box painter for that outline): avenue_lanes' 21737 turned one state,
on base 29, so the cell saves as the 29 the owner has. AVL logged the letters it needed before the piece existed:
`no avlt piece for (568,32) 29.0 (base 29) outline IICA modes CICO`.

| check | result |
|---|---|
| package | `netpack validate --tree dev/avends/tree`: OK, 0 errors (merge with 19 installed packages); selfblock 0 of 1 |
| owner save, load (B1 + B2) | `stats: avl bands converted=39, refused=11` (34 / 16 before); new `(567,23) rows 0..7 -> one-way (join or edge / corner + T)`, `(570,31) rows 0..10 -> one-way (T row of a corner + T / corner)`, `(581,33) rows 0..0 -> one-way (corner / highway ground row)` |
| live cells | (567,31) 21700.1, (568,31) 21736.2, (567,32) 21701.2, **(568,32) 22000.0**, T row 21738.3 / 21739.1, rows 31 / 32 21700.2 / 21700.0, corner (581..582,31..32) 21768.3 / 21726.0 / 21700.3 |
| seams, ENGLISH, 565..585 x 27..35 | 69 seams, **0 problems**; English-UK 16, every one where a right-hand piece meets a stock / hwave two-way piece |

## B1 + B2 in game (owner's Big One, `dev/avends/tree`, own PIDs 2972, 9140, 4456, 3560, 16656, 3536)

| check | result |
|---|---|
| routed ground trips, 150 s, box 540..590 x 25..70 (`avdiamond_trips.py`, mask 21 = road; the pop order runs against travel, as calibrated in group D) | every half only in its rule direction, **0 steps against**: 547 N 242, 548 S 1,111, row 64 E 2,059, row 65 W 3,348, 567 N 2,058, 568 S 2,126, row 31 E 4,752, row 32 W 6,170, 581 N 454, 582 S 363. Mask 8 runs both ways on four of them: subway tiles lie under every one (8 / 16 / 10 / 3 tiles) |
| save + reload | save (autosave of the B1 + B2 run): `1033 variant tile(s) written as base`; reload: `all 1033 variant tiles restored`, `converted=39, refused=11`, the 50 band lines identical, live grid 540..560 x 55..70 and 560..590 x 20..40 identical (298 cells, 0 differ) |
| saved bases vs the owner's original, same windows | (568,32) stays 29.0. 11 cells differ, all by the existing base rules: AVX box / link cells save by outline (547 / 548 x 63..65: 39 -> 11204 on the link row, 39 -> 43 / 11204 -> 39 in the box), D1's boxes at 555 / 558, avpaint's T row cell (569,32) 43.0 -> 43.1 |
| without sc3netmod (the other mods on, `SC3MODS_LIST` without sc3netmod / sc3autosave) | 298 cells read, 0 variant ids, live grid = saved bases |
| both switches off (`SC3NETMOD_AVTEE=0 SC3NETMOD_AVCT29=0`) | `converted=34, refused=16`, as before the change |
| one crash | the first reload (PID 9140) faulted at SIMCITY.DLL+0x1783 (FUN_10001752, framework vtable calls) about 9 s in, after every sc3netmod load pass had finished; the same save loaded cleanly twice afterwards. Logs kept in `dev/avends/inst/crash1/`. Not reproduced, not traced |

Pictures (`MAIN\verify\avends\owner_shots\`, not in git): `b1_547_64_z4_rot3.png` (the T, unobstructed; rot0..2 are
mostly hidden by towers), `b2_568_31_z4_rot0.png`, `b2_568_31_z4_rot2.png`. Knot pictures for group F:
`knot_584_108_z4_rot0..3.png`.

Not done: English-UK in game (offline only, the accepted limitation).

## E: a one-cell dead-end stub T'd into an avenue half, (613..615,192) (AVX block AVSTUB, off: `SC3NETMOD_AVSTUB=0`)

Cause: the stock road dead end 11225 was not in AVX's stock arm table (arms "unknown"), so the half T'd into it made
no box and avcore ended both bands on the stock T (614,192) 39.2. Change (`sc3netmod_avx.c` avx_stock_arms, twin
`avjunc_rule.STUB_MASK`): 11225 is a road arm on its one side (props 310 = 0x80008000 measured with lanekit: S at state
0; the saved cells agree, 11225.1 connects to its W). No new piece: the box cells use avjunc's 20805 / 20806.

Every stub-T box the rule makes in the 15 shipped cities + the owner save (offline diff, saved variants read; pieces
checked against the installed avxm lines; in game, see the shipped-city batch below):
| city | box cells | pieces | in game |
|---|---|---|---|
| owner's Big One | (613,192) / (614,192), between slope rows 191 / 193 | 20806.2 / 20805.0 | as designed |
| London | (238,49) / (239,49), stub 11225.3 at (237,49) | 20805.2 / 20806.0 | as designed, noses one-way |
| Sacramento | (167,139) / (168,139), a band END with road 29 W and stub 11225.1 E | 20813.3 / (20812.3) | **(168,139) stays stock 39.3: the game's piece writer refuses that put** (below) |

| check (owner save) | result |
|---|---|
| load | `converted=41, refused=9` (39 / 11 with B only); `(613,176) rows 0..15 -> one-way (join / join)`, `(613,193) rows 0..36 -> one-way (join / U-turn)` |
| seams, ENGLISH, 610..618 x 186..198 | 38 seams, 0 problems (English-UK 4: the box's road edge against the stock stub) |
| routed trips, 150 s | 613 N 7,125 / 0 against, 614 S 7,105 / 0 against; no trip used the stub cell in that window |
| save + reload | 1,143 variants saved and restored, band lines and live window (79 cells) identical |

## A1: U-turn end with a road T on the last row, (560..562,11..13); A2: U-turn pair whose bend carries a road arm, (485,18..19) (AVX + AVL block AVUEND, off: `SC3NETMOD_AVUEND=0`)

A1 cause: AVX's segment walk took the U-turn pair in and refused the segment ("piece 11203 in the segment"), so no box
formed at the T (561,12) and AVL refused the end. Change: the walk stops before a U-turn pair (AVENUE_LANES.md 3's
four end patterns, 11203 or 21701) and marks it as avcore's block (`cblk`, as D2b's corner blocks: a band arm of the
box beside it, '?' in validation, no nose); twin `avjunc_rule.uturn_stop`. AVL: a band whose end is a join (the nose
row 562) with only join rows (the box 561) and then the U-turn pair past it gets the new end kind 9 "join + U-turn"
(`avu_uturn_past`, up to 6 join rows): it writes the U-turn 21701 with the band, and the U-turn cells answer avl_dir
with their halves' travel so AVX's post pass keeps the box arm toward them one-way. No new piece (box = 20805 / 20806).

A2 cause: (485,19) is a T 39.1 = the U-turn bend 11203.1 plus an E arm into the diagonal road 35, so AVL did not read
a U-turn pair. Change: new end kind 10 "U-turn with a road" (`avu_road_uturn`): one cell 11203 at its end state, the
other a 39 whose arms are the bend's plus exactly one road arm (not toward the band) with a road beyond. The 11203 ->
21701, the 39 -> an `avlt` piece found by its letters: **22001** (avlt `ACAI TCOI`, base 39: U-turn traffic in from
the other U-turn cell, out to the band, the road two-way; lanes and art by avjunc's box-cell model and painter).

AVUEND's offline diff (saved variants read) also adds a box in 4 shipped cities, each the A1 shape (a road / ramp
junction on the rows just before a stock U-turn pair), all with existing pieces and all as designed in game:
| city | box | beside the U-turn at |
|---|---|---|
| Craterville | (189,103..104), road S | (190,103..104) |
| London | (185,169..170), road N | (184,169..170) |
| Madrid | (217,185..186), road N | (218,185..186) |
| Seoul | (224..225,107), a ramp X under the highway, link row 106 | (224..225,105) |

| check (owner save) | result |
|---|---|
| package | 22000 + 22001: `netpack validate` OK, 0 errors; selfblock 0 of 2 |
| load | `converted=43, refused=7`; `(563,11) rows 0..1 -> one-way (join + U-turn / join)`, `(484,18) rows 0..0 -> one-way (join / U-turn with a road)` |
| live cells | A1: U-turn 21701.3 / 21701.2 at 560, box 20806.3 / 20805.1 at 561, noses 20801 / 20802 at 562. A2: (485,18) 21701.0, (485,19) 22001.1, noses at 483 one-way |
| seams, ENGLISH | A2 window 21 seams, 0 problems; A1 window 42 seams, 1 line at (568,11)S inside the existing 567..568 T box (avjunc's 20807 / 20808: the same unfed entry node as in B1), none at the new cells |
| routed trips, 150 s | every half in its rule direction, 0 against: A1 row 11 E 2,273, row 12 W 3,221, U-turn 12 -> 11 373; A2 row 18 E 1,613, row 19 W 1,666, U-turn 18 -> 19 321. The side road (561,13) and the diagonal (486,19) carry trips both ways. Mask 8 both ways on row 19: 6 subway tiles under it |
| save + reload | 1,159 variants saved and restored, band lines and both live windows (99 cells) identical; saved bases: A2 cells unchanged (11203.0 / 39.1), A1 / E box cells by AVX's outline rule |
| without sc3netmod | 178 cells in the A / E windows, 0 variant ids, live grid = saved bases |
| AVUEND and AVSTUB off | `converted=39, refused=11` (the B-only result) |

## Shipped cities in game (all switches on, test-slot batch, own PIDs 11080, 19124, 3424, 20616, 19184)

London, Sacramento, Craterville, Madrid and Seoul loaded; every new box above is live as designed except Sacramento's
(168,139). With `SC3NETMOD_AVXDBG=1` the write loop logs puts that do not take:
`avx: dbg put: (168,139) wanted 20812.3, reads 39.3 after the put (was 39.3)`. The same happens on that map to three
cells that are NOT avends cases: (153,157) 20813.2, (182,194) nose 20801.0 / 20810.0, (120,196) nose 20802.3 / 20811.3.
The writer (SIMNTWRK `sc3_ntwrk_write_piece` 0x10008919) writes nothing when its factory call `vt+0x48(&occ,
0xc14f8955, id, state)` returns 0 [CONFIRMED @ 0x10008919]; why the factory refuses these (piece, state) pairs is
[UNCERTAIN] (20813.3 is accepted one cell away). Existing AVX behaviour, not caused by avends; on the owner's Big One
no put fails. Effect at Sacramento (167..168,139): one box cell one-way, the other stock 39.3 (its band still
converts).

Pictures: `e_614_192_z4_rot0.png`, `e_614_192_z4_rot2.png`, `a1_561_11_z4_rot0.png`, `a1_561_11_z4_rot2.png`,
`a2_485_18_z4_rot0.png`, `a2_485_18_z4_rot2.png` (rot 0: a grid-diagonal road draws as a vertical line).
Lab trap: a frame dump requested after an autosave in the same game did not arm again (`DUMP> armed` stops) and
`rb_lab.py shot` copied the previous dump; take pictures before the first autosave or in a fresh game.

## F: the boulevard narrowing into an avenue with an avenue T, (583..586,107..109) (owner 2026-11-09: "a junction that turns 3 into two in either left or right"; design approved with both alignments)

What the knot is: a straight boulevard (20700..20702) turns into the diagonal boulevard (20950 / 20951, rows 99..106);
its end at row 106 lands on three straight columns 583..585 for three rows (107..109), the avenue goes on south on
584 / 585 (rail crossing row 110), and the x avenue z 108 / 109 leaves east from 585. The stock tiler had left it all
as T / X pieces; DBV called the end "ragged", BV refused the 3 x 3 block (bigrbt's) and a junction in an end region.

| part | change | switch | pieces |
|---|---|---|---|
| F1 | none: BV's straight narrowing (`bva 0 / 1`, 20750..20768, bvlanes' one-way lanes) is used as it is | | |
| F2a, DBV | new end kind bend-z-tee: a bend into three straight columns whose 2nd and 3rd rows past the end also carry an avenue arm on ONE side (the arm is BV's path). `sc3netmod_dbv.c` dbv_end_kind, twin `diagbv.classify_end` | `SC3NETMOD_DBVBENDT=0` | none |
| F2b, BV | a run of exactly 3 columns is accepted when one end bends into a DBV band (end type 5) and the other narrows into an avenue (type 3); the whole run is the narrowing | `SC3NETMOD_BVSHORT=0` | bva |
| F3, BV | a narrowing whose last two columns carry an avenue arm on the kept side's outer edge: those 6 cells take `bvn` pieces, the arm's first two cells BVX's noses; BVX's "box + avenue past it" end now leaves a one-sided arm to the narrowing | `SC3NETMOD_BVNT=0` | **22002..22007** (keep rows 0 / 1, arm on row 0's side, the knot's), **22008..22013** (the mirror), base 43 |
| AVL map | a load-time re-run over a small box (BV's post-AVL hook, after BV wrote the knot) cleared AVL's whole band map, so AVX's final pass read every other band as two-way: on the first load 39 boxes were demoted (group D's diamond boxes among them), 3 after a reload. Now only the whole-map load run starts from an empty map. Needed for F; changes nothing where no load re-run happens | `SC3NETMOD_AVLKEEPMAP=0` | |

Lanes (`re/tools/netmod/avends_fbuild.py`, bvlanes' own generators): column 0 of the narrowing keeps bva's lanes;
columns 1..2 are one junction box (`bvlanes.box_lanes`, avjunc's movement rule) whose W arm is the narrowing's lanes
at the end of column 0 (3 in / 3 out), E arm the avenue (2 / 2), side arm the 2-wide avenue (`bvlanes.arm_z`), plus
the lane that opens the side coming out of the avenue to 3 lanes. The +x side's third lane merges in the straight
on (3 -> 2). Curves: shapes 26520..26999 (the stock library lacks them). Art: bvx.Box per cell (the boulevard
junctions' box look). Table: `bvn <0|1> <col1 row0..2> <col2 row0..2>` (manifest `boulevard_slope_lines`; netpack and
its schema accept the line), `avlj` on the two avenue-side cells. The cell at the closed corner (22007 / 22011) has no
lane (as bvlanes' taper corners).

| check | result |
|---|---|
| DBV before / after (twin `diagbv.bands`, `avends_dbvdiff.py`, 15 shipped cities + owner save) | the shipped cities' 3 bands (Berlin 2, Moscow 1) unchanged; owner save: 1 band, its bottom end ragged -> bend-z-tee, same 32 cells; **0 other changes** |
| package | `netpack validate` OK, 0 errors (19 installed packages); selfblock 0 of 14 |
| owner save, first load | `dbv: ... 32 cell(s)` (no ragged end); `bv: load: boulevard axis 1, columns 107..109 at row -585, 11 cell(s), 11 written`; `stats: avl bands converted=50, refused=4` (the 4: the D4 chain, owner re-drag pending); boxes with a two-way arm 3 |
| new one-way bands | `(584,110) rows 0..0` (rail row, ends join / join), `(587,108) rows 0..10` (the x avenue, join / corner), `(598,110) rows 0..0` (its corner band); D's box 112 N arm one-way (20850 / 20805) |
| live cells | 107: bva 20752.1 / 20751.1 / 20750.1; 108: 22004.1 / 22003.1 / 22002.1, noses 20910.2 / 20911.0 at 586; 109: 22007.1 / 22006.1 / 22005.1; 110: 21711.1 / 21710.1; 111: 21772.1 / 21773.3 |
| seams, ENGLISH, 580..590 x 104..113 | 59 seams: 0 at any F cell; 3 at row 112 (D's ramp box against the ramp ends, the bucket hand-off group D documented). English-UK: none at F cells |
| routed trips, 150 s (mask 21) | avenue 584 N 3,240 / 0 against, 585 S 960 / 0, x avenue row 108 E 100 / 0; row 109 W: no road trip in the window. Through the box: boulevard -> row 108 E, avenue N -> boulevard, avenue N -> row 108 E seen; boulevard -> avenue S and row 109 -> box not seen in the window |
| save + reload (final build) | `save: 1199 variant tile(s) written as base`; reload `all 1199 variant tiles restored`, the same band lines, boxes with a two-way arm 3, live grid 574..600 x 96..120 identical to the first load (242 cells, 0 differ); no fault |
| saved bases | the knot's nine cells save as 43 (BV's rule: a stock game keeps the roads joined), the link row 111 as 11204 (AVX's) |
| without sc3netmod | 242 cells, 0 variant ids, live grid = saved bases |
| shipped cities in game, F switches off / on (16 saves x 2, test-slot batch, `bv: load`, `dbv: load` and `stats: avl` lines) | 15 identical; Madrid differs only in the first 10 s stats line's `cells written` (0 / 1712: logged before / after the load pass wrote), the same 208 converted / 49 refused and the same bv / dbv lines. The Europolis maps (no avenue) never print an AVL stats line, so the batch timed out on them (marked FAIL there) after recording their (empty) lines |
| every F switch off (`DBVBENDT BVSHORT BVNT AVLKEEPMAP = 0`) | `converted=43, refused=7, cells written=298`, boxes with a two-way arm 5: the pre-F result |

Pictures (zoom 4, before the first autosave): `f_knot_584_108_z4_rot0.png` .. `rot3.png` (rot 2 reads best).

## Open items

- Refused piece puts (existing AVX limitation, no whole-box revert guard for now, orchestrator 2026-11-09): on
  Sacramento the game's piece writer leaves 4 cells stock, logged with `SC3NETMOD_AVXDBG=1`: (168,139) 20812.3 (the
  avends E box, its other cell (167,139) 20813.3 is written), (153,157) 20813.2, (182,194) nose 20801.0 / 20810.0,
  (120,196) nose 20802.3 / 20811.3. Why the factory call in 0x10008919 refuses these (piece, state) pairs is
  [UNCERTAIN]. The owner's Big One has none.
- English-UK in game (offline only, the accepted limitation).
- Debug-only switches left in: `SC3NETMOD_AVXDBG=1` (AVX drops and refused puts), `SC3NETMOD_BVDBG=1` (BV runs under 6
  columns refused, with the reason). Both log only.
- F's twin: BV's twin (boulevard.py runs) does not know F2b / F3; the shipped-city check for them is the in-game on / off
  batch above. DBV's twin (diagbv.py) has F2a.
