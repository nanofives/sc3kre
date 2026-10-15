# roundabout2: results (2026-10-13)

PRE: `verify/roundabout2/PRE.md` (commit df1e0b6, before the first launch). Trees: `Simcity_stock_roundabout2` (hard
links of Simcity_stock, new package, overlay) and `Simcity_stock_roundabout2_old` (round/1012's package = round 1,
control). mods_launch, sc3resize, sc3netmod built from child/roundabout2 (no C change vs round/1012). Every PID mine,
stopped with taskkill /PID. Instance data (logs, saves, probes, dumps): `inst_rb2`, `inst_rb2_nomod`, `inst_rb2old`.
Owner pictures: `MAIN\verify\roundabout2\owner_shots\` (7 PNG + captions.md, not in git).

## Changes made after PRE (each reported, none silent)

1. **Island fill.** In game the island first drew BLACK with leftovers of earlier frames: the engine draws no terrain
   under a 20400 cell, so transparent pixels show the back buffer (`shots/d5_crop.png`, PID 29436). Stock curve 11203
   leaves its outer corner transparent and grass shows there; why terrain is drawn under 11203 and not under 20400 (base
   39) was not traced `[UNCERTAIN]`. No stock network piece carries plain grass (scan of 395 exemplars' zoom-4 frames:
   none with > 800 green px), so the island is painted as a concrete island: apron + curb ring + centre, all from
   road 29's sidewalk profile. Package reinstalled, game relaunched (PID 34496), template placed again.
2. **Pedestrians.** Traffic frames showed pedestrians standing on the island: the T's walks (15,240)->(15,15) and
   (240,240)->(15,240) run along the two internal sides of the quarter, across the ring and the island. New graph:
   crosswalk (15,15)->(240,15) over the arm, sidewalk (240,15)->(240,240) along the closed side, exits (15,15) codes 8
   and 0, (240,15) 8, (240,240) 24 (subset of the T's walks and curves 256 / 257). Verified after TR/TI (below).
3. `nramp_cam.py`: `SC3_CAM_GRAB=1` takes a window grab instead of sc3resize's dump; `np_drive.py shot`:
   `SC3_SHOT_TIMEOUT`. The dump trigger stopped answering after camera calls on the paused game (round 1 saw the same).

## Static

| arm | outcome | verdict |
|---|---|---|
| A0 | `netpaint.py seams`: 1320 / 1320 pixels within one pixel row of the arm edge equal stock 29's frame across that edge, all 20 frames (first run 889 / 1320 with a fixed 12-unit arm strip; strip set to one pixel row per zoom and the rim clamp to one pixel) | met |
| A1 | mean abs RGB step across z = 12 (end of the strip) 20.2-27.3 vs inside the arm at z = 40: 28.4-39.7, zooms 3-4, 4 slots | met |
| validate / lanekit | `netpack.py validate`: OK, 1 WARNING (symmetric template). Turn matrix low 0x008a, high 0x3010 | as PRE |

## In game, Berlin site (25,181)..(26,182), stock DLLs

| arm | outcome | verdict |
|---|---|---|
| P | `rot 0 PLACED at (25,181) 2x2, 4 cell(s), cost 400, funds 117006 -> 116606`; cells `20400.3 20400.0 / 20400.2 20400.1`; exits (24,181) 29.0, (26,180) 11203.0, (27,182) 39.3, (25,183) 29.1 unchanged; (25,180) 39.2 -> 11203.2 (as round 1) | met |
| V | 20 views (zoom 0..4 x rotation 0..3): 12 by in-process dump, 8 by window grab (dump trigger stopped). `netart.match`, piece cells only, HUD excluded: arm z2 0.671-0.821, z3 0.753-0.890, z4 0.768-0.901; control (round-1 art, same calls) z3 r0 0.709, z4 r0 0.725, z3 r1 0.771. Arm vs control at the same view: +4.4, +4.3, +7.5 points | met |
| V seams | match diff z4 r2: occluders (lot fence, building) plus a 1 px line along the block's outer edges, including the E arm, whose neighbour is stock T 39.3. On screen the arm reads continuous. The prediction "no row of mismatched pixels along the arm edges" is **not met as worded**; cause not proven (the neighbour drawing its own rim over mine is the reading I have, not checked pixel by pixel) | not met as worded |
| TR | 480 s each, `rb_island.py` (moves + positions). Arm (PID 34496): ring moves in the new order **78, against 0**; ring -> exit 37, road -> ring 30 (all four arms: 4 / 4 / 16 / 6). Control (PID 34764): new order 0, **against 80** (= round 1's order 80 / 0), out 28, in 33 | met |
| TI | vehicle positions (+0x0c / +0x14, 40 ms poll) inside the 4 cells: arm 8,297 samples, **0** closer than 129.5 to the block centre (0 closer than 170), min 173.2; control 7,066 samples, **5,159** closer than 129.5, min 78.6 | met |
| S | `save: 4 variant tile(s) written as base, section 0x4E56 written`; `netvariant.py scan`: 0 raw variant tiles, 4 cells 39 -> 20400 | met |
| S0 | `inst_rb2_nomod` (no sc3netmod), PID 26628: cells `39.3 39.0 / 39.2 39.1`, the other 32 cells of x 23..28 / z 179..184 equal to the arm grid | met |
| S1 | PID 29028: `load: variant section 4 entries, 4 to restore, 0 not installed`, `all 4 variant tiles restored`; grid equal | met |
| B | Demolish (26,182): all 4 cells empty; exits re-tiled to road ends (24,181) 11225.1, (26,180) 11225.1, (25,183) 11225.0, (27,182) 11203.3 | met |
| ped fix | after change 2, PID 22928, 150 s: 11 ring moves with, 0 against, 0 of 1,298 samples inside 129.5; 40 window grabs at zoom 4: no pedestrian on the island | observation (not pre-registered) |

Deviations: the control game exited on its own after nramp_cam's zoom call failed with "system error" (its traffic
data was already collected; same failure as round 1's deviation 1). Window grabs were blocked once by a shell window
on top (`XamlExplorerHostIslandWindow`); in-process dumps used instead.

## Answers to the brief

- **Blender.** Not used for the art. The ground is flat and textured. The calibrated Blender camera is pixel-exact at
  zooms 3-4 only (NET_ART.md 9.2, up to 8 mismatched px per frame at zooms 0-2), and a texture rendered through it is
  resampled; `netpaint.py` uses the engine's own draw-point formula at every zoom and samples stock 29 pixels, which is
  what makes the arm seam exact (A0). No 3D prop was added: the island is flat concrete, like the stock sidewalks.
- **4 arms.** The block already has 4 arms (validate: exits (0,0)W, (0,1)S, (1,0)N, (1,1)E). Each block side is two
  cells; a single-cell road meets one of them, the other is closed. Kept.
- **Key R.** Still no visible effect: the pinwheel is the same block turned 90 degrees (validate WARNING). A mirrored
  pinwheel (arms on the other cell of each side) would need a second piece id with mirrored art and lanes; not built.
- **English-UK.** Not run. lanekit's mirror_uk reverses each lane, and the UK VPathAtt stores 1024 / 769 / 259
  reversed under the same keys (measured), so UK cars would circulate clockwise. The art has no per-language copy
  (`Res\Sprites` has no language folders): UK players would see counter-clockwise arrows.

Functions read for this task: STRTSIM `FUN_1001c750` (decomp, to confirm `this` is the vehicle) and `FUN_10020108`
(arrival-node lookup). Vehicle fields +0x0c / +0x14 measured live (30 / 30 hook calls), not from the decomp.
