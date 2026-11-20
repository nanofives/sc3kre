# sc4baseprops results (round 2026-11-19l): SimCity 4's own props from the player's install for downloaded lots

**Verdict: done in Python and in the page, byte identical. With the BSC pack and the install together, no prop row of the
JMyers pack is left without a source: 2,236 of its 5,190 rows are placed, on all 110 buildings (486 on 72 with the BSC
pack alone).** The player's SimCity 4 install is one more prop source after the download and the dependency packs:
`sc4conv.py <download> --sc4 <install>`, and in the page the game's `.dat` files picked with the download in Open SC4
.zip, or the game opened first with Open SC4 game (kept for the page session). In game: 4 JMyers designs, each
installed twice (BSC props, BSC + game props), all 8 grew in Sacramento by the first autosave, and the SC4 Small Police
Station look was picked in its list window and placed (section 4).

EA's files are read in place. Nothing of them, of the community packs or of the pictures is in the repository or docs.
Pictures in `owner_shots\` are local, for the owner. Formats and rules: `re/analysis/SC4_FORMATS.md` section 11.

## 1. Command

```
py -3.12 re/tools/sc4conv/sc4conv.py <SC4 plugin folder> --out <folder> [--deps "<BSC Common Dependencies Pack V9e.zip>"]
          --sc4 "<SimCity 4 folder, the one holding SimCity_1.dat>"
```

`--sc4` on an install conversion (`sc4conv.py <install>`) adds nothing: the install is already its own source. A folder
without `SimCity_1.dat` is refused (exit 2). Report lines: `SimCity 4 install as a prop source: 1544 prop exemplars, 388
cohorts`, then the "Lot props" line of round sc4props; the "Props not found" line names "a dependency not given" when
the install was given, "SimCity 4's own props or a dependency not given" when not.

In the page (`classifier.html`, `sc4web.js`):

| how | what the page does |
|---|---|
| Open SC4 .zip, the download + the game's `.dat` files picked together | the download is converted, the 7 game files become its prop source (`sourcesFrom`: an install's files plus another SC4 file or archive at the top of the pick). A pick of the whole game folder stays the install conversion of round sc4civ: its `Intro.dat`, `Sound.dat` and subfolders (Plugins, Sku_Data) do not count as a download |
| Open SC4 game, then Open SC4 .zip with the download alone | the game is kept for the page session (`rememberSc4Game`) and lends its props to every SC4 download opened after it |
| either | the note on the download says "SimCity 4's own props came from your SimCity 4 game (...)". Without the game and with props not found, the note says how to add it |

The page reads the install's exemplars and cohorts once per session by slices, then the S3D and FSH of the props it
places: 13.3 MB in slices and 1.0 MB of whole small files (SimCityLocale.DAT) for the JMyers pack, no large file read whole.

## 2. Measured on the JMyers pack (110 buildings, 5,190 prop rows of their smallest lots)

| sources | placed (buildings) | outside the SC3 lot | other season | in no source (ids) | no readable model |
|---|---|---|---|---|---|
| BSC pack alone (= round sc4props) | 486 (72) | 866 | 378 | 3,454 (54) | 6 |
| install alone | 1,786 (110) | 1,634 | 0 | 1,676 (81) | 94 |
| BSC pack + install | 2,236 (110) | 2,494 | 366 | **0** | 94 |

What stays out with both, and why:

- **Outside the SC3 lot, 2,494 rows**: the SC3 lot is 16 m per cell, the JMyers lots 16 x 32-48 m; a prop whose centre
  falls outside the window is left out (rule of round sc4props, unchanged).
- **Other season, 366 rows**: seasonal variants not shown on 1 July (rule unchanged).
- **No readable model, 94 rows**: 88 rows whose Resource Key Type 4 records point at resource type 0x29A5D1EC and hold no
  S3D record (`ACV6x4x4_jump-ropeanimate_1DE7` 18, `Aper2x2x4_female-S-drk01-wait` 14, `ACV6x2x4_keep-awayanimate_1D46` 12,
  `Amill4x2x4_exploritorium_29C2` 12, `Aper2x2x4_male-drk01-negative-tantrum_2875` 8, `AR8x8x2_$DogOnAChain_1ef3` 6, others
  of the people family A0000068), 6 rows of `Randomwalk_MowerBldg` (Resource Key Type 0 {S3D, 0xBADB57F1, 0}). [UNCERTAIN:
  what 0x29A5D1EC holds; by their names these props are animated. Not read.]
- The two most used ids of round sc4props, `1EDF0000` (1,380 rows) and `28330000` (804), resolve to the install's
  `Flora2x2x2_QuarterShrub_1EDF` and `Flora2x2x2_Quarterbush_2833`, as do all 54 ids the BSC pack lacked.

Two rules changed to read the sources as one exemplar space (SC4_FORMATS.md 11.2), both in Python and the page:

- **Families pooled over all sources.** Family A0000038 (cars) has 502 members in the BSC pack and 23 in the install
  (48 rows), A0000068 (people) 2 and 46 (12 rows). With one source nothing changes: the BSC-alone and install-alone
  numbers above are the same as before the change.
- **A prop's model from the first source holding its 4 views.** The BSC prop `CP_MaxisFluffyMed` names SimCity 4's own
  S3D `1EDA0000`, held only by the install: its 6 rows had "model not in the packs", now they have a model (outside the
  window on these lots).

Effect of the two rules with both sources (measured before and after): placed 2,236 both times, other season 378 -> 366
and no readable model 88 -> 94 (the 12 A0000068 rows: the BSC members 287D0000 / 28870000 are timed, interval 365, start
{10, 1}, 120 days, so not active on 1 July, and the pooled list adds the install's people), outside 2,488 -> 2,494 (the 6
FluffyMed rows).

SC4's own buildings from the install (round sc4civ): their lots have one source, so the rules give the same rows:
1,302 of 7,337 placed on 77 buildings, 0 missing, as in sc4civ (measured again in the suite, section 3). Nothing is
missing there for the BSC pack to supply.

Time: Python 12 s for the JMyers pack with both sources (BSC index cached), 10.7 s with the install alone; the node route
33.5 s with the BSC zip indexed in the run (22 s of it).

## 3. Byte identity and the suite

| check | result |
|---|---|
| `sc4_baseprops_setup.py` + `sc4_baseprops.mjs` (new, test slot) | **132 of 132**: the pick (download converted, install a prop source of 7 files, BSC zip streamed); the whole game folder picked alone (11 DBPF files, Intro.dat, Sound.dat and the two Sku_Data plugins among them) stays the install; per building OBJ / MTL byte for byte (house and `_props`), its textures pixel for pixel (110 buildings); 135 `sc4prop_*.png` pixel for pixel; models.json byte for byte; the file list (1,016 files); install read by slices; the install alone picked with the download = `sc4conv.py --sc4` (113 checks); the install remembered then the download alone: models.json = `sc4conv.py --sc4`; without the install the note keeps "SimCity 4's own props"; bldweb pack of the 12 enabled = `bldimport.py pack` (11 game files + ids.json); 240 frames RGBA |
| `pagetest.mjs --case sc4baseprops_inst --sc4with` (headless Chrome, the JMyers .zip + the 7 `.dat` files picked) | **19 of 19**: 110 cards, 12 on, 18 design groups, 36 diagonal marked, note names the game as the prop source, 110 cards with props on (= Python), the page's install = `bldimport.py pack` file by file (sha256), ids.json, backups, Web Worker |
| `pagetest.mjs ... --sc4remember` (the game opened first, then the .zip alone) | **19 of 19**, the same checks |
| `run_all.sh` with the six arguments, `SC3PACK_PACKS`, `SC4INSTALL`, `PROYECTOS_TEST_HUB=off` | see below |

`SC4INSTALL="C:/Program Files (x86)/Steam/steamapps/common/SimCity 4 Deluxe" SC3PACK_PACKS=MAIN\stage\st_packs
PROYECTOS_TEST_MEM_GB=6 PROYECTOS_TEST_HUB=off test-slot bash re/tools/bldimport/webtest/run_all.sh dev\sc4baseprops\workunall2
stageelease stage\kits "<.happy-uploads>\SC4D LEX Legacy - BSC JMyers Homes Pack V3.1.zip" stage\st_packs\sc4_jmyers_homes\jar
stage\st_packs\sc4`: **38 of 38 steps passed** (34 before + the 4 sc4baseprops steps), log `dev\sc4baseprops\workunall2.log`.
The earlier steps compare what they compared before: the BSC-alone props (step 31, 130 of 130) and the install
conversion of round sc4civ (step 33, 18 of 18; its lots still 1,302 of 7,337 prop rows placed on 77 buildings, 0 missing,
as in sc4civ).

A failure the suite caught on the first full run: `sourcesFrom` took the install's own `Intro.dat` and `Sound.dat` at the
top of a whole-folder pick for a download picked with the game, so Open SC4 game on a real game folder converted 1
building instead of 112 (`sc4_install.mjs` 1 model). The rule now ignores the game folder's other top-level files, and
`sc4_baseprops.mjs` checks the whole-folder pick.

`sync_css.py --check` in sync; `--publish` done after the last page change (docs/buildings/importer). Guide:
`make_docs.py --wt dev\sc4baseprops\wt --tree stage\release --zip <the published sample-pack URL>`: only the SC4 text
changed in docs/buildings/index.html, the sample-pack link kept, `stage\sample_pack\README.txt` byte identical (sha256
bdda1dee...).

## 4. In game

Tree `dev\sc4baseprops\tree`, mods of `dev\sc4baseprops\inst`, windowed 1600 x 1000, posted input and Frida game
calls only. Models folder `dev\sc4baseprops\work\lab`: the converter's output with BSC + install, every building off
but 4 designs entered twice, and the install's Small Police Station (`sc4conv.py <install> --only
CV24X24_4carLocalPrecinct_030C`, 35 of 36 prop rows placed). `bldimport.py build work\lab --game tree`:

| design | props placed, BSC pack | id | props placed, BSC + game | id |
|---|---|---|---|---|
| 135 Rocky Summit Road (Blue Ridge) | 3 | 38110 | 25 | 38018 |
| 214 Abbey Glen Rd (Abbey Glen) | 0 (house alone) | 38111 | 21 | 38000 |
| 10 Red Barn Road (Destiny) | 7 | 38112 | 24 | 38042 |
| 56 Amber Creek Road (Heritage) | 8 | 38113 | 22 | 38072 |

**Run 1, growth** (`bld_lab.py`, Sacramento, churn anarchy_res 5000, speed 4, autosave 150 s, game PID 15028): at the
first autosave (2.5 game-run minutes) lots per id 38110: 7, 38111: 9, 38112: 11, 38113: 6 (BSC props) and 38018: 2,
38000: 9, 38042: 12, 38072: 6 (BSC + game props). All 8 found in the zoom-4 dumps by their own frames
(`work\find_in_dump.py`, scores 0.73-0.98). A first attempt (PID 11852) wrote no log: a relative `--out` (the game
resolves it from `Apps\`) and the test slot's job ended the game when the slot closed.

**Run 2, the SC4 civic look** (`sc3dev.ps1 run sc4baseprops -City sc4baseprops_grown.sc3` = run 1's first autosave,
game PID 5480, speed 1):

| check | result |
|---|---|
| load | `CIVVAR> on: 1 civic button(s) with 1 variant look(s)`, `CIVDLG> on` |
| Police hotkey 0x18 | list window "Elegir aspecto": Comisaría, Small Police Station; picked: its picture with the lot's cars and trees, "Precio: §500", "Aspecto 2 de 2" (owner_shots 06) |
| tool after OK | key `0x207EDC0E 0xB1D10002 0x94E2` |
| placed (posted click) | `RELOCATE> building placement (kind 0) at (53, 75): placed, price 520`; `find`: type 13130, rect (53, 75)..(55, 77), flags 0x104; funds 68,604 -> 68,084 |
| pictures | zoom 4, rotations 0-3, found by its frames (scores 0.81-0.92), and zoom 3 (owner_shots 04, 05) |
| VEH FAULT | both runs: only the start-up `0xC0000096 at SC3U.exe+0x84122` |

Both games were started by this session and stopped by PID. No BMP dump left (PNG only).

| picture (`owner_shots\`) | what |
|---|---|
| `01_jmyers_bsc_vs_bsc_plus_game_a.jpg`, `02_..._b.jpg` | per design the house with the BSC props and with BSC + game props as the game drew it (zoom 4 crops x2, boxed) |
| `03_sacramento_zoom4_boxed.jpg` | one whole zoom-4 dump: BSC + game houses boxed yellow, BSC-only cyan |
| `04_sc4_police_look_placed.jpg` | the SC4 Small Police Station look placed, rotations 0-3 |
| `05_sc4_police_look_zoom4_whole.jpg` | the whole dump around it |
| `06_police_list_window_sc4_look.jpg` | the Police list window with the SC4 look picked |

How it looks (01, 02): SC4's quarter shrubs and quarter bushes line the house fronts and the flower beds and cars of the
BSC pack stay. Lot textures (driveways, paths) are still not drawn: next stream sc4lottex. [Owner call: whether the game
props should be on by default when the game is given, as they are now.]

## 5. Not run, limits

- The folder input of Open SC4 game itself (a real click, as in sc4civ): the page test calls `rememberSc4Game` with the
  game's files read by the page's own `sourcesFrom`, then opens the .zip through `openSc4`.
- Other downloads than JMyers with the install (the I-M and DiegoDL lot-only packs place SC4's own buildings as props,
  round sc4pass2: still no building model to convert).
- A disc install: the rule that ignores the game folder's other top-level files knows the Steam names (`Intro.dat`,
  `Sound.dat`). [UNCERTAIN: other top-level `.dat` names of a disc install.]

## 6. Files

| file | change |
|---|---|
| `re/tools/sc4conv/sc4conv.py` | `--sc4`, the install as the last prop source, the "Props not found" wording |
| `re/tools/sc4conv/props.py` | `owner`, families pooled in `resolve`, `msrc` (the model's source) in `plan` / `placed_meshes` |
| `re/tools/bldimport/sc4web.js` | the same in the page, `installSource`, `sourcesFrom` (install picked with a download), `INSTALL_OTHER` |
| `re/tools/bldimport/classifier.html` | `rememberSc4Game`, `opt.sc4`, note lines, button titles |
| `re/tools/bldimport/webtest/sc4_baseprops_setup.py`, `sc4_baseprops.mjs` (new, `git add -f`) | the identity test |
| `re/tools/bldimport/webtest/pagetest.mjs`, `pagetest.js` | `--sc4with`, `--sc4remember`, the props-on count read from the entry |
| `re/tools/bldimport/webtest/run_all.sh` | 4 steps with `SC4INSTALL` + the BSC zip |
| `docs/buildings/importer/*` | `sync_css.py --publish` |
| `docs/buildings/index.html` | `make_docs.py` from the template |
| `re/analysis/SC4_FORMATS.md` | section 11, section 10.5 pointer |
| MAIN `verify/bldpack/work/guide_template.html` (gitignored) | Lot props: the game as a source, the numbers, the FAQ line |
