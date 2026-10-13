# lanekit: pre-registration (2026-10-13, written before any game run)

Task `lanekit` (child of the round orchestrator, branch `child/lanekit`). Static findings this test rests on:
`re/analysis/NET_LANES.md` (being written). Tools: `re/tools/netmod/lanekit.py`, `netpack_lanes.py`.

## Setup (all arms)

- Tree: `C:\Users\maria\Desktop\Proyectos\Simcity_stock_lanekit`, hard links of `Simcity_stock` made by
  `link_tree.py` (stock DLLs, no release mods in Apps, Spanish text in the ENGLISH folder).
- Instances (CHILD_PROTOCOL 10): `Simcity_stock_lanekit\re\harness\inst_lanekit` (mods_launch.exe -multi, sc3resize.dll,
  sc3netmod.dll) and `inst_lanekit_ctl` (same files). Control runs set `SC3NETMOD_OVERLAY=0`, so the game reads the
  stock files and the only difference between arms is the overlay. sc3netmod.dll copied from
  `Simcity_stock_netramp\re\harness\inst_netramp` (source merged in round/1012), hash recorded in RESULTS.md.
- City: copy of `Cities\Berlin, Germany.sc3` (256 map; 514 straight highway cells 73 / 15051; 2,121 T junctions 39),
  one copy per instance. Windowed. Own PID only (`SC3_PID`), stopped with taskkill /PID.
- Measurement: Frida, read only, `verify/lanekit` driver `re/tools/netmod/lk_probe.py` (hooks listed per arm). The game
  is never written by the probe.
- Packages installed with `netpack.py install --tree <tree> --allow-tree` (overlay mode), one arm at a time.

## Arm H: the turn matrix steers the SimTransit trip router (highway)

Package `example_connects_hway_block`: exemplar prop 310 of pieces 73 and 15051 set to 0 (both halves).

Probe: hook SimTransit `FUN_1000755e` (capture the traffic layer `this`, read `this+0x54` once) and SIMNTWRK
`FUN_1000d73d`, counting calls whose return address is inside SimTransit.dll, by piece id (the occupant's exemplar
instance through `this`) and by result (any of the four outputs true / all false). Every 20 s: game date, sum of the
live surface density grid `this+0x6c` over the 514 straight-highway cells and over the whole map.

Predictions (arm H vs control, same city, same sim speed, >= 60 game days each):
- H1 `this+0x54` reads 1 in both arms (the low half = the ENGLISH lanes, NET_LANES.md). If it reads 0 the
  "low = ENGLISH" reading is wrong and is corrected, not explained away.
- H2 router queries on 73 / 15051 cells: arm H 100% all-false; control <= 5% all-false.
- H3 highway-cell density sum after >= 60 game days: arm H <= 20% of the control's.
- Control check: road-only router steps never call `FUN_1000d73d` (calls come from highway / bus node types only):
  every hooked call's piece is a highway / highway-road piece. A road piece (29, 39, 43 ...) in the list falsifies the
  "road trips ignore the matrix" reading.

## Arm S: TrBlkAtt lanes steer the street sim (animated cars)

Package `example_lanes_t_exit_only`: TrBlkAtt records of T junction 39 (states 0..3, all 7 languages) without the two
lanes that enter from the stem (local side x-). Turn matrix untouched.

Probe: hook STRTSIM `FUN_1001c750` (a vehicle leaving cell (x, z) by an exit edge, `+0x16` = exit code) and log
(x, z, code, result != 0). For each transition whose NEXT cell is a 39 cell, the entry side in that cell's local
frame is `(w - state) mod 4`, w = world side of the T facing the previous cell.

Predictions (camera at street zoom over T junctions so the street sim has vehicles; >= 200 transitions into T cells
per arm, else the arm is inconclusive):
- S1 arm S: transitions into a T cell through its stem (local x-) that succeed: 0. Control: > 0.
- S2 arm S: transitions into T cells through local z- / z+ succeed at a rate within 20 points of the control's.

## Arm D: demo piece, a 2x2 one-way roundabout of a NEW id

Package `example_roundabout`: variant 20400 (base 39, art from 39 recoloured yellow), TrBlkAtt from
`quarter.lanes.json` (39 with 3 of its 6 lanes: z+1 -> x-2, z-2 -> z+2, z-2 -> x-2), connects auto.
City: the Berlin copy with cells (22,152) (23,152) (23,153) (22,153) set to 20400 states 2, 3, 0, 1 by
`network_layer.py set_piece` (their stock pieces: 39/2, 39/3, 39/0, 43/0). Ring order in world cells:
(22,152) -> (23,152) -> (23,153) -> (22,153) -> (22,152).

Probe: the S hook, filtered to the four ring cells and their four spur cells (22,151) (24,152) (23,154) (21,153).

Predictions (>= 30 transitions out of ring cells, else inconclusive):
- D1 the game loads the four cells as piece 20400 (Frida cell read) and draws them yellow.
- D2 every transition from one ring cell to another follows the ring order above; 0 against it.
- D3 transitions from ring cells to their spur cells and from spur cells into ring cells both occur.
- Control (stock site, overlay off; the four cells are the stock 39/39/39/43): ring-to-ring transitions against the
  ring order occur (> 0).

## Not tested here

English-UK in game (the language is a registry setting shared with the other sessions); 1024 maps; the owner's dev
install; tiler behaviour of a piece whose matrix row is empty (static: TILER_SIM.md 6, warned by netpack_lanes).
