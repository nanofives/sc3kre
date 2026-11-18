# Round 2026-11-18d: a sample building pack + an in-browser importer + a guide (for Simtropolis)

Orchestrator: "SC3 Simtropolis feedback triage". Rules: `re/sessions/CHILD_PROTOCOL.md`. Workspaces from main (after
2ecf05d). Previous rounds: `ROUND_2026-11-18b_buildings_import.md`, `ROUND_2026-11-18c_buildings_look_bld.md`.

## Owner (2026-11-18)

"can we create a pack of buildings as sample for everyone at simtropolis to go ahead and make their own, alongside a
guide on how to upload buildings into the game?" Calls: the importer runs inside the classifier page (players have no
Python), samples from free CC0 kits plus a few of ours, the default `stock` style keeps its grain.

## Inputs

- CC0 kits downloaded by the orchestrator to `MAIN\stage\kits\` (zips + unpacked): Kenney City Kit Suburban (40
  models), Commercial (41), Industrial (37): OBJ + MTL + PNG textures (also GLB / FBX), `License.txt` = CC0 1.0, credit
  "Kenney (www.kenney.nl)" welcome, not required. They include props (roads, trees, fences): only buildings go in.
- Tools: `re/tools/bldimport/` (bldrender.py styles stock / stock_sharp / clean, bldimport.py build / restore / check,
  bldfile.py for .bld, classifier.html with .bld support), notes `BUILDING_ART.md`, `BLD_FORMAT.md`.

## Stream bldweb (opus / high): the importer inside the page

Port the render + pack + install + restore of `bldrender.py` / `bldimport.py` (OBJ / MTL / PNG and `.bld`) into the
browser so `classifier.html` gets: pick the models folder, classify, pick the game folder, "Install into the game",
"Remove from the game", with the same files, ids (`sc3build\ids.json`) and backups as the Python tool. Proof: for the
three test models, the bldfile samples and 3 Kenney buildings, the page writes byte-identical files to the Python
tool (golden test run headless, File System Access API stubbed or a test hook), and one install made by the page grows
in Sacramento. Big files: keep the page usable (a Web Worker for rendering, progress per model). The page must keep
working opened from disk with no server. Results `verify/bldweb/RESULTS.md`.
You own classifier.html and new JS files this round. Do not change the Python tools' output format.

## Stream bldpack (opus / medium): the sample pack + the guide

1. Pick 12-15 Kenney buildings that read well at zoom 3 and 4: residential, commercial and industrial, low to high
   wealth, lot sizes 1x1 to 3x3, plus 2-3 of our own test models. Scale / orient each to its lot (front +Z, 16 m cell,
   check against stock neighbours), write `models.json` (names, classes, weights near stock, 1-10).
2. Render with the Python tool (default style), install in a dev tree, grow them in Sacramento, pictures at zoom 3 and
   4 next to stock, one sheet of the whole pack. Drop any that look wrong.
3. The pack folder `stage/sample_pack/` (models + textures + `models.json` + `CREDITS.txt` naming Kenney and CC0 +
   a short `README.txt`), zipped for a release asset. Not into git (keep the repo light).
4. The guide, English, for players, under Mariano's name (facts and steps, no em-dashes, semicolons, emoji, ellipsis or
   intensifiers, never an invented number): `docs/buildings/index.html` in the gallery's style (GitHub Pages), covering
   what the tool does, the sample pack, making or finding a model (units, Y up, front +Z, 16 m cell, lot sizes,
   textures, polygon budget), classifying, installing and removing with the page (write the steps from bldweb's design
   in this brief, the orchestrator reconciles them with the final page), .bld files and their one-view limit, tips for
   a stock look, troubleshooting. Pictures from step 2. Results `verify/bldpack/RESULTS.md`.
You own stage/sample_pack and docs/buildings. Do not edit classifier.html or the Python tools (report needed changes).

## Rules

Windowed game, posted input only, test slot for long runs, kill only PIDs you started, delete BMP dumps, STATUS file at
every milestone, no git add / commit. Run a real check before reporting done, and keep working until finished.
