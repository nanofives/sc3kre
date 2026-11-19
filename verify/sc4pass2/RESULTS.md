# sc4pass2 results (round 2026-11-19f): SC4 conversion, second pass (more packs)

**Verdict: the converter and the importer page now read the three new downloads, and the page stays byte-identical
to the Python route.** The Global Office Center tower converts (class 6700 commercial dense high wealth, 4x4 lot,
251 m); its ploppable and landmark lots are named and left for later. The two lot-only packs convert to nothing,
say so in one plain report that names every missing building (DiegoDL: 23 buildings and the readme's 20 download
links; I-M: a blank placeholder model and its 6 lots), write nothing, and the page shows no card and keeps Install
off. `run_all.sh` passes **18 of 18 steps** (the 14 existing ones unchanged, 4 new). Converting lot props from the BSC
pack is feasible in Python, heavy in the page (section 4). **The tower grew in Berlin by the first autosave** (2.4
game-run minutes, commercial churn `anarchy_com=5000`), among the stock towers and a little taller than the tallest
stock one (section 5). Sacramento and Europolis gave it no lot (no dense commercial, no demand).

Before this round all three packs gave "0 buildings": GOC and DiegoDL exemplars are the TEXT form (`EQZT1###`, not
read), the I-M exemplars store single values as one-element lists, and the tower's zoom-5 views are 12 / 14 tiles,
refused by the one-mesh reader.

Nothing from the packs is in the repository or `docs/`. `SC4_FORMATS.md` section 8 holds layouts and counts only.
Pictures in `owner_shots/` are local, for the owner.

## 1. Global Office Center (the first tall, non-house building)

| question | answer (evidence) |
|---|---|
| **reprojection on a tall narrow building** | Works. Zoom-5 views are not one box mesh but 12 (S, N) / 14 (W, E) meshes, each with its own 256 x 256 texture. A joint fit (one projection per view, one pixel offset per tile) fits every vertex to 0.59 px or better, and the tile offsets fall on a 256-pixel grid to 0.15 px: the BAT cut one screen render into tiles. The converter pastes them into one canvas per view (512 x 1536 / 512 x 1792) and from there it is a normal view (`views.compose_tiles`). The composed picture has no seams (`owner_shots/01_tower_views_vs_stock.jpg`). Camera as for JMyers: elevation 45.0 degrees, azimuth 22.5 off the axis, 6.97-6.99 px/m. |
| **frames** | SC3 frames 32 x 90 (zoom 0) to 512 x 1434 (zoom 4). Stock 4009, the 6700 4x4 base: 256 x 465 at zoom 3 against the tower's 256 x 717. The tower is 251 m, about 1.5 times the stock tower's frame. |
| **night textures** | Ignored. 82 FSH at instance + 0x8000, the same sizes as the 82 day textures; no mesh names them. SC3 has no night view. |
| **class (office)** | **6700 Commercial dense, high wealth.** SC3 has one commercial zone for shops and offices and two commercial wealths (batgrow.CLASS_LABEL), so the tool maps SC4 $ to low (5100 / 5700 / 6300) and $$ / $$$ to high (5500 / 6100 / 6700), density by jobs: <= 100 light, <= 1000 medium, else dense. The tower: wealth 3, CO$$ 3500 + CO$$$ 3000 = 6500 jobs -> dense. These cuts are a rule of this tool, not a measured equivalence [owner call]. SC4 service (CS) maps the same way, industry to dirty / clean / farm. |
| **lot size** | Footprint 55.1 x 38.4 m -> 4x4 (the smallest square with both sides <= n x 16 m). The SC4 lot is 4 x 3 tiles (64 x 48 m), so the SC3 lot is one row deeper. Class 6700 has a 4x4 stock base (4009). A building needing more than 4x4 gets no class (SC3 lots are 1x1 to 4x4): 8 of DiegoDL's 23 lots are longer than 4 tiles on a side (5x3 to 4x8); their buildings' footprints decide once the models are there. |
| **growable vs ploppable vs landmark** | The growable lot's building has the model. The "Jobs" and "Landmark" lots hold a modelless building (occupant size 1 x 0 x 1, Maxis cohort parent) and the tower as a lot prop (prop exemplar 9355BAB7, the same model key). The converter converts the growable and lists the two others in `x_sc4.versions` and in the report: "the ploppable lot Global Office Center Jobs (building Global Office Center - Jobs), the landmark lot Global Office Center Landmark (building Global Office Center - Landmark): ... listed for later, not converted". Landmark = the building has property 0x2781284F ([85, 75] on this one). |

## 2. Lot-only packs

| pack | what the converter finds | what it says (the same text in the page) |
|---|---|---|
| DiegoDL Growable Pack 2019 | 46 files, all text exemplars: 23 lots, 23 buildings whose models (21 groups) no file holds | "No building converted: this download holds no building models, only 23 lots and 23 building descriptions. 23 buildings need their model from a separate download: 555 California Street, Ariel East at 2628 Broadway, ... Willoughby Tower. The download's readme lists the models to get: 555 California Street (https://community.simtropolis.com/...), ..." (20 links, from the readme's "Dependency Listing") |
| I-M manufacturers lots | 1 building `!I§§--1542 jobs` on `blank.SC4Model` (20 views, every texel transparent), 6 lots of 9 x 8 showing 1,105 lot props | "No building converted: ... only 6 lots and 1 building description. 6 lots use !I§§--1542 jobs, a blank placeholder building: what shows in SimCity 4 is lot props (SimCity 4's own buildings or other downloads), not in this download: I§§-1542-hanjin, ... I§§-1542-uniglory" |

- `sc4conv.py` prints the report and writes nothing (no folder, no `models.json`), exit code 3. `--notes-json` writes
  the lines and the missing list.
- The page (`sc4web.js convert`) returns no files and `empty: true`. `classifier.html` is not this task's file, so
  sc4web.js rewrites its note ("... Nothing was converted and nothing can be installed from it.") and its status
  line ("No building in <zip> can be converted: it holds no building models"); the grid is empty and Install / Save
  stay disabled (`owner_shots/02_page_lot_only_pack.jpg`). A cleaner branch inside classifier.html is an ask of its
  owner.
- A pack that converts some buildings and lacks others gets `x_sc4_missing` in `models.json` (name, exemplar,
  missing or blank, lots) and the same lines.

## 3. Tests

| check | result |
|---|---|
| JMyers pack, new converter against main's | 661 of 661 files byte-identical (the readers' changes do not touch it) |
| `sc4_packs.mjs` (new, after `sc4_packs_setup.py`) | **33 of 33**: 60 of 60 exemplars of the three packs (48 text form) read the same in JS and Python; the tower zip in JS: OBJ + MTL text, the 4 composed textures pixel for pixel, models.json byte for byte, file list, class / lot / tiles, the versions, the notes, folder = zip; render + pack from memory = `bldimport.py pack`: 11 game files + ids.json, 20 of 20 frames (tallest 1440 px); DiegoDL and I-M: nothing converted, notes and missing list = Python, folder = zip |
| `pagetest.mjs --case sc4empty` (new mode) | DiegoDL 4 of 4, I-M 4 of 4: no cards, Install / zip install / Save disabled, the note says nothing converts and names the buildings (and a readme link), the status line rewritten |
| `run_all.sh` (test slot, pristine `stage\release`, JMyers zip + folder, `stage\st_packs\sc4`) | **18 of 18 steps** (`work/run_all1.log`) |

## 4. BSC Common Dependencies Pack: can lot props be converted? (report only)

What it holds (`SC4_FORMATS.md` 8.5): one 1.64 GB LEX jar, 168 `.dat` files, 18,850 prop exemplars (type 0x1E), 1,837
prop families, 297,896 S3D and 492,103 FSH. **The prop models are the same S3D format** as buildings: 256,284 of the
S3D entries are the one-mesh 7-vertex box-and-picture; 27,680 one mesh of another shape (flat or crossed planes:
[UNCERTAIN: which props; not rendered]); 13,861 two or more meshes (tiles as in section 1, or several parts).

What the lots need from it:

| lot | prop rows | distinct prop ids | in the BSC pack | in neither the download nor BSC |
|---|---|---|---|---|
| Global Office Center (growable) | 28 | 9 (incl. the tower's own prop on the ploppable lots) | 0 | 8 (`2AC20000`-`2CB00000`) |
| I-M (6 lots) | 1,105 | 97 | 61 | 36 |

[UNCERTAIN: the unresolved ids are presumably SC4's own props in the game's `SimCity_1.dat`; no SC4 install was read.]

**Feasible, by this route:**
1. Read the lot's prop rows (kind 1: position, rotation, prop instance or family) as catalog.py already reads them.
2. Resolve each id against an index of the dependency packs the player has (exemplars only: 18,850, small), then load
   only the S3D + FSH of the props used.
3. Convert each prop like a building (views.load_views + compose_tiles) and place it in the building's OBJ at its lot
   position (SC4 lot metres map 1:1 to SC3's 16 m cells), so the props become part of the building's SC3 frames: SC3
   growables have no separate prop layer, the lot is one sprite.
4. Lot textures (kind 2 rows, 20 on the tower's lot) could be painted onto the ground mesh the same way.

**Costs and limits:**
- The SC3 lot is square and often larger than the SC4 lot (tower: 4x4 vs 4x3), and the converter centres the building:
  props must follow the building's offset, and the extra row stays lawn.
- Props seen from SC4's 45-degree camera get the same reprojection as buildings; flat props (crossed-plane trees,
  [UNCERTAIN: share not measured]) may look thin from SC3's 30 degrees.
- Props that are SC4's own (36 of 97 on I-M, 8 of 9 on the tower) need the player's SC4 install. Without it those
  stay empty.
- The page: the BSC jar is 1.64 GB deflated inside the zip; the page's zip reader inflates a member whole in memory,
  so it would need about 3.3 GB for zip + jar. A streaming index (read the jar's central directory, inflate only the
  .dat files, keep only exemplars until a prop is needed) is the way; about one round, plus the prop placement.
- Python: this report's scan read the 168 files one at a time (one file in memory), all S3D and FSH included.

## 5. In game

**The tower grew in Berlin by the first autosave (2.4 game-run minutes): 1 lot of 38000 at cells (155, 167), 4x4,
rotation 0, occupant class 6700**, in the downtown next to stock 4009 and other towers. It stood in all 10 saves of
that run (17.6 game-run minutes). Lever: sc3simrun churn `anarchy_res=5000` and **`anarchy_com=5000`** (the sample
pack's skyscraper lever, verify/bldpack/work/sky_lab.py), speed 4, autosave 150 s, windowed 1600 x 1000, posted input
only, test slot. Weight 1, demand not touched. `work/tower_lab.py` = bld_lab.py plus `anarchy_com`, zoom-2 pictures and
`--spot` (pictures of a lot grown in an earlier run). Faults: only the `0xC0000096 at SC3U.exe+0x84122` line every lab
run logs at start.

| run | city | result | why |
|---|---|---|---|
| tower1 | Sacramento | 0 lots, 4 saves | the city has no dense commercial at all (families 22 / 24: 0 buildings, `work/find_city.py`) |
| tower2 | Europolis | 0 lots, 14 saves, 25 min | 1,218 family-22 buildings, but in 25 minutes only 2 were rebuilt (both 4056) and no 4x4 lot came free |
| tower3 | Europolis with 3,760 free cells zoned dense commercial offline (city_write game-cell accessors, every network tile skipped, 296 free 4x4 squares; `work/zone_tower.py`) | 0 lots | the new zone got 0 buildings in 25 minutes and family 22 shrank 1,218 -> 1,123: no dense high-wealth commercial demand there |
| **tower4** | **Berlin** (170 family-22 buildings) | **1 lot at save 1, kept to save 10** | the camera hook missed the view, so no pictures in this run |
| tower8 | save 1 of tower4, pictures only (`--spot 157,169`) | 9 dumps | tower5-7 loaded save 10, dated 1 Jan 2085: the year's budget dialog covered the view and held the sim (a posted Enter and a posted click on its button did not close it); save 1 has no year end in the picture window |

Pictures (`owner_shots/`, local, phone portrait):

| file | what |
|---|---|
| `01_tower_views_vs_stock.jpg` | SC4's view S as composed from its 12 tiles; the 4 converted SC3 frames at zoom 3; stock 4031 (the tallest stock commercial building, 256 x 665) and 4009 (256 x 465) at the same scale. The tower's zoom-3 frame is 256 x 717: about 8% taller than 4031 and 54% taller than 4009 |
| `02_page_lot_only_pack.jpg` | the importer page on the DiegoDL zip: the note naming the 23 buildings and the readme's links, empty grid, Save off |
| `03_berlin_tower_zoom2.jpg` | Berlin at zoom 2, the tower boxed among the downtown towers |
| `04_berlin_tower_zoom3.jpg` | Berlin at zoom 3, the tower boxed (its top past the window) beside stock 4009 |

How it looks (from 03 / 04 and 01): the tower stands in scale with the stock towers (a little taller than the tallest
one), the glass reads as glass, the roof is seen from higher up than SC3's own roofs (SC4's 45-degree camera), and
the lit side follows SC4's screen light, as for the houses (verify/sc4conv/RESULTS.md 6). Its 4x4 lot is plain lawn
around the base: the SC4 lot's plaza props and textures are not converted (section 4). Not checked: the four view
rotations in game (the four views are in shot 01, the same frames the game draws; the lab's rotation dumps are in
`runs/tower8/fd/`).

## Files

Repo (worktree `dev\sc4pass2\wt`, branch `child/sc4pass2`, nothing committed):
`re/tools/sc4conv/exemplar.py` (text exemplars), `catalog.py` (one-value lists, `others`), `views.py`
(`compose_tiles`, `model_state`), `sc4conv.py` (classes for commercial / industry, pack notes, readme dependency list,
versions, exit 3, `--notes-json`), `re/tools/bldimport/sc4web.js` (the same steps, readmes from the zip / folder, the
empty-pack note), `webtest/sc4_packs_setup.py` + `webtest/sc4_packs.mjs` (new, need `git add -f`), `webtest/pagetest.js`
+ `pagetest.mjs` (`--expect-empty`), `webtest/run_all.sh` (6th argument), `re/analysis/SC4_FORMATS.md` (section 8).

MAIN (local): `verify/sc4pass2/` (this file, `work/tower_lab.py` = bld_lab.py with commercial churn and zoom 2 shots,
`work/find_city.py`, `work/fam_counts.py`, `work/fam22_new.py`, `work/zone_tower.py`, `work/tallest.py`, `work/shots.py`, `work/game_shots.py`, logs, `runs/tower1-4, tower8`), `re/sessions/STATUS_sc4pass2.md`.

Whole suite: `test-slot bash re/tools/bldimport/webtest/run_all.sh <work> <pristine tree> <stage\kits> <JMyers .zip> <JMyers unpacked> <stage\st_packs\sc4>`.
