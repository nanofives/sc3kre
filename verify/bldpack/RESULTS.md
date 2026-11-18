# bldpack results (round 2026-11-18d): a sample building pack and a player guide

**Verdict: done.** An 18-building sample pack (16 Kenney CC0 buildings and 2 of our test models), installed with
`bldimport.py build`, read back 18 of 18 with 20/20 frames equal, and **all 18 grew in game**: 17 with the lab's
usual settings in Sacramento or Berlin, the Skyscraper (class 6700) in Berlin once commercial churn was raised
(step 2b). The pack is zipped for a release asset with the importer inside, the importer is also hosted under
`docs/buildings/importer/`, and the guide `docs/buildings/index.html` is written in English for players, with the
install / remove steps from `verify/bldweb/RESULTS.md` "What a player does". Byline "nanofives".

## Deliverables

| what | where |
|---|---|
| pack folder (not in git) | `MAIN\stage\sample_pack\`: 18 OBJ + MTL, `Textures\` (6 PNG), `models.json`, `sc3build\ids.json` (38000-38017), `CREDITS.txt`, `Kenney_License.txt`, `README.txt`. `sc3build\<model>\` is the Python render cache, left out of the zip |
| release asset | `MAIN\stage\sample_pack\dist\sc3-sample-buildings-2026-11-18.zip` (52 files, 665,296 bytes, one top folder, `importer\index.html` + `bldweb.js` inside) |
| guide | `dev\bldpack\wt\docs\buildings\index.html` + `docs\buildings\img\` (9 JPEG) |
| hosted importer | `dev\bldpack\wt\docs\buildings\importer\index.html` + `bldweb.js` = main 8a206e5's `re/tools/bldimport/classifier.html` + `bldweb.js`, byte for byte (`cmp`), for `https://nanofives.github.io/sc3kre/buildings/importer/` |
| pictures | `MAIN\verify\bldpack\owner_shots\` (phone-sized JPEG) |
| scripts (gitignored under `verify/*/*`) | `verify\bldpack\work\make_pack.py` (pack from the kits), `make_docs.py` (README + guide from `guide_template.html`, `captions.json`), `make_zip.py`, `pack_grid.py`, `shots.py` |

## Step 1: the picks

From the 118 kit models, buildings only (no roads, fences, trees, props). Kenney's kits are not in metres (a
suburban house is 1.3 x 1.0 x 1.1 units), so each model has its own `scale`, chosen against the class's stock base
building in `bldimport.py preview` (sizes after scale in the table). All front +Z as shipped (the kits' doors face
+Z), `rotate_deg` 0, weight 2 (stock family weights measured in BUILDFAM: 1 on almost every member, 2 on 5 members of
family 7, 3 on one of family 28).

| id | building | kit model | class | lot | scale | size W x D x H | triangles |
|---|---|---|---|---|---|---|---|
| 38000 | Solar Bungalow (slate roof) | suburban building-type-h | 3100 | 1x1 | 10 | 13 x 9 x 7 m | 1,540 |
| 38001 | Red Roof House | suburban building-type-a | 3300 | 1x1 | 10 | 13 x 10 x 8 m | 2,348 |
| 38002 | Gable House (moss roof) | suburban building-type-e | 3300 | 1x1 | 10 | 13 x 10 x 11 m | 3,462 |
| 38003 | Modern Dark House | suburban building-type-p | 3500 | 1x1 | 10 | 12 x 10 x 9 m | 2,564 |
| 38004 | Big Villa (red roof) | suburban building-type-n | 3500 | 2x2 | 13 | 23 x 18 x 15 m | 3,224 |
| 38005 | Wide Apartments | commercial building-k | 3700 | 2x2 | 11 | 23 x 10 x 16 m | 5,920 |
| 38006 | Apartment Tower | commercial building-l | 4500 | 2x2 | 13 | 18 x 18 x 30 m | 7,024 |
| 38007 | Corner Shop | commercial building-c | 5100 | 1x1 | 12 | 11 x 13 x 11 m | 2,390 |
| 38008 | Shop Row | commercial building-e | 5700 | 2x2 | 17 | 28 x 17 x 15 m | 3,018 |
| 38009 | Office Block | commercial building-n | 6100 | 3x3 | 17 | 39 x 31 x 42 m | 8,700 |
| 38010 | Glass Tower | commercial building-skyscraper-a | 6300 | 2x2 | 18 | 24 x 24 x 52 m | 2,584 |
| 38011 | Skyscraper | commercial building-skyscraper-d | 6700 | 3x3 | 22 | 28 x 31 x 120 m | 3,784 |
| 38012 | Workshop | industrial building-i | 8700 | 1x1 | 12 | 12 x 16 x 9 m | 1,596 |
| 38013 | Smoke Works | industrial building-e | 8100 | 1x1 | 9 | 15 x 12 x 15 m | 2,968 |
| 38014 | Chimney Factory | industrial building-m | 8300 | 2x2 | 16 | 21 x 27 x 24 m | 3,388 |
| 38015 | Long Factory | industrial building-r | 8900 | 2x2 | 12 | 30 x 15 x 17 m | 3,824 |
| 38016 | Brick House (ours) | make_testmodels house_tex | 3300 | 1x1 | 1 | 12 x 12 x 9 m | 34 |
| 38017 | Three-Storey Block (ours) | make_testmodels block_2x2 | 3900 | 2x2 | 1 | 23 x 22 x 13 m | 554 |

Look changes made while picking (offline previews `work/preview_z3.jpg`, `preview_z4.jpg`):

1. First pass at scale 7.5 for the 1x1 houses: visibly smaller than the stock 1x1 houses next to them. Raised to 10.
   Shop Row 14 -> 17, Office Block 15 -> 17, Big Villa 11 -> 13 for the same reason.
2. Every suburban house has the kit's mint-green roof, which the `stock` style's vibrance step makes brighter. Three
   roof variants of `colormap.png` were made by replacing only the roof swatch (pixels x 0-63, y 128-255 of the
   512 x 512 map): `red` (the kit's red swatch x 0.80 / 0.62 / 0.56), `slate` (luminance x 0.62 / 0.66 / 0.78), `moss`
   (luminance x 0.52 / 0.66 / 0.50). The MTL picks the variant, the OBJ is untouched. The guide shows this as a tip.
3. The three kits all call their texture `colormap.png`. Renamed to `kenney_<kit>_colormap*.png` so one flat folder
   works in the page and the Python tool.
4. **Dropped: Narrow Green House** (suburban building-type-k, 3100). In game its mint roof stood out against every
   stock neighbour (run2 `id38001_z4`). The pack was then rebuilt with fresh ids, so 38000-38017 are consecutive.

## Step 2: in game

`bld_lab.py` (test slot), windowed 1600 x 1000, mods of `dev\bldpack\inst`, churn `anarchy_res=5000`, speed 4,
autosave every 150 s, posted input only, camera via `cam.py`, pictures by `SC3RESIZE_FRAMEDUMP`. Runs 1-3 used the
first build (19 models, the dropped house at 38001, every later model one id higher, same files and renders); the
final run used the shipped pack. Lots per building in the last autosave of each run:

| building | final id | run1 Sacramento 12.5 min | run2 Sacramento 5.0 min | run3 Berlin 9.9 min | final Sacramento 5.0 min |
|---|---|---|---|---|---|
| Solar Bungalow | 38000 | 22 | 24 | - | 18 |
| Red Roof House | 38001 | 119 | 104 | - | 113 |
| Gable House | 38002 | 112 | 108 | - | 109 |
| Modern Dark House | 38003 | 12 | 14 | - | 14 |
| Big Villa | 38004 | 0 (1-2 in earlier saves) | 4 | - | 1 |
| Wide Apartments | 38005 | 11 | 12 | - | 7 |
| Apartment Tower | 38006 | 0 | 0 | 21 | 0 |
| Corner Shop | 38007 | 8 | 4 | - | 4 |
| Shop Row | 38008 | 1 | 1 | 2 | 0 |
| Office Block | 38009 | 1 | 0 | 1 | 0 |
| Glass Tower | 38010 | 0 | 0 | 5 | 0 |
| Skyscraper | 38011 | 0 | 0 | 0 | 0 (1 in Berlin with `anarchy_com`, step 2b) |
| Workshop | 38012 | 114 | 80 | - | 83 |
| Smoke Works | 38013 | 69 | 41 | - | 54 |
| Chimney Factory | 38014 | 5 | 3 | - | 9 |
| Long Factory | 38015 | 25 | 8 | - | 13 |
| Brick House | 38016 | 103 | 102 | - | 102 |
| Three-Storey Block | 38017 | 32 | 36 | - | 23 |
| Narrow Green House (dropped) | - | 20 | 21 | - | - |

Stock occupants in the same saves: 11,114 / 11,562 / 10,863 (Berlin) / 11,520. Run3 counted only the 5 ids it was
asked for. Faults: only the `0xC0000096 at SC3U.exe+0x84122` line every run logs at start (runs 2, 3, final).

Run1's camera step stopped with `camera not captured` (cam.py: numpad - / + did not hand over the city view after
12.5 game-run minutes), so it has counts and no pictures. Run2 and the final run, 5 minutes each, took their
pictures. Not investigated further. If it repeats, `Cam([])` gets no click fallback in `bld_lab.py`.

Pictures (`owner_shots/`, 1100 px wide):

| file | what |
|---|---|
| `00_whole_pack_z3.jpg` | the 18 buildings, zoom 3 view 0, name + class + lot (offline, the rendered frames) |
| `01_houses_mix_zoom4.jpg` | Sacramento: Red Roof Houses, moss Gable Houses, Brick Houses among stock houses |
| `02_houses_mix_zoom3.jpg` | the same at zoom 3 |
| `04_modern_dark_house_zoom4.jpg` | Modern Dark House (centre) |
| `05_corner_shops_zoom4.jpg` | two Corner Shops (white, centre) on a commercial block |
| `06_chimney_factory_zoom4.jpg` | Chimney Factory, Workshops, Smoke Works, two Long Factories, stock industry |
| `07_long_factory_zoom4.jpg`, `08_industry_zoom3.jpg` | industry |
| `09_berlin_glass_tower_zoom3.jpg` | Glass Tower (centre, dark blue glass) in Berlin's downtown |
| `10_berlin_apartment_tower_zoom3.jpg` | Apartment Tower in Berlin |
| `11_berlin_shop_row_zoom4.jpg` | Shop Row in Berlin |
| `12_pack_next_to_stock_zoom3.jpg` | `bldimport.py preview`: each building's 4 views next to its stock base's 4 views |
| `13_berlin_skyscraper_zoom3.jpg` | the Skyscraper grown in Berlin (step 2b) |

No four-rotation in-game picture: the lab's rotation shots of one lot (`final/fd/id38000_z4_v0..3`) do not keep the
lot at the screen centre, so the composite showed four different streets. `12_pack_next_to_stock` shows the four
views offline instead. Raw dumps: `runs/<run>/fd/` (PNG, no BMP left), counts `runs/<run>/counts.json`, the last
autosave of each run in `runs/<run>/saves/`.

## Step 2b: the Skyscraper with commercial churn raised (owner call 2026-11-18)

Why it did not grow: not a block, a rate. Family 22 (the only family class 6700 grows from: 15 stock members of
weight 1, plus the Skyscraper at 2) held 170 lots in shipped Berlin and 166 after run3's 9.9 game-run minutes, with
single lots moving between members (`work/fam_counts.py`). Sacramento has 0 lots of family 22. So in the earlier
runs class 6700 developed about two new lots, and the Skyscraper's share of a pick is 2 / 17.

Lever chosen: the game's own redevelopment roll, not the demand valve. sc3simrun's CHURN block (released
sc3mods-2026-11-02) sets the anarchy factor per zone type (`simrun.ini [churn] anarchy_com`, game value 100 of
10000): a working commercial lot under demand is rebuilt as the same class. `bld_lab.py` writes only `anarchy_res`,
so `work/sky_lab.py` is a copy that also writes `anarchy_com` (the tool itself is unchanged). Demand was not touched.

| run | city | settings | result |
|---|---|---|---|
| `sky1_berlin` | Berlin | `anarchy_res=5000`, `anarchy_com=5000`, speed 4, autosave 150 s, posted input only, test slot | first autosave (2.4 game-run min): **1 lot of 38011**, occupant key `{0x207EDC0E, 0x57E, 0x947B}`, class 6700, cell (161, 167), rotation 0. Family 22: 128 lots in that save (lots being rebuilt) |

Faults: the usual `0xC0000096 at SC3U.exe+0x84122` at start only. Picture: `owner_shots/13_berlin_skyscraper_zoom3.jpg`
(zoom 3 frame, cropped: the Skyscraper is the blue glass grid in a white frame, right of the twin stock towers). The
lab's zoom-4 frame of the same lot shows another part of the city (the camera trap of step 2), so there is no zoom-4
picture of it. The guide's troubleshooting now says that class 6700 changes few lots and names the setting.

## The hosted importer, checked headless

1. `docs/buildings/importer/index.html?demo=1&base=<samples folder>` from file:// in headless Chrome: title
   `[demo ready]`, the Game folder / Install into the game / No folder access / Make the install .zip controls in
   the DOM. (`selftest=1` fails there by design: it fetches a hard-coded `samples/` next to the page.)
2. bldweb's own page test (`re/tools/bldimport/webtest/pagetest.mjs`, copied to the scratchpad with the page path
   pointed at `docs/buildings/importer/index.html`, its hook `webtest/pagetest.js` copied next to the page for the
   run and deleted after, test slot): the page's Install path over the 18 pack models and `dev\bldpack\tree`,
   nothing written to disk: **PASS, 53 s, renderer `worker (blob)`**, 18 `grow` lines with ids 38000-38017 from the
   shipped `ids.json`. The tree already held the Python install of the same pack, and the page skips a write when
   the bytes on disk equal its output (bldweb.js 2017-2019): it wrote only its 10 backups and `state.json`, none of
   the 11 game files. So every game file the hosted page builds equals the Python tool's, byte for byte.
3. The zip's `importer\` files are the same bytes as the docs copy and main's (`zipfile` compare).

## Step 3: the zip

`make_zip.py`: everything in `stage/sample_pack` except `dist\` and the render cache (`sc3build\<model>\`, which the
page does not write and does not need, verify/bldweb "Known differences"), plus `importer\index.html` and
`importer\bldweb.js` from `docs/buildings/importer/`. The page lists only `.obj .gltf .glb .fbx .bld` files
(`MODEL_EXT`, classifier.html 609), so the `importer` folder inside the models folder is ignored when the player
opens the pack folder. Checked: unzipped into a scratch folder,
`bldimport.py list <unzipped> --game dev\bldpack\tree` gives 18 of 18 `ok` with ids 38000-38017 from the shipped
`ids.json`. Not checked: an install by the page from the unzipped folder (bldweb's golden tests cover the page on
Kenney models with a `Textures` subfolder).

## Step 4: the guide

`docs/buildings/index.html`, the gallery's look (same tokens, sticky section chips, light and dark), no script,
works opened from disk. Sections: what it does (and does not), the sample pack (sheet, 4 in-game pictures, building
table, zip contents, credits), making or finding a model (units, Y up, front +Z, 16 m cell, footprint per lot,
class x lot table from `batgrow.class_table`, textures, polygon budget from the pack's 34 to 8,700 triangles),
classifying, installing and removing (bldweb's steps: Open folder, Game folder, Look, Install into the game, Remove
from the game, No folder access with Make the install .zip / Make the removal .zip), `.bld` files and the one-view
limit, tips for a stock look, troubleshooting (close the game, textures inside the models folder, the .zip route,
Chrome / Edge, wrong game folder, a run stopped halfway, grey textures, front the wrong way, removed models).

Voice check (script over the visible text): 0 semicolons, em or en dashes, ellipses, "very" / "really" /
"significantly" / "extremely" in the guide and the README. Rendered in headless Chrome at 1280 px. At 390 px the
headless window lays out wider than the screenshot (the existing gallery page is cut the same way), so phone width
is not verified by screenshot. Long code paths wrap (`overflow-wrap: anywhere`).

Facts in the guide and where they come from: 16 m cell, front +Z, flat-shaded two-sided faces, lot = 128 px at zoom 4,
styles (`re/analysis/BUILDING_ART.md` 4, 4.1), ids 38000-38999 and `ids.json` (bldimport), stock weights (BUILDFAM
measured above), a save opened without the buildings gets a stock building of the same type per lot
(verify/batconvert/RESULTS.md 5, same containers), "under 3 minutes" (the Python `preview` rendered all 19 of the
first build in 2 min 45 s on LIVING-PC), page steps and limits (verify/bldweb/RESULTS.md), `.bld` behaviour
(verify/bldfile/RESULTS.md).

## Open for the orchestrator

- The zip link points at `https://github.com/nanofives/sc3kre/releases/latest` (`--zip` in make_docs.py). The README
  points at `https://nanofives.github.io/sc3kre/buildings/importer/` and the guide at `.../buildings/`.
- The guide links the importer as `importer/index.html` (works on Pages and from disk) and names the zip copy.
- If `classifier.html` / `bldweb.js` change on main, recopy them into `docs/buildings/importer/` and rerun
  `make_zip.py`.
