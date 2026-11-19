# plop results (round 2026-11-19h): new ploppable buildings, landmarks first

**Verdict: landmarks work as data, no mod code.** SC3U still loads Maxis' 2000 landmark plugins (.pin + .dat) by
itself from `Apps\PlugIn\`: their buildings are in the stock landmark dialog and can be placed, saved and reloaded. As
shipped their art does not draw (SC3U dropped the 2000 LZO1X sprite decoder); converted to SC3U's QFS records it draws.
Our own buildings become landmarks the same way: `bldimport.py` / the page write a plugin
(`Apps\PlugIn\bldimport\bldimport.pin` + `.dat`), no overlay and no road mod. The pack reader installs Maxis landmark
plugins with the art converted. Civic buildings and rewards need more (menu code / reward lists): described, not
built. Static evidence: `re/analysis/PLOPPABLES.md` (worktree `dev\plop\wt`).

## 1. How the game does it (static, PLOPPABLES.md)

| question | answer | where |
|---|---|---|
| does SC3U load .pin plugins? | yes: every `*.pin` under `<Apps>\PlugIn\`, any depth | SIMINIT `0x1000583e` (Init with `PlugInDirectory() + "PlugIn\"`), `0x1000ea2a` (recursive `*.pin` scan), `0x1000e8d1` (per .pin) |
| plugin root | `[Directories] PlugIn=` of `Apps\SC3U.ini`, default the Apps folder (GOG's ini has no such section) | SC3U.exe `cGZFileSystem::PlugInDirectory` `0x00482532` |
| what reads which section | `[DBSegments]` opens the .dat as a DB segment, `[SpriteSegments]` registers `Apps\Plugin\<key>\*.DAT` as sprites, `[OccupantKeys]` goes to the `sc3occattrib` registry | SIMINIT `0x1000ec96`, `0x1000eeef`, `0x1000edfb` / `0x1000ee62` |
| landmark menu | every loaded occupant exemplar whose type (prop 0x65) IsA 18000; CitySim.ini maps 18001..18045 to 18000 | SIMADV `0x10008ef2` |
| line under the name | prop 0x7C text key (stock: the city it stands in) | catalog string table `0x62e69238` |
| why the 2000 art is blank | format 1 records with dword1 0x8000 are skipped; the 0x8000 / 0xC000 decoder slots call a `return 0` stub | SIMSPR `0x1001de49`, `0x1001e086`, `0x1004efdd` |
| the 2000 compression | LZO1X-1 (found against the pack's Palace of Fine Arts, which is also stock SC3U art) | `sc3plugin.py` |
| civic / rewards | civic = one menu entry + command per building (`MenuItem.INI`); rewards = fixed type list `Advisor-CityPlanner.ini [REWARD_BUILDINGS]` + per-reward unlock rules | needs mod code (civic) or more RE (rewards) |

## 2. Maxis Landmark Pack 1 and 2, the native way

| step | result |
|---|---|
| copy `LandmarkPack1.pin/.dat`, `LandmarkPack2.pin/.dat` as shipped into `dev\plop\tree\Apps\PlugIn\LandmarkPack1\` / `\LandmarkPack2\` | game PID 3688 (Madison, WI): a memory scan shows it opened `...\Apps\PlugIn\LandmarkPack1\LandmarkPack1.dat` and the `.pin` files, and lists `...\Apps\Plugin\LandmarkPack2\*.DAT` |
| landmark dialog (Civic button, Landmarks) | the last 5 rows: Museum Of Modern Art, Transamerica Tower, Palace Of Fine Arts, Guggenheim, New York Public Library. The stock Palace (Palacio de Bellas Artes, 9510) stays in its own place: a different key |
| place MOMA (4x4) | placed at cell (176, 213) (sc3resize log "building placement ... placed, price 120"), key `{0x207EDC0E, 0x43B843E4, 9505}`, type 18040 in the save. **Drawn as a pale blue grid on the lot, no building** (owner_shots/02) |
| convert the two .dat files (`sc3plugin.py convert`: 48 + 32 pixel records) and reload the same save (PID 15544) | MOMA draws, zoom 3 and 4, four view rotations (owner_shots/03) |
| after the change the dialog shows MOMA greyed, "Ya existente" | the game's one-per-city rule applies to plugin landmarks |

Converter check: all 80 pixel records of both packs decode to their stated length using the whole stream; the 16
Palace frames decode byte-identical to SC3U's stock 9510 blocks, and re-encoded they are byte-identical to SC3U's own
stock records. `sc3pack.js` converts both packs to the same bytes as Python (sha256 `4a5582ba...` / `40b50cf6...`).

## 3. Our buildings as new landmarks

`make_testmodels.py --landmarks` -> `bldimport.py build <folder> --game dev\plop\tree`:

| entry | result |
|---|---|
| Test obelisk, 2x2 | `plop [38000] ... Landmark, 2x2, stats of stock 9507` (Coit Tower) |
| Test pavilion, 3x3 | `plop [38001] ... Landmark, 3x3, stats of stock 9528` (Arc de Triomphe) |
| landmark 5x5 | skipped: lot 5x5 (the tool offers 1x1 to 4x4) |
| kind civic | skipped: only growable, airport, seaport and landmark buildings |
| files | `Apps/PlugIn/bldimport/bldimport.pin` (271 bytes) + `bldimport.dat` (255 KB); no overlay file touched |

In game (PID 12376, Madison with MOMA):

| check | result |
|---|---|
| dialog | "Test obelisk" and "Test pavilion" after the Maxis rows, each with its own preview picture (owner_shots/01) |
| place | obelisk at (177, 207), price 0; pavilion at (175, 209), price 5 (two other spots were refused by the stock site check, red footprint) |
| draw | zoom 3 and zoom 4, all four view rotations (owner_shots/04, 05, 06) |
| save | the autosave holds `{0x207EDC0E, 0xB1D10002, 38000}` and `38001`, type 18000, at those cells |
| reload (PID 9284) | all three landmarks draw (owner_shots/07); the dialog greys both of ours, "Ya existente" |
| description | first build: line 2 was the base's place ("San Francisco, California USA", "París, FRANCIA", owner_shots/09). Fixed: prop 0x7C -> our own text record, the entry's `description` (else its name). Rebuilt and reloaded (PID 15768): "Test monument, bldimport" (owner_shots/01) |
| load without the plugins (`bldimport.py restore` + both Maxis packs moved out; PID 20276) | no crash; no occupant on any of the three lots; the lots show orange-brown ground (owner_shots/08). Unlike growables (replaced by a stock building of the same type, verify/airsea 4), nothing takes their place |

Every game was windowed 800x600, mods of `dev\plop\inst`, posted input only (sc3io), camera through the city view's own
SetZoomAndRotation, pictures by SC3RESIZE_FRAMEDUMP (BMPs deleted). Each run's `resize.log` has one
`0xC0000096 at SC3U.exe+0x84122` line at startup, the same line as the bldrender and airsea runs. Game PIDs 3688, 15544,
12376, 9284, 20276, 15768: started by `sc3dev.ps1 run plop`, stopped by PID.

## 4. Tools

| tool | change |
|---|---|
| `bldimport.py`, `bldweb.js` | kind `landmark`: lot 1x1..4x4, weight not used; base = first stock landmark by id with that lot (`landmark_table`); exemplar re-keyed `{0x207EDC0E, 0xB1D10002, id}`, prop 0x65 = 18000, name / description / frame table in groups `0xB1D10004` / `0xB1D10005` / `0xB1D10003`, pixels `0xB1D10001`; all in `Apps/PlugIn/bldimport/bldimport.dat` + `.pin`. The overlay (road mod) is only required when the install has growables or ports, or to put back an earlier run's overlay files. `restore` removes the plugin |
| `sc3plugin.py` (new) | LZO1X-1 decoder, 2000 record -> SC3U QFS record, `convert` / `info` CLI |
| `sc3pack.py`, `sc3pack.js` | report: per plugin `install` (`Apps/PlugIn/<the .pin's folder>/...` from its `[DBSegments]` paths), `not_installable`, `art_1999`; install writes the .pin + converted .dat files with the parts' rules (conflict unless overwritten, backups, state, `remove`). The page view says where a plugin goes and how many pictures it converts, and the Install button counts plugins |
| `classifier.html` | kind `landmark` (name words landmark, monument, statue, obelisk, memorial, museum, cathedral, basilica, palace, castle, pavilion, temple), lot 1x1..4x4 with the reason, warning for other lots; `ploppable` stays for civic words (park, school, hospital, fire, police, church, library, stadium), not imported |
| `make_testmodels.py` | `--landmarks`: obelisk 2x2, pavilion 3x3, two entries to refuse |
| webtest | golden case `landmarks` (2 models + `Garvey Plaza.bld` as a landmark, one description), a landmark in case `ports` (overlay + plugin in one install), `pagetest.mjs landmarks`, `sc3pack_golden --plugin-pack maxis_addons_2000` (install, again, remove on a file list and a real folder); `pagetest.mjs` counts the backups against the outputs the game already had (the plugin files are new, like the B1D10001 DAT); run_all.sh 28 -> 29 steps with the six arguments |

## 5. run_all.sh

`test-slot bash re/tools/bldimport/webtest/run_all.sh dev\plop\work\runall2 stage\release stage\kits
"<.happy-uploads>\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes stage\st_packs\sc4`
with `SC3PACK_PACKS=stage\st_packs`: **29 of 29 steps passed** (log `dev\plop\work\runall2.log`). Among them:
golden_setup 6 cases; golden.mjs 71 of 71 (case ports with the landmark: plugin + overlay files; case landmarks: the
plugin .dat 472,706 bytes and .pin byte-identical, frames 60 of 60); pagetest ports 17 of 17 and landmarks 6 of 6 (the
page in headless Chrome installs them); sc3pack_golden.mjs 29 of 29 (the reports, the parts run and the plugin run:
install, install again, remove, on a file list and a real folder); every older step unchanged.

The first full run (`runall.log`) was 27 of 29: pagetest ports and landmarks failed only their backup count, which
assumed every output but the B1D10001 DAT already existed in the game. The plugin files are new as well; the check now
counts the outputs the game already had. All installed files had matched in that run too.

## Pictures (`owner_shots/`)

| file | what |
|---|---|
| `01_landmark_menu_maxis_and_ours.jpg` | the stock landmark dialog: the 5 Maxis plugin landmarks and our 2 at the end, ours selected with its own preview and description, "Ya existente" |
| `02_moma_2000_art_as_shipped_blank_lot.jpg` | MOMA placed from the pack as shipped: blue grid, no building |
| `03_moma_converted_zoom4.jpg` | the same lot after converting the pack: MOMA drawn |
| `04_obelisk_pavilion_moma_placed_zoom3.jpg` | our obelisk and pavilion placed next to MOMA |
| `05_obelisk_pavilion_zoom4.jpg` | ours at zoom 4 |
| `06_four_view_rotations_zoom3.jpg` | the three landmarks in view rotations 0-3 |
| `07_after_save_and_reload.jpg` | the save loaded again |
| `08_loaded_without_the_plugins.jpg` | the same save with no plugin installed: three empty orange-brown lots |
| `09_menu_entry_before_description_fix.jpg` | the pavilion's line 2 before the fix ("París, FRANCIA", from its base) |

## Not tested

- Whether the orange-brown lots left by a removed landmark can be built on again.
- A Landmark Pack installed by the page in Chrome on a real game folder (the install is checked byte for byte against
  Python on a file list and a folder handle in node, `sc3pack_golden.mjs`; `sc3pack_pagetest.mjs` drives the view).
- Landmarks of 5x5 lots (78 stock landmarks are 5x5; bldimport stops at 4x4).
- Civic buildings and rewards (section 1: mod code or more RE needed).
