# Round 2026-11-18c: stock look for rendered buildings + downloaded .bld buildings

Orchestrator: "SC3 Simtropolis feedback triage". Rules: `re/sessions/CHILD_PROTOCOL.md`. Workspaces from main 249f2dc.
Previous round: `ROUND_2026-11-18b_buildings_import.md` (bldrender + bldclass merged: `re/tools/bldimport/`,
`re/analysis/BUILDING_ART.md`, `verify/bldrender/RESULTS.md`, `verify/bldclass/RESULTS.md`).

## Owner (2026-11-18)

On the bldrender pictures: "i would like for these buildings to look more like the originals by default, do we need
to lower the resolution? or change the palette? i don't know, continue to what's next". Next in his order:
downloaded SC3 buildings, then airports and seaports, then ploppables.

## Stream bldlook (opus / medium): rendered buildings look like stock art by default

Today `bldrender.py` renders zoom 4 at full size (stock zoom 4 is zoom 3 doubled on 1,908 of 1,936 frames) with smooth
shading. Find what makes stock building art look the way it does and match it, measured, not by eye alone:
- Resolution: render zoom 3 and pixel-double it for zoom 4 as stock does, and check zoom 0-2 the same way.
- Colour: stock palette statistics (saturation, brightness, hue spread, number of distinct colours per frame, RGB565
  steps) against ours. Quantize / map toward them.
- Light and shade: sun direction and the light / shadow ratio of stock walls and roofs per view, the soft shadow.
- Edges and texture: anti-aliasing at the outline, outline darkening, surface noise / dithering of stock walls.
Deliver: 2-3 named styles in `bldrender.py` (e.g. `stock` default, `clean` = today's), the metrics table per style
against 20+ stock buildings, side-by-side sheets at zoom 3 and 4 (phone-sized) in `verify/bldlook/owner_shots/`, and
the test models growing in Sacramento with the default style. Touch only `bldrender.py` (+ its notes in
`BUILDING_ART.md`), not `bldimport.py` or `classifier.html` (bldfile owns those this round).

## Stream bldfile (opus / medium): downloaded .bld buildings grow as zoned buildings

Simtropolis buildings are Building Architect `.bld` files. Samples: the 17 in the game's `Buildings\` folder (game
content: copy them into your workspace, never modify the install). Known: a `.bld` is a skin on an existing occupant
id (`BUILDING_PICK.md`), `tools\bat_growables.ps1` already turns entries of `Apps\BARender\BAT.DAT` into growables
(ids 37000+), memory note on BAT growables (20-frame tables, PS 5.1 traps).
Do:
1. The `.bld` file format (header, the base building it skins, lot size, art frames, name), with offsets.
2. `bldimport.py` accepts `.bld` files in a folder next to 3D models: each becomes a `models.json` entry (kind
   growable, class from its base building, lot from the file) and installs as a new growable (ids 38000+ space shared
   with 3D models, kept in `sc3build\ids.json`), without the player importing it into the Building Architect first.
3. `classifier.html` opens `.bld` files too: thumbnail from the file's own art, suggested class from its base building.
4. Show 3-4 of the shipped `.bld` buildings growing in Sacramento, pictures in `verify/bldfile/owner_shots/`.
Notes in `re/analysis/BLD_FORMAT.md`, results in `verify/bldfile/RESULTS.md`.

## Rules

Windowed game, posted input only, test slot for long runs, kill only PIDs you started, delete BMP dumps, STATUS file at
every milestone, no git add / commit. Run a real check before reporting done, and keep working until finished.
