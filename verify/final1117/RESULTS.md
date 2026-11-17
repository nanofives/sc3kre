# final1117: the 2026-11-17 stage as players get it

Fresh workspace `dev/final1117` (stage\release 2026-11-17, DLLs from main b6281ac, the 26 packs of stage\src; nothing
installed or edited by hand). Runner: `verify/final1117/run.py` (verify/diagfix's regress / rev_cases / scripts,
pointed at dev/final1117's log, output here).

## 1. Full 80-case sweep in sweep order (`s1/`, log `s1_run.log`)

Against diagfix's m21 (my tree, every pack incl. diagonal_xnet 0.1.1): **0 cells differ in all 80 cases**.
78 / 79 / 80 included (80 = one on-ramp with its B joint, the xnet underpass).

## 2. Reverse builds and the extra layouts (`r1/`, `r2/`, `r3/`, fresh games)

| check | result |
|---|---|
| 39 41 45 (order_case / order_cmp) | identical in both orders |
| reversed 49 50 52 53 54 55 (rev_cases, r1) | 49 53 identical; 50 52 54 55 only the known slot-edge / far end cap cells (as m21b) |
| 49 drawn diagonal boulevard first, 9 fresh builds (r1 + r2 + r3, two games of 4) | **9 / 9 identical** to sweep order (DBVREPASS fired 5 times per game) |
| case 80 diamond, 4 ramps (`ramp80d.py`) | built: rows 139 / 142 = 30401.2 20500.0 30400.0 / 30400.2 20500.0 30401.0 (B joints, the avenue kept), as in my tree |
| highway drawn over an existing diagonal avenue (band first, `xh_run.log`) | underpass pieces 30003..30008, the same as sweep-order 72 |
| rail drawn across an existing diagonal boulevard (band first, `xr_run.log`) | level crossing pieces 30050..30053 kept |

## 3. Owner sheet (39 green, 3 amber, 0 red)

Every case the owner reviewed in rounds 11-14b / 11-15b, before (verify/xsect) | after (this stage, sweep order), plus the
diamond and the two band-first crossings: `owner_shots/sheet_final1117_1.jpg` .. `_4.jpg` (1390 px wide, 12 tiles each).

| case | verdict | why |
|---|---|---|
| 15 | green | option A: box in the road's row, lane lines and trees up to it (owner 11-16) |
| 16 | green | no grass diamond: the boulevard lanes run through the crossing |
| 17 | green | no grass or trees in the lane at the T |
| 18 | green | no grass or trees in the lane beside the road T |
| 19 | green | the original cap, opened only over the road (owner 11-16) |
| 26 | green | corner box, both arms one-way |
| 27 | green | avenue one-way through the crossing |
| 28 | green | avenue one-way through the T |
| 29 | green | avenue T on the diagonal avenue (orthfix templates) |
| 31 | amber | the avenue arm stays a short two-way stub (AVL) |
| 32 | amber | the avenue arm stays two-way (AVL refuses it); a dark wedge where it meets the boulevard |
| 33 | amber | the avenue stem stays a two-way stub (AVL) |
| 34 | green | avenue turns into the diagonal boulevard (paved bend box) |
| 37 | green | corner box (orthfix) |
| 38 | green | crossing box |
| 39 | green | opening box (orthfix); same in both draw orders |
| 40 | green | T box |
| 41 | green | boulevard bends into the diagonal avenue; same in both draw orders |
| 42 | green | crossing box |
| 43 | green | the diagonal boulevard's opening box (orthfix) |
| 44 | green | T box, no stub |
| 48 | green | corner box |
| 49 | green | crossing box; drawn boulevard first 9 / 9 OK (DBVREPASS) |
| 50 | green | T box, the stem converts |
| 52 | green | the avenue runs into the corner box (fixed 11-16) |
| 53 | green | crossing box |
| 54 | green | T box, the stem converts |
| 55 | green | the boulevard runs into the corner box (fixed 11-16) |
| 62 | green | avenue merges into the road one-way |
| 63 | green | two avenues side by side, both one-way |
| 66 | green | avenue crosses the rail (orthfix art) |
| 67 | green | boulevard crosses the rail (orthfix art) |
| 68 | green | level crossing under the diagonal avenue (diagonal_xnet) |
| 69 | green | level crossing under the diagonal boulevard (diagonal_xnet) |
| 70 | green | avenue under the highway (orthfix art) |
| 71 | green | boulevard under the highway (orthfix art) |
| 72 | green | diagonal avenue under the highway (diagonal_xnet 0.1.1, owner OK) |
| 73 | green | diagonal boulevard under the highway (diagonal_xnet 0.1.1) |
| 80 | green | on-ramp beside the diagonal avenue, B joint (one ramp as in xsect) |
| 80 diamond (4 ramps) | green | 2 entry + 2 exit ramps, B joints, the avenue kept up to them (owner 11-16) |
| highway drawn over an existing diagonal avenue | green | drawn band first: the same underpass as in sweep order (72) |
| rail drawn across an existing diagonal boulevard | green | drawn band first: the level crossing is kept |

Ambers (31 32 33) are the known AVL limit (a short avenue arm on a diagonal boulevard stays two-way), unchanged since
final1115. No red case.
