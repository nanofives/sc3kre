# plop2 results (round 2026-11-19i): landmark follow-ups

**Verdict.** (1) Landmarks have a Description box in the importer page; what the player types reaches the game byte for
byte as bldimport.py writes it. (2) The SC4 download's landmark lot now converts to a kind landmark entry (its
ploppable "Jobs" lot to a second one, off), the same in sc4conv.py and sc4web.js; the Global Office Center tower went
into the stock landmark dialog with its own picture and "From SimCity 4", and was placed in Madison. (3) The orange
lot a removed landmark leaves is **buildable**: it is zone byte 22 (kPloppedBuilding) with no occupant; a stock
landmark was placed on it and zoning turned its cells into residential zone. The bulldozer does nothing on an empty
orange cell, and bulldozing a building placed there clears only that building's footprint. (4) The guide has
"Landmarks" and "Maxis landmark packs" sections. (5) run_all.sh with all six arguments + SC3PACK_PACKS: **30 of 30 steps passed**.

## 1. Description field (classifier.html)

| what | how |
|---|---|
| panel | a "Description" text box, shown only when every selected card is kind landmark; empty = the game shows the name again (bldimport.py / bldweb.js: prop 0x7C, else the name) |
| models.json | `description` written only when set (entryOf deletes an empty one, so other entries keep their shape); a cp1252 warning on the card as for the name |
| test | `pagetest.mjs --case landmarkdesc --edit-desc "obelisk_2x2.obj=Typed in the page, Córdoba"`: the page opens the folder, the obelisk's description is blanked, the Description box is hidden for the kind civic card and shown (empty) for the obelisk, the text is typed with a change event, and the page installs from its own models.json (`modelsFolder()`). **9 of 9**: `bldimport.dat` 472,708 bytes and `bldimport.pin` 333 bytes = bldimport.py on golden case `landmarkdesc` (the same models, entries in the page's order, that description), ids.json equal |

First try compared against case `landmarks` and failed only on the .dat / .pin: the page saves entries in its grid
order (by file name), which changes the order of ids and records. Case `landmarkdesc` holds the entries in that order.

## 2. SC4 landmark and ploppable lots as landmarks (sc4conv.py, sc4web.js)

| what | how |
|---|---|
| which lots | the ones sc4pass2 named (`x_sc4.versions`): a lot whose building has no model and shows a converted building as a lot prop. Kind landmark = the building has prop 0x2781284F |
| entry | kind `landmark`, class null, lot = the building's SC3 lot, name = the SC4 lot building's name, `description` "From SimCity 4", `x_sc4` {exemplar, design, version, sc4_lot, model_of, building_tgi, model_key, size_m, diagonal, foundation, views, auto} |
| file | `<building stem>_landmark.obj` / `_ploppable.obj` (a number from the second of a kind): a byte copy of `<stem>.obj`, same MTL and textures. bldimport keys ids by file, so each entry needs its own file. The building alone, without the SC4 lot's props |
| on / off | the landmark lot on; a ploppable lot off (the same building again, SC3 landmarks have no jobs); a building with no landmark lot: its first ploppable lot on; lot above 4x4: off |
| rerun | keeps the player's edits on name, class, lot, weight, enabled, scale, rotate, notes, x_bldrender, kind and description (keyed by the SC4 exemplar) |
| report | "Global Office Center also comes as ...: converted as SC3 landmarks for the landmark menu (kind landmark), Global Office Center Landmark on, Global Office Center Jobs off (the same building again, and SC3 landmarks have no jobs)" |

Global Office Center: 3 models, 2 enabled (growable 38000, ploppable 38001 off, landmark 38002). bldimport pack:
`plop [38002] Global_Office_Center_landmark.obj: "Global Office Center - Landmark", Landmark, 4x4, stats of stock 9510`,
plugin `.dat` 1,566,732 bytes, `.pin` 236 bytes.

`sc4_packs.mjs` (after `sc4_packs_setup.py`): **37 of 37** (`dev\plop2\work\packs1.log`), 2 new lines: the two landmark
entries (lot, description, OBJ = the building's bytes, only the landmark lot on) and a rerun over a models.json edited as
the page saves it (ploppable landmark switched on, description "Edited in the page") = sc4conv.py's rerun byte for byte.
models.json byte for byte, file list (9 files), pack (every game file incl. the plugin), 40 frames of 40.

### In game (PID 9532, `dev\plop2\tree`, Madison, windowed 1280x860, posted input only)

| step | result |
|---|---|
| landmark dialog (Civic, Landmarks), scrolled to the end | last row "Global Office Center - La...", its own preview (the tower), line 2 "From SimCity 4" (`owner_shots/01`) |
| place | a refused spot (red footprint) first, then at cell (176, 213): resize.log `building placement (kind 0) at (176, 213): placed, price 120`, funds 102,174 -> 102,024 |
| draw | zoom 2, 3 and 4 (`owner_shots/02`, `03`) |
| save | autosave holds `{0x207EDC0E, 0xB1D10002, 38002}` type 18000 at (176, 213) |

## 3. The lot a removed landmark leaves

`bldimport.py restore --game dev\plop2\tree` (13 files restored, plugin gone), the autosave above loaded (PID 19480):

| check | result |
|---|---|
| the lot | orange 4x4 at (176..179, 213..216), no occupant (`owner_shots/04`). Zone raster (city_write.zone_get) of the save: byte **22** on those 16 cells, 0 around (RELOCATE.md: the placement commit writes zone 22 over the footprint; QUERY_ID.md: 22 = plopped building) |
| place a stock landmark (Coit Tower, 2x2) on it | blue footprint, `placed, price 0` at (177, 214); the other orange cells stay (`owner_shots/05`) |
| zone residential over 3 orange cells | zoned (green), funds 102,024 -> 101,994 = $30 (`owner_shots/06`) |
| bulldozer on an empty orange cell | cursor $0, no change |
| bulldoze Coit Tower | $20, funds 101,994 -> 101,974; its 2x2 footprint turns plain, the orange ring stays (`owner_shots/07`) |
| next autosave (zone raster) | x 177..178, z 214..215 = 0 (Coit's footprint), x 179, z 213..215 = 1 (the zoned cells), the other 9 cells = 22, no occupant on the 16 cells |

So zone 22 is cleared by zoning over it, or under a building placed there and later bulldozed. Not tested: the de-zone
tool (the menu slot clicked was another tool: the view scrolled, nothing changed), and whether the sim ever clears
zone 22 cells without a building on its own over a longer run (they were still 22 in the next autosave).

Both games: started by `sc3dev.ps1 run plop2`, stopped by PID. resize.log: one `0xC0000096 at SC3U.exe+0x84122` line at
start in each, the same line every lab run logs. BMP dumps deleted.

## 4. Guide (`verify/bldpack/work/guide_template.html` -> `docs/buildings/index.html`)

- New section "Landmarks": kind landmark, lots 1x1 to 4x4, stats from the first stock landmark of the lot (Coit Tower
  2x2, Arc de Triomphe 3x3, Palace of Fine Arts 4x4), the Description box, ids, the files in `Apps\PlugIn\bldimport`,
  our test, removing them and the orange lot (section 3), getting them back.
- New section "Maxis landmark packs": the 2000 packs as plugins, the blank lot as shipped, Open SC3 pack -> Install N
  plugins into Apps\PlugIn, conflicts left alone and logged, Remove, our test (Landmark Pack 1 and 2, 80 pictures
  48 + 32, the five names, MOMA in four rotations), no pack shipped.
- Fixed: "What it does not do" (landmarks now work), the Kind / Class / Description fields in Classifying, the pack
  plugins line, the SC4 versions line, the pack Remove button name ("Remove what this page installed", as sc3pack.js).
- Every number from verify/plop/RESULTS.md, verify/sc4pass2/RESULTS.md or this file. Voice check over the added text:
  0 em-dashes, en-dashes, semicolons, ellipses, emoji or intensifiers. No picture added (the test shots hold SC4 / EA art).
- `make_docs.py --wt dev\plop2\wt --tree dev\plop2\tree --zip <the 2026-11-18 sample pack URL>` (the default `--zip`
  would have replaced the published link). `stage\sample_pack\README.txt` rewritten byte-identical.

## 5. run_all.sh

`SC3PACK_PACKS=stage\st_packs test-slot bash re/tools/bldimport/webtest/run_all.sh dev\plop2\work\runall stage\release
stage\kits "<.happy-uploads>\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes
stage\st_packs\sc4`: **30 of 30 steps passed** (log `dev\plop2\work\runall.log`). 29 -> 30: the new step 10, `pagetest.mjs
landmarkdesc` (9 of 9, section 1). golden_setup now builds 7 cases (`landmarkdesc` in its default list). Among the rest:
golden.mjs 71 of 71, pagetest landmarks 6 of 6, sc4_packs.mjs 37 of 37 (2 new lines, section 2), every older step
unchanged. Before the run: `sync_css.py --publish` (classifier.html already in sync with docs/assets/sc3ui.css; copied
to `docs/buildings/importer/`), and the suite's own `sync_css.py --check` passed (step 14).

## Pictures (`owner_shots/`, local only: SC4 art)

| file | what |
|---|---|
| `01_landmark_dialog_sc4_tower.jpg` | the stock landmark dialog: "Global Office Center - Landmark", its preview, "From SimCity 4" |
| `02_sc4_tower_landmark_placed_zoom2.jpg` | the tower placed at (176, 213), zoom 2 |
| `03_sc4_tower_landmark_zoom3.jpg` | zoom 3 |
| `04_plugin_removed_orange_lot.jpg` | the same save without the plugin: the empty orange 4x4 lot |
| `05_coit_tower_placed_on_orange_lot.jpg` | Coit Tower placed on that lot |
| `06_orange_cells_zoned_residential.jpg` | 3 orange cells zoned residential |
| `07_coit_bulldozed_footprint_cleared_ring_stays.jpg` | Coit bulldozed: its footprint plain, the orange ring left |

## Files

Worktree `dev\plop2\wt` (uncommitted): `re/tools/bldimport/classifier.html`, `re/tools/sc4conv/sc4conv.py`,
`re/tools/bldimport/sc4web.js`, `re/tools/bldimport/webtest/{golden_setup.py, pagetest.js, pagetest.mjs, sc4_packs.mjs,
sc4_packs_setup.py, run_all.sh}`, `docs/buildings/index.html`, `docs/buildings/importer/{index.html, sc4web.js}`.
MAIN (local): `verify/bldpack/work/guide_template.html`, this file, `owner_shots/`, `work/lab.py` (launch, dumps,
posted clicks, camera, occupant list), `work/saves/`, `re/sessions/STATUS_plop2.md`.
