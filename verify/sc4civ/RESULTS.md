# sc4civ results (round 2026-11-19l): SimCity 4's civic buildings, parks and rewards from the player's own install

Input: the Steam SimCity 4 Deluxe on this PC, read in place (`C:\Program Files (x86)\Steam\steamapps\common\SimCity 4
Deluxe`). EA's files: nothing of them or made from them is in the repository or docs. Pictures in `owner_shots\`
(gitignored, for the owner only). Formats and counts: `re/analysis/SC4_FORMATS.md` section 10.

**Verdict.**

- **How SC4 marks them: OccupantGroups (0xAA1DD396).** 0x1005 civic (42 buildings), 0x1006 park (32), 0x150B reward
  (53), 0x150A landmark (39), plus a service group for civic buildings (0x1500 police, 0x1501 jail, 0x1502 fire, 0x1503
  school, 0x1504 college, 0x1505 library, 0x1506 museum, 0x1507 health, 0x1702 zoo). Reward conditions are not in the
  exemplars: they are 60 Lua records in SimCity_1.dat, keyed by the building's exemplar instance.
- **Mapping.** Civic buildings become civic looks of the SC3 button for their service, parks civic looks of a park
  button (by name, else by footprint), rewards SC3 rewards with SC4's population when the condition counts the whole
  city (36 of 60 records, else the default 20,000, year 0 always), landmarks SC3 landmarks. 113 buildings have a
  model, 112 convert, 73 are on by default. 21 have no model (their look is lot props) and are named, not converted.
- **The player's install is a source** in the page (new button **Open SC4 game**, or the `.dat` files through Open SC4
  .zip) and in `sc4conv.py <install>`. The page reads 79.0 MB of the install's 687 MiB, by slices. Python and the page
  give the same files to the byte: 379 OBJ / MTL / models.json files, 739 textures pixel for pixel, the 4-building
  subset's 7 game files and 80 frames.
- **In game: works.** The SC4 Small Police Station, Small Fire Station and Gazebo each appeared in their button's list
  window and were placed with the stock tool (types 13130, 13002, 14311). The Mayor's House unlocked at population 500,
  was listed, placed (type 38003). All four came back at the same cells after save and reload, the reward was not
  offered again, and the police look drew its own coverage: bulldozing it removed 180 cyan pixels from the crime map
  and added none.

## 1. Conversion of the install

`sc4conv.py "<install>" --out <dir>`: 7 DBPF files, 713 buildings with S3D models, 1,908 lots.

| | count |
|---|---|
| civic / park / reward / landmark buildings with a model | 113 (of 743 buildings) |
| converted | 112: civic 22 (police 4, fire 3, school 3, hospital 2, jail 1, college 1, library 1, museum 1, small park 4, big park 1, baseball 1), reward 51, landmark 39 (counts from the page's cards, section 2) |
| skipped | 1: Large High School, view 3: one atlas piece 59.66 px off the view's projection |
| on by default | 73 (the rest: too large for the base's lot or for 4x4, or a second building of the same SC4 name) |
| no model, named in the report | 21 (plazas, gardens, greens, Playground, Basketball Court, Skateboard Park, both stadiums) |
| lot props (the install as its own prop source) | 1,302 of 7,337 rows placed on 77 buildings, 4,247 outside the SC3 lot, 54 of another season, 1,734 without a readable model (animated people, effects, resource key type 0) |
| rewards with SC4's population | e.g. Mayor's House 500, City Hall 12,500, Courthouse 40,000, Casino 24,000 (`1.6 * POPULATION_STEP_6`), Main Library 20,000 default (it counts residents of one wealth) |
| time | Python 2 min 16 s; node 142-149 s alone (240 s with a second job running); the page in headless Chrome 84.5 s |

`bldimport.py pack` of the 73 enabled: 73 buildings, two plugins (`bldimport.dat` 11,614,923 bytes, `bldimport_rewards.dat`
6,870,230 bytes), no refusal. Note from it on the Mayor's House: its mesh is 17.0 x 14.7 m on a 1x1 lot (the occupant
size says 15 x 14 m), so it overhangs its neighbours a little.

Rebuilt views (zoom 4 frames of the test set, `dev\sc4civ\work\game4\sc3build`): the police station with its lot's cars,
the fire station, the Gazebo and the Mayor's House draw clean in the 4 rotations (checked by eye on the frames).

### Fixes found while converting

- SC4's textures are in FSH group 0x1ABE787D, not the S3D's group (all 112 needed `views.tex_key`).
- 63 of the 113 buildings hold their exemplar type only in a parent cohort (`Index.full`). Without it 63 would be missed.
- The multi-mesh views are atlases, not 256-pixel tiles (`compose_atlas`): before it 74 of the 113 failed with "tile
  offset is not on the pixel grid", and 7 passed the tile test with fits of 12-98 px (wrong pictures).
- The Casino's `1.6 * tuning_constants.POPULATION_STEP_6` first read as population 1. Thresholds now take a factor.

## 2. Byte identity, Python = page

| check | result |
|---|---|
| `sc4_install_setup.py` + `sc4_install.mjs` (test slot) | **18 of 18**: 379 OBJ / MTL / models.json byte for byte, 739 textures pixel for pixel, the file list (1,118 files), the notes, the kinds (police, fire, Gazebo small park, Softball Field baseball, Mayor's House 500, Courthouse 40,000, Big Ben landmark), read by slices (79.0 MB of 687 MiB, one whole read: SimCityLocale.DAT, 0.9 MB), the rerun keeps a reward's population + switch and a civic look's base (= sc4conv.py over the same file), two conversions the same, the subset (police, Gazebo, Mayor's House, Big Ben) packed: 7 game files + ids.json + 80 frames = bldimport.py |
| `pagetest.mjs --case sc4install` (the page in headless Chrome, the 7 `.dat` files picked) | **4 of 4**: 112 cards, 73 on, no card error; the note (install line, EA rule, no download wording); the install read only (no folder handle); kinds civic / reward / landmark, Mayor's House reward at 500, year 0 |
| `run_all.sh` with the six arguments, `SC3PACK_PACKS`, `SC4INSTALL` | see section 5 |

A page fix found by that test: a building with lot props has two OBJ files (`<stem>.obj` alone, `<stem>_props.obj` with the
props, the entry's file), and the page made a card of both (189 cards for 112 entries; also true for downloads with
props since round sc4props). The page now makes one card per models.json entry.

## 3. In game

Tree `dev\sc4civ\tree`, all mods of `dev\sc4civ\inst`, windowed 800x600, started by `pwsh re/scripts/sc3dev.ps1 run sc4civ`
only. Posted input (sc3io through `re/tools/civmod_lab.py`) and Frida reads (`tool`, `find`, the camera of
`verify/showcase/cam.py`), pictures by SC3RESIZE_FRAMEDUMP. City Madison, WI. Test data: `sc4conv.py <install> --only
<the 4>` then `bldimport.py build --game dev\sc4civ\tree`: ids 38000 fire, 38001 police, 38002 Gazebo, 38003 Mayor's House.

| check | result |
|---|---|
| load | `CIVVAR> on: 3 civic button(s) with 3 variant look(s)`, `CIVDLG> on`, `NEWREWARD> 1 reward type(s) declared by the loader 38003`, row population 500 year 0 |
| Police button (hotkey 0x18), list window | "Elegir aspecto": Comisaría, Small Police Station; the SC4 entry with its own picture, "Precio: §500", "Aspecto 2 de 2" (owner_shots 01) |
| pick + place | tool key `0x207EDC0E 0xB1D10002 0x9471`; placed at (192..194, 204..206), type 13130, flags 0x104, funds 102,174 -> 101,674 |
| Fire button (0x19) | list with "Small Fire Station" (02); key 0x9470, placed (191..193, 200..202), type 13002, price 500 (RELOCATE log) |
| Small Park button (0x39) | list with "Gazebo" (03); key 0x9472, placed (191, 205), type 14311, price 100. The three side by side: owner_shots 04 |
| reward unlock | `type 38003 passed population and year: unlocked` 146.8 s after start, population about 149,000 |
| Rewards and Opportunities (0x3b) | "Mayor's House", its picture, "From SimCity 4" (05). OK arms a one-shot tool `0xB1D10002 0x9473`; placed (189, 201), type 38003, price 0 (no price row for a new type, as in civmod); tool gone after the placement |
| save | autosave #2 copied to `tree\Cities\sc4civ_saved.sc3`; `occupant_layer.py`: 4 occupants of group `207edc0e/b1d10002` |
| reload (new game, `-City sc4civ_saved.sc3`) | `find`: the same 4 keys at the same cells; picture at zoom 3 and 4 (06, 08, 09 rotation 2); Rewards list "No hay Recompensas ni Oportunidades disponibles ahora" (07) |
| coverage | crime map (Ver datos, "Cobertura de Policía") with the SC4 police look, then the look bulldozed (Demolish 0x12), map again: cyan pixels 2,963 -> 2,783, 180 gone, 0 new, all in one region (map pixels x 247..311, y 342..406) (11, 12, 10 = the gone pixels in magenta) |
| VEH FAULT | both runs: only the start-up `0xC0000096 at SC3U.exe+0x84122` |

Game PIDs, started by this session and stopped by PID: 21804, 15128.

Pictures (`owner_shots\`): 01-03 the list windows, 04 the three looks placed, 05 the reward listed, 06 after reload,
07 the Rewards list after reload, 08-09 zoom 4 rotations 0 and 2, 10-12 the crime map.

## 4. Not run, limits

- The menu button clicks themselves (the hotkey takes the same GetCommand path, civdlg measured both).
- The fire look's own coverage map, the Gazebo's effect on land value, any reward other than the Mayor's House, any
  landmark from the install in game (the landmark kind itself was placed in plop and plop2).
- The page's Install of the install's buildings (the page test opens and checks the grid; bldweb.js packing of the
  subset is checked byte for byte in node, which is the code the page runs).
- Reward conditions other than population (mayor rating, funds, missions, buildings) have no SC3 column: on the card
  only. Rewards keep the stats of the stock reward of their lot size (civmod).
- SC4 buildings larger than the base's lot (Large Police Station 31.9 x 28 m fits 3x3; Large Medical Center 47.9 m
  fits 3x3; the Large High School does not convert) are off with the reason on the card.
- Lot textures are not drawn (next stream sc4lottex). SC4's own props are placed only on SC4's own lots: reading the
  install as a prop source for downloads is the next stream (sc4baseprops).
- The `Open SC4 game` button and the `.dat` picker were run through the page's own `openSc4` with File objects; the
  folder input itself needs a real click (owner check). Chrome's folder picker refuses Program Files (where Steam puts
  SC4), which is why the button uses a plain folder input.

## 5. Suite

`SC4INSTALL="C:/Program Files (x86)/Steam/steamapps/common/SimCity 4 Deluxe" SC3PACK_PACKS=MAIN\stage\st_packs
PROYECTOS_TEST_MEM_GB=6 PROYECTOS_TEST_HUB=off test-slot bash re/tools/bldimport/webtest/run_all.sh dev\sc4civ\workunall
stageelease stage\kits "<.happy-uploads>\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes
stage\st_packs\sc4`: **34 of 34 steps passed** (31 before + the 3 install steps). The existing SC4 steps (JMyers zip and
folder, the tower, the two lot-only packs, the BSC lot props) pass with the cohort parents, the texture key and the
atlas path in place: the downloads read as before. `sync_css.py --check` in sync, `--publish` done after the last page
change. `PROYECTOS_TEST_HUB=off`: the install exists on this PC only. Log `dev\sc4civ\workunall.log`.

## 6. Files

| file | change |
|---|---|
| `re/tools/sc4conv/rewards.py` (new, `git add -f`) | Lua reward records -> population |
| `re/tools/sc4conv/catalog.py` | `install_files`, `Index.full` (cohort parents), exemplar cache, `groups` |
| `re/tools/sc4conv/views.py` | `tex_key`, `compose_atlas`, `compose_tiles` declines atlases |
| `re/tools/sc4conv/props.py` | prop textures through `tex_key` |
| `re/tools/sc4conv/dbpf.py` | files from 16 MB memory-mapped |
| `re/tools/sc4conv/sc4conv.py` | `service_for`, kinds civic / reward / landmark, install filter + notes, `design_key`, `editable` |
| `re/tools/bldimport/sc4web.js` | the same in the page, the lazy install index (`readDbpfLazy`, `fetchTypes`, `fetchModels`) |
| `re/tools/bldimport/classifier.html` | Open SC4 game, install note + status, read only, one card per entry |
| `re/tools/bldimport/webtest/sc4_install_setup.py`, `sc4_install.mjs` (new, `git add -f`) | the identity test |
| `re/tools/bldimport/webtest/pagetest.mjs`, `pagetest.js` | `--sc4install`, `--expect-install`, the open-and-check branch |
| `re/tools/bldimport/webtest/run_all.sh` | 3 steps with `SC4INSTALL` |
| `docs/buildings/importer/*` | `sync_css.py --publish` |
| `docs/buildings/index.html` | `make_docs.py` from the template (sample pack link kept, `stage\sample_pack\README.txt` byte-identical, sha256 bdda1dee...) |
| `re/analysis/SC4_FORMATS.md` | section 10, one [UNCERTAIN] of section 9 answered |
| MAIN `verify/bldpack/work/guide_template.html` (gitignored) | new subsection "From your own SimCity 4", lot props bullet and limits line |
