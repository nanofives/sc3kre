# roundabout2: pre-registration (2026-10-13, written before the first game launch)

Task: make piece 20400 (package `re/tools/netmod/examples/roundabout`) look and drive like a one-way mini roundabout.
Owner feedback on round 1: entries not seamless, road lines must converge, roundabouts go one way. Also known: cars
drawn across the island, key R changes nothing.

## What changed (static, measured in the worktree before launch)

- **Direction.** The round-1 ring used the curve's inner lane (radius 80 about the block centre, z+ -> x- in the
  state-0 frame). In the ENGLISH lane files a straight road's lane at z 80 runs +x, which makes the frame right-handed
  seen from above and the ENGLISH half right-hand traffic (NET_LANES.md 2.4). So round 1 circulated CLOCKWISE in
  right-hand traffic. New lanes (quarter.lanes.json): ring x- (0,80) -> z+ (175,255) = stock curve 1024 (9 points,
  radius 175-176 about the corner (0,255), measured), counter-clockwise; exit x- (0,80) -> z- (80,0) = curve 769
  (radius 80 about (0,0)); entry z- (175,0) -> z+ (175,255) = curve 259 (straight, tangent to the ring). English-UK:
  lanekit mirror_uk reverses each lane; the UK VPathAtt stores 1024 / 769 / 259 reversed (measured), so UK runs
  clockwise. Turn matrix (props 310, connects auto): low 0x008a, high 0x3010, which is round 1's halves swapped.
  Arms per side unchanged (x-, z-, z+), so the tiler sees the same arms.
- **Geometry.** Every lane point in a 20400 cell is at least 175 units from the block centre (curve 1024 min 175,
  curve 769 min 255 - 80 = 175, curve 259 min 175). The art's island including its edge line has radius 129.5.
- **Art.** New: `netpaint.py` paints each pixel from the plan `paint.json` with the engine's own projection,
  colouring by sampling stock road 29's frame of the same zoom at a mapped cross-profile position (ring, entry band,
  exit band bent from 29's profile). The arm edge strip (12 units deep) is 29's own profile. No stock frame is stitched
  in. `netpack.py validate`: OK, 1 WARNING (symmetric template, known).
- **Not done with Blender** (deviation from the brief, reason in RESULTS): the ground is flat and textured; the
  calibrated Blender camera is pixel-exact only at zooms 3-4 (NET_ART.md 9.2), the painter is exact at every zoom.

## Arms

Trees: `C:\Users\maria\Desktop\Proyectos\Simcity_stock_roundabout2` (hard links of Simcity_stock, NEW package in
overlay mode) and `Simcity_stock_roundabout2_old` (hard links, round/1012's package = round 1, control). DLLs
(mods_launch, sc3resize, sc3netmod) built from child/roundabout2 (no C change vs round/1012). Every PID mine.

| arm | setup | prediction (met if all hold) |
|---|---|---|
| A0 static | `netpaint.py seams`: painted pixels within ~1 px of the arm edge vs the stock 29 frame across that edge, 20 frames | equal on all of them |
| A1 static | the internal step at the end of the arm strip: mean abs RGB difference between pixel pairs straddling z = 12 vs pairs straddling z = 40 (both inside the arm), zoom 3-4 | within 2x of each other (no visible line where the strip ends) |
| P | Berlin copy, key T, click with the anchor on (25,181) over the stock junction | PLACED, cells 20400.3 20400.0 / 20400.2 20400.1; exit roads (24,181) (26,180) (27,182) (25,183) unchanged (same as round 1 TP) |
| V | 20 in-process dumps (zoom 0..4 x rotation 0..3) of the site, camera set BEFORE the sim runs | the block draws as the offline preview; `netart.py match` of the arm vs its control (round-1 package, same camera) not lower by more than 2 points. Seams: no row of mismatched pixels along the 4 arm edges in the match diff at zoom 3 and 4 |
| TR | arm and control, same Berlin save and site, camera by minimap click + 2 zoom-in clicks, speed 4, lk_probe --watch ring + neighbours, ~480 s each | arm: ring moves in the NEW order (X+1,Z) -> (X+1,Z+1) -> (X,Z+1) -> (X,Z) >= 30 and against it = 0; exits and entries > 0. Control (round 1): its moves run the other way (the round-1 order), i.e. against the new order > 0 |
| TI | same runs: vehicle positions sampled in the 4 ring cells (Frida, fields located first on the move hook; exploratory step, the offsets get reported) | arm: 0 samples closer than 129.5 to the block centre; control: > 0 (its ring lane is at radius 80) |
| S | arm: save | log `4 variant tile(s) written as base`; 0x4E56 lists the 4 cells |
| S0 | open the save without sc3netmod | 4 cells read 39.x, rest equal |
| S1 | reopen with the mod | `all 4 variant tiles restored`, new art |
| B | Demolish one cell | whole block goes |

Not run: English-UK (shared registry language setting), 1024 maps, the release layout.
