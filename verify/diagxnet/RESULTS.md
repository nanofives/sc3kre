# diagxnet: diagonal level crossing and diagonal underpass (round 2026-11-15b, xsect 68 69 72 73)

Owner (2026-11-15): 68 / 69 "there has to be a special texture there that follows properly the diagonal", 72 / 73
"there should be a special texture for underpass diagonal". Mocks `owner_shots/mock_sheet_v1.png`, owner: "Yes, build
them", stop lines "Keep them". Code on child/diagxnet (uncommitted, files in `re/sessions/STATUS_diagxnet.md`).

## What was built

- **Pieces**: package `diagonal_xnet` 0.1.0, 70 variants 30000..30069 of the stock crossing pieces, so the rail / highway
  keep their class, Protected status, Convert rows, turn matrix (highway trips) and save as stock:
  - rail crossing (base 69, written at state 1; the same piece at state 0 serves a rail along z): DA 30000..30002 (band
    axis 0), 30015..30017 (axis 1); DB 30030..30033, 30050..30053.
  - underpass (base 15098 on a 15051 highway, 11258 on a 73 highway, written at the stock state of each deck row, 0 or 2):
    DA 30003..30014 / 30018..30029, DB 30034..30049 / 30054..30069.
- **Art** (`re/tools/netmod/xnet_paint.py`, built by `xnet_build.py`): the rail look is drawn on the stock 69 frame, so the
  1 px rim is gone. Underpass wall hits take the cell's own solid-twin pixel first, so the end-face slivers are gone.
- **Lanes**: the band cell's own car lanes and pedestrians plus 69's train lanes or the base's deck lanes. No `connects`
  entry, so the base turn matrix stays.
- **Code**: `sc3netmod_davxn.c`. DAVXNET's kept crossing cells now take the variant from the table
  `davxn <base> <base state> <band piece> <band state> <variant>` (96 lines). A variant that no band keeps goes back to
  its stock base. Switches: `SC3NETMOD_DAVXNRAIL=0` (rail), `SC3NETMOD_DAVXNHWY=0` (underpass).

## Checks (dev/diagxnet, tree = stage 2026-11-15 + diagonal_xnet)

| check | result |
|---|---|
| 80-case sweep in sweep order (`x1`, fresh sandbox), final read-back against `verify/final1115/f1` | only 68 69 72 73 80 changed, each crossing cell to its variant (`x1_diff.txt`; 80 = the DA under the highway beside the on-ramp, now an underpass too). No other case changed. |
| reverse draw order 39 41 45 49 50 52..55 (`x2_rev.log`) | 39 41 45 53 identical; 50 52 54 55 differ in 1..4 stock cells at the slot edge and 49 is timing-sensitive, both as recorded for the staged build (`verify/final1115/RESULTS.md`). No cell involves a new piece. |
| reverse draw order 68 69 72 73 (band first, then rail / highway) | the rail / highway is cut at the band. **Stock limit**: the same happens with a plain diagonal road (35) in the same game (`repro_rev.py`): the crossing builder's list has only straight road (FUN_100167d4, NETVARIANT.md). Not a regression. |
| orientations the sweep never builds (`x3`, `xnet_lab.py`): axis-1 bands, rail along z (69.0), highway along z (11258) | all 10 cases get their variants. Stock writes 11258 at state 2 on the low-x column and 0 on the high one, as predicted from the art. |
| trains cross (`x3/train_68`) | a freight train runs over 30000..30002 (four frames in `owner_shots/train_68.png`) |
| highway traffic flows (Sacramento copy, `xnet_city.py`, `c1_sac_2064.sc3`) | DA under the busy highway at (148..151, 51..52), DA across the rail at (240..242, 155), 7 game years: highway density is the same on every cell of the run, the six underpass cells included (row 51: 44, row 52: 121) |
| save + reload | all 9 variant cells come back; the load pass writes 0 |
| off switch | `SC3NETMOD_DAVXNHWY=0` on load: underpass cells back to 15098, the rail crossing stays |

Pictures: `owner_shots/game_sheet_1.png` (68 69 72 73 before | after view 0 | after view 1), `owner_shots/game_sheet_2.png`
(the 10 other orientations), `owner_shots/train_68.png`, mocks `owner_shots/mock_sheet_v1.png`.

## DAVXHEAL: rail or highway drawn across an existing diagonal (owner 2026-11-16 "Fix it")

**Cause.** A rail or highway drag skips the diagonal's cells. The crossing builder FUN_100167d4 [CONFIRMED @ SIMNTWRK
0x100167d4] only takes straight road (0x1d, 0x2bc4) as the existing piece. Stock 35 and every DA / DB piece (bases 35 /
43 / 18004) get no crossing. The run is placed on both sides with plain 44 / 15051 / 73, and the diagonal stays road in
between, so the line is cut. A plain stock diagonal road does the same. No block ran after a rail pass (rb_pass handles
net 1 and the highway blocks on net 4 only).

**Fix** (`sc3netmod_davxn.c` DAVXHEAL; one call line in `rb_pass`, sc3netmod_rbt.c; off `SC3NETMOD_DAVXHEAL=0`). After
every rail / highway pass, a straight run with two run cells on each side of 1..4 diagonal-road cells gets the stock
crossing on those cells. That is 69 at state 1 along x / 0 along z, or 15098 next to 15051 / 11258 next to 73 at the
neighbour's state, which is what drawing the rail / highway first gives. Then DBV and DAV run over the box, so a DA / DB
band takes its DAVXN variants.

**Checks** (tree = main 5df3524 code + every current pack: orthfix 11-15b ship set, diagfix 12 `diagonal_boulevard`,
`diagonal_xnet`):

| check | result |
|---|---|
| band first, then rail / highway, all orientations (DA, DB, plain diagonal road; rail along x and z; highway along x (15098) and z (11258); band axis 0 and 1), `repro_rev.py` runs h1 | every case healed: DA / DB get the same pieces and states as sweep order, the plain diagonal road gets stock 69 / 15098 / 11258 (**stock diagonal roads fixed too**) |
| reverse vs sweep order, same game (`x5_rev.log`) | 68 69 73 74 75 identical (74 / 75 = plain diagonal road x rail / highway). 72 and 45: one neighbour-slot cell at the slot edge each (45's was already in the staged build's record). 39 41 identical |
| reverse 49..55 (`x6_rev.log`, fresh game) | 53 identical; 50 52 54 55 1..4 stock cells at the slot edge; 49 timing-sensitive: all as recorded before (diagfix's open item), no new piece involved |
| 80-case sweep in sweep order (`x5`, final read-back; `cmp3.py`) | 68 69 72 73 80 same as x1 (diagxnet); 50 52 53 54 55 same as diagfix m14; 29 43 66 67 70 71 same as orthfix run14; 79 = orthfix's `avlq` art twins (21716 / 21717 -> 30235 / 30236), not DAVXHEAL; 78 unchanged. Nothing else differs |
| a rail that only ends on a band | no crossing, band untouched (0 DAVXHEAL lines) |
| trains | a freight train crosses the healed crossing (`owner_shots/train_healed_68.png`) |
| highway | SimTransit flags (+0x5c) on the healed underpass equal the sweep-built 72 cell for cell (0x3 on the six cells, 0x2 highway on both sides); the sweep-built underpass already carried Sacramento's traffic (above) |

Pictures: `owner_shots/heal_sheet.png` (72 sweep order | band first + highway | band first + rail, a train on it).

## Underpass wall wedge (owner review 2026-11-16, `diagonal_xnet` 0.1.1)

Owner, case 72 view 0: "there's triangle here that needs to be fixed", a beige triangle on the highway's near wall just
right of the opening.

**Cause.** The beige is the left end face of the stock highway cell beside the band (15051 at (32,141), frame 0, matched
pixel for pixel in the shot, `wedge/whose.py`). Every plain highway frame (15051 / 73, one layer) carries that end face,
and the next highway cell normally covers it. The game draws the 2-layer pieces' layer 0 first, then the plain highway
cells, then every layer 1. Our variants (on 15098 / 11258) had their walls in layer 0, so the neighbour's end face landed
on them. Stock 15098 relies on the same overdraw to draw the abutments of its straight opening. The draw order is
measured, not assumed: the offline composite with that order (`wedge/gameorder.py`, GO_MODE=last) equals the in-game shot
in view 0 (13 pixels off by more than 40 before the fix, 0 after the first fix build); plain painter order with layer 1
interleaved does not show the wedge at all.

Same fault, every orientation: beige wedges on 15051 decks and dark ones on 73 decks in 72, 73, H1..H6 (`w1`).

**Fix (`xnet_paint.paint_under_cell`).** Layer 1 = the stock deck top plus every pixel that shows this cell's own deck,
slab or wall (hit point inside the cell's square; deck pixels judged at the top face e = 32). Drawn after the neighbour, it
covers the end face, as a plain highway cell would. A first build judged deck pixels at the slab underside (e = 30): the
30..32 rim of each cell's end face then went into layer 1 and showed as 1 px beige seams across the deck at the band
edges (`w2`, all four views). Judging at e = 32 gives the rim to the next cell. Ground under the opening stays layer 0
only. Lanes, manifest lines and rail art unchanged (rail ids 30000..30002, 30015..30017, 30030..30033, 30050..30053
byte-identical); only the 56 underpass ids changed. Version 0.1.1.

| check | result |
|---|---|
| in game, cases 72 73 H1..H6, zoom 4, views 0..3 (`w1` 0.1.0, `w3` 0.1.1, same game build, same cells read back) | no wedge, no seam, wall line continuous outside the opening in all 32 views; the stray step in the view 1 / 3 abutment (an end face) is gone too |
| offline model of the game order on the 0.1.1 art vs the `w3` shots, case 72 | view 0: 62 pixels off, view 2: 53 (trees, pedestrians); views 1 / 3 differ only where the sandbox's other cases (power lines, water) enter the frame |

Pictures: `owner_shots/wedge_72.jpg` (72 before | after, four views), `owner_shots/wedge_all.png` (8 cases x 4 views).
