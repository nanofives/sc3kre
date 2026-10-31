# avslow: road placement slow once a boulevard (3-lane avenue) exists (2026-10-30)

Owner report: "When placing road after a 3-lane avenue is set, it is taking longer, the processing time increases way
too much."

## Verdict

Cause: block **BV** (`sc3netmod_bv.c`, automatic boulevards), which runs on RBT's hook of the SIMNTWRK retile pass
`FUN_1001547b` after every ROAD edit. Fixed by a new BVGROW block in the same file (off switch `SC3NETMOD_BVGROW=0`).
Pieces built are unchanged: road cells match the old code cell for cell.

Second owner bug, same code shape (ownership moved to avslow by the orchestrator): **DBV** (`sc3netmod_dbv.c`, diagonal
boulevards). A road placed about 22 cells from a diagonal boulevard tore the whole band back to the stock ladder.
Fixed by DBVGROW (off switch `SC3NETMOD_DBVGROW=0`), section "Diagonal boulevards" below.

## Cause

`bv_run` reads the edit box with 24 cells of margin. If an accepted boulevard run touches that window's border (the
boulevard is longer than the window, or it straddles the border), the old code did two things on every such edit:

1. `bv_pass` on the window: the cut run is not put in `keep[]`, so the revert loop gives every boulevard cell of it
   inside the window a stock rect retile (manager vt+0xb0, which runs a nested `FUN_1001547b`). Each one takes about
   8.5 ms (log timestamps 1238266.271 -> 1238274.792).
2. `bv_run` then runs `bv_pass` again over the **whole map** (1,048,576 cells on a 1024 map, 380-500 ms), which writes
   the same pieces back with `FUN_10008919`.

The cost depends on the map area and on how much of the boulevard falls inside the window. It does not depend on how
many avenues the city has. On a 256 map with a short boulevard no edit went over 87 ms. On a 1024 map, every edit
within about 24 cells of a long boulevard took 0.5-1.25 s.

## Fix (BVGROW)

- When `bv_pass` finds a cut it returns right away (no revert, no write) and reports which window sides were reached
  (`bv_bside`, the same test the old code used, split by side). A cut is one of: an accepted run at the border (the
  old test), a run the rules refuse that holds boulevard pieces and reaches the border (avdiagbreak's DAV case: the
  visible part of a cut run fails the rules, no border flag, and the revert tears it down), or a boulevard piece on
  the border ring.
- `bv_run` widens the window only on those sides, by 64 cells and then doubling, until no run is cut. The whole map is
  only the last step. The pass that writes sees every run touching the window in full, as the whole-map pass did.
- Stats line: `windows grown=N (to the whole map M)`.

## Measurements (ptime log: ms per top-level ROAD edit pass, per block)

Same save `avslow_bv1024.sc3` (Europolis 1024 + a 76-cell boulevard at x 984..986, z 730..805), same posted drags:

| drag | old (BVGROW=0) | new (BVGROW on) |
|---|---|---|
| road (995..1007, 724), 7 cells from the boulevard | **740.3 ms** (BV 734.5), repeat **658.7 ms** (BV 652.1) | **7.3 ms** (BV 2.3) |
| BV cells reverted then rewritten by that drag | 69 | 0 |
| window read by BV | 49x49, then 1024x1024 | 49x49, then 53x113 (grown z+ only) |
| road (804, 760..764), far from the boulevard | 9.0 / 10.0 ms | 7.3 ms |

Reference, before any boulevard existed (first run): placements on the 1024 map 4.7-7.7 ms (BV 0.45-0.8 ms).
While I built the boulevard in segments with the old code, the last three segment drags took 506, 511 and 654 ms
(BV 496-533 ms). Seoul (256 map): baseline 4.85 ms, after a 19-cell boulevard 6.8-8.3 ms for far and near drags.

No SC3NETMOD_<block>=0 bisect was needed: the per-block split puts 99.2% of the slow pass in BV (734.5 of 740.3 ms).
The AVL / DAV / AVX shares stayed at 0.5-3 ms in every pass.

## Same result check

Road pieces in x 982..988, z 726..808 and in the new road's row, read after both drags in the old and in the new run
(`logs/old_cells.txt`, `logs/new_cells.txt`): every network cell matches (same id and state). The 2 differing cells
differ only in a non-network occupant (tree or building, `B` vs `.`), which comes from the sim running on.
Picture: `owner_shots/avslow_boulevard_before_after.png` (old left, new right).

Re-check on the final build (all three cut checks): the same drag took 6.8 ms (BV 2.0), road cells identical to the
first fixed run.

## Diagonal boulevards (DBV, DBVGROW)

Cause: `dbv_pass` decided a band the window cut on its visible part. When that part was accepted, the old code reverted
the cut cells and then ran a whole-map pass, the same cost as BV. When it was refused (`fewer than 3 clean rows`, an end
outside the window), no border flag was raised. The revert loop then stock-retiled its pieces, and the game's retile
goes over the whole connected run, past the window.

Fix: `dbv_cut_sides` scans the window without writing anything, using the same chain and band tests as `dbv_pass`. It
reports a cut when an accepted band, a chain of 2+ rows holding DBV pieces, or a DBV piece reaches the border ring.
`dbv_pass` then returns before any write or revert, and `dbv_run` grows the window on those sides as BV does.

Lab (Roadless Paradise 192 x 192, `avdb_lab.py` game-thread builds, three joined diagonal drags from x 60, 61, 62,
z 60, 12 rows each, 9-row band, 36 cells):

| unconnected road | old (DBVGROW=0) | new |
|---|---|---|
| (90,80)-(90,85), 22 cells east of the last band row (x 68..71, z 68) | 58.6 ms (DBV 56.5), `band ... 3 row(s) left to the stock tiler: fewer than 3 clean rows`, **14 reverts, 42 cells changed: all 36 band cells back to stock 11203 / 43 / 39** | window grown x- to (2,56)-(114,109), **0 reverts, 6 cells changed (the road)**, pass 3.6 ms (DBV 0.9) |
| (95,80)-(95,85), 27 cells east | no cut seen, 6 cells changed, 3.4 ms | grown x-, 6 cells changed, 3.8 ms |
| (93,60)-(93,66), 25 cells east | not run | grown x-, 0 reverts, only the road's cells, 2.6 ms |

After the three new-mode roads, no cell west of x 85 changed (`logs/dbv_new_far_roads_diff.txt`). The band built by
the old and the new DLL is the same (0 cells differ). Picture:
`owner_shots/avslow_diagonal_boulevard_far_road.png` (built / old after the road / new after three roads).
Old pass time for the breaking road: 58.6 ms (DBV 56.5, the 14 retiles); new: 3.6 ms. On a 1024 map an accepted cut
band also cost DBV's whole-map pass, which the grow loop replaces.

## Not covered

- DAV (`sc3netmod_dav.c`) belongs to avdiagbreak (DAVCUT on main 3dd2dca). Its cut case still goes to DAV's whole-map
  pass: on a 1024 map that pass costs the whole-map read on every edit near a cut diagonal avenue. Not changed here
  (ownership). The BVGROW / DBVGROW grow loop would apply there as well.
- A refused run with no boulevard pieces (plain stock roads) at the border does not grow the window. Nothing of ours is
  reverted there, and the old code did not decide it whole either.
- No game check of a boulevard cut on two sides at once (a placement in the middle of a very long one). The code grows
  each side that was reached, so that case goes through the same loop.

## Diagnostic kept: PTIME

`sc3netmod_rbt.c` (rb_pass) and `sc3netmod_avl.c` (avl_pass) log one `ptime:` line per top-level ROAD edit pass that
took at least `SC3NETMOD_PTIME_MIN` ms (default 100, `0` = every pass), with ms per block and the AVL re-run boxes.
Off: `SC3NETMOD_PTIME=0`.

Logs: `logs/ptime_lines.txt`, `logs/old_near_drag.txt`, `logs/new_near_drag.txt`.
