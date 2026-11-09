# avdiamond: avenues under an elevated highway beside its diamond ramps (group D, round 2026-11-09)

Brief: `re/sessions/ROUND_2026-11-09_avdiamond.md`. Causes per case and the design: `re/sessions/STATUS_avdiamond.md`.
Orchestrator decisions (2026-11-09): go D1 -> D2 -> D3; half diamond (598) gets the median opening; crossing rows
split a segment only when it touches a ramp, with 0 changed boxes outside the ramp cases; D4 (hwt over the crossing at
(608,134)) after D3, find out first which came first; (584,108) out of scope.

## D1: ramp junction boxes (AVX block AVDIAMOND, off: `SC3NETMOD_AVDIAMOND=0`)

What changed (`re/harness/src/sc3netmod_avx.c`, twin `re/tools/netmod/avjunc_rule.py`):
- The ground ends of the stock on-ramp strips are arms on their ground side (15138 / 15139 at state 0: x-, 15140 / 15141:
  z-). A box edge facing an off-ramp (15138 / 15140) has mode I (both ramp lanes into the box). A box edge facing an
  on-ramp (15139 / 15141) keeps T (its out lane is the ramp's only entry). Validation reads an off-ramp as O. Until now
  AVX gave every ramp id "unknown arms" (-1), so a T / X beside a ramp read "no arm" and no box formed.
- A segment walk whose positions touch a ramp on their outside is cut at every crossing row (both cells an avcore
  crossing base 15098 / 11258 / 69 / 67). Under the highway the crossing between the two ramp junctions becomes its own
  band, ending on two boxes. A walk with no ramp is the old segment (same limit, same refusals).
- Package `avenue_diamond` (`re/tools/netmod/avdiamond_build.py`, `examples/avenue_diamond`): 7 box cells with an
  off-ramp edge, ids 20850..20856 (base 43, saved as 43), 60 lanes, curve shapes 25500..25507, art = avjunc's box
  painter for the same outline (AAAI, AAII). Table lines `avxm` + `avlj` (avenue edges only; the ramp edge is a road).

| check | result |
|---|---|
| offline diff, AVX twin with / without the change, 15 shipped cities + owner's Big One (`py -3.12 -m netmod.avdiamond_diff <save>`) | 135 changed boxes, all on a segment walk that touches a ramp or beside a ramp cell; **0 changed boxes or noses outside the ramp cases** (`verify/avdiamond/data/offline_diff.txt`, local) |
| package build check (`avdiamond_build check`, ENGLISH + English-UK) | PASSED |
| selfblock | 0 of 7 specs |
| `netpack validate --tree dev/avdiamond/tree` | OK, 0 errors (merge with 18 installed packages) |
| off-ramp lanes (64 / 174 at the shared edge) meet box entry nodes by bucket (n + 16) / 72 | 7 pieces x 2 languages, every lane lands on a node with an out edge |
| `avlanes.check` box N / S edges vs avcore's 21700, 4 states, 2 languages | 56 checks, 0 problems (a deliberately reversed half gives 2 problems, so the check is not vacuous) |

### In game, owner's Big One (`dev/avdiamond/tree`, `-City BigOne_owner.sc3`)

Game A (D1 on): `avx: load run: 36 junction box(es)` (31 before; the twin also gives 36). `avl` bands one-way 32
(27 before), two-way 18 (23 before). New one-way bands:

    band along z from (584,113) rows 0..1 -> one-way (ends: join or edge / join or edge)     crossing under the highway
    band along z from (584,118) rows 0..29 -> one-way (ends: join or edge / corner)
    band along x from (586,148) rows 0..7 -> one-way (ends: corner / join or edge)           beyond that corner
    band along x from (556,64) rows 0..1 / (560,64) rows 0..4 -> one-way                     another ramp T, x 555..564

Live grid at x 584 / 585: 111 two-way link noses, 112 box 20852.2 / 20831.0 (N arm two-way: rail row 110 stays two-way,
its north end is the out-of-scope (584,108) knot), 113 / 114 one-way crossings 21716 / 21717, 115 box 20805.2 /
20850.0 (off-ramp edge I), 116 one-way link noses, 117 nose 20800, 118.. 21700. Still two-way, as designed: the 598
crossing (forward end (598,115) is the D2 corner), (600,117), (604,119), (605,131), (608,132), (608,134).

**A regression found and fixed on the way: avcore's one-way slope variants.** The 584 band holds a slope row (31 at
(584,122) -> 21718.2). Cars (hwcars_tracks, box 580..600 x 106..150, 120 s):

| run | road cars | removed at (584,122) | steps (584,122) -> (584,121) | car height across (584,122) |
|---|---|---|---|---|
| A: D1 on, old lanekit | 375 | 229 | 0 | 23552 -> 23043 |
| B: `SC3NETMOD_AVDIAMOND=0` (band stock two-way, 31.2) | 314 | 0 | 19 | 24064 -> 23552 |
| C: D1 on, fixed lanekit, after save + reload | 265 | 0 | 38 | (as B) |

Cause: `lanekit.rotate` turned the record's corner altitudes (alt) with the corners. Stock never does. Every stock slope
record holds the same alt in every state (31 and 32 in states 0 / 2, 11201 and 11202 in 0..3). So avcore's 21718..21725
and boulevard_slopes' 27100.. carried a rotated alt in states 1..3, and cars on them ran 512 below the next cell's
nodes and were dropped at its edge. Fix: `rotate` keeps alt (`re/tools/netmod/lanekit.py`). Proof:
rotate(state 0) now reproduces 29 of 29 stock records of 14 pieces byte for byte (the old rotate missed 8, every rotated
slope state). `lanekit selftest` and `avlanes selftest` pass. This changes the compiled lanes of 2 packages
(avenue_lanes 8 slope variants, boulevard_slopes 8). **Release step: reinstall any package in stage/src (netpack
rebuilds the whole overlay with the fixed lanekit).**

Cars per half, game C (road cars, class 0, steps along x 584 / 585 rows 110..148):

| half | rule | steps with the rule | steps against |
|---|---|---|---|
| x 584 | N | 627 | 11, all in rows 110..112: the two-way rail row, the two-way link row 111 and box 112's two-way N arm |
| x 585 | S | 153 | 5, all in rows 111..112 (same two-way rows) |

`avl_tracks_an` (one-way cells 21700..21749): 26 WRONG lines, every one a subway train (class 2, y 24036 / 24548) under
the avenue, or one car on the highway deck (y 39040). Road cars against a one-way cell's direction: 0.
Ramp movements in 120 s: box (584,115) -> on-ramp SW 26, box (585,112) -> on-ramp NE 5, off-ramp SE -> box (585,115) 2,
off-ramp NW -> box (584,112) 0 (not used in the sample), median opening at 115 584 -> 585 19, at 112 584 -> 585 9.

Save + reload: save `944 variant tile(s) written as base`; reload `load: all 944 variant tiles restored`, the same 36
boxes and the same 32 one-way bands, live grid of 578..612 x 104..150 identical to game A.

No sc3netmod (the other 10 mods on: a 1024 city needs sc3bigcity; `SC3MODS_OFF=1` exits on this map): the city loads
and runs, 0 variant ids in 578..612 x 104..150, the live grid equals the saved base tiles. Against the owner's
ORIGINAL save, 8 cells in that box differ, by AVX's existing base rule (a box cell saves as 43 / 39 by its outline, a
link nose as 11204; 3,133 of 4,992 existing box cells in the shipped cities already save as another stock id than the
one they replaced):
(584,111) / (585,111) / (584,116) / (585,116) link T 39 -> 11204 (the link rows save without the T), (584,112) and
(584,115) 43.0 -> 43.2, (598,112) 39.0 -> 43.2 and (599,112) 11204.3 -> 39.0 (the median opening saves as an X + T).

Pictures (`MAIN\verify\avdiamond\owner_shots\`, not in git): `d1_584_diamond_z4.png`, `d1_584_diamond_z4_rot2.png`
(the 584 diamond with D1, both sides; cars in the box under the deck), `d1_584_nomod_z4.png` (the same view without
sc3netmod: stock yellow centre line).

Not done in D1: English-UK in game (offline only, known limitation); the 598 crossing (needs D2).

## D2a: the corner knot with an off-ramp, (598..600,116..118)

Shape: the z avenue 598/599 turns into the x avenue z 117/118 through a corner whose inner bend (599,117) and the half
beside it (599,118) are linked T's (avpaint's corner + T). The T row is (600,117)/(600,118), its road the off-ramp 15140
at (600,119). On the corner's z side there is no band, only a link row (116), the ramp T (115) and the crossing
(113/114). The x avenue has no straight pair at all (T row, 11258 crossing 601/602, on-ramp T 603, corner 604/605).

What changed:
- AVX, ramp walks only (twin `avjunc_rule.corner_trim`, `cross_pair`; C `avd_corner_trim`, `avd_cross_pair`): a crossing
  row seeds a walk too (kept only when it touches a ramp); a walk part that runs into a corner block (a position with an
  11203) stops before the block's end row, and also before a corner + T's T row when the row before the bend holds no
  straight half; the block cells get no nose. New boxes: (598,115) (on-ramp T, median opening at (599,115)) and
  (603,117)/(603,118) (on-ramp T on the x avenue). Existing box pieces cover them.
- AVL (`sc3netmod_avl.c`, switch SC3NETMOD_AVDIAMOND): a corner + T's corner side may be a junction row: two avlj pieces
  (AVX's link noses at (598,116)/(599,116)) whose letters carry the corner band's directions (`avd_ct_joinrow`). The band
  beyond the T row then decides the block alone and writes it (`avl_corner_block`, the old corner writer moved into a
  function); the linked inner bend answers avl_dir with the join cell's travel, so AVX reads its arm one-way. A road arm
  of the T row that is an off-ramp gets mode I. Missing corner + T pieces are logged (`avl: corner + T: no avlt piece`).
- Package avenue_diamond: `avlt 20857 IAAI TIIO` (base 43, art = avjunc box painter IAAI), the T row cell with the
  off-ramp below it. The other three corner + T cells reuse avpaint's 21736 / 21737 / 21738.

| check | result |
|---|---|
| offline diff, 15 shipped cities + owner save | 133 changed boxes on ramp walks, **0 outside the ramp cases**; twin 38 boxes on the owner save = game |
| package check / selfblock / avlanes | PASSED, 0 of 8, unchanged ids 20850..20856 |
| seams in 597..604 x 111..119, live pieces, `avlanes.check` | ENGLISH 0 problems in 80 checks; English-UK 24, every one where a right-hand piece meets a stock two-way piece (the accepted UK limitation) |
| owner save, load | 38 boxes, 34 one-way bands: new `(598,113) rows 0..1 -> one-way (join / join)`, `(601,117) rows 0..1 -> one-way (T row of a corner + T / join)` |
| live cells | 598 / 599: 112 box, 113 / 114 21716 / 21717, 115 box 20805 / 20806, 116 one-way link noses 21773 / 21772, 117 21700.1 + 21736.2, 118 21701.2 + 21737.1; T row 21738.3 / 20857.0; 601 / 602 21715 / 21714; 603 box 20829 / 20831 (E arms two-way: the corner 604 / 605 is in the D4 chain) |
| save + reload | save 964 variant tiles; reload `all 964 restored`, same one-way band list, live grid 578..612 x 104..150 identical |
| without sc3netmod | 0 variant ids, grid = saved bases; corner + T cells keep their stock bases; 14 cells differ from the original save, all AVX's box / link-row base rule (D1's 8 plus (598,115), (598,116), (599,115), (599,116), (603,117), (603,118)) |
| cars, 120 s, box 594..607 x 106..124 | **no ground road car entered the knot**: every class-0 sample there is at highway height (y 35..36 k), the rest subway trains. Direction on these cells is shown offline only (seams above) |

Pictures: `d2_598_knot_z4.png`, `d2_598_knot_z4_rot2.png`.

Still two-way, by the chain rule: z 604/605 (120..130) -> tight corner (605,131) -> x 131/132 -> corner + T (608,132) ->
row 133 -> (608,134) with no road. D2b (the 603..605 corner with a linked inner bend) and D3 (the tight corner) are
both in that chain, so on the owner's save neither can convert before D4 is solved.
