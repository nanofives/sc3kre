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

## D4: why the save has no road at (608,134) (read-only: hwt source + build-order lab, no hwt change)

Owner's T: hwt trumpet anchor (601,133) turn 0. (608,134) is its cell (7,1) = piece 21227 (a rewritten through-highway
cell, `hwt 21227 7 1 0 1`, saved as plain deck 15051). (608,133) = frame (7,0), not a T cell, holds a stock crossing
15098.2; (609,133..134) are outside the footprint, 15098.

Source (`re/harness/src/sc3netmod_hwt.c`):
- A NEW T (`hwt_check`) needs every through-highway cell from dx tx0-1 to tx1+1 (here -3..8) to be a plain straight
  15051 / 73 (`hwt_straight` -> `hwt_head`, lines 98..123). A road crossing 15098 there refuses the T.
- An EXISTING T (`hwt_existing`, every highway retile that reaches it and every load pass): a rewritten highway cell that
  holds any highway piece passes (`if (!c->land && v) continue; /* a rewritten highway cell, re-tiled */`, line 381),
  then every T cell is re-put with its own piece (line 393). A stock crossing 15098 there is overwritten by 21227, a
  deck with no road under it, so the road loses that cell. There is no crossing test in the file.

Lab (flattened copy of Roadless Paradise, `dev/avdiamond/tree/Cities/lab_hwt.sc3`, own PIDs 18800, 19328, 18568, 4344,
`SC3NETMOD_HWASK=0` so the T builds without the question; highways and roads by `nb_drive.py build`, no cursor):

| order | what happened |
|---|---|
| A: T first (anchor (110,60) turn 0, `hwt: load: full T ... 50 cells written`), then a road along z at x 117 (the T's dx 7) under the through highway | live, right after the drag: (117,60) 15098.2, (117,61) 15098.0, road continuous (the stock tiler replaced 21227). Saved as that. After reload, the load pass (`stats: hwt kept=1`, `hwy: load pass ... 1 written`): (117,60) 15098.2, **(117,61) 21227.0**, road cut at z 61. The same cells as the owner's (608,133) / (608,134) |
| B: road first (x 157), then the through highway over it, then the stem | live: `hwt: edit: T at anchor (150,60) turn 0 refused: the through highway must run on 6 cells right of the stem (seen from the stem), nothing past its end`; both crossings kept, no T |

**Cause: the T came first; the avenue was dragged under it afterwards; the next hwt pass over the existing T (a load,
or a highway retile reaching it) wrote 21227 back over the stock crossing and deleted the avenue's west half there.**
The road is never cut at the drag itself: it disappears at the next load / highway retile, which is why the owner
did not see it happen.

Where a road can pass under a T at all: the road column needs both sides of the through highway free of ramp cells.
Frame row dz -1 holds ramp land at dx -2..3 (and the stem at 0..1), row dz 2 at dx 0..6, so only dx <= -3 or dx >= 7
are open. The only T cell in those columns is (7,1), 21227. Proposed fix: see STATUS (reported before building).

## D4 fix: a road under a T is never deleted (hwt block, switch SC3NETMOD_HWTCROSS)

What changed (`re/harness/src/sc3netmod_hwt.c`, dispatcher line in `sc3netmod_rbt.c`, AVL family in `sc3netmod_avl.c`):
- Guard: a T highway cell holding a road / rail crossing (15098, 11258, 16006, 16007 or a variant of one) is never
  overwritten, in hwt_existing (built T), hwt_build (new T) and hwt_break (broken T). On T cell (7,1) at turns 0 / 2
  with the T's own 15098 there, the crossing twin is written; any other crossing in a T cell is left as it is and
  logged (`hwt: <who>: T cell (x,z) holds a road / rail crossing id.st: left as it is`).
- New T: a stock crossing on the through highway counts as straight highway (15098 like 15051, 11258 like 73); a
  crossing in a T cell other than a twin cell refuses the T (as before).
- Pieces (package avenue_diamond, `hwtx` highway lines + `avlc ... <family>` avenue lines): 20858 = the two-way twin of
  21227 (base 15098, stock 15098 lanes and art, saved as 15098); 20859 / 20860 = its one-way variants for AVL (avenue_lanes
  21716 / 21717's lanes, art of 15098). AVL treats a family cell like its base, writes the family's one-way variants and
  gives back the family piece (not the base) when a band reverts.
- Look: the twin draws as the stock highway-over-road crossing, not as 21227 (hwt's frames are painted by hwt_paint at
  other sizes, so no pixel composite). Lanes are the same as 21227's (plain through lanes) plus the road.
- Off (`SC3NETMOD_HWTCROSS=0`): measured, the old overwrite comes back (below).

| check | result |
|---|---|
| lab, order A (T, then road at the T's dx 7), save + reload with the fix | (117,60) 15098.2, (117,61) **20858.0**, road continuous (before the fix: 21227, road cut) |
| lab, order B (road, then through highway, then stem) | live `hwt: edit: full T at anchor (150,60) turn 0 ... 50 cells written`; (157,60) 15098.2, (157,61) 20858.0, road continuous; survives save + reload |
| lab, guard: road under T cells (2,0) / (2,1) at x 152 | reload: `T cell (152,60) / (152,61) holds a road / rail crossing 15098.0: left as it is (built T)`, both kept, T kept |
| lab, same save with `SC3NETMOD_HWTCROSS=0` | `hwy: load pass ... 4 written`: (117,61) / (157,61) 21227, (152,60) 21219, (152,61) 21224, all three roads cut (the old behaviour) |
| saves | the twins save as 15098 (network_layer on the saved lab city: all six cells 15098) |
| owner save, existing Ts without a road (5 Ts) | load with the fix on and off: `hwy: load pass ... 0 written` both, T footprint 596..612 x 126..140 identical |
| shipped cities | offline: 0 hwt pieces in all 16 saves (`data/d4_shipped_hwt_scan.txt`), so the built-T paths never run there; 7 cities hold T triggers (caps / stub X), where only the new-T check runs, and a load pass never builds a new T while hwask is on ("not asked on a load pass: the default") |
| owner save, re-drag (608,133)..(608,135) by `nb_drive build 1` | live (608,134) 15098.0; after save + reload **20858.0**, the west half continuous 133..138, T intact |

Not done: in-game run of the 15 shipped cities (offline argument above instead); English-UK; the twin's own art.

## The three corners: the chain (604,119) -> (608,134) converts (D3a, D3, D2b)

The chain z 604/605 (119..130) - tight corner (605,131) - x 131/132 (606..607) - corner (608..609,131..132) - z 608/609
(133..138) converts all or nothing. Each link needed a shape the stock tiler leaves irregular:

| shape | cells | what the tiler left | change (AVL `sc3netmod_avl.c`, AVX `sc3netmod_avx.c`, all under SC3NETMOD_AVDIAMOND) | pieces |
|---|---|---|---|---|
| D3a corner with a plain-road half | (608..609,131..132) | (609,132) a 29.1 where the corner's half belongs; outer cell (609,131) a T 39.3 with a road east | a 29 along a band axis, an 11203 beside it across the axis, a T / X / corner piece next to it along the axis and a straight half beside that one is read as the half (11204, median toward the bend): in avl_at and in AVX's corner junctions | avjunc's corner junction 21768 at (609,131), avcore 21726 / 21700 |
| D3 tight corner | (604..605,131..132) | the two U-ends share the X 43 (605,131) | new end kind "tight corner" (avl_tight_at): the U-turn bend P and the X Q in the end row, the other band's U-turn bend Q' past Q; both bands decided together | U-turn quarters 21701 at (604,131) / (605,132); new X **20861** (avlt AAAA IOIO, base 43, avjunc box lanes N->E and S->W plus the U-turns, art = avjunc box painter AAAA) |
| D2b corner beside a junction | (604..605,117..119) | (604,119) a T 39.0 whose W arm points at the side of the on-ramp 15141 (no arm back); the inner bend (604,118) a T 39.0 with a stub N arm; the other side of the block is D2a's box at 603 | a 39 whose arm points at a ramp that has no arm back is read without it (a straight half); a corner whose other side is an avlj junction row (box / link noses) converts with its band alone (the D2a join, now also for a plain bend); AVX: cells of a corner block a ramp walk stopped at count as band arms of the box beside it and are skipped in validation | avcore 21726 written at (604,118) at the 11203 state the corner wants (saves as 11203.0: the stub arm goes) |

Guards found on the way:
- The corner trim stops before a corner block only when the bend row's other cell is a straight half or a linked T. An X
  there (Moscow (82,165)) is a junction. The first version cut it and the offline diff showed 2 changed noses outside
  the ramp cases. Now 0.
- After conversion the inner bend is avcore's 21726 (base 11203), so the walk meets an 11203 one row earlier. The trim
  reads "an 11203 with another 11203 in the next row" as the inner bend. The first reload test lost the chain: box 603
  was not rebuilt and the stock retile put the 39s back. Now the chain survives the reload.
- The three shapes (29 half, tight corner, corner beside a junction) apply only with a highway piece (ramp, crossing,
  deck, interchange) within 2 cells (`avd_near_hwy`). The same shapes occur away from highways in the shipped cities
  (crude pattern count: about 970 X-with-two-bends, 24 29-halves) and belong to later groups.

| check | result |
|---|---|
| owner save (west half re-dragged), load | 37 one-way bands (34 before the corners): `(604,119) rows 0..11 -> one-way (corner + T / tight corner)`, `(606,131) rows 0..1 (tight corner / corner)`, `(608,133) rows 0..5 (corner / join or edge)`; (601,117) stays one-way |
| live cells | (604,118) 21726.0, (604,119) 21700.1, (605,117) 21701.0, (604,131) / (605,132) 21701.2, (605,131) 20861.0, (608,132) 21726.0, (609,131) 21768.3, (609,132) 21700.3, (608,134) 20860.0 (the crossing twin's one-way variant), (609,134) 21716.0 |
| seams, ENGLISH, every join that touches one of our pieces in 596..612 x 110..142 | 0 problems (English-UK: 28, all where a right-hand piece meets a stock two-way piece, the accepted limitation) |
| routed ground trips, 150 s, mask 21 (the only mask on the road halves; mask 8 runs both ways only under 584 and 604/605, where subway lines run) | every half in its rule direction, 0 steps against: 598 N 302, 599 S 105, row 117 E 920, row 118 W 407 (the D2a knot), 604 N 2,036, 605 S 2,316, row 131 E 1,471, row 132 W 1,014, 608 N 2,389, 609 S 2,508, 584 N 38,843, 585 S 2,976 |
| cars on screen, 120 s, ground height | 584 N 1,989 / 0 against, 585 S 385 / 0; no ground car entered the 598 knot or the chain in that window (the trips above are the evidence there) |
| save + reload | 1,014 variant tiles saved and restored; the same 36 one-way band lines; live grid 578..612 x 104..150 identical (0 cells) |
| without sc3netmod | 578 cells read, 0 variant ids, grid = saved bases |

Saved bases that now differ from the owner's original save in 578..612 x 104..150 (18 cells): the AVX base rule ones
listed in D1 / D2a; (604,118) 39.0 -> 11203.0 and (604,119) 39.0 -> 11204.1 (the stub arms go); (609,132) 29.1 ->
11204.3; (608,134) 15051.0 -> 15098.0 (the re-dragged road, kept by the D4 fix).

Trip recorder: `re/tools/netmod/avdiamond_trips.py` (read-only, SimTransit route + deposit hooks; the deposit order is the
popped path, so it runs against travel: calibrated on the one-way 585 half, 0 steps the other way).

Pictures: `d3_chain_604_131_z4.png`, `d3_chain_608_131_z4_rot2.png`, `d2b_603_118_z4_rot2.png`.
Open look item: the crossing twin 20858..20860 draws as the stock highway-over-road crossing.

### Shipped cities with AVDIAMOND on / off (in game, 2026-11-09)

9 shipped cities with avenues and highways (Berlin, Frankfurt, Moscow, Seoul, Madrid, Sacramento, London, Madison,
Liverpool), each loaded with `SC3NETMOD_AVDIAMOND=0` and with it on (test-slot batch, own PIDs, 18 loads, all PASS).
- One-way band lines in the load log: Frankfurt 139 -> 166, Moscow 124 -> 146, Seoul 132 -> 155, Sacramento 52 -> 62,
  Madison 6 -> 8; London 194 / 194 and Liverpool 198 / 198 unchanged; Berlin 199 / 199 and Madrid 198 / 199. The
  accepted-band log is capped at 200 lines on load, so the Berlin and Madrid lists are truncated and their line
  differences are not usable (`data/shipped_onoff_bands.txt`).
- Exact for those two, from the saved variant lists (each mode loaded, saved, `netvariant scan`): Berlin one-way avcore
  cells 1,038 -> 1,142 (**0 lost**, 104 gained), Madrid 1,599 -> 1,681 (**0 lost**, 82 gained). Gained cells farther than 8
  cells from any highway piece: Berlin 2 ((124..125,96), the end of a band whose other end is a ramp box at
  (124..125,89..92)), Madrid 32 (the band x 26..45 z 231 / 232, ending at the ramp box at x 47..54). Both are bands that
  now end on a ramp junction box, i.e. ramp cases.
