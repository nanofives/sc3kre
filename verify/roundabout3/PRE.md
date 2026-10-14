# roundabout3: pre-registration (2026-10-14)

Owner decisions of 2026-10-14 on the 20400 roundabout (package `re/tools/netmod/examples/roundabout`), after the
roundabout2 pictures: (1) no arrows on the ring, (2) find and fix the small white lines along the roundabout's outline
where it meets asphalt, (3) automatic placement instead of the T key, also on load, with revert. Branch
`child/roundabout3` from `child/roundabout2` 1967900. SIMNTWRK.DLL addresses are Ghidra VAs (image base 0x10000000).

## Build under test

- `sc3netmod.dll` from this branch: new RBT block `re/harness/src/sc3netmod_rbt.c` (+ 11 lines in `sc3netmod.c`),
  `sc3resize.dll` (frame DUMP), `mods_launch.exe`, built with `re/scripts/build_mod.ps1` into the instance below.
- Package `roundabout` 3.0.0: the `templates` section is gone (no T / R key, no Protected list entry, no Collapse group),
  new manifest section `auto_roundabouts: [{"piece": 20400, "min_arms": 3}]` -> table line `rbt 20400 3`;
  `paint.json` `"arrows": []`. `netpack.py validate`: OK. `netpack.py selftest`: 0 failures.
- Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_roundabout3`: hard links of MAIN `Apps`, `Buildings`,
  `Cities`, `Scripts`; `Apps\GZGraphicD.dll` and `Apps\SIMSPR.DLL` replaced by the `.shipped` copies (SHA-256
  48201f47..., eec71500...: stock); config files de-linked; SIMNTWRK.DLL = 693f6572... (stock). Package installed in
  overlay mode. Instance `re\harness\inst_rb3` (+ `inst_rb3_nomod` without sc3netmod for the stock-safety arm).
- Every game is mine, started with `mods_launch.exe -multi -- -intro:off <city>`, stopped by its own PID.

## The rule (owner item 3), as implemented

A block is the 2x2 of ROAD cells with origin (X, Z). Cell states of the stock pinwheel: (X,Z) 3, (X+1,Z) 0, (X+1,Z+1) 1,
(X,Z+1) 2. Each block cell serves one exit: state 3 -> W (X-1,Z), 0 -> N (X+1,Z-1), 1 -> E (X+2,Z+1), 2 -> S (X,Z+2)
(the 20400 template's edges). Closed cells: (X-1,Z+1) (X,Z-1) (X+2,Z) (X+1,Z+2). "Road" = an occupant of the surface
layer that the manager's network test vt+0x14c accepts for netType 1 (`FUN_10007791` -> `DAT_100323c0`, the ROAD
predicate the rect retile gathers nodes with) [CONFIRMED @ 0x10007791, 0x100151f1].

The block becomes 20400 (same states) when ALL hold, and returns to stock road when one stops holding:
- (a) the four cells are the stock pinwheel: right state, and T 39 where the exit holds road, curve 11203 where it
  does not (20400 counts as either);
- (b) no closed cell holds road (a road into a closed side, an avenue along a side, or another 2x2 beside it);
- (c) no exit that holds road is part of a 2x2 of road outside the block: the exit, the corner cell beside it
  (W (X-1,Z-1), N (X+2,Z-1), E (X+2,Z+2), S (X-1,Z+2)) and the two cells beyond those, away from the block, are not
  all road (a 2-wide road arriving at the exit, or another 2x2 block there);
- (d) at least 3 exits hold road.

"Touches an avenue / another 2x2", in piece ids, from the stock tiler (simulated with `tiler.py`, the offline retile
that matches the saved tiles 99.83% on ROAD, `TILER_SIM.md`; the in-game arms below check it):

| case at (X,Z) = (120,120), roads drawn one stroke at a time | stock tiles of the block (row Z / row Z+1) | stock tiles around | verdict by the rule |
|---|---|---|---|
| 4 arms | 39.3 39.0 / 39.2 39.1 | arms 29.x, ends 11225.x | converts |
| 3 arms (no S) | 39.3 39.0 / 11203.2 39.1 | | converts |
| 2 arms W, N | 39.3 39.0 / 11203.2 11203.1 | | stays (d) |
| 2 arms W, E | 39.3 11203.0 / 11203.2 39.1 | | stays (d) |
| dead end (1 arm W) | 39.3 11203.0 / 11203.2 11203.1 | | stays (d) |
| 3 arms + 2-wide road on N (exit + corner columns) | 39.3 39.0 / 39.2 39.1 | N exit 39.2, corner 11203.1, beyond 11204.1 / 11204.3 | stays (c) |
| 3 arms + 2-wide road on N (closed + exit columns) | 11204.1 11204.3 / 39.2 39.1 | 11204 up the avenue | stays (a, b) |
| two 2x2 side by side (second at X+2) | 39.3 11204.2 / 39.2 11204.0 | second block 11204.2 11203.0 / 11204.0 39.1 | both stay (a, b) |
| second 2x2 offset one row (at X+2, Z+1) | 39.3 39.0 / 39.2 39.1 | second 39.3 11203.0 / 11203.2 11203.1 | stays (c); the second stays (a/d) |
| 4 arms + road into the closed W side | 11204.2 39.0 / 11204.0 39.1 | W exit 11204.2, W closed 11204.0 | stays (a, b) |
| mirrored pinwheel (arms on the other cell of each side) | 39.2 39.3 / 39.1 39.0 | | stays (a): no mirrored piece exists |

Diagonal roads (DIAG_Set piece 35) and roads that bend right after the exit pass (c) (no 2x2 of road), so they count
as single-road arms. Offline twin of the rule on a save: `re/tools/netmod/rb_auto.py scan`. On the 16 shipped cities:
**7 blocks qualify**: Berlin (29,86) 3 arms, (57,167) 3, (145,102) 3; Craterville (132,148) 4; Moscow (30,54) 3,
(92,141) 3, (122,130) 4. None in the other 12 cities. (Berlin's roundabout2 site (25,181) holds a 4-way 43.0: it does
not qualify.)

Design calls (stated, not owner-asked): conversion is free (the road is already paid for); 20400 is NOT in the
Protected list, so any stock retile that reaches the block re-places it as stock road and the RBT pass converts it
again when it still qualifies (that is how revert works); demolishing one block cell removes one cell (no Collapse
group). On a 3-arm block the cell without an arm is drawn by 20400 too (its arm reaches the block edge, no road
beyond); saves write that cell as curve 11203, the stock tile, so a game without the mod opens exactly the stock tiles.

## Mechanism (read for this task)

- Retile pass `FUN_1001547b(this = manager, list by value (4 bytes), netType, int box[6])`, `ret 0xc`; it writes the
  box of its work list into the 4th argument before the rule stages [CONFIRMED @ 0x1001547b, ret at 0x100162f2]. Called
  by the rect retile `FUN_100151f1`, the drag build `FUN_10014a23` and the On-ramp build `FUN_1000abde` (only callers in
  the export). Entry `mov eax, 0x10027a52 / call 0x100266d4` replaced by a jmp to the RBT wrapper, which runs the pass
  and then, for netType 1, the rule over every block whose cells, closed / corner / beyond cells touch the work box.
- Load: manager vtable 0x1002c7bc slot +0x1c = `FUN_100130e9` (the network layer load, `this` = manager: it reads
  +0x3c / +0x40 / +0x44) [CONFIRMED @ 0x1002c7d8]. Wrapped; after it returns a message is posted to the game window
  and the full-map pass runs from that window procedure.
- Convert: `FUN_10008919(layer, pos, 20400 << 8 | state, -1, 8, 0)` per cell, as the TMPL click; equivalent to the
  stock commit `FUN_100165d8` (factory 0xc14f8955, remove incumbent, height from terrain, insert, side table)
  [CONFIRMED @ 0x10008919, 0x100165d8]. Revert: manager vt+0xb0 = `FUN_100151f1(rect of the block, mask 3)`.
- Cell read: surface layer vt+0x7c(x, z, &occ) (as `FUN_100165d8`), occupant +0x10 bits 30-31 = state, +0x14 low 16 =
  id (np_drive `cells`, `QUERY_ID.md` 2), occupant vtable inside SIMNTWRK, released with vt+8.

## Arms and predictions

Logs are the instance's `sc3netmod.log`. Grids are read live with `np_drive.py cells` (Frida, read only).

**L, install.** Log has `rbt: ... automatic 2x2 roundabout = piece 20400, at least 3 arm(s)`, `rbt: hooked the retile
pass ...`, `tmpl: no templates in the tables`, `### READY` with load patched. No `### rbt` error line.

**TH, threads (gate).** The load pass message and the RBT pass after a tool edit log the same thread id as the
`rbt: city load` line, or the load pass runs on the thread that runs tool edits. If the load pass runs on any other
thread than the one that runs tool retiles, STOP: the load pass is unsafe and is redesigned before any other arm.

**A, stock cities on load.** Moscow and Berlin, shipped saves (copies): the load pass logs `3 qualify, 3 converted`
for each; the cells at the predicted origins read 20400 in states 3,0 / 2,1 (as rows: (X,Z)=3, (X+1,Z)=0,
(X,Z+1)=2, (X+1,Z+1)=1); every other cell of a 9x9 box round each block reads as in the save. Craterville: 1.

**B, building cases** (Roadless Paradise copy, roads with the Road tool through `mt_drive.py road`, sites 12 cells apart,
grid read after each stroke). Predicted final grids = the table above, with the converting cases reading 20400 at
the four block cells (same states):
- B1 4 arms: converts on the stroke that completes the third arm; still 20400 after the fourth.
- B2 3 arms: converts.
- B3 2 arms W,N and B4 dead end: stay stock (grid as the table).
- B5 3 arms + 2-wide road on N, exit + corner columns: stays stock.
- B6 two side-by-side 2x2 with arms: both stay stock.
- B7 revert by avenue: a converted 3-arm block, then a second road beside its N arm (corner column, 3 cells): the block
  goes back to the stock tiles of B5's row.
- B8 revert by demolish: a converted 3-arm block (arms W, N, E), demolish the E arm's first cell: the block goes back
  to the 2-arm stock tiles 39.3 39.0 / 11203.2 11203.1, no 20400 left.
- B9 revert by a second 2x2: a converted block, then a 2x2 built at (X+2, Z+1) (on its E exit): stays/reverts to stock.
- B10 demolish one block cell of a converted block: 3 cells left, none 20400.
Each converting case logs `rbt: edit: (X,Z) -> roundabout`; no `### rbt` exception line in the whole run.

**T, traffic.** Moscow (122,130) after the load conversion (4 arms), sim running, `rb_island.py 122,130 --secs 480`:
ring moves with the order (counter-clockwise) > 0 and against = 0; vehicle samples closer than 129.5 to the block
centre = 0 (roundabout2: 78 / 0, 0 of 8,297).

**S, saves.** Save the converted Moscow. Log `save: N variant tile(s) written as base` with N = 12. `netvariant.py scan`:
0 raw variant tiles; section 0x4E56 lists the 12 cells; the saved word of the two arm-less cells of the 3-arm blocks
((30,54) block and (92,141) block, one cell each) is 11203, the others 39.
- S0 (instance without sc3netmod): the save opens; the 12 cells read the stock ids and states of the shipped Moscow save,
  every other cell of the 9x9 boxes equal.
- S1 (with the mod): `load: variant section 12 entries, 12 to restore`, `all 12 variant tiles restored`, load pass
  `3 qualify, 0 converted, 0 reverted`; grid equal to S.

**V, outline line (owner item 2).** Lab: Roadless Paradise copy with B1's 4-arm block (no buildings, no zones, so no
traffic and no occluders), saved once with the camera on the block. Two games load that save: stock art (instance
with `SC3NETMOD_RBT=0`: the block is stock 39) and roundabout (RBT on). In each, in-process frame dumps at zooms 2, 3, 4 x
rotations 0..3 (12 views), sim paused, same camera calls. Outline set O = pixels within 1 px of the block's outer
diamond edge (from the projection, NET_ART.md 2). "White" = all of R, G, B >= 200 (8-bit, from 5/6/5).
- V0 (before the fix): W = |{p in O: white in the roundabout frame and not white in the stock frame}| per view.
  Expected W > 0 in at least one view (the owner saw the line); each W pixel is traced to its source by comparing it
  with (i) the 20400 frame pixel at that position, (ii) the neighbouring cell's frame pixel, (iii) the terrain; the
  cause is written down before any art change.
- V1 (after the fix): W = 0 in all 12 views; `netpaint.py seams` still 1320 / 1320; the in-block pixels away from the
  outline unchanged except where the fix says.
- No arrows: the 20 frames of the 3.0.0 package hold 0 pixels of the marking white inside the ring band
  (radius 136..211 from the block centre) outside the give-way dash ring (211..218); 2.0.0 frames hold > 0 there.

**O, owner pictures.** `MAIN\verify\roundabout3\owner_shots\`: before / after crops of the outline at zoom 4 (x4) and
zoom 3, the 4 rotations at zoom 4, a converted stock-city block, a revert sequence, with `captions.md` in Spanish.

Anything not met is reported as not met. Changes after this file (art fix, any rule change) are listed in RESULTS
with the reason.
