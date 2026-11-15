# final1115: the shipped stage (2026-11-15) on the xsect sweep

Fresh workspace dev/final1115 (tree from stage\release 2026-11-15, packs as shipped, no hand installs), full 80-case sweep in sweep order (`verify/final1115/f1`, run log `f1_run.log`), reverse draw orders, and the owner verdicts for the 37 cases that were not green in verify/xsect.

## Verdicts (31 green, 5 amber, 1 red)

| case | xsect | final | why | before | after |
|---|---|---|---|---|---|
| 15_RxDA_L | BROKEN | **green** | road turns into the diagonal avenue's end (bend set) | `../xsect/raw/15_RxDA_L_z4.png` | `f1/raw/15_RxDA_L_z4.png` |
| 16_RxDB_cross | BROKEN | **green** | no grass diamond: the boulevard lanes run through the crossing | `../xsect/raw/16_RxDB_cross_z4.png` | `f1/raw/16_RxDB_cross_z4.png` |
| 17_RxDB_T1 | BROKEN | **green** | no grass or trees in the lane at the T | `../xsect/raw/17_RxDB_T1_z4.png` | `f1/raw/17_RxDB_T1_z4.png` |
| 18_RxDB_T2 | BROKEN | **green** | no grass or trees in the lane beside the road T | `../xsect/raw/18_RxDB_T2_z4.png` | `f1/raw/18_RxDB_T2_z4.png` |
| 19_RxDB_L | BROKEN | **green** | road turns into the diagonal boulevard's end (bend set) | `../xsect/raw/19_RxDB_L_z4.png` | `f1/raw/19_RxDB_L_z4.png` |
| 26_AxB_L | refused | **green** | corner box, both arms one-way | `../xsect/raw/26_AxB_L_z4.png` | `f1/raw/26_AxB_L_z4.png` |
| 27_AxDA_cross | refused | **green** | avenue one-way through the crossing | `../xsect/raw/27_AxDA_cross_z4.png` | `f1/raw/27_AxDA_cross_z4.png` |
| 28_AxDA_T1 | refused | **green** | avenue one-way through the T | `../xsect/raw/28_AxDA_T1_z4.png` | `f1/raw/28_AxDA_T1_z4.png` |
| 29_AxDA_T2 | refused | **amber** | by design: a short avenue stem off a diagonal stays two-way (AVL) | `../xsect/raw/29_AxDA_T2_z4.png` | `f1/raw/29_AxDA_T2_z4.png` |
| 31_AxDB_cross | BROKEN | **amber** | diagonal lanes fixed; the avenue's upper half ends in a stock box (short arm, AVL) | `../xsect/raw/31_AxDB_cross_z4.png` | `f1/raw/31_AxDB_cross_z4.png` |
| 32_AxDB_T1 | BROKEN | **amber** | gap fixed; the avenue arm stays two-way (AVL refuses it) | `../xsect/raw/32_AxDB_T1_z4.png` | `f1/raw/32_AxDB_T1_z4.png` |
| 33_AxDB_T2 | BROKEN | **amber** | grass fixed; the avenue stem stays a two-way stub (AVL) | `../xsect/raw/33_AxDB_T2_z4.png` | `f1/raw/33_AxDB_T2_z4.png` |
| 34_AxDB_L | BROKEN | **green** | avenue turns into the diagonal boulevard (paved bend box) | `../xsect/raw/34_AxDB_L_z4.png` | `f1/raw/34_AxDB_L_z4.png` |
| 37_BxB_L | refused | **green** | corner box (orthfix) | `../xsect/raw/37_BxB_L_z4.png` | `f1/raw/37_BxB_L_z4.png` |
| 38_BxDA_cross | BROKEN | **green** | crossing box | `../xsect/raw/38_BxDA_cross_z4.png` | `f1/raw/38_BxDA_cross_z4.png` |
| 39_BxDA_T1 | refused | **green** | opening box (orthfix) | `../xsect/raw/39_BxDA_T1_z4.png` | `f1/raw/39_BxDA_T1_z4.png` |
| 40_BxDA_T2 | BROKEN | **green** | T box | `../xsect/raw/40_BxDA_T2_z4.png` | `f1/raw/40_BxDA_T2_z4.png` |
| 41_BxDA_L | BROKEN | **green** | boulevard bends into the diagonal avenue (paved bend box) | `../xsect/raw/41_BxDA_L_z4.png` | `f1/raw/41_BxDA_L_z4.png` |
| 42_BxDB_cross | BROKEN | **green** | crossing box | `../xsect/raw/42_BxDB_cross_z4.png` | `f1/raw/42_BxDB_cross_z4.png` |
| 43_BxDB_T1 | BROKEN | **red** | no box: the boulevard stays stock two-way right of the T, plain road crossing | `../xsect/raw/43_BxDB_T1_z4.png` | `f1/raw/43_BxDB_T1_z4.png` |
| 44_BxDB_T2 | BROKEN | **green** | T box, no stub | `../xsect/raw/44_BxDB_T2_z4.png` | `f1/raw/44_BxDB_T2_z4.png` |
| 48_DAxDA_L | BROKEN | **green** | corner box | `../xsect/raw/48_DAxDA_L_z4.png` | `f1/raw/48_DAxDA_L_z4.png` |
| 49_DAxDB_cross | BROKEN | **green** | crossing box | `../xsect/raw/49_DAxDB_cross_z4.png` | `f1/raw/49_DAxDB_cross_z4.png` |
| 50_DAxDB_T1 | BROKEN | **green** | T box, the stem converts | `../xsect/raw/50_DAxDB_T1_z4.png` | `f1/raw/50_DAxDB_T1_z4.png` |
| 52_DAxDB_L | BROKEN | **green** | corner box, both arms convert | `../xsect/raw/52_DAxDB_L_z4.png` | `f1/raw/52_DAxDB_L_z4.png` |
| 53_DBxDB_cross | BROKEN | **green** | crossing box | `../xsect/raw/53_DBxDB_cross_z4.png` | `f1/raw/53_DBxDB_cross_z4.png` |
| 54_DBxDB_T1 | BROKEN | **green** | T box, the stem converts | `../xsect/raw/54_DBxDB_T1_z4.png` | `f1/raw/54_DBxDB_T1_z4.png` |
| 55_DBxDB_L | BROKEN | **green** | corner box, both arms convert | `../xsect/raw/55_DBxDB_L_z4.png` | `f1/raw/55_DBxDB_L_z4.png` |
| 62_AtoR_merge | refused | **green** | avenue merges into the road one-way | `../xsect/raw/62_AtoR_merge_z4.png` | `f1/raw/62_AtoR_merge_z4.png` |
| 63_AplusA_merge | refused | **green** | two avenues side by side, both one-way | `../xsect/raw/63_AplusA_merge_z4.png` | `f1/raw/63_AplusA_merge_z4.png` |
| 67_Bxrail_cross | refused | **green** | boulevard crosses the rail | `../xsect/raw/67_Bxrail_cross_z4.png` | `f1/raw/67_Bxrail_cross_z4.png` |
| 68_DAxrail_cross | BROKEN | **green** | rail kept under the diagonal avenue | `../xsect/raw/68_DAxrail_cross_z4.png` | `f1/raw/68_DAxrail_cross_z4.png` |
| 69_DBxrail_cross | BROKEN | **green** | rail kept under the diagonal boulevard | `../xsect/raw/69_DBxrail_cross_z4.png` | `f1/raw/69_DBxrail_cross_z4.png` |
| 71_Bxhwy_cross | refused | **green** | boulevard under the highway | `../xsect/raw/71_Bxhwy_cross_z4.png` | `f1/raw/71_Bxhwy_cross_z4.png` |
| 72_DAxhwy_cross | BROKEN | **green** | highway kept over the diagonal avenue | `../xsect/raw/72_DAxhwy_cross_z4.png` | `f1/raw/72_DAxhwy_cross_z4.png` |
| 73_DBxhwy_cross | BROKEN | **green** | highway kept over the diagonal boulevard | `../xsect/raw/73_DBxhwy_cross_z4.png` | `f1/raw/73_DBxhwy_cross_z4.png` |
| 80_DAxonramp | not built | **amber** | stock limit (accepted): no on-ramp beside a diagonal road; the highway is kept now | `../xsect/raw/80_DAxonramp_z4.png` | `f1/raw/80_DAxonramp_z4.png` |

Sheets: `owner_shots/sheet_final_1.png` .. `sheet_final_4.png`.
## Sweep against the two child runs (final cells, all 80 cases)

- vs diagfix m13: 26, 37, 62, 67, 71 differ: the stage ships orthfix's updated boulevard / boulevard_junctions /
  avenue_ends (corner box 37, AVL converting 26 / 62, crossing twins 67 / 71); m13's tree had only orthfix's 39 pack.
- vs orthfix run12: 49 50 52 53 54 55 differ (diagfix's DBVX boxes, not in orthfix's tree); 78 79 80 differ only
  because run12 did not build the on-ramp cases.
- Nothing else differs. No green case of verify/xsect changed except 45 (its ordered bend set).
- Three drags got no reply within 90 s (cases 40 and 45); both cases came out identical to m13 / run12.

## Draw order (reverse builds)

- 39 / 41 / 45 (verify/orthfix/order_case.py + order_cmp.py): reverse = sweep order (45: one cell of the neighbour slot,
  78,93).
- 49 50 52 53 54 55 (verify/diagfix/rev_cases.py via run.py): 49 and 53 identical; 50 52 54 55 differ only in stock
  cells at the diagonal boulevard's far end on the slot edge (1 to 4 cells). 49 drawn diagonal boulevard first matched
  here and in m13 but failed in two earlier diagfix runs: timing-sensitive, kept open.
