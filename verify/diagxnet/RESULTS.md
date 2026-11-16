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
