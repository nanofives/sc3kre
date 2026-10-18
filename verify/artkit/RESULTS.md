# artkit: RESULTS (2026-10-13)

**Verdict: new network geometry authored with the kit draws in game on stock DLLs, at every zoom and rotation,
exactly as stock art does.** A 2x2 mini roundabout (one new id, 20400, four states) built from stock parts by the
compositor matches its offline composite as well as stock T pieces in the same cells match theirs (20 of 20 frames
within 0.15 points, same offsets). Frames of a new size (Blender-rendered lamps, 20401) draw at the right place, but
the engine overdraws the top of taller-than-base network sprites on some cells in view rotations 0 and 2 (arm D),
because road pieces carry the first-pass draw bit. Clearing it in the package (`"first_pass": false`) gives
complete lamps in all four rotations (arm F, exploratory). Data only, no code patch.

Pre-registration: `PRE.md`, commit c67abac, before the first run. Tree `Simcity_stock_artkit` (hard links of
`Simcity_stock`, `link_tree.py`), instance `re\harness\inst_artkit` (mods_launch, sc3resize, sc3netmod built from
child/artkit), packages installed in overlay mode. Cities: Berlin copies edited with `plant.py`, cells
(33..34, 213..214) + two stock road 29 cells on each exit. PIDs 43960 (A), 39164 (B), 30864 (D), all mine,
stopped (and 41748 = E, 17908 = F, exploratory). Frames: sc3resize in-process dumps through `nramp_cam.py` (camera centred on (34,214)). Dumps and diffs
stay in the instance folder (game art).

## Arms

| arm | result | prediction |
|---|---|---|
| A control (`berlin_ctl.sc3`, T 39) | A1 cells (33,213) 39.3, (34,213) 39.0, (33,214) 39.2, (34,214) 39.1 (`np_drive cells`). A2 four stock T junctions drawn | met |
| B roundabout (`berlin_rb.sc3`) | B1 cells read 20400 with states 3,0,2,1, attrib key 0x4fb0. B2 the roundabout draws at all 20 zoom x rotation dumps (owner_shots 01-03). B3 equal 5/6/5 pixels vs the offline composite: zoom 4 95.43 / 89.87 / 95.93 / 96.61 %, zoom 3 94.96 / 89.30 / 95.37 / 96.04 %, zoom 2 92.61 / 86.45 / 92.79 / 93.30 % (rotations 0..3) | B1, B2 met. B3 NOT met as written (>= 98 %). The control shows the bar was wrong, see below. B4 mis-stated (see below) |
| D lamps (`berlin_lamps.sc3`, 20401, frames 128x208 at zoom 4, T 175) | D1 cells read 20401 states 3,0,2,1. D2 lamps drawn in all 20 dumps; in rotation 1 complete; in rotations 0 and 2 the two back lamps lose their heads on a horizontal line, the same at two camera positions. D3 zoom 4: 94.88 / 89.97 / 95.37 / 95.74 % | D1 met. D2 NOT met (cause and fix: section "Clip"). D3 not met as written, same engine residue as A and B |

Deviation from PRE: arm D used the same Berlin box as A and B (cells 33..34, 213..214), not another box.

**Why B3 is not a defect of the art.** The same comparison on the control A (stock T 39 in the same cells, offline
composite of stock frames) gives the same numbers within 0.15 points in all 20 frames (zoom 4: 95.36 / 89.74 /
95.86 / 96.53 %) and the same alignment offsets. The mismatched pixels are other objects drawn in front of the
cells (trees, two factory chimneys in rotation 1, a helicopter) and a 1 px rim on the front edges of the road
cells. Inside the art itself no pixel differs (diff images `inst_artkit\diff\B_z*_r*.png`). The pre-registered 98 %
did not account for occluders in that part of Berlin.

**B4** ("no terrain pixel inside the cells") was mis-stated: the roundabout quarter leaves grass outside the ring
by design. The seam question it meant is covered by B3's diffs: no mismatch along the shared cell edges.

## Clip (arm D) and the fix (arms E, F, exploratory, after PRE)

Code (read for this task, SIMSPR): the cell's vertical range comes from the CURRENT frame's own anchor T (occupant
vt+0x14 = 0x100159e2 -> 0x1005ad34 -> 0x100014e7, stored as s16 at cell+4 by 0x10007b4d / 0x1000b352), with no
cap, so T 175 reaches the engine intact. The cut comes from draw order instead: a frame table's LayerFlags (u32 at
header +0x12, reader 0x10001c90) bit 0x80 becomes cell flag bit 0 (0x100192aa), and `FUN_1000dc17` draws every
such record in a pass BEFORE all other records. Road T 39 and straight 29 ship LayerFlags 0x80 (highway 73: 0,
curve 11203: 0xC0), and the variant's table is a copy of 39's. What the second pass draws over the region above
the cell covers the part of the sprite that sticks up.

| arm | change | result |
|---|---|---|
| E (pid 41748) | 20401's table byte +0x12 0x80 -> 0x00 by hand in the overlay CSAttrib_Korea.IXF | all 4 lamps complete at zoom 4 and 3, rotations 0..3 |
| F (pid 17908) | same through the package: `"art": {..., "first_pass": false}` (netpack edits the bit), reinstalled | all 4 lamps complete in all 20 dumps; match zoom 4: 95.49 / 89.93 / 96.00 / 96.66 % (D: 94.88 / 89.97 / 95.37 / 95.74) |

Zooms 0..2 of F match 1-3 points lower than D. The D and F dumps of the same view also differ outside the piece
(zoom 2 rotation 0: 99,787 px, bounding box the whole view), cause not established, so that change is not
attributed to the bit. Not tested: cars and pedestrians on
a cell whose first-pass bit is cleared (the cell now sorts with them by depth); no traffic ran on the planted roads.

## Offline evidence

- `netart.py geometry`, `check-rot` (NET_ART.md 2, 6).
- Blender calibration on flat tile 39: zooms 3-4 0 mismatched px, zooms 0-2 4-8 px all within 1 px of the edge;
  held-out road 29 identical (NET_ART.md 9.2).
- `netpack.py selftest`: 0 failures, including U11 (80x50 frame + anchors.json -> record 80x50, anchor
  (8, 31, 72, 19)).
- Packaged records (overlay DAT): 20400 frames keep 39's sizes; 20401 zoom 0..4 = 8x14 .. 128x208, T 11 .. 175.

## Not covered

Traffic over the piece (lanekit), placement by tool (multitile), save + reload with the new id (proven for
variants by netvariant, not re-run here), the owner's dev install, 1024 maps.
