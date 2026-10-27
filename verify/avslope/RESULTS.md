# avslope RESULTS (2026-10-26): avenues and boulevards on slopes

Owner report (LAN build sc3mods-2026-10-26b): "avenue section on slope doesn't have the lanes, then check for 3 road
avenues for the same" (`MAIN\verify\avslope\owner_shots\img1_avenue_slope_no_lanes.png`).

Verdict: fixed for both. Avenues: the 8 one-way slope ids the AVL block already wrote (21718..21725) now draw the
avenue half (white dashes, median, trees) on the slope. Boulevards: BV wrote FLAT pieces on sloped cells (a terrain
hole and a step, and a save with flat ids on a slope); it now writes 12 new sloped pieces 27100..27111.

## 1. What stock and the mod did (in game, lab, LAN-build sources = main 0284ba7)

Lab `avslope.py lab`: Roadless Paradise with 5 plateaus (PA +1 and PD +2 for runs along x, PB +2 and PC +1 along z,
PE +1 for avenues along a plateau edge). Each plateau carries an avenue (two Road drags) and a boulevard (three), up one
side and down the other, so every slope piece is met at both states (`avslope_lab.py`, posted input only).

| case | stock piece on the sloped cells | netmod before this task | evidence |
|---|---|---|---|
| avenue up / down, along x and z, mag 1 and steep | 11202 / 11201 / 32 / 31 in both halves, state = downhill side | AVL converts the rows to 21718..21725 (one-way lanes right, saved as the slope piece), but those ids had no art of their own: they drew the plain sloped road (yellow line, no median, narrower asphalt = the curb jog) | lab PA..PD cells, frames `before_*` |
| boulevard on a slope | the same slope piece in all 3 cells | BV counts every ROAD cell as a column and wrote FLAT 20700 / 20701 there: in game a terrain hole and a step; the save held 11204 / 29 on the sloped cells (lab_built.sc3: (47,19) 11204, (47,20) 29, (131,7) 11204 ...), so a game without the mod also drew flat pieces on the slope | frames `before_PA_E_z4`, `before_PC_N_z4` |
| avenue halves at different heights | cannot be built: a Road drag along a cell that slopes ACROSS it builds only its first cell (lab PE rows 83 / 94: 1 of 11 cells, an SLE end cap); two adjacent flat cells share their vertices, so a terrace is impossible | n/a | lab PE cells |
| junction 2 cells from a slope (road T onto the avenue) | flat junction, slope pieces beyond | AVX box + the band through the slope converted | lab PA (45,12..15) |

Shipped cities (`avslope.py survey`, 16 cities): 390 slope cells pair across with the same slope piece (avenue rows on
a slope: 170 magnitude 1, 220 steep), 306 slope cells continue an 11204 band along their axis; 0 cells with 11204 on a
non-flat cell, 0 avenue pairs at different heights, 0 three-wide rows on a slope.

## 2. The fix

**Avenues (art only, no code, no new id).** `avslope_paint.py build <avenue_lanes>` paints 21718..21725: per rotation
slot r the variant is the flat 11204 slot q with the same median side (the variant's median is on world side side + 1
at state 0, AVENUE_LANES.md), laid on the slope piece's own plane (slopeend_paint's zoom-4 plane fit). Ground: every
opaque pixel of the stock slope frame is mapped to its tile point on the plane and takes the release's white-dash 11204
pixel there (avenue_markings.frame); where a tree hides the flat ground, the same point seen from the opposite slot;
then the slope frame's own lighting (its asphalt against road 29's). Trees: 11204 carries them in layer 1 (slots 1 / 2)
and inside layer 0 (all slots); they are cut out, given their foot on the median strip (measured in slots 1 / 2, the
same two trees in every slot) and moved up by the plane height at the foot, one whole-pixel shift per tree. One layer,
the slope piece's frame table (its sprite class places the art on the slope), first-pass bit cleared (the trees stand
above the tile). Lanes unchanged (avcore's one-way slope lanes).

**Boulevards: package `boulevard_slopes` + BVS (`sc3netmod_bvs.c`, called by BV).**

| ids | piece | base | lanes |
|---|---|---|---|
| 27100 / 27101 | sloped outer, toward S / N at state 0 | 31 | avenue_lanes 21718 / 21719's one-way slope lanes (20700 has 21700's lane positions 80 / 175) |
| 27102 / 27103 | sloped outer, toward E / W | 32 | 21720 / 21721's |
| 27104 / 27105 | sloped outer, toward S / N | 11201 | 21722 / 21723's |
| 27106 / 27107 | sloped outer, toward E / W | 11202 | 21724 / 21725's |
| 27108 / 27109 / 27110 / 27111 | sloped middle (tree median, two-way) | 31 / 32 / 11201 / 11202 | the slope piece's own two-way lanes |

Art: `avslope_paint.py bvbuild <boulevard_slopes> --boulevard <boulevard package>`: the boulevard's own 20700 (outer)
and 20701 (middle, trees from its layer 1, feet from the lowest trunk pixel) laid on the plane the same way.
Rule: on every cell BV writes, BVS reads the cell's corner pattern from the TERRAIN (FUN_1001a1f3, the call the slope
pass makes, this = the ROAD manager as for the piece writer FUN_10008919 [CONFIRMED @ 0x1001a1f3, 0x10008919]). Not a
legal slope: BV's piece. A slope: outer -> the sloped outer whose lanes run where BV's outer runs (state s toward
(s + 3) % 4), middle / nose -> the sloped middle, both at the slope's own state; any other piece (cap, taper, junction)
-> the stock slope piece. Reading the terrain, not the cell, also repairs the flat pieces an older build left on slopes
(lab run 2: the 24 cells of lab_built.sc3). All save as the slope piece. Off: `SC3NETMOD_BVS=0`.
netpack key `boulevard_slope_lines` (`bvs o <piece> <slope> <side>`, `bvs m <piece> <slope>`).

## 3. In game (lab, all mods except sc3overscroll)

| run | what | result |
|---|---|---|
| 1 (PID 24740) | LAN-build sources, drags PA..PE, frames `before_*`, saved `lab_built.sc3` | section 1 table |
| 2 (PID 31476) | the fix, load `lab_built.sc3` | `bv: load` 6 cells written per boulevard (4 boulevards, the 24 flat slope cells -> 27100..27111, `stats: bvs ... 24 sloped piece(s), 0 left the stock slope piece`); AVL bands with slopes one-way as before; frames `after_*` |
| 2 | edit path: new avenue + boulevard along z over PE, crossing the rows 82 / 93 roads beside the slope cells z 83 / 94 | avenue: 2 AVX boxes + 3 bands one-way, slope cells 21722 / 21723 / 21723 / 21722; boulevard: BV converted columns 83..92 (its ends at the crossing roads stay stock, BV's own rule: "road beside the boulevard is not a straight single road"), the slope column 83 -> 27104 / 27110 / 27105, the stock-left slope row 94 keeps 11201 |
| 2 | save | `save: 477 variant tile(s) written as base`; offline: 0 tile words on a legal slope that are not a slope piece (24 in lab_built.sc3) |
| 3 (PID 24328) | reload with the mod | `load: all 477 variant tiles restored`, BV / AVL / SLE load passes 0 writes |
| 4 (PID 20084) | the same save, sc3netmod not loaded | stock slope pieces on all sloped cells (yellow lines, as stock), no terrain hole, no lost tile; frames `modoff_*` |

Pictures (zoom 4 at the owner's angle and zoom 3 in all four views, same cameras before / after):
`MAIN\verify\avslope\owner_shots\avslope_sheet_z4.png`, `avslope_sheet_z3.png`, frames in `owner_shots\frames\`.
Offline previews: `avslope_paint.py preview` (stock look vs sloped art, zoom 3, 4 views).

## 4. Traffic on the sloped halves (Frankfurt, PID 16432, run 5)

Frankfurt (the shipped city with the most sloped avenue cells) loaded with the fix: 147 bands one-way, saved, sites
from the save's netvariant section (`avslope_trips.py sites`): 100 sloped half cells (21718..21725) and 1,336 flat ones
(21700), each with its lanes' direction. `avslope_trips.py run` (Frida, read-only: every arrived trip's deposit
sequence, SimTransit FUN_100070d0 / FUN_10006edd, hooks of avxroad_trips.py), 300 s at speed 3:

| cells | trips stepping along a half: same order as the lanes | opposite order | cells stepped on |
|---|---|---|---|
| flat halves 21700 (calibration) | 0 | 105,755 | 1,240 of 1,336 |
| sloped halves 21718..21725 | 0 | 8,062 | 89 of 100 |

32,652 trips routed, 32,281 arrived. The deposit sequence is popped destination first, so the flat halves show every
trip in the "opposite" order; the sloped halves show the same 100%: no trip runs a sloped half against its lanes.
Boulevards on slopes carry the same one-way lanes (27100..27107 = 21718..21725's specs); no shipped city has a sloped
boulevard, so they were not driven by traffic here. Probe output kept with the instance (`inst_avslope\frankfurt_trips.json`).
Frames of two sloped Frankfurt avenues with the fix: `owner_shots\frames\after_frankfurt_*.png` (last rows of the z4 sheet).

## 5. Not done / limits

- Halves at different heights: not buildable in stock (section 1), nothing to do.
- A boulevard cap, taper, junction or nose on a sloped cell gets the stock slope piece (the nose: the sloped middle);
  no shipped city has a three-wide row on a slope.
- Diagonal avenues / boulevards (DAV / DBV) on slopes not looked at.
- Zooms 0 to 2 only seen in the zoom-3 overview scale.
