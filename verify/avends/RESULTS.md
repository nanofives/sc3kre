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
