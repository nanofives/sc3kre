# artkit: PRE-REGISTRATION (2026-10-13)

Written and committed before the first game run of task artkit.

## Question
Does art authored with the artkit routes (compositor from stock parts, Blender render with the calibrated camera)
and packaged by netpack draw in game as NEW geometry, at every zoom and rotation, aligned with stock neighbours?
Does a frame of a different size than its base frame (anchors.json) draw at the right place?

## Setup
- Tree `C:\Users\maria\Desktop\Proyectos\Simcity_stock_artkit` (hard links of `Simcity_stock`, `link_tree.py`), stock
  DLLs, Spanish GOG. Instance `re\harness\inst_artkit` (mods_launch.exe, sc3resize.dll, sc3netmod.dll built from
  child/artkit). `mods_launch -multi`, my PID only, windowed.
- Packages (overlay mode, `netpack.py install`):
  - `example_roundabout_art`: id 20400, base T 39, art = `recipe.json` (stock curve 11203 ring + stock straight 29
    exit), same frame sizes as 39.
  - `example_roundabout_lamps` (arm D): id 20401, base 39, art = the same recipe plus a street lamp rendered in
    Blender (`netart.py render`, netart_calib.json), frames TALLER than 39's, registration points in anchors.json.
- Cities: copies of `Cities\Berlin, Germany.sc3` edited offline with `plant.py` (flat empty 8x8 box at (30,210),
  z 32): 2x2 pinwheel at (33..34, 213..214), states 3,0 / 2,1, two stock road 29 cells on each of the 4 exits.
  `berlin_ctl.sc3`: the 4 cells are stock T 39 (control). `berlin_rb.sc3`: the 4 cells are 20400.
  Arm D: `berlin_lamps.sc3`, the same pinwheel of 20401 at another flat box.
- Camera: `nramp_cam.py` (SIMSPR zoom/rotate calls centred on (34,214)), frames by sc3resize's in-process DUMP.
- Offline reference: `netart.py preview` of the same layout (game frames composited at the engine's draw points).

## Arms and predictions
| arm | run | prediction |
|---|---|---|
| A | `berlin_ctl.sc3`, package installed | A1 cells (33..34,213..214) read 39 with states 3,0,2,1 (`np_drive cells`); A2 the dump shows four stock T junctions there |
| B | `berlin_rb.sc3`, package installed | B1 the 4 cells read 20400, states 3,0,2,1; B2 at every zoom 0..4 x rotation 0..3 (20 dumps) the roundabout draws (ring, island, 4 exits); B3 compared in 5/6/5 with the offline preview, at zooms 2..4 at least 98% of the piece pixels (opaque in the preview, inside the 4 cells + 8 road cells) are equal, after the best integer offset; B4 no terrain pixel visible inside the union of the 12 cell diamonds (no seam) at zooms 2..4 |
| D | `berlin_lamps.sc3`, both packages | D1 the 4 cells read 20401; D2 lamps visible above each quarter at every zoom x rotation, not clipped at the top; D3 same 98% match with the offline preview at zooms 2..4, lamp pixels included |

Exploratory, no prediction: save + reload of B with the package (cells kept), and of B without sc3netmod.dll.

## Out of scope
Traffic over the piece (task lanekit), placement by tool (task multitile), owner's dev install, 1024 maps.
