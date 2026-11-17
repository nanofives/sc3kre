# shortarm: 31 / 32 / 33 with short avenue arms (round 2026-11-15b, owner "Fix 31-33 first")

Workspace dev/shortarm (main 532e65e + the staged 2026-11-17 build, every pack). Only `avenue_dbv_t` changed, 0.1.0 ->
0.2.0. No C change: dav.c / dbv.c / avl.c / bv.c untouched.

## Why 0.1.0 needed 10-cell arms

- The box took every avenue cell that touched the band, diagonal neighbours included. With the sweep's drags the east
  arm of 31 / 32 / 33 had no cell left past it (31: box x 13..21, avenue x 9..21).
- The template windows held the 10-cell arm as road, so a shorter arm matched no template, DBV wrote what it wrote
  before (single-road row pieces, the stock T 39, DBVTOUCH 29s) and AVL refused the arm: the two-way stub. The dark
  wedge in 32 was in those stock cells.

## 0.2.0 (verify/shortarm/sabox_build.py)

- Box = the scene's special cells + the avenue cells the stock tiler T's (4-neighbour of a band cell outside the
  avenue's two rows), squared to whole columns. 31: x 14..20, 32: 33..38, 33: 51..56 (sweep coordinates). Same scene
  as 0.1.0, so every box cell's art is 0.1.0's. Only the end columns are new pieces (their avlj letters face the arm).
- Windows: in the avenue's two rows, any cell past end column + 2 (`-`). One template serves every arm length.
- Per arm side two variants: 2+ cells past the box (AVL converts them: halves + U-turn) or exactly 1 (the stock
  U-turn pair alone, no AVL band forms). On a 1-cell arm the template writes the one-way U-turn itself: twin 30356 of
  avenue_lanes' 21701, the same art (stock 11203) and lanes. It is a twin because DBV treats every piece its templates
  write as its own and would retile every 21701 near a diagonal boulevard.
- 0.1.0's 95 pieces 30261..30355 keep their ids and art. The builder replays the 0.1.0 build and checks it against the
  shipped pack byte for byte, so cities built on the 2026-11-17 stage still draw. New: 30356 (U-turn twin),
  30357..30376 (10 end-column pieces + their x/z mirrors, own ids so avlj letters never land on a shared box piece).
  32 templates (31: 4 variants, 32: 4, 33: 2, x 8 symmetries, deduplicated), 456 writes, 40 avlj lines. The builder's
  check: 136 layouts (every variant, plus the shortest arm each `2` variant serves), each matched, no clashing writes.

## Minimum arm (armcheck.py, cells read back)

An arm converts when it reaches **at least one cell past the box**, i.e. one column past the last avenue cell that
touches the band. With the sweep's geometry that is exactly the sweep's 6-cell east drag. 31's east arm then ends
3 cells past the band's last cell in the upper row and 2 in the lower row. The west side needs 2 cells past the band's
first cell. One cell shorter (the arm ends on the box's own column) matches no template and stays the stock look, both
arms two-way, as before: 31:6:5, 32:6:5, 33:0:5.

| layout (case:W:E[:rev]) | east past the box | result |
|---|---|---|
| 31:6:5, 32:6:5, 33:0:5 | 0 | stock (unchanged) |
| 31:6:6, 32:6:6, 33:0:6 (= sweep), + :rev | 1 | converted, U-turn twin 30356 |
| 31:6:7, 32:6:7, 33:0:7, + :rev | 2 | converted, 21700 + 21701 |
| 31:6:8 | 3 | converted |
| 31:6:12, 32:6:12, 33:0:12, 31:6:12:rev | 7 | converted |
| 31:2:6, 32:1:6 (west 1 cell past the box), + :rev | 1 | converted, twin on both sides |
| 31:3:7, 32:2:7 (west 2) | 2 | converted |

24 + 16 layouts, logs `a1/armcheck1.log`, `r1/armcheck2.log`.

## Regression

- Full sweep, 80 cases (m1, fresh game, sweep order), against the staged build (verify/final1117/s1, `cmp_stage.py`):
  **77 identical, changed only 31 (27 cells), 32 (26), 33 (15)**, all intended. 7 drags got no reply in 90 s
  (3 in case 40, 1 in 43, 1 in 45, 2 in 54, PC under load). Those four cases still read back identical. 31 / 32 / 33's final cells equal the
  first build's (a1).
- Reverse draw order (rev_cases, m1): **31, 32, 33 identical** to sweep order. Extra reversed layouts in armcheck
  (both arm lengths) all converted.
- diagfix's DBV template cases, reversed (r1, fresh game, final1117's slot layout): 49, 52, 53, 54, 55 give the same
  difference lists as the stage's r1. 50 differs only in its slot-edge cells shared with 49's slot (4 cells here, 10 on
  the stage, no 303xx piece in either), the run-to-run edge class final1117 already lists.

## Pictures (phone-sized, zoom 4, all four views)

`owner_shots/ba4_a1_31.jpg`, `ba4_a1_32.jpg`, `ba4_a1_33.jpg` (before = the staged build in dev/final1117, after =
shortarm, both with the sweep's 6-cell arms), all three in `ba4_a1_all.jpg`. In 32 the dark wedge is gone (the cells are
box art now).

## Game faults seen

- Game a1 crashed after about 10 min of builds and camera moves: access violation at a NULL call from SIMUI.DLL+0x6D50F
  during a UI repaint (`in_rci_repaint=1`), not in netmod. Logs: `a1/crash1_sc3resize.log`, `a1/crash1_sc3netmod.log`.
  Not seen in the two later games. The third game rebuilt the same slot (row 10, column 0) without a fault.
- Game m1 (full sweep + reverse orders, about 50 min) stopped answering build jobs during the reversed 52 (no reply in
  90 s, process alive, no VEH fault logged). 31 / 32 / 33 / 49 / 50 had already been compared. That check was redone in
  the fresh game r1.

## Files

- Pack: dev/shortarm/packs/avenue_dbv_t, ship copy dev/orthfix/ship/avenue_dbv_t (+ SHIP.md), 0.1.0 in
  dev/orthfix/ship_old1117/avenue_dbv_t. Tracked: re/tools/netmod/examples/avenue_dbv_t/manifest.json +
  cap_30356.lanes.json (art is gitignored).
- Tools (MAIN/verify/shortarm, untracked like orthfix's): sabox_build.py (needs verify/orthfix/avdbx_build.py and its
  paint cache verify/orthfix/mock), run.py (regress / rev / shots4), armcheck.py, cmp_stage.py, sheet4.py.
