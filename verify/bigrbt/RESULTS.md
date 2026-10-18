# bigrbt: automatic 3x3 roundabouts (2026-10-17)

Owner request (via the avenue program): "a 3x3 bigger roundabout where it can be entered twice per side". Light
test: offline mockup, one lab game, screenshots, one save + reload.

Test tree `Simcity_stock_bigrbt`, instance `re/harness/inst_bigrbt` (sc3netmod.dll built from branch child/bigrbt,
215,040 bytes), package `big_roundabout` 0.1.0 installed as overlay, no other package installed. Lab city: copy of
`lab.sc3` (Roadless Paradise, flat patch at alt 82). Owner pictures (untracked):
`MAIN\verify\bigrbt\owner_shots\bigrbt_mockup.png` (offline), `bigrbt_sheet.png` (game).

## Rule (`bigrbt.py check`, `sc3netmod_rbt9.c r9_check`)

Block = the 3x3 cells with origin (X, Z). Converts when all hold: the 9 cells hold ROAD, each a flat stock road
piece (29, 39, 43, 11203, 11204) or an RBT9 piece; the four diagonal cells hold no ROAD; no side has all three arm
cells as ROAD; two neighbouring arm cells on a side are an avenue (the two cells beyond them hold ROAD, both arm
cells flat). Avenue arm cells are written as 11204 with the median toward each other, so the median runs up to the
block. No minimum arm count: a bare 3x3 square converts too.

Offline, on shapes tiled by the stock tiler (`tiler.py`, Roadless Paradise):

| Shape | Result |
|---|---|
| demo: avenues W (cells 0,1) and N (1,2), road E 1, roads S 0 and 2 | qualifies, 7 arms |
| bare 3x3 | qualifies, 0 arms |
| one road on each side's middle | qualifies, 4 arms |
| 2x2 block with 3 arms (RBT's shape) | refused |
| 3x4 block | refused |
| three parallel roads, 9 long (boulevard) | refused |
| 3x3 with three roads on one side | refused |
| 3x3 with road on a diagonal cell | refused |
| 2-wide arm one cell long (a lump) | refused |
| avenue x avenue 2x2 box | refused |

## Art (`bigrbt_paint.py`)

One world scene, every piece one cell of it (diagave_paint.paint_cell). Circular grass island (radius 250 lane units,
11204's median grass) with a yellow edge line (29's centre line pixels) and a concrete apron; one-lane ring; the
outer curb is road 29's own profile at its distance from the ring asphalt, so it ends exactly on the block edge on an
arm-less side; arms are sampled from stock 29 (single roads: the real arm piece, exact seam); avenue arms are 29's
carriageway with 11204's grass median ending in a concrete nose at the ring; give-way dashes across each arm's
inbound half at the ring edge (zoom 3 and up).

Canonical pieces turned to other states: the ring and island sample 29 at state 1 + sector with the point turned
the same way, and each quarter of the ring's texture coordinate is 512 long, so a turned piece shows exactly the
scene's pixels there. Measured on 3,000 random points x 4 views of the NE corner against its SE image: ring 0 / 5,244
differ, outer curb 0 / 2,992 (grass differs by its random hash only). Stock 29's slots k and k + 2 are not the same
image (3,561 of 4,224 opaque pixels differ at zoom 4, dither only), so an arm stub on a piece at state 2 or 3 meets
the stock 29 arm cell with dither that does not continue; the layout is the same.

## Avenue lane lines (owner change, 2026-10-17)

"On avenues instead of yellow lines they should be white striped lines for every lane": the avenue arm stubs inside
the pieces draw the lane line with `lanelines.py` (copied from child/diagave, not edited): footprint = the cut
positions where stock 29's centre line is yellow in at least half the samples along the road (measured per zoom and
view: x 118..138 lane units), white dashes of highway 73's pixels, period 0.25 cell, dash 0.375, phase from the world
along-coordinate, nothing below zoom 2; between dashes the lane asphalt (diagave_paint.mirror). Single-road arms keep
29's yellow line. The island's yellow edge line is not a lane line and stays. The stock 11204 arm cells beyond the
pieces stay yellow until the orchestrator's `avenue_markings` package reskins them. In game (pid 70040, the saved demo
block reloaded): one white dash in each avenue stub at zoom 4 and 3, views 0 and 1; cyan scan 0 pixels in all shots.
Owner sheet `bigrbt_sheet.png` now shows these shots.

## Lanes

VPATHATT has no curve for a lane change between slots 80 and 175 in a straight cell, and new curve shapes are not
written (NET_LANES.md 3), so the ring is ONE lane on the stock slots: x 175 in the E side cell (path 259), the r175
left turn 1024 round the centre cell's corner in the NE corner. Entries and exits: stock right turns 769 / 770 / 771
or straights 259 / 512 where the arm is tangent to the ring (the outer cells' arms). Entry lanes end on the ring
lane's exit node (no exit edge of their own); the turn matrix lists every lane's turn explicitly. Pedestrians: the
block's outer sidewalk, a crosswalk over each arm. `netpack validate`: OK, no warnings. TrBlkAtt: the package adds
56 index slots per language file (14 pieces x 4 states, 862 -> 918), installed with the growing `ixf_insert.py` from
child/diagave f92c5c9. Lanes were not watched in
game (the lab city has no traffic).

## In game (pid 27744, then 56000 after the reload)

| Check | Result |
|---|---|
| three road drags x 106..108 at z 96, 97, 98 | after the third, `rbt9: edit: (106,96) -> 3x3 roundabout, 9 cell(s) written` |
| arms: W avenue (2 drags), N avenue (2), E road, S roads at x 106 and 108 | after each drag the block re-converts; final pieces equal the offline twin cell for cell: 20616.3 20604.3 20616.0 / 20604.2 20600.0 20602.0 / 20613.2 20601.1 20611.1, avenue arm cells 11204.2 / 11204.0 (W), 11204.1 / 11204.3 (N) |
| screenshots zoom 4 and 3, views 0 and 1 (`shots/s2_arms_*.png`) | match the mockup; cyan scan (B > 180, G > 180, R < 90) finds 0 pixels in all 7 shots; no terrain holes seen |
| save (`nr_drive.py save`) | `save: 9 variant tile(s) written as base`; the file read offline holds 43 x 8 and 39.1 (S middle, no arm): a game without the mod opens stock road |
| reload | `load: variant section 9 entries, 9 to restore`; load pass `1 qualify, 0 cell(s) written`; picture identical (`s3_reload_z4_r0.png`) |
| road on the NE diagonal cell (109,95) | the block goes back to stock 39 / 43 |
| that road demolished | re-converts (`9 cell(s) written`) |
| faults | none (`###` lines: only the startup banner) |

## Open

- The ring is one lane: two-lane rings need new VPATHATT curves (lane changes 80 <-> 175).
- Shape overlap with boulevard, ruled by the orchestrator 2026-10-17: an exactly-3x3 block is RBT9's whatever its
  arms; the boulevard needs at least 4 rows. RBT9 keeps refusing any side with three arm cells.
- avx must refuse a 2x2 avenue box that is part of a 3x3 full block (it is ours).
