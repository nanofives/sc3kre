# avjunc: junctions on one-way avenues (milestone 2, built, 2026-10-19)

Plan `verify/avjunc/PLAN.md`; conventions `re/analysis/AVENUE_LANES.md` (avcore). Built on child/avcore 4c7e510. Owner
sheet `MAIN\verify\avjunc\owner_shots\avjunc_sheet.png` (game), plan `avjunc_plan.png`. Test tree
`Simcity_stock_avjunc`, instance `inst_avjunc`, packages avenue_lanes (avcore) + avenue_junctions.

## What was built

| part | file |
|---|---|
| lane model (box cell edge modes -> lanes, matrix, curves) + plan sheet | `re/tools/netmod/avjunc.py` |
| the rule, offline twin of the C block (segments, runs, boxes, spans, noses, modes, demotion, validation), city scan and edge check | `re/tools/netmod/avjunc_rule.py` |
| package builder: piece table, lane specs, curves, art, manifest, table lines, lane check | `re/tools/netmod/avjunc_build.py` |
| the AVX block, reworked (avx_run before AVL, avx_post in avcore's post-AVL phase, slot AVL_POST_AVX) | `re/harness/src/sc3netmod_avx.c` |
| package: 61 box pieces + 7 noses, table lines `avxm` / `avxn` (key `avenue_junction_lines`) and `avlj` (avcore's `avenue_lines`) | `re/tools/netmod/examples/avenue_junctions/` (`avjunc_pieces.json`, `box_*.lanes.json`, `nose_*.lanes.json`, `manifest.json`) |
| shared files, marked `task avjunc` | `sc3netmod.c` (table_read skips avxm / avxn), `netpack.py` + `netpack.schema.json` (key `avenue_junction_lines`) |

Pieces: box cells 20805..20809, 20812..20849, 21750..21767 (61, one per outline x modes, saved as 43 / 39 / 11203 / 29
by their closed edges); one-way noses 20800 (no nose) 20801 (E) 20802 (W) 20803 (both) with avcore's 21700 lanes;
two-way noses 20810 / 20811 (AVX's) and 20804 (both). 8 new curve shapes 23700..23707, every lane spec without path
keys and `"mirror_uk": false`.

Changes from the plan: (1) each avenue arm of a box is its own avcore band, so an arm can stay two-way while the
others convert: its edges turn two-way (T); a row / column keeps its one-way flow while any arm of it is one-way
(this keeps the piece count at 61; every movement the two-way arm offers still exists). (2) A box is written only if
every one-way / two-way combination of its arms has a declared piece. (3) Validation: a box whose edges do not meet
its neighbours (all arms one-way) is left stock, the rule re-runs. (4) Every piece saves as its base (no
`avx_save_id` override).

## Offline (15 shipped cities, `avjunc_rule.py check`, `avjunc_build.py check`)

- Boxes after validation: Berlin 415, London 378, Liverpool 243, Madrid 246, Frankfurt 169, Moscow 154, Seoul 147,
  Sacramento 64, Craterville 20, Madison 10 (dropped by validation: 20 / 36 / ... / 4).
- Edge check with avcore's band decisions (twin of its rule, an APPROXIMATION): 50,121 edges meet, 67 do not; all 67
  are stock-identical (a stub road that does not connect, a two-way nose at the map edge).
- Lane specs compile in ENGLISH and English-UK, every lane on a ground (y 0) curve whose end points are the lane's,
  every node has an edge; one-way noses meet avcore's 21700 in all four states, both languages (`avlanes.check`).

## In game

| step | result |
|---|---|
| lab: avenue A (rows 20 / 21) drawn, then a road x avenue, a road T, avenue B crossing (avenue x avenue) and ending on a road, avenue C ending on A | every kind boxed (20805 road x avenue, 20805 / 20806 road T, 20807 x4 ring, 20809 / 20808 / 20807 avenue T, 20812 / 20813 avenue ends on a road), one-way noses beside each box, avcore converted every band (U-turn ends 21701) |
| bug found: AVX reverted boxes and noses outside the seeds of a pass; the revert's retile spread into avcore's converted cells | fixed: reverts only within the edit box + 2 (whole map on load) |
| bug found: the link cells of a crossing avenue (stock T pieces between a box and its straight halves) did not become noses when the box was found from the other avenue | fixed in twin and C: noses also chain out of the crossing spans |
| save | `76 variant tile(s) written as base`; read offline: only stock ids (box cells 43 / 39, noses 11204) |
| reload (lab3_saved) | `load: all 76 variant tiles restored`, load pass converts all bands, avx_post via avcore's post-AVL phase writes nothing more |
| a game WITHOUT sc3netmod (inst_nomod: mods_launch + sc3resize only, PID 21920) on that save | loads stock pieces only (cells 40..76 x 10..36: 11203 8, 11204 84, 11225 5, 29 23, 39 5, 43 9), a sane stock layout (`game_nomod_z3_r0.png`) |
| bulldoze the road T's arm | the T box goes back to stock and avenue A runs one-way through (21700) |
| Seoul load | 150 junction boxes, 106 bands one-way (avcore 1,250 cells; 1,482 with its crossing variants installed), no exceptions |
| Seoul traffic (hwtraffic_probe) | failed trips per full sim month (month 1 after load is partial and not counted): PID 54208 months 2..4 2.05 / 2.02 / 1.91%; PID 41944 month 2 1.59%; PID 47568 month 2 2.12% (probe attached to the running game). Light, one game each (M1's stock-matrix arm: 1.74..2.36%). LANEDENSITY ran 2.08 M evaluations on the variants in one 18-minute game |

### Test trap: Frida hooks installed while paused, then unpaused by the probe

Not a defect of the pieces. Several Seoul games went "Not Responding": a true deadlock (CPU time flat; the main thread
in the street sim's car move STRTSIM FUN_1001b680 / FUN_10018750 -> sprite vt+100 -> SIMSPR -> SIMCITY FUN_1000d310
EnterCriticalSection; two SIMSPR render threads waiting on locks; Frida stacks via `avjunc_stacks.py`). Every hang had
the same sequence: a Frida probe hooked into the game while it was paused (hwtraffic_probe, or a segment tracer), then
unpaused by the probe's `--start`, with one-way junction pieces or avcore's U-turn end on screen at zoom 4. Seoul
copies, test tree Simcity_stock_avjunc, one run each:

| PID | build | view (camera, zoom 4) | Frida | result |
|---|---|---|---|---|
| 54208 | full | box (50,130) | probe --start, then camera call | hang |
| 21768 | full | box (50,130) | probe --start | hang |
| 70424 | AVX + AVL off | (50,130) | probe --start | no hang, 1 month |
| 22968 | AVX on, AVL off (two-way boxes) | (50,130) | probe --start | no hang, 1 month |
| 58120 | full | plain 21700 stretch (22,42), then box (50,130) | probe --start | no hang 1 month, then hang |
| 35512 | full, new curves sort id 0 | box (50,130) | probe --start | hang |
| 7468 | full | avenue ends on a road (33,130), then ring (61,63) | probe --start | no hang 1 month, then hang |
| 5460 | full, box flag 0 | ring (61,63) | probe --start | hang |
| 32452 | full | ring (61,63) | segment tracer + keys | hang |
| 41944 | full, ring left lanes off the radius-80 left | ring (61,63), (50,130), then U-turn (51,63) | probe --start | no hang 1 + 2 months, then hang on the U-turn |
| 15660 | same lanes as 41944 | ring (61,63) | probe --start | hang |
| 47568 | full, original lanes | ring (61,63) 7 min, U-turn (51,63) 5 min, speed 2 by keys | none; then hwtraffic_probe attached to the RUNNING game (2 months) | no hang (2.08 M LANEDENSITY evaluations) |

The single-run bisect first pointed at the radius-80 left-turn curve; 15660 (same lanes as the passing 41944) hung, and
47568 ran clean with no probe hooked at unpause, so that reading was noise. Why hooks installed while paused plus an
unpause deadlock is [UNCERTAIN]. Rule: attach Frida probes after the sim is running, not with `--start` from paused.
The delivered lanes are the original ones (left lane to left lane).

## Rebuild on child/avcore 0b189f8 (merge 2936359): curve sort ids

hwlanes now writes the curve record's trailing u32 (path sort id) by height. Rebuilt and reinstalled avenue_lanes +
avenue_junctions in the test tree: avjunc_build check PASSED; installed overlay VPATHATT, ENGLISH and English-UK: my
shapes 23700..23707 (32 records each) all sort id 0 (stock flat curves: 0); 16 records with 2 are avcore's slope
shapes 23604..23607 (heights -512 / -256 to 0). No change to any tracked avjunc file (the sort id is written at
install). Seoul, PID 17124, nothing hooked, speed 2 by keys, 180 s: 150 boxes / 1,482 avcore cells on load, no hang,
LANEDENSITY 620,983 honoured steps, trips through box cells (20813 at (33,130): exits on several sides, 0 wrong-way)
and noses.

## Not done / open

- Cars keeping their lane through a box was not traced car by car (the shots show traffic on converted avenues and
  junctions; lanes meet by construction, offline check above).
- English-UK not run (no English-UK install here); lane specs compile there.
- Avenue corners (PLAN 6.3) and diagonal joins (avdiag) still refuse the bands that touch them.
- Owner calls: the box look (AVX's), the one-way ring for avenue x avenue.

## Corner junctions (2026-10-19, on child/avjunc 5af604d = avcore ea549c3)

Avenue corners whose OUTER cell is a stock T 39 / X 43 with plain roads (29) leaving its outside (avcore's scope:
"T with one road" 110 ends, "X with two roads" 30). avcore writes the inner bend 21726 and the two halves 21700 and
accepts the outer cell when it holds an avlj-declared piece; AVX owns the outer cell.

| piece | outline / modes (N E S W, state 0) | base, art | avlj |
|---|---|---|---|
| 21768 | ACAA / ICTO (T) | 39, stock 39's | I..O |
| 21769 | ACAA / TCOI (T) | 39, stock 39's | ..OI |
| 21770 | AAAA / ITTO (X) | 43, stock 43's | I..O |

Lanes (`avjunc.cell_lanes(corner=True)`): the avenue's two lanes turn through the cell lane by lane, the curb lane also
turns onto the road, the road keeps two-way lanes. No new curves, no new art. Rule (`avjunc_rule.corner_at`, C
`avx_corners`): the avenue enters the cell from a half running into it and leaves into a half running away, both
halves' medians toward the inner bend diagonal to the cell; the other sides a connected 29 or closed, at least one
road. The state comes from matching the in / out pattern (not the stock state). avx_run writes it; avx_post keeps it
when avl_dir() is set on both halves, else writes the original stock T / X back (no retile). No avl_corner_ok() dry run
in avx_run: there the boxes and noses ending the group's other bands are not written yet, so a load pass refused
every corner (measured: 0 of 28 in London with it, 10 without).

Offline: 73 such outer cells in the 15 cities (London 28, Frankfurt 15, Liverpool 11, Berlin 9, Moscow 4, Madrid 3,
Sacramento 3) = 141 of avcore's 212 T / X ends (two ends per corner; the rest are "T next to T", bends, others: stock).
Lane check PASSED (ENGLISH + English-UK); 48 seam checks against 21700 (3 pieces x 4 states x both avenue sides x 2
languages): 0 problems. avcore's own check of the letters against its rule: every T fits; the X fits at the state the
writer computes.

In game (London, test tree Simcity_stock_avjunc, sim started by keys, no Frida while paused except the reads noted):

| PID | step | result |
|---|---|---|
| 73196 | before avcore accepted outer cells | 28 corners found and written, all put back to stock in post (fallback works) |
| 32692 | load | 10 of 28 converted (2 x 21768, 5 x 21769, 3 x 21770), each with 21700 halves and 21726 diagonal; avl 1,484 cells (1,302 without the corners); the final build (with the refusal below) 1,468 |
| 63124 | run 5 min, nothing hooked | no hang; LANEDENSITY 2.54 M honoured steps; trips through corner (67,174) 21769: 208 / 136 steps on its two entry sides, 0 wrong-way |
| 55716 / 44956 | load, save at once, reload (full-map reads with a long timeout) | 10 corners, 18 inner bends after reload; every cell present in both reads identical; `load: all 3931 variant tiles restored`; avx run / post 0 reverted |

Two fixes found on the way (both for the whole AVX block, not only corners):
- A reload changed the result: the noses chained from link cells (stock T / X joining the halves) were saved and
  restored as ordinary noses, which then counted as band rows, so segments, boxes and noses changed (London: 104 cells
  reverted on reload, avl 157, corners lost through their all-or-nothing groups). Link noses now have their own ids
  (one-way 21771..21774, two-way 21775..21778, same art and lanes) and stay links; a nose on a straight pair stays a
  band row. Offline reload check (`avjunc_reload.py`): London, Berlin, Liverpool, Madrid, Seoul, Frankfurt: 0 boxes
  lost, 0 cells changing on the second pass (before: London 2 lost, 680 cells).
- A box cell next to a piece whose connections the rule does not know (diagonal road pieces 35, 11211..11214, 14030,
  15138..15141 ...) is now refused (left stock) instead of skipped in validation.

Trap noted again: a Frida camera move with the sim RUNNING also deadlocked one game (PID 32692); avcore saw the same with
a camera call while paused followed by an unpause. Run checks with no Frida attached; move the camera and read cells
only as the last steps, and expect a possible hang there.

Piece table: `pieces` regenerated 57 patterns (all inside the committed 61); the committed table is kept so every id
stays where it was (saved cities store variant ids).

Sheet: `MAIN\verify\avjunc\owner_shots\avjunc_corner_sheet.png` (lanes of the three pieces + London (144,57)).

Corner piece states (avcore's check, 49ddf65): the writer takes the state from the in / out pattern. Over the 73 shipped
corners: every T at its stock state (58 of 58, so the stock 39 art lines up), every X at avcore's k = (inner 11203
state - 1) & 3 (15 of 15). London X corners after reload (final build, full-map read): (144,57), (157,102), (194,125) =
21770.0 with inner 21726.1 diagonal, both bands one-way (21700 runs of 5+ cells, two of them ending at our boxes /
noses). Cars through an X corner were not traced one by one (routing counts were read for the T at (67,174) only).
