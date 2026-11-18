# STATUS bldrender (round 2026-11-18b, child of "SC3 Simtropolis feedback triage")

## goal
A 3D model (OBJ) becomes a zoned building that grows next to the stock ones: stock art layout measured, OBJ rendered
at every zoom x rotation, packaged as a growable (ids 38000+) from a models.json entry, shown growing in Sacramento.

## verdict + deciding RVA
**DONE, works in game.** Three test models (38000 / 38001 1x1 class 3300, 38002 2x2 class 3900) grew in Sacramento by
the first autosave: 548 / 512 / 99 lots, all zooms and view rotations draw (verify/bldrender/RESULTS.md).
Deciding facts: frame = zoom*4 + ((state + viewRot) & 3) [SIMSPR 0x1005aeab, vtable 0x10068ca8 slot 0x68];
registration point = left vertex of the whole lot for any size [0x1000c678, 0x10007b4d, 0x1000be25]; stock frames
L = 0, width n*W, B = n*W/4 + 1, zoom 4 = zoom 3 at scale 2 (census of 221 RCI buildings, BUILDING_ART.md 2).
Grown buildings are saved with rotation 0 (16,322 of 16,450): they never turn to their road.

## built
- `re/tools/bldimport/bldrender.py`: numpy rasteriser on the engine's projection (no Blender: not installed on
  LIVING-PC). Lot diamond = stock on 160 of 160 frames (1x1..4x4, zooms 0-3, every slot) + tile 39 zoom 4.
  Supersampled, alpha cut, RGB565, shadow map, MTL colours + map_Kd textures, procedural lawn (no game pixels).
- `re/tools/bldimport/bldimport.py`: build / render / pack / restore / list / check / calibrate / preview. Reads the
  classifier page's models.json (checked on its own samples folder). Ids in `<folder>\sc3build\ids.json`. Installs
  into `mods\netmod\overlay` with state + backups like bat_growables; restore is byte-exact, re-runs idempotent.
- `re/tools/bldimport/make_testmodels.py` (the three test models), `bld_lab.py` (the in-game run).
- Docs: `re/analysis/BUILDING_ART.md`, `verify/bldrender/RESULTS.md`, pictures `verify/bldrender/owner_shots/01..06`.

## proven game-side vs static only
- Game-side: growth (counts from the autosave), drawing at zoom 3 / 4 and in view rotations 0-3, size against stock.
- Static: BUILDING_ART.md 2-3 (census + decomp); the +0x11 anchor offsets apply only to second-layer sprites.
- Not run: reload with / without the package (same containers as batconvert, proven there), query dialog.

## blocked on
Nothing. Note: Blender 4.5 is not installed on LIVING-PC; the built-in renderer replaces it (no player needs Blender).

## files owned (all under the deny-by-default .gitignore: `git add -f`)
In `dev\bldrender\wt` (branch child/bldrender):
- `re/tools/bldimport/bldrender.py`
- `re/tools/bldimport/bldimport.py`
- `re/tools/bldimport/make_testmodels.py`
- `re/tools/bldimport/bld_lab.py`
In MAIN (written there as the brief asked):
- `re/analysis/BUILDING_ART.md`
- `verify/bldrender/RESULTS.md`
- `verify/bldrender/owner_shots/01_sacramento_zoom4.jpg` .. `06_models_next_to_stock_zoom4.jpg`
- `re/sessions/STATUS_bldrender.md`
Not to commit: `verify/bldrender/runs/run1/` (game frame dumps + a save copy), `dev\bldrender\work\testmodels`.
Untouched: classifier.html and the bldclass samples.

## game-harness need
None left. dev\bldrender\tree still has the three test buildings installed (`bldimport.py restore --game
dev\bldrender\tree` takes them out). No game running.

## asks of other sessions
- Orchestrator / bldclass: the page's assumptions hold: metres, Y up, lot [n, n] (only square lots grow), commercial
  has no mid-wealth class (stock classes are 5100 / 5500 / 5700 / 6100 / 6300 / 6700). 16 m per cell matches stock
  by eye; the engine has no metre unit, so it is a visual value. One thing the page could show: the model's front is
  +Z (lower-right face in game slot 0); rotate_deg is counter-clockwise seen from above.
- Optional new models.json key for review: `x_bldrender` {shadow, ground: "grass"|"none", cell_m} is read; nothing
  else was added.
